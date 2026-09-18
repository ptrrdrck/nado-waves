"""Which buoys constrain the swell that can actually reach Coronado.

Run: ``python -m forecast.siting``

The station registry was inherited from *beat-the-buoy*, where stations were
chosen to be **leagues** — one buoy per stretch of populated coast, picked so
that a player in Santa Monica had somewhere to play. That is a product
criterion for a game that is dead. It says nothing about whether a buoy
observes the swell that reaches Coronado Central, and four of the six stations
it marked sit 55 to 92 degrees off Coronado's window.

This module replaces it with the only criterion this project can defend:
**does swell that enters a Coronado break's window pass over this buoy?**

The test is one line of geometry. A swell arriving at a break from bearing
``theta`` travelled the ray that leaves the break at bearing ``theta``, so a
buoy lies on some ray into the window exactly when *its own bearing from the
break* falls inside that break's swell-side window (``geometry.swell_window``).
No fitting, no waves — the same "right or wrong" standard as `geometry`.

Roles fall out of that one number:

``WINDOW``    the buoy's bearing from at least one break lies inside that
              break's swell window. Swell reaching that break crossed it.
``EDGE``      outside every window, but within `EDGE_DEGREES` of one. Useful
              upstream, and the first thing to re-check when a tip coordinate
              moves — `Point Loma is worth ~1 degree per 100 m`.
``CONTRAST``  the bearing falls inside a sector Point Loma or the Islands block
              from the centre break. These buoys measure the energy Coronado
              **cannot** receive, which is what makes them the control rather
              than useless: an aperture model that respects the geometry should
              track a WINDOW buoy and decouple from a CONTRAST one.
``OFF_AXIS``  no bearing relationship to the window at all.
``SENTINEL``  North Pacific, thousands of km upstream. Classified by region and
              not by aperture on purpose: their value is travel time, not
              direction, and the aperture test is meaningless at that range.
``UNPLACED``  no usable coordinates yet, so no claim either way.

FALSIFIED, and left here so it is not re-derived: a stronger-looking test —
"how much of the break's window can the buoy itself see, unblocked?" — carries
**no information whatsoever**. Point Loma and the Coronado Islands subtend only
a few degrees from any offshore buoy and none of it lands in the 201-260 band,
so all ten placed stations score the full window to within 0.1 degrees,
including the ones 90 degrees off axis. The blockers shadow the *beaches*, not
the buoys. Discrimination comes from the corridor test above and nowhere else;
`tests/test_siting.py` pins the null so it stays killed.

Coordinates come from `data/station_metadata.csv`, which `collector.metadata`
fetches from NDBC. They are never typed in here — a buoy this module cannot
place is reported UNPLACED rather than guessed at.
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

from collector.stations import Station, load_stations
from .geometry import Blocker, Spot, blocked_sector, load, swell_window, _relative
from .swell import great_circle_km, initial_bearing

METADATA_FILE = Path(__file__).resolve().parent.parent / "data" / "station_metadata.csv"

#: The three digitised Coronado breaks, north to south. Breakers and Gator are
#: deliberately excluded: their coordinates are still estimated (BRIEFING 2a),
#: and a station roster is not the place to launder a guess into a decision.
BREAKS = ("coronado_north", "coronado_center", "coronado_south")

#: The reference break — the Hotel del, the one BRIEFING quotes numbers at.
REFERENCE_BREAK = "coronado_center"

#: How close to a window edge still counts as EDGE rather than CONTRAST.
#: Set at 5 degrees because the Point Loma tip carries every west edge at about
#: 1 degree per 100 m, so anything inside 5 degrees is within the plausible
#: movement of the single coordinate all three windows hang on.
EDGE_DEGREES = 5.0

WINDOW = "window"
EDGE = "edge"
CONTRAST = "contrast"
OFF_AXIS = "off_axis"
SENTINEL = "sentinel"
UNPLACED = "unplaced"

#: Roles that answer "what does the swell reaching Coronado look like offshore?"
#: This is what replaces `launch_candidate` as the default analysis selection.
CONSTRAINING = (WINDOW, EDGE)


@dataclass(frozen=True)
class Siting:
    """One station's geometric relationship to Coronado's windows."""

    station: Station
    role: str
    latitude: float | None = None
    longitude: float | None = None
    #: Range and bearing from the reference break.
    range_km: float | None = None
    bearing: float | None = None
    #: Degrees from the nearest swell window, 0.0 when inside one. Per break,
    #: keyed by spot id — the spread across the three IS the finding in
    #: BRIEFING 2a, so it is never averaged away to one number.
    offsets: dict[str, float] | None = None
    #: Which breaks this buoy sits in the window of.
    in_window_of: tuple[str, ...] = ()
    #: Named blocker hiding it from the reference break, when there is one.
    blocked_by: str | None = None
    note: str = ""

    @property
    def constrains(self) -> bool:
        return self.role in CONSTRAINING


def load_coordinates(path: Path = METADATA_FILE) -> dict[str, tuple[float, float]]:
    """Usable NDBC coordinates, by station id.

    Rows `collector.metadata` marked unusable are dropped rather than trusted:
    it flags them precisely because a coordinate that failed its regional sanity
    check would put a buoy in the wrong ocean, and a forecast pulled for the
    wrong point looks fine.
    """

    if not path.exists():
        return {}
    found: dict[str, tuple[float, float]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if str(row.get("usable", "")).strip().lower() != "true":
                continue
            try:
                found[str(row["id"]).upper()] = (
                    float(row["latitude"]),
                    float(row["longitude"]),
                )
            except (TypeError, ValueError, KeyError):
                continue
    return found


def _offset(spot: Spot, blockers: list[Blocker], bearing: float) -> float:
    """Degrees from the spot's swell window; 0.0 when the bearing is inside."""

    best = 180.0
    for low, high in swell_window(spot, blockers):
        if low <= bearing <= high:
            return 0.0
        best = min(best, abs(_relative(bearing, low)), abs(_relative(bearing, high)))
    return best


