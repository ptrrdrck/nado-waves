"""The LIVE tab's Briefing: the swell, the conditions and the day's tides.

    python -m forecast.briefing                  # build; data/live/briefing.json
    python -m forecast.briefing --record BUILT   # keep it if it changed (the workflow's)

Owner's request, 2026-10-16, reshaped 2026-10-17 and again 2026-10-22: a
short read in a fold above the LIVE cards. Built every collection; it
UPDATES only when what it says about the swell or the tide changes, or
NWS's alerts do:

- **Alerts** (owner's request and calls, 2026-10-24): NWS's coast and ocean
  alerts in force at the build, a line each above the swell --
  "Coastal Flood Warning until 2 PM Sun" -- its name linking to NWS's page,
  tapped its NWS headline (`forecast.alerts`, from `data/alerts/`). One that
  starts, changes its words or ends is an update.
- **Swell** (owner's wording and calls, 2026-10-23), a summary of two
  sources that are never matched to each other. The beach, from 46232's
  chain: "3–4 ft (0.9–1.2 m)", the breaking height at the three breaks,
  lowest to highest in whole feet; then, a line each, the swell trains
  of all three breaks at ≥ `MIX_SHARE` of the biggest one anywhere, one a
  train at 46232, so one swell read at two breaks is one line
  (`listed_trains`, `forecast.trainmatch`; owner's call, 2026-10-24) --
  "SSW at 13.3 s, building.", each its offshore heading as its row names it
  (never its 5 m one), its period, and its status: its band at 46232 over the last day
  (`train_trend`). Offshore, at 46047: each west or
  north-west swell found by its rise and said for as long as Tanner Banks
  still holds it (`upstream_story`), due at 46232 and the breaks by
  deep-water speed (`forecast.upstreamlag`, BRIEFING §43), each line in
  plain words opening on its point, its trend said as offshore's: "W 10–12 s,
  building offshore; due at Point Loma South around 1:33 PM, and at the
  breaks 39–53 min later." -- the next of its bands not yet at the breaks
  (`next_band`), and gone once the last has passed (owner's wording and
  calls, 2026-10-23 and -24), a signal mark beside it on the page. Each
  sentence is a line of its own.
- **Conditions**, refreshed every collection without counting as an
  update: 46232's water temperature (`WATER_FRESH_H`), KNZY's air
  temperature, humidity and pressure, and rain — the last hour's and the
  rolling 24 hours', both shown when either is above zero, neither when
  not. Each with an arrow against an earlier reading and a sparkline of
  its recent readings (`trends`; owner's calls, 2026-10-23).
- **Tides**: the day's predicted turns, AM / PM, with the gauge's measured
  departure as the card's turns carry it, and the day's curve the page
  draws them on (`tide_story`; owner's choices, 2026-10-23).

An update is a change in the words the page prints for the alerts, the
swell or the tides (`briefingwording.render_issue`, Node, the page's own code), so a
change below the page's precision is no update. Each update is kept in
`data/briefings/YYYY-MM.jsonl`, append-only, with the conditions of that
moment; the page shows the newest build with the newest update's time, and
a green dot until the reader has opened the fold since.

**Never the model.** GFS-Wave and its ensemble are the Forecast tab's.
Units stay as each source publishes them — metres, °C, and inches for
METAR's precipitation; the page converts and words them
(`app/forecast.html`, `docs/briefing_wording.md`).
"""

from __future__ import annotations

#: Measured for the 2026-10-17 briefing's filling / fading and leader
#: (`forecast.briefingreport`, docs/briefing_thresholds.md), which the
#: briefing no longer says. Kept with their report.
CHANGE_SHARE = 0.15
MIN_SPAN_H = 6
LEAD_MARGIN = 0.05
PERIOD_AHEAD_H = 12

import argparse
import csv
import json
import math
import re
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from collector.common import DEFAULT_DATA_DIR, ISO, utcnow

from .alerts import briefing as nws_alerts

BREAKS = ("coronado_north", "coronado_center", "coronado_south")
UPSTREAM = "46047"
LOCAL_TZ = ZoneInfo("America/Los_Angeles")

#: Where the record lives, one JSONL file a month (Pacific).
RECORD_DIR = "briefings"

#: A KNZY report older than this is not "current".
WIND_FRESH_MIN = 90

#: 46232's water temperature older than this is not "current". Its
#: standard met reports every 30 min but reaches the archive on collect.yml's
#: throttled schedule: measured over the week to 2026-10-22, the newest was
#: a median 2.7 h old, ≤ 3 h 60% of the time and ≤ 6 h 99%.
WATER_FRESH_H = 6.0

#: The rolling precipitation total.
PRECIP_DAY_H = 24

#: 46047's rises FIND a swell; its presence keeps it (owner's call,
#: 2026-10-23). A rise is looked for this far back, and the swell is said
#: until Tanner Banks' energy from its sector over all the bands falls
#: below UPSTREAM_GONE_SHARE of its peak since it began (the rise factor of
#: 3, run in reverse); "fading" once under UPSTREAM_FADING_SHARE.
UPSTREAM_LOOKBACK_H = 72.0
UPSTREAM_GONE_SHARE = 1.0 / 3.0
UPSTREAM_FADING_SHARE = 0.5

