"""A headland's diffracted fill read across the Fresnel zone, before and after.

    python -m forecast.fillshift                 # print the report
    python -m forecast.fillshift --write         # ... and docs/fill_shift.md

**Reports and never edits.** Until 2026-11-21 a ray that runs into Point
Loma's or Baja's shadow carried diffracted energy read at ONE offshore
heading: the nearest clear ray's. Rays grazing Point Loma leave the shelf
anywhere from 250° to 350° half a degree apart, so that heading wandered from
frequency to frequency and the hour-to-hour headline with it (BRIEFING §60).
Since then (`raytrace.FILL_RULE = "fan"`, `raytrace.edge_fan`) the fill reads
the sea across every clear ray that passes the edge inside its Fresnel zone,
0 < u <= EDGE_U_MAX, weighted uniformly in u.

"Before" is the shipped table with each fan row read the old way
(`nearest_rule`): exact from the table alone, since the old heading is the
nearest clear row's own `off_from_deg`. Checked once against the tables as
committed before the change (BRIEFING §61): every row identical.

Every archived 46232 hour with a measured tide within 30 minutes, the shipped
chain (MEM, Madsen at that tide, surf zone from `SURF_START_M`), no chop
(§59: nothing on big days). Physics on surveyed inputs, observed by nothing:
a model's change, never an accuracy figure.
"""

from __future__ import annotations

import argparse
import bisect
import math
import sys
from pathlib import Path

from .frictionshift import HS_BANDS, MATCH, _q

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "fill_shift.md"
SECTORS = (("S", 150, 205), ("SSW–SW", 205, 235), ("WSW–W", 235, 270), ("W–WNW", 270, 295),
           ("NW", 295, 330))


def nearest_rule(table):
    """The same table with every headland fill read the old way: at the
    offshore heading of the clear ray nearest it in start heading, as
    `raytrace.table(fill="nearest")` writes it. Exact from the shipped table
    alone: that heading is the clear row's own `off_from_deg`, at the same
    rounding, and the start headings are in every row."""

    from dataclasses import replace

    from .nearshore import Table

    by_freq = {}
    for f, rays in table.by_freq.items():
        clear = [r for r in rays if r.gain > 0]
        out = []
        for r in rays:
            if r.fan and clear:
                # Rounded, so an exact tie goes to the first, as numpy's argmin did.
                c = min(clear, key=lambda c: round(abs(((c.near_from - r.near_from + 180.0)
                                                         % 360.0) - 180.0), 6))
                r = replace(r, diff_off_from=c.off_from, fan=None)
            out.append(r)
        by_freq[f] = out
    return Table(table.break_id, table.start_depth_m, by_freq, table.fetch, table.madsen)


def run(data_dir: Path = ROOT / "data", limit: int | None = None) -> dict:
    from .geometry import load
    from .mopcheck import mean_from
    from .nearshore import BREAKS, carry, density_grids, load_tables
    from .surfzone import break_on, load_profiles
    from .tidesite import BAY, _read, coast_level, msl_above_mllw
    from .transform import load_spectra

    spots = {s.id: s for s in load()[0]}
    after_t, profiles = load_tables(), load_profiles()
    before_t = {b: nearest_rule(t) for b, t in after_t.items()}
    msl = msl_above_mllw(data_dir)
    obs = _read(data_dir / "tide" / f"{BAY}_observed.csv")
    times = [t for t, _ in obs]

    def tide_at(when):
        i = bisect.bisect_left(times, when)
        near = [j for j in (i - 1, i) if 0 <= j < len(times) and abs(times[j] - when) <= MATCH]
        return obs[min(near, key=lambda j: abs(times[j] - when))][1] if near else None

    def broken(b, near, tide):
        normal = spots[b].normal
        angle = (((near.near_from_deg - normal + 180.0) % 360.0) - 180.0
                 if near.near_from_deg == near.near_from_deg else 0.0)
        got = break_on(profiles[b], hs_start_m=near.hs_ref, period_s=near.peak_period_s,
                       start_depth_m=after_t[b].start_depth_m, angle_deg=angle, tide_m=tide)
        return got.hs_m if got else None

    rows = []
    for sp in load_spectra(data_dir / "spectra" / "46232"):
        level = tide_at(sp.time)
        if level is None:
            continue
        m0 = sum(c * sp.bin_width(i) for i, c in enumerate(sp.c11) if c == c and c > 0)
        if m0 <= 0:
            continue
        tide = coast_level(level, msl)
        frm = mean_from(sp)
        sp = sp.with_spread("mem")
        grids = density_grids(sp)
        row = {"time": sp.time, "buoy": 4.0 * math.sqrt(m0), "from": frm}
        for b in BREAKS:
            nb = carry(sp, before_t[b], grids, tide_m=tide)
            na = carry(sp, after_t[b], grids, tide_m=tide)
            if not (nb.hs_ref > 0 and na.hs_ref > 0 and na.peak_period_s == na.peak_period_s
                    and nb.peak_period_s == nb.peak_period_s):
                continue
            hb, ha = broken(b, nb, tide), broken(b, na, tide)
            if hb and ha:
                row[b] = {"h5": (nb.hs_ref, na.hs_ref), "head": (hb, ha)}
        rows.append(row)
        if limit and len(rows) >= limit:
            break
    return {"rows": rows}


