"""Bottom friction before and after BRIEFING §57, archive-wide.

    python -m forecast.frictionshift                 # print the report
    python -m forecast.frictionshift --write         # ... and docs/friction_shift.md

**Reports and never edits.** §57 replaced the table's fixed-share JONSWAP
friction with Madsen's, which grows with the sea's height. This runs the
shipped chain twice on every archived 46232 spectrum that has a measured tide
within 30 minutes — `nearshore.carry(friction="jonswap")`, the chain before,
and `nearshore.carry(tide_m=...)`, the chain now — and takes each into the
surf zone (`surfzone.break_on`) at that tide, at its own peak period and 5 m
heading, as `nearshore.summarise` does. No local chop in either: it is the
same in both and a few centimetres on these hours (§36).

Two tables:

- the breaking height after over before, per break, by 46232's Hs and by
  its swell's direction (`mopcheck.mean_from`, `mopcheck.SECTORS`, as §56a
  reads MOP);
- how many hours `surfzone` still flags `outside_start` (the sea already
  breaking where the profile starts, `surfzone.START_GAIN`) after Madsen,
  per break and buoy-size band, beside the count before. The next session
  replaces that ceiling with a real break point.

Physics on surveyed inputs, observed by nothing: a change in a model's
output, not an accuracy figure. Pure Python.
"""

from __future__ import annotations

import argparse
import bisect
import math
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "friction_shift.md"
HS_BANDS = ((0.0, 1.0), (1.0, 1.5), (1.5, 2.0), (2.0, 2.5), (2.5, 99.0))
MATCH = timedelta(minutes=30)


def _band(v: float, bands) -> int | None:
    for n, (lo, hi) in enumerate(bands):
        if lo <= v < hi:
            return n
    return None


def _q(v: list[float], p: float) -> float:
    v = sorted(v)
    return v[min(len(v) - 1, int(round(p * (len(v) - 1))))]


def run(data_dir: Path = ROOT / "data", limit: int | None = None) -> list[dict]:
    """Every archived hour with a measured tide: per break, (before, after)
    breaking Hs and outside_start flags, and the 5 m heights."""

    from .geometry import load
    from .mopcheck import mean_from
    from .nearshore import BREAKS, carry, density_grids, load_tables
    from .surfzone import break_on, load_profiles
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
        row = {"time": sp.time, "buoy": 4.0 * math.sqrt(m0), "from": mean_from(sp), "tide": tide}
        sp = sp.with_spread("mem")
        grids = density_grids(sp)
        for b in BREAKS:
            table, normal = tables[b], spots[b].normal
            cells = {}
            for name, near in (("before", carry(sp, table, grids, friction="jonswap")),
                               ("after", carry(sp, table, grids, tide_m=tide))):
                angle = (((near.near_from_deg - normal + 180.0) % 360.0) - 180.0
                         if near.near_from_deg == near.near_from_deg else 0.0)
                got = break_on(profiles[b], hs_start_m=near.hs_ref, period_s=near.peak_period_s,
                               start_depth_m=table.start_depth_m, angle_deg=angle, tide_m=tide)
                cells[name] = (near.hs_ref, got.hs_m if got else float("nan"),
                               bool(got and got.outside_start))
            row[b] = cells
        out.append(row)
        if limit and len(out) >= limit:
            break
    return out


def report(rows: list[dict]) -> str:
    from .mopcheck import SECTORS
    from .nearshore import BREAKS

    sectors = tuple((n, lo, hi) for n, lo, hi in SECTORS if n != "NW")
    first, last = rows[0]["time"], rows[-1]["time"]
    lines = [
        "# Bottom friction before and after BRIEFING §57",
        "",
        "Written by `python -m forecast.frictionshift --write`. Reports, never edits.",
        f"{len(rows)} archived 46232 hours with a measured tide within 30 min, "
        f"{first:%Y-%m-%d} to {last:%Y-%m-%d}. Before: the table's JONSWAP friction "
        "(`carry(friction=\"jonswap\")`); after: Madsen's at the measured tide (what ships). "
        "Both into the surf zone at that tide; no local chop in either. A model's change, "
        "not an accuracy figure: nothing observed these heights.",
        "",
        "## Breaking height, after ÷ before",
        "",
        "Median [10th, 90th] and hours, by 46232's Hs (rows) and its swell's direction "
        "(energy-weighted mean of ≥ 8 s, `mopcheck.mean_from`).",
    ]
    for b in BREAKS:
        lines += ["", f"### {b}", "",
                  "| 46232 Hs | " + " | ".join(f"{n} {lo}–{hi}°" for n, lo, hi in sectors) + " | all |",
                  "|---|" + "---|" * (len(sectors) + 1)]
        for lo, hi in HS_BANDS:
            cells = []
            for sel in [(slo, shi) for _, slo, shi in sectors] + [(0, 360)]:
                v = [r[b]["after"][1] / r[b]["before"][1] for r in rows
                     if lo <= r["buoy"] < hi and sel[0] <= r["from"] < sel[1]
                     and r[b]["before"][1] > 0 and r[b]["after"][1] == r[b]["after"][1]]
                cells.append(f"{_q(v, .5):.2f} [{_q(v, .1):.2f}, {_q(v, .9):.2f}] n={len(v)}" if v else "–")
            label = f"{lo:.1f}–{hi:.1f} m" if hi < 99 else f"≥ {lo:.1f} m"
            lines.append(f"| {label} | " + " | ".join(cells) + " |")
        med = lambda k: _q([r[b][k][1] for r in rows if r[b][k][1] == r[b][k][1]], .5)
        lines += ["", f"Median breaking Hs over every hour: before {med('before'):.2f} m, "
                      f"after {med('after'):.2f} m."]
    lines += ["", "## Hours still flagged `outside_start` after Madsen", "",
              "The sea already breaking where the surf-zone profile starts "
              "(`surfzone.START_GAIN`): the headline there is a ceiling, not a break point. "
              "After (before), of the hours in the band.", "",
              "| 46232 Hs | " + " | ".join(BREAKS) + " |", "|---|" + "---|" * len(BREAKS)]
    for lo, hi in HS_BANDS:
        sel = [r for r in rows if lo <= r["buoy"] < hi]
        label = f"{lo:.1f}–{hi:.1f} m" if hi < 99 else f"≥ {lo:.1f} m"
        cells = []
        for b in BREAKS:
            after = sum(1 for r in sel if r[b]["after"][2])
            before = sum(1 for r in sel if r[b]["before"][2])
            cells.append(f"{after} ({before}) of {len(sel)}")
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
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
