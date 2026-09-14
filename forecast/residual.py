"""Is anything LEFT after the static correction? Measured answer: no.

Run: ``python -m forecast.residual``

SPEC section 12.3 establishes that a two-parameter fit removes 25-50% of the
forecast's error at these buoys. This module asks the follow-up that decides
whether there is a project here or only a calibration: **is the remainder
structured, or is it noise?**

The tempting evidence says structured. The calibrated residual has a one-day
autocorrelation of +0.24 to +0.43 at every station and lead. Error today
predicts error tomorrow, which is what a drifting bias looks like, and a
correction that tracks the drift should beat one fitted once.

It does, slightly, and the control shows why that is not worth anything:

- A **trailing window** of recent residuals beats the static fit by 2-9%.
- An **expanding window** — every residual knowable at cycle time, not just the
  recent ones — captures essentially all of that. Static and expanding differ by
  0.002-0.005 m. So the static fit was not stale; more data simply estimates the
  same constant slightly better.
- What is left for genuine drift is 0.5-6.4% at two stations and **negative at
  eight of eleven leads at the third**. It does not replicate.
- In units anyone uses, the entire win is **0.14 to 0.69 inches** of significant
  wave height.

The autocorrelation is real but it is within-episode persistence — the same
swell being mis-modelled two days running — not a bias that moves. It is
largest at +0h, where it is a nowcast of an error already observable, and it
decays to nothing by the lead times a forecast is actually read at.

**Causality is enforced and is the whole game here.** To correct a forecast for
valid time T at lead L, the cycle ran at T-L, so only residuals for valid times
at or before T-L are knowable. At ten days the freshest usable observation is
ten days stale. Relaxing this produces a large, entirely fictional improvement.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR

from .stats import rmse
from .swell import travel_hours
from .verify import (
    DEFAULT_TEST_YEARS,
    DEFAULT_TRAIN_YEARS,
    METRES_TO_FEET,
    Pair,
    calibrate_and_test,
    fit_correction,
    load_forecasts,
    pair_up,
)

#: Typical Southern Ocean fetch-to-SoCal great-circle distance. Not a precise
#: number for any one storm; it is the scale that decides whether a swell has
#: been generated yet at a given lead time, and 9,000 km is right to within the
#: width of the source region.
SOUTHERN_OCEAN_KM = 9000.0

#: Period used for the transit-time gate. Long enough to be a real south swell,
#: short enough not to flatter the calculation: a 20 s forerunner crosses in
#: 6.7 days, a 14 s train in 9.5, and 17 s sits between them.
SOUTH_SWELL_PERIOD_S = 17.0

#: Trailing window length, in samples rather than days. The south-swell sample
#: is seasonal and sparse, so thirty samples is roughly two months of south
#: swells, not thirty days — which is the timescale a regime drift would live
#: on if one existed.
DEFAULT_WINDOW = 30


@dataclass(frozen=True)
class LeadResult:
    lead_h: int
    n_train: int
    n_test: int
    autocorr_1: float
    static_rmse_m: float
    expanding_rmse_m: float
    windowed_rmse_m: float

    @property
    def drift_gain(self) -> float:
        """Windowed against expanding: the only comparison that isolates drift."""
        if not self.expanding_rmse_m:
            return float("nan")
        return 1.0 - self.windowed_rmse_m / self.expanding_rmse_m

    @property
    def win_inches(self) -> float:
        return (self.static_rmse_m - self.windowed_rmse_m) * METRES_TO_FEET * 12.0


def autocorrelation(values: list[float], lag: int) -> float:
    if len(values) <= lag + 1:
        return float("nan")
    earlier, later = values[:-lag], values[lag:]
    mean_earlier = statistics.fmean(earlier)
    mean_later = statistics.fmean(later)
    covariance = sum(
        (a - mean_earlier) * (b - mean_later) for a, b in zip(earlier, later)
    )
    spread = (
        sum((a - mean_earlier) ** 2 for a in earlier)
        * sum((b - mean_later) ** 2 for b in later)
    ) ** 0.5
    return covariance / spread if spread else float("nan")


def assess_lead(
    pairs: list[Pair],
    lead_h: int,
    train_years: tuple[int, ...],
    test_years: tuple[int, ...],
    window: int = DEFAULT_WINDOW,
    minimum: int = 30,
) -> LeadResult | None:
    """Static, expanding and windowed correction at one lead time."""

    ordered = sorted(pairs, key=lambda p: p.valid)
    train = [p for p in ordered if p.valid.year in train_years]
    test = [p for p in ordered if p.valid.year in test_years]
    if len(train) < minimum or len(test) < minimum:
        return None

    intercept, slope = fit_correction(train)

    def residual(pair: Pair) -> float:
        return pair.observed - (intercept + slope * pair.forecast)

    # Every residual, in time order, including the test year's own earlier
    # residuals — which a forecaster genuinely would have had.
    history = [(p.valid, residual(p)) for p in ordered]

    def scored(size: int | None) -> float:
        errors = []
        for pair in test:
            cycle = pair.valid - timedelta(hours=lead_h)
            knowable = [value for stamp, value in history if stamp <= cycle]
            if size is not None:
                knowable = knowable[-size:]
            offset = statistics.fmean(knowable) if knowable else 0.0
            errors.append(residual(pair) - offset)
        return rmse(errors)

    return LeadResult(
        lead_h=lead_h,
        n_train=len(train),
        n_test=len(test),
        autocorr_1=autocorrelation([residual(p) for p in train], 1),
        static_rmse_m=rmse([residual(p) for p in test]),
        expanding_rmse_m=scored(None),
        windowed_rmse_m=scored(window),
    )


def ceiling(
    data_dir: Path,
    station_id: str,
    quantity: str,
    train_years: tuple[int, ...],
    test_years: tuple[int, ...],
    distance_km: float = SOUTHERN_OCEAN_KM,
    period_s: float = SOUTH_SWELL_PERIOD_S,
) -> list[str]:
    """What could an observation of the swell IN TRANSIT possibly be worth?

    Two subtractions decide Tier 2, and both are unkind to it.

    The first is the floor. Calibrated error at +0h is representativeness and
    measurement — the model's grid point is not the buoy's mooring. No
    observation anywhere upstream removes that, so only the part of the error
    ABOVE the +0h floor is in play, and it comes off in quadrature.

    The second is the transit gate. A satellite can only see a swell that
    already exists. For arrival at lead L after D hours in transit, the swell
    was generated at forecast hour L - D; when that is positive the generating
    storm has not happened yet at cycle time and no observation of the ocean
    can see the swell at all. So in-transit observation acts only where
    L < D — and at this distance D is about eight days, which excludes exactly
    the long leads where the error is largest.
    """

    points = load_forecasts(data_dir / "wave_forecasts" / f"{station_id}.csv")
    if not points:
        return [f"{station_id}: no archived forecasts; run collector.gfswave_backfill"]
    pairs = pair_up(points, data_dir, station_id, quantity)

    base = calibrate_and_test(
        [p for p in pairs if p.lead_h == 0], train_years, test_years
    )
    if base is None:
        return [f"{station_id}: too few pairs at +0h to establish the floor"]
    floor = base["rmse_calibrated_m"]
    transit_h = travel_hours(distance_km, period_s)

    lines = [
        f"## {station_id} — {quantity}, ceiling on an in-transit observation",
        "",
        f"Floor at +0h: {floor:.3f} m ({floor * METRES_TO_FEET * 12:.1f} in). "
        "Representativeness, not forecast error;",
        "no upstream observation removes it, so it comes off in quadrature.",
        f"Transit at {period_s:.0f} s over {distance_km:,.0f} km: "
        f"{transit_h / 24:.1f} days.",
        "",
        "lead | cal RMSE m | above floor | above floor in | in-transit observation",
        "-----+------------+-------------+----------------+-----------------------",
    ]
    for lead in sorted({p.lead_h for p in pairs}):
        result = calibrate_and_test(
            [p for p in pairs if p.lead_h == lead], train_years, test_years
        )
        if result is None:
            continue
        above = max(result["rmse_calibrated_m"] ** 2 - floor ** 2, 0.0) ** 0.5
        reach = "can act" if lead < transit_h else "BLIND — not generated yet"
        lines.append(
            f"{lead:4d} | {result['rmse_calibrated_m']:10.3f} | {above:11.3f} | "
            f"{above * METRES_TO_FEET * 12:14.1f} | {reach}"
        )
    return lines


def report(
    data_dir: Path,
    station_id: str,
    quantity: str,
    train_years: tuple[int, ...],
    test_years: tuple[int, ...],
    window: int,
) -> list[str]:
    points = load_forecasts(data_dir / "wave_forecasts" / f"{station_id}.csv")
    if not points:
        return [f"{station_id}: no archived forecasts; run collector.gfswave_backfill"]
    pairs = pair_up(points, data_dir, station_id, quantity)

    lines = [
        f"## {station_id} — {quantity}, residual after the static correction",
        "",
        "'drift gain' is windowed against EXPANDING, not against static: only that",
        "comparison separates a bias that moves from a constant estimated better.",
        "",
        "lead | lag-1 ac | static m | expand m | last30 m | drift gain | win inches",
        "-----+----------+----------+----------+----------+------------+-----------",
    ]
    for lead in sorted({p.lead_h for p in pairs}):
        result = assess_lead(
            [p for p in pairs if p.lead_h == lead],
            lead,
            train_years,
            test_years,
            window,
        )
        if result is None:
            lines.append(f"{lead:4d} |  (too few pairs to split)")
            continue
        lines.append(
            f"{lead:4d} | {result.autocorr_1:+8.2f} | {result.static_rmse_m:8.3f} | "
            f"{result.expanding_rmse_m:8.3f} | {result.windowed_rmse_m:8.3f} | "
            f"{result.drift_gain:+10.1%} | {result.win_inches:10.2f}"
        )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--stations", default="46232,46224,46222")
    parser.add_argument("--quantity", default="south", choices=("total", "south"))
    parser.add_argument("--window", type=int, default=DEFAULT_WINDOW)
    parser.add_argument(
        "--ceiling",
        action="store_true",
        help="Instead: what could an in-transit observation be worth? (Tier 2)",
    )
    parser.add_argument(
        "--train-years", default=",".join(str(y) for y in DEFAULT_TRAIN_YEARS)
    )
    parser.add_argument(
        "--test-years", default=",".join(str(y) for y in DEFAULT_TEST_YEARS)
    )
    args = parser.parse_args(argv)

    train = tuple(int(y) for y in args.train_years.split(",") if y.strip())
    test = tuple(int(y) for y in args.test_years.split(",") if y.strip())

    lines: list[str] = []
    for station_id in [s.strip() for s in args.stations.split(",") if s.strip()]:
        if args.ceiling:
            lines += ceiling(args.data_dir, station_id, args.quantity, train, test)
        else:
            lines += report(
                args.data_dir, station_id, args.quantity, train, test, args.window
            )
        lines.append("")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
