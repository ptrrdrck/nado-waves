"""Score the chain and MOP against an observation: one year at Imperial Beach Nearshore.

The owner's question (handoff item 24, 2026-11-20) is whether the chain's
deep-water-to-10 m leg should give way to CDIP MOP's. §56a–§56d could only
show where two models disagree. This scores both against a wave buoy.

THE VERIFICATION SERIES: CDIP 155, Imperial Beach Nearshore (NDBC 46235), a
Datawell Waverider in ~21 m, its primary QC flag 1, over the year
`collector.nearshore_test` chose by its fixed rule (`data/nearshore_test/`).
It judges the deep-water-to-21 m leg at Imperial Beach, outside Point Loma's
shadow. It is not a break, it is not Coronado, and nothing here is a
verification of a break forecast.

Three comparisons, all on the same hours:

- **The chain at the buoy, exactly**: tables traced from the buoy's own
  position at the seabed's depth there (both half-fans, so every heading),
  46232's spectrum (CDIP 191, the chain's input) carried hour by hour (MEM,
  as shipped), the local spectrum at 21 m set against the buoy's. No
  de-shoaling, no proxy. Before friction, and with the table's JONSWAP
  friction as a bracket (Madsen is not tabulated at this point).
- **MOP and the chain at MOP's point D0043** (10 m, 1.9 km inshore of the
  buoy), both deep-water-equivalent, against the buoy de-shoaled from its
  depth band by band. Like for like between the models, approximate against
  the observation: the two places differ, and `chain at D0043 / chain at the
  buoy` (deep-water-equivalent) is the chain's own estimate of how much.
- Direction per band: the buoy's mean direction against each model's.

Controls: CDIP's 191 converted to NDBC's form against this repository's NDBC
archive of 46232 on the hours both hold (the input is the input); every
read-back; the chain at the buoy from a second position (the deployments'
spread); MOP's inputs (if 155 drove MOP, MOP is not independent).

Report only and precompute-side (numpy; no workflow runs it). Nothing is
fitted and nothing ships.

THE SERIES ARE NOT TRACKED (~90 MB; owner's call, 2026-11-21): only
`fetch.json` and the meta and band files are. To re-run, put run 9's series
back first: `git checkout 38e295e -- data/nearshore_test` (the commit that
held them), or a later run's `nearshore-test-<run id>` artifact unpacked
into `data/nearshore_test/`. The tables rebuild into `data/live/` (~25 min
cold).
"""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import mopdepth as md
from . import raytrace as rt
from .mopcheck import MATCH_S, SECTORS, mean_from
from .nearshore import density_grids, shoaling_squared
from .transform import Spectrum, load_spectra

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "nearshore_test"
CACHE = ROOT / "data" / "live" / "nearshoretest"
REPORT = ROOT / "docs" / "nearshore_test.md"
OBS, INP = "imperial_beach_nearshore", "point_loma_south"
#: The coarse bands every comparison is read in (mopdepth's), clipped below to
#: the lowest frequency all three series cover.
EDGES = md.BAND_EDGES_HZ
MIN_HS = md.BAND_MIN_HS
GOOD_FLAG = 1
#: Observed-Hs classes (m) for the size table.
SIZES = ((0.0, 0.75), (0.75, 1.0), (1.0, 1.5), (1.5, 2.0), (2.0, 9.9))


# ------------------------------------------------------------------ inputs

def read_series(name: str) -> dict:
    """A buoy's or MOP's saved spectrum (mopdepth's reader: refused unless the
    read-back passed), with its Hs and QC flag by time."""

    if not (DATA / f"{name}_spectrum.csv").exists():
        raise SystemExit(f"{name}: the series are not tracked; `git checkout 38e295e -- data/nearshore_test` "
                         "or unpack a `nearshore-test-<run id>` artifact there first (module docstring)")
    spec, why = md.read_mop_spectrum(DATA, name)
    if spec is None:
        raise SystemExit(f"{name}: {why}")
    hs, flag = {}, {}
    with (DATA / f"{name}.csv").open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            t = datetime.fromisoformat(r["valid_utc"].replace("Z", "+00:00"))
            hs[t] = float(r["hs_m"]) if r["hs_m"] else None
            if "flag_primary" in r:
                flag[t] = int(r["flag_primary"]) if r["flag_primary"] else None
    spec["hs"], spec["flag"] = hs, flag
    spec["times"] = sorted(spec["energy"])
    return spec


def nearest(times: list[datetime], t: datetime) -> datetime | None:
    i = bisect.bisect_left(times, t)
    near = [times[j] for j in (i - 1, i) if 0 <= j < len(times)
            and abs((times[j] - t).total_seconds()) <= MATCH_S]
    return min(near, key=lambda x: abs((x - t).total_seconds())) if near else None