def _jumps(rows, b, which: int):
    out = []
    for a, c in zip(rows, rows[1:]):
        if (c["time"] - a["time"]).total_seconds() != 3600 or b not in a or b not in c:
            continue
        out.append((abs(math.log(c["buoy"] / a["buoy"])),
                    abs(math.log(c[b]["head"][which] / a[b]["head"][which]))))
    return out


def report(res: dict) -> str:
    from .nearshore import BREAKS

    rows = res["rows"]
    short = {b: b.split("_")[1].capitalize() for b in BREAKS}
    q = lambda v: f"{_q(v, .5):.3f} [{_q(v, .1):.3f}, {_q(v, .9):.3f}]" if v else "–"
    lines = [
        "# A headland's diffracted fill read across the Fresnel zone: before and after",
        "",
        "Written by `python -m forecast.fillshift --write`. Reports, never edits. "
        f"{len(rows)} archived 46232 hours with a measured tide within 30 min, "
        f"{rows[0]['time']:%Y-%m-%d} to {rows[-1]['time']:%Y-%m-%d}; the shipped chain, no local "
        "chop. Before: each headland fill read at its nearest clear ray's offshore heading. After: "
        "across the clear rays inside the edge's Fresnel zone (`raytrace.edge_fan`). A model's "
        "change, not an accuracy figure: nothing observed these heights.",
    ]
    for b in BREAKS:
        sel = [r for r in rows if b in r]
        lines += ["", f"## {short[b]}", "",
                  "Breaking height after ÷ before by 46232's swell sector (rows) and Hs (columns), "
                  "median [10th, 90th], hours in brackets.", "",
                  "| sector | " + " | ".join(
                      (f"{lo:.1f}–{hi:.1f} m" if hi < 99 else f"≥ {lo:.1f} m") for lo, hi in HS_BANDS)
                  + " | all | worst |",
                  "|---|" + "---|" * (len(HS_BANDS) + 2)]
        for name, lo_d, hi_d in SECTORS + (("all", 0, 360),):
            cells, allv = [], []
            for lo, hi in HS_BANDS:
                v = [r[b]["head"][1] / r[b]["head"][0] for r in sel
                     if lo <= r["buoy"] < hi and lo_d <= r["from"] < hi_d]
                allv += v
                cells.append(f"{q(v)} ({len(v)})" if v else "–")
            worst = max(allv, key=lambda x: abs(x - 1)) if allv else float("nan")
            lines.append(f"| {name} | " + " | ".join(cells) + f" | {q(allv)} ({len(allv)}) | {worst:.3f} |")
        big = [r for r in sel if r["buoy"] >= 2.0 and 270 <= r["from"] < 295]
        jb, ja = _jumps(big, b, 0), _jumps(big, b, 1)
        cnt = lambda j: sum(1 for db, dh in j if dh > 0.15 and db < 0.05)
        lines += ["", f"Big westerly hours (46232 ≥ 2 m from 270–295°, {len(big)} hours, "
                      f"{len(jb)} consecutive pairs): |Δ ln headline| median [90th] before "
                      f"{_q([d for _, d in jb], .5):.3f} [{_q([d for _, d in jb], .9):.3f}] → after "
                      f"{_q([d for _, d in ja], .5):.3f} [{_q([d for _, d in ja], .9):.3f}]; jumps "
                      f"(> 15% with 46232 < 5%) {cnt(jb)} → {cnt(ja)}." if jb else ""]
    day = [r for r in rows if r["time"].strftime("%Y-%m-%d") == "2026-11-17"]
    lines += ["", "## 17 Nov, hour by hour", "", "Breaking height (m), before → after.", "",
              "| hour | 46232 | " + " | ".join(short[b] for b in BREAKS) + " |",
              "|---|---|" + "---|" * len(BREAKS)]
    for r in day:
        lines.append(f"| {r['time']:%HZ} | {r['buoy']:.2f} m, {r['from']:.0f}° | " + " | ".join(
            f"{r[b]['head'][0]:.2f} → {r[b]['head'][1]:.2f}" if b in r else "–" for b in BREAKS) + " |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true", help=f"also write {OUT.relative_to(ROOT)}")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args(argv)
    text = report(run(limit=args.limit))
    print(text)
    if args.write:
        OUT.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
