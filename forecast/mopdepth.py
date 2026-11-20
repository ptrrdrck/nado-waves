"""The chain's own rays from CDIP MOP's points: the place, or the tables?

    python -m forecast.mopdepth [--break B] [--control] [--out docs/mop_depth.md]

PRECOMPUTE-SIDE AND REPORT-ONLY: it imports `forecast.raytrace` (numpy), so
nothing on a production path may import it, and no workflow runs it. It
reads `data/mop/` (`collector.mop`, Actions) and the archived 46232 spectra,
builds transfer tables with `raytrace.table` itself, and **reports and never
edits**. MOP is a model, not an observation (CLAUDE.md).

`forecast.mopcheck` (BRIEFING §56a) found the chain lets more energy into
Center and South than MOP from every direction. The chain starts 130-230 m
off the break at 5 m; MOP's points are ~10 m deep and 0.6-1.4 km away. This
module separates the two by tracing the chain's own rays from three starts
per break, the same frequencies, 0.5° headings, islands and diffracting edges
as shipped, no Madsen (before friction, as MOP):

- `break_5m`   — the shipped start (and the control: it must give the
  committed `data/nearshore/<break>.csv` back row for row);
- `normal_mop` — the break's own normal, out to the seabed's depth at the
  MOP point: beside the MOP point at South, but ~3 km out on the open shelf
  at Center and North, where the ~11 m contour on the normal lies;
- `mop`        — at the MOP point itself (2 m seaward of it along the break's
  normal, `MOP_H_REF`), fan centred on the break's normal; plus `mop_back`,
  the opposite half-fan, so a point whose seabed faces another way is not
  short of headings (its rays are added to `mop`'s).

Built tables go to `data/live/mopdepth/` (gitignored; ~3 min a table).

**A point that is not a break** (handoff 24b; `collector.mop --points
extra`, filed under `points.json`'s `"points"`): there is no break, so no
`break_5m` or `normal_mop`; `mop` and `mop_back` only, the fan centred on
MOP's own `metaShoreNormal`, held exactly (`PointSpot`), so nothing is
digitised for it. Its hours are cut to those in every break's MOP series,
and "Exposed against shadowed" sets its band ratios beside the breaks' on
the hours all of them share. Control: the same path, given Center's MOP
point and Center's normal, gives Center's `mop` table back row for row.

**MOP's own spectrum** (handoff item 24a), when `collector.mop` has saved it
and its read-back passed: both sides are set on common period bands
(`BAND_EDGES_HZ`), each side's bins split by where their edges overlap.
MOP is de-shoaled band by band at each band's own frequency from its depth;
chain-at-MOP is already deep-water-equivalent per 46232 bin. Per band:
chain-at-MOP over MOP, and each over 46232's own energy in the band, so a
band MOP is short in reads apart from one the chain is long in. With the
moments, MOP's mean direction per band beside the heading chain-at-MOP's
energy arrives on, once MOP's a1/b1 convention has been read off its own Dp.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import raytrace as rt
from .geometry import Spot, open_windows
from .mopcheck import MATCH_S, SECTORS, ks, mean_from, read_mop

ROOT = Path(__file__).resolve().parent.parent
MOP_DIR = ROOT / "data" / "mop"
CACHE = ROOT / "data" / "live" / "mopdepth"
VARIANTS = ("break_5m", "normal_mop", "mop", "mop_back")
#: Start depth at a MOP point: below the seabed there (10.8-11.0 m MSL), so
#: `start_point` stops at its first step, 2 m seaward along the normal.
MOP_H_REF = 10.0
#: Swell period bands (s) of 46232's swell peak for the by-period split.
PERIOD_BANDS = ((8, 11), (11, 14), (14, 17), (17, 26))
KINDS = ("clear", "island fill", "Point Loma fill", "Baja fill")
#: Upper frequency (Hz) of the chain-at-MOP energy set against MOP's whole
#: Hs: where in frequency the excess builds (0.58 is everything).
CUTS_HZ = (0.1, 0.125, 0.15, 0.2, 0.25, 0.58)
#: Period bands for the per-band comparison, as frequency edges (Hz): > 16.7,
#: 13–16.7, 10–13, 8–10, 6.7–8, 5–6.7, 4–5, < 4 s. The outer two are clipped
#: to the range both MOP's bands and 46232's bins cover.
BAND_EDGES_HZ = (0.0, 0.06, 1 / 13, 0.1, 0.125, 0.15, 0.2, 0.25, 1.0)
#: A band-hour is compared only when 46232 has at least this height in it (m).
BAND_MIN_HS = 0.05
#: How MOP's a1/b1 might map to a direction FROM, clockwise from north; the
#: one that agrees with MOP's own Dp at its peak band is used (`convention`).
CONVENTIONS = {
    "from, clockwise from north: atan2(b1, a1)": lambda t: t % 360,
    "toward, clockwise from north: atan2(b1, a1) + 180": lambda t: (t + 180) % 360,
    "toward, counter-clockwise from east: 270 - atan2(b1, a1)": lambda t: (270 - t) % 360,
    "from, counter-clockwise from east: 90 - atan2(b1, a1)": lambda t: (90 - t) % 360,
}
#: The convention is taken only if its median |difference| from Dp is below this (°).
CONVENTION_MAX_DEG = 10.0


# ------------------------------------------------------------------ build

def spot_for(variant: str, spot, point: dict):
    if variant in ("break_5m", "normal_mop"):
        return spot
    moved = dataclasses.replace(spot, position=(point["lat"], point["lon"]))
    if variant == "mop_back":
        a, b = spot.shoreline
        moved = dataclasses.replace(moved, shoreline=(b, a))
    return moved


@dataclasses.dataclass(frozen=True)
class PointSpot(Spot):
    """A MOP point that is not a break (handoff 24b). Its normal is MOP's own
    `metaShoreNormal`, held exactly: nothing about the point is digitised
    here. The chord is synthesised perpendicular to it only so that anything
    reading one finds a consistent one; `raytrace.table` reads the position,
    the normal and the id."""

    fixed_normal: float = 0.0

    @property
    def normal(self) -> float:
        return self.fixed_normal % 360.0


#: Half-length (m) of the synthesised chord. It sets nothing: the normal is
#: held, and `raytrace.table` does not read the chord.
CHORD_HALF_M = 100.0


def point_spot(name: str, point: dict, normal: float, back: bool = False) -> PointSpot:
    """The spot `raytrace.table` traces from at a MOP point that is not a
    break; `back` turns the fan round (the opposite half, as `mop_back`)."""

    n = (normal + (180.0 if back else 0.0)) % 360.0
    lat, lon = float(point["lat"]), float(point["lon"])
    along = math.radians(n - 90.0)          # the chord runs at normal − 90°
    dlat = CHORD_HALF_M * math.cos(along) / 111_320.0
    dlon = CHORD_HALF_M * math.sin(along) / (111_320.0 * math.cos(math.radians(lat)))
    chord = ((lat - dlat, lon - dlon), (lat + dlat, lon + dlon))
    return PointSpot(id=name, name=name, position=(lat, lon), shoreline=chord,
                     notes=f"MOP {point.get('point')}: normal {n:.2f}° from its own metaShoreNormal",
                     fixed_normal=n)


def mop_normal(meta: dict) -> float | None:
    """MOP's own shore normal (°) from the point's saved small variables."""

    import re
    m = re.search(r"metaShoreNormal,\s*(-?[\d.]+)", meta.get("small_variables", {}).get("ascii", ""))
    return float(m.group(1)) if m else None


def seabed_at(bathy, lat: float, lon: float) -> float:
    x, y = rt.to_utm(lat, lon)
    h, *_ = bathy.sample(np.array([x]), np.array([y]))
    return float(h[0])


def h_ref_for(variant: str, bathy, point: dict) -> float:
    if variant == "break_5m":
        return rt.H_REF
    if variant == "normal_mop":
        return round(seabed_at(bathy, point["lat"], point["lon"]), 2)
    return MOP_H_REF


def without_nearshore(bathy):
    """The seabed with the 8 m `nearshore` grid left out: what a point
    outside it (Imperial Beach) is traced on, the 32 m `regional` first."""

    keep = [i for i, n in enumerate(bathy.names) if n != "nearshore"]
    return rt.Bathymetry([bathy.grids[i] for i in keep], bathy.msl_offset_m,
                         tuple(bathy.names[i] for i in keep))


def build(break_id: str, variant: str, point: dict, cache: Path = CACHE, refresh: bool = False,
          normal: float | None = None, coarse_seabed: bool = False):
    """(rows, meta) for one start, from the cache or `raytrace.table`.

    With `normal`, `break_id` names a point that is not a break: only `mop`
    and `mop_back`, traced from `point_spot` at MOP_H_REF. `coarse_seabed`
    leaves the 8 m grid out (the grid control for a point outside it)."""

    if normal is not None and variant not in ("mop", "mop_back"):
        raise ValueError(f"{break_id} is not a break: no {variant} start")
    if coarse_seabed and variant not in ("mop", "mop_back"):
        raise ValueError("the coarse-seabed control is for the MOP-point starts only")

    tag = "_32m" if coarse_seabed else ""
    csv_path = cache / f"{break_id}_{variant}{tag}.csv"
    meta_path = cache / f"{break_id}_{variant}{tag}.json"
    if csv_path.exists() and meta_path.exists() and not refresh:
        with csv_path.open(newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh)), json.loads(meta_path.read_text())
    bathy = rt.Bathymetry.load()
    if coarse_seabed:
        bathy = without_nearshore(bathy)
    spots, blockers = rt.load()
    if normal is None:
        spot = spot_for(variant, {s.id: s for s in spots}[break_id], point)
        h_ref = h_ref_for(variant, bathy, point)
    else:
        spot, h_ref = point_spot(break_id, point, normal, back=variant == "mop_back"), MOP_H_REF
    rows, meta = rt.table(bathy, spot, blockers, rt.frequencies(), h_ref=h_ref)
    meta["variant"] = variant
    meta["grids"] = list(bathy.names)
    if normal is not None:
        meta["normal_deg"] = round(spot.normal, 4)
        meta["normal_from"] = "MOP's metaShoreNormal"
    meta["mop_point"] = point.get("point")
    meta["seabed_at_mop_msl_m"] = round(seabed_at(bathy, point["lat"], point["lon"]), 2)
    cache.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=rt.FIELDS)
        w.writeheader()
        w.writerows(rows)
    meta_path.write_text(json.dumps(meta, indent=1))
    return [{k: str(v) for k, v in r.items()} for r in rows], meta


def control(break_id: str, point: dict, cache: Path = CACHE) -> tuple[int, int]:
    """Rows of `break_5m` that differ from the committed table, and the count."""

    rows, _ = build(break_id, "break_5m", point, cache)
    old = rt.committed_rows(break_id)
    bad = sum(1 for a, b in zip(rows, old) if a != b) + abs(len(rows) - len(old))
    return bad, len(old)


def point_control(points: dict, cache: Path = CACHE) -> tuple[int, int] | None:
    """The point path against the break path: Center's MOP point traced by
    `point_spot` with Center's own normal must give Center's `mop` table
    back row for row (rows differing, rows). None without Center."""

    if "coronado_center" not in points:
        return None
    spot = {s.id: s for s in rt.load()[0]}["coronado_center"]
    want, _ = build("coronado_center", "mop", points["coronado_center"], cache)
    got, _ = build("control_point_path_center", "mop", points["coronado_center"], cache, normal=spot.normal)
    bad = sum(1 for a, b in zip(got, want) if a != b) + abs(len(got) - len(want))
    return bad, len(want)


def windows_at(name: str, point: dict, normal: float) -> list[str]:
    """The open arcs at a MOP point, each edge with what forms it (straight
    lines to the charted blockers, `geometry.open_windows`)."""

    _, blockers = rt.load()
    out = []
    for w in open_windows(point_spot(name, point, normal), blockers):
        src = [getattr(e.source, "name", e.source) for e in (w.low, w.high)]
        out.append(f"{w.low.bearing:.1f}° ({src[0]}) – {w.high.bearing:.1f}° ({src[1]})")
    return out


# ------------------------------------------------------------------ carry

def kind_of(row: dict) -> str:
    if float(row["gain"]) > 0:
        return "clear"
    b = row["blocker"]
    if b.startswith(rt.ISLAND_PREFIX):
        return "island fill"
    if b.startswith("Point Loma"):
        return "Point Loma fill"
    if b.startswith("Baja"):
        return "Baja fill"
    return "other fill"


class Arrays:
    """A table's carrying rows as arrays per frequency (only what carries)."""

    def __init__(self, rows: list[dict], start_depth_m: float):
        self.start_depth_m = start_depth_m
        by: dict[float, list[dict]] = {}
        for r in rows:
            if float(r["gain"]) <= 0 and float(r["diff_gain"]) <= 0:
                continue
            by.setdefault(float(r["freq_hz"]), []).append(r)
        self.freqs = sorted(by)
        self.f: dict[float, dict] = {}
        for f, rs in by.items():
            self.f[f] = {
                "w": np.array([math.radians(float(r["near_width_deg"])) for r in rs]),
                "near": np.radians(np.array([float(r["near_from_deg"]) for r in rs])),
                "off": np.array([float(r["off_from_deg"]) for r in rs]),
                "gain": np.array([float(r["gain"]) for r in rs]),
                "doff": np.array([float(r["diff_off_from_deg"]) for r in rs]),
                "dgain": np.array([float(r["diff_gain"]) for r in rs]),
                "kind": np.array([KINDS.index(kind_of(r)) if kind_of(r) in KINDS else len(KINDS)
                                  for r in rs]),
                "ks2": rt_shoaling(f, start_depth_m),
            }

    def merged(self, other: "Arrays") -> "Arrays":
        out = Arrays([], self.start_depth_m)
        out.freqs = sorted(set(self.freqs) | set(other.freqs))
        for f in out.freqs:
            a, b = self.f.get(f), other.f.get(f)
            if a is None or b is None:
                out.f[f] = a or b
                continue
            # The two halves start 4 m apart at the same depth: one Ks.
            out.f[f] = {k: (np.concatenate([a[k], b[k]]) if k != "ks2" else a[k]) for k in a}
        return out


