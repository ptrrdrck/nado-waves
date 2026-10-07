"""Could 46232's spectra come from CDIP directly, every half hour?

    python -m collector.probe_cdip                        # 191p1 against 46232
    python -m collector.probe_cdip --watch-minutes 95     # and time both feeds
    python -m collector.probe_cdip --station 191p1=46232,220p1=46258

46232 is not an NDBC buoy. It is CDIP station 191, Point Loma South, a
Datawell buoy CDIP operates; NDBC republishes it, HOURLY, and the archive in
`data/spectra/46232/` is that republication. CDIP itself publishes a spectrum
every 30 minutes (a CDIP employee, 2026-10-07, pointing at the realtime
THREDDS dataset `191p1_rt.nc`). If that holds, the Now tab's swell could be
half as stale on cadence alone, and perhaps sooner after each sample, since
NDBC's relay is a hop CDIP's own server does not have.

None of that is measured, and BRIEFING §15 is why it has to be: **a total is
not a validation of a mapping.** CDIP does not publish NDBC's five files. It
publishes the Fourier coefficients a1, b1, a2, b2 per band, and turning those
into NDBC's alpha1, alpha2, r1, r2 is a convention choice (which way round
atan2, from or toward, north or east) that integrates to exactly the right Hs
whichever way it is made. So this probe never chooses a convention. It tries
every candidate and scores each one against two independent references:

1. the file's own `waveMeanDirection`, per band;
2. NDBC's `swdir`, per band, on the records NDBC republished, read from
   this repository's own archive.

The second needs to know which CDIP record NDBC stamps HH:00 — the sample
starting then, or one either side — and that is ALSO measured rather than
assumed: every NDBC record is compared with every CDIP record within 75
minutes of it, and the offset where they agree bin by bin is the answer. A
match at one offset and noise at the others is the control: two consecutive
half-hour samples of the same sea differ by sampling variability, so the
right pairing should stand out by an order of magnitude, not a few percent.

What else it reports, for the decision the owner asked to explore:

- the cadence actually published (consecutive spacing, minute of the hour);
- the newest record's age at fetch time, and with `--watch-minutes`, when
  each new record first becomes fetchable at CDIP *and* at NDBC, polled once
  a minute — the head-to-head lag for the same samples, which nothing in the
  repository can reconstruct after the fact (the spectra files carry no
  first-seen column; NDBC's lag was bracketed from git history, §39);
- CDIP's own quality flags and fill values over the window (§34: one
  unmasked sentinel made the buoy read 21.9 m);
- what NDBC's relay rounds away (directions, moments and energy precision);
- the historic dataset's span, because "the archive starts 2026-08-04" may
  not be true of CDIP, and BRIEFING's infrastructure notes record what it
  cost once to assume history was unrecoverable;
- the NDAR text interface the same email pointed at, raw, unparsed.

Run it on Actions. From a Claude session both CDIP hosts and NDBC are denied
at CONNECT (BRIEFING §8, re-checked 2026-10-07), and "unreachable from here" is
not "not published".

Standard library only, like every collector: THREDDS answers OPeNDAP's ASCII
form (`.dds`, `.das`, `.ascii?var[a:b]`), so no netCDF library is needed to
read it — which also means the parse below is of a text format and is checked
against the DDS shapes it declares, never trusted on its own.

It writes nothing to the repository. It does not archive; that is a different
file, and whether to write it is the owner's decision once this has answered.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median

from .common import DEFAULT_DATA_DIR, utcnow, write_step_summary
from .ndbc import USER_AGENT
from .probe_mop import DENIAL_NOTE
from .probe_spectra import REALTIME as NDBC_REALTIME
from .probe_spectra import fetch, parse_spectral

THREDDS = "https://thredds.cdip.ucsd.edu/thredds/dodsC/cdip"
REALTIME_PATH = "realtime/{stn}_rt.nc"
HISTORIC_PATH = "archive/{stn}/{stn}_historic.nc"
NDAR = "https://cdip.ucsd.edu/data_access/ndar.cdip?{query}"

#: What a spectrum needs, and what checks it. One-dimensional on frequency:
FREQ_VARS = ("waveFrequency", "waveBandwidth")
#: Two-dimensional, time x frequency:
SPEC_VARS = (
    "waveEnergyDensity",
    "waveMeanDirection",
    "waveA1Value",
    "waveB1Value",
    "waveA2Value",
    "waveB2Value",
)
#: One-dimensional on time, the bulk parameters CDIP computes itself:
BULK_VARS = ("waveHs", "waveTp", "waveDp", "waveFlagPrimary")

#: A record is compared with NDBC's within this many minutes either side.
PAIR_WINDOW_MIN = 75

#: Bands carrying at least this share of a record's peak energy are the ones a
#: direction is scored on. A direction in an empty band is noise in both feeds.
ENERGETIC_SHARE = 0.05

#: Older than this and the dataset is present but not live (probe_spectra's
#: rule, carried over).
STALE_HOURS = 12.0

#: Each candidate maps the mathematical angle phi = atan2(b, a) to a compass
#: bearing as  s * phi + c.  These are the four ways a Fourier pair is commonly
#: turned into a bearing: as-is, axes swapped (90 - phi), reversed (from vs
#: toward), and both. alpha2 follows from the same (s, c), modulo 180, since
#: cos 2(theta - alpha2) cannot tell alpha2 from alpha2 + 180.
CONVENTIONS = {
    "atan2(b,a)": (1, 0.0),
    "90-atan2(b,a)": (-1, 90.0),
    "atan2(b,a)+180": (1, 180.0),
    "270-atan2(b,a)": (-1, 270.0),
}


# --------------------------------------------------------------------------
# OPeNDAP text


def parse_dds(text: str) -> dict[str, list[tuple[str, int]]]:
    """Every declared array and its dimensions, from a DAP2 DDS.

    A Grid declares its array and its maps; both come back, under their own
    names, which is harmless — a map is the coordinate variable it names.
    """

    out: dict[str, list[tuple[str, int]]] = {}
    for match in re.finditer(r"\b\w+\s+(\w+)((?:\s*\[\s*\w+\s*=\s*\d+\s*\])+)\s*;", text):
        name = match.group(1)
        dims = [(d, int(n)) for d, n in re.findall(r"\[\s*(\w+)\s*=\s*(\d+)\s*\]", match.group(2))]
        out.setdefault(name, dims)
    return out


def parse_das(text: str) -> dict[str, dict[str, str]]:
    """Attributes by variable, values kept as the raw text after the name."""

    out: dict[str, dict[str, str]] = {}
    stack: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.endswith("{"):
            stack.append(line[:-1].strip())
            out.setdefault(stack[-1], {})
            continue
        if line.startswith("}"):
            if stack:
                stack.pop()
            continue
        if stack and line.endswith(";"):
            parts = line[:-1].split(None, 2)
            if len(parts) == 3:
                value = parts[2].strip()
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                out[stack[-1]][parts[1]] = value
    return out


_BLOCK = re.compile(r"^([A-Za-z_][\w.]*?)((?:\[\d+\])+)\s*$")
_INDEX = re.compile(r"^(?:\[\d+\])+\s*,\s*")


def parse_ascii(text: str) -> dict[str, list]:
    """Arrays from an OPeNDAP `.ascii` response.

    After the DDS and a rule of dashes, each array is a header such as
    `waveHs[48]` or, for a Grid, `waveHs.waveHs[48]` (its maps follow as
    `waveHs.waveTime[48]`, and are skipped: the coordinate is requested on its
    own). A 1-D array's values follow comma-separated; a 2-D array's come one
    row per line, each prefixed `[i], `. Returned as a flat list (1-D) or a
    list of rows (2-D), and CHECKED against the header's own shape — a parse
    that comes out a different size from what the server declared is refused,
    never trimmed or padded.
    """

    body = text.split("\n---", 1)[1] if "\n---" in text else text
    body = body.split("\n", 1)[1] if body.startswith("-") else body
    out: dict[str, list] = {}
    name: str | None = None
    shape: list[int] = []
    values: list[float] = []

    def close() -> None:
        if name is None:
            return
        expected = math.prod(shape)
        if len(values) != expected:
            raise ValueError(
                f"{name}: parsed {len(values)} values where the server declared "
                f"{'x'.join(map(str, shape))} = {expected}"
            )
        if len(shape) == 1:
            out[name] = list(values)
        else:
            width = shape[-1]
            out[name] = [values[i:i + width] for i in range(0, expected, width)]

    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        header = _BLOCK.match(line)
        if header:
            close()
            parts = header.group(1).split(".")
            # A Grid's maps are skipped; its array (`x.x`) and plain arrays kept.
            is_map = len(parts) > 1 and parts[0] != parts[-1]
            name = None if is_map else parts[-1]
            shape = [int(n) for n in re.findall(r"\[(\d+)\]", header.group(2))]
            values = []
            if is_map:
                name = None
            continue
        if name is None:
            continue
        line = _INDEX.sub("", line)
        for token in line.split(","):
            token = token.strip()
            if token:
                values.append(float(token))
    close()
    return out


def ascii_url(base: str, projection: str) -> str:
    """An `.ascii` request with its constraint percent-encoded.

    THREDDS runs on Tomcat, which refuses a bare `[` or `]` in a request
    target with a 400 since 8.5; encoded, THREDDS decodes them itself.
    """

    return f"{base}.ascii?{urllib.parse.quote(projection, safe=',:')}"


def opendap(url: str, *, timeout: float = 90.0, raw_dir: Path | None = None, label: str = "") -> str:
    payload = fetch(url, timeout=timeout)
    text = payload.decode("utf-8", errors="replace")
    if raw_dir is not None and label:
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / label).write_text(text, encoding="utf-8")
    return text


def classify(exc: Exception) -> tuple[str, bool]:
    """Text of a failure, and whether it is a denial (BRIEFING §8)."""

    text = f"{exc.__class__.__name__}: {exc}"
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTP {exc.code} {exc.reason}", exc.code == 403
    return text, isinstance(exc, urllib.error.URLError) or "CONNECT" in text


# --------------------------------------------------------------------------
# The record


@dataclass
class CdipRecord:
    time: datetime
    c11: list[float]
    mean_dir: list[float]
    a1: list[float]
    b1: list[float]
    a2: list[float]
    b2: list[float]
    hs: float = float("nan")
    flag: float = float("nan")


def bearing(a: float, b: float, convention: str, *, second: bool = False) -> float:
    """The compass bearing a Fourier pair gives under one candidate convention."""

    s, c = CONVENTIONS[convention]
    phi = math.degrees(math.atan2(b, a))
    if second:
        return (s * phi / 2.0 + c) % 180.0
    return (s * phi + c) % 360.0


def moment(a: float, b: float) -> float:
    return math.hypot(a, b)


def angdiff(x: float, y: float, period: float = 360.0) -> float:
    d = abs(x - y) % period
    return min(d, period - d)


def energetic(c11: list[float]) -> list[int]:
    finite = [v for v in c11 if not math.isnan(v)]
    if not finite or max(finite) <= 0:
        return []
    floor = ENERGETIC_SHARE * max(finite)
    return [i for i, v in enumerate(c11) if not math.isnan(v) and v >= floor]


def masked(value: float, fill: float | None) -> float:
    if math.isnan(value) or (fill is not None and value == fill):
        return float("nan")
    return value


def records_from(arrays: dict[str, list], fills: dict[str, float | None]) -> list[CdipRecord]:
    """Zip the arrays into records. Fill values become NaN, never values."""

    times = arrays["waveTime"]
    out = []
    for i, t in enumerate(times):
        def row(name: str) -> list[float]:
            return [masked(v, fills.get(name)) for v in arrays[name][i]]

        out.append(CdipRecord(
            time=datetime.fromtimestamp(t, tz=timezone.utc),
            c11=row("waveEnergyDensity"),
            mean_dir=row("waveMeanDirection"),
            a1=row("waveA1Value"),
            b1=row("waveB1Value"),
            a2=row("waveA2Value"),
            b2=row("waveB2Value"),
            hs=masked(arrays["waveHs"][i], fills.get("waveHs")) if "waveHs" in arrays else float("nan"),
            flag=arrays["waveFlagPrimary"][i] if "waveFlagPrimary" in arrays else float("nan"),
        ))
    return out


def fill_value(das: dict[str, dict[str, str]], name: str) -> float | None:
    raw = das.get(name, {}).get("_FillValue")
    try:
        return float(raw) if raw is not None else None
    except ValueError:
        return None


def time_units_are_epoch_seconds(das: dict[str, dict[str, str]]) -> bool:
    units = das.get("waveTime", {}).get("units", "")
    return units.startswith("seconds since 1970-01-01")


# --------------------------------------------------------------------------
# NDBC's republication, from this repository's archive


@dataclass
class NdbcRecord:
    time: datetime
    c11: list[float]
    a1: list[float]
    a2: list[float]
    r1: list[float]
    r2: list[float]


def load_ndbc_archive(directory: Path) -> tuple[list[float], dict[datetime, NdbcRecord]]:
    parts: dict[str, dict[datetime, list[float]]] = {}
    freqs: list[float] = []
    for kind in ("c11", "a1", "a2", "r1", "r2"):
        path = directory / f"{kind}.csv"
        if not path.exists():
            return [], {}
        rows: dict[datetime, list[float]] = {}
        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            freqs = [float(h) for h in next(reader)[1:]]
            for row in reader:
                if not row or not row[0]:
                    continue
                stamp = datetime.fromisoformat(row[0].replace("Z", "+00:00"))
                values = [float(v) if v else float("nan") for v in row[1:]]
                if kind != "c11":
                    values = [float("nan") if v == 999.0 else v for v in values]
                rows[stamp] = values
        parts[kind] = rows
    shared = set.intersection(*(set(p) for p in parts.values()))
    return freqs, {
        t: NdbcRecord(t, parts["c11"][t], parts["a1"][t], parts["a2"][t], parts["r1"][t], parts["r2"][t])
        for t in shared
    }


def bin_map(cdip_freqs: list[float], ndbc_freqs: list[float], tol: float = 0.0011) -> dict[int, int] | None:
    """CDIP band index for each NDBC bin, by FREQUENCY, never by position.

    NDBC writes 0.10125 Hz as 0.1010; a 1.1 mHz tolerance takes that and
    nothing else (the narrowest band spacing is 5 mHz). Every NDBC bin must
    find exactly one band or the comparison is refused.
    """

    out: dict[int, int] = {}
    for j, f in enumerate(ndbc_freqs):
        hits = [i for i, g in enumerate(cdip_freqs) if abs(g - f) <= tol]
        if len(hits) != 1:
            return None
        out[j] = hits[0]
    return out


@dataclass
class PairScore:
    offset_min: float
    energy_rel: float
    dir_err: float
    r1_err: float


def score_pair(cdip: CdipRecord, ndbc: NdbcRecord, bins: dict[int, int], convention: str) -> PairScore | None:
    c_e = [cdip.c11[bins[j]] for j in range(len(bins))]
    n_e = ndbc.c11
    pairs = [(c, n) for c, n in zip(c_e, n_e) if not (math.isnan(c) or math.isnan(n))]
    total = sum(n for _, n in pairs)
    if total <= 0:
        return None
    energy_rel = sum(abs(c - n) for c, n in pairs) / total
    dirs, moments = [], []
    for j in energetic(n_e):
        i = bins[j]
        a, b = cdip.a1[i], cdip.b1[i]
        if any(math.isnan(v) for v in (a, b, ndbc.a1[j], ndbc.r1[j])):
            continue
        dirs.append(angdiff(bearing(a, b, convention), ndbc.a1[j]))
        moments.append(abs(moment(a, b) - ndbc.r1[j]))
    if not dirs:
        return None
    offset = (cdip.time - ndbc.time).total_seconds() / 60.0
    return PairScore(offset, energy_rel, median(dirs), median(moments))


def offsets_table(
    cdip: list[CdipRecord],
    ndbc: dict[datetime, NdbcRecord],
    bins: dict[int, int],
    convention: str,
) -> dict[float, list[PairScore]]:
    by_offset: dict[float, list[PairScore]] = {}
    window = timedelta(minutes=PAIR_WINDOW_MIN)
    for rec in cdip:
        for t, n in ndbc.items():
            if abs(rec.time - t) <= window:
                s = score_pair(rec, n, bins, convention)
                if s is not None:
                    by_offset.setdefault(round(s.offset_min, 1), []).append(s)
    return by_offset


def convention_against_own_mean(records: list[CdipRecord], convention: str) -> float | None:
    errs = []
    for rec in records:
        for i in energetic(rec.c11):
            if any(math.isnan(v) for v in (rec.a1[i], rec.b1[i], rec.mean_dir[i])):
                continue
            errs.append(angdiff(bearing(rec.a1[i], rec.b1[i], convention), rec.mean_dir[i]))
    return median(errs) if errs else None


def second_against_ndbc(
    pairs: list[tuple[CdipRecord, NdbcRecord]], bins: dict[int, int], convention: str
) -> tuple[float | None, float | None]:
    """alpha2 (mod 180) and r2 against NDBC's, on energetic bins."""

    dirs, mom = [], []
    for cdip, ndbc in pairs:
        for j in energetic(ndbc.c11):
            i = bins[j]
            a, b = cdip.a2[i], cdip.b2[i]
            if any(math.isnan(v) for v in (a, b, ndbc.a2[j], ndbc.r2[j])):
                continue
            dirs.append(angdiff(bearing(a, b, convention, second=True), ndbc.a2[j] % 180.0, 180.0))
            mom.append(abs(moment(a, b) - ndbc.r2[j]))
    return (median(dirs) if dirs else None, median(mom) if mom else None)


