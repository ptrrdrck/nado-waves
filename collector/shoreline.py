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

#: Named fetch boxes. A region is a bbox AND a filename suffix, because the
#: two must not drift apart: the stored Coronado files were clipped on all four
#: edges by their own envelope, and only the suffix in their names says which
#: envelope that was.
#:
#: - `coronado` — the beach. The digitised stretch runs 32.6737 to 32.6866 N,
#:   -117.1976 to -117.1724 E, padded by roughly 2 km so a fit at the 2 km
#:   scale has vertices beyond both ends rather than running out of line.
#: - `baja` — the coast south of the border, from the Tijuana river mouth to
#:   Punta Banda. It exists to find ONE number: the bearing of the seaward-most
#:   point of that coast as seen from Coronado, which is the southern edge of
#:   the swell window. Measured from public landmark positions, the whole Baja
#:   coast out to Punta Eugenia (573 km) sits inside 152–165° from Coronado —
#:   seen almost exactly edge-on — so the edge is a tangent, and a tangent is
#:   decided by whichever vertex the chart happened to place furthest seaward.
#:   Same shape as the Point Loma tip, and the same leverage.
#: - `point_loma` — the peninsula west of the harbour channel, tip to Ocean
#:   Beach. It exists to find the one vertex that carries the WEST edge of
#:   every Coronado window: the seaward-most point of the tip as seen from each
#:   break. Until this region existed that vertex was a Google Earth trace, and
#:   it is the highest-leverage coordinate in the repository (~1 degree per
#:   100 m). Neither other box reaches it: `coronado` stops at -117.22 and
#:   `baja` at 32.66, and the tip sits at about 32.665, -117.243. The floor
#:   sits 2.5 km of open water south of the tip, so the tip is inside the
#:   envelope on every side and cannot be the box's own corner. The east edge
#:   stops at -117.226 so the far side of the channel -- North Island -- stays
#:   out of the file rather than being filtered out downstream.
REGIONS: dict[str, tuple[float, float, float, float]] = {
    "coronado": (-117.2200, 32.6550, -117.1500, 32.7060),
    "baja": (-117.4000, 31.6000, -116.5500, 32.6600),
    "point_loma": (-117.3000, 32.6400, -117.2260, 32.7500),
}

#: The default region, kept as a module constant because every existing caller
#: and test passes the Coronado box by this name.
BBOX = REGIONS["coronado"]   # xmin, ymin, xmax, ymax

#: ENC usage bands, coarse to fine. This is a DOCUMENTED quality ordering and
#: the first version of this collector ignored it entirely: it took whichever
#: coastline layer answered first and never asked whether a better one existed.
#: Measured 2026-09-20 (BRIEFING §22), that cost real resolution —
#: `enc_harbour/84` carries 97 features in the Coronado box where
#: `enc_approach/88` carries 61, and §21 fitted the 61.
SCALE_RANK = {
    "enc_berthing": 6,
    "enc_harbour": 5,
    "enc_approach": 4,
    "enc_coastal": 3,
    "enc_general": 2,
    "enc_overview": 1,
}


def scale_of(url: str) -> int:
    """Finer is higher. 0 for anything not on the band list."""

    for name, rank in SCALE_RANK.items():
        if name in url:
            return rank
    return 0


def store_name(layer_url: str, region: str = "coronado") -> str:
    """One file per SOURCE and REGION, so neither can clobber the other.

    Keeping both sources is the point: two charts of the same coast at two
    scales is the only cross-check available here, and a single
    `noaa_shoreline.csv` made that impossible — the finer fetch would simply
    overwrite the coarser one and the disagreement would never be visible.

    The region is in the name for a different reason. A stored extract is
    clipped by its own query envelope on all four edges, and nothing inside the
    file records which envelope that was: reading `enc_harbour_84` and finding
    it stops 2.8 km south of the beach says nothing about what the chart
    carries there. The suffix is the only place that distinction lives.
    """

    parts = [p for p in layer_url.rstrip("/").split("/") if p]
    service = next((p for p in parts if p in SCALE_RANK), "enc")
    layer_id = parts[-1] if parts[-1].isdigit() else "x"
    return f"{service}_{layer_id}_{region}.csv"


