"""The Swell card map's fill on LIVE: each train's energy, ray by ray.

    python -m forecast.fill        # data/live/now.json -> data/live/fill.json

The owner's request (2026-11-10; mocked in mocks/swell_fill, retired once shipped): on LIVE, a
picked train's energy comes in along its rays' real paths over the seabed,
long periods first. The paths are static (`raytrace --paths-only` ->
`data/nearshore/<break>_paths.json`); what changes with every spectrum is how
much of each train each ray carries, and that is this file.

For now.json's own spectrum (its `observed_utc`) it re-runs the LIVE chain's
carry (`nearshore.buoy_split`, `nearshore.carry`, maximum entropy) and, for
each train a break card lists, credits every ray's 5 m energy as `carry`
does: the row's bins, its arc, and -- for a row divided by the buoy's trains
-- only the buoy swell(s) it is. A ray the land stops carries nothing hard;
what diffraction gives it is credited to the clearing ray of the same period
whose offshore heading is nearest the one the table credits it to,
raytrace's own reading of where diffracted energy comes round an edge from.

**Checked, never trusted**: each row's period and heading must equal
now.json's, and its rays' 5 m energy summed must give the chain's own 5 m
height to 2 mm. A row that fails is left out and said in `notes`, so the page
offers no fill for it rather than a wrong one. Rays under `MIN_SHARE` of a
row's energy are not listed; `drawn_share` says how much is.

Its own file, never a key in now.json (owner's question, 2026-11-10: the
energy per ray, ~10 KB, would ride every five-minute refresh; this is
fetched only when a fill is played). Built every collection after
`forecast.now`; a failure here never touches now.json.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR

#: Rays carrying less than this share of a row's 5 m energy are not listed.
MIN_SHARE = 2e-4
#: The 5 m height the rays must rebuild, to this (m).
TOLERANCE_M = 0.002
#: The paths' band (`raytrace.PATH_BAND_HZ`), repeated here so this module
#: needs no numpy; a test holds the two equal.
PATH_BAND_HZ = (0.03, 0.25)


def _ang(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def rows_for(spectrum, table, grids, split, owner, trains, shown) -> tuple[list, list]:
    """The fill rows for one break: (rows, notes)."""

    from .nearshore import _arc_degrees, at, shoaling_squared

    rows, notes = [], []
    for n, (row, t) in enumerate(zip(shown, trains)):
        if row.get("period_s") != round(t.period_s, 1) or row.get("from_deg") != round(t.from_deg):
            notes.append(f"{table.break_id} row {n}: now.json and the rebuilt chain disagree; no fill")
            continue
        arc = set(_arc_degrees(t.arc))
        mine = set(t.buoys or ()) | ({t.buoy} if t.buoy is not None else set())
        divided = bool(t.buoys)
        credit: dict[tuple[str, int], float] = {}
        five = 0.0
        for i in t.bins:
            grid = grids.get(i)
            if grid is None:
                continue
            f = spectrum.frequencies[i]
            near_f = min(table.by_freq, key=lambda q: abs(q - f))
            key = f"{near_f:.4f}"
            width = spectrum.bin_width(i)
            rays = table.by_freq[near_f]
            clear = [r for r in rays if r.gain > 0]
            drawn = PATH_BAND_HZ[0] <= near_f <= PATH_BAND_HZ[1]
            for ray in rays:
                if ray.diff_gain <= 0:
                    continue
                kk = int(ray.diff_off_from) % 360
                if kk not in arc or (divided and owner(i, kk) not in mine):
                    continue
                e = at(grid, ray.diff_off_from) * width * ray.width_rad * ray.diff_gain * ray.diff_friction
                five += e
                if not drawn:
                    continue
                target = ray if ray.gain > 0 else (
                    min(clear, key=lambda c: _ang(c.off_from, ray.diff_off_from)) if clear else None)
                if target is None:
                    continue
                credit[(key, target.k)] = credit.get((key, target.k), 0.0) + e
        hs5 = 4.0 * math.sqrt(five) if five > 0 else 0.0
        if abs(hs5 - t.hs_m) > TOLERANCE_M:
            notes.append(f"{table.break_id} row {n}: rays give {hs5:.3f} m at 5 m, the chain "
                         f"{t.hs_m:.3f} m; no fill")
            continue
        total = sum(credit.values())
        kept = {k: v for k, v in credit.items() if total and v >= MIN_SHARE * total}
        rows.append({
            "row": n, "period_s": row["period_s"], "from_deg": row["from_deg"],
            "row_hs_m": row["hs_m"],
            "drawn_share": round(sum(kept.values()) / five, 4) if five else 0.0,
            # [frequency key, the ray's place in <break>.csv, share of the row's 5 m energy]
            "rays": [[fk, k, round(v / five, 6)] for (fk, k), v in sorted(kept.items())],
        })
    return rows, notes


def build(data_dir: Path = DEFAULT_DATA_DIR) -> dict:
    from .nearshore import _buoy_owner, buoy_split, carry, density_grids, load_tables
    from .transform import load_spectra

    now = json.loads((Path(data_dir) / "live" / "now.json").read_text(encoding="utf-8"))
    out = {"observed_utc": now.get("observed_utc"), "breaks": {}, "notes": []}
    if not now.get("observed_utc") or not now.get("breaks"):
        out["notes"].append("now.json has no reading; no fill")
        return out
    when = datetime.fromisoformat(now["observed_utc"].replace("Z", "+00:00"))
    directory = Path(data_dir) / "spectra" / now.get("station", "46232")
    spectra = [s for s in load_spectra(directory, limit=6) if s.time == when]
    if not spectra:
        out["notes"].append(f"no spectrum at {now['observed_utc']}; no fill")
        return out
    spectrum = spectra[0].with_spread("mem")
    grids = density_grids(spectrum)
    split = buoy_split(spectrum, grids)
    owner = _buoy_owner(split)
    tables = load_tables()
    for b in now["breaks"]:
        table = tables.get(b["id"])
        shown = (b.get("nearshore") or {}).get("trains") or []
        if table is None or not shown:
            continue
        carried = carry(spectrum, table, grids, split)
        rows, notes = rows_for(spectrum, table, grids, split, owner, carried.trains[:3], shown)
        out["breaks"][b["id"]] = rows
        out["notes"] += notes
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    a = ap.parse_args(argv)
    source = Path(a.data_dir) / "live" / "now.json"
    if not source.exists():
        print(f"{source} missing: run forecast.now first; no fill written")
        return 0
    data = build(a.data_dir)
    path = Path(a.data_dir) / "live" / "fill.json"
    path.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    for bid, rows in data["breaks"].items():
        for r in rows:
            print(f"{bid} row {r['row']}: {r['period_s']} s from {r['from_deg']}°, "
                  f"{len(r['rays'])} rays, {100 * r['drawn_share']:.1f}% of its 5 m energy drawn")
    for note in data["notes"]:
        print("note:", note)
    print(f"Wrote {path} ({path.stat().st_size / 1e3:.1f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
