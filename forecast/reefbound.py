"""How much Madsen's friction at a rock roughness could take off the wrap
round Point Loma on big westerly hours: an upper bound (handoff item 27d).

    python -m forecast.reefbound --build K BREAK   # one rough Madsen table (cached)
    python -m forecast.reefbound --build K BREAK --rule R1   # ... rough on located rock only
    python -m forecast.reefbound                   # print the report
    python -m forecast.reefbound --write           # ... and docs/reef_bound.md

**Reports and never edits.** Item 27b (`forecast.wrapbudget`, BRIEFING §60)
put 70-71% of Center's and South's 5 m energy on big westerly hours in the
wrap round Point Loma. The chain's bottom friction is Madsen's at ONE
roughness, k_N = 0.05 m (SWAN's default, for sand), everywhere
(`raytrace.MADSEN_K_N`). Point Loma's reef lies along part of the wrap's
path, and nothing in the archive says where the seabed is rock. So this
bounds, without a map: what a rougher bed would take if it lay under the
WHOLE of the wrap's paths (variant A), and under every ray's (variant B).

- The rough Madsen tables are built by the shipped call,
  `raytrace.table(madsen_k_n=K)`, on the table's own traces; the rows must
  come back as committed (the `--madsen-only` guard) or the build refuses.
  Cached in `data/live/reefbound/` (gitignored), ~12 min a break and K.
- Each hour is carried as it ships (`nearshore.carry`, Madsen at the
  measured coast tide, no chop). Every carrying ray keeps the shipped
  friction factor except, in A, the wrap's rays — the clear rays whose
  offshore heading sits west of the straight-line window, as
  `wrapbudget.part_of` puts them, and the fills that read the sea from that
  side — which take the rough table's factor at the same hour's sea.
  B gives every ray the rough factor. The local sea Madsen's rate depends on
  is the break's LINEAR 5 m Hs and peak, before any friction, so it is the
  same in every column.
- The 5 m height is 4·sqrt(sum of the rays' energies); the headline is
  `surfzone.break_on` at that height with the shipped carry's peak period
  and heading held (as `wrapbudget` breaks its no-wrap column).

K = 0.1, 0.2 and 0.5 m are a SWEEP, not an estimate of rock: no paper on a
rock or reef roughness has been read from this project (BRIEFING §62), and
none of these numbers is to be quoted as "the reef". Falsifier, stated
before running: if A at K = 0.5 m takes under about 5% off the headline at
Center and South, the reef's roughness cannot be the stage that makes the
excess. Physics on surveyed inputs, observed by nothing.

**Located** (after `collector.seabed`'s run 19, `data/seabed/`): the same
sweep with the rough bed only on the wet steps a rule puts on rock (`RULES`:
R0 inside a charted rock or boulder area; R1, R2 nearest bottom sample within
250 m / 1 km and rock or boulder), every ray, Center and South. Each step's
position comes from `raytrace.trace(step_xy=True)`, and the build is
`raytrace.table(madsen_k_n=RockBed(...))`. Falsifier, stated before running:
R2 at 0.5 m keeping more than 0.95 of the headline means the rock the chart
knows cannot make the excess.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "reef_bound.md"
CACHE = ROOT / "data" / "live" / "reefbound"
ROUGH = (0.1, 0.2, 0.5)
VARIANTS = ("A", "B")
FALSIFIER = 0.95
#: The located rules (handoff 27d after run 19): which wet steps lie on rock.
#: R0, inside a charted rock or boulder area; R1 and R2, nearest bottom sample
#: within that many metres and its nature rock or boulder. A sample's nature
#: taken for the ground round it is a judgement, swept over two radii.
RULES = {"R0": None, "R1": 250.0, "R2": 1000.0}
LOCATED_BREAKS = ("coronado_center", "coronado_south")
#: What counts as rock in the chart's NATSUR words (`data/seabed/`).
ROCKY = ("rock", "boulder")
SEABED_DIR = ROOT / "data" / "seabed"


# ---------------------------------------------------------------- the rough tables

def table_path(k_n: float, break_id: str, rule: str | None = None) -> Path:
    return CACHE / (f"{rule}_k{k_n:g}" if rule else f"k{k_n:g}") / f"{break_id}_madsen.json"


# ---------------------------------------------------------------- where the rock is

def _rocky(natsur) -> bool:
    return natsur is not None and any(w in str(natsur).lower() for w in ROCKY)


def load_seabed(directory: Path = SEABED_DIR) -> tuple[list[np.ndarray], np.ndarray, np.ndarray]:
    """(rock and boulder area rings, each (n, 2) UTM; every bottom sample's
    UTM position (m, 2); whether each sample is rock or boulder), from
    `collector.seabed`'s files. Refuses if they are missing: no file is not
    "no rock"."""

    import csv

    from .utm import to_utm

    doc = json.loads((directory / "enc_sbdare.json").read_text(encoding="utf-8"))
    nat = {(f["service"], str(f["feature"])): f["attributes"].get("NATSUR") for f in doc["features"]}
    rings: dict = {}
    with (directory / "enc_sbdare.csv").open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            key = (r["service"], r["feature"])
            if _rocky(nat.get(key)):
                rings.setdefault((key, r["ring"]), []).append(to_utm(float(r["lat"]), float(r["lon"])))
    xy, rock = [], []
    with (directory / "enc_sbdare_points.csv").open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            xy.append(to_utm(float(r["lat"]), float(r["lon"])))
            rock.append(_rocky(nat.get((r["service"], r["feature"]))))
    return [np.array(v) for v in rings.values()], np.array(xy), np.array(rock, bool)


def inside(x: np.ndarray, y: np.ndarray, ring: np.ndarray) -> np.ndarray:
    """Even-odd point-in-polygon for one ring."""

    out = np.zeros(x.shape, bool)
    px, py = ring[:, 0], ring[:, 1]
    box = (x >= px.min()) & (x <= px.max()) & (y >= py.min()) & (y <= py.max())
    if not box.any():
        return out
    xs, ys = x[box], y[box]
    hit = np.zeros(xs.shape, bool)
    for i in range(len(ring) - 1):
        x1, y1, x2, y2 = px[i], py[i], px[i + 1], py[i + 1]
        crosses = (y1 > ys) != (y2 > ys)
        with np.errstate(divide="ignore", invalid="ignore"):
            xc = x1 + (ys - y1) * (x2 - x1) / (y2 - y1)
        hit ^= crosses & (xs < xc)
    out[box] = hit
    return out


class RockBed:
    """A located seabed for `raytrace.table(madsen_k_n=)`: `k_rock` on the
    wet steps the rule puts on rock, the shipped roughness elsewhere."""

    def __init__(self, rule: str, k_rock: float, seabed=None):
        from .raytrace import MADSEN_K_N

        self.rule, self.k_rock, self.k_sand = rule, k_rock, MADSEN_K_N
        self.radius = RULES[rule]
        self.rings, self.samples, self.rock = seabed if seabed is not None else load_seabed()

    def on_rock(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        x, y = np.asarray(x, float), np.asarray(y, float)
        if self.radius is None:
            on = np.zeros(x.shape, bool)
            for ring in self.rings:
                on |= inside(x, y, ring)
            return on
        on = np.zeros(x.shape, bool)
        if not x.size or not len(self.samples):
            return on
        r = self.radius
        near = ((self.samples[:, 0] >= x.min() - r) & (self.samples[:, 0] <= x.max() + r)
                & (self.samples[:, 1] >= y.min() - r) & (self.samples[:, 1] <= y.max() + r))
        if not near.any():
            return on
        sx, sy, rk = self.samples[near, 0], self.samples[near, 1], self.rock[near]
        d2 = (x[:, None] - sx[None, :]) ** 2 + (y[:, None] - sy[None, :]) ** 2
        j = np.argmin(d2, axis=1)
        return (d2[np.arange(x.size), j] <= r * r) & rk[j]

    def __call__(self, x, y) -> np.ndarray:
        return np.where(self.on_rock(x, y), self.k_rock, self.k_sand)


def build(k_n: float, break_id: str, rule: str | None = None) -> Path:
    """`<break>_madsen.json` at roughness `k_n` (everywhere, or on the rock
    `rule` locates), from the table's own call. Refuses unless the re-trace
    gives the committed rows back."""

    from . import raytrace as rt

    bathy = rt.Bathymetry.load()
    spots, blockers = rt.load()
    spot = {s.id: s for s in spots}[break_id]
    madsen: dict = {}
    rows, _ = rt.table(bathy, spot, blockers, rt.frequencies(), madsen_out=madsen,
                       madsen_k_n=RockBed(rule, k_n) if rule else k_n)
    old = rt.committed_rows(break_id)
    bad = sum(1 for a, b in zip(rows, old) if {k: str(v) for k, v in a.items()} != b)
    if len(rows) != len(old) or bad:
        raise RuntimeError(f"{break_id}: the re-trace does not give the committed table back "
                           f"({bad} rows differ, {len(rows)} vs {len(old)})")
    out = table_path(k_n, break_id, rule)
    out.parent.mkdir(parents=True, exist_ok=True)
    path = rt.write_madsen(madsen, break_id, out_dir=out.parent)
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc["meta"]["k_n_m"] != k_n:               # write_madsen states the shipped K
        text = path.read_text(encoding="utf-8")
        old_meta = json.dumps(doc["meta"])
        doc["meta"]["k_n_m"] = k_n
        if rule:
            doc["meta"]["located"] = {"rule": rule, "radius_m": RULES[rule], "k_n_rock_m": k_n,
                                      "k_n_elsewhere_m": rt.MADSEN_K_N}
        path.write_text(text.replace(old_meta, json.dumps(doc["meta"]), 1), encoding="utf-8")
    return path


def rough_share(k_n: float, break_id: str, rule: str) -> dict[float, dict[int, float]]:
    """Per frequency, each carrying row's share of its path's wet length on
    rock, from a located build."""

    doc = json.loads(table_path(k_n, break_id, rule).read_text(encoding="utf-8"))
    return {float(f): {int(k): v["rough_share"][j] for k, j in v["rows"].items()}
            for f, v in doc["freqs"].items() if "rough_share" in v}


def rough_table(table, k_n: float, rule: str | None = None):
    """The shipped `Table` with its Madsen table and every ray's weights
    swapped for the rough build's. Rows, gains and headings untouched."""

    from .nearshore import MadsenTable, Table

    madsen, weights = MadsenTable.load(table_path(k_n, table.break_id, rule))
    by_freq = {}
    for f, rays in table.by_freq.items():
        w = weights.get(f, {})
        by_freq[f] = [dataclasses.replace(r, madsen=w.get(r.k)) if r.diff_gain > 0 else r
                      for r in rays]
    missing = sum(1 for rays in by_freq.values() for r in rays
                  if r.diff_gain > 0 and r.madsen is None)
    if missing:
        raise ValueError(f"{table_path(k_n, table.break_id)}: {missing} carrying rows have no weights")
    return Table(table.break_id, table.start_depth_m, by_freq, table.fetch, madsen)


