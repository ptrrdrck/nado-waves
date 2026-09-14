"""Dead-man's check for the collector.

A silently dead collector is the worst failure mode in this project: the lost
days are unrecoverable and nothing in the app surfaces the problem until scoring
breaks months later (SPEC section 4, "Monitoring").

    python -m collector.staleness [--max-age-hours 48]

Exit code 0 means healthy, 1 means something needs a human. The check
deliberately distinguishes three cases:

* every station stale  -> the collector is dead. Always alert.
* a station newly dark -> that buoy just stopped. Alert once.
* a station long dark  -> already known, already shown as paused in the app.
  Reported, but not alerted: an alert that fires every day for a buoy that has
  been retired for a month is how alerts get ignored.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from .common import DEFAULT_DATA_DIR, to_iso, utcnow, write_step_summary
from .health import (
    DEFAULT_MAX_AGE_HOURS,
    LIVE,
    build_status,
    inspect_station,
    newly_dark,
)
from .stations import load_stations, select


def format_report(
    healths: list, now: datetime, max_age_hours: float
) -> tuple[str, list]:
    stale = [h for h in healths if h.is_stale(now, max_age_hours)]
    lines = [
        "| Station | Name | Rows | Newest observation | Age (h) | Newest water temp | Status |",
        "| --- | --- | ---: | --- | ---: | --- | --- |",
    ]
    for health in healths:
        age = health.age_hours(now)
        state = health.state(now, max_age_hours)
        status = "ok" if state == LIVE else state.replace("_", " ").upper()
        lines.append(
            f"| {health.station.id} | {health.station.name} | {health.rows} | "
            f"{to_iso(health.newest_observation) or '—'} | "
            f"{'—' if age is None else format(age, '.1f')} | "
            f"{to_iso(health.newest_primary) or 'none'} | {status} |"
        )

    header = [
        f"Checked {len(healths)} stations at {to_iso(now)} against a "
        f"{max_age_hours:.0f}h threshold.",
        "",
    ]

    if not stale:
        return "\n".join(header + ["All stations fresh.", ""] + lines), stale

    if len(stale) == len(healths):
        header.insert(
            0,
            "**Every station is stale — this looks like a dead collector, not a dead "
            "buoy.** Check that the scheduled workflow is still enabled (GitHub "
            "disables schedules after 60 days of repository inactivity) and that its "
            "recent runs succeeded.\n",
        )
    else:
        header.insert(
            0,
            f"**{len(stale)} of {len(healths)} stations are dark.** The collector is "
            "running, so these buoys are most likely offline or retired. They stay "
            "discoverable in the app with rounds paused; confirm on the NDBC station "
            "page before writing one off.\n",
        )
    return "\n".join(header + lines), stale


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Alert if observations have gone stale.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--max-age-hours", type=float, default=DEFAULT_MAX_AGE_HOURS)
    parser.add_argument("--stations", help="Comma-separated station ids to check.")
    parser.add_argument(
        "--output", type=Path, help="Also write the report here (for alerting steps)."
    )
    args = parser.parse_args(argv)

    stations = select(
        load_stations(), args.stations.split(",") if args.stations else None
    )
    now = utcnow()
    healths = [inspect_station(args.data_dir, station) for station in stations]
    report, stale = format_report(healths, now, args.max_age_hours)

    status = build_status(
        args.data_dir, stations, now=now, max_age_hours=args.max_age_hours
    )
    fresh_problems = newly_dark(status, now=now)
    collector_dead = len(stale) == len(healths) and healths

    known = [
        entry
        for entry in status["stations"]
        if entry["state"] != LIVE and entry not in fresh_problems
    ]
    if known:
        report += "\n\nKnown-dark buoys (already paused in the app, not re-alerting):\n"
        report += "\n".join(
            f"- `{entry['id']}` {entry['name']} — dark since "
            f"{entry['state_since_utc']}"
            for entry in known
        )

    print(report)
    write_step_summary("## Collector staleness check\n\n" + report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report + "\n", encoding="utf-8")

    if collector_dead:
        print("::error title=Collector staleness::no station has reported recently")
        return 1
    if fresh_problems:
        names = ", ".join(entry["id"] for entry in fresh_problems)
        print(f"::error title=Buoy went dark::{names}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
