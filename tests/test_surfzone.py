"""forecast.surfzone against what a 1-D surf-zone model has to get right.

Outside the surf zone it must be linear shoaling and Snell refraction and
nothing else; inside, Battjes & Janssen's fraction of breaking waves and their
cap; and on a planar beach the tide must move the break point without
changing the break. Since BRIEFING §58 the profiles start seaward of the
table's 5 m start point: with breaking off the march must give the 5 m figure
back there exactly, a sea nothing breaks before 5 m must break exactly as
before, and one already breaking at 5 m must find its break further out.
"""

from __future__ import annotations

import math

import pytest

from forecast.surfzone import (START_GAIN, Profile, break_on, breaker_index, celerities,
                               fraction_breaking, load_profiles)

SLOPE = 0.03
#: Where the surf zone starts (`raytrace.SURF_START_M`), copied rather than
#: imported: raytrace needs numpy, and this suite runs without it.
SURF_START_M = {"coronado_north": 7.0, "coronado_center": 10.0, "coronado_south": 10.0}


def planar(start=5.0, dry=-2.5, step=2.0, outer=None) -> Profile:
    """A planar beach with the table's start point at x = 0 in `start` m of
    water; with `outer`, extended seaward (negative x) to that depth, as the
    stored profiles are since BRIEFING §58."""

    n = int((start - dry) / SLOPE / step) + 1
    d = [i * step for i in range(n)]
    if outer is not None:
        m = int(round((outer - start) / SLOPE / step))
        d = [-i * step for i in range(m, 0, -1)] + d
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


def test_a_maximum_a_step_inside_the_start_is_still_already_breaking():
    """BRIEFING §56: a maximum 1 m in, with shoaling adding 0.002% before
    breaking overtook it, is the start point's figure, not a break the
    profile found. Until 2026-11-17 only a maximum exactly at the first point
    was flagged, and a third of the big-swell hours at Center and South were
    not."""

    path = []
    got = break_on(planar(), hs_start_m=2.1, period_s=16.0, start_depth_m=5.0,
                   angle_deg=0.0, tide_m=0.0, path=path)
    assert got.distance_m > 0.0
    assert got.hs_m <= path[0][2] * (1 + START_GAIN)
    assert got.outside_start


def test_the_flag_is_the_gain_over_the_start_and_nothing_else():
    """Control: across a sweep of start heights the flag is exactly 'the
    maximum is within START_GAIN of the first point', so it turns on where
    the gain falls through it and not at some distance; and the smaller
    waves, which shoal well past it before breaking, are never flagged."""

    flags = []
    for i in range(30):
        hs = 1.6 + 0.02 * i
        path = []
        got = break_on(planar(), hs_start_m=hs, period_s=16.0, start_depth_m=5.0,
                       angle_deg=0.0, tide_m=0.0, path=path)
        assert got.outside_start == (got.hs_m <= path[0][2] * (1 + START_GAIN))
        flags.append(got.outside_start)
    assert not flags[0] and flags[-1]
    assert flags == sorted(flags)          # once on, stays on as the sea grows


def test_no_tide_no_answer():
    """Running it at mean sea level would fill a missing observation."""

    assert break_on(planar(), hs_start_m=1.0, period_s=12.0, start_depth_m=5.0,
                    angle_deg=0.0, tide_m=None) is None


def test_the_stored_profiles_run_from_where_the_surf_zone_starts_to_dry_sand():
    """Since BRIEFING §58: from SURF_START_M of water seaward of the table's
    start point (x = 0, 5 m of water, still a row of its own) to dry sand,
    every 2 m, and nowhere seaward of the start point shallower than it is."""

    for break_id, profile in load_profiles().items():
        d, h = profile.distance_m, profile.depth_m
        assert SURF_START_M[break_id] <= h[0] < SURF_START_M[break_id] + 0.1, break_id
        assert d[0] < 0.0, break_id
        zero = d.index(0.0)
        assert 4.9 < h[zero] < 5.3, break_id
        assert min(h[:zero]) >= h[zero], break_id
        assert all(b - a == pytest.approx(2.0) for a, b in zip(d, d[1:])), break_id
        assert h[-1] <= -2.5, break_id
        assert d[-1] < 600.0 and d[0] > -1000.0, break_id
        inshore = profile.inshore()
        assert inshore.distance_m[0] == 0.0 and inshore.depth_m == h[zero:], break_id


# ------------------------------------------------- the surf zone starts deeper (§58)

SEAS = [(0.4, 9.0, 0.0), (1.1, 13.0, 15.0), (1.9, 14.3, -20.0), (2.6, 16.0, 5.0), (3.4, 18.0, 30.0)]