#: The bands a rise is looked for in: §43's three (`upstreamlag.BANDS_S`),
#: and 8–10 s (owner's request, 2026-10-23), whose lag the archive check
#: there did not cover. A test pins the three to upstreamlag's.
UPSTREAM_BANDS_S = ((8.0, 10.0), (10.0, 12.0), (12.0, 14.0), (14.0, 17.0))

#: Rises in a sector's longer bands within this before its newest are one
#: swell (`disperse`): a dispersed swell's long periods lead its short ones,
#: by hours from a near storm and a day or more from a far one.
UPSTREAM_GROUP_H = 24.0

#: The trend words (owner's calls, 2026-10-23), in energy, over the last
#: TREND_H: up by BUILDING_RATIO is "building", down to FADING_RATIO
#: "fading". For each train at the beach, of its band at 46232 smoothed
#: over TREND_H (`train_trend`): else "peaking" when its highest in
#: PEAK_OVER_H came within TREND_H, else "holding". At Tanner Banks:
#: building, else fading under UPSTREAM_FADING_SHARE of the peak, else
#: peaking.
TREND_H = 3.0
BUILDING_RATIO = 1.25
FADING_RATIO = 0.75
PEAK_OVER_H = 24.0
#: A train's day must hold this share of its hours to say "peaking".
PEAK_COVER = 0.75

#: Every swell train at any of the three breaks that holds this share of
#: the biggest one's height is listed, a line each, one a compass point
#: (owner's calls, 2026-10-23: half its height, a quarter of its energy,
#: pooled over the breaks; it was 0.7, beside the lead at the biggest break,
#: from another point only). Never wind sea or local chop.
MIX_SHARE = 0.5


def _utc(stamp: str | None) -> datetime | None:
    return datetime.strptime(stamp, ISO).replace(tzinfo=timezone.utc) if stamp else None


def _iso(t: datetime | None) -> str | None:
    return t.strftime(ISO) if t else None


