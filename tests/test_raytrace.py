"""forecast.raytrace against the one case with a textbook answer.

On a planar beach -- straight, parallel depth contours -- refraction is
Snell's law, sin(θ)/c constant along a ray, and the energy reaching a point
from a narrow offshore beam is the offshore energy times Ks²·Kr², with
Ks² = cg0/cg and Kr² = cos θ0 / cos θ. Both are pinned here through the whole
chain: rays traced backward over a grid, the gain stored per heading, and the
spectrum integrated over nearshore headings the way the forecast will do it.

A total is not a validation of a mapping (BRIEFING §15), so the heading each
ray leaves deep water on is checked ray by ray, not just the energy sum.
"""

from __future__ import annotations

import math

import pytest

np = pytest.importorskip("numpy")

from forecast.raytrace import (  # noqa: E402
    DEEP, LAND, G, Bathymetry, Grid, speeds, trace, straight_line_blocker,
)
from forecast.geometry import load  # noqa: E402

SLOPE = 0.03
CELL = 20.0
WIDTH, HEIGHT = 30_000.0, 16_000.0
SHORE_Y = 1_000.0


def planar() -> Bathymetry:
    """Shore along y = SHORE_Y, sea to the north, depth = SLOPE * distance."""

    cols, rows = int(WIDTH / CELL), int(HEIGHT / CELL)
    ys = HEIGHT - (np.arange(rows) + 0.5) * CELL          # row 0 is the top
    depth = SLOPE * (ys - SHORE_Y)
    elevation = -np.repeat(depth[:, None], cols, axis=1)
    return Bathymetry([Grid.from_elevation(elevation, 0.0, HEIGHT, CELL, 0.0)], 0.0)


def start(bathy, h=10.0):
    return WIDTH / 2.0, SHORE_Y + h / SLOPE


@pytest.mark.parametrize("period", [8.0, 12.0, 16.0])
def test_rays_obey_snells_law(period):
    bathy = planar()
    x0, y0 = start(bathy)
    omega = 2 * math.pi / period
    c_n = float(speeds(omega, np.array([10.0]))[0][0])
    c0 = G / omega
    # Only headings Snell allows: past asin(c_n/c0) the ray turns back.
    limit = math.degrees(math.asin(c_n / c0))
    near = np.array([-0.9, -0.5, -0.1, 0.0, 0.1, 0.5, 0.9]) * limit % 360.0
    rays = trace(bathy, x0, y0, near, period)
    for theta_n, theta_0, status in zip(near, rays.off_from_deg, rays.status):
        assert status == DEEP
        rel_n = math.radians(((theta_n + 180) % 360) - 180)
        rel_0 = math.radians(((theta_0 + 180) % 360) - 180)
        assert math.sin(rel_0) == pytest.approx(math.sin(rel_n) * c0 / c_n, abs=2e-3)


def test_a_heading_snell_forbids_turns_back_onto_the_beach():
    """Total internal reflection: no deep-water heading arrives at 60° off
    the normal in 10 m of water at 12 s, so the backward ray turns and lands."""

    bathy = planar()
    x0, y0 = start(bathy)
    rays = trace(bathy, x0, y0, np.array([60.0]), 12.0)
    assert rays.status[0] == LAND


def test_a_ray_aimed_at_the_beach_from_behind_lands():
    bathy = planar()
    x0, y0 = start(bathy)
    rays = trace(bathy, x0, y0, np.array([180.0]), 10.0)
    assert rays.status[0] == LAND


@pytest.mark.parametrize("period,theta0", [(10.0, 0.0), (10.0, 25.0), (14.0, -30.0)])
def test_integrated_energy_is_ks2_kr2(period, theta0):
    """A narrow offshore beam, integrated over nearshore headings through the
    stored gain, has to come out at Ks²·Kr² of the offshore energy."""

    bathy = planar()
    x0, y0 = start(bathy)
    step = 0.1
    near = (np.arange(-89.95, 90.0, step)) % 360.0
    rays = trace(bathy, x0, y0, near, period)
    omega = 2 * math.pi / period
    c_n, cg_n, _ = speeds(omega, np.array([10.0]))
    c0 = G / omega
    gain = (c0 * 0.5 * c0) / float(c_n[0] * cg_n[0])

    width = 2.0                               # degrees, a narrow beam
    def s_off(theta):                         # unit energy, Gaussian in heading
        rel = ((theta - theta0 + 180.0) % 360.0) - 180.0
        return np.exp(-0.5 * (rel / width) ** 2) / (width * math.sqrt(2 * math.pi))

    ok = rays.status == DEEP
    e_near = float(np.sum(s_off(rays.off_from_deg[ok]) * gain) * step)

    t0 = math.radians(theta0)
    tn = math.asin(math.sin(t0) * float(c_n[0]) / c0)
    ks2 = (0.5 * c0) / float(cg_n[0])
    kr2 = math.cos(t0) / math.cos(tn)
    assert e_near == pytest.approx(ks2 * kr2, rel=0.01)


def test_the_deep_water_leg_is_tested_against_the_charted_blockers():
    """From a point west of Point Loma's tip, the peninsula's bearings are
    blocked and the open ocean to the west is not."""

    _, blockers = load()
    loma = next(b for b in blockers if b.name.startswith("Point Loma"))
    lat, lon = loma.a[0], loma.a[1] - 0.05
    assert straight_line_blocker(blockers, lat, lon, 270.0) is None
    assert straight_line_blocker(blockers, lat, lon, 45.0) == loma.name
