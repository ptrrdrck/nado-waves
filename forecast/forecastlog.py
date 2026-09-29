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
with the measured reading at each hour.

Beside it, ``46232_shown/YYYY-MM.jsonl`` keeps each build's hours IN FULL for
the 48 h after it was published — what a past card needs to be drawn as it
was (`append_shown`). ``--seed-shown`` fills it for builds logged before it
existed, from the files the delivery repository actually published. The measured side is NOT stored here:
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


# --- What each build SHOWED, in full ------------------------------------------
#
# The CSV above keeps a headline per hour, forever, for the bias report. The
# page's past hours need more: the trains, what takes the swell, and the
# calculation behind the headline, so that 11 AM reads the same after 11 AM as
# it did before (owner's report, 2026-09-26: an earlier run's hour had lost its
# drawing and calculation because only the headline had been kept).
#
# So every build also writes, for each offered hour it covers from its own
# publication to `SHOWN_AHEAD_HOURS` later, the hour exactly as forecast.json
# carried it: each break's hour, the buoy and the tide. Only those hours can
# ever be picked as "what the page showed" (a build is chosen for an hour only
# if it was published before it), and 48 h ahead covers a day of missed
# builds. About 85 KB a build, appended, so git stores only the additions.

#: How far past its own publication a build's hours are kept in full.
SHOWN_AHEAD_HOURS = PAST_HOURS


def shown_dir(data_dir: Path = DEFAULT_DATA_DIR, station: str = STATION) -> Path:
    return Path(data_dir) / "forecast_log" / f"{station}_shown"


def shown_lines(forecast: dict, *, step: int = HOUR_STEP,
                ahead: int = SHOWN_AHEAD_HOURS) -> list[dict]:
    """The hours this build could be shown for, in full, from its forecast.json.

    Works on the hourly file `live.write` writes and on the 3-hourly one the
    delivery repository holds, which is what `--seed-shown` reads.
    """

    breaks = forecast.get("breaks") or []
    if not breaks or not forecast.get("cycle_utc") or not forecast.get("generated_utc"):
        return []
    generated = forecast["generated_utc"]
    limit = _parse(generated) + timedelta(hours=ahead)
    buoy = {b.get("valid_utc"): b for b in forecast.get("buoy") or []}
    tide = {t.get("valid_utc"): t for t in forecast.get("tide") or []}
    out = []
    for n, hour in enumerate(breaks[0].get("hours") or []):
        valid = hour.get("valid_utc", "")
        if hour.get("lead_h", 0) % step or valid < generated or _parse(valid) > limit:
            continue
        hours = {}
        for entry in breaks:
            theirs = entry.get("hours") or []
            if n < len(theirs) and theirs[n].get("valid_utc") == valid:
                hours[entry["id"]] = theirs[n]
        out.append({
            "generated_utc": generated, "cycle_utc": forecast["cycle_utc"],
            "valid_utc": valid, "lead_h": hour.get("lead_h"),
            "wave_source": forecast.get("wave_source", ""),
            "buoy": buoy.get(valid), "tide": tide.get(valid), "breaks": hours,
        })
    return out


def _shown_prefix(generated_utc: str) -> str:
    """How every line of one build starts: `generated_utc` is its first key."""

    return json.dumps({"generated_utc": generated_utc}, separators=(",", ":"))[:-1]


def append_shown(forecast: dict, directory: Path) -> int:
    """Append this build's shown hours. Returns how many (0 if already logged)."""

    lines = shown_lines(forecast)
    if not lines:
        return 0
    generated = forecast["generated_utc"]
    path = directory / f"{generated[:7]}.jsonl"
    prefix = _shown_prefix(generated)
    if path.exists():
        with path.open(encoding="utf-8") as fh:
            if any(line.startswith(prefix) for line in fh):
                return 0
    directory.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for line in lines:
            fh.write(json.dumps(line, separators=(",", ":")) + "\n")
    return len(lines)


def _month_after(month: str) -> str:
    year, mon = int(month[:4]), int(month[5:7])
    return f"{year + mon // 12:04d}-{mon % 12 + 1:02d}"


def read_shown(directory: Path, *, since: str = "") -> dict[tuple[str, str], dict]:
    """Shown hours keyed by (generated_utc, valid_utc), valid at or after `since`.

    A month's file holds builds from that month, whose hours reach at most
    48 h into the next, so older files are not opened at all.
    """

    out: dict[tuple[str, str], dict] = {}
    if not directory.is_dir():
        return out
    for path in sorted(directory.glob("*.jsonl")):
        if since and _month_after(path.stem) < since[:7]:
            continue
        with path.open(encoding="utf-8") as fh:
            for raw in fh:
                if not raw.strip():
                    continue
                line = json.loads(raw)
                if since and line.get("valid_utc", "") < since:
                    continue
                out[(line["generated_utc"], line["valid_utc"])] = line
    return out


def past_hours(logged: list[dict], generated_utc: str, *,
               hours: int = PAST_HOURS, step: int = HOUR_STEP,
               shown: dict[tuple[str, str], dict] | None = None) -> list[dict]:
    """What the page showed for each offered hour in the `hours` before `generated_utc`.

    For each hour, the row from the LATEST build whose `generated_utc` is at or
    before that hour: the forecast a reader could actually have seen for it in
    advance. A cycle's own first hours are not that — GFS-Wave publishes ~5 h
    after its nominal time, so they were already past when it appeared — and
    neither is a later cycle's view of an hour that had gone by. An hour no
    build covered in advance is left out, never filled from a later one.

    With `shown` (`read_shown`), each hour also carries `detail`: that SAME
    build's hour in full, so the page can draw the card it drew then. Never
    another build's: an hour whose own build kept no detail has none.
    """

    kept = shown or {}
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
        detail = kept.get((any_row["generated_utc"], valid))
        out.append({
            "valid_utc": valid,
            "detail": ({"buoy": detail.get("buoy"), "tide": detail.get("tide"),
                        "breaks": detail.get("breaks") or {}} if detail else None),
            "generated_utc": any_row["generated_utc"],
            "cycle_utc": any_row["cycle_utc"],
            "lead_h": int(any_row["lead_h"]),
            "wave_source": any_row.get("wave_source", ""),
            "buoy": _entry(buoy) if buoy else None,
            "breaks": {site: _entry(r) for site, r in shown.items() if site != BUOY},
        })
    return out


