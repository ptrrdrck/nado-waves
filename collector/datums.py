"""Fetch NOAA's tidal datums for 9410170, the tide station for these beaches.

Run: ``python -m collector.datums`` — on Actions; api.tidesandcurrents.noaa.gov
is denied at CONNECT from a Claude session (BRIEFING §8).

The map draws its coast at mean high water, the line a chart's coastline is
(`forecast.seabedvector`; BRIEFING §53): the geometry's vertices are chart
coast, and drawn at the ray tracer's land depth instead, 0.9 m lower, the
breaks sat 13-34 m inside the map's land. MHW is read off these datums,
fetched, never typed, for the same reason a buoy coordinate is: a typed copy
drifts from its source without anyone noticing.

Stored as CO-OPS serves it, with when and where it came from:

    data/tide/9410170_datums.json

Every value is in metres above the station datum (STND); only differences
between two of them mean anything here. `mhw_above_msl_m` reads the one the
map needs. The datums change only when NOAA adopts a new tidal epoch, so the
collection runs this with `--max-age-days` and re-fetches only an old file.
A fetch that fails leaves the stored file as it was.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path

from .common import DEFAULT_DATA_DIR, ISO, parse_iso, utcnow, write_step_summary
from .tide import STATION, fetch

MDAPI = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi"

#: The datums a reader of this file needs: the two the map's coast is drawn
#: between (MSL, the seabed's zero, and MHW, the chart's coastline) and the
#: two the grids are carried by (NAVD88) and the predictions are stated in
#: (MLLW).
REQUIRED = ("MHW", "MSL", "MLLW", "NAVD88")


class DatumsError(RuntimeError):
    pass


def datums_path(data_dir: Path = DEFAULT_DATA_DIR, station: str = STATION) -> Path:
    return Path(data_dir) / "tide" / f"{station}_datums.json"


def url(station: str = STATION) -> str:
    return f"{MDAPI}/stations/{station}/datums.json?units=metric"


def by_name(body: dict) -> dict[str, float]:
    return {d["name"]: float(d["value"]) for d in body.get("datums") or []
            if d.get("name") and d.get("value") is not None}


def parse(payload: bytes) -> dict:
    """The response, checked: CO-OPS reports some failures as a 200 with an
    `error` body, and a datum missing from the list must not read as zero."""

    try:
        body = json.loads(payload.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise DatumsError(f"response was not JSON: {exc}") from None
    if not isinstance(body, dict) or body.get("error"):
        raise DatumsError(f"CO-OPS error in a 200 body: {str(body)[:200]}")
    units = body.get("units")
    if units is not None and str(units).lower() not in ("meters", "metres", "metric"):
        raise DatumsError(f"datums not in metres: {units!r}")
    have = by_name(body)
    missing = [k for k in REQUIRED if k not in have]
    if missing:
        raise DatumsError(f"datums lack {missing}")
    if not 0.0 < have["MHW"] - have["MSL"] < 2.0:
        raise DatumsError(f"MHW {have['MHW']} is not just above MSL {have['MSL']}")
    return body


def mhw_above_msl_m(data_dir: Path = DEFAULT_DATA_DIR, station: str = STATION) -> float | None:
    """Mean high water above mean sea level (m) from the stored datums, or None
    when they have not been fetched."""

    try:
        stored = json.loads(datums_path(data_dir, station).read_text())
    except (OSError, json.JSONDecodeError):
        return None
    have = by_name(stored.get("response") or {})
    if "MHW" not in have or "MSL" not in have:
        return None
    return round(have["MHW"] - have["MSL"], 4)


def age_days(path: Path) -> float | None:
    try:
        stored = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    fetched = parse_iso(stored.get("fetched_utc"))
    return None if fetched is None else (utcnow() - fetched) / timedelta(days=1)


def collect(station: str = STATION, data_dir: Path = DEFAULT_DATA_DIR) -> dict:
    source = url(station)
    body = parse(fetch(source))
    record = {"station": station, "fetched_utc": utcnow().strftime(ISO),
              "source": source, "response": body}
    path = datums_path(data_dir, station)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=1) + "\n")
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--station", default=STATION)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--max-age-days", type=float, default=None,
                        help="skip the fetch when the stored file is younger than this")
    args = parser.parse_args(argv)

    path = datums_path(args.data_dir, args.station)
    age = age_days(path)
    if args.max_age_days is not None and age is not None and age < args.max_age_days:
        print(f"{path.name} is {age:.1f} days old; not re-fetched.")
        return 0
    try:
        record = collect(args.station, args.data_dir)
    except Exception as exc:  # noqa: BLE001 -- reported, and the stored file stands
        message = f"Tidal datums not fetched: {exc}"
        print(message)
        write_step_summary(f"### Tidal datums\n\n{message}")
        return 1
    have = by_name(record["response"])
    summary = (f"### Tidal datums — {args.station}\n\n"
               f"MHW {have['MHW'] - have['MSL']:+.3f} m and MLLW {have['MLLW'] - have['MSL']:+.3f} m "
               f"from MSL, epoch {record['response'].get('epoch')}; stored in {path.name}.")
    print(summary)
    write_step_summary(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
