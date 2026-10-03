"""Does a swell's great-circle path from a storm to a buoy cross land?

The land is `collector.coastline`'s Natural Earth polygons (eastern Pacific,
islands under 50 km dropped). Sampled every `STEP_KM` along the path; one
sample inside a polygon blocks it. A blocked path is a hard shadow: nothing is
diffracted round a peninsula 1,200 km long, which is the case this exists for
(Polo, BRIEFING §37b).

Pure Python; never on the observed chain's own numbers, only on which best-track
fixes a forward band may use (`forecast.stormtrack`).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR

from .swell import destination_point, great_circle_km, initial_bearing

LAND = "shoreline/ne10m_land_epac.json"
STEP_KM = 10.0


@lru_cache(maxsize=None)
def load_land(data_dir: str = str(DEFAULT_DATA_DIR)) -> tuple:
    """(ring, bbox) per polygon; empty when the file was never fetched."""

    path = Path(data_dir) / LAND
    if not path.exists():
        return ()
    rings = json.loads(path.read_text(encoding="utf-8"))["polygons"]
    out = []
    for ring in rings:
        lons = [p[0] for p in ring]
        lats = [p[1] for p in ring]
        out.append((tuple(map(tuple, ring)), (min(lons), min(lats), max(lons), max(lats))))
    return tuple(out)


def inside(lat: float, lon: float, ring) -> bool:
    """Ray casting in lon/lat: fine at these scales, nowhere near a pole."""

    hit = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat):
            if lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
                hit = not hit
        j = i
    return hit


def on_land(lat: float, lon: float, land) -> bool:
    for ring, (x0, y0, x1, y1) in land:
        if x0 <= lon <= x1 and y0 <= lat <= y1 and inside(lat, lon, ring):
            return True
    return False


def blocked(source: tuple[float, float], buoy: tuple[float, float], land) -> bool:
    """True when the great circle from `source` to `buoy` crosses land.

    The endpoints themselves are not tested: a fix is a storm's centre, and a
    storm over land sends no swell anyway (its fix is then dropped as blocked
    by the first sample off its centre).
    """

    if not land:
        return False
    total = great_circle_km(source, buoy)
    bearing = initial_bearing(source, buoy)
    s = STEP_KM
    while s < total - STEP_KM / 2:
        lat, lon = destination_point(source, bearing, s)
        if on_land(lat, lon, land):
            return True
        s += STEP_KM
    return False
