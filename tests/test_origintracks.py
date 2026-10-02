"""Origin against NHC best tracks: the parsing and the comparison, offline."""

from __future__ import annotations



import pytest

from forecast.origintracks import nearest, parse_bdeck, report
from forecast.swell import destination_point, great_circle_km

HOME = (32.517, -117.425)

#: ATCF b-deck rows as NHC writes them: one row per wind-radius threshold.
BDECK = """\
EP, 12, 2026082000,   , BEST,   0, 140N, 1150W,  60,  990, TS,  34, NEQ,   60,   50,   40,   50, 1008,  150,  25,   0,   0,   E,   0,    ,   0,   0,       TEST, M,
EP, 12, 2026082006,   , BEST,   0, 153N, 1165W,  85,  975, HU,  34, NEQ,  120,  100,   80,  110, 1008,  180,  20,   0,   0,   E,   0,    ,   0,   0,       TEST, D,
EP, 12, 2026082006,   , BEST,   0, 153N, 1165W,  85,  975, HU,  50, NEQ,   60,   50,   40,   50, 1008,  180,  20,   0,   0,   E,   0,    ,   0,   0,       TEST, D,
EP, 12, 2026082012,   , BEST,   0, 160N, 1180W,  95,  965, HU,  34, NEQ,  130,  110,   90,  120, 1008,  190,  20,   0,   0,   E,   0,    ,   0,   0,       TEST, D,
"""


def test_a_bdeck_is_one_fix_per_time_in_signed_degrees():
    fixes = parse_bdeck(BDECK)
    assert [f.time.hour for f in fixes] == [0, 6, 12]
    assert fixes[1].lat == pytest.approx(15.3) and fixes[1].lon == pytest.approx(-116.5)
    assert fixes[1].vmax_kt == 85 and fixes[1].name == "TEST" and fixes[1].storm == "EP12"


def reading_at(fix_lat, fix_lon, *, born="2026-08-20T06:00:00Z", placed=True):
    d = great_circle_km(HOME, (fix_lat, fix_lon))
    from forecast.swell import initial_bearing

    b = initial_bearing(HOME, (fix_lat, fix_lon))
    return {"first_utc": "2026-08-23T00:00:00Z", "generated_utc": born,
            "distance_km": round(d), "bearing_deg": round(b) if placed else None,
            "region": "the eastern North Pacific" if placed else None,
            "origin": list(destination_point(HOME, b, d)) if placed else None}


def test_a_reading_on_the_storm_misses_by_nothing_and_the_control_by_far():
    tracks = {"EP12": parse_bdeck(BDECK)}
    r = reading_at(15.3, -116.5)
    m = nearest(r, tracks, HOME)
    assert m.miss_km < 5 and m.fix.time.hour == 6
    assert nearest(r, tracks, HOME, shift_days=10) is None


def test_outside_the_window_there_is_no_match():
    tracks = {"EP12": parse_bdeck(BDECK)}
    assert nearest(reading_at(15.3, -116.5, born="2026-09-10T00:00:00Z"), tracks, HOME) is None


def test_an_unplaced_reading_is_compared_on_distance_and_says_so():
    tracks = {"EP12": parse_bdeck(BDECK)}
    r = reading_at(15.3, -116.5, placed=False)
    assert nearest(r, tracks, HOME).miss_km < 1
    assert "(distance only)" in report([r], tracks, HOME)


def test_a_disturbance_too_weak_to_make_swell_is_not_counted():
    tracks = {"EP12": parse_bdeck(BDECK)}
    r = reading_at(14.0, -115.0, born="2026-08-20T00:00:00Z")
    assert nearest(r, tracks, HOME).fix.vmax_kt == 60
    assert nearest(r, tracks, HOME, min_kt=64).fix.vmax_kt >= 64
