"""46232's north-west bearing: what it is, and what it costs the breaks.

    python -m forecast.nwbearing             # the full report (~10 min)
    python -m forecast.nwbearing --quick     # skip the per-train sections

Reports, never edits (BRIEFING §38). §37 measured 46232 reading a north-west
swell 52-74° south of 46047's bearing for the same ridge, and `forecast.origin`
said why: "because the islands bend it". Nothing had tested that, and it
matters twice: Origin needs the open-ocean bearing, and the break chain takes
46232's directional spectrum as the sea arriving at Coronado. Six questions,
each with the test that could kill its answer:

1. **Is the gap the buoy, or the average?** On north-west hours (46047's
   11-20 s swell dominated by a 280-340° lobe), 46232's energy-weighted mean
   heading against 46047's lobe, and 46232's own westerly LOBE against it. A
   mean taken across two lobes lands between them, where little energy is.
2. **Is it the hull?** The same at 46258 (a Waverider, like 46232) and 46086
   (an NDBC hull, like 46047). A hull artifact would pin at the Waveriders and
   not at 46086; a compass error would track 46047 with a slope near one.
3. **Is it the islands' edges?** The Channel Islands from NOAA's ENC
   (`collector.shoreline`, the two `channel_islands_*` regions), clustered into
   islands, and every island's edges as seen from each buoy. An edge effect
   puts each buoy's lobe at the same place relative to the edges it sees.
4. **Does it reach the beach?** On those hours, the share of each break's 5 m
   energy that left deep water at 255-345°, and the break's height with that
   lobe rotated by -9, +9 and +18° (the spread between 46232 and 46258), or
   removed. Plus where the breaks' westerly rays leave deep water.
5. **Does it reach the page?** Every swell train the page shows, on the
   buoy's tab and each break's: its heading against the lobes of its own
   energy. `transform.split_trains` reports a train at its energy-weighted
   mean heading and says so; this counts how often that lands more than 20°
   from every lobe holding a fifth of the train.
6. **Would a finer coast change a hurricane's path verdict?** The land
   `forecast.landpath` tests is Natural Earth on a 0.05° raster; every
   >= 64 kt fix's path to each gate buoy, with the coast moved 5 and 10 km.

Lobes are maxima of the maximum-entropy distribution summed over a 21° window,
each the largest within 30° either side; a lobe's share is the energy within
25° of it. Directions are FROM, degrees true. Gaps are dropped, never filled.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR

from .swell import destination_point, great_circle_km, initial_bearing
from .transform import lobes  # the one lobe finder: Origin and the train labels use it too

#: The swell band the bearing comparisons use: 20 s to 11 s.
BAND_HZ = (1.0 / 20.0, 1.0 / 11.0)
#: A north-west hour: 46047's band at least this high, its largest lobe in
#: this sector holding at least this share.
NW_MIN_HS_M = 0.5
NW_SECTOR = (280.0, 340.0)
NW_MIN_SHARE = 0.4
#: A shadowed buoy's westerly lobe: the largest in this sector holding at
#: least this share of its band.
WEST_SECTOR = (225.0, 345.0)
WEST_MIN_SHARE = 0.15
#: A train's heading is "off" when it sits further than this from every lobe
#: holding at least `BIG_LOBE` of the train.
OFF_DEG = 20.0
BIG_LOBE = 0.2
#: Section 4: the lobe moved, and the sector it is taken from.
ROTATIONS = (-9, 9, 18)
LOBE_SECTOR = (250, 346)
SWELL_PERIOD_S = (10.0, 25.0)
#: Islands: chart vertices within this of each other are one island, and an
#: island smaller than `MIN_SPAN_KM` is a rock the swell wraps.
CLUSTER_KM = 1.0
MIN_SPAN_KM = 0.5
ISLAND_BAND = "enc_approach_88"
ISLAND_REGIONS = ("channel_islands_south", "channel_islands_north")
#: Names by nearest centroid, within 15 km; a label only, read by no number.
ISLAND_NAMES = {
    "San Clemente": (32.90, -118.50), "Santa Catalina": (33.38, -118.42),
    "Santa Barbara I.": (33.48, -119.04), "San Nicolas": (33.25, -119.50),
    "Santa Cruz": (34.00, -119.75), "Santa Rosa": (33.95, -120.10),
    "San Miguel": (34.04, -120.37), "Anacapa": (34.01, -119.40),
}
STATIONS = ("46232", "46258", "46086")
REFERENCE = "46047"
MATCH_MIN = 45.0


# ------------------------------------------------------------ distributions

def angular(a: float, b: float) -> float:
    """Signed a − b in (−180, 180]."""

    return (a - b + 180.0) % 360.0 - 180.0


def band_distribution(spectrum, band: tuple[float, float] = BAND_HZ):
    """Energy over 1° headings in a frequency band, as a share, and the band's
    m0 (m²). The shipped D(θ): whatever `spectrum.spread` says, MEM on every
    surface. None when the band is empty."""

    from .nearshore import density_grids

    grids = density_grids(spectrum)
    dist = [0.0] * 360
    m0 = 0.0
    for i, grid in grids.items():
        if not (band[0] <= spectrum.frequencies[i] <= band[1]):
            continue
        w = spectrum.bin_width(i) * math.radians(1.0)
        for k in range(360):
            dist[k] += grid[k] * w
    m0 = sum(dist)
    if m0 <= 0:
        return None, 0.0
    return [v / m0 for v in dist], m0


def mean_heading(dist: list[float]) -> float:
    x = sum(v * math.cos(math.radians(k + 0.5)) for k, v in enumerate(dist))
    y = sum(v * math.sin(math.radians(k + 0.5)) for k, v in enumerate(dist))
    return math.degrees(math.atan2(y, x)) % 360.0


def westerly_lobe(dist: list[float]) -> float | None:
    found = [lobe for lobe in lobes(dist)
             if WEST_SECTOR[0] <= lobe[0] <= WEST_SECTOR[1] and lobe[1] >= WEST_MIN_SHARE]
    return max(found, key=lambda lobe: lobe[1])[0] if found else None


def off_lobe(dist: list[float], shown: float) -> float | None:
    """How far a shown heading sits from the nearest lobe holding `BIG_LOBE`,
    or None when no lobe does."""

    big = [h for h, share in lobes(dist) if share >= BIG_LOBE]
    return min(abs(angular(shown, h)) for h in big) if big else None


def slope(xs: list[float], ys: list[float]) -> float:
    mx, my = statistics.mean(xs), statistics.mean(ys)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)


# ------------------------------------------------------------------ islands

def _parts(path: Path) -> list[list[tuple[float, float]]]:
    parts: dict[str, list] = defaultdict(list)
    with path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            parts[row["part"]].append((float(row["lat"]), float(row["lon"])))
    return list(parts.values())


def cluster(parts: list[list[tuple[float, float]]], km: float = CLUSTER_KM) -> list[list[tuple[float, float]]]:
    """Chart parts whose vertices come within about `km` of each other, joined.
    A grid of `km` cells; neighbouring cells join."""

    parent = list(range(len(parts)))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    size = km / 111.0
    cells: dict[tuple[int, int], set[int]] = defaultdict(set)
    for i, part in enumerate(parts):
        for lat, lon in part:
            cells[(int(math.floor(lat / size)), int(math.floor(lon / size)))].add(i)
    for (a, b), ids in cells.items():
        near = set(ids)
        for da in (-1, 0, 1):
            for db in (-1, 0, 1):
                near |= cells.get((a + da, b + db), set())
        near = sorted(near)
        for j in near[1:]:
            parent[root(j)] = root(near[0])
    groups: dict[int, list] = defaultdict(list)
    for i, part in enumerate(parts):
        groups[root(i)] += part
    return list(groups.values())


def _span_km(points) -> float:
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    mid = math.cos(math.radians(statistics.mean(lats)))
    return math.hypot(max(lats) - min(lats), (max(lons) - min(lons)) * mid) * 111.0


def _name(points) -> str:
    lat = statistics.mean(p[0] for p in points)
    lon = statistics.mean(p[1] for p in points)
    best = min(ISLAND_NAMES, key=lambda n: great_circle_km((lat, lon), ISLAND_NAMES[n]))
    return best if great_circle_km((lat, lon), ISLAND_NAMES[best]) < 15 else f"({lat:.2f}, {lon:.2f})"


def load_islands(data_dir: Path = DEFAULT_DATA_DIR) -> dict[str, list[tuple[float, float]]]:
    """Every charted island in the two regions, by name. Empty when the
    extracts were never fetched."""

    out: dict[str, list] = {}
    for region in ISLAND_REGIONS:
        path = Path(data_dir) / "shoreline" / f"{ISLAND_BAND}_{region}.csv"
        if not path.exists():
            continue
        for points in cluster(_parts(path)):
            if _span_km(points) < MIN_SPAN_KM:
                continue
            name = _name(points)
            while name in out:
                name += "'"
            out[name] = points
    return out


def edges(observer: tuple[float, float], points) -> tuple[float, float]:
    """The island's two edges as seen from `observer`, clockwise order."""

    bearings = [initial_bearing(observer, p) for p in points]
    ref = bearings[0]
    rel = [angular(b, ref) for b in bearings]
    return (ref + min(rel)) % 360.0, (ref + max(rel)) % 360.0