#: How many coastline sources to keep. More than one so they can be compared;
#: not all of them, because the coarse bands add nothing but bytes.
SOURCE_BUDGET = 3

#: `cell` is the ENC chart cell a vertex came from, blank when the service
#: names none. It sits before `fetched_utc` rather than at the end because
#: these files are rewritten whole on every fetch — unlike the tide and buoy
#: archives, where appending a column to an existing CSV would misalign it.
FIELDS = ["part", "seq", "lat", "lon", "source_layer", "cell", "fetched_utc"]

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
    #: The ENC cells the stored vertices came from, and every attribute name
    #: the service returned. A usage band is a mosaic, not a chart, so
    #: "digitised from the approach band" names the drawer; the cells name the
    #: charts. The key list is here so an empty `cells` reads as "the service
    #: does not publish one" rather than as a silent miss.
    cells: list[str] = field(default_factory=list)
    attribute_keys: list[str] = field(default_factory=list)
    #: Which named box this run asked for, and the box itself. A stored extract
    #: is clipped by its envelope on every edge, so the envelope is part of the
    #: finding and belongs in the summary beside the vertex count.
    region: str = "coronado"
    bbox: tuple[float, float, float, float] = BBOX
    attempts: list[Attempt] = field(default_factory=list)
    candidates: list[str] = field(default_factory=list)
    #: Layers that were still returning `exceededTransferLimit` when the page
    #: budget ran out. A non-empty list means the stored coastline is INCOMPLETE
    #: and no tangent bearing may be read off it.
    truncated: list[str] = field(default_factory=list)
    layer: str = ""
    parts: int = 0
    vertices: int = 0
    stored: Path | None = None
    #: Every file written this run, one per source chart band.
    sources: list[str] = field(default_factory=list)

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


def query_url(
    layer_url: str,
    bbox: tuple[float, float, float, float],
    offset: int = 0,
) -> str:
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
    if offset:
        params["resultOffset"] = str(offset)
    return f"{layer_url}/query?{urllib.parse.urlencode(params)}"


#: How many pages of features to pull from one layer before giving up. At the
#: server's usual 1000-2000 features a page this is far more coast than any
#: region here needs; the cap exists so a server that ignores `resultOffset`
#: loops a bounded number of times rather than forever.
PAGE_BUDGET = 12


def fetch_paths(
    layer_url: str,
    bbox: tuple[float, float, float, float],
    *,
    fetch=None,
) -> tuple[list[tuple[list[tuple[float, float]], str]], bool, list[str]]:
    """Every feature in the box, following `exceededTransferLimit`.

    Returns the paths and whether the layer was STILL truncated when the page
    budget ran out, because those are two different answers and a caller that
    cannot tell them apart is the fault BRIEFING §8 keeps naming: the Coronado
    box returned 97 features and never came near a page limit, so nothing here
    had ever met one. A 130 km box will, and a silently truncated coastline
    would drop exactly the seaward-most vertex this fetch exists to find.
    """

    fetch = fetch or fetch_json
    paths: list[tuple[list[tuple[float, float]], str]] = []
    keys: list[str] = []
    offset = 0
    for _ in range(PAGE_BUDGET):
        payload = fetch(query_url(layer_url, bbox, offset))
        page = parse_features(payload)
        paths += page
        keys = keys or attribute_keys(payload)
        if not payload.get("exceededTransferLimit") or not page:
            return paths, False, keys
        offset += len(payload.get("features") or page)
    return paths, True, keys


#: Attribute names that identify the ENC CELL a feature came from, best
#: first. A usage band is not a chart: `enc_approach/88` is a mosaic of many
#: cells, and "digitised from the approach band" names the drawer rather than
#: the chart. Tried case-insensitively; the summary lists every attribute key
#: the service actually returned, so a miss here is visible in one run rather
#: than inferred from a blank column.
CELL_FIELDS = ("DSNM", "CELLNAME", "CELL_NAME", "CELL", "SORIND", "LNAM")


