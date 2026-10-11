"""Where the tide is in its cycles: the Tide card's phase line and its summary.

Pure Python, on the forecast path. Reads NOAA's harmonic constants for
9410170 (`collector.harcon` → data/tide/9410170_harcon.json, fetched, never
typed), the Moon from `forecast.moon`, and the card's own turns.

Three cycles shape the tide here (BRIEFING §41):

- **Spring and neap**, 14.8 d: M2 and S2 (with N2, K2 and the small
  twice-daily terms) in and out of step. Read off the constants, so it
  carries the station's own lag: springs ~3 h before new or full moon.
- **The Moon's declination**, 13.7 d: K1 and O1. Far north or south, one tide
  of the day is much bigger than the other; over the equator they even out.
  The tide answers ~14 h late here (the diurnal age, from K1-O1).
- **Perigee and apogee**, 27.6 d: N2 against M2, about ±16% on M2.

The station's form factor, (K1+O1)/(M2+S2), is 0.72: mixed, mainly twice a
day.

What it never does: compute a turn or a height for the card. The card's turns
are CO-OPS's own (`interval=hilo`, BRIEFING §19) and there is no fallback
between the two. The constants are read here for the CYCLES -- which day is a
spring, how big one will be against this week -- and the reconstruction
below exists to measure the thresholds (`--measure`) and to check the
constants against CO-OPS's hourly predictions (1.2 cm RMS, a test pins it).

Nothing here says anything about waves: on the 2016 profile the whole tide
range moves the break point 34-53 m and the breaking height under 2%
(BRIEFING §32).
"""

from __future__ import annotations

import argparse
import cmath
import json
import math
import re
import statistics
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from . import moon

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
STATION = "9410170"
LOCAL_TZ = ZoneInfo("America/Los_Angeles")
ISO = "%Y-%m-%dT%H:%M:%SZ"

# ------------------------------------------------------------------ thresholds
# Every one measured by `python -m forecast.tidephasereport` over 19 years of
# the station's own tide (2017-2035, a whole nodal cycle), reconstructed from
# the constants; BRIEFING §41 has the sweeps, and `tests/test_tidephase.py`
# re-runs them. One rule throughout (owner's request to measure them,
# 2026-10-11): a slot is said only where it is right on at least
# `RIGHT_SHARE` of the occasions it fires. The phase label alone always says
# something, so it takes the window that agrees best instead.
RIGHT_SHARE = 0.85

#: A day is "spring tides" or "neap tides" within this many hours of the
#: twice-daily envelope's peak or trough; between, building or easing.
#: Against the top and bottom third of the 15 days around each day by its
#: biggest swing, 72 h agrees on 69.5% of days, the best of 24-108 h (60 h
#: 69.3%, 84 h 67.5%). No window reaches RIGHT_SHARE on both labels.
PHASE_WINDOW_H = 72

#: The Moon "near the equator" and "far north / far south", in degrees of
#: declination as the tide feels it (`diurnal_age_h` earlier). Near: 88.1%
#: of those days have the day's two tides in the bottom quartile of their
#: difference (5° gives 84.8%). Far: 86.1% in the top quartile (24° gives
#: 80.9%); only near a major lunar standstill, as in 2024-2027.
DEC_EQUATOR_DEG = 4.0
DEC_FAR_DEG = 26.0

#: The new or full moon (quarter moon) a spring (neap) is named with is
#: looked for this far from it: the farthest apart they fell in 19 years was
#: 64 h (38 h for a quarter), so the slot is always filled.
MOON_WINDOW_H = 66

#: A perigee or apogee is "near" a spring or neap within this many hours:
#: springs near perigee are bigger than the median spring 85.7% of the time,
#: and the other three pairings 94-100% (96 h: 84.2%).
DISTANCE_WINDOW_H = 72

#: Two consecutive turns this close are "a high and low only … apart":
#: 89.9% of them fall within EVIDENCE_DAYS of a neap (0.25 m: 84.7%).
SMALL_SWING_M = 0.20

