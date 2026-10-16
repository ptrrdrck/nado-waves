"""Sunrise, and sunset as each break sees it: behind Point Loma or in the sea.

Owner's request, 2026-10-16 (BRIEFING §42). Every published sunset is the
sea-horizon time: the sun's upper limb on a level horizon. From Coronado's
sand the peninsula stands 1.1-1.5° above that horizon across most of the
year's sunset azimuths, so the sun goes behind it several minutes earlier --
the "Point Loma sunset". Through the winter it sets far enough south to go
into the sea LEFT of the point instead, and how much of the winter that is
depends on the break: the tip's bearing sweeps 18° along 2.8 km of sand.

For one break and one day:

- `sea_utc`: the upper limb on the sea horizon (apparent altitude 0, the
  published convention; dip from the eye's height ignored, as it is there).
- `seen_utc`: the last moment ANY of the disc is above whatever is in front
  of it -- the skyline table (`forecast.skyline`, CoNED bare earth) or the
  sea -- across 41 columns of the disc, each refracted at its own altitude.
- `kind`: "sea" when that last light is over open water (the sun set left of
  the point, and `seen_utc` is `sea_utc`), else "point_loma".

The sun is Meeus, *Astronomical Algorithms* ch. 25 (low precision, ~0.01°)
with sidereal time from ch. 12; refraction is Bennett's formula at the
apparent altitude of what hides the limb. Checked against PyEphem
(`tests/test_sunset.py`). Pure Python, no network; times UTC.

WHAT IT IS NOT. Refraction at the horizon swings with the marine layer, a
minute either way on a real evening, and the ridge's trees and buildings are
not in a bare-earth survey -- they can only make the Point Loma sunset
EARLIER. Sunrise is the sea-level time only: the land east of the breaks
(the city, the mesas, the mountains) is not in the grids.
"""

from __future__ import annotations

import csv
import math
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from collector.common import ISO

ROOT = Path(__file__).resolve().parent.parent
TABLES = ROOT / "data" / "nearshore"
BREAKS = ("coronado_north", "coronado_center", "coronado_south")
LOCAL_TZ = ZoneInfo("America/Los_Angeles")
#: The sun's mean semi-diameter at 1 au, degrees.
SD_AU = 0.26667
#: Columns across the disc: 41 puts one every ~0.013°, under a second of
#: sunset against the tip's slope.
COLUMNS = 41
#: How far ahead the season is read, in days.
SEASON_DAYS = 366


# ------------------------------------------------------------------ the sun

def _jd(when: datetime) -> float:
    return when.timestamp() / 86400.0 + 2440587.5


def sun_position(when: datetime, lat: float, lon: float) -> tuple[float, float, float]:
    """(true altitude, azimuth from north, semi-diameter), all degrees.

    Meeus ch. 25, low precision; UT is used for TT (~69 s, 0.0008° of the
    Sun's motion)."""

    jd = _jd(when)
    t = (jd - 2451545.0) / 36525.0
    l0 = 280.46646 + t * (36000.76983 + 0.0003032 * t)
    m = math.radians(357.52911 + t * (35999.05029 - 0.0001537 * t))
    e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
    c = ((1.914602 - t * (0.004817 + 0.000014 * t)) * math.sin(m)
         + (0.019993 - 0.000101 * t) * math.sin(2 * m) + 0.000289 * math.sin(3 * m))
    nu = m + math.radians(c)
    r = 1.000001018 * (1 - e * e) / (1 + e * math.cos(nu))
    omega = math.radians(125.04 - 1934.136 * t)
    lam = math.radians(l0 + c - 0.00569 - 0.00478 * math.sin(omega))
    eps0 = 23 + (26 + (21.448 - t * (46.8150 + t * (0.00059 - t * 0.001813))) / 60) / 60
    eps = math.radians(eps0 + 0.00256 * math.cos(omega))
    ra = math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))
    dec = math.asin(math.sin(eps) * math.sin(lam))
    gmst = (280.46061837 + 360.98564736629 * (jd - 2451545.0)
            + t * t * (0.000387933 - t / 38710000.0))
    h = math.radians(gmst + lon) - ra
    phi = math.radians(lat)
    alt = math.asin(math.sin(phi) * math.sin(dec) + math.cos(phi) * math.cos(dec) * math.cos(h))
    az = math.atan2(math.sin(h), math.cos(h) * math.sin(phi) - math.tan(dec) * math.cos(phi))
    return math.degrees(alt), (math.degrees(az) + 180.0) % 360.0, SD_AU / r


def refraction(apparent_deg: float) -> float:
    """Bennett (1982): degrees of refraction at an APPARENT altitude, standard
    pressure and temperature. 34.5' at the horizon."""

    return 1.0 / math.tan(math.radians(apparent_deg + 7.31 / (apparent_deg + 4.4))) / 60.0


# ------------------------------------------------------------------ the skyline

