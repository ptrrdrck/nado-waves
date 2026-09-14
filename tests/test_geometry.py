"""Beach geometry: the sign errors here point a beach at the wrong ocean."""

from __future__ import annotations

import json
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

    spot = BY_ID["coronado_central"]
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
    assert not reaches(BY_ID["coronado_central"], BLOCKERS, 260.0)
    assert reaches(BY_ID["nab_gator"], BLOCKERS, 260.0)

    # And a mid-south swell reaches all three.
    for spot in SPOTS:
        assert reaches(spot, BLOCKERS, 215.0)


def test_coordinates_are_flagged_unverified_until_someone_checks_them():
    """A guessed coordinate that quietly claims to be surveyed is the worst case.

    This test is meant to be deleted by whoever digitises real shoreline points
    and flips `verified` — until then it keeps the caveat load-bearing.
    """

    assert all(not s.verified for s in SPOTS)


def test_blocker_entirely_behind_the_beach_is_ignored():
    spot = BY_ID["coronado_central"]
    inland = Blocker(name="downtown", a=(32.71, -117.16), b=(32.72, -117.15))
    assert blocked_sector(spot, inland) is None


def test_spots_file_documents_what_it_leaves_out():
    data = json.loads(Path("forecast/spots.json").read_text())
    assert data["_missing"], "the omissions list is part of the model"
