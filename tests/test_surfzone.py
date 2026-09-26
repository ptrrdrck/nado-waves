"""forecast.surfzone against what a 1-D surf-zone model has to get right.

Outside the surf zone it must be linear shoaling and Snell refraction and
nothing else; inside, Battjes & Janssen's fraction of breaking waves and their
cap; and on a planar beach the tide must move the break point without
changing the break.
"""

from __future__ import annotations

import math

import pytest

from forecast.surfzone import (Profile, break_on, breaker_index, celerities,
                               fraction_breaking, load_profiles)

SLOPE = 0.03


def planar(start=5.0, dry=-2.5, step=2.0) -> Profile:
    n = int((start - dry) / SLOPE / step) + 1
    d = [i * step for i in range(n)]
    return Profile("planar", d, [start - SLOPE * x for x in d])


@pytest.mark.parametrize("ratio", [0.3, 0.5, 0.8, 0.95])
def test_fraction_breaking_solves_battjes_janssen(ratio):
    q = fraction_breaking(ratio)
    assert 0.0 < q < 1.0
    assert (1 - q) / math.log(q) == pytest.approx(-ratio * ratio, rel=1e-6)


def test_fraction_breaking_limits():
    assert fraction_breaking(1.0) == 1.0
    assert fraction_breaking(1.3) == 1.0
    assert fraction_breaking(0.1) == 0.0
    assert fraction_breaking(0.4) < fraction_breaking(0.6) < fraction_breaking(0.9)


def test_breaker_index_is_battjes_stive():
    assert breaker_index(0.0, 12.0) == pytest.approx(0.5)
    assert 0.5 < breaker_index(1.0, 8.0) < 0.9


@pytest.mark.parametrize("angle", [0.0, 25.0])
def test_small_waves_shoal_and_refract_linearly_before_they_break(angle):
    """Where nothing is breaking, H ∝ sqrt(cg0·cosθ0 / (cg·cosθ)): Ks·Kr."""

    omega = 2 * math.pi / 12.0
    path = []
    break_on(planar(), hs_start_m=0.05, period_s=12.0, start_depth_m=5.0,
             angle_deg=angle, tide_m=0.0, path=path)
    c0, cg0 = celerities(omega, 5.0)
    t0 = math.radians(angle)
    for x, h, hs in path:
        if abs(h - 3.0) < 0.01:
            c, cg = celerities(omega, h)
            t = math.asin(math.sin(t0) * c / c0)
            expected = 0.05 * math.sqrt(cg0 * math.cos(t0) / (cg * math.cos(t)))
            assert hs == pytest.approx(expected, rel=0.002)
            return
    pytest.fail("no step landed at 3 m")


def test_breaking_caps_the_height_at_the_depth():
    path = []
    got = break_on(planar(), hs_start_m=1.5, period_s=14.0, start_depth_m=5.0,
                   angle_deg=0.0, tide_m=0.0, path=path)
    for _, h, hs in path:
        assert hs / math.sqrt(2) <= got.gamma * h + 1e-9
    # A maximum inside the profile, where the larger waves are breaking.
    assert not got.outside_start
    assert 0.02 < got.fraction_breaking < 0.5
    assert 1.5 < got.hs_m < 2.2 and 2.0 < got.depth_m < 4.5


def test_the_tide_moves_the_break_point_on_a_planar_beach_and_not_the_break():
    low = break_on(planar(), hs_start_m=1.0, period_s=12.0, start_depth_m=5.0,
                   angle_deg=0.0, tide_m=-0.5)
    high = break_on(planar(), hs_start_m=1.0, period_s=12.0, start_depth_m=5.0,
                    angle_deg=0.0, tide_m=+0.5)
    assert high.hs_m == pytest.approx(low.hs_m, rel=0.01)
    assert high.depth_m == pytest.approx(low.depth_m, rel=0.03)
    assert high.distance_m - low.distance_m == pytest.approx(1.0 / SLOPE, abs=2.0)


def test_the_march_is_converged_at_its_step():
    kw = dict(hs_start_m=1.2, period_s=13.0, start_depth_m=5.0, angle_deg=10.0, tide_m=0.2)
    coarse = break_on(planar(), **kw)
    fine = break_on(planar(), step_m=0.1, **kw)
    assert coarse.hs_m == pytest.approx(fine.hs_m, rel=0.005)
    assert coarse.depth_m == pytest.approx(fine.depth_m, abs=0.05)


def test_waves_already_breaking_at_the_start_are_flagged():
    got = break_on(planar(), hs_start_m=3.0, period_s=16.0, start_depth_m=5.0,
                   angle_deg=0.0, tide_m=-0.5)
    assert got.outside_start


def test_no_tide_no_answer():
    """Running it at mean sea level would fill a missing observation."""

    assert break_on(planar(), hs_start_m=1.0, period_s=12.0, start_depth_m=5.0,
                    angle_deg=0.0, tide_m=None) is None


def test_the_stored_profiles_run_from_the_start_depth_to_dry_sand():
    for break_id, profile in load_profiles().items():
        assert 4.9 < profile.depth_m[0] < 5.3, break_id
        assert profile.depth_m[-1] <= -2.5, break_id
        assert profile.distance_m[-1] < 600.0, break_id
