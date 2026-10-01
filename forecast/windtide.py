"""The wind and the tide, hour by hour, for the charts on the Wind and Tide cards.

Run: ``python -m forecast.windtide`` — writes ``data/live/windtide.json``.

Owner's request, 2026-09-30: a chart under each of those cards, like the
Swell card's. On the Now tab it is what was MEASURED; on the Forecast tab the
same measured hours sit beside the forecast (which comes from
`forecast.json`, never from here).

**Read straight from the archives, not rebuilt.** Unlike the swell's series
(`forecast.series`), nothing here passes through a chain: KNZY's METARs and
the gauge's samples are the measurements themselves, committed as they
arrive, so an hour is read, never recomputed, and today's code cannot change
a past hour.

**One slot per UTC hour, and a missing reading is a gap in it.**

- ``wind``: the newest KNZY report taken in the hour up to the slot, (H−1 h,
  H] — the routine METAR at :52 in the hour before, or a SPECI after it. Each
  report lands in exactly one slot and a slot is never filled from the hour
  beside it: a missed METAR is a gap, where `measured` would carry the
  previous one for up to two hours (`now.WIND_AS_OF_HOURS`), because a line
  drawn through a carried reading looks like a second measurement. How many
  minutes before the slot it was taken is kept, so the page can say when. A
  calm (0 kt) or variable report has a speed and no direction.
- ``tide_m``: the gauge's sample stamped exactly at the hour, carried to the
  open coast on its MLLW (`tidesite.coast_height`, the Tide card's own
  number) — never the :06 sample, and never interpolated across a gap.

**The one modelled number: the next 24 h of harmonic prediction** (owner's
call: the Now card already carries a predicted turn, labelled). The bay's
prediction carried to the open coast, with the gauge's measured departure from
it over the last 3 days (`tidesite.anomaly`), as the card's turn heights and
the forecast's tide carry — bare, it would sit ~0.2 m under the measured line
beside it. It is kept under its own key and the page labels it.

Derived and gitignored like the rest of ``data/live/``. It reaches back
`REACH_HOURS` (the chart's 1M button); the archives themselves go on.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR, ISO

from .live import TIDE_STATION, TIDE_STATION_NAME, WIND_STATION, WIND_STATION_NAME
from .tidesite import (ANOMALY_HOURS, SITE_NAME, _read, anomaly, coast_height, coast_predicted,
                       predicted_series)

#: How far back the charts reach: a month, the chart's 1M.
REACH_HOURS = 31 * 24
#: How far ahead the Now tab's tide prediction runs (owner's call).
PREDICT_HOURS = 24


def _utc(stamp: str) -> datetime:
    return datetime.strptime(stamp, ISO).replace(tzinfo=timezone.utc)


def _num(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def slots(until: datetime, hours: int = REACH_HOURS) -> list[datetime]:
    """`hours` consecutive UTC hours ending at the one `until` falls in."""

    last = until.replace(minute=0, second=0, microsecond=0)
    return [last - timedelta(hours=n) for n in range(hours - 1, -1, -1)]


def read_wind(data_dir: Path) -> list[dict]:
    """KNZY's reports, oldest first, one per observation time."""

    path = Path(data_dir) / "wind" / f"{WIND_STATION}.csv"
    if not path.exists():
        return []
    by_time: dict[str, dict] = {}
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("observed_utc"):
                by_time[row["observed_utc"]] = row      # a revision replaces
    return [by_time[k] for k in sorted(by_time)]


def wind_slots(rows: list[dict], hours: list[datetime]) -> dict[str, list]:
    """Per slot: direction, speed, gust, and minutes before the slot it was taken."""

    out = {"from_deg": [], "kt": [], "gust_kt": [], "age_min": []}
    stamps = [r["observed_utc"] for r in rows]
    for slot in hours:
        hi = bisect.bisect_right(stamps, slot.strftime(ISO))
        row = rows[hi - 1] if hi else None
        if row is None or _utc(row["observed_utc"]) <= slot - timedelta(hours=1):
            for key in out:
                out[key].append(None)
            continue
        kt = _num(row.get("wind_kt"))
        direction = _num(row.get("wind_from_deg"))
        # Calm has no direction (METAR writes it 00000KT), and neither does
        # a variable wind.
        if row.get("variable") == "1" or not kt:
            direction = None
        out["from_deg"].append(None if direction is None else round(direction) % 360)
        out["kt"].append(None if kt is None else round(kt, 1))
        gust = _num(row.get("gust_kt"))
        out["gust_kt"].append(None if gust is None else round(gust, 1))
        out["age_min"].append(round((slot - _utc(row["observed_utc"])).total_seconds() / 60))
    return out


def tide_slots(data_dir: Path, hours: list[datetime]) -> list[float | None]:
    """The gauge's sample at each hour exactly, on the open coast's MLLW."""

    path = Path(data_dir) / "tide" / f"{TIDE_STATION}_observed.csv"
    wanted = {h.strftime(ISO) for h in hours}
    found: dict[str, float] = {}
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                stamp = row.get("time_utc")
                value = _num(row.get("height_m"))
                if stamp in wanted and value is not None:
                    found[stamp] = value
    return [round(coast_height(found[k]), 3) if k in found else None
            for k in (h.strftime(ISO) for h in hours)]


