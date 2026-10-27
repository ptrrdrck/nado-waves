"""The LIVE briefing's thresholds, measured.

    python -m forecast.briefingreport            # the report
    python -m forecast.briefingreport --write    # ... into docs/briefing_thresholds.md

The briefing (`forecast.briefing`) says a thing only where it is right at
least `RIGHT` of the times it fires, the Phase fold's rule (BRIEFING §41).
"Right" here is a reasonable expectation, never a forecast: what the
briefing says about the last few hours still holds over the next three.

- **Rose / dropped since sunset.** Decided on 3-hour medians (the newest
  three readings, and the three around sunset) by a relative change. Right
  when the median of the NEXT three hours sits on the same side of sunset's.
  Every span from 6 to 24 h, every break, from `data/series/` (the observed
  chain rebuilt with today's chain; a gap is a gap).
- **Which break leads.** The newest three-hour medians, the leader ahead of
  the second by a relative margin. Right when the next three hours' medians
  have the same leader.
- **A ridge's period ahead.** Origin's fitted line, from the first moment the
  ridge passes Origin's gate, projected 12, 24 and 36 h on; right when the
  ridge's own reading then is within 1 s.
- **The wind's onshore habit.** Each day's first onshore hour (> 3 kt, by
  the card's `sense`) at each break from KNZY, against the median of the 14
  days before; right within 1.5 h.
- **Long-period energy ahead** (measured 2026-10-27, at the owner's request,
  to re-run in winter). 46232's energy at periods of `LONG_S` and longer,
  from the breaks' windows (the arc spanning the three, `long_arc`), fires
  when it doubles on 3 h before -- each hour's own, or 3-hour means -- and
  reaches `LONG_FLOOR_M` as a height; a firing within 12 h of the last is
  the same one. Right when the beach (the biggest of the three breaking
  heights) is `briefing.CHANGE_SHARE` above its height at the firing within
  24 h, or its biggest in the next 36 h is that much above its biggest in
  the 24 h before ("a bigger day"); each beside the same over every hour.

Reports, never edits. Pure Python.
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
SERIES = ROOT / "data" / "series" / "46232"
WIND = ROOT / "data" / "wind" / "KNZY.csv"
DOC = ROOT / "docs" / "briefing_thresholds.md"

BREAKS = ("coronado_north", "coronado_center", "coronado_south")
RIGHT = 0.85
SPANS_H = (6, 12, 18, 24)
CHANGE_STEPS = (0.05, 0.08, 0.10, 0.12, 0.15, 0.20)
MARGIN_STEPS = (0.0, 0.03, 0.05, 0.08, 0.10)
HORIZONS_H = (12, 24, 36)
LONG_S = (14.0, 16.0, 18.0)
LONG_FLOOR_M = 0.3
LONG_RATIO = 2.0
LOCAL = ZoneInfo("America/Los_Angeles")


def load_heights(directory: Path = SERIES) -> dict[datetime, list[float]]:
    """Breaking height at the three breaks, hours where all three have one."""

    out = {}
    for path in sorted(directory.glob("*.csv")):
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if row.get("gap") == "1":
                    continue
                vals = [row.get(f"{b}_hs_m") for b in BREAKS]
                if all(vals):
                    t = datetime.fromisoformat(row["valid_utc"].replace("Z", "+00:00"))
                    out[t] = [float(v) for v in vals]
    return out


def median_at(heights, hours, k: int) -> float | None:
    """Median of break k over the given hours, from at least two that exist."""

    vals = [heights[t][k] for t in hours if t in heights]
    return statistics.median(vals) if len(vals) >= 2 else None


def newest3(t):
    return [t - timedelta(hours=h) for h in (0, 1, 2)]


def around(t):
    return [t + timedelta(hours=h) for h in (-1, 0, 1)]


def next3(t):
    return [t + timedelta(hours=h) for h in (1, 2, 3)]


def change_precision(heights, k: int, span_h: int, share: float) -> tuple[int, float]:
    n = ok = 0
    for t in heights:
        then = t - timedelta(hours=span_h)
        now_m, then_m = median_at(heights, newest3(t), k), median_at(heights, around(then), k)
        if now_m is None or then_m is None:
            continue
        rel = now_m / then_m - 1.0
        if abs(rel) < share:
            continue
        ahead = median_at(heights, next3(t), k)
        if ahead is None:
            continue
        n += 1
        ok += (ahead - then_m) * rel > 0
    return n, ok / n if n else float("nan")


def leader(heights, hours) -> tuple[int, float] | None:
    meds = [median_at(heights, hours, k) for k in range(len(BREAKS))]
    if any(m is None for m in meds):
        return None
    order = sorted(range(len(BREAKS)), key=lambda k: -meds[k])
    return order[0], meds[order[0]] / meds[order[1]] - 1.0


def leader_precision(heights, margin: float) -> tuple[int, float]:
    n = ok = 0
    for t in heights:
        now = leader(heights, newest3(t))
        ahead = leader(heights, next3(t))
        if not now or not ahead or now[1] < margin:
            continue
        n += 1
        ok += ahead[0] == now[0]
    return n, ok / n if n else float("nan")


def smallest(steps, measure, *, every) -> float | None:
    """The smallest step right ≥ RIGHT on every case in `every`."""

    for step in steps:
        if all(measure(case, step)[1] >= RIGHT for case in every):
            return step
    return None


def period_projection(spectra=None) -> dict[int, list[float]]:
    """Signed error, seconds, of Origin's line `h` hours after it is gated."""

    from . import origin
    from .transform import load_spectra

    if spectra is None:
        spectra = load_spectra(ROOT / "data" / "spectra" / "46232")
    errors: dict[int, list[float]] = {h: [] for h in HORIZONS_H}
    for ridge in origin.ridges(spectra):
        pts = ridge.points
        fit = None
        for k in range(origin.MIN_POINTS, len(pts) + 1):
            sub = origin.Ridge(pts[:k])
            fit = origin.fit_ridge(sub)
            if origin.qualifies(sub, fit):
                break
        else:
            continue
        gated = pts[k - 1].time
        for h in HORIZONS_H:
            target = gated + timedelta(hours=h)
            seen = [p for p in pts if abs((p.time - target).total_seconds()) <= 1800]
            if seen:
                errors[h].append(projected_period(fit, target) - 1.0 / seen[0].freq_hz)
    return errors