def nearest_edge(observer, islands, heading: float) -> tuple[float, str, bool]:
    """Signed distance from `heading` to the nearest island edge, which island,
    and whether the heading sits inside that island's arc."""

    best = None
    for name, points in islands.items():
        a, b = edges(observer, points)
        inside = angular(heading, a) >= 0 and angular(b, heading) >= 0
        for edge in (a, b):
            d = angular(heading, edge)
            if best is None or abs(d) < abs(best[0]):
                best = (d, name, inside)
    return best


# -------------------------------------------------------------------- data

def positions(data_dir: Path) -> dict[str, tuple[float, float]]:
    """From NDBC's own metadata; never typed."""

    with (Path(data_dir) / "station_metadata.csv").open(newline="") as fh:
        return {r["id"]: (float(r["latitude"]), float(r["longitude"])) for r in csv.DictReader(fh)}


def load(data_dir: Path) -> dict[str, list]:
    from .transform import load_spectra

    out = {}
    for station in (REFERENCE,) + STATIONS:
        try:
            out[station] = [s.with_spread("mem") for s in load_spectra(Path(data_dir) / "spectra" / station)]
        except (FileNotFoundError, ValueError):
            out[station] = []
    return out


def _nearest(index, moment):
    by_time, times = index
    k = bisect.bisect_left(times, moment)
    best = None
    for j in (k - 1, k):
        if 0 <= j < len(times):
            gap = abs((times[j] - moment).total_seconds()) / 60.0
            if gap <= MATCH_MIN and (best is None or gap < best[0]):
                best = (gap, times[j])
    return by_time[best[1]] if best else None


