"""Archive the Coronado hubs' receiver temperatures from CSULB Shark Lab's ERDDAP.

    python -m collector.sharklab

Each Coronado hub carries an Innovasea receiver whose status reports an
`ambient_temperature`. Measured (BRIEFING §47, `probe_sharklab --temps`): it
is the water's, at the receiver's ~1-2 m -- +0.6 °C against the lab's
AquaMeasure sensors on 19,129 pairs, the same day and night, and at
Coronado -0.4 °C against 46232 through September and October 2026. The
Briefing's Water row reads it (`forecast.briefing.water_now`).

What the source is, and what that costs:

- The lab downloads from Innovasea ONCE A NIGHT, a whole UTC day at a time,
  the next day; days go missing and stay missing; and every row is stored
  twice, as exact copies (probe runs 8-12). So each collection re-reads a
  trailing window, keeps each reading once, and never fills a gap.
- A stamp that comes back with a different value keeps the first and is
  counted, never overwritten. Every row carries `first_seen_utc`, so the
  delay from reading to archive is measured, not assumed.
- Which break a hub serves is read off its own newest position in the
  water against spots.json (a hub on land sits by the lifeguard station,
  both hubs within 10 m of each other), and kept in `hubs.json`.
- A hub whose detections name a receiver other than the registry's warns:
  a swapped receiver would otherwise be read as the old one's water.

Plain http, and denied from a Claude session: an Actions job only.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import timedelta
from pathlib import Path

from . import probe_sharklab as lab
from .common import DEFAULT_DATA_DIR, parse_iso, to_iso, utcnow, write_step_summary

REGISTRY = Path(__file__).resolve().parent / "sharklab.json"

#: Each collection re-reads this far back: a day lands the next day, and a
#: later night can bring a day the one before did not have.
TRAILING_H = 72

#: A fix this far seaward of its nearest break's shoreline is in the water
#: (probe: deployed ~460-480 m out, on land ~190 m inland).
IN_WATER_M = lab.IN_WATER_M

FIELDS = ("timestamp_utc", "device_time_ms", "ambient_temperature", "tilt", "first_seen_utc")

#: The lab's data changes once a night, so a collection fetches only when the
#: last fetch is at least this old (owner's call, 2026-10-29: the step took
#: ~50 s of every 3-minute collection). Kept in `state.json`.
MIN_INTERVAL_MIN = 60

STATE = "state.json"


def read_state(data_dir: Path) -> dict:
    path = Path(data_dir) / "sharklab" / STATE
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_state(data_dir: Path, state: dict) -> None:
    path = Path(data_dir) / "sharklab" / STATE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def due(state: dict, now, min_interval_min: float) -> bool:
    last = parse_iso(state.get("last_fetch_utc"))
    return last is None or (now - last).total_seconds() >= min_interval_min * 60


def registry(path: Path = REGISTRY) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def archive_path(data_dir: Path, receiver: str, month: str) -> Path:
    return Path(data_dir) / "sharklab" / receiver / f"{month}.csv"


def store(data_dir: Path, receiver: str, readings: list[dict], seen: str) -> tuple[int, int]:
    """Append each reading not already archived, by its device stamp, to its
    month's file. Returns (added, conflicts): a stamp archived with other
    values keeps the first and counts one conflict."""

    added = conflicts = 0
    by_month: dict[str, list[dict]] = {}
    for r in readings:
        by_month.setdefault(r["timestamp_utc"][:7], []).append(r)
    for month, rows in sorted(by_month.items()):
        path = archive_path(data_dir, receiver, month)
        have: dict[str, dict] = {}
        if path.exists():
            with path.open(newline="", encoding="utf-8") as fh:
                have = {row["device_time_ms"]: row for row in csv.DictReader(fh)}
        new = []
        for r in sorted(rows, key=lambda x: int(x["device_time_ms"])):
            old = have.get(r["device_time_ms"])
            if old is None:
                row = {**r, "first_seen_utc": seen}
                have[r["device_time_ms"]] = row
                new.append(row)
            elif (old["ambient_temperature"], old["tilt"]) != (r["ambient_temperature"], r["tilt"]):
                conflicts += 1
        if not new:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        fresh = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDS)
            if fresh:
                writer.writeheader()
            writer.writerows(new)
        added += len(new)
    return added, conflicts


def readings(fetched: "lab.Fetched") -> dict[str, list[dict]]:
    """Each receiver's readings, each once (the lab stores every row twice),
    in the archive's form. A stamp or value that does not parse is left out."""

    out: dict[str, dict[str, dict]] = {}
    cols = [lab.column(fetched, n) for n in ("device_time_utc", "serial_number",
                                              "ambient_temperature", "tilt")]
    for ms, rx, temp, tilt in zip(*cols):
        when = lab.parse_time(ms)
        if when is None or not lab._is_number(temp):
            continue
        out.setdefault(rx, {}).setdefault(ms, {
            "timestamp_utc": to_iso(when), "device_time_ms": ms,
            "ambient_temperature": temp, "tilt": tilt})
    return {rx: list(rows.values()) for rx, rows in out.items()}


