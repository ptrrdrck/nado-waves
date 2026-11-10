"""The swell-fill map's seabed as map tiles, drawn straight from the grids.

    python -m mocks.swell_fill.tiles OUT_DIR

Three layers, each from the grids fit for its zoom, so nothing is drawn finer
than its source or sampled coarser than a pixel:

- `context`, zooms 6-9: `collector.bathymetry`'s GMRT context grid (400 m),
  out past Tanner Bank. Read by no chain.
- `inner`, zooms 10-12: the CoNED regional grid (32 m), then GMRT's outer
  (90 m), the rays' own grids.
- `near`, zooms 13-14: the CoNED nearshore grid (8 m), then the regional.

Each tile is 256 px in Web Mercator ({z}/{x}/{y}.png), shaded as the map's
seabed is: greys, lighter for shallower, depth below mean sea level as the
ray tracer reads it, contours at 5, 10, 20, 50, 100, 200, 500, 1,000 and
2,000 m, land lighter still, and clear where a layer's grids have no cell, so
the layer under it shows. A tile with no cell at all is not written. The page
loads only the tiles in view (Leaflet's tile layers), so a wider grid costs
disk and nothing on screen. Writes OUT_DIR/manifest.json: each layer's zooms
and bounds. A MOCK.
"""
from __future__ import annotations

import argparse
import io
import json
import math
from pathlib import Path

import numpy as np

from forecast import utm as U
from forecast.raytrace import Bathymetry, H_LAND

from .context import load as load_context

TILE = 256
LEVELS = (5, 10, 20, 50, 100, 200, 500, 1000, 2000)
#: name -> (zooms, the grids it is drawn from, finest first, how many of them
#: bound it: the near layer covers the nearshore grid's box, the regional only
#: filling any cell it lacks)
LAYERS = {
    "context": ((6, 9), ("context",), 1),
    "inner": ((10, 12), ("regional", "outer"), 2),
    "near": ((13, 14), ("nearshore", "regional"), 1),
}


def to_utm(lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """`forecast.utm.to_utm` on arrays: the same Krüger series, the same constants."""

    phi, lam = np.radians(lat), np.radians(lon) - U._LON0
    t = np.sinh(np.arctanh(np.sin(phi)) - U._E * np.arctanh(U._E * np.sin(phi)))
    xi = np.arctan2(t, np.cos(lam))
    eta = np.arctanh(np.sin(lam) / np.sqrt(1 + t * t))
    x = eta + sum(a * np.cos(2 * j * xi) * np.sinh(2 * j * eta) for j, a in enumerate(U._ALPHA, 1))
    y = xi + sum(a * np.sin(2 * j * xi) * np.cosh(2 * j * eta) for j, a in enumerate(U._ALPHA, 1))
    return U._E0 + U._K0 * U._AR * x, U._K0 * U._AR * y


def grids() -> dict[str, Bathymetry]:
    """Each grid on its own, as `Bathymetry.load` reads it."""

    full = Bathymetry.load()
    out = {name: Bathymetry([g], full.msl_offset_m, (name,)) for name, g in zip(full.names, full.grids)}
    ctx = load_context()
    if ctx is not None:
        out["context"] = ctx[0]
    return out


def lat_of(y: np.ndarray, z: int) -> np.ndarray:
    return np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * y / 2 ** z))))


def lon_of(x: np.ndarray, z: int) -> np.ndarray:
    return x / 2 ** z * 360.0 - 180.0


