"""Which wave buoys could score the chain AND MOP against an observation.

The question this answers (handoff item 24, 2026-11-20): should the chain's
deep-water-to-10 m leg give way to CDIP MOP's? Two models cannot settle that
between themselves (BRIEFING §56a-§56d end "which model is right is not
decided here" every time, by construction). An observed directional spectrum
at a nearshore buoy can: trace the chain to the buoy from 46232's spectra
(`forecast.mopdepth` already traces from any point), take MOP's point nearest
the buoy, and score both against what the buoy measured. That judges exactly
the leg in dispute. It is not the beach, and it never becomes a verification
series for a break.

This module only finds out whether such a test is possible. Report only; it
reads nothing the forecast uses and nothing reads it. It runs on Actions
(`mop-check.yml` with `points=census`): both NDBC and CDIP are refused at
CONNECT from a Claude session (BRIEFING §8).

What it records, every station inside the chain's seabed grids:

- NDBC: position, owner, name and stated water depth (station table, station
  metadata, station page), and the years of each historical spectral file
  (density `w`, mean direction `d`, principal direction `i`, `r1` `j`, `r2`
  `k`) for that station and for 46232;
- CDIP, for the shallow ones: the archive's deployments and coverage, whether
  it reports now, the MOP point nearest it and that point's nowcast and
  hindcast coverage; and, once, every MOP product CDIP lists for San Diego
  county (is there a MOP forecast at all?).

Nothing is inferred. A position NDBC does not give is "unplaced"; a coverage
a DAS does not state is "not stated"; a request that failed says so.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from collector import mop
from collector.common import write_step_summary
from collector.metadata import LOCATION_RE, STATION_TABLE_URL, parse_location, parse_station_table
from collector.ndbc import USER_AGENT
from forecast.utm import to_utm

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "nearshore_census"
REPORT = ROOT / "docs" / "nearshore_census.md"
BATHY_DIR = ROOT / "data" / "bathymetry"

#: The chain's own seabed, finest first. A buoy outside `outer` has no seabed
#: under the chain's rays that this repository holds, so it cannot be traced to.
GRIDS = ("nearshore", "regional", "outer")
STATION_META_URL = "https://www.ndbc.noaa.gov/metadata/stationmetadata.xml"
STATION_PAGE_URL = "https://www.ndbc.noaa.gov/station_page.php?station={sid}"
HISTORICAL_URL = "https://www.ndbc.noaa.gov/data/historical/{kind}/"
#: NDBC's historical spectral files: directory -> the letter in `<id><letter><year>.txt.gz`.
KINDS = {"swden": "w", "swdir": "d", "swdir2": "i", "swr1": "j", "swr2": "k"}
HIST_FILE = re.compile(r"\b(\w{5})([wdijk])(\d{4})\.txt\.gz\b", re.I)
WATER_DEPTH = re.compile(r"Water depth:\s*([0-9]+(?:\.[0-9]+)?)\s*m\b", re.I)
CDIP_ID = re.compile(r"\((\d{3})\)")
FOLDER = re.compile(r'xlink:href="(\d{3}p\d)/catalog\.xml"', re.I)
REALTIME = re.compile(r"\b(\d{3}p\d)_rt\.nc\b", re.I)
PRODUCT = re.compile(rf"\b({mop.REGION}\d{{4}})_(\w+?)\.nc\b")
#: Stations stated shallower than this (or with no depth stated) get the CDIP
#: and MOP lookups. MOP's points sit at 10 m; a buoy in 200 m of water is
#: another offshore input (46232 is one), not a test of the shelf leg. Chosen
#: wide on purpose: the report shows every depth, and nothing is dropped.
SHALLOW_M = 60.0
#: CDIP's catalogue refused a run 14 minutes after another's 94 requests
#: (BRIEFING §56c); this job spends at most this many there.
CDIP_REQUESTS = 90
#: NDBC is not throttled like CDIP, but station pages are fetched one by one.
NDBC_DELAY = 0.5
PAGE_LIMIT = 60
INPUT = "46232"


# ------------------------------------------------------------------ parsing

def parse_station_metadata(xml: str) -> dict[str, dict]:
    """{id: {name, owner, positions: [(lat, lon, start, stop)]}} from NDBC's
    stationmetadata.xml. Regex, not an XML parser: a malformed entry costs
    that entry, not the file."""

    out: dict[str, dict] = {}
    for m in re.finditer(r"<station\b([^>]*)>(.*?)</station>", xml, re.S | re.I):
        attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        sid = attrs.get("id", "").upper()
        if not sid:
            continue
        positions = []
        for h in re.finditer(r"<history\b([^>]*)/?>", m.group(2), re.I):
            ha = dict(re.findall(r'(\w+)="([^"]*)"', h.group(1)))
            try:
                positions.append((float(ha["lat"]), float(ha.get("lng", ha.get("lon", "nan"))),
                                  ha.get("start", ""), ha.get("stop", "")))
            except (KeyError, ValueError):
                continue
        out[sid] = {"name": attrs.get("name", ""), "owner": attrs.get("owner", ""),
                    "positions": positions}
    return out


def parse_historical(listing: str) -> dict[str, dict[str, list[int]]]:
    """{station: {letter: [years]}} from one historical directory listing."""

    found: dict[str, dict[str, set[int]]] = {}
    for sid, letter, year in HIST_FILE.findall(listing):
        found.setdefault(sid.upper(), {}).setdefault(letter.lower(), set()).add(int(year))
    return {s: {k: sorted(v) for k, v in d.items()} for s, d in found.items()}


def merge_historical(parts: list[dict]) -> dict[str, dict[str, list[int]]]:
    out: dict[str, dict[str, list[int]]] = {}
    for part in parts:
        for sid, kinds in part.items():
            for letter, years in kinds.items():
                out.setdefault(sid, {})[letter] = sorted(set(out.get(sid, {}).get(letter, [])) | set(years))
    return out


def directional_years(kinds: dict[str, list[int]]) -> list[int]:
    """Years with all five files: density and the four directional moments.
    Density alone cannot drive or judge a directional transform."""

    sets = [set(kinds.get(letter, [])) for letter in KINDS.values()]
    return sorted(set.intersection(*sets)) if sets else []


def parse_page(html: str) -> dict:
    """Position and stated water depth from an NDBC station page."""

    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&deg;|°", " ", text)
    out: dict = {}
    m = LOCATION_RE.search(text)
    if m:
        out["position"] = parse_location(m.group(0))
    d = WATER_DEPTH.search(text)
    if d:
        out["water_depth_m"] = float(d.group(1))
    return out


def grids_covering(lat: float, lon: float, bounds: dict[str, list[float]]) -> list[str]:
    e, n = to_utm(lat, lon)
    return [g for g in GRIDS if g in bounds
            and bounds[g][0] <= e <= bounds[g][2] and bounds[g][1] <= n <= bounds[g][3]]


def coverage(attrs: dict[str, dict]) -> dict:
    """time_coverage_start/end and position as a DAS's global attributes state them."""

    g = attrs.get("NC_GLOBAL", {})
    keep = {}
    for k, v in g.items():
        if re.search(r"time_coverage|geospatial_lat|geospatial_lon|title|platform|wmo|station|depth", k, re.I):
            keep[k] = v
    return keep