class Skyline:
    """A break's skyline: the apparent altitude of the land at each azimuth,
    None where the line of sight crosses only sea."""

    def __init__(self, start: float, step: float, elevation: list[float | None]):
        self.start, self.step, self.elevation = start, step, elevation

    @classmethod
    def load(cls, break_id: str, directory: Path = TABLES) -> "Skyline":
        with (directory / f"{break_id}_skyline.csv").open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        az = [float(r["azimuth_deg"]) for r in rows]
        el = [float(r["elevation_deg"]) if r["elevation_deg"] else None for r in rows]
        return cls(az[0], round(az[1] - az[0], 6), el)

    def land(self, az: float) -> float | None:
        """The land's apparent altitude at `az`, interpolated; None for sea.
        Between land and sea the nearer sample decides."""

        x = (az - self.start) / self.step
        i = math.floor(x)
        if i < 0 or i + 1 >= len(self.elevation):
            return None
        a, b = self.elevation[i], self.elevation[i + 1]
        f = x - i
        if a is None or b is None:
            return a if f < 0.5 else b
        return a + (b - a) * f

    def first_land(self) -> float:
        """The first azimuth, sweeping north from the south, where the land
        stands above the sea horizon: the point, as the sun sees it."""

        for i, el in enumerate(self.elevation):
            if el is not None and el > 0:
                return self.start + i * self.step
        return float("nan")


def _visible(when: datetime, pos: tuple[float, float], sky: Skyline | None) -> tuple[bool, bool]:
    """(any of the disc visible, the visible part over open sea)."""

    alt, az, sd = sun_position(when, *pos)
    seen = over_sea = False
    cos_alt = max(math.cos(math.radians(alt)), 1e-6)
    for k in range(COLUMNS):
        dz = sd * (2 * k / (COLUMNS - 1) - 1)
        top = alt + math.sqrt(max(sd * sd - dz * dz, 0.0))
        land = sky.land(az + dz / cos_alt) if sky else None
        hide = max(0.0, land) if land is not None else 0.0
        if top > hide - refraction(hide):
            seen = True
            if land is None or land <= 0:
                over_sea = True
    return seen, over_sea


def _last(pred, lo: datetime, hi: datetime, seconds: float = 1.0) -> datetime:
    """The last instant in [lo, hi] at which `pred` holds, `pred` true at lo
    and false at hi."""

    while (hi - lo).total_seconds() > seconds:
        mid = lo + (hi - lo) / 2
        if pred(mid):
            lo = mid
        else:
            hi = mid
    return lo


def _local(day: date, hour: int) -> datetime:
    return datetime.combine(day, time(hour), LOCAL_TZ).astimezone(timezone.utc)


def _round(t: datetime) -> str:
    return (t + timedelta(seconds=30)).replace(second=0, microsecond=0).strftime(ISO)


def sea_times(day: date, pos: tuple[float, float]) -> tuple[datetime, datetime]:
    """Sunrise and sunset at the sea horizon on the local `day`."""

    def up(t):
        alt, _, sd = sun_position(t, *pos)
        return alt + sd > -refraction(0.0)

    rise = _last(lambda t: not up(t), _local(day, 0), _local(day, 12))
    sets = _last(up, _local(day, 12), _local(day, 23))
    return rise, sets


def sunset(day: date, pos: tuple[float, float], sky: Skyline) -> dict:
    """One break's sunset on the local `day`."""

    _, sea = sea_times(day, pos)
    # Is any of the disc still showing over the sea a moment before the limb
    # meets the sea horizon? Then the sun sets in the sea, at `sea`.
    seen_now, over_sea = _visible(sea - timedelta(seconds=2), pos, sky)
    if seen_now and over_sea:
        return {"seen_utc": _round(sea), "kind": "sea", "early_min": 0.0, "_sea": sea}
    seen = _last(lambda t: _visible(t, pos, sky)[0], sea - timedelta(minutes=30), sea)
    return {"seen_utc": _round(seen), "kind": "point_loma",
            "early_min": round((sea - seen).total_seconds() / 60, 1), "_sea": sea}


def season(start: date, pos: tuple[float, float], sky: Skyline, days: int = SEASON_DAYS) -> dict:
    """Where the sun sets, day by day for a year from `start`, as runs of one
    kind: {"runs": [{"kind", "from", "to"}], "closest": ...}. `closest` is the
    day the sun came nearest to clearing the point (fewest minutes early) when
    it never does -- the north break's case."""

    runs, closest = [], None
    for k in range(days):
        day = start + timedelta(days=k)
        s = sunset(day, pos, sky)
        if runs and runs[-1]["kind"] == s["kind"]:
            runs[-1]["to"] = day.isoformat()
        else:
            runs.append({"kind": s["kind"], "from": day.isoformat(), "to": day.isoformat()})
        if s["kind"] == "point_loma" and (closest is None or s["early_min"] < closest["early_min"]):
            closest = {"day": day.isoformat(), "early_min": s["early_min"]}
    out = {"runs": runs}
    if all(r["kind"] == "point_loma" for r in runs):
        out["closest"] = closest
    return out


def block(days: list[date], spots=None, directory: Path = TABLES) -> dict:
    """The payload's `sun`: per local day, sunrise and the sea-horizon sunset
    at the center break and each break's own sunset; per break, its season
    read forward a year from the first day."""

    from .geometry import load

    by_id = {s.id: s for s in (spots or load()[0])}
    skies = {b: Skyline.load(b, directory) for b in BREAKS}
    center = by_id["coronado_center"].position
    out = {"days": {}, "seasons": {}, "point": {}}
    for day in days:
        rise, sets = sea_times(day, center)
        entry = {"sunrise_utc": _round(rise), "sunset_utc": _round(sets), "breaks": {}}
        for b in BREAKS:
            s = sunset(day, by_id[b].position, skies[b])
            s.pop("_sea")
            entry["breaks"][b] = s
        out["days"][day.isoformat()] = entry
    if days:
        for b in BREAKS:
            out["seasons"][b] = season(days[0], by_id[b].position, skies[b])
            out["point"][b] = round(skies[b].first_land(), 2)
    return out
