"""Land on a swell's path: the raster, the path test, and the coastline clip."""

from __future__ import annotations

import random

import pytest

from collector import coastline
from forecast import landpath
from forecast.landpath import Land, blocked, inside

#: A peninsula 10° long and 2° wide, the shape that stops Polo's swell.
PENINSULA = [(-114.0, 22.0), (-112.0, 22.0), (-112.0, 32.0), (-114.0, 32.0)]
BOX = (-130.0, 10.0, -100.0, 35.0)


def test_the_raster_agrees_with_ray_casting():
    land = Land([PENINSULA], BOX)
    rng = random.Random(5)
    for _ in range(500):
        lat, lon = rng.uniform(15, 34), rng.uniform(-120, -105)
        if abs(lon + 114) < 0.06 or abs(lon + 112) < 0.06 or abs(lat - 22) < 0.06:
            continue
        assert ((lat, lon) in land) == inside(lat, lon, PENINSULA)


def test_a_path_across_the_peninsula_is_blocked_and_one_west_of_it_is_not():
    land = Land([PENINSULA], BOX)
    buoy = (32.4, -119.5)
    assert blocked((20.0, -108.0), buoy, land)       # from the far side
    assert not blocked((18.0, -118.0), buoy, land)   # open water all the way


def test_no_land_file_means_nothing_is_blocked(tmp_path):
    landpath.load_land.cache_clear()
    assert not blocked((20.0, -108.0), (32.4, -119.5), landpath.load_land(str(tmp_path)))


def test_the_clip_keeps_only_whats_inside_the_box():
    ring = [[-150.0, 0.0], [-90.0, 0.0], [-90.0, 40.0], [-150.0, 40.0]]
    clipped = coastline.clip(ring)
    assert all(coastline.BBOX[0] <= x <= coastline.BBOX[2] and
               coastline.BBOX[1] <= y <= coastline.BBOX[3] for x, y in clipped)
    assert coastline.extent_km(clipped) > 4000


def test_small_islands_are_dropped():
    island = [[-118.0, 29.0], [-117.8, 29.0], [-117.8, 29.2], [-118.0, 29.2], [-118.0, 29.0]]
    big = [[-114.0, 22.0], [-112.0, 22.0], [-112.0, 32.0], [-114.0, 32.0], [-114.0, 22.0]]
    geo = {"features": [{"geometry": {"type": "Polygon", "coordinates": [island]}},
                        {"geometry": {"type": "Polygon", "coordinates": [big]}}]}
    assert len(coastline.polygons(geo)) == 1


def test_the_mem_sector_is_the_sum_of_mems_bins():
    from forecast.spreadmethod import Unrealisable, mem, mem_sector

    rng = random.Random(9)
    checked = 0
    for _ in range(300):
        r1 = rng.uniform(0.1, 0.97)
        r2 = rng.uniform(0.0, r1)
        a1, a2 = rng.uniform(0, 360), rng.uniform(0, 360)
        try:
            dist = mem(r1, r2, a1, a2)
        except Unrealisable:
            continue
        lo, width = rng.randrange(360), rng.randrange(1, 200)
        assert mem_sector(r1, r2, a1, a2, lo, lo + width) == pytest.approx(
            sum(dist[(lo + k) % 360] for k in range(width)), abs=1e-9)
        checked += 1
    assert checked > 150
