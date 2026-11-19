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
5. Saves what the file says about itself, so nothing about MOP is taken from
   memory (BRIEFING §56b left the datum, diffraction and the driving buoys
   inferred): `data/mop/<break>_meta.json` holds the DDS and DAS verbatim,
   every attribute parsed (the global ones and `metaWaterDepth`'s among
   them), and the values of every small variable off the time axis.
6. Saves MOP's own frequency spectrum, checked against the DDS and DAS first
   (`spectral_schema`): `<break>_bands.csv` (centre and edges),
   `<break>_spectrum.csv` (energy density, m²/Hz, one row an hour) and, only
   if the file carries all four, `<break>_moments.csv` (a1, b1, a2, b2). Each
   variable's own `_FillValue` is a gap, never a number. The read-back,
   4·sqrt(Σ E·df) against the file's own Hs hour by hour, goes into the meta
   file: it is what says the units and band widths were read right, and
   `forecast.mopdepth` refuses a spectrum whose read-back failed.

7. **A point that is not a break** (`EXTRA_POINTS`, `--points extra|all`):
   the same files under the point's own name, filed in `points.json` under
   `"points"`, never `"breaks"`, and merged into the file so a run for one
   set never drops the other. Its position is only where the nearest-point
   search starts; the MOP point's own position, depth and shore normal come
   from its file. Handoff item 24b: Imperial Beach, outside Point Loma's
   shadow, to tell the shadow from the input (BRIEFING §56c).

Exit status: 0 everything written; 1 a break's series stopped; 2 CDIP not
reachable; 3 every series written but a spectrum or metadata step stopped
(the workflow commits what it has and then goes red).
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
#: Run 1 used 88 of 90 on the series alone; the spectrum and the small
#: variables add two a point, four if THREDDS refuses a combined request, and
#: the inputs one more (run 2 used 94 without them).
MAX_REQUESTS = 110
#: The variables used, by CDIP's naming. Checked against each file's DDS.
LAT, LON, DEPTH = "metaLatitude", "metaLongitude", "metaWaterDepth"
TIME, HS, TP, DP = "waveTime", "waveHs", "waveTp", "waveDp"
#: MOP's spectrum, by CDIP's naming; checked against the DDS, never assumed.
FREQ, ENERGY = "waveFrequency", "waveEnergyDensity"
BOUNDS, BANDWIDTH = "waveFrequencyBounds", "waveBandwidth"
MOMENTS = ("waveA1Value", "waveB1Value", "waveA2Value", "waveB2Value")
#: What drove each hour (run 2 found both declared): the input sources, a
#: string an hour, and the weighted input coverage of each band.
SOURCE, COVERAGE = "waveModelInputSource", "waveModelBinInputCoverage"
#: A variable off the time axis with at most this many values is fetched
#: whole into the meta file (positions, depth, shore normal, labels, bands).
SMALL_MAX = 2000
#: The read-back must sit within this of 1 (median over the hours), and the
#: worst hour within READBACK_WORST: a unit or a band-width misread is a
#: factor, not a few percent.
READBACK_TOL, READBACK_WORST = 0.03, 0.15
DAP_TYPES = "Byte|Int16|UInt16|Int32|UInt32|Float32|Float64|String|Url"
#: San Diego county's MOP points carry this prefix.
REGION = "D"
#: Points that are not breaks, by name: (lat, lon) WHERE THE SEARCH STARTS,
#: and why. A search target, not a claim about where anything is: the MOP
#: point found, and its position, depth and shore normal, are read from its
#: own file. Imperial Beach (handoff 24b): the straight-line Point Loma edge
#: there is 314.1°, against 258.8-265.8° at the Coronado MOP points, so all
#: of W-WNW (270-295°) arrives without wrapping (`geometry.open_windows`).
EXTRA_POINTS = {
    "imperial_beach": ((32.5785, -117.140),
                       "Imperial Beach, near the pier: outside Point Loma's shadow (handoff 24b)"),
}
POINT_SETS = ("breaks", "extra", "all")