def projected_period(fit, moment: datetime) -> float:
    """The period Origin's line puts at `moment`: f = g(t − t0)/4πR."""

    hours = (moment - fit.generated_utc).total_seconds() / 3600.0
    hz_per_h = 9.81 / (4.0 * 3.141592653589793 * fit.distance_km * 1000.0) * 3600.0
    return 1.0 / (hz_per_h * hours)


def wind_habit(path: Path = WIND) -> dict[str, tuple[int, int]]:
    from .geometry import load
    from .live import offshore_component

    spots, _ = load()
    normal = {s.id: s.normal for s in spots}
    days: dict = {}
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if not row["wind_kt"]:
                continue
            t = datetime.fromisoformat(row["observed_utc"].replace("Z", "+00:00")).astimezone(LOCAL)
            d = row["wind_from_deg"] if row.get("variable") != "true" else ""
            days.setdefault(t.date(), []).append((t, float(row["wind_kt"]), float(d) if d else None))
    out = {}
    for bid in BREAKS:
        onset = {}
        for day, obs in days.items():
            hours = sorted(o for o in obs if 6 <= o[0].hour <= 18)
            if len(hours) < 10:
                continue
            onset[day] = next((t.hour + t.minute / 60.0 for t, kt, d in hours
                               if d is not None and kt > 3 and offshore_component(d, normal[bid]) < -0.3), None)
        hits = n = 0
        for day in sorted(onset):
            before = [onset[d] for d in onset if 0 < (day - d).days <= 14]
            got = [x for x in before if x is not None]
            if len(before) < 7 or len(got) < 0.7 * len(before):
                continue
            n += 1
            hits += onset[day] is not None and abs(onset[day] - statistics.median(got)) <= 1.5
        out[bid] = (hits, n)
    return out


