"""Point Loma's skyline as each break sees it, for the Sun card's sunset.

    python -m forecast.skyline            # build data/nearshore/<break>_skyline.csv

PRECOMPUTE ONLY. Needs numpy (requirements-precompute.txt). The forecast never
imports this module; `forecast.sunset` reads the tables it writes.

Owner's request, 2026-10-16 (BRIEFING §42): for most of the year the sun sets
behind the Point Loma peninsula, several minutes before the sea-horizon time
every published table gives, and through the winter it sets in the sea to the
LEFT of the point. Both are a matter of where the land stands against the sky
from each break, and the seabed grids already carry it: USGS CoNED is a
TOPObathymetric survey, so Point Loma's ridge is in `data/bathymetry/` beside
the seabed the rays are traced over.

For each break and each azimuth (every `AZ_STEP_DEG` across `AZ_RANGE`) a
straight line is walked from the break out over the grids, and the land on it
(above MSL) is turned into the angle it stands above the eye's horizontal:

    atan((h - EYE_M) / d) - d (1 - K) / 2R

the last term the Earth's curvature less the terrestrial refraction that
lifts a distant hill (k = 0.13, the surveyors' standard). The largest angle
along the line is the skyline at that azimuth. An azimuth with no land on it
is open sea, written as an empty cell -- never a number, because the sea's
own horizon is a different thing (`forecast.sunset` sets it at zero, as the
published times do).

WHAT IT IS NOT. CoNED is bare earth: the trees along the ridge, the lighthouse
and the buildings on Point Loma are not in it, so the skyline here is the
LOWEST the real one can be and the sunset computed from it the LATEST.
Land within `NEAR_M` of the break is skipped: it is the observer's own beach.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

import numpy as np

from .geometry import load
from .raytrace import BREAKS, Bathymetry, OUT_DIR
from .utm import to_utm

#: The eye above mean sea level: standing on the sand near the water. Two
#: metres either way moves the skyline 0.02° at Point Loma's 5-8 km, about
#: six seconds of sunset.
EYE_M = 3.0
#: Terrestrial refraction coefficient (light from a distant hill bends down
#: toward the observer, lifting it); 0.13 is the surveyors' standard.
K = 0.13
EARTH_R_M = 6371000.0
#: West-south-west to west-north-west, every sunset azimuth of the year at
#: 32.7° N (about 241-299°) with margin either side.
AZ_RANGE = (225.0, 315.0)
AZ_STEP_DEG = 0.02
STEP_M = 8.0
#: The observer's own beach is not the skyline.
NEAR_M = 200.0
#: The grids end about 20 km out on the azimuths that matter; Point Loma's
#: ridge is 4.5-8 km from the breaks.
FAR_M = 20000.0


def skyline(bathy: Bathymetry, position: tuple[float, float]) -> list[tuple[float, float | None, float | None]]:
    """(azimuth, elevation angle in degrees or None for open sea, distance in
    metres of the land that sets it) every `AZ_STEP_DEG`."""

    x0, y0 = to_utm(*position)
    d = np.arange(NEAR_M, FAR_M, STEP_M)
    drop = np.degrees(d * (1 - K) / (2 * EARTH_R_M))
    n = int(round((AZ_RANGE[1] - AZ_RANGE[0]) / AZ_STEP_DEG)) + 1
    out = []
    for i in range(n):
        az = AZ_RANGE[0] + i * AZ_STEP_DEG
        x = x0 + d * math.sin(math.radians(az))
        y = y0 + d * math.cos(math.radians(az))
        depth, *_ = bathy.sample(x, y)
        h = -depth
        land = np.isfinite(h) & (h > 0)
        if not land.any():
            out.append((round(az, 2), None, None))
            continue
        ang = np.where(land, np.degrees(np.arctan2(h - EYE_M, d)) - drop, -np.inf)
        k = int(np.argmax(ang))
        out.append((round(az, 2), round(float(ang[k]), 4), round(float(d[k]))))
    return out


def write(rows, break_id: str, out_dir: Path = OUT_DIR) -> Path:
    path = out_dir / f"{break_id}_skyline.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["azimuth_deg", "elevation_deg", "distance_m"])
        for az, el, dist in rows:
            w.writerow([f"{az:.2f}", "" if el is None else f"{el:.4f}", "" if dist is None else dist])
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--break", dest="only", choices=BREAKS)
    args = parser.parse_args(argv)
    bathy = Bathymetry.load()
    by_id = {s.id: s for s in load()[0]}
    for sid in BREAKS:
        if args.only and sid != args.only:
            continue
        rows = skyline(bathy, by_id[sid].position)
        land = [r for r in rows if r[1] is not None]
        print(f"{sid}: first land at {land[0][0]:.2f}°, highest {max(r[1] for r in land):.2f}° "
              f"-> {write(rows, sid)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
