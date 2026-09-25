"""Seabed depth around Coronado, for refraction and shoaling.

    python -m collector.bathymetry               # grids + datum, archive both
    python -m collector.bathymetry --skip-datum  # grids only (a session can do this)

WHY. The aperture (`forecast.transform`) treats the sea between the buoy and the
beach as if it had no bottom: swell arrives along a straight line or not at
all. Long-period swell does not do that. It bends toward shallow water and
changes height as the depth changes, and around a headland like Point Loma
that is the difference between a hard shadow and a lee that still gets surf.
Refraction and shoaling need the depth, so this fetches it.

SOURCE. The USGS CoNED integrated topobathymetric model for Southern
California (2016), 1 m, NAVD88, EPSG:26911 — "from the Mexican border to Point
Conception, and extending offshore to a depth of 2,847 meters", mirrored in
NOAA's public Digital Coast bucket on AWS. Its southern edge is 32.49 N, so it
does NOT cover the Coronado Islands (32.40-32.45 N, Mexican waters) or the Baja
coast. Those stay what they are in `spots.json`: charted outlines, handled as
blockers, not as seabed. Recorded in the sidecar so nobody reads the grid as
covering them.

Only a decimated window is read, through the file's own overviews over HTTP
range requests: the tiles are about a gigabyte each at 1 m and none of that is
needed at the scales refraction works on.

TWO GRIDS, both derived from `spots.json` and the buoy's NDBC position rather
than typed boxes:

- `regional` — every break, the whole Point Loma outline and buoy 46232, with
  a margin, at 32 m. What backward rays cross between the beach and deep water.
- `nearshore` — the three break chords with a few kilometres around them, at
  8 m. Where the rays start and where shoaling is decided.

DATUM. The grid is NAVD88; waves see mean sea level. The offset between them
at NOAA 9410170 is FETCHED from CO-OPS (`datums` endpoint), never typed. CO-OPS
is denied at CONNECT from a Claude session, so `--skip-datum` stores the grids
with the offset recorded as not fetched; the workflow run fills it in. An
offset recorded as null is a gap, and consumers must treat it as one.

Stored as `data/bathymetry/<grid>.npz` (elevation in decimetres, int16, NAVD88,
nodata -32768) plus `<grid>.json` with the affine transform, the CRS, the
source and what it does not cover. Data files are tracked.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "bathymetry"
STATIONS = ROOT / "data" / "station_metadata.csv"

SOURCE_VRT = ("https://noaa-nos-coastal-lidar-pds.s3.amazonaws.com/dem/"
              "CA_Southern_CoNED_DEM_2016_8658/CA_Southern_CoNED_DEM_2016_m8658_EPSG-26911.vrt")
SOURCE_NAME = "USGS CoNED Southern California topobathymetric DEM, 2016 (1 m, NAVD88)"
SOURCE_CRS = "EPSG:26911"
SOURCE_NODATA = -32767.0

BUOY = "46232"
TIDE_STATION = "9410170"
DATUMS_URL = ("https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/"
              f"{TIDE_STATION}/datums.json?units=metric")

#: Grid name -> (cell size in metres, margin in metres around its anchors).
GRIDS = {"regional": (32.0, 3000.0), "nearshore": (8.0, 3000.0)}

NODATA_DM = -32768
NOT_COVERED = ("the Coronado Islands and the Baja coast (south of the source's "
               "32.49 N edge, Mexican waters)")


def buoy_position(path: Path = STATIONS) -> tuple[float, float]:
    """46232 from NDBC's own metadata, never typed (CLAUDE.md)."""

    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.reader(fh):
            if row and row[0] == BUOY:
                return float(row[4]), float(row[5])
    raise LookupError(f"{BUOY} is not placed in {path}; run collector.metadata on Actions")


def anchors(grid: str) -> list[tuple[float, float]]:
    """The lat/lon points a grid has to contain, from the files that own them."""

    sys.path.insert(0, str(ROOT))
    from forecast.geometry import load

    spots, blockers = load()
    coronado = [s for s in spots if s.id.startswith("coronado_")]
    points = [p for s in coronado for p in s.shoreline]
    if grid == "regional":
        loma = next(b for b in blockers if b.name.startswith("Point Loma"))
        points += [loma.a, loma.b, *loma.outline, buoy_position()]
    return points


