"""Do the wrap's rays cross Point Loma's charted kelp, and what could it take?

    python -m forecast.kelpcross                # print the report
    python -m forecast.kelpcross --write        # ... and docs/kelp_cross.md

**Reports and never edits** (handoff item 27d). BRIEFING §60: on big westerly
hours the wrap round Point Loma carries 70% of Center's and South's 5 m
energy. Point Loma's kelp forest lies across part of the water south and west
of the tip. This measures, on the same hours, how much of each break's 5 m
energy travels along a path through the CHARTED kelp (`data/kelp/`, NOAA ENC
WEDKLP, `collector.kelp`), and for how far; then what an attenuation from the
measured literature would take off the headline if it applied along those
lengths.

- Paths: each clear ray's own traced path (`<break>_paths.json`, the map
  fill's, 0.03–0.25 Hz); a diffracted fill takes the path of the clear ray
  nearest it in start heading, as `raytrace.table` gives it its friction.
  Energy at frequencies without a stored path is reported as such.
- Kelp: the finest chart scale that carries any (harbour, approach, coastal,
  general), every ring even-odd, so a hole is a hole. A charted outline of
  its source survey's date, not this year's canopy.
- The attenuation is literature, never fitted: E kept = exp(−α·L) along a
  path's length L in kelp, for each α in `ALPHAS`, then broken as shipped.

Physics on charted inputs, observed by nothing. Pure Python.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "kelp_cross.md"
KELP_CSV = ROOT / "data" / "kelp" / "enc_wedklp.csv"
#: Finest first.
SCALES = ("enc_harbour", "enc_approach", "enc_coastal", "enc_general")
STEP_M = 10.0
#: Energy attenuation coefficients per metre of kelp, from the literature
#: (docs/kelp_cross.md says where each comes from and what it was measured on).
ALPHAS = (("none measured at swell periods (Elwany et al. 1995; Rosman et al. 2007)", 0.0),
          ("1e-4 /m", 1e-4),
          ("1e-3 /m: Elsmore et al. 2024's order for 1–3 s waves, applied to swell", 1e-3))


# ---------------------------------------------------------------- polygons

def load_kelp(path: Path = KELP_CSV) -> tuple[str, list[list[list[tuple[float, float]]]]]:
    """(scale used, features), each feature a list of rings in UTM metres."""

    from .raytrace import to_utm

    by_scale: dict[str, dict] = {}
    with path.open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            feat = by_scale.setdefault(r["service"], {}).setdefault((r["layer_id"], r["feature"]), {})
            feat.setdefault(r["ring"], []).append((int(r["seq"]), float(r["lat"]), float(r["lon"])))
    for scale in SCALES:
        if scale in by_scale:
            feats = []
            for rings in by_scale[scale].values():
                feats.append([[to_utm(la, lo) for _, la, lo in sorted(ring)] for ring in rings.values()])
            return scale, feats
    raise ValueError(f"{path}: no feature at any of {SCALES}")


def inside(x: float, y: float, rings: list) -> bool:
    """Even-odd over every ring of one feature."""

    hit = False
    for ring in rings:
        n = len(ring)
        for i in range(n):
            (x1, y1), (x2, y2) = ring[i], ring[(i + 1) % n]
            if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                hit = not hit
    return hit


def length_in(points_xy: list[tuple[float, float]], feats: list, boxes: list) -> float:
    """Metres of the polyline inside any feature, sampled every STEP_M."""

    total = 0.0
    for (x1, y1), (x2, y2) in zip(points_xy, points_xy[1:]):
        seg = math.hypot(x2 - x1, y2 - y1)
        n = max(1, int(math.ceil(seg / STEP_M)))
        for j in range(n):
            t = (j + 0.5) / n
            x, y = x1 + t * (x2 - x1), y1 + t * (y2 - y1)
            if any(bx0 <= x <= bx1 and by0 <= y <= by1 and inside(x, y, f)
                   for f, (bx0, by0, bx1, by1) in zip(feats, boxes)):
                total += seg / n
    return total


def path_lengths(break_id: str, feats: list) -> dict[tuple[float, int], float]:
    """(table frequency, row k) -> metres in kelp, for every stored path."""

    from .nearshore import TABLE_DIR
    from .raytrace import to_utm

    boxes = []
    for f in feats:
        xs = [p[0] for ring in f for p in ring]
        ys = [p[1] for ring in f for p in ring]
        boxes.append((min(xs), min(ys), max(xs), max(ys)))
    doc = json.loads((TABLE_DIR / f"{break_id}_paths.json").read_text())
    out = {}
    for key, rays in doc["rays"].items():
        for k, _off, pts in rays:
            xy = [to_utm(la, lo) for la, lo, _t in pts]
            out[(float(key), int(k))] = length_in(xy, feats, boxes)
    return out


# ---------------------------------------------------------------- the run

def run(data_dir: Path = ROOT / "data", limit: int | None = None) -> dict:
    import bisect

    from .frictionshift import MATCH
    from .geometry import load
    from .nearshore import BREAKS, at, carry, density_grids, load_tables
    from .surfzone import break_on, load_profiles
    from .tidesite import BAY, _read, coast_level, msl_above_mllw
    from .transform import load_spectra
    from .westerlygap import selected
    from .wrapbudget import arcs_for, part_of

    scale, feats = load_kelp()
    spots, blockers = load()
    spots = {s.id: s for s in spots}
    arcs = {b: arcs_for(spots[b], blockers) for b in BREAKS}
    tables, profiles = load_tables(), load_profiles()
    lengths = {b: path_lengths(b, feats) for b in BREAKS}
    # A fill row's path: the clear row nearest it in start heading.
    path_of = {}
    for b in BREAKS:
        for f, rays in tables[b].by_freq.items():
            clear = [r.k for r in rays if r.gain > 0]
            for r in rays:
                if r.gain <= 0 and r.diff_gain > 0 and clear:
                    path_of[(b, f, r.k)] = min(clear, key=lambda c: abs(c - r.k))

    msl = msl_above_mllw(data_dir)
    obs = _read(data_dir / "tide" / f"{BAY}_observed.csv")
    times = [t for t, _ in obs]

    def tide_at(when):
        i = bisect.bisect_left(times, when)
        near = [j for j in (i - 1, i) if 0 <= j < len(times) and abs(times[j] - when) <= MATCH]
        return obs[min(near, key=lambda j: abs(times[j] - when))][1] if near else None

    hours = selected(load_spectra(data_dir / "spectra" / "46232"))
    if limit:
        hours = hours[:limit]
    rows = []
    for sp, hs, frm in hours:
        level = tide_at(sp.time)
        if level is None:
            continue
        tide = coast_level(level, msl)
        sp = sp.with_spread("mem")
        grids = density_grids(sp)
        row = {"time": sp.time, "buoy": hs, "from": frm}
        for b in BREAKS:
            table = tables[b]
            near = carry(sp, table, grids, tide_m=tide)
            if not (near.hs_ref > 0 and near.peak_period_s == near.peak_period_s):
                continue
            freqs = sorted(table.by_freq)
            e_all = e_wrap = e_nopath = e_cross = e_wrap_cross = 0.0
            lw = []                                   # (energy, metres in kelp)
            kept = {a: 0.0 for _, a in ALPHAS}
            for i, f in enumerate(sp.frequencies):
                grid = grids.get(i)
                if grid is None:
                    continue
                nf = min(freqs, key=lambda t: abs(t - f))
                if abs(nf - f) > 0.05 * f:
                    continue
                width = sp.bin_width(i)
                fac = near.ray_friction[nf]
                for j, ray in enumerate(table.by_freq[nf]):
                    if ray.diff_gain <= 0:
                        continue
                    e = at(grid, ray.diff_off_from) * width * ray.width_rad * ray.diff_gain * fac[j]
                    k = ray.k if ray.gain > 0 else path_of.get((b, nf, ray.k))
                    L = lengths[b].get((nf, k))
                    wrap = ray.gain > 0 and part_of(ray.diff_off_from, spots[b].normal, arcs[b]) == "wrap"
                    e_all += e
                    e_wrap += e if wrap else 0.0
                    if L is None:
                        e_nopath += e
                        for a in kept:
                            kept[a] += e
                        continue
                    if L > 0:
                        e_cross += e
                        e_wrap_cross += e if wrap else 0.0
                        lw.append((e, L))
                    for a in kept:
                        kept[a] += e * math.exp(-a * L)
            normal = spots[b].normal
            angle = (((near.near_from_deg - normal + 180.0) % 360.0) - 180.0
                     if near.near_from_deg == near.near_from_deg else 0.0)

            def broken(h):
                got = break_on(profiles[b], hs_start_m=h, period_s=near.peak_period_s,
                               start_depth_m=table.start_depth_m, angle_deg=angle, tide_m=tide)
                return got.hs_m if got else None

            head = broken(near.hs_ref)
            row[b] = {"head": head, "e_all": e_all, "share_cross": e_cross / e_all,
                      "wrap_share": e_wrap / e_all,
                      "wrap_cross": e_wrap_cross / e_wrap if e_wrap > 0 else None,
                      "nopath": e_nopath / e_all, "lw": lw,
                      "ratio": {a: (broken(near.hs_ref * math.sqrt(kept[a] / e_all)) or 0) / head
                                if head else None for a in kept},
                      "check": 4.0 * math.sqrt(e_all) / near.hs_ref}
        rows.append(row)
    return {"rows": rows, "scale": scale, "features": len(feats),
            "area_km2": sum(_area(f) for f in feats) / 1e6, "lengths": lengths}


def _area(rings) -> float:
    """One feature's area: its largest ring less the others (holes), whatever
    way each ring winds."""

    areas = sorted((abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2)
                            in zip(ring, ring[1:] + ring[:1]))) / 2.0 for ring in rings),
                   reverse=True)
    return areas[0] - sum(areas[1:]) if areas else 0.0


def _wq(pairs: list[tuple[float, float]], p: float) -> float:
    """Energy-weighted quantile of the second element."""

    pairs = sorted(pairs, key=lambda t: t[1])
    tot = sum(e for e, _ in pairs)
    acc = 0.0
    for e, v in pairs:
        acc += e
        if acc >= p * tot:
            return v
    return pairs[-1][1] if pairs else float("nan")


def report(res: dict) -> str:
    from .frictionshift import _q
    from .nearshore import BREAKS
    from .wrapbudget import _qs

    short = {b: b.split("_")[1].capitalize() for b in BREAKS}
    rows = res["rows"]
    big = [r for r in rows if r["buoy"] >= 2.0 and 270.0 <= r["from"] < 295.0]
    lines = [
        "# Do the wrap's rays cross Point Loma's charted kelp?",
        "",
        "Written by `python -m forecast.kelpcross --write` (handoff item 27d). Reports, never "
        f"edits. {len(big)} big westerly hours (46232 ≥ 2 m, swell from 270–295°) through the "
        "chain as it ships (Madsen at the measured tide, surf zone from `SURF_START_M`, no chop). "
        f"Kelp: NOAA ENC WEDKLP at the `{res['scale']}` scale, {res['features']} feature(s), "
        f"{res['area_km2']:.2f} km² — a charted outline of its source survey's date "
        "(`data/kelp/enc_wedklp.json`), not this year's canopy. **Nothing here is observed.**",
        "",
        "## Controls",
        "",
        "- The per-ray sum against `carry`'s 5 m height: worst |Δ| "
        f"{100 * max(abs(r[b]['check'] - 1) for r in rows for b in BREAKS if b in r):.4f}%.",
        "- Energy at frequencies with no stored path (outside 0.03–0.25 Hz), kept whole in every "
        "column: " + "; ".join(
            f"{short[b]} {_qs([r[b]['nopath'] for r in big if b in r], 3)}" for b in BREAKS) + ".",
        "",
        "## Crossing",
        "",
        "Median [10th, 90th] over the hours. Length in kelp is energy-weighted over the crossing "
        "energy, all hours pooled.", "",
        "| break | wrap share of 5 m energy | wrap energy crossing kelp | all energy crossing kelp | "
        "metres in kelp, crossing rays: median [90th] |",
        "|---|---|---|---|---|"]
    for b in BREAKS:
        sel = [r[b] for r in big if b in r and r[b]["head"]]
        pooled = [p for c in sel for p in c["lw"]]
        lines.append(f"| {short[b]} | {_qs([c['wrap_share'] for c in sel])} "
                     f"| {_qs([c['wrap_cross'] for c in sel if c['wrap_cross'] is not None])} "
                     f"| {_qs([c['share_cross'] for c in sel])} "
                     f"| {_wq(pooled, .5):.0f} [{_wq(pooled, .9):.0f}] m |" if pooled else
                     f"| {short[b]} | {_qs([c['wrap_share'] for c in sel])} | 0 | 0 | – |")
    lines += ["", "## What a literature attenuation would take", "",
              "Headline with E kept = exp(−α·L) along each path's length in kelp, over the shipped "
              "headline; median [10th, 90th].", "",
              "| α | " + " | ".join(short[b] for b in BREAKS) + " |",
              "|---|" + "---|" * len(BREAKS)]
    for label, a in ALPHAS:
        cells = [_qs([r[b]["ratio"][a] for r in big if b in r and r[b]["ratio"][a]], 3) for b in BREAKS]
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
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