#: "Larger" or "smaller extremes than this week" only past this share of the
#: combined envelope, which is then right on 86.1% (with no margin, 80.6%);
#: inside it, "similar".
SIMILAR_SHARE = 0.10

#: Evidence from the turns is looked for this far either side of a date.
EVIDENCE_DAYS = 2

# ------------------------------------------------------------------ constants

SEMI = ("M2", "S2", "N2", "K2", "NU2", "MU2", "2N2", "L2", "T2", "LAM2", "R2")
DIU = ("K1", "O1", "P1", "Q1", "J1", "OO1", "RHO", "2Q1", "S1")


@dataclass(frozen=True)
class Constituent:
    name: str
    amplitude_m: float
    phase_gmt: float
    speed: float  # degrees per hour


@dataclass(frozen=True)
class Constants:
    station: str
    constituents: dict
    analysis: str | None  # "2017–2021", from NOAA's own comment
    fetched_utc: str | None


def harcon_path(data_dir: Path = DEFAULT_DATA_DIR, station: str = STATION) -> Path:
    return Path(data_dir) / "tide" / f"{station}_harcon.json"


def load(data_dir: Path = DEFAULT_DATA_DIR, station: str = STATION) -> Constants | None:
    """The stored constants, or None when there are none: the phase line is
    then absent, never computed from a guess."""

    try:
        stored = json.loads(harcon_path(data_dir, station).read_text())
    except (OSError, json.JSONDecodeError):
        return None
    body = stored.get("response") or {}
    scale = 0.3048 if "f" in str(body.get("units", "")).lower() else 1.0
    out = {}
    for row in body.get("HarmonicConstituents") or []:
        try:
            out[row["name"]] = Constituent(row["name"], float(row["amplitude"]) * scale,
                                           float(row["phase_GMT"]), float(row["speed"]))
        except (KeyError, TypeError, ValueError):
            continue
    if not all(n in out for n in ("M2", "S2", "K1", "O1")):
        return None
    analysis = None
    for row in body.get("HarmonicConstituents") or []:
        m = re.search(r"\((\d{4})\s*-\s*(\d{4})\)", str(row.get("comments", "")))
        if row.get("name") == "M2" and m:
            analysis = f"{m.group(1)}–{m.group(2)}"
    return Constants(station, out, analysis, stored.get("fetched_utc"))


# ------------------------------------------------------------------ astronomy
# Schureman's equilibrium arguments and nodal factors, as CO-OPS predicts.

def _args(when: datetime) -> dict:
    t = (when - moon.J2000) / timedelta(days=36525)
    ut = (when.hour + when.minute / 60 + when.second / 3600)
    return {"T": 180.0 + 15.0 * ut,
            "s": 218.3165 + 481267.8813 * t, "h": 280.4661 + 36000.7698 * t,
            "p": 83.3535 + 4069.0137 * t, "N": 125.0445 - 1934.1363 * t,
            "p1": 282.9384 + 1.7195 * t}


def _nodal(n_deg: float) -> dict:
    n = math.radians(n_deg)
    c, s = math.cos, math.sin
    return {
        "M2": (1.0004 - 0.0373 * c(n) + 0.0002 * c(2 * n), -2.14 * s(n)),
        "K1": (1.0060 + 0.1150 * c(n) - 0.0088 * c(2 * n) + 0.0006 * c(3 * n),
               -8.86 * s(n) + 0.68 * s(2 * n) - 0.07 * s(3 * n)),
        "O1": (1.0089 + 0.1871 * c(n) - 0.0147 * c(2 * n) + 0.0014 * c(3 * n),
               10.80 * s(n) - 1.34 * s(2 * n) + 0.19 * s(3 * n)),
        "K2": (1.0241 + 0.2863 * c(n) + 0.0083 * c(2 * n) - 0.0015 * c(3 * n),
               -17.74 * s(n) + 0.68 * s(2 * n) - 0.04 * s(3 * n)),
        "J1": (1.1029 + 0.1676 * c(n) - 0.0170 * c(2 * n) + 0.0016 * c(3 * n),
               -12.94 * s(n) + 1.34 * s(2 * n) - 0.19 * s(3 * n)),
        "OO1": (1.1027 + 0.6504 * c(n) + 0.0317 * c(2 * n) - 0.0014 * c(3 * n),
                -36.68 * s(n) + 4.02 * s(2 * n) - 0.57 * s(3 * n)),
    }


