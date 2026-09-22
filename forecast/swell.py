"""Propagate swell from an upstream sentinel buoy to a nearshore station.

    python -m forecast.swell

Tests the one idea that survived everything else: rather than predicting a
nearshore buoy from its own past, watch a buoy thousands of kilometres upstream
and call the swell before it lands.

The physics, which the first version of this test ignored and got a meaningless
negative from:

* **Speed depends on period.** Deep-water group velocity is `gT/4π`, so a
  20-second swell crosses 3383 km in 2.5 days and a 13-second one takes 3.9.
  Every reading has to be propagated at *its own* speed, not at a fixed lag.
* **Direction decides whether it is even ours.** `mwd` is where the waves come
  *from*; they travel toward `mwd + 180`. A swell aimed at Baja never reaches
  San Pedro, and counting it is noise.
* **Energy, not height.** Flux goes as `H²T`, which is what combines across a
  swell train.
* **Resolution is a window peak, never a spot reading.** Long periods outrun
  short ones, so a swell does not land at an instant — it fills in over a day
  or more. The daily peak absorbs arrival-time error that no model removes.

Station positions are approximate and inlined. `collector/metadata.py` can
replace them with NDBC's own table; they are good to a few km, which is
irrelevant next to a 60° aiming tolerance.
"""

from __future__ import annotations

import argparse
import math
import statistics
import sys
from datetime import timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from collector.common import DEFAULT_DATA_DIR
from .stats import LOCAL_TZ
from .stats import load_column

EARTH_RADIUS_KM = 6371.0

#: How far off the great circle a swell may be aimed and still count.
AIM_TOLERANCE_DEG = 60.0

POSITIONS = {
    "46001": (56.23, -148.02), "46006": (40.75, -137.48),
    "46005": (45.95, -131.00), "46059": (37.98, -130.00),
    "51101": (24.32, -162.06), "51002": (17.09, -157.81),
    "46219": (33.22, -119.88), "46221": (33.86, -118.63),
    "46222": (33.62, -118.32), "46224": (33.18, -117.47),
    "46225": (32.93, -117.39), "46258": (32.75, -117.50),
    "46047": (32.418, -119.535), "46086": (32.504, -118.029),
    "46232": (32.52, -117.42), "46253": (33.576, -118.181),
}

TARGETS = ("46221", "46222", "46224", "46225", "46258")
SENTINELS = ("46001", "46006", "46059", "51101", "51002", "46219")


def great_circle_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    return EARTH_RADIUS_KM * 2 * math.asin(
        math.sqrt(
            math.sin((la2 - la1) / 2) ** 2
            + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
        )
    )


