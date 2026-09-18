"""Archive wind at KNZY (NAS North Island), the wind station for these beaches.

Run: ``python -m collector.wind`` — on Actions; aviationweather.gov is denied
at CONNECT from a Claude session (BRIEFING §8, checked again 2026-09-18).

CLAUDE.md: "Wind and tide are not optional at these beaches." KNZY sits on the
north end of the peninsula, roughly 4 km from Coronado's north break and 6 km
from the south break — close enough to stand for all three, and the only
continuously reporting wind station on the peninsula itself.

Storage: ``data/wind/KNZY.csv``, one row per observation.

**Wind direction is degrees FROM**, matching NDBC `MWD` and
`forecast.geometry`, and NOT the GFS-Wave bulletin convention that
`collector.gfswave` flips on the way in. METAR is already FROM, so nothing is
flipped here — which is worth stating precisely because the one measured
direction bug in this project cost 151° of error (CLAUDE.md).

What is deliberately NOT done here: no conversion to offshore/onshore, no
"clean/blown out" verdict. That depends on the shore normal, which differs by
break and, at Coronado's north break, rests on a chord flagged unverified.
`forecast.live` does it where the geometry is in scope and the caveat can be
attached to it.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .common import DEFAULT_DATA_DIR, ISO, utcnow, write_step_summary

STATION = "KNZY"

#: Aviation Weather Center's public METAR API. Chosen over scraping a page:
#: it is JSON, it is documented, and BRIEFING §8's list of probe failures is
#: mostly substring matches against page furniture.
BASE_URL = "https://aviationweather.gov/api/data/metar"

USER_AGENT = "nado-waves/1.0 (surf forecast research; contact via repository)"

FIELDS = [
    "observed_utc",
    "first_seen_utc",
    "wind_from_deg",
    "wind_kt",
    "gust_kt",
    "variable",
    "raw",
]

#: METAR reports a calm or variable wind as direction "VRB" or 0 with a speed.
#: Neither is a bearing, and storing 0 as a compass direction would make a calm
#: morning look like a due-north wind. Flagged instead.
VARIABLE_TOKENS = {"VRB", "vrb"}


class WindError(RuntimeError):
    pass


@dataclass
class WindResult:
    station: str
    fetched: int = 0
    added: int = 0
    denied: bool = False
    error: str = ""
    newest: str | None = None
    rows: list[dict[str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.error and not self.denied


def wind_path(data_dir: Path, station: str = STATION) -> Path:
    return Path(data_dir) / "wind" / f"{station.upper()}.csv"


def build_url(station: str = STATION, hours: int = 6) -> str:
    return f"{BASE_URL}?ids={station}&format=json&hours={int(hours)}"


def fetch(url: str, *, timeout: float = 30.0) -> bytes:
    """One fetch, no retry. A denial is not throttling (BRIEFING §8)."""

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _stamp(value) -> datetime | None:
    """METAR times arrive as epoch seconds or ISO, depending on the endpoint."""

    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def parse(payload: bytes) -> list[dict[str, str]]:
    """Parse the METAR JSON into storable rows.

    Missing fields are left EMPTY, never defaulted to zero. A missing gust is
    not a gust of nothing and a missing wind is not a calm — the archive has to
    be able to say it does not know (CLAUDE.md, and the 999.0-as-wave-height
    trap in BRIEFING §1).
    """

    try:
        data = json.loads(payload.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise WindError(f"response was not JSON: {exc}") from None

    if isinstance(data, dict):
        data = data.get("data", data.get("features", []))
    if not isinstance(data, list):
        raise WindError("response JSON was not a list of observations")

    rows: list[dict[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        observed = _stamp(item.get("obsTime") or item.get("reportTime"))
        if observed is None:
            continue

        raw_dir = item.get("wdir")
        variable = ""
        wind_from = ""
        if raw_dir in VARIABLE_TOKENS:
            variable = "1"
        elif raw_dir not in (None, ""):
            try:
                wind_from = str(int(round(float(raw_dir)))% 360)
            except (TypeError, ValueError):
                variable = "1"

        def number(key: str) -> str:
            value = item.get(key)
            if value in (None, ""):
                return ""
            try:
                return f"{float(value):g}"
            except (TypeError, ValueError):
                return ""

        rows.append({
            "observed_utc": observed.strftime(ISO),
            "first_seen_utc": "",
            "wind_from_deg": wind_from,
            "wind_kt": number("wspd"),
            "gust_kt": number("wgst"),
            "variable": variable,
            "raw": str(item.get("rawOb", "")).strip(),
        })
    rows.sort(key=lambda r: r["observed_utc"])
    return rows


def read_existing(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open(newline="", encoding="utf-8") as fh:
        return {row["observed_utc"] for row in csv.DictReader(fh) if row.get("observed_utc")}


def append(path: Path, rows: list[dict[str, str]], *, seen_at: str) -> int:
    """Append observations not already stored. `first_seen_utc` is never rewritten."""

    stored = read_existing(path)
    fresh = [r for r in rows if r["observed_utc"] not in stored]
    if not fresh:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        for row in fresh:
            writer.writerow({**row, "first_seen_utc": seen_at})
    return len(fresh)


def collect(
    station: str = STATION,
    data_dir: Path = DEFAULT_DATA_DIR,
    *,
    hours: int = 6,
) -> WindResult:
    result = WindResult(station=station)
    try:
        payload = fetch(build_url(station, hours))
    except Exception as exc:  # noqa: BLE001 — classified below
        text = f"{exc.__class__.__name__}: {exc}"
        result.error = text
        result.denied = "403" in text or "URLError" in text or "CONNECT" in text
        return result

    try:
        rows = parse(payload)
    except WindError as exc:
        result.error = str(exc)
        return result

    result.fetched = len(rows)
    result.rows = rows
    path = wind_path(data_dir, station)
    result.added = append(path, rows, seen_at=utcnow().strftime(ISO))
    stored = read_existing(path)
    result.newest = max(stored) if stored else None
    return result


def format_summary(result: WindResult) -> str:
    lines = [f"### Wind — {result.station}", ""]
    if result.denied:
        lines += [
            f"**Denied at CONNECT**: `{result.error[:120]}`",
            "",
            "A policy denial, not throttling (BRIEFING §8). Report the host; do not route around it.",
        ]
    elif result.error:
        lines += [f"**Error**: `{result.error[:200]}`"]
    else:
        lines += [
            f"| fetched | new | newest stored |",
            "|---|---|---|",
            f"| {result.fetched} | {result.added} | {result.newest or '—'} |",
        ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--station", default=STATION)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--hours", type=int, default=6)
    args = parser.parse_args(argv)

    result = collect(args.station, args.data_dir, hours=args.hours)
    summary = format_summary(result)
    print(summary)
    write_step_summary(summary)
    if result.denied:
        return 2
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