def tile_of(lat: float, lon: float, z: int) -> tuple[float, float]:
    n = 2 ** z
    return ((lon + 180) / 360 * n,
            (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)


def sample(bathys: list[Bathymetry], lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Depth (m, positive water) and coverage from the first grid holding each point."""

    x, y = to_utm(lat.ravel(), lon.ravel())
    h = np.full(x.shape, np.nan)
    todo = np.ones(x.shape, bool)
    for b in bathys:
        if not todo.any():
            break
        idx = np.flatnonzero(todo)
        got, *_rest, cov = b.sample(x[idx], y[idx])
        ok = cov & np.isfinite(got)
        h[idx[ok]] = got[ok]
        todo[idx[ok]] = False
    return h.reshape(lat.shape), (~todo).reshape(lat.shape)


def shade(h: np.ndarray, covered: np.ndarray) -> np.ndarray:
    """RGBA for a padded (258 x 258) block; the caller crops the pad."""

    water = covered & (h > H_LAND)
    land = covered & ~water
    d = np.clip(np.where(water, h, 1.0), 1.0, 4000.0)
    grey = np.clip(92 - 62 * np.log10(d) / np.log10(2000.0), 18, 255)
    img = np.where(water, grey, 150.0)
    rgb = np.stack([img * 0.92, img * 0.98, img * 1.06], -1)
    depth = np.where(water, h, 0.0)
    edge = np.zeros(h.shape, bool)
    for level in LEVELS:
        above = depth >= level
        e = np.zeros_like(above)
        e[:-1] |= above[:-1] != above[1:]
        e[:, :-1] |= above[:, :-1] != above[:, 1:]
        edge |= e & water
    rgb[edge] = rgb[edge] * 0.55 + 255 * 0.45 * 0.6
    alpha = np.where(covered, 255, 0)
    return np.dstack([np.clip(rgb, 0, 255), alpha]).astype(np.uint8)


def bounds_of(bathys: list[Bathymetry]) -> list[list[float]]:
    """The lat/lon box round every grid of a layer."""

    lats, lons = [], []
    for b in bathys:
        for g in b.grids:
            left, top = g.left, g.top
            right, bottom = left + g.cell * g.depth.shape[1], top - g.cell * g.depth.shape[0]
            for x in (left, right):
                for y in (bottom, top):
                    la, lo = U.from_utm(x, y)
                    lats.append(la); lons.append(lo)
    return [[min(lats), min(lons)], [max(lats), max(lons)]]


def build(out: Path) -> dict:
    from PIL import Image

    have = grids()
    manifest = {"tile": TILE, "layers": []}
    written = 0
    for name, ((z0, z1), names, bounding) in LAYERS.items():
        bathys = [have[n] for n in names if n in have]
        if not bathys or names[0] not in have:
            print(f"{name}: {names[0]} not present; skipped")
            continue
        (south, west), (north, east) = bounds_of([have[n] for n in names[:bounding] if n in have])
        count = 0
        for z in range(z0, z1 + 1):
            fx0, fy1 = tile_of(south, west, z)
            fx1, fy0 = tile_of(north, east, z)
            for tx in range(int(fx0), int(fx1) + 1):
                for ty in range(int(fy0), int(fy1) + 1):
                    # one pixel of pad each side, so contours meet across tiles
                    px = (np.arange(-1, TILE + 1) + 0.5) / TILE
                    lon = lon_of(tx + px, z)
                    lat = lat_of(ty + px, z)
                    LON, LAT = np.meshgrid(lon, lat)
                    h, cov = sample(bathys, LAT, LON)
                    if not cov.any():
                        continue
                    rgba = shade(h, cov)[1:-1, 1:-1]
                    path = out / str(z) / str(tx) / f"{ty}.png"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    buf = io.BytesIO()
                    Image.fromarray(rgba, "RGBA").quantize(colors=64, method=Image.Quantize.FASTOCTREE).save(
                        buf, "PNG", optimize=True)
                    path.write_bytes(buf.getvalue())
                    count += 1
        written += count
        manifest["layers"].append({"name": name, "zooms": [z0, z1], "bounds": [[south, west], [north, east]],
                                   "grids": [n for n in names if n in have], "tiles": count})
        print(f"{name}: zooms {z0}-{z1}, {count} tiles, from {[n for n in names if n in have]}")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    size = sum(p.stat().st_size for p in out.rglob("*.png"))
    print(f"{written} tiles, {size / 1e6:.2f} MB")
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    a = ap.parse_args()
    build(a.out)


if __name__ == "__main__":
    main()
