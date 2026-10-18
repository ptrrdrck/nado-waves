"""The LIVE tab's Briefing: a Morning and a Midday issue, each kept.

    python -m forecast.briefing                  # issue if one is due; data/live/briefing.json
    python -m forecast.briefing --record ISSUE   # append ISSUE to the record (the workflow's)

Owner's request, 2026-10-16, reshaped 2026-10-17: a lifeguard's read above
the LIVE cards, so the cards need not be put together by hand. Rebuilt every
collection it never sat still, which defeated its calm purpose, so it is now
ISSUED twice a day and then left alone:

- **Morning** at `ISSUES["morning"]` Pacific, over the night since the last
  sunset; **Midday** at `ISSUES["midday"]`, over the morning since the
  Morning slot. Issued by the first collection at or after its slot, and
  not at all once `MAX_LATE_H` has passed: a missed issue is a gap, never
  written later as though it had been on time.
- **Every issue is kept** in `data/briefings/YYYY-MM.jsonl`, one line each,
  append-only, the payload as built and, where Node is installed, the words
  the page printed from it (`briefingwording.render_issue`): the record of
  what was said, which no later change to the page or the chain rewrites.
  The page shows the newest line (`data/live/briefing.json`).

Five entries, each over its own clock:

- **Overview**: sunrise and daylight (`forecast.sunset`, the Sun card's sea
  horizon), and the weather over the window from KNZY's reports — rain,
  air temperature, humidity — with 46232's water temperature.
- **Swell**: 46232's trains now and at the previous issue's newest spectrum
  ("what was out there"), each break's breaking height then and now with
  filling / fading on `CHANGE_SHARE`, the leader on `LEAD_MARGIN`; Origin's
  arrivals (arriving, and finished since the window opened); 46047's west or
  north-west rises, due here by deep-water speed (coming; BRIEFING §43).
- **Tide**: the turns around the issue, the previous one and the rest of the
  day's (predicted, with the gauge's departure, as the card's), the departure
  itself, the day's range and the phase.
- **Wind**: KNZY's newest report against the same hour on every archived day
  before it, by the card's verdict at each break. A COUNT of past days, never
  a habit: when the wind turns onshore was measured and failed (under half
  the days within 1.5 h, docs/briefing_thresholds.md) and is not said.
- **Watching**: every storm NHC is tracking, when its swell is due at the
  breaks by deep-water speed, or that its path is behind land.

**Never the model.** GFS-Wave and its ensemble are the Forecast tab's; the
briefing is the LIVE chain, KNZY's reports and NHC's fixes and official
forecast (owner's call, 2026-10-16).

**Every word that judges is measured** (`forecast.briefingreport`): filling
and fading are the measured rose and dropped, said only over a span the
measurement covered (`MIN_SPAN_H`), a leader only past its margin.

Units stay as each source publishes them — metres, knots, °C, and inches for
METAR's precipitation; the page converts and words them (`app/forecast.html`,
`docs/briefing_wording.md`). Its own file and its own step: a context buoy
never enters `now.json` or the chain.
"""

from __future__ import annotations

#: Filling / fading: the 3-hour medians then and now differ by at least this
#: share (measured: the smallest step right ≥ 85% on every break and span
#: 6–24 h; 10% held from 12 h but north reached only 83% over 6 h).
CHANGE_SHARE = 0.15

#: Spans shorter than this were not measured; the swell entry then gives the
#: two readings with no word between them.
MIN_SPAN_H = 6

#: A break leads when its 3-hour median is ahead of the next by this share
#: (measured: 3% is the smallest right ≥ 85%, 86.3%; 5% so the two heights
#: differ on screen at 0.1 ft).
LEAD_MARGIN = 0.05

#: A running ridge's period is projected this far ahead, in whole seconds
#: (measured: within 1 s on 9 of 9 at 12 h; 4 of 5 at 24 h).
PERIOD_AHEAD_H = 12

import argparse
import bisect
import csv
import json
import math
import re
import statistics
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from collector.common import DEFAULT_DATA_DIR, ISO, utcnow

