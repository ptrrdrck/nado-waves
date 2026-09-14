"""Is there NDBC history older than the 45-day real-time window?

    python -m collector.probe_history

SPEC section 4 says "Only the last 45 days are retained". That is true of the
**real-time** service (`realtime2`) and is misleading about NDBC as a whole:
NDBC also publishes a historical archive, and CDIP keeps its own. If those are
reachable, the scoring function can be calibrated against years and several
upwelling seasons rather than the 46 days the collector has gathered so far —
which is currently a single late-summer window, the quietest part of the year.

What backfill would NOT fix, and why the collector still had to come first:

* The historical archive is **quality-controlled after the fact**. The
  collector captures values *as first published*, with `first_seen_utc`. Scoring
  a round depends on what was known at round open, not on what NDBC decided the
  value was months later (SPEC section 4, "Storing the data"). Backfill is for
  calibration; the live archive is the system of record.
* Forecast history is still unrecoverable. Nobody archives the forecast that was
  published last March for us.

This probe only reports what exists. It does not download an archive.
"""

from __future__ import annotations

import argparse
import gzip
import io
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .common import write_step_summary
from .ndbc import USER_AGENT, parse_realtime2

#: One CDIP-relayed station and one NDBC moored buoy, so the report shows
#: whether coverage differs by station type.
SAMPLE_CDIP = "46222"
SAMPLE_MOORED = "46086"

THIS_YEAR = datetime.now(timezone.utc).year


@dataclass
class Source:
    name: str
    url: str
    notes: str = ""
    gzipped: bool = True


@dataclass
class Finding:
    source: Source
    status: str = ""
    size: int = 0
    error: str = ""
    header: str = ""
    first_row: str = ""
    last_row: str = ""
    rows_parsed: int = 0
    span: str = ""

    @property
    def ok(self) -> bool:
        return not self.error and self.status.startswith("2")


def candidates() -> list[Source]:
    previous = THIS_YEAR - 1
    return [
        Source(
            name=f"NDBC historical stdmet {SAMPLE_CDIP} {previous}",
            url=f"https://www.ndbc.noaa.gov/data/historical/stdmet/{SAMPLE_CDIP}h{previous}.txt.gz",
            notes="Annual per-station file. If this exists, whole years are "
                  "available for the CDIP-relayed stations.",
        ),
        Source(
            name=f"NDBC historical stdmet {SAMPLE_MOORED} {previous}",
            url=f"https://www.ndbc.noaa.gov/data/historical/stdmet/{SAMPLE_MOORED}h{previous}.txt.gz",
            notes="Same, for an NDBC moored buoy.",
        ),
        Source(
            name=f"NDBC historical stdmet {SAMPLE_CDIP} {previous - 4}",
            url=f"https://www.ndbc.noaa.gov/data/historical/stdmet/{SAMPLE_CDIP}h{previous - 4}.txt.gz",
            notes="How far back does it go? Older files use a different column "
                  "layout (2-digit year, no minute column before ~2005).",
        ),
        Source(
            name="NDBC historical directory listing",
            url="https://www.ndbc.noaa.gov/data/historical/stdmet/",
            notes="Authoritative answer on what is actually published.",
            gzipped=False,
        ),
        Source(
            name=f"NDBC month-so-far {SAMPLE_CDIP}",
            url=f"https://www.ndbc.noaa.gov/data/stdmet/Aug/{SAMPLE_CDIP}8{THIS_YEAR}.txt.gz",
            notes="Bridges the gap between the last annual file and the 45-day "
                  "real-time window. URL shape is a guess and may 404.",
        ),
        Source(
            name="CDIP THREDDS archive catalogue",
            url="https://thredds.cdip.ucsd.edu/thredds/catalog/cdip/archive/catalog.html",
            notes="CDIP keeps its own archive for the buoys that make up most of "
                  "the launch set. NetCDF, so it needs a dependency we do not have.",
            gzipped=False,
        ),
    ]


