"""How much of the aperture's answer is the spreading function, not the coast?

Run: ``python -m forecast.spreadmethod`` (reads ``data/spectra/46232``)

A pitch-roll buoy measures only the first two circular moments of the
directional distribution at each frequency: α1, r1, α2, r2. Everything
`forecast.transform` does with direction rests on turning those four numbers
back into a full D(f, θ), and there is more than one way to do it.

- **Fourier** — NDBC's own reconstruction,
  ``D = (1/π)[0.5 + r1 cos(θ − α1) + r2 cos(2(θ − α2))]``. This is what ships.
  A two-term series cannot be narrow: it keeps a floor of energy well away from
  the peak, and has to be clamped where it goes negative.
- **MEM** — the maximum-entropy estimate of Lygre & Krogstad (1986). The same
  four numbers reproduced exactly (the control below checks it), with no more
  structure than they carry. It is typically much narrower, and is known to
  invent a second peak when the moments are ambiguous.

Neither is the truth. There is no directional observation at the beach and no
second directional instrument at the buoy, so this cannot say which is RIGHT —
only how far apart they are, and where. That is the whole claim of the module.
It reports and never edits: nothing that ships changes on the strength of it.

Both are renormalised to integrate to one per frequency, so the comparison is
purely about where each puts the energy, never about how much there is. The
clamped Fourier shape therefore differs very slightly from `transform.through`,
which does not renormalise; the report prints that difference as its first
control.
"""

from __future__ import annotations

import argparse
import cmath
import math
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .geometry import Blocker, Spot, _relative, blocked_sector, load
from .transform import (
    SEAWARD_CLIP,
    WIND_SEA_PERIOD_S,
    Spectrum,
    load_spectra,
    through,
)

DEFAULT_SPECTRA = Path(__file__).resolve().parent.parent / "data" / "spectra" / "46232"

BREAKS = ("coronado_north", "coronado_center", "coronado_south")

#: 1° bins, the same step `transform` integrates on.
STEP_DEG = 1.0
_N = int(round(360.0 / STEP_DEG))
_THETA = [math.radians((n + 0.5) * STEP_DEG) for n in range(_N)]
_COS = [math.cos(t) for t in _THETA]
_SIN = [math.sin(t) for t in _THETA]
_COS2 = [math.cos(2 * t) for t in _THETA]
_SIN2 = [math.sin(2 * t) for t in _THETA]
#: Bin EDGES, for integrating MEM exactly rather than sampling it.
_EDGES = [math.radians(n * STEP_DEG) for n in range(_N + 1)]
_EIP = [cmath.exp(1j * t) for t in _EDGES]
_EIM = [cmath.exp(-1j * t) for t in _EDGES]

#: MEM divides by (1 − r1²). A bin whose r1 sits this close to one is a
#: degenerate fit, not a very narrow swell, and is left out of BOTH methods so
#: the two are always compared on the same energy.
R1_CEILING = 0.999


class Unrealisable(ValueError):
    """Four moments no distribution on the circle can have.

    Measurement noise can hand back (r1, r2) that violate the Toeplitz
    condition; MEM's poles then sit on or outside the unit circle and the
    "distribution" is not one. Such a bin is left out of BOTH methods, counted,
    and never patched: a gap is a gap.
    """


IN_WINDOW = "in window"
ISLANDS = "Coronado Islands"


def fourier(r1: float, r2: float, a1: float, a2: float, *, normalise: bool = True
            ) -> list[float]:
    """NDBC's two-term reconstruction on the 1° grid, clamped, sum = 1.

    `normalise=False` gives the SHIPPED form instead: clamped and not rescaled,
    in units where an unclamped distribution sums to one. Clamping only ever
    adds, so a bin that needed it carries a little more than its measured
    energy -- which is the whole difference between the two forms.
    """

    ca1, sa1 = math.cos(math.radians(a1)), math.sin(math.radians(a1))
    ca2, sa2 = math.cos(math.radians(2 * a2)), math.sin(math.radians(2 * a2))
    raw = [
        max(0.0, 0.5 + r1 * (c * ca1 + s * sa1) + r2 * (c2 * ca2 + s2 * sa2))
        for c, s, c2, s2 in zip(_COS, _SIN, _COS2, _SIN2)
    ]
    if not normalise:
        scale = math.radians(STEP_DEG) / math.pi
        return [v * scale for v in raw]
    total = sum(raw)
    return [v / total for v in raw] if total > 0 else raw


