"""What does CSULB Shark Lab's ERDDAP serve, and is any of it at Coronado?

    python -m collector.probe_sharklab

The owner's question (2026-10-20): Coronado's two "shark buoys" -- receiver
hubs owned by the city and kept by its lifeguards, one at Center and one about
halfway from Center to South, just south of the jetty -- are part of the Shark
Lab's array, and its ERDDAP may carry their detections, their hub status and
possibly water temperature. Nothing here has been seen yet: the host was
denied at CONNECT from the session that asked (BRIEFING section 8), so this is
an Actions job, as `probe_spectra` was.

It answers three things and builds nothing on them:

- which datasets the server lists, with their bounds and time range;
- which stations in each sit near Coronado's breaks, by distance to each
  break's position in spots.json -- never a typed coordinate, and the hub
  positions are the SERVER's, reported, not assumed to be the owner's two;
- how fresh the newest row near Coronado is, read from the parsed time column,
  never from an HTTP 200 (BRIEFING section 8, fault one).

Every response is read in full, its byte count reported, and its header and
first rows printed verbatim beside the parse. Exits 2 on a denial, 1 when
nothing fresh was found near Coronado, 0 when something was.
"""

from __future__ import annotations

import argparse
import csv
import io
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from forecast import geometry
from forecast.swell import great_circle_km

from .common import utcnow, write_step_summary
from .ndbc import USER_AGENT
from .probe_mop import DENIAL_NOTE

#: The public server its maintainer gave (2026-10-22): plain http, not https.
#: His email spelled it "csulbshsrklab", which does not resolve (run 3). erddap-02.thesharklab.org, the address first given, resolves but
#: accepts no connection from GitHub's runners (run 2, 2026-10-20).
BASE = "http://erddap-public.csulbsharklab.org/erddap"

#: Coronado's three breaks -- the only spots with charted positions.
CORONADO = ("coronado_north", "coronado_center", "coronado_south")

#: A station this close to a break is reported as "at Coronado". Center to
#: South is ~1.5 km, so a hub halfway between sits well inside it.
NEAR_KM = 3.0

#: Looking back this far for the newest rows near Coronado.
RECENT_DAYS = 30

#: The same, for a time kept as text, which ERDDAP cannot narrow with
#: `now-`: every hub's detections in it are read, so it is kept short.
RECENT_TEXT_DAYS = 2

#: A text column with at most this many distinct values in the window is
#: tallied (detection types, sensor types, animals).
TALLY_MAX = 20

#: Older than this and the newest row is present but not live.
STALE_HOURS = 48.0

#: Rows printed verbatim per query; the parse still reads all of them.
SHOWN_ROWS = 8

#: Positions are fetched only inside this box around the breaks, degrees: the
#: detections dataset carries every GPS fix of every receiver, and run 4
#: listed them all (54 MB, past the step summary's 1 MB).
BOX_DEG = 0.2

#: Positions are grouped to ~100 m, so a hub's GPS jitter reads as one place.
CLUSTER_DECIMALS = 3
MAX_CLUSTERS = 40

#: The step summary refuses more than 1 MB.
SUMMARY_LIMIT = 900_000

#: Names the server's datasets use, found on run 4 (`Lng` in the temperatures).
LAT_NAMES = ("latitude", "lat", "Lat", "Latitude")
LON_NAMES = ("longitude", "lon", "Lng", "lng", "Lon", "Longitude", "long")
GROUP_NAMES = ("hub_serial", "serial_number", "serial", "Station", "station", "receiver", "device")

ALL_DATASETS_COLUMNS = (
    "datasetID", "title", "institution", "cdm_data_type", "dataStructure",
    "minLongitude", "maxLongitude", "minLatitude", "maxLatitude",
    "minTime", "maxTime",
)


@dataclass
class Fetched:
    url: str
    ok: bool = False
    denied: bool = False
    empty: bool = False
    timed_out: bool = False
    status: int | None = None
    bytes_read: int = 0
    header: list[str] = field(default_factory=list)
    units: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    raw_head: str = ""
    raw_tail: str = ""
    error: str = ""