def hs_from(c11: list[float], bandwidth: list[float]) -> float:
    m0 = sum(e * w for e, w in zip(c11, bandwidth) if not math.isnan(e))
    return 4.0 * math.sqrt(m0) if m0 > 0 else float("nan")


def quantisation(ndbc: dict[datetime, NdbcRecord]) -> dict[str, float]:
    """What NDBC's relay keeps: share of a1 on a 4-degree step, r1 decimals."""

    a1 = [v for r in ndbc.values() for v in r.a1 if not math.isnan(v)]
    r1 = [v for r in ndbc.values() for v in r.r1 if not math.isnan(v)]
    if not a1 or not r1:
        return {}
    return {
        "a1_whole_deg": sum(v == int(v) for v in a1) / len(a1),
        "a1_step4": sum(int(v) % 4 == 0 and v == int(v) for v in a1) / len(a1),
        "r1_two_dp": sum(abs(v * 100 - round(v * 100)) < 1e-6 for v in r1) / len(r1),
    }


# --------------------------------------------------------------------------
# The probe


@dataclass
class StationProbe:
    cdip: str
    ndbc: str
    lines: list[str] = field(default_factory=list)
    denied: bool = False
    failed: bool = False
    stale: bool = False


def probe_station(
    cdip_id: str,
    ndbc_id: str,
    *,
    records: int,
    data_dir: Path,
    raw_dir: Path | None,
    timeout: float,
) -> StationProbe:
    out = StationProbe(cdip_id, ndbc_id)
    lines = out.lines
    base = f"{THREDDS}/{REALTIME_PATH.format(stn=cdip_id)}"
    lines += [f"## CDIP {cdip_id} against NDBC {ndbc_id}", "", f"Dataset: `{base}`", ""]

    try:
        dds_text = opendap(base + ".dds", timeout=timeout, raw_dir=raw_dir, label=f"{cdip_id}_rt.dds")
        das_text = opendap(base + ".das", timeout=timeout, raw_dir=raw_dir, label=f"{cdip_id}_rt.das")
    except Exception as exc:  # noqa: BLE001 - classified
        text, denied = classify(exc)
        out.denied, out.failed = denied, True
        lines += [f"**{'DENIED' if denied else 'FAILED'}** fetching the DDS/DAS: {text}", ""]
        if denied:
            lines += [DENIAL_NOTE.strip(), ""]
        return out

    dds = parse_dds(dds_text)
    das = parse_das(das_text)
    glob = das.get("NC_GLOBAL", {})
    wmo = glob.get("wmo_id", "").strip()
    lines += [
        "| attribute | value |",
        "|---|---|",
        *(f"| `{k}` | {glob.get(k, '—')} |" for k in (
            "title", "wmo_id", "id", "platform_id", "time_coverage_start", "time_coverage_end",
            "geospatial_lat_min", "geospatial_lon_min", "date_modified",
        )),
        "",
    ]
    if wmo and wmo != ndbc_id:
        lines += [f"**CDIP {cdip_id} names itself WMO `{wmo}`, not {ndbc_id}.** "
                  "No comparison is made against a buoy it does not claim to be.", ""]
        out.failed = True
        return out
    if not wmo:
        lines += ["No `wmo_id` in the global attributes; the NDBC id is the caller's claim, unverified.", ""]

    missing = [v for v in ("waveTime", *FREQ_VARS, *SPEC_VARS) if v not in dds]
    if missing:
        lines += [f"**Not in the DDS:** {', '.join(missing)}. Declared: "
                  f"{', '.join(sorted(dds))}", ""]
        out.failed = True
        return out
    n_time = dds["waveTime"][0][1]
    n_freq = dds["waveFrequency"][0][1]
    lines += [f"Declared: **{n_time} records x {n_freq} bands**.", ""]

    lines += ["<details><summary>Variable attributes, verbatim (the conventions live here)</summary>", "", "```"]
    for name in ("waveTime", *FREQ_VARS, *SPEC_VARS, *BULK_VARS):
        attrs = das.get(name, {})
        lines.append(f"{name}: " + "; ".join(f"{k}={v}" for k, v in attrs.items()))
    lines += ["```", "", "</details>", ""]
    if not time_units_are_epoch_seconds(das):
        lines += [f"**waveTime units are `{das.get('waveTime', {}).get('units')}`**, not epoch "
                  "seconds. Refusing to read the clock by assumption.", ""]
        out.failed = True
        return out

    count = min(records, n_time)
    i0, i1 = n_time - count, n_time - 1
    bulk = [v for v in BULK_VARS if v in dds]
    query = ",".join(
        [f"waveTime[{i0}:1:{i1}]", *(f"{v}[0:1:{n_freq - 1}]" for v in FREQ_VARS)]
        + [f"{v}[{i0}:1:{i1}][0:1:{n_freq - 1}]" for v in SPEC_VARS]
        + [f"{v}[{i0}:1:{i1}]" for v in bulk]
    )
    fetched_at = utcnow()
    started = time.monotonic()
    try:
        text = opendap(ascii_url(base, query), timeout=timeout * 3, raw_dir=raw_dir, label=f"{cdip_id}_rt_newest.ascii")
    except Exception as exc:  # noqa: BLE001
        text_, denied = classify(exc)
        out.denied, out.failed = denied, True
        lines += [f"**{'DENIED' if denied else 'FAILED'}** fetching {count} records: {text_}", ""]
        return out
    elapsed = time.monotonic() - started

    try:
        arrays = parse_ascii(text)
    except ValueError as exc:
        out.failed = True
        lines += [f"**The ASCII parse disagrees with the server's shape:** {exc}", "",
                  "```", text[:1500], "```", ""]
        return out
    fills = {v: fill_value(das, v) for v in (*SPEC_VARS, *bulk)}
    recs = records_from(arrays, fills)
    freqs = arrays["waveFrequency"]
    bandwidth = arrays["waveBandwidth"]
    lines += [f"Read **{len(recs)} records** ({len(text) / 1e6:.2f} MB of text, {elapsed:.1f} s).", ""]

    # --- freshness and cadence
    newest = recs[-1].time
    age_min = (fetched_at - newest).total_seconds() / 60.0
    out.stale = age_min > STALE_HOURS * 60
    spacing = Counter(round((b.time - a.time).total_seconds() / 60.0) for a, b in zip(recs, recs[1:]))
    minute = Counter(r.time.minute for r in recs)
    lines += [
        "### Cadence and freshness",
        "",
        f"- span **{recs[0].time:%Y-%m-%d %H:%M} → {newest:%Y-%m-%d %H:%M} UTC**",
        f"- newest record **{age_min:.1f} min old** at fetch ({fetched_at:%H:%M:%S} UTC)"
        + (" — **STALE**" if out.stale else ""),
        f"- spacing between consecutive records (min: count): "
        + ", ".join(f"{k}: {v}" for k, v in spacing.most_common(8)),
        f"- minute of the hour (minute: count): "
        + ", ".join(f"{k:02d}: {v}" for k, v in sorted(minute.items())),
        "",
    ]
    gaps = [(a.time, b.time) for a, b in zip(recs, recs[1:]) if (b.time - a.time) > timedelta(minutes=45)]
    if gaps:
        lines += [f"{len(gaps)} gap(s) over 45 min; largest: "
                  + ", ".join(f"{a:%m-%d %H:%M}→{b:%m-%d %H:%M}" for a, b in
                              sorted(gaps, key=lambda g: g[0] - g[1])[:5]), ""]

    # --- frequency layout, flags, fills, Hs
    flags = Counter(r.flag for r in recs)
    nan_cells = {v: sum(math.isnan(x) for r in recs for x in getattr(r, attr))
                 for v, attr in (("waveEnergyDensity", "c11"), ("waveA1Value", "a1"), ("waveB1Value", "b1"),
                                 ("waveA2Value", "a2"), ("waveB2Value", "b2"))}
    hs_ratio = [hs_from(r.c11, bandwidth) / r.hs for r in recs
                if r.hs and not math.isnan(r.hs) and r.hs > 0 and not math.isnan(hs_from(r.c11, bandwidth))]
    max_moment = max((moment(r.a1[i], r.b1[i]) for r in recs for i in range(n_freq)
                      if not math.isnan(r.a1[i]) and not math.isnan(r.b1[i])), default=float("nan"))
    lines += [
        "### What the file carries",
        "",
        f"- bands: {len(freqs)}, {freqs[0]:.5f}–{freqs[-1]:.5f} Hz; first ten: "
        + ", ".join(f"{f:.5f}" for f in freqs[:10]),
        f"- bandwidths: {min(bandwidth):.5f}–{max(bandwidth):.5f} Hz",
        f"- `waveFlagPrimary` over the window: "
        + ", ".join(f"{k:g}: {v}" for k, v in sorted(flags.items(), key=lambda kv: str(kv[0]))),
        f"- fill/NaN cells: " + ", ".join(f"{k} {v}" for k, v in nan_cells.items()),
        f"- largest r1 = hypot(a1, b1): {max_moment:.3f}" + (" (above 1: these are NOT normalised)" if max_moment > 1.0001 else ""),
        f"- Hs from sum(E·bandwidth) over `waveHs`: median ratio "
        + (f"{median(hs_ratio):.4f} (n = {len(hs_ratio)}, range {min(hs_ratio):.4f}–{max(hs_ratio):.4f})" if hs_ratio else "—"),
        "",
    ]

    # --- conventions against the file's own mean direction
    own = {c: convention_against_own_mean(recs, c) for c in CONVENTIONS}
    lines += [
        "### alpha1 from (a1, b1): every candidate, against two references",
        "",
        "| candidate | vs own `waveMeanDirection` (median °) | vs NDBC `swdir` at the best offset (median °) | r1 vs NDBC (median) |",
        "|---|---|---|---|",
    ]

    # --- against NDBC's republication
    ndbc_freqs, ndbc = load_ndbc_archive(Path(data_dir) / "spectra" / ndbc_id)
    bins = bin_map(freqs, ndbc_freqs) if ndbc_freqs else None
    best_offset = None
    vs_ndbc: dict[str, tuple[float, float]] = {}
    offset_lines: list[str] = []
    pairs: list[tuple[CdipRecord, NdbcRecord]] = []
    if ndbc and bins:
        # The pairing is found on energy alone, which no direction convention
        # touches; directions are then scored at that offset only.
        table = offsets_table(recs, ndbc, bins, "atan2(b,a)")
        offset_lines += [
            "### Which CDIP record NDBC stamps HH:00",
            "",
            "Every NDBC record in the archive against every CDIP record within "
            f"{PAIR_WINDOW_MIN} min. Energy agreement is sum|E_cdip − E_ndbc| / sum E_ndbc over "
            "NDBC's 64 bins, matched by frequency.",
            "",
            "| CDIP minus NDBC stamp (min) | pairs | energy, median rel. diff | energy, 90th pct |",
            "|---|---|---|---|",
        ]
        for off in sorted(table):
            vals = sorted(s.energy_rel for s in table[off])
            offset_lines.append(
                f"| {off:+g} | {len(vals)} | {median(vals):.4f} | {vals[int(0.9 * (len(vals) - 1))]:.4f} |"
            )
        offset_lines.append("")
        ranked = sorted((median([s.energy_rel for s in v]), k) for k, v in table.items() if len(v) >= 3)
        if ranked:
            best_offset = ranked[0][1]
            runner = ranked[1][0] if len(ranked) > 1 else float("nan")
            offset_lines += [
                f"**Best offset {best_offset:+g} min** (median {ranked[0][0]:.4f}); "
                f"the next best is {runner:.4f}, "
                f"{runner / ranked[0][0]:.0f}x worse." if ranked[0][0] > 0 and not math.isnan(runner)
                else f"**Best offset {best_offset:+g} min.**",
                "",
            ]
            for rec in recs:
                t = rec.time - timedelta(minutes=best_offset)
                if t in ndbc:
                    pairs.append((rec, ndbc[t]))
            for c in CONVENTIONS:
                scores = [score_pair(cr, nr, bins, c) for cr, nr in pairs]
                scores = [s for s in scores if s]
                if scores:
                    vs_ndbc[c] = (median(s.dir_err for s in scores), median(s.r1_err for s in scores))
    for c in CONVENTIONS:
        o = own[c]
        n = vs_ndbc.get(c)
        lines.append(
            f"| `{c}` | {o:.2f} |" if o is not None else f"| `{c}` | — |"
        )
        lines[-1] += (f" {n[0]:.2f} | {n[1]:.4f} |" if n else " — | — |")
    lines.append("")
    if not ndbc:
        lines += [f"No NDBC archive at `data/spectra/{ndbc_id}/`; nothing to pair against.", ""]
    elif not bins:
        lines += ["**Frequency bins do not map one-to-one** between CDIP and NDBC. "
                  f"NDBC: {', '.join(f'{f:.4f}' for f in ndbc_freqs[:12])} …", ""]
    lines += offset_lines

    if pairs and vs_ndbc:
        chosen = min(vs_ndbc, key=lambda c: vs_ndbc[c][0])
        a2_err, r2_err = second_against_ndbc(pairs, bins, chosen)
        own_choice = min((c for c in own if own[c] is not None), key=lambda c: own[c], default=None)
        agree = "agree" if own_choice == chosen else f"DISAGREE (own mean picks `{own_choice}`)"
        lines += [
            "### The conversion, on both references",
            "",
            f"- alpha1: **`{chosen}`**; the two references {agree}.",
            f"- alpha2 = same convention on (a2, b2), halved, compared modulo 180: median "
            + (f"{a2_err:.2f}°" if a2_err is not None else "—")
            + "; r2 = hypot(a2, b2) vs NDBC: median " + (f"{r2_err:.4f}" if r2_err is not None else "—"),
            f"- paired records: {len(pairs)}, {pairs[0][1].time:%Y-%m-%d %H:%M} → {pairs[-1][1].time:%Y-%m-%d %H:%M}",
            "",
        ]
        q = quantisation(ndbc)
        if q:
            lines += [
                "### What NDBC's relay rounds away",
                "",
                f"- NDBC alpha1 in whole degrees: {q['a1_whole_deg']:.1%}; on a 4° step: {q['a1_step4']:.1%}",
                f"- NDBC r1 at two decimals: {q['r1_two_dp']:.1%}",
                "- CDIP's coefficients arrive as floats; energy per bin in the newest pair, "
                "CDIP | NDBC, for the five most energetic bins:",
                "",
            ]
            cr, nr = pairs[-1]
            top = sorted(range(len(nr.c11)), key=lambda j: -(nr.c11[j] if not math.isnan(nr.c11[j]) else -1))[:5]
            lines += [f"  - {ndbc_freqs[j]:.4f} Hz: {cr.c11[bins[j]]:.6g} | {nr.c11[j]:g}" for j in sorted(top)]
            lines.append("")

    return out