def to_spectrum(t: datetime, spec: dict, freqs: list[float]) -> Spectrum | None:
    """CDIP's energy and a1-b2 in NDBC's form: α1 = atan2(b1, a1) FROM
    (CDIP's convention, §56c), r1 = |(a1, b1)|, α2 = ½·atan2(b2, a2),
    r2 = |(a2, b2)|. None if the record has a gap."""

    e, m = spec["energy"].get(t), (spec["moments"] or {}).get(t)
    if e is None or m is None or any(x is None for x in e) or any(x is None for x in m):
        return None
    n = len(e)
    a1, b1, a2, b2 = m[:n], m[n:2 * n], m[2 * n:3 * n], m[3 * n:]
    return Spectrum(time=t, frequencies=list(freqs), c11=list(e),
                    a1=[math.degrees(math.atan2(y, x)) % 360 for x, y in zip(a1, b1)],
                    a2=[(0.5 * math.degrees(math.atan2(y, x))) % 360 for x, y in zip(a2, b2)],
                    r1=[math.hypot(x, y) for x, y in zip(a1, b1)],
                    r2=[math.hypot(x, y) for x, y in zip(a2, b2)])


#: NDBC's text files round the band centres to three decimals (0.101 for
#: CDIP's 0.10125): the same band within this.
BAND_TOL_HZ = 5e-4


def same_bands(a: list[float], b: list[float]) -> bool:
    return len(a) == len(b) and max(abs(x - y) for x, y in zip(a, b)) <= BAND_TOL_HZ


def shipped_frequencies(cdip: list[float]) -> list[float]:
    """46232's bins as the shipped chain reads them (NDBC's), when CDIP's are
    the same bands: so the input carries exactly as it would in production."""

    ndbc = rt.frequencies()
    if not same_bands(ndbc, cdip):
        raise SystemExit(f"CDIP 191's bands are not NDBC's 46232 bands: {cdip[:4]}… against {ndbc[:4]}…")
    return ndbc


#: NDBC's 46232 feed is quantised (energy density in steps of ~0.011 m²/Hz,
#: directions in 4°): per-bin agreement is read only where a step is a few
#: per cent of the value.
CONTROL_MIN_C11 = 0.2
#: Swell, where the dispute is (≥ 8 s), against the shorter-period tail.
SWELL_HZ = 0.125


def control_input(spec_control: dict) -> dict:
    """CDIP's 191 against this repository's NDBC archive of 46232, on the
    records both hold at the SAME time (CDIP every 30 min, NDBC hourly): the
    same buoy through two archives must agree to NDBC's quantisation."""

    freqs = shipped_frequencies([b[0] for b in spec_control["bands"]])
    ndbc = {s.time: s for s in load_spectra(ROOT / "data" / "spectra" / "46232")}
    hs, dc, da, dr = [], [], [], []
    split_hs: dict[str, list[float]] = {"swell": [], "tail": []}
    for t in sorted(spec_control["energy"]):
        ref, sp = ndbc.get(t), to_spectrum(t, spec_control, freqs)
        if ref is None or sp is None:
            continue
        if not same_bands(ref.frequencies, freqs):
            return {"hours": 0, "problem": f"bands differ: NDBC {ref.frequencies[:3]}…, CDIP {freqs[:3]}…"}
        m = [sum(c * x.bin_width(i) for i, c in enumerate(x.c11) if c == c and c > 0) for x in (sp, ref)]
        if m[1] > 0:
            hs.append(math.sqrt(m[0] / m[1]) - 1)
        for part, keep in (("swell", lambda f: f <= SWELL_HZ), ("tail", lambda f: f > SWELL_HZ)):
            mm = [sum(c * x.bin_width(i) for i, c in enumerate(x.c11) if c == c and c > 0 and keep(freqs[i]))
                  for x in (sp, ref)]
            if mm[1] > 0:
                split_hs[part].append(math.sqrt(mm[0] / mm[1]) - 1)
        for i in range(len(freqs)):
            c, r = sp.c11[i], ref.c11[i]
            if r == r and r >= CONTROL_MIN_C11:
                dc.append(c / r - 1)
                if ref.r1[i] == ref.r1[i] and ref.r1[i] > 0.3:
                    da.append(((sp.a1[i] - ref.a1[i] + 180) % 360) - 180)
                    dr.append(sp.r1[i] - ref.r1[i])
    q = lambda v: (float(np.median(np.abs(v))), float(np.percentile(np.abs(v), 99))) if v else (float("nan"),) * 2
    return {"hours": len(hs), "bins": len(dc), "hs_rel": q(hs), "hs_bias": float(np.median(hs)) if hs else float("nan"),
            "c11_rel": q(dc), "c11_bias": float(np.median(dc)) if dc else float("nan"),
            "alpha1_deg": q(da), "r1": q(dr),
            "split": {k: (float(np.median(v)), float(np.percentile(v, 10)), float(np.percentile(v, 90)))
                      for k, v in split_hs.items() if v}}


# ------------------------------------------------------------------ tables

def point_dict(name: str, lat: float, lon: float) -> dict:
    return {"point": name, "lat": lat, "lon": lon}


