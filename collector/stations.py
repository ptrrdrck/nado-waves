"""The station registry: which buoys the collector archives.

This is a collection list, not a ranking. It carries only what cannot be
derived — id, name, region, and prose. Which stations actually constrain the
swell reaching Coronado is computed from coordinates and geometry by
`forecast.siting`, and is deliberately not duplicated here.

It used to carry `launch_candidate`, a flag from the predecessor game marking
which buoys would host a per-buoy league. That was a product decision about
where players lived, and it survived the game by accident; measured against the
beach geometry, four of its six candidates sit 55-92 degrees off Coronado's
swell window. It is gone rather than repurposed, because a stale flag that
looks like a decision is worse than no flag.
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
    notes: str = ""


def load_stations(path: Path | None = None) -> list[Station]:
    payload = json.loads(Path(path or REGISTRY_PATH).read_text(encoding="utf-8"))
    stations = [
        Station(
            id=str(entry["id"]).upper(),
            name=entry.get("name", ""),
            region=entry.get("region", ""),
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