@pytest.mark.parametrize("tide", [-0.6, 0.0, 1.2])
def test_with_breaking_off_the_march_gives_the_5m_figure_back_at_5m(tide):
    """The key control: the deeper start's sea is the table's 5 m flux carried
    back out linearly, so with breaking off the march returns, at x = 0, the
    figure today's march started from, to the digit, on every stored profile
    and on the planar one. At mean sea level on the planar beach (x = 0 is
    exactly the start depth) that is the table's own Hs."""

    profiles = dict(load_profiles(), planar=planar(outer=10.0))
    for name, profile in profiles.items():
        for hs, period, angle in SEAS:
            kw = dict(hs_start_m=hs, period_s=period, start_depth_m=profile.depth_at(0.0),
                      angle_deg=angle, tide_m=tide, breaking=False)
            here, there = [], []
            break_on(profile, path=here, **kw)
            break_on(profile.inshore(), path=there, **kw)
            at0 = [p for p in here if p[0] == 0.0]
            assert here[0][0] < 0.0 and at0, name
            assert at0[0][2] == there[0][2], (name, hs, period)
            # ... and every point in from there is the same march
            assert [p[2] for p in here if p[0] >= 0.0] == [p[2] for p in there], name
            if name == "planar" and tide == 0.0:
                assert at0[0][2] == pytest.approx(hs, rel=1e-12)


def test_outside_the_surf_zone_breaking_off_is_linear_shoaling_and_snell_seaward_too():
    """Between the deeper start and 5 m the march is Ks·Kr about the 5 m figure:
    smaller further out, by exactly the linear ratio."""

    omega = 2 * math.pi / 12.0
    path = []
    break_on(planar(outer=10.0), hs_start_m=1.0, period_s=12.0, start_depth_m=5.0,
             angle_deg=20.0, tide_m=0.0, path=path, breaking=False)
    c5, cg5 = celerities(omega, 5.0)
    t5 = math.radians(20.0)
    for x, h, hs in path:
        if x < 0 and abs(h - 8.0) < 1e-9:
            c, cg = celerities(omega, h)
            t = math.asin(math.sin(t5) * c / c5)
            assert hs == pytest.approx(math.sqrt(cg5 * math.cos(t5) / (cg * math.cos(t))), rel=1e-9)
            assert hs < 1.0
            break
    else:
        pytest.fail("no point at 8 m")


@pytest.mark.parametrize("tide", [-0.5, 0.0, 1.0])
def test_a_sea_nothing_breaks_before_5m_breaks_exactly_as_before(tide):
    """Hours not flagged with the 5 m start, where no wave is breaking seaward
    of 5 m (Battjes-Janssen's Qb is exactly zero below Hrms/Hmax = 0.2): the
    deeper start changes nothing, to the digit published (and to 1e-12: the
    march re-forms the flux from Hrms at every step, which costs an ulp or
    two over the extension)."""

    for profile in list(load_profiles().values()) + [planar(outer=10.0)]:
        for hs, period, angle in [(0.3, 8.0, 0.0), (0.5, 12.0, 15.0), (0.55, 15.0, -10.0)]:
            kw = dict(hs_start_m=hs, period_s=period, start_depth_m=profile.depth_at(0.0),
                      angle_deg=angle, tide_m=tide)
            path = []
            new = break_on(profile, path=path, **kw)
            assert all(p[2] / math.sqrt(2) <= 0.2 * new.gamma * p[1] for p in path if p[0] < 0)
            old = break_on(profile.inshore(), **kw)
            assert new.as_dict() == old.as_dict()
            assert new.hs_m == pytest.approx(old.hs_m, rel=1e-12)


def test_a_sea_already_breaking_at_5m_finds_its_break_further_out():
    """The case BRIEFING §58 is for. A 3 m, 16 s sea at 5 m is flagged on a
    beach that starts at 5 m (test_waves_already_breaking_at_the_start_are_flagged);
    started at 10 m, it breaks seaward of 5 m, unflagged, lower than the
    ceiling, in deeper water than 5 m."""

    kw = dict(hs_start_m=3.0, period_s=16.0, start_depth_m=5.0, angle_deg=0.0, tide_m=-0.5)
    ceiling = break_on(planar(), **kw)
    got = break_on(planar(outer=10.0), **kw)
    assert ceiling.outside_start
    assert not got.outside_start
    assert got.distance_m < 0.0
    assert got.depth_m > 5.0 - 0.5
    assert got.hs_m < ceiling.hs_m


@pytest.mark.parametrize("hs", [1.0, 3.0])
def test_on_the_extended_planar_beach_the_tide_moves_the_break_point_not_the_break(hs):
    """The planar control on the extended profile, for a sea that breaks
    inside 5 m and for one that now breaks outside it."""

    kw = dict(hs_start_m=hs, period_s=14.0, start_depth_m=5.0, angle_deg=0.0)
    low = break_on(planar(outer=10.0), tide_m=-0.5, **kw)
    high = break_on(planar(outer=10.0), tide_m=+0.5, **kw)
    assert not low.outside_start and not high.outside_start
    assert high.hs_m == pytest.approx(low.hs_m, rel=0.01)
    assert high.depth_m == pytest.approx(low.depth_m, rel=0.03)
    assert high.distance_m - low.distance_m == pytest.approx(1.0 / SLOPE, abs=2.0)


def test_beyond_the_headroom_the_deeper_start_still_flags():
    """A sea that is already breaking at the deeper start too is flagged
    there: the guard stays for seas bigger than the archive's."""

    got = break_on(planar(outer=7.0), hs_start_m=5.0, period_s=16.0, start_depth_m=5.0,
                   angle_deg=0.0, tide_m=0.0)
    assert got.outside_start
    assert got.distance_m < 0.0
