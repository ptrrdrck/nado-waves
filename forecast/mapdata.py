"""What the Swell card's map draws besides the swell: `map.json`.

    python -m forecast.mapdata        # write data/live/map.json

- `geometry`: `forecast.geomviz`'s model, from spots.json, as docs.html's
  drawing reads it: each break's position, chord, normal and windows, each
  window edge's charted vertex, bearing and range; each blocker's outline; and
  46232. Never typed: the same file the forecast reads.
- `buoys`: the other buoys the page shows, 46086 and 46047, at NDBC's fetched
  coordinates (`forecast.siting.load_coordinates`), never typed.
- `seabed`: `data/seabed_tiles/manifest.json`, so the page knows each tile
  layer's zooms and bounds and asks for no tile that is not there.

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
TILES_DIR = ROOT / "data" / "seabed_tiles"
#: The buoys marked on the map beside 46232 (geomviz's own), as the Buoys tab
#: shows them.
OTHER_BUOYS = ("46086", "46047")


def build(data_dir: Path = DEFAULT_DATA_DIR, tiles: Path = TILES_DIR) -> dict:
    from . import geomviz
    from .siting import load_coordinates

    where = load_coordinates()
    manifest_path = tiles / "manifest.json"
    seabed = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None
    return {
        "geometry": json.loads(json.dumps(geomviz.build(data_dir=data_dir), default=list)),
        "buoys": {b: list(where[b]) for b in OTHER_BUOYS if b in where},
        "seabed": seabed,
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
