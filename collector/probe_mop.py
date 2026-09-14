"""Does CDIP publish MOP history, and is it a forecast archive or a hindcast?

    python -m collector.probe_mop

Why this matters. The only structure worth playing that three years of buoy
archive turned up is swell propagation: an offshore sentinel leads the nearshore
stations by 1–6 hours, and predicting your own break from it beats persistence
by ~6% out of sample at the southern stations. That is under the bar — but the
test was against the wrong opponent. CDIP's MOP model does exactly this
propagation professionally, so the real question is whether a person with local
knowledge can beat MOP, not whether they can beat persistence.

**The distinction this probe exists to make.** Two different things get called
"MOP history":

* a **forecast archive** — what the model predicted *at the time*, before the
  waves arrived. This is the only thing that can be a scoring baseline, for the
  same reason `data/observations/` and not `data/historical/` resolves a round.
* a **hindcast** — the model re-run afterwards with the inputs it turned out to
  have. Far more accurate, and worthless as an opponent: scoring players against
  it would mean scoring them against a number that did not exist when they
  called.

A hindcast-only archive means the baseline has to be captured live from here on,
which is the unrecoverable-history problem again.

Rather than guessing deep URLs — which produced two wrong verdicts earlier in
this project — this crawls the THREDDS catalogue and reports what is actually
there.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urljoin
from dataclasses import dataclass, field

from .common import write_step_summary
from .ndbc import USER_AGENT

#: Candidate starting points, tried in order. The first version of this probe
#: guessed a single root and got a 404 — the same "don't guess deep URLs"
#: mistake it exists to avoid. The THREDDS server root is the canonical entry
#: point; the archive catalogue is known to respond because an earlier probe
#: fetched its HTML form.
ROOTS = (
    "https://thredds.cdip.ucsd.edu/thredds/catalog.xml",
    "https://thredds.cdip.ucsd.edu/thredds/catalog/cdip/archive/catalog.xml",
    "https://thredds.cdip.ucsd.edu/thredds/catalog/cdip/catalog.xml",
)

#: Branches worth descending into once past the top. Near the root everything
#: is followed, because the interesting names only appear deeper and filtering
#: too early is how a crawl reports "nothing found" about a place it never
#: looked.
INTERESTING = re.compile(r"mop|model|forecast|nowcast|hindcast|alongshore", re.I)

#: Depth below which every branch is followed regardless of its name.
FOLLOW_ALL_DEPTH = 1

#: Politeness. This is a university research server, not a CDN, and running
#: this probe four times in ten minutes got every request refused — including a
#: URL that had answered 200 three minutes earlier. Crawl slowly, crawl once,
#: and treat a sudden blanket failure as "we are the problem", not as a finding
#: about CDIP.
MAX_REQUESTS = 20
MAX_DEPTH = 3
REQUEST_DELAY = 2.0

CATALOG_REF = re.compile(
    r'<catalogRef[^>]*xlink:href="([^"]+)"[^>]*xlink:title="([^"]+)"', re.I
)
CATALOG_REF_ALT = re.compile(
    r'<catalogRef[^>]*xlink:title="([^"]+)"[^>]*xlink:href="([^"]+)"', re.I
)
DATASET = re.compile(r'<dataset[^>]*name="([^"]+)"', re.I)
TIME_COVERAGE = re.compile(r"<(start|end)>([^<]+)</\1>", re.I)


#: What a 403 actually means when the session runs behind a policy-enforcing
#: egress proxy, which is how this project is usually run.
#:
#: Established 2026-09-13. An earlier run crawled four roots in ten minutes,
#: watched every one start failing, concluded CDIP was rate-limiting us, and
#: added a 2 s delay. **That diagnosis cannot be supported.** Re-probed slowly,
#: both `thredds.cdip.ucsd.edu` and `cdip.ucsd.edu` fail at CONNECT with a
#: proxy-side 403 — an organisation egress-policy denial. Backing off does not
#: move it, and the polite delay added as the "fix" fixed nothing. The delay is
#: still good manners and stays; the explanation attached to it was wrong.
#:
#: The tell is that the proxy refuses the tunnel before any HTTP request is
#: sent, so the failure surfaces as a connection error rather than a status
#: code — the host looks dead rather than forbidden. Check
#: `$HTTPS_PROXY/__agentproxy/status`, whose recentRelayFailures names the host
#: and the reason. Do not retry a policy denial and do not route around it:
#: report the blocked host.
DENIAL_NOTE = (
    "  **This looks like an egress-policy denial, not throttling.** Check "
    "$HTTPS_PROXY/__agentproxy/status -> recentRelayFailures for the host and "
    "reason. Backing off will not help; report the blocked host instead."
)


@dataclass
class Node:
    title: str
    url: str
    depth: int
    datasets: list[str] = field(default_factory=list)
    children: list[str] = field(default_factory=list)
    coverage: list[str] = field(default_factory=list)
    error: str = ""


def resolutions(base: str, href: str) -> list[str]:
    """Every plausible absolute form of a catalogRef href, best guess first.

    `urljoin` does the real work. Hand-rolled string surgery got this wrong
    twice: CDIP's root catalogue uses ROOT-RELATIVE hrefs
    (`/thredds/catalog/cdip/model/catalog.xml`), and stripping their leading
    slash turns them into relative paths that resolve to
    `/thredds/thredds/catalog/...` and 404. The fallbacks only exist for servers
    that use bare relative hrefs.
    """

    href = href.strip()
    if href.startswith("http"):
        return [href]

    server = "/".join(base.split("/", 3)[:3])
    bare = href.lstrip("./")
    out = [
        urljoin(base, href),                  # correct for relative AND /root-relative
        f"{server}/thredds/catalog/{bare}",   # THREDDS convention, bare hrefs
        f"{server}/thredds/{bare}",
    ]
    seen, unique = set(), []
    for url in out:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


def fetch(url: str, timeout: float, delay: float = REQUEST_DELAY) -> str:
    time.sleep(delay)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(2_000_000).decode("utf-8", errors="replace")


def find_root(timeout: float) -> tuple[str, str]:
    """First responding catalogue, and a note about what was tried."""

    tried = []
    throttled = denied = False
    for candidate in ROOTS:
        try:
            fetch(candidate, timeout)
            return candidate, f"entry point: {candidate}"
        except urllib.error.HTTPError as exc:
            # Report the status, not just the exception class. 404 means the
            # path is wrong; 429/503 means we are being throttled; 403 is
            # something else again and used to be lumped in with throttling
            # here, which sent this project backing off for hours against a
            # wall that backing off cannot move. See DENIAL_NOTE.
            tried.append(f"{candidate} -> HTTP {exc.code} {exc.reason}")
            if exc.code in (429, 503):
                throttled = True
            elif exc.code == 403:
                denied = True
        except Exception as exc:  # noqa: BLE001
            tried.append(f"{candidate} -> {exc.__class__.__name__}: {exc}")
            # A tunnelled request refused by an egress proxy never reaches the
            # HTTP layer at all: curl reports 000, urllib raises URLError, and
            # the host looks dead rather than forbidden.
            if isinstance(exc, urllib.error.URLError):
                denied = True
    note = "no catalogue root responded: " + "; ".join(tried)
    if denied:
        note += DENIAL_NOTE
    if throttled:
        note += (
            "  **429/503 across roots is throttling: back off for a few hours "
            "before probing again.**"
        )
    return "", note


def crawl(timeout: float = 30.0) -> tuple[list[Node], str]:
    root, note = find_root(timeout)
    if not root:
        return [], note

    seen: set[str] = set()
    queue = [("root", root, 0)]
    nodes: list[Node] = []
    requests = 0

    while queue and requests < MAX_REQUESTS:
        title, url, depth = queue.pop(0)
        key = url[0] if isinstance(url, list) else url
        if key in seen:
            continue
        seen.add(key)
        node = Node(title=title, url=url, depth=depth)
        nodes.append(node)

        body = None
        for candidate in url if isinstance(url, list) else [url]:
            if requests >= MAX_REQUESTS:
                break
            try:
                body = fetch(candidate, timeout)
                requests += 1
                node.url = candidate
                break
            except urllib.error.HTTPError as exc:
                requests += 1
                node.error = f"HTTP {exc.code} {exc.reason}"
            except Exception as exc:  # noqa: BLE001 - a probe reports, never raises
                requests += 1
                node.error = f"{exc.__class__.__name__}: {exc}"
        if body is None:
            continue
        node.error = ""

        refs = CATALOG_REF.findall(body)
        refs = [(h, t) for h, t in refs] or [
            (h, t) for t, h in CATALOG_REF_ALT.findall(body)
        ]
        node.children = [t for _, t in refs]
        node.datasets = DATASET.findall(body)[:25]
        node.coverage = [f"{k}={v}" for k, v in TIME_COVERAGE.findall(body)][:6]

        if depth < MAX_DEPTH:
            for href, child_title in refs:
                follow = (
                    depth < FOLLOW_ALL_DEPTH
                    or INTERESTING.search(child_title)
                    or INTERESTING.search(href)
                )
                if follow:
                    queue.append(
                        (child_title, resolutions(node.url, href), depth + 1)
                    )
    return nodes, note


def classify(text: str) -> str:
    lowered = text.lower()
    if "hindcast" in lowered:
        return "HINDCAST (re-run after the fact — cannot be a baseline)"
    if "forecast" in lowered:
        return "forecast (check whether past runs are retained)"
    if "nowcast" in lowered:
        return "nowcast (check whether past runs are retained)"
    return ""


def format_report(nodes: list[Node], note: str = "") -> str:
    lines = [
        "## CDIP MOP probe",
        "",
        "Looking for whether MOP output is published with history, and if so "
        "whether it is a **forecast archive** (what the model said at the time — "
        "usable as a scoring baseline) or a **hindcast** (re-run afterwards with "
        "known inputs — not usable, for the same reason the NDBC historical "
        "archive cannot resolve a round).",
        "",
        f"Crawled {len(nodes)} catalogue nodes. {note}",
        "",
    ]

    reached = [n for n in nodes if not n.error]
    if not reached:
        lines.append("**Nothing reachable.** " + (nodes[0].error if nodes else ""))
        return "\n".join(lines)

    lines += ["| Node | Depth | Sub-catalogues | Datasets | Note |",
              "| --- | ---: | ---: | ---: | --- |"]
    for node in nodes:
        note = node.error or classify(node.title + " " + " ".join(node.datasets))
        lines.append(
            f"| {node.title[:44]} | {node.depth} | {len(node.children)} | "
            f"{len(node.datasets)} | {note} |"
        )

    lines += ["", "### Detail", ""]
    for node in nodes:
        if node.error:
            tried = node.url if isinstance(node.url, str) else " , ".join(node.url)
            lines.append(f"**{node.title}** — failed: {node.error}  ")
            lines.append(f"tried `{tried}`  ")
            lines.append("")
            continue
        lines.append(f"**{node.title}** — `{node.url}`  ")
        if node.coverage:
            lines.append(f"time coverage: {', '.join(node.coverage)}  ")
        if node.children:
            lines.append(f"sub-catalogues: {', '.join(node.children[:14])}  ")
        if node.datasets:
            lines.append(f"datasets: {', '.join(node.datasets[:14])}  ")
        lines.append("")

    blob = " ".join(n.title for n in nodes) + " " + " ".join(
        d for n in nodes for d in n.datasets
    )
    lines += ["### Read", ""]
    if re.search(r"hindcast", blob, re.I):
        lines.append(
            "A **hindcast** product is present. Useful for studying the physics, "
            "**not** usable as a scoring baseline: it is the model re-run with "
            "inputs it did not have at the time, so players would be scored "
            "against a number that did not exist when they called."
        )
        lines.append("")
    if re.search(r"mop", blob, re.I):
        lines.append(
            "MOP output is published here. The remaining question the catalogue "
            "cannot answer: are **past forecast runs retained**, or only the "
            "current one? If only the current one, the baseline has to be "
            "archived live from today — the unrecoverable-history problem again, "
            "and the argument for starting that archive now rather than after "
            "deciding."
        )
    else:
        lines.append(
            "No MOP dataset surfaced in the branches crawled. Either it lives "
            "outside THREDDS (CDIP serves some products through its own web "
            "endpoints) or the crawl did not reach it. Not a negative result — "
            "an inconclusive one."
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe CDIP for MOP history.")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)

    nodes, note = crawl(timeout=args.timeout)
    report = format_report(nodes, note)
    print(report)
    write_step_summary(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
