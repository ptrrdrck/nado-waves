"""Land between the hurricanes and the buoys: Natural Earth, clipped to the eastern Pacific.

Run: ``python -m collector.coastline``

NOAA's ENC stops at 32.38 N (`collector.shoreline`), and the swell a hurricane
off Mexico sends to these buoys has to clear the Baja peninsula first. BRIEFING
§37b: Polo's strongest days sat where a straight path to 46047 runs past Cabo
San Lucas and up the peninsula, and with no land modelled those days diluted
the days whose swell had open water. This is the land that says which.

Source: Natural Earth 1:10m land (public domain), read from its own repository
at a PINNED commit, so the file can be fetched again byte for byte, and its
SHA-256 is stored beside the result. 1:10m places a coast to ~1 km: ample for a
path test thousands of kilometres long, and nowhere near the ENC charts the
breaks' geometry uses, which it never replaces.

Stored: ``data/shoreline/ne10m_land_epac.json`` — every land polygon's outer
ring clipped to `BBOX` (Sutherland-Hodgman against the box), keeping only
polygons whose clipped extent is at least `MIN_EXTENT_KM` across. Smaller
islands are dropped on purpose: a swell wraps round an island tens of
kilometres across within a few hundred kilometres (the Coronado Islands' own
shadow is under 5%, CLAUDE.md), so an island 35 km long does not stop a train
crossing an ocean. Cedros and Guadalupe fall under the cut; the peninsula and
the mainland do not. Holes are ignored: none matters at sea.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import urllib.request
from pathlib import Path

from .common import DEFAULT_DATA_DIR, utcnow, write_step_summary

COMMIT = "ca96624a56bd078437bca8184e78163e5039ad19"
URL = (f"https://raw.githubusercontent.com/nvkelso/natural-earth-vector/{COMMIT}"
       f"/geojson/ne_10m_land.geojson")
#: lon_min, lat_min, lon_max, lat_max: the hurricanes' sea and the buoys.
BBOX = (-140.0, 5.0, -95.0, 35.0)
MIN_EXTENT_KM = 50.0
OUT = "shoreline/ne10m_land_epac.json"


def clip(ring: list[list[float]], box=BBOX) -> list[list[float]]:
    """Sutherland-Hodgman: a polygon ring against an axis-aligned box."""

    x0, y0, x1, y1 = box
    edges = [
        (lambda p: p[0] >= x0, lambda a, b: _cross_x(a, b, x0)),
        (lambda p: p[0] <= x1, lambda a, b: _cross_x(a, b, x1)),
        (lambda p: p[1] >= y0, lambda a, b: _cross_y(a, b, y0)),
        (lambda p: p[1] <= y1, lambda a, b: _cross_y(a, b, y1)),
    ]
    out = [list(p[:2]) for p in ring]
    for inside, cross in edges:
        if not out:
            break
        src, out = out, []
        prev = src[-1]
        for cur in src:
            if inside(cur):
                if not inside(prev):
                    out.append(cross(prev, cur))
                out.append(cur)
            elif inside(prev):
                out.append(cross(prev, cur))
            prev = cur
    return out


def _cross_x(a, b, x):
    t = (x - a[0]) / (b[0] - a[0])
    return [x, a[1] + t * (b[1] - a[1])]


def _cross_y(a, b, y):
    t = (y - a[1]) / (b[1] - a[1])
    return [a[0] + t * (b[0] - a[0]), y]


def extent_km(ring: list[list[float]]) -> float:
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    mid = math.radians((min(lats) + max(lats)) / 2)
    dx = (max(lons) - min(lons)) * 111.32 * math.cos(mid)
    dy = (max(lats) - min(lats)) * 110.57
    return max(dx, dy)


def polygons(geojson: dict) -> list[list[list[float]]]:
    out = []
    for feature in geojson["features"]:
        geom = feature["geometry"]
        parts = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        for poly in parts:
            ring = clip(poly[0])
            if len(ring) >= 3 and extent_km(ring) >= MIN_EXTENT_KM:
                out.append([[round(x, 4), round(y, 4)] for x, y in ring])
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = parser.parse_args(argv)
    request = urllib.request.Request(URL, headers={"User-Agent": "nado-waves coastline"})
    with urllib.request.urlopen(request, timeout=120) as response:
        raw = response.read()
    rings = polygons(json.loads(raw))
    out = Path(args.data_dir) / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "source": URL,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "fetched_utc": utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bbox": BBOX,
        "min_extent_km": MIN_EXTENT_KM,
        "note": "outer rings only, clipped to bbox; islands under min_extent_km dropped",
        "polygons": rings,
    }), encoding="utf-8")
    text = f"{len(rings)} land polygons, {sum(len(r) for r in rings)} vertices -> {out}"
    print(text)
    write_step_summary(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
