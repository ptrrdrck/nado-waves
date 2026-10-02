"""Sunrise and sunset at the breaks, for the daylight shading on the Tide charts.

Owner's request, 2026-10-02: the tide's curve shaded by night, so a low tide in
the dark reads differently from one at dawn. Computed, not fetched: NOAA's
solar-position equations (the ones behind its Solar Calculator, after Meeus),
good to about a minute at this latitude, with the sun's upper limb on the
horizon and standard refraction (zenith 90.833°). The position is Coronado's
center break, read from `forecast/spots.json` like every other coordinate the
page uses -- never typed. 2.8 km along the sand moves sunrise by seconds.

Pure Python, no network. Times are UTC; the page shows them on the reader's
clock as it does every other time.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone

from collector.common import ISO

#: The sun's centre this far below the geometric horizon at sunrise and
#: sunset: 50' of refraction and semi-diameter, the convention NOAA uses.
ZENITH_DEG = 90.833
BREAK = "coronado_center"


def _sun(day: date, lat: float, lon: float, rising: bool) -> datetime | None:
    """NOAA's sunrise/sunset for one UTC date, or None when the sun neither
    rises nor sets (not at 32° N, but the guard costs nothing)."""

    n = day.timetuple().tm_yday
    # Fractional year at local noon, radians.
    gamma = 2 * math.pi / 365 * (n - 1 + (12 - lon / 15) / 24)
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(gamma) - 0.032077 * math.sin(gamma)
                       - 0.014615 * math.cos(2 * gamma) - 0.040849 * math.sin(2 * gamma))
    decl = (0.006918 - 0.399912 * math.cos(gamma) + 0.070257 * math.sin(gamma)
            - 0.006758 * math.cos(2 * gamma) + 0.000907 * math.sin(2 * gamma)
            - 0.002697 * math.cos(3 * gamma) + 0.00148 * math.sin(3 * gamma))
    phi = math.radians(lat)
    cos_h = (math.cos(math.radians(ZENITH_DEG)) / (math.cos(phi) * math.cos(decl))
             - math.tan(phi) * math.tan(decl))
    if not -1 <= cos_h <= 1:
        return None
    ha = math.degrees(math.acos(cos_h)) * (1 if rising else -1)
    minutes = 720 - 4 * (lon + ha) - eqtime
    return datetime(day.year, day.month, day.day, tzinfo=timezone.utc) + timedelta(minutes=minutes)


def position(spots=None) -> tuple[float, float]:
    from .geometry import load

    spot = next(s for s in (spots or load()[0]) if s.id == BREAK)
    return spot.position


def nights(start: datetime, end: datetime, lat: float | None = None,
           lon: float | None = None) -> list[list[str]]:
    """Every stretch of night that overlaps [start, end], as [sunset, sunrise]
    pairs in UTC, clipped to the window. Days are walked in UTC with a day's
    margin either side, so a night that began before the window still shades
    its start."""

    if lat is None or lon is None:
        lat, lon = position()
    events = []
    day = (start - timedelta(days=1)).date()
    while day <= (end + timedelta(days=1)).date():
        for rising in (True, False):
            t = _sun(day, lat, lon, rising)
            if t is not None:
                events.append((t, rising))
        day += timedelta(days=1)
    events.sort()
    out = []
    dark_from = None
    for t, rising in events:
        if not rising:
            dark_from = t
        elif dark_from is not None:
            a, b = max(dark_from, start), min(t, end)
            if a < b:
                out.append([a.strftime(ISO), b.strftime(ISO)])
            dark_from = None
    return out
