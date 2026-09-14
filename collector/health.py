"""Station liveness, and the status file the app reads.

A buoy going dark is a normal event, not an error: buoys drift, are pulled for
maintenance, and are retired. The product decision (SPEC section 5) is that a
dark buoy stays **discoverable** — it keeps its league page and its history, and
the app says plainly why it is not taking calls — rather than vanishing from the
list. That requires a machine-readable liveness signal, which is what
`data/station_status.json` is.

Two states must not be confused:

* **paused** — the buoy is dark at round-open time, so the round never opens.
* **void** — a round opened, and its resolving observation turned out missing
  (SPEC section 4). Void is scored (as a non-event, breaking no streaks); paused
  never becomes a round at all.

Liveness is derived from the archive on every run rather than hand-maintained in
the registry, because a hand-maintained flag goes stale exactly when it matters.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .archive import observations_path
from .common import ISO, parse_iso, to_iso, utcnow
from .ndbc import PRIMARY_COLUMN
from .stations import Station

#: Hours without an observation before a station is considered dark.
DEFAULT_MAX_AGE_HOURS = 48.0

STATUS_FILENAME = "station_status.json"

LIVE = "live"
DARK = "dark"
NEVER_SEEN = "never_seen"


def status_path(data_dir: Path) -> Path:
    return Path(data_dir) / STATUS_FILENAME


@dataclass
class StationHealth:
    station: Station
    rows: int = 0
    newest_observation: datetime | None = None
    newest_primary: datetime | None = None
    last_written: datetime | None = None
    missing_file: bool = False

    def age_hours(self, now: datetime) -> float | None:
        if self.newest_observation is None:
            return None
        return (now - self.newest_observation).total_seconds() / 3600.0

    def primary_age_hours(self, now: datetime) -> float | None:
        if self.newest_primary is None:
            return None
        return (now - self.newest_primary).total_seconds() / 3600.0

    def state(self, now: datetime, max_age_hours: float) -> str:
        if self.newest_observation is None:
            return NEVER_SEEN
        age = self.age_hours(now)
        return DARK if age is None or age > max_age_hours else LIVE

    def is_stale(self, now: datetime, max_age_hours: float) -> bool:
        return self.state(now, max_age_hours) != LIVE


def inspect_station(data_dir: Path, station: Station) -> StationHealth:
    health = StationHealth(station=station)
    path = observations_path(data_dir, station.id)
    if not path.exists():
        health.missing_file = True
        return health

    primary = PRIMARY_COLUMN.lower()
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            health.rows += 1
            timestamp = parse_iso(row.get("timestamp_utc"))
            if timestamp and (
                health.newest_observation is None
                or timestamp > health.newest_observation
            ):
                health.newest_observation = timestamp
            if timestamp and row.get(primary):
                if health.newest_primary is None or timestamp > health.newest_primary:
                    health.newest_primary = timestamp
            written = parse_iso(row.get("first_seen_utc"))
            if written and (health.last_written is None or written > health.last_written):
                health.last_written = written
    return health


def _paused_reason(health: StationHealth, state: str, now: datetime,
                   max_age_hours: float) -> str | None:
    """Player-facing wording. Says what happened and when, never "error"."""

    if state == NEVER_SEEN:
        return "This buoy has not reported since the archive began."
    if state == DARK:
        stopped = to_iso(health.newest_observation)
        return (
            f"This buoy stopped reporting on {stopped}. Rounds are paused until "
            "it comes back. Past results are still here."
        )
    primary_age = health.primary_age_hours(now)
    if primary_age is None:
        return (
            "This buoy reports, but not water temperature, so it cannot host a "
            "round."
        )
    if primary_age > max_age_hours:
        stopped = to_iso(health.newest_primary)
        return (
            f"This buoy is still reporting, but its last water temperature was "
            f"{stopped}. Rounds are paused until the sensor returns."
        )
    return None


def load_status(data_dir: Path) -> dict:
    path = status_path(data_dir)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def build_status(
    data_dir: Path,
    stations: list[Station],
    *,
    now: datetime | None = None,
    max_age_hours: float = DEFAULT_MAX_AGE_HOURS,
    previous: dict | None = None,
) -> dict:
    """Build the status document the app reads.

    `state_since_utc` is preserved across runs while a state holds, so the app
    can say "dark since the 1st" rather than "dark as of this morning". When a
    station goes dark, the moment it went dark is its last observation, not the
    moment we noticed.
    """

    now = now or utcnow()
    previous = previous if previous is not None else load_status(data_dir)
    prior = {entry["id"]: entry for entry in previous.get("stations", [])}

    entries = []
    for station in stations:
        health = inspect_station(data_dir, station)
        state = health.state(now, max_age_hours)
        reason = _paused_reason(health, state, now, max_age_hours)

        was = prior.get(station.id, {})
        if was.get("state") == state and was.get("state_since_utc"):
            state_since = was["state_since_utc"]
        elif state == DARK:
            state_since = to_iso(health.newest_observation)
        elif state == NEVER_SEEN:
            state_since = None
        else:
            state_since = now.strftime(ISO)

        entries.append(
            {
                "id": station.id,
                "name": station.name,
                "region": station.region,
                "launch_candidate": station.launch_candidate,
                "state": state,
                "state_since_utc": state_since,
                "rounds_paused": reason is not None,
                "paused_reason": reason,
                "newest_observation_utc": to_iso(health.newest_observation),
                "newest_water_temp_utc": to_iso(health.newest_primary),
                "observation_rows": health.rows,
            }
        )

    return {
        "generated_utc": now.strftime(ISO),
        "max_age_hours": max_age_hours,
        "stations": entries,
    }


def write_status(data_dir: Path, payload: dict) -> Path:
    path = status_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def newly_dark(payload: dict, *, now: datetime | None = None) -> list[dict]:
    """Stations that went dark recently enough to be worth an alert.

    A station dark for weeks is a known condition, already visible in the status
    file and the app. Re-alerting daily would train the owner to ignore the
    alert, which is the failure mode the dead-man check exists to prevent.
    """

    now = now or utcnow()
    window = payload.get("max_age_hours", DEFAULT_MAX_AGE_HOURS) * 2
    fresh = []
    for entry in payload.get("stations", []):
        if entry["state"] == LIVE:
            continue
        since = parse_iso(entry.get("state_since_utc"))
        if since is None or (now - since).total_seconds() / 3600.0 <= window:
            fresh.append(entry)
    return fresh