def _vfu(a: dict, nodal: dict) -> dict:
    """V (degrees), f and u for every constituent this module models."""

    T, s, h, p, p1 = a["T"], a["s"], a["h"], a["p"], a["p1"]
    one = (1.0, 0.0)
    fm, um = nodal["M2"]
    fk, uk = nodal["K1"]
    m2 = 2 * T - 2 * s + 2 * h
    rows = {
        "M2": (m2, nodal["M2"]), "S2": (2 * T, one),
        "N2": (2 * T - 3 * s + 2 * h + p, nodal["M2"]), "K2": (2 * T + 2 * h, nodal["K2"]),
        "K1": (T + h - 90, nodal["K1"]), "O1": (T - 2 * s + h + 90, nodal["O1"]),
        "P1": (T - h + 90, one), "Q1": (T - 3 * s + h + p + 90, nodal["O1"]),
        "NU2": (2 * T - 3 * s + 4 * h - p, nodal["M2"]), "MU2": (2 * T - 4 * s + 4 * h, nodal["M2"]),
        "2N2": (2 * T - 4 * s + 2 * h + 2 * p, nodal["M2"]),
        "LAM2": (2 * T - s + p + 180, nodal["M2"]), "L2": (2 * T - s + 2 * h - p + 180, nodal["M2"]),
        "T2": (2 * T - h + p1, one), "R2": (2 * T + h - p1 + 180, one),
        "J1": (T + s + h - p - 90, nodal["J1"]), "OO1": (T + 2 * s + h - 90, nodal["OO1"]),
        "2Q1": (T - 4 * s + h + 2 * p + 90, nodal["O1"]), "RHO": (T - 3 * s + 3 * h - p + 90, nodal["O1"]),
        "S1": (T, one), "SA": (h, one), "SSA": (2 * h, one),
        "M4": (2 * m2, (fm * fm, 2 * um)), "MS4": (m2 + 2 * T, nodal["M2"]),
        "MN4": (2 * m2 - s + p, (fm * fm, 2 * um)), "M6": (3 * m2, (fm ** 3, 3 * um)),
        "S4": (4 * T, one), "S6": (6 * T, one), "2SM2": (4 * T - m2, (fm, -um)),
        "MK3": (m2 + T + h - 90, (fm * fk, um + uk)),
        "2MK3": (2 * m2 - (T + h - 90), (fm * fm * fk, 2 * um - uk)),
    }
    return {k: (v, f, u) for k, (v, (f, u)) in rows.items()}


def _terms(c: Constants, when: datetime, names) -> list[complex]:
    a = _args(when)
    table = _vfu(a, _nodal(a["N"]))
    out = []
    for n in names:
        k = c.constituents.get(n)
        if k is None or n not in table:
            continue
        v, f, u = table[n]
        out.append(f * k.amplitude_m * cmath.exp(1j * math.radians(v + u - k.phase_gmt)))
    return out


def height(c: Constants, when: datetime) -> float:
    """The station's tide about its mean, metres. For measurement and the
    check against CO-OPS only; the card never shows it."""

    return sum(t.real for t in _terms(c, when, c.constituents))


def envelope(c: Constants, when: datetime, names=SEMI) -> float:
    """Amplitude of a species' combined tide (the twice-daily or once-daily
    group): the slowly varying size the spring-neap and declination cycles
    are made of."""

    return abs(sum(_terms(c, when, names)))


