"""The permanent record of what the forecast said, cycle by cycle.

Run: ``python -m forecast.forecastlog`` — appends the rows for
``data/live/forecast.json`` to ``data/forecast_log/46232/YYYY-MM.csv``.

Why it exists. Everything else this project compares a forecast against can be
rebuilt at any time: the buoy's spectra, KNZY and the tide gauge are committed
here, and GFS-Wave's own spectrum is served by NOAA back to 2021 (BRIEFING §15).
What cannot be rebuilt is the forecast **as it was built and shown on the day**
— the chain changes (a charted edge, a new transfer table), and re-running an
old cycle through today's chain answers a different question. So this keeps it,
and keeps it small: every third hour (`publish.HOUR_STEP`, what the page offers),
one row per site, the numbers a reader saw and the few a later comparison needs.

It is never shown by itself. `forecast.live` reads it back for the 48 hours the
page reaches into the past (`past_hours`), and `forecast.modelbias` pairs it
with the measured reading at each hour. The measured side is NOT stored here:
it is recomputable from the committed archive, with any version of the chain.

One file per month of `generated_utc`, so a commit rewrites a bounded file and
a cycle's rows never straddle two files. Append-only and idempotent on
`generated_utc`: re-running the same build adds nothing.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR, ISO

STATION = "46232"
#: Must match `publish.HOUR_STEP` and the page's `lead_h % 3` filter; a test
#: pins it. Imported there rather than here to keep this module dependency-free.
HOUR_STEP = 3
#: How far back the page reaches (owner's decision, 2026-09-26).
PAST_HOURS = 48

BUOY = "buoy"

FIELDS = (
    "generated_utc", "cycle_utc", "valid_utc", "lead_h", "wave_source", "site",
    # The number the card showed, and what it was: the breaking height
    # ("breaking"), the figure at 5 m of water when there was no tide ("5m"),
    # the straight-line window figure when there were no transfer tables
    # ("window"), or the buoy's own Hs ("buoy").
    "hs_m", "hs_basis", "depth_m",
    # Tide-independent: swell and local chop together at the start depth. The
    # forecast's tide is a prediction plus a persisted departure and the
    # measured reading's is the gauge, so comparing breaking heights mixes a
    # tide error into a wave error. This is the figure the bias report uses.
    "hs_5m_m",
    "hs_window_m", "hs_offshore_m", "period_s", "from_deg",
    "build_sha",
)


def _num(value, digits: int = 3) -> str:
    return "" if value is None else str(round(float(value), digits))


def rows(forecast: dict, *, step: int = HOUR_STEP, build_sha: str = "") -> list[dict]:
    """One row per offered hour per site, from a forecast as `live.write` wrote it."""

    breaks = forecast.get("breaks") or []
    if not breaks or not forecast.get("cycle_utc"):
        return []
    buoy = {b["valid_utc"]: b for b in forecast.get("buoy") or []}
    base = {
        "generated_utc": forecast["generated_utc"],
        "cycle_utc": forecast["cycle_utc"],
        "wave_source": forecast.get("wave_source", ""),
        "build_sha": build_sha,
    }
    out: list[dict] = []
    first = breaks[0].get("hours") or []
    for n, hour in enumerate(first):
        if hour.get("lead_h", 0) % step:
            continue
        valid = hour["valid_utc"]
        at = {**base, "valid_utc": valid, "lead_h": hour["lead_h"]}
        # The buoy's figure is the model's own spectrum at 46232 when there is
        # one; on the partitions path it is the partitions' total, which every
        # break carries as `hs_offshore_m`.
        seen = buoy.get(valid)
        out.append({
            **at, "site": BUOY,
            "hs_m": _num(seen["hs_m"] if seen else hour.get("hs_offshore_m")),
            "hs_basis": BUOY, "depth_m": "", "hs_5m_m": "", "hs_window_m": "",
            "hs_offshore_m": _num(seen["hs_m"] if seen else hour.get("hs_offshore_m")),
            "period_s": _num(seen.get("peak_period_s") if seen else None, 1),
            "from_deg": _num(seen.get("peak_direction_deg") if seen else None, 0),
        })
        for entry in breaks:
            h = (entry.get("hours") or [])[n] if n < len(entry.get("hours") or []) else {}
            if h.get("valid_utc") != valid:
                continue
            near = h.get("nearshore") or {}
            broke = near.get("breaking")
            if h.get("hs_nearshore_m") is not None:
                basis = "breaking" if broke else "5m"
                headline = h["hs_nearshore_m"]
                depth = broke["depth_m"] if broke else near.get("depth_m")
            else:
                basis, headline, depth = "window", h.get("hs_window_m"), None
            out.append({
                **at, "site": entry["id"],
                "hs_m": _num(headline), "hs_basis": basis, "depth_m": _num(depth, 2),
                "hs_5m_m": _num((near.get("effects") or {}).get("with_chop_hs_m")),
                "hs_window_m": _num(h.get("hs_window_m")),
                "hs_offshore_m": _num(h.get("hs_offshore_m")),
                "period_s": _num(h.get("dominant_period_s"), 1),
                "from_deg": _num(h.get("dominant_from_deg"), 0),
            })
    return out


def log_dir(data_dir: Path = DEFAULT_DATA_DIR, station: str = STATION) -> Path:
    return Path(data_dir) / "forecast_log" / station


def read(directory: Path) -> list[dict]:
    """Every logged row, oldest file first. Missing directory: no rows."""

    out: list[dict] = []
    if not directory.is_dir():
        return out
    for path in sorted(directory.glob("*.csv")):
        with path.open(newline="", encoding="utf-8") as fh:
            out.extend(csv.DictReader(fh))
    return out


def append(forecast: dict, directory: Path, *, build_sha: str = "") -> int:
    """Append this build's rows. Returns how many were written (0 if already logged)."""

    new = rows(forecast, build_sha=build_sha)
    if not new:
        return 0
    generated = forecast["generated_utc"]
    path = directory / f"{generated[:7]}.csv"
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fh:
            if any(r.get("generated_utc") == generated for r in csv.DictReader(fh)):
                return 0
    directory.mkdir(parents=True, exist_ok=True)
    fresh = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        if fresh:
            writer.writeheader()
        writer.writerows(new)
    return len(new)


