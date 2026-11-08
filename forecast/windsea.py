"""Which trains are wind sea: the wind still driving them, never their period.

    python -m forecast.windsea      # the measurement behind it (~1 min, 4 cores)

Until 2026-11-08 every train under 8 s was "wind sea". The owner asked
whether that was so (5 Nov 17Z: a 6.7 s row at North under a 3 kt KNZY wind,
which cannot grow a 6.7 s sea), and it mostly was not (BRIEFING §51).

A train is wind sea when the wind along it outruns it -- WAVE AGE: the wind
speed times the cosine of the angle between the wind and the train, times
`beta`, above the train's deep-water phase speed g T / 2π. A 6.7 s train
needs 14 kt along it at beta 1.5, a 5 s train 10 kt. 46232 has no
anemometer, so the wind is someone else's, and which one decides the answer:

**LIVE** (owner's decision, 2026-11-08): wind sea only when KNZY on the
sand AND NDBC 46086 offshore both say so, at beta 1.5. Both are
measurements, so the LIVE chain stays measurements only. Measured over
46232's archive (`report`, 4 Aug - 8 Nov 2026): the period rule named 32% of
trains; by wave age 13% of those were being driven with KNZY's wind, 33%
with 46086's, 55% with 46047's, and when either of KNZY and 46086 fired,
both did on only 30%. Both together named 94 of 2,876 trains, and the
independent checks agreed: 46047's wind 79 of 91 (87%), GFS-Wave's wind
24 of 27 (89%). Every other train is no kind: its period says it is short.

**Forecast** (owner's decision, same day): GFS-Wave decides, at
WAVEWATCH III's own wind-sea multiplier (`MODEL_BETA`, its documented
default) against its own 10 m wind at 46232 -- the wind it grew that sea
from; or, on the partition fallback, its bulletin's own wind-sea flag.

Nothing here observes the sea being driven; three anemometers agreeing on
the wind is the closest check there is without one at 46232. The beta and
the anemometer height are from the literature and NDBC, never fitted.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR

G = 9.81
KT_TO_MS = 0.514444
#: Wave age's wind multiplier on LIVE: Hanson & Phillips (2001) partition
#: wind sea at c_p / (U cos θ) < 1.5. Measured at 1.2 and 1.7 too (`report`):
#: the period rule's agreement moved 8-18% with KNZY, 19-41% with 46086.
LIVE_BETA = 1.5
#: WAVEWATCH III's own (its `WSM`, documented default 1.7): on the Forecast
#: tab the model that grew the sea decides what it calls wind sea.
MODEL_BETA = 1.7
#: The offshore anemometer the LIVE label needs beside KNZY.
OFFSHORE_STATION = "46086"
#: NDBC's 3 m discus anemometers sit ~4.1 m up; carried to 10 m by the
#: neutral log profile over a sea surface roughness of 0.2 mm (x1.09).
#: An assumption, stated, not fitted.
ANEMOMETER_M = 4.1
ROUGHNESS_M = 2e-4
STDMET_U10 = math.log(10 / ROUGHNESS_M) / math.log(ANEMOMETER_M / ROUGHNESS_M)
#: A wind reading counts for a spectrum stamped t only within these: KNZY's
#: METAR from 70 min before (its :52 report for the next hour's :00) to 10
#: after; 46086's 10-minute standard met within 30 min either side.
KNZY_BEFORE = timedelta(minutes=70)
KNZY_AFTER = timedelta(minutes=10)
STDMET_WINDOW = timedelta(minutes=30)
#: A partition matches a train within these (the Forecast's fallback).
PARTITION_PERIOD_S = 1.5
PARTITION_DEG = 45.0


@dataclass(frozen=True)
class Wind:
    speed_ms: float
    #: None for a variable wind (a METAR's VRB): no direction, so no age.
    from_deg: float | None
    source: str


def phase_speed(period_s: float) -> float:
    return G * period_s / (2 * math.pi)


def driven(period_s: float, from_deg: float, wind: Wind | None, beta: float) -> bool | None:
    """Is the wind outrunning this train along its heading? None when the
    wind cannot say (missing, or variable with some speed)."""

    if wind is None or period_s is None or math.isnan(period_s) or math.isnan(from_deg):
        return None
    if wind.speed_ms <= 0:
        return False
    if wind.from_deg is None:
        return None
    along = wind.speed_ms * math.cos(math.radians(from_deg - wind.from_deg))
    return beta * along > phase_speed(period_s)


def _ts(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


@lru_cache(maxsize=4)
def _knzy(path: str, mtime: float) -> tuple:
    out = []
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            if not r.get("wind_kt"):
                continue
            d = (None if (r.get("variable") or "").strip() or not r.get("wind_from_deg")
                 else float(r["wind_from_deg"]))
            out.append((_ts(r["observed_utc"]), float(r["wind_kt"]) * KT_TO_MS, d))
    out.sort(key=lambda x: x[0])
    return tuple(out)


@lru_cache(maxsize=4)
def _stdmet(path: str, mtime: float) -> tuple:
    out = []
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            if r.get("wspd") in ("", None) or r.get("wdir") in ("", None):
                continue
            out.append((_ts(r["timestamp_utc"]), float(r["wspd"]) * STDMET_U10, float(r["wdir"])))
    out.sort(key=lambda x: x[0])
    return tuple(out)


def _asof(series: tuple, t: datetime, before: timedelta, after: timedelta):
    keys = [x[0] for x in series]
    i = bisect.bisect_right(keys, t + after) - 1
    if i >= 0 and series[i][0] >= t - before:
        return series[i]
    return None


def knzy_at(t: datetime, data_dir: Path = DEFAULT_DATA_DIR) -> Wind | None:
    path = Path(data_dir) / "wind" / "KNZY.csv"
    if not path.exists():
        return None
    got = _asof(_knzy(str(path), path.stat().st_mtime), t, KNZY_BEFORE, KNZY_AFTER)
    return Wind(got[1], got[2], "KNZY") if got else None


def stdmet_at(station: str, t: datetime, data_dir: Path = DEFAULT_DATA_DIR) -> Wind | None:
    path = Path(data_dir) / "observations" / f"{station}.csv"
    if not path.exists():
        return None
    got = _asof(_stdmet(str(path), path.stat().st_mtime), t, STDMET_WINDOW, STDMET_WINDOW)
    return Wind(got[1], got[2], station) if got else None


def live_winds(t: datetime, data_dir: Path = DEFAULT_DATA_DIR) -> tuple[Wind | None, Wind | None]:
    """The two winds the LIVE label needs, as of a spectrum stamped `t`."""

    return knzy_at(t, data_dir), stdmet_at(OFFSHORE_STATION, t, data_dir)


def label_live(trains, winds: tuple[Wind | None, Wind | None]) -> None:
    """Wind sea where BOTH winds drive it at LIVE_BETA; no label otherwise,
    and none at all when either wind is missing."""

    for t in trains:
        got = [driven(t.period_s, t.from_deg, w, LIVE_BETA) for w in winds]
        t.wind_sea = bool(winds) and all(g is True for g in got)


def label_model(trains, wind_kt: float | None, wind_from_deg: float | None) -> None:
    """GFS-Wave decides: wave age against its own wind at MODEL_BETA."""

    wind = (None if wind_kt is None or wind_from_deg is None
            else Wind(wind_kt * KT_TO_MS, wind_from_deg, "GFS-Wave"))
    for t in trains:
        t.wind_sea = driven(t.period_s, t.from_deg, wind, MODEL_BETA) is True


def label_partitions(trains, parts) -> None:
    """The partition fallback: wind sea where the bulletin flags a partition
    within PARTITION_PERIOD_S and PARTITION_DEG of the train. `parts` are
    (hs, tp, from_deg, wind_sea)."""

    flagged = [(tp, d) for _, tp, d, ws in parts if ws]
    for t in trains:
        t.wind_sea = any(abs(tp - t.period_s) <= PARTITION_PERIOD_S
                         and abs((d - t.from_deg + 180) % 360 - 180) <= PARTITION_DEG
                         for tp, d in flagged) if not math.isnan(t.from_deg) else False


# ------------------------------------------------------------------ the report

def _trains_at(args):
    data_dir, i = args
    from . import transform as T

    global _SPECTRA
    if _SPECTRA is None:
        _SPECTRA = T.load_spectra(Path(data_dir) / "spectra" / "46232")
    sp = _SPECTRA[i]
    return sp.time, [(t.hs_m, t.period_s, t.from_deg) for t in T.at_buoy(sp.with_spread("mem")).trains]


_SPECTRA = None


def _model_winds(data_dir: Path) -> dict:
    """GFS-Wave's wind at 46232 for each valid hour, from the kept builds,
    the shortest lead of each (`forecastlog`'s 46232_shown)."""

    import glob
    import json

    out = {}
    for f in sorted(glob.glob(str(Path(data_dir) / "forecast_log" / "46232_shown" / "*.jsonl"))):
        with open(f) as fh:
            for line in fh:
                d = json.loads(line)
                b = (d.get("breaks") or {}).get("coronado_center") or {}
                if b.get("wind_kt") is None or b.get("wind_from_deg") is None:
                    continue
                v = _ts(d["valid_utc"])
                if v not in out or d["lead_h"] < out[v][0]:
                    out[v] = (d["lead_h"], Wind(b["wind_kt"] * KT_TO_MS, b["wind_from_deg"], "GFS-Wave"))
    return {v: w for v, (_, w) in out.items()}


def report(data_dir: Path = DEFAULT_DATA_DIR, workers: int = 4) -> str:
    from multiprocessing import Pool

    from . import transform as T

    n = len(T.load_spectra(Path(data_dir) / "spectra" / "46232"))
    with Pool(workers) as pool:
        hours = pool.map(_trains_at, [(str(data_dir), i) for i in range(n)], chunksize=20)
    model = _model_winds(data_dir)
    rows = []
    for t, trains in hours:
        winds = {"KNZY": knzy_at(t, data_dir), "46086": stdmet_at("46086", t, data_dir),
                 "46047": stdmet_at("46047", t, data_dir), "GFS-Wave": model.get(t)}
        rows += [(per, frm, winds) for _, per, frm in trains]
    lines = [f"46232, {hours[0][0]:%d %b} - {hours[-1][0]:%d %b %Y}: {len(hours)} spectra, "
             f"{len(rows)} trains; the period rule (< {T.WIND_SEA_PERIOD_S:g} s) names "
             f"{sum(1 for r in rows if r[0] < T.WIND_SEA_PERIOD_S)}"]
    lines.append("\nWave age against each wind, of the trains the period rule names:")
    for src in ("KNZY", "46086", "46047"):
        for beta in (1.2, 1.5, 1.7):
            got = [(per, driven(per, frm, w[src], beta)) for per, frm, w in rows]
            known = [(p, g) for p, g in got if g is not None]
            short = [g for p, g in known if p < T.WIND_SEA_PERIOD_S]
            lines.append(f"  {src:6s} beta {beta}: driven {sum(short)} of {len(short)} "
                         f"({100 * sum(short) / max(len(short), 1):.0f}%); "
                         f"any period {sum(g for _, g in known)} of {len(known)}")
    lines.append(f"\nTwo winds together at beta {LIVE_BETA}, and the winds that played no part:")
    for a, b in (("KNZY", "46086"), ("GFS-Wave", "KNZY")):
        n_ = both = either = 0
        checks: dict = {}
        for per, frm, w in rows:
            fa, fb = driven(per, frm, w[a], LIVE_BETA), driven(per, frm, w[b], LIVE_BETA)
            if fa is None or fb is None:
                continue
            n_ += 1; either += fa or fb; both += fa and fb
            if fa and fb:
                for c in ("KNZY", "46086", "46047", "GFS-Wave"):
                    if c in (a, b):
                        continue
                    fc = driven(per, frm, w[c], LIVE_BETA)
                    if fc is not None:
                        k = checks.setdefault(c, [0, 0]); k[0] += fc; k[1] += 1
        lines.append(f"  {a} and {b}: {both} of {n_} trains (either: {either}); "
                     + ", ".join(f"{c} agrees {x}/{y} ({100 * x / y:.0f}%)" for c, (x, y) in checks.items()))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)
    print(report(args.data_dir, args.workers))
    return 0


if __name__ == "__main__":
    sys.exit(main())