def years_between(start: str | None, end: str | None) -> list[int]:
    if not start or not end:
        return []
    try:
        a, b = int(str(start)[:4]), int(str(end)[:4])
    except ValueError:
        return []
    return list(range(a, b + 1))


# ------------------------------------------------------------------ fetching

def get(url: str, timeout: float = 60.0) -> str:
    time.sleep(NDBC_DELAY)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def attempt(log: list[str], what: str, fn):
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 - a census reports what failed, never guesses past it
        log.append(f"{what}: {exc.__class__.__name__}: {exc}")
        return None


def grid_bounds() -> dict[str, list[float]]:
    out = {}
    for g in GRIDS:
        p = BATHY_DIR / f"{g}.json"
        if p.exists():
            out[g] = json.loads(p.read_text(encoding="utf-8"))["bounds_utm"]
    return out


def references() -> dict[str, tuple[float, float]]:
    from forecast.geometry import load

    spots = {s.id: s for s in load()[0]}
    refs = {"coronado_center": tuple(spots["coronado_center"].position)}
    refs["imperial_beach"] = tuple(mop.EXTRA_POINTS["imperial_beach"][0])
    return refs


def census(log: list[str]) -> dict:
    bounds = grid_bounds()
    refs = references()

    table = attempt(log, "NDBC station table", lambda: parse_station_table(get(STATION_TABLE_URL))) or {}
    meta = attempt(log, "NDBC station metadata", lambda: parse_station_metadata(get(STATION_META_URL))) or {}
    hist = merge_historical([attempt(log, f"NDBC historical {kind}",
                                     lambda kind=kind: parse_historical(get(HISTORICAL_URL.format(kind=kind)))) or {}
                             for kind in KINDS])

    stations: dict[str, dict] = {}
    for sid in sorted(set(table) | set(meta) | set(hist)):
        if not re.fullmatch(r"46\d{3}", sid):
            continue                                # the Pacific's WMO block only
        rec = {"id": sid, "name": (table.get(sid, {}).get("NAME") or meta.get(sid, {}).get("name", "")),
               "owner": table.get(sid, {}).get("OWNER") or meta.get(sid, {}).get("owner", ""),
               "positions": [], "historical": hist.get(sid, {})}
        pos = parse_location(table.get(sid, {}).get("LOCATION", ""))
        if pos:
            rec["positions"].append({"lat": pos[0], "lon": pos[1], "source": "station table"})
        for lat, lon, start, stop in meta.get(sid, {}).get("positions", []):
            rec["positions"].append({"lat": lat, "lon": lon, "source": "station metadata",
                                     "start": start, "stop": stop})
        stations[sid] = rec

    # Station pages: for the ones near enough to matter, and the unplaced
    # 462xx (CDIP's block in Southern California), whose history is often all
    # NDBC still holds of them.
    def near(rec) -> bool:
        return any(grids_covering(p["lat"], p["lon"], bounds) for p in rec["positions"])

    want = [s for s, r in stations.items() if near(r) or (not r["positions"] and s.startswith("462"))]
    for sid in want[:PAGE_LIMIT]:
        page = attempt(log, f"NDBC station page {sid}", lambda sid=sid: parse_page(get(STATION_PAGE_URL.format(sid=sid))))
        if page:
            if page.get("position"):
                lat, lon = page["position"]
                stations[sid]["positions"].append({"lat": lat, "lon": lon, "source": "station page"})
            if "water_depth_m" in page:
                stations[sid]["water_depth_m"] = page["water_depth_m"]
    if len(want) > PAGE_LIMIT:
        log.append(f"station pages: {len(want)} wanted, {PAGE_LIMIT} fetched")

    inside = {}
    for sid, rec in stations.items():
        grids = sorted({g for p in rec["positions"] for g in grids_covering(p["lat"], p["lon"], bounds)},
                       key=GRIDS.index)
        if not grids:
            continue
        p = rec["positions"][-1]
        rec["grids"] = grids
        rec["distance_km"] = {k: round(mop.distance_m((p["lat"], p["lon"]), v) / 1000.0, 1)
                              for k, v in refs.items()}
        rec["directional_years"] = directional_years(rec["historical"])
        m = CDIP_ID.search(rec["name"] or "")
        rec["cdip_id"] = m.group(1) if m else None
        inside[sid] = rec

    out = {"retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "grids": bounds, "references": refs, "shallow_m": SHALLOW_M,
           "input": {"id": INPUT, "historical": hist.get(INPUT, {}),
                     "directional_years": directional_years(hist.get(INPUT, {}))},
           "stations": inside, "unplaced_462xx": sorted(s for s, r in stations.items()
                                                       if not r["positions"] and s.startswith("462"))}
    cdip(out, log)
    return out