def _parse(stamp: str) -> datetime:
    return datetime.strptime(stamp, ISO).replace(tzinfo=timezone.utc)


def past_hours(logged: list[dict], generated_utc: str, *,
               hours: int = PAST_HOURS, step: int = HOUR_STEP) -> list[dict]:
    """What the page showed for each offered hour in the `hours` before `generated_utc`.

    For each hour, the row from the LATEST build whose `generated_utc` is at or
    before that hour: the forecast a reader could actually have seen for it in
    advance. A cycle's own first hours are not that — GFS-Wave publishes ~5 h
    after its nominal time, so they were already past when it appeared — and
    neither is a later cycle's view of an hour that had gone by. An hour no
    build covered in advance is left out, never filled from a later one.
    """

    until = _parse(generated_utc)
    since = until - timedelta(hours=hours)
    # valid_utc -> generated_utc -> site -> row
    by_valid: dict[str, dict[str, dict[str, dict]]] = {}
    for row in logged:
        try:
            valid = _parse(row["valid_utc"])
        except (KeyError, ValueError):
            continue
        if not (since <= valid < until) or valid.hour % step:
            continue
        if row.get("generated_utc", "") > row["valid_utc"]:
            continue
        by_valid.setdefault(row["valid_utc"], {}).setdefault(
            row["generated_utc"], {})[row["site"]] = row

    out = []
    for valid in sorted(by_valid):
        builds = by_valid[valid]
        shown = builds[max(builds)]
        buoy = shown.get(BUOY)
        any_row = next(iter(shown.values()))
        out.append({
            "valid_utc": valid,
            "generated_utc": any_row["generated_utc"],
            "cycle_utc": any_row["cycle_utc"],
            "lead_h": int(any_row["lead_h"]),
            "wave_source": any_row.get("wave_source", ""),
            "buoy": _entry(buoy) if buoy else None,
            "breaks": {site: _entry(r) for site, r in shown.items() if site != BUOY},
        })
    return out


def _float(value: str | None):
    return float(value) if value not in (None, "") else None


def _entry(row: dict) -> dict:
    return {
        "hs_m": _float(row.get("hs_m")),
        "hs_basis": row.get("hs_basis", ""),
        "depth_m": _float(row.get("depth_m")),
        "hs_5m_m": _float(row.get("hs_5m_m")),
        "hs_window_m": _float(row.get("hs_window_m")),
        "period_s": _float(row.get("period_s")),
        "from_deg": _float(row.get("from_deg")),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--forecast", type=Path, default=None,
                        help="default: <data-dir>/live/forecast.json")
    args = parser.parse_args(argv)

    source = args.forecast or Path(args.data_dir) / "live" / "forecast.json"
    forecast = json.loads(source.read_text(encoding="utf-8"))
    sha = os.environ.get("GITHUB_SHA", "")[:7]
    written = append(forecast, log_dir(args.data_dir), build_sha=sha)
    print(f"{written} row(s) logged for build {forecast.get('generated_utc')}"
          if written else f"build {forecast.get('generated_utc')} already logged, or empty")
    return 0


if __name__ == "__main__":
    sys.exit(main())
