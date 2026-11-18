"""Where the surf zone starts, before and after BRIEFING §58, archive-wide.

    python -m forecast.breakshift                 # print the report
    python -m forecast.breakshift --write         # ... and docs/break_shift.md

**Reports and never edits.** Until §58 each break's surf-zone profile started
at the transfer table's start point, 5 m of water, and on big days the sea was
already breaking there: `surfzone` reported the linear 5 m figure as a ceiling
(`outside_start`). Since §58 the profiles start further out
(`raytrace.SURF_START_M`) and the same 5 m sea, carried back out linearly,
breaks on the way in. This runs the shipped chain on every archived 46232
spectrum with a measured tide within 30 minutes — `nearshore.carry` with
Madsen's friction at that tide — and takes it into the surf zone twice, at its
own peak period and 5 m heading as `nearshore.summarise` does: on the profile
from the table's start point in (`Profile.inshore`, before) and on the whole
profile (after). No local chop in either: it is the same in both and a few
centimetres on these hours (§36).

Three tables per break, by 46232's Hs:

- the breaking height and the depth it breaks in, before and after, and how
  many hours break seaward of the table's start point;
- how many hours `surfzone` flags `outside_start` (already breaking where the
  profile starts), before and after;
- on the hours NOT flagged before, the change, by how much of the sea was
  already breaking at 5 m with the old start (Battjes-Janssen's Qb there):
  none breaking, the height is unchanged; some, it is the new physics.

Physics on surveyed inputs, observed by nothing: a change in a model's output,
not an accuracy figure. Pure Python.
"""

from __future__ import annotations

import argparse
import bisect
import math
import sys
from pathlib import Path

from .frictionshift import HS_BANDS, MATCH, _q

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "break_shift.md"
#: Battjes-Janssen's share of waves breaking at the table's start point with
#: the old start: exactly none, under one in a thousand, under one in a
#: hundred, more.
QB_CLASSES = ((0.0, 0.0), (0.0, 1e-3), (1e-3, 1e-2), (1e-2, 1.0))


def run(data_dir: Path = ROOT / "data", limit: int | None = None) -> list[dict]:
    """Every archived hour with a measured tide: per break, the breaking
    height, depth, distance and flag on the old (inshore) profile and the
    new one, and Qb at the table's start point on the old."""

    from .geometry import load
    from .nearshore import BREAKS, carry, density_grids, load_tables
    from .surfzone import break_on, fraction_breaking, load_profiles
    from .tidesite import BAY, _read, coast_level, msl_above_mllw
    from .transform import load_spectra

    spots = {s.id: s for s in load()[0]}
    tables, profiles = load_tables(), load_profiles()
    msl = msl_above_mllw(data_dir)
    obs = _read(data_dir / "tide" / f"{BAY}_observed.csv")
    times = [t for t, _ in obs]

    def tide_at(when):
        i = bisect.bisect_left(times, when)
        near = [j for j in (i - 1, i) if 0 <= j < len(times) and abs(times[j] - when) <= MATCH]
        return obs[min(near, key=lambda j: abs(times[j] - when))][1] if near else None

    out = []
    for sp in load_spectra(data_dir / "spectra" / "46232"):
        level = tide_at(sp.time)
        if level is None:
            continue
        m0 = sum(c * sp.bin_width(i) for i, c in enumerate(sp.c11) if c == c and c > 0)
        if m0 <= 0:
            continue
        tide = coast_level(level, msl)
        row = {"time": sp.time, "buoy": 4.0 * math.sqrt(m0), "tide": tide}
        sp = sp.with_spread("mem")
        grids = density_grids(sp)
        for b in BREAKS:
            near = carry(sp, tables[b], grids, tide_m=tide)
            if not (near.hs_ref > 0 and near.peak_period_s == near.peak_period_s):
                continue
            normal = spots[b].normal
            angle = (((near.near_from_deg - normal + 180.0) % 360.0) - 180.0
                     if near.near_from_deg == near.near_from_deg else 0.0)
            kw = dict(hs_start_m=near.hs_ref, period_s=near.peak_period_s,
                      start_depth_m=tables[b].start_depth_m, angle_deg=angle, tide_m=tide)
            path: list = []
            before = break_on(profiles[b].inshore(), path=path, **kw)
            after = break_on(profiles[b], **kw)
            if not (before and after):
                continue
            # The share of waves breaking at the table's start point, old start.
            x0, h0, hs0 = path[0]
            qb0 = fraction_breaking(hs0 / math.sqrt(2) / (before.gamma * h0))
            row[b] = {"hs5": near.hs_ref, "qb5": qb0,
                      "before": (before.hs_m, before.depth_m, before.distance_m, before.outside_start),
                      "after": (after.hs_m, after.depth_m, after.distance_m, after.outside_start)}
        out.append(row)
        if limit and len(out) >= limit:
            break
    return out


