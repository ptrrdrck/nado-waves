"""GEFS-Wave's ensemble at 46232, and how often the buoy has fallen inside it.

Findings in BRIEFING §35. Run: ``python -m forecast.ensemble`` -- writes ``docs/ensemble_spread.md``.

What the page draws from it (`for_forecast`, `coverage`): on the Forecast
tab's buoy chart, the ensemble mean with a shaded band one spread either side,
and beside it, per lead time, the share of hours on which 46232 actually fell
inside that band -- measured here, against the buoy, over the dates it names.
That is the only way a band gets onto this page (CLAUDE.md: bands are
earned, and an accuracy figure names its verification series). It is a band
**at the buoy**. The bulletin has total Hs only, no direction, so it cannot be
carried through a break's windows, and nothing here says anything about the
beach.

What it measures, in order:

1. **The ensemble mean against GFS-Wave**, 2023-2025 00Z, against the buoy
   archive: whether 31 runs averaged share the single run's low bias
   (BRIEFING §5, §33). Every member is the same wave model, so they should.
2. **The spread against the buoy**, from the first cycle that published one
   (`collector.gefswave.SPREAD_STARTS`) to the end of the buoy record in the
   repository: the share of hours inside mean ± 1 spread and ± 2 spread, by
   lead. A calibrated Gaussian ensemble would hold ~68% and ~95%; an
   ensemble too narrow for its own error holds far less.
3. **The exceedance shares** P(Hs > 1 m) and P(Hs > 2 m): the mean share
   against how often the buoy was above, and a Brier score.

It reports and never edits. It fits nothing, removes no bias, and widens no
band: any of those would be a correction, and applying one waits on the
owner's decision and on what info.html calls it.
"""

from __future__ import annotations

import argparse
import math
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR, ISO
from collector.gefswave import SPREAD_STARTS, archive_path, read
from .stats import load_column
from .verify import SOUTH_MIN_PERIOD, SOUTH_WINDOW, _indexed, _lookup

STATION = "46232"

#: Lead-time buckets the coverage is reported and shown in, in hours:
#: [low, high). The page picks the bucket an hour's lead falls in.
LEAD_BUCKETS = ((0, 24), (24, 72), (72, 120), (120, 168), (168, 241))

#: The exceedance columns whose threshold was MEASURED, by what they hold
#: rather than what their header says (`collector.gefswave.THRESHOLDS_M`).
#: The others are never read.
P_ABOVE = {1.0: "p_col2", 2.0: "p_col3"}

#: Fewer pairs than this in a bucket and its coverage is not published: a
#: share of a handful of hours is a number, not a measurement.
MIN_PAIRS = 40

DOC = Path(__file__).resolve().parent.parent / "docs" / "ensemble_spread.md"


def _parse(stamp: str) -> datetime:
    return datetime.strptime(stamp, ISO).replace(tzinfo=timezone.utc)


def _num(value: str | None) -> float | None:
    return float(value) if value not in (None, "") else None


def observations(data_dir: Path = DEFAULT_DATA_DIR, station: str = STATION) -> dict:
    """46232's measured Hs, period and direction: the three-year archive and
    the collected record after it. A sentinel is not a wave height."""

    out = {}
    for column in ("wvht", "dpd", "mwd"):
        merged = {}
        for path in (Path(data_dir) / "historical" / f"{station}.csv",
                     Path(data_dir) / "observations" / f"{station}.csv"):
            merged.update(load_column(path, column))
        if column == "wvht":
            merged = {t: v for t, v in merged.items() if 0 <= v < 90}
        out[column] = _indexed(merged)
    return out


@dataclass(frozen=True)
class Pair:
    cycle: datetime
    valid: datetime
    lead_h: int
    mean: float
    spread: float | None
    p1: float | None
    p2: float | None
    observed: float
    south: bool


def pairs(rows: list[dict], obs: dict) -> list[Pair]:
    """Each bulletin row matched to the buoy at its valid hour, or dropped.

    Never interpolated: an hour the buoy did not report shrinks the sample
    (`verify.nearest_observation`)."""

    out = []
    for row in rows:
        valid = _parse(row["valid_utc"])
        seen = _lookup(obs["wvht"], valid)
        if seen is None:
            continue
        dpd, mwd = _lookup(obs["dpd"], valid), _lookup(obs["mwd"], valid)
        south = (dpd is not None and mwd is not None and dpd >= SOUTH_MIN_PERIOD
                 and SOUTH_WINDOW[0] <= mwd <= SOUTH_WINDOW[1])
        out.append(Pair(_parse(row["cycle_utc"]), valid, int(row["lead_h"]),
                        float(row["hs_mean_m"]), _num(row.get("hs_spread_m")),
                        _num(row.get(P_ABOVE[1.0])), _num(row.get(P_ABOVE[2.0])),
                        seen, south))
    return out


def bucket_of(lead_h: int) -> tuple[int, int] | None:
    return next((b for b in LEAD_BUCKETS if b[0] <= lead_h < b[1]), None)


