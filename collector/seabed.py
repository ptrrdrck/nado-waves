"""NOAA's charted seabed nature over the wrap's water, from the ENC services.

    python -m collector.seabed            # fetch and store data/seabed/
    python -m collector.seabed --probe    # list the seabed layers and counts only

Run it on Actions (`shoreline.yml`, input `seabed`): `gis.charttools.noaa.gov`
answers from a runner and not from a Claude session (`collector.enc_layers`).

WHY (handoff item 27d, BRIEFING §63). The chain's bottom friction is Madsen's
at one roughness, SWAN's sand default, everywhere. A rougher bed laid under
the whole of the wrap round Point Loma could take a fifth to two fifths off
Center's and South's big-westerly headline; nothing in the archive says where
the bed is rock. The chart does, in part: S-57 object class SBDARE ("seabed
area"), with NATSUR (nature of surface: sand, rock, ...) and NATQUA
(qualifier), drawn as areas, lines or points.

WHAT IT IS. A chart's seabed nature is what its source surveys sampled or
saw, generalised for navigation, of the survey's date. An area says the
surface there was charted as that; a point is one sample, not an extent; and
the absence of a feature is not sand. Stored with the layer, feature id and
every attribute the service returns.

NOTHING IS INFERRED. As `collector.kelp`: no layer or no feature in the box
is exit 1 and nothing is written; a CONNECT denial is exit 2; no service
answering at all is exit 3, never "none charted"; points or lines with no
area is exit 4, stored but flagged (nothing to measure a path through).
Each file is written only when it has a row.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .common import DEFAULT_DATA_DIR, write_step_summary
from .enc_layers import SERVICES, enumerate_service, TIMEOUT
from .kelp import features, point_rows, query_url, ring_rows
from .shoreline import fetch_json, is_denial

#: The water the wrap's rays cross: west of Point Loma's tip, south of it, and
#: east to the Coronado breaks and the harbour entrance (lon, lat). Wider than
#: `collector.kelp`'s box to the west and south, where the wrap's paths leave
#: the shelf; the US charts end at the border.
BBOX = (-117.4500, 32.5000, -117.1000, 32.8000)
#: A layer is a seabed-nature layer by its S-57 acronym or its English name.
SEABED = re.compile(r"SBDARE|sea.?bed|bottom.?charact", re.I)
FIELDS = ["service", "layer_id", "layer", "feature", "ring", "seq", "lat", "lon"]
POINT_FIELDS = ["service", "layer_id", "layer", "feature", "lat", "lon"]
LINE_FIELDS = ["service", "layer_id", "layer", "feature", "path", "seq", "lat", "lon"]
EXIT_NO_AREA = 4
#: S-57 NATSUR codes (IHO S-57 Appendix A), for the run's summary only; the
#: stored attributes are the service's own values, undecoded.
NATSUR = {"1": "mud", "2": "clay", "3": "silt", "4": "sand", "5": "stone", "6": "gravel",
          "7": "pebbles", "8": "cobbles", "9": "rock", "11": "lava", "14": "coral",
          "17": "shells", "18": "boulder"}


def line_rows(name: str, layer, fid, geometry: dict | None) -> list[list]:
    """One row per vertex of every path of a line feature; [] for anything else."""
    out = []
    for path_no, path in enumerate((geometry or {}).get("paths") or []):
        for seq, (lon, lat) in enumerate(path):
            out.append([name, layer.id, layer.name, fid, path_no, seq, f"{lat:.6f}", f"{lon:.6f}"])
    return out


def natsur_of(attributes: dict) -> str | None:
    """The feature's NATSUR as the service gives it, whatever its key's case."""
    for k, v in attributes.items():
        if k.upper() == "NATSUR":
            return None if v in (None, "") else str(v)
    return None


def decode(natsur: str | None) -> str:
    if natsur is None:
        return "no NATSUR"
    return "+".join(NATSUR.get(c.strip(), f"code {c.strip()}") for c in re.split(r"[,;]", natsur))


def run(data_dir: Path, probe: bool) -> int:
    lines = ["## Charted seabed nature over the wrap (S-57 SBDARE)", "", f"Box: `{BBOX}`", ""]
    found, denials, errors = [], 0, []
    for service in SERVICES:
        layers, err = enumerate_service(service)
        if err:
            errors.append(f"{service}: {err}")
            denials += "403" in err or "CONNECT" in err or "Tunnel" in err
            continue
        for layer in layers:
            if not SEABED.search(layer.name):
                continue
            url = f"{service}/{layer.id}"
            try:
                n = fetch_json(query_url(url, count_only=True, bbox=BBOX), timeout=TIMEOUT).get("count")
            except Exception as exc:  # noqa: BLE001 -- reported, never hidden
                if is_denial(exc):
                    denials += 1
                errors.append(f"{url}: {exc.__class__.__name__}: {exc}"[:200])
                continue
            found.append((service, layer, n))
    lines += ["| service | id | layer | geometry | features in box |", "|---|---|---|---|---|"]
    lines += [f"| {s.rstrip('/').split('/')[-2]} | {l.id} | {l.name} | {l.geometry} | {n} |"
              for s, l, n in found] or ["| – | – | no layer named for the seabed | – | – |"]
    if errors:
        lines += ["", "Errors:", ""] + [f"- {e}" for e in errors]
    if denials and not found:
        write_step_summary("\n".join(lines + ["", "**Denied at CONNECT**: run on Actions."]))
        print("\n".join(lines))
        return 2
    if len(errors) >= len(SERVICES) and not found:
        lines += ["", "**No chart service answered** (above). Nothing learned about the "
                      "seabed; nothing written."]
        write_step_summary("\n".join(lines))
        print("\n".join(lines))
        return 3
    populated = [(s, l, n) for s, l, n in found if n]
    if probe or not populated:
        if not populated:
            lines += ["", "**No charted seabed nature in the box.** Nothing written; nothing "
                          "inferred (absence is not sand)."]
        write_step_summary("\n".join(lines))
        print("\n".join(lines))
        return 0 if probe else 1

    out_dir = data_dir / "seabed"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows, points, paths, attrs = [], [], [], []
    kinds: Counter = Counter()
    for service, layer, _ in populated:
        name = service.rstrip("/").split("/")[-2]
        for feat in features(f"{service}/{layer.id}", bbox=BBOX):
            a = feat.get("attributes") or {}
            fid = a.get("OBJECTID", a.get("objectid", len(attrs)))
            g = feat.get("geometry")
            attrs.append({"service": name, "layer_id": layer.id, "layer": layer.name,
                          "feature": fid, "attributes": a})
            r, p, ln = ring_rows(name, layer, fid, g), point_rows(name, layer, fid, g), \
                line_rows(name, layer, fid, g)
            rows += r
            points += p
            paths += ln
            shape = "area" if r else "line" if ln else "point" if p else "no geometry"
            kinds[(shape, decode(natsur_of(a)))] += 1
    for fname, fields, data in (("enc_sbdare.csv", FIELDS, rows),
                                ("enc_sbdare_points.csv", POINT_FIELDS, points),
                                ("enc_sbdare_lines.csv", LINE_FIELDS, paths)):
        path = out_dir / fname
        if not data:
            path.unlink(missing_ok=True)  # never an empty file standing for "none"
            continue
        with path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(fields)
            w.writerows(data)
    (out_dir / "enc_sbdare.json").write_text(json.dumps({
        "fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bbox_lon_lat": BBOX, "object_class": "SBDARE",
        "note": "Charted seabed nature: what the source surveys sampled, generalised for "
                "navigation, of their dates. A point is one sample, not an extent; no "
                "feature is not sand.",
        "features": attrs}, indent=1, default=str))
    lines += ["", f"Stored {len(attrs)} feature(s) in data/seabed/.", "",
              "| geometry | NATSUR (S-57 code meaning) | features |", "|---|---|---|"]
    lines += [f"| {shape} | {nat} | {n} |" for (shape, nat), n in sorted(kinds.items())]
    if not rows:
        lines += ["", "**No area charted.** Points and lines are stored; there is no extent "
                      "to measure a path through (exit 4)."]
    write_step_summary("\n".join(lines))
    print("\n".join(lines))
    return 0 if rows else EXIT_NO_AREA


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--probe", action="store_true", help="list seabed layers and counts only")
    ap.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = ap.parse_args(argv)
    return run(args.data_dir, args.probe)


if __name__ == "__main__":
    sys.exit(main())