def fetch_csv(path: str, query: str = "", *, timeout: float = 120.0) -> Fetched:
    """One ERDDAP .csv response, read in full and parsed. Never retried: a
    denial does not yield to a second try (BRIEFING section 8)."""

    url = f"{BASE}/{path}" + (f"?{query}" if query else "")
    result = Fetched(url=url)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result.status = response.status
            payload = response.read()
    except urllib.error.HTTPError as exc:
        result.status = exc.code
        body = exc.read().decode("utf-8", errors="replace")
        result.error = f"HTTP {exc.code} {exc.reason}: {body.strip()[:300]}"
        # ERDDAP answers a query that matches nothing with a 404 whose body
        # says so; that is an empty result, not a missing dataset.
        result.empty = exc.code == 404 and "matching results" in body
        result.denied = exc.code == 403
        return result
    except (urllib.error.URLError, TimeoutError) as exc:
        result.error = f"{exc.__class__.__name__}: {exc}"
        # Only a proxy's refused tunnel is a denial (see DENIAL_NOTE). A
        # timeout is the server not answering, which is a different claim:
        # run 1 on Actions, where there is no proxy, timed out and was
        # reported as a denial until this was split out.
        result.denied = is_denial(exc)
        result.timed_out = is_timeout(exc)
        return result
    except Exception as exc:  # noqa: BLE001 - network layer
        result.error = f"{exc.__class__.__name__}: {exc}"
        return result

    result.ok = True
    result.bytes_read = len(payload)
    text = payload.decode("utf-8", errors="replace")
    text_lines = text.splitlines()
    result.raw_head = "\n".join(text_lines[: SHOWN_ROWS + 2])
    result.raw_tail = "\n".join(text_lines[:2] + text_lines[2:][-SHOWN_ROWS:])
    result.header, result.units, result.rows = parse_erddap_csv(text)
    return result


def is_denial(exc: BaseException) -> bool:
    text = str(exc)
    return "Tunnel connection failed" in text and "403" in text


def is_timeout(exc: BaseException) -> bool:
    reason = getattr(exc, "reason", exc)
    return isinstance(reason, (TimeoutError, socket.timeout)) or "timed out" in str(exc)


def reach(timeout: float = 20.0) -> tuple[list[str], bool]:
    """Where the road stops: DNS, then a TCP connection to the port, then ERDDAP's
    cheapest page. Each step's answer and time, so "the server did not
    answer" says at which layer."""

    parts = urllib.parse.urlsplit(BASE)
    host = parts.hostname or ""
    port = parts.port or (443 if parts.scheme == "https" else 80)
    lines = [f"### Reachability of {host}", ""]
    start = time.monotonic()
    try:
        addresses = sorted({a[4][0] for a in socket.getaddrinfo(host, port)})
    except OSError as exc:
        return lines + [f"- DNS: failed, {exc}", ""], False
    lines.append(f"- DNS: {', '.join(addresses)} ({time.monotonic() - start:.1f} s)")
    start = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
    except OSError as exc:
        return lines + [f"- TCP {port}: failed after {time.monotonic() - start:.1f} s, "
                        f"{exc.__class__.__name__}: {exc}", ""], False
    lines.append(f"- TCP {port}: connected ({time.monotonic() - start:.1f} s)")
    start = time.monotonic()
    version = fetch_csv("version", timeout=timeout * 3)
    elapsed = time.monotonic() - start
    if not version.ok:
        return lines + [f"- GET /erddap/version: failed after {elapsed:.1f} s, "
                        f"{version.error}", ""], False
    lines += [f"- GET /erddap/version: HTTP {version.status} ({elapsed:.1f} s), "
              f"{' '.join(version.header)}", ""]
    return lines, True


def parse_erddap_csv(text: str) -> tuple[list[str], list[str], list[list[str]]]:
    """ERDDAP's .csv: a names row, a units row, then data. The info pages
    carry no units row, so it is detected rather than assumed -- a units row
    on tabledap is all unit strings or blanks, never a parseable data row of
    the same shape as the first."""

    rows = list(csv.reader(io.StringIO(text)))
    rows = [r for r in rows if r]
    if not rows:
        return [], [], []
    header, rest = rows[0], rows[1:]
    units: list[str] = []
    if rest and _looks_like_units(rest[0]):
        units, rest = rest[0], rest[1:]
    return header, units, rest


def _looks_like_units(row: list[str]) -> bool:
    known = {"", "UTC", "degrees_north", "degrees_east", "m", "degree_C", "1"}
    return any(cell in known for cell in row) and not any(
        _is_iso_time(cell) for cell in row
    )


def _is_iso_time(cell: str) -> bool:
    return parse_time(cell) is not None


#: An epoch number's unit, read from its size: seconds have ten digits now,
#: milliseconds thirteen. Anything else is not read as a time.
EPOCH_SCALES = ((1e9, 1e10, 1.0), (1e12, 1e13, 1e3))


def epoch_scale(value: float) -> float | None:
    return next((k for lo, hi, k in EPOCH_SCALES if lo <= abs(value) < hi), None)