def table_at(name: str, point: dict, normal: float, h_ref: float, back: bool, refresh: bool = False):
    """`raytrace.table` from `point` on `normal` (or its back half) at h_ref,
    cached; the shipped frequencies, headings, islands and edges."""

    tag = f"{name}_{'back' if back else 'fwd'}"
    csv_path, meta_path = CACHE / f"{tag}.csv", CACHE / f"{tag}.json"
    if csv_path.exists() and meta_path.exists() and not refresh:
        with csv_path.open(newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh)), json.loads(meta_path.read_text())
    bathy = rt.Bathymetry.load()
    _, blockers = rt.load()
    spot = md.point_spot(name, point, normal, back=back)
    rows, meta = rt.table(bathy, spot, blockers, rt.frequencies(), h_ref=h_ref)
    meta.update({"normal_deg": round(spot.normal, 3), "point": point})
    CACHE.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=rt.FIELDS)
        w.writeheader()
        w.writerows(rows)
    meta_path.write_text(json.dumps(meta, indent=1))
    return [{k: str(v) for k, v in r.items()} for r in rows], meta


class Comb:
    """Both half-fans' carrying rows as arrays per frequency, with the
    friction column (the table's JONSWAP survival) beside the gain."""

    def __init__(self, halves: list[tuple[list[dict], dict]]):
        self.start_depth_m = float(np.mean([m["start_depth_m"] for _, m in halves]))
        by: dict[float, list[dict]] = {}
        from .nearshore import parse_fan

        for rows, _ in halves:
            for r in rows:
                if float(r["diff_gain"]) > 0:
                    # A headland fill, one entry per heading of its fan (§61).
                    for h, w in (parse_fan(r.get("diff_fan")) or ((None, 1.0),)):
                        by.setdefault(float(r["freq_hz"]), []).append(
                            r if h is None else {**r, "diff_off_from_deg": h,
                                                 "diff_gain": float(r["diff_gain"]) * w})
        self.freqs = sorted(by)
        self.f = {f: {"w": np.array([math.radians(float(r["near_width_deg"])) for r in rs]),
                      "near": np.radians([float(r["near_from_deg"]) for r in rs]),
                      "doff": np.array([float(r["diff_off_from_deg"]) for r in rs]),
                      "dgain": np.array([float(r["diff_gain"]) for r in rs]),
                      "fric": np.array([float(r["diff_friction"]) for r in rs])}
                  for f, rs in by.items()}

    def carry(self, sp: Spectrum, grids: dict) -> dict:
        """Per 46232 bin: local energy density at the start (m²/Hz), with the
        JONSWAP friction too, and the arrival vector."""

        out = {"e": np.zeros(len(sp.frequencies)), "e_fric": np.zeros(len(sp.frequencies)),
               "s": np.zeros(len(sp.frequencies)), "c": np.zeros(len(sp.frequencies))}
        for i, f in enumerate(sp.frequencies):
            g = grids.get(i)
            if g is None or not self.freqs:
                continue
            near = min(self.freqs, key=lambda t: abs(t - f))
            if abs(near - f) > 0.05 * f:
                continue
            a = self.f[near]
            v = md.interp(np.asarray(g), a["doff"]) * a["w"] * a["dgain"]
            out["e"][i] = v.sum()
            out["e_fric"][i] = (v * a["fric"]).sum()
            out["s"][i] = (v * np.sin(a["near"])).sum()
            out["c"][i] = (v * np.cos(a["near"])).sum()
        return out


class Shipped:
    """The chain AS SHIPPED at a point: `raytrace.table` with Madsen's friction
    tabulated for the table's own start depth (`h_ref`, so the local sea is
    read at 21 m, not 5), loaded by `nearshore.Table.load` and carried by
    `nearshore.carry` itself (friction="madsen", the coast tide unknown for
    2024, so MSL). Both half-fans, each carried on its own: the back half
    takes 0.5% of the energy at the buoy, and its Madsen sea is its own."""

    def __init__(self, name: str, point: dict, normal: float, h_ref: float, refresh: bool = False):
        from .nearshore import Table

        out = CACHE / "shipped"
        self.tables = []
        for back in (False, True):
            tag = f"{name}_{'back' if back else 'fwd'}"
            if refresh or not (out / f"{tag}_madsen.json").exists():
                bathy = rt.Bathymetry.load()
                _, blockers = rt.load()
                spot = md.point_spot(tag, point, normal, back=back)
                madsen: dict = {}
                rows, meta = rt.table(bathy, spot, blockers, rt.frequencies(), madsen_out=madsen, h_ref=h_ref)
                meta["break"] = tag
                rt.write(rows, meta, out)
                rt.write_madsen(madsen, tag, out)
            self.tables.append(Table.load(tag, out))
        self.start_depth_m = self.tables[0].start_depth_m
        self.arrays = [{f: (np.array([h for r in rays for h, _ in r.samples()]),
                            np.array([r.width_rad * r.diff_gain * w for r in rays
                                      for _, w in r.samples()]))
                        for f, rays in t.by_freq.items()} for t in self.tables]

    def carry(self, sp: Spectrum, grids: dict) -> np.ndarray:
        """Local energy density per 46232 bin at the start, after Madsen."""

        from .nearshore import carry

        e = np.zeros(len(sp.frequencies))
        for table, arrays in zip(self.tables, self.arrays):
            got = carry(sp, table, grids=grids, tide_m=None, friction="madsen")
            freqs = sorted(table.by_freq)
            for i, f in enumerate(sp.frequencies):
                g = grids.get(i)
                if g is None or not freqs:
                    continue
                near = min(freqs, key=lambda t: abs(t - f))
                if abs(near - f) > 0.05 * f:
                    continue
                doff, wg = arrays[near]
                # One share per heading: a fill's fan repeats its ray's (§61).
                fr = np.array([x if x is not None else 0.0
                               for ray, x in zip(table.by_freq[near], got.ray_friction.get(near, []))
                               for _ in ray.samples()])
                if fr.size != doff.size:
                    raise ValueError(f"{table.break_id} {near}: {fr.size} friction shares for {doff.size} rays")
                e[i] += float(np.sum(md.interp(np.asarray(g), doff) * wg * fr))
        return e


