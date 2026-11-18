"""The chain's wrap against CDIP MOP's, hour by hour: a model against a model.

    python -m forecast.mopcheck [--out docs/mop_check.md]

Reads `data/mop/<break>.csv` (`collector.mop`, Actions only) and the archived
46232 spectra, and **reports and never edits**. MOP is not an observation
(CLAUDE.md): agreement says the two ray models agree, disagreement is a
finding about this implementation before it is one about the coast
(BRIEFING §29), and neither says what the beach did.

What is compared, so that the two answer the same question:

- **Deep-water-equivalent height over the buoy's.** MOP gives Hs at its
  point's depth (about 10 m) with no friction; it is de-shoaled to deep
  water by linear Ks at its own Tp and depth. The chain gives
  `Nearshore.hs_equivalent`: refraction and diffraction over the seabed,
  shoaling divided back out, BEFORE bottom friction, which MOP does not
  apply. Both over 46232's own Hs from the same hour's spectrum. What is
  left between them is where each lets energy in: refraction, sheltering,
  and the start point (5 m against MOP's ~10 m).
- **By 46232's direction**, because §56 found the chain's excess on
  westerly swell, where its rays wrap round Point Loma's tip.
- **North is shown and not read**: its 10 m contour lies 2.2 km out, level
  with Point Loma's tip and outside its shadow (§29), so MOP's North point
  sits in different water from the chain's.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MOP_DIR = ROOT / "data" / "mop"
G = 9.81
SECTORS = (("S", 150, 205), ("SSW-SW", 205, 235), ("WSW-W", 235, 270), ("W-WNW", 270, 295),
           ("NW", 295, 330))
#: Pairs are kept when MOP's hour and the spectrum's are within this (s).
MATCH_S = 30 * 60


def ks(period_s: float, depth_m: float) -> float:
    """Linear shoaling coefficient at `depth_m` for `period_s`: sqrt(cg0/cg)."""

    from .surfzone import celerities

    omega = 2 * math.pi / period_s
    _, cg = celerities(omega, depth_m)
    return math.sqrt((G / (2 * omega)) / cg)


def read_mop(path: Path) -> dict[datetime, tuple[float, float, float]]:
    out = {}
    with path.open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if not (r["hs_m"] and r["tp_s"]):
                continue
            t = datetime.fromisoformat(r["valid_utc"].replace("Z", "+00:00"))
            out[t] = (float(r["hs_m"]), float(r["tp_s"]), float(r["dp_deg"]) if r["dp_deg"] else float("nan"))
    return out


def mean_from(spectrum) -> float:
    """Energy-weighted mean direction the buoy's swell (≥ 8 s) comes from."""

    s = c = 0.0
    for i, f in enumerate(spectrum.frequencies):
        e = spectrum.c11[i]
        if not (e == e and e > 0) or f > 1 / 8.0:
            continue
        a = spectrum.a1[i]
        if a != a:
            continue
        w = e * spectrum.bin_width(i)
        s += w * math.sin(math.radians(a)); c += w * math.cos(math.radians(a))
    return math.degrees(math.atan2(s, c)) % 360 if (s or c) else float("nan")


def pairs(break_id: str, mop: dict, spectra, table, depth_m: float) -> list[dict]:
    from .nearshore import carry, density_grids

    times = sorted(mop)
    import bisect
    rows = []
    for sp in spectra:
        i = bisect.bisect_left(times, sp.time)
        near = [j for j in (i - 1, i) if 0 <= j < len(times)
                and abs((times[j] - sp.time).total_seconds()) <= MATCH_S]
        if not near:
            continue
        hs_mop, tp_mop, dp_mop = mop[times[min(near, key=lambda j: abs(times[j] - sp.time))]]
        m0 = sum(c * sp.bin_width(k) for k, c in enumerate(sp.c11) if c == c and c > 0)
        buoy = 4 * math.sqrt(m0)
        if buoy <= 0 or tp_mop <= 0:
            continue
        mem = sp.with_spread("mem")
        n = carry(mem, table, density_grids(mem))
        rows.append({"time": sp.time, "buoy": buoy, "from": mean_from(sp),
                     "mop": hs_mop / ks(tp_mop, depth_m) / buoy,
                     "chain": n.hs_equivalent / buoy, "chain_hard": n.hs_hard / buoy,
                     "tp_mop": tp_mop, "dp_mop": dp_mop})
    return rows


