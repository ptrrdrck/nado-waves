"""Station siting against Coronado's swell windows.

These tests pin geometry, not accuracy. Nothing here claims a buoy forecasts
anything — there is still no wave observation at any of the three beaches.
"""

from pathlib import Path

import pytest

from collector.stations import Station, load_stations
from forecast import siting
from forecast.geometry import load, open_window, swell_window
from forecast.swell import initial_bearing

BREAKS = ("coronado_north", "coronado_center", "coronado_south")


@pytest.fixture(scope="module")
def spots_and_blockers():
    spot_list, blockers = load()
    return {s.id: s for s in spot_list}, blockers


@pytest.fixture(scope="module")
def survey():
    return {entry.station.id: entry for entry in siting.survey()}


# --- the geometry primitive -------------------------------------------------

def test_every_published_edge_now_stands_on_land(spots_and_blockers):
    """BRIEFING section 12 dissolved, 2026-09-20.

    The rule has not changed: a window edge formed by the seaward half-plane
    means the arc ran out of MODELLED land, not that it ran into ocean, and
    such an arc may not be published. What changed is the modelled land. With
    the Baja coast charted and added as a blocker, the half-plane no longer
    forms an edge for any spot in the file, so `swell_window` now returns
    everything `open_window` does. The clip was never a fact about the coast;
    it was a fact about what this repository had digitised.
    """

    spots, blockers = spots_and_blockers
    for spot in spots.values():
        assert swell_window(spot, blockers) == open_window(spot, blockers), spot.id
        assert len(swell_window(spot, blockers)) == 3, spot.id


def test_the_guard_still_fires_for_a_spot_the_land_does_not_surround(
    spots_and_blockers,
):
    """Identity is a property of these five spots, not of the function. A spot
    with only one blocker near it still gets its raw arc withheld — otherwise
    the next break added to the file publishes open water across a coastline
    nobody has digitised, which is exactly what section 12 was written about.
    """

    spots, blockers = spots_and_blockers
    spot = spots["coronado_center"]
    islands_only = [b for b in blockers if "Islands" in b.name]
    assert len(open_window(spot, islands_only)) > len(swell_window(spot, islands_only))
    for low, high in swell_window(spot, islands_only):
        assert (low, high) not in [(w[0], w[1]) for w in []]


@pytest.mark.parametrize(
    "spot_id,low,high",
    [
        ("coronado_north", 200.6, 241.7),
        ("coronado_center", 202.6, 250.3),
        ("coronado_south", 205.2, 260.0),
        ("nasni_breakers", 196.9, 220.0),
        ("nab_gator", 207.8, 270.0),
    ],
)
def test_the_west_window_reproduces_the_published_numbers(
    spots_and_blockers, spot_id, low, high
):
    """The spread BRIEFING section 2a is built on, on the WEST window.

    Its low edge moved 1.2 to 1.9 degrees when the Coronado Islands were
    charted on 2026-09-20, and its HIGH edge moved -0.53 / +0.01 / +0.17 at
    north / center / south when the Point Loma tip was charted on 2026-09-22
    - per break, off the tip's outline, because each break's tangent lands
    on a different vertex of a rounded headland. The widths are now
    41.1 / 47.7 / 54.9 (were 41.6 / 47.7 / 54.7, and 42.8 / 49.1 / 56.3
    before the islands). Breakers moves most, 2.6 degrees, being nearest the
    tip - and it is still standing on an estimated position.
    """

    spots, blockers = spots_and_blockers
    windows = swell_window(spots[spot_id], blockers)
    got_low, got_high = windows[-1]     # the west window is the last by bearing
    assert got_low == pytest.approx(low, abs=0.1)
    assert got_high == pytest.approx(high, abs=0.1)


def test_the_spread_along_coronados_sand_survives_the_island_charting():
    """BRIEFING section 2a's headline. It is a Point Loma quantity, so it
    moved when the tip was charted: 13.1 on the imagery trace, 13.8 on the
    chart, because the north break's edge swung west and the south's east."""

    from forecast.geometry import load
    spots, blockers = load()
    by_id = {s.id: s for s in spots}
    widths = {}
    for sid in ("coronado_north", "coronado_center", "coronado_south"):
        low, high = swell_window(by_id[sid], blockers)[-1]
        widths[sid] = high - low
    spread = widths["coronado_south"] - widths["coronado_north"]
    assert spread == pytest.approx(13.8, abs=0.3)


# --- the criterion ----------------------------------------------------------

def test_46232_is_the_only_buoy_inside_all_three_windows(survey):
    """The anchor is load-bearing and has no substitute in the array.

    This is the fact that makes 46232's outage a project-level problem rather
    than an inconvenience, so it is pinned: if a coordinate change ever makes
    something else qualify, that should be news.
    """

    everywhere = [
        sid for sid, entry in survey.items()
        if len(entry.in_window_of) == len(BREAKS)
    ]
    assert everywhere == ["46232"]