def coverage(matched: list[Pair], *, south_only: bool = False) -> list[dict]:
    """Per lead bucket: how often the buoy fell inside mean ± 1 and ± 2
    spread, and the mean's own bias and scatter. Only pairs that carry a
    spread count; a bucket under `MIN_PAIRS` reports its n and nothing else."""

    grouped: dict[tuple[int, int], list[Pair]] = defaultdict(list)
    for p in matched:
        if p.spread is None or (south_only and not p.south):
            continue
        b = bucket_of(p.lead_h)
        if b:
            grouped[b].append(p)
    out = []
    for b in LEAD_BUCKETS:
        got = grouped.get(b, [])
        entry = {"lead_from_h": b[0], "lead_to_h": b[1], "n": len(got),
                 "cycles": len({p.cycle for p in got})}
        if got:
            entry["first_utc"] = min(p.valid for p in got).strftime(ISO)
            entry["last_utc"] = max(p.valid for p in got).strftime(ISO)
        if len(got) >= MIN_PAIRS:
            err = [p.observed - p.mean for p in got]
            bias = sum(err) / len(err)
            entry.update({
                "inside_1": sum(abs(e) <= p.spread for e, p in zip(err, got)) / len(got),
                "inside_2": sum(abs(e) <= 2 * p.spread for e, p in zip(err, got)) / len(got),
                "buoy_minus_mean_m": bias,
                "error_sd_m": math.sqrt(sum((e - bias) ** 2 for e in err) / (len(err) - 1)),
                "mean_spread_m": sum(p.spread for p in got) / len(got),
            })
        out.append(entry)
    return out


def exceedance(matched: list[Pair]) -> list[dict]:
    """The share of members above 1 m and 2 m against how often the buoy was,
    per lead bucket, with a Brier score. Pairs with shares only."""

    out = []
    for b in LEAD_BUCKETS:
        got = [p for p in matched if p.p1 is not None and bucket_of(p.lead_h) == b]
        entry = {"lead_from_h": b[0], "lead_to_h": b[1], "n": len(got)}
        if len(got) >= MIN_PAIRS:
            for key, limit in (("1m", 1.0), ("2m", 2.0)):
                prob = [p.p1 if limit == 1.0 else p.p2 for p in got]
                hit = [1.0 if p.observed > limit else 0.0 for p in got]
                entry[f"p_gt_{key}_mean"] = sum(prob) / len(prob)
                entry[f"gt_{key}_observed"] = sum(hit) / len(hit)
                entry[f"brier_{key}"] = sum((q - o) ** 2 for q, o in zip(prob, hit)) / len(hit)
        out.append(entry)
    return out


def mean_against_single_run(matched: list[Pair], data_dir: Path) -> list[dict]:
    """The ensemble mean's bias and RMSE beside GFS-Wave's, on the SAME
    (cycle, lead) pairs -- 00Z cycles both archives hold."""

    single = {}
    path = Path(data_dir) / "wave_forecasts" / f"{STATION}.csv"
    if path.exists():
        import csv
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                single[(row["cycle_utc"], int(row["lead_h"]))] = float(row["hs_total_m"])
    out = []
    for b in LEAD_BUCKETS:
        both = []
        for p in matched:
            if bucket_of(p.lead_h) != b:
                continue
            g = single.get((p.cycle.strftime(ISO), p.lead_h))
            if g is not None:
                both.append((p.observed, p.mean, g))
        entry = {"lead_from_h": b[0], "lead_to_h": b[1], "n": len(both)}
        if len(both) >= MIN_PAIRS:
            for key, k in (("mean", 1), ("single", 2)):
                err = [row[k] - row[0] for row in both]
                entry[f"{key}_bias_m"] = sum(err) / len(err)
                entry[f"{key}_rmse_m"] = math.sqrt(sum(e * e for e in err) / len(err))
        out.append(entry)
    return out


def load(data_dir: Path = DEFAULT_DATA_DIR, *, spread_only: bool = False
         ) -> tuple[list[dict], list[Pair]]:
    """The archive and its rows matched to the buoy. `spread_only` skips the
    means-only years, which only the report's first table reads."""

    rows = read(archive_path(STATION, data_dir))
    if spread_only:
        rows = [r for r in rows if r.get("hs_spread_m")]
    return rows, pairs(rows, observations(data_dir))


# ---------------------------------------------------------------- the page


