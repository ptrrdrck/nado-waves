"""Archive the county's beach water quality at Coronado's three breaks.

    python -m collector.beachwater

The County of San Diego's Beach & Bay Water Quality Monitoring Program
(DEHQ) samples Coronado at three stations, one per break (owner's request,
2026-10-30; `beachwater.json`): Coronado North Beach (EH-060), Coronado Main
Lifeguard Tower (EH-050, Center) and Avenida Lunar (IB-079, South). Its site,
`cosdapps.sandiegocounty.gov/sdbeachinfo`, is an OutSystems Reactive app
(rebuilt July 2026): the pages are an empty shell, and the data is read the
way the page reads it, from its screen services (`collector.probe_beachwater`,
runs 1-6):

- the module's scripts are listed by `moduleservices/moduleinfo`; each
  block's script names its aggregates and their API versions, which change
  whenever the county redeploys, so they are read afresh every collection,
  never stored;
- an aggregate is a POST of the module's version, the API version, the
  SCREEN the block is shown on as `viewName` (a block's own name is refused,
  "No role validation found"), the block's variables and the paging as
  `inputParameters`; OutSystems reports a refusal inside an HTTP 200.

Two things are archived, each kept once:

- **samples**: every result the county posts for each station, by its own
  record id, with `first_seen_utc`; a result that comes back changed keeps
  the first and is counted, never overwritten;
- **events**: each advisory, closure or warning the county lists for the
  stations, by station, type and issue time; its lift time is the county's
  and may be set at issue (a General Rain Advisory's 72 h) or later, so a
  changed lift time is a new row, both kept, the newest read.

A day with no sample is a gap, never filled (a rain advisory stops sampling;
a sample can fail). Denied at CONNECT from a Claude session: Actions only.
"""

from __future__ import annotations

import argparse
import csv
import http.cookiejar
import json
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from .common import DEFAULT_DATA_DIR, parse_iso, to_iso, utcnow, write_step_summary
from .ndbc import USER_AGENT

REGISTRY = Path(__file__).resolve().parent / "beachwater.json"

#: The anonymous CSRF token every OutSystems Reactive app sends before
#: sign-in (the runtime's `AnonymousCSRFToken`, probe run 2).
CSRF = "T6C+9iB49TLra4jEsMeSckDMNhQ="

#: The block scripts read, and the screen each is shown on: the server checks
#: `viewName` against the screens it knows (probe runs 3-4).
BLOCKS = {
    "SampleBlock": "MainFlow.SamplesReport",
    "SamplePostingReportBlock": "MainFlow.SamplePostingReport",
    "BlockMarkup": "MainFlow.Home",
    "BlockLegend": "MainFlow.Home",
}
MODULE = "CoSD_Beach_Water_CW"

#: An aggregate's call in a block's script.
CALL = re.compile(r"""callAggregate\w*\(\s*"(\w+)"\s*,\s*"(screenservices/[^"]+)"\s*,\s*"([^"]+)\"""")

#: The OutSystems null date and time: an event never lifted carries it.
NULL_TIME = "1900-01-01T00:00:00"


def registry(path: Path = REGISTRY) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class Refused(Exception):
    """The server answered, and said no (OutSystems puts it in the body)."""