# ---------------------------------------------------------------- per ray

def on_wrap(ray, normal: float, arcs) -> bool:
    """Whether a carrying ray travels the wrap round Point Loma: a clear ray
    whose offshore heading is west of the straight-line window, or a fill
    that reads the sea from there (its fan's mean heading)."""

    from .wrapbudget import part_of

    heading = ray.off_from if ray.gain > 0 else ray.diff_off_from
    return part_of(heading, normal, arcs) == "wrap"


def mixed(shipped: dict, rough: dict, table, wrap: dict) -> dict:
    """Variant A's factors: the rough factor on the wrap's rays, shipped
    elsewhere. `wrap[f][j]` is `on_wrap` for row j at frequency f."""

    return {f: [rough[f][j] if wrap[f][j] else shipped[f][j] for j in range(len(rays))]
            for f, rays in table.by_freq.items()}


def energy5(spectrum, table, grids, factors) -> float:
    """The energy at the start depth with these factors, m²:
    `wrapbudget.ray_energies` summed."""

    from .wrapbudget import ray_energies

    rays = ray_energies(spectrum, table, grids, factors)
    return sum(r[0] for r in rays)


def row_energies(spectrum, table, grids, factors) -> dict[tuple[float, int], float]:
    """Each carrying row's energy at the start depth (m², all buoy bins it
    takes), keyed (table frequency, place in `by_freq`): `ray_energies` with
    the rows named."""

    from .nearshore import at

    freqs = sorted(table.by_freq)
    out: dict = {}
    for i, f in enumerate(spectrum.frequencies):
        grid = grids.get(i)
        if grid is None:
            continue
        near = min(freqs, key=lambda t: abs(t - f))
        if abs(near - f) > 0.05 * f:
            continue
        width = spectrum.bin_width(i)
        fac = factors[near]
        for j, ray in enumerate(table.by_freq[near]):
            if ray.diff_gain <= 0:
                continue
            e = sum(at(grid, h) * w for h, w in ray.samples()) * width * ray.width_rad * ray.diff_gain
            out[(near, j)] = out.get((near, j), 0.0) + e * fac[j]
    return out


