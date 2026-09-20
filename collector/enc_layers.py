"""What is actually inside NOAA's ENC chart services near the harbour entrance.

    python -m collector.enc_layers

Run it on Actions. `gis.charttools.noaa.gov` answers from a runner and not from
a Claude session, the same as every other NOAA host (BRIEFING §8, §21a).

WHY. `collector.shoreline` pulled the coastline (S-57 object class COALNE) out
of `encdirect/enc_approach` layer 88 and stopped there, because a coastline was
all it was looking for. The same services carry the rest of the chart, and the
next three geometries this project needs are in it:

  SLCONS  shoreline construction — jetties, breakwaters, training walls.
          ZUNIGA JETTY IS THIS. It is a rubble mound awash for much of its
          length, so it is NOT on the MHW coastline and a shoreline product
          will not have it. A chart will.
  DEPCNT  depth contours, and DEPARE depth areas — the only route to Zuniga
          Shoals, which is submerged and has no shoreline at all.
  LNDARE  land areas — island silhouettes.

WHAT THIS IS NOT. It does not fetch geometry and it does not store anything.
It asks each service what layers it has, counts features inside the box, and
prints the table. Deciding which layer becomes a blocker is a judgement with a
provenance record attached, and BRIEFING §20 already says a shoal is not a
blocker at all — it refracts, it does not shadow. Nothing here shortcuts that.

COUNTS, NOT FEATURES. `returnCountOnly=true` is a fraction of the payload and
it is the whole question at this stage: does this layer have anything HERE.
It also sidesteps whatever made layers 19 and 87 answer "Invalid or missing
input parameters" to a full query on 2026-09-20 — and when a layer still
refuses, that is reported rather than hidden, because a layer that cannot be
queried and a layer that is empty are different facts.
"""

from __future__ import annotations

import argparse
import sys
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

from .common import write_step_summary
from .shoreline import ShorelineError, fetch_json, is_denial

#: The chart services found by `collector.shoreline`'s catalogue walk on
#: 2026-09-20. Ordered coarse to fine; the finer scales carry more detail over
#: a smaller area, and the harbour entrance is covered by several at once.
SERVICES = tuple(
    f"https://gis.charttools.noaa.gov/arcgis/rest/services/encdirect/{name}/MapServer"
    for name in ("enc_approach", "enc_harbour", "enc_coastal", "enc_general")
)

#: THE APPROACHES, not the beach. `collector.shoreline.BBOX` was drawn around
#: Coronado's sand and excludes Point Loma's tip at -117.2427 and the Zuniga
#: jetty entirely — measured, three of the five geometries this project still
#: needs fall outside it. This box covers the tip, the harbour entrance, the
#: whole of Coronado and south past Imperial Beach.
BBOX = (-117.2800, 32.6000, -117.1400, 32.7500)

#: S-57 object classes worth asking about, and why. Anything else in the chart
#: is navigation furniture for this project's purposes.
WANTED_CLASSES = {
    "COALNE": "coastline",
    "SLCONS": "shoreline construction — jetties, breakwaters",
    "LNDARE": "land area — island and headland silhouettes",
    "DEPCNT": "depth contour",
    "DEPARE": "depth area",
    "OBSTRN": "obstruction",
    "UWTROC": "underwater rock",
    "SBDARE": "seabed area",
}

#: How many layers to query per service. A chart service carries well over a
#: hundred and this is a probe, not a crawl.
QUERY_BUDGET = 24

TIMEOUT = 45.0


@dataclass
class Layer:
    service: str
    id: int
    name: str
    geometry: str
    count: int | None = None
    note: str = ""

    @property
    def klass(self) -> str:
        """The S-57 acronym, if the layer's name carries one."""

        upper = self.name.upper()
        for acronym in WANTED_CLASSES:
            if acronym in upper:
                return acronym
        return ""


@dataclass
class Result:
    layers: list[Layer] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    denied: bool = False

    @property
    def interesting(self) -> list[Layer]:
        return [l for l in self.layers if l.klass]

    @property
    def populated(self) -> list[Layer]:
        return [l for l in self.interesting if l.count]


def count_url(layer_url: str, bbox: tuple[float, float, float, float]) -> str:
    params = {
        "where": "1=1",
        "geometry": ",".join(f"{v}" for v in bbox),
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "returnCountOnly": "true",
        "f": "json",
    }
    return f"{layer_url}/query?{urllib.parse.urlencode(params)}"


