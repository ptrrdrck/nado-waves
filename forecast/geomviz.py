"""Draw the geometry the model actually uses — its vertices, not the chart.

    python -m forecast.geomviz OUT.html

Writes one self-contained page from `app/geometry.html` with the payload
below embedded in it. Everything on that page is read from `spots.json`
through `forecast.geometry`, the same way the forecast reads it, so the
drawing cannot show a blocker the model does not have or miss one it does.

It is NOT a picture of the ENC coastline. The chart extracts in
`data/shoreline/` carry thousands of vertices; the model uses a few dozen of
them, and that gap is the thing worth seeing. Each window edge is drawn as a
ray from a break to the ONE vertex that forms it, which is also the vertex
whose error moves that edge (`Edge.moves_by` in `forecast.blockeredge`).

Distances are great-circle, from `forecast.swell`. Display units follow the
project rule — imperial first, metric in parentheses — and the conversion
happens in the page, never here: this payload stays in km and degrees.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR
from .geometry import SEAWARD, Blocker, Spot, load, swell_windows
from .swell import great_circle_km, initial_bearing

TEMPLATE = Path(__file__).resolve().parent.parent / "app" / "geometry.html"
PLACEHOLDER = "/*__MODEL__*/null"

#: The anchor buoy. Its coordinate is READ from the metadata NDBC published,
#: never typed (CLAUDE.md: never type a buoy coordinate).
BUOY = "46232"

#: The Google Earth trace the tip replaced on 2026-09-22, kept so the drawing
#: can show how far the chart moved it. History, not model input.
IMAGERY_TIP = (32.6648144, -117.2427037)


def buoy_position(data_dir: Path = DEFAULT_DATA_DIR) -> tuple[float, float] | None:
    path = Path(data_dir) / "station_metadata.csv"
    if not path.exists():
        return None
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("id") == BUOY:
                try:
                    return (float(row["latitude"]), float(row["longitude"]))
                except (KeyError, ValueError):
                    return None
    return None


def edge_vertex(spot: Spot, blocker: Blocker, bearing: float) -> tuple[float, float]:
    """The endpoint of `blocker` that forms the window edge at `bearing`."""

    candidates = (blocker.a_seen_from(spot.position), blocker.b)
    return min(candidates, key=lambda p: abs(
        (initial_bearing(spot.position, p) - bearing + 180.0) % 360.0 - 180.0))


def km(p: tuple[float, float], q: tuple[float, float]) -> float:
    return round(great_circle_km(p, q), 4)


def build(spots_path: Path | None = None, data_dir: Path = DEFAULT_DATA_DIR,
          only: tuple[str, ...] = ("coronado_north", "coronado_center",
                                   "coronado_south")) -> dict:
    spots, blockers = load(spots_path) if spots_path else load()
    raw = json.loads((spots_path or Path(__file__).resolve().parent
                      / "spots.json").read_text(encoding="utf-8"))
    raw_spots = {s["id"]: s for s in raw["spots"]}
    raw_blockers = {b["name"]: b for b in raw["blockers"]}
    by_name = {b.name: b for b in blockers}
    chosen = [s for s in spots if s.id in only]

    breaks = []
    for spot in chosen:
        windows = []
        for w in swell_windows(spot, blockers):
            entry = {"from": round(w.low.bearing, 2), "to": round(w.high.bearing, 2),
                     "span": round(w.span, 2), "edges": []}
            for side, edge in (("low", w.low), ("high", w.high)):
                if edge.source == SEAWARD or edge.source not in by_name:
                    entry["edges"].append({"side": side, "bearing": round(edge.bearing, 2),
                                           "blocker": None})
                    continue
                v = edge_vertex(spot, by_name[edge.source], edge.bearing)
                entry["edges"].append({
                    "side": side, "bearing": round(edge.bearing, 3),
                    "blocker": edge.source, "vertex": v,
                    "range_km": km(spot.position, v),
                })
            windows.append(entry)
        prov = raw_spots[spot.id].get("provenance", {})
        breaks.append({
            "id": spot.id, "name": spot.name,
            "position": spot.position, "chord": spot.shoreline,
            "chord_m": round(great_circle_km(*spot.shoreline) * 1000.0, 1),
            "normal": round(spot.normal, 2),
            "source": "imagery" if not spot.cells else "chart",
            "cells": list(spot.cells),
            "method": prov.get("method", ""), "date": prov.get("date", ""),
            "windows": windows,
        })

    out_blockers = []
    for b in blockers:
        prov = raw_blockers[b.name].get("provenance", {})
        out_blockers.append({
            "name": b.name, "a": b.a, "b": b.b, "continues": b.continues,
            "outline": list(b.outline), "cells": list(b.cells),
            "method": prov.get("method", ""), "date": prov.get("date", ""),
            "span_km": km(b.a, b.b) if not b.continues else None,
        })

    return {
        "breaks": breaks,
        "blockers": out_blockers,
        "buoy": {"id": BUOY, "position": buoy_position(data_dir)},
        "imagery_tip": IMAGERY_TIP,
        "distances": distances(breaks, by_name, buoy_position(data_dir)),
    }


def distances(breaks: list[dict], by_name: dict[str, Blocker],
              buoy: tuple[float, float] | None) -> list[dict]:
    """The pairs worth a number. Grouped so the page can show them by view."""

    out: list[dict] = []

    def add(group: str, label: str, p, q, note: str = "") -> None:
        out.append({"group": group, "label": label, "a": p, "b": q,
                    "km": km(p, q), "note": note})

    ids = {b["id"]: b for b in breaks}
    pairs = (("coronado_north", "coronado_center"), ("coronado_center", "coronado_south"),
             ("coronado_north", "coronado_south"))
    for x, y in pairs:
        if x in ids and y in ids:
            add("beach", f"{short(x)} ↔ {short(y)}", ids[x]["position"], ids[y]["position"],
                "break to break, midpoint of each chord")

    loma = by_name.get("Point Loma peninsula")
    if loma:
        tangents = {}
        for b in breaks:
            v = loma.a_seen_from(tuple(b["position"]))
            tangents[b["id"]] = v
            add("near", f"{short(b['id'])} → Point Loma tangent", b["position"], v,
                "the ray that IS this break's west edge")
        vs = list(dict.fromkeys(tangents.values()))
        if len(vs) >= 2:
            far = max(((p, q) for i, p in enumerate(vs) for q in vs[i + 1:]),
                      key=lambda pq: great_circle_km(*pq))
            add("tip", "spread of the three tangent vertices", far[0], far[1],
                "why no single point can stand for the tip")
        for b in breaks:
            add("tip", f"imagery trace → {short(b['id'])} tangent", IMAGERY_TIP,
                tangents[b["id"]], "how far the chart moved this break's vertex")

    south = by_name.get("Coronado Islands (south group)")
    north = by_name.get("Coronado Islands (north)")
    if south and north:
        add("islands", "south group, end to end", south.a, south.b,
            "the screen the model draws for three islands")
        add("islands", "north island, end to end", north.a, north.b, "")
        gap = min(((p, q) for p in (south.a, south.b) for q in (north.a, north.b)),
                  key=lambda pq: great_circle_km(*pq))
        add("islands", "channel between the islands", gap[0], gap[1],
            "open water the old one-blocker model called land")

    baja = by_name.get("Baja mainland")
    center = ids.get("coronado_center")
    if baja and center:
        add("far", "center → Baja tangent", center["position"], baja.a,
            "one vertex carries every south edge")
    if south and center:
        add("far", "center → Coronado Islands (north)", center["position"], north.b, "")
    if buoy and center:
        add("far", f"center → buoy {BUOY}", center["position"], buoy,
            "the anchor sits outside the beach's shadow")
    if buoy and loma:
        add("far", f"Point Loma tip → buoy {BUOY}", loma.a, buoy, "")
    return out


def short(spot_id: str) -> str:
    return spot_id.replace("coronado_", "")


def render(model: dict, template: Path = TEMPLATE) -> str:
    text = template.read_text(encoding="utf-8")
    if PLACEHOLDER not in text:
        raise ValueError(f"{template} has no {PLACEHOLDER} placeholder")
    return text.replace(PLACEHOLDER, json.dumps(model, separators=(",", ":")))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = parser.parse_args(argv)
    args.out.write_text(render(build(data_dir=args.data_dir)), encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
