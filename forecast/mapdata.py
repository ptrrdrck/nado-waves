"""What the Swell card's map draws besides the swell: `map.json`.

    python -m forecast.mapdata        # write data/live/map.json

- `geometry`: `forecast.geomviz`'s model, from spots.json, as docs.html's
  drawing reads it: each break's position, chord, normal and windows, each
  window edge's charted vertex, bearing and range; each blocker's outline; and
  46232. Never typed: the same file the forecast reads.
- `buoys`: the other buoys the page shows, 46086 and 46047, at NDBC's fetched
  coordinates (`forecast.siting.load_coordinates`), never typed.
- `seabed`: `data/seabed_vector/manifest.json`, so the page knows each
  grid's file, the zoom it is drawn from and its fingerprint
  (forecast.seabedvector).
- `paths`: each break's `<break>_paths.json` (the fill's rays) by its
  fingerprint. The page keeps a copy of every file the map loads in the
  browser's own cache under that fingerprint (`kept`): Pages lets a browser
  hold a file for ten minutes only and redeploys every collection, so the
  map's ~1 MB came down again on any visit after ten minutes (owner's
  report, 2026-11-12).

Static between geometry changes, a few KB, built by `forecast.publish` into
both bundles beside the page (which ships from both jobs) and written here for
the page served from the repository.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR

ROOT = Path(__file__).resolve().parent.parent
SEABED_DIR = ROOT / "data" / "seabed_vector"
NEARSHORE_DIR = ROOT / "data" / "nearshore"
#: The buoys marked on the map beside 46232 (geomviz's own), as the Buoys tab
#: shows them.
OTHER_BUOYS = ("46086", "46047")


def build(data_dir: Path = DEFAULT_DATA_DIR, seabed_dir: Path = SEABED_DIR,
          nearshore_dir: Path = NEARSHORE_DIR) -> dict:
    from . import geomviz
    from .seabedvector import fingerprint
    from .siting import load_coordinates

    where = load_coordinates()
    manifest_path = seabed_dir / "manifest.json"
    seabed = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None
    return {
        "geometry": json.loads(json.dumps(geomviz.build(data_dir=data_dir), default=list)),
        "buoys": {b: list(where[b]) for b in OTHER_BUOYS if b in where},
        "seabed": seabed,
        "paths": {p.name.removesuffix("_paths.json"): fingerprint(p)
                  for p in sorted(nearshore_dir.glob("*_paths.json"))},
    }


def write(data_dir: Path = DEFAULT_DATA_DIR) -> Path:
    path = Path(data_dir) / "live" / "map.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build(data_dir), separators=(",", ":")), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    a = ap.parse_args(argv)
    path = write(a.data_dir)
    print(path, f"{path.stat().st_size / 1e3:.1f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
