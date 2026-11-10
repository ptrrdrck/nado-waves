"""The swell-fill map's rays: each one's real path, and a picked train's energy on it.

    python -m mocks.swell_fill.rays NOW.json            # check, and print what it built
    python -m mocks.swell_fill.rays NOW.json --json     # the map's payload

PRECOMPUTE (numpy, the CoNED / GMRT grids). For the moment `now.json` was built
from, and each period bin its trains hold, this re-traces every ray of each
break's transfer table -- the same start point, the same 0.5° of 5 m headings,
the same step -- with `trace_paths`, a copy of `forecast.raytrace.trace` that
also records where each ray went and when. The copy is checked against the
original: every ray's status and offshore heading must agree, and each
clearing ray's must agree with the table's own row, or the build stops.

Each ray then carries the train's energy exactly as `nearshore.carry` credits
it (fill.py's membership: the row's bins, its arc, its buoy swell). A ray the
land stops carries nothing hard; what diffraction gives it is drawn along the
clearing ray of the same period whose offshore heading is nearest the one
the table credits it to -- raytrace's own reading of where diffracted energy
comes round an edge from. Every ray's 5 m energy summed is checked against the
chain's 5 m height for the row.

Times are minutes after the same wave group passed 46232, as
`raytrace.leg_table` computes them: the plane-wave offset from the buoy to the
ray's deep-water exit, then ∫ ds / cg along the bent path. Seaward of the exit
the path is straight, and it is drawn from the line through 46232 square to
its heading, where the clock reads 0: the chain takes the buoy's spectrum to
hold all along that line. From 5 m it runs on to the break along the break's
normal, the line the surf zone is computed on.

Also a seabed picture for the map, from the same grids (depth below MSL as
the tracer reads it), since the bending happens over it. A MOCK.
"""
from __future__ import annotations

import argparse
import base64
import csv
import io
import json
import math
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

from forecast.geometry import load as load_geometry
from forecast.nearshore import (TABLE_DIR, _arc_degrees, _buoy_owner, at, buoy_split, carry,
                                density_grids, load_tables, shoaling_squared)
from forecast.raytrace import (DEEP, DIR_STEP_DEG, EDGE, G, H_LAND, LAND, LONG, MAX_PATH_M,
                               STEP_FRACTION, Bathymetry, beta_from_compass, compass_from,
                               friction_rate, speeds, start_point, trace)
from forecast.siting import load_coordinates
from forecast.transform import load_spectra
from forecast.utm import from_utm, to_utm

ROOT = Path(__file__).resolve().parents[2]
SPECTRA = ROOT / "data" / "spectra" / "46232"
BUOY = "46232"
#: The surf zone's middle depth, for how long 5 m to the break takes (m).
SURF_MID_DEPTH_M = 2.5
#: Path simplification tolerance, metres (Douglas-Peucker in UTM).
SIMPLIFY_M = 12.0
#: Rays carrying less than this share of a row's 5 m energy are left out.
MIN_SHARE = 2e-4


# ------------------------------------------------------------------ the tracer, with paths

