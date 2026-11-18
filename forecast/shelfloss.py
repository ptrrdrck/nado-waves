"""What the shelf would take on a big day: breaking and a height-dependent
friction along each break's rays, measured beside the shipped chain.

    python -m forecast.shelfloss [--min-buoy 2.0] [--every 6] [--hours 2026-11-17T22]

**Reports and never edits** (as `forecast.spreadmethod` does). Nothing that
ships reads it. BRIEFING §56 is the reason it exists: on big westerly days the
headline at Center and South is the 5 m figure carried in LINEARLY — the rays
carry no breaking at all (§29, §31) and the friction they carry is JONSWAP's,
a fixed share of the energy whatever the height (§32) — and on 63–87% of the
hours with 46232 at 2.5 m or more the surf zone finds the waves already
breaking where it starts. Both missing terms grow with the height: real
friction with the orbital velocity, breaking exponentially with Hs/h. Neither
can live in the precomputed table, because the table is linear in energy.
This measures what they would do.

How, per break and per hour:

1. Every ray of the transfer table is re-traced (`raytrace.trace`, the same
   start point, headings and seabed) and its path's depth kept, deep water
   to the start. A ray the table fills by diffraction takes the path of the
   clear ray whose friction it took (`raytrace.table`), as the table does.
2. The ray's energy at the start depth, friction aside, is what `carry`
   integrates: S(f, θ_off)·Δf·Δθ·diff_gain.
3. Along the path, deep water inward, the ray's energy decays at
       d ln F / ds = −(friction rate + breaking rate)
   with the sea around it taken as the break's own linear 5 m Hs, de-shoaled
   to the local depth at the peak period and reduced by the ray's own
   losses so far (H_loc = H5·√(cg5/cg)·√F). That is a mean-field estimate
   of the bulk sea a ray crosses, not a wave model; the sensitivity rows
   scale it ±15% to show how much the answer leans on it.
   - friction: SWAN's form, −C·ω²/(g²·sinh²kh)·E, with C = 0.038 m²/s³
     (JONSWAP, what ships) or C = f_w·g·U_rms/√2 (Madsen, Poon & Graber
     1988, SWAN's implementation), f_w from the bed's roughness k_N = 0.05 m
     (SWAN's default) and the bulk near-bed excursion. Literature values,
     never tuned.
   - breaking: Battjes & Janssen (1978) on the bulk sea, γ from Battjes &
     Stive (1985) on the deep-water steepness — `forecast.surfzone`'s own
     law and constants, applied over the shelf instead of only inside 5 m.
4. Then into the surf zone (`surfzone.break_on`) at the measured tide.

Controls, all three must hold before any number is read:
- the re-traced JONSWAP friction reproduces the table's stored friction,
  ray by ray;
- the shipped energies (step 2 times stored friction) reproduce
  `nearshore.carry`'s 5 m height;
- the march with JONSWAP and no breaking reproduces the shipped 5 m height.

No local chop in any column, so "shipped" here is the swell's figure; local
chop is a few centimetres on these hours (§36).

Since BRIEFING §57 Madsen's friction (no breaking) is what ships, tabulated by
`raytrace.madsen_losses` and interpolated by `nearshore.carry`; this module is
its reference. The "runtime" column is that shipped carry, and a fourth
control holds it to the "Madsen" column hour by hour. Two changes with it:
the re-trace now starts from the table's own headings (the CSV rounds them to
0.01°, which flipped 2–5 grazing rays per frequency, Center's main 18 s
westerly ray among them, onto Point Loma) with the islands and edges as the
table traces them, so every ray's status and friction come back; and the
march's sea takes the LINEAR peak (`carry`'s `friction_peak_hz`, the bin
with the most energy before friction), each column breaking at its own
peak and mean heading.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import math
import statistics
import sys
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import numpy as np

from . import raytrace as R
from .nearshore import BREAKS, TABLE_DIR, at, carry, density_grids, load_tables
from .surfzone import breaker_index, load_profiles, break_on

ROOT = Path(__file__).resolve().parent.parent
G = 9.81
#: Madsen's bed roughness and SWAN's m_f: the shipped constants (raytrace).
K_N = R.MADSEN_K_N
M_F = R.MADSEN_M_F
#: Battjes & Janssen's α, as in forecast.surfzone.
ALPHA = 1.0
#: Thin each recorded path to steps of at least this (m): dissipation is
#: integrated, and the finest grid's 4 m step resolves nothing more here.
THIN_M = 20.0
#: Beyond this depth neither friction nor breaking takes anything measurable
#: from these periods, and the path is thinned to THIN_DEEP_M steps.
THIN_DEEP_FROM_M = 40.0
THIN_DEEP_M = 250.0
#: A ray carrying less than this share of the break's energy this hour is
#: left out of the march (its energy too). The control column says what that
#: costs: it is computed the same way.
PRUNE = 1e-6
#: How far either side the mean-field local height is scaled.
SENSITIVITY = 0.15

#: Depth lookup for k and cg per frequency (m). Log-spaced: the shelf
#: matters most and deep water not at all.
_DEPTHS = np.concatenate([np.linspace(0.3, 30.0, 600), np.geomspace(30.5, 5000.0, 300)])


# ------------------------------------------------------------------ paths

@dataclass
class FreqPaths:
    freq: float
    omega: float
    depth: np.ndarray          # (n_paths, L) MSL depth, deep -> start, NaN padded
    ds: np.ndarray             # (n_paths, L) step lengths, 0 padded
    k_tab: np.ndarray          # k on _DEPTHS
    cg_tab: np.ndarray         # cg on _DEPTHS
    traced_friction: np.ndarray  # per ray, JONSWAP, from the re-trace
    path_of: np.ndarray        # per table row (ray): which path it travels


def _path_arrays(bathy, paths, keep) -> tuple[np.ndarray, np.ndarray]:
    rows_h, rows_ds = [], []
    for j in keep:
        pts = np.array([(p[0], p[1]) for p in paths[j]])
        if len(pts) < 2:
            rows_h.append(np.array([5.0])); rows_ds.append(np.array([0.0]))
            continue
        seg = np.hypot(np.diff(pts[:, 0]), np.diff(pts[:, 1]))
        mid = 0.5 * (pts[1:] + pts[:-1])
        h, *_ = bathy.sample(mid[:, 0], mid[:, 1])
        # Thin: merge consecutive steps until each is THIN_M long, depth the
        # length-weighted mean of what was merged.
        hh, dd, acc_h, acc_d = [], [], 0.0, 0.0
        for hi, si in zip(h, seg):
            if not np.isfinite(hi):
                continue
            acc_h += hi * si; acc_d += si
            if acc_d >= (THIN_M if acc_h / acc_d < THIN_DEEP_FROM_M else THIN_DEEP_M):
                hh.append(acc_h / acc_d); dd.append(acc_d); acc_h = acc_d = 0.0
        if acc_d > 0:
            hh.append(acc_h / acc_d); dd.append(acc_d)
        # Recorded start -> outward; waves travel the other way.
        rows_h.append(np.array(hh[::-1])); rows_ds.append(np.array(dd[::-1]))
    n = max(len(r) for r in rows_h)
    depth = np.full((len(rows_h), n), np.nan)
    ds = np.zeros((len(rows_h), n))
    for i, (h, d) in enumerate(zip(rows_h, rows_ds)):
        # Right-aligned: every path ENDS at the start point together, so the
        # march's last column is the start depth for all of them.
        depth[i, n - len(h):] = h
        ds[i, n - len(d):] = d
    return depth, ds


def build_paths(break_id: str, bathy=None) -> tuple[dict[float, FreqPaths], dict[float, list[dict]]]:
    """Re-trace one break's table, ray for ray, and keep each path's depths."""

    from .geometry import load

    bathy = bathy or R.Bathymetry.load()
    spots, blockers = load()
    spot = {s.id: s for s in spots}[break_id]
    xs, ys, _ = R.start_point(bathy, spot)
    # The table's own headings and the islands and edges as it traces them:
    # the CSV's headings are rounded to 0.01°, and that is enough to flip a
    # ray grazing Point Loma onto the land (BRIEFING §57).
    islands = R.islands_from(blockers)
    R.ring_depths(bathy, islands)
    edges = R.edge_points(blockers)
    near = (spot.normal - 90.0 + R.DIR_STEP_DEG / 2.0
            + R.DIR_STEP_DEG * np.arange(int(round(180.0 / R.DIR_STEP_DEG)))) % 360.0
    rows: dict[float, list[dict]] = {}
    with (TABLE_DIR / f"{break_id}.csv").open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.setdefault(float(r["freq_hz"]), []).append(r)
    out = {}
    for f, rr in rows.items():
        if len(rr) != near.size or any(f"{a:.2f}" != r["near_from_deg"] for a, r in zip(near, rr)):
            raise ValueError(f"{break_id} {f}: the table's headings are not the spot's")
        rays = R.trace(bathy, xs, ys, near, 1.0 / f, islands, edges, record=True)
        fric = np.array([float(r["friction"]) for r in rr])
        dfric = np.array([float(r["diff_friction"]) for r in rr])
        # Which path each ray's energy travels: its own, unless the table gave
        # it another ray's friction (a diffracted fill), then that ray's —
        # the nearest by heading among those whose friction is the one taken.
        path_of = np.arange(len(rr))
        for i in range(len(rr)):
            if float(rr[i]["diff_gain"]) > 0 and abs(dfric[i] - fric[i]) > 1e-5:
                cand = np.flatnonzero(np.abs(fric - dfric[i]) <= 5e-6)
                if cand.size:
                    path_of[i] = cand[np.argmin(np.abs(cand - i))]
        used = sorted({int(path_of[i]) for i in range(len(rr)) if float(rr[i]["diff_gain"]) > 0})
        depth, ds = _path_arrays(bathy, rays.paths, used)
        remap = {j: n for n, j in enumerate(used)}
        omega = 2 * math.pi * f
        k_tab = R.wavenumber(omega, _DEPTHS)
        _, cg_tab, _ = R.speeds(omega, _DEPTHS)
        out[f] = FreqPaths(f, omega, depth, ds, k_tab, cg_tab, rays.friction,
                           np.array([remap.get(int(p), -1) for p in path_of]))
    return out, rows


# ------------------------------------------------------------------ physics

def fraction_breaking_v(ratio: np.ndarray) -> np.ndarray:
    """`surfzone.fraction_breaking` on an array: the root below 1 of
    1 − Q + ratio²·ln Q, by bisection, with its limits (Q = 1 at ratio ≥ 1,
    0 at ratio ≤ 0.2). Pinned to the scalar form by the control in `main`."""

    r = np.asarray(ratio, float)
    b2 = r * r
    lo = np.full(r.shape, 1e-12)
    hi = np.full(r.shape, 1.0 - 1e-9)
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        pos = 1.0 - mid + b2 * np.log(mid) > 0
        hi = np.where(pos, mid, hi)
        lo = np.where(pos, lo, mid)
    q = 0.5 * (lo + hi)
    return np.where(r >= 1.0, 1.0, np.where(r <= 0.2, 0.0, q))


#: Madsen's f_w, solved and on its lookup table: the shipped forms (raytrace).
madsen_fw = R.madsen_fw
fw_lookup = R.fw_lookup


#: Fixed-point passes for the ray's own losses inside its local height. The
#: losses enter only through √F in H_loc, so each pass recomputes every
#: step's rate from the previous pass's F, damped (the geometric mean of the
#: old and new F) because a ray over a shoal otherwise oscillates: unbroken
#: it is big and breaks hard, broken it is small and does not. Passes stop
#: when no ray's survival moves by more than TOL; `main` reports the worst.
PASSES = 30
TOL = 1e-3


_QB_R = np.linspace(0.0, 1.0, 4001)
_QB = None


def qb_lookup(ratio: np.ndarray) -> np.ndarray:
    """fraction_breaking_v on a 4,001-point table (pinned by the control)."""

    global _QB
    if _QB is None:
        _QB = fraction_breaking_v(_QB_R)
    return np.interp(np.minimum(ratio, 1.0), _QB_R, _QB)


def march(fp: FreqPaths, hs5_lin: float, tide_m: float, peak: FreqPaths, gamma: float,
          friction: str, breaking: bool, scale: float = 1.0, passes: int = PASSES,
          trace: list | None = None) -> np.ndarray:
    """Survival F per path, deep water to the start, for this hour's sea.

    Whole-array: every path and step at once, F along each path by a
    cumulative sum of rate·ds, and the dependence of the rate on F (through
    the local height) by fixed-point passes."""

    live = np.isfinite(fp.depth) & (fp.ds > 0)
    ht = np.where(live, np.maximum(np.nan_to_num(fp.depth, nan=5.0) + tide_m, 0.3), 5.0)
    k = np.interp(ht, _DEPTHS, fp.k_tab)
    cg = np.interp(ht, _DEPTHS, fp.cg_tab)
    sh2 = np.sinh(np.minimum(k * ht, 300.0)) ** 2
    kp = np.interp(ht, _DEPTHS, peak.k_tab)
    cgp = np.interp(ht, _DEPTHS, peak.cg_tab)
    shp = np.sinh(np.minimum(kp * ht, 300.0))
    cg5 = float(np.interp(5.0 + tide_m, _DEPTHS, peak.cg_tab))
    base = scale * hs5_lin * np.sqrt(cg5 / cgp)
    shape = fp.omega ** 2 / (G ** 2 * sh2 * cg)
    F_before = np.ones(fp.depth.shape)        # F on arrival at each step
    F = np.ones(fp.depth.shape[0])
    iterate = friction != "jonswap" or breaking
    for n in range(passes if iterate else 1):
        hs_loc = base * np.sqrt(F_before)
        if friction == "jonswap":
            c = R.C_BOTTOM
        else:
            urms = peak.omega * hs_loc / (4.0 * shp)
            ab = math.sqrt(2.0) * hs_loc / (4.0 * shp)
            c = fw_lookup(ab) * G * urms / math.sqrt(2.0)
        rate = c * shape
        if breaking:
            hrms = hs_loc / math.sqrt(2.0)
            hmax = gamma * ht
            qb = qb_lookup(hrms / hmax)
            d = 0.25 * ALPHA * (peak.omega / (2 * math.pi)) * qb * hmax * hmax
            rate = rate + d / (hrms * hrms / 8.0 * cgp)
        loss = np.where(live, rate * fp.ds, 0.0)
        cum = np.cumsum(loss, axis=1)
        new_before = np.exp(-(cum - loss))
        F_new = np.exp(-cum[:, -1])
        change = float(np.max(np.abs(F_new - F))) if n else 1.0
        if n:
            new_before = np.sqrt(F_before * new_before)
            F_new = np.sqrt(F * F_new)
        F_before, F = new_before, F_new
        if n and change < TOL:
            break
    if trace is not None:
        trace.append(change if iterate else 0.0)
    return F


# ------------------------------------------------------------------ one hour

VARIANTS = (
    ("JONSWAP (shipped before §57)", "jonswap", False, 1.0),
    ("JONSWAP + shelf breaking", "jonswap", True, 1.0),
    ("Madsen, no breaking (ships, §57)", "madsen", False, 1.0),
    ("Madsen + shelf breaking", "madsen", True, 1.0),
    (f"Madsen + breaking, local Hs -{SENSITIVITY:.0%}", "madsen", True, 1.0 - SENSITIVITY),
    (f"Madsen + breaking, local Hs +{SENSITIVITY:.0%}", "madsen", True, 1.0 + SENSITIVITY),
)


def hour(spectrum, break_id: str, paths: dict[float, FreqPaths], rows: dict[float, list[dict]],
         table, profile, tide_m: float, normal_deg: float, grids=None) -> dict:
    grids = grids or density_grids(spectrum)
    near = carry(spectrum, table, grids, friction="jonswap")
    # What ships (§57): Madsen from the table, at this tide.
    run = carry(spectrum, table, grids, tide_m=tide_m)
    freqs = sorted(rows)
    per_f = {}                       # freq -> (energies per ray, stored diff friction)
    for i, f in enumerate(spectrum.frequencies):
        g = grids.get(i)
        if g is None:
            continue
        tf = min(freqs, key=lambda t: abs(t - f))
        if abs(tf - f) > 0.05 * f:
            continue
        w = spectrum.bin_width(i)
        e = np.array([at(g, float(r["diff_off_from_deg"])) * w * math.radians(float(r["near_width_deg"]))
                      * float(r["diff_gain"]) if float(r["diff_gain"]) > 0 else 0.0 for r in rows[tf]])
        fr = np.array([float(r["diff_friction"]) for r in rows[tf]])
        prev = per_f.get(tf)
        per_f[tf] = (e + prev[0], fr) if prev else (e, fr)
    e_lin = sum(float(e.sum()) for e, _ in per_f.values())
    e_ship = sum(float((e * fr).sum()) for e, fr in per_f.values())
    hs5_lin = 4.0 * math.sqrt(e_lin)
    # The sea the march crosses: the linear peak, as the runtime takes it.
    peak_hz = run.friction_peak_hz if run.friction_peak_hz else 1.0 / near.peak_period_s
    tp = 1.0 / peak_hz
    peak = paths[min(paths, key=lambda f: abs(f - peak_hz))]
    # surfzone's γ: deep-water Hrms from the 5 m figure, shoaling divided out.
    cg5 = float(np.interp(5.0, _DEPTHS, peak.cg_tab))
    hrms0 = hs5_lin / math.sqrt(2) * math.sqrt(cg5 / (0.5 * G / peak.omega))
    gamma = breaker_index(hrms0, tp)
    def angle_of(deg: float) -> float:
        return ((deg - normal_deg + 180.0) % 360.0) - 180.0 if deg == deg else 0.0
    # Control: the march with JONSWAP, no breaking, at MSL (where the table's
    # friction was computed) must give the stored friction back.
    e_ctrl = 0.0
    for tf, (e, _) in per_f.items():
        fp = paths[tf]
        ok = (fp.path_of >= 0) & (e > PRUNE * e_lin)
        if not ok.any():
            continue
        used = np.unique(fp.path_of[ok])
        sub = FreqPaths(fp.freq, fp.omega, fp.depth[used], fp.ds[used], fp.k_tab, fp.cg_tab,
                        fp.traced_friction, fp.path_of)
        F = march(sub, hs5_lin, 0.0, peak, gamma, "jonswap", False)
        e_ctrl += float((e[ok] * F[np.searchsorted(used, fp.path_of[ok])]).sum())
    rb = break_on(profile, hs_start_m=run.hs_ref, period_s=run.peak_period_s,
                  start_depth_m=table.start_depth_m, angle_deg=angle_of(run.near_from_deg), tide_m=tide_m)
    out = {"carry_hs5": near.hs_ref, "rebuilt_hs5": 4.0 * math.sqrt(e_ship), "lin_hs5": hs5_lin,
           "march_msl_hs5": 4.0 * math.sqrt(e_ctrl), "tp": tp, "variants": {},
           "runtime": (run.hs_ref, rb.hs_m if rb else float("nan"), bool(rb and rb.outside_start)),
           "runtime_lin_hs5": run.friction_hs_lin}
    for name, fric, brk, scale in VARIANTS:
        e5 = 0.0
        by_tf: dict[float, float] = {}
        sn = cn = 0.0
        for tf, (e, _) in per_f.items():
            fp = paths[tf]
            idx = fp.path_of
            ok = (idx >= 0) & (e > PRUNE * e_lin)
            if not ok.any():
                continue
            used = np.unique(idx[ok])
            sub = FreqPaths(fp.freq, fp.omega, fp.depth[used], fp.ds[used], fp.k_tab, fp.cg_tab,
                            fp.traced_friction, fp.path_of)
            conv: list = []
            F = march(sub, hs5_lin, tide_m, peak, gamma, fric, brk, scale, trace=conv)
            out["last_pass"] = max(out.get("last_pass", 0.0), conv[-1])
            where = np.searchsorted(used, idx[ok])
            got = e[ok] * F[where]
            e5 += float(got.sum())
            by_tf[tf] = float(got.sum())
            heads = np.radians([float(rows[tf][j]["near_from_deg"]) for j in np.flatnonzero(ok)])
            sn += float((got * np.sin(heads)).sum()); cn += float((got * np.cos(heads)).sum())
        hs5 = 4.0 * math.sqrt(e5)
        # Each column breaks at its own peak and mean 5 m heading, as summarise does.
        tp_v = 1.0 / max(by_tf, key=by_tf.get) if by_tf else tp
        heading = math.degrees(math.atan2(sn, cn)) % 360.0 if e5 > 0 else float("nan")
        b = break_on(profile, hs_start_m=hs5, period_s=tp_v, start_depth_m=table.start_depth_m,
                     angle_deg=angle_of(heading), tide_m=tide_m)
        out["variants"][name] = (hs5, b.hs_m if b else float("nan"), bool(b and b.outside_start))
    return out


# ------------------------------------------------------------------ report

def controls(paths_by_break, rows_by_break) -> list[str]:
    """The re-trace against the table, on the rays whose OWN path carries
    energy: those that reach deep water or the grid's edge. A ray that ends
    on land carries energy only as a diffracted fill, along the clear ray it
    took its friction from (`path_of`); its own path is never used, and its
    landing point is the most sensitive thing a ray tracer computes (it
    differs from the table's build on ~1 in 3 land rays)."""

    from .surfzone import fraction_breaking

    lines = []
    for b, paths in paths_by_break.items():
        d_all, flips, n = [], 0, 0
        for f, fp in paths.items():
            rr = rows_by_break[b][f]
            stored = np.array([float(r["friction"]) for r in rr])
            own = np.array([r["status"] != "land" for r in rr])
            d_all.extend(np.abs(fp.traced_friction - stored)[own].tolist())
            n += int(own.sum())
        d = np.array(d_all)
        lines.append(f"  {b}: re-traced JONSWAP friction vs the table's, {n} rays off the land: "
                     f"median |Δ| {np.median(d):.1e}, 99th {np.quantile(d, .99):.1e}, worst {d.max():.1e}")
    grid = np.linspace(0.0, 1.2, 241)
    worst = max(abs(float(fraction_breaking_v(np.array([v]))[0]) - fraction_breaking(v)) for v in grid)
    lines.append(f"  vectorised Qb vs surfzone.fraction_breaking, worst |Δ| {worst:.1e}")
    r = np.linspace(0.0, 1.0, 997)
    lines.append(f"  Qb table vs the bisection, worst |Δ| {np.max(np.abs(qb_lookup(r) - fraction_breaking_v(r))):.1e}")
    ab = np.geomspace(1e-3, 50.0, 997)
    lines.append(f"  f_w table vs Madsen solved, worst relative |Δ| {np.max(np.abs(fw_lookup(ab) / madsen_fw(ab) - 1)):.1e}")
    return lines


MADSEN = VARIANTS[2][0]


def runtime_control(results: list[dict]) -> list[str]:
    """The runtime against the march, per break: the linear 5 m Hs both
    evaluate Madsen for; the 5 m height with the march's own path-thinning
    error divided out (its JONSWAP march at MSL over the table's carry, the
    same paths and steps, so what is left is the runtime's interpolation);
    and the breaking height as each gives it, thinning and all."""

    lines = []
    for b in BREAKS:
        lin, five, brk = [], [], []
        for r in results:
            x = r[b]
            if not x["carry_hs5"] > 0 or not x["march_msl_hs5"] > 0:
                continue
            m5, mb, _ = x["variants"][MADSEN]
            r5, rbk, _ = x["runtime"]
            lin.append((x["runtime_lin_hs5"] / x["lin_hs5"] - 1, r["time"]))
            five.append((r5 / (m5 * x["carry_hs5"] / x["march_msl_hs5"]) - 1, r["time"]))
            if mb > 0 and rbk == rbk:
                brk.append((rbk / mb - 1, r["time"]))
        for label, v in (("linear 5 m Hs", lin), ("5 m Hs, thinning out", five), ("breaking Hs", brk)):
            if not v:
                continue
            a = sorted(abs(d) for d, _ in v)
            worst = max(v, key=lambda t: abs(t[0]))
            lines.append(f"  {b:16s} {label:22s} median |Δ| {a[len(a) // 2]:.2%}  99th "
                         f"{a[min(len(a) - 1, int(0.99 * len(a)))]:.2%}  worst {worst[0]:+.2%} "
                         f"({worst[1]:%Y-%m-%d %HZ}), n={len(v)}")
    return lines


def main(argv: list[str] | None = None) -> int:
    from .geometry import load
    from .tidesite import BAY, _read, coast_level, msl_above_mllw
    from .transform import load_spectra

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--min-buoy", type=float, default=0.0, help="only hours with 46232 at least this Hs (m)")
    ap.add_argument("--every", type=int, default=1, help="below --big, keep every n-th hour")
    ap.add_argument("--big", type=float, default=2.0, help="hours at or above this buoy Hs are all kept")
    ap.add_argument("--hours", nargs="*", default=None, help="ISO hour prefixes to run instead")
    ap.add_argument("--out", type=Path, default=None, help="write every hour's columns here (JSON)")
    ap.add_argument("--cache", type=Path, default=None,
                    help="pickle of the re-traced paths (~4 min to build); written if absent")
    args = ap.parse_args(argv)

    spots, _ = load()
    by_id = {s.id: s for s in spots}
    tables, profiles = load_tables(), load_profiles()
    import pickle

    paths_by_break, rows_by_break = {}, {}
    if args.cache and args.cache.exists():
        paths_by_break, rows_by_break = pickle.loads(args.cache.read_bytes())
    else:
        bathy = R.Bathymetry.load()
        for b in BREAKS:
            paths_by_break[b], rows_by_break[b] = build_paths(b, bathy)
        if args.cache:
            args.cache.write_bytes(pickle.dumps((paths_by_break, rows_by_break)))
    print("Controls")
    print("\n".join(controls(paths_by_break, rows_by_break)))

    msl = msl_above_mllw()
    obs = _read(ROOT / "data" / "tide" / f"{BAY}_observed.csv")
    times = [t for t, _ in obs]

    def tide_at(when):
        i = bisect.bisect_left(times, when)
        near = [j for j in (i - 1, i) if 0 <= j < len(times) and abs(times[j] - when) <= timedelta(minutes=30)]
        return obs[min(near, key=lambda j: abs(times[j] - when))][1] if near else None

    results = []
    n_small = 0
    for sp in load_spectra(ROOT / "data" / "spectra" / "46232"):
        if args.hours and not any(sp.time.isoformat().startswith(h) for h in args.hours):
            continue
        level = tide_at(sp.time)
        if level is None:
            continue
        m0 = sum(c * sp.bin_width(i) for i, c in enumerate(sp.c11) if c == c and c > 0)
        buoy = 4.0 * math.sqrt(m0)
        if buoy < args.min_buoy:
            continue
        if not args.hours and buoy < args.big:
            n_small += 1
            if n_small % args.every:
                continue
        sp = sp.with_spread("mem")
        grids = density_grids(sp)
        tide = coast_level(level, msl)
        row = {"time": sp.time, "buoy": buoy, "from": sp.mean_direction() if hasattr(sp, "mean_direction") else None}
        for b in BREAKS:
            row[b] = hour(sp, b, paths_by_break[b], rows_by_break[b], tables[b], profiles[b], tide,
                          by_id[b].normal, grids)
        results.append(row)
        if args.hours:
            print(f"\n{sp.time:%Y-%m-%d %HZ}  buoy {buoy:.2f} m, tide {tide:+.2f} m on MSL")
            for b in BREAKS:
                r = row[b]
                print(f"  {b}: carry 5 m {r['carry_hs5']:.3f}, rebuilt {r['rebuilt_hs5']:.3f}, "
                      f"linear (no friction) {r['lin_hs5']:.3f}, Tp {r['tp']:.1f} s")
                for name, (h5, hb, flag) in r["variants"].items():
                    print(f"    {name:42s} 5 m {h5:5.2f}  breaking {hb:5.2f}{'  (already breaking at 5 m)' if flag else ''}")

    worst5 = max((abs(r[b]["rebuilt_hs5"] / r[b]["carry_hs5"] - 1) for r in results for b in BREAKS
                  if r[b]["carry_hs5"] > 0), default=float("nan"))
    ship = VARIANTS[0][0]
    worstm = max((abs(r[b]["march_msl_hs5"] / r[b]["carry_hs5"] - 1) for r in results for b in BREAKS
                  if r[b]["carry_hs5"] > 0), default=float("nan"))
    print(f"  rebuilt 5 m vs nearshore.carry, worst |Δ| {worst5:.2%} over {len(results)} hours")
    print(f"  march (JONSWAP, no breaking, at MSL) vs nearshore.carry, worst |Δ| {worstm:.2%}")
    lastp = max((r[b].get("last_pass", 0.0) for r in results for b in BREAKS), default=float("nan"))
    print(f"  fixed point: the last pass changed a ray's survival by at most {lastp:.1e} (stops at {TOL:g}, or {PASSES} passes)")
    print("\nThe shipped runtime (nearshore.carry, Madsen table) against the Madsen march, hour by hour:")
    for line in runtime_control(results):
        print(line)
    if args.out:
        import json
        args.out.write_text(json.dumps([{**{k: (v.isoformat() if k == "time" else v) for k, v in r.items()
                                            if k not in BREAKS},
                                         **{b: r[b] for b in BREAKS}} for r in results], default=str))
    if args.hours:
        return 0

    print("\nBreaking height under each variant over the JONSWAP breaking height, median [10th, 90th],"
          " by 46232's Hs. No local chop in either.")
    bands = ((0.0, 1.0), (1.0, 1.5), (1.5, 2.0), (2.0, 2.5), (2.5, 9.0))
    for b in BREAKS:
        print(f"\n  {b}")
        for lo, hi in bands:
            sel = [r for r in results if lo <= r["buoy"] < hi]
            if not sel:
                continue
            cells = []
            for name, *_ in VARIANTS[1:4]:
                v = sorted(r[b]["variants"][name][1] / r[b]["variants"][ship][1] for r in sel
                           if r[b]["variants"][ship][1] > 0)
                q = lambda p: v[min(len(v) - 1, int(round(p * (len(v) - 1))))]
                cells.append(f"{q(.5):.2f} [{q(.1):.2f}, {q(.9):.2f}]")
            print(f"    buoy {lo:.1f}-{hi:.1f} m  n={len(sel):3d}   " + "   ".join(cells))
        print("      columns: " + " | ".join(n for n, *_ in VARIANTS[1:4]))
    big = [r for r in results if r["buoy"] >= 2.5]
    if big:
        print("\n  sensitivity, buoy >= 2.5 m (Madsen + breaking, local Hs scaled), median ratio to shipped:")
        for b in BREAKS:
            cells = []
            for name, *_ in VARIANTS[3:]:
                cells.append(f"{statistics.median(r[b]['variants'][name][1] / r[b]['variants'][ship][1] for r in big):.2f}")
            print(f"    {b:16s} " + "  ".join(cells))
    return 0


if __name__ == "__main__":
    sys.exit(main())
