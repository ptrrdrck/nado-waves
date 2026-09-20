"""Fetch NOAA's surveyed shoreline near Coronado, to check the digitised chords.

    python -m collector.shoreline          # discover, fetch, archive
    python -m collector.shoreline --probe  # discover and report, store nothing

Run it on Actions. Every NOAA coastal host is denied at CONNECT from a Claude
session — measured 2026-09-20, `chs.coast.noaa.gov`, `coast.noaa.gov`,
`geodesy.noaa.gov` and `maps.coast.noaa.gov` all answered 403 (BRIEFING §8).

WHY THIS EXISTS. `forecast/spots.json` carries three shoreline chords traced by
hand from Google Earth. They set each break's seaward normal, which is the only
thing standing behind the offshore/onshore/cross-shore reading on the app
surface. One of the three, `coronado_north`, is known by its own provenance to
be about 19 degrees off from an imagery splice. Nothing independent has ever
checked the other two.

That matters more than it sounds. Measured (BRIEFING §20): the verdict
boundaries sit at fixed angles from the normal, which puts six of the nine
boundaries for Coronado's three breaks inside 265-330 degrees — and 62.6% of a
three-year wind record sits in 270-330. One degree of normal error changes the
verdict on 4.2% of readings; five degrees on 21%; north's known 19 on ~70%.
A hand-traced chord is not good enough for a number that sensitive.

DISCOVERY, NOT GUESSED URLS. `probe_mop` learned this the expensive way and
says so in its own docstring: guessing a deep path produced two wrong verdicts
earlier in this project. So this walks the ArcGIS REST catalogue from documented
roots and looks for a shoreline layer, rather than hardcoding a path this
session cannot reach to verify. What it found, and what it tried and failed, go
into the step summary either way.

WHAT THE ANSWER IS AND IS NOT. A surveyed shoreline is an independent
measurement of where the land meets the sea, and it settles the ORIENTATION
question the chords are being used for. It is not the same line as the traced
waterline: NOAA's shoreline products are referenced to a tidal datum (MHW,
typically) while a Google Earth trace follows whatever the water was doing when
the image was taken. Expect a systematic cross-shore offset between the two and
do not read it as error. Orientation is what is being checked here, and
orientation is what survives a translation.

It is also NOT the normal that refraction will want. That one belongs to the
depth contours at breaking depth, which is a bathymetry question and a
different job.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import re
import zlib
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from .common import DEFAULT_DATA_DIR, ISO, utcnow, write_step_summary

USER_AGENT = "nado-waves/1.0 (surf forecast research; contact via repository)"

#: Catalogue roots, not layer paths. Each is an ArcGIS REST services directory
#: that is expected to respond; what lives inside it is discovered.
CATALOG_ROOTS = (
    "https://gis.charttools.noaa.gov/arcgis/rest/services",
    "https://coast.noaa.gov/arcgis/rest/services",
    "https://chs.coast.noaa.gov/arcgis/rest/services",
    "https://mapservices.weather.noaa.gov/static/rest/services",
)

#: Services the first two probe runs turned up that are worth opening whatever
#: their NAME matches, because NOAA's ENC chart data carries the coastline as a
#: feature class (COALNE) inside a service called something else entirely.
#: These are catalogue entries observed on 2026-09-20, not guesses.
KNOWN_SERVICES = (
    "https://gis.charttools.noaa.gov/arcgis/rest/services/MCS/ENCOnline/MapServer",
    "https://gis.charttools.noaa.gov/arcgis/rest/services/MCS/NOAAChartDisplay/MapServer",
    "https://gis.charttools.noaa.gov/arcgis/rest/services/MarineChart_Services/NOAACharts/MapServer",
)

#: Folders worth opening ahead of the rest even though their names say nothing
#: about shorelines. NGS is the National Geodetic Survey -- the office that
#: publishes the US shoreline -- and `encdirect` serves ENC chart data, which
#: carries the coastline as a feature class. charttools has 22 folders and the
#: budget was 12 sorted alphabetically, so `NGS/` was never opened.
PRIORITY_FOLDERS = re.compile(r"ngs|geodet|encdirect|hydrographic|nav", re.I)

#: How many folders to open per root. A discovery pass, not a crawl -- but 12
#: was under the 22 charttools carries, which is how the one folder that
#: mattered got cut.
FOLDER_BUDGET = 28

#: Digital Coast serves its bulk products as files under /htdata/, not as
#: ArcGIS services. Measured 2026-09-20: coast.noaa.gov's REST catalogue
#: carries 374 entries across 16 folders and NOT ONE matches a shoreline
#: pattern, so if CUSP is reachable at all it is a download and not a service.
#:
#: These are directory roots, listed and reported -- not a guessed path to a
#: file. The probe says what it found; it does not assume a filename.
HTDATA_ROOTS = (
    "https://coast.noaa.gov/htdata/Shoreline/",
    "https://coast.noaa.gov/htdata/",
)

#: An href in an Apache/IIS directory index. Anything else on the page is
#: chrome.
HREF = re.compile(r'href="([^"?][^"]*)"', re.I)

#: How many entries to print per root. One catalogue with four thousand
#: services buried the other three in the second run's summary.
LISTING_CAP = 60

#: A service or layer worth opening. Deliberately broad — the point is to see
#: what is there, and the summary lists everything matched so a human can judge.
WANTED = re.compile(r"shorelin|cusp|coalne|coast.?line|\bmhw\b|coastal[_ ]?survey", re.I)

#: Coronado's digitised stretch runs 32.6737 to 32.6866 N, -117.1976 to
#: -117.1724 E. Padded by roughly 2 km so a fit at the 2 km scale has vertices
#: beyond both ends of the beach rather than running out of line at the edges.
BBOX = (-117.2200, 32.6550, -117.1500, 32.7060)   # xmin, ymin, xmax, ymax

STORE_NAME = "noaa_shoreline_coronado.csv"

FIELDS = ["part", "seq", "lat", "lon", "source_layer", "fetched_utc"]

TIMEOUT = 45.0

#: Denial is policy, not throttling, and must be reported rather than retried.
DENIAL_NOTE = (
    "403 at CONNECT is the egress policy refusing the host, not NOAA refusing "
    "the request. Run this job on Actions; do not route around it (BRIEFING §8)."
)


class ShorelineError(RuntimeError):
    pass


@dataclass
class Attempt:
    url: str
    ok: bool = False
    denied: bool = False
    note: str = ""
    #: What the root actually contained. A probe that reports only its own
    #: MATCHES says nothing at all when there are none — which is what the
    #: first run of this did, and it is the same shape as the staleness alert
    #: that watched for the failure it expected (BRIEFING §8). The listing is
    #: the finding when the filter comes back empty.
    listing: list[str] = field(default_factory=list)
    #: First bytes of a body that would not parse, so "not JSON" can be told
    #: from "an HTML login page" without another run.
    sample: str = ""


@dataclass
class Result:
    attempts: list[Attempt] = field(default_factory=list)
    candidates: list[str] = field(default_factory=list)
    layer: str = ""
    parts: int = 0
    vertices: int = 0
    stored: Path | None = None

    @property
    def ok(self) -> bool:
        return self.vertices > 0

    @property
    def denied(self) -> bool:
        return bool(self.attempts) and all(a.denied for a in self.attempts)


class NotJSON(ShorelineError):
    """The body parsed as something, just not JSON. Carries what it looked like."""

    def __init__(self, message: str, sample: str = ""):
        super().__init__(message)
        self.sample = sample


#: gzip's magic number. coast.noaa.gov serves compressed bodies whether or not
#: they were asked for, and urllib does not decompress on its own -- the first
#: three probe runs read that as "not JSON" and wrote the host off. It is the
#: Digital Coast host, the likeliest home of a surveyed shoreline, so that
#: mistake cost the whole exercise. Caught only because the summary started
#: sampling bodies it could not parse.
GZIP_MAGIC = b"\x1f\x8b"


def decompress(payload: bytes, encoding: str = "") -> bytes:
    """Undo a content encoding, by header or by magic number.

    By BOTH, because the header is what the server says and the magic number is
    what it did, and coast.noaa.gov is an example of the two disagreeing.
    """

    encoding = (encoding or "").lower()
    if encoding == "gzip" or payload[:2] == GZIP_MAGIC:
        try:
            return gzip.GzipFile(fileobj=io.BytesIO(payload)).read()
        except (OSError, EOFError):
            # EOFError is NOT an OSError, and a truncated body raises it. A
            # crash here would turn "the response was cut short" into a dead
            # host, which is the distinction this whole module exists to make.
            return payload
    if encoding == "deflate":
        for wbits in (zlib.MAX_WBITS, -zlib.MAX_WBITS):
            try:
                return zlib.decompress(payload, wbits)
            except zlib.error:
                continue
    return payload


def fetch_json(url: str, *, timeout: float = TIMEOUT) -> dict:
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate",
    })
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = decompress(response.read(),
                             response.headers.get("Content-Encoding", ""))
    text = payload.decode("utf-8", errors="replace")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise NotJSON(f"not JSON: {exc}", sample=" ".join(text[:180].split())) from None
    # ArcGIS reports failure inside a 200 body, the same shape CO-OPS does and
    # the same shape BRIEFING §8 lists first. Check the error before the data.
    if isinstance(data, dict) and data.get("error"):
        message = data["error"].get("message", "") if isinstance(data["error"], dict) else str(data["error"])
        raise ShorelineError(f"ArcGIS error in a 200 body: {message[:200]}")
    return data


def is_denial(exc: Exception) -> bool:
    """Is this the EGRESS POLICY refusing, or the origin server refusing?

    The same 403 means opposite things depending on where this runs. From a
    Claude session it is the proxy refusing CONNECT and the host may be fine;
    from an Actions runner there is no such proxy, so a 403 is NOAA itself
    saying no — measured 2026-09-20, `coast.noaa.gov/htdata/` answers 403 to a
    runner because directory listing is switched off.

    Calling the second one a denial would file "this directory is not
    browsable" under "we could not reach this host", which is the same class
    of fault as reading NCEP's 404 as "no cycle today" (CLAUDE.md). An
    HTTPError carries a real status from a real response, so it is never an
    egress denial; only a refused tunnel is.
    """

    if isinstance(exc, urllib.error.HTTPError):
        return False
    text = f"{exc.__class__.__name__}: {exc}"
    return "403" in text or "CONNECT" in text or "URLError" in text


def discover(roots: tuple[str, ...] = CATALOG_ROOTS) -> Result:
    """Walk each catalogue root one level and collect services worth trying."""

    result = Result()
    for root in roots:
        attempt = Attempt(url=root)
        try:
            catalog = fetch_json(f"{root}?f=json")
        except Exception as exc:  # noqa: BLE001 — classified, not swallowed
            attempt.denied = is_denial(exc)
            attempt.note = f"{exc.__class__.__name__}: {exc}"[:160]
            attempt.sample = getattr(exc, "sample", "")
            result.attempts.append(attempt)
            continue

        attempt.ok = True
        found = 0
        for service in catalog.get("services", []) or []:
            name = str(service.get("name", ""))
            kind = str(service.get("type", ""))
            attempt.listing.append(f"{name} ({kind})")
            if kind not in ("MapServer", "FeatureServer"):
                continue
            if not WANTED.search(name):
                continue
            result.candidates.append(f"{root}/{name.split('/')[-1]}/{kind}")
            found += 1

        # EVERY folder, not only the ones whose NAME matches. A shoreline layer
        # can live in a folder called anything, and the first run of this probe
        # filtered folders by name and reported "0 candidates" from a catalogue
        # it had barely opened.
        folders = [str(f) for f in (catalog.get("folders", []) or [])]
        attempt.listing += [f"{f}/ (folder)" for f in folders]
        ordered = sorted(folders, key=lambda f: (
            0 if WANTED.search(f) else 1 if PRIORITY_FOLDERS.search(f) else 2, f))
        for folder in ordered[:FOLDER_BUDGET]:
            try:
                inner = fetch_json(f"{root}/{folder}?f=json")
            except Exception:  # noqa: BLE001 — a dead folder is not fatal
                continue
            for service in inner.get("services", []) or []:
                kind = str(service.get("type", ""))
                name = str(service.get("name", "")).split("/")[-1]
                if kind not in ("MapServer", "FeatureServer"):
                    continue
                attempt.listing.append(f"{folder}/{name} ({kind})")
                if not (WANTED.search(name) or WANTED.search(folder)
                        or PRIORITY_FOLDERS.search(folder)):
                    continue
                result.candidates.append(f"{root}/{folder}/{name}/{kind}")
                found += 1
        attempt.note = (f"{found} candidate service(s) from "
                        f"{len(attempt.listing)} entries seen")
        result.attempts.append(attempt)
    return result


def fetch_text(url: str, *, timeout: float = TIMEOUT) -> str:
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
    })
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = decompress(response.read(),
                             response.headers.get("Content-Encoding", ""))
    return payload.decode("utf-8", errors="replace")


def list_directory(url: str) -> list[str]:
    """Entries in a served directory index, parent links dropped.

    HTML, not JSON, because this half of Digital Coast is a file tree. It is
    parsed only well enough to say WHAT IS THERE — nothing downstream depends
    on the parse, because the point is to put the listing in front of a human
    rather than to pick a file automatically.
    """

    names = []
    for href in HREF.findall(fetch_text(url)):
        if href.startswith(("/", "#", "http", "..", "?")):
            continue
        if href not in names:
            names.append(href)
    return names


def probe_htdata(roots: tuple[str, ...] = HTDATA_ROOTS) -> list[Attempt]:
    """Report what the file tree holds. Stores nothing, assumes nothing."""

    out = []
    for root in roots:
        attempt = Attempt(url=root)
        try:
            names = list_directory(root)
        except Exception as exc:  # noqa: BLE001 — classified, not swallowed
            attempt.denied = is_denial(exc)
            attempt.note = f"{exc.__class__.__name__}: {exc}"[:160]
            attempt.sample = getattr(exc, "sample", "")
            out.append(attempt)
            continue
        attempt.ok = True
        attempt.listing = names
        hits = [n for n in names if WANTED.search(n)]
        attempt.note = (f"{len(names)} entr(ies)"
                        + (f", {len(hits)} matching: " + ", ".join(hits[:6]) if hits else ""))
        out.append(attempt)
    return out


def line_layers(service_url: str) -> list[str]:
    """Polyline layers in a service, the shoreline-named ones first.

    Matching on LAYER names and not only service names is what the second probe
    run was missing: NOAA's ENC chart services are called things like
    `NOAACharts`, and the coastline lives inside them as a feature class named
    COALNE. Filtering at the service level never opened them.
    """

    try:
        meta = fetch_json(f"{service_url}?f=json")
    except Exception:  # noqa: BLE001 — try the next service
        return []
    named, other = [], []
    for layer in meta.get("layers", []) or []:
        geometry = str(layer.get("geometryType", ""))
        if geometry and "Polyline" not in geometry:
            continue
        url = f"{service_url}/{layer.get('id')}"
        (named if WANTED.search(str(layer.get("name", ""))) else other).append(url)
    # A chart service has dozens of layers and querying every one of them is a
    # crawl, not a probe. The named ones are the point; a handful of others are
    # kept in case the naming differs.
    return named + other[:8]


def query_url(layer_url: str, bbox: tuple[float, float, float, float]) -> str:
    params = {
        "where": "1=1",
        "geometry": ",".join(f"{v}" for v in bbox),
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "outSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "returnGeometry": "true",
        "outFields": "*",
        "f": "json",
    }
    return f"{layer_url}/query?{urllib.parse.urlencode(params)}"


def parse_paths(payload: dict) -> list[list[tuple[float, float]]]:
    """Polyline paths as (lat, lon) lists. Empty when the layer had none.

    ArcGIS gives x,y — longitude first. Flipping that silently would put
    Coronado in the Indian Ocean, so it is done once, here, on the way in.
    """

    parts: list[list[tuple[float, float]]] = []
    for feature in payload.get("features", []) or []:
        geometry = feature.get("geometry") or {}
        for path in geometry.get("paths", []) or []:
            points = []
            for point in path:
                if not isinstance(point, (list, tuple)) or len(point) < 2:
                    continue
                lon, lat = float(point[0]), float(point[1])
                points.append((lat, lon))
            if len(points) >= 2:
                parts.append(points)
    return parts


def in_bbox(lat: float, lon: float, bbox: tuple[float, float, float, float]) -> bool:
    xmin, ymin, xmax, ymax = bbox
    return xmin <= lon <= xmax and ymin <= lat <= ymax


def store(parts: list[list[tuple[float, float]]], layer: str, data_dir: Path) -> Path:
    """Write the vertices. Overwrites: a shoreline is a survey, not a series.

    Unlike the tide and buoy archives there is nothing here that a later fetch
    would destroy — this is one published survey, not a stream of observations
    whose earlier values are the record. The git history is the version log.
    """

    path = Path(data_dir) / "shoreline" / STORE_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = utcnow().strftime(ISO)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        for index, part in enumerate(parts):
            for seq, (lat, lon) in enumerate(part):
                writer.writerow({
                    "part": index, "seq": seq,
                    "lat": f"{lat:.7f}", "lon": f"{lon:.7f}",
                    "source_layer": layer, "fetched_utc": stamp,
                })
    return path


def collect(
    data_dir: Path = DEFAULT_DATA_DIR,
    *,
    bbox: tuple[float, float, float, float] = BBOX,
    probe_only: bool = False,
) -> Result:
    result = discover()
    # The file tree is discovery only and never short-circuits the service
    # walk: it reports alongside, so one run answers both questions.
    result.attempts += probe_htdata()
    # Observed services go first: they are known to exist and known to be the
    # kind of thing that carries a coastline, whatever they are called.
    result.candidates = list(KNOWN_SERVICES) + result.candidates

    for service in result.candidates:
        for layer in line_layers(service):
            try:
                payload = fetch_json(query_url(layer, bbox))
            except Exception as exc:  # noqa: BLE001 — try the next layer
                result.attempts.append(
                    Attempt(url=layer, denied=is_denial(exc),
                            note=f"{exc.__class__.__name__}: {exc}"[:160]))
                continue
            parts = [
                [p for p in path if in_bbox(*p, bbox)]
                for path in parse_paths(payload)
            ]
            parts = [p for p in parts if len(p) >= 2]
            if not parts:
                result.attempts.append(Attempt(url=layer, ok=True, note="no vertices in bbox"))
                continue
            result.layer = layer
            result.parts = len(parts)
            result.vertices = sum(len(p) for p in parts)
            result.attempts.append(
                Attempt(url=layer, ok=True,
                        note=f"{result.vertices} vertices in {result.parts} part(s)"))
            if not probe_only:
                result.stored = store(parts, layer, data_dir)
            return result
    return result


def format_summary(result: Result) -> str:
    lines = ["### Shoreline — NOAA surveyed vector near Coronado", ""]
    lines += ["| tried | ok | note |", "|---|---|---|"]
    for attempt in result.attempts:
        state = "denied" if attempt.denied else ("yes" if attempt.ok else "no")
        note = attempt.note
        if attempt.sample:
            note += f" — body began: `{attempt.sample[:120]}`"
        lines.append(f"| `{attempt.url}` | {state} | {note} |")
    lines.append("")

    # What was actually there, matched or not. Without this a zero-candidate
    # run says only "I found nothing", which is not a finding about NOAA.
    for attempt in result.attempts:
        if not attempt.listing:
            continue
        lines.append(f"<details><summary>{len(attempt.listing)} entries at "
                     f"<code>{attempt.url}</code></summary>\n")
        lines += [f"- `{entry}`" for entry in attempt.listing[:LISTING_CAP]]
        if len(attempt.listing) > LISTING_CAP:
            lines.append(f"- …and {len(attempt.listing) - LISTING_CAP} more")
        lines.append("\n</details>\n")
    if result.candidates:
        lines.append(f"**{len(result.candidates)} candidate service(s):**")
        lines += [f"- `{c}`" for c in result.candidates]
        lines.append("")
    if result.ok:
        lines.append(
            f"**Stored {result.vertices} vertices** in {result.parts} part(s) from "
            f"`{result.layer}` → `{result.stored}`."
        )
        lines.append("")
        lines.append(
            "Run `python -m forecast.shorenormal` to compare these against the "
            "hand-digitised chords in `forecast/spots.json`."
        )
    elif result.denied:
        lines.append(f"**Denied at CONNECT.** {DENIAL_NOTE}")
    else:
        lines.append(
            "**No shoreline layer found.** Nothing was stored, and nothing is "
            "inferred from the miss — the chords keep their existing "
            "`shoreline_verified` flags. The table above is what to read next."
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--probe", action="store_true",
                        help="discover and report, store nothing")
    args = parser.parse_args(argv)

    result = collect(args.data_dir, probe_only=args.probe)
    summary = format_summary(result)
    print(summary)
    write_step_summary(summary)

    if result.denied:
        return 2
    return 0 if (result.ok or args.probe) else 1


if __name__ == "__main__":
    sys.exit(main())
