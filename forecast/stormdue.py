"""When a hurricane's swell is due at each break, from NHC's own fixes.

The LIVE briefing's longest story (owner's request, 2026-10-16): from when
a storm's swell can first reach the breaks to when it no longer can.
`forecast.stormtrack` already runs each fix forward to the gate buoys and
decides whether the swell ARRIVED; this says when it is DUE, which needs no
spectrum at all, and so stands before any buoy has seen it.

Each source fix (`stormtrack.sources`: hurricane strength, and tropical storm
after the first hurricane fix) whose great circle to 46232 crosses no land
(`landpath.blocked`, as the gate tests it) sends a train of frequency f that
reaches 46232 d / cg(f) later, cg = g/4πf in deep water; then each break
after the rays' leg (`upstreamlag.leg`, BRIEFING §42). Over `BAND_S` that is
the due window: its first edge is the fastest swell of the first open fix,
its last the slowest swell of the last.

Two kinds of fix, never mixed and always named:

- **best track** (`data/besttracks/`): where NHC has had the storm;
- **NHC's forecast** (`data/nhcforecasts/`, the newest official forecast,
  OFCL): where NHC expects it, every forecast hour at TS or HU strength
  (≥ 34 kt) after the best track's last fix. The page names any window
  edge that comes from it as NHC's forecast.

And what each break takes from the storm's bearing: a one-metre train at
`RESPONSE_PERIOD_S` from the open fixes' mean bearing, carried through
that break's ray tables to 5 m (`nearshore.carry`): integrated over the
heading spread, never a test of one bearing against a window (BRIEFING
§10). Physics, not verified.

Due is not arrived: Polo's band was due and showed at no buoy on any day
(BRIEFING §37b). Whether it arrived is the gate's (`stormtrack.live`) and
Origin's, which the briefing shows beside this.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR

from .origintracks import Fix, _coord, load_tracks
from .swell import great_circle_km, initial_bearing

#: The swell band a window is drawn over, seconds: 20 s leads, 12 s trails.
#: Past 20 s a hurricane's energy is small; under 12 s it is mostly the
#: storm's own sea and the coast's, and the gate reads 10–25 s (BAND_HZ).
BAND_S = (12.0, 20.0)

#: A storm is live while its newest best-track fix is this recent.
ACTIVE_H = 72

#: A due window is kept this long after its last edge has passed.
KEEP_AFTER_H = 12

#: What each break takes is read at this period.
RESPONSE_PERIOD_S = 15.0

#: NHC's forecast fixes count at tropical storm strength and above.
FORECAST_MIN_KT = 34

#: The rays' leg is read over this many degrees either side of the bearing.
LEG_SECTOR_DEG = 30.0


@dataclass(frozen=True)
class ForecastFix:
    issued: datetime
    tau_h: int
    time: datetime
    lat: float
    lon: float
    vmax_kt: int


def parse_ofcl(text: str) -> dict[datetime, list[ForecastFix]]:
    """An archived OFCL file (`collector.nhcforecast`), by issue time.

    ATCF a-deck columns: basin, number, issue YYYYMMDDHH, technique number,
    technique, tau (h), latitude, longitude, vmax (kt), ... A forecast hour
    repeats once per wind-radius threshold; the first is kept.
    """

    out: dict[datetime, dict[int, ForecastFix]] = {}
    for line in text.splitlines():
        cols = [c.strip() for c in line.split(",")]
        if len(cols) < 9 or cols[4] != "OFCL":
            continue
        try:
            issued = datetime.strptime(cols[2], "%Y%m%d%H").replace(tzinfo=timezone.utc)
            tau = int(cols[5])
            fix = ForecastFix(issued, tau, issued + timedelta(hours=tau),
                              _coord(cols[6]), _coord(cols[7]), int(cols[8] or 0))
        except (ValueError, IndexError):
            continue
        out.setdefault(issued, {}).setdefault(tau, fix)
    return {t: [v[k] for k in sorted(v)] for t, v in sorted(out.items())}


def load_forecast(storm: str, year: int, data_dir: Path = DEFAULT_DATA_DIR,
                  as_of: datetime | None = None) -> list[ForecastFix]:
    """The newest official forecast for `storm` (``EP20``) issued by `as_of`."""

    path = Path(data_dir) / "nhcforecasts" / str(year) / f"a{storm.lower()}{year}_ofcl.dat"
    if not path.exists():
        return []
    issues = parse_ofcl(path.read_text(encoding="utf-8"))
    usable = [t for t in issues if as_of is None or t <= as_of]
    return issues[max(usable)] if usable else []


@dataclass
class Edge:
    utc: datetime
    period_s: float
    source: str          # "best track" or "NHC forecast"
    fix_utc: datetime


@dataclass
class Due:
    storm: str
    name: str
    strength: str                    # at the newest best-track fix
    newest_fix_utc: datetime
    bearing_deg: float | None        # mean over the open fixes, from 46232
    distance_km: float | None        # newest open fix to 46232
    open_fixes: int
    blocked_fixes: int
    forecast_issued_utc: datetime | None
    breaks: dict = field(default_factory=dict)   # id -> {"first": Edge, "last": Edge, "keeps": float | None}


def _arrival(when: datetime, period_s: float, distance_km: float) -> datetime:
    cg = 9.81 * period_s / (4.0 * math.pi)
    return when + timedelta(seconds=distance_km * 1000.0 / cg)


def _minute(t: datetime) -> datetime:
    return t.replace(second=0, microsecond=0)


def _mean_bearing(home, points) -> float | None:
    if not points:
        return None
    x = sum(math.sin(math.radians(initial_bearing(home, p))) for p in points)
    y = sum(math.cos(math.radians(initial_bearing(home, p))) for p in points)
    return math.degrees(math.atan2(x, y)) % 360.0


def response(bearing_deg: float, tables: dict | None = None) -> dict[str, float]:
    """The share of a one-metre train at RESPONSE_PERIOD_S from `bearing_deg`
    (the chain's own spread) that reaches each break's 5 m start, shoaling
    divided out: windows, refraction, diffraction, friction — the quantity
    BRIEFING §29's directional table gives."""

    from .nearshore import carry, load_tables, spectrum_from_partitions, table_frequencies

    tables = load_tables() if tables is None else tables
    spectrum = spectrum_from_partitions([(1.0, RESPONSE_PERIOD_S, bearing_deg, False)],
                                        datetime(2026, 1, 1, tzinfo=timezone.utc),
                                        table_frequencies(tables))
    return {bid: round(carry(spectrum, table).hs_equivalent, 2) for bid, table in tables.items()}


def due(fixes: list[Fix], forecast: list[ForecastFix], *, home: tuple[float, float],
        breaks: list[str], land=(), tables: dict | None = None,
        leg=None) -> Due | None:
    """The due window at each break for one storm, or None if it never had a
    source fix."""

    from .landpath import blocked
    from .stormtrack import sources, strength
    from .upstreamlag import leg_over

    def leg_fn(bid, period, bearing):
        # The leg is minutes against a window of days: the rays within
        # LEG_SECTOR_DEG of the bearing, else every unblocked ray at that
        # period. Never a gate on one heading (BRIEFING §10).
        return (leg_over(bid, period, (bearing - LEG_SECTOR_DEG, bearing + LEG_SECTOR_DEG))
                or leg_over(bid, period, (0.0, 359.99)))

    leg = leg or leg_fn
    strong = sources(fixes)
    if not strong:
        return None
    last_best = fixes[-1].time
    points: list[tuple[datetime, float, float, str]] = [
        (f.time, f.lat, f.lon, "best track") for f in strong]
    points += [(f.time, f.lat, f.lon, "NHC forecast") for f in forecast
               if f.time > last_best and f.vmax_kt >= FORECAST_MIN_KT]
    open_ = [p for p in points if not blocked((p[1], p[2]), home, land)]
    names = [f.name for f in fixes if f.name and not f.name.upper().startswith(("INVEST", "GENESIS"))]
    out = Due(
        storm=fixes[0].storm, name=names[-1] if names else fixes[0].storm,
        strength=strength(fixes[-1]) if fixes[-1].vmax_kt >= 34 else "remnant",
        newest_fix_utc=last_best,
        bearing_deg=_mean_bearing(home, [(p[1], p[2]) for p in open_]),
        distance_km=round(great_circle_km(home, (open_[-1][1], open_[-1][2]))) if open_ else None,
        open_fixes=len(open_), blocked_fixes=len(points) - len(open_),
        forecast_issued_utc=forecast[0].issued if forecast else None,
    )
    if not open_:
        return out
    fast, slow = BAND_S[1], BAND_S[0]
    first_p, last_p = open_[0], open_[-1]
    keeps = response(out.bearing_deg, tables)
    for bid in breaks:
        # The leg at the open fixes' bearing; at the band's own period.
        lf = leg(bid, fast, out.bearing_deg)
        ls = leg(bid, slow, out.bearing_deg)
        if lf is None or ls is None:
            out.breaks[bid] = {"first": None, "last": None, "keeps": keeps.get(bid)}
            continue
        d_first = great_circle_km(home, (first_p[1], first_p[2]))
        d_last = great_circle_km(home, (last_p[1], last_p[2]))
        first = _minute(_arrival(first_p[0], fast, d_first) + timedelta(minutes=lf.lo_min))
        last = _minute(_arrival(last_p[0], slow, d_last) + timedelta(minutes=ls.hi_min))
        out.breaks[bid] = {
            "first": Edge(first, fast, first_p[3], first_p[0]),
            "last": Edge(last, slow, last_p[3], last_p[0]),
            "keeps": keeps.get(bid),
        }
    return out


def live(at: datetime, *, data_dir: Path = DEFAULT_DATA_DIR, home: tuple[float, float],
         breaks: list[str], tables: dict | None = None) -> list[Due]:
    """Every storm with a live best track whose window has not long passed."""

    from .landpath import load_land

    land = load_land(str(data_dir))
    out = []
    for storm, fixes in load_tracks(data_dir, at.year).items():
        fixes = [f for f in fixes if f.time <= at]
        if not fixes or at - fixes[-1].time > timedelta(hours=ACTIVE_H):
            continue
        forecast = load_forecast(storm, at.year, data_dir, as_of=at)
        d = due(fixes, forecast, home=home, breaks=breaks, land=land, tables=tables)
        if d is None:
            continue
        lasts = [b["last"].utc for b in d.breaks.values() if b.get("last")]
        if lasts and max(lasts) < at - timedelta(hours=KEEP_AFTER_H):
            continue
        out.append(d)
    return out
