"""The wrap round Point Loma on big westerly hours: its share, its rays, and
whether it survives a smoothed input and a finer comb (handoff item 27b).

    python -m forecast.wrapbudget                 # print the report
    python -m forecast.wrapbudget --write         # ... and docs/wrap_budget.md

**Reports and never edits.** Item 27a (`forecast.westerlygap`, BRIEFING §59)
found the shipped headline still about twice the straight-line window at
Center and South on big westerly hours, local chop adding nothing, and the
headline jumping by up to a third from one hour to the next with 46232
steady. This takes the same hours (46232 >= 2 m, swell from 270-295°, plus
17 Nov) and asks three things of the chain as it ships (Madsen at the
measured tide, surf zone from `SURF_START_M`, no chop):

1. **Budget.** Each ray's energy is put to the part of the window its
   offshore heading sits in, seen in a straight line from the break: inside
   the straight-line window (``direct``), west of it behind Point Loma
   (``wrap``), between the window's arcs behind the Coronado Islands
   (``islands``), east of it along Baja (``baja``), and a ray the land stops
   that carries only diffracted energy (``fill``). The headline is then
   broken again without the wrap, as an indication of its weight (period and
   heading held; breaking is not linear).
2. **Concentration.** The share of the 5 m energy in the top 1, 3 and 10
   rays (a ray is one table row at one buoy frequency bin).
3. **Robustness**, the falsification test: if the wrap's size is a ray comb
   focusing on a spiky MEM density, smoothing the input density in direction
   (Gaussian, sigma 5° and 10°) and tracing a finer comb (0.25° and 0.125°
   start headings, `raytrace.table(dir_step=)`) should each lower the
   headline and its hour-to-hour jumps. The finer tables carry no Madsen
   table: the comparison is fine / coarse with the rows' own JONSWAP
   friction, the shipped Madsen 5 m height scaled by it, then broken.

Physics on surveyed inputs, observed by nothing: a model's anatomy, never a
score. The finer tables are cached in `data/live/wrapbudget/` (gitignored);
~15 min cold, ~5 warm.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

from .frictionshift import MATCH, _q

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "wrap_budget.md"
CACHE = ROOT / "data" / "live" / "wrapbudget"
PARTS = ("direct", "wrap", "islands", "baja", "fill")
SIGMAS = (5, 10)
FINE = (0.25, 0.125)
TOP = (1, 3, 10)
#: An hour-to-hour step counted as a jump: the headline moves by more than
#: this (|Δ ln|) while 46232's Hs moves by under JUMP_BUOY.
JUMP, JUMP_BUOY = 0.15, 0.05


# ---------------------------------------------------------------- geometry

def part_of(off_from: float, normal: float, arcs: list[tuple[float, float]]) -> str:
    """Which part of the straight-line view an offshore heading sits in.
    `arcs` are the swell-side windows relative to the normal, ascending."""

    rel = ((off_from - normal + 180.0) % 360.0) - 180.0
    for lo, hi in arcs:
        if lo <= rel <= hi:
            return "direct"
    if rel > arcs[-1][1]:
        return "wrap"
    if rel < arcs[0][0]:
        return "baja"
    return "islands"


def arcs_for(spot, blockers) -> list[tuple[float, float]]:
    from .geometry import swell_windows

    rel = lambda b: ((b - spot.normal + 180.0) % 360.0) - 180.0
    return sorted((rel(w.low.bearing), rel(w.high.bearing)) for w in swell_windows(spot, blockers))


# ---------------------------------------------------------------- the finer combs

def fine_rows(break_id: str, step: float, refresh: bool = False) -> tuple[list[dict], dict]:
    from . import raytrace as rt

    csv_path, meta_path = CACHE / f"{break_id}_{step:g}.csv", CACHE / f"{break_id}_{step:g}.json"
    if csv_path.exists() and meta_path.exists() and not refresh:
        with csv_path.open(newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh)), json.loads(meta_path.read_text())
    bathy = rt.Bathymetry.load()
    spots, blockers = rt.load()
    spot = {s.id: s for s in spots}[break_id]
    rows, meta = rt.table(bathy, spot, blockers, rt.frequencies(), dir_step=step)
    CACHE.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=rt.FIELDS)
        w.writeheader()
        w.writerows(rows)
    meta_path.write_text(json.dumps(meta, indent=1))
    return [{k: str(v) for k, v in r.items()} for r in rows], meta


def table_from_rows(break_id: str, rows: list[dict], start_depth_m: float):
    """A `Table` with no Madsen table, as `Table.load` reads its CSV."""

    from .nearshore import Ray, Table, parse_fan

    by_freq, place = {}, {}
    for row in rows:
        f = float(row["freq_hz"])
        k = place[f] = place.get(f, -1) + 1
        gain, diff_gain = float(row["gain"]), float(row["diff_gain"])
        if gain <= 0.0 and diff_gain <= 0.0:
            continue
        by_freq.setdefault(f, []).append(Ray(
            float(row["near_from_deg"]), math.radians(float(row["near_width_deg"])),
            float(row["off_from_deg"]), gain, float(row["diff_off_from_deg"]), diff_gain,
            float(row.get("friction") or 1.0), float(row.get("diff_friction") or 1.0), k,
            None, parse_fan(row.get("diff_fan"))))
    return Table(break_id, start_depth_m, by_freq)


def comb_control(break_id: str) -> tuple[int, int]:
    """`raytrace.table(dir_step=0.5)` against the committed table: rows that
    differ, and the count."""

    from . import raytrace as rt

    rows, _ = fine_rows(break_id, rt.DIR_STEP_DEG)
    old = rt.committed_rows(break_id)
    return sum(1 for a, b in zip(rows, old) if a != b) + abs(len(rows) - len(old)), len(old)


# ---------------------------------------------------------------- per ray

def ray_energies(spectrum, table, grids, factors: dict | None):
    """Each carrying ray's energy at the start depth (m², per buoy bin), with
    its offshore heading and whether it is a fill, and the same before
    friction and shoaling divided out (deep-water-equivalent). Mirrors
    `nearshore.carry`'s loop; `factors` is its `ray_friction` (None: the
    rows' own JONSWAP column)."""

    from .nearshore import at, shoaling_squared

    freqs = sorted(table.by_freq)
    out = []
    for i, f in enumerate(spectrum.frequencies):
        grid = grids.get(i)
        if grid is None:
            continue
        near = min(freqs, key=lambda t: abs(t - f))
        if abs(near - f) > 0.05 * f:
            continue
        width = spectrum.bin_width(i)
        ks2 = shoaling_squared(f, table.start_depth_m)
        fac = factors[near] if factors is not None else None
        for j, ray in enumerate(table.by_freq[near]):
            if ray.diff_gain <= 0:
                continue
            keep = fac[j] if fac is not None else ray.diff_friction
            for h, w in ray.samples():
                e = at(grid, h) * w * width * ray.width_rad * ray.diff_gain
                out.append((e * keep, e / ks2, h, ray.gain <= 0))
    return out