def species(c: Constants, when: datetime) -> tuple[float, float, float]:
    """The height, the twice-daily envelope and the once-daily envelope,
    from one evaluation of the arguments."""

    a = _args(when)
    table = _vfu(a, _nodal(a["N"]))
    total = 0.0
    semi = diu = 0j
    for n, k in c.constituents.items():
        if n not in table:
            continue
        v, f, u = table[n]
        z = f * k.amplitude_m * cmath.exp(1j * math.radians(v + u - k.phase_gmt))
        total += z.real
        if n in SEMI:
            semi += z
        elif n in DIU:
            diu += z
    return total, abs(semi), abs(diu)


def form_factor(c: Constants) -> float:
    k = c.constituents
    return (k["K1"].amplitude_m + k["O1"].amplitude_m) / (k["M2"].amplitude_m + k["S2"].amplitude_m)


def _age(c: Constants, a: str, b: str) -> float:
    ka, kb = c.constituents[a], c.constituents[b]
    d = (ka.phase_gmt - kb.phase_gmt + 180.0) % 360.0 - 180.0
    return d / (ka.speed - kb.speed)


def phase_age_h(c: Constants) -> float:
    """Hours from new or full moon to spring tide (negative: springs first)."""
    return _age(c, "S2", "M2")


def diurnal_age_h(c: Constants) -> float:
    """Hours from the Moon's greatest declination to the biggest inequality."""
    return _age(c, "K1", "O1")


def parallax_age_h(c: Constants) -> float:
    """Hours from perigee to its largest effect on the tide."""
    return _age(c, "M2", "N2")


# ------------------------------------------------------------------ cycles

def extremes(c: Constants, start: datetime, end: datetime) -> list[tuple[str, datetime, float]]:
    """Spring and neap: the twice-daily envelope's peaks and troughs, to the
    hour, with the combined (twice-daily plus once-daily) envelope there --
    the size a reader sees."""

    step = timedelta(hours=1)
    times, values, once = [], [], []
    t = start
    while t <= end:
        _, semi, diu = species(c, t)
        times.append(t)
        values.append(semi)
        once.append(diu)
        t += step
    out = []
    for i in range(1, len(values) - 1):
        a, b, d = values[i - 1], values[i], values[i + 1]
        if b > a and b >= d:
            out.append(("spring", times[i], b + once[i]))
        elif b < a and b <= d:
            out.append(("neap", times[i], b + once[i]))
    return out


def felt_declination(c: Constants, when: datetime) -> float:
    """The Moon's declination as the tide feels it: `diurnal_age_h` earlier."""
    return moon.declination(when - timedelta(hours=diurnal_age_h(c)))


def declination_state(c: Constants, when: datetime) -> dict:
    """near the equator, far north or south, or between and heading which way."""

    d = felt_declination(c, when)
    later = felt_declination(c, when + timedelta(hours=6))
    side = "north" if d >= 0 else "south"
    if abs(d) <= DEC_EQUATOR_DEG:
        return {"state": "equator", "side": side, "deg": round(d, 1)}
    if abs(d) >= DEC_FAR_DEG:
        return {"state": "far", "side": side, "deg": round(d, 1)}
    return {"state": "away" if abs(later) > abs(d) else "toward", "side": side, "deg": round(d, 1)}


def _nearest(events, when: datetime, names, hours: float):
    best = None
    for name, t in events:
        if name in names and abs((t - when) / timedelta(hours=1)) <= hours:
            if best is None or abs(t - when) < abs(best[1] - when):
                best = (name, t)
    return best


# ------------------------------------------------------------------ the turns

def _parse(iso: str) -> datetime:
    return datetime.strptime(iso, ISO).replace(tzinfo=timezone.utc)


def _local_day(when: datetime) -> date:
    return when.astimezone(LOCAL_TZ).date()