def cell_of(attributes: dict) -> str:
    """The ENC cell id in a feature's attributes, or "" if none is named."""

    lowered = {str(k).lower(): v for k, v in (attributes or {}).items()}
    for field in CELL_FIELDS:
        value = lowered.get(field.lower())
        if value not in (None, "", "null"):
            text = str(value).strip()
            # S-57 SORIND is a four-field citation — agency, indication,
            # method, SOURCE ID — and it is the last field that names the
            # chart. Reading the second instead returns "US" for every
            # feature on the US coast, which looks like a populated column.
            if field == "SORIND" and "," in text:
                bits = [b.strip() for b in text.split(",") if b.strip()]
                return bits[-1] if bits else text
            return text
    return ""


def attribute_keys(payload: dict) -> list[str]:
    """Every attribute name the service returned, for the summary."""

    keys: dict[str, None] = {}
    for feature in payload.get("features", []) or []:
        for key in (feature.get("attributes") or {}):
            keys[str(key)] = None
    return sorted(keys)


def parse_features(payload: dict) -> list[tuple[list[tuple[float, float]], str]]:
    """Polyline paths as (points, cell) pairs. Empty when the layer had none.

    ArcGIS gives x,y — longitude first. Flipping that silently would put
    Coronado in the Indian Ocean, so it is done once, here, on the way in.
    """

    parts: list[tuple[list[tuple[float, float]], str]] = []
    for feature in payload.get("features", []) or []:
        geometry = feature.get("geometry") or {}
        cell = cell_of(feature.get("attributes") or {})
        for path in geometry.get("paths", []) or []:
            points = []
            for point in path:
                if not isinstance(point, (list, tuple)) or len(point) < 2:
                    continue
                lon, lat = float(point[0]), float(point[1])
                points.append((lat, lon))
            if len(points) >= 2:
                parts.append((points, cell))
    return parts


def parse_paths(payload: dict) -> list[list[tuple[float, float]]]:
    """The geometry alone. Kept because most callers only want the points."""

    return [points for points, _ in parse_features(payload)]


def in_bbox(lat: float, lon: float, bbox: tuple[float, float, float, float]) -> bool:
    xmin, ymin, xmax, ymax = bbox
    return xmin <= lon <= xmax and ymin <= lat <= ymax


def store(
    parts: list[list[tuple[float, float]]] | list[tuple[list[tuple[float, float]], str]],
    layer: str,
    data_dir: Path,
    region: str = "coronado",
) -> Path:
    """Write the vertices, to a file named for the SOURCE.

    Overwrites its own file: a shoreline is a survey, not a series, and unlike
    the tide and buoy archives nothing here is destroyed by a later fetch of
    the same layer. The git history is the version log. It does NOT overwrite
    another source's file, which the single fixed filename used to do.
    """

    path = Path(data_dir) / "shoreline" / store_name(layer, region)
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = utcnow().strftime(ISO)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        for index, part in enumerate(parts):
            # A bare list of points is still accepted: the cell is an addition
            # to what a part carries, not a change of what a part IS.
            points, cell = part if isinstance(part, tuple) else (part, "")
            for seq, (lat, lon) in enumerate(points):
                writer.writerow({
                    "part": index, "seq": seq,
                    "lat": f"{lat:.7f}", "lon": f"{lon:.7f}",
                    "source_layer": layer, "cell": cell, "fetched_utc": stamp,
                })
    return path