def smoothed(grids: dict, sigma: float) -> dict:
    """Each bin's 1° directional density convolved with a Gaussian in
    direction: energy per bin unchanged."""

    k = np.arange(-4 * sigma, 4 * sigma + 1)
    w = np.exp(-0.5 * (k / sigma) ** 2)
    w /= w.sum()
    out = {}
    for i, g in grids.items():
        a = np.asarray(g)
        out[i] = list(sum(wj * np.roll(a, -int(kj)) for kj, wj in zip(k, w)))
    return out


# ---------------------------------------------------------------- the run

def run(data_dir: Path = ROOT / "data", limit: int | None = None) -> dict:
    from .geometry import load
    from .nearshore import BREAKS, carry, density_grids, load_tables
    from .surfzone import break_on, load_profiles
    from .tidesite import BAY, _read, coast_level, msl_above_mllw
    from .transform import load_spectra
    from .westerlygap import selected

    spots, blockers = load()
    spots = {s.id: s for s in spots}
    arcs = {b: arcs_for(spots[b], blockers) for b in BREAKS}
    tables, profiles = load_tables(), load_profiles()
    controls = {b: comb_control(b) for b in BREAKS}
    fine = {(b, s): table_from_rows(b, fine_rows(b, s)[0], tables[b].start_depth_m)
            for b in BREAKS for s in FINE}
    coarse_j = {b: table_from_rows(b, fine_rows(b, 0.5)[0], tables[b].start_depth_m) for b in BREAKS}

    msl = msl_above_mllw(data_dir)
    obs = _read(data_dir / "tide" / f"{BAY}_observed.csv")
    times = [t for t, _ in obs]

    def tide_at(when):
        i = bisect.bisect_left(times, when)
        near = [j for j in (i - 1, i) if 0 <= j < len(times) and abs(times[j] - when) <= MATCH]
        return obs[min(near, key=lambda j: abs(times[j] - when))][1] if near else None

    def broken(b, near, hs_start, tide):
        normal = spots[b].normal
        angle = (((near.near_from_deg - normal + 180.0) % 360.0) - 180.0
                 if near.near_from_deg == near.near_from_deg else 0.0)
        got = break_on(profiles[b], hs_start_m=hs_start, period_s=near.peak_period_s,
                       start_depth_m=tables[b].start_depth_m, angle_deg=angle, tide_m=tide)
        return got.hs_m if got else None

    hours = selected(load_spectra(data_dir / "spectra" / "46232"))
    if limit:
        hours = hours[:limit]
    rows, worst_sum = [], 0.0
    for sp, hs, frm in hours:
        level = tide_at(sp.time)
        if level is None:
            continue
        tide = coast_level(level, msl)
        sp = sp.with_spread("mem")
        grids = density_grids(sp)
        smooth = {s: smoothed(grids, s) for s in SIGMAS}
        row = {"time": sp.time, "buoy": hs, "from": frm, "tide": tide}
        for b in BREAKS:
            near = carry(sp, tables[b], grids, tide_m=tide)
            if not (near.hs_ref > 0 and near.peak_period_s == near.peak_period_s):
                continue
            rays = ray_energies(sp, tables[b], grids, near.ray_friction)
            e5 = sum(r[0] for r in rays)
            worst_sum = max(worst_sum, abs(4.0 * math.sqrt(e5) / near.hs_ref - 1.0))
            parts5 = dict.fromkeys(PARTS, 0.0)
            parts0 = dict.fromkeys(PARTS, 0.0)
            for e, e0, off, fill in rays:
                p = "fill" if fill else part_of(off, spots[b].normal, arcs[b])
                parts5[p] += e
                parts0[p] += e0
            top = sorted((r[0] for r in rays), reverse=True)
            cum, half = 0.0, 0
            for e in top:
                cum += e
                half += 1
                if cum >= 0.5 * e5:
                    break
            head = broken(b, near, near.hs_ref, tide)
            no_wrap = broken(b, near, 4.0 * math.sqrt(max(e5 - parts5["wrap"], 0.0)), tide)
            out = {"hs5": near.hs_ref, "head": head, "no_wrap": no_wrap,
                   "parts5": {k: v / e5 for k, v in parts5.items()},
                   "parts0": parts0, "e0": sum(parts0.values()),
                   "top": {n: sum(top[:n]) / e5 for n in TOP}, "half": half, "rays": len(top)}
            # The smoothed input, through the shipped chain.
            for s in SIGMAS:
                ns = carry(sp, tables[b], smooth[s], tide_m=tide)
                out[f"s{s}"] = (ns.hs_ref, broken(b, ns, ns.hs_ref, tide))
            # The finer combs: fine / coarse with the rows' JONSWAP friction.
            cj = carry(sp, coarse_j[b], grids, friction="jonswap")
            out["coarse_j"] = (cj.hs_equivalent, cj.hs_ref)
            for s in FINE:
                fj = carry(sp, fine[(b, s)], grids, friction="jonswap")
                scale = fj.hs_ref / cj.hs_ref if cj.hs_ref > 0 else float("nan")
                fr = ray_energies(sp, fine[(b, s)], grids, None)
                fe = sum(r[0] for r in fr)
                ftop = sorted((r[0] for r in fr), reverse=True)
                wrap = sum(r[0] for r in fr if not r[3]
                           and part_of(r[2], spots[b].normal, arcs[b]) == "wrap")
                out[f"f{s}"] = {"eq": fj.hs_equivalent / cj.hs_equivalent, "j": scale,
                                "head": broken(b, near, near.hs_ref * scale, tide),
                                "top": {n: sum(ftop[:n]) / fe for n in TOP} if fe > 0 else None,
                                "wrap": wrap / fe if fe > 0 else None}
            row[b] = out
        rows.append(row)
    return {"rows": rows, "controls": controls, "worst_sum": worst_sum, "arcs": arcs}