def probe_historic(cdip_id: str, *, timeout: float, raw_dir: Path | None) -> list[str]:
    base = f"{THREDDS}/{HISTORIC_PATH.format(stn=cdip_id)}"
    lines = [f"### Historic dataset — {cdip_id}", "", f"`{base}`", ""]
    try:
        dds = parse_dds(opendap(base + ".dds", timeout=timeout, raw_dir=raw_dir, label=f"{cdip_id}_historic.dds"))
        n = dds["waveTime"][0][1]
        # Two projections of one variable would come back as two blocks under
        # one name, so the first and last stamps are asked for separately.
        first = parse_ascii(opendap(ascii_url(base, "waveTime[0:1:0]"), timeout=timeout))["waveTime"][0]
        last = parse_ascii(opendap(ascii_url(base, f"waveTime[{n - 1}:1:{n - 1}]"), timeout=timeout))["waveTime"][0]
    except Exception as exc:  # noqa: BLE001
        text, denied = classify(exc)
        return lines + [f"{'DENIED' if denied else 'Not read'}: {text}", ""]
    t0 = datetime.fromtimestamp(first, tz=timezone.utc)
    t1 = datetime.fromtimestamp(last, tz=timezone.utc)
    return lines + [f"**{n} records, {t0:%Y-%m-%d %H:%M} → {t1:%Y-%m-%d %H:%M} UTC.**", ""]


