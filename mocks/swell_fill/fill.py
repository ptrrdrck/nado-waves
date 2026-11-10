"""What the swell-fill mock animates: one break train's energy, ray by ray.

    python -m mocks.swell_fill.fill NOW.json            # check against now.json
    python -m mocks.swell_fill.fill NOW.json --json     # the mock's payload

For the moment `now.json` was built from (its `observed_utc`), this re-runs
the LIVE chain's own carry (`nearshore.buoy_split`, `nearshore.carry`) and,
for each train a break card lists, reads back what the chain did to it:

- at the buoy, its energy by offshore degree and period bin: the bins the
  row holds, the headings it holds (its `arc`), and only the buoy swell(s)
  the row is (`Train.buoy` / `buoys`), so another swell sharing its periods
  from a blocked bearing is not drawn as this one being blocked;
- whether each degree is inside a straight-line window (now.json's own
  `swell_window`, the drawing's);
- what reached 5 m of water from each degree, ray by ray, exactly as `carry`
  credits it (`diff_off_from`, diffraction and bottom friction in, shoaling
  divided out so it compares with the buoy), and where those rays head in
  5 m of water;
- when it reaches 5 m, in minutes after the same wave group passed 46232:
  the transfer tables' own `<break>_leg.csv` (`raytrace.leg_table`),
  interpolated over offshore heading within its period.

The heights it prints are the chain's: each row's 5 m height is rebuilt and
checked against now.json's, and a mismatch stops the build. Nothing here is
fitted or observed; it is the chain read back for drawing. A MOCK.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
import sys
from datetime import datetime
from pathlib import Path

from forecast.nearshore import (TABLE_DIR, _arc_degrees, _buoy_owner, at, buoy_split, carry,
                                density_grids, load_tables, shoaling_squared)
from forecast.transform import load_spectra

ROOT = Path(__file__).resolve().parents[2]
SPECTRA = ROOT / "data" / "spectra" / "46232"


def legs(break_id: str) -> dict[float, list[tuple[float, float]]]:
    """period bin (Hz) -> [(offshore heading FROM, minutes after 46232)], by heading."""
    out: dict[float, list[tuple[float, float]]] = {}
    with (TABLE_DIR / f"{break_id}_leg.csv").open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out.setdefault(float(r["freq_hz"]), []).append(
                (float(r["off_from_deg"]), float(r["from_buoy_min"])))
    for v in out.values():
        v.sort()
    return out


def arrival(leg: dict, f: float, deg: float) -> tuple[float | None, bool]:
    """Minutes after 46232 for a group of frequency f from heading deg, and
    whether the leg table holds that period (False: scaled from the nearest
    tabled period by deep-water group speed, 1/f -- outside 8-22 s)."""
    if not leg:
        return None, False
    near = min(leg, key=lambda t: abs(t - f))
    tabled = abs(near - f) <= 0.05 * f
    rows = leg[near]
    heads = [h for h, _ in rows]
    j = bisect.bisect_left(heads, deg)
    if j == 0:
        t = rows[0][1]
    elif j == len(rows):
        t = rows[-1][1]
    else:
        (h0, t0), (h1, t1) = rows[j - 1], rows[j]
        t = t0 + (t1 - t0) * (deg - h0) / (h1 - h0) if h1 > h0 else t0
    if not tabled:
        t *= near / f        # group speed ∝ period in deep water; a stand-in, flagged
    return t, tabled


def in_windows(deg: float, windows: list[dict]) -> bool:
    return any(w["from"] <= deg <= w["to"] for w in windows)


def build(now_path: Path) -> dict:
    now = json.loads(now_path.read_text(encoding="utf-8"))
    when = datetime.fromisoformat(now["observed_utc"].replace("Z", "+00:00"))
    spectra = [s for s in load_spectra(SPECTRA) if s.time == when]
    if not spectra:
        sys.exit(f"no 46232 spectrum at {now['observed_utc']} in {SPECTRA}")
    spectrum = spectra[0].with_spread("mem")
    grids = density_grids(spectrum)
    split = buoy_split(spectrum, grids)
    owner = _buoy_owner(split)
    tables = load_tables()
    rad = math.radians(1.0)
    out = {"observed_utc": now["observed_utc"], "breaks": {}}
    for b in now["breaks"]:
        table = tables[b["id"]]
        carried = carry(spectrum, table, grids, split)
        leg = legs(b["id"])
        shown = (b.get("nearshore") or {}).get("trains") or []
        rows = []
        for n, (row, t) in enumerate(zip(shown, carried.trains[:3])):
            # The rows are the carried trains scaled, all by one factor, to the
            # breaking height (`nearshore.summarise`); same order, same heading.
            if row["period_s"] != round(t.period_s, 1) or row["from_deg"] != round(t.from_deg):
                sys.exit(f"{b['id']} row {n}: now.json {row['period_s']} s {row['from_deg']}°, "
                         f"rebuilt {t.period_s:.1f} s {t.from_deg:.0f}°")
            arc = set(_arc_degrees(t.arc))
            mine = set(t.buoys or ()) | ({t.buoy} if t.buoy is not None else set())
            divided = bool(t.buoys)
            # [bin, degree FROM offshore, energy at the buoy, energy reaching 5 m
            #  (shoaling divided out, as the window step compares), its 5 m
            #  heading, minutes after 46232, energy at 5 m with shoaling]
            streams = []
            tot = {"buoy": 0.0, "window": 0.0, "hard": 0.0, "soft": 0.0, "friction": 0.0, "five": 0.0}
            untabled = 0
            for i in t.bins:
                f = spectrum.frequencies[i]
                grid = grids.get(i)
                if grid is None:
                    continue
                width = spectrum.bin_width(i)
                near_f = min(table.by_freq, key=lambda q: abs(q - f))
                ks2 = shoaling_squared(f, table.start_depth_m)
                reached = [0.0] * 360
                five = [0.0] * 360
                hard = [0.0] * 360
                sn, cn = [0.0] * 360, [0.0] * 360
                for ray in table.by_freq[near_f]:
                    if ray.gain > 0:
                        k = int(ray.off_from) % 360
                        if k in arc and (not divided or owner(i, k) in mine):
                            hard[k] += at(grid, ray.off_from) * width * ray.width_rad * ray.gain / ks2
                    if ray.diff_gain <= 0:
                        continue
                    k = int(ray.diff_off_from) % 360
                    if k not in arc or (divided and owner(i, k) not in mine):
                        continue
                    e = at(grid, ray.diff_off_from) * width * ray.width_rad * ray.diff_gain
                    tot["soft"] += e / ks2
                    tot["friction"] += e * ray.diff_friction / ks2
                    tot["five"] += e * ray.diff_friction
                    five[k] += e * ray.diff_friction
                    e *= ray.diff_friction / ks2
                    reached[k] += e
                    th = math.radians(ray.near_from)
                    sn[k] += e * math.sin(th)
                    cn[k] += e * math.cos(th)
                tot["hard"] += sum(hard)
                for k in sorted(arc):
                    be = grid[k] * rad * width
                    if not (owner(i, k) in mine or not mine or reached[k] > 0):
                        be = 0.0
                    if be <= 0 and reached[k] <= 0:
                        continue
                    tot["buoy"] += be
                    if in_windows(k + 0.5, b["swell_window"]):
                        tot["window"] += be
                    nd = mins = None
                    if reached[k] > 0:
                        nd = round(math.degrees(math.atan2(sn[k], cn[k])) % 360, 1)
                        mins, tabled = arrival(leg, f, k + 0.5)
                        untabled += not tabled
                        mins = None if mins is None else round(mins, 1)
                    streams.append([i, k, be, reached[k], nd, mins, five[k]])
            five_hs = 4 * math.sqrt(tot["five"])
            if abs(five_hs - t.hs_m) > 0.002:
                sys.exit(f"{b['id']} row {n}: 5 m rebuilt {five_hs:.3f} m, chain {t.hs_m:.3f} m")
            top = max((s[2] for s in streams), default=0) or 1.0
            ftop = max((s[6] for s in streams), default=0) or 1.0
            rows.append({
                "period_s": row["period_s"], "from_deg": row["from_deg"],
                "near_from_deg": row.get("near_from_deg"),
                "bins": {str(i): round(1.0 / spectrum.frequencies[i], 2) for i in t.bins
                         if i in grids},
                "hs": {k: round(4 * math.sqrt(v), 3) for k, v in tot.items()},
                # the row's own number: its 5 m height scaled to the breaking height
                "row_hs_m": row["hs_m"],
                "untabled_streams": untabled,
                # energies scaled to the largest buoy cell, 4 figures
                "scale": top,
                "five_scale": ftop,
                "streams": [[s[0], s[1], round(s[2] / top, 4), round(s[3] / top, 4), s[4], s[5],
                             round(s[6] / ftop, 4)]
                            for s in streams if s[2] / top >= 1e-4 or s[3] / top >= 1e-4],
            })
        out["breaks"][b["id"]] = rows
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("now", type=Path)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    data = build(a.now)
    if a.json:
        print(json.dumps(data, separators=(",", ":")))
        return
    print("46232", data["observed_utc"])
    for bid, rows in data["breaks"].items():
        for n, r in enumerate(rows):
            ts = [s[5] for s in r["streams"] if s[5] is not None]
            print(f"{bid:16s} row {n}: {r['period_s']} s from {r['from_deg']}° -> 5 m {r['near_from_deg']}°  "
                  f"Hs {r['hs']}  streams {len(r['streams'])}  "
                  f"arrive {min(ts) if ts else '-'}-{max(ts) if ts else '-'} min  untabled {r['untabled_streams']}")


if __name__ == "__main__":
    main()