def _turns(turns) -> list[tuple[datetime, float, str]]:
    """The card's turns, as (time, height, event), sorted. Accepts the
    payloads' dicts (`valid_utc`, `height_m`, `event`)."""

    out = []
    for t in turns or []:
        when = t.get("valid_utc") if isinstance(t, dict) else t.valid_utc
        h = t.get("height_m") if isinstance(t, dict) else t.height_m
        ev = t.get("event") if isinstance(t, dict) else t.event
        if when and h is not None and ev in ("high", "low"):
            out.append((_parse(when), float(h), ev))
    out.sort()
    return out


def _complete_days(turns) -> set[date]:
    """Local days the turns cover from end to end: a turn before the day and
    a turn after it, so a count of the day's turns is a fact about the day."""

    if len(turns) < 2:
        return set()
    first, last = _local_day(turns[0][0]), _local_day(turns[-1][0])
    days, d = set(), first + timedelta(days=1)
    while d < last:
        days.add(d)
        d += timedelta(days=1)
    return days


def neap_evidence(turns, around: datetime) -> list[dict]:
    """Small swings and days of a single high and low, within EVIDENCE_DAYS."""

    lo = _local_day(around) - timedelta(days=EVIDENCE_DAYS)
    hi = _local_day(around) + timedelta(days=EVIDENCE_DAYS)
    complete = _complete_days(turns)
    out: list[dict] = []
    singles = []
    d = lo
    while d <= hi:
        if d in complete:
            day = [t for t in turns if _local_day(t[0]) == d]
            if len(day) == 2 and {t[2] for t in day} == {"high", "low"}:
                singles.append(d)
        small = [abs(a[1] - b[1]) for a, b in zip(turns, turns[1:])
                 if _local_day(a[0]) == d and a[2] != b[2] and abs(a[1] - b[1]) < SMALL_SWING_M]
        if small:
            out.append({"kind": "small", "day": d.isoformat(), "apart_m": round(min(small), 3)})
        d += timedelta(days=1)
    # Consecutive single days read as one run: "16-17 Oct".
    runs: list[list[date]] = []
    for d in singles:
        if runs and (d - runs[-1][-1]).days == 1:
            runs[-1].append(d)
        else:
            runs.append([d])
    for r in runs:
        out.append({"kind": "single", "day": r[0].isoformat(), "last_day": r[-1].isoformat()})
    out.sort(key=lambda e: e["day"])
    return out


def spring_evidence(turns, around: datetime) -> list[dict]:
    """The largest consecutive swing within EVIDENCE_DAYS."""

    best = None
    for a, b in zip(turns, turns[1:]):
        if a[2] == b[2] or abs(a[0] - around) > timedelta(days=EVIDENCE_DAYS):
            continue
        swing = abs(a[1] - b[1])
        if best is None or swing > best["swing_m"]:
            best = {"kind": "biggest", "day": _local_day(a[0]).isoformat(),
                    "swing_m": round(swing, 3), "from": a[2]}
    return [best] if best else []


def day_pair(turns, day: date) -> dict | None:
    """The day's two highs or two lows, whichever pair differs more: the
    Moon's declination shows here far more in the lows than in the highs
    (r = 0.82 against 0.66 over 19 years, BRIEFING §41), so "the two highs"
    alone would hide it. Only on a day the turns cover whole."""

    if day not in _complete_days(turns):
        return None
    pairs = []
    for ev in ("high", "low"):
        hs = [round(h, 3) for t, h, e in turns if e == ev and _local_day(t) == day]
        if len(hs) == 2:
            pairs.append({"event": ev, "heights_m": hs})
    if not pairs:
        return None
    return max(pairs, key=lambda p: abs(p["heights_m"][0] - p["heights_m"][1]))


# ------------------------------------------------------------------ the summary

def _iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime(ISO)


def _event(e) -> dict | None:
    return {"name": e[0], "utc": _iso(e[1])} if e else None