def _read(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return None


# ------------------------------------------------------------------ the record

def record_path(data_dir: Path, built_utc: str) -> Path:
    month = _utc(built_utc).astimezone(LOCAL_TZ).strftime("%Y-%m")
    return Path(data_dir) / RECORD_DIR / f"{month}.jsonl"


def newest(data_dir: Path) -> dict | None:
    """The newest kept line, by when it was built."""

    best = None
    for path in sorted((Path(data_dir) / RECORD_DIR).glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                got = json.loads(line)
                stamp = got.get("built_utc") or got.get("issued_utc")
                if best is None or stamp >= (best.get("built_utc") or best.get("issued_utc")):
                    best = got
    return best


def settle(kept: dict | None, built: dict) -> tuple[dict, bool]:
    """`built` as the page shows it, and whether it is an update: an update
    when its swell or tide words differ from the newest kept line's (a line
    of the 2026-10-17 design never matches), else the kept update's key and
    time on this build's conditions."""

    words = built.get("update_words")
    same = (kept is not None and words is not None and kept.get("update_words") == words)
    if same:
        return {**built, "key": kept["key"], "updated_utc": kept["updated_utc"]}, False
    return {**built, "key": built["built_utc"], "updated_utc": built["built_utc"]}, True


def append(data_dir: Path, line: dict) -> None:
    path = record_path(data_dir, line["built_utc"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, separators=(",", ":"), ensure_ascii=False) + "\n")


# ------------------------------------------------------------------ conditions

#: METAR's present-weather precipitation, by what the page calls it.
PRECIP_KINDS = (("TS", "thunder"), ("SH", "showers"), ("DZ", "drizzle"), ("RA", "rain"),
                ("SN", "snow"), ("GR", "hail"), ("GS", "hail"), ("UP", "precipitation"))


def parse_metar(raw: str) -> dict:
    """What the briefing reads from one KNZY report: temperature and
    dewpoint (°C, the RMK T group's tenths where it is there), the hour's
    precipitation (RMK P group, hundredths of an inch, routine reports only)
    and the kinds of precipitation in present weather; and the altimeter
    setting (the body's A group, inHg as METAR publishes it)."""

    out = {"air_c": None, "dew_c": None, "precip_in": None, "kinds": [], "altimeter_inhg": None}
    body, _, rmk = raw.partition(" RMK ")
    alt = re.search(r"\sA(\d{4})\b", body)
    if alt:
        out["altimeter_inhg"] = int(alt.group(1)) / 100
    exact = re.search(r"\bT([01])(\d{3})([01])(\d{3})\b", rmk)
    if exact:
        sign = lambda s: -1 if s == "1" else 1
        out["air_c"] = sign(exact.group(1)) * int(exact.group(2)) / 10
        out["dew_c"] = sign(exact.group(3)) * int(exact.group(4)) / 10
    else:
        main = re.search(r"\s(M?\d{2})/(M?\d{2})?\s", body + " ")
        if main:
            num = lambda s: -int(s[1:]) if s.startswith("M") else int(s)
            out["air_c"] = num(main.group(1))
            out["dew_c"] = num(main.group(2)) if main.group(2) else None
    hourly = re.search(r"\bP(\d{4})\b", rmk)
    if hourly and raw.startswith("METAR"):
        out["precip_in"] = int(hourly.group(1)) / 100
    for token in body.split()[2:]:
        bare = token.lstrip("+-")
        if bare.startswith("VC") or not re.fullmatch(r"(TS|SH)?(RA|DZ|SN|GR|GS|UP)+|TS", bare):
            continue
        for code, kind in PRECIP_KINDS:
            if code in bare and kind not in out["kinds"]:
                out["kinds"].append(kind)
    return out


def humidity(air_c: float, dew_c: float) -> float:
    """Relative humidity in percent from temperature and dewpoint (Magnus,
    Alduchov & Eskridge's constants)."""

    f = lambda t: math.exp(17.625 * t / (243.04 + t))
    return 100.0 * f(dew_c) / f(air_c)




def _knzy_reports(data_dir: Path, start: datetime, end: datetime) -> list[tuple[datetime, str, dict]]:
    path = Path(data_dir) / "wind" / "KNZY.csv"
    rows = []
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                t = _utc(row["observed_utc"])
                if start < t <= end and row.get("raw"):
                    rows.append((t, row["raw"], parse_metar(row["raw"])))
    rows.sort(key=lambda r: r[0])
    return rows


def weather_now(data_dir: Path, at: datetime) -> dict:
    """KNZY's newest report: air temperature and humidity; the newest
    routine report's altimeter setting; and the
    precipitation of the last hour (the newest routine report's P group) and
    of the last `PRECIP_DAY_H` (every routine report's), with the kinds
    reported in the last hour."""

    rows = _knzy_reports(data_dir, at - timedelta(hours=PRECIP_DAY_H), at)
    fresh = [r for r in rows if at - r[0] <= timedelta(minutes=WIND_FRESH_MIN)]
    air = next(((t, m) for t, _, m in reversed(fresh) if m["air_c"] is not None), None)
    routine = [(t, m) for t, raw, m in rows if raw.startswith("METAR")]
    last = next(((t, m) for t, m in reversed(routine) if at - t <= timedelta(minutes=WIND_FRESH_MIN)), None)
    hour_kinds = []
    for t, _, m in fresh:
        if at - t <= timedelta(minutes=60):
            hour_kinds += [k for k in m["kinds"] if k not in hour_kinds]
    return {"station": "KNZY",
            "air_c": air[1]["air_c"] if air else None,
            "humidity_pct": (round(humidity(air[1]["air_c"], air[1]["dew_c"]), 1)
                             if air and air[1]["dew_c"] is not None else None),
            "observed_utc": _iso(air[0]) if air else None,
            "precip_hour_in": (last[1]["precip_in"] or 0.0) if last else None,
            "precip_day_in": round(sum(m["precip_in"] or 0.0 for _, m in routine), 2) if routine else None,
            "precip_kinds": hour_kinds,
            "pressure_inhg": last[1]["altimeter_inhg"] if last else None,
            "pressure_utc": _iso(last[0]) if last and last[1]["altimeter_inhg"] is not None else None}


def water_now(data_dir: Path, at: datetime, station: str = "46232") -> dict | None:
    """46232's newest water temperature (its standard met, WTMP)."""

    from collector.ndbc import is_missing

    path = Path(data_dir) / "observations" / f"{station}.csv"
    if not path.exists():
        return None
    best = None
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            token = row.get("wtmp") or ""
            t = _utc(row["timestamp_utc"])
            if (token and not is_missing("WTMP", token) and t <= at
                    and at - t <= timedelta(hours=WATER_FRESH_H) and (best is None or t > best[0])):
                best = (t, float(token))
    return {"station": station, "c": best[1], "observed_utc": _iso(best[0])} if best else None


# ------------------------------------------------------------------ trends

#: The conditions' arrows and sparklines (owner's calls, 2026-10-23). Water
#: and air are compared with the reading TREND_BACK_H earlier, not the one
#: before: measured over the archive, the previous reading was the same on
#: 64% of 46232's half-hours and 32% of KNZY's hours, 3 h back on 22% and
#: 15%. Humidity and pressure with the report before. A change under half a
#: source's own step is steady; humidity, computed, is compared in the whole
#: percent the page shows.
TREND_BACK_H = 3.0
TREND_MATCH_MIN = 20
STEADY = {"water": 0.05, "air": 0.05, "humidity": 0.5, "pressure": 0.005}
#: Each sparkline's window, by how fast the condition moves.
SPARK_H = {"water": 14 * 24, "air": 24, "humidity": 24, "pressure": 72, "beach": 24}
RAIN_DAYS = 7


def _direction(key: str, now: float, was: float | None) -> str | None:
    if was is None:
        return None
    if key == "humidity":            # computed, not measured: compared as the page shows it
        now, was = round(now), round(was)
    d = now - was
    return "steady" if abs(d) < STEADY[key] else "up" if d > 0 else "down"


def _near(series: list[tuple[datetime, float]], t: datetime, within_min: float):
    best = min(series, key=lambda p: abs((p[0] - t).total_seconds()), default=None)
    return best if best and abs((best[0] - t).total_seconds()) <= within_min * 60 else None


def _hourly(series: list[tuple[datetime, float]]) -> list[list]:
    """One reading an hour, the hour's newest, as [epoch s, value]: the
    sparkline's points. Never a value an hour did not have."""

    by_hour = {}
    for t, v in series:
        by_hour[t.replace(minute=0, second=0, microsecond=0)] = (t, v)
    return [[int(t.timestamp()), round(v, 3)] for t, v in sorted(by_hour.values())]


def _trend(key: str, series: list[tuple[datetime, float]], back_h: float | None) -> dict | None:
    """The newest reading's arrow against the one `back_h` earlier (the
    report before when None), and the sparkline over SPARK_H[key]."""

    if not series:
        return None
    t, v = series[-1]
    if back_h is None:
        before = series[-2] if len(series) > 1 and t - series[-2][0] <= timedelta(minutes=WIND_FRESH_MIN) else None
    else:
        before = _near(series[:-1], t - timedelta(hours=back_h), TREND_MATCH_MIN)
    spark = [p for p in series if p[0] > t - timedelta(hours=SPARK_H[key])]
    return {"dir": _direction(key, v, before[1] if before else None),
            "was": round(before[1], 3) if before else None, "was_utc": _iso(before[0]) if before else None,
            "window_h": SPARK_H[key], "spark": _hourly(spark)}


def trends(data_dir: Path, at: datetime, water: dict | None, weather: dict) -> dict:
    """The arrows and sparklines for the conditions shown: only for a
    reading the block shows, each from its own source's archive."""

    from collector.ndbc import is_missing

    out = {}
    if water:
        path = Path(data_dir) / "observations" / f"{water['station']}.csv"
        newest = _utc(water["observed_utc"])
        ser = {}
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                token = row.get("wtmp") or ""
                t = _utc(row["timestamp_utc"])
                if token and not is_missing("WTMP", token) and newest - timedelta(hours=SPARK_H["water"]) < t <= newest:
                    ser[t] = float(token)
        out["water"] = _trend("water", sorted(ser.items()), TREND_BACK_H)
    span = max(SPARK_H["air"], SPARK_H["pressure"], RAIN_DAYS * 24) + 24
    routine = [(t, m) for t, raw, m in _knzy_reports(data_dir, at - timedelta(hours=span), at)
               if raw.startswith("METAR")]
    if weather.get("air_c") is not None:
        out["air"] = _trend("air", [(t, m["air_c"]) for t, m in routine if m["air_c"] is not None], TREND_BACK_H)
    if weather.get("humidity_pct") is not None:
        out["humidity"] = _trend("humidity", [(t, humidity(m["air_c"], m["dew_c"])) for t, m in routine
                                              if m["air_c"] is not None and m["dew_c"] is not None], None)
    if weather.get("pressure_inhg") is not None:
        out["pressure"] = _trend("pressure", [(t, m["altimeter_inhg"]) for t, m in routine
                                              if m["altimeter_inhg"] is not None], None)
    if weather.get("precip_hour_in") is not None:
        today = at.astimezone(LOCAL_TZ).date()
        days = {today - timedelta(days=k): None for k in range(RAIN_DAYS - 1, -1, -1)}
        for t, m in routine:
            d = t.astimezone(LOCAL_TZ).date()
            if d in days:
                days[d] = round((days[d] or 0.0) + (m["precip_in"] or 0.0), 2)
        out["rain"] = {"days": [[str(d), v] for d, v in days.items()]}
    return out


def unsparked(line: dict) -> dict:
    """A build as the record keeps it: the arrows, not the sparklines or the
    tide's curve, which are the archives' own readings over again."""

    line = json.loads(json.dumps(line))
    for t in ((line.get("conditions") or {}).get("trends") or {}).values():
        if isinstance(t, dict):
            t.pop("spark", None)
            t.pop("days", None)
    (line.get("swell") or {}).pop("spark", None)
    for key in ("curve", "nights"):
        (line.get("tide") or {}).pop(key, None)
    return line


# ------------------------------------------------------------------ swell

def _value_near(ser: list[tuple[datetime, float]], t: datetime, within_h: float) -> float | None:
    """The value at the stamp nearest `t`, if one is within `within_h`."""

    if not ser:
        return None
    tt, v = min(ser, key=lambda p: abs((p[0] - t).total_seconds()))
    return v if abs((tt - t).total_seconds()) <= within_h * 3600.0 else None


def upstream_story(data_dir: Path, buoys: dict | None, at: datetime, spectra=None) -> list[dict]:
    """46047's west and north-west swells: one entry per sector holding a
    swell that rose in the last UPSTREAM_LOOKBACK_H and is still there, its
    bands earliest first (a dispersed swell's long periods lead), each band
    when it rose and when deep water puts it at 46232 and the breaks
    (BRIEFING §43); its first arrival at the breaks, and its trend at Tanner
    Banks now."""

    from . import upstreamlag as ul

    fresh = next((b for b in (buoys or {}).get("buoys", []) if b["station"] == UPSTREAM), None)
    if not fresh or fresh.get("stale"):
        return []
    if spectra is None:
        from .transform import load_spectra
        try:
            spectra = load_spectra(Path(data_dir) / "spectra" / UPSTREAM)
        except (FileNotFoundError, ValueError):
            return []
    since = at - timedelta(hours=UPSTREAM_LOOKBACK_H)
    recent = [s.with_spread("mem") for s in spectra
              if since - timedelta(hours=ul.RISE_WITHIN_H) <= s.time <= at]
    whole_band = (UPSTREAM_BANDS_S[0][0], UPSTREAM_BANDS_S[-1][1])
    out = []
    for sector in ul.TIMED:
        heading = sum(ul.SECTORS[sector]) / 2.0
        risen = {}
        for band in UPSTREAM_BANDS_S:
            smoothed = ul.smooth_log(ul.series(recent, band, ul.SECTORS[sector]), ul.SMOOTH_ONSET_H)
            risen[band] = [r for r in ul.rises(smoothed) if since - timedelta(hours=UPSTREAM_GROUP_H) <= r.mid <= at]
        swell = disperse(risen, since)
        if not swell:
            continue
        start = min(r.start for _, r in swell)
        held = [(t, math.exp(v)) for t, v in ul.smooth_log(ul.series(recent, whole_band, ul.SECTORS[sector]),
                                                           ul.SMOOTH_ONSET_H) if t >= start]
        if not held:
            continue
        peak, now_e = max(v for _, v in held), held[-1][1]
        if now_e < peak * UPSTREAM_GONE_SHARE:
            continue
        before = _value_near(held, held[-1][0] - timedelta(hours=TREND_H), 0.75)
        trend = ("building" if before and now_e / before >= BUILDING_RATIO
                 else "fading" if now_e < peak * UPSTREAM_FADING_SHARE else "peaking")
        bands = []
        for band, rise in swell:
            period = sum(band) / 2.0
            lag = ul.deep_water_lag_h(period, heading)
            at_buoy = rise.mid + timedelta(hours=lag)
            legs = []
            for bid in BREAKS:
                lg = ul.leg_over(bid, period, ul.ANCHOR_SECTORS[sector])
                if lg:
                    legs.append({"id": bid, "lo_min": round(lg.lo_min), "hi_min": round(lg.hi_min)})
            bands.append({"band_s": list(band), "since_utc": _iso(_minute(rise.mid)),
                          "factor": round(rise.factor, 1), "lag_h": round(lag, 1),
                          "due_buoy_utc": _iso(_minute(at_buoy)), "legs": legs})
        bands.sort(key=lambda b: b["since_utc"])
        first = bands[0]
        arrives = _utc(first["due_buoy_utc"]) + timedelta(
            minutes=min((l["lo_min"] for l in first["legs"]), default=0))
        out.append({"sector": sector, "sector_deg": list(ul.SECTORS[sector]), "bands": bands,
                    "arrives_utc": _iso(arrives), "trend": trend,
                    "peak_m2": round(peak, 5), "now_m2": round(now_e, 5), "read_utc": _iso(held[-1][0])})
    return out


def next_band(swell: dict, at: datetime) -> dict | None:
    """The band of a Tanner Banks swell the Briefing names at `at`: the
    first, by its due time, whose window at the breaks (due at 46232 plus
    the slowest leg) has not yet passed. None once the last has: by then the
    swell is the beach chain's to show, in the headline or not at all
    (owner's call, 2026-10-24, replacing "arriving since")."""

    def window_end(band):
        return _utc(band["due_buoy_utc"]) + timedelta(
            minutes=max((leg["hi_min"] for leg in band.get("legs") or []), default=0))

    ahead = [b for b in swell.get("bands") or [] if window_end(b) > at]
    return min(ahead, key=lambda b: b["due_buoy_utc"]) if ahead else None


def disperse(risen: dict, since: datetime) -> list[tuple[tuple[float, float], object]]:
    """One swell from each band's rises, as dispersion orders it: the newest
    rise since `since`, then each LONGER band's newest rise before the one
    already taken, within UPSTREAM_GROUP_H of the newest; a band that did
    not rise on its own is passed over (its energy rode in under its
    neighbours'). A shorter band that
    rose earlier is another swell (a dispersed swell's long periods lead),
    and so is a longer band that rose later."""

    newest = max(((b, r) for b, rs in risen.items() for r in rs if r.mid >= since),
                 key=lambda br: br[1].mid, default=None)
    if newest is None:
        return []
    swell, (band, rise) = [newest], newest
    limit = rise.mid - timedelta(hours=UPSTREAM_GROUP_H)
    for longer in sorted((b for b in risen if b[0] > band[0]), key=lambda b: b[0]):
        earlier = [r for r in risen[longer] if limit <= r.mid <= swell[-1][1].mid]
        if earlier:
            swell.append((longer, earlier[-1]))
    return swell


def trend_word(pts: list[tuple[datetime, float]]) -> str | None:
    """Building, fading, peaking or holding: an hourly energy series
    averaged over the trailing TREND_H, its newest against TREND_H before.
    None without that hour: a gap is never filled from the hour beside it."""

    if not pts:
        return None
    newest = pts[-1][0]
    pts = [p for p in pts if p[0] > newest - timedelta(hours=PEAK_OVER_H + TREND_H)]
    span = timedelta(hours=TREND_H - 1.0)
    smooth = []
    for t, _ in pts:
        w = [v for tt, v in pts if t - span <= tt <= t]
        smooth.append((t, sum(w) / len(w)))
    now_e = smooth[-1][1]
    before = next((v for t, v in smooth if t == newest - timedelta(hours=TREND_H)), None)
    if before is None:
        return None
    if now_e / before >= BUILDING_RATIO:
        return "building"
    if now_e / before <= FADING_RATIO:
        return "fading"
    day = [(t, v) for t, v in smooth if t > newest - timedelta(hours=PEAK_OVER_H)]
    if len(day) >= PEAK_COVER * PEAK_OVER_H:
        top = max(day, key=lambda p: p[1])[0]
        if top >= newest - timedelta(hours=TREND_H):
            return "peaking"
    return "holding"


def beach_spark(steps: list[dict]) -> list[list]:
    """The swell headline's sparkline: the biggest of the three breaks'
    breaking heights each hour over SPARK_H["beach"], in metres, a missing
    hour missing."""

    pts = []
    for st in steps or []:
        if st.get("gap") or st.get("pending"):
            continue
        hs = [((st.get("breaks") or {}).get(b) or {}).get("hs_m") for b in BREAKS]
        hs = [h for h in hs if h is not None]
        if hs:
            pts.append((_utc(st["valid_utc"]), max(hs)))
    if not pts:
        return []
    newest = pts[-1][0]
    return _hourly([p for p in pts if p[0] > newest - timedelta(hours=SPARK_H["beach"])])


def _minute(t: datetime) -> datetime:
    return t.replace(second=0, microsecond=0)




def _heading(train: dict) -> float | None:
    lobes = train.get("lobes") or []
    return lobes[0][0] if len(lobes) >= 2 else train.get("from_deg")


def listed_trains(sites: list[dict]) -> list[dict]:
    """The swell trains the headline lists, POOLED over the three breaks
    (owner's call, 2026-10-23, after the WSW sea leading Center and South
    went unsaid because North was the biggest break): every swell train at
    any break at ≥ MIX_SHARE of the biggest one anywhere, biggest first,
    and ONE LINE A BUOY TRAIN (owner's call, 2026-10-24, replacing one a
    compass point, which listed one W swell twice either side of the W / WSW
    boundary): trains at two breaks that are the same train at 46232
    (`buoy_train`, `forecast.trainmatch`) are one line, the biggest's. A
    train with no buoy train is its own line. Never wind sea or local chop;
    with no swell train at all, the biggest break's lead as its row gives it.
    Each with its offshore heading as its row names it, and its band at the
    buoy (`band_hz`, `held_deg`) from its own break when the reading carries
    one."""

    order = {b: k for k, b in enumerate(BREAKS)}
    pool = sorted(((t, site) for site in sites for t in site.get("trains") or []
                   if not t.get("wind_sea") and not t.get("local") and _heading(t) is not None),
                  key=lambda ts: (-(ts[0].get("hs_m") or 0.0), order.get(ts[1].get("id"), 9)))
    if not pool:
        if not sites:
            return []
        top = max(sites, key=lambda b: b.get("hs_nearshore_m") or 0.0)
        trains = top.get("trains") or []
        if trains:
            t = trains[0]
            return [{"period_s": t.get("period_s"), "from_deg": _heading(t), "hs_m": t.get("hs_m"),
                     "band_hz": t.get("band_hz"), "held_deg": t.get("held_deg")}]
        return ([{"period_s": top.get("peak_period_s"), "from_deg": top.get("peak_direction_deg"),
                  "hs_m": top.get("hs_nearshore_m")}] if top.get("peak_period_s") is not None else [])
    biggest = pool[0][0].get("hs_m") or 0.0
    out, said = [], set()
    for t, site in pool:
        if (t.get("hs_m") or 0.0) < MIX_SHARE * biggest:
            break
        swell = t.get("buoy_train")
        if swell is not None:
            if swell in said:
                continue
            said.add(swell)
        out.append({"period_s": t.get("period_s"), "from_deg": _heading(t), "hs_m": t.get("hs_m"),
                    "band_hz": t.get("band_hz"), "held_deg": t.get("held_deg")})
    return out


def band_energy(spectrum, band_hz, held) -> float | None:
    """m² at the buoy in a train's band: the frequency bins from its lowest
    to its highest, from the headings it held (`held_deg`; every heading
    when it held them all), by maximum entropy in closed form. A bin MEM
    cannot represent (r1 at its ceiling, or moments it finds unrealisable)
    is read as the chain reads it (`transform.Spectrum.density`): by NDBC's
    clamped Fourier form, so the status reads the same energy the card's
    heights were made from. Before 2026-10-27 such a bin dropped the whole
    band, and 9 of 225 train lines since 23 Oct had no status; 16.7% of
    46232's spectra hold at least one. None only when a bin has no reading
    at all (an energetic bin with none never loads: `transform.unplaceable_bin`):
    never a partial sum."""

    from .spreadmethod import R1_CEILING, Unrealisable, mem_sector, shipped

    lo, hi = band_hz
    whole = not held or (held[1] - held[0]) % 360 == 0
    total, n = 0.0, 0
    for i, f in enumerate(spectrum.frequencies):
        if not lo - 1e-9 <= f <= hi + 1e-9:
            continue
        e = spectrum.c11[i]
        if e is None or math.isnan(e):
            return None
        share = 1.0
        if not whole:
            vals = (spectrum.r1[i], spectrum.r2[i], spectrum.a1[i], spectrum.a2[i])
            if any(v is None or math.isnan(v) for v in vals):
                return None
            try:
                if vals[0] >= R1_CEILING:
                    raise Unrealisable("r1 at its ceiling")
                share = mem_sector(*vals, float(held[0]), float(held[1]))
            except (Unrealisable, ValueError, ZeroDivisionError):
                share = fourier_sector(shipped(*vals), held)
        total += e * spectrum.bin_width(i) * share
        n += 1
    return total if n else None


def fourier_sector(dist: list[float], held) -> float:
    """The share of a 1° distribution (`spreadmethod.shipped`'s, centred on
    each half degree) between two bearings, clockwise from the first."""

    lo, width = held[0] % 360.0, (held[1] - held[0]) % 360.0
    return sum(v for d, v in enumerate(dist) if (d + 0.5 - lo) % 360.0 < width)


def train_trend(spectra, train: dict, newest: datetime) -> str | None:
    """A train's status (owner's call, 2026-10-23): its band at 46232 --
    the periods and headings it holds in the newest spectrum -- each hour
    of the last PEAK_OVER_H + TREND_H, through `trend_word`. Nothing follows
    a train between spectra, so this is the band's energy, not the train's."""

    if not train.get("band_hz"):
        return None
    start = newest - timedelta(hours=PEAK_OVER_H + TREND_H)
    pts = []
    for sp in spectra:
        if start < sp.time <= newest:
            e = band_energy(sp, train["band_hz"], train.get("held_deg"))
            if e is not None:
                pts.append((sp.time, e))
    if not pts or pts[-1][0] != newest:
        return None
    return trend_word(pts)


def swell_story(now: dict, buoys: dict | None, at: datetime, data_dir: Path,
                series: dict | None = None, spectra=None) -> dict:
    """The breaking height at each break as the cards show it; the trains
    the page lists, pooled over the three breaks, each with its status; the
    biggest breaking height's last day; and 46047's swells."""

    newest = _utc(now.get("observed_utc"))
    if now.get("stale") or newest is None:
        return {"dark": True, "newest_utc": _iso(newest)}
    sites = [b for b in now.get("breaks", []) if b.get("id") in BREAKS and b.get("hs_nearshore_m") is not None]
    trains = listed_trains(sites)
    if trains:
        if any(t.get("band_hz") for t in trains):
            if spectra is None:
                from .transform import load_spectra
                try:
                    spectra = load_spectra(Path(data_dir) / "spectra" / (now.get("station") or "46232"))
                except (FileNotFoundError, ValueError):
                    spectra = []
            for t in trains:
                t["trend"] = train_trend(spectra, t, newest)
        for t in trains:
            t.pop("band_hz", None)
            t.pop("held_deg", None)
            t.setdefault("trend", None)
    coming = [(c, next_band(c, at)) for c in upstream_story(data_dir, buoys, at)]
    steps = (series or {}).get("steps") or []
    return {"dark": False, "newest_utc": _iso(newest),
            "breaks": [{"id": b["id"], "hs_m": b["hs_nearshore_m"]} for b in sites],
            "trains": trains, "spark": beach_spark(steps), "window_h": SPARK_H["beach"],
            "coming": [{"sector": c["sector"], "sector_deg": c["sector_deg"], **band, "trend": c["trend"]}
                       for c, band in coming if band is not None]}


# ------------------------------------------------------------------ tide

#: The day's tide curve, a point every this many minutes: the hourly
#: prediction interpolated as the Tide card's is, close enough that the
#: drawn curve meets each turn's own dot.
TIDE_CURVE_MIN = 30

def tide_story(now: dict, data_dir: Path, at: datetime) -> dict:
    """The Pacific day's predicted turns at the open coast, each carrying
    the gauge's measured departure as the card's do."""

    from .daylight import nights
    from .tidesite import anomaly, coast_predicted, coast_turn, predicted_series
    from .tideturns import read_turns

    departure, _ = anomaly(data_dir, at)
    day = at.astimezone(LOCAL_TZ).date()
    start = datetime.combine(day, time(0), tzinfo=LOCAL_TZ).astimezone(timezone.utc)
    end = datetime.combine(day + timedelta(days=1), time(0), tzinfo=LOCAL_TZ).astimezone(timezone.utc)
    turns = [coast_turn(t, departure).as_dict()
             for t in read_turns(data_dir, now.get("tide_station") or "9410170")]
    # The day's curve (owner's choice, 2026-10-23): the same prediction the
    # turns are, at the open coast with the departure, every TIDE_CURVE_MIN
    # from Coronado's midnight to the next; a stamp the prediction does not
    # reach is left out, never filled.
    predicted = predicted_series(data_dir)
    curve, t = [], start
    while t <= end:
        h = coast_predicted(predicted, t, departure)
        if h is not None:
            curve.append([int(t.timestamp()), round(h, 3)])
        t += timedelta(minutes=TIDE_CURVE_MIN)
    return {"day": day.isoformat(), "station": now.get("tide_station") or "9410170",
            "departure_m": round(departure, 3) if departure is not None else None,
            "turns": [{k: t[k] for k in ("valid_utc", "height_m", "event")} for t in turns
                      if start <= _utc(t["valid_utc"]) < end],
            "start_utc": _iso(start), "end_utc": _iso(end), "curve": curve,
            "nights": nights(start, end)}


# ------------------------------------------------------------------ build

def build(*, data_dir: Path = DEFAULT_DATA_DIR, at: datetime | None = None,
          live_dir: Path | None = None) -> dict:
    """This collection's briefing, from the payloads it just wrote into
    `live_dir` (``data/live``) and the archives under `data_dir`."""

    live = Path(live_dir) if live_dir else Path(data_dir) / "live"
    at = at or utcnow()
    built = _iso(_minute(at))
    now = _read(live / "now.json")
    if not now:
        return {"built_utc": built, "available": False, "why": "no observed reading was built this collection"}
    origin = now.get("origin") or {}
    return {
        "built_utc": built, "available": True,
        "station": now.get("station"), "station_cdip": now.get("station_cdip"),
        "station_names": origin.get("station_names") or {},
        "alerts": nws_alerts(Path(data_dir), at),
        "swell": swell_story(now, _read(live / "buoys.json"), at, Path(data_dir), _read(live / "series.json")),
        "conditions": _conditions(Path(data_dir), at),
        "tide": tide_story(now, Path(data_dir), at),
    }


def _conditions(data_dir: Path, at: datetime) -> dict:
    water, weather = water_now(data_dir, at), weather_now(data_dir, at)
    return {"water": water, "weather": weather, "trends": trends(data_dir, at, water, weather)}


def with_text(built: dict) -> dict:
    """The build with the words the page prints from it, and the alert,
    swell and tide words that decide an update. Without Node the words are null and
    every build is an update, said on stderr."""

    from .briefingwording import render_issue

    try:
        text = render_issue(built)
    except Exception as exc:  # noqa: BLE001 -- the payload stands without its words
        print(f"briefing: words not rendered ({type(exc).__name__}: {exc})", file=sys.stderr)
        return {**built, "text": None, "update_words": None}
    return {**built, "text": text, "update_words": text["alerts"] + text["swell"] + text["tides"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--live-dir", type=Path, default=None,
                        help="where now.json and the other payloads are (default DATA_DIR/live)")
    parser.add_argument("--out", type=Path, default=None, help="the page's file (default LIVE_DIR/briefing.json)")
    parser.add_argument("--built-out", type=Path, default=None,
                        help="this collection's build, for --record (default LIVE_DIR/briefing_built.json)")
    parser.add_argument("--record", type=Path, default=None, metavar="BUILT",
                        help="settle this build against DATA_DIR's record, keep it if it is an update, "
                             "and write --out")
    parser.add_argument("--at", default=None, help="build as of this UTC stamp (testing)")
    args = parser.parse_args(argv)
    live = args.live_dir or Path(args.data_dir) / "live"
    out = args.out or live / "briefing.json"
    out.parent.mkdir(parents=True, exist_ok=True)

    if args.record is not None:
        built = _read(args.record)
        if not built or not built.get("available"):
            print("Nothing built this collection.")
            return 0
        page, update = settle(newest(args.data_dir), built)
        if update:
            append(args.data_dir, unsparked(page))
        print(f"{'Updated' if update else 'No change'}: {page['key']}")
    else:
        at = _utc(args.at) if args.at else utcnow()
        built = build(data_dir=args.data_dir, at=at, live_dir=live)
        built_out = args.built_out or live / "briefing_built.json"
        if not built.get("available"):
            built_out.unlink(missing_ok=True)
            print(f"Not built: {built['why']}")
            page = newest(args.data_dir) or {"available": False, "why": built["why"]}
        else:
            built = with_text(built)
            built_out.write_text(json.dumps(built, indent=1, ensure_ascii=False), encoding="utf-8")
            page, update = settle(newest(args.data_dir), built)
            print(f"Built {built['built_utc']}; {'an update' if update else 'no change'} against the local record")
    out.write_text(json.dumps(page, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
