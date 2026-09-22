"""Beach geometry: the sign errors here point a beach at the wrong ocean."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from forecast.geometry import (
    SEAWARD_HALF_WIDTH,
    Blocker,
    Spot,
    blocked_sector,
    load,
    open_window,
    reaches,
)

SPOTS, BLOCKERS = load()
BY_ID = {s.id: s for s in SPOTS}


def test_every_beach_faces_the_ocean_not_the_bay():
    """The bug this catches actually happened: Coronado came out facing 71°.

    All three beaches are on the ocean side of the peninsula, so every seaward
    normal must point into the western half of the compass. A normal pointing
    east is pointing at San Diego Bay, through several miles of Coronado.
    """

    for spot in SPOTS:
        assert 180.0 < spot.normal < 320.0, f"{spot.id} faces {spot.normal:.0f}°"


def test_a_peninsula_shadow_does_not_close_again():
    """Point Loma runs north off the end of the chord; an island would not."""

    spot = BY_ID["coronado_center"]
    peninsula = next(b for b in BLOCKERS if b.continues)
    low, high = blocked_sector(spot, peninsula)
    assert high == pytest.approx(SEAWARD_HALF_WIDTH)  # runs to the arc edge

    island = next(b for b in BLOCKERS if not b.continues)
    low, high = blocked_sector(spot, island)
    assert -SEAWARD_HALF_WIDTH < low < high < SEAWARD_HALF_WIDTH  # closes both sides


def test_reaches_agrees_with_the_open_window():
    """Two independent paths to the same answer, checked every degree."""

    for spot in SPOTS:
        windows = open_window(spot, BLOCKERS)
        for whole in range(360):
            bearing = float(whole)
            inside = any(
                (lo <= bearing <= hi) if lo <= hi else (bearing >= lo or bearing <= hi)
                for lo, hi in windows
            )
            assert reaches(spot, BLOCKERS, bearing) == inside, (
                f"{spot.id} disagrees at {bearing:.0f}°"
            )


def test_nothing_arrives_from_behind_the_beach():
    for spot in SPOTS:
        behind = (spot.normal + 180.0) % 360.0
        assert not reaches(spot, BLOCKERS, behind)
        assert not reaches(spot, BLOCKERS, (spot.normal + 120.0) % 360.0)


def test_the_three_beaches_differ_the_way_the_geometry_says_they_must():
    """Distance from Point Loma orders the shadows; this pins that ordering.

    Breakers sits closest to the peninsula and loses the most; Gator sits
    furthest south and is the only one of the three that keeps any west swell.
    If a coordinate edit reverses this, something is wrong with the edit.
    """

    assert not reaches(BY_ID["nasni_breakers"], BLOCKERS, 260.0)
    assert not reaches(BY_ID["coronado_center"], BLOCKERS, 260.0)
    assert reaches(BY_ID["nab_gator"], BLOCKERS, 260.0)

    # And a mid-south swell reaches all three.
    for spot in SPOTS:
        assert reaches(spot, BLOCKERS, 215.0)


def test_verification_is_two_claims_and_a_claim_carries_its_provenance():
    """The predecessor of this test asserted every spot was unverified.

    That was the right test while every coordinate was a guess. Now that the
    three Coronado breaks are digitised it would just fail, so it is replaced
    by the rule that actually protects the same thing: a spot may say it is
    verified, but it may not say so anonymously. Anything claiming a digitised
    coordinate has to name the method and the date, and the two claims are
    tracked apart because they are separate facts about separate quantities.
    """

    data = json.loads(Path("forecast/spots.json").read_text())
    for entry in data["spots"]:
        assert "position_verified" in entry, f"{entry['id']} does not say"
        assert "shoreline_verified" in entry, f"{entry['id']} does not say"
        if entry["position_verified"] or entry["shoreline_verified"]:
            provenance = entry.get("provenance", {})
            assert provenance.get("method"), f"{entry['id']} claims verified with no method"
            assert provenance.get("date"), f"{entry['id']} claims verified with no date"

    # Breakers and Gator are still estimates. Scoped out is not the same as good.
    assert not BY_ID["nasni_breakers"].position_verified
    assert not BY_ID["nab_gator"].position_verified

    # And `verified` stays the conservative reading: the north break has a
    # digitised position and a spliced chord, so it is not simply "verified".
    assert BY_ID["coronado_north"].position_verified
    assert not BY_ID["coronado_north"].shoreline_verified
    assert not BY_ID["coronado_north"].verified
    assert BY_ID["coronado_center"].verified


def _rotate_chord(spot: Spot, degrees: float) -> Spot:
    """The same spot with its shoreline chord pivoted about its midpoint."""

    (la1, lo1), (la2, lo2) = spot.shoreline
    mid_la, mid_lo = (la1 + la2) / 2.0, (lo1 + lo2) / 2.0
    scale = math.cos(math.radians(mid_la))
    turn = math.radians(degrees)
    moved = []
    for la, lo in spot.shoreline:
        x, y = (lo - mid_lo) * scale, la - mid_la
        moved.append(
            (
                mid_la + (-x * math.sin(turn) + y * math.cos(turn)),
                mid_lo + (x * math.cos(turn) + y * math.sin(turn)) / scale,
            )
        )
    return Spot(
        spot.id, spot.name, spot.position, (moved[0], moved[1]),
        spot.position_verified, spot.shoreline_verified,
    )


def _swell_window(spot: Spot) -> tuple[float, float]:
    """The WEST window — the one whose far edge is the Point Loma tip.

    Named by its blocker rather than by an angle band, because there are three
    windows now and two of them sit inside 180-300 degrees. The old version
    took the first match in that band and would silently return the 6-degree
    channel between the Coronado Islands, which moves for entirely different
    reasons than this one does.

    The window it skips is no longer "near-useless" either: measured on the
    three-year 46232 archive, arrivals from 100-190 degrees are 16.7% of rows
    and 11.6% of energy. It is skipped here because these tests are about the
    Point Loma edge, not because nothing arrives through it.
    """

    from forecast.geometry import swell_windows

    for window in swell_windows(spot, BLOCKERS):
        if "Point Loma" in window.high.source:
            return window.low.bearing, window.high.bearing
    raise AssertionError(f"{spot.id} has no window bounded by Point Loma")


def test_the_shoreline_chord_does_not_move_the_swell_window():
    """Measured, and it contradicts what this repository used to assert.

    `spots.json` claimed the chord "matters most" and that five degrees of
    chord error moved the window five degrees. It moves it by zero. Both edges
    of the swell-side window are blocker-derived — Point Loma to the west, the
    Coronado Islands to the east — so the seaward half-plane clip never binds
    there and the normal is irrelevant to which swell arrives.

    This matters beyond pedantry: it is why Coronado's north break keeps a
    trustworthy window despite an imagery splice that rotated its chord about
    19 degrees, and it is what says digitising effort belongs on positions and
    on the Point Loma tip rather than on chord angles.
    """

    for spot in SPOTS:
        base = _swell_window(spot)
        for error in (-10.0, -5.0, -2.0, 2.0, 5.0, 10.0):
            moved = _swell_window(_rotate_chord(spot, error))
            assert moved == pytest.approx(base, abs=1e-9), (
                f"{spot.id}: {error:+.0f}° of chord error moved the swell window"
            )


def test_but_position_does_move_the_swell_window():
    """The control for the test above.

    Chord-invariance would be an empty result if nothing moved the window —
    it would just mean the test is insensitive. Position moves it, on the same
    fixture, through the same code path.
    """

    for spot in SPOTS:
        before = _swell_window(spot)
        north = Spot(
            spot.id, spot.name,
            (spot.position[0] + 500.0 / 111_320.0, spot.position[1]),
            spot.shoreline, spot.position_verified, spot.shoreline_verified,
        )
        after = _swell_window(north)
        shift = abs(((after[1] - before[1] + 180.0) % 360.0) - 180.0)
        assert shift > 1.0, f"{spot.id}: 500 m moved the west edge only {shift:.2f}°"


def test_coronado_is_not_one_beach():
    """The project's own rule, applied to the beach it is named after.

    The west edge of the window IS the bearing to the Point Loma tip, and that
    bearing sweeps as you walk the sand. Across 2.8 km of Coronado the open
    window runs about 43° at the north break to 56° at the south — a spread
    comparable to the difference between the named beaches, which is the whole
    premise of the project. Any surface that prints one number for "Coronado"
    is averaging across this.
    """

    north = _swell_window(BY_ID["coronado_north"])
    center = _swell_window(BY_ID["coronado_center"])
    south = _swell_window(BY_ID["coronado_south"])

    widths = [(high - low) % 360.0 for low, high in (north, center, south)]
    assert widths[0] < widths[1] < widths[2], "distance from Point Loma must order them"
    assert max(widths) - min(widths) > 10.0, f"spread collapsed to {max(widths) - min(widths):.1f}°"

    # The west edge walks south-west along the beach, monotonically.
    assert north[1] < center[1] < south[1]


def test_a_digitised_position_sits_on_its_own_shoreline():
    """Catches a drift that had already happened.

    The estimated `coronado_central` carried a stored position 698 m off the
    perpendicular from its own shoreline chord: two independent guesses at the
    same place, disagreeing, with the position silently winning every blocked
    sector. Digitised spots derive the position from the chord midpoint, so
    this holds by construction — the test is here to keep it that way if
    someone adds an explicit `position` back.
    """

    for spot in SPOTS:
        if not spot.position_verified:
            continue
        (la1, lo1), (la2, lo2) = spot.shoreline
        scale = math.cos(math.radians(la1)) * 111_320.0
        ax, ay = 0.0, 0.0
        bx, by = (lo2 - lo1) * scale, (la2 - la1) * 111_320.0
        px, py = (spot.position[1] - lo1) * scale, (spot.position[0] - la1) * 111_320.0
        along = ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / ((bx - ax) ** 2 + (by - ay) ** 2)
        cx, cy = ax + along * (bx - ax), ay + along * (by - ay)
        offset = math.hypot(px - cx, py - cy)
        assert offset < 50.0, f"{spot.id}: position sits {offset:.0f} m off its own chord"
        assert 0.0 <= along <= 1.0, f"{spot.id}: position is off the end of its chord"


def test_blocker_entirely_behind_the_beach_is_ignored():
    spot = BY_ID["coronado_center"]
    inland = Blocker(name="downtown", a=(32.71, -117.16), b=(32.72, -117.15))
    assert blocked_sector(spot, inland) is None


def test_spots_file_documents_what_it_leaves_out():
    data = json.loads(Path("forecast/spots.json").read_text())
    assert data["_missing"], "the omissions list is part of the model"


# --- a rounded tip: the tangent is per observer -------------------------------

class TestTipOutline:
    """Charted 2026-09-22 (BRIEFING §26). The Point Loma tip is a rounded
    headland, and the breaks look at it from bearings 18 degrees apart, so
    each break's tangent lands on a different charted vertex. A single `a`
    was wrong by up to 0.67 degrees somewhere - as large as the correction."""

    def test_no_outline_means_a_is_the_edge_for_everyone(self):
        from forecast.geometry import Blocker

        b = Blocker("x", (32.0, -117.0), (32.1, -117.0))
        assert b.a_seen_from((32.5, -117.5)) == (32.0, -117.0)

    def test_the_tangent_is_taken_per_observer(self):
        """Two observers either side of a round tip see its two shoulders."""

        from forecast.geometry import Blocker

        tip = ((32.000, -117.000), (31.999, -117.001), (31.999, -116.999))
        b = Blocker("x", tip[0], (32.05, -117.0), "b", outline=tip)
        west = b.a_seen_from((32.02, -117.05))
        east = b.a_seen_from((32.02, -116.95))
        assert west != east

    def test_point_loma_hands_each_coronado_break_its_own_vertex(self):
        spots, blockers = load()
        loma = next(b for b in blockers if b.name == "Point Loma peninsula")
        assert loma.outline, "the tip should be a charted outline"
        seen = {s.id: loma.a_seen_from(s.position) for s in spots
                if s.id.startswith("coronado_")}
        assert len(set(seen.values())) == 3

    def test_no_blocker_is_standing_on_imagery_any_more(self):
        """The last imagery-derived blocker was the tip. If one comes back the
        surface's provenance line must name it, and this test says so first."""

        from forecast.geometry import geometry_provenance

        _, blockers = load()
        got = geometry_provenance(blockers)
        assert got["from_imagery"] == []
        assert "US4CA74M.000" in got["cells"]

    def test_the_break_positions_are_still_named_as_imagery(self):
        """With the tip charted, the only imagery left in the aperture is its
        observer end. It must still reach the surface's provenance line."""

        from forecast.geometry import geometry_line, geometry_provenance

        spots, blockers = load()
        coronado = [s for s in spots if s.id.startswith("coronado_")]
        got = geometry_provenance(blockers, coronado)
        assert got["breaks_from_imagery"] == [s.id for s in coronado]
        assert "imagery for the break positions" in geometry_line(blockers, coronado)
