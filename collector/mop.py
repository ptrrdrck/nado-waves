"""CDIP MOP at the three Coronado breaks: find the nearest points, archive their series.

    python -m collector.mop [--product nowcast] [--since 2026-08-04]

**Run it on Actions, never from a session**: both CDIP hosts are refused at
CONNECT by a session's egress proxy (BRIEFING §8, `probe_mop.DENIAL_NOTE`).

Why (BRIEFING §29's "Next", never done until §56). MOP is CDIP's backward
ray model from the buoys to every 100 m of the California coast at 10 m of
water — the established version of exactly what `forecast.raytrace` builds.
It is a MODEL, not an observation (CLAUDE.md): a cross-check, never a
verification series, and never blended into anything. §56 found the chain
taking westerly swell round Point Loma into Center and South at about twice
a planar beach's acceptance; MOP is the one outside calculation of the same
wrap.

What this does, and why it discovers rather than assumes:

1. Reads the MOP_alongshore THREDDS catalogue and lists the datasets that
   exist for the product asked (nowcast by default: MOP driven by the
   buoys' observed spectra, which is what LIVE does with 46232). Nothing
   here guesses a dataset name; `probe_mop` exists because guessed deep URLs
   gave this project two wrong verdicts.
2. Finds each break's nearest point by its position, reading positions from
   the files' own metadata, with a bounded pattern search over the listed
   ids (MOP numbers its points along the coast), politely: one request every
   REQUEST_DELAY seconds, at most MAX_REQUESTS in all.
3. Reads the chosen file's DDS and DAS, and stops with what it found if the
   variables or the time units are not the ones below — a renamed variable
   is reported, never guessed at.
4. Fetches time, Hs, Tp and Dp since `--since` through OPeNDAP's ASCII form
   (standard library only, like every collector) and writes
   `data/mop/<break>.csv` and `data/mop/points.json`.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .common import write_step_summary
from .ndbc import USER_AGENT

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "mop"
SERVER = "https://thredds.cdip.ucsd.edu"
CATALOG = f"{SERVER}/thredds/catalog/cdip/model/MOP_alongshore/catalog.xml"
DODS = f"{SERVER}/thredds/dodsC/"
#: Politeness, as `probe_mop`: a university research server, not a CDN.
REQUEST_DELAY = 2.0
MAX_REQUESTS = 90
#: The variables used, by CDIP's naming. Checked against each file's DDS.
LAT, LON, DEPTH = "metaLatitude", "metaLongitude", "metaWaterDepth"
TIME, HS, TP, DP = "waveTime", "waveHs", "waveTp", "waveDp"
#: San Diego county's MOP points carry this prefix.
REGION = "D"

DATASET = re.compile(r'<dataset\b[^>]*\bname="([^"]+)"[^>]*\burlPath="([^"]+)"', re.I)
DATASET_ALT = re.compile(r'<dataset\b[^>]*\burlPath="([^"]+)"[^>]*\bname="([^"]+)"', re.I)
POINT_ID = re.compile(rf"\b({REGION}\d{{4}})_(\w+?)\.nc\b")


class Budget:
    def __init__(self, limit: int = MAX_REQUESTS, delay: float = REQUEST_DELAY):
        self.left, self.delay = limit, delay

    def fetch(self, url: str, timeout: float = 60.0) -> str:
        if self.left <= 0:
            raise RuntimeError(f"request budget ({MAX_REQUESTS}) spent; not fetching {url}")
        self.left -= 1
        time.sleep(self.delay)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")


# ------------------------------------------------------------------ parsing

def list_points(catalog_xml: str, product: str) -> dict[str, str]:
    """{point id: urlPath} for one product, from a THREDDS catalogue."""

    found = {}
    pairs = [(n, u) for n, u in DATASET.findall(catalog_xml)]
    pairs += [(n, u) for u, n in DATASET_ALT.findall(catalog_xml)]
    for name, url in pairs:
        m = POINT_ID.search(name) or POINT_ID.search(url)
        if m and m.group(2).lower() == product.lower():
            found[m.group(1)] = url
    return dict(sorted(found.items()))


def parse_ascii(body: str) -> dict[str, list[float]]:
    """OPeNDAP's .ascii response: values per variable after the dashed rule.

    Scalars come as `name, value`; arrays as a `name[n]` line followed by
    comma-separated values, possibly over several lines. Grids repeat their
    map vectors as `name.map[n]`; only the bare variable names are kept."""

    if "---" not in body:
        raise ValueError("not an OPeNDAP ASCII response (no dashed rule)")
    data = body.split("\n", body.count("\n"))
    start = next(i for i, line in enumerate(data) if line.startswith("---")) + 1
    out: dict[str, list[float]] = {}
    current = None
    for line in data[start:]:
        line = line.strip()
        if not line:
            continue
        head = re.match(r"^([A-Za-z_][\w.]*)(\[\d+\])*\s*(,\s*(.*))?$", line)
        if head and not re.match(r"^[-+0-9.eE]", line):
            name = head.group(1).split(".")[-1]
            current = name
            out.setdefault(name, [])
            rest = head.group(4)
            if rest:
                out[name].extend(_numbers(rest))
            continue
        if current is not None:
            # An array row may be prefixed by its index, "[0], 1.2, 1.3".
            out[current].extend(_numbers(re.sub(r"^\[\d+\]\s*,?", "", line)))
    return out


def _numbers(text: str) -> list[float]:
    vals = []
    for tok in text.split(","):
        tok = tok.strip()
        if tok:
            try:
                vals.append(float(tok))
            except ValueError:
                pass
    return vals


def time_units(das: str) -> str | None:
    m = re.search(rf"{TIME}\s*\{{(.*?)\}}", das, re.S)
    if not m:
        return None
    u = re.search(r'units\s+"([^"]+)"', m.group(1))
    return u.group(1) if u else None


def check_dds(dds: str) -> list[str]:
    """Variables this module needs that the file does not declare."""

    return [v for v in (LAT, LON, DEPTH, TIME, HS, TP, DP) if not re.search(rf"\b{v}\b", dds)]


def distance_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat = math.radians(0.5 * (a[0] + b[0]))
    dy = (a[0] - b[0]) * 111_320.0
    dx = (a[1] - b[1]) * 111_320.0 * math.cos(lat)
    return math.hypot(dx, dy)


# ------------------------------------------------------------------ search

def nearest(ids: list[str], position, where) -> tuple[str, float, dict]:
    """Pattern search over the listed ids for the point nearest `position`.

    `where(id)` returns (lat, lon, depth) from the file's metadata. MOP
    numbers its points in order along the coast, so distance along the list
    is unimodal near the answer; a coarse pass first, then halving steps."""

    seen: dict[int, float] = {}
    meta: dict[str, tuple] = {}

    def d(i: int) -> float:
        i = max(0, min(len(ids) - 1, i))
        if i not in seen:
            m = where(ids[i])
            meta[ids[i]] = m
            seen[i] = distance_m(position, m[:2])
        return seen[i]

    coarse = sorted({int(round(k * (len(ids) - 1) / 8)) for k in range(9)})
    best = min(coarse, key=d)
    step = max(1, len(ids) // 16)
    while step >= 1:
        moved = True
        while moved:
            moved = False
            for cand in (best - step, best + step):
                if 0 <= cand < len(ids) and d(cand) < d(best):
                    best, moved = cand, True
        step //= 2
    return ids[best], seen[best], {"lat": meta[ids[best]][0], "lon": meta[ids[best]][1],
                                   "depth_m": meta[ids[best]][2]}


# ------------------------------------------------------------------ main

def main(argv: list[str] | None = None) -> int:
    from forecast.geometry import load
    from forecast.nearshore import BREAKS

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--product", default="nowcast")
    ap.add_argument("--since", default="2026-08-04", help="first day to keep (UTC)")
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args(argv)

    budget = Budget()
    report = [f"## CDIP MOP at the Coronado breaks ({args.product})", ""]
    try:
        catalog = budget.fetch(CATALOG)
    except Exception as exc:  # noqa: BLE001 - reports, never raises
        report.append(f"Catalogue not reachable: {exc.__class__.__name__}: {exc}")
        print("\n".join(report)); write_step_summary("\n".join(report))
        return 2
    points = list_points(catalog, args.product)
    report.append(f"{len(points)} {REGION}-prefixed {args.product} datasets listed in the catalogue.")
    if not points:
        sample = sorted({n for n, _ in DATASET.findall(catalog)})[:20]
        report.append(f"None matched `{REGION}NNNN_{args.product}.nc`. First names listed: {sample}")
        print("\n".join(report)); write_step_summary("\n".join(report))
        return 1
    ids = list(points)

    def where(pid: str):
        body = budget.fetch(f"{DODS}{points[pid]}.ascii?{LAT},{LON},{DEPTH}")
        v = parse_ascii(body)
        return v[LAT][0], v[LON][0], (v.get(DEPTH) or [float("nan")])[0]

    spots, _ = load()
    by_id = {s.id: s for s in spots}
    since = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc).timestamp()
    args.out.mkdir(parents=True, exist_ok=True)
    chosen = {}
    status = 0
    for b in BREAKS:
        pos = tuple(by_id[b].position)
        try:
            pid, dist, meta = nearest(ids, pos, where)
            dds = budget.fetch(f"{DODS}{points[pid]}.dds")
            missing = check_dds(dds)
            if missing:
                report.append(f"- {b}: {pid} lacks {missing}. DDS:\n```\n{dds[:1500]}\n```")
                status = 1
                continue
            units = time_units(budget.fetch(f"{DODS}{points[pid]}.das"))
            if not units or not units.startswith("seconds since 1970-01-01"):
                report.append(f"- {b}: {pid} {TIME} units are {units!r}, not seconds since 1970; stopped.")
                status = 1
                continue
            t = parse_ascii(budget.fetch(f"{DODS}{points[pid]}.ascii?{TIME}"))[TIME]
            i0 = next((i for i, v in enumerate(t) if v >= since), None)
            if i0 is None:
                report.append(f"- {b}: {pid} has nothing since {args.since} (last {t[-1] if t else 'none'}).")
                status = 1
                continue
            i1 = len(t) - 1
            sl = f"[{i0}:1:{i1}]"
            v = parse_ascii(budget.fetch(f"{DODS}{points[pid]}.ascii?{HS}{sl},{TP}{sl},{DP}{sl}"))
            n = i1 - i0 + 1
            if not all(len(v.get(k, [])) == n for k in (HS, TP, DP)):
                report.append(f"- {b}: {pid} returned {[len(v.get(k, [])) for k in (HS, TP, DP)]} values for {n} times; stopped.")
                status = 1
                continue
            with (args.out / f"{b}.csv").open("w", encoding="utf-8") as fh:
                fh.write("valid_utc,hs_m,tp_s,dp_deg\n")
                for k in range(n):
                    when = datetime.fromtimestamp(t[i0 + k], tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                    hs, tp, dp = v[HS][k], v[TP][k], v[DP][k]
                    # CDIP's fill values are large negatives; a gap stays a gap.
                    cells = ["" if (x != x or x < -900 or x > 900) else f"{x:.3f}" for x in (hs, tp, dp)]
                    fh.write(f"{when},{','.join(cells)}\n")
            chosen[b] = {"point": pid, "url_path": points[pid], "distance_m": round(dist),
                         "product": args.product, **meta, "hours": n,
                         "first_utc": datetime.fromtimestamp(t[i0], tz=timezone.utc).isoformat(),
                         "last_utc": datetime.fromtimestamp(t[i1], tz=timezone.utc).isoformat()}
            report.append(f"- {b}: {pid}, {dist:.0f} m from the break, {meta['depth_m']:.1f} m deep, {n} hours.")
        except Exception as exc:  # noqa: BLE001
            report.append(f"- {b}: failed, {exc.__class__.__name__}: {exc}")
            status = 2 if isinstance(exc, urllib.error.URLError) else 1
    if chosen:
        (args.out / "points.json").write_text(json.dumps(
            {"source": CATALOG, "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "requests_used": MAX_REQUESTS - budget.left, "breaks": chosen}, indent=2) + "\n")
    report.append(f"\n{MAX_REQUESTS - budget.left} requests of {MAX_REQUESTS}.")
    print("\n".join(report))
    write_step_summary("\n".join(report))
    return status


if __name__ == "__main__":
    sys.exit(main())
