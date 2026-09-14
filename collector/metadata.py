"""Station coordinates, taken from NDBC rather than guessed.

The forecast experiment needs a latitude and longitude per buoy. Typing
approximate coordinates into the registry from memory would be inventing data —
the one thing this project does not do — and a forecast pulled for the wrong
point is worse than no forecast, because it looks fine.

NDBC publishes the authoritative table at
https://www.ndbc.noaa.gov/data/stations/station_table.txt, pipe-delimited, with
a LOCATION column like:

    32.933 N 117.391 W (32&#176;56'0" N 117&#176;23'28" W)

    python -m collector.metadata

Writes `data/station_metadata.csv`. Coordinates that fail a regional sanity
check are recorded but marked unusable, and the forecast archiver skips those
stations rather than pulling a forecast for the wrong ocean.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from .common import DEFAULT_DATA_DIR, write_step_summary
from .ndbc import USER_AGENT
from .stations import Station, load_stations, select

STATION_TABLE_URL = "https://www.ndbc.noaa.gov/data/stations/station_table.txt"

METADATA_FILENAME = "station_metadata.csv"

METADATA_FIELDS = [
    "id",
    "name",
    "owner",
    "station_type",
    "latitude",
    "longitude",
    "usable",
    "note",
]

#: Plausible bounding boxes per registry region. A coordinate outside its box
#: means the parse went wrong, or the registry names a station somewhere else
#: entirely. Either way it must not silently become a forecast location.
REGION_BOUNDS = {
    "socal": (30.0, 36.0, -122.0, -116.0),  # lat_min, lat_max, lon_min, lon_max
}

LOCATION_RE = re.compile(
    r"([0-9]+(?:\.[0-9]+)?)\s*([NS])\s+([0-9]+(?:\.[0-9]+)?)\s*([EW])"
)


@dataclass
class StationMetadata:
    id: str
    name: str = ""
    owner: str = ""
    station_type: str = ""
    latitude: float | None = None
    longitude: float | None = None
    usable: bool = False
    note: str = ""


def parse_location(text: str) -> tuple[float, float] | None:
    """Pull decimal degrees out of an NDBC LOCATION cell."""

    match = LOCATION_RE.search(text or "")
    if not match:
        return None
    lat, lat_hemi, lon, lon_hemi = match.groups()
    latitude = float(lat) * (-1 if lat_hemi.upper() == "S" else 1)
    longitude = float(lon) * (-1 if lon_hemi.upper() == "W" else 1)
    return latitude, longitude


def parse_station_table(text: str) -> dict[str, dict[str, str]]:
    """Parse the pipe-delimited station table into {STATION_ID: columns}."""

    header: list[str] | None = None
    rows: dict[str, dict[str, str]] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            if header is None and "|" in line:
                header = [c.strip().upper() for c in line.lstrip("#").split("|")]
            continue
        cells = [c.strip() for c in line.split("|")]
        if not cells or not cells[0]:
            continue
        names = header or ["STATION_ID", "OWNER", "TTYPE", "HULL", "NAME",
                           "PAYLOAD", "LOCATION", "TIMEZONE", "FORECAST", "NOTE"]
        record = {names[i]: cells[i] for i in range(min(len(names), len(cells)))}
        rows[cells[0].upper()] = record
    return rows


def in_bounds(station: Station, latitude: float, longitude: float) -> bool:
    bounds = REGION_BOUNDS.get(station.region)
    if bounds is None:
        return -90 <= latitude <= 90 and -180 <= longitude <= 180
    lat_min, lat_max, lon_min, lon_max = bounds
    return lat_min <= latitude <= lat_max and lon_min <= longitude <= lon_max


def build_metadata(stations: list[Station], table: dict[str, dict[str, str]]) -> list[StationMetadata]:
    out = []
    for station in stations:
        record = table.get(station.id.upper())
        meta = StationMetadata(id=station.id, name=station.name)
        if record is None:
            meta.note = "not present in the NDBC station table"
            out.append(meta)
            continue

        meta.owner = record.get("OWNER", "")
        meta.station_type = record.get("TTYPE", "")
        coords = parse_location(record.get("LOCATION", ""))
        if coords is None:
            meta.note = f"could not parse LOCATION: {record.get('LOCATION', '')!r}"
        else:
            meta.latitude, meta.longitude = coords
            if in_bounds(station, *coords):
                meta.usable = True
            else:
                meta.note = (
                    f"coordinates {coords[0]:.3f},{coords[1]:.3f} fall outside the "
                    f"expected bounds for region {station.region!r}"
                )
        out.append(meta)
    return out


def metadata_path(data_dir: Path) -> Path:
    return Path(data_dir) / METADATA_FILENAME


def write_metadata(data_dir: Path, records: list[StationMetadata]) -> Path:
    path = metadata_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=METADATA_FIELDS, lineterminator="\n")
        writer.writeheader()
        for record in sorted(records, key=lambda r: r.id):
            writer.writerow(
                {
                    "id": record.id,
                    "name": record.name,
                    "owner": record.owner,
                    "station_type": record.station_type,
                    "latitude": "" if record.latitude is None else f"{record.latitude:.4f}",
                    "longitude": "" if record.longitude is None else f"{record.longitude:.4f}",
                    "usable": "true" if record.usable else "false",
                    "note": record.note,
                }
            )
    return path


def load_metadata(data_dir: Path) -> dict[str, StationMetadata]:
    path = metadata_path(data_dir)
    if not path.exists():
        return {}
    out: dict[str, StationMetadata] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            try:
                latitude = float(row["latitude"]) if row["latitude"] else None
                longitude = float(row["longitude"]) if row["longitude"] else None
            except ValueError:
                latitude = longitude = None
            out[row["id"]] = StationMetadata(
                id=row["id"],
                name=row.get("name", ""),
                owner=row.get("owner", ""),
                station_type=row.get("station_type", ""),
                latitude=latitude,
                longitude=longitude,
                usable=row.get("usable") == "true",
                note=row.get("note", ""),
            )
    return out


def fetch_station_table(timeout: float = 30.0, retries: int = 3) -> str:
    # Reuses the collector's fetch so retries and the User-Agent stay in one place.
    import urllib.request

    request = urllib.request.Request(
        STATION_TABLE_URL, headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Archive NDBC station coordinates.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--stations", help="Comma-separated station ids.")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)

    stations = select(
        load_stations(), args.stations.split(",") if args.stations else None
    )

    try:
        table = parse_station_table(fetch_station_table(timeout=args.timeout))
    except Exception as exc:  # noqa: BLE001
        print(f"::error title=Station table::could not fetch: {exc}")
        return 1

    records = build_metadata(stations, table)
    write_metadata(args.data_dir, records)

    lines = [
        "## Station coordinates",
        "",
        f"Parsed {len(table)} stations from the NDBC station table.",
        "",
        "| Station | Name | Type | Latitude | Longitude | Usable | Note |",
        "| --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for record in sorted(records, key=lambda r: r.id):
        lines.append(
            f"| {record.id} | {record.name} | {record.station_type} | "
            f"{'—' if record.latitude is None else f'{record.latitude:.3f}'} | "
            f"{'—' if record.longitude is None else f'{record.longitude:.3f}'} | "
            f"{'yes' if record.usable else '**no**'} | {record.note or ''} |"
        )
    report = "\n".join(lines)
    print(report)
    write_step_summary(report)

    unusable = [r for r in records if not r.usable]
    if unusable:
        print(
            "::warning title=Station coordinates::"
            + ", ".join(r.id for r in unusable)
            + " have no usable coordinates; they will be skipped by the forecast "
            "experiment"
        )
    return 0 if len(unusable) < len(records) else 1


if __name__ == "__main__":
    sys.exit(main())
