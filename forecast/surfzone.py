"""From 5 m of water to the break: shoaling on, and breaking, on each break's profile.

Pure Python. Reads `data/nearshore/<break>_profile.csv` (`forecast.raytrace
--profile-only`, depth below MSL every 2 m straight in along the normal, from
the table's start point to dry sand) and carries the wave energy flux the
transfer table delivers at the start point across it:

    d(E·cg·cos θ)/dx = −D,     E = Hrms²/8   (per ρg)

with θ by Snell's law from the start heading, and D the breaking dissipation
of Battjes & Janssen (1978):

    D = (α/4)·fp·Qb·Hmax²,   α = 1,   Hmax = γ·h,
    (1 − Qb) / ln Qb = −(Hrms / Hmax)²

The breaker index is Battjes & Stive's (1985) fit, γ = 0.5 + 0.4·tanh(33·s0)
on the deep-water steepness s0 = Hrms0/L0. It is taken from the literature
and NOT tuned: fitting γ to anything here would be calibration, and there is
nothing observed at these beaches to fit it to (CLAUDE.md).

Depth is the profile's depth below MSL PLUS the tide at the open coast
(`forecast.tidesite`), so the answer moves with the tide, as the break does.
No tide, no answer: running it at mean sea level instead would be a missing
observation filled with a constant.

WHAT IS REPORTED. The largest Hs along the profile, where it is, and how deep
the water is there. Shoaling raises Hs until breaking dissipation overtakes
it; the maximum is where the larger waves are breaking, and is the height a
break-point observer would compare. `outside_start` flags a maximum at the
start point itself: the waves were already breaking in 5 m of water, the
linear figure there is an upper bound (raytrace.H_REF), and the true break
point is further out than this profile starts.

WHAT IT IS NOT. One line straight in, alongshore-uniform, bulk (one period,
the peak's): the standard 1-D surf-zone model and no more. The 2016 CoNED
survey's sand, not this season's bars. Hs, not a face height — the step from
one to the other is still unfitted, and only the observation log can fit it.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TABLE_DIR = ROOT / "data" / "nearshore"
G = 9.81

ALPHA = 1.0
#: Below this much water the profile is on the sand.
H_DRY = 0.05
#: March step. The profile is every 2 m; four steps across each keeps the
#: second-order march converged (tests/test_surfzone.py).
STEP_M = 0.5


@dataclass
class Profile:
    break_id: str
    distance_m: list[float]
    depth_m: list[float]          # below MSL; negative is sand above it

    @classmethod
    def load(cls, break_id: str, directory: Path = TABLE_DIR) -> "Profile":
        d, h = [], []
        with (directory / f"{break_id}_profile.csv").open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                d.append(float(row["distance_m"]))
                h.append(float(row["depth_m"]))
        return cls(break_id, d, h)

    def depth_at(self, x: float) -> float:
        if x <= self.distance_m[0]:
            return self.depth_m[0]
        for i in range(1, len(self.distance_m)):
            if x <= self.distance_m[i]:
                x0, x1 = self.distance_m[i - 1], self.distance_m[i]
                w = (x - x0) / (x1 - x0)
                return self.depth_m[i - 1] * (1 - w) + self.depth_m[i] * w
        return self.depth_m[-1]


def load_profiles(directory: Path = TABLE_DIR, breaks=None) -> dict[str, Profile]:
    from .nearshore import BREAKS

    return {b: Profile.load(b, directory) for b in (breaks or BREAKS)}


# ------------------------------------------------------------------ physics

def wavenumber(omega: float, h: float) -> float:
    k0 = omega * omega / G
    k = k0 / math.sqrt(math.tanh(k0 * h))
    for _ in range(8):
        th = math.tanh(k * h)
        k -= (G * k * th - omega * omega) / (G * th + G * k * h * (1 - th * th))
    return k


def celerities(omega: float, h: float) -> tuple[float, float]:
    k = wavenumber(omega, h)
    c = omega / k
    two_kh = 2 * k * h
    return c, 0.5 * c * (1 + (two_kh / math.sinh(two_kh) if two_kh < 50 else 0.0))


def breaker_index(hrms0: float, period_s: float) -> float:
    """Battjes & Stive (1985): γ from the deep-water steepness."""

    l0 = G * period_s ** 2 / (2 * math.pi)
    return 0.5 + 0.4 * math.tanh(33.0 * hrms0 / l0)


def fraction_breaking(ratio: float) -> float:
    """Qb from (1 − Qb)/ln Qb = −ratio², ratio = Hrms/Hmax (Battjes & Janssen).

    Q = 1 always solves it; the physical root is the one below 1, found by
    bisection on 1 − Q + ratio²·ln Q, positive just under 1 and −∞ at 0.
    """

    if ratio >= 1.0:
        return 1.0
    if ratio <= 0.2:
        return 0.0                 # below 1e-10: nothing is breaking
    b2 = ratio * ratio
    lo, hi = 1e-12, 1.0 - 1e-9
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if 1.0 - mid + b2 * math.log(mid) > 0:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


@dataclass
class Breaking:
    hs_m: float                   # largest Hs along the profile
    depth_m: float                # water depth there, tide included
    distance_m: float             # from the table's start point, shoreward
    tide_m: float                 # open-coast level relative to MSL
    gamma: float
    fraction_breaking: float      # Qb there
    outside_start: bool

    def as_dict(self) -> dict:
        return {"hs_m": round(self.hs_m, 3), "depth_m": round(self.depth_m, 2),
                "distance_m": round(self.distance_m, 1), "tide_m": round(self.tide_m, 3),
                "gamma": round(self.gamma, 3), "fraction_breaking": round(self.fraction_breaking, 3),
                "outside_start": self.outside_start}


def break_on(profile: Profile, *, hs_start_m: float, period_s: float, start_depth_m: float,
             angle_deg: float, tide_m: float, step_m: float = STEP_M,
             path: list | None = None) -> Breaking | None:
    """March the energy flux in from the start point.

    `hs_start_m` is Hs at `start_depth_m` below MSL (the transfer table's
    figure); `angle_deg` its mean heading off the shore normal there. The flux
    at the start is fixed by those; the tide changes the depth it then crosses.
    """

    if not (hs_start_m > 0) or not (period_s > 0) or tide_m is None:
        return None
    omega = 2 * math.pi / period_s
    theta0 = math.radians(max(-80.0, min(80.0, angle_deg)))

    c_s, cg_s = celerities(omega, start_depth_m)
    flux = (hs_start_m / math.sqrt(2)) ** 2 / 8.0 * cg_s * math.cos(theta0)
    snell = math.sin(theta0) / c_s
    # Deep-water height for the breaker index: shoaling divided back out.
    hrms0 = hs_start_m / math.sqrt(2) * math.sqrt(cg_s / (0.5 * G / omega))
    gamma = breaker_index(hrms0, period_s)

    def state(x: float, f: float):
        h = profile.depth_at(x) + tide_m
        if h <= H_DRY or f <= 0:
            return None
        c, cg = celerities(omega, h)
        cos_t = math.sqrt(max(1e-6, 1.0 - (snell * c) ** 2))
        hmax = gamma * h
        # Battjes & Janssen's distribution is truncated at Hmax, so Hrms
        # cannot exceed it. Near the shoreline linear cg goes to zero and a
        # finite march cannot drain the flux as fast as the depth shrinks;
        # without the cap the height runs away at the waterline.
        hrms = min(math.sqrt(8.0 * f / (cg * cos_t)), hmax)
        qb = fraction_breaking(hrms / hmax)
        return h, hrms, qb, 0.25 * ALPHA * (1.0 / period_s) * qb * hmax * hmax, cg * cos_t

    x, end = profile.distance_m[0], profile.distance_m[-1]
    best = None
    while x <= end:
        s = state(x, flux)
        if s is None:
            break
        h, hrms, qb, d1, cgc = s
        flux = min(flux, hrms * hrms / 8.0 * cgc)
        hs = math.sqrt(2) * hrms
        if best is None or hs > best.hs_m:
            best = Breaking(hs, h, x, tide_m, gamma, qb, x == profile.distance_m[0])
        # Heun: Euler predictor, trapezoidal corrector.
        if path is not None:
            path.append((x, h, hs))
        s2 = state(x + step_m, flux - step_m * d1)
        if s2 is None:
            break
        flux -= 0.5 * step_m * (d1 + s2[3])
        x += step_m
    return best


# ------------------------------------------------------------------ report

def report(limit: int | None = None) -> str:
    """Over every archived spectrum with a measured tide within 30 minutes:
    what breaking does to the 5 m figure, where it breaks, and how much the
    tide range moves it (the same spectrum at MLLW and at MHHW)."""

    import statistics
    from datetime import timedelta

    from .geometry import load
    from .nearshore import BREAKS, carry, density_grids, load_tables, summarise
    from .tidesite import BAY, _read, coast_level, msl_above_mllw
    from .transform import load_spectra

    spots, _ = load()
    by_id = {s.id: s for s in spots}
    tables, profiles = load_tables(), load_profiles()
    msl = msl_above_mllw()
    datums = __import__("json").loads((ROOT / "data" / "tide" / "stations.json").read_text())["datums_m"][BAY]
    low, high = (coast_level(datums[k] - datums["MLLW"], msl) for k in ("MLLW", "MHHW"))
    observed = _read(ROOT / "data" / "tide" / f"{BAY}_observed.csv")
    times = [t for t, _ in observed]

    def tide_at(when):
        import bisect
        i = bisect.bisect_left(times, when)
        near = [j for j in (i - 1, i) if 0 <= j < len(times)
                and abs(times[j] - when) <= timedelta(minutes=30)]
        return observed[min(near, key=lambda j: abs(times[j] - when))][1] if near else None

    rows = {b: [] for b in BREAKS}
    for sp in load_spectra(ROOT / "data" / "spectra" / "46232", limit=limit):
        level = tide_at(sp.time)
        if level is None:
            continue
        sp = sp.with_spread("mem")
        grids = density_grids(sp)
        for b in BREAKS:
            near = carry(sp, tables[b], grids)
            if not near.hs_ref > 0:
                continue
            common = dict(buoy_hs_m=0.0, window_hs_m=0.0, depth_m=tables[b].start_depth_m,
                          profile=profiles[b], normal_deg=by_id[b].normal)
            now = summarise(near, None, tide_m=coast_level(level, msl), **common)["breaking"]
            lo = summarise(near, None, tide_m=low, **common)["breaking"]
            hi = summarise(near, None, tide_m=high, **common)["breaking"]
            if now and lo and hi:
                rows[b].append((near.hs_ref, now, lo, hi))

    def pct(v, q):
        v = sorted(v)
        return v[int(round((len(v) - 1) * q))] if v else float("nan")

    out = [f"Breaking over the archive, spectra with a measured tide within 30 min. "
           f"MLLW is {low:+.2f} m and MHHW {high:+.2f} m on MSL at the open coast. "
           f"Median [10th, 90th]."]
    for b in BREAKS:
        r = rows[b]
        if not r:
            continue
        ratio = [n["hs_m"] / h for h, n, _, _ in r]
        depth = [n["depth_m"] for _, n, _, _ in r]
        swing = [hi["hs_m"] / lo["hs_m"] - 1 for _, _, lo, hi in r]
        moved = [hi["distance_m"] - lo["distance_m"] for _, _, lo, hi in r]
        outside = sum(1 for _, n, _, _ in r if n["outside_start"])
        out.append(f"\n  {b}  (n = {len(r)})")
        out.append(f"    breaking / 5 m height:     {pct(ratio, .5):.3f} [{pct(ratio, .1):.3f}, {pct(ratio, .9):.3f}]")
        out.append(f"    depth it breaks in:        {pct(depth, .5):.2f} m [{pct(depth, .1):.2f}, {pct(depth, .9):.2f}]")
        out.append(f"    MHHW vs MLLW, height:      {100 * pct(swing, .5):+.1f}% [{100 * pct(swing, .1):+.1f}, {100 * pct(swing, .9):+.1f}]")
        out.append(f"    MHHW vs MLLW, break point: {pct(moved, .5):+.0f} m shoreward [{pct(moved, .1):+.0f}, {pct(moved, .9):+.0f}]")
        out.append(f"    already breaking at 5 m:   {outside} of {len(r)}")
    south, north = rows.get("coronado_south"), rows.get("coronado_north")
    if south and north and len(south) == len(north):
        at5 = [s[0] / n[0] for s, n in zip(south, north)]
        brk = [s[1]["hs_m"] / n[1]["hs_m"] for s, n in zip(south, north)]
        out.append("\n  south / north (the differential):")
        out.append(f"    at 5 m     {pct(at5, .5):.3f} [{pct(at5, .1):.3f}, {pct(at5, .9):.3f}]")
        out.append(f"    breaking   {pct(brk, .5):.3f} [{pct(brk, .1):.3f}, {pct(brk, .9):.3f}]")
    return "\n".join(out)


if __name__ == "__main__":
    import sys

    print(report())
    sys.exit(0)