def nw_hours(spectra: dict[str, list]) -> list[dict]:
    """Every hour 46047's band is a north-west swell, with each station's
    westerly lobe and mean heading at the nearest spectrum."""

    index = {st: ({s.time: s for s in spectra[st]}, sorted(s.time for s in spectra[st]))
             for st in STATIONS}
    rows = []
    for ref in spectra[REFERENCE]:
        dist, m0 = band_distribution(ref)
        if dist is None or 4.0 * math.sqrt(m0) < NW_MIN_HS_M:
            continue
        top = lobes(dist)
        if not top or not (NW_SECTOR[0] <= top[0][0] <= NW_SECTOR[1]) or top[0][1] < NW_MIN_SHARE:
            continue
        row = {"time": ref.time, REFERENCE: top[0][0], "spectra": {}}
        for station in STATIONS:
            spectrum = _nearest(index[station], ref.time)
            if spectrum is None:
                continue
            d, _ = band_distribution(spectrum)
            if d is None:
                continue
            row["spectra"][station] = spectrum
            row[station + "_mean"] = mean_heading(d)
            lobe = westerly_lobe(d)
            if lobe is not None:
                row[station] = lobe
        rows.append(row)
    return rows


def _q(values: list[float]) -> str:
    qs = statistics.quantiles(values, n=10)
    return f"median {statistics.median(values):+.1f}% (10th {qs[0]:+.1f}, 90th {qs[-1]:+.1f})"