@dataclass
class Client:
    """One session against the site: cookies, the module's version, and the
    API version of every aggregate in BLOCKS, read from the scripts."""

    base: str
    timeout: float = 60.0
    module_version: str = ""
    services: dict = field(default_factory=dict)  # "Block.Name" -> (path, api)
    opener: urllib.request.OpenerDirector = field(init=False)

    def __post_init__(self):
        self.base = self.base.rstrip("/")
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def _get(self, url: str) -> str:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with self.opener.open(req, timeout=self.timeout) as r:
            return r.read().decode("utf-8", errors="replace")

    def start(self) -> Client:
        page = self._get(f"{self.base}/")
        m = re.search(r'indexVersionToken\s*=\s*"([^"]+)"', page)
        token = m.group(1) if m else ""
        manifest = json.loads(self._get(f"{self.base}/moduleservices/moduleinfo?{token}"))["manifest"]
        self.module_version = json.loads(
            self._get(f"{self.base}/moduleservices/moduleversioninfo?{token}"))["versionToken"]
        root = self.base.split("/", 3)[:3]
        for key, version in manifest["urlVersions"].items():
            m = re.search(rf"/scripts/{MODULE}\.MainFlow\.(\w+)\.mvc\.js$", key)
            if not m or m.group(1) not in BLOCKS:
                continue
            script = self._get("/".join(root) + key + version)
            for name, path, api in CALL.findall(script):
                self.services[f"{m.group(1)}.{name.removeprefix('ScreenDataSet')}"] = (path, api)
        return self

    def aggregate(self, service: str, variables: dict, max_records: int = 1000, start: int = 0) -> dict:
        """One aggregate's `data`, as the block's screen asks for it."""

        if service not in self.services:
            raise Refused(f"{service}: not in the site's scripts (renamed or removed?)")
        path, api = self.services[service]
        body = {"versionInfo": {"moduleVersion": self.module_version, "apiVersion": api},
                "viewName": BLOCKS[service.split(".")[0]],
                "screenData": {"variables": variables},
                "inputParameters": {"StartIndex": start, "MaxRecords": max_records}}
        req = urllib.request.Request(
            f"{self.base}/{path}", data=json.dumps(body).encode(),
            headers={"User-Agent": USER_AGENT, "Content-Type": "application/json; charset=UTF-8",
                     "Accept": "application/json", "X-CSRFToken": CSRF})
        try:
            with self.opener.open(req, timeout=self.timeout) as r:
                got = json.loads(r.read())
        except urllib.error.HTTPError as exc:
            try:
                got = json.loads(exc.read())
            except ValueError:
                raise Refused(f"{service}: HTTP {exc.code}") from exc
        if got.get("exception"):
            raise Refused(f"{service}: {got['exception'].get('message')}")
        if (got.get("versionInfo") or {}).get("hasApiVersionChanged"):
            raise Refused(f"{service}: the API version changed under the session")
        return got.get("data") or {}


def rows(data: dict) -> list:
    return ((data.get("List") or {}).get("List")) or []


#: The variables each block's screen sends; a station or filter on top.
SAMPLE_VARS = {"IsLoadingUpload": False, "NumberRecordsExcel": 0, "ShowError": False, "ShowValidated": False,
               "TableSort": "", "StartIndex": 0, "MaxRecords": 1000, "StationIdFilter": "0",
               "StationName3": "", "SampleDataFrom": "1900-01-01", "SampleDataTo": "1900-01-01",
               "ShowImport": False, "UrlBase": "", "isPublic": True, "SiteId": "0"}
POSTING_VARS = {"TableSort": "", "StartIndex": 0, "MaxRecords": 1000, "BeachGroupIdFilter": "0",
                "BeachNameFilter": "", "TypeFilter": 0, "YearFilter": 0}

#: Rows asked for at a time; a full page asks for the next (the posting
#: report held 1,028 rows on 30 Oct 2026, and run 6 stopped at exactly 1000).
PAGE = 1000
MAX_PAGES = 50


def paged(client: Client, service: str, variables: dict) -> list[dict]:
    out: list[dict] = []
    for page in range(MAX_PAGES):
        got = rows(client.aggregate(service, variables, max_records=PAGE, start=page * PAGE))
        out += got
        if len(got) < PAGE:
            return out
    raise Refused(f"{service}: more than {MAX_PAGES} pages")


def samples(client: Client, site: str) -> list[dict]:
    """A station's samples, as its samples page lists them: the block filters
    by `StationIdFilter`, and ignores SiteId (probe run 5 had every
    station's)."""

    return paged(client, "SampleBlock.GetSamples", {**SAMPLE_VARS, "StationIdFilter": site, "SiteId": site})


def events(client: Client) -> list[dict]:
    """The county's posting report: every advisory, closure and warning it
    lists, newest first, a station once per beach group it belongs to."""

    return paged(client, "SamplePostingReportBlock.GetSites", POSTING_VARS)


def legend(client: Client) -> dict[int, str]:
    """The map legend's labels by id: Warning 1, Open 2, Advisory 3, Closed 4
    on 30 Oct 2026."""

    return {int((r.get("Legend") or {}).get("Id", 0)): (r.get("Legend") or {}).get("Label", "")
            for r in rows(client.aggregate("BlockLegend.GetLegends", {}))}


def priority(client: Client, site: str) -> int | None:
    """A site's status as the county's map draws it: the PriorityMax of its
    events in force, an id of the legend's (Silver Strand's two closed
    stations read 4, Closed, on 30 Oct 2026). None when nothing is in force,
    which the map draws as Open."""

    got = rows(client.aggregate("BlockMarkup.GetEvents", {"SiteId": site}, max_records=50))
    values = [int(r.get("PriorityMax") or 0) for r in got]
    return max(values) if values else None