BREAKS = ("coronado_north", "coronado_center", "coronado_south")
UPSTREAM = "46047"
LOCAL_TZ = ZoneInfo("America/Los_Angeles")

#: The two issues, in Pacific time (owner's request, 2026-10-17).
ISSUES = {"morning": time(6, 0), "midday": time(12, 0)}

#: An issue is written by the first collection at or after its slot, up to
#: this long after it. Later is a gap: a Morning written at 11 AM would
#: present a late read as the morning's.
MAX_LATE_H = 3.0

#: Where the record lives, one JSONL file a month (the issue's Pacific day).
RECORD_DIR = "briefings"

#: The wind is compared with the reading taken in the hour up to the same
#: clock time on each earlier day (windtide's hour slot, never carried).
WIND_SLOT_MIN = 60

#: A KNZY report older than this at the issue is not "now".
WIND_FRESH_MIN = 90

#: A 46047 rise is kept until this long after its swell was due at the last
#: break: the briefing says "due", and by then the arriving story has it.
UPSTREAM_KEEP_H = 6.0


def _utc(stamp: str | None) -> datetime | None:
    return datetime.strptime(stamp, ISO).replace(tzinfo=timezone.utc) if stamp else None


def _iso(t: datetime | None) -> str | None:
    return t.strftime(ISO) if t else None


