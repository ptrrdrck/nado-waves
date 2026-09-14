"""The station registry.

Per-buoy leagues are structural, not cosmetic (SPEC section 5), so a station is
a first-class record from the first commit rather than a bare id in a list.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

REGISTRY_PATH = Path(__file__).with_name("stations.json")


@dataclass(frozen=True)
class Station:
    id: str
    name: str
    region: str = ""
    launch_candidate: bool = False
    notes: str = ""


def load_stations(path: Path | None = None) -> list[Station]:
    payload = json.loads(Path(path or REGISTRY_PATH).read_text(encoding="utf-8"))
    stations = [
        Station(
            id=str(entry["id"]).upper(),
            name=entry.get("name", ""),
            region=entry.get("region", ""),
            launch_candidate=bool(entry.get("launch_candidate", False)),
            notes=entry.get("notes", ""),
        )
        for entry in payload["stations"]
    ]

    seen: set[str] = set()
    for station in stations:
        if station.id in seen:
            raise ValueError(f"duplicate station id in registry: {station.id}")
        seen.add(station.id)

    return stations


def select(stations: list[Station], ids: list[str] | None) -> list[Station]:
    if not ids:
        return stations
    wanted = {value.strip().upper() for value in ids if value.strip()}
    chosen = [station for station in stations if station.id in wanted]
    unknown = wanted - {station.id for station in chosen}
    if unknown:
        raise ValueError(f"unknown station id(s): {', '.join(sorted(unknown))}")
    return chosen