def trace_paths(bathy: Bathymetry, x0: float, y0: float, near_from_deg: np.ndarray, period_s: float):
    """`raytrace.trace`'s loop without islands or edges, recording each ray's
    position and elapsed group time at every step. Returns (status,
    off_from_deg, paths) with paths[i] an array of (x, y, elapsed_s) from the
    start point outward."""

    omega = 2.0 * math.pi / period_s
    l0 = G * period_s ** 2 / (2.0 * math.pi)
    h_deep = l0
    n = near_from_deg.size
    x = np.full(n, float(x0))
    y = np.full(n, float(y0))
    beta = beta_from_compass(near_from_deg)
    path = np.zeros(n)
    status = np.full(n, "", dtype=object)
    exit_depth = np.full(n, np.nan)
    active = np.ones(n, bool)
    elapsed = np.zeros(n)
    rec: list[list[tuple[float, float, float]]] = [[(x0, y0, 0.0)] for _ in range(n)]

    def rhs(xa, ya, ba):
        h, hx, hy, cell, covered = bathy.sample(xa, ya)
        c, _, dc_dh = speeds(omega, np.where(np.isfinite(h), h, 1.0))
        cx, cy = dc_dh * hx, dc_dh * hy
        dbeta = (cx * np.sin(ba) - cy * np.cos(ba)) / c
        return dbeta, h, cell, covered

    while active.any():
        idx = np.flatnonzero(active)
        xa, ya, ba = x[idx], y[idx], beta[idx]
        k1, h, cell, covered = rhs(xa, ya, ba)
        land = covered & (h <= H_LAND)
        deep = covered & (h >= h_deep)
        last = np.where(np.isfinite(exit_depth[idx]), exit_depth[idx], 0.0)
        edge = ~covered
        edge_deep = edge & (last >= 0.5 * l0)
        edge = edge & ~edge_deep
        deep = deep | edge_deep
        long_ = path[idx] >= MAX_PATH_M
        for mask, label in ((land, LAND), (deep, DEEP), (edge, EDGE), (long_, LONG)):
            hit = mask & (status[idx] == "")
            status[idx[hit]] = label
            exit_depth[idx[hit]] = np.where(covered[hit], h[hit], exit_depth[idx[hit]])
        done = status[idx] != ""
        active[idx[done]] = False
        seen = covered & ~done
        exit_depth[idx[seen]] = h[seen]
        go = ~done
        if not go.any():
            break
        idx, xa, ya, ba = idx[go], xa[go], ya[go], ba[go]
        k1, ds = k1[go], STEP_FRACTION * cell[go]
        wet = covered[go] & np.isfinite(h[go])
        if wet.any():
            _, cg_here, _ = speeds(omega, h[go][wet])
            elapsed[idx[wet]] += ds[wet] / cg_here
        xm = xa + 0.5 * ds * np.cos(ba)
        ym = ya + 0.5 * ds * np.sin(ba)
        bm = ba + 0.5 * ds * k1
        k2, _, _, cov2 = rhs(xm, ym, bm)
        k2 = np.where(cov2, k2, k1)
        x[idx] = xa + ds * np.cos(bm)
        y[idx] = ya + ds * np.sin(bm)
        beta[idx] = ba + ds * k2
        path[idx] += ds
        for j in idx:
            rec[j].append((x[j], y[j], elapsed[j]))
    return status, compass_from(beta), [np.array(r) for r in rec]