def cdip(out: dict, log: list[str]) -> None:
    budget = mop.Budget(limit=CDIP_REQUESTS)
    catalog = attempt(log, "MOP catalogue", lambda: budget.fetch(mop.CATALOG))
    if catalog:
        # Distinct (point, product) pairs: each dataset is named in both its
        # `name` and its `urlPath`.
        pairs = set(PRODUCT.findall(catalog))
        products: dict[str, int] = {}
        for _, product in pairs:
            products[product] = products.get(product, 0) + 1
        out["mop_products"] = dict(sorted(products.items()))
    archive = attempt(log, "CDIP archive catalogue",
                      lambda: budget.fetch(f"{mop.SERVER}/thredds/catalog/cdip/archive/catalog.xml"))
    realtime = attempt(log, "CDIP realtime catalogue",
                       lambda: budget.fetch(f"{mop.SERVER}/thredds/catalog/cdip/realtime/catalog.xml"))
    folders = set(FOLDER.findall(archive or ""))
    live = set(REALTIME.findall(realtime or ""))
    out["cdip_archive_folders"] = len(folders)

    nowcast = mop.list_points(catalog, "nowcast") if catalog else {}
    hindcast = mop.list_points(catalog, "hindcast") if catalog else {}
    cache: dict[str, tuple] = {}

    def where(pid: str):
        if pid not in cache:
            v = mop.parse_ascii(budget.fetch(f"{mop.DODS}{nowcast[pid]}.ascii?{mop.LAT},{mop.LON},{mop.DEPTH}"))
            cache[pid] = (v[mop.LAT][0], v[mop.LON][0], (v.get(mop.DEPTH) or [float("nan")])[0])
        return cache[pid]

    shallow = [r for r in out["stations"].values()
               if r["id"] != INPUT and (r.get("water_depth_m") is None or r["water_depth_m"] <= SHALLOW_M)]
    shallow.sort(key=lambda r: r["distance_km"]["imperial_beach"])
    for rec in shallow:
        cid = rec.get("cdip_id")
        if cid:
            folder = f"{cid}p1"
            rec["cdip"] = {"in_archive": folder in folders, "reporting_now": folder in live}
            if folder in folders:
                listing = attempt(log, f"CDIP {folder} catalogue", lambda: budget.fetch(
                    f"{mop.SERVER}/thredds/catalog/cdip/archive/{folder}/catalog.xml"))
                if listing:
                    rec["cdip"]["datasets"] = sorted({n for n, _ in mop.DATASET.findall(listing)}
                                                     | {n for _, n in mop.DATASET_ALT.findall(listing)})
                das = attempt(log, f"CDIP {folder} historic DAS", lambda: budget.fetch(
                    f"{mop.DODS}cdip/archive/{folder}/{folder}_historic.nc.das"))
                if das:
                    rec["cdip"]["historic"] = coverage(mop.parse_das(das))
        if nowcast and rec["positions"]:
            p = rec["positions"][-1]
            found = attempt(log, f"MOP point nearest {rec['id']}",
                            lambda: mop.nearest(list(nowcast), (p["lat"], p["lon"]), where))
            if found:
                pid, dist, meta = found
                rec["mop"] = {"point": pid, "distance_m": round(dist), **meta}
                for product, listing in (("nowcast", nowcast), ("hindcast", hindcast)):
                    if pid in listing:
                        das = attempt(log, f"MOP {pid} {product} DAS",
                                      lambda listing=listing: budget.fetch(f"{mop.DODS}{listing[pid]}.das"))
                        if das:
                            rec["mop"][product] = coverage(mop.parse_das(das))
    out["cdip_requests"] = CDIP_REQUESTS - budget.left


