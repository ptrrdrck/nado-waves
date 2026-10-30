"""What does the County of San Diego's beach water quality site serve?

    python -m collector.probe_beachwater [--path SamplesReport?SiteId=7 ...]

The owner's request (2026-10-30): the County of San Diego Beach & Bay Water
Quality Monitoring Program (DEHQ) samples Coronado at three stations --
Coronado Main Lifeguard Tower (EH-050, Center), Coronado North Beach (EH-060,
North) and Avenida Lunar (IB-079, South) -- and posts results at
`cosdapps.sandiegocounty.gov/sdbeachinfo/SamplesReport?SiteId=7`. The site was
rebuilt in July 2026 and nothing here has seen it: the host is denied at
CONNECT from a Claude session (BRIEFING section 8), so this is an Actions job,
as `probe_sharklab` was.

It answers what the pages are made of and builds nothing on them:

- each page's title, forms (with every option of a select, which is where a
  site list with its IDs would be), tables (headers and rows, verbatim text),
  same-origin links and script sources;
- every line of visible text naming a Coronado station, an advisory, a
  closure or a rain advisory;
- the URLs the site's own scripts name (an `api/` or a `Get...` endpoint is
  what a collector should read, rather than scraping HTML);
- JSON responses, printed.

Run 1 found an OutSystems Reactive app, whose HTML is an empty shell; its
data is read from the screen services its own scripts name (`outsystems`).

Every response is read in full, its byte count reported, and the head of its
markup printed verbatim beside the parse. Exits 2 on a denial, 1 when the
samples page did not parse to a table, 0 when it did.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser

from .common import write_step_summary
from .ndbc import USER_AGENT
from .probe_sharklab import is_denial, is_timeout

BASE = "https://cosdapps.sandiegocounty.gov/sdbeachinfo/"

#: The page the owner gave: Coronado's samples.
SAMPLES = "SamplesReport?SiteId=7"

#: Text worth printing wherever it appears.
KEYWORDS = re.compile(
    r"coronado|EH-0?50|EH-0?60|IB-0?79|avenida lunar|lifeguard|advisory|"
    r"closure|closed|rain|expire|enterococ|coliform|status",
    re.IGNORECASE,
)

#: URL-like strings in a script: absolute same-site paths or API calls.
SCRIPT_URL = re.compile(
    r"""["'`]((?:/sdbeachinfo/|\.\./|\./|api/|/api/)?[A-Za-z0-9_\-/]*"""
    r"""(?:api|Api|API|Get[A-Z][A-Za-z]*|Report|Sample|Site|Beach|Status|"""
    r"""Advisor|Closure)[A-Za-z0-9_\-/.?=&{}$]*)["'`]"""
)

#: One cookie jar for the run: an OutSystems app sets its visitor cookies on
#: the first page and reads them back on every screen service.
JAR = http.cookiejar.CookieJar()
OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(JAR))

SHOWN_ROWS = 25
RAW_HEAD = 6000
MAX_PAGES = 40
MAX_SCRIPTS = 15


@dataclass
class Table:
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)


@dataclass
class Form:
    action: str = ""
    method: str = ""
    inputs: list[str] = field(default_factory=list)
    selects: dict[str, list[str]] = field(default_factory=dict)


