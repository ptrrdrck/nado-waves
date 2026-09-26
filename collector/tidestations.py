"""Which tide stations describe the water level at Coronado's breaks?

Run: ``python -m collector.tidestations`` — on Actions; CO-OPS is denied at
CONNECT from a Claude session (BRIEFING §8).

9410170 is the tide the whole project uses, and it is a gauge on a pier INSIDE
San Diego Bay, well up the harbour from the entrance. The breaks are on the
open coast outside it. A bay modifies the tide that enters it — it arrives
late and its range changes — so the question is whether the gauge's level is
the beach's level, in time and in height. Water depth at the break is what
wave breaking needs, so for the first time the tide stops being context and
becomes an input to a number on the card.

This collects the evidence and decides nothing:

    data/tide/stations.json           every CO-OPS prediction and water-level
                                      station near the breaks, its position
                                      as CO-OPS gives it, its distance from
                                      each break, and — for a subordinate
                                      station — CO-OPS's own time and height
                                      offsets from its reference
    data/tide/comparison/<id>_<product>.csv
                                      the last 31 days of 6-minute measured
                                      level at each nearby water-level station,
                                      and the hilo predictions of every nearby
                                      prediction station over the same days,
                                      all on MLLW, so a lag and a range ratio
                                      can be MEASURED between them rather than
                                      assumed (forecast/tidesite.py)

and CO-OPS's tidal datums for the gauges, so a level on MLLW can be put on
MSL — the datum the seabed grids are on — from a published number.

No coordinate is typed here. Every position comes from CO-OPS's metadata, and
the breaks' from spots.json.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import timedelta
from pathlib import Path

from forecast.geometry import load
from forecast.swell import great_circle_km

from .common import DEFAULT_DATA_DIR, ISO, utcnow, write_step_summary
from .tide import DATUM, UNITS, fetch

MDAPI = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi"
DATAGETTER = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"

#: Search radius around the breaks. Wide enough to reach La Jolla, the
#: nearest open-coast gauge with a long record, and the whole of the bay.
RADIUS_KM = 30.0

#: CO-OPS serves at most 31 days of 6-minute data in one request.
DAYS = 30

REFERENCE = "9410170"


def get_json(url: str) -> dict:
    body = json.loads(fetch(url).decode("utf-8", errors="replace"))
    if isinstance(body, dict) and body.get("error"):
        raise RuntimeError(f"CO-OPS error in a 200 body: {str(body['error'])[:200]}")
    return body


def nearby(kind: str, breaks) -> list[dict]:
    body = get_json(f"{MDAPI}/stations.json?type={kind}")
    found = []
    for station in body.get("stations", []):
        try:
            where = (float(station["lat"]), float(station["lng"]))
        except (KeyError, TypeError, ValueError):
            continue
        distances = {b.id: round(great_circle_km(where, b.position), 2) for b in breaks}
        if min(distances.values()) > RADIUS_KM:
            continue
        found.append({
            "id": str(station["id"]),
            "name": station.get("name", ""),
            "lat": where[0],
            "lon": where[1],
            "type": station.get("type", ""),
            "reference_id": station.get("reference_id", ""),
            "km_from": distances,
        })
    return sorted(found, key=lambda s: min(s["km_from"].values()))


def offsets(station_id: str) -> dict | None:
    try:
        return get_json(f"{MDAPI}/stations/{station_id}/tidepredoffsets.json")
    except Exception as exc:  # noqa: BLE001 — recorded, not fatal
        return {"error": f"{exc.__class__.__name__}: {exc}"[:300]}


def series(station_id: str, product: str, begin, end, interval: str | None) -> list[dict]:
    params = [
        f"product={product}", f"station={station_id}",
        f"begin_date={begin:%Y%m%d%%20%H:%M}", f"end_date={end:%Y%m%d%%20%H:%M}",
        f"datum={DATUM}", f"units={UNITS}", "time_zone=gmt", "format=json",
        "application=nado-waves",
    ]
    if interval:
        params.append(f"interval={interval}")
    body = get_json(f"{DATAGETTER}?{'&'.join(params)}")
    key = "data" if product == "water_level" else "predictions"
    rows = []
    for item in body.get(key) or []:
        if item.get("v") in (None, ""):
            continue                      # a gap stays a gap
        rows.append({"time_utc": item["t"].replace(" ", "T") + ":00Z",
                     "height_m": item["v"], "type": item.get("type", "")})
    return rows


def write_series(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["time_utc", "height_m", "type"])
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = parser.parse_args(argv)

    spots, _ = load()
    breaks = [s for s in spots if s.id.startswith("coronado_")]
    now = utcnow()
    begin, end = now - timedelta(days=DAYS), now

    try:
        predictions = nearby("tidepredictions", breaks)
        levels = nearby("waterlevels", breaks)
    except Exception as exc:  # noqa: BLE001
        print(f"station list: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        return 2

    for station in predictions:
        if station["type"] == "S":
            station["offsets"] = offsets(station["id"])

    datums = {}
    for station_id in (REFERENCE, *[s["id"] for s in levels if s["id"] != REFERENCE]):
        try:
            body = get_json(f"{MDAPI}/stations/{station_id}/datums.json?units=metric")
            datums[station_id] = {d["name"]: d["value"] for d in body.get("datums", [])}
            datums[station_id]["epoch"] = body.get("epoch", "")
        except Exception as exc:  # noqa: BLE001 — recorded, not fatal
            datums[station_id] = {"error": f"{exc.__class__.__name__}: {exc}"[:300]}

    out = args.data_dir / "tide"
    fetched: dict[str, str] = {}
    for station in levels:
        try:
            rows = series(station["id"], "water_level", begin, end, None)
        except Exception as exc:  # noqa: BLE001
            fetched[f"{station['id']} water_level"] = f"failed: {exc}"[:200]
            continue
        write_series(out / "comparison" / f"{station['id']}_observed.csv", rows)
        fetched[f"{station['id']} water_level"] = f"{len(rows)} rows"
    for station in predictions:
        try:
            rows = series(station["id"], "predictions", begin, end, "hilo")
        except Exception as exc:  # noqa: BLE001
            fetched[f"{station['id']} hilo"] = f"failed: {exc}"[:200]
            continue
        write_series(out / "comparison" / f"{station['id']}_turns.csv", rows)
        fetched[f"{station['id']} hilo"] = f"{len(rows)} rows"

    record = {
        "fetched_utc": now.strftime(ISO),
        "radius_km": RADIUS_KM,
        "datum": DATUM,
        "reference_in_use": REFERENCE,
        "breaks": {b.id: list(b.position) for b in breaks},
        "prediction_stations": predictions,
        "water_level_stations": levels,
        "datums_m": datums,
        "comparison_window_utc": [begin.strftime(ISO), end.strftime(ISO)],
        "comparison_fetch": fetched,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "stations.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    lines = ["## Tide stations near the breaks", ""]
    for station in predictions:
        lines.append(f"- prediction {station['id']} {station['name']} ({station['type']}) "
                     f"{min(station['km_from'].values()):.1f} km  offsets={station.get('offsets')}")
    for station in levels:
        lines.append(f"- water level {station['id']} {station['name']} "
                     f"{min(station['km_from'].values()):.1f} km")
    lines += ["", *[f"- {k}: {v}" for k, v in fetched.items()]]
    text = "\n".join(lines)
    print(text)
    write_step_summary(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
