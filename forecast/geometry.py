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
    #: Whether the endpoint that carries this blocker's edges has been
    #: digitised. Point Loma's tip is; the Coronado Islands are not. Measured
    #: on 2026-09-18: moving the islands 500 m west flips the open/shut answer
    #: on 20.6% of current swell hours and 10.8% of the 3-year archive, so
    #: which blocker forms an edge is not a footnote — it is the difference
    #: between a claim and a guess, and the surface has to say which it is.
    tip_verified: bool = False


@dataclass(frozen=True)
class Spot:
    id: str
    name: str
    position: tuple[float, float]
    shoreline: tuple[tuple[float, float], tuple[float, float]]
    #: Whether the POSITION has been digitised. This is the flag that governs
    #: whether the open window can be trusted: both edges of the swell-side
    #: window are blocker-derived, so the window is a function of position and
    #: the blockers, and not of the chord.
    position_verified: bool = False
    #: Whether the SHORELINE CHORD has been digitised. Separate because it is a
    #: separate claim about a separate quantity. The chord sets the normal, and
    #: the normal moves the window by exactly nothing — but it is what the
    #: "shadow edge sits one degree off the normal" figure is computed from,
    #: and what wind fetch and refraction will need. A spot can honestly have a
    #: verified position and an unverified chord; Coronado's north break does.
    shoreline_verified: bool = False
    notes: str = ""

    @property
    def verified(self) -> bool:
        """Fully verified — both claims, not either.

        Deliberately the conservative reading. Anything asking a spot a plain
        "are you verified?" gets a yes only when nothing about it is still a
        guess.
        """

        return self.position_verified and self.shoreline_verified

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


def _position(spot: dict) -> tuple[float, float]:
    """Where the spot is, defaulting to the midpoint of its shoreline chord.

    `position` is optional on purpose. It drives every blocked sector, so it is
    the load-bearing coordinate, and storing it separately from the chord it
    should lie on invites exactly one bug: the two drift apart and the window is
    computed for somewhere the beach is not. That had already happened — the
    estimated `coronado_central` carried a position 698 m off its own chord.
    Digitised breaks omit it and get the midpoint; the older estimates keep
    theirs, flagged unverified.
    """

    if "position" in spot:
        return tuple(spot["position"])
    (la1, lo1), (la2, lo2) = spot["shoreline"]
    return ((la1 + la2) / 2.0, (lo1 + lo2) / 2.0)