def quantisation(shipped: Shipped, control: dict) -> dict:
    """What NDBC's rounded feed does to the shipped chain at the buoy: the
    same tables carried from NDBC's archive of 46232 and from CDIP's 191 on
    the records both hold at the same time (August 2026; no observation then,
    so a ratio of two carries, not a score). Hs NDBC-fed over CDIP-fed, whole
    and split at 8 s."""

    freqs = shipped_frequencies([b[0] for b in control["bands"]])
    ndbc = {s.time: s for s in load_spectra(ROOT / "data" / "spectra" / "46232")}
    out = {"whole": [], "swell": [], "short": []}
    for t in sorted(control["energy"]):
        ref, sp = ndbc.get(t), to_spectrum(t, control, freqs)
        if ref is None or sp is None:
            continue
        es = []
        for x in (ref, sp):
            mem = x.with_spread("mem")
            es.append(shipped.carry(mem, density_grids(mem)) * [x.bin_width(i) for i in range(len(freqs))])
        for key, keep in (("whole", lambda f: True), ("swell", lambda f: f <= SWELL_HZ),
                          ("short", lambda f: f > SWELL_HZ)):
            m = [sum(e[i] for i, f in enumerate(freqs) if keep(f)) for e in es]
            if m[1] > 0:
                out[key].append(math.sqrt(m[0] / m[1]))
    return {k: (float(np.median(v)), float(np.percentile(v, 10)), float(np.percentile(v, 90)), len(v))
            for k, v in out.items() if v}


# ------------------------------------------------------------------ bands

def coarse_bands(lows: list[float], highs: list[float]) -> list[tuple[float, float]]:
    """mopdepth's bands clipped to the range every series covers (MOP's 20
    bands stop at 0.45 Hz, the buoys' at 0.58)."""

    lo, hi = max(lows), min(highs)
    out = []
    for a, b in zip(EDGES[:-1], EDGES[1:]):
        a, b = max(a, lo), min(b, hi)
        if b > a:
            out.append((a, b))
    return out


def in_bands(values: list[tuple[float, float, float]], coarse) -> np.ndarray:
    return np.array(md.split(values, coarse))


def series_bands(row: list[float], bands, coarse, depth: float | None = None) -> np.ndarray:
    """Energy (m²) per coarse band of a saved series; de-shoaled band by band
    to deep water when `depth` is given."""

    return in_bands([(e * (hi - lo) / (shoaling_squared(fc, depth) if depth else 1.0), lo, hi)
                     for e, (fc, lo, hi) in zip(row, bands)], coarse)


def series_direction(row, mom, bands, coarse) -> np.ndarray:
    """Energy-weighted mean direction FROM per coarse band, from a1/b1."""

    n = len(row)
    a1, b1 = mom[:n], mom[n:2 * n]
    s = in_bands([(e * (hi - lo) * y, lo, hi) for e, y, (_, lo, hi) in zip(row, b1, bands)], coarse)
    c = in_bands([(e * (hi - lo) * x, lo, hi) for e, x, (_, lo, hi) in zip(row, a1, bands)], coarse)
    return np.degrees(np.arctan2(s, c)) % 360


def chain_bands(sp: Spectrum, part: np.ndarray, coarse, edges, depth: float | None = None) -> np.ndarray:
    return in_bands([(part[i] * sp.bin_width(i) / (shoaling_squared(f, depth) if depth else 1.0), lo, hi)
                     for i, (f, (lo, hi)) in enumerate(zip(sp.frequencies, edges))], coarse)


def chain_direction(sp: Spectrum, c: dict, coarse, edges) -> np.ndarray:
    s = in_bands([(c["s"][i] * sp.bin_width(i), lo, hi) for i, (lo, hi) in enumerate(edges)], coarse)
    k = in_bands([(c["c"][i] * sp.bin_width(i), lo, hi) for i, (lo, hi) in enumerate(edges)], coarse)
    return np.degrees(np.arctan2(s, k)) % 360


# ------------------------------------------------------------------ the year