# ---------------------------------------------------------------- sections

def decomposition(rows: list[dict]) -> list[str]:
    out = ["1-2. The westerly lobe at each shadowed buoy, against 46047's north-west lobe"]
    days = sorted({r["time"].strftime("%m-%d") for r in rows})
    out.append(f"   {len(rows)} north-west hours at 46047 on {len(days)} days ({', '.join(days)})")
    for station in STATIONS:
        got = [r for r in rows if station in r]
        if len(got) < 4:
            out.append(f"   {station}: {len(got)} hours, too few")
            continue
        xs = [r[REFERENCE] for r in got]
        ys = [r[station] for r in got]
        qs = statistics.quantiles(ys, n=4)
        lobe_gap = statistics.median(angular(y, x) for x, y in zip(xs, ys))
        mean_gap = statistics.median(angular(r[station + "_mean"], r[REFERENCE]) for r in got)
        out.append(
            f"   {station}: {len(got)} h on {len({r['time'].date() for r in got})} days | westerly lobe "
            f"median {statistics.median(ys):.0f}° (IQR {qs[0]:.0f}-{qs[2]:.0f}) | slope on 46047's "
            f"{slope(xs, ys):+.2f} | lobe − 46047 {lobe_gap:+.0f}° | mean heading − 46047 {mean_gap:+.0f}°")
    return out


def island_edges(rows: list[dict], islands: dict, where: dict) -> list[str]:
    out = ["3. The charted Channel Islands' edges, as seen from each buoy"]
    if not islands:
        return out + ["   no channel_islands_* extract in data/shoreline: run shoreline.yml"]
    out.append(f"   {len(islands)} islands from {ISLAND_BAND} ({', '.join(sorted(islands))})")
    for station in (REFERENCE,) + STATIONS:
        arcs = sorted((edges(where[station], pts), name) for name, pts in islands.items())
        text = "; ".join(f"{name} {a:.1f}-{b:.1f}" for (a, b), name in arcs)
        out.append(f"   {station}: {text}")
        got = [r[station] for r in rows if station in r]
        if got:
            lobe = statistics.median(got)
            d, name, inside = nearest_edge(where[station], islands, lobe)
            out.append(f"      lobe {lobe:.0f}°: {abs(d):.1f}° {'clockwise' if d > 0 else 'anticlockwise'} "
                       f"of {name}'s nearest edge{', INSIDE its arc' if inside else ''}")
    return out