def long_arc() -> list[float]:
    """From the lowest to the highest heading of the three breaks' windows."""

    from .geometry import load, swell_window

    spots, blockers = load()
    wins = [w for s in spots if s.id in BREAKS for w in swell_window(s, blockers)]
    return [min(a for a, _ in wins), max(b for _, b in wins)]


def _beach_rises(beach, t, ahead_h: int, share: float):
    """Whether the beach is `share` above its height at `t` within
    `ahead_h`; None without the hour or most of the hours after it."""

    if t not in beach:
        return None
    later = [beach.get(t + timedelta(hours=h)) for h in range(1, ahead_h + 1)]
    later = [x for x in later if x is not None]
    if len(later) < 0.75 * ahead_h:
        return None
    return max(later) >= (1 + share) * beach[t]


def _bigger_day(beach, t, ahead_h: int, share: float):
    """Whether the beach's biggest in the next `ahead_h` is `share` above its
    biggest in the 24 h before; None without most of either."""

    past = [beach.get(t - timedelta(hours=h)) for h in range(24)]
    later = [beach.get(t + timedelta(hours=h)) for h in range(1, ahead_h + 1)]
    past, later = [x for x in past if x is not None], [x for x in later if x is not None]
    if len(past) < 18 or len(later) < 0.75 * ahead_h:
        return None
    return max(later) >= (1 + share) * max(past)


def long_period_ahead(heights=None, spectra=None) -> list[dict]:
    """Each band and signal: firings, and how often each outcome followed
    them and any hour."""

    from .briefing import CHANGE_SHARE, band_energy
    from .transform import load_spectra

    heights = load_heights() if heights is None else heights
    if spectra is None:
        spectra = load_spectra(ROOT / "data" / "spectra" / "46232")
    beach = {t: max(v) for t, v in heights.items()}
    arc = long_arc()
    floor = (LONG_FLOOR_M / 4.0) ** 2

    outcomes = {"rise": (_beach_rises, 24), "bigger": (_bigger_day, 36)}

    def score(name, moments):
        f, ahead = outcomes[name]
        got = [f(beach, t, ahead, CHANGE_SHARE) for t in moments]
        got = [x for x in got if x is not None]
        return sum(got), len(got)

    base = {name: score(name, sorted(beach)) for name in outcomes}
    out = []
    for long_s in LONG_S:
        energy = {sp.time: band_energy(sp, [0.0, 1.0 / long_s], arc) for sp in spectra}
        mean3 = {}
        for t in energy:
            vals = [energy.get(t - timedelta(hours=h)) for h in range(3)]
            vals = [v for v in vals if v is not None]
            mean3[t] = sum(vals) / len(vals) if len(vals) >= 2 else None
        for signal, series in (("hourly", energy), ("3-hour mean", mean3)):
            fired, last = [], None
            for t in sorted(series):
                now, was = series[t], series.get(t - timedelta(hours=3))
                if now is None or was is None or now < floor or now < LONG_RATIO * max(was, 1e-12):
                    continue
                if last is None or t - last > timedelta(hours=12):
                    fired.append(t)
                last = t
            row = {"long_s": long_s, "signal": signal, "fired": len(fired)}
            for name in outcomes:
                row[name], row[f"{name}_any"] = score(name, fired), base[name]
            out.append(row)
    return out