# ---------------------------------------------------------------- the run

def run(data_dir: Path = ROOT / "data", limit: int | None = None) -> dict:
    import bisect

    from .frictionshift import MATCH
    from .geometry import load
    from .nearshore import BREAKS, carry, density_grids, load_tables
    from .surfzone import break_on, load_profiles
    from .tidesite import BAY, _read, coast_level, msl_above_mllw
    from .transform import load_spectra
    from .westerlygap import selected
    from .wrapbudget import arcs_for, part_of, ray_energies

    spots, blockers = load()
    spots = {s.id: s for s in spots}
    arcs = {b: arcs_for(spots[b], blockers) for b in BREAKS}
    tables, profiles = load_tables(), load_profiles()
    rough = {(b, k): rough_table(tables[b], k) for b in BREAKS for k in ROUGH}
    located = {(b, r, k): rough_table(tables[b], k, r)
               for b in LOCATED_BREAKS for r in RULES for k in ROUGH}
    # Per row: its path's share of wet length on rock, by rule (k-independent;
    # read from the 0.5 m build, checked equal across K below).
    share = {(b, r): {f: [rough_share(0.5, b, r).get(f, {}).get(ray.k, 0.0)
                          for ray in rays] for f, rays in tables[b].by_freq.items()}
             for b in LOCATED_BREAKS for r in RULES}
    share_agree = all(rough_share(k, b, r) == rough_share(0.5, b, r)
                      for b in LOCATED_BREAKS for r in RULES for k in ROUGH)
    wrap = {b: {f: [r.diff_gain > 0 and on_wrap(r, spots[b].normal, arcs[b]) for r in rays]
                for f, rays in tables[b].by_freq.items()} for b in BREAKS}

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

    def split(sp, table, grids, factors, b):
        """(total, wrap-route) 5 m energy."""
        tot = wr = 0.0
        for e, _, off, fill in ray_energies(sp, table, grids, factors):
            tot += e
            if not fill and part_of(off, spots[b].normal, arcs[b]) == "wrap":
                wr += e
        return tot, wr

    hours = selected(load_spectra(data_dir / "spectra" / "46232"))
    if limit:
        hours = hours[:limit]
    rows, worst_sum, worst_same, worst_rows = [], 0.0, 0.0, 0.0
    for sp, hs, frm in hours:
        level = tide_at(sp.time)
        if level is None:
            continue
        tide = coast_level(level, msl)
        sp = sp.with_spread("mem")
        grids = density_grids(sp)
        row = {"time": sp.time, "buoy": hs, "from": frm, "tide": tide}
        for b in BREAKS:
            near = carry(sp, tables[b], grids, tide_m=tide)
            if not (near.hs_ref > 0 and near.peak_period_s == near.peak_period_s):
                continue
            ship = near.ray_friction
            e5, w5 = split(sp, tables[b], grids, ship, b)
            worst_sum = max(worst_sum, abs(4.0 * math.sqrt(e5) / near.hs_ref - 1.0))
            # Control: variant A with the shipped factors on both sides is the
            # shipped carry (the mixing changes nothing by itself).
            same = mixed(ship, ship, tables[b], wrap[b])
            worst_same = max(worst_same, abs(energy5(sp, tables[b], grids, same) / e5 - 1.0))
            head = broken(b, near, near.hs_ref, tide)
            out = {"hs5": near.hs_ref, "head": head, "wrap": w5 / e5}
            for k in ROUGH:
                rk = carry(sp, rough[(b, k)], grids, tide_m=tide)
                fr = rk.ray_friction
                for v, fac in (("A", mixed(ship, fr, tables[b], wrap[b])), ("B", fr)):
                    tot, wr = split(sp, tables[b], grids, fac, b)
                    hs5 = 4.0 * math.sqrt(tot)
                    hb = broken(b, near, hs5, tide)
                    out[(v, k)] = {"hs5": hs5 / near.hs_ref,
                                   "head": hb / head if hb and head else None,
                                   "wrap": wr / tot if tot > 0 else None,
                                   "wrap_kept": wr / w5 if w5 > 0 else None}
            if b in LOCATED_BREAKS:
                e_ship = row_energies(sp, tables[b], grids, ship)
                tot_ship = sum(e_ship.values())
                worst_rows = max(worst_rows, abs(tot_ship / e5 - 1.0))
                for r in RULES:
                    sh = share[(b, r)]
                    on_rock = {key: sh[key[0]][key[1]] for key in e_ship}
                    w_keys = [key for key in e_ship if wrap[b][key[0]][key[1]]]
                    w_ship = sum(e_ship[key] for key in w_keys)
                    out[("rock", r)] = {
                        "all": sum(e_ship[key] * on_rock[key] for key in e_ship) / tot_ship,
                        "wrap": (sum(e_ship[key] * on_rock[key] for key in w_keys) / w_ship
                                 if w_ship > 0 else None)}
                    for k in ROUGH:
                        fr = carry(sp, located[(b, r, k)], grids, tide_m=tide).ray_friction
                        e_r = row_energies(sp, tables[b], grids, fr)
                        tot = sum(e_r.values())
                        lost = tot_ship - tot
                        lost_wrap = w_ship - sum(e_r[key] for key in w_keys)
                        hs5 = 4.0 * math.sqrt(tot)
                        hb = broken(b, near, hs5, tide)
                        out[(r, k)] = {"hs5": hs5 / near.hs_ref,
                                       "head": hb / head if hb and head else None,
                                       "lost_on_wrap": lost_wrap / lost if lost > 1e-12 else None}
            row[b] = out
        rows.append(row)
    return {"rows": rows, "worst_sum": worst_sum, "worst_same": worst_same,
            "share_agree": share_agree, "worst_rows": worst_rows,
            "arcs": arcs, "rough": ROUGH}