def shipped(r1: float, r2: float, a1: float, a2: float) -> list[float]:
    return fourier(r1, r2, a1, a2, normalise=False)


def mem(r1: float, r2: float, a1: float, a2: float) -> list[float]:
    """Lygre & Krogstad (1986) maximum entropy, integrated EXACTLY per 1° bin.

    MEM is D(θ) ∝ 1 / |1 − φ1 e^{-iθ} − φ2 e^{-2iθ}|², which for a swell with
    r1 near one is a spike far narrower than a degree. Sampling it at bin
    centres misplaced that spike and returned moments up to 0.17 in r1 and 34°
    in α1 away from the buoy's own. So it is integrated instead.

    With z = e^{iθ} the denominator is |(z − p1)(z − p2)|², p the roots of
    z² − φ1 z − φ2, and partial fractions turn D into two Poisson kernels and a
    cross term, each a sum of 1/(1 − w e^{±iθ}) with |w| < 1 — whose integral
    is θ ± i·log(1 − w e^{±iθ}), with no branch to cross.
    """

    c1 = r1 * cmath.exp(1j * math.radians(a1))
    c2 = r2 * cmath.exp(2j * math.radians(a2))
    phi1 = (c1 - c2 * c1.conjugate()) / (1.0 - abs(c1) ** 2)
    phi2 = c2 - c1 * phi1
    disc = cmath.sqrt(phi1 * phi1 + 4.0 * phi2)
    p1, p2 = (phi1 + disc) / 2.0, (phi1 - disc) / 2.0
    if max(abs(p1), abs(p2)) >= 1.0 - 1e-9 or abs(p1 - p2) < 1e-9:
        raise Unrealisable(f"poles {abs(p1):.4f}, {abs(p2):.4f}")

    def anti(k: int, w_plus: complex, w_minus: complex) -> complex:
        # ∫ [1/(1 − w₊ e^{iθ}) + 1/(1 − w₋ e^{-iθ}) − 1] dθ, at edge k.
        return (_EDGES[k] + 1j * cmath.log(1.0 - w_plus * _EIP[k])
                - 1j * cmath.log(1.0 - w_minus * _EIM[k]))

    k11 = 1.0 / (1.0 - abs(p1) ** 2)
    k22 = 1.0 / (1.0 - abs(p2) ** 2)
    k12 = 1.0 / (1.0 - p1 * p2.conjugate())
    prev = None
    raw = []
    for k in range(_N + 1):
        # 1/|z−p|² = K[1/(1−p̄z) + 1/(1−pz̄) − 1];  1/((z−p)(z̄−q̄)) = K'[1/(1−q̄z) + 1/(1−pz̄) − 1]
        v = (k11 * anti(k, p1.conjugate(), p1) + k22 * anti(k, p2.conjugate(), p2)
             - 2.0 * (k12 * anti(k, p2.conjugate(), p1)).real)
        if prev is not None:
            raw.append(max(0.0, (v - prev).real))
        prev = v
    total = sum(raw)
    return [v / total for v in raw]


def moments(dist: list[float]) -> tuple[float, float, float, float]:
    """(r1, α1, r2, α2) of a distribution on the grid — the control.

    A reconstruction that does not give back the four numbers it was built
    from is not a reconstruction of this buoy, whatever it looks like.
    """

    a = sum(d * c for d, c in zip(dist, _COS))
    b = sum(d * s for d, s in zip(dist, _SIN))
    a2 = sum(d * c for d, c in zip(dist, _COS2))
    b2 = sum(d * s for d, s in zip(dist, _SIN2))
    return (math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360.0,
            math.hypot(a2, b2), (math.degrees(math.atan2(b2, a2)) / 2.0) % 180.0)