def collect(
    data_dir: Path = DEFAULT_DATA_DIR,
    *,
    region: str = "coronado",
    bbox: tuple[float, float, float, float] | None = None,
    probe_only: bool = False,
) -> Result:
    bbox = bbox if bbox is not None else REGIONS[region]
    result = Result(region=region, bbox=bbox)
    discovered = discover()
    result.attempts = discovered.attempts
    result.candidates = discovered.candidates
    # The file tree is discovery only and never short-circuits the service
    # walk: it reports alongside, so one run answers both questions.
    result.attempts += probe_htdata()
    # Observed services go first: they are known to exist and known to be the
    # kind of thing that carries a coastline, whatever they are called.
    result.candidates = list(KNOWN_SERVICES) + result.candidates
    # Finest chart band first. Without this the order is whatever the
    # catalogue walk happened to produce, which is how §21 ended up fitting
    # normals to the approach chart while a finer one sat unused.
    result.candidates.sort(key=lambda url: -scale_of(url))

    kept = 0
    for service in result.candidates:
        if kept >= SOURCE_BUDGET:
            break
        for layer in line_layers(service):
            try:
                raw, truncated, keys = fetch_paths(layer, bbox)
            except Exception as exc:  # noqa: BLE001 — try the next layer
                result.attempts.append(
                    Attempt(url=layer, denied=is_denial(exc),
                            note=f"{exc.__class__.__name__}: {exc}"[:160]))
                continue
            parts = [
                ([p for p in path if in_bbox(*p, bbox)], cell)
                for path, cell in raw
            ]
            parts = [(p, cell) for p, cell in parts if len(p) >= 2]
            result.attribute_keys = result.attribute_keys or keys
            for _, cell in parts:
                if cell and cell not in result.cells:
                    result.cells.append(cell)
            if not parts:
                result.attempts.append(Attempt(url=layer, ok=True, note="no vertices in bbox"))
                continue
            vertices = sum(len(p) for p, _ in parts)
            # First one found stays the headline, so the summary keeps reading
            # the way it did; the rest are stored beside it for comparison.
            if not result.layer:
                result.layer = layer
                result.parts = len(parts)
                result.vertices = vertices
            note = f"{vertices} vertices in {len(parts)} part(s)"
            if truncated:
                note += (f" — STILL TRUNCATED after {PAGE_BUDGET} pages; "
                         "the box is too big or the server ignores resultOffset")
                result.truncated.append(layer)
            result.attempts.append(Attempt(url=layer, ok=True, note=note))
            if not probe_only:
                path = store(parts, layer, data_dir, region)
                result.stored = result.stored or path
                result.sources.append(str(path))
            kept += 1
            break       # one coastline layer per service is enough
    return result


def format_summary(result: Result) -> str:
    xmin, ymin, xmax, ymax = result.bbox
    lines = [
        f"### Shoreline — NOAA chart vector, region `{result.region}`",
        "",
        f"Query envelope `{xmin} {ymin} {xmax} {ymax}`. Everything stored is "
        "clipped to it on all four edges, so a file that stops short of "
        "somewhere says nothing about what the chart carries there.",
        "",
    ]
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
    if result.truncated:
        lines.append(
            "**Incomplete.** These layers were still truncated when the page "
            "budget ran out, so the stored coastline is missing features and "
            "no edge may be read off it:"
        )
        lines += [f"- `{layer}`" for layer in result.truncated]
        lines.append("")
    if result.cells:
        lines.append(
            f"**ENC cells** ({len(result.cells)}): "
            + ", ".join(f"`{c}`" for c in sorted(result.cells))
        )
        lines.append("")
        lines.append(
            "These are the charts. The usage band is the drawer they sit in, "
            "so a provenance line should name these and not `enc_approach/88`."
        )
        lines.append("")
    elif result.attribute_keys:
        lines.append(
            "**No ENC cell attribute.** The service returned these keys and "
            "none of them is a cell id, so the provenance can only name the "
            "usage band: "
            + ", ".join(f"`{k}`" for k in result.attribute_keys[:40])
        )
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
    parser.add_argument("--region", choices=sorted(REGIONS), default="coronado",
                        help="which named query envelope to fetch")
    args = parser.parse_args(argv)

    result = collect(args.data_dir, region=args.region, probe_only=args.probe)
    summary = format_summary(result)
    print(summary)
    write_step_summary(summary)

    if result.denied:
        return 2
    return 0 if (result.ok or args.probe) else 1


if __name__ == "__main__":
    sys.exit(main())
