"""Coverage diagnostics for the archive.

    python -m collector.report

This is not the scoring function — that is the next build step and belongs in
its own module (CLAUDE.md, "Build order"). This only answers the questions the
collector itself has to answer before a launch set can be chosen:

* Does this station actually publish water temperature, and how often?
* How big are the gaps?
* Does the quantity move? Section 2 of SPEC is load-bearing on water temp being
  forecastable but not solved; if day-over-day swings at a station are always
  near zero, that station is a boring league and should not launch.
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .archive import observations_path
from .ndbc import PRIMARY_COLUMN
from .run import DEFAULT_DATA_DIR
from .stations import load_stations, select


def daily_means(path: Path) -> tuple[dict[str, float], int, int]:
    """Mean water temperature per UTC day, plus (rows, rows with a value)."""

    buckets: dict[str, list[float]] = defaultdict(list)
    rows = 0
    with_value = 0
    primary = PRIMARY_COLUMN.lower()

    if not path.exists():
        return {}, 0, 0

    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows += 1
            raw = (row.get(primary) or "").strip()
            if not raw:
                continue
            try:
                value = float(raw)
            except ValueError:
                continue
            with_value += 1
            buckets[row["timestamp_utc"][:10]].append(value)

    return (
        {day: statistics.fmean(values) for day, values in buckets.items()},
        rows,
        with_value,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report archive coverage per station.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--stations", help="Comma-separated station ids.")
    args = parser.parse_args(argv)

    stations = select(
        load_stations(), args.stations.split(",") if args.stations else None
    )

    print(f"Archive coverage as of {datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ}")
    print()
    print(
        f"{'Station':<8} {'Rows':>7} {'WTMP':>7} {'Cov':>6} {'Days':>6} "
        f"{'Median |Δday|':>14} {'Max |Δday|':>11}  Span"
    )
    print("-" * 96)

    for station in stations:
        means, rows, with_value = daily_means(
            observations_path(args.data_dir, station.id)
        )
        days = sorted(means)
        deltas = [
            abs(means[b] - means[a])
            for a, b in zip(days, days[1:])
            if (
                datetime.strptime(b, "%Y-%m-%d") - datetime.strptime(a, "%Y-%m-%d")
            ).days == 1
        ]
        coverage = f"{100 * with_value / rows:.0f}%" if rows else "—"
        median = f"{statistics.median(deltas):.2f}C" if deltas else "—"
        largest = f"{max(deltas):.2f}C" if deltas else "—"
        span = f"{days[0]} .. {days[-1]}" if days else "no data yet"
        print(
            f"{station.id:<8} {rows:>7} {with_value:>7} {coverage:>6} {len(days):>6} "
            f"{median:>14} {largest:>11}  {span}"
        )

    print()
    print(
        "Δday is the change in daily mean water temperature between consecutive days —"
    )
    print(
        "the spread a persistence baseline has to beat. Stations with a flat Δday"
    )
    print("distribution make dull leagues; prefer the ones that move.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