def _q(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(round(p * (len(v) - 1))))] if v else float("nan")


def report(results: dict[str, list[dict]], points: dict) -> str:
    lines = ["# The chain's wrap against CDIP MOP's",
             "",
             f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC by `python -m forecast.mopcheck`; "
             "MOP from `collector.mop` (Actions). **A model against a model**: MOP is a cross-check, not a "
             "verification series, and nothing here is fitted or shipped (BRIEFING §56).",
             "",
             "Each cell: deep-water-equivalent Hs over 46232's Hs, median [10th, 90th], for MOP (de-shoaled from "
             "its point's depth at its own Tp) and the chain (`hs_equivalent`: refraction and diffraction, "
             "shoaling divided out, before friction, which MOP does not apply); then chain / MOP per hour. "
             "Sector is 46232's energy-weighted mean direction of its swell (≥ 8 s).",
             ""]
    for b, rows in results.items():
        p = points.get(b, {})
        lines += [f"## {b}" + (" — shown, not read (§29: its 10 m water is outside Point Loma's shadow)"
                               if b == "coronado_north" else ""),
                  "",
                  f"MOP point {p.get('point', '?')} ({p.get('product', '?')}), {p.get('distance_m', '?')} m from "
                  f"the break, {p.get('depth_m', float('nan')):.1f} m deep; {len(rows)} matched hours.",
                  "",
                  "| 46232 from | n | MOP | chain | chain / MOP |",
                  "|---|---:|---|---|---|"]
        for name, lo, hi in SECTORS + (("all", 0, 360),):
            sel = [r for r in rows if lo <= r["from"] < hi]
            if not sel:
                continue
            cell = lambda key: f"{_q([r[key] for r in sel], .5):.2f} [{_q([r[key] for r in sel], .1):.2f}, {_q([r[key] for r in sel], .9):.2f}]"
            ratio = [r["chain"] / r["mop"] for r in sel if r["mop"] > 0]
            lines.append(f"| {name} ({lo}–{hi}°) | {len(sel)} | {cell('mop')} | {cell('chain')} | "
                         f"{_q(ratio, .5):.2f} [{_q(ratio, .1):.2f}, {_q(ratio, .9):.2f}] |")
        lines.append("")
    lines += ["## How to read it",
              "",
              "- chain / MOP near 1 on south swell and well above 1 on W–WNW says the excess §56 found is in "
              "the chain's wrap round Point Loma, not shared by the established model.",
              "- Near 1 everywhere says the two ray models agree, and the excess, if the beach shows one, "
              "is in what both leave out (dissipation over the shelf, §56's other half) or in the ray method "
              "itself.",
              "- Neither says what the beach did. Only the observation log can.",
              ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    from .nearshore import BREAKS, load_tables
    from .transform import load_spectra

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--mop-dir", type=Path, default=MOP_DIR)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    meta_path = args.mop_dir / "points.json"
    if not meta_path.exists():
        print(f"No {meta_path}: run `python -m collector.mop` on Actions first.")
        return 1
    points = json.loads(meta_path.read_text())["breaks"]
    tables = load_tables()
    spectra = list(load_spectra(ROOT / "data" / "spectra" / "46232"))
    results = {}
    for b in BREAKS:
        if b not in points or not (args.mop_dir / f"{b}.csv").exists():
            continue
        results[b] = pairs(b, read_mop(args.mop_dir / f"{b}.csv"), spectra, tables[b],
                           float(points[b]["depth_m"]))
    text = report(results, points)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