DATASET = re.compile(r'<dataset\b[^>]*\bname="([^"]+)"[^>]*\burlPath="([^"]+)"', re.I)
DATASET_ALT = re.compile(r'<dataset\b[^>]*\burlPath="([^"]+)"[^>]*\bname="([^"]+)"', re.I)
POINT_ID = re.compile(rf"\b({REGION}\d{{4}})_(\w+?)\.nc\b")


class Budget:
    def __init__(self, limit: int = MAX_REQUESTS, delay: float = REQUEST_DELAY):
        self.left, self.delay = limit, delay

    def fetch(self, url: str, timeout: float = 120.0) -> str:
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
    comma-separated values, possibly over several lines, a 2-D array one row
    a line prefixed by its index (`[0], 1.2, 1.3`), row-major. A Grid comes
    as `name.name[n][m]` and then its map vectors as `name.map[n]`: the
    array is kept under the bare name and each map under its dotted one, so
    a map never lands in a variable of the same name fetched beside it."""

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
            parts = head.group(1).split(".")
            name = parts[-1] if len(parts) == 1 or parts[-1] == parts[-2] else ".".join(parts[-2:])
            current = name
            out.setdefault(name, [])
            rest = head.group(4)
            if rest:
                out[name].extend(_numbers(rest))
            continue
        if current is not None:
            # An array row may be prefixed by its index, "[0], 1.2, 1.3".
            out[current].extend(_numbers(re.sub(r"^(\[\d+\])+\s*,?", "", line)))
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


def parse_dds(dds: str) -> dict[str, dict]:
    """{variable: {"type", "dims": [(name, size), ...]}} from a DDS.

    A Grid declares its array and then its maps; the first declaration of a
    name is kept, which is the array (maps repeat coordinate variables)."""

    out: dict[str, dict] = {}
    decl = re.compile(rf"\b({DAP_TYPES})\s+(\w+)\s*((?:\[[^\]]*\])*)\s*;")
    for typ, name, dims in decl.findall(dds):
        if name in out:
            continue
        shape = [((d or f"dim{i}"), int(n)) for i, (d, n) in
                 enumerate(re.findall(r"\[\s*(?:(\w+)\s*=\s*)?(\d+)\s*\]", dims))]
        out[name] = {"type": typ, "dims": shape}
    return out


def _das_tokens(das: str):
    i, n = 0, len(das)
    while i < n:
        c = das[i]
        if c.isspace():
            i += 1
        elif c in "{};,":
            yield c
            i += 1
        elif c == '"':
            j, buf = i + 1, []
            while j < n and das[j] != '"':
                if das[j] == "\\" and j + 1 < n:
                    j += 1
                buf.append(das[j])
                j += 1
            yield ("str", "".join(buf))
            i = j + 1
        else:
            j = i
            while j < n and not das[j].isspace() and das[j] not in '{};,"':
                j += 1
            yield das[i:j]
            i = j


def parse_das(das: str) -> dict[str, dict]:
    """{container: {attribute: value}} from a DAS; nested containers are
    flattened as `outer.inner`. A value is a string, a number, or a list of
    them when the attribute holds several. Strings are kept exactly."""

    toks = list(_das_tokens(das))
    out: dict[str, dict] = {}
    stack: list[str] = []
    i = 0

    def scalar(t):
        if isinstance(t, tuple):
            return t[1]
        try:
            v = float(t)
        except ValueError:
            return t
        return int(v) if re.fullmatch(r"[-+]?\d+", t) else v

    while i < len(toks):
        t = toks[i]
        if t == "}":
            if stack:
                stack.pop()
            i += 1
            if i < len(toks) and toks[i] == ";":
                i += 1
            continue
        if t in ("{", ";", ","):
            i += 1
            continue
        if i + 1 < len(toks) and toks[i + 1] == "{":
            if not (t == "Attributes" and not stack):
                stack.append(t if isinstance(t, str) else t[1])
                out.setdefault(".".join(stack), {})
            i += 2
            continue
        # `Type name value[, value]*;`
        if i + 2 < len(toks) and stack:
            name = toks[i + 1]
            vals, j = [], i + 2
            while j < len(toks) and toks[j] != ";":
                if toks[j] != ",":
                    vals.append(scalar(toks[j]))
                j += 1
            out[".".join(stack)][name] = vals[0] if len(vals) == 1 else vals
            i = j + 1
            continue
        i += 1
    return out


def parse_ascii_strings(body: str, name: str) -> list[str]:
    """The quoted values of one String array in an OPeNDAP ASCII response
    (bare or as a Grid's array, `name.name[n]`), in order. A quote inside a
    value comes escaped, `\\"`."""

    if "---" not in body:
        raise ValueError("not an OPeNDAP ASCII response (no dashed rule)")
    lines = body.split("\n")
    start = next(i for i, line in enumerate(lines) if line.startswith("---")) + 1
    head = re.compile(rf"^(?:{name}\.)?{name}(\[\d+\])*\s*(,(.*))?$")
    out: list[str] = []
    inside = False
    for line in lines[start:]:
        t = line.strip()
        if not t:
            continue
        m = head.match(t)
        if m:
            inside = True
            if m.group(3):
                out += [re.sub(r'\\(.)', r"\1", x) for x in re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(3))]
            continue
        if re.match(r"^[A-Za-z_]", t):
            if inside:
                break
            continue
        if inside:
            out += [re.sub(r'\\(.)', r"\1", x) for x in re.findall(r'"((?:[^"\\]|\\.)*)"', t)]
    return out


def fill_values(attrs: dict) -> set[float]:
    out = set()
    for key in ("_FillValue", "missing_value"):
        v = attrs.get(key)
        for x in (v if isinstance(v, list) else [v]):
            if isinstance(x, (int, float)):
                out.add(float(x))
    return out


def is_gap(x: float, fills: set[float]) -> bool:
    """NaN, a declared fill, or a CDIP large-magnitude sentinel: a gap."""

    return x != x or x in fills or abs(x) > 900


def spectral_schema(dims: dict[str, dict], attrs: dict[str, dict]) -> tuple[dict | None, list[str]]:
    """What the file offers for MOP's spectrum, or why it cannot be read.

    Required: `waveFrequency` (Hz), `waveEnergyDensity` on (waveTime,
    waveFrequency) in either order, and the band edges as
    `waveFrequencyBounds` (n × 2) or, failing that, `waveBandwidth`. The
    moments are taken only when all four share the energy's dimensions.
    Returns (schema, problems); a problem is reported, never guessed past."""

    problems = []
    f = dims.get(FREQ)
    e = dims.get(ENERGY)
    if not f or len(f["dims"]) != 1:
        problems.append(f"{FREQ} not declared as 1-D: {f}")
    if not e or len(e["dims"]) != 2:
        problems.append(f"{ENERGY} not declared as 2-D: {e}")
    if problems:
        return None, problems
    nf = f["dims"][0][1]
    names = [d for d, _ in e["dims"]]
    if sorted(names) != sorted([TIME, FREQ]):
        return None, [f"{ENERGY} is on {e['dims']}, not ({TIME}, {FREQ})"]
    if dict(e["dims"])[FREQ] != nf:
        return None, [f"{ENERGY} has {dict(e['dims'])[FREQ]} frequencies, {FREQ} {nf}"]
    f_units = str(attrs.get(FREQ, {}).get("units", ""))
    if f_units.strip().lower() not in ("hz", "hertz", "s-1", "1/s", "s^-1"):
        problems.append(f"{FREQ} units are {f_units!r}, not Hz")
    edges = None
    b = dims.get(BOUNDS)
    if b and len(b["dims"]) == 2 and b["dims"][0] == (FREQ, nf) and b["dims"][1][1] == 2:
        edges = BOUNDS
    elif dims.get(BANDWIDTH, {}).get("dims") == [(FREQ, nf)]:
        edges = BANDWIDTH
    else:
        problems.append(f"no band edges: {BOUNDS} {b}, {BANDWIDTH} {dims.get(BANDWIDTH)}")
    moments = all(dims.get(m, {}).get("dims") == e["dims"] for m in MOMENTS)
    if problems:
        return None, problems
    return {"nf": nf, "time_first": names[0] == TIME, "edges_from": edges, "moments": moments,
            "units": {v: attrs.get(v, {}).get("units") for v in (FREQ, ENERGY, BOUNDS, BANDWIDTH, *MOMENTS)
                      if v in dims}}, []


def small_variables(dims: dict[str, dict]) -> list[str]:
    """Variables off the time axis with at most SMALL_MAX values."""

    out = []
    for name, d in dims.items():
        size = 1
        for _, n in d["dims"]:
            size *= n
        if TIME not in [k for k, _ in d["dims"]] and size <= SMALL_MAX and name != TIME:
            out.append(name)
    return out


def band_edges(schema: dict, values: dict[str, list[float]]) -> list[tuple[float, float, float, float | None]]:
    """[(centre, lower, upper, bandwidth or None)] per band, from the file's
    own bounds, else centred on the frequency by its bandwidth."""

    f = values[FREQ]
    bw = values.get(BANDWIDTH) or [None] * len(f)
    if len(bw) != len(f):
        bw = [None] * len(f)
    if schema["edges_from"] == BOUNDS:
        b = values[BOUNDS]
        if len(b) != 2 * len(f):
            raise ValueError(f"{BOUNDS} gave {len(b)} values for {len(f)} bands")
        return [(f[i], b[2 * i], b[2 * i + 1], bw[i]) for i in range(len(f))]
    return [(f[i], f[i] - bw[i] / 2, f[i] + bw[i] / 2, bw[i]) for i in range(len(f))]


def unpack(flat: list[float], n_time: int, nf: int, time_first: bool) -> list[list[float]]:
    """Row-major values of a (time, freq) or (freq, time) array, by hour."""

    if len(flat) != n_time * nf:
        raise ValueError(f"{len(flat)} values for {n_time} x {nf}")
    if time_first:
        return [flat[k * nf:(k + 1) * nf] for k in range(n_time)]
    return [[flat[i * n_time + k] for i in range(nf)] for k in range(n_time)]


def readback(energy: list[list[float | None]], widths: list[float], hs: list[float]) -> dict:
    """4·sqrt(Σ E·df) over the file's own Hs, hour by hour (complete hours)."""

    r = []
    for row, h in zip(energy, hs):
        if h is None or h <= 0 or any(x is None for x in row):
            continue
        m0 = sum(x * w for x, w in zip(row, widths))
        if m0 > 0:
            r.append(4 * math.sqrt(m0) / h)
    if not r:
        return {"hours": 0, "ok": False}
    r.sort()
    med = r[len(r) // 2]
    worst = max(r, key=lambda x: abs(x - 1))
    return {"hours": len(r), "median": round(med, 5), "p01": round(r[int(0.01 * (len(r) - 1))], 5),
            "p99": round(r[int(0.99 * (len(r) - 1))], 5), "worst": round(worst, 5),
            "ok": abs(med - 1) <= READBACK_TOL and abs(worst - 1) <= READBACK_WORST}


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


# ------------------------------------------------------------------ spectrum and metadata

def save_extras(budget: Budget, break_id: str, pid: str, url_path: str, dds: str, das: str,
                times: tuple[int, int, list[float]], hs: list[float | None],
                out: Path) -> tuple[list[str], bool]:
    """Write `<break>_meta.json` and, if the schema allows, the spectrum
    files for one point. `times` is (first index, last index, the epoch
    seconds between them), the same slice as the Hs series. Returns (report
    lines, everything written and read back)."""

    lines: list[str] = []
    dims = parse_dds(dds)
    attrs = parse_das(das)
    meta = {"point": pid, "url_path": url_path,
            "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "global": attrs.get("NC_GLOBAL", {}), "metaWaterDepth": attrs.get(DEPTH, {}),
            "attributes": attrs, "variables": {k: {"type": v["type"], "dims": v["dims"]} for k, v in dims.items()},
            "dds": dds, "das": das}
    ok = True
    small = small_variables(dims)
    values: dict[str, list[float]] = {}
    if small:
        try:
            body = budget.fetch(f"{DODS}{url_path}.ascii?{','.join(small)}")
        except urllib.error.HTTPError as exc:
            # One variable THREDDS will not serve as ASCII must not cost the
            # bands: say so, and fetch only what the spectrum needs.
            small_err = f"{exc.__class__.__name__}: {exc}"
            small = [v for v in (FREQ, BOUNDS, BANDWIDTH) if v in dims]
            body = budget.fetch(f"{DODS}{url_path}.ascii?{','.join(small)}") if small else ""
            meta["small_variables_error"] = small_err
            lines.append(f"  - the small variables were refused together ({small_err}); bands fetched alone")
        meta["small_variables"] = {"names": small, "ascii": body}
        values = parse_ascii(body) if body else {}
    schema, problems = spectral_schema(dims, attrs)
    meta["spectrum"] = {"schema": schema, "problems": problems}
    if schema is None:
        ok = False
        lines.append(f"  - spectrum not read: {'; '.join(problems)}. Variables declared: {sorted(dims)}")
    else:
        try:
            bands = band_edges(schema, values)
            nf = schema["nf"]
            e_dims = dims[ENERGY]["dims"]
            sl = {TIME: f"[{times[0]}:1:{times[1]}]", FREQ: f"[0:1:{nf - 1}]"}
            hyper = "".join(sl[d] for d, _ in e_dims)
            names = [ENERGY] + (list(MOMENTS) if schema["moments"] else [])
            try:
                got = parse_ascii(budget.fetch(f"{DODS}{url_path}.ascii?{','.join(v + hyper for v in names)}",
                                               timeout=600.0))
            except urllib.error.HTTPError as exc:
                if len(names) == 1:
                    raise
                # Too much in one response: the energy, then the moments.
                lines.append(f"  - energy and moments refused together ({exc}); fetched apart")
                got = parse_ascii(budget.fetch(f"{DODS}{url_path}.ascii?{ENERGY}{hyper}", timeout=600.0))
                got.update(parse_ascii(budget.fetch(
                    f"{DODS}{url_path}.ascii?{','.join(m + hyper for m in MOMENTS)}", timeout=600.0)))
            n_time = times[1] - times[0] + 1
            masked = {}
            arrays = {}
            for v in names:
                fills = fill_values(attrs.get(v, {}))
                rows = unpack(got.get(v, []), n_time, nf, schema["time_first"])
                arrays[v] = [[None if is_gap(x, fills) else x for x in r] for r in rows]
                masked[v] = sum(x is None for r in arrays[v] for x in r)
            widths = [hi - lo for _, lo, hi, _ in bands]
            rb = readback(arrays[ENERGY], widths, hs)
            meta["spectrum"].update({"bands": nf, "hours": n_time, "masked": masked, "readback": rb,
                                     "first_index": times[0], "last_index": times[1]})
            with (out / f"{break_id}_bands.csv").open("w", encoding="utf-8") as fh:
                fh.write("band,freq_hz,lower_hz,upper_hz,bandwidth_hz\n")
                for i, (fc, lo, hi, bw) in enumerate(bands):
                    fh.write(f"{i},{fc:.6g},{lo:.6g},{hi:.6g},{'' if bw is None else f'{bw:.6g}'}\n")
            stamps = [datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                      for t in times[2]]
            cell = lambda x, fmt: "" if x is None else format(x, fmt)
            with (out / f"{break_id}_spectrum.csv").open("w", encoding="utf-8") as fh:
                fh.write("valid_utc," + ",".join(f"e{i:02d}" for i in range(nf)) + "\n")
                for k in range(n_time):
                    fh.write(stamps[k] + "," + ",".join(cell(x, ".4g") for x in arrays[ENERGY][k]) + "\n")
            mom_path = out / f"{break_id}_moments.csv"
            if schema["moments"]:
                heads = [f"{m}_{i:02d}" for m in ("a1", "b1", "a2", "b2") for i in range(nf)]
                with mom_path.open("w", encoding="utf-8") as fh:
                    fh.write("valid_utc," + ",".join(heads) + "\n")
                    for k in range(n_time):
                        fh.write(stamps[k] + "," + ",".join(cell(x, ".3f") for m in MOMENTS
                                                            for x in arrays[m][k]) + "\n")
            elif mom_path.exists():
                mom_path.unlink()
            if SOURCE in dims or COVERAGE in dims:
                write_inputs(budget, break_id, url_path, dims, attrs, (times[0], times[1]), stamps, nf, out, meta)
            if meta.get("inputs", {}).get("sources") is not None:
                top = list(meta["inputs"]["sources"].items())[:6]
                lines.append(f"  - input sources (hours): {top}")
            lines.append(f"  - spectrum: {nf} bands {bands[0][1]:.4f}–{bands[-1][2]:.4f} Hz (edges from "
                         f"{schema['edges_from']}), moments {'saved' if schema['moments'] else 'not in the file'}; "
                         f"gaps {masked}; read-back 4√m0 / Hs median {rb.get('median')}, worst {rb.get('worst')} "
                         f"over {rb['hours']} hours{'' if rb['ok'] else ' — FAILED, not to be read'}.")
            ok = ok and rb["ok"]
        except Exception as exc:  # noqa: BLE001 - reported; the series is already written
            ok = False
            meta["spectrum"]["problems"].append(f"{exc.__class__.__name__}: {exc}")
            lines.append(f"  - spectrum failed: {exc.__class__.__name__}: {exc}")
    depth_attrs = attrs.get(DEPTH, {})
    lines.append(f"  - {DEPTH} attributes: {json.dumps(depth_attrs)}")
    (out / f"{break_id}_meta.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    return lines, ok


def write_inputs(budget: Budget, break_id: str, url_path: str, dims: dict, attrs: dict,
                 span: tuple[int, int], stamps: list[str], nf: int, out: Path, meta: dict) -> None:
    """`<break>_inputs.csv`: what drove each hour (the input sources) and how
    much of each band had input (weighted coverage), as the file says.
    A fill is a gap; a source string is kept exactly."""

    i0, i1 = span
    n = i1 - i0 + 1
    parts = []
    if SOURCE in dims and [d for d, _ in dims[SOURCE]["dims"]] == [TIME]:
        parts.append(f"{SOURCE}[{i0}:1:{i1}]")
    cov_ok = COVERAGE in dims and dims[COVERAGE]["dims"] == dims[ENERGY]["dims"]
    if cov_ok:
        e_dims = dims[COVERAGE]["dims"]
        parts.append(COVERAGE + "".join(f"[{i0}:1:{i1}]" if d == TIME else f"[0:1:{nf - 1}]" for d, _ in e_dims))
    if not parts:
        meta["inputs"] = {"problems": [f"{SOURCE} {dims.get(SOURCE)}, {COVERAGE} {dims.get(COVERAGE)}"]}
        return
    body = budget.fetch(f"{DODS}{url_path}.ascii?{','.join(parts)}", timeout=600.0)
    src = parse_ascii_strings(body, SOURCE) if SOURCE in parts[0] else []
    fill_s = attrs.get(SOURCE, {}).get("_FillValue")
    src = [None if (x == fill_s or x == "") else x for x in src]
    if src and len(src) != n:
        raise ValueError(f"{SOURCE}: {len(src)} values for {n} hours")
    cov = None
    if cov_ok:
        fills = fill_values(attrs.get(COVERAGE, {}))
        cov = [[None if is_gap(x, fills) else x for x in r]
               for r in unpack(parse_ascii(body).get(COVERAGE, []), n, nf, dims[ENERGY]["dims"][0][0] == TIME)]
    with (out / f"{break_id}_inputs.csv").open("w", encoding="utf-8") as fh:
        fh.write("valid_utc,input_source" + "".join(f",cov{i:02d}" for i in range(nf if cov else 0)) + "\n")
        for k in range(n):
            s = "" if not src or src[k] is None else '"' + src[k].replace('"', '""') + '"'
            c = "" if cov is None else "," + ",".join("" if x is None else f"{x:.3f}" for x in cov[k])
            fh.write(f"{stamps[k]},{s}{c}\n")
    counts: dict[str, int] = {}
    for x in src:
        counts[x or ""] = counts.get(x or "", 0) + 1
    meta["inputs"] = {"sources": dict(sorted(counts.items(), key=lambda kv: -kv[1])),
                      "coverage": bool(cov), "hours": n}


# ------------------------------------------------------------------ main

def write_points(path: Path, chosen: dict[str, dict], requests_used: int) -> dict:
    """Merge this run's points into `points.json`: a run for the breaks never
    drops the points that are not breaks, nor the other way round. Within a
    section, only the entries this run fetched are replaced."""

    old = json.loads(path.read_text()) if path.exists() else {}
    doc = {"source": CATALOG, "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "requests_used": requests_used}
    for section in ("breaks", "points"):
        merged = {**old.get(section, {}), **chosen.get(section, {})}
        if merged:
            doc[section] = merged
    path.write_text(json.dumps(doc, indent=2) + "\n")
    return doc


def main(argv: list[str] | None = None) -> int:
    from forecast.geometry import load
    from forecast.nearshore import BREAKS

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--product", default="nowcast")
    ap.add_argument("--since", default="2026-08-04", help="first day to keep (UTC)")
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--points", choices=POINT_SETS, default="breaks",
                    help="the three breaks (default), the points that are not breaks (EXTRA_POINTS), or both")
    args = ap.parse_args(argv)

    budget = Budget()
    title = {"breaks": "the Coronado breaks", "extra": "points that are not breaks",
             "all": "the Coronado breaks and points that are not breaks"}[args.points]
    report = [f"## CDIP MOP at {title} ({args.product})", ""]
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
    targets: list[tuple[str, tuple[float, float], str]] = []
    if args.points in ("breaks", "all"):
        targets += [(b, tuple(by_id[b].position), "breaks") for b in BREAKS]
    if args.points in ("extra", "all"):
        targets += [(name, tuple(pos), "points") for name, (pos, _) in EXTRA_POINTS.items()]
    since = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc).timestamp()
    args.out.mkdir(parents=True, exist_ok=True)
    chosen: dict[str, dict] = {"breaks": {}, "points": {}}
    status = 0
    extras_failed = False
    for b, pos, section in targets:
        try:
            pid, dist, meta = nearest(ids, pos, where)
            dds = budget.fetch(f"{DODS}{points[pid]}.dds")
            missing = check_dds(dds)
            if missing:
                report.append(f"- {b}: {pid} lacks {missing}. DDS:\n```\n{dds[:1500]}\n```")
                status = 1
                continue
            das = budget.fetch(f"{DODS}{points[pid]}.das")
            units = time_units(das)
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
            chosen[section][b] = {"point": pid, "url_path": points[pid], "distance_m": round(dist),
                                  "product": args.product, **meta, "hours": n,
                                  "first_utc": datetime.fromtimestamp(t[i0], tz=timezone.utc).isoformat(),
                                  "last_utc": datetime.fromtimestamp(t[i1], tz=timezone.utc).isoformat()}
            if section == "points":
                chosen[section][b].update({"search_from": list(pos), "why": EXTRA_POINTS[b][1]})
            what = "the break" if section == "breaks" else "the search target"
            report.append(f"- {b}: {pid}, {dist:.0f} m from {what}, {meta['depth_m']:.1f} m deep, {n} hours.")
            try:
                hs_vals = [None if is_gap(x, fill_values(parse_das(das).get(HS, {}))) else x for x in v[HS]]
                extra, ok = save_extras(budget, b, pid, points[pid], dds, das, (i0, i1, t[i0:i1 + 1]),
                                        hs_vals, args.out)
                report += extra
                if not ok:
                    extras_failed = True
            except Exception as exc:  # noqa: BLE001 - the series stands; this is reported
                report.append(f"  - metadata or spectrum failed: {exc.__class__.__name__}: {exc}")
                extras_failed = True
        except Exception as exc:  # noqa: BLE001
            report.append(f"- {b}: failed, {exc.__class__.__name__}: {exc}")
            status = 2 if isinstance(exc, urllib.error.URLError) else 1
    if chosen["breaks"] or chosen["points"]:
        write_points(args.out / "points.json", chosen, MAX_REQUESTS - budget.left)
    report.append(f"\n{MAX_REQUESTS - budget.left} requests of {MAX_REQUESTS}.")
    print("\n".join(report))
    write_step_summary("\n".join(report))
    if status == 0 and extras_failed:
        return 3
    return status


if __name__ == "__main__":
    sys.exit(main())