# ------------------------------------------------------------------ the archive

ARCHIVE = "beach_water"
SAMPLE_FIELDS = ("sample_id", "sample_date", "sample_time", "parameter", "method", "qualifier", "result",
                 "units", "comments", "first_seen_utc")
EVENT_FIELDS = ("station", "event_type", "issued_utc", "lifted_utc", "distance", "indicator", "reason",
                "public_notification", "first_seen_utc")
EVENT_KEY = ("station", "event_type", "issued_utc", "lifted_utc")
STATUS_FIELDS = ("first_seen_utc", "station", "priority", "status")

#: The site changes when the county posts, not by the minute: a collection
#: fetches only when the last fetch is at least this old. Each fetch is ~15
#: requests (the scripts, three stations' samples, the posting report's
#: pages, three statuses and the legend).
MIN_INTERVAL_MIN = 30

STATE = "state.json"


def utc_text(stamp: str | None) -> str:
    """The site's DateTime as the archive keeps it, whole seconds UTC; the
    null date as empty. ("2026-08-09T23:23:00.253Z" -> "2026-08-09T23:23:00Z")"""

    stamp = (stamp or "").strip()
    if not stamp or stamp.startswith("1900-01-01"):
        return ""
    stamp = stamp.rstrip("Z").split(".")[0]
    return stamp + "Z"


def sample_row(r: dict) -> dict:
    sm = r.get("Sample") or {}
    return {"sample_id": str(sm.get("Id", "")), "sample_date": sm.get("SampleDate", ""),
            "sample_time": sm.get("SampleTime", ""),
            "parameter": (r.get("Parameter") or {}).get("Label") or sm.get("ParameterOther", ""),
            "method": (r.get("AnalysisMethod") or {}).get("Label") or sm.get("AnalysisMethodOther", ""),
            "qualifier": sm.get("Qualifier", ""), "result": str(sm.get("Result", "")),
            "units": (r.get("Units") or {}).get("Label") or sm.get("UnitOther", ""),
            "comments": (sm.get("Comments") or "").strip()}


def event_row(r: dict) -> dict:
    return {"station": r.get("StationID", ""), "event_type": r.get("EventType", ""),
            "issued_utc": utc_text(r.get("IssueDateTime")), "lifted_utc": utc_text(r.get("LiftedDateTime")),
            "distance": (r.get("Distance") or "").strip(), "indicator": (r.get("IndicatorDetails") or "").strip(),
            "reason": (r.get("Reason") or "").strip(),
            "public_notification": (r.get("PublicNotification") or "").strip()}


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _append(path: Path, fields, new: list[dict]) -> None:
    if not new:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fresh = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        if fresh:
            writer.writeheader()
        writer.writerows(new)


def store_samples(data_dir: Path, station: str, got: list[dict], seen: str) -> tuple[int, int]:
    """Append each sample not yet archived, by the county's own id. Returns
    (added, conflicts): an id archived with other values keeps the first and
    counts one conflict, never overwritten."""

    path = Path(data_dir) / ARCHIVE / "samples" / f"{station}.csv"
    have = {r["sample_id"]: r for r in _read(path)}
    new, conflicts = [], 0
    for r in sorted(got, key=lambda x: (x["sample_date"], x["sample_time"], x["sample_id"])):
        old = have.get(r["sample_id"])
        if old is None:
            row = {**r, "first_seen_utc": seen}
            have[r["sample_id"]] = row
            new.append(row)
        elif any(old.get(k, "") != r[k] for k in SAMPLE_FIELDS[:-1]):
            conflicts += 1
    _append(path, SAMPLE_FIELDS, new)
    return len(new), conflicts


def store_events(data_dir: Path, got: list[dict], stations, seen: str) -> int:
    """Append each of the stations' events not yet archived, keyed by
    station, type, issue and lift time: the report lists an event once per
    beach group it belongs to, and the groups' rows differ in their free
    text (one Center closure read "1.5 Miles" in one group and "300 ft" in
    another, probe run 8), so the first row seen is kept. A lift time set or
    moved later is a new row, and both are kept."""

    path = Path(data_dir) / ARCHIVE / "events.csv"
    key = lambda r: tuple(r[k] for k in EVENT_KEY)
    have = {key(r) for r in _read(path)}
    new = []
    for r in got:
        if r["station"] in stations and key(r) not in have:
            have.add(key(r))
            new.append({**r, "first_seen_utc": seen})
    new.sort(key=lambda x: (x["station"], x["issued_utc"], x["lifted_utc"]))
    _append(path, EVENT_FIELDS, new)
    return len(new)


