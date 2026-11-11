"""The Swell card map's seabed, as vectors drawn straight from the grids.

    python -m forecast.seabedvector            # rebuild data/seabed_vector/
    python -m forecast.seabedvector --check    # are they from today's grids?

PRECOMPUTE (numpy, contourpy and shapely; requirements-precompute.txt). The
map draws the seabed rather than a photograph (owner's choice, 2026-11-10):
the same depths the rays are traced over, so what bends the swell is what the
reader sees. Since 2026-11-11 as VECTORS (owner's request: the 2x raster
tiles still looked "like a retro monitor" on a phone): filled depth bands,
contour lines and the shoreline, sharp at any zoom on any screen, and smaller
than the tiles they replace (about 1.5 MB, 0.4 MB compressed, against 489
tiles and 2.2 MB).

One GeoJSON file per grid, finest drawn on top, each from the zoom its cells
are fit for (`TIERS`):

- `context`, from zoom 0: `collector.bathymetry`'s GMRT context grid
  (400 m), out past Tanner Bank. Read by no chain.
- `outer`, from zoom 8: GMRT's 90 m grid, the rays' outermost.
- `regional`, from zoom 9: CoNED's 32 m grid.
- `nearshore`, from zoom 11: CoNED's 8 m grid.

Depth below mean sea level as the ray tracer reads it (CoNED carried from
NAVD88 by the grid's own fetched offset, GMRT already sea level). Each file
holds:

- the bands as NESTED polygons, `{"k": "fill", "b": n}`: n = -1 is every
  covered cell (the land colour shows where nothing deeper lies over it),
  n = 0 water deeper than `raytrace.H_LAND`, then 5, 10, 20, 50, 100, 200,
  500, 1,000, 2,000, 3,000 and 4,000 m (`BANDS`). Nested, not side by side,
  so simplifying one band's edge can open no gap to the next;
- the contours, `{"k": "line", "d": depth}`, at `LINES`;
- the shoreline, `{"k": "coast"}`, where the depth crosses `H_LAND`.

Each grid is smoothed over about a cell before it is contoured (`TIERS`), so
a line does not trace the survey's cell-scale noise, and simplified to a few
metres near the beach and 80 m out past Tanner Bank. A display, never a
depth anyone reads: the chain reads the grids themselves.

`manifest.json` holds each file's zoom and size and each grid's
`retrieved_utc`, so a test can tell when a grid has been fetched again and the
seabed not redrawn. The bathymetry workflows redraw it after every fetch.
Derived but tracked, as `data/series/` is: a collection cannot build it.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np

from . import utm as U
from .raytrace import BATHY_DIR, H_LAND, Bathymetry, Grid

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "seabed_vector"
#: The bands' shallow edges (m), after the land: index 0 is H_LAND.
BANDS = (5, 10, 20, 50, 100, 200, 500, 1000, 2000, 3000, 4000)
#: The contour lines (m).
LINES = (5, 10, 20, 50, 100, 200, 500, 1000, 2000)
#: grid -> (the zoom it is drawn from, smoothing sigma in cells, simplifying
#: tolerance in metres, decimal places of a degree kept), coarsest first: the
#: order they are drawn in.
TIERS = {
    "context": (0, 0.8, 80.0, 4),
    "outer": (8, 0.8, 20.0, 5),
    "regional": (9, 1.0, 6.0, 5),
    "nearshore": (11, 1.0, 2.0, 5),
}


def load_grid(name: str, directory: Path = BATHY_DIR) -> Grid | None:
    """One stored grid read as `Bathymetry.load` reads it (CoNED shifted from
    NAVD88 by its own fetched offset); None when it is not stored."""

    if not (directory / f"{name}.npz").exists():
        return None
    meta = json.loads((directory / f"{name}.json").read_text(encoding="utf-8"))
    raw = np.load(directory / f"{name}.npz")["elevation_dm"].astype(float)
    raw[raw == meta["nodata"]] = np.nan
    a, _, left, _, _, top = meta["transform"]
    shift = 0.0
    if meta["vertical_datum"] == "NAVD88":
        shift = meta["datum"].get("msl_above_navd88_m") or 0.0
    return Bathymetry([Grid.from_elevation(raw / 10.0, left, top, a, shift)], None, (name,)).grids[0]


def smooth(a: np.ndarray, sigma: float) -> np.ndarray:
    """A Gaussian blur that ignores empty cells (NaN stays NaN)."""

    r = int(math.ceil(3 * sigma))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    ok = np.isfinite(a)
    num, den = np.where(ok, a, 0.0), ok.astype(float)
    for axis in (0, 1):
        num = np.apply_along_axis(lambda v: np.convolve(v, k, "same"), axis, num)
        den = np.apply_along_axis(lambda v: np.convolve(v, k, "same"), axis, den)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(ok, num / den, np.nan)


def _lonlat(coords: np.ndarray, dec: int) -> list[list[float]]:
    out = []
    for x, y in coords:
        la, lo = U.from_utm(float(x), float(y))
        out.append([round(lo, dec), round(la, dec)])
    return out


def features(grid: Grid, sigma: float, tol: float, dec: int) -> list[dict]:
    """One grid's bands, contours and shoreline as GeoJSON features."""

    import contourpy
    from shapely import simplify
    from shapely.geometry import LineString, Polygon

    depth = smooth(grid.depth, sigma)
    rows, cols = depth.shape
    x = grid.left + (np.arange(cols) + 0.5) * grid.cell
    y = grid.top - (np.arange(rows) + 0.5) * grid.cell
    gen = contourpy.contour_generator(x, y, np.ma.masked_invalid(depth),
                                      fill_type="OuterOffset", line_type="Separate", name="serial")
    least = (2 * tol) ** 2
    out: list[dict] = []
    for band, lower in enumerate((-1e9, H_LAND) + BANDS):
        polys, offsets = gen.filled(lower, 1e9)
        for pts, off in zip(polys, offsets):
            rings = [pts[off[i]:off[i + 1]] for i in range(len(off) - 1)]
            shape = simplify(Polygon(rings[0], rings[1:]), tol, preserve_topology=True)
            for part in ([shape] if shape.geom_type == "Polygon" else list(getattr(shape, "geoms", []))):
                if part.is_empty or part.area < least:
                    continue
                coords = [_lonlat(np.asarray(part.exterior.coords), dec)]
                coords += [_lonlat(np.asarray(h.coords), dec) for h in part.interiors if Polygon(h).area >= least]
                out.append({"type": "Feature", "properties": {"k": "fill", "b": band - 1},
                            "geometry": {"type": "Polygon", "coordinates": coords}})
    for level in (H_LAND,) + LINES:
        for pts in gen.lines(level):
            if len(pts) < 3:
                continue
            line = simplify(LineString(pts), tol)
            if line.length < 4 * tol:
                continue
            props = {"k": "coast"} if level == H_LAND else {"k": "line", "d": level}
            out.append({"type": "Feature", "properties": props,
                        "geometry": {"type": "LineString", "coordinates": _lonlat(np.asarray(line.coords), dec)}})
    return out


