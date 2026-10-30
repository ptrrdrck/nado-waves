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

import http.cookiejar
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

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


def samples(client: Client, site: str, *, filter_var: str = "StationIdFilter") -> list[dict]:
    """A station's samples, as the samples page lists them."""

    return rows(client.aggregate("SampleBlock.GetSamples", {**SAMPLE_VARS, filter_var: site, "SiteId": site}))


def events(client: Client, year: int = 0) -> list[dict]:
    """The county's posting report: every advisory, closure and warning it
    lists, each station once per beach group it belongs to."""

    return rows(client.aggregate("SamplePostingReportBlock.GetSites", {**POSTING_VARS, "YearFilter": year}))