def simplify(pts: np.ndarray, tol: float) -> np.ndarray:
    """Douglas-Peucker on (x, y, ...) rows, keeping both ends."""

    if len(pts) < 3:
        return pts
    keep = np.zeros(len(pts), bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        if b <= a + 1:
            continue
        p, q = pts[a, :2], pts[b, :2]
        d = q - p
        seg = np.hypot(*d) or 1.0
        mid = pts[a + 1:b, :2]
        dist = np.abs(d[0] * (mid[:, 1] - p[1]) - d[1] * (mid[:, 0] - p[0])) / seg
        k = int(np.argmax(dist))
        if dist[k] > tol:
            m = a + 1 + k
            keep[m] = True
            stack += [(a, m), (m, b)]
    return pts[keep]


# ------------------------------------------------------------------ the table, as written

def table_rows(break_id: str) -> dict[float, list[dict]]:
    out: dict[float, list[dict]] = {}
    with (TABLE_DIR / f"{break_id}.csv").open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out.setdefault(float(r["freq_hz"]), []).append(r)
    return out


def ang(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


# ------------------------------------------------------------------ the seabed picture

def seabed_png(bathy: Bathymetry, south: float, west: float, north: float, east: float,
               px: int = 1100, feather: float = 0.06) -> tuple[str, list]:
    """Depth below MSL as greys on a Web-Mercator-aligned grid, land lighter,
    with contours at 5, 10, 20, 50, 100, 200, 500, 1,000 and 2,000 m. A data: URI. Its
    edges fade out over `feather` of its size, and where the grids have no
    cell it is clear, so the picture under it shows through."""

    from PIL import Image

    def merc(lat):
        return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    y0, y1 = merc(south), merc(north)
    aspect = (y1 - y0) / math.radians(east - west)
    w = px
    hgt = max(1, int(round(px * aspect)))
    lons = west + (np.arange(w) + 0.5) / w * (east - west)
    ys = y1 - (np.arange(hgt) + 0.5) / hgt * (y1 - y0)
    lats = np.degrees(2 * np.arctan(np.exp(ys)) - math.pi / 2)
    LON, LAT = np.meshgrid(lons, lats)
    flat = [to_utm(la, lo) for la, lo in zip(LAT.ravel(), LON.ravel())]
    xs = np.array([p[0] for p in flat]).reshape(LON.shape)
    yy = np.array([p[1] for p in flat]).reshape(LON.shape)
    h, *_rest, covered = bathy.sample(xs.ravel(), yy.ravel())
    h = h.reshape(LON.shape)
    covered = covered.reshape(LON.shape)
    water = covered & np.isfinite(h) & (h > H_LAND)
    land = covered & np.isfinite(h) & ~water
    d = np.clip(np.where(water, h, 1.0), 1.0, 2000.0)
    t = np.log10(d) / np.log10(2000.0)          # 0 at 1 m, 1 at 2,000 m
    grey = 92 - 62 * t                           # shallow lighter, deep darker
    img = np.where(water, grey, np.where(land, 150.0, 18.0))
    rgb = np.stack([img * 0.92, img * 0.98, img * 1.06], -1)   # the map's navy-grey, faintly
    edge = np.zeros(h.shape, bool)
    for level in (5, 10, 20, 50, 100, 200, 500, 1000, 2000):
        above = np.where(water, h, 0.0) >= level
        e = np.zeros_like(above)
        e[:-1] |= above[:-1] != above[1:]
        e[:, :-1] |= above[:, :-1] != above[:, 1:]
        edge |= e & water
    rgb[edge] = rgb[edge] * 0.55 + 255 * 0.45 * 0.6
    rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    ramp = ((lambda n: np.clip(np.minimum(np.arange(n) + 0.5, n - np.arange(n) - 0.5) / (feather * n), 0, 1))
            if feather > 0 else (lambda n: np.ones(n)))
    alpha = np.outer(ramp(hgt), ramp(w)) * (water | land)
    rgba = np.dstack([rgb, (alpha * 255).astype(np.uint8)])
    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").quantize(colors=96, method=Image.Quantize.FASTOCTREE).save(
        buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(), [[south, west], [north, east]]


# ------------------------------------------------------------------ the build

def build(now_path: Path, seabed: bool = True) -> dict:
    now = json.loads(now_path.read_text(encoding="utf-8"))
    when = datetime.fromisoformat(now["observed_utc"].replace("Z", "+00:00"))
    spectra = [s for s in load_spectra(SPECTRA) if s.time == when]
    if not spectra:
        sys.exit(f"no 46232 spectrum at {now['observed_utc']}")
    spectrum = spectra[0].with_spread("mem")
    grids = density_grids(spectrum)
    split = buoy_split(spectrum, grids)
    owner = _buoy_owner(split)
    tables = load_tables()
    bathy = Bathymetry.load()
    spots = {s.id: s for s in load_geometry()[0]}
    buoy = load_coordinates()[BUOY]
    bx, by = to_utm(*buoy)
    out = {"observed_utc": now["observed_utc"], "buoy": list(buoy), "breaks": {}}
    lat_lo, lat_hi, lon_lo, lon_hi = buoy[0], buoy[0], buoy[1], buoy[1]

    for b in now["breaks"]:
        bid = b["id"]
        spot = spots[bid]
        table = tables[bid]
        rows_by_f = table_rows(bid)
        carried = carry(spectrum, table, grids, split)
        shown = (b.get("nearshore") or {}).get("trains") or []
        trains = list(zip(shown, carried.trains[:3]))
        xs, ys, _ = start_point(bathy, spot)
        bx_break, by_break = to_utm(*spot.position)
        near = (spot.normal - 90.0 + DIR_STEP_DEG / 2.0
                + DIR_STEP_DEG * np.arange(int(round(180.0 / DIR_STEP_DEG)))) % 360.0
        bins = sorted({i for _, t in trains for i in t.bins if i in grids})
        rays_out = []            # one per clearing ray drawn: points and times
        ray_key = {}             # (bin, table row index) -> index in rays_out
        traced = {}              # bin -> (status, off, paths, rows)
        for i in bins:
            f = spectrum.frequencies[i]
            near_f = min(table.by_freq, key=lambda q: abs(q - f))
            rows = rows_by_f[min(rows_by_f, key=lambda q: abs(q - near_f))]
            if len(rows) != near.size:
                sys.exit(f"{bid} {near_f} Hz: {len(rows)} table rows, {near.size} headings")
            period = 1.0 / near_f
            status, off, paths = trace_paths(bathy, xs, ys, near, period)
            ref = trace(bathy, xs, ys, near, period)
            if not (np.array_equal(status, ref.status) and np.allclose(off, ref.off_from_deg, atol=1e-9)):
                sys.exit(f"{bid} {near_f} Hz: trace_paths disagrees with raytrace.trace")
            for k, r in enumerate(rows):
                if abs(float(r["near_from_deg"]) - near[k]) > 0.02:
                    sys.exit(f"{bid} {near_f} Hz row {k}: table {r['near_from_deg']}°, here {near[k]:.2f}°")
                if float(r["gain"]) > 0 and ang(float(r["off_from_deg"]), off[k]) > 0.02:
                    sys.exit(f"{bid} {near_f} Hz row {k}: table off {r['off_from_deg']}°, traced {off[k]:.2f}°")
            traced[i] = (status, off, paths, rows, near_f)

        def ray_index(i: int, k: int) -> int:
            """The drawn ray for table row k of bin i, made on first use."""
            if (i, k) in ray_key:
                return ray_key[(i, k)]
            status, off, paths, rows, near_f = traced[i]
            p = paths[k]
            period = 1.0 / near_f
            cg0 = G * period / (4.0 * math.pi)
            total = p[-1, 2]
            ex, ey = p[-1, 0], p[-1, 1]
            toward = math.radians(off[k] + 180.0)
            offset_s = ((ex - bx) * math.sin(toward) + (ey - by) * math.cos(toward)) / cg0
            t_exit = (offset_s) / 60.0
            # Seaward of the exit the ray is straight. It starts on the line
            # through 46232 square to its heading, where the clock is 0: the
            # chain takes the buoy's spectrum to hold all along that line. An
            # exit already up-swell of that line starts at the exit itself.
            back = max(0.0, offset_s * cg0)
            pts = [(ex - back * math.sin(toward), ey - back * math.cos(toward),
                    t_exit - back / cg0 / 60.0)] if back > 0 else []
            inward = simplify(p[::-1].copy(), SIMPLIFY_M)
            for x, y, e in inward:
                pts.append((x, y, t_exit + (total - e) / 60.0))
            # 5 m in to the break: the surf zone's own line, the break's
            # normal (`surfzone` carries the sea along it, not along a ray), at
            # the shallow-water speed of its middle depth.
            sx, sy = bx_break, by_break
            run = math.hypot(sx - xs, sy - ys)
            pts.append((sx, sy, pts[-1][2] + run / math.sqrt(G * SURF_MID_DEPTH_M) / 60.0))
            ll = []
            for x, y, t in pts:
                la, lo = from_utm(x, y)
                ll.append([round(la, 5), round(lo, 5), round(t, 2)])
            ray_key[(i, k)] = len(rays_out)
            rays_out.append({"bin": i, "period_s": round(period, 2), "off_deg": round(float(off[k]), 2),
                             "near_deg": round(float(near[k]), 2), "pts": ll})
            return ray_key[(i, k)]

        rows_out = []
        for n, (row, t) in enumerate(trains):
            if row["period_s"] != round(t.period_s, 1) or row["from_deg"] != round(t.from_deg):
                sys.exit(f"{bid} row {n}: now.json and the rebuilt chain disagree")
            arc = set(_arc_degrees(t.arc))
            mine = set(t.buoys or ()) | ({t.buoy} if t.buoy is not None else set())
            divided = bool(t.buoys)
            weights: dict[int, list[float]] = {}
            five_total = 0.0
            for i in t.bins:
                if i not in traced:
                    continue
                status, off, paths, rows, near_f = traced[i]
                grid = grids[i]
                width = spectrum.bin_width(i)
                ks2 = shoaling_squared(spectrum.frequencies[i], table.start_depth_m)
                clear = [k for k, r in enumerate(rows) if float(r["gain"]) > 0]
                for k, r in enumerate(rows):
                    dg = float(r["diff_gain"])
                    if dg <= 0:
                        continue
                    d_off = float(r["diff_off_from_deg"])
                    kk = int(d_off) % 360
                    if kk not in arc or (divided and owner(i, kk) not in mine):
                        continue
                    e = (at(grid, d_off) * width * math.radians(float(r["near_width_deg"]))
                         * dg * float(r["diff_friction"]))
                    five_total += e
                    if float(r["gain"]) > 0:
                        j = k
                    elif clear:
                        j = min(clear, key=lambda c: ang(float(rows[c]["off_from_deg"]), d_off))
                    else:
                        continue
                    w = weights.setdefault(ray_index(i, j), [0.0, 0.0])
                    w[0] += e / ks2           # shoaling divided out: for drawing
                    w[1] += e                 # at 5 m: for the height in so far
            hs5 = 4 * math.sqrt(five_total)
            if abs(hs5 - t.hs_m) > 0.002:
                sys.exit(f"{bid} row {n}: rays sum to {hs5:.3f} m at 5 m, chain {t.hs_m:.3f} m")
            drawn = sum(w[1] for w in weights.values())
            keep = {j: w for j, w in weights.items() if w[1] >= MIN_SHARE * drawn}
            top = max((w[0] for w in keep.values()), default=1.0) or 1.0
            rows_out.append({
                "period_s": row["period_s"], "from_deg": row["from_deg"],
                "row_hs_m": row["hs_m"],
                "drawn_share": round(sum(w[1] for w in keep.values()) / five_total, 4) if five_total else 0,
                # [ray, energy scaled to the row's strongest ray, share of the row's 5 m energy]
                "rays": [[j, round(w[0] / top, 4), round(w[1] / five_total, 6)] for j, w in sorted(keep.items())],
            })
        used = sorted({j for r in rows_out for j, *_ in r["rays"]})
        remap = {j: n for n, j in enumerate(used)}
        for r in rows_out:
            r["rays"] = [[remap[j], *rest] for j, *rest in r["rays"]]
        rays_final = [rays_out[j] for j in used]
        for ray in rays_final:
            for la, lo, _ in ray["pts"]:
                lat_lo, lat_hi = min(lat_lo, la), max(lat_hi, la)
                lon_lo, lon_hi = min(lon_lo, lo), max(lon_hi, lo)
        sla, slo = from_utm(xs, ys)
        out["breaks"][bid] = {"start": [round(sla, 5), round(slo, 5)], "rays": rays_final, "rows": rows_out,
                              "periods": {str(i): round(1.0 / spectrum.frequencies[i], 2) for i in bins}}
    if seabed:
        # Two pictures: the whole of every drawn ray, and a finer one over
        # the breaks and the Point Loma tip, where the rays turn most.
        pad = 0.02
        wide = seabed_png(bathy, lat_lo - pad, lon_lo - pad, lat_hi + pad, lon_hi + pad)
        starts = [b["start"] for b in out["breaks"].values()]
        cla = sum(p[0] for p in starts) / len(starts)
        clo = sum(p[1] for p in starts) / len(starts) - 0.04
        dla, dlo = 9.0 / 111.32, 9.0 / (111.32 * math.cos(math.radians(cla)))
        fine = seabed_png(bathy, cla - dla, clo - dlo, cla + dla, clo + dlo, px=1500)
        out["seabed"] = {"layers": [{"png": png, "bounds": bounds} for png, bounds in (wide, fine)],
                         "source": "USGS CoNED 2016 and GMRT, depth below mean sea level"}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("now", type=Path)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-seabed", action="store_true")
    a = ap.parse_args()
    data = build(a.now, seabed=not a.no_seabed)
    if a.json:
        print(json.dumps(data, separators=(",", ":")))
        return
    print("46232", data["observed_utc"])
    for bid, b in data["breaks"].items():
        npts = sum(len(r["pts"]) for r in b["rays"])
        print(f"{bid:16s} rays {len(b['rays'])}  points {npts}")
        for n, r in enumerate(b["rows"]):
            print(f"   row {n}: {r['period_s']} s from {r['from_deg']}°, {len(r['rays'])} rays drawn, "
                  f"{100 * r['drawn_share']:.1f}% of its 5 m energy")
    if "seabed" in data:
        print("seabed", data["seabed"]["bounds"], f"{len(data['seabed']['png']) / 1e3:.0f} KB")


if __name__ == "__main__":
    main()