def rt_shoaling(f: float, h: float) -> float:
    from .nearshore import shoaling_squared

    return shoaling_squared(f, h)


def interp(grid: np.ndarray, deg: np.ndarray) -> np.ndarray:
    """`nearshore.at`, vectorised."""

    pos = (deg - 0.5) % 360.0
    i = pos.astype(int)
    frac = pos - i
    return grid[i] * (1 - frac) + grid[(i + 1) % 360] * frac


def carry_parts(spectrum, grids: dict[int, list[float]], table: Arrays) -> dict:
    """Deep-water-equivalent energy, hard and diffracted, as `nearshore.carry`
    sums it (its `e_hard` and `e_eq`), and the diffracted energy split by
    kind of ray, by offshore heading (5° bins) and by frequency."""

    e_hard = e_eq = 0.0
    kinds = np.zeros(len(KINDS) + 1)
    heading = np.zeros(72)
    by_f: dict[float, float] = {}
    near_dir: dict[float, tuple[float, float]] = {}
    for i, f in enumerate(spectrum.frequencies):
        grid = grids.get(i)
        if grid is None or not table.freqs:
            continue
        near = min(table.freqs, key=lambda t: abs(t - f))
        if abs(near - f) > 0.05 * f:
            continue
        a = table.f[near]
        g = np.asarray(grid)
        width = spectrum.bin_width(i)
        e_hard += float(np.sum(interp(g, a["off"]) * a["w"] * a["gain"])) * width / a["ks2"]
        e = interp(g, a["doff"]) * a["w"] * a["dgain"] * width / a["ks2"]
        e_eq += float(e.sum())
        np.add.at(kinds, a["kind"], e)
        np.add.at(heading, (a["doff"] // 5).astype(int) % 72, e)
        by_f[f] = by_f.get(f, 0.0) + float(e.sum())
        near_dir[f] = (float(np.sum(e * np.sin(a["near"]))), float(np.sum(e * np.cos(a["near"]))))
    return {"hard": e_hard, "eq": e_eq, "kinds": kinds, "heading": heading, "by_f": by_f,
            "near_dir": near_dir}


def arrives_from(parts: dict, period_s: float) -> float:
    """The heading the energy arrives on at the start, in the 46232 bin
    nearest `period_s` (to set beside MOP's own peak direction)."""

    nd = parts["near_dir"]
    if not nd:
        return float("nan")
    f = min(nd, key=lambda t: abs(t - 1.0 / period_s))
    s, c = nd[f]
    return math.degrees(math.atan2(s, c)) % 360 if (s or c) else float("nan")


def swell_peak_s(spectrum) -> float:
    best, fp = 0.0, float("nan")
    for i, f in enumerate(spectrum.frequencies):
        c = spectrum.c11[i]
        if c == c and c > best and f <= 1 / 8.0:
            best, fp = c, f
    return 1.0 / fp if fp == fp else float("nan")


def hours(break_id: str, mop: dict, spectra, tables: dict[str, Arrays], mop_depth_m: float,
          navd88_depth_msl_m: float, spec: dict | None = None, coarse=None,
          conv: str | None = None) -> list[dict]:
    """One row per matched hour: MOP and each start's chain, over 46232's Hs;
    with MOP's saved spectrum (`spec`), its per-band figures too."""

    from .nearshore import density_grids
    import bisect

    times = sorted(mop)
    out = []
    for sp in spectra:
        i = bisect.bisect_left(times, sp.time)
        near = [j for j in (i - 1, i) if 0 <= j < len(times)
                and abs((times[j] - sp.time).total_seconds()) <= MATCH_S]
        if not near:
            continue
        t_mop = times[min(near, key=lambda j: abs(times[j] - sp.time))]
        hs_mop, tp_mop, dp_mop = mop[t_mop]
        m0 = sum(c * sp.bin_width(k) for k, c in enumerate(sp.c11) if c == c and c > 0)
        buoy = 4 * math.sqrt(m0)
        if buoy <= 0 or tp_mop <= 0:
            continue
        mem = sp.with_spread("mem")
        grids = density_grids(mem)
        row = {"time": sp.time, "buoy": buoy, "from": mean_from(sp), "tp": swell_peak_s(sp),
               "mop": hs_mop / ks(tp_mop, mop_depth_m) / buoy,
               "mop_navd": hs_mop / ks(tp_mop, navd88_depth_msl_m) / buoy, "parts": {},
               "tp_mop": tp_mop, "dp_mop": dp_mop}
        for v, t in tables.items():
            p = carry_parts(mem, grids, t)
            row["parts"][v] = p
            row[f"{v}_eq"] = 4 * math.sqrt(max(p["eq"], 0.0)) / buoy
            row[f"{v}_hard"] = 4 * math.sqrt(max(p["hard"], 0.0)) / buoy
            row[f"{v}_dir"] = arrives_from(p, tp_mop)
        p = row["parts"]["mop"]
        for fc in CUTS_HZ:
            e = sum(v for f, v in p["by_f"].items() if f <= fc + 1e-9)
            row[("cut", fc)] = 4 * math.sqrt(max(e, 0.0)) / buoy
        dens = {f: v / mem.bin_width(mem.frequencies.index(f)) for f, v in p["by_f"].items() if v > 0}
        row["mop_peak_s"] = 1.0 / max(dens, key=dens.get) if dens else float("nan")
        k = max(range(len(sp.c11)), key=lambda k: sp.c11[k] if sp.c11[k] == sp.c11[k] else -1.0)
        row["buoy_peak_s"] = 1.0 / sp.frequencies[k]
        four = sp.with_spread("fourier")
        row["mop_eq_fourier"] = 4 * math.sqrt(max(carry_parts(four, density_grids(four), tables["mop"])["eq"], 0.0)) / buoy
        row["hs_mop"] = hs_mop
        if spec is not None and coarse:
            add_bands(row, mem, spec, t_mop, coarse, mop_depth_m, navd88_depth_msl_m, conv)
        out.append(row)
    return out


# ------------------------------------------------------------------ MOP's own spectrum

def read_mop_spectrum(mop_dir: Path, break_id: str) -> tuple[dict | None, str]:
    """MOP's saved spectrum for one point, or (None, why not).

    Refused unless the collector's read-back (4·sqrt(Σ E·df) over MOP's own
    Hs) passed: a unit or band-width misread is a factor, and nothing here
    should be built on one."""

    meta_path = mop_dir / f"{break_id}_meta.json"
    spec_path = mop_dir / f"{break_id}_spectrum.csv"
    bands_path = mop_dir / f"{break_id}_bands.csv"
    if not (meta_path.exists() and spec_path.exists() and bands_path.exists()):
        return None, "no saved spectrum (run `collector.mop` on Actions)"
    meta = json.loads(meta_path.read_text())
    rb = meta.get("spectrum", {}).get("readback", {})
    if not rb.get("ok"):
        return None, f"read-back failed or absent: {rb}"
    with bands_path.open(newline="", encoding="utf-8") as fh:
        bands = [(float(r["freq_hz"]), float(r["lower_hz"]), float(r["upper_hz"])) for r in csv.DictReader(fh)]

    def table(path: Path) -> dict[datetime, list[float | None]]:
        out = {}
        with path.open(newline="", encoding="utf-8") as fh:
            rd = csv.reader(fh)
            next(rd)
            for r in rd:
                t = datetime.fromisoformat(r[0].replace("Z", "+00:00"))
                out[t] = [float(x) if x else None for x in r[1:]]
        return out

    energy = table(spec_path)
    mom_path = mop_dir / f"{break_id}_moments.csv"
    moments = table(mom_path) if mom_path.exists() else None
    inputs = None
    in_path = mop_dir / f"{break_id}_inputs.csv"
    if in_path.exists():
        inputs = {}
        with in_path.open(newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                t = datetime.fromisoformat(r["valid_utc"].replace("Z", "+00:00"))
                cov = [float(r[k]) if r[k] else None for k in r if k.startswith("cov")]
                inputs[t] = (r["input_source"] or None, cov)
    return {"bands": bands, "energy": energy, "moments": moments, "inputs": inputs, "meta": meta}, ""


def overlap(lo: float, hi: float, a: float, b: float) -> float:
    return max(0.0, min(hi, b) - max(lo, a))


def bin_edges(freqs: list[float]) -> list[tuple[float, float]]:
    """46232's bins as `Spectrum.bin_width` reads them: edges at midpoints,
    the end bins as wide as their one neighbour's gap."""

    n = len(freqs)
    out = []
    for i, f in enumerate(freqs):
        lo = (freqs[i - 1] + f) / 2 if i > 0 else f - (freqs[1] - f) / 2
        hi = (f + freqs[i + 1]) / 2 if i < n - 1 else f + (f - freqs[i - 1]) / 2
        out.append((lo, hi))
    return out


def common_bands(mop_bands: list[tuple[float, float, float]], buoy_freqs: list[float]) -> list[tuple[float, float]]:
    """`BAND_EDGES_HZ`, clipped to the range both sides cover."""

    edges = bin_edges(buoy_freqs)
    lo = max(min(b[1] for b in mop_bands), edges[0][0])
    hi = min(max(b[2] for b in mop_bands), edges[-1][1])
    out = []
    for a, b in zip(BAND_EDGES_HZ[:-1], BAND_EDGES_HZ[1:]):
        a, b = max(a, lo), min(b, hi)
        if b > a:
            out.append((a, b))
    return out


def band_label(a: float, b: float) -> str:
    return f"{1 / b:.1f}–{1 / a:.1f} s" if a > 0 else f"> {1 / b:.1f} s"


def split(values: list[tuple[float, float, float]], coarse: list[tuple[float, float]]) -> list[float]:
    """Sum (energy, lo, hi) bins into coarse bands, each by its overlap share."""

    out = [0.0] * len(coarse)
    for e, lo, hi in values:
        w = hi - lo
        if w <= 0 or not e:
            continue
        for k, (a, b) in enumerate(coarse):
            ov = overlap(lo, hi, a, b)
            if ov > 0:
                out[k] += e * ov / w
    return out


def mop_band_energy(row: list[float | None], bands, depth_m: float, coarse) -> list[float] | None:
    """MOP's deep-water-equivalent energy (m²) per coarse band: each MOP
    band de-shoaled at its own frequency. None if the hour has a gap."""

    if any(x is None for x in row):
        return None
    return split([(e * (hi - lo) / rt_shoaling(fc, depth_m), lo, hi)
                  for e, (fc, lo, hi) in zip(row, bands)], coarse)


def mop_band_direction(row, mom, bands, coarse, conv) -> list[float]:
    """MOP's energy-weighted mean direction FROM per coarse band (°)."""

    nf = len(bands)
    a1, b1 = mom[:nf], mom[nf:2 * nf]
    out = []
    for a, b in coarse:
        sa = sb = 0.0
        for i, (fc, lo, hi) in enumerate(bands):
            ov = overlap(lo, hi, a, b)
            if ov > 0 and row[i] and a1[i] is not None and b1[i] is not None:
                sa += row[i] * ov * a1[i]
                sb += row[i] * ov * b1[i]
        out.append(conv(math.degrees(math.atan2(sb, sa))) if (sa or sb) else float("nan"))
    return out


def chain_band_direction(near_dir: dict, freqs: list[float], coarse) -> list[float]:
    """The heading chain-at-MOP's energy arrives on, per coarse band (°)."""

    edges = dict(zip(freqs, bin_edges(freqs)))
    s = [0.0] * len(coarse)
    c = [0.0] * len(coarse)
    for f, (ss, cc) in near_dir.items():
        lo, hi = edges[f]
        for k, (a, b) in enumerate(coarse):
            ov = overlap(lo, hi, a, b)
            if ov > 0:
                s[k] += ss * ov / (hi - lo)
                c[k] += cc * ov / (hi - lo)
    return [math.degrees(math.atan2(x, y)) % 360 if (x or y) else float("nan") for x, y in zip(s, c)]


def source_label(src: str | None) -> str:
    return "(gap)" if not src else src.rstrip("_") or "(gap)"


def circ(d: float) -> float:
    return ((d + 180) % 360) - 180


def convention(spec: dict, mop: dict) -> tuple[str | None, dict[str, float]]:
    """Which a1/b1 → direction mapping agrees with MOP's own Dp at its peak
    band: {name: median |difference|}, and the one taken (None if none is
    within CONVENTION_MAX_DEG). Read off the file, not assumed."""

    mom = spec["moments"]
    if not mom:
        return None, {}
    nf = len(spec["bands"])
    diffs: dict[str, list[float]] = {k: [] for k in CONVENTIONS}
    for t, row in spec["energy"].items():
        m = mom.get(t)
        if m is None or t not in mop or any(x is None for x in row):
            continue
        dp = mop[t][2]
        i = max(range(nf), key=lambda j: row[j])
        a1, b1 = m[i], m[nf + i]
        if dp != dp or a1 is None or b1 is None or not (a1 or b1):
            continue
        theta = math.degrees(math.atan2(b1, a1))
        for k, f in CONVENTIONS.items():
            diffs[k].append(abs(circ(f(theta) - dp)))
    med = {k: q(v, .5) for k, v in diffs.items() if v}
    if not med:
        return None, {}
    best = min(med, key=med.get)
    return (best if med[best] <= CONVENTION_MAX_DEG else None), med


def add_bands(row: dict, sp, spec: dict, t_mop, coarse, depth_m: float, navd_m: float, conv) -> None:
    """Per-band figures for one matched hour, into `row["band"]`."""

    e_row = spec["energy"].get(t_mop)
    if e_row is None:
        return
    mop_e = mop_band_energy(e_row, spec["bands"], depth_m, coarse)
    if mop_e is None:
        return
    mop_n = mop_band_energy(e_row, spec["bands"], navd_m, coarse)
    edges = bin_edges(sp.frequencies)
    buoy = split([(c * sp.bin_width(i), *edges[i]) for i, c in enumerate(sp.c11) if c == c and c > 0], coarse)
    by_f = row["parts"]["mop"]["by_f"]
    idx = {f: i for i, f in enumerate(sp.frequencies)}
    chain = split([(e, *edges[idx[f]]) for f, e in by_f.items()], coarse)
    band = {"mop": mop_e, "mop_navd": mop_n, "chain": chain, "buoy": buoy,
            "point_hs": 4 * math.sqrt(sum(e * (hi - lo) for e, (_, lo, hi) in zip(e_row, spec["bands"])))}
    if conv is not None and spec["moments"] and spec["moments"].get(t_mop):
        band["mop_dir"] = mop_band_direction(e_row, spec["moments"][t_mop], spec["bands"], coarse,
                                             CONVENTIONS[conv])
        band["chain_dir"] = chain_band_direction(row["parts"]["mop"]["near_dir"], sp.frequencies, coarse)
    inp = (spec.get("inputs") or {}).get(t_mop)
    if inp is not None:
        band["source"] = inp[0]
        cov = inp[1]
        if cov and len(cov) == len(spec["bands"]):
            band["coverage"] = [
                (sum(c * overlap(lo, hi, a, b) for c, (_, lo, hi) in zip(cov, spec["bands"]) if c is not None)
                 / max(sum(overlap(lo, hi, a, b) for c, (_, lo, hi) in zip(cov, spec["bands"]) if c is not None),
                       1e-30)) for a, b in coarse]
    row["band"] = band
    row["mop_bandwise"] = 4 * math.sqrt(sum(mop_e)) / row["buoy"]
    row["mop_bandwise_navd"] = 4 * math.sqrt(sum(mop_n)) / row["buoy"]


# ------------------------------------------------------------------ report

def q(v, p):
    v = sorted(x for x in v if x == x)
    return v[min(len(v) - 1, int(round(p * (len(v) - 1))))] if v else float("nan")


def cell(v) -> str:
    return f"{q(v, .5):.2f} [{q(v, .1):.2f}, {q(v, .9):.2f}]"


def sectors():
    return SECTORS[:4] + (("all", 0, 360),)


def acceptance(rows: list[dict], start_depth_m: float, period_s: float,
               step: int = 10) -> tuple[dict[int, float], float]:
    """Σ width·diff_gain/Ks² per radian of offshore heading, by `step`° bin,
    at the table frequency nearest `period_s` (§56's comb: Kr² on a planar
    beach, ≤ 1, read as a bin average because each ray samples one heading)."""

    freqs = sorted({float(r["freq_hz"]) for r in rows})
    f = min(freqs, key=lambda t: abs(1 / t - period_s))
    ks2 = rt_shoaling(f, start_depth_m)
    out: dict[int, float] = {}
    for r in rows:
        if float(r["freq_hz"]) != f or float(r["diff_gain"]) <= 0:
            continue
        b = int(float(r["diff_off_from_deg"]) // step) * step
        out[b] = out.get(b, 0.0) + math.radians(float(r["near_width_deg"])) * float(r["diff_gain"]) / ks2
    return {b: v / math.radians(step) for b, v in sorted(out.items())}, 1.0 / f


def ok_band(r: dict, k: int) -> bool:
    b = r["band"]
    return b["mop"][k] > 0 and b["chain"][k] > 0 and 4 * math.sqrt(b["buoy"][k]) >= BAND_MIN_HS


def band_report(rows: list[dict], spec: dict | None, why: str, coarse, conv, conv_med: dict) -> list[str]:
    """The per-band section for one break."""

    L = ["", "### MOP's own spectrum, band by band", ""]
    if spec is None:
        return L + [f"Not compared: {why}.", ""]
    rows = [r for r in rows if "band" in r]
    m = spec["meta"]["spectrum"]
    bands = spec["bands"]
    rb = m.get("readback", {})
    L += [f"MOP's {len(bands)} bands, {bands[0][1]:.4f}–{bands[-1][2]:.4f} Hz (edges from "
          f"`{(m.get('schema') or {}).get('edges_from')}`); read-back 4·sqrt(Σ E·df) / MOP's Hs "
          f"median {rb.get('median')}, worst {rb.get('worst')} over {rb.get('hours')} hours. Common bands "
          f"{coarse[0][0]:.4f}–{coarse[-1][1]:.4f} Hz. {len(rows)} matched hours with a complete MOP "
          f"spectrum; a band-hour is compared when 46232 has ≥ {BAND_MIN_HS} m in the band.", ""]
    if not rows:
        return L
    labels = [band_label(a, b) for a, b in coarse]
    # Whole spectrum, de-shoaled band by band against at Tp.
    L += ["Whole spectrum, MOP de-shoaled band by band at each band's frequency (10.77 m in brackets) "
          "against at its Tp as above; MOP's spectrum summed over its own Hs at the point:", "",
          "| 46232 from | n | MOP, by band | MOP, at Tp | chain-at-MOP / MOP, by band | at Tp | spectrum Hs / MOP Hs |",
          "|---|---:|---|---|---|---|---|"]
    for name, lo, hi in sectors():
        sel = [r for r in rows if lo <= r["from"] < hi and r["mop_bandwise"] > 0]
        if sel:
            L.append(f"| {name} | {len(sel)} | {cell([r['mop_bandwise'] for r in sel])} | "
                     f"{cell([r['mop'] for r in sel])} | {cell([r['mop_eq'] / r['mop_bandwise'] for r in sel])} "
                     f"({q([r['mop_eq'] / r['mop_bandwise_navd'] for r in sel], .5):.2f}) | "
                     f"{q([r['mop_eq'] / r['mop'] for r in sel], .5):.2f} | "
                     f"{cell([r['band']['point_hs'] / r['hs_mop'] for r in sel])} |")
    L += ["", "chain-at-MOP / MOP in each band, as heights (√ of the energy ratio, both deep-water-equivalent, "
          "before friction), median [10th, 90th] and hours:", "",
          "| 46232 from | " + " | ".join(labels) + " |", "|---|" + "---|" * len(labels)]
    for name, lo, hi in sectors():
        sel = [r for r in rows if lo <= r["from"] < hi]
        cells = []
        for k in range(len(coarse)):
            v = [math.sqrt(r["band"]["chain"][k] / r["band"]["mop"][k]) for r in sel if ok_band(r, k)]
            cells.append(f"{cell(v)} n {len(v)}" if v else "–")
        if sel:
            L.append(f"| {name} | " + " | ".join(cells) + " |")
    L += ["", "Each over 46232 in the same band, as heights (√ energy ratio), median: MOP / chain-at-MOP. "
          "Where MOP is lower than the chain, this says whether MOP takes less of the buoy's band or "
          "the chain takes more:", "",
          "| 46232 from | " + " | ".join(labels) + " |", "|---|" + "---|" * len(labels)]
    for name, lo, hi in sectors():
        sel = [r for r in rows if lo <= r["from"] < hi]
        cells = []
        for k in range(len(coarse)):
            s2 = [r for r in sel if ok_band(r, k)]
            cells.append(f"{q([math.sqrt(r['band']['mop'][k] / r['band']['buoy'][k]) for r in s2], .5):.2f} / "
                         f"{q([math.sqrt(r['band']['chain'][k] / r['band']['buoy'][k]) for r in s2], .5):.2f}"
                         if s2 else "–")
        if sel:
            L.append(f"| {name} | " + " | ".join(cells) + " |")
    L += ["", "Share of the deep-water-equivalent energy by band (sector totals): MOP / chain-at-MOP / 46232:", "",
          "| 46232 from | " + " | ".join(labels) + " |", "|---|" + "---|" * len(labels)]
    for name, lo, hi in sectors():
        sel = [r for r in rows if lo <= r["from"] < hi]
        if not sel:
            continue
        tot = {k: [sum(r["band"][k][j] for r in sel) for j in range(len(coarse))] for k in ("mop", "chain", "buoy")}
        sh = {k: [x / max(sum(v), 1e-30) for x in v] for k, v in tot.items()}
        L.append(f"| {name} | " + " | ".join(f"{100 * sh['mop'][j]:.0f} / {100 * sh['chain'][j]:.0f} / "
                                             f"{100 * sh['buoy'][j]:.0f}%" for j in range(len(coarse))) + " |")
    with_cov = [r for r in rows if "coverage" in r["band"]]
    if with_cov:
        L += ["", "MOP's own weighted input coverage per band (`waveModelBinInputCoverage`, overlap-weighted "
              "mean of its bands), median [10th, 90th]:", "",
              "| 46232 from | " + " | ".join(labels) + " |", "|---|" + "---|" * len(labels)]
        for name, lo, hi in sectors():
            sel = [r for r in with_cov if lo <= r["from"] < hi]
            if sel:
                L.append(f"| {name} | " + " | ".join(cell([r["band"]["coverage"][k] for r in sel])
                                                     for k in range(len(coarse))) + " |")
    srcs: dict[str, list[dict]] = {}
    for r in rows:
        if "source" in r["band"]:
            srcs.setdefault(source_label(r["band"]["source"]), []).append(r)
    if srcs:
        L += ["", "By MOP's input sources (`waveModelInputSource` as written, trailing padding dropped; "
              "CDIP station ids): whole-spectrum chain-at-MOP / MOP (MOP de-shoaled by band), median "
              "[10th, 90th] and hours, by 46232's sector:", "",
              "| inputs | " + " | ".join(n for n, _, _ in sectors()) + " |", "|---|" + "---|" * len(sectors())]
        for k, rs in sorted(srcs.items(), key=lambda kv: -len(kv[1])):
            cells = []
            for name, lo, hi in sectors():
                v = [r["mop_eq"] / r["mop_bandwise"] for r in rs if lo <= r["from"] < hi and r["mop_bandwise"] > 0]
                cells.append(f"{cell(v)} n {len(v)}" if v else "–")
            L.append(f"| `{k}` | " + " | ".join(cells) + " |")
    if spec["moments"] is None:
        L += ["", "Direction by band: MOP's files carry no moments.", ""]
        return L
    L += ["", "MOP's a1/b1 convention, read off its own Dp at its peak band (median |difference|): "
          + "; ".join(f"{k} {v:.1f}°" for k, v in conv_med.items()) + "."
          + (f" Taken: **{conv}**." if conv else f" None within {CONVENTION_MAX_DEG:g}°: no direction table.")]
    if conv is None:
        return L + [""]
    L += ["", "Direction by band: chain-at-MOP's arrival heading minus MOP's mean direction from (°), "
          "median [10th, 90th]; MOP's mean direction in brackets:", "",
          "| 46232 from | " + " | ".join(labels) + " |", "|---|" + "---|" * len(labels)]
    for name, lo, hi in sectors():
        sel = [r for r in rows if lo <= r["from"] < hi and "mop_dir" in r["band"]]
        cells = []
        for k in range(len(coarse)):
            s2 = [r for r in sel if ok_band(r, k) and r["band"]["mop_dir"][k] == r["band"]["mop_dir"][k]
                  and r["band"]["chain_dir"][k] == r["band"]["chain_dir"][k]]
            d = [circ(r["band"]["chain_dir"][k] - r["band"]["mop_dir"][k]) for r in s2]
            cells.append(f"{cell(d)} ({q([r['band']['mop_dir'][k] for r in s2], .5):.0f}°)" if d else "–")
        if sel:
            L.append(f"| {name} | " + " | ".join(cells) + " |")
    return L + [""]


def files_report(points: dict, specs: dict) -> list[str]:
    """What MOP's files say about themselves: global attributes in full for
    the first point (and any that differ elsewhere), `metaWaterDepth`'s
    attributes and the small variables for every point."""

    L = ["## What MOP's files say about themselves", "",
         "Read from each file's DAS and from its small variables (`collector.mop`, Actions), verbatim. "
         "This is where MOP's depth datum, its method and the buoys that drive the nowcast are read; "
         "nothing in this section is inferred.", ""]
    metas = {}
    for b in points:
        mp = MOP_DIR / f"{b}_meta.json"
        if mp.exists():
            metas[b] = json.loads(mp.read_text())
    if not metas:
        return L + ["No `<break>_meta.json` yet: run `collector.mop` on Actions.", ""]
    first = next(iter(metas))
    g0 = metas[first].get("global", {})
    L += [f"### Global attributes ({metas[first]['point']})", ""]
    for k, v in g0.items():
        L.append(f"- `{k}`: {json.dumps(v, ensure_ascii=False)}")
    for b, m in metas.items():
        if b == first:
            continue
        diff = {k: v for k, v in m.get("global", {}).items() if g0.get(k) != v}
        if diff:
            L += ["", f"Differing at {m['point']} ({b}):"] + [f"- `{k}`: {json.dumps(v, ensure_ascii=False)}"
                                                               for k, v in diff.items()]
    L += ["", "### Per point", ""]
    for b, m in metas.items():
        sv = m.get("small_variables", {})
        body = sv.get("ascii", "")
        body = body.split("---------------------------------------------", 1)[-1].strip()
        sp = m.get("spectrum", {})
        L += [f"**{m['point']}** ({b}) — `metaWaterDepth` attributes: "
              f"{json.dumps(m.get('metaWaterDepth', {}), ensure_ascii=False)}. Spectrum: "
              f"{'read' if specs.get(b, (None, ''))[0] else 'not read'}"
              f"{'' if not sp.get('problems') else ' (' + '; '.join(sp['problems']) + ')'}; "
              f"variables declared: {', '.join(sorted(m.get('variables', {})))}.", "",
              "Small variables (off the time axis), as served:", "", "```", body[:6000], "```", ""]
    return L


def band_ratio(r: dict, k: int) -> float | None:
    """chain-at-MOP / MOP in coarse band k as a height, or None."""

    return math.sqrt(r["band"]["chain"][k] / r["band"]["mop"][k]) if "band" in r and ok_band(r, k) else None


def exposed_report(places: dict[str, list[dict]], coarse, edges: dict[str, str]) -> list[str]:
    """Handoff 24b: the band ratios at each place side by side, on the hours
    every place has a complete MOP spectrum for, by 46232's sector."""

    rows = {k: {r["time"]: r for r in v if "band" in r} for k, v in places.items()}
    common = set.intersection(*(set(v) for v in rows.values())) if rows else set()
    labels = [band_label(a, b) for a, b in coarse]
    L = ["## Exposed against shadowed (handoff 24b)", "",
         f"chain-at-MOP / MOP in each band as heights (√ energy ratio, both deep-water-equivalent before "
         f"friction, MOP de-shoaled band by band), median, on the {len(common)} hours every place below "
         f"has a matched 46232 spectrum and a complete MOP spectrum for. Straight-line Point Loma edge at "
         f"each MOP point in brackets (`geometry.open_windows`, MOP's own normal). A band-hour is "
         f"compared when 46232 has ≥ {BAND_MIN_HS} m in it. Whole spectrum: chain-at-MOP / MOP, MOP "
         "de-shoaled by band. `32 m seabed` is the grid control: the same MOP point traced with the 8 m "
         "`nearshore` grid left out, the seabed a point outside it (Imperial Beach) is traced on.", "",
         "| 46232 from | place | n | whole | " + " | ".join(labels) + " |",
         "|---|---|---:|---|" + "---|" * len(labels)]
    for name, lo, hi in sectors():
        for place, by_t in rows.items():
            sel = [by_t[t] for t in common if lo <= by_t[t]["from"] < hi]
            if not sel:
                continue
            whole = [r["mop_eq"] / r["mop_bandwise"] for r in sel if r["mop_bandwise"] > 0]
            cells = []
            for k in range(len(coarse)):
                v = [x for x in (band_ratio(r, k) for r in sel) if x is not None]
                cells.append(f"{q(v, .5):.2f}" if v else "–")
            L.append(f"| {name} | {place} ({edges.get(place, '?')}) | {len(sel)} | {q(whole, .5):.2f} | "
                     + " | ".join(cells) + " |")
    return L + [""]


def planar(off_deg: float, period_s: float, depth_m: float) -> tuple[float, float]:
    """A beach of straight parallel contours: (Kr², arrival off the normal in
    degrees) at `depth_m` for swell `off_deg` off the normal in deep water
    (Snell). The reference for an acceptance comb, not a claim about any
    real seabed."""

    if abs(off_deg) >= 90:
        return 0.0, float("nan")
    k0 = 4 * math.pi ** 2 / (9.81 * period_s ** 2)
    k = k0
    for _ in range(200):
        k = k0 / math.tanh(k * depth_m)
    th = math.asin(math.sin(math.radians(off_deg)) * k0 / k)
    return math.cos(math.radians(off_deg)) / math.cos(th), math.degrees(th)


def point_report(name: str, p: dict, normal: float, meta: dict, rows: list[dict], windows: list[str],
                 seabed: tuple[float, float], cut: tuple[int, int],
                 comb: tuple[dict[int, float], float] | None = None) -> list[str]:
    """The section for one point that is not a break: where it is, what its
    window is, and the whole-spectrum comparison (the band section follows)."""

    m, mb = meta["mop"], meta["mop_back"]
    L = [f"## {name} — a MOP point that is not a break (handoff 24b)", "",
         f"MOP {p['point']} at {p['lat']}, {p['lon']}, {p['distance_m']} m from the search target "
         f"{p.get('search_from')} ({p.get('why', '')}). MOP's `metaWaterDepth` {p['depth_m']}; the seabed "
         f"reads {seabed[0]:.2f} m below MSL there, from the {seabed[1]:g} m grid (the Coronado points "
         f"sit in the 8 m one). Fan centred on MOP's own `metaShoreNormal`, {normal:.2f}°; `mop` starts "
         f"{m['start_depth_m']} m at {m['start_lat']}, {m['start_lon']}, `mop_back` (the opposite half) "
         f"{mb['start_depth_m']} m. {len(rows)} matched hours, cut to the {cut[0]} of its {cut[1]} MOP "
         "hours that every break's MOP series also has.", "",
         "Open arcs there, straight lines to the charted blockers: " + "; ".join(windows) + ".", "",
         "| 46232 from | n | MOP (at Tp) | chain-at-MOP eq | chain-at-MOP / MOP, eq (at Tp) | hard / MOP | "
         "back half's share | Fourier / MOP |",
         "|---|---:|---|---|---|---|---|---|"]
    for sname, lo, hi in sectors():
        sel = [r for r in rows if lo <= r["from"] < hi and r["mop"] > 0]
        if not sel:
            continue
        back = [r["parts"]["mop_back"]["eq"] / r["parts"]["mop"]["eq"] for r in sel if r["parts"]["mop"]["eq"] > 0]
        L.append(f"| {sname} | {len(sel)} | {cell([r['mop'] for r in sel])} | {cell([r['mop_eq'] for r in sel])} | "
                 f"{cell([r['mop_eq'] / r['mop'] for r in sel])} | {cell([r['mop_hard'] / r['mop'] for r in sel])} | "
                 f"{100 * q(back, .5):.1f}% | {cell([r['mop_eq_fourier'] / r['mop'] for r in sel])} |")
    # Energy arriving from offshore headings more than 90° off the normal:
    # past the seaward limit, alongside the coast (at Imperial Beach, the
    # Baja coast, which the chain has only as a tangent; BRIEFING §12).
    lim = (normal - 90.0) % 360.0
    behind = np.array([((5 * k + 2.5 - normal + 180) % 360 - 180) < -90 or
                       ((5 * k + 2.5 - normal + 180) % 360 - 180) > 90 for k in range(72)])
    L += ["", f"From past the seaward limit: the share of chain-at-MOP's energy arriving from offshore "
          f"headings more than 90° off the normal (below {lim:.1f}° or above {(normal + 90) % 360:.1f}°, "
          "5° bins by centre), median, and chain-at-MOP / MOP (MOP de-shoaled by band) with and without "
          "those rays:", "",
          "| 46232 from | n | share past the limit | chain-at-MOP / MOP | without them |", "|---|---:|---|---|---|"]
    for sname, lo, hi in sectors():
        sel = [r for r in rows if lo <= r["from"] < hi and r.get("mop_bandwise", 0) > 0 and r["parts"]["mop"]["eq"] > 0]
        if not sel:
            continue
        share = [float(r["parts"]["mop"]["heading"][behind].sum()) / r["parts"]["mop"]["eq"] for r in sel]
        L.append(f"| {sname} | {len(sel)} | {100 * q(share, .5):.1f}% [{100 * q(share, .1):.1f}, "
                 f"{100 * q(share, .9):.1f}] | {cell([r['mop_eq'] / r['mop_bandwise'] for r in sel])} | "
                 f"{cell([r['mop_eq'] * math.sqrt(max(1 - x, 0.0)) / r['mop_bandwise'] for r, x in zip(sel, share)])} |")
    L += ["", "Share of chain-at-MOP's diffracted energy by kind of ray (sector totals), and "
          "chain-at-MOP / MOP (at Tp) with only the clear rays:", "",
          "| 46232 from | " + " | ".join(KINDS) + " | clear only / MOP |",
          "|---|" + "---|" * (len(KINDS) + 1)]
    for sname, lo, hi in sectors():
        sel = [r for r in rows if lo <= r["from"] < hi and r["mop"] > 0]
        if not sel:
            continue
        tot = sum(r["parts"]["mop"]["kinds"] for r in sel)
        share = tot / max(tot.sum(), 1e-30)
        clear = [4 * math.sqrt(r["parts"]["mop"]["kinds"][0]) / r["buoy"] / r["mop"] for r in sel]
        L.append(f"| {sname} | " + " | ".join(f"{100 * share[k]:.1f}%" for k in range(len(KINDS)))
                 + f" | {cell(clear)} |")
    if comb:
        acc, period = comb
        depth = float(m["start_depth_m"])
        L += ["", f"Acceptance per offshore degree at {period:.1f} s (Σ width·diff_gain/Ks² per radian, "
              f"10° bins, both half-fans), beside a beach of straight parallel contours at MOP's normal "
              f"({normal:.2f}°) and the start's depth ({depth} m): Snell's Kr² and arrival off the normal. "
              "A reference, not a claim about this seabed:", "",
              "| offshore from | chain | straight contours Kr² | their arrival off normal |", "|---|---|---|---|"]
        tot_c = tot_p = 0.0
        for k in range(150, 330, 10):
            kr2, th = planar(k + 5 - normal, period, depth)
            v = acc.get(k, 0.0)
            tot_c, tot_p = tot_c + 10 * v, tot_p + 10 * kr2
            L.append(f"| {k}–{k + 10}° | {v:.2f} | {kr2:.2f} | {'' if th != th else f'{th:+.0f}°'} |")
        L.append(f"| 150–330°, Σ × 10° | {tot_c:.0f}° | {tot_p:.0f}° | |")
    return L


def report(results: dict, metas: dict, controls: dict, points: dict, combs: dict,
           bands: dict | None = None, files: list[str] | None = None,
           extra: list[str] | None = None) -> str:
    L = ["# The chain's own rays from MOP's points",
         "",
         f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC by `python -m forecast.mopdepth` "
         "(precompute-side, numpy; not run by any workflow). **A model against a model**: MOP is a "
         "cross-check, not a verification series; nothing here is fitted or shipped (BRIEFING §56b).",
         "",
         "Each start is a transfer table built by `raytrace.table` itself (same frequencies, 0.5° "
         "headings, islands and diffracting edges as shipped; no Madsen), carried hour by hour "
         "through the archived 46232 spectra (maximum entropy). Every figure is deep-water-equivalent "
         "Hs over 46232's Hs, before friction: `eq` with diffraction (`hs_equivalent`), `hard` with "
         "hard edges (`hs_hard`). MOP is de-shoaled at its own Tp from 10 m (as `mopcheck`) and, in "
         "brackets in the ratio tables, from 10.77 m (10 m NAVD88 on MSL).",
         "",
         "Starts: `break_5m` the shipped table; `normal_mop` the break's normal out to the seabed's "
         "depth at the MOP point; `mop` at the MOP point (both half-fans).",
         ""]
    L += ["## How to read it", "",
          "- chain-at-MOP / MOP near 1 would put the 5 m excess between 10 m and 5 m (the place); "
          "above 1 puts it in the tables over the same water. `5 m / chain-at-MOP` is what the leg "
          "from MOP's point to the break adds.",
          "- `normal_mop` is the break's own normal out to the MOP point's depth. At South it is "
          "beside the MOP point; at Center and North the ~11 m contour on the normal is 3 km out, "
          "on the open shelf, so there it is a third place, not the 10 m → 5 m leg.",
          "- The frequency table sets the chain's energy up to a cut against MOP's WHOLE Hs. Near 1 "
          "at ≤ 0.1 Hz says the chain's swell alone is as big as all of MOP; it does not say the "
          "swell agrees. Which band MOP is short in is the per-band section under each break, "
          "from MOP's own spectrum.",
          "- Per band, both sides are deep-water-equivalent before friction: MOP de-shoaled band by "
          "band at each band's own frequency, chain-at-MOP as carried. `MOP / chain-at-MOP` over "
          "46232 in the same band says which side moves: MOP taking less of the buoy's band, or the "
          "chain taking more.",
          "- Fourier against maximum entropy is the buoy's directional reading alone: the same "
          "tables, a different spread.",
          ""]
    L += ["## Controls", ""]
    for b, (bad, n) in controls.items():
        if b == "point path":
            L.append(f"- The point path (`point_spot`, the normal held), given Center's MOP point and "
                     f"Center's normal, against Center's `mop` table: {bad} of {n} rows differ.")
        else:
            L.append(f"- {b}: `break_5m` against the committed table: {bad} of {n} rows differ.")
    L.append("")
    if extra:
        L += extra
    for b, rows in results.items():
        if b not in points:
            continue
        p = points[b]
        m = metas[b]
        L += [f"## {b}" + (" — shown, not read (§29)" if b == "coronado_north" else ""), "",
              f"MOP {p['point']}: seabed {m['mop']['seabed_at_mop_msl_m']} m below MSL there; "
              f"starts: `break_5m` {m['break_5m']['start_depth_m']} m at "
              f"{m['break_5m']['start_lat']}, {m['break_5m']['start_lon']}; `normal_mop` "
              f"{m['normal_mop']['start_depth_m']} m at {m['normal_mop']['start_lat']}, "
              f"{m['normal_mop']['start_lon']}; `mop` {m['mop']['start_depth_m']} m at "
              f"{m['mop']['start_lat']}, {m['mop']['start_lon']}. {len(rows)} matched hours.",
              "",
              "| 46232 from | n | MOP | break_5m eq | normal_mop eq | mop eq | mop hard |",
              "|---|---:|---|---|---|---|---|"]
        for name, lo, hi in sectors():
            s = [r for r in rows if lo <= r["from"] < hi]
            if s:
                L.append(f"| {name} ({lo}–{hi}°) | {len(s)} | {cell([r['mop'] for r in s])} | "
                         f"{cell([r['break_5m_eq'] for r in s])} | {cell([r['normal_mop_eq'] for r in s])} | "
                         f"{cell([r['mop_eq'] for r in s])} | {cell([r['mop_hard'] for r in s])} |")
        L += ["", "Ratios, hour by hour, median [10th, 90th] (MOP from 10.77 m in brackets):", "",
              "| 46232 from | chain-at-MOP / MOP, eq | hard | 5 m / chain-at-MOP | 5 m / normal 10 m | normal 10 m / chain-at-MOP |",
              "|---|---|---|---|---|---|"]
        for name, lo, hi in sectors():
            s = [r for r in rows if lo <= r["from"] < hi]
            if not s:
                continue
            ok = [r for r in s if r["mop"] > 0 and r["mop_eq"] > 0]
            L.append(f"| {name} | {cell([r['mop_eq'] / r['mop'] for r in ok])} "
                     f"({q([r['mop_eq'] / r['mop_navd'] for r in ok], .5):.2f}) | "
                     f"{cell([r['mop_hard'] / r['mop'] for r in ok])} | "
                     f"{cell([r['break_5m_eq'] / r['mop_eq'] for r in ok])} | "
                     f"{cell([r['break_5m_eq'] / r['normal_mop_eq'] for r in ok if r['normal_mop_eq'] > 0])} | "
                     f"{cell([r['normal_mop_eq'] / r['mop_eq'] for r in ok])} |")
        # By period.
        L += ["", "chain-at-MOP / MOP (eq) by 46232's swell peak period:", "",
              "| 46232 from | " + " | ".join(f"{a}–{b} s" for a, b in PERIOD_BANDS) + " |",
              "|---|" + "---|" * len(PERIOD_BANDS)]
        for name, lo, hi in sectors():
            cells = []
            for a, bb in PERIOD_BANDS:
                s = [r for r in rows if lo <= r["from"] < hi and a <= r["tp"] < bb and r["mop"] > 0]
                cells.append(f"{q([r['mop_eq'] / r['mop'] for r in s], .5):.2f} (n {len(s)})" if s else "–")
            L.append(f"| {name} | " + " | ".join(cells) + " |")
        # By frequency: the chain's energy up to a cut, against MOP's whole Hs.
        L += ["", "chain-at-MOP (eq, maximum entropy) with only its energy up to a frequency, over MOP's "
              "whole Hs; and with the whole spectrum read by Fourier instead:", "",
              "| 46232 from | " + " | ".join(f"≤ {fc:g} Hz" for fc in CUTS_HZ) + " | Fourier, all |",
              "|---|" + "---|" * (len(CUTS_HZ) + 1)]
        for name, lo, hi in sectors():
            s = [r for r in rows if lo <= r["from"] < hi and r["mop"] > 0]
            if s:
                L.append(f"| {name} | " + " | ".join(f"{q([r[('cut', fc)] / r['mop'] for r in s], .5):.2f}"
                                                     for fc in CUTS_HZ)
                         + f" | {q([r['mop_eq_fourier'] / r['mop'] for r in s], .5):.2f} |")
        L += ["", "Peak period over the same water (MOP's Tp; chain-at-MOP's densest bin), by 46232's "
              "overall peak:", "",
              "| 46232 peak | n | MOP Tp | chain-at-MOP peak | hours MOP Tp < 9 s | hours chain peak < 9 s |",
              "|---|---:|---|---|---:|---:|"]
        for name, lo, hi in (("< 9 s", 0, 9), ("9–12 s", 9, 12), ("≥ 12 s", 12, 99)):
            s = [r for r in rows if lo <= r["buoy_peak_s"] < hi]
            if s:
                L.append(f"| {name} | {len(s)} | {cell([r['tp_mop'] for r in s])} | "
                         f"{cell([r['mop_peak_s'] for r in s])} | {sum(r['tp_mop'] < 9 for r in s)} | "
                         f"{sum(r['mop_peak_s'] < 9 for r in s)} |")
        # By kind of ray.
        L += ["", "Share of chain-at-MOP's diffracted energy by kind of ray (sector totals), and "
              "chain-at-MOP / MOP with only the clear rays:", "",
              "| 46232 from | " + " | ".join(KINDS) + " | clear only / MOP |",
              "|---|" + "---|" * (len(KINDS) + 1)]
        for name, lo, hi in sectors():
            s = [r for r in rows if lo <= r["from"] < hi and r["mop"] > 0]
            if not s:
                continue
            tot = sum(r["parts"]["mop"]["kinds"] for r in s)
            share = tot / max(tot.sum(), 1e-30)
            clear = [4 * math.sqrt(r["parts"]["mop"]["kinds"][0]) / r["buoy"] / r["mop"] for r in s]
            L.append(f"| {name} | " + " | ".join(f"{100 * share[k]:.1f}%" for k in range(len(KINDS)))
                     + f" | {cell(clear)} |")
        # By offshore heading.
        L += ["", "Where chain-at-MOP's energy comes from offshore (diffracted, sector totals, share by "
              "10° of offshore heading; ≥ 3% shown) beside `break_5m`'s:", ""]
        for name, lo, hi in sectors()[:4]:
            s = [r for r in rows if lo <= r["from"] < hi]
            if not s:
                continue
            parts = []
            for v in ("mop", "break_5m"):
                h = sum(r["parts"][v]["heading"] for r in s)
                h10 = h.reshape(36, 2).sum(axis=1)
                h10 = h10 / max(h10.sum(), 1e-30)
                parts.append(", ".join(f"{10 * k}°s {100 * x:.0f}%" for k, x in enumerate(h10) if x >= 0.03))
            L.append(f"- **{name}** — MOP point: {parts[0]}; break 5 m: {parts[1]}")
        L += ["", "Direction over the same water: MOP's peak direction (Dp) against the heading "
              "chain-at-MOP's energy arrives on in the 46232 bin nearest MOP's Tp:", "",
              "| 46232 from | MOP Dp | chain-at-MOP | chain − MOP |", "|---|---|---|---|"]
        for name, lo, hi in sectors():
            s = [r for r in rows if lo <= r["from"] < hi and r["dp_mop"] == r["dp_mop"]
                 and r["mop_dir"] == r["mop_dir"]]
            if s:
                d = [((r["mop_dir"] - r["dp_mop"] + 180) % 360) - 180 for r in s]
                L.append(f"| {name} | {cell([r['dp_mop'] for r in s])} | {cell([r['mop_dir'] for r in s])} | "
                         f"{cell(d)} |")
        comb = combs[b]
        period = next(iter(comb.values()))[1]
        bins = sorted({k for c, _ in comb.values() for k in c})
        L += ["", f"Acceptance per offshore degree at {period:.1f} s (Σ width·diff_gain/Ks² per radian, "
              "10° bins; planar-beach Kr² ≤ 1), by start:", "",
              "| offshore from | " + " | ".join(comb) + " |", "|---|" + "---|" * len(comb)]
        for k in bins:
            if 150 <= k < 320:
                L.append(f"| {k}–{k + 10}° | " + " | ".join(f"{c.get(k, 0.0):.2f}" for c, _ in comb.values()) + " |")
        L.append("")
        if bands and b in bands:
            L += bands[b]
    if files:
        L += files
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    from .nearshore import BREAKS
    from .transform import load_spectra

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--break", dest="only", choices=BREAKS)
    ap.add_argument("--control", action="store_true", help="build and check break_5m only")
    ap.add_argument("--refresh", action="store_true", help="rebuild cached tables")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--point", dest="points", action="append", default=None,
                    help="a point that is not a break, from points.json's \"points\" (default: every one; "
                         "repeatable); none with --break")
    args = ap.parse_args(argv)
    doc = json.loads((MOP_DIR / "points.json").read_text())
    points = doc["breaks"]
    extra_pts = {k: v for k, v in doc.get("points", {}).items()
                 if not args.only and (args.points is None or k in args.points)}
    if args.points and set(args.points) - set(extra_pts):
        print(f"not in points.json's points: {sorted(set(args.points) - set(extra_pts))}", file=sys.stderr)
        return 1
    bathy = rt.Bathymetry.load()
    msl = bathy.msl_offset_m
    breaks = [b for b in BREAKS if b in points and (not args.only or b == args.only)]
    controls = {b: control(b, points[b]) for b in breaks}
    if extra_pts:
        pc = point_control(points)
        if pc is not None:
            controls["point path"] = pc
    for b, (bad, n) in controls.items():
        print(f"{b}: control {bad} of {n} rows differ", flush=True)
    if args.control:
        return 1 if any(bad for bad, _ in controls.values()) else 0
    if any(bad for bad, _ in controls.values()):
        print("control failed: the tables are not reproduced; not reading anything", file=sys.stderr)
        return 1
    spectra = list(load_spectra(ROOT / "data" / "spectra" / "46232"))
    results, metas, combs = {}, {}, {}
    band_sections, specs = {}, {}
    for b in breaks:
        built = {v: build(b, v, points[b], refresh=args.refresh) for v in VARIANTS}
        metas[b] = {v: m for v, (_, m) in built.items()}
        arrays = {v: Arrays(rows, float(m["start_depth_m"])) for v, (rows, m) in built.items()}
        tables = {"break_5m": arrays["break_5m"], "normal_mop": arrays["normal_mop"],
                  "mop": arrays["mop"].merged(arrays["mop_back"]), "mop_back": arrays["mop_back"]}
        combs[b] = {v: acceptance(rows, float(m["start_depth_m"]), 14.3)
                    for v, (rows, m) in (("break_5m", built["break_5m"]), ("normal_mop", built["normal_mop"]),
                                         ("mop", (built["mop"][0] + built["mop_back"][0], built["mop"][1])))}
        mop = read_mop(MOP_DIR / f"{b}.csv")
        spec, why = read_mop_spectrum(MOP_DIR, b)
        coarse = common_bands(spec["bands"], spectra[0].frequencies) if spec else None
        conv, conv_med = convention(spec, mop) if spec else (None, {})
        results[b] = hours(b, mop, spectra, tables, float(points[b]["depth_m"]),
                           float(points[b]["depth_m"]) + msl, spec, coarse, conv)
        band_sections[b] = band_report(results[b], spec, why, coarse, conv, conv_med)
        specs[b] = (spec, why)
        print(f"{b}: {len(results[b])} hours; spectrum {'read' if spec else why}; convention {conv}", flush=True)
    extra: list[str] = []
    if extra_pts:
        all_t = [set(read_mop(MOP_DIR / f"{b}.csv")) for b in BREAKS if (MOP_DIR / f"{b}.csv").exists()]
        common_t = set.intersection(*all_t) if all_t else None
        places, edges, sections, coarse_any = {}, {}, [], None
        for b in breaks:
            n = mop_normal(json.loads((MOP_DIR / f"{b}_meta.json").read_text())) \
                if (MOP_DIR / f"{b}_meta.json").exists() else None
            pl = [w for w in (windows_at(b, points[b], n) if n is not None else []) if "Point Loma" in w]
            edges[b] = f"Point Loma {pl[-1].split(' – ')[-1].split('°')[0]}°" if pl else "?"
            places[b] = results[b]
        # The grid control: a point outside the 8 m grid is traced on the 32 m
        # one, so Center's MOP point is traced on that alone too, and its
        # band ratios go beside the shipped seabed's.
        c = "coronado_center"
        if c in breaks and specs.get(c, (None, ""))[0] is not None:
            built = {v: build(c, v, points[c], refresh=args.refresh, coarse_seabed=True)
                     for v in ("mop", "mop_back")}
            arr = {v: Arrays(rows, float(m["start_depth_m"])) for v, (rows, m) in built.items()}
            spec_c = specs[c][0]
            coarse_c = common_bands(spec_c["bands"], spectra[0].frequencies)
            conv_c, _ = convention(spec_c, read_mop(MOP_DIR / f"{c}.csv"))
            cname = f"{c}, 32 m seabed"
            places[cname] = hours(c, read_mop(MOP_DIR / f"{c}.csv"), spectra,
                                  {"mop": arr["mop"].merged(arr["mop_back"]), "mop_back": arr["mop_back"]},
                                  float(points[c]["depth_m"]), float(points[c]["depth_m"]) + msl,
                                  spec_c, coarse_c, conv_c)
            edges[cname] = edges[c]
            print(f"{cname}: {len(places[cname])} hours (grid control)", flush=True)
        for name, p in extra_pts.items():
            meta_path = MOP_DIR / f"{name}_meta.json"
            normal = mop_normal(json.loads(meta_path.read_text())) if meta_path.exists() else None
            if normal is None:
                sections += [f"## {name}", "", "Not compared: no `metaShoreNormal` in its saved meta file "
                             "(run `collector.mop --points extra` on Actions).", ""]
                continue
            built = {v: build(name, v, p, refresh=args.refresh, normal=normal) for v in ("mop", "mop_back")}
            arrays = {v: Arrays(rows, float(m["start_depth_m"])) for v, (rows, m) in built.items()}
            tables = {"mop": arrays["mop"].merged(arrays["mop_back"]), "mop_back": arrays["mop_back"]}
            mop_all = read_mop(MOP_DIR / f"{name}.csv")
            mop = {t: v for t, v in mop_all.items() if common_t is None or t in common_t}
            spec, why = read_mop_spectrum(MOP_DIR, name)
            coarse = common_bands(spec["bands"], spectra[0].frequencies) if spec else None
            conv, conv_med = convention(spec, mop) if spec else (None, {})
            rows = hours(name, mop, spectra, tables, float(p["depth_m"]), float(p["depth_m"]) + msl,
                         spec, coarse, conv)
            x, y = rt.to_utm(float(p["lat"]), float(p["lon"]))
            h, _, _, cellm, _ = bathy.sample(np.array([x]), np.array([y]))
            wins = windows_at(name, p, normal)
            pl = [w for w in wins if "Point Loma" in w]
            edges[name] = f"Point Loma {pl[-1].split(' – ')[-1].split('°')[0]}°" if pl else "?"
            comb = acceptance(built["mop"][0] + built["mop_back"][0], float(built["mop"][1]["start_depth_m"]), 14.3)
            sections += point_report(name, p, normal, {v: m for v, (_, m) in built.items()}, rows, wins,
                                     (float(h[0]), float(cellm[0])), (len(mop), len(mop_all)), comb)
            sections += band_report(rows, spec, why, coarse, conv, conv_med)
            places[name] = rows
            coarse_any = coarse_any or coarse
            specs[name] = (spec, why)
            print(f"{name}: {len(rows)} hours; normal {normal}; spectrum {'read' if spec else why}", flush=True)
        if coarse_any and len(places) > 1:
            extra = exposed_report(places, coarse_any, edges) + sections
        else:
            extra = sections
    text = report(results, metas, controls, points, combs, band_sections,
                  files_report({**points, **extra_pts}, specs), extra)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