def hub_breaks(fetched: "lab.Fetched", spots, before: dict) -> dict:
    """Each hub's break, from its newest fix in the water; a hub with none in
    the window keeps what `before` said."""

    out = {k: dict(v) for k, v in before.items()}
    newest: dict[str, tuple] = {}
    cols = [lab.column(fetched, n) for n in ("device_time_utc", "serial_number", "latitude", "longitude")]
    for ms, hub, la, lo in zip(*cols):
        when = lab.parse_time(ms)
        try:
            lat, lon = float(la), float(lo)
        except ValueError:
            continue
        if when is None or lat != lat or lon != lon or lab.seaward_m(lat, lon, spots) <= IN_WATER_M:
            continue
        if hub not in newest or when > newest[hub][0]:
            newest[hub] = (when, lat, lon)
    for hub, (when, lat, lon) in newest.items():
        spot, km = lab.nearest_break(lat, lon, spots)
        out[hub] = {"break": spot, "lat": round(lat, 6), "lon": round(lon, 6),
                    "fix_utc": to_iso(when), "km_from_break": round(km, 2)}
    return out


def receiver_swaps(fetched: "lab.Fetched", hubs: dict) -> list[str]:
    """Hubs whose detections in the window name a receiver other than the
    registry's."""

    seen: dict[str, set] = {}
    for hub, rx in zip(lab.column(fetched, "hub_serial"), lab.column(fetched, "serial_number")):
        seen.setdefault(hub, set()).add(rx)
    return [f"hub {hub}: registry says {hubs[hub]['receiver']}, detections name {', '.join(sorted(rxs))}"
            for hub, rxs in sorted(seen.items())
            if hub in hubs and rxs - {hubs[hub]["receiver"]}]


