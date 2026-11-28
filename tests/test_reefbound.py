"""forecast.reefbound's pieces, and the roughness argument it added to
raytrace's Madsen functions, that need no archive run."""

import math

import numpy as np
import pytest

from forecast import raytrace as RT
from forecast import reefbound as R
from forecast.geometry import load
from forecast.nearshore import Ray, Table
from forecast.wrapbudget import arcs_for

from test_raytrace import planar, start, trace


def test_the_roughness_argument_defaults_to_what_ships():
    ab = np.geomspace(1e-3, 50.0, 199)
    assert np.array_equal(RT.madsen_fw(ab), RT.madsen_fw(ab, RT.MADSEN_K_N))
    assert np.array_equal(RT.fw_lookup(ab), RT.fw_lookup(ab, RT.MADSEN_K_N))
    bathy = planar()
    x0, y0 = start(bathy)
    rays = trace(bathy, x0, y0, np.array([0.0, 25.0]), 14.0, steps=True)
    omega = 2 * math.pi / 14.0
    assert np.array_equal(RT.madsen_losses(rays.steps, omega),
                          RT.madsen_losses(rays.steps, omega, k_n=RT.MADSEN_K_N))


def test_a_rougher_bed_takes_more():
    ab = np.geomspace(1e-2, 20.0, 99)
    fw = [RT.madsen_fw(ab, k) for k in (0.05, 0.1, 0.2, 0.5)]
    assert all(np.all(b >= a) for a, b in zip(fw, fw[1:]))
    for k in (0.1, 0.5):
        assert np.max(np.abs(RT.fw_lookup(ab, k) / RT.madsen_fw(ab, k) - 1)) < 1e-3
    bathy = planar()
    x0, y0 = start(bathy)
    rays = trace(bathy, x0, y0, np.array([0.0]), 14.0, steps=True)
    loss = [float(RT.madsen_losses(rays.steps, 2 * math.pi / 14.0, hs_m=(2.0,),
                                   peak_hz=(1 / 14.0,), tide_m=(0.0,), k_n=k)[0, 0, 0, 0])
            for k in (0.05, 0.1, 0.2, 0.5)]
    assert all(b > a for a, b in zip(loss, loss[1:]))


@pytest.fixture(scope="module")
def center():
    spots, blockers = load()
    spot = {s.id: s for s in spots}["coronado_center"]
    return spot, arcs_for(spot, blockers)


def _ray(off, gain, diff_off=None):
    return Ray(near_from=200.0, width_rad=0.01, off_from=off, gain=gain,
               diff_off_from=off if diff_off is None else diff_off, diff_gain=0.5)


def test_which_rays_travel_the_wrap(center):
    spot, arcs = center
    assert R.on_wrap(_ray(285.0, 0.4), spot.normal, arcs)             # clear, behind Point Loma
    assert not R.on_wrap(_ray(230.0, 0.4), spot.normal, arcs)         # clear, in the window
    assert R.on_wrap(_ray(240.0, 0.0, diff_off=280.0), spot.normal, arcs)    # fill read from the wrap side
    assert not R.on_wrap(_ray(285.0, 0.0, diff_off=230.0), spot.normal, arcs)


def test_mixing_takes_the_rough_factor_on_the_wrap_only():
    table = Table("x", 5.0, {0.1: [_ray(285.0, 0.4), _ray(230.0, 0.4), _ray(240.0, 0.0)]})
    shipped = {0.1: [0.9, 0.8, 0.7]}
    rough = {0.1: [0.5, 0.4, 0.3]}
    assert R.mixed(shipped, rough, table, {0.1: [True, False, True]}) == {0.1: [0.5, 0.8, 0.3]}
    assert R.mixed(shipped, shipped, table, {0.1: [True, False, True]}) == shipped


# ------------------------------------------------------------ a located seabed