def store_status(data_dir: Path, current: dict[str, tuple], seen: str) -> list[str]:
    """Log each station's status when it differs from its last logged one.
    Returns the stations that changed."""

    path = Path(data_dir) / ARCHIVE / "status.csv"
    last: dict[str, tuple] = {}
    for r in _read(path):
        last[r["station"]] = (r["priority"], r["status"])
    new = [{"first_seen_utc": seen, "station": st, "priority": p, "status": label}
           for st, (p, label) in sorted(current.items()) if last.get(st) != (p, label)]
    _append(path, STATUS_FIELDS, new)
    return [r["station"] for r in new]


def read_state(data_dir: Path) -> dict:
    path = Path(data_dir) / ARCHIVE / STATE
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_state(data_dir: Path, state: dict) -> None:
    path = Path(data_dir) / ARCHIVE / STATE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def due(state: dict, now, min_interval_min: float) -> bool:
    last = parse_iso(state.get("last_fetch_utc"))
    return last is None or (now - last).total_seconds() >= min_interval_min * 60


def collect(data_dir: Path = DEFAULT_DATA_DIR, min_interval_min: float = 0) -> tuple[list[str], int]:
    """One collection: each station's samples and status, the stations'
    events from the posting report, and the legend. Skipped while the last
    fetch is under `min_interval_min` old."""

    reg = registry()
    now = utcnow()
    seen = to_iso(now)
    state = read_state(data_dir)
    if not due(state, now, min_interval_min):
        return [(f"Beach water: last fetched {state.get('last_fetch_utc')}, under "
                 f"{min_interval_min:.0f} min ago; not fetched.")], 0
    lines = [f"## Beach water quality ({reg['base']})", "", f"Run at {seen}.", ""]
    state["last_fetch_utc"] = seen
    try:
        client = Client(reg["base"]).start()
        labels = legend(client)
        stations = {v["station"] for v in reg["breaks"].values()}
        current: dict[str, tuple] = {}
        for brk, v in reg["breaks"].items():
            raw = samples(client, v["site"])
            # Only the station's own rows: a filter the county changes must
            # not file another station's results under this one.
            foreign = sorted({str((r.get("Site") or {}).get("StationID")) for r in raw}
                             - {v["station"]})
            got = [sample_row(r) for r in raw if (r.get("Site") or {}).get("StationID") == v["station"]]
            added, conflicts = store_samples(data_dir, v["station"], got, seen)
            p = priority(client, v["site"])
            label = labels.get(p, f"priority {p}") if p is not None else labels.get(2, "Open")
            current[v["station"]] = (str(p) if p is not None else "", label)
            newest = max((r["sample_date"] for r in got), default="none")
            lines.append(f"- {brk} {v['station']} (site {v['site']}): {label}; {len(got)} samples, {added} new, "
                         f"{conflicts} changed since archived (kept as first seen), newest {newest}")
            if foreign:
                lines.append(f"  - rows from other stations: {foreign}")
        ev = [event_row(r) for r in events(client)]
        added = store_events(data_dir, ev, stations, seen)
        changed = store_status(data_dir, current, seen)
        lines.append(f"- posting report: {len(ev)} rows, {added} new event rows at the three")
        if changed:
            lines.append(f"- status changed: {', '.join(changed)}")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError, Refused) as exc:
        state["last_error"] = f"{seen} {type(exc).__name__}: {exc}"
        write_state(data_dir, state)
        denied = "Tunnel connection failed" in str(exc) and "403" in str(exc)
        return lines + [f"FAILED: {type(exc).__name__}: {exc}"], 2 if denied else 1
    state.update({"last_ok_utc": seen, "module_version": client.module_version,
                  "legend": {str(k): v for k, v in sorted(labels.items())},
                  "current": {st: {"priority": p, "status": label} for st, (p, label) in sorted(current.items())}})
    state.pop("last_error", None)
    write_state(data_dir, state)
    return lines, 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Archive the county's beach water quality at Coronado.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--min-interval-min", type=float, default=0,
                        help="Skip when the last fetch is under this many minutes old.")
    args = parser.parse_args(argv)
    lines, code = collect(args.data_dir, args.min_interval_min)
    text = "\n".join(lines)
    print(text)
    write_step_summary(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
