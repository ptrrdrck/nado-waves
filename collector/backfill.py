"""Backfill years of NDBC history, for calibration only.

    python -m collector.backfill --years 3

Pulls `data/historical/stdmet/{STATION}h{YEAR}.txt.gz` and writes
`data/historical/{STATION}.csv`.

**This is not the system of record and never merges into `data/observations/`.**
Three reasons, and they are the whole design:

1. **Different data.** The historical archive is quality-controlled after the
   fact. `data/observations/` holds values *as first published*, stamped with
   `first_seen_utc`. A round is scored against what was known when it opened
   (SPEC section 3), so the live archive is the only thing that can resolve a
   round. Backfill calibrates the scoring function; it never settles a bet.
2. **Different missing-value convention.** Historical files use per-column
   numeric sentinels (`999.0`, `99.0`, `9999.0`), not `MM`. They look like real
   numbers. `collector.ndbc.is_missing` handles both — but a merged file would
   lose track of which convention produced which blank.
3. **Different durability.** The 45-day urgency does not apply here. NDBC keeps
   the historical archive indefinitely, so committing it is a convenience, not
   preservation. That is why this is allowed to be lossy where the live
   collector is not.

Because it is a convenience, it is deliberately **reduced**: downsampled to one
row per hour, and narrowed to the columns this project actually uses. A full
station-year is ~1.5 MB raw and there are ten stations; storing everything would
add tens of megabytes to the repository to answer questions nobody has asked.
Anything dropped can be re-fetched from NDBC, which is exactly not true of the
live archive.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .common import DEFAULT_DATA_DIR, ISO, utcnow, write_step_summary
from .ndbc import USER_AGENT, parse_realtime2
from .stations import Station, load_stations, select

HISTORICAL_URL = "https://www.ndbc.noaa.gov/data/historical/stdmet/{station}h{year}.txt.gz"

#: The columns this project uses.
#:
#: `dpd` and `mwd` are here because swell propagation is period-dependent and
#: directional: a 20-second swell crosses 3383 km in 2.5 days and a 13-second
#: one takes 3.9, and a swell aimed at Baja never reaches San Pedro. Testing a
#: sentinel buoy without period is asking a model to predict arrival without
#: knowing the speed — which is exactly the under-powered test that produced
#: the first, meaningless negative.
KEPT_COLUMNS = ("wtmp", "wvht", "dpd", "mwd", "atmp", "wspd", "wdir")

#: Every scalar in the standard meteorological file. Not for the committed
#: archive — the skill sweep fetches these into a scratch directory precisely so
#: the repository does not carry columns nobody plays.
ALL_COLUMNS = (
    "wdir", "wspd", "gst", "wvht", "dpd", "apd", "mwd",
    "pres", "atmp", "wtmp", "dewp",
)

HISTORICAL_FIELDS = ["timestamp_utc", *KEPT_COLUMNS]

MANIFEST_FIELDS = [
    "station_id",
    "year",
    "url",
    "retrieved_at_utc",
    "rows_parsed",
    "rows_kept",
    "span",
    "note",
]


class BackfillError(RuntimeError):
    pass


@dataclass
class YearResult:
    station_id: str
    year: int
    rows_parsed: int = 0
    rows_kept: int = 0
    span: str = ""
    note: str = ""

    @property
    def ok(self) -> bool:
        return not self.note


def fields_for(columns: tuple[str, ...]) -> list[str]:
    return ["timestamp_utc", *columns]


def historical_path(data_dir: Path, station_id: str) -> Path:
    return Path(data_dir) / "historical" / f"{station_id.upper()}.csv"


def manifest_path(data_dir: Path) -> Path:
    return Path(data_dir) / "historical" / "_manifest.csv"


def read_manifest(data_dir: Path) -> dict[tuple[str, int], dict]:
    path = manifest_path(data_dir)
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        return {
            (row["station_id"], int(row["year"])): row
            for row in csv.DictReader(handle)
            if row.get("station_id") and row.get("year", "").isdigit()
        }


def fetch_year(station_id: str, year: int, timeout: float = 120.0) -> str:
    url = HISTORICAL_URL.format(station=station_id.lower(), year=year)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise BackfillError(f"no archive published for {station_id} {year}") from exc
        raise BackfillError(f"HTTP {exc.code} {exc.reason}") from exc
    except Exception as exc:  # noqa: BLE001
        raise BackfillError(f"{exc.__class__.__name__}: {exc}") from exc

    try:
        raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
    except (OSError, EOFError) as exc:
        raise BackfillError(f"could not decompress: {exc}") from exc
    return raw.decode("utf-8", errors="replace")


def downsample_hourly(observations: list) -> list:
    """Collapse each clock hour to one row, MERGING the values within it.

    Not "keep the first record in the hour", which is what this did and which
    silently destroyed every wave observation at the moored buoys. Those report
    meteorology every 10 minutes but waves only once an hour, at :30, :40 or
    :50 — never at :00. Taking the first record therefore kept the wind and
    dropped the waves on every single hour: 46001 came back with 7 wave heights
    out of 22,467 rows from a file that plainly contains them.

    Merging takes the first non-empty value for each column across the hour, so
    a wave reading at :50 survives alongside a wind reading at :00. The row
    carries the hour's first timestamp; within-hour timing is not preserved,
    which is acceptable for a calibration archive and is why this file is not
    the system of record.
    """

    from .ndbc import Observation

    buckets: dict[str, list] = {}
    for observation in observations:
        hour = observation.timestamp.strftime("%Y-%m-%dT%H")
        buckets.setdefault(hour, []).append(observation)

    merged = []
    for hour in sorted(buckets):
        group = sorted(buckets[hour], key=lambda o: o.timestamp)
        values: dict[str, str] = {}
        for observation in group:
            for column, value in observation.values.items():
                if value and not values.get(column):
                    values[column] = value
        merged.append(Observation(timestamp=group[0].timestamp, values=values))
    return merged


def read_existing(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        return {
            row["timestamp_utc"]: row
            for row in csv.DictReader(handle)
            if row.get("timestamp_utc")
        }


def write_historical(
    data_dir: Path,
    station_id: str,
    rows: dict[str, dict[str, str]],
    columns: tuple[str, ...] = KEPT_COLUMNS,
) -> None:
    path = historical_path(data_dir, station_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields_for(columns)
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for key in sorted(rows):
            writer.writerow({f: rows[key].get(f, "") for f in fields})
    temporary.replace(path)


def backfill_year(
    data_dir: Path,
    station: Station,
    year: int,
    *,
    timeout: float = 120.0,
    dry_run: bool = False,
    columns: tuple[str, ...] = KEPT_COLUMNS,
    fetch=fetch_year,
) -> YearResult:
    result = YearResult(station_id=station.id, year=year)
    try:
        text = fetch(station.id, year, timeout=timeout)
    except BackfillError as exc:
        result.note = str(exc)
        return result

    observations = parse_realtime2(text)
    result.rows_parsed = len(observations)
    if not observations:
        result.note = "file fetched but contained no parseable rows"
        return result

    hourly = downsample_hourly(observations)
    result.rows_kept = len(hourly)
    result.span = (
        f"{hourly[0].timestamp:%Y-%m-%d} .. {hourly[-1].timestamp:%Y-%m-%d}"
    )

    if dry_run:
        return result

    path = historical_path(data_dir, station.id)
    rows = read_existing(path)
    for observation in hourly:
        row = {"timestamp_utc": observation.timestamp_utc}
        for column in columns:
            row[column] = observation.get(column)
        rows[observation.timestamp_utc] = row
    write_historical(data_dir, station.id, rows, columns)
    return result


def append_manifest(data_dir: Path, results: list[YearResult], retrieved_at: str) -> None:
    path = manifest_path(data_dir)
    existing = read_manifest(data_dir)
    for result in results:
        existing[(result.station_id, result.year)] = {
            "station_id": result.station_id,
            "year": str(result.year),
            "url": HISTORICAL_URL.format(station=result.station_id.lower(), year=result.year),
            "retrieved_at_utc": retrieved_at,
            "rows_parsed": str(result.rows_parsed),
            "rows_kept": str(result.rows_kept),
            "span": result.span,
            "note": result.note,
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS, lineterminator="\n")
        writer.writeheader()
        for key in sorted(existing):
            writer.writerow(existing[key])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Backfill NDBC history for calibration (not the system of record)."
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--stations", help="Comma-separated ids. Default: launch candidates.")
    parser.add_argument("--years", type=int, default=3, help="How many complete years back.")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--force", action="store_true", help="Re-fetch station-years already in the manifest.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--all-columns",
        action="store_true",
        help="Keep every scalar NDBC publishes. For analysis into a scratch "
             "--data-dir; never for the committed archive.",
    )
    args = parser.parse_args(argv)
    columns = ALL_COLUMNS if args.all_columns else KEPT_COLUMNS

    registry = load_stations()
    if args.stations:
        stations = select(registry, args.stations.split(","))
    else:
        stations = [s for s in registry if s.launch_candidate]

    last_complete = utcnow().year - 1
    years = list(range(last_complete - args.years + 1, last_complete + 1))
    manifest = read_manifest(args.data_dir)
    retrieved_at = utcnow().strftime(ISO)

    results: list[YearResult] = []
    skipped = 0
    for station in stations:
        for year in years:
            if not args.force and (station.id, year) in manifest:
                previous = manifest[(station.id, year)]
                if not previous.get("note"):
                    skipped += 1
                    continue
            results.append(
                backfill_year(
                    args.data_dir, station, year,
                    timeout=args.timeout, dry_run=args.dry_run, columns=columns,
                )
            )

    if not args.dry_run and results:
        append_manifest(args.data_dir, results, retrieved_at)

    lines = [
        "## Historical backfill (calibration only)",
        "",
        f"Stations: {', '.join(s.id for s in stations)}  ",
        f"Years: {years[0]}–{years[-1]}  ",
        f"Already present, skipped: {skipped}",
        "",
        "Downsampled to hourly and narrowed to "
        f"`{', '.join(columns)}`. NDBC keeps the full archive "
        "indefinitely, so anything dropped is re-fetchable — which is exactly "
        "not true of `data/observations/`.",
        "",
        "| Station | Year | Rows in file | Kept (hourly) | Span | Note |",
        "| --- | ---: | ---: | ---: | --- | --- |",
    ]
    for r in results:
        lines.append(
            f"| {r.station_id} | {r.year} | {r.rows_parsed} | {r.rows_kept} | "
            f"{r.span or '—'} | {r.note or ''} |"
        )
    report = "\n".join(lines)
    print(report)
    write_step_summary(report)

    failed = [r for r in results if not r.ok]
    for r in failed:
        print(f"::warning title=Backfill::{r.station_id} {r.year}: {r.note}")
    if results and len(failed) == len(results):
        print("::error title=Backfill::every station-year failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
