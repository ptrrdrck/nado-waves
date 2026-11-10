"""The map's outer seabed, for context out past Tanner Bank.

    python -m mocks.swell_fill.context OUT.json [--zoom 10]

The rays' grids (CoNED and GMRT, `rays.py`) stop ~30 km from the breaks. Past
them, for context only, the map shows AWS's open Terrain Tiles (Mapzen's
"Joerd" synthesis, Terrarium encoding: its sea floor is ETOPO1 and other
public models), fetched at build time, mosaicked and shaded as `rays.py`
shades the grids, so the two read as one picture. Nothing is traced over it
and nothing is computed from it. Fetched tiles are cached under the
directory `--cache` names (default: none). A MOCK.

Its west edge sits just past NDBC 46047, Tanner Bank's buoy, whose
coordinate is fetched metadata (`forecast.siting.load_coordinates`), never
typed.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import math
import urllib.request
from pathlib import Path

import numpy as np

from forecast.siting import load_coordinates

TILE_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
SOURCE = "Terrain Tiles (AWS Open Data; ETOPO1 and other public models)"
#: How far past each edge of the breaks-to-46047 box the context reaches, degrees.
PAD_DEG = (0.35, 0.9)          # (lon, lat)
#: The coarse picture's reach, in breaks-to-46047 distances every way.
FAR_TIMES = 2.2
LEVELS = (5, 10, 20, 50, 100, 200, 500, 1000, 2000)


def tile_xy(lat: float, lon: float, z: int) -> tuple[float, float]:
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def tile_lat(y: float, z: int) -> float:
    n = 2 ** z
    return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))


def fetch(z: int, x: int, y: int, cache: Path | None) -> np.ndarray:
    from PIL import Image

    path = cache / f"{z}_{x}_{y}.png" if cache else None
    if path and path.exists():
        raw = path.read_bytes()
    else:
        with urllib.request.urlopen(TILE_URL.format(z=z, x=x, y=y), timeout=60) as r:
            raw = r.read()
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    a = np.asarray(Image.open(io.BytesIO(raw)).convert("RGB"), dtype=float)
    return a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768     # metres


def shade(elev: np.ndarray) -> np.ndarray:
    """As rays.seabed_png shades depth below MSL: greys, lighter for shallower,
    contours, land lighter still."""

    water = elev < 0
    d = np.clip(np.where(water, -elev, 1.0), 1.0, 4000.0)
    t = np.log10(d) / np.log10(2000.0)
    grey = np.clip(92 - 62 * t, 18, 255)
    img = np.where(water, grey, 150.0)
    rgb = np.stack([img * 0.92, img * 0.98, img * 1.06], -1)
    depth = np.where(water, -elev, 0.0)
    edge = np.zeros(elev.shape, bool)
    for level in LEVELS:
        above = depth >= level
        e = np.zeros_like(above)
        e[:-1] |= above[:-1] != above[1:]
        e[:, :-1] |= above[:, :-1] != above[:, 1:]
        edge |= e & water
    rgb[edge] = rgb[edge] * 0.55 + 255 * 0.45 * 0.6
    return np.clip(rgb, 0, 255).astype(np.uint8)


def mosaic(south: float, west: float, north: float, east: float, zoom: int,
           cache: Path | None) -> dict:
    """One shaded picture of the tiles covering a box, at one zoom."""

    from PIL import Image

    x0, y1 = tile_xy(south, west, zoom)
    x1, y0 = tile_xy(north, east, zoom)
    xs = range(int(math.floor(x0)), int(math.floor(x1)) + 1)
    ys = range(int(math.floor(y0)), int(math.floor(y1)) + 1)
    rows = [np.concatenate([fetch(zoom, x, y, cache) for x in xs], axis=1) for y in ys]
    elev = np.concatenate(rows, axis=0)
    n = 2 ** zoom
    bounds = [[tile_lat(ys[-1] + 1, zoom), xs[0] / n * 360 - 180],
              [tile_lat(ys[0], zoom), (xs[-1] + 1) / n * 360 - 180]]
    buf = io.BytesIO()
    Image.fromarray(shade(elev), "RGB").convert("P", palette=Image.ADAPTIVE, colors=64).save(
        buf, "PNG", optimize=True)
    return {"png": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(), "bounds": bounds}


def build(breaks: list[tuple[float, float]], zoom: int = 10, cache: Path | None = None) -> dict:
    """Two pictures, back to front: a coarse one (zoom - 2) reaching
    `FAR_TIMES` the breaks-to-46047 distance every way, which is as far as
    the map can show at its widest; and a finer one over the breaks and
    46047."""

    tanner = load_coordinates()["46047"]
    lats = [p[0] for p in breaks] + [tanner[0]]
    lons = [p[1] for p in breaks] + [tanner[1]]
    south, north = min(lats) - PAD_DEG[1], max(lats) + PAD_DEG[1]
    west, east = min(lons) - PAD_DEG[0], max(lons) + PAD_DEG[0]
    near = mosaic(south, west, north, east, zoom, cache)
    cla = sum(p[0] for p in breaks) / len(breaks)
    clo = sum(p[1] for p in breaks) / len(breaks)
    km = FAR_TIMES * 111.32 * math.hypot(tanner[0] - cla, (tanner[1] - clo) * math.cos(math.radians(cla)))
    dla, dlo = km / 111.32, km / (111.32 * math.cos(math.radians(cla)))
    far = mosaic(cla - dla, clo - dlo, cla + dla, clo + dlo, zoom - 2, cache)
    return {"layers": [far, near], "source": SOURCE, "tanner": list(tanner)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--zoom", type=int, default=10)
    ap.add_argument("--cache", type=Path)
    ap.add_argument("--breaks", type=Path, default=Path(__file__).resolve().parents[2] / "forecast" / "spots.json")
    a = ap.parse_args()
    from forecast.geometry import load
    spots = [s.position for s in load()[0] if s.id.startswith("coronado")]
    out = build(spots, a.zoom, a.cache)
    a.out.write_text(json.dumps(out), encoding="utf-8")
    for layer in out["layers"]:
        print(layer["bounds"], f"{len(layer['png']) / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
