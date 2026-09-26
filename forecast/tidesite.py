"""The water level at Coronado's breaks, from a gauge inside San Diego Bay.

    python -m forecast.tidesite       # re-measure the transfer from the archive

9410170 is at Broadway Pier, well up the harbour from the entrance; the breaks
are on the open coast outside it. For the tide CARD that is a labelled station
reading and needs nothing. For wave breaking it is an input — the depth the
waves break in — and the bay's tide is not the beach's.

MEASURED 2026-09-26 against La Jolla (9410230, the nearest open-coast gauge
with a measured record), 30 days of 6-minute data, 7,149 matched samples, each
gauge on its own MSL (1983–2001 epoch, CO-OPS datums):

    open coast = −0.024 m + 0.944 × bay,   rms 2.4 cm,   r = 0.9987
    the open coast leads the bay by ~3 minutes

CO-OPS's own subordinate stations either side of Coronado agree: Imperial
Beach ×0.93 highs / ×0.96 lows at 0 / −3 min, Point Loma ×0.92 at −9 / −2 min
(`data/tide/stations.json`). Two independent sources, one observed and one
CO-OPS's, and both say the bay's range is ~6% bigger and its tide a few
minutes late. The height matters — 6 cm at a 1 m tide — and the time does not
(≤1.5 cm at the fastest tide), but both are applied where they can be.

THE EPOCH GAP. Harmonic predictions are relative to the 1983–2001 epoch and
know nothing of the sea-level rise since, nor of the season. Over the same 30
days both gauges sat ~0.3 m above epoch MSL, and 9410170's measured level ran
+0.23 m above its own prediction. So a forecast built from the prediction
alone would put every break ~0.2 m too shallow. `anomaly` measures the
departure over the last few days and the forecast carries it forward —
persistence, and said so on the surface. It is not a gap being filled: the
prediction is the model, the measured departure is an observation of it.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR, ISO

BAY = "9410170"
OPEN_COAST = "9410230"

#: The transfer, measured (module docstring). `tests/test_tidesite.py` re-fits
#: them from `data/tide/comparison/` and fails if the file and these disagree.
RATIO = 0.944
OFFSET_M = -0.024
LEAD_MIN = 3

#: How far back the measured departure from the prediction is averaged.
ANOMALY_HOURS = 72


def msl_above_mllw(data_dir: Path = DEFAULT_DATA_DIR, station: str = BAY) -> float:
    """From CO-OPS's published datums, never typed (collector.tidestations)."""

    datums = json.loads((Path(data_dir) / "tide" / "stations.json").read_text())["datums_m"][station]
    return datums["MSL"] - datums["MLLW"]


def coast_level(bay_mllw_m: float, msl_m: float) -> float:
    """Water level at the open coast relative to MSL, from the bay gauge's
    reading on MLLW."""

    return OFFSET_M + RATIO * (bay_mllw_m - msl_m)


def _read(path: Path) -> list[tuple[datetime, float]]:
    out = []
    if not path.exists():
        return out
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                t = datetime.strptime(row["time_utc"], ISO).replace(tzinfo=timezone.utc)
                out.append((t, float(row["height_m"])))
            except (KeyError, ValueError):
                continue           # a gap stays a gap
    out.sort()
    return out


def interpolate(series: list[tuple[datetime, float]], when: datetime,
                max_gap: timedelta = timedelta(hours=1, minutes=1)) -> float | None:
    """Linear between the two samples either side; None across a gap."""

    times = [t for t, _ in series]
    i = bisect.bisect_left(times, when)
    if i < len(times) and times[i] == when:
        return series[i][1]
    if i == 0 or i >= len(times) or times[i] - times[i - 1] > max_gap:
        return None
    (t0, v0), (t1, v1) = series[i - 1], series[i]
    w = (when - t0) / (t1 - t0)
    return v0 + (v1 - v0) * w


def anomaly(data_dir: Path, until: datetime, hours: int = ANOMALY_HOURS) -> tuple[float | None, int]:
    """Mean measured-minus-predicted at the bay over the `hours` before
    `until`, and how many hourly pairs it stands on."""

    tide = Path(data_dir) / "tide"
    observed = _read(tide / f"{BAY}_observed.csv")
    predicted = dict(_read(tide / f"{BAY}_predicted.csv"))
    since = until - timedelta(hours=hours)
    pairs = [v - predicted[t] for t, v in observed if since <= t <= until and t in predicted]
    return (statistics.fmean(pairs) if pairs else None), len(pairs)