def report() -> str:
    from . import briefing

    heights = load_heights()
    times = sorted(heights)
    lines = ["# Briefing thresholds", "",
             "Generated by `python -m forecast.briefingreport --write`; the rule and the tests are in "
             f"the module's docstring. A slot is said only where it is right ≥ {RIGHT:.0%} of the "
             "times it fires.", "",
             f"Heights: {len(heights)} hours with a breaking height at all three breaks, "
             f"{times[0]:%Y-%m-%d} to {times[-1]:%Y-%m-%d} (`data/series/46232/`).", "",
             "## Rose / dropped since sunset", "",
             "| change ≥ | " + " | ".join(f"{b.replace('coronado_', '')} {s} h" for b in BREAKS for s in SPANS_H) + " |",
             "|---|" + "---|" * (len(BREAKS) * len(SPANS_H))]
    for share in CHANGE_STEPS:
        cells = []
        for k in range(len(BREAKS)):
            for s in SPANS_H:
                n, p = change_precision(heights, k, s, share)
                cells.append(f"{p:.0%} ({n})")
        lines.append(f"| {share:.0%} | " + " | ".join(cells) + " |")
    chosen = smallest(CHANGE_STEPS, lambda case, step: change_precision(heights, case[0], case[1], step),
                      every=[(k, s) for k in range(len(BREAKS)) for s in SPANS_H])
    lines += ["", f"Smallest step right on every break and span: **{chosen:.0%}**; "
              f"`briefing.CHANGE_SHARE` is {briefing.CHANGE_SHARE:.0%}. Below it the briefing says "
              "\"little change\".", "",
              "## Which break leads", "", "| margin ≥ | fires | right |", "|---|---|---|"]
    for m in MARGIN_STEPS:
        n, p = leader_precision(heights, m)
        lines.append(f"| {m:.0%} | {n} | {p:.1%} |")
    lowest = smallest(MARGIN_STEPS, lambda case, step: leader_precision(heights, step), every=[0])
    lines += ["", f"Smallest margin right ≥ {RIGHT:.0%}: {lowest:.0%}. `briefing.LEAD_MARGIN` is "
              f"{briefing.LEAD_MARGIN:.0%}, one step stricter, so the two heights it names differ on "
              "screen at the 0.1 ft the page shows them in (3% of 2 ft is 0.06 ft). Below it no break "
              "is named as leading.", "",
              "## A ridge's period ahead", "", "| ahead | ridges still read | within 1 s | median error |",
              "|---|---|---|---|"]
    errors = period_projection()
    for h, errs in errors.items():
        within = sum(abs(e) <= 1.0 for e in errs) / len(errs) if errs else float("nan")
        med = statistics.median(abs(e) for e in errs) if errs else float("nan")
        lines.append(f"| {h} h | {len(errs)} | {within:.0%} | {med:.2f} s |")
    lines += ["", f"`briefing.PERIOD_AHEAD_H` is {briefing.PERIOD_AHEAD_H} h, in whole seconds. Thin "
              "(one late-summer season) and biased toward ridges that last, since an ended ridge "
              "has no reading to score against.", "",
              "## The wind's onshore habit", "", "| break | within 1.5 h of the 14-day median |", "|---|---|"]
    for bid, (hits, n) in wind_habit().items():
        lines.append(f"| {bid.replace('coronado_', '')} | {hits} of {n} |")
    lines += ["", "**Fails the rule, so the briefing does not carry it**: a trailing habit read beside "
              "this morning's wind is a forecast, and this one is right well under half the time. "
              "Re-measure in winter.", "",
              "## Long-period energy ahead", "",
              f"46232's energy at the period or longer from {'–'.join(f'{a:.0f}' for a in long_arc())}° "
              f"(the breaks' windows), doubling on 3 h before and at least {LONG_FLOOR_M} m as a height.", "",
              "| period ≥ | signal | fired | beach +15% within 24 h | any hour | bigger day within 36 h | any hour |",
              "|---|---|---|---|---|---|---|"]
    rows = long_period_ahead()
    pct = lambda hit_n: f"{hit_n[0]} of {hit_n[1]} ({hit_n[0] / hit_n[1]:.0%})" if hit_n[1] else "none"
    for r in rows:
        lines.append(f"| {r['long_s']:.0f} s | {r['signal']} | {r['fired']} | {pct(r['rise'])} | "
                     f"{pct(r['rise_any'])} | {pct(r['bigger'])} | {pct(r['bigger_any'])} |")
    lines += ["", "**Fails the rule, so the briefing does not carry it**: no row comes near "
              f"{RIGHT:.0%}. After a firing the beach rises 15% within a day LESS often than after "
              "any hour, and a bigger day follows at most one firing in five. Most firings are one "
              "noisy hour; the 3-hour mean removes those and still gives no lead. First measured "
              "2026-10-27 on one autumn with no winter groundswell: re-measure in winter.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    text = report()
    if args.write:
        DOC.write_text(text, encoding="utf-8")
        print(f"wrote {DOC}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
