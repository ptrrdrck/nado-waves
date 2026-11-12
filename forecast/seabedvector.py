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

- `wide`, from zoom 0: GMRT at 2 km, 1,200 km round the breaks, under
  everything, so the widest view is seabed to its corners. Read by no chain.
- `context`, from zoom 0: `collector.bathymetry`'s GMRT context grid
  (400 m), out past Tanner Bank, over the wide. Read by no chain.
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

Every band and line is cut to one outline, the grid's covered cells set two
tolerances in (`edge`), so all of a grid's bands end on the same line and the
grid beneath shows past it: simplified one by one, and each straight in UTM
but not on the map, they ended kilometres apart, and the land colour drew a
line along the grid's edge across open sea.

Each grid is smoothed over about a cell before it is contoured (`TIERS`), so
a line does not trace the survey's cell-scale noise, and simplified to a few
metres near the beach and 80 m out past Tanner Bank. A display, never a
depth anyone reads: the chain reads the grids themselves.

`manifest.json` holds each file's zoom, size and fingerprint and each grid's
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
#: How far inside a grid's covered cells its bands are cut, in simplifying
#: tolerances: past the 1 x a simplified band can wander from the edge (`edge`).
EDGE_INSET = 2.0
#: The longest stretch of that outline left without a vertex, in tolerances.
EDGE_STEP = 250.0
#: The strip along a grid's edge where only the band shown is drawn, in CSS
#: pixels at the zoom the tier is first drawn (`features`, `strip_m`).
STRIP_PX = 3.0
#: About the map's widest zoom on a phone (it opens far nearer).
WIDEST_ZOOM = 4
#: grid -> (the zoom it is drawn from, smoothing sigma in cells, simplifying
#: tolerance in metres, decimal places of a degree kept), coarsest first: the
#: order they are drawn in.
TIERS = {
    "wide": (0, 0.8, 400.0, 3),
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


def features(grid: Grid, sigma: float, tol: float, dec: int, strip: float | None = None) -> list[dict]:
    """One grid's bands, contours and shoreline as GeoJSON features.

    Within `strip` metres of the grid's edge each band is cut away under the
    next deeper, so only the band shown reaches the edge, and the grid's land
    colour lies under nothing there. MapLibre simplifies every shape again as
    it draws it, each alone, so edges that meet exactly in the file part by
    up to a fifth of a pixel on screen; nested, the land colour showed in
    that gap as a faint dotted line along the context grid's edge across open
    sea (owner's report, 2026-11-12, on an iPhone, after the fill outlines
    were gone). Cut, a gap shows the coarser grid's sea beneath. Nothing else
    changes: in the strip the band shown is the one left."""

    import contourpy
    from shapely import segmentize, simplify, union_all
    from shapely.geometry import LineString, Polygon

    depth = smooth(grid.depth, sigma)
    rows, cols = depth.shape
    x = grid.left + (np.arange(cols) + 0.5) * grid.cell
    y = grid.top - (np.arange(rows) + 0.5) * grid.cell
    gen = contourpy.contour_generator(x, y, np.ma.masked_invalid(depth),
                                      fill_type="OuterOffset", line_type="Separate", name="serial")
    least = (2 * tol) ** 2

    def filled(lower: float) -> list[Polygon]:
        polys, offsets = gen.filled(lower, 1e9)
        return [Polygon(pts[off[0]:off[1]], [pts[off[i]:off[i + 1]] for i in range(1, len(off) - 1)])
                for pts, off in zip(polys, offsets)]

    clip = edge(filled(-1e9), tol)
    inner = segmentize(clip.buffer(-(strip if strip is not None else EDGE_INSET * tol), join_style="mitre"),
                       EDGE_STEP * tol)
    bands = []
    for lower in (-1e9, H_LAND) + BANDS:
        bands.append(union_all([simplify(poly, tol, preserve_topology=True).intersection(clip)
                                for poly in filled(lower)] or [Polygon()]))
    out: list[dict] = []
    for band, shape in enumerate(bands):
        if band + 1 < len(bands) and not bands[band + 1].is_empty:
            # Within the strip along the grid's edge, only the band shown.
            shape = union_all([shape.intersection(inner), shape.difference(inner).difference(bands[band + 1])])
        for part in _parts(shape, "Polygon"):
            if part.area < least:
                continue
            coords = [_lonlat(np.asarray(part.exterior.coords), dec)]
            coords += [_lonlat(np.asarray(h.coords), dec) for h in part.interiors if Polygon(h).area >= least]
            out.append({"type": "Feature", "properties": {"k": "fill", "b": band - 1},
                        "geometry": {"type": "Polygon", "coordinates": coords}})
    for level in (H_LAND,) + LINES:
        for pts in gen.lines(level):
            if len(pts) < 3:
                continue
            props = {"k": "coast"} if level == H_LAND else {"k": "line", "d": level}
            for line in _parts(simplify(LineString(pts), tol).intersection(clip), "LineString"):
                if line.length < 4 * tol:
                    continue
                out.append({"type": "Feature", "properties": props,
                            "geometry": {"type": "LineString", "coordinates": _lonlat(np.asarray(line.coords), dec)}})
    return out


def _parts(shape, kind: str) -> list:
    """The pieces of `kind` in a shapely result, whatever it came back as."""

    if shape.is_empty:
        return []
    if shape.geom_type == kind:
        return [shape]
    return [p for g in getattr(shape, "geoms", []) for p in _parts(g, kind)]


def edge(cover: list, tol: float):
    """ONE outline every band and line of a grid is cut to: the grid's
    covered cells, simplified as the bands are and set `EDGE_INSET` x the
    tolerance inside. Each band simplified alone wanders up to `tol` from the
    grid's edge, a different way each, so the land colour under them all (b
    -1) showed as a thin line along a straight grid edge across open sea
    (owner's report, 2026-11-11: the context grid's edge over the wide).
    Cut to one outline, every band that reaches the edge ends on the same
    line, and the coarser grid shows past it.

    The outline is then given a vertex every `EDGE_STEP` tolerances. A
    straight line in UTM is a curve in the map's projection, so a band whose
    edge was one chord across the grid's 900 km side bowed kilometres away
    from a band whose edge had vertices along it, even where the two agreed
    exactly in UTM; with the same vertices, every band bends the same way."""

    from shapely import segmentize, simplify, union_all

    clip = simplify(union_all(cover), tol, preserve_topology=True).buffer(-EDGE_INSET * tol, join_style="mitre")
    return segmentize(clip, EDGE_STEP * tol)


def fingerprint(path: Path) -> str:
    """A file's content as 16 hex digits of its SHA-256: the version the page
    keeps a copy under (`kept` in app/forecast.html), so a changed file is a
    new copy and an unchanged one is never fetched twice."""

    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def strip_m(minzoom: int) -> float:
    """`STRIP_PX` CSS pixels in metres at the zoom a tier is first drawn (no
    wider than the map's widest view, `WIDEST_ZOOM`), at the breaks'
    latitude, MapLibre's 512 px tiles."""

    zoom = max(minzoom, WIDEST_ZOOM)
    return STRIP_PX * 2 * math.pi * 6_378_137 * math.cos(math.radians(32.7)) / (512 * 2 ** zoom)


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
        feats = features(grid, sigma, tol, dec, strip_m(minzoom))
        path = out / f"{name}.geojson"
        path.write_text(json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":")),
                        encoding="utf-8")
        manifest["tiers"].append({"name": name, "file": path.name, "minzoom": minzoom,
                                  "features": len(feats), "bytes": path.stat().st_size,
                                  "sha": fingerprint(path)})
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
        if not f.exists() or f.stat().st_size != tier["bytes"] or fingerprint(f) != tier.get("sha"):
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