def collect(data_dir: Path = DEFAULT_DATA_DIR, backfill_from=None,
            min_interval_min: float = 0) -> tuple[list[str], int]:
    """One collection: the receivers over the trailing window (or, once,
    from `backfill_from`), each hub's break and the swap check over the
    trailing window. Skipped while the last fetch is under
    `min_interval_min` old; a backfill is never skipped."""

    reg = registry()
    lab.BASE = reg["base"].rstrip("/")
    hubs = reg["hubs"]
    receivers = sorted(h["receiver"] for h in hubs.values())
    now = utcnow()
    state = read_state(data_dir)
    if backfill_from is None and not due(state, now, min_interval_min):
        return [f"Shark Lab: last fetched {state.get('last_fetch_utc')}, under "
                f"{min_interval_min:.0f} min ago; the lab's data changes nightly, so not fetched."], 0
    since = now - timedelta(hours=TRAILING_H)
    window = backfill_from or since
    lines = [f"## Shark Lab receivers ({lab.BASE})", "", f"Run at {now:%Y-%m-%d %H:%M}Z, "
             + (f"a BACKFILL from {window:%Y-%m-%d}." if backfill_from else f"the last {TRAILING_H} h."), ""]

    rinfo, got = lab.dataset_info(lab.RECEIVER_STATUS)
    if not got.ok:
        return lines + [f"receiver status info failed: {got.error}"], 2 if got.denied else 1
    status = lab.fetch_csv(f"tabledap/{lab.RECEIVER_STATUS}.csv",
                           lab._q("device_time_utc,serial_number,ambient_temperature,tilt",
                                  lab._time_constraint(rinfo, window),
                                  f'serial_number=~"({"|".join(receivers)})"'), timeout=600)
    if status.empty:
        per = {}
    elif not status.ok:
        return lines + [f"receiver status failed: {status.error}"], 2 if status.denied else 1
    else:
        per = readings(status)
    seen = to_iso(now)
    for rx in receivers:
        added, conflicts = store(data_dir, rx, per.get(rx, []), seen)
        newest = max((r["timestamp_utc"] for r in per.get(rx, [])), default=None)
        lines.append(f"- receiver {rx}: {len(per.get(rx, []))} readings in the window, {added} new, "
                     f"{conflicts} changed since archived (kept as first seen), newest {newest or 'none'}")
    lines.append("")
    state["last_fetch_utc"] = seen
    if backfill_from:
        # Backfilled rows carry the backfill's first_seen_utc, which is when
        # this archive first held them, not when the lab loaded them: a lag
        # measured on first_seen_utc must leave these runs out.
        state.setdefault("backfills", []).append({"run_utc": seen, "from_utc": to_iso(backfill_from)})
    write_state(data_dir, state)

    hinfo, _ = lab.dataset_info(lab.HUB_STATUS)
    fixes = lab.fetch_csv(f"tabledap/{lab.HUB_STATUS}.csv",
                          lab._q("device_time_utc,serial_number,latitude,longitude",
                                 lab._time_constraint(hinfo, since),
                                 f'serial_number=~"({"|".join(sorted(hubs))})"'), timeout=300)
    hubs_file = Path(data_dir) / "sharklab" / "hubs.json"
    before = json.loads(hubs_file.read_text(encoding="utf-8")) if hubs_file.exists() else {}
    placed = (hub_breaks(fixes, lab.breaks(), before) if fixes.ok
              else {k: dict(v) for k, v in before.items()})
    for hub in sorted(hubs):
        placed.setdefault(hub, {})["receiver"] = hubs[hub]["receiver"]
    if placed != before:
        hubs_file.parent.mkdir(parents=True, exist_ok=True)
        hubs_file.write_text(json.dumps(placed, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for hub, v in sorted(placed.items()):
        lines.append(f"- hub {hub} (receiver {v.get('receiver')}): {v.get('break', 'not placed')}, "
                     f"from its fix in the water at {v.get('fix_utc', '-')}")
    if not fixes.ok and not fixes.empty:
        lines.append(f"- hub status failed: {fixes.error}; breaks kept as they were")
    lines.append("")

    dinfo, _ = lab.dataset_info(lab.DETECTIONS)
    det = lab.fetch_csv(f"tabledap/{lab.DETECTIONS}.csv",
                        lab._q("hub_serial,serial_number", lab._time_constraint(dinfo, since),
                               f'hub_serial=~"({"|".join(sorted(hubs))})"', "distinct()"), timeout=300)
    swaps = receiver_swaps(det, hubs) if det.ok else []
    for s in swaps:
        print(f"::warning title=Shark Lab receiver changed::{s}. Update collector/sharklab.json.",
              file=sys.stderr)
        lines.append(f"- **receiver changed**: {s}")
    return lines, 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Archive the Coronado hubs' receiver temperatures.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--min-interval-min", type=float, default=0,
                        help="Skip when the last fetch is under this many minutes old.")
    parser.add_argument("--backfill-from", default=None, metavar="YYYY-MM-DD",
                        help="Once: read the receivers from this date, not the trailing window.")
    args = parser.parse_args(argv)
    start = None
    if args.backfill_from:
        from datetime import datetime, timezone

        start = datetime.strptime(args.backfill_from, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    lines, code = collect(args.data_dir, start, args.min_interval_min)
    text = "\n".join(lines)
    print(text)
    write_step_summary(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
