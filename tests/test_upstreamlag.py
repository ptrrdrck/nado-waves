"""The upstream lag: Tanner Banks (46047) to Point Loma South (46232) to the breaks.

The report's measurements live in docs/upstream_lag.md; these pin the pure
pieces the LIVE briefing reads: the deep-water lag, the leg tables, and the
rise detector, each against a known answer.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from forecast import upstreamlag as ul
from forecast.swell import group_velocity
from forecast.transform import at_buoy, load_spectra

COORDS = {"46047": (32.418, -119.535), "46232": (32.517, -117.425)}


def test_west_swell_takes_the_whole_offset_at_group_speed():
    east, north = ul.offset_km(COORDS)
    expected = east * 1000.0 / group_velocity(12.0) / 3600.0
    assert ul.deep_water_lag_h(12.0, 270.0, COORDS) == pytest.approx(expected, rel=1e-9)
    assert 5.5 < expected < 6.2


def test_south_swell_reaches_46232_sooner_than_north_west():
    """The direction dependence the report's control rests on."""

    assert ul.deep_water_lag_h(13.0, 200.0, COORDS) < ul.deep_water_lag_h(13.0, 300.0, COORDS) - 1.5


def test_longer_swell_crosses_faster():
    assert ul.deep_water_lag_h(16.0, 290.0, COORDS) < ul.deep_water_lag_h(11.0, 290.0, COORDS)


def test_swell_travelling_from_46232_toward_46047_reads_negative():
    assert ul.deep_water_lag_h(12.0, 90.0, COORDS) < 0


def test_the_whole_circle_band_energy_is_the_buoy_view_in_that_band():
    """band_energy over (nearly) the whole circle is the band's m0: the sector
    share is 1. (0–360 exactly is an empty sector to `mem_sector`, whose
    edges are taken modulo 360.)"""

    s = load_spectra(ul.SPECTRA / "46232", limit=1)[0].with_spread("mem")
    band = (10.0, 12.0)
    total = sum(s.c11[i] * s.bin_width(i) for i, f in enumerate(s.frequencies)
                if 1 / band[1] <= f < 1 / band[0])
    assert ul.band_energy(s, band, (0.0, 359.999)) == pytest.approx(total, rel=1e-4)
    assert at_buoy(s)  # the spectrum is readable at all


def test_each_break_has_a_leg_table_from_46232():
    for bid in ("coronado_north", "coronado_center", "coronado_south"):
        rows = ul.load_leg(bid)
        assert rows, bid
        periods = {r["period_s"] for r in rows}
        assert min(periods) >= 8.0 and max(periods) <= 22.0


def test_the_leg_is_tens_of_minutes_and_shorter_for_longer_swell():
    """29 km at deep-water group speed is 50 min at 12 s; the rays agree."""

    for bid in ("coronado_north", "coronado_center", "coronado_south"):
        short = ul.leg_over(bid, 11.0, ul.ANCHOR_SECTORS["north-west"])
        long_ = ul.leg_over(bid, 15.5, ul.ANCHOR_SECTORS["north-west"])
        assert short and long_
        assert 20 < long_.lo_min <= long_.hi_min < short.hi_min < 70


def test_center_from_230_matches_the_straight_line_check():
    lg = ul.leg("coronado_center", 12.0, 230.0)
    assert lg is not None and 45 < lg.lo_min <= lg.hi_min < 56


def _series(levels, start=datetime(2026, 10, 1, tzinfo=timezone.utc), step_min=30):
    return [(start + timedelta(minutes=step_min * k), math.log(v)) for k, v in enumerate(levels)]


def test_a_tripling_is_a_rise_timed_at_its_log_midpoint():
    levels = [0.002] * 10 + [0.002 * 1.25 ** k for k in range(1, 9)] + [0.002 * 1.25 ** 8] * 10
    found = ul.rises(_series(levels))
    assert len(found) == 1
    r = found[0]
    assert r.factor == pytest.approx(1.25 ** 8, rel=1e-9)
    # log rises linearly from stamp 9 to 17, so halfway is stamp 13.
    assert r.mid == datetime(2026, 10, 1, tzinfo=timezone.utc) + timedelta(minutes=30 * 13)


def test_a_doubling_is_not_a_rise():
    levels = [0.004] * 10 + [0.008] * 10
    assert ul.rises(_series(levels)) == []


def test_a_rise_of_nothing_much_is_not_a_rise():
    levels = [1e-5] * 10 + [1e-4] * 10
    assert ul.rises(_series(levels)) == []