def at_the_breaks(rows: list[dict], data_dir: Path, where: dict) -> list[str]:
    from .nearshore import carry, density_grids, load_tables

    tables = load_tables()
    out = ["4. What 46232's westerly lobe carries into each break, on the same hours (energy at 5 m)"]
    lo, hi = 1.0 / SWELL_PERIOD_S[1], 1.0 / SWELL_PERIOD_S[0]
    acc = {b: defaultdict(list) for b in tables}
    for row in rows:
        spectrum = row["spectra"].get("46232")
        if spectrum is None:
            continue
        grids = density_grids(spectrum)
        variants = {"absent": {}, **{r: {} for r in ROTATIONS}}
        for i, grid in grids.items():
            swell = lo <= spectrum.frequencies[i] <= hi
            variants["absent"][i] = ([0.0 if 255 <= k + 0.5 <= 345 else v for k, v in enumerate(grid)]
                                     if swell else grid)
            for rot in ROTATIONS:
                if not swell:
                    variants[rot][i] = grid
                    continue
                moved = list(grid)
                for k in range(*LOBE_SECTOR):
                    moved[k] = 0.0
                for k in range(*LOBE_SECTOR):
                    moved[(k + rot) % 360] += grid[k]
                variants[rot][i] = moved
        for name, table in tables.items():
            base = carry(spectrum, table, grids).hs_ref
            if base <= 0.05:
                continue
            for key, g in variants.items():
                acc[name][key].append(100.0 * (carry(spectrum, table, g).hs_ref / base - 1.0))
            share = 1.0 - (carry(spectrum, table, variants["absent"]).hs_ref / base) ** 2
            acc[name]["share"].append(100.0 * share)
    for name, got in acc.items():
        if not got["share"]:
            continue
        out.append(f"   {name} (n={len(got['share'])})")
        out.append(f"      share from 255-345° offshore, {SWELL_PERIOD_S[0]:.0f}-{SWELL_PERIOD_S[1]:.0f} s: "
                   + _q(got["share"]))
        out.append(f"      Hs with that lobe absent: {_q(got['absent'])}")
        for rot in ROTATIONS:
            out.append(f"      Hs with the lobe turned {rot:+d}°: {_q(got[rot])}")
    # where the westerly rays leave deep water
    for name in tables:
        meta = json.loads((Path(data_dir) / "nearshore" / f"{name}.json").read_text())
        start = (meta["start_lat"], meta["start_lon"])
        with (Path(data_dir) / "nearshore" / f"{name}.csv").open(newline="") as fh:
            rays = [r for r in csv.DictReader(fh)
                    if float(r["diff_gain"]) > 0 and 255 <= float(r["diff_off_from_deg"]) <= 300
                    and 10 <= float(r["period_s"]) <= 20]
        exits = [destination_point(start, float(r["diff_off_from_deg"]), float(r["path_km"])) for r in rays]
        if exits:
            out.append(f"   {name}: {len(rays)} westerly rays (10-20 s) leave deep water a median "
                       f"{statistics.median(great_circle_km(p, where['46232']) for p in exits):.0f} km from 46232 "
                       f"and {statistics.median(great_circle_km(p, where['46258']) for p in exits):.0f} km from 46258")
    return out


def on_the_page(spectra46232: list) -> list[str]:
    from .nearshore import at as interp, density_grids, load_tables
    from .transform import at_buoy, split_trains, train_bands

    tables = load_tables()
    counts = {k: [0, 0, 0, set()] for k in ["buoy", *tables]}   # trains, off, split, hours
    peak = [0, 0]

    def tally(key, bands, hists, trains, when, freqs):
        # A train is matched to the period band its peak bin sits in: since
        # BRIEFING §40 one band can be two trains, each from one of its lobes.
        mine = [({i for i, _ in band}, [sum(hists[i][k] for i, _ in band) for k in range(360)])
                for band in bands]
        for train in trains:
            if train.is_wind_sea or math.isnan(train.from_deg) or not mine:
                continue
            peak = min(range(len(freqs)), key=lambda i: abs(1.0 / freqs[i] - train.period_s))
            hist = next((h for bins, h in mine if peak in bins), None)
            if hist is None:
                continue
            off = off_lobe(hist, train.from_deg)
            if off is None:
                continue
            row = counts[key]
            row[0] += 1
            if off > OFF_DEG:
                row[1] += 1
                row[3].add(when)
            if sum(1 for _, share in lobes(hist) if share >= BIG_LOBE) >= 2:
                row[2] += 1

    for spectrum in spectra46232:
        grids = density_grids(spectrum)
        hists, per_bin = {}, []
        for i, grid in sorted(grids.items()):
            w = spectrum.bin_width(i) * math.radians(1.0)
            hists[i] = [v * w for v in grid]
            per_bin.append((i, sum(hists[i])))
        view = at_buoy(spectrum)
        tally("buoy", train_bands(per_bin), hists, view.trains, spectrum.time,
              spectrum.frequencies)
        if per_bin:
            best = max(per_bin, key=lambda item: item[1])[0]
            off = off_lobe(hists[best], view.peak_direction_deg)
            if off is not None:
                peak[0] += 1
                peak[1] += off > OFF_DEG
        for name, table in tables.items():
            freqs = sorted(table.by_freq)
            bh, pb, sins, coss = {}, [], {}, {}
            for i, f in enumerate(spectrum.frequencies):
                grid = grids.get(i)
                if grid is None:
                    continue
                near = min(freqs, key=lambda t: abs(t - f))
                if abs(near - f) > 0.05 * f:
                    continue
                h = [0.0] * 360
                w = spectrum.bin_width(i)
                for ray in table.by_freq[near]:
                    if ray.diff_gain > 0:
                        h[int(ray.diff_off_from) % 360] += (interp(grid, ray.diff_off_from) * w * ray.width_rad
                                                            * ray.diff_gain * ray.diff_friction)
                bh[i] = h
                pb.append((i, sum(h)))
                sins[i] = sum(v * math.sin(math.radians(k + 0.5)) for k, v in enumerate(h))
                coss[i] = sum(v * math.cos(math.radians(k + 0.5)) for k, v in enumerate(h))
            tally(name, train_bands(pb), bh,
                  split_trains(pb, spectrum.frequencies, sins, coss, hists=bh), spectrum.time,
                  spectrum.frequencies)

    out = [f"5. Shown train headings against their own energy's lobes ({len(spectra46232)} spectra at 46232)"]
    for key, (n, off, split, hours) in counts.items():
        if n:
            out.append(f"   {key:16} {n:5} swell trains | heading > {OFF_DEG:.0f}° from every lobe holding "
                       f"{BIG_LOBE:.0%}: {off} ({100 * off / n:.1f}%) on {len(hours)} hours | two lobes "
                       f"or more: {split} ({100 * split / n:.1f}%)")
    if peak[0]:
        out.append(f"   peak strip (a1 of 46232's peak bin): > {OFF_DEG:.0f}° from every lobe on "
                   f"{peak[1]} of {peak[0]} hours ({100 * peak[1] / peak[0]:.1f}%)")
    return out


