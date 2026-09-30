"""The local wind forecast at the beach: the NWS San Diego forecast grid.

Fetched by `forecast.live` on every build (``fetch``), on Actions only --
api.weather.gov and aviationweather.gov are both denied at CONNECT from a
Claude session (checked 2026-09-30). Nothing is archived here: what each build
showed is kept hour by hour in the forecast log, like the rest of the card.

Why this and not KNZY's TAF. The Forecast tab's wind is GFS-Wave's own 10 m
wind at 46232, 29 km offshore: the right wind for how much wind sea the model
is making, and the wrong one for whether it is offshore at a break, which
needs the wind on the sand. KNZY does issue a TAF, but a TAF covers 24-30 h,
is coded in change groups (FM/BECMG/TEMPO) that have to be interpreted into
hours, and is written for the runway. The NWS gridded forecast is the San
Diego office's hourly wind on a 2.5 km grid, seven days out, for the point
asked for -- here Coronado's center break, read from `forecast/spots.json`,
never typed. It is a forecast, and the page says whose.

**Direction is degrees FROM**, like METAR and NDBC, and the grid's own
convention; nothing is flipped. Speeds arrive in km/h (the grid's
``wmoUnit:km_h-1``) and are stored in knots, the unit every other wind in
this project's JSON is in; any other unit is refused rather than guessed.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from .common import ISO
from .wind import USER_AGENT

BASE_URL = "https://api.weather.gov"

#: What the grid publishes speeds in, and the factor to knots for each.
_TO_KT = {"wmoUnit:km_h-1": 1 / 1.852, "wmoUnit:m_s-1": 3600 / 1852}

_DURATION = re.compile(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?$")


class LocalWindError(RuntimeError):
    pass


def _get(url: str, *, timeout: float, opener) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                                   "Accept": "application/geo+json"})
    try:
        with opener(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise LocalWindError(f"{url}: HTTP {error.code}") from error
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise LocalWindError(f"{url}: {error}") from error


def _hours(valid_time: str) -> list[datetime]:
    """The whole UTC hours an ISO interval covers: "2026-09-30T05:00:00+00:00/PT3H"."""

    start, _, span = valid_time.partition("/")
    found = _DURATION.match(span)
    if not found:
        raise LocalWindError(f"unreadable interval {valid_time!r}")
    days, hours, minutes = (int(v or 0) for v in found.groups())
    begin = datetime.fromisoformat(start).astimezone(timezone.utc)
    length = timedelta(days=days, hours=hours, minutes=minutes)
    n = max(1, int(length.total_seconds() // 3600))
    return [begin + timedelta(hours=k) for k in range(n)]


def _series(prop: dict, *, speed: bool) -> dict[str, float]:
    unit = prop.get("uom", "")
    factor = 1.0
    if speed:
        if unit not in _TO_KT:
            raise LocalWindError(f"wind speed in {unit!r}, not a unit this reads")
        factor = _TO_KT[unit]
    elif unit not in ("wmoUnit:degree_(angle)", ""):
        raise LocalWindError(f"wind direction in {unit!r}")
    out = {}
    for item in prop.get("values") or []:
        value = item.get("value")
        if value is None:
            continue
        for hour in _hours(item["validTime"]):
            out[hour.strftime(ISO)] = value * factor
    return out


def parse_grid(grid: dict) -> dict:
    """The hourly local wind a gridpoint document carries, and whose it is.

    An hour missing its direction or its speed is left out, never filled from
    the hour beside it; a missing gust is just absent.
    """

    props = grid.get("properties") or {}
    direction = _series(props.get("windDirection") or {}, speed=False)
    speed = _series(props.get("windSpeed") or {}, speed=True)
    gust = _series(props.get("windGust") or {}, speed=True)
    hours = []
    for stamp in sorted(set(direction) & set(speed)):
        hours.append({"valid_utc": stamp,
                      "from_deg": round(direction[stamp] % 360, 0),
                      "speed_kt": round(speed[stamp], 1),
                      "gust_kt": round(gust[stamp], 1) if stamp in gust else None})
    return {"updated_utc": _stamp(props.get("updateTime")), "hours": hours}


def _stamp(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).astimezone(timezone.utc).strftime(ISO)
    except ValueError:
        return None


def fetch(lat: float, lon: float, *, timeout: float = 30.0,
          opener=urllib.request.urlopen) -> dict:
    """The NWS forecast grid's hourly wind at a point: two requests, the
    point's grid cell and then the cell's forecast."""

    point = _get(f"{BASE_URL}/points/{lat:.4f},{lon:.4f}", timeout=timeout, opener=opener)
    props = point.get("properties") or {}
    url = props.get("forecastGridData")
    if not url:
        raise LocalWindError("the point has no forecast grid")
    got = parse_grid(_get(url, timeout=timeout, opener=opener))
    got.update({
        "provider": "NWS",
        "office": props.get("gridId"),
        "grid_x": props.get("gridX"),
        "grid_y": props.get("gridY"),
        "point": [round(lat, 4), round(lon, 4)],
    })
    return got
