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
#: The land is rasterised once onto this grid (degrees, ~5 km): a path is
#: sampled every 10 km, and ray-casting the 4,700-vertex mainland ring at every
#: sample made one season's report minutes long and a live collection slower
#: than the collection itself.
CELL_DEG = 0.05


class Land:
    """Natural Earth's land on a regular grid, filled row by row (scanline)."""

    def __init__(self, rings: list, bbox: tuple[float, float, float, float]):
        self.rings = rings
        self.x0, self.y0, self.x1, self.y1 = bbox
        self.nx = int(round((self.x1 - self.x0) / CELL_DEG))
        self.ny = int(round((self.y1 - self.y0) / CELL_DEG))
        self.rows: list[list[tuple[float, float]]] = []
        for j in range(self.ny):
            lat = self.y0 + (j + 0.5) * CELL_DEG
            spans = []
            for ring in rings:
                xs = []
                n = len(ring)
                for i in range(n):
                    (xa, ya), (xb, yb) = ring[i - 1], ring[i]
                    if (ya > lat) != (yb > lat):
                        xs.append(xa + (lat - ya) * (xb - xa) / (yb - ya))
                xs.sort()
                spans += list(zip(xs[0::2], xs[1::2]))
            self.rows.append(spans)

    def __bool__(self) -> bool:
        return bool(self.rings)

    def __contains__(self, point: tuple[float, float]) -> bool:
        lat, lon = point
        if not (self.y0 <= lat < self.y1 and self.x0 <= lon <= self.x1):
            return False
        row = self.rows[min(int((lat - self.y0) / CELL_DEG), self.ny - 1)]
        return any(a <= lon <= b for a, b in row)


@lru_cache(maxsize=None)
def load_land(data_dir: str = str(DEFAULT_DATA_DIR)):
    """The rasterised land; an empty tuple when the file was never fetched."""

    path = Path(data_dir) / LAND
    if not path.exists():
        return ()
    data = json.loads(path.read_text(encoding="utf-8"))
    return Land([[tuple(p) for p in ring] for ring in data["polygons"]], tuple(data["bbox"]))


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
    return bool(land) and (lat, lon) in land


@lru_cache(maxsize=65536)
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
