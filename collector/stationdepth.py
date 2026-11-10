"""Each shown buoy's water depth, as NDBC's station page states it.

Run: ``python -m collector.stationdepth`` -- on Actions; www.ndbc.noaa.gov is
denied at CONNECT from a Claude session (BRIEFING §8).

The Buoys tab's station block names how deep the water is under each buoy
(owner's request, 2026-11-10). NDBC's station table, which
`collector.metadata` reads for coordinates, has no depth column; the station
page does, as a line like ``Water depth: 1394 m``. So the page is fetched and
that one figure kept, with the words it was read from, the URL and when --
never typed, for the same reason a buoy coordinate is not: a typed copy drifts
from its source without anyone noticing.

Stored as

    data/station_depth.json   {station: {depth_m, read, source, fetched_utc}}

A buoy is re-moored now and then, so the collection runs this with
`--max-age-days` and re-fetches only an old file. A page with no depth line,
or one that fails to load, leaves that station's stored record as it was and
is reported; a station never read has no record, and the page says nothing
about its depth rather than guess.

Checked against the live pages on Actions 2026-11-10 (probe-station-depth.yml):
"Water depth: 1049.8 m" at 46232, "1862 m" at 46086, "1390 m" at 46047 --
one line each, 46232's to the decimetre, the others whole metres.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.request
from datetime import timedelta
from pathlib import Path

from .common import DEFAULT_DATA_DIR, ISO, parse_iso, utcnow, write_step_summary
from .ndbc import USER_AGENT

#: The buoys the Buoys tab shows: forecast.buoys' ANCHOR and STATIONS, held
#: to them by a test (a collector does not import the forecast package).
STATIONS = ("46232", "46086", "46047")

PAGE = "https://www.ndbc.noaa.gov/station_page.php?station={}"

FILENAME = "station_depth.json"

#: "Water depth: 1394 m", "Water depth: 1,394.0 m" -- read after the page's
#: tags are stripped, so "<b>Water depth:</b> 1394 m" reads the same.
DEPTH_RE = re.compile(r"Water depth:\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*m\b", re.IGNORECASE)

#: Plausible open-ocean mooring depths. Outside them the parse went wrong.
DEPTH_BOUNDS_M = (1.0, 11000.0)


class DepthError(RuntimeError):
    pass


def depth_path(data_dir: Path = DEFAULT_DATA_DIR) -> Path:
    return Path(data_dir) / FILENAME


def page_text(raw: str) -> str:
    """The page as plain words: tags out, entities read, spaces collapsed."""

    text = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse(raw: str) -> tuple[float, str]:
    """The depth in metres and the words it was read from."""

    text = page_text(raw)
    found = DEPTH_RE.findall(text)
    if not found:
        raise DepthError("no 'Water depth: … m' line on the page")
    values = {float(v.replace(",", "")) for v in found}
    if len(values) > 1:
        raise DepthError(f"the page states more than one depth: {sorted(values)}")
    depth = values.pop()
    lo, hi = DEPTH_BOUNDS_M
    if not lo <= depth <= hi:
        raise DepthError(f"{depth} m is outside {lo}-{hi} m; the parse went wrong")
    return depth, DEPTH_RE.search(text).group(0)


def fetch(station: str, timeout: float = 30.0) -> str:
    request = urllib.request.Request(PAGE.format(station), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def load(data_dir: Path = DEFAULT_DATA_DIR) -> dict:
    try:
        return json.loads(depth_path(data_dir).read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def age_days(record: dict | None) -> float | None:
    fetched = parse_iso((record or {}).get("fetched_utc"))
    return None if fetched is None else (utcnow() - fetched) / timedelta(days=1)


def collect(stations=STATIONS, data_dir: Path = DEFAULT_DATA_DIR,
            max_age_days: float | None = None, fetcher=fetch) -> tuple[dict, list[str]]:
    """Fetch each station's depth; keep the stored record where a fetch fails."""

    stored = load(data_dir)
    problems: list[str] = []
    for station in stations:
        age = age_days(stored.get(station))
        if max_age_days is not None and age is not None and age < max_age_days:
            continue
        try:
            depth, read = parse(fetcher(station))
        except Exception as exc:  # noqa: BLE001 -- reported, the stored record stands
            problems.append(f"{station}: {exc}")
            continue
        stored[station] = {"depth_m": depth, "read": read, "source": PAGE.format(station),
                           "fetched_utc": utcnow().strftime(ISO)}
    path = depth_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(sorted(stored.items())), indent=1) + "\n")
    return stored, problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--stations", default=",".join(STATIONS))
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--max-age-days", type=float, default=None,
                        help="skip a station whose stored depth is younger than this")
    args = parser.parse_args(argv)

    stations = [s.strip() for s in args.stations.split(",") if s.strip()]
    stored, problems = collect(stations, args.data_dir, args.max_age_days)
    lines = ["### Buoy water depth", "", "| Station | Depth | Read | Fetched |", "| --- | ---: | --- | --- |"]
    for station in stations:
        r = stored.get(station)
        lines.append(f"| {station} | {r['depth_m']:g} m | {r['read']} | {r['fetched_utc']} |" if r
                     else f"| {station} | — | never read | — |")
    if problems:
        lines += ["", *(f"- not read: {p}" for p in problems)]
    report = "\n".join(lines)
    print(report)
    write_step_summary(report)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