# ---------------------------------------------------------------- the report

def _q(v: list[float]) -> tuple[float, float, float]:
    a = np.array([x for x in v if x is not None and x == x], float)
    if not a.size:
        return (float("nan"),) * 3
    return tuple(float(np.quantile(a, q)) for q in (0.5, 0.1, 0.9))


def _qs(v: list[float]) -> str:
    m, lo, hi = _q(v)
    return f"{m:.2f} [{lo:.2f}, {hi:.2f}]" if m == m else "—"


def _verdict(res: dict) -> str:
    k = max(res["rough"])
    got = {b: _q([r[b][("A", k)]["head"] for r in res["rows"] if b in r])[0]
           for b in ("coronado_center", "coronado_south")}
    text = ", ".join(f"{b.split('_')[1].title()} {v:.2f}" for b, v in got.items())
    if all(v > FALSIFIER for v in got.values()):
        return (f"A at {k:g} m keeps {text} of the headline (median), above {FALSIFIER:.2f}: "
                "the reef's roughness is ruled out as the stage.")
    return (f"A at {k:g} m keeps {text} of the headline (median), not above {FALSIFIER:.2f}: "
            "the reef's roughness is NOT ruled out. Whether it is the stage depends on where "
            "the rock is and what roughness it has, neither of which this measures.")


