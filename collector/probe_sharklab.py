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
from datetime import datetime, timezone

from forecast import geometry
from forecast.swell import great_circle_km

from .common import utcnow, write_step_summary
from .ndbc import USER_AGENT
from .probe_mop import DENIAL_NOTE

#: The public server, as its maintainer gave it (2026-10-22): plain http, not
#: https. erddap-02.thesharklab.org, the address first given, resolves but
#: accepts no connection from GitHub's runners (run 2, 2026-10-20).
BASE = "http://erddap-public.csulbshsrklab.org/erddap"

#: Coronado's three breaks -- the only spots with charted positions.
CORONADO = ("coronado_north", "coronado_center", "coronado_south")

#: A station this close to a break is reported as "at Coronado". Center to
#: South is ~1.5 km, so a hub halfway between sits well inside it.
NEAR_KM = 3.0

#: Looking back this far for the newest rows near Coronado.
RECENT_DAYS = 30

#: Older than this and the newest row is present but not live.
STALE_HOURS = 48.0

#: Rows printed verbatim per query; the parse still reads all of them.
SHOWN_ROWS = 8

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
    result.raw_head = "\n".join(text.splitlines()[: SHOWN_ROWS + 2])
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


def parse_time(cell: str) -> datetime | None:
    cell = cell.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"):
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
    for kind, name, attr, value in zip(kinds, names, attrs, values):
        if kind == "variable":
            info.variables.append(name)
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


def _q(*parts: str) -> str:
    """Join query parts, percent-encoding what ERDDAP needs encoded."""

    return "&".join(urllib.parse.quote(p, safe="=,()-.:") for p in parts)


def _quoted(row: list[str]) -> str:
    return " | ".join(row)


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

        if not {"latitude", "longitude"} <= set(info.variables):
            lines += ["No latitude/longitude variables: no station positions to place.", ""]
            continue

        ids_vars = info.station_variables()
        positions = fetch_csv(
            f"tabledap/{urllib.parse.quote(dataset_id)}.csv",
            _q(",".join(ids_vars + ["latitude", "longitude"]), "distinct()"),
        )
        if not positions.ok:
            lines += [f"positions failed: {positions.error}", ""]
            denied |= positions.denied
            continue
        lats = column(positions, "latitude")
        lons = column(positions, "longitude")
        near = []
        lines += [f"Stations ({len(positions.rows)}; station variables "
                  f"{ids_vars or 'none declared'}), nearest Coronado break:", ""]
        for row, lat, lon in zip(positions.rows, lats, lons):
            try:
                spot_id, km = nearest_break(float(lat), float(lon), spots)
            except ValueError:
                lines.append(f"- {_quoted(row)}: position not numeric")
                continue
            mark = " **near**" if km <= NEAR_KM else ""
            lines.append(f"- {_quoted(row)}: {km:.2f} km from {spot_id}{mark}")
            if km <= NEAR_KM:
                near.append((float(lat), float(lon)))
        lines.append("")
        if not near or "time" not in info.variables:
            continue

        # Newest rows inside a box around the near stations, last RECENT_DAYS.
        pad = 0.005
        box = (min(a for a, _ in near) - pad, max(a for a, _ in near) + pad,
               min(o for _, o in near) - pad, max(o for _, o in near) + pad)
        recent = fetch_csv(
            f"tabledap/{urllib.parse.quote(dataset_id)}.csv",
            _q(f"time>=now-{RECENT_DAYS}days",
               f"latitude>={box[0]:.5f}", f"latitude<={box[1]:.5f}",
               f"longitude>={box[2]:.5f}", f"longitude<={box[3]:.5f}",
               'orderByMax("time")' if not ids_vars
               else f'orderByMax("{",".join(ids_vars)},time")'),
        )
        if recent.empty:
            lines += [f"Nothing near Coronado in the last {RECENT_DAYS} days.", ""]
            continue
        if not recent.ok:
            lines += [f"recent rows failed: {recent.error}", ""]
            denied |= recent.denied
            continue
        times = [t for t in (parse_time(c) for c in column(recent, "time")) if t]
        newest = max(times) if times else None
        age_h = (utcnow() - newest).total_seconds() / 3600 if newest else None
        stale = age_h is None or age_h > STALE_HOURS
        found_fresh |= not stale
        lines += [
            f"Newest row near Coronado: {newest:%Y-%m-%d %H:%M}Z, {age_h:.1f} h old"
            + (" (STALE)" if stale else "") if newest else "No parseable time column.",
            f"({len(recent.rows)} rows, {recent.bytes_read} bytes; verbatim head:)", "",
            "```", recent.raw_head, "```", "",
        ]

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
    write_step_summary(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