class Page(HTMLParser):
    """Titles, tables, forms, links, scripts and visible text, nothing else."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.tables: list[Table] = []
        self.forms: list[Form] = []
        self.links: list[tuple[str, str]] = []
        self.scripts: list[str] = []
        self.inline_scripts: list[str] = []
        self.text: list[str] = []
        self._stack: list[str] = []
        self._cell: list[str] | None = None
        self._row: list[str] | None = None
        self._row_is_head = False
        self._table_stack: list[Table] = []
        self._select: tuple[str, list[str]] | None = None
        self._option: list[str] | None = None
        self._option_value = ""
        self._link: tuple[str, list[str]] | None = None
        self._in_title = False
        self._in_script = False
        self._script_buf: list[str] = []
        self._in_style = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag == "script":
            self._in_script = True
            self._script_buf = []
            if a.get("src"):
                self.scripts.append(a["src"])
        elif tag == "style":
            self._in_style = True
        elif tag == "table":
            self._table_stack.append(Table())
        elif tag == "tr":
            self._row = []
            self._row_is_head = False
        elif tag in ("td", "th"):
            self._cell = []
            if tag == "th":
                self._row_is_head = True
        elif tag == "form":
            self.forms.append(Form(a.get("action") or "", a.get("method") or ""))
        elif tag == "input" and self.forms:
            self.forms[-1].inputs.append(
                f"{a.get('type', 'text')} name={a.get('name')} value={a.get('value', '')!r}"
            )
        elif tag == "select":
            self._select = (a.get("name") or a.get("id") or "?", [])
        elif tag == "option":
            self._option = []
            self._option_value = a.get("value") or ""
        elif tag == "a" and a.get("href"):
            self._link = (a["href"], [])
        elif tag in ("br", "p", "div", "li", "h1", "h2", "h3", "h4", "h5", "span"):
            self.text.append("\n")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "script":
            self._in_script = False
            body = "".join(self._script_buf).strip()
            if body:
                self.inline_scripts.append(body)
        elif tag == "style":
            self._in_style = False
        elif tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
            self.text.append(" | ")
        elif tag == "tr" and self._row is not None and self._table_stack:
            table = self._table_stack[-1]
            if self._row_is_head and not table.headers:
                table.headers = self._row
            elif self._row:
                table.rows.append(self._row)
            self._row = None
        elif tag == "table" and self._table_stack:
            self.tables.append(self._table_stack.pop())
        elif tag == "option" and self._option is not None and self._select:
            self._select[1].append(f"{self._option_value!r}: {' '.join(''.join(self._option).split())}")
            self._option = None
        elif tag == "select" and self._select:
            target = self.forms[-1].selects if self.forms else {}
            target[self._select[0]] = self._select[1]
            if not self.forms:
                self.forms.append(Form("(no form)", "", [], {self._select[0]: self._select[1]}))
            self._select = None
        elif tag == "a" and self._link:
            self.links.append((self._link[0], " ".join("".join(self._link[1]).split())))
            self._link = None
        elif tag in ("p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5"):
            self.text.append("\n")

    def handle_data(self, data):
        if self._in_script:
            self._script_buf.append(data)
            return
        if self._in_style:
            return
        if self._in_title:
            self.title += data
        if self._cell is not None:
            self._cell.append(data)
        if self._option is not None:
            self._option.append(data)
        if self._link is not None:
            self._link[1].append(data)
        self.text.append(data)

    def lines(self) -> list[str]:
        out = []
        for line in "".join(self.text).splitlines():
            line = " ".join(line.split())
            if line:
                out.append(line)
        return out


@dataclass
class Fetched:
    url: str
    ok: bool = False
    denied: bool = False
    status: int | None = None
    content_type: str = ""
    final_url: str = ""
    body: str = ""
    error: str = ""


def fetch(url: str, *, timeout: float = 60.0, body: dict | None = None,
          headers: dict | None = None) -> Fetched:
    """One response, read in full; a POST of `body` as JSON when given.
    Never retried (BRIEFING section 8)."""

    result = Fetched(url=url)
    head = {"User-Agent": USER_AGENT, "Accept": "text/html,application/json,*/*"}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        head["Content-Type"] = "application/json; charset=UTF-8"
    head.update(headers or {})
    request = urllib.request.Request(url, data=data, headers=head)
    try:
        with OPENER.open(request, timeout=timeout) as response:
            result.status = response.status
            result.content_type = response.headers.get("Content-Type", "")
            result.final_url = response.geturl()
            payload = response.read()
    except urllib.error.HTTPError as exc:
        result.status = exc.code
        result.error = f"HTTP {exc.code} {exc.reason}: {exc.read()[:1500]!r}"
        result.denied = exc.code == 403
        return result
    except (urllib.error.URLError, TimeoutError) as exc:
        result.error = f"{exc.__class__.__name__}: {exc}"
        result.denied = is_denial(exc) and not is_timeout(exc)
        return result
    except Exception as exc:  # noqa: BLE001 - network layer
        result.error = f"{exc.__class__.__name__}: {exc}"
        return result
    result.ok = True
    result.body = payload.decode("utf-8", errors="replace")
    return result


def same_site(href: str, base: str) -> str | None:
    url = urllib.parse.urljoin(base, href)
    parts = urllib.parse.urlsplit(url)
    if parts.netloc != urllib.parse.urlsplit(BASE).netloc:
        return None
    if not parts.path.startswith(urllib.parse.urlsplit(BASE).path.rstrip("/")):
        return None
    return urllib.parse.urlunsplit(parts._replace(fragment=""))


def report_page(f: Fetched, *, full: bool, out: list[str]) -> Page | None:
    out.append(f"\n## {f.url}")
    if not f.ok:
        out.append(f"  FAILED: {f.error}")
        return None
    out.append(
        f"  HTTP {f.status}, {len(f.body.encode())} bytes, {f.content_type}"
        + (f", landed on {f.final_url}" if f.final_url and f.final_url != f.url else "")
    )
    if "json" in f.content_type or f.body.lstrip()[:1] in ("{", "["):
        try:
            data = json.loads(f.body)
            out.append("  JSON:\n" + json.dumps(data, indent=1)[: RAW_HEAD * 2])
        except ValueError:
            out.append("  (not JSON) " + f.body[:RAW_HEAD])
        return None
    page = Page()
    page.feed(f.body)
    out.append(f"  title: {page.title.strip()!r}")
    for form in page.forms:
        out.append(f"  form action={form.action!r} method={form.method!r}")
        for i in form.inputs:
            out.append(f"    input {i}")
        for name, options in form.selects.items():
            out.append(f"    select {name}: {len(options)} options")
            for option in options[: 200 if full else 10]:
                out.append(f"      {option}")
    for n, table in enumerate(page.tables):
        out.append(f"  table {n}: {len(table.rows)} rows, headers {table.headers}")
        for row in table.rows[: SHOWN_ROWS if full else 3]:
            out.append(f"    {row}")
        if full and len(table.rows) > SHOWN_ROWS:
            out.append(f"    ... last: {table.rows[-1]}")
    hits = [line for line in page.lines() if KEYWORDS.search(line)]
    out.append(f"  keyword lines: {len(hits)}")
    for line in hits[: 80 if full else 12]:
        out.append(f"    | {line[:300]}")
    if full:
        out.append("  visible text (first 120 lines):")
        for line in page.lines()[:120]:
            out.append(f"    . {line[:300]}")
        out.append(f"  links ({len(page.links)}):")
        for href, text in page.links[:150]:
            out.append(f"    {href!r} {text[:80]!r}")
        out.append(f"  scripts: {page.scripts}")
        for body in page.inline_scripts:
            out.append(f"  inline script ({len(body)} chars):\n{body[:3000]}")
        out.append(f"  raw head ({RAW_HEAD} chars):\n{f.body[:RAW_HEAD]}")
        start = f.body.find("<table")
        if start >= 0:
            out.append(f"  raw first table ({RAW_HEAD} chars):\n{f.body[start:start + RAW_HEAD]}")
    return page


# ------------------------------------------------------------- OutSystems
#
# Run 1 (2026-10-30): every page is the same 2 KB shell -- an OutSystems
# Reactive app, "JavaScript is required" -- so the data is not in any HTML.
# Such an app fetches it as JSON from "screen services": each screen's
# `<module>.<Flow>.<Screen>.mvc.js` names its data actions,
# `callDataAction("Name", "screenservices/...", "<apiVersion>", ...)`, and a
# POST to that path with the module's version and the screen's variables
# returns the screen's data. The module's scripts are listed in
# `moduleservices/moduleinfo`.

#: A screen service call in a script: a data action, a server action, or an
#: aggregate (`callAggregateWithStartIndexAndClientVars("ScreenDataSet...",
#: "screenservices/...", "<apiVersion>", ...)`). Run 2 found the data behind
#: no data action: the screens' blocks live in a second module,
#: CoSD_Beach_Water_CW, and read by aggregates.
OS_CALL = re.compile(
    r"""(call\w*)\(\s*["']([^"']+)["']\s*,\s*["'](screenservices/[^"']+)["']\s*,\s*["']([^"']+)["']"""
)

#: A variable or record attribute's declaration, either runtime's form:
#: this.attr("Name", "nameIn", "Name", mandatory, isInput?, OS.Types.X ...
OS_ATTR = re.compile(
    r"""(?:AttributeInfo|this\.attr|\battr)\(\s*"(\w+)"\s*,\s*"(\w+)"\s*,\s*"(\w+)"\s*,\s*(true|false)\s*,\s*(true|false)\s*,\s*OS\.(?:DataTypes\.DataTypes|Types)\.(\w+)"""
)

#: The anonymous CSRF token OutSystems Reactive apps fall back to (run 2:
#: the runtime's `AnonymousCSRFToken`).
OS_CSRF_DEFAULT = "T6C+9iB49TLra4jEsMeSckDMNhQ="

#: Never called: anything that could write (the site takes alert sign-ups).
OS_WRITES = re.compile(r"subscri|suscri|save|create|update|delete|send|register|insert|remove|login|logout|"
                       r"feedback|captcha", re.IGNORECASE)

#: The scripts read (run 2 listed the manifest): the samples and home
#: screens and blocks, the legend, and the two modules' record types.
OS_SCRIPTS = re.compile(
    r"/scripts/(?:CoSD_Beach_Water_CW\.MainFlow\.(?:Sample\w*|HomeBlockNew|BlockLegend|BlockMarkup|"
    r"HistoricalReportsBlock|ExportBlock|FieldShow)\.mvc|sdbeachinfo\.MainFlow\.(?:SamplesReport|Home|"
    r"SamplePostingReport|HistoricalReports)\.mvc)\.js$"
)

#: Characters of each JSON response printed.
OS_SHOWN = 16000

#: The screen each block is shown on: the server checks a request's
#: `viewName` against the screens it knows ("No role validation found" for
#: a block's own name, run 3).
OS_HOSTS = {"SampleBlock": ["MainFlow.SamplesReport"],
            "SamplePostingReportBlock": ["MainFlow.SamplePostingReport"],
            "HomeBlockNew": ["MainFlow.Home"], "BlockMarkup": ["MainFlow.Home"],
            "BlockLegend": ["MainFlow.Home"], "ExportBlock": ["MainFlow.Home"],
            "HistoricalReportsBlock": ["MainFlow.HistoricalReports"]}

#: An empty value per OutSystems type, for a screen variable the probe does
#: not set. Long integers and decimals travel as strings.
OS_EMPTY = {"LongInteger": "0", "Integer": 0, "Decimal": "0", "Currency": "0", "Text": "", "Boolean": False,
            "Date": "1900-01-01", "DateTime": "1900-01-01T00:00:00", "Time": "00:00:00"}


#: Rows an aggregate is asked for.
OS_MAX_RECORDS = 200


def xlsx_rows(data: bytes, limit: int = 400) -> list[list[str]]:
    """An .xlsx file's first sheet as rows of text, by the standard library
    alone (the runner has no openpyxl)."""

    import io
    import xml.etree.ElementTree as ET
    import zipfile

    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = z.namelist()
        shared = []
        if "xl/sharedStrings.xml" in names:
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{ns['m']}}}t")))
        sheet = min(n for n in names if n.startswith("xl/worksheets/sheet"))
        rows = []
        for row in ET.fromstring(z.read(sheet)).iter(f"{{{ns['m']}}}row"):
            cells = []
            for c in row.findall("m:c", ns):
                v = c.find("m:v", ns)
                text = v.text if v is not None else "".join(t.text or "" for t in c.iter(f"{{{ns['m']}}}t"))
                if c.get("t") == "s" and text is not None:
                    text = shared[int(text)]
                cells.append(f"{c.get('r')}={text}")
            rows.append(cells)
            if len(rows) >= limit:
                break
        return rows


def binaries(node):
    """A response with every base64 file in it read: an .xlsx as its rows,
    anything else as its first bytes."""

    import base64

    if isinstance(node, dict):
        return {k: binaries(v) for k, v in node.items()}
    if isinstance(node, list):
        return [binaries(v) for v in node]
    if isinstance(node, str) and len(node) > 200 and re.fullmatch(r"[A-Za-z0-9+/=\s]+", node):
        try:
            raw = base64.b64decode(node)
        except ValueError:
            return node[:200]
        if raw[:2] == b"PK":
            try:
                return {"xlsx_rows": xlsx_rows(raw)}
            except Exception as exc:  # noqa: BLE001 - report it
                return f"(zip, {len(raw)} bytes, unread: {exc})"
        return f"({len(raw)} bytes: {raw[:300]!r})"
    return node


def module_url(key: str, version: str) -> str:
    """A manifest key ("/sdbeachinfo/scripts/x.js") and its version as a URL."""

    return urllib.parse.urljoin(f"https://{urllib.parse.urlsplit(BASE).netloc}", key) + version


def outsystems(out: list[str], index_token: str, site_id: int) -> int:
    """The scripts behind the samples and home screens, their screen
    services, and each read-only one called. Returns how many answered."""

    base = BASE.rstrip("/")
    info = fetch(f"{base}/moduleservices/moduleinfo?{index_token}")
    out.append(f"\n# OutSystems moduleinfo: {info.status} {info.error or ''}")
    manifest = {}
    if info.ok:
        try:
            manifest = json.loads(info.body).get("manifest", {})
        except ValueError:
            out.append(info.body[:2000])
    urls = manifest.get("urlVersions", {}) or {}
    version = fetch(f"{base}/moduleservices/moduleversioninfo?{index_token}")
    module_version = ""
    if version.ok:
        try:
            module_version = json.loads(version.body).get("versionToken", "")
        except ValueError:
            pass
    out.append(f"  {len(urls)} urlVersions; moduleversioninfo {module_version!r} {version.error}")

    read = [k for k in sorted(urls) if OS_SCRIPTS.search(k)]
    out.append(f"\n# Scripts read: {len(read)}")
    calls: list[tuple[str, str, str, str, list]] = []  # (script, kind, name, path, api, attrs)
    for key in read:
        f = fetch(module_url(key, urls[key]))
        if not f.ok:
            out.append(f"  {key}: {f.error}")
            continue
        found = OS_CALL.findall(f.body)
        attrs = OS_ATTR.findall(f.body)
        out.append(f"\n## {key}: {len(f.body)} chars, {len(found)} screen services, {len(attrs)} attributes")
        if key.endswith(".model.js"):
            # Record types: each type's attributes, by the type they open.
            for name, var, ext, mandatory, flag, dtype in attrs[:400]:
                out.append(f"    {ext}: {dtype}")
            names = sorted(set(re.findall(r'"(\w*(?:Sample|Site|Status|Advis|Closure|Result|Station|Beach)\w*)"',
                                          f.body)))
            out.append(f"    names: {names[:200]}")
            continue
        for name, var, ext, mandatory, flag, dtype in attrs[:150]:
            out.append(f"    attr {ext} ({var}, {dtype}, mandatory={mandatory}, {flag})")
        for kind, name, path, api in found:
            out.append(f"    {kind} {name}: {path} api {api}")
            calls.append((key, kind, name, path, api, attrs))
            i = f.body.find(path)
            out.append(f"      before: {f.body[max(0, i - 700):i]!r}")
        words = sorted(set(re.findall(r'"([^"]{0,80}(?:Advisory|Closure|Closed|Open|Rain|Expir|Status|Result|'
                                      r'Enterococ|Coliform|Fecal)[^"]{0,80})"', f.body)))
        if words:
            out.append(f"    strings: {words[:120]}")

    # How the runtime builds an aggregate's request, and every header it sets.
    runtime = next((k for k in urls if k.endswith("/OutSystems.js")), None)
    rt = fetch(module_url(runtime, urls[runtime])) if runtime else None
    if rt and rt.ok:
        for pat in (r"callAggregateWithStartIndexAndClientVars\s*=\s*function", r"\.callAggregate\w*=function",
                    r"viewName", r"screenData", r"No role validation", r"rolesInfo", r"setHeader\("):
            hits = [m.start() for m in re.finditer(pat, rt.body)][:4]
            for i in hits:
                out.append(f"  runtime [{pat}]: {rt.body[max(0, i - 300):i + 500]!r}")
    out.append(f"  cookies: {[c.name for c in JAR]}")

    answered = 0
    out.append(f"\n# Calling read-only screen services ({len(calls)} found)")
    for key, kind, name, path, api, attrs in calls:
        # An allow-list (run 3 called a server action named MigrateSample on
        # a deny-list, which the server refused for want of a role): only
        # aggregates, data actions and server actions named Get...
        reads = kind.startswith("callAggregate") or kind == "callDataAction" or name.startswith("Get")
        if not reads or OS_WRITES.search(name) or "/FieldShow/" in path or "StormDrain" in name:
            out.append(f"  SKIP {kind} {name}")
            continue
        block = path.split("/")[3]
        views = OS_HOSTS.get(block, []) + [f"MainFlow.{block}"]
        variables, lists = {}, {}
        for _, var, ext, _, _, dtype in attrs:
            value = OS_EMPTY.get(dtype, "")
            if dtype in ("Record", "RecordList"):
                if not var.endswith(("Aggr", "DataAct")):
                    lists[ext] = [] if dtype == "RecordList" else {}
                continue
            if "siteid" in ext.lower():
                value = str(site_id) if dtype == "LongInteger" else site_id
            if ext == "MaxRecords":
                value = 100
            if ext == "isPublic":
                value = True
            variables[ext] = value
        done = False
        for view in views:
            # Run 4: an aggregate without its paging answered "Failed to parse
            # JSON request content"; the runtime sends it as inputParameters.
            for screen_vars in (variables, {**variables, **lists}):
                body = {"versionInfo": {"moduleVersion": module_version, "apiVersion": api}, "viewName": view}
                if kind.startswith("callServerAction"):
                    body["inputParameters"] = {}
                else:
                    body["screenData"] = {"variables": screen_vars}
                    if kind.startswith("callAggregate"):
                        body["inputParameters"] = {"StartIndex": 0, "MaxRecords": OS_MAX_RECORDS}
                f = fetch(f"{base}/{path}", body=body, headers={"X-CSRFToken": OS_CSRF_DEFAULT})
                got = {}
                try:
                    got = json.loads(f.body if f.ok else f.error.split(": ", 1)[-1].strip("b'"))
                except ValueError:
                    pass
                err = (got.get("exception") or {}).get("message", "") or (f.error[:300] if not f.ok else "")
                out.append(f"\n  {kind} {name} as {view}: HTTP {f.status} {err}")
                if f.ok and not err:
                    answered += 1
                    done = True
                    out.append(f"    sent variables: {json.dumps(screen_vars)[:2000]}")
                    out.append(json.dumps(binaries(got), indent=1)[:OS_SHOWN])
                    break
                if kind.startswith("callServerAction") or "parse" not in err:
                    break
            if done:
                break
    return answered


# ------------------------------------------------------------- Coronado
#
# Run 5: every aggregate answered once called as its host screen with its
# paging. The samples aggregate ignored SiteId (it returned every station's
# first results, from May 2026); the posting report lists each advisory,
# closure and warning by station; the home screen's marker block reads one
# site's status. Run 6 reads just Coronado's three, compactly, through the
# collector's own client.

def _short(r: dict) -> str:
    return json.dumps(r, separators=(",", ":"), ensure_ascii=False)[:600]


def coronado(out: list[str]) -> int:
    """Run 7: what run 6 left open. An ACTIVE event's shape (none at
    Coronado on 30 Oct; Silver Strand's IB-068 and IB-070 were closed), the
    advisory categories by id, the posting report paged past its 1000-row
    cap, and North's and Center's samples (run 6's log lost its head)."""

    from . import beachwater as bw

    reg = bw.registry()
    client = bw.Client(reg["base"]).start()
    out.append(f"\n# Coronado through collector.beachwater: module {client.module_version}")
    ours = {v["station"] for v in reg["breaks"].values()}
    found = 0

    for brk, v in reg["breaks"].items():
        got = bw.samples(client, v["site"])
        stations = sorted({(r.get("Site") or {}).get("StationID") for r in got})
        params = sorted({((r.get("Parameter") or {}).get("Label"), (r.get("AnalysisMethod") or {}).get("Label"),
                          (r.get("Units") or {}).get("Label")) for r in got})
        dates = sorted((r.get("Sample") or {}).get("SampleDate", "") for r in got)
        found += stations == [v["station"]]
        out.append(f"\n## {brk} {v['station']} samples: {len(got)}, stations {stations}, {params}, "
                   f"{dates[:1]}..{dates[-1:]}, distinct dates {len(set(dates))}")
        quals = sorted({(r.get("Sample") or {}).get("Qualifier") for r in got})
        types = sorted({(r.get("Sample") or {}).get("SampleType") for r in got})
        out.append(f"  qualifiers {quals}, sample types {types}")
        for r in sorted(got, key=lambda r: ((r.get("Sample") or {}).get("SampleDate", ""),
                                            (r.get("Sample") or {}).get("SampleTime", "")))[-8:]:
            sm = r.get("Sample") or {}
            out.append(f"  {sm.get('Id')} {sm.get('SampleDate')} {sm.get('SampleTime')} "
                       f"{sm.get('Qualifier')}{sm.get('Result')} comments={sm.get('Comments')!r}")

    total, page = 0, 0
    keyed = set()
    while page < 30:
        got = bw.rows(client.aggregate("SamplePostingReportBlock.GetSites", bw.POSTING_VARS,
                                       max_records=1000, start=page * 1000))
        total += len(got)
        for r in got:
            keyed.add((r.get("StationID"), r.get("EventType"), r.get("IssueDateTime"), r.get("LiftedDateTime")))
        out.append(f"\n## posting report page {page}: {len(got)} rows, first issued "
                   f"{got[0].get('IssueDateTime') if got else None}, last {got[-1].get('IssueDateTime') if got else None}")
        if len(got) < 1000:
            break
        page += 1
    mine = sorted(k for k in keyed if k[0] in ours)
    out.append(f"  {total} rows in all, {len(keyed)} distinct events, {len(mine)} at Coronado's three")
    for year in (2026, 2025):
        got = bw.rows(client.aggregate("SamplePostingReportBlock.GetSites", {**bw.POSTING_VARS, "YearFilter": year}))
        out.append(f"  YearFilter {year}: {len(got)} rows")

    for site, name in (("118", "Silver Strand - Guard Shack (IB-068)"), ("120", "Silver Strand N End (IB-070)"),
                       ("7", "Center")):
        for svc in ("BlockMarkup.GetEventsIsActive", "BlockMarkup.GetEvents"):
            got = client.aggregate(svc, {"SiteId": site}, max_records=50)
            out.append(f"\n## {svc} site {site} {name}: {len(bw.rows(got))} rows")
            for r in bw.rows(got):
                if "Site" in r:
                    r = {**r, "Site": {k: r["Site"].get(k) for k in ("StationID", "LocationName")}}
                out.append("  " + json.dumps(r, ensure_ascii=False)[:3000])

    # The advisory categories: named in the module's model as static records.
    base = reg["base"]
    page_html = client._get(f"{base}/")
    token = (re.search(r'indexVersionToken\s*=\s*"([^"]+)"', page_html) or [None, ""])[1]
    manifest = json.loads(client._get(f"{base}/moduleservices/moduleinfo?{token}"))["manifest"]
    root = "/".join(base.split("/", 3)[:3])
    for key, ver in manifest["urlVersions"].items():
        if not re.search(r"/scripts/(sdbeachinfo|CoSD_Beach_Water_C[SW])\.model\.js$", key):
            continue
        js = client._get(root + key + ver)
        for word in ("generalRainAdvisory", "bacterialExceedanceAdvisory", "precautionaryAdvisory", "Closure",
                     "CategoryId"):
            for m in list(re.finditer(word, js))[:3]:
                out.append(f"  {key} [{word}]: {js[max(0, m.start() - 400):m.start() + 400]!r}")
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--path", action="append", default=[],
                        help="extra path under the site, printed in full (repeatable)")
    parser.add_argument("--site", type=int, default=7, help="SiteId passed to the screen services")
    parser.add_argument("--discover", action="store_true",
                        help="the whole discovery (runs 1-5) instead of Coronado's records (run 6)")
    parser.add_argument("--no-crawl", action="store_true",
                        help="only the root, the samples page and --path pages")
    args = parser.parse_args(argv)

    out: list[str] = [f"# Beach water quality probe: {BASE}"]
    if not args.discover:
        try:
            found = coronado(out)
        except (urllib.error.URLError, TimeoutError) as exc:
            out.append(f"FAILED: {exc}")
            print("\n".join(out))
            return 2 if is_denial(exc) else 1
        text = "\n".join(out)
        print(text)
        write_step_summary("```\n" + text[:900_000] + "\n```")
        return 0 if found else 1
    full_urls = [BASE, urllib.parse.urljoin(BASE, SAMPLES)]
    full_urls += [urllib.parse.urljoin(BASE, p) for p in args.path]

    seen: set[str] = set()
    pages: dict[str, Page] = {}
    denied = False
    samples_tables = 0
    for url in full_urls:
        f = fetch(url)
        seen.add(url)
        denied |= f.denied
        page = report_page(f, full=True, out=out)
        if page:
            pages[url] = page
            if url.endswith(SAMPLES):
                samples_tables = sum(1 for t in page.tables if t.rows)

    if denied and not pages:
        out.append("\nDENIED: every page was refused before HTTP. Run this on Actions.")
        print("\n".join(out))
        write_step_summary("\n".join(out)[:900_000])
        return 2

    # The scripts the pages load, for the URLs the site calls itself.
    script_urls: list[str] = []
    for url, page in pages.items():
        for src in page.scripts:
            s = urllib.parse.urljoin(url, src)
            if s not in script_urls and urllib.parse.urlsplit(s).netloc == urllib.parse.urlsplit(BASE).netloc:
                script_urls.append(s)
    out.append(f"\n# Same-site scripts ({len(script_urls)})")
    named: set[str] = set()
    for s in script_urls[:MAX_SCRIPTS]:
        f = fetch(s)
        if not f.ok:
            out.append(f"  {s}: {f.error}")
            continue
        found = sorted(set(SCRIPT_URL.findall(f.body)))
        out.append(f"  {s}: {len(f.body)} chars, {len(found)} URL-like strings")
        for item in found[:60]:
            out.append(f"    {item}")
            named.add(item)
    for page in pages.values():
        for body in page.inline_scripts:
            for item in SCRIPT_URL.findall(body):
                named.add(item)
    out.append(f"\n# URL-like strings named by scripts ({len(named)})")
    for item in sorted(named):
        out.append(f"  {item}")

    if not args.no_crawl:
        queue: list[str] = []
        for url, page in pages.items():
            for href, _ in page.links:
                target = same_site(href, url)
                if target and target not in seen and target not in queue:
                    queue.append(target)
        out.append(f"\n# One level of same-site links ({len(queue)}, first {MAX_PAGES})")
        for url in queue[:MAX_PAGES]:
            seen.add(url)
            report_page(fetch(url), full=False, out=out)

    token = ""
    for page in pages.values():
        for body in page.inline_scripts:
            m = re.search(r'indexVersionToken\s*=\s*"([^"]+)"', body)
            if m:
                token = m.group(1)
    answered = outsystems(out, token, args.site)

    out.append(f"\nSamples page tables with rows: {samples_tables}; screen services answered: {answered}")
    text = "\n".join(out)
    print(text)
    write_step_summary("```\n" + text[:900_000] + "\n```")
    return 0 if samples_tables or answered else 1


if __name__ == "__main__":
    sys.exit(main())