def labels(spot: Spot, blockers: list[Blocker]) -> list[str]:
    """What each 1° bin is, from this break: in window, a blocker, or away.

    Same rule as `transform.through`: a bearing in two shadows goes to the
    first blocker in file order, so shares sum without double-counting. The
    two island groups are pooled here because the question is "the islands",
    not which of them.
    """

    sectors = [(b.name, blocked_sector(spot, b)) for b in blockers]
    out = []
    for n in range(_N):
        offset = _relative((n + 0.5) * STEP_DEG, spot.normal)
        if abs(offset) > 90.0:
            out.append(SEAWARD_CLIP)
            continue
        who = IN_WINDOW
        for name, sector in sectors:
            if sector and sector[0] <= offset <= sector[1]:
                who = ISLANDS if name.startswith(ISLANDS) else name
                break
        out.append(who)
    return out


@dataclass
class Split:
    """Shares of one spectrum's energy, per break, for one method and band."""

    shares: dict[str, float] = field(default_factory=dict)
    energy: float = 0.0


def split(spectrum: Spectrum, marks: dict[str, list[str]], bands: dict
          ) -> tuple[dict, int, int]:
    """Energy shares per band, method and break, for one spectrum.

    Each bin's distributions are computed once and fed to every band.
    Returns (out[band][method][break] -> Split, degenerate bins, unrealisable
    bins); both kinds are dropped from the two candidates, never from the
    shipped control.
    """

    out = {band: {m: {sid: Split() for sid in marks} for m in METHODS} for band in bands}
    degenerate = unrealisable = 0
    for i, f in enumerate(spectrum.frequencies):
        e = spectrum.c11[i]
        vals = (e, spectrum.r1[i], spectrum.r2[i], spectrum.a1[i], spectrum.a2[i])
        if any(v is None or math.isnan(v) for v in vals) or e <= 0 or f <= 0:
            continue
        args = (spectrum.r1[i], spectrum.r2[i], spectrum.a1[i], spectrum.a2[i])
        # The shipped control sees every bin `transform.through` sees; the two
        # candidates are compared only where BOTH exist.
        dists = {"shipped": shipped(*args)}
        if spectrum.r1[i] >= R1_CEILING:
            degenerate += 1
        else:
            try:
                dists["mem"] = mem(*args)
                dists["fourier"] = fourier(*args)
            except Unrealisable:
                unrealisable += 1
        period = 1.0 / f
        energy = e * spectrum.bin_width(i)
        for band_name, band in bands.items():
            if band and not (band[0] <= period < band[1]):
                continue
            for m, dist in dists.items():
                weight = energy * (sum(dist) if m == "shipped" else 1.0)
                for sid, mark in marks.items():
                    acc = out[band_name][m][sid]
                    acc.energy += weight
                    for d, who in zip(dist, mark):
                        if d:
                            acc.shares[who] = acc.shares.get(who, 0.0) + energy * d
    for per_method in out.values():
        for per_break in per_method.values():
            for acc in per_break.values():
                if acc.energy > 0:
                    acc.shares = {k: v / acc.energy for k, v in acc.shares.items()}
    return out, degenerate, unrealisable


#: "shipped" is the control, not a candidate: it must reproduce
#: `transform.through`, which proves the labels and the integration here are
#: the ones the forecast uses before either of the other two is compared.
METHODS = {"fourier": fourier, "mem": mem, "shipped": shipped}

SWELL = (WIND_SEA_PERIOD_S, 1e9)
WIND_SEA = (0.0, WIND_SEA_PERIOD_S)
BANDS = {"all periods": None, f"swell (>= {WIND_SEA_PERIOD_S:g} s)": SWELL,
         f"wind sea (< {WIND_SEA_PERIOD_S:g} s)": WIND_SEA}
CATEGORIES = (IN_WINDOW, "Point Loma peninsula", "Baja peninsula", ISLANDS, SEAWARD_CLIP)


