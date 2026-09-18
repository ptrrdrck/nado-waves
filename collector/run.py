"""Collector entrypoint: fetch every station's rolling window and archive it.

    python -m collector.run [--stations 46222,46221] [--dry-run]

Run cadence is intentionally decoupled from data resolution. Each NDBC file
carries many hours of history, so four runs a day capture every hourly
observation with three-fold redundancy against a failed run, at roughly a sixth
of the Actions usage of an hourly job.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .archive import MergeResult, merge_station, utcnow_iso
from .common import DEFAULT_DATA_DIR, write_step_summary
from .health import build_status, write_status
from .ndbc import NdbcError, PRIMARY_COLUMN, fetch_station, parse_realtime2
from .stations import Station, load_stations, select


class StationOutcome:
    def __init__(self, station: Station):
        self.station = station
        self.result: MergeResult | None = None
        self.error: str | None = None
        self.fetched_rows = 0

    @property
    def ok(self) -> bool:
        return self.error is None


def collect_station(
    station: Station,
    data_dir: Path,
    *,
    timeout: float,
    retries: int,
    dry_run: bool,
    now: str,
    fetch=fetch_station,
) -> StationOutcome:
    outcome = StationOutcome(station)
    try:
        text = fetch(station.id, timeout=timeout, retries=retries)
        observations = parse_realtime2(text)
        if not observations:
            raise NdbcError(f"{station.id}: file fetched but contained no data rows")
        outcome.fetched_rows = len(observations)
        outcome.result = merge_station(
            data_dir,
            station.id,
            observations,
            primary_column=PRIMARY_COLUMN.lower(),
            now=now,
            dry_run=dry_run,
        )
    except NdbcError as exc:
        outcome.error = str(exc)
    except Exception as exc:  # noqa: BLE001 - one bad station must not stop the rest
        outcome.error = f"{station.id}: unexpected error: {exc.__class__.__name__}: {exc}"
    return outcome


def format_summary(outcomes: list[StationOutcome], now: str) -> str:
    lines = [
        f"## NDBC collection — {now}",
        "",
        "| Station | Name | Rows in file | New | Revised | Archived | Newest obs | Newest water temp |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for outcome in outcomes:
        station = outcome.station
        if outcome.result is None:
            lines.append(
                f"| {station.id} | {station.name} | — | — | — | — | "
                f"FAILED | {outcome.error} |"
            )
            continue
        result = outcome.result
        lines.append(
            f"| {station.id} | {station.name} | {outcome.fetched_rows} | {result.added} | "
            f"{result.revised + result.blanked} | {result.total_rows} | "
            f"{result.newest_timestamp or '—'} | {result.newest_primary_timestamp or 'none'} |"
        )

    failed = [o for o in outcomes if not o.ok]
    no_primary = [
        o for o in outcomes if o.ok and o.result and not o.result.newest_primary_timestamp
    ]
    lines.append("")
    lines.append(
        f"{len(outcomes) - len(failed)}/{len(outcomes)} stations collected; "
        f"{sum(o.result.added for o in outcomes if o.result)} new observations archived."
    )
    if no_primary:
        lines.append("")
        lines.append(
            "Stations reporting no water temperature (not viable as v1 leagues): "
            + ", ".join(o.station.id for o in no_primary)
        )
    if failed:
        lines.append("")
        lines.append("Failures:")
        lines.extend(f"- `{o.station.id}` {o.error}" for o in failed)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Archive NDBC observations.")
    parser.add_argument(
        "--stations",
        help="Comma-separated station ids. Default: every station in the registry.",
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and parse, report what would change, write nothing.",
    )
    args = parser.parse_args(argv)

    stations = select(
        load_stations(), args.stations.split(",") if args.stations else None
    )
    now = utcnow_iso()

    outcomes = [
        collect_station(
            station,
            args.data_dir,
            timeout=args.timeout,
            retries=args.retries,
            dry_run=args.dry_run,
            now=now,
        )
        for station in stations
    ]

    if not args.dry_run:
        # The app reads this to decide which buoys can take a call today, and
        # what to tell a player whose home buoy has gone dark.
        # The status file says what each buoy is FOR, not just whether it is
        # alive: a dark anchor and a dark off-axis buoy are different news.
        # Geometry failures must not take the collector down with them, so the
        # roles are best-effort and their absence reads as "unclassified".
        try:
            from forecast.siting import survey
            roles = {e.station.id: e.role for e in survey(stations)}
        except Exception as exc:  # pragma: no cover - geometry is not the job here
            print(f"siting unavailable, status roles omitted: {exc}")
            roles = {}
        write_status(
            args.data_dir, build_status(args.data_dir, stations, roles=roles)
        )

    summary = format_summary(outcomes, now)
    print(summary)
    write_step_summary(summary)

    for outcome in outcomes:
        if not outcome.ok:
            print(f"::warning title=NDBC station failed::{outcome.error}")

    added = sum(o.result.added for o in outcomes if o.result)
    print(f"::notice title=NDBC collection::{added} new observations archived")

    failed = [o for o in outcomes if not o.ok]
    if failed and len(failed) == len(outcomes):
        # Every station failed: NDBC is down, the URL shape changed, or the
        # runner has no network. That is a real outage, not a flaky buoy.
        print("::error title=NDBC collection failed::no station could be collected")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
