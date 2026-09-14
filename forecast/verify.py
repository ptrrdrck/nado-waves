"""How wrong is the wave forecast, and can we say so honestly?

Run: ``python -m forecast.verify``

This is Tier 1 of the forecast-error work (SPEC section 12). It does not try to
make the forecast better. It tries to make the forecast's *error* legible, which
is a different and much cheaper problem, and the one a surfer actually has:
"three foot on Thursday" is useless without knowing whether Thursday's three
foot is worth planning around.

Four questions, in order of how much they matter:

1. **Bias.** Does the model sit systematically high or low at this buoy? A
   global 0.25-degree wave model cannot see the Channel Islands or the shelf,
   so its value at a nearshore point is a smooth-ocean value. If that offset is
   stable it is free to remove, and removing it is the single largest available
   win.
2. **Spread.** After the bias is gone, how much scatter is left, and how does it
   grow with lead time? This is the number that decides how far ahead a forecast
   is worth reading.
3. **Calibration.** Fit the correction on 2023-2024 and test it on 2025. An
   in-sample correction always looks good; the only number worth quoting is the
   out-of-sample one.
4. **Coverage.** If we publish "5-7 ft, 70% confidence", does 70% of the time
   actually land inside? A confidence interval that is wrong about its own
   confidence is worse than no interval, because it is believed.

And one question that needs no buoy at all: **run-to-run wobble** — how far a
forecast for a given day moves between its ten-day and its one-day version. That
is the thing people complain about, and it is measurable purely from archived
cycles, with no verification data involved.

Everything here is diagnostic. Nothing in this module may be wired into round
scoring: a GFS-Wave bulletin is the public forecast, which is exactly what
CLAUDE.md says a game quantity must not be derivable from.
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR
from .stats import angular_difference, least_squares, load_column, rmse

METRES_TO_FEET = 3.28084

#: How far a buoy observation may sit from the forecast's valid hour and still
#: count as the same moment. CDIP stations report at :26, NDBC moored buoys at
#: :40 or :50, so anything tighter than this silently drops whole stations.
MATCH_WINDOW = timedelta(minutes=40)

#: "South swell is running": long period, arriving from the southern window.
#: Both halves are needed — a 16-second train from 280 degrees is a NW swell,
#: and a 9-second train from 190 degrees is local wind slop.
SOUTH_WINDOW = (160.0, 230.0)
SOUTH_MIN_PERIOD = 14.0

#: The lead time a forecast is treated as having settled. Drift is measured
#: back to this, not to the observation: the question is how much the
#: forecast moved, which is separate from whether it ended up right.
SETTLED_LEAD = 24

DEFAULT_TRAIN_YEARS = (2023, 2024)
DEFAULT_TEST_YEARS = (2025,)


@dataclass(frozen=True)
class ForecastPoint:
    cycle: datetime
    valid: datetime
    lead_h: int
    hs_total_m: float
    partitions: tuple[tuple[float, float, int, bool], ...]

    def largest(self):
        return max(self.partitions, key=lambda p: p[0], default=None)

    def south_hs(self) -> float:
        """Combined height of the south-window swell trains.

        Partitions are independent wave systems, so their heights add in
        variance, not linearly: two 2 ft trains make a 2.8 ft sea, not 4 ft.
        Getting this wrong inflates every south-swell forecast.
        """
        low, high = SOUTH_WINDOW
        energy = sum(
            hs * hs
            for hs, tp, from_deg, _ in self.partitions
            if low <= from_deg <= high and tp >= SOUTH_MIN_PERIOD
        )
        return math.sqrt(energy)


def load_forecasts(path: Path) -> list[ForecastPoint]:
    """Rebuild forecast points from the flat per-partition archive."""

    grouped: dict[tuple[str, int], dict] = {}
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = (row["cycle_utc"], int(row["lead_h"]))
            entry = grouped.setdefault(
                key,
                {
                    "cycle": _iso(row["cycle_utc"]),
                    "valid": _iso(row["valid_utc"]),
                    "lead_h": int(row["lead_h"]),
                    "hs_total_m": float(row["hs_total_m"]),
                    "partitions": [],
                },
            )
            if (row["part_hs_m"] or "").strip():
                entry["partitions"].append(
                    (
                        float(row["part_hs_m"]),
                        float(row["part_tp_s"]),
                        int(row["part_from_deg"]),
                        row["wind_sea"] == "1",
                    )
                )
    points = [
        ForecastPoint(
            cycle=e["cycle"],
            valid=e["valid"],
            lead_h=e["lead_h"],
            hs_total_m=e["hs_total_m"],
            partitions=tuple(sorted(e["partitions"], key=lambda p: -p[0])),
        )
        for e in grouped.values()
    ]
    points.sort(key=lambda p: (p.valid, p.lead_h))
    return points


def _iso(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def nearest_observation(series: dict[datetime, float], moment: datetime):
    """The observation closest to `moment`, or None if the buoy was quiet.

    Deliberately not an interpolation. CLAUDE.md forbids inventing a resolution
    value, and the same discipline applies to a verification value: a gap in the
    buoy record must shrink the sample, never fill it with a guess.
    """
    best = None
    for stamp, value in series.items():
        gap = abs(stamp - moment)
        if gap <= MATCH_WINDOW and (best is None or gap < best[0]):
            best = (gap, value)
    return best[1] if best else None


def _indexed(series: dict[datetime, float]) -> dict[str, list[tuple[datetime, float]]]:
    """Bucket a series by hour so matching is not quadratic over three years."""
    buckets: dict[str, list[tuple[datetime, float]]] = {}
    for stamp, value in series.items():
        buckets.setdefault(stamp.strftime("%Y-%m-%dT%H"), []).append((stamp, value))
    return buckets


def _lookup(buckets, moment: datetime):
    best = None
    for offset in (-1, 0, 1):
        key = (moment + timedelta(hours=offset)).strftime("%Y-%m-%dT%H")
        for stamp, value in buckets.get(key, ()):
            gap = abs(stamp - moment)
            if gap <= MATCH_WINDOW and (best is None or gap < best[0]):
                best = (gap, value)
    return best[1] if best else None


@dataclass(frozen=True)
class Pair:
    valid: datetime
    lead_h: int
    forecast: float
    observed: float


def pair_up(
    points: list[ForecastPoint],
    data_dir: Path,
    station_id: str,
    quantity: str = "total",
) -> list[Pair]:
    """Match forecasts to what the buoy actually recorded.

    Both quantities compare the bulletin's **total** Hs against the buoy's
    **total** WVHT, because that is the only like-for-like pair available: the
    standard meteorological file reports one height for the whole sea, not one
    per wave train. An earlier version of this compared the forecast's
    south-window partitions against the buoy total and produced a confident
    -0.65 m "bias" that was almost entirely the windsea the buoy could see and
    the partition sum could not. Comparing a part to a whole is not a bias
    measurement.

    What "south" changes is therefore the **sample, not the sides**: it keeps
    only the hours the buoy itself says are south-swell dominated (long period,
    southern quadrant). That answers "how good is the forecast when a south
    swell is running", which is the question, without pretending we can isolate
    the south swell's height from a single-number observation.
    """
    hs = load_column(data_dir / "historical" / f"{station_id}.csv", "wvht")
    if not hs:
        return []
    hs_index = _indexed(hs)
    dpd_index = mwd_index = None
    if quantity == "south":
        dpd_index = _indexed(load_column(data_dir / "historical" / f"{station_id}.csv", "dpd"))
        mwd_index = _indexed(load_column(data_dir / "historical" / f"{station_id}.csv", "mwd"))

    pairs: list[Pair] = []
    for point in points:
        observed = _lookup(hs_index, point.valid)
        if observed is None:
            continue
        if quantity == "south":
            dpd = _lookup(dpd_index, point.valid)
            mwd = _lookup(mwd_index, point.valid)
            if dpd is None or mwd is None:
                continue
            if dpd < SOUTH_MIN_PERIOD or not (SOUTH_WINDOW[0] <= mwd <= SOUTH_WINDOW[1]):
                continue
        pairs.append(Pair(point.valid, point.lead_h, point.hs_total_m, observed))
    return pairs


def error_stats(pairs: list[Pair]) -> dict:
    if len(pairs) < 2:
        return {"n": len(pairs)}
    errors = [p.forecast - p.observed for p in pairs]
    observed = [p.observed for p in pairs]
    mean_observed = statistics.fmean(observed)
    spread = statistics.pstdev(errors)
    return {
        "n": len(pairs),
        "bias_m": statistics.fmean(errors),
        "rmse_m": rmse(errors),
        "sd_m": spread,
        # Scatter index: error spread as a fraction of the mean sea state. The
        # metric the WMO Lead Centre reports, so our numbers are comparable to
        # the published global ones rather than a private scale.
        "scatter_index": spread / mean_observed if mean_observed else float("nan"),
        "mean_observed_m": mean_observed,
    }


def fit_correction(pairs: list[Pair]) -> tuple[float, float]:
    """Least-squares ``observed ~ a + b * forecast``.

    Deliberately the simplest model that can express both halves of what a
    coarse model gets wrong at a nearshore point: a constant offset (a) and a
    systematic over- or under-response to sea state (b). Anything richer would
    fit 2023-2024's weather rather than the model's geometry.
    """
    rows = [[1.0, p.forecast] for p in pairs]
    targets = [p.observed for p in pairs]
    coefficients = least_squares(rows, targets)
    return coefficients[0], coefficients[1]


def quantile(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    position = q * (len(ordered) - 1)
    low = int(math.floor(position))
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def calibrate_and_test(
    pairs: list[Pair],
    train_years: tuple[int, ...],
    test_years: tuple[int, ...],
    bands: tuple[float, ...] = (0.70, 0.90),
) -> dict | None:
    """Fit on one period, measure on another, and check the bands are honest."""

    train = [p for p in pairs if p.valid.year in train_years]
    test = [p for p in pairs if p.valid.year in test_years]
    if len(train) < 30 or len(test) < 30:
        return None

    intercept, slope = fit_correction(train)
    residuals = [p.observed - (intercept + slope * p.forecast) for p in train]

    raw_errors = [p.forecast - p.observed for p in test]
    corrected = [(intercept + slope * p.forecast) - p.observed for p in test]

    # Two shapes of band, because which one is right is an empirical question
    # and asserting it is how you end up publishing a confident wrong interval.
    # Fixed: the same +/- at every size. Proportional: the interval scales with
    # the forecast, on the theory that a 6 ft call is uncertain by feet where a
    # 1 ft call is uncertain by inches.
    ratios = [
        (p.observed - (intercept + slope * p.forecast)) / max(p.forecast, 0.1)
        for p in train
    ]
    coverage = {}
    for band in bands:
        tail = (1.0 - band) / 2.0
        low, high = quantile(residuals, tail), quantile(residuals, 1.0 - tail)
        low_ratio, high_ratio = quantile(ratios, tail), quantile(ratios, 1.0 - tail)
        fixed_inside = scaled_inside = 0
        for p in test:
            residual = p.observed - (intercept + slope * p.forecast)
            scale = max(p.forecast, 0.1)
            if low <= residual <= high:
                fixed_inside += 1
            if low_ratio * scale <= residual <= high_ratio * scale:
                scaled_inside += 1
        coverage[band] = {
            "half_width_m": (high - low) / 2.0,
            "half_width_ft": (high - low) / 2.0 * METRES_TO_FEET,
            "actual": fixed_inside / len(test),
            "actual_scaled": scaled_inside / len(test),
        }

    return {
        "n_train": len(train),
        "n_test": len(test),
        "intercept_m": intercept,
        "slope": slope,
        "rmse_raw_m": rmse(raw_errors),
        "rmse_calibrated_m": rmse(corrected),
        "bias_raw_m": statistics.fmean(raw_errors),
        "bias_calibrated_m": statistics.fmean(corrected),
        "coverage": coverage,
    }


def wobble(
    points: list[ForecastPoint], only: set[datetime] | None = None
) -> dict[int, dict]:
    """How much a forecast for one moment moves as the model gets closer.

    Needs no observations at all: for every valid time held at two adjacent lead
    times, this measures the change between them. A model whose ten-day call
    survives to one day is stable whether or not it is right; a model that
    rewrites the week every cycle is the thing surfers mean by "wobble", and it
    is a separate failure from being wrong.

    Still takes no observations. `only` restricts the moments considered, so a
    caller that has already decided which hours are south-swell hours can ask
    the same question of that subset without this function ever seeing a buoy
    reading.
    """
    by_valid: dict[datetime, dict[int, float]] = {}
    for point in points:
        if only is not None and point.valid not in only:
            continue
        by_valid.setdefault(point.valid, {})[point.lead_h] = point.hs_total_m

    steps: dict[int, list[float]] = {}
    drifts: dict[int, list[float]] = {}
    revisions: dict[int, list[float]] = {}
    for leads in by_valid.values():
        settled = leads.get(SETTLED_LEAD)
        for lead in leads:
            if lead + 24 in leads:
                steps.setdefault(lead + 24, []).append(abs(leads[lead] - leads[lead + 24]))
            # Cumulative drift is the number a person actually experiences: not
            # "how much did it move last night" but "how different is it from
            # what I saw when I first looked".
            if settled is not None and lead > SETTLED_LEAD:
                drifts.setdefault(lead, []).append(abs(settled - leads[lead]))
                # Signed, and the more diagnostic of the two. Absolute drift
                # says how much a forecast moves; the sign says which way, and
                # a system that moves one way on average is telling on itself.
                # Positive means the model talked itself UP as the event
                # approached - the "it filled in late" story. Negative means it
                # talked itself down.
                revisions.setdefault(lead, []).append(settled - leads[lead])

    return {
        lead: {
            "n": len(changes),
            "mean_shift_m": statistics.fmean(changes),
            "p90_shift_m": quantile(changes, 0.90),
            "mean_drift_m": statistics.fmean(drifts[lead]) if lead in drifts else None,
            "p90_drift_m": quantile(drifts[lead], 0.90) if lead in drifts else None,
            "mean_revision_m": (
                statistics.fmean(revisions[lead]) if lead in revisions else None
            ),
            "share_revised_up": (
                sum(1 for value in revisions[lead] if value > 0) / len(revisions[lead])
                if lead in revisions
                else None
            ),
        }
        for lead, changes in sorted(steps.items())
    }


def report(
    data_dir: Path,
    station_id: str,
    quantity: str,
    train_years: tuple[int, ...],
    test_years: tuple[int, ...],
) -> list[str]:
    points = load_forecasts(data_dir / "wave_forecasts" / f"{station_id}.csv")
    if not points:
        return [f"{station_id}: no archived forecasts; run collector.gfswave_backfill"]

    pairs = pair_up(points, data_dir, station_id, quantity)
    lines = [
        f"## {station_id} — {quantity} significant wave height",
        f"cycles {points[0].cycle:%Y-%m-%d}..{points[-1].cycle:%Y-%m-%d}, "
        f"{len(points)} forecast points, {len(pairs)} matched to the buoy",
        "",
        "lead |     n | bias m | rmse m | scatter | obs mean m",
        "-----+-------+--------+--------+---------+-----------",
    ]
    leads = sorted({p.lead_h for p in pairs})
    for lead in leads:
        stats = error_stats([p for p in pairs if p.lead_h == lead])
        if stats.get("n", 0) < 2:
            lines.append(f"{lead:4d} | {stats.get('n', 0):5d} |   (too few)")
            continue
        lines.append(
            f"{lead:4d} | {stats['n']:5d} | {stats['bias_m']:+6.2f} | "
            f"{stats['rmse_m']:6.2f} | {stats['scatter_index']:7.1%} | "
            f"{stats['mean_observed_m']:10.2f}"
        )

    lines += [
        "",
        f"### Calibration — fit {train_years}, tested on {test_years}",
        "'actual' is what fraction of the test year really landed inside the band;",
        "'scaled' is the same band made proportional to the forecast height.",
        "",
        "lead | rmse raw | rmse cal |  gain | 70% +/- ft | 70% act | scaled | 90% act",
        "-----+----------+----------+-------+------------+---------+--------+--------",
    ]
    for lead in leads:
        result = calibrate_and_test(
            [p for p in pairs if p.lead_h == lead], train_years, test_years
        )
        if result is None:
            lines.append(f"{lead:4d} |  (too few pairs to split)")
            continue
        gain = 1.0 - result["rmse_calibrated_m"] / result["rmse_raw_m"]
        band70 = result["coverage"][0.70]
        band90 = result["coverage"][0.90]
        lines.append(
            f"{lead:4d} | {result['rmse_raw_m']:8.2f} | "
            f"{result['rmse_calibrated_m']:8.2f} | {gain:+5.1%} | "
            f"{band70['half_width_ft']:10.2f} | {band70['actual']:7.1%} | "
            f"{band70['actual_scaled']:6.1%} | {band90['actual']:7.1%}"
        )

    lines += [
        "",
        "### Run-to-run wobble — no observations involved",
        f"'drift' is the gap to the same day's +{SETTLED_LEAD}h forecast: what a",
        "person who looked early actually experiences by the time it arrives.",
        "'revision' is the same gap WITH ITS SIGN, and '% up' the share that were",
        "revised upward. A model that fills in late revises up; near 50% is a",
        "model with no standing story about its own error.",
        f"Restricted to the {len({p.valid for p in pairs})} {quantity}-regime "
        "hours the buoy confirmed."
        if quantity != "total"
        else "All hours.",
        "",
        "lead | n step | mean step m | p90 drift m | mean revision m | % up",
        "-----+-------+-------------+-------------+-----------------+------",
    ]
    moments = {p.valid for p in pairs} if quantity != "total" else None
    for lead, stats in wobble(points, moments).items():
        if stats["mean_revision_m"] is None:
            tail = f"{'-':>11} | {'-':>15} | {'-':>5}"
        else:
            tail = (
                f"{stats['p90_drift_m']:11.2f} | {stats['mean_revision_m']:+15.3f} | "
                f"{stats['share_revised_up']:5.1%}"
            )
        lines.append(
            f"{lead:4d} | {stats['n']:5d} | {stats['mean_shift_m']:11.2f} | {tail}"
        )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--stations", default="46232,46224,46222")
    parser.add_argument("--quantity", default="total", choices=("total", "south"))
    parser.add_argument("--train-years", default=",".join(str(y) for y in DEFAULT_TRAIN_YEARS))
    parser.add_argument("--test-years", default=",".join(str(y) for y in DEFAULT_TEST_YEARS))
    args = parser.parse_args(argv)

    train = tuple(int(y) for y in args.train_years.split(",") if y.strip())
    test = tuple(int(y) for y in args.test_years.split(",") if y.strip())

    lines: list[str] = []
    for station_id in [s.strip() for s in args.stations.split(",") if s.strip()]:
        lines += report(args.data_dir, station_id, args.quantity, train, test)
        lines.append("")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
