"""A swell arrival's dispersion line, and the distance it implies.

    python -m forecast.dispersion

A storm at distance R radiates swell of every period at once. Long periods
travel faster -- deep-water group velocity is `gT/4π` -- so they arrive first and
the period at the buoy declines steadily as the shorter stuff catches up. Write
that out and `1/T` is *linear* in arrival time, with slope `g/(4πR)`. So:

    R = g / (4π · slope)

and the line reaches `1/T = 0` at the moment the storm blew.

This module is the fit, and the scan of a buoy's DOMINANT period for arrivals
clean enough to fit (`dispersive_arrivals`). `forecast.forensics` puts a place
on the historical ones; `forecast.origin` reads each train separately off the
live spectrum, because the real-time dominant period is rounded to whole
seconds and finds almost nothing (BRIEFING §37).

Carried over from the predecessor's game, which used the distance as a round to
call: its "swell building" tier is gone with the game. What survived is
measured: a fit on the first 12 hours misses the 36-hour answer by 23% at the
median, and on 24 hours by 9% (BRIEFING §37, 2023-2025, six buoys). Two buoys
fitting the same storm independently agree to about 18-25%, and that, not the
fit's R², is the precision of a distance read this way.
"""

from __future__ import annotations

import argparse
import math
import statistics
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR
from collector.stations import load_stations, select
from .siting import constraining
from .stats import load_column

GRAVITY = 9.81

# --- A clean dispersive arrival ----------------------------------------------

#: The forerunners have to be genuine groundswell.
MIN_LEAD_PERIOD_S = 13.0
#: And the period has to actually fall, or there is no line to fit.
MIN_PERIOD_DROP_S = 2.0
#: How straight `1/T` against time has to be before we believe the distance.
MIN_FIT_R2 = 0.75
#: Window over which the arrival is judged to have played out.
SETTLE_HOURS = 36
#: Distances outside this are not a storm, they are a bad fit.
PLAUSIBLE_KM = (500.0, 20000.0)


@dataclass(frozen=True)
class StormOrigin:
    distance_km: float
    r_squared: float
    generated_at: datetime
    lead_period_s: float
    trailing_period_s: float

    @property
    def age_days(self) -> float:
        return 0.0  # filled by the caller that knows the arrival time


def _fit_line(xs: list[float], ys: list[float]) -> tuple[float, float, float] | None:
    """(intercept, slope, r_squared) by least squares."""

    if len(xs) < 3:
        return None
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    intercept = my - slope * mx
    residual = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    total = sum((y - my) ** 2 for y in ys)
    return intercept, slope, (1 - residual / total if total else 0.0)


def distance_from_slope(slope_per_hour: float) -> float:
    """R = g / (4π · slope), with slope in (1/s) per hour, returning km."""

    return GRAVITY / (4 * math.pi * slope_per_hour) / 1000.0 * 3600.0


def origin_from_series(
    periods: dict,
    stamps: list[datetime],
    min_r2: float = MIN_FIT_R2,
) -> StormOrigin | None:
    """The fit itself, on an already-selected run of timestamps.

    Separated from the file loading because `dispersive_arrivals` scans
    thousands of candidate windows: re-reading a 26,000-row CSV inside each one
    turned a two-second job into minutes.
    """

    if len(stamps) < 6:
        return None

    observed = [periods[t] for t in stamps]
    if observed[0] - observed[-1] < MIN_PERIOD_DROP_S:
        return None

    elapsed = [(t - stamps[0]).total_seconds() / 3600.0 for t in stamps]
    fitted = _fit_line(elapsed, [1.0 / p for p in observed])
    if fitted is None:
        return None
    intercept, slope, r2 = fitted
    if slope <= 1e-7 or r2 < min_r2:
        return None

    distance = distance_from_slope(slope)
    low, high = PLAUSIBLE_KM
    if not low < distance < high:
        return None

    # The line crosses 1/T = 0 at the moment the (infinitely fast) longest
    # period would have left: that is the generation time.
    return StormOrigin(
        distance_km=distance,
        r_squared=r2,
        generated_at=stamps[0] - timedelta(hours=intercept / slope),
        lead_period_s=observed[0],
        trailing_period_s=observed[-1],
    )


def storm_origin(
    data_dir: Path,
    station: str,
    arrival: datetime,
    hours: int = SETTLE_HOURS,
    min_r2: float = MIN_FIT_R2,
) -> StormOrigin | None:
    """Where and when was the swell now arriving at `station` generated?"""

    heights = load_column(data_dir / "historical" / f"{station}.csv", "wvht")
    periods = load_column(data_dir / "historical" / f"{station}.csv", "dpd")
    stamps = sorted(
        t for t in set(heights) & set(periods)
        if arrival <= t <= arrival + timedelta(hours=hours)
    )
    return origin_from_series(periods, stamps, min_r2)


def dispersive_arrivals(data_dir: Path, station: str, window: int = SETTLE_HOURS) -> list:
    """Arrivals clean enough to ask where the storm was."""

    heights = load_column(data_dir / "historical" / f"{station}.csv", "wvht")
    periods = load_column(data_dir / "historical" / f"{station}.csv", "dpd")
    stamps = sorted(set(heights) & set(periods))

    found, index = [], 0
    while index < len(stamps) - window:
        start = stamps[index]
        group = stamps[index : index + window]
        if (group[-1] - group[0]).total_seconds() / 3600.0 > window * 1.6:
            index += 6
            continue
        observed = [periods[t] for t in group]
        if observed[0] >= MIN_LEAD_PERIOD_S and max(heights[t] for t in group) >= 0.8:
            origin = origin_from_series(periods, group)
            if origin is not None:
                found.append((start, origin))
                index += window
                continue
        index += 6
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clean dispersive arrivals, by buoy.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--stations", help="Comma-separated ids.")
    args = parser.parse_args(argv)

    registry = load_stations()
    stations = (
        select(registry, args.stations.split(","))
        if args.stations
        else constraining(registry)
    )

    print(f"{'station':<9} {'arrival':<18} {'R2':>5} {'period':>12} {'distance':>10} {'blew':>9}")
    print("-" * 70)
    for station in stations:
        for arrival, origin in dispersive_arrivals(args.data_dir, station.id)[:4]:
            age = (arrival - origin.generated_at).total_seconds() / 86400
            print(
                f"{station.id:<9} {arrival:%Y-%m-%d %H:%M}  {origin.r_squared:>5.2f} "
                f"{origin.lead_period_s:>5.1f}->{origin.trailing_period_s:<5.1f} "
                f"{origin.distance_km:>8.0f}km {age:>7.1f}d"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