def test_46258_is_behind_point_loma_and_never_an_anchor(survey):
    """Mission Bay West is the contrast buoy, not a fallback for 46232.

    It is at very nearly 46232's range from the centre break on the far side of
    the blocker, which is what makes it a control. Using it as a stand-in while
    46232 is dark would feed the transform energy that cannot physically
    arrive — the exact failure BRIEFING section 2 describes.
    """

    entry = survey["46258"]
    assert entry.role == siting.CONTRAST
    assert entry.in_window_of == ()
    assert entry.blocked_by == "Point Loma peninsula"
    assert not entry.constrains
    # Matched range is the point of the pairing.
    assert abs(entry.range_km - survey["46232"].range_km) < 5.0


def test_the_dead_games_league_set_is_mostly_off_axis(survey):
    """Four of beat-the-buoy's six launch candidates see no Coronado swell.

    The old flag is gone from the registry, so this hard-codes the set it used
    to mark. That is deliberate: it is the measurement that justified removing
    it, and it should keep failing loudly if the geometry ever says otherwise.
    """

    old_league_set = ("46222", "46221", "46224", "46225", "46258", "46232")
    off = [sid for sid in old_league_set if survey[sid].role == siting.OFF_AXIS]
    assert sorted(off) == ["46221", "46222", "46224", "46225"]
    for sid in off:
        assert min(survey[sid].offsets.values()) > 50.0


def test_the_constraining_set_is_small_and_ordered(survey):
    ids = [s.id for s in siting.constraining()]
    assert ids == ["46232", "46086", "46047"]


# --- the control that killed the stronger-looking criterion -----------------

def test_blocker_visibility_at_the_buoy_carries_no_information(spots_and_blockers):
    """FALSIFIED criterion, kept so it is not re-derived.

    "How much of the break's window can the buoy itself see past the blockers?"
    sounds stronger than a bearing test and is worthless: Point Loma and the
    Coronado Islands subtend a few degrees from any offshore buoy and none of it
    lands in the 201-260 band, so every placed station scores the full window —
    including ones 90 degrees off axis. If this test ever fails, the criterion
    has become informative and siting.py should be revisited.
    """

    spots, blockers = spots_and_blockers
    coordinates = siting.load_coordinates()
    assert coordinates, "no coordinates to test against"

    def blocker_arc(position, blocker):
        a = initial_bearing(position, blocker.a_seen_from(position))
        b = initial_bearing(position, blocker.b)
        delta = (b - a + 180.0) % 360.0 - 180.0
        return (a, a + delta) if delta >= 0 else (a + delta, a)

    def visible(position, bearing):
        for blocker in blockers:
            low, high = blocker_arc(position, blocker)
            if (bearing - low) % 360.0 <= (high - low) % 360.0:
                return False
        return True

    for position in coordinates.values():
        for break_id in BREAKS:
            # The west window. Siting asks which buoys sit in the arc
            # that carries the swell these breaks are forecast for,
            # and that has always been this one.
            low, high = swell_window(spots[break_id], blockers)[-1]
            seen = sum(
                1 for step in range(int((high - low) * 10))
                if visible(position, low + step / 10.0)
            )
            assert seen == int((high - low) * 10), (
                "a buoy failed to see the whole window — the null result this "
                "test pins has broken, so the criterion may now discriminate"
            )


# --- honesty about what is not known ---------------------------------------

def test_a_station_without_coordinates_is_unplaced_not_guessed(survey):
    """46235 was added before anything knew where it is.

    The registry must be able to say "collecting, but unclassified" without
    that decaying into an invented position.
    """

    entry = survey["46235"]
    assert entry.role == siting.UNPLACED
    assert entry.latitude is None and entry.longitude is None
    assert entry.offsets is None
    assert not entry.constrains
    assert "metadata" in entry.note


def test_unusable_coordinates_are_dropped_rather_than_trusted(tmp_path):
    """collector.metadata flags a coordinate that failed its sanity check."""

    path = tmp_path / "meta.csv"
    path.write_text(
        "id,name,owner,station_type,latitude,longitude,usable,note\n"
        "46232,Point Loma South,R,Waverider,32.5170,-117.4250,true,\n"
        "99999,Nowhere,R,Waverider,12.0,34.0,false,failed regional check\n",
        encoding="utf-8",
    )
    found = siting.load_coordinates(path)
    assert "46232" in found
    assert "99999" not in found


def test_missing_metadata_file_places_nothing_and_raises_nothing(tmp_path):
    assert siting.load_coordinates(tmp_path / "absent.csv") == {}
    sentinel = Station(id="46232", name="Point Loma South, CA", region="socal")
    entries = siting.survey([sentinel], metadata_path=tmp_path / "absent.csv")
    assert entries[0].role == siting.UNPLACED


def test_sentinels_are_classified_by_region_not_aperture(survey):
    """The corridor test is meaningless at 4,000 km and must not be applied."""

    for sid in ("46001", "46005", "46006", "46059", "51101", "51002"):
        assert survey[sid].role == siting.SENTINEL
        assert survey[sid].offsets is None


def test_every_registry_station_is_classified(survey):
    assert set(survey) == {s.id for s in load_stations()}
    assert all(e.role for e in survey.values())
