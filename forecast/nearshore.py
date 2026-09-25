"""The buoy's spectrum carried to 5 m of water off each break, and local chop.

    python -m forecast.nearshore            # compare against the aperture, archive-wide

Pure Python; reads the transfer tables `forecast.raytrace` writes to
`data/nearshore/` and never needs numpy.

WHAT IT GIVES, per break and spectrum:

- `hs_ref` — Hs at the table's start point, `raytrace.H_REF` (5) metres of
  water off the break: refraction over the seabed, shoaling, Point Loma and Baja as land,
  the Coronado Islands as Fresnel diffraction. Linear theory, no breaking.
- `hs_equivalent` — the same with shoaling divided back out, per frequency:
  refraction and sheltering only. This is the like-for-like against the
  aperture's `hs_in_window_m`, which has no seabed at all.
- `hs_islands_geometric` / `hs_no_islands` — the same as `hs_equivalent` with
  the islands as a hard shadow, and with no islands, so their effect is a
  measured difference rather than a claim.
- `local` — fetch-limited wind sea from the measured wind, only where the
  fetch upwind of the break is closed by land (`raytrace.fetch_table`).

WHAT IT IS NOT. None of it has been observed. It is "physically derived" in
the project's sense: every step is textbook physics on charted and surveyed
inputs, and nothing has checked the result against the beach. The step from
here to a face height at the sand needs the observation log, which is empty.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .transform import Spectrum, load_spectra, through

ROOT = Path(__file__).resolve().parent.parent
TABLE_DIR = ROOT / "data" / "nearshore"
BREAKS = ("coronado_north", "coronado_center", "coronado_south")
G = 9.81
KT_TO_MS = 0.514444


# ------------------------------------------------------------------ tables

@dataclass
class Ray:
    near_from: float
    width_rad: float
    off_from: float
    gain: float
    island_factor: float
    island_geometric: float


@dataclass
class Table:
    break_id: str
    start_depth_m: float
    by_freq: dict[float, list[Ray]]
    fetch: list[tuple[float, bool]] = field(default_factory=list)   # index = wind_from_deg

    @classmethod
    def load(cls, break_id: str, directory: Path = TABLE_DIR) -> "Table":
        meta = json.loads((directory / f"{break_id}.json").read_text())
        by_freq: dict[float, list[Ray]] = {}
        with (directory / f"{break_id}.csv").open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                gain = float(row["gain"])
                if gain <= 0.0:
                    continue          # a ray that lands carries nothing
                by_freq.setdefault(float(row["freq_hz"]), []).append(Ray(
                    float(row["near_from_deg"]), math.radians(float(row["near_width_deg"])),
                    float(row["off_from_deg"]), gain,
                    float(row["island_factor"]), float(row["island_geometric"])))
        fetch = []
        path = directory / f"{break_id}_fetch.csv"
        if path.exists():
            with path.open(newline="", encoding="utf-8") as fh:
                fetch = [(float(r["fetch_km"]), r["closed"] == "1") for r in csv.DictReader(fh)]
        return cls(break_id, float(meta["start_depth_m"]), by_freq, fetch)


# ------------------------------------------------------------------ physics

def wavenumber(omega: float, h: float) -> float:
    k0 = omega * omega / G
    k = k0 / math.sqrt(math.tanh(k0 * h))
    for _ in range(8):
        th = math.tanh(k * h)
        k -= (G * k * th - omega * omega) / (G * th + G * k * h * (1 - th * th))
    return k


def shoaling_squared(freq: float, h: float) -> float:
    """Ks² = cg0 / cg(h) — the part of the gain that is not refraction."""

    omega = 2 * math.pi * freq
    k = wavenumber(omega, h)
    c = omega / k
    two_kh = 2 * k * h
    # Past 2kh ~ 50 the correction is below 1e-20 and sinh overflows first.
    cg = 0.5 * c * (1 + (two_kh / math.sinh(two_kh) if two_kh < 50 else 0.0))
    return (0.5 * G / omega) / cg


# ------------------------------------------------------------------ spectra

def fourier_density(spectrum: Spectrum, index: int) -> list[float]:
    """The shipped D(θ)·c11 on a 1° grid, per radian (transform.Spectrum.density)."""

    return [spectrum.density(index, n + 0.5) for n in range(360)]


def at(grid: list[float], deg: float) -> float:
    """Linear interpolation on a 1°-centred circular grid."""

    pos = (deg - 0.5) % 360.0
    i = int(pos)
    frac = pos - i
    return grid[i] * (1 - frac) + grid[(i + 1) % 360] * frac


@dataclass
class Nearshore:
    break_id: str
    hs_ref: float
    hs_equivalent: float
    hs_islands_geometric: float
    hs_no_islands: float
    #: Energy-weighted mean heading AT 10 m and where that energy came from.
    near_from_deg: float
    off_from_deg: float
    peak_period_s: float
    unmatched_bins: int = 0


def carry(spectrum: Spectrum, table: Table, density=fourier_density) -> Nearshore:
    """Integrate S_off(f, θ0)·gain over the nearshore headings, per frequency."""

    freqs = sorted(table.by_freq)
    e10 = e_eq = e_geo = e_none = 0.0
    sn = cn = so = co = 0.0
    best_bin, best_energy = None, -1.0
    unmatched = 0
    for i, f in enumerate(spectrum.frequencies):
        c11 = spectrum.c11[i]
        if not (c11 > 0) or math.isnan(c11):
            continue
        near = min(freqs, key=lambda t: abs(t - f))
        if abs(near - f) > 0.05 * f:
            unmatched += 1
            continue
        grid = density(spectrum, i)
        width = spectrum.bin_width(i)
        ks2 = shoaling_squared(f, table.start_depth_m)
        bin_e = 0.0
        for ray in table.by_freq[near]:
            s = at(grid, ray.off_from) * width * ray.width_rad * ray.gain
            e = s * ray.island_factor
            e10 += e
            bin_e += e
            e_eq += e / ks2
            e_geo += s * ray.island_geometric / ks2
            e_none += s / ks2
            t = math.radians(ray.near_from)
            sn += e * math.sin(t); cn += e * math.cos(t)
            t = math.radians(ray.off_from)
            so += e * math.sin(t); co += e * math.cos(t)
        if bin_e > best_energy:
            best_bin, best_energy = f, bin_e
    hs = lambda m0: 4.0 * math.sqrt(max(m0, 0.0))
    return Nearshore(
        table.break_id, hs(e10), hs(e_eq), hs(e_geo), hs(e_none),
        math.degrees(math.atan2(sn, cn)) % 360 if e10 > 0 else float("nan"),
        math.degrees(math.atan2(so, co)) % 360 if e10 > 0 else float("nan"),
        1.0 / best_bin if best_bin else float("nan"), unmatched)


# ------------------------------------------------------------------ local sea

@dataclass
class LocalSea:
    hs_m: float
    tp_s: float
    from_deg: float
    fetch_km: float


def local_sea(table: Table, normal_deg: float, wind_kt: float | None,
              wind_from_deg: float | None) -> LocalSea | None:
    """Fetch-limited wind sea (Coastal Engineering Manual, 2002, II-2).

    With u*² = C_D·U10², C_D = 0.001·(1.1 + 0.035·U10):
      g·Hm0/u*² = 4.13e-2·(g·X/u*²)^½,  g·Tp/u* = 0.751·(g·X/u*²)^⅓,
    capped at the fully developed 211.5 and 239.8. Steady wind assumed; a gust
    front younger than its fetch-limited growth time would be overstated.

    Only for a wind blowing FROM the break's seaward half-plane (its waves run
    downwind, onto the beach) and only over a CLOSED fetch: an open one is
    already in the buoy's spectrum.
    """

    if wind_kt is None or wind_from_deg is None or not table.fetch or wind_kt <= 0:
        return None
    off = ((wind_from_deg - normal_deg + 180.0) % 360.0) - 180.0
    if abs(off) >= 90.0:
        return None
    fetch_km, closed = table.fetch[int(round(wind_from_deg)) % 360]
    if not closed:
        return None
    u10 = wind_kt * KT_TO_MS
    ustar = math.sqrt(0.001 * (1.1 + 0.035 * u10)) * u10
    x = G * fetch_km * 1000.0 / ustar ** 2
    hs = min(4.13e-2 * math.sqrt(x), 211.5) * ustar ** 2 / G
    tp = min(0.751 * x ** (1.0 / 3.0), 239.8) * ustar / G
    return LocalSea(hs, tp, wind_from_deg, fetch_km)


# ------------------------------------------------------------------ report

def _pct(values, q):
    ordered = sorted(v for v in values if v == v)
    if not ordered:
        return float("nan")
    k = (len(ordered) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def report(spectra: list[Spectrum]) -> str:
    from .geometry import load

    spots, blockers = load()
    by_id = {s.id: s for s in spots}
    tables = {sid: Table.load(sid) for sid in BREAKS}
    rows = {sid: [] for sid in BREAKS}
    for sp in spectra:
        for sid in BREAKS:
            ap = through(sp, by_id[sid], blockers)
            if not (ap.hs_in_window_m > 0):
                continue
            ns = carry(sp, tables[sid])
            rows[sid].append((ap.hs_in_window_m, ns, math.degrees(0)))
    out = [f"{len(spectra)} spectra from 46232. Ratios are nearshore / aperture, "
           "median [10th, 90th]."]
    for sid in BREAKS:
        r = rows[sid]
        if not r:
            continue
        ap = [a for a, _, _ in r]
        eq = [n.hs_equivalent / a for a, n, _ in r]
        h10 = [n.hs_ref / a for a, n, _ in r]
        isl_d = [1 - n.hs_equivalent / n.hs_no_islands for _, n, _ in r if n.hs_no_islands > 0]
        isl_g = [1 - n.hs_islands_geometric / n.hs_no_islands for _, n, _ in r if n.hs_no_islands > 0]
        out.append(f"\n  {sid}  (n = {len(r)}, aperture Hs median {_pct(ap, .5):.2f} m)")
        out.append(f"    refraction + sheltering, no shoaling: {_pct(eq, .5):.3f} "
                   f"[{_pct(eq, .1):.3f}, {_pct(eq, .9):.3f}]")
        out.append(f"    at {tables[sid].start_depth_m:.0f} m with shoaling:         {_pct(h10, .5):.3f} "
                   f"[{_pct(h10, .1):.3f}, {_pct(h10, .9):.3f}]")
        out.append(f"    height the islands take, diffracted: {100 * _pct(isl_d, .5):.1f}% "
                   f"[{100 * _pct(isl_d, .1):.1f}, {100 * _pct(isl_d, .9):.1f}]  "
                   f"| as a hard shadow: {100 * _pct(isl_g, .5):.1f}% "
                   f"[{100 * _pct(isl_g, .1):.1f}, {100 * _pct(isl_g, .9):.1f}]")
    south = rows["coronado_south"]
    north = rows["coronado_north"]
    if south and north and len(south) == len(north):
        ap_ratio = [s[0] / n[0] for s, n in zip(south, north)]
        ns_ratio = [s[1].hs_equivalent / n[1].hs_equivalent for s, n in zip(south, north)
                    if n[1].hs_equivalent > 0]
        out.append("\n  south / north (the differential, BRIEFING §11):")
        out.append(f"    aperture   {_pct(ap_ratio, .5):.3f} [{_pct(ap_ratio, .1):.3f}, {_pct(ap_ratio, .9):.3f}]")
        out.append(f"    nearshore  {_pct(ns_ratio, .5):.3f} [{_pct(ns_ratio, .1):.3f}, {_pct(ns_ratio, .9):.3f}]")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)
    spectra = load_spectra(ROOT / "data" / "spectra" / "46232", limit=args.limit)
    print(report(spectra))
    return 0


if __name__ == "__main__":
    sys.exit(main())