def located_report(res: dict) -> list[str]:
    rows = res["rows"]
    name = {b: b.split("_")[1].title() for b in LOCATED_BREAKS}
    k_max = max(res["rough"])
    r2 = {b: _q([r[b][("R2", k_max)]["head"] for r in rows if b in r])[0] for b in LOCATED_BREAKS}
    fired = all(v > FALSIFIER for v in r2.values())
    lines = [
        "",
        "## Located: rough only where the chart puts rock (Center and South)",
        "",
        "The chart's seabed nature (`collector.seabed`, run 19, `data/seabed/`): 24 areas, all "
        "intertidal rock or boulder at Point Loma's west shore, and 461 bottom samples. Each "
        "wet step of every ray takes k_N on rock and the shipped 0.05 m elsewhere; every ray, "
        "not only the wrap's, since rock is rock for any ray.",
        "",
        "- **R0**: inside a charted rock or boulder area (the chart's own extents).",
        f"- **R1**: nearest bottom sample within {RULES['R1']:g} m, and it is rock or boulder.",
        f"- **R2**: the same within {RULES['R2']:g} m.",
        "",
        "R1 and R2 take a sample's nature for the ground round it: a judgement, swept over "
        "two radii, never a charted extent.",
        "",
        f"Falsifier, stated before running: R2 at {k_max:g} m keeping more than "
        f"{FALSIFIER:.2f} of the headline at Center and South means the rock the chart knows "
        "cannot make the excess.",
        "",
        "**Verdict**: R2 at " + f"{k_max:g} m keeps " +
        ", ".join(f"{name[b]} {v:.3f}" for b, v in r2.items()) + " (median): " +
        ("the falsifier fired" if fired else "the falsifier did not fire") +
        ("; " + ", ".join(name[b] for b, v in r2.items() if abs(v - FALSIFIER) < 0.01)
         + " within a point of the line, so the verdict there rests on R2's radius, a "
         "judgement." if any(abs(v - FALSIFIER) < 0.01 for v in r2.values()) else ".")
        + (" On the rock the chart knows, the charted rock is not the stage." if fired else ""),
        "",
        "Controls: the row-by-row energy sum gives the shipped 5 m energy to "
        f"{100 * res['worst_rows']:.1e}% (worst); each path's share on rock is the same in "
        f"every K's build ({'yes' if res['share_agree'] else 'NO'}); a located bed with no "
        "step on rock gives the shipped-roughness build back exactly, and every step on rock "
        "the uniform build (`tests/test_reefbound.py`).",
        "",
        "### Headline over shipped, median [10th, 90th]",
        "",
        "| rule | k_N | " + " | ".join(name[b] for b in LOCATED_BREAKS)
        + " | ceiling (§63 A): " + " / ".join(name[b] for b in LOCATED_BREAKS) + " |",
        "|---|---|" + "---|" * len(LOCATED_BREAKS) + "---|",
    ]
    for rule in RULES:
        for k in res["rough"]:
            cells = [_qs([r[b][(rule, k)]["head"] for r in rows if b in r]) for b in LOCATED_BREAKS]
            ceil = " / ".join(f"{_q([r[b][('A', k)]['head'] for r in rows if b in r])[0]:.2f}"
                              for b in LOCATED_BREAKS)
            lines.append(f"| {rule} | {k:g} m | " + " | ".join(cells) + f" | {ceil} |")
    lines += ["", "### 5 m height over shipped, median [10th, 90th]", "",
              "| rule | k_N | " + " | ".join(name[b] for b in LOCATED_BREAKS) + " |",
              "|---|---|" + "---|" * len(LOCATED_BREAKS)]
    for rule in RULES:
        for k in res["rough"]:
            cells = [_qs([r[b][(rule, k)]["hs5"] for r in rows if b in r]) for b in LOCATED_BREAKS]
            lines.append(f"| {rule} | {k:g} m | " + " | ".join(cells) + " |")
    lines += ["", "### Where it acts, median [10th, 90th]", "",
              "Path share on rock: each carrying row's share of its path's wet length on rock, "
              "weighted by the row's shipped 5 m energy. Loss on the wrap: of the energy the "
              f"rough rock takes at {k_max:g} m, the share taken from the wrap route's rows.", "",
              "| rule | " + " | ".join(f"{name[b]}: on rock, wrap / all / loss on the wrap"
                                       for b in LOCATED_BREAKS) + " |",
              "|---|" + "---|" * len(LOCATED_BREAKS)]
    for rule in RULES:
        cells = []
        for b in LOCATED_BREAKS:
            sel = [r[b] for r in rows if b in r]
            cells.append(" / ".join((
                _qs([o[("rock", rule)]["wrap"] for o in sel]),
                _qs([o[("rock", rule)]["all"] for o in sel]),
                _qs([o[(rule, k_max)]["lost_on_wrap"] for o in sel]))))
        lines.append(f"| {rule} | " + " | ".join(cells) + " |")
    return lines


