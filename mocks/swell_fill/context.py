"""The map's outer seabed, for context out past Tanner Bank.

    python -m mocks.swell_fill.context OUT.json

The rays' grids (CoNED and GMRT) stop ~30 km from the breaks. Past them, for
context only, the map draws `collector.bathymetry`'s `context` grid: GMRT,
coarse, round the breaks and the three buoys the page shows, fetched on
Actions by bathymetry-context.yml (gmrt.org is denied from a session). It is
shaded as `rays.py` shades the grids, so the two read as one picture. Nothing
is traced over it and nothing is computed from it.

Until that grid is in `data/bathymetry/` there is no context picture: the
map shows the rays' grids alone, and its own deep grey past them. A MOCK.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from forecast.raytrace import Bathymetry, Grid
from forecast.utm import from_utm

from .rays import seabed_png

DIR = Path(__file__).resolve().parents[2] / "data" / "bathymetry"
SOURCE = "GMRT (the Global Multi-Resolution Topography synthesis), the context grid"


def load(directory: Path = DIR) -> tuple[Bathymetry, dict] | None:
    """The context grid as a one-grid Bathymetry, as `Bathymetry.load` reads
    a GMRT grid (already sea level), or None when it has not been fetched."""

    if not (directory / "context.npz").exists():
        return None
    meta = json.loads((directory / "context.json").read_text())
    raw = np.load(directory / "context.npz")["elevation_dm"].astype(float)
    raw[raw == meta["nodata"]] = np.nan
    a, _, left, _, _, top = meta["transform"]
    return Bathymetry([Grid.from_elevation(raw / 10.0, left, top, a, 0.0)], None, ("context",)), meta


def build(directory: Path = DIR, px: int = 1400) -> dict | None:
    got = load(directory)
    if got is None:
        return None
    bathy, meta = got
    left, bottom, right, top = meta["bounds_utm"]
    corners = [from_utm(x, y) for x in (left, right) for y in (bottom, top)]
    # The lat/lon box round the grid; outside the grid the picture is clear.
    south, north = min(c[0] for c in corners), max(c[0] for c in corners)
    west, east = min(c[1] for c in corners), max(c[1] for c in corners)
    png, bounds = seabed_png(bathy, south, west, north, east, px=px, feather=0.0)
    return {"layers": [{"png": png, "bounds": bounds}], "source": SOURCE,
            "retrieved_utc": meta.get("retrieved_utc")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    a = ap.parse_args()
    out = build()
    if out is None:
        print(f"no context grid in {DIR}: run bathymetry-context.yml on Actions")
        return
    a.out.write_text(json.dumps(out), encoding="utf-8")
    print(a.out, out["layers"][0]["bounds"], f"{len(out['layers'][0]['png']) / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