def to_utm(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    from forecast.utm import to_utm as one

    return [one(lat, lon) for lat, lon in points]


def box(grid: str, bounds) -> tuple[float, float, float, float]:
    """(left, bottom, right, top) in UTM, snapped to the cell, clipped to the source."""

    cell, margin = GRIDS[grid]
    utm = to_utm(anchors(grid))
    left = math.floor((min(x for x, _ in utm) - margin) / cell) * cell
    right = math.ceil((max(x for x, _ in utm) + margin) / cell) * cell
    bottom = math.floor((min(y for _, y in utm) - margin) / cell) * cell
    top = math.ceil((max(y for _, y in utm) + margin) / cell) * cell
    # Clipping is reported, not hidden: the regional box wants the buoy, and
    # the buoy sits south of the source's edge.
    clipped = (max(left, math.ceil(bounds.left / cell) * cell),
               max(bottom, math.ceil(bounds.bottom / cell) * cell),
               min(right, math.floor(bounds.right / cell) * cell),
               min(top, math.floor(bounds.top / cell) * cell))
    return clipped


def read_grid(grid: str):
    """Decimated read of one box. Returns (int16 decimetres, transform, box, stats)."""

    import numpy as np
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.env import Env
    from rasterio.transform import from_origin
    from rasterio.windows import from_bounds

    cell, _ = GRIDS[grid]
    with Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
             CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.vrt",
             GDAL_HTTP_MAX_RETRY="4", GDAL_HTTP_RETRY_DELAY="2"):
        with rasterio.open(f"/vsicurl/{SOURCE_VRT}") as src:
            left, bottom, right, top = box(grid, src.bounds)
            width = int(round((right - left) / cell))
            height = int(round((top - bottom) / cell))
            window = from_bounds(left, bottom, right, top, transform=src.transform)
            # AVERAGE, not nearest: a 32 m cell should carry the mean depth of
            # the 1 m cells inside it, not whichever one happened to be picked.
            data = src.read(1, window=window, out_shape=(height, width),
                            resampling=Resampling.average, masked=True,
                            boundless=True, fill_value=SOURCE_NODATA)
    arr = np.ma.filled(data.astype("float64"), np.nan)
    arr[arr <= SOURCE_NODATA + 1] = np.nan
    dm = np.where(np.isnan(arr), NODATA_DM, np.clip(np.round(arr * 10.0), -32767, 32767)).astype("int16")
    finite = arr[np.isfinite(arr)]
    stats = {
        "cells": int(arr.size),
        "nodata_cells": int(np.isnan(arr).sum()),
        "min_elevation_m": float(finite.min()) if finite.size else None,
        "max_elevation_m": float(finite.max()) if finite.size else None,
    }
    return dm, from_origin(left, top, cell, cell), (left, bottom, right, top), stats


def fetch_datum() -> dict:
    """MSL above NAVD88 at 9410170, from CO-OPS. Raises on any failure."""

    with urllib.request.urlopen(DATUMS_URL, timeout=30) as resp:
        body = json.load(resp)
    by_name = {d["name"]: d["value"] for d in body.get("datums", [])}
    if "MSL" not in by_name or "NAVD88" not in by_name:
        raise LookupError(f"CO-OPS datums for {TIDE_STATION} lack MSL or NAVD88: {sorted(by_name)}")
    return {
        "station": TIDE_STATION,
        "msl_above_navd88_m": round(by_name["MSL"] - by_name["NAVD88"], 4),
        "epoch": body.get("epoch"),
        "source": DATUMS_URL,
    }


def write(grid: str, dm, transform, bounds, stats, datum: dict | None, out_dir: Path) -> Path:
    import numpy as np

    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_dir / f"{grid}.npz", elevation_dm=dm)
    meta = {
        "grid": grid,
        "source": SOURCE_NAME,
        "source_url": SOURCE_VRT,
        "crs": SOURCE_CRS,
        "vertical_datum": "NAVD88",
        "units": "decimetres, elevation (negative is below NAVD88)",
        "nodata": NODATA_DM,
        "cell_m": GRIDS[grid][0],
        "shape": [int(dm.shape[0]), int(dm.shape[1])],
        "transform": [transform.a, transform.b, transform.c, transform.d, transform.e, transform.f],
        "bounds_utm": list(bounds),
        "resampling": "average of the 1 m cells, via the source's overviews",
        "not_covered": NOT_COVERED,
        "datum": datum or {"station": TIDE_STATION, "msl_above_navd88_m": None,
                           "note": "not fetched: CO-OPS is denied from a session; run the workflow"},
        "stats": stats,
        "retrieved_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    path = out_dir / f"{grid}.json"
    path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-datum", action="store_true",
                        help="store the grids without the MSL/NAVD88 offset (a session cannot reach CO-OPS)")
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)

    datum = None
    if not args.skip_datum:
        try:
            datum = fetch_datum()
        except (urllib.error.URLError, OSError, LookupError, ValueError) as exc:
            print(f"datum: {exc}", file=sys.stderr)
            return 2
        print(f"datum: MSL is {datum['msl_above_navd88_m']:+.3f} m relative to NAVD88 at {TIDE_STATION}")

    for grid in GRIDS:
        dm, transform, bounds, stats = read_grid(grid)
        path = write(grid, dm, transform, bounds, stats, datum, args.out)
        print(f"{grid}: {dm.shape[1]} x {dm.shape[0]} cells at {GRIDS[grid][0]:g} m, "
              f"{stats['nodata_cells']} without data, elevation "
              f"{stats['min_elevation_m']:.1f} to {stats['max_elevation_m']:.1f} m -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
