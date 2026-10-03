"""GFS-Wave's own first hours, cycle after cycle: a model hindcast at the buoys.

Run: ``python -m collector.wavehindcast --start 2026-08-04 --end 2026-10-02``

Each 6-hourly cycle's leads 0-5 at 46047, 46086 and 46232, partitions and all,
so consecutive cycles tile time with the model's freshest hours. It is what
WAVEWATCH III said the sea WAS doing, and the model knows every hurricane NHC
tracked: its partitions say whether a train from a storm's bearing, at the
period its track predicts, was in the water when the buoys say it was
(`forecast.stormtrack`). A MODEL, so a cross-check on the attribution and
never evidence that a swell arrived — that is the buoys' job.

Stored apart from `data/wave_forecasts/` (00Z, daily leads, 2023-2025, what
`forecast.verify` reads) in ``data/wave_hindcast/{station}.csv`` with the same
columns, so nothing reading either file can mix them up. Resumable by cycle.

NOAA's bucket is reachable from a session (2026-10-02) and from Actions. A
cycle whose per-station files are missing is read from that cycle's tar, once
for all the stations missing from it (`collector.gfswave`).
"""

from __future__ import annotations

import argparse
import csv
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .common import DEFAULT_DATA_DIR, ISO, utcnow, write_step_summary
from .gfswave import BulletinError, fetch_bulletin, fetch_bulletins_from_tar
from .gfswave_backfill import DEFAULT_MIN_HS, FIELDS, read_existing, rows_for

STATIONS = ("46047", "46086", "46232")
CYCLE_HOURS = (0, 6, 12, 18)
LEADS = tuple(range(6))


def path_for(data_dir: Path, station: str) -> Path:
    return Path(data_dir) / "wave_hindcast" / f"{station}.csv"


def cycles(start: datetime, end: datetime) -> list[datetime]:
    out, day = [], start
    while day <= end:
        out.extend(day.replace(hour=h) for h in CYCLE_HOURS)
        day += timedelta(days=1)
    return [c for c in out if c <= end + timedelta(hours=18)]


def fetch_cycle(cycle: datetime, stations: list[str]) -> tuple[dict, list[str]]:
    """{station: bulletin} for one cycle, and what could not be had."""

    got, missing = {}, []
    for station in stations:
        try:
            got[station] = fetch_bulletin(station, cycle)
        except BulletinError as error:
            if error.args and "HTTP 404" not in str(error):
                missing.append(f"{station} {cycle:%Y-%m-%d %HZ}: {error}")
    rest = [s for s in stations if s not in got]
    if rest:
        try:
            got.update(fetch_bulletins_from_tar(rest, cycle))
        except BulletinError as error:
            missing.append(f"{cycle:%Y-%m-%d %HZ} tar: {error}")
        missing += [f"{s} {cycle:%Y-%m-%d %HZ}: not in the tar" for s in rest if s not in got]
    return got, missing


def run(data_dir: Path, start: datetime, end: datetime, workers: int = 6) -> str:
    existing = {s: read_existing(path_for(data_dir, s)) for s in STATIONS}
    wanted = [c for c in cycles(start, end)
              if c <= utcnow() - timedelta(hours=6)
              and any(c.strftime(ISO) not in existing[s][1] for s in STATIONS)]
    rows = {s: list(existing[s][0]) for s in STATIONS}
    failures: list[str] = []

    def work(cycle):
        need = [s for s in STATIONS if cycle.strftime(ISO) not in existing[s][1]]
        return fetch_cycle(cycle, need)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for got, missing in pool.map(work, wanted):
            failures += missing
            for station, bulletin in got.items():
                rows[station].extend(rows_for(bulletin, LEADS, DEFAULT_MIN_HS))
    for station in STATIONS:
        path = path_for(data_dir, station)
        path.parent.mkdir(parents=True, exist_ok=True)
        merged = sorted(rows[station], key=lambda r: (r["cycle_utc"], int(r["lead_h"]),
                                                      str(r["part_rank"])))
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(merged)
    return (f"GFS-Wave hindcast {start:%Y-%m-%d}..{end:%Y-%m-%d}: {len(wanted)} cycles fetched, "
            f"{len(failures)} gaps" + "".join(f"\n  - {f}" for f in failures[:10]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--start", default="2026-08-04")
    parser.add_argument("--end", default=utcnow().strftime("%Y-%m-%d"))
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args(argv)
    parse = lambda s: datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    text = run(args.data_dir, parse(args.start), parse(args.end), args.workers)
    print(text)
    write_step_summary(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