def departure_slots(data_dir: Path, hours: list[datetime]) -> tuple[list, list]:
    """The gauge's measured departure from its own harmonic prediction at each
    hour, and the trailing mean of it the forecast carries, both on the open
    coast (scaled as the card's correction is).

    The hourly figure is the sample at the hour less the prediction for it,
    or None where either is missing. The mean is `tidesite.anomaly`'s, worked
    for every hour: all the hourly pairs in the `ANOMALY_HOURS` up to it,
    whatever their number -- what a forecast built at that hour would have
    added, not a smoothed line of this chart's own."""

    tide = Path(data_dir) / "tide"
    observed = dict(_read(tide / f"{TIDE_STATION}_observed.csv"))
    predicted = dict(_read(tide / f"{TIDE_STATION}_predicted.csv"))
    pairs = sorted((t, v - predicted[t]) for t, v in observed.items() if t in predicted)
    times = [t for t, _ in pairs]
    each, mean = [], []
    for slot in hours:
        dep = observed.get(slot)
        dep = None if dep is None or slot not in predicted else dep - predicted[slot]
        each.append(None if dep is None else round(coast_height(dep), 3))
        lo = bisect.bisect_left(times, slot - timedelta(hours=ANOMALY_HOURS))
        hi = bisect.bisect_right(times, slot)
        window = [d for _, d in pairs[lo:hi]]
        mean.append(round(coast_height(sum(window) / len(window)), 3) if window else None)
    return each, mean


def prediction(data_dir: Path, now: datetime, hours: int = PREDICT_HOURS) -> dict:
    """The next `hours` of harmonic prediction at the open coast, hourly from
    the hour `now` falls in, with the measured departure added."""

    start = now.replace(minute=0, second=0, microsecond=0)
    departure, n = anomaly(data_dir, now)
    series = predicted_series(data_dir)
    heights = []
    for k in range(hours + 1):
        value = coast_predicted(series, start + timedelta(hours=k), departure)
        heights.append(None if value is None else round(value, 3))
    return {
        "start_utc": start.strftime(ISO),
        "heights_m": heights,
        "departure_m": None if departure is None else round(coast_height(departure), 3),
        "departure_hours": ANOMALY_HOURS,
        "departure_pairs": n,
    }


def build(data_dir: Path = DEFAULT_DATA_DIR, *, now: datetime | None = None,
          hours: int = REACH_HOURS) -> dict:
    moment = now or datetime.now(timezone.utc)
    marks = slots(moment, hours)
    wind = wind_slots(read_wind(data_dir), marks)
    tide = tide_slots(data_dir, marks)
    # Before either archive began there is nothing to show, not a gap: the
    # chart starts at the first hour anything was collected.
    first = next((i for i in range(len(marks))
                  if wind["kt"][i] is not None or tide[i] is not None), len(marks) - 1)
    marks, tide = marks[first:], tide[first:]
    wind = {key: values[first:] for key, values in wind.items()}
    departure, departure_mean = departure_slots(data_dir, marks)
    return {
        "generated_utc": moment.strftime(ISO),
        "start_utc": marks[0].strftime(ISO),
        "hours": len(marks),
        "step_h": 1,
        "wind_station": WIND_STATION,
        "wind_station_name": WIND_STATION_NAME,
        "tide_station": TIDE_STATION,
        "tide_station_name": TIDE_STATION_NAME,
        "tide_site": SITE_NAME,
        "wind": wind,
        "tide_m": tide,
        "departure_m": departure,
        "departure_mean_m": departure_mean,
        "departure_hours": ANOMALY_HOURS,
        "prediction": prediction(data_dir, moment),
        "standing_on": {
            "wind": f"OBSERVED — {WIND_STATION}'s METAR taken in the hour up to each slot; "
                    "an hour without one is a gap, never the report beside it",
            "tide": f"OBSERVED — {TIDE_STATION}'s sample at each hour exactly, carried to the "
                    "open coast; an hour without one is a gap",
            "departure": f"OBSERVED less PREDICTED — {TIDE_STATION}'s sample at each hour "
                         "less its harmonic prediction, on the open coast, and the trailing "
                         f"{ANOMALY_HOURS // 24}-day mean the forecast adds",
            "prediction": f"PREDICTED — the harmonic tide at {TIDE_STATION} for the next "
                          f"{PREDICT_HOURS} h, carried to the open coast, plus the gauge's "
                          f"measured departure from it over the last {ANOMALY_HOURS // 24} days",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    got = build(args.data_dir)
    out = args.out or Path(args.data_dir) / "live" / "windtide.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(got, separators=(",", ":")), encoding="utf-8")
    winds = sum(v is not None for v in got["wind"]["kt"])
    tides = sum(v is not None for v in got["tide_m"])
    print(f"Wrote {out}: {got['hours']} hour(s), wind in {winds}, tide in {tides}, "
          f"{sum(v is not None for v in got['prediction']['heights_m'])} predicted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