def probe_ndar(queries: list[str], *, timeout: float, raw_dir: Path | None) -> list[str]:
    lines = ["### NDAR text interface — raw, not parsed", ""]
    for q in queries:
        url = NDAR.format(query=q)
        try:
            text = fetch(url, timeout=timeout).decode("utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            msg, denied = classify(exc)
            lines += [f"- `{url}`: {'DENIED' if denied else 'failed'} — {msg}"]
            continue
        if raw_dir is not None:
            raw_dir.mkdir(parents=True, exist_ok=True)
            (raw_dir / ("ndar_" + re.sub(r"\W+", "_", q) + ".txt")).write_text(text, encoding="utf-8")
        head = text.splitlines()[:30]
        lines += [f"<details><summary><code>{q}</code> — {len(text)} bytes, "
                  f"{len(text.splitlines())} lines</summary>", "", "```", *(h[:220] for h in head), "```", "",
                  "</details>", ""]
    return lines


# --------------------------------------------------------------------------
# Watching both feeds for the same samples


def watch(pairs: list[tuple[str, str]], minutes: float, poll_s: float, timeout: float) -> list[str]:
    """When does each new record first become fetchable, at CDIP and at NDBC?

    One request a minute per feed: CDIP's DDS (a few hundred bytes, whose
    waveTime size grows by one per record) and NDBC's `.data_spec`. The lag is
    first-seen minus the record's own stamp, bracketed by the poll before it.
    """

    seen_cdip: dict[str, int] = {}
    seen_ndbc: dict[str, datetime | None] = {}
    events: list[tuple[str, datetime, datetime, datetime]] = []
    errors: Counter = Counter()
    last_poll: dict[str, datetime] = {}
    deadline = time.monotonic() + minutes * 60
    while True:
        for cdip_id, ndbc_id in pairs:
            base = f"{THREDDS}/{REALTIME_PATH.format(stn=cdip_id)}"
            now = utcnow()
            try:
                n = parse_dds(opendap(base + ".dds", timeout=timeout))["waveTime"][0][1]
                if cdip_id in seen_cdip and n > seen_cdip[cdip_id]:
                    arr = parse_ascii(opendap(ascii_url(base, f"waveTime[{seen_cdip[cdip_id]}:1:{n - 1}]"), timeout=timeout))
                    for t in arr["waveTime"]:
                        events.append((f"CDIP {cdip_id}", datetime.fromtimestamp(t, tz=timezone.utc),
                                       last_poll.get("c" + cdip_id, now), now))
                seen_cdip[cdip_id] = n
                last_poll["c" + cdip_id] = now
            except Exception as exc:  # noqa: BLE001
                errors[f"CDIP {cdip_id}: {classify(exc)[0][:80]}"] += 1
            now = utcnow()
            try:
                text = fetch(NDBC_REALTIME.format(station=ndbc_id, suffix=".data_spec"), timeout=timeout)
                _, rows, _, _ = parse_spectral(text.decode("utf-8", errors="replace"))
                newest = rows[-1][0] if rows else None
                if ndbc_id in seen_ndbc and newest and (seen_ndbc[ndbc_id] is None or newest > seen_ndbc[ndbc_id]):
                    events.append((f"NDBC {ndbc_id}", newest, last_poll.get("n" + ndbc_id, now), now))
                seen_ndbc[ndbc_id] = newest
                last_poll["n" + ndbc_id] = now
            except Exception as exc:  # noqa: BLE001
                errors[f"NDBC {ndbc_id}: {classify(exc)[0][:80]}"] += 1
        if time.monotonic() >= deadline:
            break
        time.sleep(poll_s)

    lines = [
        f"### Watched for {minutes:g} min, polling every {poll_s:g} s",
        "",
        "A record's lag is first-seen minus its own stamp; 'absent at' is the poll before.",
        "",
        "| feed | record stamp | absent at | first seen | lag (min) |",
        "|---|---|---|---|---|",
    ]
    for feed, stamp, before, seen in sorted(events, key=lambda e: (e[1], e[0])):
        lines.append(
            f"| {feed} | {stamp:%m-%d %H:%M} | +{(before - stamp).total_seconds() / 60:.1f} "
            f"| +{(seen - stamp).total_seconds() / 60:.1f} | **{(seen - stamp).total_seconds() / 60:.1f}** |"
        )
    if not events:
        lines.append("| — | no new record appeared in either feed | | | |")
    lines.append("")
    if errors:
        lines += ["Poll failures: " + "; ".join(f"{k} ×{v}" for k, v in errors.items()), ""]
    return lines


def parse_stations(spec: str) -> list[tuple[str, str]]:
    out = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        cdip_id, _, ndbc_id = part.partition("=")
        out.append((cdip_id.strip().lower(), ndbc_id.strip()))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe CDIP's own directional spectra against NDBC's relay.")
    parser.add_argument("--station", default="191p1=46232",
                        help="CDIP id = NDBC id, comma-separated. The NDBC id is checked "
                             "against the dataset's own wmo_id, never trusted.")
    parser.add_argument("--records", type=int, default=1500,
                        help="Newest records to read (1500 at 30 min ≈ 31 days).")
    parser.add_argument("--watch-minutes", type=float, default=0.0)
    parser.add_argument("--watch-only", action="store_true",
                        help="Skip the comparison and only time the two feeds, so the "
                             "workflow can run the watch as its own job beside it.")
    parser.add_argument("--poll-seconds", type=float, default=60.0)
    parser.add_argument("--no-historic", action="store_true")
    parser.add_argument("--no-ndar", action="store_true")
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--raw-dir", type=Path, default=None,
                        help="Write every response here, verbatim, for the run's artifact.")
    args = parser.parse_args(argv)

    stations = parse_stations(args.station)
    results = []
    for cdip_id, ndbc_id in [] if args.watch_only else stations:
        result = probe_station(cdip_id, ndbc_id, records=args.records, data_dir=args.data_dir,
                               raw_dir=args.raw_dir, timeout=args.timeout)
        if not args.no_historic and not result.denied:
            result.lines += probe_historic(cdip_id, timeout=args.timeout, raw_dir=args.raw_dir)
        if not args.no_ndar and not result.denied:
            num = re.sub(r"\D.*$", "", cdip_id)
            month = utcnow().strftime("%Y%m")
            result.lines += probe_ndar([f"{num}+st+h", f"{num}+mp+{month}+h"],
                                       timeout=args.timeout, raw_dir=args.raw_dir)
        text = "\n".join(result.lines)
        print(text, flush=True)
        write_step_summary(text)
        results.append(result)

    if args.watch_minutes > 0 and not any(r.denied for r in results):
        text = "\n".join(watch(stations, args.watch_minutes, args.poll_seconds, args.timeout))
        print(text, flush=True)
        write_step_summary(text)

    if any(r.denied for r in results):
        return 2
    if any(r.failed or r.stale for r in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
