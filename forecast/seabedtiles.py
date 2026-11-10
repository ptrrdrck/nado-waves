"""The Swell card map's seabed, as map tiles drawn straight from the grids.

    python -m forecast.seabedtiles            # rebuild data/seabed_tiles/
    python -m forecast.seabedtiles --check    # are the tiles from today's grids?

PRECOMPUTE (numpy and Pillow, requirements-precompute.txt). The map on the
LIVE and Forecast tabs draws the seabed rather than a photograph (owner's
choice, 2026-11-10): the same depths the rays are traced over, so what bends
the swell is what the reader sees. Three layers, each from the grids fit for
its zoom, so nothing is drawn finer than its source or sampled coarser than a
pixel:

- `context`, zooms 5-9: `collector.bathymetry`'s GMRT context grid (400 m),
  out past Tanner Bank. Read by no chain.
- `inner`, zooms 10-12: the CoNED regional grid (32 m), then GMRT's outer
  (90 m): the rays' own grids.
- `near`, zooms 13-14: the CoNED nearshore grid (8 m), then the regional.

Each tile is 256 px in Web Mercator ({z}/{x}/{y}.png), shaded: greys, lighter
for shallower, depth below mean sea level as the ray tracer reads it (CoNED
carried from NAVD88 by the grid's own fetched offset, GMRT already sea level),
contours at 5, 10, 20, 50, 100, 200, 500, 1,000 and 2,000 m, land lighter
still, and clear where a layer's grids have no cell, so the layer under it
shows. A tile with no cell at all is not written. The page loads only the tiles
in view, so a wider grid costs disk and nothing on screen.

`manifest.json` holds each layer's zooms, bounds and tile count, and each
grid's `retrieved_utc`, so a test can tell when a grid has been fetched again
and its tiles not rebuilt. The bathymetry workflows rebuild them after every
fetch. Derived but tracked, as `data/series/` is: a collection cannot build
them (they need numpy), and the page cannot wait for them.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np

from . import utm as U
from .raytrace import BATHY_DIR, H_LAND, Bathymetry, Grid

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "seabed_tiles"
TILE = 256
LEVELS = (5, 10, 20, 50, 100, 200, 500, 1000, 2000)
#: name -> (zooms, the grids it is drawn from finest first, how many of those
#: bound it: the near layer covers the nearshore grid's box, the regional only
#: filling any cell it lacks)
LAYERS = {
    "context": ((5, 9), ("context",), 1),
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


def load_grid(name: str, directory: Path = BATHY_DIR) -> tuple[Bathymetry, dict] | None:
    """One stored grid as a one-grid Bathymetry, read as `Bathymetry.load`
    reads it (CoNED shifted from NAVD88 by its own fetched offset), with its
    sidecar; None when it is not stored."""

    if not (directory / f"{name}.npz").exists():
        return None
    meta = json.loads((directory / f"{name}.json").read_text(encoding="utf-8"))
    raw = np.load(directory / f"{name}.npz")["elevation_dm"].astype(float)
    raw[raw == meta["nodata"]] = np.nan
    a, _, left, _, _, top = meta["transform"]
    shift = 0.0
    offset = None
    if meta["vertical_datum"] == "NAVD88":
        offset = meta["datum"].get("msl_above_navd88_m")
        shift = offset or 0.0
    grid = Grid.from_elevation(raw / 10.0, left, top, a, shift)
    return Bathymetry([grid], offset, (name,)), meta


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
    """RGBA for a padded block; the caller crops the pad."""

    water = covered & (h > H_LAND)
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
    """The lat/lon box round every grid given."""

    lats, lons = [], []
    for b in bathys:
        for g in b.grids:
            right = g.left + g.cell * g.depth.shape[1]
            bottom = g.top - g.cell * g.depth.shape[0]
            for x in (g.left, right):
                for y in (bottom, g.top):
                    la, lo = U.from_utm(x, y)
                    lats.append(la)
                    lons.append(lo)
    return [[round(min(lats), 5), round(min(lons), 5)], [round(max(lats), 5), round(max(lons), 5)]]


def retrieved(directory: Path = BATHY_DIR) -> dict[str, str | None]:
    """Each stored grid's `retrieved_utc`, the tiles' provenance."""

    out = {}
    for name in ("nearshore", "regional", "outer", "context"):
        path = directory / f"{name}.json"
        if path.exists():
            out[name] = json.loads(path.read_text(encoding="utf-8")).get("retrieved_utc")
    return out


def build(out: Path = OUT_DIR, directory: Path = BATHY_DIR) -> dict:
    from PIL import Image

    have = {}
    for name in ("nearshore", "regional", "outer", "context"):
        got = load_grid(name, directory)
        if got is not None:
            have[name] = got[0]
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    manifest = {"tile": TILE, "grids": retrieved(directory), "layers": []}
    total = 0
    for name, ((z0, z1), names, bounding) in LAYERS.items():
        if names[0] not in have:
            print(f"{name}: {names[0]} not stored; skipped")
            continue
        bathys = [have[n] for n in names if n in have]
        (south, west), (north, east) = bounds_of([have[n] for n in names[:bounding] if n in have])
        count = 0
        for z in range(z0, z1 + 1):
            fx0, fy1 = tile_of(south, west, z)
            fx1, fy0 = tile_of(north, east, z)
            # one pixel of pad each side, so contours meet across tiles
            px = (np.arange(-1, TILE + 1) + 0.5) / TILE
            for tx in range(int(fx0), int(fx1) + 1):
                for ty in range(int(fy0), int(fy1) + 1):
                    lon_grid, lat_grid = np.meshgrid(lon_of(tx + px, z), lat_of(ty + px, z))
                    h, cov = sample(bathys, lat_grid, lon_grid)
                    if not cov.any():
                        continue
                    rgba = shade(h, cov)[1:-1, 1:-1]
                    path = out / str(z) / str(tx) / f"{ty}.png"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    buf = io.BytesIO()
                    Image.fromarray(rgba, "RGBA").quantize(
                        colors=64, method=Image.Quantize.FASTOCTREE).save(buf, "PNG", optimize=True)
                    path.write_bytes(buf.getvalue())
                    count += 1
        total += count
        manifest["layers"].append({"name": name, "zooms": [z0, z1],
                                   "bounds": [[south, west], [north, east]],
                                   "grids": [n for n in names if n in have], "tiles": count})
        print(f"{name}: zooms {z0}-{z1}, {count} tiles, from {[n for n in names if n in have]}")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    size = sum(p.stat().st_size for p in out.rglob("*.png"))
    print(f"{total} tiles, {size / 1e6:.2f} MB -> {out}")
    return manifest


def check(out: Path = OUT_DIR, directory: Path = BATHY_DIR) -> list[str]:
    """What is wrong with the stored tiles, if anything: grids fetched again
    since they were drawn, or a layer's tiles missing."""

    problems = []
    path = out / "manifest.json"
    if not path.exists():
        return [f"{path} missing: run python -m forecast.seabedtiles"]
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("grids") != retrieved(directory):
        problems.append("a grid was fetched again since the tiles were drawn: "
                        f"tiles {manifest.get('grids')} against grids {retrieved(directory)}")
    for layer in manifest["layers"]:
        z0, z1 = layer["zooms"]
        found = sum(1 for z in range(z0, z1 + 1) for _ in (out / str(z)).rglob("*.png"))
        if found != layer["tiles"]:
            problems.append(f"{layer['name']}: {found} tiles on disk, manifest says {layer['tiles']}")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    if a.check:
        problems = check()
        for p in problems:
            print(p)
        return 1 if problems else 0
    build()
    return 0


if __name__ == "__main__":
    sys.exit(main())