#: How many earlier model runs the Forecast tab's Runs chart draws beside the
#: current one: two days of cycles at four a day.
RUNS_KEPT = 8


def recent_runs(logged: list[dict], cycle_utc: str, *, keep: int = RUNS_KEPT,
                step: int = HOUR_STEP) -> list[dict]:
    """What each of the last `keep` model runs said, before the one being built.

    One entry per cycle, from that cycle's LATEST build (a cycle rebuilt with a
    changed chain says what the page showed last), oldest first. Each carries
    its headline per site at every offered hour it covered: the breaking
    height at a break, the model's own Hs at the buoy. A break's hour with any
    other basis -- the 5 m figure when there was no tide, the window figure
    before the tables -- is None, because it is another quantity and a line
    that switched to it would draw a step nothing caused. It is never filled.

    Nothing here says which run was right. It is what each said, side by side,
    for the Runs chart; the measured chain is the separate line beside it.
    """

    latest: dict[str, str] = {}
    for row in logged:
        cycle = row.get("cycle_utc", "")
        if not cycle or cycle >= cycle_utc:
            continue
        latest[cycle] = max(latest.get(cycle, ""), row.get("generated_utc", ""))
    chosen = sorted(latest)[-keep:] if keep > 0 else []
    wanted = {(c, latest[c]) for c in chosen}
    hours: dict[str, dict[str, dict[str, float | None]]] = {c: {} for c in chosen}
    for row in logged:
        key = (row.get("cycle_utc", ""), row.get("generated_utc", ""))
        if key not in wanted:
            continue
        try:
            if _parse(row["valid_utc"]).hour % step:
                continue
        except (KeyError, ValueError):
            continue
        site = row.get("site", "")
        basis = row.get("hs_basis", "")
        ok = basis == ("buoy" if site == BUOY else "breaking")
        hours[key[0]].setdefault(row["valid_utc"], {})[site] = _float(row.get("hs_m")) if ok else None

    out = []
    for cycle in chosen:
        valid = sorted(hours[cycle])
        if not valid:
            continue
        sites = sorted({site for by in hours[cycle].values() for site in by})
        start = _parse(valid[0])
        n = int((_parse(valid[-1]) - start).total_seconds() // (3600 * step)) + 1
        slots = [(start + timedelta(hours=step * i)).strftime(ISO) for i in range(n)]
        out.append({
            "cycle_utc": cycle,
            "generated_utc": latest[cycle],
            "start_utc": valid[0],
            "step_h": step,
            "hs_m": {site: [hours[cycle].get(v, {}).get(site) for v in slots] for site in sites},
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


def seed_shown(forecasts: list[dict], data_dir: Path = DEFAULT_DATA_DIR) -> list[str]:
    """Fill the shown log for builds logged before it existed, from what was published.

    The delivery repository's history holds every forecast.json the page was
    served, so for a build logged with headlines only, its published file IS
    the full detail of what was shown. The control makes that a check rather
    than an assumption: a file is used only if its build is already in the
    headline log AND every headline it carries matches the logged one.
    Anything else is reported and skipped, never guessed at. Idempotent.
    """

    logged: dict[str, dict[tuple[str, str], str]] = {}
    for row in read(log_dir(data_dir)):
        logged.setdefault(row["generated_utc"], {})[(row["valid_utc"], row["site"])] = row["hs_m"]
    report = []
    for forecast in forecasts:
        generated = forecast.get("generated_utc", "?")
        mine = logged.get(generated)
        if not mine:
            report.append(f"{generated}: not in the headline log; skipped")
            continue
        theirs = {(r["valid_utc"], r["site"]): r["hs_m"] for r in rows(forecast)}
        both = set(mine) & set(theirs)
        wrong = [k for k in both if mine[k] != theirs[k]]
        if not both or wrong:
            report.append(f"{generated}: {len(wrong)} of {len(both)} headlines differ "
                          f"from the log; skipped")
            continue
        n = append_shown(forecast, shown_dir(data_dir))
        report.append(f"{generated}: {len(both)} headlines match; "
                      + (f"{n} shown hour(s) seeded" if n else "already seeded"))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--forecast", type=Path, default=None,
                        help="default: <data-dir>/live/forecast.json")
    parser.add_argument("--seed-shown", type=Path, nargs="+", metavar="FILE",
                        help="published forecast.json files to fill the shown log from")
    args = parser.parse_args(argv)

    if args.seed_shown:
        files = [json.loads(p.read_text(encoding="utf-8")) for p in args.seed_shown]
        for line in seed_shown(files, args.data_dir):
            print(line)
        return 0

    source = args.forecast or Path(args.data_dir) / "live" / "forecast.json"
    forecast = json.loads(source.read_text(encoding="utf-8"))
    sha = os.environ.get("GITHUB_SHA", "")[:7]
    written = append(forecast, log_dir(args.data_dir), build_sha=sha)
    print(f"{written} row(s) logged for build {forecast.get('generated_utc')}"
          if written else f"build {forecast.get('generated_utc')} already logged, or empty")
    shown = append_shown(forecast, shown_dir(args.data_dir))
    print(f"{shown} shown hour(s) logged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
