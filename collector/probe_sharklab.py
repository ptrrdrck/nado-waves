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
    if dtype == "String":
        return f'"{start:%Y-%m-%d}"'
    numbers = [float(c) for c in cells if _is_number(c)]
    scale = epoch_scale(max(numbers)) if numbers else None
    return None if scale is None else f"{start.timestamp() * scale:.0f}"


def newest_by_group(fetched: Fetched, group: list[str], time_var: str,
                    window: str) -> list[str]:
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
    for name in fetched.header:
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


def main(argv: list[str] | None = None) -> int:
    global BASE
    parser = argparse.ArgumentParser(description="Probe CSULB Shark Lab's ERDDAP.")
    parser.add_argument("--base", default=None,
                        help=f"ERDDAP root URL, default {BASE}.")
    parser.add_argument("--dataset", action="append", default=None,
                        help="Only this datasetID (repeatable); default every one.")
    args = parser.parse_args(argv)
    if args.base:
        BASE = args.base.rstrip("/")
    lines, code = probe(args.dataset)
    text = "\n".join(lines)
    print(text)
    write_step_summary(text if len(text) <= SUMMARY_LIMIT
                       else text[:SUMMARY_LIMIT] + "\n\n(cut at the summary's limit; the log has it all)")
    return code


if __name__ == "__main__":
    sys.exit(main())