def run(refresh: bool = False, every: int = 1) -> dict:
    fetch = json.loads((DATA / "fetch.json").read_text(encoding="utf-8"))
    pid = fetch["mop"]["point"]
    obs, inp, mop = read_series(OBS), read_series(INP), read_series(f"mop_{pid}")
    census = json.loads((ROOT / "data" / "nearshore_census" / "census.json").read_text(encoding="utf-8"))
    site = census["stations"]["46235"]

    # Where the buoy is: CDIP's own geospatial extent over its deployments.
    g = obs["meta"]["global"]
    lat_lo, lat_hi = g["geospatial_lat_min"], g["geospatial_lat_max"]
    lon_lo, lon_hi = g["geospatial_lon_min"], g["geospatial_lon_max"]
    buoy = point_dict("ib_nearshore_buoy", 0.5 * (lat_lo + lat_hi), 0.5 * (lon_lo + lon_hi))
    corner = point_dict("ib_nearshore_buoy_corner", lat_hi, lon_lo)
    mop_pt = point_dict(f"ib_nearshore_{pid}", site["mop"]["lat"], site["mop"]["lon"])
    normal = md.mop_normal(mop["meta"])
    if normal is None:
        raise SystemExit(f"{pid}: no metaShoreNormal in its small variables")
    bathy = rt.Bathymetry.load()
    seabed = {p["point"]: md.seabed_at(bathy, p["lat"], p["lon"]) for p in (buoy, corner, mop_pt)}
    # MOP's stated depth (its own metaWaterDepth), as mopdepth de-shoals it.
    m = re.search(r"metaWaterDepth,\s*([\d.]+)", mop["meta"].get("small_variables", {}).get("ascii", ""))
    mop_depth = float(m.group(1)) if m else md.MOP_H_REF
    obs_depth = seabed["ib_nearshore_buoy"]

    combs = {}
    for key, p, h in (("buoy", buoy, seabed["ib_nearshore_buoy"] - 0.5),
                      ("corner", corner, seabed["ib_nearshore_buoy_corner"] - 0.5),
                      ("mop", mop_pt, md.MOP_H_REF)):
        combs[key] = Comb([table_at(p["point"], p, normal, h, back, refresh) for back in (False, True)])
    shipped = Shipped("ib_nearshore_buoy_shipped", buoy, normal, seabed["ib_nearshore_buoy"] - 0.05, refresh)

    freqs_inp = shipped_frequencies([b[0] for b in inp["bands"]])
    edges = md.bin_edges(freqs_inp)
    coarse = coarse_bands([obs["bands"][0][1], mop["bands"][0][1], edges[0][0]],
                          [obs["bands"][-1][2], mop["bands"][-1][2], edges[-1][1]])
    rows = []
    for k, t in enumerate(sorted(mop["energy"])):
        if k % every:
            continue
        to, ti = nearest(obs["times"], t), nearest(inp["times"], t)
        if to is None or ti is None or obs["flag"].get(to) != GOOD_FLAG or inp["flag"].get(ti) != GOOD_FLAG:
            continue
        e_obs, m_obs, e_mop = obs["energy"][to], obs["moments"][to], mop["energy"][t]
        if any(x is None for x in e_obs) or any(x is None for x in m_obs) or any(x is None for x in e_mop):
            continue
        sp = to_spectrum(ti, inp, freqs_inp)
        if sp is None:
            continue
        mem = sp.with_spread("mem")
        grids = density_grids(mem)
        cb, cc, cm = (combs[x].carry(mem, grids) for x in ("buoy", "corner", "mop"))
        r = {"t": t, "from": mean_from(sp),
             "hs_obs": 4 * math.sqrt(sum(e * (hi - lo) for e, (_, lo, hi) in zip(e_obs, obs["bands"]))),
             "hs_inp": 4 * math.sqrt(sum(c * sp.bin_width(i) for i, c in enumerate(sp.c11) if c > 0)),
             "obs": series_bands(e_obs, obs["bands"], coarse),
             "obs_deq": series_bands(e_obs, obs["bands"], coarse, obs_depth),
             "mop_deq": series_bands(e_mop, mop["bands"], coarse, mop_depth),
             "inp": chain_bands(sp, np.array([c if c > 0 else 0.0 for c in sp.c11]), coarse, edges),
             "chain": chain_bands(sp, cb["e"], coarse, edges),
             "chain_fric": chain_bands(sp, cb["e_fric"], coarse, edges),
             "chain_deq": chain_bands(sp, cb["e"], coarse, edges, combs["buoy"].start_depth_m),
             "corner": chain_bands(sp, cc["e"], coarse, edges),
             "chain_mop_deq": chain_bands(sp, cm["e"], coarse, edges, combs["mop"].start_depth_m),
             "dir_obs": series_direction(e_obs, m_obs, obs["bands"], coarse),
             "dir_chain": chain_direction(sp, cb, coarse, edges),
             "dir_chain_mop": chain_direction(sp, cm, coarse, edges),
             "dir_mop": series_direction(e_mop, mop["moments"][t], mop["bands"], coarse)
             if mop["moments"] and mop["moments"].get(t) and None not in mop["moments"][t] else None}
        r["hs_chain"] = 4 * math.sqrt(float(np.sum(cb["e"] * [sp.bin_width(i) for i in range(len(sp.c11))])))
        r["hs_chain_fric"] = 4 * math.sqrt(float(np.sum(cb["e_fric"] * [sp.bin_width(i) for i in range(len(sp.c11))])))
        r["hs_corner"] = 4 * math.sqrt(float(np.sum(cc["e"] * [sp.bin_width(i) for i in range(len(sp.c11))])))
        es = shipped.carry(mem, grids)
        r["shipped"] = chain_bands(sp, es, coarse, edges)
        r["hs_shipped"] = 4 * math.sqrt(float(np.sum(es * [sp.bin_width(i) for i in range(len(sp.c11))])))
        rows.append(r)
    ctrl = control_input(read_series(f"{INP}_control"))
    quant = quantisation(shipped, read_series(f"{INP}_control"))
    return {"rows": rows, "coarse": coarse, "control": ctrl, "quant": quant, "shipped_start": shipped.start_depth_m,
            "fetch": fetch, "pid": pid, "normal": normal,
            "buoy": buoy, "corner": corner, "mop_pt": mop_pt, "seabed": seabed, "mop_depth": mop_depth,
            "starts": {k: c.start_depth_m for k, c in combs.items()},
            "readbacks": {n: s["meta"]["spectrum"]["readback"] for n, s in
                          ((OBS, obs), (INP, inp), (f"mop_{pid}", mop))},
            "flags": obs["meta"].get("flags"), "inputs": fetch["mop"].get("inputs", {}),
            "driven_by_obs": fetch["mop"].get("hours_driven_by_the_observed_buoy")}