def parse_time(cell: str) -> datetime | None:
    cell = cell.strip()
    try:
        number = float(cell)
    except ValueError:
        number = None
    if number is not None:
        scale = epoch_scale(number)
        if scale is None:
            return None
        return datetime.fromtimestamp(number / scale, tz=timezone.utc)
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(cell, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def column(fetched: Fetched, name: str) -> list[str]:
    if name not in fetched.header:
        return []
    i = fetched.header.index(name)
    return [r[i] if i < len(r) else "" for r in fetched.rows]


@dataclass
class DatasetInfo:
    dataset_id: str
    variables: list[str] = field(default_factory=list)
    #: (variable, attribute) -> value; "NC_GLOBAL" holds the globals.
    attributes: dict[tuple[str, str], str] = field(default_factory=dict)
    #: variable -> ERDDAP data type ("String", "double", "long", ...).
    types: dict[str, str] = field(default_factory=dict)

    def station_variables(self) -> list[str]:
        """The variables that name a station, from the CF/ERDDAP cdm
        attribute when the dataset declares one; otherwise none is guessed."""

        for key in ("cdm_timeseries_variables", "cdm_trajectory_variables",
                    "cdm_profile_variables"):
            value = self.attributes.get(("NC_GLOBAL", key), "")
            names = [n.strip() for n in value.split(",") if n.strip()]
            names = [n for n in names if n in self.variables
                     and n not in ("latitude", "longitude")]
            if names:
                return names
        return []


def dataset_info(dataset_id: str) -> tuple[DatasetInfo, Fetched]:
    fetched = fetch_csv(f"info/{urllib.parse.quote(dataset_id)}/index.csv")
    info = DatasetInfo(dataset_id)
    if not fetched.ok:
        return info, fetched
    kinds = column(fetched, "Row Type")
    names = column(fetched, "Variable Name")
    attrs = column(fetched, "Attribute Name")
    values = column(fetched, "Value")
    dtypes = column(fetched, "Data Type")
    for kind, name, attr, value, dtype in zip(kinds, names, attrs, values, dtypes):
        if kind == "variable":
            info.variables.append(name)
            info.types[name] = dtype
        elif kind == "attribute":
            info.attributes[(name, attr)] = value
    return info, fetched


def breaks() -> list[geometry.Spot]:
    spots, _ = geometry.load()
    return [s for s in spots if s.id in CORONADO]


def nearest_break(lat: float, lon: float, spots: list[geometry.Spot]) -> tuple[str, float]:
    distances = [(great_circle_km((lat, lon), s.position), s.id) for s in spots]
    km, spot_id = min(distances)
    return spot_id, km


def _pick(variables: list[str], names: tuple[str, ...]) -> str | None:
    return next((n for n in names if n in variables), None)


def time_variable(info: "DatasetInfo") -> str | None:
    """`time` if there is one, else the first variable ERDDAP keeps as a time
    ("seconds since"), else the first whose name says time."""

    if "time" in info.variables:
        return "time"
    for v in info.variables:
        if "since" in info.attributes.get((v, "units"), ""):
            return v
    return next((v for v in info.variables if "time" in v.lower()), None)


def _box(lat_var: str, lon_var: str, points: list[tuple[float, float]],
         pad: float) -> list[str]:
    return [f"{lat_var}>={min(p[0] for p in points) - pad:.5f}",
            f"{lat_var}<={max(p[0] for p in points) + pad:.5f}",
            f"{lon_var}>={min(p[1] for p in points) - pad:.5f}",
            f"{lon_var}<={max(p[1] for p in points) + pad:.5f}"]


@dataclass
class Cluster:
    key: tuple[str, ...]
    lat: float
    lon: float
    rows: int
    spot: str
    km: float


def cluster_positions(fetched: Fetched, group: list[str], lat_var: str, lon_var: str,
                      spots: list[geometry.Spot]) -> list[Cluster]:
    """Distinct positions grouped by station and ~100 m, nearest break first.
    A position that does not parse is left out, never placed."""

    sums: dict[tuple, list[float]] = {}
    keys = list(zip(*(column(fetched, g) for g in group))) or [()] * len(fetched.rows)
    for key, lat, lon in zip(keys, column(fetched, lat_var), column(fetched, lon_var)):
        try:
            a, o = float(lat), float(lon)
        except ValueError:
            continue
        if a != a or o != o:
            continue
        cell = (tuple(key), round(a, CLUSTER_DECIMALS), round(o, CLUSTER_DECIMALS))
        acc = sums.setdefault(cell, [0.0, 0.0, 0])
        acc[0] += a
        acc[1] += o
        acc[2] += 1
    clusters = []
    for (key, _, _), (a, o, n) in sums.items():
        spot, km = nearest_break(a / n, o / n, spots)
        clusters.append(Cluster(key, a / n, o / n, int(n), spot, km))
    return sorted(clusters, key=lambda c: c.km)


def _q(*parts: str) -> str:
    """Join query parts, percent-encoding what ERDDAP needs encoded."""

    return "&".join(urllib.parse.quote(p, safe="=,()-.:") for p in parts)


def _quoted(row: list[str]) -> str:
    return " | ".join(row)


@dataclass
class Latest:
    key: tuple[str, ...]
    newest: datetime
    rows: int
    row: list[str]

    @property
    def age_hours(self) -> float:
        return (utcnow() - self.newest).total_seconds() / 3600

    @property
    def stale(self) -> bool:
        return self.age_hours > STALE_HOURS


def latest_rows(fetched: Fetched, group: list[str], time_var: str) -> list[Latest]:
    """The newest row of each group, by the parsed time; a row whose time does
    not parse is counted nowhere rather than guessed."""

    keys = list(zip(*(column(fetched, g) for g in group))) or [()] * len(fetched.rows)
    out: dict[tuple, Latest] = {}
    for key, cell, row in zip(keys, column(fetched, time_var), fetched.rows):
        stamp = parse_time(cell)
        if stamp is None:
            continue
        best = out.get(tuple(key))
        if best is None:
            out[tuple(key)] = Latest(tuple(key), stamp, 1, row)
            continue
        best.rows += 1
        if stamp > best.newest:
            best.newest, best.row = stamp, row
    return sorted(out.values(), key=lambda g: g.newest, reverse=True)


def window_start(cells: list[str], dtype: str) -> str | None:
    """The constraint value RECENT_TEXT_DAYS before the newest of `cells`, in
    the column's own form: a quoted ISO date for text, the same epoch unit for
    a number. None when the newest cannot be read as a time."""

    stamps = [t for t in (parse_time(c) for c in cells) if t]
    if not stamps:
        return None
    start = max(stamps) - timedelta(days=RECENT_TEXT_DAYS)
    numbers = [float(c) for c in cells if _is_number(c)]
    if not numbers:
        return f'"{start:%Y-%m-%d}"'
    scale = epoch_scale(max(numbers))
    if scale is None:
        return None
    value = f"{start.timestamp() * scale:.0f}"
    # An epoch kept as text (run 7: the detections' device_time_utc) compares
    # as text, which equal-length digit strings do correctly.
    return f'"{value}"' if dtype == "String" else value


def newest_by_group(fetched: Fetched, group: list[str], time_var: str,
                    window: str, tally: bool = True) -> list[str]:
    latest = latest_rows(fetched, group, time_var)
    unparsed = len(fetched.rows) - sum(g.rows for g in latest)
    lines = [f"Rows in the last {window}: {len(fetched.rows)} ({fetched.bytes_read} "
             f"bytes){f', {unparsed} with an unparseable time' if unparsed else ''}. "
             f"Newest per {','.join(group) or 'dataset'}:", "",
             "```", ",".join(fetched.header)]
    for g in latest:
        flag = " STALE" if g.stale else ""
        lines.append(",".join(g.row) + f"   <- {g.rows} rows, {g.age_hours:.1f} h old{flag}")
    lines += ["```", ""]
    for name in fetched.header if tally else []:
        if name == time_var or name in group:
            continue
        values = column(fetched, name)
        distinct = set(values)
        if 1 < len(distinct) <= TALLY_MAX and not all(_is_number(v) for v in distinct):
            tally = sorted(((values.count(v), v) for v in distinct), reverse=True)
            lines.append(f"- `{name}`: " + ", ".join(f"{v or '(blank)'} x{n}" for n, v in tally))
    lines.append("")
    return lines


def _is_number(cell: str) -> bool:
    try:
        float(cell)
    except ValueError:
        return False
    return True


def probe(dataset_ids: list[str] | None = None) -> tuple[list[str], int]:
    lines = [f"## CSULB Shark Lab ERDDAP probe ({BASE})", "",
             f"Run at {utcnow():%Y-%m-%d %H:%M}Z.", ""]
    spots = breaks()

    reached, ok = reach()
    lines += reached
    if not ok:
        lines.append("Stopped: the server was not reached, so nothing about its "
                     "datasets can be said.")
        return lines, 1

    listing = fetch_csv("tabledap/allDatasets.csv", ",".join(ALL_DATASETS_COLUMNS))
    if not listing.ok:
        lines += [f"**allDatasets failed:** {listing.error}", ""]
        if listing.denied:
            lines.append(DENIAL_NOTE)
        return lines, 2 if listing.denied else 1

    lines += [f"### Datasets ({len(listing.rows)} rows, {listing.bytes_read} bytes)", "",
              "| " + " | ".join(listing.header) + " |",
              "|" + "---|" * len(listing.header)]
    lines += ["| " + " | ".join(r) + " |" for r in listing.rows]
    lines.append("")

    ids = [i for i in column(listing, "datasetID") if i != "allDatasets"]
    if dataset_ids:
        ids = [i for i in ids if i in dataset_ids]

    found_fresh = False
    denied = False
    for dataset_id in ids:
        info, fetched = dataset_info(dataset_id)
        lines.append(f"### {dataset_id}")
        if not fetched.ok:
            lines += [f"info failed: {fetched.error}", ""]
            denied |= fetched.denied
            continue
        title = info.attributes.get(("NC_GLOBAL", "title"), "")
        lines += [f"{title}", "", "Variables: " + ", ".join(
            f"`{v}` ({info.attributes.get((v, 'units'), 'no units')})" for v in info.variables), ""]
        for key in ("cdm_data_type", "cdm_timeseries_variables", "subsetVariables",
                    "license", "creator_name", "summary"):
            value = info.attributes.get(("NC_GLOBAL", key))
            if value:
                lines.append(f"- {key}: {value}")
        lines.append("")

        lat_var = _pick(info.variables, LAT_NAMES)
        lon_var = _pick(info.variables, LON_NAMES)
        time_var = time_variable(info)
        group = info.station_variables() or (
            [g] if (g := _pick(info.variables, GROUP_NAMES)) else [])
        path = f"tabledap/{urllib.parse.quote(dataset_id)}.csv"
        lines.append(f"Position `{lat_var}`/`{lon_var}`, time `{time_var}`, "
                     f"grouped by {group or 'nothing'}.")
        lines.append("")

        box: list[str] = []
        if lat_var and lon_var:
            box = _box(lat_var, lon_var, [s.position for s in spots], BOX_DEG)
            positions = fetch_csv(path, _q(",".join(group + [lat_var, lon_var]),
                                           *box, "distinct()"))
            if positions.empty:
                lines += [f"No positions within {BOX_DEG}° of the breaks.", ""]
                continue
            if not positions.ok:
                lines += [f"positions failed: {positions.error}", ""]
                denied |= positions.denied
                continue
            clusters = cluster_positions(positions, group, lat_var, lon_var, spots)
            lines += [f"Positions within {BOX_DEG}° of the breaks: "
                      f"{len(positions.rows)} distinct, in {len(clusters)} "
                      f"clusters of ~100 m (mean position, rows, nearest break):", ""]
            for c in clusters[:MAX_CLUSTERS]:
                mark = " **near**" if c.km <= NEAR_KM else ""
                lines.append(f"- {' | '.join(c.key) or '-'}: {c.lat:.5f}, {c.lon:.5f} "
                             f"({c.rows} positions), {c.km:.2f} km from {c.spot}{mark}")
            lines.append("")
            near = [c for c in clusters if c.km <= NEAR_KM]
            if not near:
                continue
            pad = 0.005
            box = _box(lat_var, lon_var, [(c.lat, c.lon) for c in near], pad)
        else:
            lines += ["No position variables: rows are read whole, not placed.", ""]

        if not time_var:
            continue
        erddap_time = "since" in info.attributes.get((time_var, "units"), "")
        if erddap_time:
            # ERDDAP's own time: narrowed on the server with `now-`.
            window = f"{RECENT_DAYS} days"
            recent = fetch_csv(path, "&" + _q(*box, f"{time_var}>=now-{RECENT_DAYS}days"))
            latest_src = recent
        else:
            # A time ERDDAP does not know as one (run 6: device_time_utc is a
            # number with no units). The newest row per group comes from the
            # server's orderByMax, then the window is set back from it in the
            # column's own terms. With no variable list, the first constraint
            # still needs its "&" (run 5).
            by = ",".join(group + [time_var])
            latest_src = fetch_csv(path, "&" + _q(*box, f'orderByMax("{by}")'))
            if not latest_src.ok:
                lines += [f"newest rows failed: {latest_src.error}", ""]
                denied |= latest_src.denied
                continue
            window = f"{RECENT_TEXT_DAYS} days before the newest row"
            since = window_start(column(latest_src, time_var), info.types.get(time_var, ""))
            recent = (fetch_csv(path, "&" + _q(*box, f"{time_var}>={since}"))
                      if since is not None else latest_src)
        if latest_src is not recent and latest_src.ok:
            lines += newest_by_group(latest_src, group, time_var, "whole dataset",
                                     tally=False)
        if recent.empty:
            lines += [f"No rows in the last {window}"
                      + (" near Coronado." if box else "."), ""]
            continue
        if not recent.ok:
            lines += [f"recent rows failed: {recent.error}", ""]
            denied |= recent.denied
            continue
        lines += newest_by_group(recent, group, time_var, window)
        found_fresh |= any(not g.stale for g in latest_rows(latest_src, group, time_var))

    if denied:
        lines.append(DENIAL_NOTE)
        return lines, 2
    return lines, 0 if found_fresh else 1


# --- The Coronado hubs' history (--hubs) ------------------------------------
#
# Run 8 found every hub and receiver on the server silent since 2026-10-18
# 23:59Z, and Coronado's two lying on land. Before anything is built on them,
# the question is what their record holds: when each was in the water, how
# often it heard a tag, and whether any temperature came through it. So this
# reads each hub's whole history, and prints only aggregates: tag IDs stay
# out of a public log until the lab has said how detections may be shown.

#: The server's own dataset IDs, as run 5 listed them.
DETECTIONS = "datasets_0794_7c56_a4f4"
HUB_STATUS = "datasets_0193_1f45_ee2a"
RECEIVER_STATUS = "datasets_575b_8cd5_27db"
TAGGED_SHARKS = "datasets_b8e8_5e7d_89aa"

#: A fix this far seaward of its nearest break's shoreline is in the water.
#: Run 7 put the deployed fixes ~460-480 m out and the newest ~190 m inland,
#: so the threshold sits well clear of both.
IN_WATER_M = 100.0

#: No fix for this long splits a stretch: the hub was not reporting.
SILENT_H = 24.0

HISTORY_TIMEOUT_S = 300.0

#: The stretch table is printed for this many recent days only; the monthly
#: coverage covers the rest (run 9's full table outran the readable log).
RECENT_STRETCH_DAYS = 120

#: A hub reports every 2 minutes since November 2025 (run 9: 720 a day), so
#: a day with fewer fixes than this is partial.
FULL_DAY_FIXES = 700


def coverage(fixes: list[tuple[datetime, bool]]) -> list[str]:
    """Per UTC month: days with any fix, of those full days, days with a fix in
    the water and on land; then each missing day in the last
    RECENT_STRETCH_DAYS. A day absent here is absent on the server."""

    from collections import Counter

    per_day = Counter(f[0].date() for f in fixes)
    wet = {f[0].date() for f in fixes if f[1]}
    dry = {f[0].date() for f in fixes if not f[1]}
    if not per_day:
        return ["No fixes.", ""]
    first, last = min(per_day), max(per_day)
    lines = ["| Month | Days with fixes | Full days | In the water | On land |",
             "|---|---|---|---|---|"]
    months: dict[str, list] = {}
    day = first
    while day <= last:
        m = months.setdefault(f"{day:%Y-%m}", [0, 0, 0, 0, 0])
        m[0] += 1
        if day in per_day:
            m[1] += 1
            m[2] += per_day[day] >= FULL_DAY_FIXES
            m[3] += day in wet
            m[4] += day in dry
        day += timedelta(days=1)
    for key, (n, have, full, w, d) in months.items():
        lines.append(f"| {key} | {have} / {n} | {full} | {w} | {d} |")
    since = max(first, (utcnow() - timedelta(days=RECENT_STRETCH_DAYS)).date())
    missing, day = [], since
    while day <= last:
        if day not in per_day:
            missing.append(f"{day:%m-%d}")
        day += timedelta(days=1)
    partial = [f"{d:%m-%d} ({per_day[d]})" for d in sorted(per_day)
               if d >= since and per_day[d] < FULL_DAY_FIXES]
    lines += ["", f"Missing days since {since}: {', '.join(missing) or 'none'}.",
              f"Partial days since {since} (fixes): {', '.join(partial) or 'none'}.",
              f"Newest fix {_fmt(max(f[0] for f in fixes))}.", ""]
    return lines


def seaward_m(lat: float, lon: float, spots: list[geometry.Spot]) -> float:
    """Metres seaward of the nearest break's position along its normal;
    negative is landward."""

    import math

    from forecast.swell import initial_bearing

    spot = min(spots, key=lambda s: great_circle_km((lat, lon), s.position))
    d = great_circle_km(spot.position, (lat, lon)) * 1000.0
    if d == 0:
        return 0.0
    bearing = initial_bearing(spot.position, (lat, lon))
    return d * math.cos(math.radians(bearing - spot.normal))


@dataclass
class Stretch:
    in_water: bool | None   # None: no fix at all (silent)
    start: datetime
    end: datetime
    fixes: int


def stretches(fixes: list[tuple[datetime, bool]]) -> list[Stretch]:
    """Consecutive fixes on the same side of the shoreline, a silence of
    more than SILENT_H between two fixes its own stretch."""

    out: list[Stretch] = []
    for when, wet in sorted(fixes):
        last = out[-1] if out else None
        if last and (when - last.end).total_seconds() / 3600 > SILENT_H:
            out.append(Stretch(None, last.end, when, 0))
            last = None
        if last and last.in_water == wet:
            last.end, last.fixes = when, last.fixes + 1
        else:
            out.append(Stretch(wet, when, when, 1))
    return out


def lab_tags() -> set[str]:
    """The lab's own tagged sharks as "codeSpace-ID", the detections' form."""

    import ast

    fetched = fetch_csv(f"tabledap/{TAGGED_SHARKS}.csv", "fullIDs")
    tags: set[str] = set()
    for cell in column(fetched, "fullIDs"):
        try:
            for entry in ast.literal_eval(cell):
                tags.add(f"{entry['codeSpace']}-{entry['ID']}")
        except (ValueError, SyntaxError, TypeError, KeyError):
            continue
    return tags


def _constraint(info: DatasetInfo, name: str, value: str) -> str:
    return f'{name}="{value}"' if info.types.get(name) == "String" else f"{name}={value}"


def _fmt(t: datetime | None) -> str:
    return f"{t:%Y-%m-%d %H:%M}Z" if t else "-"


def distinct_rows(rows: list[list[str]]) -> list[list[str]]:
    """Each row once, in order. Run 12 found every Coronado status and
    detection row stored twice, exactly (detections before the lab's
    2026-10-29 refresh too): everything after the count reads each once."""

    seen: set[tuple] = set()
    out = []
    for row in rows:
        key = tuple(row)
        if key not in seen:
            seen.add(key)
            out.append(row)
    return out


def duplicates(label: str, times: list[str], rows: list[tuple]) -> list[str]:
    """Rows against distinct rows and distinct stamps, per UTC month: run 10,
    after the lab's refresh, read ~1,440 fixes a day where run 9 read ~720,
    from hubs that report every 2 minutes. An exact repeat is a stored
    duplicate; a repeated stamp with different values is not, and is said."""

    from collections import defaultdict

    per: dict[str, list] = defaultdict(lambda: [0, set(), set()])
    for t, row in zip(times, rows):
        when = parse_time(t)
        if when is None:
            continue
        m = per[f"{when:%Y-%m}"]
        m[0] += 1
        m[1].add(row)
        m[2].add(t)
    total = sum(m[0] for m in per.values())
    distinct = sum(len(m[1]) for m in per.values())
    lines = [f"{label}: {total} rows, {distinct} distinct rows, "
             f"{total - distinct} exact repeats.", "",
             "| Month | Rows | Distinct rows | Distinct stamps |", "|---|---|---|---|"]
    for key in sorted(per):
        n, uniq, stamps = per[key]
        if n != len(uniq) or key >= f"{utcnow() - timedelta(days=RECENT_STRETCH_DAYS):%Y-%m}":
            lines.append(f"| {key} | {n} | {len(uniq)} | {len(stamps)} |")
    return lines + [""]


def hub_history(hub: str, spots: list[geometry.Spot], tags: set[str]) -> list[str]:
    lines = [f"### Hub {hub}", ""]

    info, _ = dataset_info(HUB_STATUS)
    status = fetch_csv(f"tabledap/{HUB_STATUS}.csv",
                       _q("device_time_utc,latitude,longitude,battery_remaining,tilt",
                          _constraint(info, "serial_number", hub)),
                       timeout=HISTORY_TIMEOUT_S)
    if not status.ok:
        return lines + [f"hub status failed: {status.error}", ""]
    fixes: list[tuple[datetime, bool]] = []
    for t, a, o in zip(column(status, "device_time_utc"), column(status, "latitude"),
                       column(status, "longitude")):
        when = parse_time(t)
        try:
            lat, lon = float(a), float(o)
        except ValueError:
            continue
        if when is None or lat != lat or lon != lon:
            continue
        fixes.append((when, seaward_m(lat, lon, spots) > IN_WATER_M))
    lines += duplicates("Status", column(status, "device_time_utc"),
                        [tuple(r) for r in status.rows])
    status.rows = distinct_rows(status.rows)
    runs = stretches(fixes)
    lines += [f"Status: {len(status.rows)} rows, {len(fixes)} placed fixes, "
              f"{_fmt(min(f[0] for f in fixes) if fixes else None)} to "
              f"{_fmt(max(f[0] for f in fixes) if fixes else None)}. "
              f"In the water = more than {IN_WATER_M:.0f} m seaward of the "
              f"nearest break's shoreline; a silence is over {SILENT_H:.0f} h "
              f"without a fix.", "",
              ]
    lines += coverage(fixes)
    recent = [r for r in runs if r.end >= utcnow() - timedelta(days=RECENT_STRETCH_DAYS)]
    lines += [f"Stretches in the last {RECENT_STRETCH_DAYS} days:", "",
              "| From | To | Days | State | Fixes |", "|---|---|---|---|---|"]
    for r in recent:
        state = {True: "in the water", False: "on land", None: "silent"}[r.in_water]
        days = (r.end - r.start).total_seconds() / 86400
        if r.in_water is not None and days < 0.5 and r.fixes < 20:
            continue  # a stray fix, not a stretch; still counted below
        lines.append(f"| {_fmt(r.start)} | {_fmt(r.end)} | {days:.1f} | {state} | {r.fixes} |")
    wet_days = sum((r.end - r.start).total_seconds() for r in runs if r.in_water) / 86400
    lines += ["", f"In the water {wet_days:.0f} days in all.", ""]

    dinfo, _ = dataset_info(DETECTIONS)
    det = fetch_csv(f"tabledap/{DETECTIONS}.csv",
                    _q("device_time_utc,serial_number,full_id,sensor_type,sensor_value,sensor_unit",
                       _constraint(dinfo, "hub_serial", hub)),
                    timeout=HISTORY_TIMEOUT_S)
    if det.empty:
        return lines + ["No detection rows at all.", ""]
    if not det.ok:
        return lines + [f"detections failed: {det.error}", ""]
    receivers = sorted(set(column(det, "serial_number")))
    lines += duplicates("Detections", column(det, "device_time_utc"),
                        [tuple(r) for r in det.rows])
    det.rows = distinct_rows(det.rows)
    lines += [f"Detections: {len(det.rows)} distinct rows, receiver(s) {', '.join(receivers)}.", ""]

    months: dict[str, dict] = {}
    sensors: dict[str, list[float]] = {}
    units: dict[str, set[str]] = {}
    for t, fid, stype, sval, sunit in zip(column(det, "device_time_utc"), column(det, "full_id"),
                                          column(det, "sensor_type"), column(det, "sensor_value"),
                                          column(det, "sensor_unit")):
        when = parse_time(t)
        if when is None:
            continue
        m = months.setdefault(f"{when:%Y-%m}", {"rows": 0, "tags": set(), "lab": set(),
                                                 "sensor": 0, "temps": []})
        if stype:
            m["sensor"] += 1
            units.setdefault(stype, set()).add(sunit)
            if _is_number(sval):
                sensors.setdefault(stype, []).append(float(sval))
                if stype == "Temperature":
                    m["temps"].append(float(sval))
            continue
        m["rows"] += 1
        m["tags"].add(fid)
        if fid in tags:
            m["lab"].add(fid)
    lines += ["| Month | Tag detections | Distinct tags | Of them the lab's white sharks | "
              "Sensor rows | Temperature min / mean / max |", "|---|---|---|---|---|---|"]
    for key in sorted(months):
        m = months[key]
        temps = m["temps"]
        tt = (f"{min(temps):.1f} / {sum(temps) / len(temps):.1f} / {max(temps):.1f}"
              if temps else "-")
        lines.append(f"| {key} | {m['rows']} | {len(m['tags'])} | {len(m['lab'])} | "
                     f"{m['sensor']} | {tt} |")
    lines.append("")
    for stype, values in sorted(sensors.items()):
        lines.append(f"- Sensor `{stype}` ({', '.join(sorted(units[stype]))}): {len(values)} "
                     f"readings, {min(values):.1f} to {max(values):.1f}")
    all_tags = set().union(*(m["tags"] for m in months.values())) if months else set()
    lines += ["", f"{len(all_tags)} distinct tags in all, "
              f"{len(all_tags & tags)} of them in the lab's white-shark list.", ""]
    return lines


def history(hubs: list[str]) -> tuple[list[str], int]:
    lines = [f"## Coronado hubs' history ({BASE})", "",
             f"Run at {utcnow():%Y-%m-%d %H:%M}Z.", ""]
    reached, ok = reach()
    lines += reached
    if not ok:
        return lines + ["Stopped: the server was not reached."], 1
    spots = breaks()
    tags = lab_tags()
    lines += [f"The lab's tag list: {len(tags)} tag IDs.", ""]
    for hub in hubs:
        lines += hub_history(hub, spots, tags)
    return lines, 0


def main(argv: list[str] | None = None) -> int:
    global BASE
    parser = argparse.ArgumentParser(description="Probe CSULB Shark Lab's ERDDAP.")
    parser.add_argument("--base", default=None,
                        help=f"ERDDAP root URL, default {BASE}.")
    parser.add_argument("--dataset", action="append", default=None,
                        help="Only this datasetID (repeatable); default every one.")
    parser.add_argument("--hubs", default="",
                        help="Comma-separated hub serials: read their whole history "
                             "instead of surveying the server.")
    args = parser.parse_args(argv)
    if args.base:
        BASE = args.base.rstrip("/")
    hubs = [h.strip() for h in args.hubs.split(",") if h.strip()]
    lines, code = history(hubs) if hubs else probe(args.dataset)
    text = "\n".join(lines)
    print(text)
    write_step_summary(text if len(text) <= SUMMARY_LIMIT
                       else text[:SUMMARY_LIMIT] + "\n\n(cut at the summary's limit; the log has it all)")
    return code


if __name__ == "__main__":
    sys.exit(main())