def test_step_positions_line_up_with_the_steps_and_change_nothing_else():
    bathy = planar()
    x0, y0 = start(bathy)
    heads = np.array([-30.0, 0.0, 30.0])
    plain = trace(bathy, x0, y0, heads, 12.0, steps=True)
    placed = trace(bathy, x0, y0, heads, 12.0, steps=True, step_xy=True)
    assert plain.step_xy is None
    for (x, y), (h, d), (h0, d0) in zip(placed.step_xy, placed.steps, plain.steps):
        assert len(x) == len(y) == len(h) == len(d)
        assert np.array_equal(h, h0) and np.array_equal(d, d0)
    assert np.array_equal(placed.friction, plain.friction)
    # The first wet step starts at the start point.
    assert placed.step_xy[1][0][0] == pytest.approx(x0) and placed.step_xy[1][1][0] == pytest.approx(y0)


def test_a_per_step_roughness_is_the_scalar_where_it_is_uniform():
    bathy = planar()
    x0, y0 = start(bathy)
    rays = trace(bathy, x0, y0, np.array([0.0, 25.0]), 14.0, steps=True)
    omega = 2 * math.pi / 14.0
    for k in (RT.MADSEN_K_N, 0.5):
        uniform = [np.full(len(h), k) for h, _ in rays.steps]
        assert np.array_equal(RT.madsen_losses(rays.steps, omega, k_n=uniform),
                              RT.madsen_losses(rays.steps, omega, k_n=k))
    half = [np.where(np.arange(len(h)) < len(h) // 2, 0.5, RT.MADSEN_K_N) for h, _ in rays.steps]
    lo, mid, hi = (RT.madsen_losses(rays.steps, omega, k_n=k)
                   for k in (RT.MADSEN_K_N, half, 0.5))
    # Never less, and more wherever f_w is off its 0.3 cap (a small sea's
    # a_b/k_N < 1.57 caps it at both roughnesses).
    assert np.all(lo <= mid) and np.all(mid <= hi)
    assert np.any(lo < mid) and np.any(mid < hi)
    with pytest.raises(ValueError):
        RT.madsen_losses(rays.steps, omega, k_n=[np.zeros(3), np.zeros(3)])


def test_a_located_bed_all_sand_or_all_rock_is_the_uniform_table():
    """Center at 0.101 Hz: a located bed with no step on rock gives the
    shipped-roughness build back exactly, and every step on rock gives the
    uniformly rough build; the share of wet length on rock is 0 and 1."""

    from forecast.raytrace import Bathymetry

    bathy = Bathymetry.load()
    spots, blockers = load()
    spot = {s.id: s for s in spots}["coronado_center"]

    def built(k):
        out: dict = {}
        RT.table(bathy, spot, blockers, [0.101], madsen_out=out, madsen_k_n=k)
        return out["0.1010"]

    sand, rough = built(RT.MADSEN_K_N), built(0.5)
    none = built(lambda x, y: np.full(np.shape(x), RT.MADSEN_K_N))
    every = built(lambda x, y: np.full(np.shape(x), 0.5))
    assert set(none.pop("rough_share")) == {0.0}
    assert set(every.pop("rough_share")) <= {0.0, 1.0}        # 0 only for a path with no wet step
    assert none == sand
    assert every == rough


def test_inside_a_ring_and_the_nearest_sample_rule():
    ring = np.array([[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0], [0.0, 0.0]])
    got = R.inside(np.array([5.0, 15.0, 9.9, -1.0]), np.array([5.0, 5.0, 9.9, 5.0]), ring)
    assert got.tolist() == [True, False, True, False]
    samples = np.array([[0.0, 0.0], [300.0, 0.0]])
    bed = R.RockBed("R1", 0.5, ([], samples, np.array([True, False])))
    x, y = np.array([10.0, 200.0, 290.0, 0.0]), np.array([0.0, 0.0, 0.0, 400.0])
    # 10 m from the rock sample; nearest is the sand sample (100 m and 10 m
    # away) though rock is within 250 m; nothing within 250 m.
    assert bed.on_rock(x, y).tolist() == [True, False, False, False]
    assert bed(x, y).tolist() == [0.5, RT.MADSEN_K_N, RT.MADSEN_K_N, RT.MADSEN_K_N]
    area = R.RockBed("R0", 0.2, ([ring], samples, np.array([True, False])))
    assert area(np.array([5.0, 50.0]), np.array([5.0, 5.0])).tolist() == [0.2, RT.MADSEN_K_N]