def predicted_series(data_dir: Path) -> list[tuple[datetime, float]]:
    return _read(Path(data_dir) / "tide" / f"{BAY}_predicted.csv")


def forecast_level(predicted: list[tuple[datetime, float]], when: datetime,
                   departure: float | None, msl_m: float) -> float | None:
    """The open coast at `when`, relative to MSL: the bay's prediction
    `LEAD_MIN` later (the coast leads), plus the measured departure, through
    the transfer. None when the prediction does not cover the hour."""

    value = interpolate(predicted, when + timedelta(minutes=LEAD_MIN))
    if value is None:
        return None
    return coast_level(value + (departure or 0.0), msl_m)


# ------------------------------------------------------------------ measure

def measure(data_dir: Path = DEFAULT_DATA_DIR) -> dict:
    """Re-fit the transfer from `data/tide/comparison/`: the open-coast gauge
    against the bay gauge, each on its own MSL, over a range of leads."""

    comp = Path(data_dir) / "tide" / "comparison"
    bay = _read(comp / f"{BAY}_observed.csv")
    coast = _read(comp / f"{OPEN_COAST}_observed.csv")
    if not bay or not coast:
        raise FileNotFoundError("no comparison series; run collector.tidestations on Actions")
    msl_bay = msl_above_mllw(data_dir, BAY)
    msl_coast = msl_above_mllw(data_dir, OPEN_COAST)
    best = None
    for lead in range(-9, 10):
        xs, ys = [], []
        for t, v in coast:
            b = interpolate(bay, t + timedelta(minutes=lead), max_gap=timedelta(minutes=6))
            if b is not None:
                xs.append(b - msl_bay)
                ys.append(v - msl_coast)
        mx, my = statistics.fmean(xs), statistics.fmean(ys)
        sxx = sum((x - mx) ** 2 for x in xs)
        slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
        offset = my - slope * mx
        rms = math.sqrt(statistics.fmean((y - offset - slope * x) ** 2 for x, y in zip(xs, ys)))
        if best is None or rms < best["rms_m"]:
            best = {"ratio": slope, "offset_m": offset, "lead_min": lead, "rms_m": rms, "n": len(xs)}
    return best


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = parser.parse_args(argv)
    got = measure(args.data_dir)
    print(f"open coast = {got['offset_m']:+.4f} m + {got['ratio']:.4f} x bay, "
          f"coast leads by {got['lead_min']} min, rms {100 * got['rms_m']:.1f} cm, n = {got['n']}")
    print(f"in use:      {OFFSET_M:+.4f} m + {RATIO:.4f} x bay, lead {LEAD_MIN} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())


# ------------------------------------------------------------------ the card

#: What the Tide card is about, now that it is not the gauge's own reading.
SITE_NAME = "Coronado open coast"


def coast_height(bay_mllw_m: float) -> float:
    """The card's height at the open coast, on its own MLLW.

    CO-OPS's convention for a subordinate station (`heightAdjustedType` "R",
    as Imperial Beach and Point Loma are published): the reference station's
    height on MLLW times a ratio. The ratio is the one measured here. This is
    the card's number; breaking uses `coast_level`, on MSL, because the seabed
    grids are on MSL.
    """

    return RATIO * bay_mllw_m


def coast_turn(turn):
    """A predicted turn of the bay's tide as it happens on the open coast:
    `LEAD_MIN` earlier, `RATIO` of the height."""

    from .tideturns import Turn

    when = datetime.strptime(turn.valid_utc, ISO).replace(tzinfo=timezone.utc)
    return Turn((when - timedelta(minutes=LEAD_MIN)).strftime(ISO),
                coast_height(turn.height_m), turn.event)


def coast_predicted(predicted: list[tuple[datetime, float]], when: datetime) -> float | None:
    """The open coast's predicted height at `when`, on its MLLW: the bay's
    prediction `LEAD_MIN` later, scaled."""

    value = interpolate(predicted, when + timedelta(minutes=LEAD_MIN))
    return None if value is None else coast_height(value)
