"""NOAA's charted kelp off Point Loma, from the ENC chart services.

    python -m collector.kelp            # fetch and store data/kelp/
    python -m collector.kelp --probe    # list the kelp layers and counts only

Run it on Actions (`shoreline.yml`, input `kelp`): `gis.charttools.noaa.gov`
answers from a runner and not from a Claude session (`collector.enc_layers`).

WHY (handoff item 27d). On big westerly days the wrap round Point Loma carries
70% of Center's and South's 5 m energy (BRIEFING §60), along rays that pass
about a kilometre south of the tip and cross the shelf east to Coronado. Point
Loma's kelp forest lies across part of that water; whether the rays cross it,
and for how far, needs an outline. The chart carries one: S-57 object class
WEDKLP ("weed/kelp"), drawn as areas.

WHAT IT IS. A chart's kelp is a navigational warning, generalised, of the date
its source survey says (`SORDAT` when the layer carries it) and not of this
year: a kelp bed's extent changes from year to year. It is an outline of where
kelp has been charted, never a measurement of the canopy now. Stored with the
layer, feature id and every attribute the service returns, so the report can
say exactly which outline it used.

POINTS ARE NOT AN OUTLINE. The chart may draw kelp as point symbols, not
areas: off Point Loma it does, everywhere in the box (run 17, 2026-11-22: 45
points across the harbour, approach and coastal charts, surveys 1998-2005, no
area). Areas go to `enc_wedklp.csv` (rings), points to
`enc_wedklp_points.csv` (one position each), and each file is written only
when it has a row. Points with no area is its own exit, 4: stored, so where
the chart puts kelp is on record, but nothing a path length can be measured
through, and `forecast.kelpcross` refuses rather than read it as "no kelp
crossed". Until 2026-11-22 the points' positions were dropped, an empty CSV
was committed and the run reported success.

NOTHING IS INFERRED. A layer that matches no kelp, or a box with no feature,
is reported as such (exit 1) and nothing is written; a CONNECT denial is exit
2, as in `collector.shoreline`; no service answering at all (timeouts) is
exit 3, never "none charted"; points and no area is exit 4.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from .common import DEFAULT_DATA_DIR, write_step_summary
from .enc_layers import SERVICES, TIMEOUT, enumerate_service
from .shoreline import fetch_json, is_denial

#: Point Loma's west side from Sunset Cliffs to the tip, the water south of the
#: tip the wrap's rays cross, and east to the harbour entrance (lon, lat).
BBOX = (-117.3600, 32.5800, -117.1500, 32.8000)
#: A layer is a kelp layer by its S-57 acronym or its English name.
KELP = re.compile(r"WEDKLP|kelp|weed", re.I)
FIELDS = ["service", "layer_id", "layer", "feature", "ring", "seq", "lat", "lon"]
POINT_FIELDS = ["service", "layer_id", "layer", "feature", "lat", "lon"]
#: Charted as points only, no area: stored, but no outline (see the docstring).
EXIT_POINTS_ONLY = 4
PAGE = 500


def query_url(layer_url: str, *, count_only: bool, offset: int = 0) -> str:
    params = {
        "where": "1=1",
        "geometry": ",".join(f"{v}" for v in BBOX),
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "f": "json",
    }
    if count_only:
        params["returnCountOnly"] = "true"
    else:
        params.update({"outFields": "*", "returnGeometry": "true", "outSR": "4326",
                       "resultOffset": str(offset), "resultRecordCount": str(PAGE)})
    return f"{layer_url}/query?{urllib.parse.urlencode(params)}"


def features(layer_url: str) -> list[dict]:
    out, offset = [], 0
    while True:
        page = fetch_json(query_url(layer_url, count_only=False, offset=offset), timeout=TIMEOUT)
        if "error" in page:
            raise RuntimeError(f"{layer_url}: {json.dumps(page['error'])[:200]}")
        got = page.get("features") or []
        out += got
        if not page.get("exceededTransferLimit") or not got:
            return out
        offset += len(got)


def run(data_dir: Path, probe: bool) -> int:
    lines = ["## Charted kelp off Point Loma (S-57 WEDKLP)", "", f"Box: `{BBOX}`", ""]
    found, denials, errors = [], 0, []
    for service in SERVICES:
        layers, err = enumerate_service(service)
        if err:
            errors.append(f"{service}: {err}")
            denials += "403" in err or "CONNECT" in err or "Tunnel" in err
            continue
        for layer in layers:
            if not KELP.search(layer.name):
                continue
            url = f"{service}/{layer.id}"
            try:
                n = fetch_json(query_url(url, count_only=True), timeout=TIMEOUT).get("count")
            except Exception as exc:  # noqa: BLE001 -- reported, never hidden
                if is_denial(exc):
                    denials += 1
                errors.append(f"{url}: {exc.__class__.__name__}: {exc}"[:200])
                continue
            found.append((service, layer, n))
    lines += ["| service | id | layer | geometry | features in box |", "|---|---|---|---|---|"]
    lines += [f"| {s.rstrip('/').split('/')[-2]} | {l.id} | {l.name} | {l.geometry} | {n} |"
              for s, l, n in found] or ["| – | – | no layer named for kelp or weed | – | – |"]
    if errors:
        lines += ["", "Errors:", ""] + [f"- {e}" for e in errors]
    if denials and not found:
        write_step_summary("\n".join(lines + ["", "**Denied at CONNECT**: run on Actions."]))
        print("\n".join(lines))
        return 2
    if len(errors) >= len(SERVICES) and not found:
        # No service answered: that says nothing about kelp, and must not read
        # as "none charted" (a third state, not the second).
        lines += ["", "**No chart service answered** (above). Nothing learned about kelp; "
                      "nothing written."]
        write_step_summary("\n".join(lines))
        print("\n".join(lines))
        return 3
    populated = [(s, l, n) for s, l, n in found if n]
    if probe or not populated:
        if not populated:
            lines += ["", "**No charted kelp in the box.** Nothing written; nothing inferred."]
        write_step_summary("\n".join(lines))
        print("\n".join(lines))
        return 0 if probe else 1

    out_dir = data_dir / "kelp"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows, points, attrs = [], [], []
    for service, layer, _ in populated:
        name = service.rstrip("/").split("/")[-2]
        for feat in features(f"{service}/{layer.id}"):
            a = feat.get("attributes") or {}
            fid = a.get("OBJECTID", a.get("objectid", len(attrs)))
            attrs.append({"service": name, "layer_id": layer.id, "layer": layer.name,
                          "feature": fid, "attributes": a})
            rows += ring_rows(name, layer, fid, feat.get("geometry"))
            points += point_rows(name, layer, fid, feat.get("geometry"))
    for fname, fields, data in (("enc_wedklp.csv", FIELDS, rows),
                                ("enc_wedklp_points.csv", POINT_FIELDS, points)):
        path = out_dir / fname
        if not data:
            path.unlink(missing_ok=True)  # never an empty file standing for "none"
            continue
        with path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(fields)
            w.writerows(data)
    (out_dir / "enc_wedklp.json").write_text(json.dumps({
        "fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bbox_lon_lat": BBOX, "object_class": "WEDKLP",
        "note": "Charted kelp: a navigational outline of its source survey's date, "
                "not this year's canopy.",
        "features": attrs}, indent=1, default=str))
    n_areas = len({(r[0], r[1], r[3]) for r in rows})
    lines += ["", f"Stored {len(attrs)} feature(s) in data/kelp/: {n_areas} area(s) "
                  f"({len(rows)} vertices), {len(points)} point(s)."]
    if not rows:
        lines += ["", "**Charted as points only, no area.** Where the chart puts kelp is "
                      "stored; there is no outline to measure a path through (exit 4)."]
    write_step_summary("\n".join(lines))
    print("\n".join(lines))
    return 0 if rows else EXIT_POINTS_ONLY


def ring_rows(name: str, layer, fid, geometry: dict | None) -> list[list]:
    """One row per vertex of every ring of an area feature; [] for anything else."""
    out = []
    for ring_no, ring in enumerate((geometry or {}).get("rings") or []):
        for seq, (lon, lat) in enumerate(ring):
            out.append([name, layer.id, layer.name, fid, ring_no, seq, f"{lat:.6f}", f"{lon:.6f}"])
    return out


def point_rows(name: str, layer, fid, geometry: dict | None) -> list[list]:
    """One row per point symbol (ArcGIS x/y, or each of a multipoint's); [] for an area."""
    g = geometry or {}
    pts = g.get("points") or ([[g["x"], g["y"]]] if "x" in g and "y" in g else [])
    return [[name, layer.id, layer.name, fid, f"{lat:.6f}", f"{lon:.6f}"]
            for lon, lat in pts if lon is not None and lat is not None]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--probe", action="store_true", help="list kelp layers and counts only")
    ap.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = ap.parse_args(argv)
    return run(args.data_dir, args.probe)


if __name__ == "__main__":
    sys.exit(main())