# ------------------------------------------------------------------ report

def q(v, p=None):
    v = [x for x in v if x == x]
    if not v:
        return "—"
    med = float(np.median(v))
    if p is None:
        return f"{med:.2f} [{np.percentile(v, 10):.2f}, {np.percentile(v, 90):.2f}]"
    return f"{med:.{p}f}"


def sector_of(d: float) -> str | None:
    for name, lo, hi in SECTORS:
        if lo <= d < hi:
            return name
    return None


def groups(rows):
    out = [(name, [r for r in rows if sector_of(r["from"]) == name]) for name, _, _ in SECTORS[:4]]
    return out + [("all", rows)]


def ratio(r, num: str, den: str, k: int | None = None) -> float:
    a, b = (r[num], r[den]) if k is None else (r[num][k], r[den][k])
    if k is not None and 4 * math.sqrt(max(b, 0.0)) < MIN_HS:
        return float("nan")
    return math.sqrt(a / b) if b > 0 and a >= 0 else float("nan")


def whole(r, key: str) -> float:
    return 4 * math.sqrt(max(float(np.sum(r[key])), 0.0))


def control_line(c: dict) -> str:
    if c.get("problem") or not c.get("bins"):
        return f"- **The input is the input: NOT CHECKED** — {c.get('problem', 'no common hours')}."
    return (f"- **The input is the input**: CDIP's 191, converted to NDBC's form, against this repository's NDBC "
            f"archive of 46232 on the {c['hours']} records both hold at the same time (August 2026). Hs |Δ|/Hs "
            f"median {c['hs_rel'][0]:.4f}, 99th {c['hs_rel'][1]:.4f} (signed median {c['hs_bias']:+.4f}); "
            f"energy density in bins ≥ {CONTROL_MIN_C11} m²/Hz ({c['bins']}), |Δ|/E median {c['c11_rel'][0]:.4f}, "
            f"99th {c['c11_rel'][1]:.4f}; α1 |Δ| median {c['alpha1_deg'][0]:.2f}°, 99th {c['alpha1_deg'][1]:.2f}° "
            f"(r1 > 0.3); r1 |Δ| median {c['r1'][0]:.4f}. CDIP over NDBC, Hs signed median [10th, 90th]: "
            + "; ".join(f"{'≥ 8 s' if k == 'swell' else '< 8 s'} {v[0]:+.3f} [{v[1]:+.3f}, {v[2]:+.3f}]"
                        for k, v in c.get("split", {}).items())
            + ". NDBC's feed is quantised and its small bins read low; CDIP's archive is neither, and the year "
            "below is carried from CDIP's. Where the models disagree (≥ 8 s) the two are the same input to about 1%.")


def quant_line(qt: dict) -> str:
    if not qt:
        return "- **NDBC's rounded feed through the shipped chain: NOT MEASURED.**"
    lab = {"whole": "whole", "swell": "≥ 8 s", "short": "< 8 s"}
    return ("- **What NDBC's rounded feed does to the shipped chain at the buoy** (the shipped tables fed NDBC's "
            "archive of 46232 and CDIP's 191 on the same records, August 2026; no observation then, so a ratio "
            "of two carries, not a score): Hs NDBC-fed / CDIP-fed, median [10th, 90th], "
            + "; ".join(f"{lab[k]} {v[0]:.3f} [{v[1]:.3f}, {v[2]:.3f}]" for k, v in qt.items())
            + f" over {next(iter(qt.values()))[3]} records. Production reads NDBC's feed; the year below is "
            "CDIP's.")