# ------------------------------------------------------------------ report

def cov(c: dict | None) -> str:
    if not c:
        return "—"
    s, e = c.get("time_coverage_start"), c.get("time_coverage_end")
    return f"{str(s)[:10]} – {str(e)[:10]}" if s or e else "not stated"


def span(years: list[int]) -> str:
    if not years:
        return "none"
    runs, start = [], years[0]
    for a, b in zip(years, years[1:] + [None]):
        if b != a + 1:
            runs.append(f"{start}" if start == a else f"{start}–{a}")
            start = b
    return ", ".join(runs)


def report(data: dict, log: list[str]) -> str:
    lines = ["# Observed nearshore spectra: can the chain and MOP be scored?", "",
             f"Generated {data['retrieved_utc']} by `python -m collector.nearshore_census` on Actions "
             "(`mop-check.yml`, `points=census`). Report only: nothing the forecast uses reads it. "
             "The test it looks for: trace the chain to an observed nearshore buoy from 46232's spectra, "
             "take MOP's nearest point, and score both against what the buoy measured. That judges the "
             "deep-water-to-10 m leg the two models disagree on (BRIEFING §56a–§56d); it is not a "
             "verification series for any break.", "",
             f"46232 (the chain's input), years with all five NDBC spectral files: "
             f"**{span(data['input']['directional_years'])}**.", ""]
    if "mop_products" in data:
        lines += ["MOP products CDIP lists for San Diego county (datasets): "
                  + ", ".join(f"`{k}` {v}" for k, v in data["mop_products"].items()), ""]
    lines += [f"Every NDBC station inside the chain's seabed grids ({', '.join(data['grids'])}), "
              "nearest Imperial Beach first. Directional years: all of density, mean and principal "
              "direction, r1 and r2 at NDBC. Overlap: those years shared with 46232's.", "",
              "| NDBC | CDIP | name | stated depth | grids | km to IB / Center | directional years | overlap with 46232 | CDIP archive | reporting now | MOP point (m away, depth) | MOP nowcast | MOP hindcast |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    rows = sorted(data["stations"].values(), key=lambda r: r["distance_km"]["imperial_beach"])
    inp = set(data["input"]["directional_years"])
    for r in rows:
        c, m = r.get("cdip", {}), r.get("mop", {})
        depth = f"{r['water_depth_m']:g} m" if r.get("water_depth_m") is not None else "not stated"
        lines.append("| " + " | ".join([
            r["id"] + (" (input)" if r["id"] == INPUT else ""), r.get("cdip_id") or "—",
            (r["name"] or "—").replace("|", "/"), depth, ", ".join(r["grids"]),
            f"{r['distance_km']['imperial_beach']} / {r['distance_km']['coronado_center']}",
            span(r["directional_years"]), span(sorted(inp & set(r["directional_years"]))),
            cov(c.get("historic")) if c.get("in_archive") else ("not in archive" if c else "—"),
            ("yes" if c.get("reporting_now") else "no") if c else "—",
            f"{m['point']} ({m['distance_m']}, {m.get('depth_m', float('nan')):.1f} m)" if m else "—",
            cov(m.get("nowcast")), cov(m.get("hindcast"))]) + " |")
    if data.get("unplaced_462xx"):
        lines += ["", "462xx stations with NDBC history but no position anywhere NDBC states one: "
                  + ", ".join(data["unplaced_462xx"]) + "."]
    lines += ["", f"CDIP requests spent: {data.get('cdip_requests', 0)} of {CDIP_REQUESTS}.", ""]
    lines += ["## What failed", ""] + ([f"- {x}" for x in log] if log else ["- nothing"])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--report", type=Path, default=REPORT)
    args = ap.parse_args(argv)
    log: list[str] = []
    data = census(log)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "census.json").write_text(json.dumps({**data, "failed": log}, indent=1, sort_keys=True) + "\n",
                                          encoding="utf-8")
    text = report(data, log)
    args.report.write_text(text, encoding="utf-8")
    print(text)
    write_step_summary(text)
    # 2: no station list at all; 3: written, but something failed on the way.
    if not data["stations"]:
        return 2
    return 3 if log else 0


if __name__ == "__main__":
    sys.exit(main())
