"""Pull archived GFS-Wave cycles into a compact, verifiable forecast archive.

Run: ``python -m collector.gfswave_backfill --start 2023-01-01 --end 2025-12-31``

Each fetched bulletin is 52 KB of fixed-width text covering 385 hourly steps and
up to six partitions. Storing that verbatim for three years and a handful of
buoys would be hundreds of megabytes of whitespace, so this keeps only what the
error model in ``forecast.verify`` actually reads: a chosen grid of lead times, and
partitions at or above the bulletin's own 0.15 m significance threshold.

One row per (cycle, lead, partition). Direction is stored **already flipped**
into the "coming from" convention that NDBC uses, because the one thing
guaranteed to go wrong later is somebody flipping it a second time.

The archive is resumable: cycles already present are skipped unless ``--force``
is given, so an interrupted run is restarted by re-running the same command.
"""

from __future__ import annotations

import argparse
import csv
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .common import DEFAULT_DATA_DIR, ISO, utcnow, write_step_summary
from .gfswave import ARCHIVE_STARTS, BulletinError, fetch_bulletin

#: Daily steps to ten days. Beyond that the forecast is climatology with a
#: pressure pattern attached, and the bulletin's own skill is not the question.
DEFAULT_LEADS = tuple(range(0, 241, 24))

#: The bulletin omits fields below 0.15 m from its own overflow count; keeping
#: partitions under that is storing noise at full price.
DEFAULT_MIN_HS = 0.15

FIELDS = [
    "cycle_utc",
    "valid_utc",
    "lead_h",
    "hs_total_m",
    "n_fields",
    "n_omitted",
    "part_rank",
    "part_hs_m",
    "part_tp_s",
    "part_from_deg",
    "wind_sea",
]


def archive_path(data_dir: Path, station_id: str) -> Path:
    return data_dir / "wave_forecasts" / f"{station_id}.csv"


def read_existing(path: Path) -> tuple[list[dict], set[str]]:
    if not path.exists():
        return [], set()
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return rows, {row["cycle_utc"] for row in rows}


def rows_for(bulletin, leads, min_hs: float) -> list[dict]:
    cycle = bulletin.cycle_utc.strftime(ISO)
    out: list[dict] = []
    for lead in leads:
        row = bulletin.at_lead(lead)
        if row is None:
            continue
        base = {
            "cycle_utc": cycle,
            "valid_utc": row.valid_utc.strftime(ISO),
            "lead_h": row.lead_hours,
            "hs_total_m": f"{row.hs_total_m:.2f}",
            "n_fields": row.fields_found,
            "n_omitted": row.fields_omitted,
        }
        kept = [p for p in row.partitions if p.hs_m >= min_hs]
        if not kept:
            # Flat sea still has to be recorded: an hour with no partition above
            # threshold is a real forecast, not a gap, and dropping it would let
            # the verifier silently score only the interesting days.
            out.append({**base, "part_rank": "", "part_hs_m": "", "part_tp_s": "",
                        "part_from_deg": "", "wind_sea": ""})
            continue
        for rank, partition in enumerate(kept):
            out.append({
                **base,
                "part_rank": rank,
                "part_hs_m": f"{partition.hs_m:.2f}",
                "part_tp_s": f"{partition.tp_s:.1f}",
                "part_from_deg": partition.from_deg,
                "wind_sea": "1" if partition.wind_sea else "0",
            })
    return out


def cycles_between(start: datetime, end: datetime, hours: list[int], step_days: int):
    day = start
    while day <= end:
        for hour in hours:
            moment = day.replace(hour=hour)
            if moment >= ARCHIVE_STARTS:
                yield moment
        day += timedelta(days=step_days)


def backfill_station(
    station_id: str,
    cycles: list[datetime],
    data_dir: Path,
    leads: tuple[int, ...],
    min_hs: float,
    workers: int,
    timeout: float,
    force: bool,
    dry_run: bool,
) -> dict:
    path = archive_path(data_dir, station_id)
    existing, have = read_existing(path)
    wanted = [c for c in cycles if force or c.strftime(ISO) not in have]
    if dry_run:
        return {"station": station_id, "wanted": len(wanted), "fetched": 0,
                "missing": 0, "rows": len(existing)}

    def work(cycle):
        try:
            return cycle, fetch_bulletin(station_id, cycle, timeout=timeout), None
        except BulletinError as error:
            return cycle, None, str(error)

    fetched: list[dict] = []
    missing: list[str] = []
    if wanted:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for cycle, bulletin, error in pool.map(work, wanted):
                if bulletin is None:
                    missing.append(f"{cycle.strftime(ISO)}: {error}")
                    continue
                if bulletin.station_id != station_id:
                    missing.append(
                        f"{cycle.strftime(ISO)}: bulletin is for "
                        f"{bulletin.station_id}, not {station_id}"
                    )
                    continue
                fetched.extend(rows_for(bulletin, leads, min_hs))

    if force:
        refreshed = {row["cycle_utc"] for row in fetched}
        existing = [row for row in existing if row["cycle_utc"] not in refreshed]
    merged = existing + fetched
    merged.sort(key=lambda row: (row["cycle_utc"], int(row["lead_h"]),
                                 str(row["part_rank"])))

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(merged)

    return {
        "station": station_id,
        "wanted": len(wanted),
        "fetched": len(wanted) - len(missing),
        "missing": len(missing),
        "missing_detail": missing[:5],
        "rows": len(merged),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--stations", default="46232,46224",
                        help="Comma-separated NDBC ids.")
    parser.add_argument("--start", default="2023-01-01")
    parser.add_argument("--end", default="2025-12-31")
    parser.add_argument("--cycles", default="0",
                        help="Comma-separated model cycle hours, e.g. 0,12.")
    parser.add_argument("--step-days", type=int, default=1)
    parser.add_argument("--leads", default=",".join(str(l) for l in DEFAULT_LEADS))
    parser.add_argument("--min-hs", type=float, default=DEFAULT_MIN_HS)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    start = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(args.end, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    hours = [int(h) for h in args.cycles.split(",") if h.strip()]
    leads = tuple(int(l) for l in args.leads.split(",") if l.strip())
    cycles = list(cycles_between(start, end, hours, args.step_days))

    lines = [f"GFS-Wave backfill {args.start}..{args.end}, {len(cycles)} cycles/station"]
    for station_id in [s.strip() for s in args.stations.split(",") if s.strip()]:
        summary = backfill_station(
            station_id, cycles, args.data_dir, leads, args.min_hs,
            args.workers, args.timeout, args.force, args.dry_run,
        )
        lines.append(
            f"  {summary['station']}: wanted {summary['wanted']}, "
            f"fetched {summary['fetched']}, missing {summary['missing']}, "
            f"rows now {summary['rows']}"
        )
        for detail in summary.get("missing_detail", []):
            lines.append(f"      - {detail}")
    text = "\n".join(lines)
    print(text)
    write_step_summary(f"### GFS-Wave backfill\n\n```\n{text}\n```")
    return 0


if __name__ == "__main__":
    sys.exit(main())