def report(res: dict) -> str:
    rows, coarse = res["rows"], res["coarse"]
    labels = [md.band_label(a, b) for a, b in coarse]
    f = res["fetch"]
    w = f["window"]
    c = res["control"]
    L = ["# The chain and MOP against an observation: one year at Imperial Beach Nearshore", "",
         f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC by `python -m forecast.nearshoretest` "
         "(precompute-side, numpy; not run by any workflow). Report only: nothing here is fitted or shipped.", "",
         "**Verification series: CDIP 155, Imperial Beach Nearshore (NDBC 46235)**, a Datawell Waverider, "
         f"primary QC flag {GOOD_FLAG} only, {w['start'][:10]} – {w['end'][:10]} "
         f"(the year `collector.nearshore_test` chose by its rule: {f['rule']}). It judges the leg from deep "
         "water to ~21 m at Imperial Beach, outside Point Loma's shadow. It is not a break and not Coronado.", "",
         f"Input: CDIP 191 (46232), MEM as shipped. MOP: `{w['product']}` at {res['pid']}. "
         f"{len(rows)} hours with all three (both buoys flag {GOOD_FLAG}, no gap, within "
         f"{MATCH_S // 60} min of MOP's hour). No lag between 46232 and the buoy (~30 km, about an hour of "
         "swell travel): hour-to-hour scatter, not bias.", "",
         "## Controls", "",
         control_line(c),
         quant_line(res.get("quant", {})),
         "- **Read-backs** (4·sqrt(Σ E·df) / Hs, median / worst): "
         + "; ".join(f"{n} {rb.get('median')} / {rb.get('worst')}" for n, rb in res["readbacks"].items()) + ".",
         f"- **QC flags** at the buoy over the year: {res['flags']}.",
         f"- **MOP's independence**: inputs {res['inputs']}; driven by 155 on {res['driven_by_obs']} hours.",
         f"- **Where the buoy is**: CDIP's extent over its deployments, {res['buoy']['lat']:.5f}, "
         f"{res['buoy']['lon']:.5f} (centre); seabed there {res['seabed']['ib_nearshore_buoy']:.2f} m MSL "
         f"(the chain's grid; the station states 21 m). Traced again from the extent's corner "
         f"({res['corner']['lat']:.5f}, {res['corner']['lon']:.5f}, seabed "
         f"{res['seabed']['ib_nearshore_buoy_corner']:.2f} m): Hs corner / centre "
         f"{q([r['hs_corner'] / r['hs_chain'] for r in rows if r['hs_chain'] > 0])}.",
         f"- Starts: buoy {res['starts']['buoy']:.2f} m, corner {res['starts']['corner']:.2f} m, "
         f"{res['pid']} {res['starts']['mop']:.2f} m (its seabed {res['seabed'][res['mop_pt']['point']]:.2f} m; "
         f"MOP states {res['mop_depth']} m). Fans on {res['pid']}'s `metaShoreNormal` {res['normal']:.2f}°, both "
         "halves, so every heading.", "",
         "## The score at the buoy (the chain, exactly; Hs over the observed Hs)", "",
         "Hs is the whole spectrum, 0.025–0.58 Hz on both sides. Median [10th, 90th]; bias and RMS in metres "
         "(model − observed).", "",
         "**The shipped chain** is the chain as it runs: Madsen's friction tabulated at this start "
         f"({res['shipped_start']:.2f} m) and carried by `nearshore.carry` itself, at MSL (no coast tide for "
         "2024). `before friction` and `JONSWAP` are the same tables without it and with the table's old "
         "fixed-share friction. All three are fed CDIP's 191; NDBC's rounded feed, which production reads, "
         "is in the controls.", "",
         "| 46232 from | n | observed Hs | 46232 Hs / observed | **shipped chain / observed** | bias, RMS (m) "
         "| before friction / observed | bias, RMS (m) | JONSWAP / observed | bias, RMS (m) |",
         "|---|---:|---|---|---|---|---|---|---|---|"]
    for name, rs in groups(rows):
        if not rs:
            continue
        rms = lambda v: math.sqrt(float(np.mean(np.square(v))))
        cols = []
        for key in ("hs_shipped", "hs_chain", "hs_chain_fric"):
            b = [r[key] - r["hs_obs"] for r in rs]
            cols.append(f"{q([r[key] / r['hs_obs'] for r in rs])} | {np.mean(b):+.2f}, {rms(b):.2f}")
        L.append(f"| {name} | {len(rs)} | {q([r['hs_obs'] for r in rs])} | {q([r['hs_inp'] / r['hs_obs'] for r in rs])} "
                 f"| " + " | ".join(cols) + " |")
    L += ["", "By the observed Hs (all directions; W–WNW in brackets, where §56 found the headline high on big "
          "days). MOP and its column are deep-water-equivalent against the buoy de-shoaled, as below:", "",
          "| observed Hs | n (W–WNW) | shipped chain / observed | bias (m) | before friction / observed "
          "| MOP / observed |", "|---|---|---|---|---|---|"]
    for lo, hi in SIZES:
        rs = [r for r in rows if lo <= r["hs_obs"] < hi]
        ws = [r for r in rs if sector_of(r["from"]) == "W-WNW"]
        if not rs:
            continue
        cell = lambda f: f"{q([f(r) for r in rs])} ({q([f(r) for r in ws], 2) if ws else '—'})"
        L.append(f"| {f"≥ {lo:g}" if hi > 9 else f"{lo:g}–{hi:g}"} m | {len(rs)} ({len(ws)}) "
                 f"| {cell(lambda r: r['hs_shipped'] / r['hs_obs'])} "
                 f"| {np.mean([r['hs_shipped'] - r['hs_obs'] for r in rs]):+.2f} "
                 f"| {cell(lambda r: r['hs_chain'] / r['hs_obs'])} "
                 f"| {cell(lambda r: whole(r, 'mop_deq') / whole(r, 'obs_deq'))} |")
    for title, key in (("the shipped chain", "shipped"), ("the chain before friction", "chain")):
        L += ["", f"By band, {title} / observed as heights at the buoy (√ energy ratio), median [10th, 90th]; "
              f"a band-hour counts when the observed band holds ≥ {MIN_HS} m:", "",
              "| 46232 from | " + " | ".join(labels) + " |", "|---|" + "---|" * len(labels)]
        for name, rs in groups(rows):
            if rs:
                L.append(f"| {name} | " + " | ".join(q([ratio(r, key, 'obs', k) for r in rs])
                                                    for k in range(len(coarse))) + " |")
    L += ["", "## Both models, deep-water-equivalent, against the buoy de-shoaled", "",
          f"MOP at {res['pid']} and the chain traced from {res['pid']}, both de-shoaled band by band from their "
          "start; the buoy de-shoaled from its seabed depth. Like for like between the two models; against the "
          "observation it carries the 1.9 km between the places, which the last column estimates from the "
          "chain's own two tables. Whole = the coarse bands summed.", "",
          "| 46232 from | n | MOP / observed | chain at MOP's point / observed | chain at the buoy / observed "
          "| chain at MOP's point / chain at the buoy |", "|---|---:|---|---|---|---|"]
    for name, rs in groups(rows):
        if rs:
            L.append(f"| {name} | {len(rs)} | {q([whole(r, 'mop_deq') / whole(r, 'obs_deq') for r in rs])} "
                     f"| {q([whole(r, 'chain_mop_deq') / whole(r, 'obs_deq') for r in rs])} "
                     f"| {q([whole(r, 'chain_deq') / whole(r, 'obs_deq') for r in rs])} "
                     f"| {q([whole(r, 'chain_mop_deq') / whole(r, 'chain_deq') for r in rs])} |")
    for title, key in (("MOP / observed", "mop_deq"), ("chain at MOP's point / observed", "chain_mop_deq")):
        L += ["", f"By band, {title}, deep-water-equivalent as heights:", "",
              "| 46232 from | " + " | ".join(labels) + " |", "|---|" + "---|" * len(labels)]
        for name, rs in groups(rows):
            if rs:
                L.append(f"| {name} | " + " | ".join(q([ratio(r, key, 'obs_deq', k) for r in rs])
                                                    for k in range(len(coarse))) + " |")
    L += ["", "## Direction by band", "",
          "The buoy's mean direction FROM (median) and each model's minus it (median [10th, 90th]); band-hours "
          f"with the observed band ≥ {MIN_HS} m. The chain at the buoy; MOP at its point, 1.9 km inshore, where "
          "refraction has turned the swell further.", ""]
    L += ["The last column is like for like between the models: the chain traced from MOP's own point, against "
          "MOP there.", "",
          "| 46232 from | band | observed | chain − observed | MOP − observed | chain at MOP's point − MOP |",
          "|---|---|---|---|---|---|"]
    circ = lambda d: ((d + 180) % 360) - 180
    for name, rs in groups(rows):
        for k, lab in enumerate(labels):
            ok = [r for r in rs if 4 * math.sqrt(max(r["obs"][k], 0)) >= MIN_HS]
            if len(ok) < 20:
                continue
            o = [r["dir_obs"][k] for r in ok]
            om = math.degrees(math.atan2(np.mean(np.sin(np.radians(o))), np.mean(np.cos(np.radians(o))))) % 360
            L.append(f"| {name} | {lab} | {om:.0f}° | {q([circ(r['dir_chain'][k] - r['dir_obs'][k]) for r in ok])} "
                     f"| {q([circ(r['dir_mop'][k] - r['dir_obs'][k]) for r in ok if r['dir_mop'] is not None])} "
                     f"| {q([circ(r['dir_chain_mop'][k] - r['dir_mop'][k]) for r in ok if r['dir_mop'] is not None])} |")
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=REPORT)
    ap.add_argument("--refresh", action="store_true", help="rebuild the cached tables")
    ap.add_argument("--every", type=int, default=1, help="every n-th MOP hour (a quick look)")
    args = ap.parse_args(argv)
    res = run(args.refresh, args.every)
    text = report(res)
    args.out.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