def summary(c: Constants, day: date, turns, *, now: datetime | None = None,
            events=None, cycles=None) -> dict:
    """The phase line and the summary for one local day, as slots.

    `now` is the moment "today" is read at (noon on `day` when not given).
    The page renders the words (`app/forecast.html`, `tidePhaseText`); this
    decides every slot's value."""

    noon = datetime(day.year, day.month, day.day, 12, tzinfo=LOCAL_TZ).astimezone(timezone.utc)
    at = now or noon
    if events is None:
        events = moon.events(at - timedelta(days=10), at + timedelta(days=40))
    if cycles is None:
        cycles = extremes(c, at - timedelta(days=10), at + timedelta(days=40))
    turns = _turns(turns)
    window = timedelta(hours=PHASE_WINDOW_H)

    current = min((e for e in cycles if abs(e[1] - at) <= window),
                  key=lambda e: abs(e[1] - at), default=None)
    upcoming = next((e for e in cycles if e[1] > at), None)
    if current:
        phase = current[0]
    elif upcoming:
        phase = "building" if upcoming[0] == "spring" else "easing"
    else:
        return {}

    today: dict = {"declination": declination_state(c, at)}
    if current:
        names = ("new moon", "full moon") if phase == "spring" else ("first quarter", "last quarter")
        today["moon"] = _event(_nearest(events, current[1], names, MOON_WINDOW_H))
    pair = day_pair(turns, day)
    if pair:
        today["pair"] = pair

    later = [e for e in cycles if e[1] > at + window]
    out = {"day": day.isoformat(), "phase": phase, "today": today}

    if later:
        kind, t, _ = later[0]
        d = declination_state(c, t)
        coincide = []
        dist = _nearest(events, t, ("perigee", "apogee"), DISTANCE_WINDOW_H)
        if dist:
            coincide.append(dist[0])
        if d["state"] == "far":
            coincide.append("maximum declination")
        elif d["state"] == "equator":
            coincide.append("the Moon over the equator")
        out["next"] = {"kind": kind, "utc": _iso(t), "declination": d["state"],
                       "coincide": coincide,
                       "evidence": (neap_evidence if kind == "neap" else spring_evidence)(turns, t)}

    if len(later) > 1:
        kind, t, size = later[1]
        names = ("new moon", "full moon") if kind == "spring" else ("first quarter", "last quarter")
        now_size = envelope(c, at, SEMI) + envelope(c, at, DIU)
        share = size / now_size - 1 if now_size else 0.0
        grows = abs(felt_declination(c, t + timedelta(hours=6))) > abs(felt_declination(c, t))
        out["after"] = {
            "kind": kind, "utc": _iso(t),
            "moon": _event(_nearest(events, t, names, MOON_WINDOW_H)),
            "distance": _event(_nearest(events, t, ("perigee", "apogee"), DISTANCE_WINDOW_H)),
            "declination": "growing" if grows else "falling",
            "compare": "larger" if share > SIMILAR_SHARE else "smaller" if share < -SIMILAR_SHARE else "similar",
        }
    return out


def block(data_dir: Path, days, turns, *, now: datetime | None = None) -> dict | None:
    """What a payload carries: one summary per local day, keyed by date, or
    None when the constants are not stored."""

    c = load(data_dir)
    if c is None or not days:
        return None
    days = sorted(days)
    first = datetime(days[0].year, days[0].month, days[0].day, tzinfo=LOCAL_TZ).astimezone(timezone.utc)
    last = datetime(days[-1].year, days[-1].month, days[-1].day, tzinfo=LOCAL_TZ).astimezone(timezone.utc)
    events = moon.events(first - timedelta(days=10), last + timedelta(days=41))
    cycles = extremes(c, first - timedelta(days=10), last + timedelta(days=41))
    today = _local_day(now) if now else None
    out = {}
    for d in days:
        s = summary(c, d, turns, now=now if d == today else None, events=events, cycles=cycles)
        if s:
            out[d.isoformat()] = s
    return {"station": c.station, "analysis": c.analysis, "fetched_utc": c.fetched_utc,
            "diurnal_age_h": round(diurnal_age_h(c), 1), "days": out} if out else None
