"""The LIVE tab's Briefing: the swell, the conditions and the day's tides.

    python -m forecast.briefing                  # build; data/live/briefing.json
    python -m forecast.briefing --record BUILT   # keep it if it changed (the workflow's)

Owner's request, 2026-10-16, reshaped 2026-10-17 and again 2026-10-22: a
short read in a fold above the LIVE cards. Built every collection; it
UPDATES only when what it says about the swell or the tide changes:

- **Swell**, two sentences (owner's wording, 2026-10-23). "3–4 ft
  (0.9–1.2 m) from the SSW at 13.3 s": the breaking height at the three
  breaks, lowest to highest in whole feet, then the offshore heading and
  the period of the biggest train at the break with the biggest waves (the
  cards' own numbers; the heading the train row's, not its 5 m one). Then
  46047's west or north-west rise, due at 46232 and the breaks by
  deep-water speed (`forecast.upstreamlag`, BRIEFING §43): "West swell
  (250–280°) offshore, 10–12 s first; due at Point Loma South around
  1:33 PM, and at the breaks 39–53 min later."
- **Conditions**, refreshed every collection without counting as an
  update: 46232's water temperature (`WATER_FRESH_H`), KNZY's air
  temperature and humidity,
  and precipitation — the last hour's and the rolling 24 hours', both shown
  when either is above zero, neither when not.
- **Tides**: the day's predicted turns, AM / PM, with the gauge's measured
  departure as the card's turns carry it.

An update is a change in the words the page prints for the swell or the
tides (`briefingwording.render_issue`, Node, the page's own code), so a
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

#: 46047's rises are read this far back; each is kept until this long after
#: its swell was due at the last break (`upstream_story`).
UPSTREAM_LOOKBACK_H = 24.0
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
    """KNZY's newest report: air temperature and humidity; and the
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
            "precip_kinds": hour_kinds}


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


# ------------------------------------------------------------------ swell

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




def lead_heading(site: dict) -> float | None:
    """Where the break's lead train comes from offshore, as its row on the
    card says it: one direction, its mean; two, the larger (lobes come
    largest first), as the row's shortest form names it. Never the 5 m
    heading (owner's call, 2026-10-23)."""

    trains = site.get("trains") or []
    if not trains:
        return site.get("peak_direction_deg")
    lobes = trains[0].get("lobes") or []
    return lobes[0][0] if len(lobes) >= 2 else trains[0].get("from_deg")


def swell_story(now: dict, buoys: dict | None, at: datetime, data_dir: Path) -> dict:
    """The breaking height and lead train's period and heading at each break,
    as the cards show them, and 46047's rises."""

    newest = _utc(now.get("observed_utc"))
    if now.get("stale") or newest is None:
        return {"dark": True, "newest_utc": _iso(newest)}
    breaks = [{"id": b["id"], "hs_m": b.get("hs_nearshore_m"), "period_s": b.get("peak_period_s"),
               "from_deg": lead_heading(b)}
              for b in now.get("breaks", []) if b.get("id") in BREAKS]
    coming = upstream_story(data_dir, buoys, at - timedelta(hours=UPSTREAM_LOOKBACK_H), at)
    return {"dark": False, "newest_utc": _iso(newest),
            "breaks": [b for b in breaks if b["hs_m"] is not None],
            "coming": [{"sector": c["sector"], "sector_deg": c["sector_deg"], **c["bands"][0]} for c in coming]}


# ------------------------------------------------------------------ tide

def tide_story(now: dict, data_dir: Path, at: datetime) -> dict:
    """The Pacific day's predicted turns at the open coast, each carrying
    the gauge's measured departure as the card's do."""

    from .tidesite import anomaly, coast_turn
    from .tideturns import read_turns

    departure, _ = anomaly(data_dir, at)
    day = at.astimezone(LOCAL_TZ).date()
    start = datetime.combine(day, time(0), tzinfo=LOCAL_TZ).astimezone(timezone.utc)
    end = start + timedelta(days=1)
    turns = [coast_turn(t, departure).as_dict()
             for t in read_turns(data_dir, now.get("tide_station") or "9410170")]
    return {"day": day.isoformat(), "departure_m": round(departure, 3) if departure is not None else None,
            "turns": [{k: t[k] for k in ("valid_utc", "height_m", "event")} for t in turns
                      if start <= _utc(t["valid_utc"]) < end]}


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
        "swell": swell_story(now, _read(live / "buoys.json"), at, Path(data_dir)),
        "conditions": {"water": water_now(Path(data_dir), at), "weather": weather_now(Path(data_dir), at)},
        "tide": tide_story(now, Path(data_dir), at),
    }


def with_text(built: dict) -> dict:
    """The build with the words the page prints from it, and the swell and
    tide words that decide an update. Without Node the words are null and
    every build is an update, said on stderr."""

    from .briefingwording import render_issue

    try:
        text = render_issue(built)
    except Exception as exc:  # noqa: BLE001 -- the payload stands without its words
        print(f"briefing: words not rendered ({type(exc).__name__}: {exc})", file=sys.stderr)
        return {**built, "text": None, "update_words": None}
    return {**built, "text": text, "update_words": text["swell"] + text["tides"]}


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
            append(args.data_dir, page)
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
