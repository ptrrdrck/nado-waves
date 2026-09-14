"""Merging fetched observations into the committed per-station archive.

Storage layout (all tracked in git, deliberately — see CLAUDE.md):

    data/observations/{STATION}.csv   one row per observation timestamp
    data/revisions/{STATION}.csv      every time NDBC changed a published value

Two rules make this archive trustworthy for baseline-relative scoring:

* ``first_seen_utc`` is stamped when the collector first stores a row and is
  never rewritten. It is the record of *what was known when*, which is what
  freezing a baseline at round open depends on (SPEC section 3).
* NDBC revises values after first publication. A revision overwrites the cell
  in the observations file (so the file always reflects the latest published
  truth) and appends a row to the revisions file (so the earlier value is never
  lost). A previously published value is never replaced by a missing one — the
  blanking is logged instead. Nothing is ever inferred, interpolated, or
  substituted.
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .ndbc import DATA_COLUMNS, Observation

OBSERVATION_FIELDS = ["timestamp_utc", "first_seen_utc"] + [
    column.lower() for column in DATA_COLUMNS
]

REVISION_FIELDS = [
    "timestamp_utc",
    "field",
    "old_value",
    "new_value",
    "observed_at_utc",
]


@dataclass
class MergeResult:
    station_id: str
    added: int = 0
    revised: int = 0
    blanked: int = 0
    total_rows: int = 0
    newest_timestamp: str | None = None
    newest_primary_timestamp: str | None = None

    @property
    def changed(self) -> bool:
        return bool(self.added or self.revised or self.blanked)


def observations_path(data_dir: Path, station_id: str) -> Path:
    return Path(data_dir) / "observations" / f"{station_id.upper()}.csv"


def revisions_path(data_dir: Path, station_id: str) -> Path:
    return Path(data_dir) / "revisions" / f"{station_id.upper()}.csv"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_rows(path: Path) -> dict[str, dict[str, str]]:
    """Read an observations file into {timestamp_utc: row}."""

    if not path.exists():
        return {}

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows: dict[str, dict[str, str]] = {}
        for row in reader:
            key = (row.get("timestamp_utc") or "").strip()
            if key:
                rows[key] = {field: (row.get(field) or "") for field in OBSERVATION_FIELDS}
        return rows


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    """Write atomically so an interrupted run can never truncate the archive."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})
    os.replace(temporary, path)


def append_revisions(path: Path, revisions: list[dict[str, str]]) -> None:
    if not revisions:
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVISION_FIELDS, lineterminator="\n")
        if not exists:
            writer.writeheader()
        for revision in revisions:
            writer.writerow(revision)


def merge_station(
    data_dir: Path,
    station_id: str,
    observations: list[Observation],
    *,
    primary_column: str = "wtmp",
    now: str | None = None,
    dry_run: bool = False,
) -> MergeResult:
    """Merge a freshly fetched rolling window into the station's archive."""

    station_id = station_id.upper()
    now = now or utcnow_iso()
    obs_path = observations_path(data_dir, station_id)
    rev_path = revisions_path(data_dir, station_id)

    stored = read_rows(obs_path)
    result = MergeResult(station_id=station_id)
    revisions: list[dict[str, str]] = []

    for observation in observations:
        key = observation.timestamp_utc
        existing = stored.get(key)

        if existing is None:
            row = {"timestamp_utc": key, "first_seen_utc": now}
            for column in DATA_COLUMNS:
                row[column.lower()] = observation.get(column)
            stored[key] = row
            result.added += 1
            continue

        for column in DATA_COLUMNS:
            name = column.lower()
            old_value = existing.get(name, "")
            new_value = observation.get(column)

            if old_value == new_value:
                continue

            if new_value == "":
                # NDBC dropped a value it had already published. Keep what we
                # captured and log the blanking; never discard observed data.
                result.blanked += 1
                revisions.append(
                    {
                        "timestamp_utc": key,
                        "field": name,
                        "old_value": old_value,
                        "new_value": "",
                        "observed_at_utc": now,
                    }
                )
                continue

            if old_value != "":
                result.revised += 1
                revisions.append(
                    {
                        "timestamp_utc": key,
                        "field": name,
                        "old_value": old_value,
                        "new_value": new_value,
                        "observed_at_utc": now,
                    }
                )
            else:
                # Was missing at first publication, now filled in by NDBC.
                result.revised += 1
                revisions.append(
                    {
                        "timestamp_utc": key,
                        "field": name,
                        "old_value": "",
                        "new_value": new_value,
                        "observed_at_utc": now,
                    }
                )

            existing[name] = new_value

    ordered = [stored[key] for key in sorted(stored)]
    result.total_rows = len(ordered)
    if ordered:
        result.newest_timestamp = ordered[-1]["timestamp_utc"]
        for row in reversed(ordered):
            if row.get(primary_column):
                result.newest_primary_timestamp = row["timestamp_utc"]
                break

    if not dry_run and (result.changed or not obs_path.exists()):
        _write_csv(obs_path, OBSERVATION_FIELDS, ordered)
        append_revisions(rev_path, revisions)

    return result
