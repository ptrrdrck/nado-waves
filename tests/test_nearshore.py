"""forecast.nearshore — the pure-Python half, which the forecast would run.

The transfer tables are tested where they are built (tests/test_raytrace.py,
against Snell and Ks²·Kr²). Here: that carrying a spectrum through a table
integrates the way the tables mean, and that the local-sea term only switches
on where it cannot double-count the buoy's own wind sea.
"""

from __future__ import annotations

import math

import pytest

from forecast.geometry import load
from forecast.nearshore import Ray, Table, carry, local_sea, shoaling_squared
from forecast.transform import through
from tests.test_transform import synthetic

SPOTS, _ = load()
SOUTH = next(s for s in SPOTS if s.id == "coronado_south")


def test_shoaling_is_one_in_deep_water_and_grows_for_long_waves_in_ten_metres():
    assert shoaling_squared(1 / 8.0, 4000.0) == pytest.approx(1.0, abs=1e-6)
    assert shoaling_squared(1 / 16.0, 10.0) > 1.2


def open_table(depth=4000.0, step=0.5, normal=None):
    """No refraction, no land, no islands: every heading maps to itself with
    the pure shoaling gain, across one break's seaward half-plane."""

    normal = SOUTH.normal if normal is None else normal
    by_freq = {}
    for f in [0.025 + 0.0075 * i for i in range(48)]:
        ks2 = shoaling_squared(f, depth)
        by_freq[f] = [Ray(h, math.radians(step), h, ks2, h, ks2)
                      for h in ((normal - 90.0 + step / 2 + step * k) % 360.0
                                for k in range(int(180 / step)))]
    return Table("test", depth, by_freq)


@pytest.mark.parametrize("direction", [200.0, 240.0, 290.0])
def test_a_table_with_nothing_in_the_way_reproduces_the_aperture_with_no_blockers(direction):
    """Same density, same half-plane, no seabed: the two must agree. That
    makes every later difference between them the seabed and the islands."""

    spectrum = synthetic(direction, hs=1.5, spread_deg=15.0)
    got = carry(spectrum, open_table())
    aperture = through(spectrum, SOUTH, [])
    assert got.hs_equivalent == pytest.approx(aperture.hs_in_window_m, rel=0.005)
    assert got.hs_ref == pytest.approx(got.hs_equivalent, rel=1e-6)


def test_hard_and_diffracted_edges_are_kept_apart():
    """A band of headings shadowed hard but partly lit by diffraction: the
    hard figure loses it all, the diffracted one keeps some, and the open
    table keeps everything."""

    table = open_table()
    for rays in table.by_freq.values():
        for ray in rays:
            if 195.0 <= ray.near_from <= 205.0:
                ray.gain, ray.diff_gain = 0.0, 0.25 * ray.diff_gain
    got = carry(synthetic(200.0, hs=1.5, spread_deg=15.0), table)
    full = carry(synthetic(200.0, hs=1.5, spread_deg=15.0), open_table())
    assert got.hs_hard < got.hs_equivalent < full.hs_equivalent


def test_a_diffracted_ray_reads_the_spectrum_at_its_own_heading():
    """A ray the land stops takes the energy that diffracts round the edge,
    which comes from the heading of the ray that clears it."""

    table = open_table()
    for rays in table.by_freq.values():
        for ray in rays:
            ray.gain = 0.0
            ray.diff_off_from = 200.0
    got = carry(synthetic(200.0, hs=1.5, spread_deg=5.0), table)
    assert got.hs_hard == 0.0
    assert got.off_from_deg == pytest.approx(200.0, abs=0.5)


def fetch_table():
    table = open_table()
    # Closed 6 km fetch from the west, open ocean from the south-west.
    table.fetch = [(6.0, True) if 260 <= d <= 300 else (80.0, False) for d in range(360)]
    return table


def test_local_sea_grows_over_a_closed_onshore_fetch():
    got = local_sea(fetch_table(), 200.0, 20.0, 280.0)
    assert got is not None
    assert 0.3 < got.hs_m < 1.0 and 2.0 < got.tp_s < 5.0
    assert got.fetch_km == 6.0


def test_local_sea_is_not_added_over_an_open_fetch():
    """The buoy already saw that wind sea; it arrives through the table."""

    assert local_sea(fetch_table(), 200.0, 20.0, 220.0) is None


def test_an_offshore_wind_makes_no_waves_at_the_beach():
    """Wind waves run downwind. Wind from behind the beach carries its waves
    out to sea, whatever the fetch."""

    assert local_sea(fetch_table(), 200.0, 20.0, 20.0) is None


def test_no_wind_no_local_sea():
    assert local_sea(fetch_table(), 200.0, 0.0, 280.0) is None
    assert local_sea(fetch_table(), 200.0, None, None) is None