def report(res: dict) -> str:
    from .nearshore import BREAKS

    rows = res["rows"]
    days = sorted({r["time"].date() for r in rows})
    lines = [
        "# Madsen at a rock roughness along the wrap: an upper bound",
        "",
        "Generated by `python -m forecast.reefbound --write` (handoff item 27d, "
        "BRIEFING §63). Report only; nothing is edited or shipped.",
        "",
        f"{len(rows)} archived hours on {len(days)} days ({days[0]} to {days[-1]}): "
        "46232 >= 2 m with swell (>= 8 s) from 270-295°, plus all of 17 Nov "
        "(`westerlygap.selected`), each at its measured coast tide, the chain as it "
        "ships (Madsen at k_N = 0.05 m, surf zone from `SURF_START_M`, no chop).",
        "",
        "- **A**: the rough k_N under the wrap's paths only (clear rays west of the "
        "straight-line window, and fills reading the sea from there); every other "
        "ray as shipped.",
        "- **B**: the rough k_N under every ray's path.",
        "",
        "k_N = 0.1, 0.2, 0.5 m is a sweep, not a rock value: no paper on reef or "
        "rock roughness has been read here. Falsifier, stated before running: "
        f"A at 0.5 m keeping more than {FALSIFIER:.2f} of the headline at Center "
        "and South rules the reef's roughness out as the stage.",
        "",
        "## Verdict on the falsifier",
        "",
        _verdict(res),
        "",
        "## Controls",
        "",
        f"- The per-ray sum gives `carry`'s 5 m height to {100 * res['worst_sum']:.4f}% (worst).",
        f"- Mixing the shipped factors with themselves gives the shipped 5 m energy "
        f"to {100 * res['worst_same']:.1e}% (worst).",
        "- Each rough table is the shipped call's (`raytrace.table(madsen_k_n=)`); "
        "every build gave the committed rows back, all three breaks.",
        "",
        "## Headline breaking Hs over shipped, median [10th, 90th]",
        "",
        "| k_N | variant | " + " | ".join(BREAKS) + " |",
        "|---|---|" + "---|" * len(BREAKS),
    ]
    for k in res["rough"]:
        for v in VARIANTS:
            cells = [_qs([r[b][(v, k)]["head"] for r in rows if b in r]) for b in BREAKS]
            lines.append(f"| {k:g} m | {v} | " + " | ".join(cells) + " |")
    lines += ["", "## 5 m height over shipped, median [10th, 90th]", "",
              "| k_N | variant | " + " | ".join(BREAKS) + " |",
              "|---|---|" + "---|" * len(BREAKS)]
    for k in res["rough"]:
        for v in VARIANTS:
            cells = [_qs([r[b][(v, k)]["hs5"] for r in rows if b in r]) for b in BREAKS]
            lines.append(f"| {k:g} m | {v} | " + " | ".join(cells) + " |")
    lines += ["", "## The wrap's share of the 5 m energy, and how much of its energy A keeps",
              "", "| | " + " | ".join(BREAKS) + " |", "|---|" + "---|" * len(BREAKS),
              "| shipped share | " + " | ".join(_qs([r[b]["wrap"] for r in rows if b in r])
                                                for b in BREAKS) + " |"]
    for k in res["rough"]:
        lines.append(f"| share, A at {k:g} m | " + " | ".join(
            _qs([r[b][("A", k)]["wrap"] for r in rows if b in r]) for b in BREAKS) + " |")
        lines.append(f"| wrap energy kept, A at {k:g} m | " + " | ".join(
            _qs([r[b][("A", k)]["wrap_kept"] for r in rows if b in r]) for b in BREAKS) + " |")
    lines += ["", "## By 46232's Hs (variant A, headline over shipped, median)", "",
              "| 46232 Hs | n | " + " | ".join(f"{b} {k:g} m" for b in BREAKS for k in res["rough"]) + " |",
              "|---|---|" + "---|" * (len(BREAKS) * len(res["rough"]))]
    for lo, hi in ((2.0, 2.5), (2.5, 3.0), (3.0, 9.9)):
        sel = [r for r in rows if lo <= r["buoy"] < hi]
        if not sel:
            continue
        cells = [f"{_q([r[b][('A', k)]['head'] for r in sel if b in r])[0]:.2f}"
                 for b in BREAKS for k in res["rough"]]
        label = f">= {lo:g} m" if hi > 9 else f"{lo:g}-{hi:g} m"
        lines.append(f"| {label} | {len(sel)} | " + " | ".join(cells) + " |")
    lines += located_report(res)
    lines += [
        "",
        "## What this does not say",
        "",
        "- **Nothing is observed.** A model's friction with an unread roughness laid "
        "over the whole of a path; where the rock is, and what roughness it has, are "
        "both unknown here.",
        "- **An upper bound in extent, not in roughness.** The rough bed covers every "
        "metre of each wrap path, deep water and sand included; a real reef covers part. "
        "A rougher k_N than 0.5 m would take more.",
        "- **Not a fix.** Fitting k_N to make the headline agree with anything would be "
        "calibration, which is the beach log's.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--build", nargs=2, metavar=("K", "BREAK"),
                    help="build one rough Madsen table into the cache and stop")
    ap.add_argument("--rule", choices=sorted(RULES),
                    help="with --build: rough only on the rock this rule locates")
    ap.add_argument("--write", action="store_true", help=f"also write {OUT.relative_to(ROOT)}")
    ap.add_argument("--limit", type=int, help="only the first N hours (a quick look)")
    args = ap.parse_args(argv)
    if args.build:
        k, b = float(args.build[0]), args.build[1]
        path = build(k, b, args.rule)
        print(f"{b} k_N={k:g} {args.rule or 'everywhere'}: {path}")
        return 0
    from .nearshore import BREAKS

    missing = [str(table_path(k, b)) for k in ROUGH for b in BREAKS
               if not table_path(k, b).exists()]
    missing += [str(table_path(k, b, r)) for r in RULES for k in ROUGH for b in LOCATED_BREAKS
                if not table_path(k, b, r).exists()]
    if missing:
        print("missing rough tables (python -m forecast.reefbound --build K BREAK [--rule R]):\n  "
              + "\n  ".join(missing), file=sys.stderr)
        return 1
    text = report(run(limit=args.limit))
    print(text)
    if args.write:
        OUT.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
