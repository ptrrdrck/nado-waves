"""GFS-Wave station bulletins — the forecast, as it was published at the time.

This is the input for the forecast-error work (SPEC section 12). It is **not**
a game data source and nothing here may be wired into scoring: a GFS-Wave
bulletin is the public forecast, so it fails the second half of the CLAUDE.md
test ("absent from the public forecasts players would read") by definition.

Why this file exists at all: NCEP publishes, for every wave model cycle, a
plain-text bulletin at each NDBC station point. It carries total significant
wave height plus up to six *partitions* — separate wave trains, each with its
own height, peak period and direction — hourly out to +384h. That is the whole
forecast for our buoys, in a format the standard library can read, with no
GRIB or NetCDF dependency.

The part that decides the shape of the project: these cycles are **archived**,
not just served live. The NOAA Open Data bucket retains every cycle back to
2021-03 (probed 2026-09-13; 2021-03-15 is 404, 2021-03-25 is 200, consistent
with the GFS v16 wave implementation). Our buoy archive covers 2023-2025. The
overlap is three full years of forecast/observation pairs available *today* —
so forecast error can be measured now rather than after six months of
archiving forward. This is the opposite of the `collector/forecast.py`
situation, where history genuinely was unrecoverable.

Two conventions in the bulletin that are easy to get wrong:

- **Direction is the direction waves travel TOWARD**, not the direction they
  come from. NDBC's ``MWD`` is the opposite convention. Comparing the two
  without a 180-degree flip produces a clean, confident, completely wrong
  answer. ``from_direction`` does the flip; nothing else should.
- **Rows are stamped day-of-month and hour, not lead time.** A 16-day bulletin
  crosses a month boundary most of the time. Reconstructing the valid time
  means rolling the month forward whenever the day number goes backwards,
  which is what ``_valid_times`` does — and it cross-checks against the
  expected hourly cadence so a format change fails loudly instead of silently
  shifting every timestamp by a month.
"""

from __future__ import annotations

import http.client
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .ndbc import USER_AGENT

#: NOAA Open Data Dissemination bucket. Public, no credentials, no egress cost.
BASE_URL = "https://noaa-gfs-bdp-pds.s3.amazonaws.com"

#: Earliest cycle the bucket serves, established by probe rather than assumed.
#: Bracketed between 2021-03-15 (404) and 2021-03-25 (200).
ARCHIVE_STARTS = datetime(2021, 3, 25, tzinfo=timezone.utc)

MAX_PARTITIONS = 6

_LOCATION = re.compile(
    r"Location\s*:\s*(\S+)\s*\(\s*([\d.]+)([NS])\s+([\d.]+)([EW])\s*\)"
)
_CYCLE = re.compile(r"Cycle\s*:\s*(\d{8})\s+(\d{1,2})\s*UTC")


class BulletinError(RuntimeError):
    pass


@dataclass(frozen=True)
class Partition:
    """One wave train: a swell or the local wind sea."""

    hs_m: float
    tp_s: float
    #: Direction the train travels TOWARD, degrees true. See module docstring.
    toward_deg: int
    #: The bulletin's ``*`` marker: "wave generation due to local wind probable".
    wind_sea: bool

    @property
    def from_deg(self) -> int:
        return from_direction(self.toward_deg)


@dataclass(frozen=True)
class BulletinRow:
    valid_utc: datetime
    lead_hours: int
    hs_total_m: float
    #: Bulletin ``n``: fields with Hs > 0.05 m found in the 2-D spectrum.
    fields_found: int
    #: Bulletin ``x``: fields with Hs > 0.15 m that did NOT fit in the table.
    #: Non-zero means the six columns clipped a real wave train.
    fields_omitted: int
    partitions: tuple[Partition, ...]

    def largest(self) -> Partition | None:
        """The most energetic train, which is what a buoy's DPD/MWD reflects."""
        return max(self.partitions, key=lambda p: p.hs_m, default=None)

    def swell_from(self, low_deg: float, high_deg: float, min_period_s: float = 0.0):
        """Partitions arriving from a compass window, largest first.

        The window is inclusive and does not wrap; a south window (160-230) does
        not need to. Wind sea is not excluded here — a caller asking for a
        long-period south window has already excluded it by period.
        """
        chosen = [
            p
            for p in self.partitions
            if low_deg <= p.from_deg <= high_deg and p.tp_s >= min_period_s
        ]
        return sorted(chosen, key=lambda p: p.hs_m, reverse=True)


@dataclass(frozen=True)
class Bulletin:
    station_id: str
    latitude: float
    longitude: float
    cycle_utc: datetime
    rows: tuple[BulletinRow, ...]

    def at_lead(self, lead_hours: int) -> BulletinRow | None:
        for row in self.rows:
            if row.lead_hours == lead_hours:
                return row
        return None


def from_direction(toward_deg: float) -> int:
    """Flip a travel direction into the "coming from" convention NDBC uses."""
    return int(round(toward_deg + 180)) % 360


def bulletin_url(station_id: str, cycle: datetime) -> str:
    day = cycle.strftime("%Y%m%d")
    hour = f"{cycle.hour:02d}"
    return (
        f"{BASE_URL}/gfs.{day}/{hour}/wave/station/"
        f"bulls.t{hour}z/gfswave.{station_id}.bull"
    )


