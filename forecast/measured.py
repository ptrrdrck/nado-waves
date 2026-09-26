"""The observed chain, rebuilt for each of the last 48 hours the page offers.

Run: ``python -m forecast.measured`` — writes ``data/live/measured.json``.

The Forecast tab reaches 48 h into the past (owner's decision, 2026-09-26), and
on every hour that has gone by it shows, in blue under what the forecast said,
what 46232 MEASURED at that hour carried in by the same chain the Now tab uses
(`forecast.now.build`): the buoy's own directional spectrum, KNZY's wind for the
local chop and the gauge's measured water level for the depth it breaks in.

**What the comparison is, and is not.** Both numbers pass through the same
windows, seabed and surf zone, so their difference is GFS-Wave's error AT THE
BUOY, carried in — the model level, checked against an observation. It is not a
check at the beach: nothing measures the beach (CLAUDE.md), and a physics error
common to both chains cancels out of the comparison entirely. The page labels it
"measured at 46232, same chain" and never "what happened".

**A missing observation is a gap.** Only a spectrum stamped exactly at the hour
is used — never the one an hour either side — and wind and tide are the readings
that existed at that hour (`now.build(as_of=True)`), never a later one. An hour
with no spectrum is written as `{"gap": true}` and the page says so.

Derived and gitignored like `now.json`: every input is committed, so this is
rebuilt from scratch each collection, for any chain version, and there is
nothing here to keep. `forecast.modelbias` rebuilds the same entries for
whatever hours it needs.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR, ISO

from . import now as observed
from .forecastlog import HOUR_STEP, PAST_HOURS
from .nearshore import load_tables
from .surfzone import load_profiles
from .transform import Spectrum, load_spectra

STATION = observed.STATION


def marks(until: datetime, *, hours: int = PAST_HOURS, step: int = HOUR_STEP) -> list[datetime]:
    """The offered hours in the `hours` up to `until`, oldest first.

    Forecast hours fall on multiples of `step` UTC (cycles at 00/06/12/18Z,
    every third lead), so those are the hours the page can pair with.
    """

    last = until.replace(minute=0, second=0, microsecond=0)
    last -= timedelta(hours=last.hour % step)
    first = until - timedelta(hours=hours)
    out = []
    t = last
    while t >= first:
        out.append(t)
        t -= timedelta(hours=step)
    return out[::-1]


def _r(value, digits: int = 3):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return round(float(value), digits)


def entry(reading: observed.Now, valid: datetime) -> dict:
    """One hour's compact entry, in the same keys `forecastlog.past_hours` uses."""

    if not reading.breaks:
        return {"valid_utc": valid.strftime(ISO), "gap": True,
                "why": "; ".join(reading.warnings) or "no reading"}
    breaks = {}
    for b in reading.breaks:
        near = b.nearshore or {}
        broke = near.get("breaking")
        if b.hs_nearshore_m is not None:
            basis = "breaking" if broke else "5m"
            depth = broke["depth_m"] if broke else near.get("depth_m")
            headline = b.hs_nearshore_m
        else:
            basis, depth, headline = "window", None, b.hs_in_window_m
        breaks[b.id] = {
            "hs_m": _r(headline), "hs_basis": basis, "depth_m": _r(depth, 2),
            "hs_5m_m": _r((near.get("effects") or {}).get("with_chop_hs_m")),
            "hs_window_m": _r(b.hs_in_window_m),
            "period_s": _r(b.peak_period_s, 1), "from_deg": _r(b.peak_direction_deg, 0),
        }
    buoy = reading.buoy or {}
    return {
        "valid_utc": valid.strftime(ISO),
        "gap": False,
        "buoy": {"hs_m": _r(buoy.get("hs_m")), "hs_basis": "buoy",
                 "period_s": _r(buoy.get("peak_period_s"), 1),
                 "from_deg": _r(buoy.get("peak_direction_deg"), 0)},
        "breaks": breaks,
        "tide_m": _r(reading.tide.height_m) if not reading.tide.note else None,
        "wind_kt": _r(reading.wind.speed_kt, 1),
        "wind_from_deg": _r(reading.wind.from_deg, 0),
    }


class Rebuilder:
    """Rebuilds measured entries for any hours, loading the heavy inputs once."""

    def __init__(self, data_dir: Path = DEFAULT_DATA_DIR,
                 spectra: list[Spectrum] | None = None):
        self.data_dir = Path(data_dir)
        if spectra is None:
            try:
                spectra = load_spectra(self.data_dir / "spectra" / STATION)
            except (FileNotFoundError, ValueError):
                spectra = []
        self.by_time = {s.time: s for s in spectra}
        try:
            self.tables = load_tables()
            self.profiles = load_profiles()
        except (FileNotFoundError, ValueError):
            self.tables, self.profiles = None, None

    def at(self, valid: datetime) -> dict:
        spectrum = self.by_time.get(valid)
        if spectrum is None:
            # Newer than anything collected is not a gap yet: 46232's spectra
            # land H+7 to H+35 min (CLAUDE.md), so the latest hour is usually
            # still on its way. A gap is an hour a LATER spectrum has passed.
            if not self.by_time or valid > max(self.by_time):
                return {"valid_utc": valid.strftime(ISO), "gap": False, "pending": True,
                        "why": f"no {STATION} spectrum collected for this hour yet"}
            return {"valid_utc": valid.strftime(ISO), "gap": True,
                    "why": f"no {STATION} spectrum stamped at this hour"}
        reading = observed.build(data_dir=self.data_dir, now=valid, spectrum=spectrum,
                                 as_of=True, tables=self.tables, profiles=self.profiles)
        return entry(reading, valid)


def build(*, data_dir: Path = DEFAULT_DATA_DIR, now: datetime | None = None,
          spectra: list[Spectrum] | None = None) -> dict:
    moment = now or datetime.now(timezone.utc)
    rebuild = Rebuilder(data_dir, spectra)
    return {
        "generated_utc": moment.strftime(ISO),
        "station": STATION,
        "past_hours": PAST_HOURS,
        "hour_step_h": HOUR_STEP,
        "standing_on": {
            "waves": f"OBSERVED — the NDBC directional spectrum at {STATION} stamped at "
                     f"that hour; an hour without one is a gap, never filled",
            "wind": f"OBSERVED — the {observed.WIND_STATION} METAR in force at that hour",
            "tide": f"OBSERVED — the measured water level at {observed.TIDE_STATION} at "
                    f"that hour, carried to the open coast",
            "chain": "the same windows, seabed and surf zone as the forecast beside it",
            "claim": "the difference from the forecast is the model's error at the buoy, "
                     "carried in; it checks nothing at the beach",
        },
        "steps": [rebuild.at(t) for t in marks(moment)],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    got = build(data_dir=args.data_dir)
    out = args.out or Path(args.data_dir) / "live" / "measured.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(got, indent=1), encoding="utf-8")
    gaps = sum(1 for s in got["steps"] if s["gap"])
    pending = sum(1 for s in got["steps"] if s.get("pending"))
    print(f"Wrote {out}: {len(got['steps'])} hour(s), {gaps} gap(s), {pending} not in yet")
    for s in got["steps"]:
        if s["gap"] or s.get("pending"):
            print(f"  {s['valid_utc']}  {'gap' if s['gap'] else 'pending'} — {s['why']}")
        else:
            hs = "  ".join(f"{k.split('_')[-1]} {v['hs_m']}" for k, v in s["breaks"].items())
            print(f"  {s['valid_utc']}  buoy {s['buoy']['hs_m']}  {hs}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