def _read(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return None


def last_sunset(moment: datetime) -> datetime:
    """The newest sunset at the center break at or before `moment`."""

    from .daylight import _sun, position

    lat, lon = position()
    best = None
    for back in range(0, 3):
        t = _sun((moment - timedelta(days=back)).date(), lat, lon, False)
        if t is not None and t <= moment and (best is None or t > best):
            best = t
    return best


# ------------------------------------------------------------------ issues

def slot(day: date, edition: str) -> datetime:
    """An issue's slot, in UTC, on the Pacific `day`."""

    return datetime.combine(day, ISSUES[edition], tzinfo=LOCAL_TZ).astimezone(timezone.utc)


def key(day: date, edition: str) -> str:
    return f"{day.isoformat()}-{edition}"


def latest_slot(at: datetime) -> tuple[date, str, datetime]:
    """The newest slot at or before `at`."""

    local = at.astimezone(LOCAL_TZ).date()
    best = None
    for day in (local - timedelta(days=1), local):
        for edition in ISSUES:
            t = slot(day, edition)
            if t <= at and (best is None or t > best[2]):
                best = (day, edition, t)
    return best


def previous_slot(day: date, edition: str) -> tuple[date, str, datetime]:
    """The slot before this one: Midday's is the same day's Morning, the
    Morning's the day before's Midday."""

    order = list(ISSUES)
    i = order.index(edition)
    if i:
        return day, order[i - 1], slot(day, order[i - 1])
    before = day - timedelta(days=1)
    return before, order[-1], slot(before, order[-1])


def due(at: datetime, record: dict[str, dict]) -> tuple[date, str, datetime] | None:
    """The issue to write now, if any: the newest slot, unless it is already
    in the record or more than `MAX_LATE_H` old."""

    day, edition, t = latest_slot(at)
    if key(day, edition) in record or at - t > timedelta(hours=MAX_LATE_H):
        return None
    return day, edition, t


def record_path(data_dir: Path, day: date) -> Path:
    return Path(data_dir) / RECORD_DIR / f"{day.strftime('%Y-%m')}.jsonl"


def read_record(data_dir: Path) -> dict[str, dict]:
    """Every issue kept, by key, oldest first."""

    out = {}
    for path in sorted((Path(data_dir) / RECORD_DIR).glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                got = json.loads(line)
                out[got["key"]] = got
    return dict(sorted(out.items(), key=lambda kv: kv[1]["slot_utc"]))


def append(data_dir: Path, issue: dict) -> bool:
    """Add `issue` to the record unless its key is already there. Idempotent,
    so a push that loses a race re-runs it on the new tip (CLAUDE.md: a
    rejected append-only log re-appends; it never rebases)."""

    if issue["key"] in read_record(data_dir):
        return False
    path = record_path(data_dir, date.fromisoformat(issue["day"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(issue, separators=(",", ":"), ensure_ascii=False) + "\n")
    return True


def newest(data_dir: Path) -> dict | None:
    record = read_record(data_dir)
    return list(record.values())[-1] if record else None


# ------------------------------------------------------------------ overview

#: METAR's present-weather precipitation, by what the page calls it.
PRECIP_KINDS = (("TS", "thunder"), ("SH", "showers"), ("DZ", "drizzle"), ("RA", "rain"),
                ("SN", "snow"), ("GR", "hail"), ("GS", "hail"), ("UP", "precipitation"))


def parse_metar(raw: str) -> dict:
    """What the briefing reads from one KNZY report: temperature and
    dewpoint (°C, the RMK T group's tenths where it is there), the hour's
    precipitation (RMK P group, hundredths of an inch, routine reports only)
    and the kinds of precipitation in present weather."""

    out = {"air_c": None, "dew_c": None, "precip_in": None, "kinds": []}
    body, _, rmk = raw.partition(" RMK ")
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


def weather_story(data_dir: Path, start: datetime, end: datetime) -> dict:
    """KNZY's reports from `start` to `end`: rain, air temperature and
    humidity over the window, and the newest of each."""

    path = Path(data_dir) / "wind" / "KNZY.csv"
    rows = []
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                t = _utc(row["observed_utc"])
                if start < t <= end and row.get("raw"):
                    rows.append((t, parse_metar(row["raw"])))
    rows.sort(key=lambda r: r[0])
    temps = [(t, m["air_c"]) for t, m in rows if m["air_c"] is not None]
    rh = [(t, humidity(m["air_c"], m["dew_c"])) for t, m in rows
          if m["air_c"] is not None and m["dew_c"] is not None]
    wet = [t for t, m in rows if m["kinds"] or (m["precip_in"] or 0) > 0]
    kinds = []
    for _, m in rows:
        kinds += [k for k in m["kinds"] if k not in kinds]
    span = lambda xs: ({"min": round(min(v for _, v in xs), 1), "max": round(max(v for _, v in xs), 1),
                        "now": round(xs[-1][1], 1), "now_utc": _iso(xs[-1][0])} if xs else None)
    return {"station": "KNZY", "reports": len(rows), "from_utc": _iso(start), "to_utc": _iso(end),
            "air_c": span(temps), "humidity_pct": span(rh),
            "precip_in": round(sum(m["precip_in"] or 0 for _, m in rows), 2),
            "precip_kinds": kinds, "wet_reports": len(wet),
            "wet_from_utc": _iso(wet[0]) if wet else None, "wet_to_utc": _iso(wet[-1]) if wet else None}


def water_story(data_dir: Path, start: datetime, end: datetime, station: str = "46232") -> dict | None:
    """46232's water temperature (its standard met, WTMP) over the window,
    and the newest."""

    from collector.ndbc import is_missing

    path = Path(data_dir) / "observations" / f"{station}.csv"
    if not path.exists():
        return None
    got = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            token = row.get("wtmp") or ""
            t = _utc(row["timestamp_utc"])
            if token and not is_missing("WTMP", token) and start < t <= end:
                got.append((t, float(token)))
    if not got:
        return None
    got.sort()
    return {"station": station, "min_c": min(v for _, v in got), "max_c": max(v for _, v in got),
            "now_c": got[-1][1], "now_utc": _iso(got[-1][0])}


def overview_story(data_dir: Path, day: date, start: datetime, end: datetime) -> dict:
    from .geometry import load
    from .sunset import sea_times

    center = {s.id: s for s in load()[0]}["coronado_center"].position
    rise, sets = sea_times(day, center)
    rise, sets = (t.astimezone(timezone.utc) for t in (rise, sets))
    return {"sunrise_utc": _iso(_minute(rise + timedelta(seconds=30))),
            "sunset_utc": _iso(_minute(sets + timedelta(seconds=30))),
            "daylight_min": round((sets - rise).total_seconds() / 60.0),
            "weather": weather_story(data_dir, start, end),
            "water": water_story(data_dir, start, end)}


# ------------------------------------------------------------------ swell

def _heights(series: dict | None) -> dict[datetime, dict[str, float]]:
    out = {}
    for step in (series or {}).get("steps", []):
        if step.get("gap") or step.get("pending"):
            continue
        hs = {bid: b.get("hs_m") for bid, b in (step.get("breaks") or {}).items()}
        if all(hs.get(bid) is not None for bid in BREAKS):
            out[_utc(step["valid_utc"])] = hs
    return out


def _median(heights, hours, bid):
    vals = [heights[t][bid] for t in hours if t in heights]
    return statistics.median(vals) if len(vals) >= 2 else None


def _leader(meds: dict[str, float | None]) -> str | None:
    if any(v is None for v in meds.values()):
        return None
    order = sorted(BREAKS, key=lambda b: -meds[b])
    return order[0] if meds[order[0]] / meds[order[1]] - 1.0 >= LEAD_MARGIN else None


def change(now: dict, series: dict | None, then_hour: datetime | None) -> dict | None:
    """Each break's breaking height at `then_hour` and at the newest
    spectrum, filling / fading / little change on the measured 3-hour
    medians (`since_sunset` until 2026-10-17, the same measurement), and the
    leader then and now."""

    heights = _heights(series)
    newest = _utc(now.get("observed_utc"))
    if now.get("stale") or newest is None or newest not in heights:
        return None
    newest3 = [newest - timedelta(hours=h) for h in (0, 1, 2)]
    lead_now = _leader({bid: _median(heights, newest3, bid) for bid in BREAKS})
    rows = [{"id": bid, "then_m": None, "now_m": heights[newest][bid], "change": None} for bid in BREAKS]
    out = {"then_utc": None, "now_utc": _iso(newest), "span_h": None, "measured": False,
           "breaks": rows, "lead_then": None, "lead_now": lead_now}
    if then_hour is None or then_hour not in heights or then_hour >= newest:
        return out
    span_h = (newest - then_hour).total_seconds() / 3600.0
    measured = span_h >= MIN_SPAN_H
    around = [then_hour + timedelta(hours=h) for h in (-1, 0, 1)]
    for r in rows:
        bid = r["id"]
        r["then_m"] = heights[then_hour][bid]
        med_then, med_now = _median(heights, around, bid), _median(heights, newest3, bid)
        if measured and med_then and med_now:
            rel = med_now / med_then - 1.0
            if abs(rel) >= CHANGE_SHARE and rel * (r["now_m"] - r["then_m"]) > 0:
                r["change"] = "filling" if rel > 0 else "fading"
            else:
                r["change"] = "little"
    out.update(then_utc=_iso(then_hour), span_h=round(span_h, 1), measured=measured,
               lead_then=_leader({bid: _median(heights, around, bid) for bid in BREAKS}))
    return out


def buoy_trains(trains: list[dict] | None, limit: int = 3) -> list[dict]:
    keep = ("hs_m", "period_s", "from_deg", "wind_sea")
    return [{k: t.get(k) for k in keep} for t in (trains or [])[:limit]]


def trains_at(data_dir: Path, hour: datetime, spectra=None) -> list[dict] | None:
    """46232's trains at the buoy from the spectrum stamped `hour`, as
    now.json's are built (maximum entropy, `at_buoy`). None if there is no
    spectrum stamped then: a gap is a gap, never the hour beside it."""

    from .now import as_trains
    from .transform import at_buoy, load_spectra

    if spectra is None:
        try:
            spectra = load_spectra(Path(data_dir) / "spectra" / "46232")
        except (FileNotFoundError, ValueError):
            return None
    found = next((s for s in spectra if s.time == hour), None)
    if found is None:
        return None
    return buoy_trains(as_trains(at_buoy(found.with_spread("mem")).trains))


def then_hour(record: dict[str, dict], prior: tuple[date, str, datetime], series: dict | None) -> datetime | None:
    """"What was out there": the newest spectrum the previous issue read,
    from the record; with no previous issue kept, the newest hour the series
    has at or before its slot."""

    got = record.get(key(prior[0], prior[1]))
    if got and (got.get("swell") or {}).get("newest_utc"):
        return _utc(got["swell"]["newest_utc"])
    hours = [t for t in _heights(series) if t <= prior[2]]
    return max(hours) if hours else None


def _projected(arrival: dict, at: datetime) -> float | None:
    from .briefingreport import projected_period

    class _Fit:
        distance_km = arrival["distance_km"]
        generated_utc = _utc(arrival["generated_utc"])

    period = projected_period(_Fit, at)
    return round(period) if period and period > 0 else None


def _arrival_slots(a: dict) -> dict:
    keep = ("first_utc", "last_utc", "running", "hours_read", "lead_period_s", "latest_period_s",
            "distance_km", "generated_utc", "bearing_deg", "bearing_from", "bearing_lobes", "region")
    return {k: a.get(k) for k in keep}


def origin_story(now: dict, since: datetime, newest: datetime) -> dict:
    """Origin's arrivals at the breaks: those arriving now, with each
    ridge's period `PERIOD_AHEAD_H` on, and those that finished since the
    window opened."""

    block = now.get("origin") or {}
    arrivals = block.get("arrivals") or []
    current, ended = {}, {}
    for site, got in (block.get("sites") or {}).items():
        if site not in BREAKS:
            continue
        # Each break's `current` is {"arrival": index, "train_period_s": …}
        # (now.origin_reading); `last` is a bare index.
        here = [c["arrival"] for c in got.get("current") or []]
        for i in here:
            current.setdefault(i, []).append(site)
        last = got.get("last")
        if last is not None and last not in here:
            a = arrivals[last]
            if not a.get("running") and _utc(a["last_utc"]) >= since:
                ended.setdefault(last, []).append(site)
    ahead = newest + timedelta(hours=PERIOD_AHEAD_H)
    return {"arriving": [{**_arrival_slots(arrivals[i]), "breaks": sites, "ahead_utc": _iso(ahead),
                          "ahead_period_s": _projected(arrivals[i], ahead)}
                         for i, sites in sorted(current.items())],
            "finished": [{**_arrival_slots(arrivals[i]), "breaks": s} for i, s in sorted(ended.items())],
            "named": [h.get("name") for h in block.get("hurricanes") or [] if h.get("name")]}


def upstream_story(data_dir: Path, buoys: dict | None, since: datetime, at: datetime,
                   spectra=None) -> list[dict]:
    """46047's west and north-west sectors over the window: one entry per
    sector that rose, its bands earliest first (a dispersed swell's long
    periods lead), each band when it rose and when deep water puts it at
    46232 and the breaks (BRIEFING §43)."""

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
    recent = [s.with_spread("mem") for s in spectra
              if since - timedelta(hours=ul.RISE_WITHIN_H) <= s.time <= at]
    out = []
    for sector in ul.TIMED:
        heading = sum(ul.SECTORS[sector]) / 2.0
        bands = []
        for band in ul.BANDS_S:
            smoothed = ul.smooth_log(ul.series(recent, band, ul.SECTORS[sector]), ul.SMOOTH_ONSET_H)
            risen = [r for r in ul.rises(smoothed) if r.mid >= since]
            if not risen:
                continue
            rise = risen[0]
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
        if not bands:
            continue
        bands.sort(key=lambda b: b["since_utc"])
        latest = max(_utc(b["due_buoy_utc"]) + timedelta(minutes=max((l["hi_min"] for l in b["legs"]), default=0))
                     for b in bands)
        if at - latest > timedelta(hours=UPSTREAM_KEEP_H):
            continue
        out.append({"sector": sector, "sector_deg": list(ul.SECTORS[sector]), "bands": bands})
    return out


def _minute(t: datetime) -> datetime:
    return t.replace(second=0, microsecond=0)


def swell_story(now: dict, series: dict | None, buoys: dict | None, then: datetime | None,
                since: datetime, at: datetime, data_dir: Path) -> dict:
    newest = _utc(now.get("observed_utc"))
    if now.get("stale") or newest is None:
        return {"dark": True, "newest_utc": _iso(newest)}
    origin = origin_story(now, since, newest)
    return {"dark": False, "newest_utc": _iso(newest),
            "buoy_now": buoy_trains((now.get("buoy") or {}).get("trains")),
            "buoy_now_hs_m": (now.get("buoy") or {}).get("hs_m"),
            "then_utc": _iso(then),
            "buoy_then": trains_at(data_dir, then) if then else None,
            "breaks": change(now, series, then),
            "arriving": origin["arriving"], "finished": origin["finished"],
            "coming": upstream_story(data_dir, buoys, since, at)}


# ------------------------------------------------------------------ tide

def tide_story(now: dict, data_dir: Path, day: date, at: datetime) -> dict:
    """The coast's predicted turns around the issue — the one before it, the
    two after it and the rest of the Pacific day — each carrying the gauge's
    measured departure as the card's do; the departure; the day's range,
    the largest swing between consecutive turns of the day (the Daily range
    chart's); and the phase."""

    from .tidesite import anomaly, coast_turn
    from .tideturns import read_turns

    departure, pairs = anomaly(data_dir, at)
    turns = [coast_turn(t, departure).as_dict() for t in read_turns(data_dir, now.get("tide_station") or "9410170")]
    stamp = _iso(at)
    before = [t for t in turns if t["valid_utc"] <= stamp]
    after = [t for t in turns if t["valid_utc"] > stamp]
    start = datetime.combine(day, time(0), tzinfo=LOCAL_TZ).astimezone(timezone.utc)
    end = start + timedelta(days=1)
    in_day = [t for t in turns if start <= _utc(t["valid_utc"]) < end]
    keep = ([before[-1]] if before else []) + after[:2] + [t for t in in_day if t["valid_utc"] > stamp][2:]
    swing = None
    for a, b in zip(in_day, in_day[1:]):
        d = abs(b["height_m"] - a["height_m"])
        if swing is None or d > swing["m"]:
            swing = {"m": round(d, 3), "from_utc": a["valid_utc"], "to_utc": b["valid_utc"]}
    phase = ((now.get("tide_phase") or {}).get("days") or {}).get(day.isoformat())
    return {"turns": [dict(t, role="previous" if t["valid_utc"] <= stamp else "ahead") for t in keep],
            "departure_m": round(departure, 3) if departure is not None else None,
            "departure_hours": pairs, "range": swing,
            "phase": {"phase": phase.get("phase"), "next": phase.get("next")} if phase else None}


# ------------------------------------------------------------------ wind

def _sense(offshore: float | None, kt: float) -> str:
    """The page's `sense()` as the charts count it: 0 kt calm, ≤ LIGHT_KT
    light (a side the card still names, the charts do not), no direction
    variable."""

    if kt == 0:
        return "calm"
    if kt <= 3:
        return "light"
    if offshore is None:
        return "variable"
    return "offshore" if offshore > 0.3 else "onshore" if offshore < -0.3 else "cross-shore"


def _knzy(data_dir: Path) -> list[tuple[datetime, float, float | None]]:
    path = Path(data_dir) / "wind" / "KNZY.csv"
    out = []
    if not path.exists():
        return out
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if not row.get("wind_kt"):
                continue
            d = row.get("wind_from_deg") if row.get("variable") != "true" else ""
            out.append((_utc(row["observed_utc"]), float(row["wind_kt"]), float(d) if d else None))
    out.sort(key=lambda r: r[0])
    return out


def wind_story(now: dict, data_dir: Path, at: datetime) -> dict:
    """KNZY's newest report at the issue, and the same clock hour on every
    earlier day in the archive: how many days each break read offshore,
    cross-shore, onshore, or light / calm / variable, and the median speed.
    A count of what was, never a habit said as a forecast."""

    from .live import offshore_component

    normals = {b["id"]: b.get("shore_normal_deg") for b in now.get("breaks", [])}
    rows = _knzy(data_dir)
    latest = next((r for r in reversed(rows) if r[0] <= at), None)
    if latest is None or at - latest[0] > timedelta(minutes=WIND_FRESH_MIN):
        return {"now": None, "history": None}
    when, kt, deg = latest
    verdict = lambda d, k, bid: _sense(None if d is None or normals.get(bid) is None
                                       else offshore_component(d, normals[bid]), k)
    local = when.astimezone(LOCAL_TZ)
    counts = {bid: {} for bid in BREAKS}
    speeds, days = [], 0
    stamps = [r[0] for r in rows]
    day = local.date() - timedelta(days=1)
    first = rows[0][0].astimezone(LOCAL_TZ).date()
    while day >= first:
        mark = datetime.combine(day, local.time(), tzinfo=LOCAL_TZ).astimezone(timezone.utc)
        # Bisected: a scan per day grows with the archive squared (CLAUDE.md).
        i = bisect.bisect_right(stamps, mark) - 1
        if i >= 0 and rows[i][0] > mark - timedelta(minutes=WIND_SLOT_MIN):
            _, k, d = rows[i]
            days += 1
            speeds.append(k)
            for bid in BREAKS:
                v = verdict(d, k, bid)
                counts[bid][v] = counts[bid].get(v, 0) + 1
        day -= timedelta(days=1)
    return {"now": {"observed_utc": _iso(when), "speed_kt": kt, "from_deg": deg,
                    "offshore": {bid: None if deg is None or normals.get(bid) is None
                                 else round(offshore_component(deg, normals[bid]), 3) for bid in BREAKS},
                    "by_break": {bid: verdict(deg, kt, bid) for bid in BREAKS}},
            "history": {"days": days, "by_break": counts,
                        "median_kt": statistics.median(speeds) if speeds else None,
                        "from_day": first.isoformat()}}


# ------------------------------------------------------------------ watching

def storms_story(at: datetime, data_dir: Path) -> list[dict]:
    from .siting import load_coordinates
    from .stormdue import live

    home = load_coordinates().get("46232")
    if home is None:
        return []
    out = []
    for d in live(at, data_dir=data_dir, home=home, breaks=list(BREAKS)):
        rows = []
        for bid, edge in d.breaks.items():
            first, last = edge.get("first"), edge.get("last")
            rows.append({"id": bid, "keeps": edge.get("keeps"),
                         "first_utc": _iso(first.utc) if first else None,
                         "first_source": first.source if first else None,
                         "first_period_s": first.period_s if first else None,
                         "last_utc": _iso(last.utc) if last else None,
                         "last_source": last.source if last else None,
                         "last_period_s": last.period_s if last else None})
        out.append({"storm": d.storm, "name": d.name, "strength": d.strength,
                    "newest_fix_utc": _iso(d.newest_fix_utc),
                    "bearing_deg": round(d.bearing_deg) if d.bearing_deg is not None else None,
                    "distance_km": d.distance_km, "open_fixes": d.open_fixes,
                    "blocked_fixes": d.blocked_fixes,
                    "forecast_issued_utc": _iso(d.forecast_issued_utc), "breaks": rows})
    return out


# ------------------------------------------------------------------ build

def build(*, data_dir: Path = DEFAULT_DATA_DIR, at: datetime | None = None,
          live_dir: Path | None = None, issue: tuple[date, str, datetime] | None = None,
          record: dict[str, dict] | None = None) -> dict:
    """One issue, from the payloads this collection just wrote into
    `live_dir` (``data/live``) and the archives under `data_dir`, nothing
    after `at`. `issue` is the slot (`due`); by default the newest."""

    live = Path(live_dir) if live_dir else Path(data_dir) / "live"
    at = at or utcnow()
    day, edition, slot_t = issue or latest_slot(at)
    head = {"key": key(day, edition), "edition": edition, "day": day.isoformat(),
            "slot_utc": _iso(slot_t), "issued_utc": _iso(_minute(at))}
    now = _read(live / "now.json")
    if not now:
        return {**head, "available": False, "why": "no observed reading was built this collection"}
    record = read_record(data_dir) if record is None else record
    prior = previous_slot(day, edition)
    # Morning covers the night since sunset, Midday the morning since its slot.
    since = last_sunset(at) if edition == "morning" else slot(day, "morning")
    series, buoys = _read(live / "series.json"), _read(live / "buoys.json")
    origin = now.get("origin") or {}
    return {
        **head, "available": True, "window_from_utc": _iso(since),
        "prior": {"key": key(prior[0], prior[1]), "edition": prior[1], "slot_utc": _iso(prior[2])},
        "station": now.get("station"), "station_cdip": now.get("station_cdip"),
        "station_names": origin.get("station_names") or {},
        "station_cdips": origin.get("station_cdips") or {},
        "overview": overview_story(Path(data_dir), day, since, at),
        "swell": swell_story(now, series, buoys, then_hour(record, prior, series), since, at, Path(data_dir)),
        "tide": tide_story(now, Path(data_dir), day, at),
        "wind": wind_story(now, Path(data_dir), at),
        "watching": {"storms": storms_story(at, Path(data_dir)),
                     "named": (origin_story(now, since, at)["named"])},
        "thresholds": {"change_share": CHANGE_SHARE, "lead_margin": LEAD_MARGIN,
                       "min_span_h": MIN_SPAN_H, "period_ahead_h": PERIOD_AHEAD_H},
    }


def with_text(issue: dict) -> dict:
    """The issue with the words the page prints from it, for the record.
    Without Node the record keeps the payload alone, and says so."""

    from .briefingwording import render_issue

    try:
        return {**issue, "text": render_issue(issue)}
    except Exception as exc:  # noqa: BLE001 -- the payload is the record; the words are a convenience
        print(f"briefing: words not rendered ({type(exc).__name__}: {exc})", file=sys.stderr)
        return {**issue, "text": None}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--live-dir", type=Path, default=None,
                        help="where now.json and the other payloads are (default DATA_DIR/live)")
    parser.add_argument("--out", type=Path, default=None, help="the page's file (default LIVE_DIR/briefing.json)")
    parser.add_argument("--issue-out", type=Path, default=None,
                        help="where a due issue is written for --record (default LIVE_DIR/briefing_issue.json)")
    parser.add_argument("--record", type=Path, default=None, metavar="ISSUE",
                        help="append this issue file to DATA_DIR's record, then write --out from it")
    parser.add_argument("--at", default=None, help="build as of this UTC stamp (testing)")
    args = parser.parse_args(argv)
    live = args.live_dir or Path(args.data_dir) / "live"
    out = args.out or live / "briefing.json"
    out.parent.mkdir(parents=True, exist_ok=True)

    if args.record is not None:
        if args.record.exists():
            issue = json.loads(args.record.read_text(encoding="utf-8"))
            print(f"{'Recorded' if append(args.data_dir, issue) else 'Already recorded'}: {issue['key']}")
        else:
            print("No issue this collection.")
    else:
        at = _utc(args.at) if args.at else utcnow()
        record = read_record(args.data_dir)
        slot_due = due(at, record)
        issue_out = args.issue_out or live / "briefing_issue.json"
        if slot_due is None:
            issue_out.unlink(missing_ok=True)
            print("No issue due.")
        else:
            issue = build(data_dir=args.data_dir, at=at, live_dir=live, issue=slot_due, record=record)
            if issue.get("available"):
                issue_out.write_text(json.dumps(with_text(issue), indent=1, ensure_ascii=False), encoding="utf-8")
                print(f"Issued {issue['key']} → {issue_out}")
            else:
                issue_out.unlink(missing_ok=True)
                print(f"Not issued: {issue['why']}")

    latest = newest(args.data_dir)
    payload = latest or {"available": False, "why": "no briefing has been issued yet"}
    out.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