@dataclass
class Report:
    n_spectra: int
    skipped_bins: int
    unrealisable_bins: int
    total_bins: int
    #: worst |r1 error| and |α1 error| of MEM against the buoy, archive-wide
    mem_moment_error: tuple[float, float]
    #: worst |in-window fraction| gap between the shipped form here and
    #: `transform.through` at the south break -- should be ~0
    shipped_gap: float
    #: in-window percentage points between Fourier as compared here
    #: (renormalised, realisable bins only) and as shipped, every break and
    #: spectrum -- how far the comparison baseline sits from the forecast
    renorm_pts: list[float]
    #: rows[band][break][category] = (fourier values, mem values), one per spectrum
    rows: dict[str, dict[str, dict[str, tuple[list[float], list[float]]]]]
    #: in-window Hs ratio (MEM / Fourier) per break, all periods
    hs_ratio: dict[str, list[float]]
    #: the peak-bin α1 per spectrum, for splitting by incoming direction
    peak_dir: list[float]


def build(directory: Path = DEFAULT_SPECTRA) -> Report:
    spots, blockers = load()
    by_id = {s.id: s for s in spots}
    marks = {sid: labels(by_id[sid], blockers) for sid in BREAKS}
    spectra = load_spectra(directory)

    rows = {band: {sid: {c: ([], []) for c in CATEGORIES} for sid in BREAKS} for band in BANDS}
    hs_ratio = {sid: [] for sid in BREAKS}
    peak_dir: list[float] = []
    skipped = unreal = bins = 0
    worst_r1 = worst_a1 = worst_gap = 0.0
    renorm: list[float] = []
    used = 0

    for sp in spectra:
        good = [i for i, e in enumerate(sp.c11) if e == e and e > 0]
        if not good:
            continue
        bins += len(good)
        peak = max(good, key=lambda i: sp.c11[i])
        results, degenerate, unrealisable = split(sp, marks, BANDS)
        skipped += degenerate
        unreal += unrealisable
        fo_all, me_all = results["all periods"]["fourier"], results["all periods"]["mem"]
        if not any(fo_all[sid].energy > 0 for sid in BREAKS):
            continue
        used += 1
        peak_dir.append(sp.a1[peak] % 360.0)
        for band_name, per_method in results.items():
            fo, me = per_method["fourier"], per_method["mem"]
            for sid in BREAKS:
                for c in CATEGORIES:
                    rows[band_name][sid][c][0].append(fo[sid].shares.get(c, 0.0))
                    rows[band_name][sid][c][1].append(me[sid].shares.get(c, 0.0))
        for sid in BREAKS:
            f_in = fo_all[sid].shares.get(IN_WINDOW, 0.0)
            m_in = me_all[sid].shares.get(IN_WINDOW, 0.0)
            hs_ratio[sid].append(math.sqrt(m_in / f_in) if f_in > 0 else float("nan"))
            s_in = results["all periods"]["shipped"][sid].shares.get(IN_WINDOW, 0.0)
            renorm.append(100 * (f_in - s_in))
            if sid == "coronado_south":
                fraction = through(sp, by_id[sid], blockers).fraction
                if fraction == fraction:
                    worst_gap = max(worst_gap, abs(fraction - s_in))

        # The control, on the peak bin of every spectrum.
        i = peak
        if sp.r1[i] < R1_CEILING:
            try:
                r1, a1, _, _ = moments(mem(sp.r1[i], sp.r2[i], sp.a1[i], sp.a2[i]))
            except Unrealisable:
                pass
            else:
                worst_r1 = max(worst_r1, abs(r1 - sp.r1[i]))
                worst_a1 = max(worst_a1, abs(_relative(a1, sp.a1[i])))

    return Report(used, skipped, unreal, bins, (worst_r1, worst_a1), worst_gap, renorm,
                  rows, hs_ratio, peak_dir)


