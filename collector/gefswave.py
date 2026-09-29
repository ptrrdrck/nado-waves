"""GEFS-Wave station bulletins — the model's own ensemble, at the buoy.

Findings in BRIEFING §35. Run: ``python -m collector.gefswave`` for the latest cycle, or
``python -m collector.gefswave --since 2023-01-01 --until 2025-12-31`` to
backfill 00Z cycles. Appends to ``data/ensemble_forecasts/<station>.csv``.

What it is. GEFS-Wave is WAVEWATCH III run 31 times from the GEFS atmospheric
ensemble (a control and 30 perturbed members), four cycles a day. For every
NDBC station point NCEP publishes a plain-text bulletin of the ensemble's
statistics: Hs mean and spread, Tp mean and spread, 10 m wind mean and
spread, and the share of members above six Hs thresholds, 3-hourly to +240 h
and 6-hourly to +384 h. The bulletin's own footer defines the spread:
"Spread (standard deviation) of ensemble members".

What it is NOT. It carries **total Hs only** -- no partitions, no direction --
so it cannot be carried through a break's windows the way GFS-Wave's own
spectrum is. The members' partitions exist, in the per-member global grids
(`wave/gridded/`, 23 fields a member an hour), but reading them for one point
costs ~7 MB a member an hour, ~17 GB a cycle: probed 2026-09-29 and not used.
Its spread is the model disagreeing with itself; it knows nothing of the low
bias the model shares with every member (BRIEFING §5, §33), and ensembles are
commonly too narrow. `forecast.ensemblespread` measures both against 46232
before anything is drawn from it.

Where it lives. The NOAA Open Data bucket ``noaa-gefs-pds`` serves
``gefs.YYYYMMDD/HH/wave/station/gefs.wave.tHHz.bull_tar`` -- ~3.7 MB for all
240 stations -- back to at least 2020-10 (probed 2026-09-29), so three years of
history pair with the buoy archive today rather than after a season of
collecting. Standard library only, like the GFS-Wave collector.
"""

from __future__ import annotations

import argparse
import csv
import http.client
import re
import sys
import tarfile
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .common import DEFAULT_DATA_DIR, ISO
from .gfswave import BulletinError, _valid_times
from .ndbc import USER_AGENT

BASE_URL = "https://noaa-gefs-pds.s3.amazonaws.com"

#: The buoy every transform here is anchored on. Others ride the same tar for
#: free with --station, and the bucket keeps them all.
DEFAULT_STATIONS = ("46232",)

#: The thresholds the bulletin's six P(Hs>) columns are PRINTED for. Checked on
#: every parse, so a changed header fails loudly. They are NOT the thresholds
#: the columns hold: fitted 2026-09-29 against the ensemble's own mean and
#: spread over 12k rows, the column printed "2.00m" behaves as P(Hs > 1 m)
#: (rms 0.098) and "3.00m" as P(Hs > 2 m) (rms 0.068); "1.00m" is 1 on every
#: row; and the last three stay 0 even at a 3.2 m ± 0.5 mean, so theirs cannot
#: be read off this buoy. A label is not a validation of a mapping (the WW3
#: direction axis taught the same, BRIEFING §15). So the archive names the
#: columns by POSITION, and `forecast.ensemble` reads only the two measured.
THRESHOLDS_M = (1.0, 2.0, 3.0, 5.5, 7.0, 9.0)

#: The first cycle whose bulletin carries the spread and the exceedance
#: shares. Before it the rows held three numbers -- Hs, Tp and U10 means --
#: under the SAME thirteen-column header, so the header alone says nothing
#: about which format a file is in; the row width does. Bisected 2026-09-29:
#: 2026-02-25 06Z has four cells, 12Z thirteen.
SPREAD_STARTS = datetime(2026, 2, 25, 12, tzinfo=timezone.utc)

#: Only the leads the page and the report use are kept; the rest of the
#: bulletin (to +384 h) stays in the bucket, which keeps it.
MAX_LEAD_H = 240

FIELDS = (
    "cycle_utc", "valid_utc", "lead_h",
    "hs_mean_m", "hs_spread_m", "tp_mean_s", "tp_spread_s",
    "u10_mean_ms", "u10_spread_ms",
    *(f"p_col{k}" for k in range(1, len(THRESHOLDS_M) + 1)),
)

#: The longitude is printed signed AND lettered ("-117.421W"); the letter is
#: what decides the hemisphere, so the sign is dropped rather than doubled.
_LOCATION = re.compile(r"Location\s*:\s*(\S+)\s*\(\s*-?([\d.]+)([NS])\s+-?([\d.]+)([EW])\s*\)")
_CYCLE = re.compile(r"Cycle\s*:\s*(\d{8})\s+t?(\d{1,2})z?\s*UTC")
_THRESHOLD = re.compile(r"([\d.]+)m")


