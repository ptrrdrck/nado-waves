"""Which directions can actually reach each beach.

Run: ``python -m forecast.geometry``

This is the first component of the Coronado forecaster and deliberately the
most boring one: it computes, from coordinates alone, the compass sectors a
swell can arrive from and still reach a given beach. No waves, no model, no
fitting. Geometry that is either right or wrong.

It exists because the offshore buoy does not share the beach's geometry.
46232 sits south-west of Point Loma with the peninsula behind it to the
north-east; Coronado sits *behind* that peninsula. Any forecast that carries
the buoy's energy to the beach without imposing the beach's own aperture will
deliver north-west swell that physically cannot arrive, on the majority of days
in the year.

Two ideas do all the work:

- **The seaward half-plane.** A beach can only be reached from within 90
  degrees either side of its shore normal. Swell from outside that is coming
  from behind the beach.
- **Blocked sectors.** Land between the beach and the open ocean removes a
  range of bearings. A peninsula differs from an island in that its shadow does
  not close again — hence `continues` in the spot file.

What is left is the open window. At Coronado that window is narrow and its edge
sits within a couple of degrees of the shore normal, which is why small errors
in incident direction have outsized consequences there. This module reports the
window; it does not yet say what happens to the energy inside it.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from .swell import great_circle_km, initial_bearing

SPOTS_FILE = Path(__file__).resolve().parent / "spots.json"

#: A beach receives nothing from behind itself. Half-width of the seaward arc.
SEAWARD_HALF_WIDTH = 90.0


@dataclass(frozen=True)
class Blocker:
    name: str
    a: tuple[float, float]
    b: tuple[float, float]
    #: "a" or "b" when the landmass continues past that endpoint instead of
    #: ending there — a peninsula rather than an island.
    continues: str | None = None


@dataclass(frozen=True)
class Spot:
    id: str
    name: str
    position: tuple[float, float]
    shoreline: tuple[tuple[float, float], tuple[float, float]]
    verified: bool
    notes: str = ""

    @property
    def shore_bearing(self) -> float:
        return initial_bearing(self.shoreline[0], self.shoreline[1])

    @property
    def normal(self) -> float:
        """Seaward normal.

        The shoreline chord runs north-west to south-east along this coast, so
        the seaward side is 90 degrees clockwise from it. Written as an explicit
        convention rather than an abs() or a min() because the sign is exactly
        the kind of thing that silently points a beach inland — an earlier
        version of this calculation put Coronado facing 71 degrees, into San
        Diego Bay.
        """

        return (self.shore_bearing + 90.0) % 360.0

    @property
    def seaward(self) -> tuple[float, float]:
        return (
            (self.normal - SEAWARD_HALF_WIDTH) % 360.0,
            (self.normal + SEAWARD_HALF_WIDTH) % 360.0,
        )


def load(path: Path = SPOTS_FILE) -> tuple[list[Spot], list[Blocker]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    spots = [
        Spot(
            id=s["id"],
            name=s["name"],
            position=tuple(s["position"]),
            shoreline=(tuple(s["shoreline"][0]), tuple(s["shoreline"][1])),
            verified=s.get("verified", False),
            notes=s.get("notes", ""),
        )
        for s in data["spots"]
    ]
    blockers = [
        Blocker(
            name=b["name"],
            a=tuple(b["a"]),
            b=tuple(b["b"]),
            continues=b.get("continues"),
        )
        for b in data["blockers"]
    ]
    return spots, blockers


def _relative(bearing: float, origin: float) -> float:
    """Bearing expressed as degrees clockwise from `origin`, in [-180, 180)."""

    return (bearing - origin + 180.0) % 360.0 - 180.0


def blocked_sector(spot: Spot, blocker: Blocker) -> tuple[float, float] | None:
    """The blocker's angular extent, in degrees relative to the shore normal.

    Working relative to the normal rather than in absolute compass degrees is
    what keeps the arithmetic free of wrap-around: the seaward arc is then just
    [-90, +90] and every comparison is ordinary.
    """

    ra = _relative(initial_bearing(spot.position, blocker.a), spot.normal)
    rb = _relative(initial_bearing(spot.position, blocker.b), spot.normal)
    low, high = sorted((ra, rb))

    if blocker.continues == "a":
        low, high = (low, SEAWARD_HALF_WIDTH) if ra > rb else (-SEAWARD_HALF_WIDTH, high)
    elif blocker.continues == "b":
        low, high = (low, SEAWARD_HALF_WIDTH) if rb > ra else (-SEAWARD_HALF_WIDTH, high)

    low = max(low, -SEAWARD_HALF_WIDTH)
    high = min(high, SEAWARD_HALF_WIDTH)
    return (low, high) if high > low else None


def open_window(spot: Spot, blockers: list[Blocker]) -> list[tuple[float, float]]:
    """Seaward arcs that no blocker covers, as absolute compass bearings."""

    cuts = [s for s in (blocked_sector(spot, b) for b in blockers) if s]
    cuts.sort()

    free: list[tuple[float, float]] = []
    cursor = -SEAWARD_HALF_WIDTH
    for low, high in cuts:
        if low > cursor:
            free.append((cursor, low))
        cursor = max(cursor, high)
    if cursor < SEAWARD_HALF_WIDTH:
        free.append((cursor, SEAWARD_HALF_WIDTH))

    return [
        ((spot.normal + lo) % 360.0, (spot.normal + hi) % 360.0)
        for lo, hi in free
        if hi - lo > 0.5  # slivers below half a degree are noise, not a window
    ]


def reaches(spot: Spot, blockers: list[Blocker], bearing: float) -> bool:
    """Can swell from this compass bearing reach the beach at all?"""

    offset = _relative(bearing, spot.normal)
    if abs(offset) > SEAWARD_HALF_WIDTH:
        return False
    for blocker in blockers:
        sector = blocked_sector(spot, blocker)
        if sector and sector[0] <= offset <= sector[1]:
            return False
    return True


def describe(spot: Spot, blockers: list[Blocker]) -> list[str]:
    lines = [
        f"{spot.name}  ({spot.id})",
        f"  shoreline runs {spot.shore_bearing:.0f}°, so the beach faces "
        f"{spot.normal:.0f}°"
        + ("" if spot.verified else "   [coordinates UNVERIFIED]"),
    ]
    for blocker in blockers:
        sector = blocked_sector(spot, blocker)
        distance = min(
            great_circle_km(spot.position, blocker.a),
            great_circle_km(spot.position, blocker.b),
        )
        if sector is None:
            lines.append(f"  {blocker.name:<22} outside the seaward arc ({distance:.1f} km)")
        else:
            lo = (spot.normal + sector[0]) % 360.0
            hi = (spot.normal + sector[1]) % 360.0
            lines.append(
                f"  {blocker.name:<22} blocks {lo:5.0f}°–{hi:5.0f}°   "
                f"({sector[1] - sector[0]:4.0f}° wide, {distance:.1f} km away)"
            )
    windows = open_window(spot, blockers)
    total = sum((hi - lo) % 360.0 for lo, hi in windows)
    for lo, hi in windows:
        edge = min(abs(_relative(lo, spot.normal)), abs(_relative(hi, spot.normal)))
        lines.append(
            f"  OPEN  {lo:5.0f}°–{hi:5.0f}°   ({(hi - lo) % 360.0:.0f}° wide; "
            f"nearest edge {edge:.0f}° from the shore normal)"
        )
    lines.append(f"  total open arc: {total:.0f}° of a possible 180°")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spots-file", type=Path, default=SPOTS_FILE)
    parser.add_argument("--bearing", type=float, help="Ask whether one bearing reaches each beach.")
    args = parser.parse_args(argv)

    spots, blockers = load(args.spots_file)
    for spot in spots:
        print("\n".join(describe(spot, blockers)))
        if args.bearing is not None:
            verdict = "REACHES" if reaches(spot, blockers, args.bearing) else "blocked"
            print(f"  swell from {args.bearing:.0f}°: {verdict}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
