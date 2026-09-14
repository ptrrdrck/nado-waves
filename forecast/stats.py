"""Is there any skill to score in a quantity? The residual test.

    python -m forecast.stats --column wtmp --wind-station 46086

SPEC section 2 requires every candidate quantity to pass a residual-error check
against the baseline before it ships. This is that check, made repeatable, so a
v2 candidate can be rejected in an afternoon instead of after building a game on
it.

**The question is not "does this quantity move".** It is "is the part that moves
*predictable by some players and not others*". Three outcomes:

* **Skill ceiling near zero** — nobody can beat persistence. The leaderboard is
  a lottery no matter how the points are scaled. This is the failure mode that
  is easy to miss, because the quantity can look exciting while being noise.
* **Skill ceiling high, and public forecasts capture it** — everyone who reads a
  forecast scores identically. Solved. This is what SPEC section 2 rejected wave
  height for.
* **Skill ceiling high, public forecasts do not capture it** — a game exists.

The ceiling is deliberately fit **in sample**, with no train/test split. That
overfits on purpose: a number a real player could never achieve is the right
shape for an upper bound. If the in-sample ceiling is small, the honest ceiling
is smaller, and no cleverness recovers it.
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from collector.common import DEFAULT_DATA_DIR
from collector.stations import load_stations, select
#: Every beach in this project is in one timezone, and daily aggregation
#: has to happen in local days rather than UTC days or the "day" straddles
#: two afternoons' sea breeze.
LEAGUE_TZ = ZoneInfo("America/Los_Angeles")

#: Alongshore axis for SoCal upwelling. Wind from this direction drives the
#: offshore Ekman transport that brings cold water up.
UPWELLING_AXIS_DEG = 320.0


def load_column(path: Path, column: str) -> dict[datetime, float]:
    out: dict[datetime, float] = {}
    if not path.exists():
        return out
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            raw = (row.get(column) or "").strip()
            if not raw:
                continue
            try:
                value = float(raw)
                stamp = datetime.strptime(
                    row["timestamp_utc"], "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=timezone.utc)
            except (ValueError, KeyError):
                continue
            out[stamp] = value
    return dict(sorted(out.items()))


#: Circular quantities. 359 degrees and 1 degree are two degrees apart, not
#: 358, so neither the daily aggregate nor the day-to-day change can be computed
#: the ordinary way — and a linear fit on raw degrees is meaningless across the
#: wrap. These get vector treatment instead.
CIRCULAR_COLUMNS = {"wdir", "mwd"}


def angular_difference(later: float, earlier: float) -> float:
    """Signed degrees from `earlier` to `later`, wrapped to [-180, 180).

    An exact half-turn is equally far in both directions; it resolves to -180.
    Arbitrary, but deterministic, which is what matters for a scored game.
    """

    return (later - earlier + 180.0) % 360.0 - 180.0


def daily_circular_mean(
    series: dict[datetime, float], tz: ZoneInfo = LEAGUE_TZ, minimum: int = 18
) -> dict:
    """Mean direction per day, via unit vectors rather than arithmetic."""

    buckets: dict = {}
    for stamp, degrees in series.items():
        buckets.setdefault(stamp.astimezone(tz).date(), []).append(degrees)
    out = {}
    for day, values in buckets.items():
        if len(values) < minimum:
            continue
        x = statistics.fmean(math.cos(math.radians(v)) for v in values)
        y = statistics.fmean(math.sin(math.radians(v)) for v in values)
        if x == 0.0 and y == 0.0:
            continue
        out[day] = math.degrees(math.atan2(y, x)) % 360.0
    return dict(sorted(out.items()))


def fit_circular(
    daily: dict, horizon: int, features: tuple[str, ...]
) -> tuple[float, float, int] | None:
    """Predictability of a DIRECTION, in degrees.

    The target is the wrapped angular change; the current direction enters the
    fit as its sine and cosine, so the model never sees a discontinuity at
    north. Persistence means "it will be pointing the same way tomorrow".
    """

    rows: list[list[float]] = []
    targets: list[float] = []
    for day in sorted(daily):
        nxt = day + timedelta(days=horizon)
        prev, prev2 = day - timedelta(days=1), day - timedelta(days=2)
        if nxt not in daily or prev not in daily or prev2 not in daily:
            continue
        doy = day.timetuple().tm_yday
        radians = math.radians(daily[day])
        row = [1.0]
        if "level" in features:
            row += [math.sin(radians), math.cos(radians)]
        if "season" in features:
            row += [math.sin(2 * math.pi * doy / 365), math.cos(2 * math.pi * doy / 365)]
        if "weather" in features:
            row += [
                angular_difference(daily[day], daily[prev]),
                angular_difference(daily[prev], daily[prev2]),
            ]
        rows.append(row)
        targets.append(angular_difference(daily[nxt], daily[day]))

    if len(rows) < 300:
        return None
    beta = least_squares(rows, targets)
    predicted = [sum(b * x for b, x in zip(beta, row)) for row in rows]
    base = rmse(targets)
    fitted = rmse([t - p for t, p in zip(targets, predicted)])
    return base, (base - fitted) / base * 100, len(rows)


def contested_circular(daily: dict, horizon: int) -> float | None:
    public = fit_circular(daily, horizon, PUBLIC_FEATURES)
    everything = fit_circular(daily, horizon, ALL_FEATURES)
    if public is None or everything is None:
        return None
    return everything[1] - public[1]


def daily_mean(
    series: dict[datetime, float], tz: ZoneInfo = LEAGUE_TZ, minimum: int = 18
) -> dict:
    buckets: dict = {}
    for stamp, value in series.items():
        buckets.setdefault(stamp.astimezone(tz).date(), []).append(value)
    return {
        day: statistics.fmean(values)
        for day, values in buckets.items()
        if len(values) >= minimum
    }


def daily_upwelling_wind(data_dir: Path, station_id: str, tz: ZoneInfo = LEAGUE_TZ) -> dict:
    path = data_dir / "historical" / f"{station_id.upper()}.csv"
    speed = load_column(path, "wspd")
    direction = load_column(path, "wdir")
    buckets: dict = {}
    for stamp, value in speed.items():
        bearing = direction.get(stamp)
        if bearing is None:
            continue
        along = value * math.cos(math.radians(bearing - UPWELLING_AXIS_DEG))
        buckets.setdefault(stamp.astimezone(tz).date(), []).append(along)
    return {
        day: statistics.fmean(values)
        for day, values in buckets.items()
        if len(values) >= 12
    }


def least_squares(rows: list[list[float]], targets: list[float]) -> list[float]:
    """Gauss-Jordan on the normal equations. Stdlib only, like everything here."""

    n, k = len(rows), len(rows[0])
    a = [[sum(rows[i][x] * rows[i][y] for i in range(n)) for y in range(k)] for x in range(k)]
    b = [sum(rows[i][x] * targets[i] for i in range(n)) for x in range(k)]
    for col in range(k):
        pivot = max(range(col, k), key=lambda r: abs(a[r][col]))
        a[col], a[pivot] = a[pivot], a[col]
        b[col], b[pivot] = b[pivot], b[col]
        if abs(a[col][col]) < 1e-12:
            continue
        for row in range(k):
            if row == col:
                continue
            factor = a[row][col] / a[col][col]
            for c in range(col, k):
                a[row][c] -= factor * a[col][c]
            b[row] -= factor * b[col]
    return [b[i] / a[i][i] if abs(a[i][i]) > 1e-12 else 0.0 for i in range(k)]


def rmse(errors: list[float]) -> float:
    return (sum(e * e for e in errors) / len(errors)) ** 0.5 if errors else float("nan")


#: Feature groups. The first two are facts every player has — how far today sits
#: from the seasonal norm, and that extremes decay. Skill "against" them is not
#: skill; it is a knowledge gap that closes the day somebody writes it down.
PUBLIC_FEATURES = ("level", "season")
ALL_FEATURES = ("level", "season", "weather")


def fit_subset(
    daily: dict, horizon: int, features: tuple[str, ...], wind: dict | None = None
) -> tuple[float, float, int] | None:
    """(persistence RMSE, ceiling %, n) using only the named feature groups."""

    rows: list[list[float]] = []
    targets: list[float] = []
    for day in sorted(daily):
        nxt = day + timedelta(days=horizon)
        prev, prev2 = day - timedelta(days=1), day - timedelta(days=2)
        if nxt not in daily or prev not in daily or prev2 not in daily:
            continue
        doy = day.timetuple().tm_yday
        row = [1.0]
        if "level" in features:
            row.append(daily[day])
        if "season" in features:
            row += [math.sin(2 * math.pi * doy / 365), math.cos(2 * math.pi * doy / 365)]
        if "weather" in features:
            row += [daily[day] - daily[prev], daily[prev] - daily[prev2]]
        if "wind" in features and wind is not None:
            lags = [day - timedelta(days=k) for k in range(4)]
            if not all(lag in wind for lag in lags):
                continue
            row += [wind[lag] for lag in lags]
        rows.append(row)
        targets.append(daily[nxt] - daily[day])

    if len(rows) < 300:
        return None
    beta = least_squares(rows, targets)
    predicted = [sum(b * x for b, x in zip(beta, row)) for row in rows]
    base = rmse(targets)
    fitted = rmse([t - p for t, p in zip(targets, predicted)])
    return base, (base - fitted) / base * 100, len(rows)


def contested_skill(daily: dict, horizon: int, wind: dict | None = None) -> float | None:
    """How much is left to compete over once everyone applies the public facts.

    This, not the raw ceiling, is what decides a leaderboard. Wave height at
    seven days has a 26% ceiling and 0.1% of it is contested: the rest is
    "big swells decay", which every player knows.
    """

    public = fit_subset(daily, horizon, PUBLIC_FEATURES, wind)
    everything = fit_subset(daily, horizon, ALL_FEATURES + ("wind",), wind)
    if public is None:
        return None
    if everything is None:
        everything = fit_subset(daily, horizon, ALL_FEATURES, wind)
    if everything is None:
        return None
    return everything[1] - public[1]


def assess(
    daily: dict, wind: dict | None, horizon: int = 1
) -> tuple[float, float, int] | None:
    """(persistence RMSE, skill ceiling %, n) for an `horizon`-day-ahead change.

    The horizon matters as much as the quantity. A residual that is noise at one
    day can be synoptic weather at five, which is forecastable — and the reverse
    holds too, so it has to be measured rather than assumed.
    """

    rows: list[list[float]] = []
    targets: list[float] = []
    for day in sorted(daily):
        nxt, prev, prev2 = (
            day + timedelta(days=horizon),
            day - timedelta(days=1),
            day - timedelta(days=2),
        )
        if nxt not in daily or prev not in daily or prev2 not in daily:
            continue
        doy = day.timetuple().tm_yday
        features = [
            1.0,
            daily[day],
            daily[day] - daily[prev],
            daily[prev] - daily[prev2],
            math.sin(2 * math.pi * doy / 365),
            math.cos(2 * math.pi * doy / 365),
        ]
        if wind is not None:
            lags = [day - timedelta(days=k) for k in range(4)]
            if not all(lag in wind for lag in lags):
                continue
            features.extend(wind[lag] for lag in lags)
            features.append(statistics.fmean([wind[lag] for lag in lags]))
        rows.append(features)
        targets.append(daily[nxt] - daily[day])

    if len(rows) < 300:
        return None
    beta = least_squares(rows, targets)
    predicted = [sum(b * x for b, x in zip(beta, row)) for row in rows]
    base = rmse(targets)
    fitted = rmse([t - p for t, p in zip(targets, predicted)])
    return base, (base - fitted) / base * 100, len(rows)


def _constraining(registry):
    """The default station set, imported at call time on purpose.

    `forecast.siting` reaches `forecast.geometry` -> `forecast.swell`, and
    `swell` still imports `LEAGUE_TZ` from this module — a leftover from the
    predecessor game (see CLAUDE.md: trimming this module is a good first
    cleanup). Until that dependency goes, a module-level import here closes a
    cycle. Deferring it is the small fix; untangling `swell` is the real one.
    """

    from .siting import constraining

    return constraining(registry)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Residual test for a candidate quantity.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--column", default="wtmp", help="wtmp, wvht, atmp, ...")
    parser.add_argument("--stations", help="Comma-separated ids. Default: launch candidates.")
    parser.add_argument(
        "--wind-station",
        help="Station to take an upwelling wind index from (needs wspd/wdir).",
    )
    args = parser.parse_args(argv)

    registry = load_stations()
    stations = (
        select(registry, args.stations.split(","))
        if args.stations
        else _constraining(registry)
    )

    wind = (
        daily_upwelling_wind(args.data_dir, args.wind_station)
        if args.wind_station
        else None
    )

    print(f"Residual test — {args.column}, {args.horizon} day(s) ahead, daily means")
    if wind:
        print(f"Wind predictors from {args.wind_station} ({len(wind)} days)")
    print()
    print(f"{'Station':<9} {'n':>6} {'persistence RMSE':>18} {'skill ceiling':>15}")
    print("-" * 52)

    ceilings = []
    for station in stations:
        path = args.data_dir / "historical" / f"{station.id}.csv"
        result = assess(
            daily_mean(load_column(path, args.column)), wind, args.horizon
        )
        if result is None:
            print(f"{station.id:<9} {'—':>6} {'not enough history':>18}")
            continue
        base, ceiling, n = result
        ceilings.append(ceiling)
        print(f"{station.id:<9} {n:>6} {base:>18.3f} {ceiling:>14.1f}%")

    if not ceilings:
        print("\nNo station had enough history. Run `python -m collector.backfill` first.")
        return 0

    mean = statistics.fmean(ceilings)
    print()
    print(f"Skill ceiling (in sample, so an overestimate): {mean:+.1f}%")
    print()
    if mean < 10:
        print(
            "**Below 10%. There is essentially nothing to be good at.** A player\n"
            "with perfect knowledge of everything measurable barely beats one who\n"
            "copies the baseline, so the leaderboard is decided by luck however the\n"
            "points are scaled. This fails SPEC section 2's 'forecastable' half."
        )
    else:
        print(
            "Materially predictable from its own history. That clears the\n"
            "'forecastable' half of SPEC section 2 — now check the other half:\n"
            "if public forecasts already capture this, everyone scores the same\n"
            "and it is solved."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