def _pct(values: list[float], q: float) -> float:
    ordered = sorted(v for v in values if v == v)
    if not ordered:
        return float("nan")
    k = (len(ordered) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


SHORT = {IN_WINDOW: "in window", "Point Loma peninsula": "Point Loma",
         "Baja peninsula": "Baja", ISLANDS: "islands", SEAWARD_CLIP: "behind beach"}

#: Incoming-direction sectors for the split by where the swell is aimed.
SECTORS = ((100, 200, "S of the islands"), (200, 240, "into the windows"),
           (240, 262, "at Point Loma's edges"), (262, 360, "behind Point Loma"))


def format_report(r: Report) -> str:
    out = [
        f"{r.n_spectra} spectra from 46232, {r.total_bins} energy bins; left out of "
        f"BOTH methods: {r.skipped_bins} degenerate (r1 >= {R1_CEILING}), "
        f"{r.unrealisable_bins} unrealisable ({100 * r.unrealisable_bins / max(r.total_bins, 1):.1f}%).",
        f"control: MEM reproduces the buoy's moments to |r1| {r.mem_moment_error[0]:.1e}, "
        f"|a1| {r.mem_moment_error[1]:.1e} deg (worst, peak bin).",
        f"control: shipped Fourier here vs transform.through (south, in-window "
        f"fraction), worst gap {r.shipped_gap:.1e}.",
        f"Fourier as compared here (renormalised, realisable bins) vs as shipped, in-window: "
        f"{_pct(r.renorm_pts, .5):+.2f} pts median [{_pct(r.renorm_pts, .1):+.2f}, "
        f"{_pct(r.renorm_pts, .9):+.2f}]; worst {max(r.renorm_pts, key=abs):+.2f}.",
        "",
        "Mean share of energy, Fourier -> MEM, and the MEM-minus-Fourier gap in",
        "percentage points (median [10th, 90th percentile] across spectra):",
    ]
    for band, per_break in r.rows.items():
        out.append(f"\n  {band}")
        for sid in BREAKS:
            bits = []
            for c in CATEGORIES:
                fo, me = per_break[sid][c]
                diff = [100 * (m - f) for f, m in zip(fo, me)]
                bits.append(
                    f"{SHORT[c]} {100 * statistics.fmean(fo):.1f}->{100 * statistics.fmean(me):.1f}"
                    f" ({_pct(diff, .5):+.1f} [{_pct(diff, .1):+.1f},{_pct(diff, .9):+.1f}])")
            out.append(f"    {sid.split('_')[1]:6s} " + " | ".join(bits))
    out.append("\nIn-window Hs, MEM / Fourier, all periods: median [10th, 90th]")
    for sid in BREAKS:
        v = r.hs_ratio[sid]
        out.append(f"    {sid.split('_')[1]:6s} {_pct(v, .5):.3f} [{_pct(v, .1):.3f}, {_pct(v, .9):.3f}]")
    out.append("\nThe differential (BRIEFING §11): in-window Hs south / north, all periods,")
    out.append("median [10th, 90th], Fourier then MEM:")
    for band in ("all periods", f"swell (>= {WIND_SEA_PERIOD_S:g} s)"):
        south = r.rows[band]["coronado_south"][IN_WINDOW]
        north = r.rows[band]["coronado_north"][IN_WINDOW]
        ratios = []
        for k in (0, 1):
            ratios.append([math.sqrt(s_ / n_) for s_, n_ in zip(south[k], north[k]) if n_ > 0])
        out.append(f"    {band:18s} " + "  ->  ".join(
            f"{_pct(v, .5):.3f} [{_pct(v, .1):.3f}, {_pct(v, .9):.3f}]" for v in ratios))
    out.append("\nBy where the peak bin is aimed (buoy a1), all periods, south break,")
    out.append("in-window share Fourier -> MEM (mean):")
    fo_all, me_all = r.rows["all periods"]["coronado_south"][IN_WINDOW]
    for lo, hi, name in SECTORS:
        idx = [k for k, d in enumerate(r.peak_dir) if lo <= d < hi]
        if not idx:
            out.append(f"    {lo:3d}-{hi:3d} {name:22s} n=0")
            continue
        f = statistics.fmean(fo_all[k] for k in idx)
        m = statistics.fmean(me_all[k] for k in idx)
        out.append(f"    {lo:3d}-{hi:3d} {name:22s} n={len(idx):4d}  "
                   f"{100 * f:.1f} -> {100 * m:.1f} ({100 * (m - f):+.1f} pts)")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spectra", type=Path, default=DEFAULT_SPECTRA)
    args = parser.parse_args(argv)
    print(format_report(build(args.spectra)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