def coast_margin(data_dir: Path, where: dict) -> list[str]:
    from .landpath import STEP_KM, load_land
    from .origintracks import MIN_KT, load_tracks

    land = load_land(str(data_dir))
    out = ["6. Hurricane paths and the coast's resolution (forecast.landpath, Natural Earth 1:10m on 0.05°)"]
    if not land:
        return out + ["   no land file"]

    def crosses(source, buoy, km: float) -> bool:
        total = great_circle_km(source, buoy)
        bearing = initial_bearing(source, buoy)
        s = STEP_KM
        while s < total - STEP_KM / 2:
            p = destination_point(source, bearing, s)
            ring = [destination_point(p, b, abs(km)) for b in range(0, 360, 45)] if km else []
            if km >= 0 and (p in land or any(q in land for q in ring)):
                return True
            if km < 0 and p in land and all(q in land for q in ring):
                return True
            s += STEP_KM
        return False

    n = 0
    flips = {5: 0, -5: 0, 10: 0, -10: 0}
    named: set[str] = set()
    for fixes in load_tracks(Path(data_dir)).values():
        for fix in fixes:
            if fix.vmax_kt < MIN_KT:
                continue
            for station in (REFERENCE, "46086", "46232"):
                n += 1
                base = crosses((fix.lat, fix.lon), where[station], 0)
                for km in flips:
                    if crosses((fix.lat, fix.lon), where[station], km) != base:
                        flips[km] += 1
                        named.add(f"{fix.name.title()} {fix.time:%m-%d %H}Z->{station}")
    out.append(f"   {n} fix-to-buoy paths (>= {MIN_KT} kt). Verdicts that change with the coast moved:")
    for km, count in flips.items():
        out.append(f"      {'seaward' if km > 0 else 'landward'} {abs(km)} km: {count} ({100 * count / n:.1f}%)")
    if named:
        out.append(f"   which: {', '.join(sorted(named))}")
    return out


def report(data_dir: Path = DEFAULT_DATA_DIR, *, quick: bool = False) -> str:
    data_dir = Path(data_dir)
    where = positions(data_dir)
    spectra = load(data_dir)
    rows = nw_hours(spectra)
    islands = load_islands(data_dir)
    out = decomposition(rows) + [""]
    out += island_edges(rows, islands, where) + [""]
    if not quick:
        out += at_the_breaks(rows, data_dir, where) + [""]
        out += on_the_page(spectra["46232"]) + [""]
    out += coast_margin(data_dir, where)
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--quick", action="store_true", help="skip sections 4 and 5")
    args = parser.parse_args(argv)
    print(report(args.data_dir, quick=args.quick))
    return 0


if __name__ == "__main__":
    sys.exit(main())