def for_forecast(rows: list[dict], matched: list[Pair], cycle_utc: str | None,
                 *, step: int = 3, until_utc: str | None = None) -> dict:
    """What `forecast.live` puts in forecast.json: the newest ensemble cycle
    at or before the model run on screen, every `step` hours, and the measured
    coverage beside it. Without a spread there is no band, and the block says
    why rather than drawing one."""

    with_spread = sorted({r["cycle_utc"] for r in rows if r.get("hs_spread_m")})
    usable = [c for c in with_spread if cycle_utc is None or c <= cycle_utc]
    if not usable:
        return {"available": False,
                "why": "no GEFS-Wave cycle with a spread at or before this run"}
    cycle = usable[-1]
    hours = []
    for r in rows:
        if r["cycle_utc"] != cycle or _parse(r["valid_utc"]).hour % step:
            continue
        if until_utc and r["valid_utc"] > until_utc:
            continue
        hours.append({"valid_utc": r["valid_utc"], "lead_h": int(r["lead_h"]),
                      "hs_mean_m": float(r["hs_mean_m"]),
                      "hs_spread_m": float(r["hs_spread_m"]),
                      "p_gt_1m": _num(r.get(P_ABOVE[1.0])),
                      "p_gt_2m": _num(r.get(P_ABOVE[2.0]))})
    return {
        "available": True,
        "model": "GEFS-Wave",
        "members": 31,
        "station": STATION,
        "cycle_utc": cycle,
        "hours": hours,
        # Measured, per lead bucket, against the buoy: the page shows the
        # share beside the band, with the dates and n it rests on.
        "coverage": coverage(matched),
        "standing_on": {
            "band": "GEFS-Wave's 31 members at the buoy: their mean, and one standard "
                    "deviation either side. The model disagreeing with itself, not a range "
                    "the swell will fall in.",
            "measured": f"How often buoy {STATION} fell inside that band, per lead, over the "
                        "dates named -- the only check on it. Nothing measures the breaks, and "
                        "the ensemble has no direction to carry through their windows.",
        },
    }


# ---------------------------------------------------------------- the report


def _pct(v):
    return "—" if v is None else f"{100 * v:.0f}%"


def _m(v):
    return "—" if v is None else f"{v:+.2f}"


def _f(v):
    return "—" if v is None else f"{v:.2f}"


def report(data_dir: Path = DEFAULT_DATA_DIR) -> str:
    rows, matched = load(data_dir)
    lines = ["# GEFS-Wave's ensemble at 46232, against the buoy", "",
             "Generated by `python -m forecast.ensemble`. Reports; never edits.", ""]
    if not rows:
        return "\n".join(lines + ["No GEFS-Wave cycles archived yet."])
    cycles = sorted({r["cycle_utc"] for r in rows})
    lines += [f"{len(cycles)} cycles archived, {cycles[0]} to {cycles[-1]}; "
              f"{len(matched)} rows matched to a buoy reading.", ""]

    lines += ["## 1. The ensemble mean beside GFS-Wave's single run", "",
              "Same 00Z cycles, same leads, same buoy hours. Model minus buoy.", "",
              "| lead | n | mean bias | mean RMSE | single-run bias | single-run RMSE |",
              "|---|---|---|---|---|---|"]
    for e in mean_against_single_run(matched, data_dir):
        lines.append(f"| {e['lead_from_h']}–{e['lead_to_h']} h | {e['n']} | "
                     f"{_m(e.get('mean_bias_m'))} | {_f(e.get('mean_rmse_m'))} | "
                     f"{_m(e.get('single_bias_m'))} | {_f(e.get('single_rmse_m'))} |")

    for label, south in (("All hours", False), ("South-swell hours (buoy DPD ≥ 14 s, MWD 160–230°)", True)):
        lines += ["", f"## 2. How often the buoy fell inside the spread — {label}", "",
                  f"Cycles from {SPREAD_STARTS:%Y-%m-%d %HZ}, when the bulletin began printing a "
                  "spread. A calibrated ensemble holds ~68% inside ±1 spread and ~95% inside ±2.", "",
                  "| lead | n | cycles | inside ±1 | inside ±2 | buoy − mean | error sd | mean spread | dates |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for e in coverage(matched, south_only=south):
            dates = f"{e.get('first_utc', '')[:10]} to {e.get('last_utc', '')[:10]}" if e["n"] else ""
            lines.append(
                f"| {e['lead_from_h']}–{e['lead_to_h']} h | {e['n']} | {e['cycles']} | "
                f"{_pct(e.get('inside_1'))} | {_pct(e.get('inside_2'))} | "
                f"{_m(e.get('buoy_minus_mean_m'))} | {_f(e.get('error_sd_m'))} | "
                f"{_f(e.get('mean_spread_m'))} | {dates} |")

    lines += ["", "## 3. The exceedance shares", "",
              "| lead | n | P(>1 m) mean | >1 m observed | Brier | P(>2 m) mean | >2 m observed | Brier |",
              "|---|---|---|---|---|---|---|---|"]
    for e in exceedance(matched):
        lines.append(
            f"| {e['lead_from_h']}–{e['lead_to_h']} h | {e['n']} | {_pct(e.get('p_gt_1m_mean'))} | "
            f"{_pct(e.get('gt_1m_observed'))} | {_f(e.get('brier_1m'))} | "
            f"{_pct(e.get('p_gt_2m_mean'))} | {_pct(e.get('gt_2m_observed'))} | "
            f"{_f(e.get('brier_2m'))} |")
    lines += ["", f"Buckets with fewer than {MIN_PAIRS} pairs show their n and nothing else.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--out", type=Path, default=DOC)
    args = parser.parse_args(argv)
    text = report(args.data_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