def _label(lo: float, hi: float) -> str:
    return f"{lo:.1f}–{hi:.1f} m" if hi < 99 else f"≥ {lo:.1f} m"


def report(rows: list[dict]) -> str:
    from .nearshore import BREAKS
    from .raytrace import SURF_START_M

    first, last = rows[0]["time"], rows[-1]["time"]
    lines = [
        "# Where the surf zone starts, before and after BRIEFING §58",
        "",
        "Written by `python -m forecast.breakshift --write`. Reports, never edits.",
        f"{len(rows)} archived 46232 hours with a measured tide within 30 min, "
        f"{first:%Y-%m-%d} to {last:%Y-%m-%d}; the shipped chain (Madsen's friction at the "
        "measured tide) into the surf zone at that tide, no local chop. Before: the profile "
        "from the table's start point (5 m) in. After: the profile from "
        + ", ".join(f"{SURF_START_M[b]:g} m ({b.split('_')[1]})" for b in BREAKS)
        + ". A model's change, not an accuracy figure: nothing observed these heights.",
    ]
    for b in BREAKS:
        sel = [r for r in rows if b in r]
        lines += ["", f"## {b}", "",
                  "| 46232 Hs | hours | breaking Hs, median: before → after | after ÷ before: "
                  "median [10th] min | break depth, median: before → after [90th] max | "
                  "break seaward of 5 m | flagged: before → after |",
                  "|---|---|---|---|---|---|---|"]
        for lo, hi in HS_BANDS:
            band = [r[b] for r in sel if lo <= r["buoy"] < hi]
            if not band:
                continue
            hb, ha = [c["before"][0] for c in band], [c["after"][0] for c in band]
            ratio = [a / x for a, x in zip(ha, hb)]
            db, da = [c["before"][1] for c in band], [c["after"][1] for c in band]
            seaward = sum(1 for c in band if c["after"][2] < 0.0)
            fb = sum(1 for c in band if c["before"][3])
            fa = sum(1 for c in band if c["after"][3])
            lines.append(
                f"| {_label(lo, hi)} | {len(band)} | {_q(hb, .5):.2f} → {_q(ha, .5):.2f} m "
                f"| {_q(ratio, .5):.3f} [{_q(ratio, .1):.3f}] {min(ratio):.3f} "
                f"| {_q(db, .5):.2f} → {_q(da, .5):.2f} m [{_q(da, .9):.2f}] {max(da):.2f} m "
                f"| {seaward} | {fb} → {fa} |")
        lines += ["", "Hours not flagged before, by the share of waves already breaking at the "
                      "table's start point with the old start (Qb): the breaking height after ÷ "
                      "before − 1.", "",
                  "| Qb at 5 m, old start | hours | worst | 99th percentile of the size |",
                  "|---|---|---|---|"]
        for lo, hi in QB_CLASSES:
            got = [c["after"][0] / c["before"][0] - 1 for r in sel for c in [r[b]]
                   if not c["before"][3] and ((c["qb5"] == 0.0) if hi == 0.0 else (lo <= c["qb5"] < hi and c["qb5"] > 0.0))]
            label = "none" if hi == 0.0 else f"{lo:g} – {hi:g}"
            if got:
                worst = max(got, key=abs)
                worst = 0.0 if abs(worst) < 5e-6 else worst     # an ulp is not a change
                lines.append(f"| {label} | {len(got)} | {100 * worst:+.3f}% "
                             f"| {100 * _q([abs(g) for g in got], .99):.3f}% |")
            else:
                lines.append(f"| {label} | 0 | – | – |")
        still = [r for r in sel if r[b]["after"][3]]
        lines += ["", f"Flagged after: {len(still)} of {len(sel)} hours."
                  + ("" if not still else " " + "; ".join(
                      f"{r['time']:%Y-%m-%d %HZ} (46232 {r['buoy']:.2f} m, 5 m Hs "
                      f"{r[b]['hs5']:.2f} m)" for r in still[:20]))]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true", help=f"also write {OUT.relative_to(ROOT)}")
    ap.add_argument("--limit", type=int, default=None, help="only the first n hours (a quick look)")
    args = ap.parse_args(argv)
    text = report(run(limit=args.limit))
    print(text)
    if args.write:
        OUT.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