def fetch_bulletin(
    station_id: str,
    cycle: datetime,
    timeout: float = 60.0,
    opener=urllib.request.urlopen,
    attempts: int = 4,
    backoff: float = 2.0,
) -> Bulletin:
    """Fetch and parse one cycle for one station.

    A missing cycle raises rather than returning None: the caller backfilling a
    date range needs to distinguish "NCEP skipped this run" from "we forgot to
    ask", and an exception carrying the URL says which.

    Transport failures are retried with backoff; a 404 is not. Pulling a
    thousand 52 KB files over one connection pool reliably produces a few
    truncated reads, and losing a whole station's backfill to one of them is a
    waste of an hour.
    """
    url = bulletin_url(station_id, cycle)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            with opener(request, timeout=timeout) as response:
                payload = response.read().decode("utf-8", errors="replace")
            return parse_bulletin(payload)
        except urllib.error.HTTPError as error:
            # A 404 is an answer: NCEP did not run that cycle. Retrying it just
            # spends the budget that a genuinely flaky connection needs.
            raise BulletinError(f"{url}: HTTP {error.code}") from error
        except (urllib.error.URLError, OSError, http.client.HTTPException) as error:
            last = error
            if attempt + 1 < attempts:
                time.sleep(backoff * (2 ** attempt))
    raise BulletinError(f"{url}: {last}") from last


def parse_bulletin(text: str) -> Bulletin:
    lines = text.splitlines()

    station_id = latitude = longitude = None
    cycle = None
    for line in lines[:12]:
        match = _LOCATION.search(line)
        if match:
            station_id = match.group(1)
            latitude = float(match.group(2)) * (-1 if match.group(3) == "S" else 1)
            longitude = float(match.group(4)) * (-1 if match.group(5) == "W" else 1)
            continue
        match = _CYCLE.search(line)
        if match:
            cycle = datetime.strptime(match.group(1), "%Y%m%d").replace(
                hour=int(match.group(2)), tzinfo=timezone.utc
            )
    if station_id is None:
        raise BulletinError("no Location line; not a GFS-Wave station bulletin")
    if cycle is None:
        raise BulletinError("no Cycle line; cannot anchor valid times")

    parsed: list[tuple[int, int, float, int, int, tuple[Partition, ...]]] = []
    for line in lines:
        record = _parse_row(line)
        if record is not None:
            parsed.append(record)
    if not parsed:
        raise BulletinError("bulletin has no forecast rows")

    valid_times = _valid_times(cycle, [(day, hour) for day, hour, *_ in parsed])
    rows = tuple(
        BulletinRow(
            valid_utc=valid,
            lead_hours=int((valid - cycle).total_seconds() // 3600),
            hs_total_m=hs_total,
            fields_found=found,
            fields_omitted=omitted,
            partitions=partitions,
        )
        for valid, (_, _, hs_total, found, omitted, partitions) in zip(
            valid_times, parsed
        )
    )
    return Bulletin(
        station_id=station_id,
        latitude=latitude,
        longitude=longitude,
        cycle_utc=cycle,
        rows=rows,
    )


def _parse_row(line: str):
    """Return (day, hour, hs_total, n, x, partitions) or None if not a data row.

    Cells are delimited by ``|`` and fixed width, but this splits on the
    delimiter rather than slicing by column offset: NCEP has widened these
    tables before, and a split survives that where offsets do not.
    """
    if "|" not in line:
        return None
    cells = line.split("|")
    if len(cells) < 4:
        return None

    stamp = cells[1].split()
    if len(stamp) != 2:
        return None
    try:
        day, hour = int(stamp[0]), int(stamp[1])
    except ValueError:
        return None  # the "day &" / "hour" header rows land here
    if not (1 <= day <= 31 and 0 <= hour <= 23):
        return None

    totals = cells[2].split()
    if not totals:
        return None
    try:
        hs_total = float(totals[0])
        fields_found = int(totals[1]) if len(totals) > 1 else 0
        fields_omitted = int(totals[2]) if len(totals) > 2 else 0
    except ValueError:
        return None

    partitions = []
    for cell in cells[3 : 3 + MAX_PARTITIONS]:
        body = cell.strip()
        if not body:
            continue
        wind_sea = body.startswith("*")
        tokens = body.lstrip("*").split()
        if len(tokens) != 3:
            continue
        try:
            partitions.append(
                Partition(
                    hs_m=float(tokens[0]),
                    tp_s=float(tokens[1]),
                    toward_deg=int(round(float(tokens[2]))) % 360,
                    wind_sea=wind_sea,
                )
            )
        except ValueError:
            continue

    return day, hour, hs_total, fields_found, fields_omitted, tuple(partitions)


def _valid_times(cycle: datetime, stamps: list[tuple[int, int]]) -> list[datetime]:
    """Turn (day-of-month, hour) stamps into absolute UTC times.

    The bulletin never states the month. Rolling forward on a decreasing day
    number is the only way to recover it — and the only way to get it wrong is
    silently, so this also checks the reconstructed series is strictly
    increasing and never jumps more than a day.
    """
    times: list[datetime] = []
    year, month = cycle.year, cycle.month
    previous_day = None
    for day, hour in stamps:
        if previous_day is not None and day < previous_day:
            month += 1
            if month > 12:
                month = 1
                year += 1
        previous_day = day
        try:
            moment = datetime(year, month, day, hour, tzinfo=timezone.utc)
        except ValueError as error:
            raise BulletinError(f"impossible date {year}-{month}-{day}: {error}")
        if times:
            step = moment - times[-1]
            if step <= timedelta(0) or step > timedelta(days=1):
                raise BulletinError(
                    f"valid times not monotonic at {moment:%Y-%m-%dT%H}: step {step}"
                )
        times.append(moment)
    if times[0] < cycle:
        raise BulletinError(f"first row {times[0]} precedes cycle {cycle}")
    return times