def enumerate_service(service_url: str) -> tuple[list[Layer], str]:
    """Every layer the service declares. One request."""

    try:
        meta = fetch_json(f"{service_url}?f=json", timeout=TIMEOUT)
    except Exception as exc:  # noqa: BLE001 — classified by the caller
        return [], f"{exc.__class__.__name__}: {exc}"[:160]

    name = service_url.rstrip("/").split("/")[-2]
    out = []
    for layer in meta.get("layers", []) or []:
        out.append(Layer(
            service=name,
            id=int(layer.get("id", -1)),
            name=str(layer.get("name", "")),
            geometry=str(layer.get("geometryType", "")).replace("esriGeometry", ""),
        ))
    return out, ""


def count_features(layer: Layer, service_url: str,
                   bbox: tuple[float, float, float, float]) -> None:
    """Fill in `count`, or `note` saying why it could not be had."""

    try:
        payload = fetch_json(count_url(f"{service_url}/{layer.id}", bbox),
                             timeout=TIMEOUT)
    except ShorelineError as exc:
        # An ArcGIS error inside a 200. Layers 19 and 87 did this on
        # 2026-09-20 and it is a fact about the layer, not a failure here.
        layer.note = str(exc)[:80]
        return
    except Exception as exc:  # noqa: BLE001
        layer.note = f"{exc.__class__.__name__}: {exc}"[:80]
        return
    value = payload.get("count")
    layer.count = int(value) if isinstance(value, int) else None
    if layer.count is None:
        layer.note = "no count in the response"


def survey(services: tuple[str, ...] = SERVICES,
           bbox: tuple[float, float, float, float] = BBOX) -> Result:
    result = Result()
    denials = 0
    for service_url in services:
        layers, error = enumerate_service(service_url)
        if error:
            result.errors.append(f"{service_url} — {error}")
            if "403" in error or "CONNECT" in error or "URLError" in error:
                denials += 1
            continue
        result.layers += layers

        asked = 0
        for layer in layers:
            if not layer.klass or asked >= QUERY_BUDGET:
                continue
            count_features(layer, service_url, bbox)
            asked += 1
    result.denied = bool(services) and denials == len(services)
    return result


def format_summary(result: Result) -> str:
    lines = ["### ENC chart layers near the San Diego harbour entrance", ""]
    lines.append(f"Box: `{BBOX}` — the approaches, not the beach.")
    lines.append("")

    if result.errors:
        lines += ["**Services that did not answer:**"]
        lines += [f"- {e}" for e in result.errors]
        lines.append("")

    if not result.layers:
        lines.append(
            "**No layers enumerated.** Nothing is inferred from that — "
            "`gis.charttools.noaa.gov` answers from a runner and not from a "
            "session, so read the errors above before concluding anything."
        )
        return "\n".join(lines)

    lines.append(f"{len(result.layers)} layers across "
                 f"{len({l.service for l in result.layers})} service(s); "
                 f"{len(result.interesting)} carry an S-57 class this project "
                 f"asked about.")
    lines += ["", "| service | id | layer | geometry | features in box |",
              "|---|---|---|---|---|"]
    for layer in sorted(result.interesting,
                        key=lambda l: (-(l.count or 0), l.service, l.id)):
        count = (f"**{layer.count}**" if layer.count
                 else ("0" if layer.count == 0 else f"— {layer.note}"))
        lines.append(f"| {layer.service} | {layer.id} | `{layer.name}` | "
                     f"{layer.geometry} | {count} |")
    lines.append("")

    lines += ["**What each class would be for:**", ""]
    seen = {l.klass for l in result.populated}
    for acronym, why in WANTED_CLASSES.items():
        mark = "yes" if acronym in seen else "not found in box"
        lines.append(f"- `{acronym}` — {why} — **{mark}**")
    lines += ["", "This enumerates. It stores nothing and edits nothing. "
                  "Which layer becomes a blocker is a judgement with a "
                  "provenance record, and BRIEFING §20 already says a shoal is "
                  "not a blocker at all — it refracts, it does not shadow."]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bbox", type=float, nargs=4, default=list(BBOX),
                        metavar=("XMIN", "YMIN", "XMAX", "YMAX"))
    args = parser.parse_args(argv)

    result = survey(bbox=tuple(args.bbox))
    summary = format_summary(result)
    print(summary)
    write_step_summary(summary)

    if result.denied:
        return 2
    return 0 if result.layers else 1


if __name__ == "__main__":
    sys.exit(main())