def retrieved(directory: Path = BATHY_DIR) -> dict[str, str | None]:
    """Each stored grid's `retrieved_utc`, the seabed's provenance."""

    out = {}
    for name in TIERS:
        path = directory / f"{name}.json"
        if path.exists():
            out[name] = json.loads(path.read_text(encoding="utf-8")).get("retrieved_utc")
    return out


def build(out: Path = OUT_DIR, directory: Path = BATHY_DIR) -> dict:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    manifest = {"bands": [H_LAND, *BANDS], "lines": list(LINES), "grids": retrieved(directory), "tiers": []}
    for name, (minzoom, sigma, tol, dec) in TIERS.items():
        grid = load_grid(name, directory)
        if grid is None:
            print(f"{name}: not stored; skipped")
            continue
        feats = features(grid, sigma, tol, dec)
        path = out / f"{name}.geojson"
        path.write_text(json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":")),
                        encoding="utf-8")
        manifest["tiers"].append({"name": name, "file": path.name, "minzoom": minzoom,
                                  "features": len(feats), "bytes": path.stat().st_size})
        print(f"{name}: from zoom {minzoom}, {len(feats)} features, {path.stat().st_size / 1e3:.0f} KB")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    return manifest


def check(out: Path = OUT_DIR, directory: Path = BATHY_DIR) -> list[str]:
    """What is wrong with the stored seabed, if anything: grids fetched again
    since it was drawn, or a file missing or changed."""

    path = out / "manifest.json"
    if not path.exists():
        return [f"{path} missing: run python -m forecast.seabedvector"]
    manifest = json.loads(path.read_text(encoding="utf-8"))
    problems = []
    if manifest.get("grids") != retrieved(directory):
        problems.append("a grid was fetched again since the seabed was drawn: "
                        f"drawn from {manifest.get('grids')}, grids now {retrieved(directory)}")
    for tier in manifest["tiers"]:
        f = out / tier["file"]
        if not f.exists() or f.stat().st_size != tier["bytes"]:
            problems.append(f"{tier['name']}: {f.name} missing or not the file the manifest names")
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
