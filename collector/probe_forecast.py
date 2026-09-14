"""Find out which public forecast sources actually carry nearshore water temp.

    python -m collector.probe_forecast

Reconnaissance, not an archiver. SPEC section 3 proposes a published forecast as
the scoring baseline, but section 2 chose water temperature precisely *because*
"no public model forecasts it well". If no usable public forecast exists, option
B is off the table, persistence becomes the baseline by default, and the "beat
the forecast" pitch needs rewording. That has to be settled with facts before an
archiver is written against an API that may not carry the field.

Three rules, each learned from the first run of this probe getting it wrong:

1. **Reachable is not usable.** The NWS coastal text product returned HTTP 200
   and content dated eighteen months earlier. A baseline archiver that trusted a
   200 would have silently recorded a 2025 forecast as today's opponent. Every
   candidate is therefore dated, and a stale source is a failed source.
2. **A substring match is not a field.** Searching a directory listing for
   "rtofs" matches the page title; searching an ERDDAP index for "griddap"
   matches a column header. Match strings must be specific enough that a hit
   means the data is actually there.
3. **Never truncate before searching.** The first run capped reads at 200 KB and
   reported "field not found" on a body that was cut off at exactly the cap.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .common import write_step_summary
from .ndbc import USER_AGENT

#: A representative SoCal nearshore point (La Jolla / Torrey Pines).
LAT, LON = 32.87, -117.25

#: Read the whole body before searching it. Bodies larger than this are a
#: finding in themselves, not something to silently cut short.
MAX_BYTES = 8_000_000

#: A forecast older than this is not a forecast.
FRESH_WITHIN_HOURS = 30.0

MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
# Digit-boundary lookarounds, not \b: an ISO timestamp is "2026-09-13T06:00",
# and there is no word boundary between the "3" and the "T", so \b would miss
# every timestamp in every JSON API we might archive.
DATE_PATTERNS = (
    re.compile(r"(?<!\d)(20\d{2})-(\d{2})-(\d{2})(?!\d)"),
    re.compile(rf"\b({MONTHS})\w*\s+(\d{{1,2}})\s+(20\d{{2}})\b", re.IGNORECASE),
    re.compile(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)"),
)


@dataclass
class Candidate:
    name: str
    url: str
    looking_for: tuple[str, ...]
    operator: str
    #: Whether this is a NOAA product. A typed flag, not a substring search on
    #: `operator` — "Open-Meteo (THIRD PARTY, not NOAA)" contains "NOAA", and
    #: sniffing the prose counted a third-party source as first-party.
    noaa: bool = True
    notes: str = ""
    follow: str | None = None
    json_preview: tuple[str, ...] = ()


@dataclass
class Result:
    candidate: Candidate
    status: str = ""
    content_type: str = ""
    size: int = 0
    elapsed_ms: int = 0
    found: tuple[str, ...] = field(default_factory=tuple)
    sample: str = ""
    error: str = ""
    followed_url: str = ""
    truncated: bool = False
    dated: datetime | None = None
    date_source: str = ""
    preview: dict = field(default_factory=dict)

    @property
    def reachable(self) -> bool:
        return not self.error and self.status.startswith("2")

    def age_hours(self, now: datetime) -> float | None:
        if self.dated is None:
            return None
        return (now - self.dated).total_seconds() / 3600.0

    def is_stale(self, now: datetime) -> bool | None:
        age = self.age_hours(now)
        return None if age is None else age > FRESH_WITHIN_HOURS

    def verdict(self, now: datetime) -> str:
        if not self.reachable:
            return "unreachable"
        if self.truncated:
            return "inconclusive (truncated)"
        if not self.found:
            return "no target field"
        if self.is_stale(now):
            return "STALE DATA"
        if self.is_stale(now) is None:
            return "field present, undated"
        return "usable"


def sniff_date(text: str, headers: dict, now: datetime) -> tuple[datetime | None, str]:
    """The newest date mentioned anywhere in the body.

    Not an issue-time: a forecast payload is full of future valid-times, and the
    newest of those is the forecast horizon. It is deliberately the *newest*
    date, because the question being asked is only "does this content know about
    the present" — which is what separates a live product from the 18-month-old
    cached text the first probe run swallowed.

    Content beats headers, because a CDN will happily serve a fresh
    Last-Modified over stale bytes.
    """

    best: datetime | None = None
    for pattern in DATE_PATTERNS:
        for match in pattern.finditer(text[:200_000]):
            groups = match.groups()
            try:
                if groups[0][:2] == "20" and len(groups[0]) == 4:
                    year, a, b = int(groups[0]), int(groups[1]), int(groups[2])
                    candidate = datetime(year, a, b, tzinfo=timezone.utc)
                else:
                    month = 1 + "jan feb mar apr may jun jul aug sep oct nov dec".split().index(
                        groups[0][:3].lower()
                    )
                    candidate = datetime(
                        int(groups[2]), month, int(groups[1]), tzinfo=timezone.utc
                    )
            except (ValueError, IndexError):
                continue
            if candidate > now + timedelta(days=10):
                continue  # a forecast valid-time, not an issue-time
            if best is None or candidate > best:
                best = candidate
    if best is not None:
        return best, "content"

    for header in ("Last-Modified", "Date"):
        raw = headers.get(header)
        if not raw:
            continue
        try:
            from email.utils import parsedate_to_datetime

            return parsedate_to_datetime(raw), f"{header} header"
        except (TypeError, ValueError):
            continue
    return None, ""


CANDIDATES = [
    Candidate(
        name="NWS gridpoint forecast",
        url=f"https://api.weather.gov/points/{LAT},{LON}",
        looking_for=('"waterTemperature"', '"seaSurfaceTemperature"'),
        operator="NOAA / NWS",
        notes="Read in full this time. If waterTemperature is absent from the "
              "whole gridpoint payload, NWS does not publish it for this point.",
        follow="properties.forecastGridData",
    ),
    Candidate(
        name="NWS marine zone forecast (PZZ750, API)",
        url="https://api.weather.gov/zones/forecast/PZZ750/forecast",
        looking_for=("water temp", "Water temp", "WATER TEMP"),
        operator="NOAA / NWS",
        notes="The API equivalent of the coastal text product, which served "
              "18-month-old content over HTTP 200 on the first probe run.",
    ),
    Candidate(
        name="CO-OPS water temperature (San Diego 9410170)",
        url=(
            "https://api.tidesandcurrents.noaa.gov/api/datagetter?"
            "product=water_temperature&application=beat_the_buoy&"
            "date=latest&station=9410170&time_zone=gmt&units=metric&format=json"
        ),
        looking_for=('"v"',),
        operator="NOAA / CO-OPS",
        notes="Observations, not a forecast. Returned 403 on the first run; "
              "retried with a corrected application parameter.",
        json_preview=("data",),
    ),
    Candidate(
        name="NOMADS RTOFS (dated model cycles)",
        url="https://nomads.ncep.noaa.gov/pub/data/nccf/com/rtofs/prod/",
        looking_for=("rtofs.20",),
        operator="NOAA / NCEP",
        notes="Match tightened to rtofs.YYYYMMDD so it cannot pass on the page "
              "title alone. Even if present, output is GRIB/NetCDF at ~9km — "
              "coarse for nearshore and needs a dependency we do not have.",
    ),
    Candidate(
        name="ERDDAP search for SST forecast datasets",
        url=(
            "https://coastwatch.pfeg.noaa.gov/erddap/search/index.json?"
            "searchFor=sea+surface+temperature+forecast"
        ),
        looking_for=("datasetID", "sst"),
        operator="NOAA / CoastWatch",
        notes="A real dataset search rather than the index page. ERDDAP serves "
              "CSV the stdlib can parse; the open question is whether any "
              "dataset is a forecast rather than an analysis of the past.",
    ),
    Candidate(
        name="Open-Meteo Marine",
        url=(
            f"https://marine-api.open-meteo.com/v1/marine?latitude={LAT}&"
            f"longitude={LON}&hourly=sea_surface_temperature&forecast_days=2"
        ),
        looking_for=('"sea_surface_temperature"',),
        operator="Open-Meteo (THIRD PARTY)",
        noaa=False,
        notes="Free, no key, JSON. First run returned elevation 97m, which "
              "suggests the nearest cell is on land — so the values are "
              "inspected here, not just the key name. Using this at all is a "
              "deliberate deviation from SPEC section 3, not a quiet import.",
        json_preview=("elevation", "hourly.sea_surface_temperature"),
    ),
]


def _dig(payload, path: str):
    node = payload
    for key in path.split("."):
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def fetch(url: str, timeout: float) -> tuple[str, dict, bytes, int, bool]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read(MAX_BYTES + 1)
        elapsed = int((time.monotonic() - started) * 1000)
        truncated = len(body) > MAX_BYTES
        return (
            str(response.status),
            dict(response.headers),
            body[:MAX_BYTES],
            elapsed,
            truncated,
        )


def probe(candidate: Candidate, timeout: float = 30.0, now: datetime | None = None) -> Result:
    now = now or datetime.now(timezone.utc)
    result = Result(candidate=candidate)
    try:
        status, headers, body, elapsed, truncated = fetch(candidate.url, timeout)
        result.status, result.elapsed_ms = status, elapsed
        result.content_type = headers.get("Content-Type", "")
        text = body.decode("utf-8", errors="replace")

        if candidate.follow and "json" in result.content_type:
            try:
                nxt = _dig(json.loads(text), candidate.follow)
            except json.JSONDecodeError:
                nxt = None
            if isinstance(nxt, str):
                result.followed_url = nxt
                status, headers, body, elapsed, truncated = fetch(nxt, timeout)
                result.status, result.elapsed_ms = status, elapsed
                result.content_type = headers.get("Content-Type", "")
                text = body.decode("utf-8", errors="replace")

        result.size, result.truncated = len(body), truncated
        result.found = tuple(t for t in candidate.looking_for if t in text)
        result.dated, result.date_source = sniff_date(text, headers, now)
        result.sample = " ".join(text[:200].split())

        if candidate.json_preview and "json" in result.content_type:
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                payload = None
            for path in candidate.json_preview:
                value = _dig(payload, path) if payload is not None else None
                if isinstance(value, list):
                    value = value[:4]
                result.preview[path] = value
    except urllib.error.HTTPError as exc:
        result.status, result.error = str(exc.code), f"HTTP {exc.code} {exc.reason}"
    except Exception as exc:  # noqa: BLE001 - a probe reports failures, never raises
        result.error = f"{exc.__class__.__name__}: {exc}"
    return result


def format_report(results: list[Result], now: datetime) -> str:
    lines = [
        "## Forecast source probe",
        "",
        "Does a public 24h nearshore water-temperature forecast exist, and can we "
        "reach it? A source counts as usable only if it is reachable, carries the "
        "field, AND its content is fresh — a source that returns HTTP 200 with "
        "18-month-old data is worse than one that fails outright.",
        "",
        "| Source | Operator | Verdict | Field found | Newest date in body | Age |",
        "| --- | --- | --- | --- | --- | ---: |",
    ]
    for r in results:
        age = r.age_hours(now)
        age_text = "—" if age is None else f"{age / 24:.0f}d"
        if r.is_stale(now):
            age_text = f"**{age_text}**"
        dated = r.dated.strftime("%Y-%m-%d") if r.dated else "undated"
        lines.append(
            f"| {r.candidate.name} | {r.candidate.operator} | {r.verdict(now)} | "
            f"{', '.join(r.found) or '—'} | {dated} ({r.date_source or 'n/a'}) | "
            f"{age_text} |"
        )

    lines += ["", "### Detail", ""]
    for r in results:
        lines.append(f"**{r.candidate.name}** — {r.verdict(now)}  ")
        lines.append(f"`{r.candidate.url}`  ")
        if r.followed_url:
            lines.append(f"followed to `{r.followed_url}`  ")
        lines.append(f"{r.candidate.notes}  ")
        if r.error:
            lines.append(f"Failed: {r.error}")
        else:
            lines.append(
                f"`{r.status}` `{r.content_type}` {r.size} bytes"
                + (" **TRUNCATED**" if r.truncated else "")
            )
            if r.preview:
                lines.append("")
                for path, value in r.preview.items():
                    lines.append(f"  - `{path}` = `{value}`")
            lines.append(f"  sample: `{r.sample[:160]}`")
        lines.append("")

    usable = [r for r in results if r.verdict(now) == "usable"]
    noaa = [r for r in usable if r.candidate.noaa]
    stale = [r for r in results if r.is_stale(now)]

    lines += ["### Read", ""]
    if not usable:
        lines.append(
            "**No probed source is usable.** If this holds, SPEC section 3's "
            "published-forecast baseline does not exist for this quantity, "
            "persistence is the baseline by default, and the pitch needs "
            "rewording — 'beat the forecast' has no forecast to beat."
        )
    elif not noaa:
        lines.append(
            f"**Only non-NOAA sources are usable** ({', '.join(r.candidate.name for r in usable)}). "
            "Adopting one is a deliberate deviation from SPEC section 3 and puts "
            "a third-party dependency on the scoring path. That is a decision to "
            "make explicitly, and to mirror into the archive so the baseline "
            "survives the source disappearing."
        )
    else:
        lines.append(
            f"{len(noaa)} NOAA source(s) usable. Confirm each is a *forecast* "
            "rather than an analysis of the past, and that it publishes before "
            "the call window opens."
        )
    if stale:
        lines += [
            "",
            "**Stale sources (HTTP 200, old content):** "
            + ", ".join(r.candidate.name for r in stale)
            + ". Never archive one of these as a baseline without a freshness "
            "assertion at write time.",
        ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe candidate forecast sources.")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)

    now = datetime.now(timezone.utc)
    results = [probe(c, timeout=args.timeout, now=now) for c in CANDIDATES]
    report = format_report(results, now)
    print(report)
    write_step_summary(report)
    # A probe never fails the run: an unreachable or stale source is the finding.
    return 0


if __name__ == "__main__":
    sys.exit(main())
