"""The buoy's spectrum carried to 5 m of water off each break, and local chop.

    python -m forecast.nearshore            # compare against the aperture, archive-wide

Pure Python; reads the transfer tables `forecast.raytrace` writes to
`data/nearshore/` and never needs numpy.

WHAT IT GIVES, per break and spectrum:

- `hs_ref` — Hs at the table's start point, `raytrace.H_REF` (5) metres of
  water off the break: refraction over the seabed (the islands' own shelves
  included), shoaling, and diffraction at every window edge — the Coronado
  Islands, the Point Loma tip and the Baja tangent. Linear theory, no breaking.
- `hs_equivalent` — the same with shoaling divided back out, per frequency,
  and without bottom friction.
- `hs_friction` — `hs_equivalent` after bottom friction along each ray's
  path (JONSWAP law, `raytrace.friction_rate`). `hs_ref` includes it.
- `hs_hard` — refraction with every window edge a HARD shadow and shoaling
  divided out. Against the aperture's `hs_in_window_m` (straight lines, hard
  edges) it is the seabed alone; `hs_equivalent` against it is diffraction
  alone, measured rather than claimed.
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
    #: Hard window edges: the gain at `off_from`, 0 for a ray the land stops.
    gain: float
    #: Diffracting window edges: the gain at `diff_off_from` — the same heading
    #: for a ray that clears every edge, and the heading of the energy that
    #: diffracts round the edge for one that does not (raytrace.table).
    diff_off_from: float
    diff_gain: float
    #: Share of each answer's energy flux left after bottom friction along its
    #: path over the shelf. Stored apart from the gains so friction can be
    #: stated as its own effect; 1 for a table built before it was modelled.
    friction: float = 1.0
    diff_friction: float = 1.0


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
                gain, diff_gain = float(row["gain"]), float(row["diff_gain"])
                if gain <= 0.0 and diff_gain <= 0.0:
                    continue          # carries nothing, hard or soft
                by_freq.setdefault(float(row["freq_hz"]), []).append(Ray(
                    float(row["near_from_deg"]), math.radians(float(row["near_width_deg"])),
                    float(row["off_from_deg"]), gain,
                    float(row["diff_off_from_deg"]), diff_gain,
                    float(row.get("friction") or 1.0),
                    float(row.get("diff_friction") or 1.0)))
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

def density_grids(spectrum) -> dict[int, list[float]]:
    """E(f, θ) on a 1° grid per frequency bin, per radian, from whatever the
    spectrum is: an NDBC `Spectrum` (Fourier or MEM, its own `spread`) or a
    WAVEWATCH III `GridSpectrum`. Computed once per spectrum and shared by
    the three breaks."""

    out = {}
    for i, c11 in enumerate(spectrum.c11):
        if c11 > 0 and not math.isnan(c11):
            out[i] = [spectrum.density(i, n + 0.5) for n in range(360)]
    return out


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
    hs_hard: float
    #: Energy-weighted mean heading AT the start depth and where that energy
    #: came from offshore.
    near_from_deg: float
    off_from_deg: float
    peak_period_s: float
    unmatched_bins: int = 0
    #: Shoaling divided out, bottom friction in: between `hs_equivalent` and
    #: `hs_ref` in the chain of effects. None from a caller that predates it.
    hs_friction: float | None = None
    #: The arriving energy split into trains, each headed by where its energy
    #: came FROM offshore — the frame the window drawing is in.
    trains: list = field(default_factory=list)


def carry(spectrum, table: Table, grids: dict[int, list[float]] | None = None) -> Nearshore:
    """Integrate S_off(f, θ0)·gain over the nearshore headings, per frequency."""

    from .transform import split_trains

    grids = density_grids(spectrum) if grids is None else grids
    freqs = sorted(table.by_freq)
    e10 = e_eq = e_hard = e_fric = 0.0
    sn = cn = so = co = 0.0
    per_bin: list[tuple[int, float]] = []
    bin_sin: dict[int, float] = {}
    bin_cos: dict[int, float] = {}
    unmatched = 0
    for i, f in enumerate(spectrum.frequencies):
        grid = grids.get(i)
        if grid is None:
            continue
        near = min(freqs, key=lambda t: abs(t - f))
        if abs(near - f) > 0.05 * f:
            unmatched += 1
            continue
        width = spectrum.bin_width(i)
        ks2 = shoaling_squared(f, table.start_depth_m)
        bin_e = bs = bc = 0.0
        for ray in table.by_freq[near]:
            if ray.gain > 0:
                e_hard += at(grid, ray.off_from) * width * ray.width_rad * ray.gain / ks2
            if ray.diff_gain <= 0:
                continue
            e = at(grid, ray.diff_off_from) * width * ray.width_rad * ray.diff_gain
            e_eq += e / ks2
            e *= ray.diff_friction
            e_fric += e / ks2
            e10 += e
            bin_e += e
            t = math.radians(ray.near_from)
            sn += e * math.sin(t); cn += e * math.cos(t)
            t = math.radians(ray.diff_off_from)
            so += e * math.sin(t); co += e * math.cos(t)
            bs += e * math.sin(t); bc += e * math.cos(t)
        per_bin.append((i, bin_e))
        bin_sin[i], bin_cos[i] = bs, bc
    peak = max(per_bin, key=lambda item: item[1]) if per_bin else None
    hs = lambda m0: 4.0 * math.sqrt(max(m0, 0.0))
    return Nearshore(
        table.break_id, hs(e10), hs(e_eq), hs(e_hard),
        math.degrees(math.atan2(sn, cn)) % 360 if e10 > 0 else float("nan"),
        math.degrees(math.atan2(so, co)) % 360 if e10 > 0 else float("nan"),
        1.0 / spectrum.frequencies[peak[0]] if peak and peak[1] > 0 else float("nan"),
        unmatched,
        hs(e_fric),
        split_trains(per_bin, spectrum.frequencies, bin_sin, bin_cos) if e10 > 0 else [],
    )


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


# ------------------------------------------------------------------ surfaces

def train_dicts(trains) -> list[dict]:
    return [
        {
            "hs_m": round(t.hs_m, 3),
            "period_s": round(t.period_s, 1),
            "from_deg": None if math.isnan(t.from_deg) else round(t.from_deg),
            "share": round(t.share, 4),
            "wind_sea": t.is_wind_sea,
        }
        for t in trains
    ]


def summarise(near: Nearshore, local: LocalSea | None, *, buoy_hs_m: float,
              window_hs_m: float, depth_m: float, profile=None, tide_m: float | None = None,
              normal_deg: float | None = None) -> dict:
    """What a surface shows for one break: the number, its trains, and the
    chain of effects that turned the buoy's reading into it.

    The swell at the start depth and local chop add in energy — different
    waves on the same water, and heights of independent trains add as
    squares. Local chop is listed as its own train, tagged.

    With a `profile` and the open-coast `tide_m`, that sea is then carried in
    to where it breaks (`forecast.surfzone`), and `hs_m` is the breaking
    height. The trains are scaled with it, all by the same factor: a bulk
    breaking model dissipates each part of the spectrum in proportion to its
    energy (as SWAN distributes Battjes-Janssen), so the trains still sum to
    the number above them. Without a profile or a tide, `hs_m` stays the
    figure at the start depth and `breaking` is None — never a breaking height
    at an assumed tide.
    """

    from .surfzone import break_on

    local_hs = local.hs_m if local else 0.0
    total = math.sqrt(near.hs_ref ** 2 + local_hs ** 2)
    trains = train_dicts(near.trains[:3])
    if local:
        trains.append({"hs_m": round(local.hs_m, 3), "period_s": round(local.tp_s, 1),
                       "from_deg": round(local.from_deg), "share": None,
                       "wind_sea": True, "local": True})
    broke = None
    if profile is not None and tide_m is not None and total > 0:
        period = near.peak_period_s if near.peak_period_s == near.peak_period_s else (
            local.tp_s if local else float("nan"))
        angle = (((near.near_from_deg - normal_deg + 180.0) % 360.0) - 180.0
                 if normal_deg is not None and near.near_from_deg == near.near_from_deg else 0.0)
        broke = break_on(profile, hs_start_m=total, period_s=period,
                         start_depth_m=depth_m, angle_deg=angle, tide_m=tide_m)
    headline = broke.hs_m if broke else total
    if broke and total > 0:
        scale = headline / total
        for t in trains:
            t["hs_m"] = round(t["hs_m"] * scale, 3)
    return {
        "hs_m": round(headline, 3),
        "depth_m": round(depth_m, 1),
        "trains": trains,
        "breaking": broke.as_dict() if broke else None,
        "effects": {
            "buoy_hs_m": round(buoy_hs_m, 3),
            "window_hs_m": round(window_hs_m, 3),
            # Refraction alone: bent rays with every window edge still a hard
            # shadow, as the straight-line window treats them, so window ->
            # refracted is the seabed and nothing else. Diffraction alone:
            # the same rays with every edge diffracting (islands, Point Loma
            # tip, Baja tangent), so refracted -> diffracted is that and
            # nothing else. Then bottom friction, then shoaling divided
            # back in.
            "refracted_hs_m": round(near.hs_hard, 3),
            "diffracted_hs_m": round(near.hs_equivalent, 3),
            # Bottom friction along each ray's path, shoaling still out.
            "friction_hs_m": round(near.hs_friction if near.hs_friction is not None
                                   else near.hs_equivalent, 3),
            "shoaled_hs_m": round(near.hs_ref, 3),
            # Swell and local chop together at the start depth: what breaking
            # starts from.
            "with_chop_hs_m": round(total, 3),
            "local": ({"hs_m": round(local.hs_m, 3), "tp_s": round(local.tp_s, 1),
                       "from_deg": round(local.from_deg), "fetch_km": round(local.fetch_km, 1)}
                      if local else None),
        },
    }


def spectrum_from_partitions(parts: list[tuple[float, float, float, bool]], time,
                             frequencies: list[float]) -> Spectrum:
    """A buoy-style spectrum rebuilt from GFS-Wave partitions, for the
    fallback path when the model's own directional grid is unavailable.

    Each (hs, tp, from_deg, wind_sea) becomes a Pierson-Moskowitz shape with
    the energy its Hs demands, and the assumed spread
    (`transform.spread_for`, BRIEFING §11) as its circular moments; the
    partitions add per frequency as energy and as moment vectors. Read back
    by maximum entropy, like the observed buoy. The assumed spread is exactly
    what the spectral path exists to avoid, and the forecast says which it
    used (`wave_source`).
    """

    import cmath

    from .transform import moments_for_spread, spread_for

    n = len(frequencies)
    width = [(frequencies[min(i + 1, n - 1)] - frequencies[max(i - 1, 0)])
             / (2.0 if 0 < i < n - 1 else 1.0) for i in range(n)]
    c11 = [0.0] * n
    m1 = [0j] * n
    m2 = [0j] * n
    for hs, tp, from_deg, wind_sea in parts:
        if not hs or not tp or hs <= 0 or tp <= 0:
            continue
        fp = 1.0 / tp
        shape = [math.exp(-1.25 * (fp / f) ** 4) * (f / fp) ** -5 if f > 0 else 0.0
                 for f in frequencies]
        m0 = sum(v * w for v, w in zip(shape, width)) or 1.0
        scale = (hs / 4.0) ** 2 / m0
        r1, r2 = moments_for_spread(spread_for(tp, wind_sea))
        a = math.radians(from_deg)
        for i, v in enumerate(shape):
            e = v * scale
            c11[i] += e
            m1[i] += e * r1 * cmath.exp(1j * a)
            m2[i] += e * r2 * cmath.exp(2j * a)
    a1, a2, r1s, r2s = [], [], [], []
    for i in range(n):
        if c11[i] > 0:
            v1, v2 = m1[i] / c11[i], m2[i] / c11[i]
            r1s.append(abs(v1)); a1.append(math.degrees(cmath.phase(v1)) % 360.0)
            r2s.append(abs(v2)); a2.append((math.degrees(cmath.phase(v2)) / 2.0) % 180.0)
        else:
            r1s.append(0.0); a1.append(0.0); r2s.append(0.0); a2.append(0.0)
    return Spectrum(time, list(frequencies), c11, a1, a2, r1s, r2s, spread="mem")


def table_frequencies(tables: dict[str, "Table"]) -> list[float]:
    return sorted(next(iter(tables.values())).by_freq) if tables else []


def load_tables(directory: Path = TABLE_DIR) -> dict[str, Table]:
    return {sid: Table.load(sid, directory) for sid in BREAKS}


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
        # What ships reads the buoy by maximum entropy; so does this report.
        sp = sp.with_spread("mem")
        grids = density_grids(sp)
        for sid in BREAKS:
            ap = through(sp, by_id[sid], blockers)
            if not (ap.hs_in_window_m > 0):
                continue
            ns = carry(sp, tables[sid], grids)
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
        refr = [n.hs_hard / a for a, n, _ in r]
        diff = [n.hs_equivalent / n.hs_hard - 1 for _, n, _ in r if n.hs_hard > 0]
        fric = [n.hs_friction / n.hs_equivalent - 1 for _, n, _ in r
                if n.hs_equivalent > 0 and n.hs_friction is not None]
        out.append(f"\n  {sid}  (n = {len(r)}, aperture Hs median {_pct(ap, .5):.2f} m)")
        out.append(f"    refraction, hard edges:               {_pct(refr, .5):.3f} "
                   f"[{_pct(refr, .1):.3f}, {_pct(refr, .9):.3f}]")
        out.append(f"    + diffraction at every edge:          {_pct(eq, .5):.3f} "
                   f"[{_pct(eq, .1):.3f}, {_pct(eq, .9):.3f}]")
        out.append(f"    at {tables[sid].start_depth_m:.0f} m with shoaling:         {_pct(h10, .5):.3f} "
                   f"[{_pct(h10, .1):.3f}, {_pct(h10, .9):.3f}]")
        out.append(f"    height diffraction adds to hard edges: {100 * _pct(diff, .5):+.1f}% "
                   f"[{100 * _pct(diff, .1):+.1f}, {100 * _pct(diff, .9):+.1f}]")
        if fric:
            out.append(f"    height bottom friction takes:         {100 * _pct(fric, .5):+.2f}% "
                       f"[{100 * _pct(fric, .1):+.2f}, {100 * _pct(fric, .9):+.2f}]; "
                       f"worst {100 * min(fric):+.1f}%")
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
