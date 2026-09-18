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

def test_swell_window_drops_the_near_useless_south_east_arc(spots_and_blockers):
    """Every spot has two open arcs; only one can carry a real swell.

    BRIEFING section 2 says the total open arc overstates because the south-east
    arc points into the bight. The swell-side window is the one with land on
    both edges, and it must be strictly narrower than the open arc.
    """

    spots, blockers = spots_and_blockers
    for spot in spots.values():
        full = open_window(spot, blockers)
        swell = swell_window(spot, blockers)
        assert len(swell) == 1, f"{spot.id} should have exactly one swell window"
        assert len(full) > len(swell), f"{spot.id} lost its south-east arc"


@pytest.mark.parametrize(
    "spot_id,low,high",
    [
        ("coronado_north", 199.4, 242.2),
        ("coronado_center", 201.2, 250.3),
        ("coronado_south", 203.5, 259.9),
        ("nasni_breakers", 196.0, 222.6),
        ("nab_gator", 205.9, 269.9),
    ],
)
def test_swell_window_reproduces_the_published_numbers(spots_and_blockers, spot_id, low, high):
    """The 42.8 / 49.1 / 56.3 spread BRIEFING section 2a is built on."""

    spots, blockers = spots_and_blockers
    (got_low, got_high), = swell_window(spots[spot_id], blockers)
    assert got_low == pytest.approx(low, abs=0.1)
    assert got_high == pytest.approx(high, abs=0.1)


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
        a = initial_bearing(position, blocker.a)
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
            (low, high), = swell_window(spots[break_id], blockers)
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
