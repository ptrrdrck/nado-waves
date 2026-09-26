"""Does GFS-Wave's bias at 46232 survive each break's windows?

Run: ``python -m forecast.modelbias`` — the report, from the logs on disk.
     ``python -m forecast.modelbias --recompute 2026-08-04 2026-09-25`` — ON
     ACTIONS: rebuild each 00Z cycle in that span with today's chain (617 MB
     streamed per cycle from NOAA) into ``data/forecast_log/46232_recomputed/``.

BRIEFING §5 measured GFS-Wave **0.26–0.31 m low** at 46232, at every lead, and
a fixed two-parameter correction cut RMSE by about half; §4 found that a
correction which keeps adapting buys nothing a fixed one does not. Neither was
measured THROUGH a break's windows: both compared the bulletin's total Hs with
the buoy's. The windows take most of the westerly wind sea (§14), so a bias
that lives there could all but vanish at the breaks — or the opposite. This
report measures that, and nothing more. **It reports and never edits**: no
forecast number changes on the strength of it (owner's decision, 2026-09-26).
Applying a correction is a separate decision, and one that has to settle what
`info.html`'s confidence levels call it first — "calibration" is reserved for
the beach log.

What is compared, per logged hour:

* **buoy** — the forecast's Hs at 46232 against the buoy's own spectrum.
* **5 m** — each break's swell and local chop at 5 m of water, forecast
  against measured through the same chain (`forecast.measured`). Tide-free, so
  a tide error does not pass for a wave error.
* **breaking** — each break's headline, only where both sides broke; the tide
  is in this one (prediction plus persisted departure, against the gauge).

Both sides pass through identical physics, so any error in the windows, seabed
or surf zone cancels: this is the MODEL's error at the buoy, seen at each
break. It says nothing about the beach, which nothing measures.

Regime follows §5: "south" is a measured buoy peak of 14 s or longer from
160–230°, everything else "other". Gaps and not-yet-collected hours are
dropped, never filled.

Two logs, never mixed. ``46232/`` is what was built and shown on the day;
``46232_recomputed/`` is a later rebuild of past cycles with the chain of the
day it ran, so the report does not have to wait months for the first log to
fill. They answer slightly different questions and are reported apart.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR, ISO

from . import forecastlog
from .verify import Pair, error_stats, fit_correction

STATION = forecastlog.STATION
BREAKS = ("coronado_north", "coronado_center", "coronado_south")
SOUTH_MIN_PERIOD_S = 14.0
SOUTH_FROM = (160.0, 230.0)
#: Lead buckets, inclusive: short enough to see growth, wide enough to fill.
LEADS = ((0, 11), (12, 35), (36, 59), (60, 95), (96, 143), (144, 168))
#: Below this a two-parameter fit describes the weather, not the model.
MIN_FIT = 30


def recomputed_dir(data_dir: Path = DEFAULT_DATA_DIR) -> Path:
    return Path(data_dir) / "forecast_log" / f"{STATION}_recomputed"


def regime(measured: dict) -> str:
    buoy = measured.get("buoy") or {}
    period, heading = buoy.get("period_s"), buoy.get("from_deg")
    if period is None or heading is None:
        return "other"
    south = period >= SOUTH_MIN_PERIOD_S and SOUTH_FROM[0] <= heading <= SOUTH_FROM[1]
    return "south" if south else "other"


def lead_bucket(lead_h: int) -> str | None:
    for low, high in LEADS:
        if low <= lead_h <= high:
            return f"{low}-{high} h"
    return None


def _float(value) -> float | None:
    return float(value) if value not in (None, "") else None


def samples(rows: list[dict], measured_at) -> list[dict]:
    """One sample per (row, quantity) with both sides present.

    `measured_at(valid: datetime) -> dict` is `measured.Rebuilder.at`, cached
    here because many builds forecast the same hour.
    """

    cache: dict[str, dict] = {}
    out = []
    for row in rows:
        valid = row["valid_utc"]
        if valid not in cache:
            moment = datetime.strptime(valid, ISO).replace(tzinfo=timezone.utc)
            cache[valid] = measured_at(moment)
        got = cache[valid]
        if got.get("gap") or got.get("pending") or "breaks" not in got:
            continue
        lead = int(row["lead_h"])
        base = {"valid": valid, "lead_h": lead, "regime": regime(got), "site": row["site"]}
        if row["site"] == forecastlog.BUOY:
            f, o = _float(row["hs_m"]), (got.get("buoy") or {}).get("hs_m")
            if f is not None and o is not None:
                out.append({**base, "quantity": "buoy", "forecast": f, "observed": o})
            continue
        seen = (got.get("breaks") or {}).get(row["site"]) or {}
        f5, o5 = _float(row.get("hs_5m_m")), seen.get("hs_5m_m")
        if f5 is not None and o5 is not None:
            out.append({**base, "quantity": "5 m", "forecast": f5, "observed": o5})
        if row.get("hs_basis") == "breaking" and seen.get("hs_basis") == "breaking":
            fb, ob = _float(row["hs_m"]), seen.get("hs_m")
            if fb is not None and ob is not None:
                out.append({**base, "quantity": "breaking", "forecast": fb, "observed": ob})
    return out


def _pairs(group: list[dict]) -> list[Pair]:
    return [Pair(datetime.strptime(s["valid"], ISO), s["lead_h"], s["forecast"], s["observed"])
            for s in group]


def summarise(found: list[dict]) -> list[dict]:
    """Stats per quantity x site x regime x lead bucket, plus all leads pooled."""

    keys: dict[tuple, list[dict]] = {}
    for s in found:
        bucket = lead_bucket(s["lead_h"])
        if bucket is None:
            continue
        for lead in (bucket, "all"):
            for reg in (s["regime"], "all"):
                keys.setdefault((s["quantity"], s["site"], reg, lead), []).append(s)
    out = []
    for (quantity, site, reg, lead), group in sorted(keys.items()):
        stats = error_stats(_pairs(group))
        entry = {"quantity": quantity, "site": site, "regime": reg, "lead": lead, **stats}
        if stats.get("n", 0) >= 2 and stats.get("mean_observed_m"):
            entry["bias_pct"] = 100 * stats["bias_m"] / stats["mean_observed_m"]
        if lead == "all" and len(group) >= MIN_FIT:
            entry["fit_a"], entry["fit_b"] = fit_correction(_pairs(group))
        out.append(entry)
    return out


def _fmt(v, spec: str) -> str:
    return "—" if v is None else format(v, spec)


def format_report(title: str, rows: list[dict], found: list[dict]) -> str:
    if not found:
        return f"## {title}\n\nNo pairs yet: no logged hour has a measured reading beside it.\n"
    first = min(s["valid"] for s in found)
    last = max(s["valid"] for s in found)
    lines = [f"## {title}", "",
             f"{len(rows)} logged rows; {len(found)} forecast/measured pairs, "
             f"valid {first} to {last}.", "",
             "Error = forecast − measured. Bias % is the bias over the mean measured height,",
             "the figure that can be compared between the buoy and a break whose heights are",
             "smaller. Fit is measured ≈ a + b × forecast, over all leads, where n ≥ "
             f"{MIN_FIT}.", ""]
    table = summarise(found)

    # The line the report exists for.
    lines += ["### Does the buoy's bias survive the windows? (all leads)", "",
              "| quantity | site | regime | n | bias m | bias % | sd m | fit a | fit b |",
              "|---|---|---|---|---|---|---|---|---|"]
    for e in table:
        if e["lead"] != "all" or e["quantity"] == "breaking":
            continue
        lines.append(
            f"| {e['quantity']} | {e['site']} | {e['regime']} | {e['n']} | "
            f"{_fmt(e.get('bias_m'), '+.3f')} | {_fmt(e.get('bias_pct'), '+.1f')} | "
            f"{_fmt(e.get('sd_m'), '.3f')} | {_fmt(e.get('fit_a'), '+.3f')} | "
            f"{_fmt(e.get('fit_b'), '.3f')} |")

    lines += ["", "### By lead (regime: all)", "",
              "| quantity | site | lead | n | bias m | bias % | RMSE m |",
              "|---|---|---|---|---|---|---|"]
    order = {f"{a}-{b} h": n for n, (a, b) in enumerate(LEADS)}
    for e in sorted((e for e in table if e["regime"] == "all" and e["lead"] != "all"),
                    key=lambda e: (e["quantity"], e["site"], order[e["lead"]])):
        lines.append(
            f"| {e['quantity']} | {e['site']} | {e['lead']} | {e['n']} | "
            f"{_fmt(e.get('bias_m'), '+.3f')} | {_fmt(e.get('bias_pct'), '+.1f')} | "
            f"{_fmt(e.get('rmse_m'), '.3f')} |")
    return "\n".join(lines) + "\n"


def report(data_dir: Path = DEFAULT_DATA_DIR) -> str:
    from .measured import Rebuilder

    rebuild = Rebuilder(data_dir)
    parts = ["# GFS-Wave at 46232, through each break's windows — measured",
             "",
             f"Generated by `python -m forecast.modelbias` on "
             f"{datetime.now(timezone.utc):%Y-%m-%d}. Reports, never edits: no forecast",
             "number changes because of it. The comparison is the model's error at the buoy",
             "carried in by the same chain on both sides; it checks nothing at the beach.",
             ""]
    for title, directory in (("As built and shown", forecastlog.log_dir(data_dir)),
                             ("Recomputed with a later chain", recomputed_dir(data_dir))):
        rows = forecastlog.read(directory)
        parts.append(format_report(title, rows, samples(rows, rebuild.at)))
    return "\n".join(parts)


def recompute(start: datetime, end: datetime, *, data_dir: Path = DEFAULT_DATA_DIR,
              hours: int = 168) -> int:
    """Rebuild every 00Z cycle from `start` to `end` into the recomputed log.

    Streams 617 MB per cycle from NOAA: run it on Actions, never a session.
    Idempotent: a cycle already in the log is skipped before anything is
    fetched.
    """

    from . import live

    directory = recomputed_dir(data_dir)
    done = {r["cycle_utc"] for r in forecastlog.read(directory)}
    written = 0
    cycle = start.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
    while cycle <= end:
        stamp = cycle.strftime(ISO)
        if stamp in done:
            print(f"{stamp}: already recomputed")
        else:
            # Published CYCLE_LAG_HOURS after the nominal time, as the live
            # job would have built it.
            moment = cycle + timedelta(hours=live.CYCLE_LAG_HOURS)
            got = live.build(data_dir=data_dir, hours=hours, now=moment, use_spectra=True)
            if got.cycle_utc != stamp:
                print(f"{stamp}: NOAA served {got.cycle_utc} instead; skipped")
            else:
                n = forecastlog.append(json.loads(json.dumps(asdict(got))), directory,
                                       build_sha="recomputed")
                written += n
                print(f"{stamp}: {n} row(s), {got.wave_source}")
        cycle += timedelta(days=1)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--recompute", nargs=2, metavar=("FROM", "TO"),
                        help="rebuild 00Z cycles FROM..TO (YYYY-MM-DD); Actions only")
    parser.add_argument("--out", type=Path, default=None, help="write the report here")
    args = parser.parse_args(argv)

    if args.recompute:
        start, end = (datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                      for d in args.recompute)
        print(f"{recompute(start, end, data_dir=args.data_dir)} row(s) recomputed")
        return 0

    text = report(args.data_dir)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