def _blocker_hiding(spot: Spot, blockers: list[Blocker], bearing: float) -> str | None:
    offset = _relative(bearing, spot.normal)
    for blocker in blockers:
        sector = blocked_sector(spot, blocker)
        if sector and sector[0] <= offset <= sector[1]:
            return blocker.name
    return None


def site(station: Station, coordinates: dict[str, tuple[float, float]],
         spots: dict[str, Spot], blockers: list[Blocker]) -> Siting:
    """Classify one station. Never invents a coordinate it does not have."""

    if station.region == "sentinel_np":
        return Siting(
            station=station,
            role=SENTINEL,
            note="North Pacific sentinel: valued for travel time, not aperture.",
        )

    position = coordinates.get(station.id)
    if position is None:
        return Siting(
            station=station,
            role=UNPLACED,
            note="No usable coordinates in data/station_metadata.csv. Run "
                 "`python -m collector.metadata` (on Actions) before claiming "
                 "anything about this buoy.",
        )

    offsets = {
        break_id: _offset(spots[break_id], blockers,
                          initial_bearing(spots[break_id].position, position))
        for break_id in BREAKS
        if break_id in spots
    }
    inside = tuple(b for b, off in offsets.items() if off == 0.0)
    reference = spots[REFERENCE_BREAK]
    bearing = initial_bearing(reference.position, position)
    blocked_by = _blocker_hiding(reference, blockers, bearing)

    if inside:
        role = WINDOW
    elif offsets and min(offsets.values()) <= EDGE_DEGREES:
        role = EDGE
    elif blocked_by:
        role = CONTRAST
    else:
        role = OFF_AXIS

    return Siting(
        station=station,
        role=role,
        latitude=position[0],
        longitude=position[1],
        range_km=great_circle_km(reference.position, position),
        bearing=bearing,
        offsets=offsets,
        in_window_of=inside,
        blocked_by=blocked_by,
    )