def fetch(source: Source, timeout: float) -> tuple[str, bytes]:
    request = urllib.request.Request(source.url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read(4_000_000)
        if source.gzipped or response.headers.get("Content-Encoding") == "gzip":
            try:
                raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
            except (OSError, EOFError):
                pass  # truncated gzip or not gzipped after all; report what we got
        return str(response.status), raw


def probe(source: Source, timeout: float = 60.0) -> Finding:
    finding = Finding(source=source)
    try:
        status, raw = fetch(source, timeout)
        finding.status, finding.size = status, len(raw)
        text = raw.decode("utf-8", errors="replace")
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if lines:
            finding.header = lines[0][:120]
            data = [ln for ln in lines if not ln.startswith("#")]
            if data:
                finding.first_row = data[0][:90]
                finding.last_row = data[-1][:90]
        observations = parse_realtime2(text)
        finding.rows_parsed = len(observations)
        if observations:
            finding.span = (
                f"{observations[0].timestamp:%Y-%m-%d} .. "
                f"{observations[-1].timestamp:%Y-%m-%d}"
            )
    except urllib.error.HTTPError as exc:
        finding.status, finding.error = str(exc.code), f"HTTP {exc.code} {exc.reason}"
    except Exception as exc:  # noqa: BLE001 - a probe reports, never raises
        finding.error = f"{exc.__class__.__name__}: {exc}"
    return finding


def format_report(findings: list[Finding]) -> str:
    lines = [
        "## Historical archive probe",
        "",
        "SPEC section 4's \"only the last 45 days are retained\" describes the "
        "real-time service. This checks whether NDBC or CDIP publish history "
        "beyond it — which would let the scoring function be calibrated against "
        "years and several upwelling seasons instead of one late-summer window.",
        "",
        "| Source | Reachable | Bytes | Rows our parser read | Span |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for f in findings:
        reach = "yes" if f.ok else f"**no** ({f.error})"
        lines.append(
            f"| {f.source.name} | {reach} | {f.size} | {f.rows_parsed} | "
            f"{f.span or '—'} |"
        )

    lines += ["", "### Detail", ""]
    for f in findings:
        lines.append(f"**{f.source.name}**  ")
        lines.append(f"`{f.source.url}`  ")
        lines.append(f"{f.source.notes}  ")
        if f.error:
            lines.append(f"Failed: {f.error}")
        else:
            lines.append(f"`{f.status}` {f.size} bytes, parser read {f.rows_parsed} rows")
            if f.header:
                lines.append(f"  header: `{f.header}`")
            if f.first_row:
                lines.append(f"  first:  `{f.first_row}`")
                lines.append(f"  last:   `{f.last_row}`")
        lines.append("")

    usable = [f for f in findings if f.ok and f.rows_parsed > 100]
    lines += ["### Read", ""]
    if usable:
        lines.append(
            f"**{len(usable)} source(s) returned parseable history.** The 45-day "
            "limit applies to the real-time feed only, and SPEC section 4 should "
            "say so. Backfill would widen the calibration set from 46 days to "
            "years."
        )
        lines.append("")
        lines.append(
            "Two things backfill does NOT change: the historical archive is "
            "quality-controlled after the fact, so it cannot tell us what was "
            "*known at round open* — that is what the live collector's "
            "`first_seen_utc` is for — and forecast history is still "
            "unrecoverable."
        )
    else:
        parseable = [f for f in findings if f.ok]
        if parseable:
            lines.append(
                "Sources responded but our parser read little or nothing from "
                "them. Older NDBC files use a different column layout (2-digit "
                "year, no minute column), so the parser likely needs a variant "
                "before backfill is possible. Check the headers above."
            )
        else:
            lines.append(
                "Nothing reachable. The 45-day window stands as the practical "
                "limit and the collector remains the only source of history."
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe for NDBC history beyond 45 days.")
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args(argv)

    findings = [probe(source, timeout=args.timeout) for source in candidates()]
    report = format_report(findings)
    print(report)
    write_step_summary(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
