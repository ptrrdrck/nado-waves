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