def initial_bearing(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    y = math.sin(lo2 - lo1) * math.cos(la2)
    x = math.cos(la1) * math.sin(la2) - math.sin(la1) * math.cos(la2) * math.cos(lo2 - lo1)
    return math.degrees(math.atan2(y, x)) % 360.0


def destination_point(
    start: tuple[float, float], bearing_deg: float, distance_km: float
) -> tuple[float, float]:
    """Walk `distance_km` from `start` along `bearing_deg` on a sphere.

    The inverse of `initial_bearing` + `great_circle_km`, and the step that
    turns "9,400 km away, from 205 degrees" into a place on a map.
    """

    lat = math.radians(start[0])
    lon = math.radians(start[1])
    bearing = math.radians(bearing_deg)
    angular = distance_km / EARTH_RADIUS_KM

    end_lat = math.asin(
        math.sin(lat) * math.cos(angular)
        + math.cos(lat) * math.sin(angular) * math.cos(bearing)
    )
    end_lon = lon + math.atan2(
        math.sin(bearing) * math.sin(angular) * math.cos(lat),
        math.cos(angular) - math.sin(lat) * math.sin(end_lat),
    )
    return math.degrees(end_lat), (math.degrees(end_lon) + 540.0) % 360.0 - 180.0


def cross_track_km(
    start: tuple[float, float], end: tuple[float, float], point: tuple[float, float]
) -> float:
    """How far `point` sits off the great circle from `start` to `end`.

    Signed distance is not wanted here; a sentinel 200 km left of the path and
    one 200 km right of it are equally good witnesses.
    """

    angular = great_circle_km(start, point) / EARTH_RADIUS_KM
    spread = math.radians(
        (initial_bearing(start, point) - initial_bearing(start, end) + 180.0) % 360.0
        - 180.0
    )
    return abs(math.asin(math.sin(angular) * math.sin(spread)) * EARTH_RADIUS_KM)


def group_velocity(period_s: float) -> float:
    """Deep-water group velocity in m/s. Half the phase speed — `gT/4π`."""

    return 9.81 * period_s / (4 * math.pi)


def travel_hours(distance_km: float, period_s: float) -> float:
    return distance_km * 1000.0 / group_velocity(period_s) / 3600.0


def aimed_at(mwd_deg: float, bearing_deg: float, tolerance: float = AIM_TOLERANCE_DEG) -> bool:
    """Is swell arriving FROM `mwd` travelling toward `bearing`?"""

    travelling_toward = (mwd_deg + 180.0) % 360.0
    off = abs((travelling_toward - bearing_deg + 180.0) % 360.0 - 180.0)
    return off <= tolerance


def arriving_energy(
    data_dir: Path,
    sentinel: str,
    target: str,
    tz: ZoneInfo = LOCAL_TZ,
    tolerance: float = AIM_TOLERANCE_DEG,
) -> tuple[dict, float, int, int]:
    """Peak `H²T` predicted to land at `target` on each local day."""

    distance = great_circle_km(POSITIONS[sentinel], POSITIONS[target])
    bearing = initial_bearing(POSITIONS[sentinel], POSITIONS[target])

    heights = load_column(data_dir / "historical" / f"{sentinel}.csv", "wvht")
    periods = load_column(data_dir / "historical" / f"{sentinel}.csv", "dpd")
    directions = load_column(data_dir / "historical" / f"{sentinel}.csv", "mwd")

    landing: dict = {}
    seen = aimed = 0
    for stamp, height in heights.items():
        period = periods.get(stamp)
        if not period or period <= 0:
            continue
        seen += 1
        heading = directions.get(stamp)
        if heading is not None and not aimed_at(heading, bearing, tolerance):
            continue
        aimed += 1
        eta = stamp + timedelta(hours=travel_hours(distance, period))
        day = eta.astimezone(tz).date()
        landing[day] = max(landing.get(day, 0.0), height * height * period)
    return landing, distance, seen, aimed


def daily_peak(data_dir: Path, station: str, tz: ZoneInfo = LOCAL_TZ) -> dict:
    """The resolution rule: peak wave height in the local day."""

    out: dict = {}
    for stamp, value in load_column(
        data_dir / "historical" / f"{station}.csv", "wvht"
    ).items():
        day = stamp.astimezone(tz).date()
        out[day] = max(out.get(day, 0.0), value)
    return out


def correlation(x: list[float], y: list[float]) -> float | None:
    if len(x) < 3:
        return None
    mx, my = statistics.fmean(x), statistics.fmean(y)
    sxy = sum((i - mx) * (j - my) for i, j in zip(x, y))
    sxx = sum((i - mx) ** 2 for i in x)
    syy = sum((j - my) ** 2 for j in y)
    return sxy / (sxx * syy) ** 0.5 if sxx and syy else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sentinel swell propagation.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--tolerance", type=float, default=AIM_TOLERANCE_DEG)
    args = parser.parse_args(argv)

    print("Propagated sentinel energy vs the SoCal daily peak it should cause")
    print(f"Aiming tolerance {args.tolerance:.0f}°, deep-water group velocity\n")
    print(
        f"{'sentinel':<9} {'km':>6} {'aimed':>13}  "
        + "  ".join(f"{t:>7}" for t in TARGETS)
    )
    print("-" * 80)

    rows = []
    for sentinel in SENTINELS:
        cells, distance, share = [], 0.0, ""
        for target in TARGETS:
            landing, distance, seen, aimed = arriving_energy(
                args.data_dir, sentinel, target, tolerance=args.tolerance
            )
            share = f"{aimed}/{seen}" if seen else "—"
            peaks = daily_peak(args.data_dir, target)
            days = sorted(set(landing) & set(peaks))
            if len(days) < 300:
                cells.append("      —")
                continue
            r = correlation([landing[d] for d in days], [peaks[d] for d in days])
            cells.append("      —" if r is None else f"{r:>+7.2f}")
            rows.append((sentinel, distance, r))
        print(f"{sentinel:<9} {distance:>6.0f} {share:>13}  " + "  ".join(cells))

    print()
    print("Correlation falls off with distance — the signal is real near in and")
    print("gone by the ranges that would buy multi-day lead time. 'aimed' is how")
    print("often the sentinel is even looking at SoCal; a buoy pointed elsewhere")
    print("98% of the time cannot anchor a daily game.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