@dataclass(frozen=True)
class EnsembleRow:
    valid_utc: datetime
    lead_h: int
    hs_mean_m: float
    #: The ensemble's standard deviation, as the bulletin defines "spr". None
    #: before `SPREAD_STARTS`, when the bulletin printed the means alone.
    hs_spread_m: float | None
    tp_mean_s: float
    tp_spread_s: float | None
    u10_mean_ms: float
    u10_spread_ms: float | None
    #: The six exceedance shares, in the bulletin's column order -- NOT the
    #: order of `THRESHOLDS_M`'s labels; see there. () before `SPREAD_STARTS`.
    p_exceed: tuple[float, ...]


@dataclass(frozen=True)
class EnsembleBulletin:
    station_id: str
    latitude: float
    longitude: float
    cycle: datetime
    rows: tuple[EnsembleRow, ...]


def bulletin_tar_url(cycle: datetime) -> str:
    day = cycle.strftime("%Y%m%d")
    hour = f"{cycle.hour:02d}"
    return f"{BASE_URL}/gefs.{day}/{hour}/wave/station/gefs.wave.t{hour}z.bull_tar"


def parse_bulletin(text: str) -> EnsembleBulletin:
    lines = text.splitlines()
    station = lat = lon = cycle = None
    for line in lines[:6]:
        found = _LOCATION.search(line)
        if found:
            station = found.group(1)
            lat = float(found.group(2)) * (1 if found.group(3) == "N" else -1)
            lon = float(found.group(4)) * (1 if found.group(5) == "E" else -1)
        found = _CYCLE.search(line)
        if found:
            cycle = datetime.strptime(found.group(1), "%Y%m%d").replace(
                hour=int(found.group(2)), tzinfo=timezone.utc)
    if station is None or cycle is None:
        raise BulletinError("no Location or Cycle line in the header")

    header = next((ln for ln in lines if "hour" in ln and "m |" in ln), None)
    if header is None:
        raise BulletinError(f"{station}: no threshold row in the header")
    printed = tuple(float(v) for v in _THRESHOLD.findall(header.split("(m/s)")[-1]))
    if printed != THRESHOLDS_M:
        raise BulletinError(f"{station}: thresholds {printed}, expected {THRESHOLDS_M}")

    stamps, values = [], []
    for line in lines:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not re.fullmatch(r"\d{1,2} \d{2}", cells[0]):
            continue
        try:
            numbers = [float(c) for c in cells[1:]]
        except ValueError as error:
            raise BulletinError(f"{station}: unreadable row {line!r}") from error
        if len(numbers) == 3:
            # The means-only format: Hs, Tp, U10. Nothing is invented for the
            # columns it did not print.
            numbers = [numbers[0], None, numbers[1], None, numbers[2], None]
        elif len(numbers) != 12:
            raise BulletinError(f"{station}: a row of {len(numbers)} numbers: {line!r}")
        day, hour = (int(v) for v in cells[0].split())
        stamps.append((day, hour))
        values.append(numbers)
    if not stamps:
        raise BulletinError(f"{station}: no rows")

    rows = []
    for valid, v in zip(_valid_times(cycle, stamps), values):
        rows.append(EnsembleRow(
            valid_utc=valid, lead_h=int((valid - cycle).total_seconds() // 3600),
            hs_mean_m=v[0], hs_spread_m=v[1], tp_mean_s=v[2], tp_spread_s=v[3],
            u10_mean_ms=v[4], u10_spread_ms=v[5], p_exceed=tuple(v[6:12])))
    formats = {r.hs_spread_m is None for r in rows}
    if len(formats) > 1:
        raise BulletinError(f"{station}: rows of both formats in one bulletin")
    return EnsembleBulletin(station, lat, lon, cycle, tuple(rows))


def fetch_from_tar(station_ids, cycle: datetime, *, timeout: float = 120.0,
                   opener=urllib.request.urlopen, attempts: int = 3,
                   backoff: float = 2.0) -> dict[str, EnsembleBulletin]:
    """Several stations out of one cycle's tar, streamed, in one download.

    A 404 raises: for a backfill, "NCEP did not run it" and "not published
    yet" both mean no rows, and the caller decides which it was. Transport
    failures are retried.
    """

    url = bulletin_tar_url(cycle)
    wanted = {f"gefs.wave.{s}.bull" for s in station_ids}
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last: Exception | None = None
    for attempt in range(attempts):
        found: dict[str, EnsembleBulletin] = {}
        try:
            with opener(request, timeout=timeout) as response:
                with tarfile.open(fileobj=response, mode="r|") as archive:
                    for member in archive:
                        if member.name.lstrip("./") not in wanted:
                            continue
                        handle = archive.extractfile(member)
                        if handle is None:
                            continue
                        got = parse_bulletin(handle.read().decode("utf-8", errors="replace"))
                        found[got.station_id] = got
                        if len(found) == len(wanted):
                            break
            return found
        except urllib.error.HTTPError as error:
            raise BulletinError(f"{url}: HTTP {error.code}") from error
        except (urllib.error.URLError, OSError, tarfile.TarError,
                http.client.HTTPException) as error:
            last = error
            if attempt + 1 < attempts:
                time.sleep(backoff * (2 ** attempt))
    raise BulletinError(f"{url}: {last}") from last


def _cell(value: float | None) -> str:
    return "" if value is None else f"{value:g}"


def csv_rows(bulletin: EnsembleBulletin) -> list[dict]:
    out = []
    for r in bulletin.rows:
        if r.lead_h > MAX_LEAD_H:
            continue
        row = {"cycle_utc": bulletin.cycle.strftime(ISO), "valid_utc": r.valid_utc.strftime(ISO),
               "lead_h": str(r.lead_h), "hs_mean_m": _cell(r.hs_mean_m),
               "hs_spread_m": _cell(r.hs_spread_m), "tp_mean_s": _cell(r.tp_mean_s),
               "tp_spread_s": _cell(r.tp_spread_s), "u10_mean_ms": _cell(r.u10_mean_ms),
               "u10_spread_ms": _cell(r.u10_spread_ms)}
        names = FIELDS[-len(THRESHOLDS_M):]
        row.update({name: _cell(r.p_exceed[k] if r.p_exceed else None) for k, name in enumerate(names)})
        out.append(row)
    return out


def archive_path(station: str, data_dir: Path = DEFAULT_DATA_DIR) -> Path:
    return Path(data_dir) / "ensemble_forecasts" / f"{station}.csv"


def logged_cycles(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["cycle_utc"] for row in csv.DictReader(handle)}


def append(bulletins: list[EnsembleBulletin], path: Path) -> int:
    """Append each cycle not already in the file, in cycle order. Idempotent."""

    have = logged_cycles(path)
    fresh = sorted((b for b in bulletins if b.cycle.strftime(ISO) not in have),
                   key=lambda b: b.cycle)
    if not fresh:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    written = 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if new:
            writer.writeheader()
        for bulletin in fresh:
            rows = csv_rows(bulletin)
            writer.writerows(rows)
            written += len(rows)
    return written


def read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def latest_cycle(now: datetime | None = None, *, delay_h: int = 6) -> datetime:
    """The newest cycle that should be published: GEFS-Wave lands roughly five
    to six hours after its nominal time, like GFS-Wave."""

    moment = (now or datetime.now(timezone.utc)) - timedelta(hours=delay_h)
    return moment.replace(hour=moment.hour - moment.hour % 6, minute=0, second=0, microsecond=0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--station", action="append", dest="stations")
    parser.add_argument("--since", help="backfill 00Z cycles from this date (YYYY-MM-DD)")
    parser.add_argument("--until", help="... to this date, inclusive")
    parser.add_argument("--hours", default="0",
                        help="cycles per day to backfill, e.g. 0 or 0,6,12,18")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args(argv)
    stations = tuple(args.stations or DEFAULT_STATIONS)

    if args.since:
        start = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end = datetime.strptime(args.until, "%Y-%m-%d").replace(tzinfo=timezone.utc) \
            if args.until else start
        hours = sorted(int(h) for h in args.hours.split(","))
        cycles = [start + timedelta(days=d, hours=h)
                  for d in range((end - start).days + 1) for h in hours]
    else:
        # The newest published cycle, and the one before it in case the newest
        # is late: an idempotent append makes asking twice free.
        newest = latest_cycle()
        cycles = [newest - timedelta(hours=6), newest]

    have = {s: logged_cycles(archive_path(s, args.data_dir)) for s in stations}
    todo = [c for c in cycles if any(c.strftime(ISO) not in have[s] for s in stations)]

    got: dict[str, list[EnsembleBulletin]] = {s: [] for s in stations}
    missing: list[str] = []

    def one(cycle):
        try:
            return cycle, fetch_from_tar(stations, cycle), None
        except BulletinError as error:
            return cycle, {}, str(error)

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        for cycle, found, error in pool.map(one, todo):
            if error:
                missing.append(f"{cycle:%Y-%m-%dT%H}Z: {error}")
            for s in stations:
                if s in found:
                    got[s].append(found[s])
                elif not error:
                    missing.append(f"{cycle:%Y-%m-%dT%H}Z: {s} not in the tar")

    for s in stations:
        added = append(got[s], archive_path(s, args.data_dir))
        print(f"{s}: {len(got[s])} cycle(s) fetched, {added} row(s) added "
              f"to {archive_path(s, args.data_dir)}")
    for line in missing[:20]:
        print(f"  missing {line}")
    if len(missing) > 20:
        print(f"  ... and {len(missing) - 20} more")
    return 0 if any(got.values()) or not todo else 1


if __name__ == "__main__":
    sys.exit(main())