# ---------------------------------------------------------------- the report

def _qs(v: list[float], n: int = 2) -> str:
    v = [x for x in v if x is not None and x == x]
    return f"{_q(v, .5):.{n}f} [{_q(v, .1):.{n}f}, {_q(v, .9):.{n}f}]" if v else "–"


def _jumps(rows, b, key) -> list[tuple]:
    """Consecutive hours (one hour apart): (time, |Δ ln buoy|, |Δ ln headline|)."""

    out = []
    for a, c in zip(rows, rows[1:]):
        if (c["time"] - a["time"]).total_seconds() != 3600 or b not in a or b not in c:
            continue
        ha, hc = key(a[b]), key(c[b])
        if not (ha and hc):
            continue
        out.append((c["time"], abs(math.log(c["buoy"] / a["buoy"])), abs(math.log(hc / ha))))
    return out


def report(res: dict) -> str:
    from .nearshore import BREAKS

    rows = res["rows"]
    short = {b: b.split("_")[1].capitalize() for b in BREAKS}
    big = [r for r in rows if r["buoy"] >= 2.0 and 270.0 <= r["from"] < 295.0]
    lines = [
        "# The wrap round Point Loma on big westerly hours: budget, rays, robustness",
        "",
        "Written by `python -m forecast.wrapbudget --write` (handoff item 27b). Reports, never "
        "edits. The chain as it ships (MEM, Madsen at the measured tide, surf zone from "
        "`SURF_START_M`), no local chop (27a: it adds nothing on these hours). "
        f"{len(big)} hours with 46232 ≥ 2 m and swell (≥ 8 s) from 270–295°, plus 17 Nov "
        f"({len(rows)} in all, with a measured tide). **Nothing here is observed**: a model's "
        "anatomy, never a score.",
        "",
        "## Controls",
        "",
        "- `raytrace.table(dir_step=0.5)` against the committed tables: "
        + "; ".join(f"{short[b]} {bad} of {n} rows differ" for b, (bad, n) in res["controls"].items())
        + ".",
        f"- The per-ray sum against `carry`'s 5 m height: worst |Δ| {100 * res['worst_sum']:.4f}%.",
        "- Straight-line windows relative to each break's normal (°): "
        + "; ".join(f"{short[b]} " + ", ".join(f"{lo:+.1f}…{hi:+.1f}" for lo, hi in a)
                    for b, a in res["arcs"].items())
        + ". West of the last arc is `wrap`.",
    ]

    lines += ["", "## 1. Budget", "",
              "Share of the 5 m energy (after Madsen) by where each ray's offshore heading sits "
              "in the straight-line view from the break; median [10th, 90th]. **headline without "
              "the wrap** breaks the 5 m sea with the wrap's energy taken out, period and heading "
              "held: an indication of its weight, not a decomposition (breaking is not linear).", "",
              "| break | hours | direct | wrap | islands | baja | fill | headline, m | without the wrap ÷ headline |",
              "|---|---|---|---|---|---|---|---|---|"]
    for b in BREAKS:
        sel = [r[b] for r in big if b in r and r[b]["head"]]
        if not sel:
            continue
        cells = [_qs([c["parts5"][p] for c in sel]) for p in PARTS]
        nw = [c["no_wrap"] / c["head"] for c in sel if c["no_wrap"]]
        lines.append(f"| {short[b]} | {len(sel)} | " + " | ".join(cells)
                     + f" | {_qs([c['head'] for c in sel])} | {_qs(nw)} |")

    lines += ["", "## 2. Concentration", "",
              "Share of the 5 m energy in the top 1, 3 and 10 rays, and how many rays carry half of "
              "it, at the shipped 0.5° comb and the finest; median [10th, 90th].", "",
              "| break | top 1 | top 3 | top 10 | rays for half (of all carrying) | top 3 at 0.125° | wrap share at 0.125° |",
              "|---|---|---|---|---|---|---|"]
    for b in BREAKS:
        sel = [r[b] for r in big if b in r and r[b]["head"]]
        if not sel:
            continue
        f = sel[0].get(f"f{FINE[-1]}") and [c[f"f{FINE[-1]}"] for c in sel]
        lines.append(f"| {short[b]} | {_qs([c['top'][1] for c in sel])} | {_qs([c['top'][3] for c in sel])} "
                     f"| {_qs([c['top'][10] for c in sel])} | {_q([c['half'] for c in sel], .5)} "
                     f"({_q([c['rays'] for c in sel], .5)}) | {_qs([x['top'][3] for x in f if x['top']])} "
                     f"| {_qs([x['wrap'] for x in f])} |")

    lines += ["", "## 3. Robustness: does the wrap survive a smoothed input and a finer comb?", "",
              "Each over the shipped chain, median [10th, 90th]. Smoothed: the MEM density "
              "convolved in direction (Gaussian σ), through the shipped chain. Finer: the 5 m "
              "height with the rows' JONSWAP friction, fine ÷ 0.5°, and the headline when the "
              "shipped Madsen 5 m height is scaled by it.", "",
              "| break | 5 m: σ 5° | σ 10° | 0.25° | 0.125° | 0.125° before friction | headline: σ 5° | σ 10° | 0.25° | 0.125° |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for b in BREAKS:
        sel = [r[b] for r in big if b in r and r[b]["head"]]
        if not sel:
            continue
        c5 = [_qs([c[f"s{s}"][0] / c["hs5"] for c in sel]) for s in SIGMAS]
        cf = [_qs([c[f"f{s}"]["j"] for c in sel]) for s in FINE]
        ce = _qs([c[f"f{FINE[-1]}"]["eq"] for c in sel])
        h5 = [_qs([c[f"s{s}"][1] / c["head"] for c in sel if c[f"s{s}"][1]]) for s in SIGMAS]
        hf = [_qs([c[f"f{s}"]["head"] / c["head"] for c in sel if c[f"f{s}"]["head"]]) for s in FINE]
        lines.append(f"| {short[b]} | " + " | ".join(c5 + cf + [ce] + h5 + hf) + " |")

    lines += ["", "### Hour-to-hour jumps", "",
              f"Consecutive hours of the selection one hour apart. A **jump**: the headline moves by "
              f"more than {100 * JUMP:.0f}% (|Δ ln|) while 46232's Hs moves under "
              f"{100 * JUMP_BUOY:.0f}%. |Δ ln headline|: median [90th]; jumps counted.", "",
              "| break | pairs | shipped | σ 5° | σ 10° | 0.25° | 0.125° | jumps: shipped / σ 5° / σ 10° / 0.25° / 0.125° | top-3 share, jump hours vs the rest |",
              "|---|---|---|---|---|---|---|---|---|"]
    keys = [("shipped", lambda c: c["head"])] + [
        (f"s{s}", lambda c, s=s: c[f"s{s}"][1]) for s in SIGMAS] + [
        (f"f{s}", lambda c, s=s: c[f"f{s}"]["head"]) for s in FINE]
    for b in BREAKS:
        stats, counts = [], []
        for _, key in keys:
            j = _jumps(rows, b, key)
            d = [x[2] for x in j]
            stats.append(f"{_q(d, .5):.3f} [{_q(d, .9):.3f}]" if d else "–")
            counts.append(str(sum(1 for x in j if x[2] > JUMP and x[1] < JUMP_BUOY)))
        j = _jumps(rows, b, keys[0][1])
        when = {x[0] for x in j if x[2] > JUMP and x[1] < JUMP_BUOY}
        by_t = {r["time"]: r[b] for r in rows if b in r}
        jt = [by_t[t]["top"][3] for t in when if t in by_t]
        rest = [by_t[x[0]]["top"][3] for x in j if x[0] not in when and x[0] in by_t]
        lines.append(f"| {short[b]} | {len(j)} | " + " | ".join(stats) + " | " + " / ".join(counts)
                     + f" | {_qs(jt)} vs {_qs(rest)} |")

    day = [r for r in rows if r["time"].strftime("%Y-%m-%d") == "2026-11-17"]
    lines += ["", "### 17 Nov, hour by hour", "",
              "Headline (m): shipped / σ 10° / 0.125°; the wrap's share of the 5 m energy; top-3 "
              "rays' share.", "",
              "| hour | 46232 | " + " | ".join(short[b] for b in BREAKS) + " |",
              "|---|---|" + "---|" * len(BREAKS)]
    for r in day:
        cells = []
        for b in BREAKS:
            c = r.get(b)
            if not c or not c["head"]:
                cells.append("–")
                continue
            f = c[f"f{FINE[-1]}"]["head"]
            cells.append(f"{c['head']:.2f} / {c['s10'][1]:.2f} / {f:.2f}; wrap "
                         f"{c['parts5']['wrap']:.2f}; top 3 {c['top'][3]:.2f}")
        lines.append(f"| {r['time']:%HZ} | {r['buoy']:.2f} m, {r['from']:.0f}° | " + " | ".join(cells) + " |")
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