def survey(stations: list[Station] | None = None,
           metadata_path: Path = METADATA_FILE) -> list[Siting]:
    """Every station, classified, ordered most-constraining first."""

    spot_list, blockers = load()
    spots = {spot.id: spot for spot in spot_list}
    coordinates = load_coordinates(metadata_path)
    order = {WINDOW: 0, EDGE: 1, CONTRAST: 2, OFF_AXIS: 3, UNPLACED: 4, SENTINEL: 5}
    sitings = [
        site(station, coordinates, spots, blockers)
        for station in (stations if stations is not None else load_stations())
    ]
    return sorted(
        sitings,
        key=lambda s: (order[s.role], s.range_km if s.range_km is not None else 1e9),
    )


def constraining(stations: list[Station] | None = None,
                 metadata_path: Path = METADATA_FILE) -> list[Station]:
    """The default analysis set: stations on the swell's path into the window.

    This is the replacement for `[s for s in registry if s.launch_candidate]`.
    It is deliberately small. Being small is the point — the old filter's six
    stations included four that no swell reaching Coronado ever passes.
    """

    return [s.station for s in survey(stations, metadata_path) if s.constrains]


def describe(sitings: list[Siting]) -> list[str]:
    lines = [
        "Buoys by what they constrain about swell reaching Coronado's window",
        "",
        f"  reference break: {REFERENCE_BREAK}   "
        f"(offsets given for {'/'.join(b.split('_')[-1] for b in BREAKS)})",
        "",
        f"{'buoy':<7} {'name':<24} {'role':<9} {'km':>6} {'brg':>6} "
        f"{'off N':>6} {'off C':>6} {'off S':>6}",
        "-" * 80,
    ]
    for entry in sitings:
        if entry.offsets is None:
            lines.append(
                f"{entry.station.id:<7} {entry.station.name[:24]:<24} "
                f"{entry.role.upper():<9} {'—':>6} {'—':>6} {'—':>6} {'—':>6} {'—':>6}"
            )
            continue
        offs = " ".join(f"{entry.offsets.get(b, float('nan')):6.1f}" for b in BREAKS)
        lines.append(
            f"{entry.station.id:<7} {entry.station.name[:24]:<24} "
            f"{entry.role.upper():<9} {entry.range_km:6.1f} {entry.bearing:6.1f} {offs}"
        )

    lines.append("")
    for entry in sitings:
        if entry.role == WINDOW:
            lines.append(
                f"  {entry.station.id}: inside the window of "
                f"{', '.join(entry.in_window_of)} — swell reaching "
                f"{'those breaks' if len(entry.in_window_of) > 1 else 'that break'}"
                f" passed over it."
            )
        elif entry.role == EDGE:
            nearest = min(entry.offsets, key=entry.offsets.get)
            lines.append(
                f"  {entry.station.id}: {entry.offsets[nearest]:.1f}° outside "
                f"{nearest}'s window — upstream, and inside the movement one "
                f"tip coordinate could produce."
            )
        elif entry.role == CONTRAST:
            lines.append(
                f"  {entry.station.id}: behind {entry.blocked_by} from the "
                f"reference break — measures energy Coronado cannot receive."
            )
        elif entry.role == UNPLACED:
            lines.append(f"  {entry.station.id}: {entry.note}")

    constrain = [e for e in sitings if e.constrains]
    lines += [
        "",
        f"{len(constrain)} of {len(sitings)} stations constrain the window: "
        f"{', '.join(e.station.id for e in constrain) or '(none)'}",
        "",
        "This is geometry, not accuracy. It says which buoys OBSERVE the swell",
        "that can reach these breaks. Nothing here measures how well anything",
        "forecasts them — there is still no wave observation at any of the",
        "three beaches (CLAUDE.md, 'the rule that governs everything').",
    ]
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Station siting against Coronado's windows.")
    parser.add_argument("--metadata", type=Path, default=METADATA_FILE)
    parser.add_argument("--constraining", action="store_true",
                        help="Print only the ids of the constraining set.")
    args = parser.parse_args(argv)

    sitings = survey(metadata_path=args.metadata)
    if args.constraining:
        print("\n".join(e.station.id for e in sitings if e.constrains))
        return 0
    print("\n".join(describe(sitings)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
