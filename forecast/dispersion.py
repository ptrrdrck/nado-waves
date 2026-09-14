"""Event-driven rounds: swell arrivals, and where the storm was.

    python -m forecast.dispersion

The daily format was the wrong shape for this data. Every skill measurement in
this project averaged over all days, including the ~80% when nothing happens,
which drags the average to nothing. If rounds fire on *events* instead, the
quiet days stop diluting the game and every round has something at stake.

Two tiers, both automatically detected and automatically resolved.

**Tier 1 — "swell building at your break, call the peak."** About three a month
per station. On these days the spread to play for is 0.54m against 0.36m on an
average day, and the skill ceiling is 17.8% against 11.9%. More at stake *and*
more to be right about.

**Tier 2 — "a groundswell is arriving. Where was it born?"** About six a year.
This is the interesting one, and it is not in any surf app.

A storm at distance R radiates swell of every period at once. Long periods
travel faster — deep-water group velocity is `gT/4π` — so they arrive first and
the period at the buoy declines steadily as the shorter stuff catches up. Write
that out and `1/T` is *linear* in arrival time, with slope `g/(4πR)`. So:

    R = g / (4π · slope)

A single buoy, watching its own period decline, can say how far away the storm
was and when it blew. Verified two ways here: five stations independently agreed
on one arrival to within 19%, and the implied distances (4100–5700 km, 3.7–4.7
days) land squarely in the North Pacific storm track in winter.

It is a fair game because the answer is not computable when the round opens. A
fit on the first 12 hours misses the settled answer by 11% at the median and up
to 43%, because early on there are few periods to draw a line through. The
player calls it from the forerunners; the ocean finishes the sentence.
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
from .stats import LEAGUE_TZ
from .stats import load_column
from .swell import daily_peak

GRAVITY = 9.81

# --- Tier 1: a swell is building -------------------------------------------

#: A round opens when the daily peak jumps this much and clears this height.
MIN_RISE_M = 0.3
MIN_PEAK_M = 1.2
#: Quiet days needed before a new event counts as a new event.
EVENT_SEPARATION_DAYS = 2


# --- Tier 2: a clean dispersive arrival -------------------------------------

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


def swell_events(data_dir: Path, station: str) -> list:
    """Tier 1: days a round would open because a swell is building."""

    peaks = daily_peak(data_dir, station)
    days = sorted(peaks)
    events, last = [], None
    for previous, day in zip(days, days[1:]):
        if (day - previous).days != 1:
            continue
        if peaks[day] - peaks[previous] >= MIN_RISE_M and peaks[day] >= MIN_PEAK_M:
            if last is None or (day - last).days >= EVENT_SEPARATION_DAYS:
                events.append(day)
            last = day
    return events


def dispersive_arrivals(data_dir: Path, station: str, window: int = SETTLE_HOURS) -> list:
    """Tier 2: arrivals clean enough to ask where the storm was."""

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
    parser = argparse.ArgumentParser(description="Event-driven round candidates.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--stations", help="Comma-separated ids.")
    args = parser.parse_args(argv)

    registry = load_stations()
    stations = (
        select(registry, args.stations.split(","))
        if args.stations
        else [s for s in registry if s.launch_candidate]
    )

    print("Tier 1 — swell building (a round opens)\n")
    print(f"{'station':<9} {'events':>7} {'per year':>9} {'per month':>10}")
    print("-" * 40)
    for station in stations:
        events = swell_events(args.data_dir, station.id)
        if not events:
            continue
        span = (events[-1] - events[0]).days / 365.25 or 1
        print(f"{station.id:<9} {len(events):>7} {len(events)/span:>9.1f} {len(events)/span/12:>10.1f}")

    print("\nTier 2 — clean dispersive arrival (where was the storm?)\n")
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