def load(path: Path = SPOTS_FILE) -> tuple[list[Spot], list[Blocker]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    spots = [
        Spot(
            id=s["id"],
            name=s["name"],
            position=_position(s),
            shoreline=(tuple(s["shoreline"][0]), tuple(s["shoreline"][1])),
            position_verified=s.get("position_verified", False),
            shoreline_verified=s.get("shoreline_verified", False),
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
            tip_verified=b.get("tip_verified", False),
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
    """Seaward arcs that no blocker covers, as absolute compass bearings.

    The bare-tuple view of `open_windows`, kept because most callers only want
    the numbers and every existing test is written against this shape.
    """

    return [(w.low.bearing, w.high.bearing) for w in open_windows(spot, blockers)]


#: An edge formed by the seaward half-plane rather than by land.
SEAWARD = "seaward limit"

#: Confidence tiers for a window edge or an arrival. There are deliberately
#: only two, and neither is a probability. "high" means every coordinate the
#: edge stands on has been digitised; "low" means at least one is an estimate.
#: Nothing here is calibrated against an observation, so a third tier would be
#: inventing precision the project has not earned — CLAUDE.md, the rule that
#: governs everything.
HIGH = "high"
LOW = "low"


@dataclass(frozen=True)
class Edge:
    """One end of an open window, and what it is standing on."""

    bearing: float
    #: The blocker whose endpoint sets this edge, or `SEAWARD`.
    source: str
    #: Both coordinates behind this edge are digitised. A bearing is drawn
    #: between two points, so an edge is only as good as the worse of them:
    #: a digitised Point Loma tip seen from an estimated break is still a
    #: guess, and so is a digitised break looking at an estimated island.
    verified: bool


@dataclass(frozen=True)
class Window:
    """An open arc, with provenance on both edges."""

    spot_id: str
    low: Edge
    high: Edge

    @property
    def span(self) -> float:
        return (self.high.bearing - self.low.bearing) % 360.0

    @property
    def confidence(self) -> str:
        return HIGH if (self.low.verified and self.high.verified) else LOW

    @property
    def unverified(self) -> list[str]:
        """Which sources make this window a guess. Empty when it is not."""

        return [e.source for e in (self.low, self.high) if not e.verified]


@dataclass(frozen=True)
class Arrival:
    """Whether one bearing reaches one spot, and how much to trust the answer.

    `reaches` is the ordinal claim this project actually makes. `confidence`
    says whether it rests on digitised coordinates or estimated ones, and
    `because` names the thing responsible either way, so a surface can show
    the reason rather than a bare verdict.
    """

    spot_id: str
    bearing: float
    reaches: bool
    confidence: str
    because: str

    @property
    def verified(self) -> bool:
        return self.confidence == HIGH


def _edge(spot: Spot, relative: float, blocker: Blocker | None) -> Edge:
    bearing = (spot.normal + relative) % 360.0
    if blocker is None:
        # The seaward clip is drawn from the normal, so it is the CHORD that
        # has to be digitised for it to be trustworthy - not the position.
        # The two flags govern different things (BRIEFING section 2a).
        return Edge(bearing, SEAWARD, spot.shoreline_verified)
    return Edge(bearing, blocker.name, blocker.tip_verified and spot.position_verified)


def open_windows(spot: Spot, blockers: list[Blocker]) -> list[Window]:
    """Open arcs, each carrying which blocker formed which edge.

    Same sweep as `open_window`, which now delegates here; the only addition is
    that the cursor remembers what moved it. That bookkeeping is the whole
    point: without it the surface can say a break is open but not whether the
    edge it is open to was digitised or guessed, and at these beaches those are
    very different statements.
    """

    cuts = []
    for blocker in blockers:
        sector = blocked_sector(spot, blocker)
        if sector:
            cuts.append((sector[0], sector[1], blocker))
    cuts.sort(key=lambda cut: cut[0])

    free: list[tuple[float, Blocker | None, float, Blocker | None]] = []
    cursor = -SEAWARD_HALF_WIDTH
    cursor_source: Blocker | None = None
    for low, high, blocker in cuts:
        if low > cursor:
            free.append((cursor, cursor_source, low, blocker))
        if high > cursor:
            cursor, cursor_source = high, blocker
    if cursor < SEAWARD_HALF_WIDTH:
        free.append((cursor, cursor_source, SEAWARD_HALF_WIDTH, None))

    return [
        Window(spot.id, _edge(spot, lo, lo_src), _edge(spot, hi, hi_src))
        for lo, lo_src, hi, hi_src in free
        if hi - lo > 0.5  # slivers below half a degree are noise, not a window
    ]


def blocked_by(spot: Spot, blockers: list[Blocker], bearing: float) -> Blocker | None:
    """Which blocker stops this bearing, or None if nothing does."""

    offset = _relative(bearing, spot.normal)
    if abs(offset) > SEAWARD_HALF_WIDTH:
        return None
    for blocker in blockers:
        sector = blocked_sector(spot, blocker)
        if sector and sector[0] <= offset <= sector[1]:
            return blocker
    return None


def arrival(spot: Spot, blockers: list[Blocker], bearing: float) -> Arrival:
    """The full verdict for one bearing at one spot, with its confidence.

    Blocked and open are not symmetric, and the asymmetry is the reason this
    returns a record rather than a bool. A blocked bearing is standing on the
    one blocker that stops it. An open bearing is standing on BOTH edges of the
    window it sits in, because either of them moving could close it. So a
    shadow cast by a digitised headland is a high-confidence "no" even at a
    spot whose other edge is a guess, while an open verdict inherits the worse
    of the two edges.
    """

    offset = _relative(bearing, spot.normal)
    if abs(offset) > SEAWARD_HALF_WIDTH:
        return Arrival(
            spot.id, bearing, False,
            HIGH if spot.shoreline_verified else LOW,
            "behind the beach",
        )

    blocker = blocked_by(spot, blockers, bearing)
    if blocker is not None:
        confidence = HIGH if (blocker.tip_verified and spot.position_verified) else LOW
        return Arrival(spot.id, bearing, False, confidence, blocker.name)

    for window in open_windows(spot, blockers):
        if _within(bearing, window):
            sources = " and ".join(dict.fromkeys([window.low.source, window.high.source]))
            return Arrival(spot.id, bearing, True, window.confidence, f"open between {sources}")

    # Not inside any window and not blocked: only reachable through the
    # sub-degree slivers open_windows discards. Treat that as no window.
    return Arrival(spot.id, bearing, True, LOW, "open, but only through a sliver window")


def _within(bearing: float, window: Window) -> bool:
    return ((bearing - window.low.bearing) % 360.0) <= window.span


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


def _provenance(spot: Spot) -> str:
    """Say which of the two coordinate claims is standing on a digitised point.

    Four states, not two, and the distinction is not cosmetic: a spot with a
    verified position has a trustworthy WINDOW even if its chord is a guess,
    because the window does not come from the chord. Collapsing that to one
    "unverified" label would either throw away a good window or quietly claim a
    normal nobody has checked.
    """

    if spot.position_verified and spot.shoreline_verified:
        return "coordinates digitised"
    if spot.position_verified:
        return "position digitised; CHORD UNVERIFIED, so the normal is a guess"
    if spot.shoreline_verified:
        return "chord digitised; POSITION UNVERIFIED, so the window is a guess"
    return "coordinates UNVERIFIED"


def describe(spot: Spot, blockers: list[Blocker]) -> list[str]:
    lines = [
        f"{spot.name}  ({spot.id})",
        f"  shoreline runs {spot.shore_bearing:.0f}°, so the beach faces "
        f"{spot.normal:.0f}°   [{_provenance(spot)}]",
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
