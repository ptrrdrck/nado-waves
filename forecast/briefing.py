"""The LIVE tab's Briefing: what has happened since sunset, what is arriving.

    python -m forecast.briefing        # data/live/briefing.json

Owner's request, 2026-10-16: a lifeguard's morning read, so the cards need
not be put together by hand. It sits above the LIVE cards in its own fold.
Every number in it is already on the page or measured from what the page
reads; what it adds is the comparison across time and across cards, each
story over its own clock:

- **Standing on**: each feed's stamp, anything overdue, any hour since
  sunset 46232 has no spectrum for. 46232 dark stands every break story down.
- **Since sunset**: each break's breaking height at the last sunset and now,
  rose / dropped / little change, which break leads then and now, each
  break's biggest train then and now, and the leading break's biggest
  calculation step.
- **Arriving**: Origin's arrivals at the breaks (current, and ended since
  sunset), each running ridge's period projected `PERIOD_AHEAD_H` ahead; the
  hurricanes NHC tracks, due at the breaks by deep-water speed from their
  fixes (best track, then NHC's forecast, each named as such) until their
  last open-water fix's swell has passed; and 46047's west or north-west
  sector risen since sunset, due at 46232 and the breaks by deep-water speed
  (`forecast.upstreamlag`, BRIEFING §43).
- **Wind**: the KNZY reading each hour since sunset, per break by the card's
  verdict, and the newest; local chop now.
- **Tide**: the card's next turns (predicted), the departure, the phase.
- **Buoys and season**: 46047's and 46086's trains now, two directions at
  once where a buoy holds them, and how the leading break's height ranks in
  the archive.

**Never the model.** GFS-Wave and its ensemble are the Forecast tab's; the
briefing is the LIVE chain plus NHC's fixes, the one input the owner allowed
(2026-10-16) because the hurricane gate is already checking it.

**Every word that judges is measured** (`forecast.briefingreport`,
`docs/briefing_thresholds.md`): a slot is said only where it is right ≥ 85%
of the times it fires. The wind's onshore habit failed and is not carried.

Units stay metres and knots here; the page converts and words it
(`app/forecast.html`, `docs/briefing_wording.md`). This module is its own
file and its own step: a context buoy never enters `now.json` or the chain.
"""

from __future__ import annotations

#: Rose / dropped: the 3-hour medians at sunset and now differ by at least
#: this share (measured: the smallest step right ≥ 85% on every break and
#: span 6–24 h; 10% held from 12 h but north reached only 83% over 6 h).
CHANGE_SHARE = 0.15

#: Spans shorter than this were not measured; the story then gives the two
#: readings with no word between them.
MIN_SPAN_H = 6

#: A break leads when its 3-hour median is ahead of the next by this share
#: (measured: 3% is the smallest right ≥ 85%, 86.3%; 5% so the two heights
#: differ on screen at 0.1 ft).
LEAD_MARGIN = 0.05

#: A running ridge's period is projected this far ahead, in whole seconds
#: (measured: within 1 s on 9 of 9 at 12 h; 4 of 5 at 24 h).
PERIOD_AHEAD_H = 12

import argparse
import json
import math
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR, ISO, utcnow

BREAKS = ("coronado_north", "coronado_center", "coronado_south")
UPSTREAM = "46047"

#: The calculation table's rows, in its order (`nearshore.summarise`): the
#: biggest step at the leading break is the one named.
STEPS = (("windows", "window_hs_m"), ("refraction", "refracted_hs_m"),
         ("diffraction", "diffracted_hs_m"), ("bottom friction", "friction_hs_m"),
         ("shoaling", "shoaled_hs_m"), ("local chop", "with_chop_hs_m"))

#: Two readings of a break's biggest train are named as different at the
#: page's own precision: whole seconds of period beyond rounding, or a
#: different 22.5° compass point and 15° of heading.
TRAIN_DIFF_S = 1.0
TRAIN_DIFF_DEG = 15.0

#: "Biggest since" is said only when that was at least this long ago: a
#: ranking against yesterday is noise, not season.
SEASON_MIN_DAYS = 7

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


# ------------------------------------------------------------------ standing on

def standing_on(now: dict, buoys: dict | None, series: dict | None, since: datetime,
                at: datetime) -> dict:
    # Each feed's own deadline, never a flag frozen at build time: the page
    # judges lateness on the reader's clock, as its countdowns do.
    feeds = []
    for feed, station, observed in (
            ("swell", now.get("station"), now.get("observed_utc")),
            ("wind", (now.get("wind") or {}).get("station"), (now.get("wind") or {}).get("observed_utc")),
            ("tide", now.get("tide_station"), (now.get("tide") or {}).get("observed_utc"))):
        feeds.append({"feed": feed, "station": station, "observed_utc": observed,
                      "overdue_after_utc": (now.get("overdue_after") or {}).get(feed)})
    for b in (buoys or {}).get("buoys", []):
        feeds.append({"feed": "buoy", "station": b["station"], "observed_utc": b.get("observed_utc"),
                      "overdue_after_utc": b.get("overdue_after")})
    gaps = []
    for step in (series or {}).get("steps", []):
        t = _utc(step["valid_utc"])
        if t >= since and step.get("gap"):
            if gaps and _utc(gaps[-1]["to_utc"]) == t - timedelta(hours=1):
                gaps[-1]["to_utc"] = step["valid_utc"]
            else:
                gaps.append({"from_utc": step["valid_utc"], "to_utc": step["valid_utc"]})
    return {"feeds": feeds, "gaps": gaps, "dark": bool(now.get("stale"))}


# ------------------------------------------------------------------ since sunset

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


def _biggest(trains: list[dict]) -> dict | None:
    swell = [t for t in trains or [] if t.get("hs_m") is not None]
    if not swell:
        return None
    t = max(swell, key=lambda t: t["hs_m"])
    return {"period_s": t.get("period_s"), "from_deg": t.get("from_deg"), "hs_m": t.get("hs_m")}


def _differs(a: dict | None, b: dict | None) -> bool:
    if not a or not b:
        return False
    if abs(round(a["period_s"]) - round(b["period_s"])) >= TRAIN_DIFF_S:
        return True
    gap = abs((a["from_deg"] - b["from_deg"] + 180.0) % 360.0 - 180.0)
    point = lambda d: int(((d % 360.0) + 11.25) // 22.5) % 16
    return gap >= TRAIN_DIFF_DEG and point(a["from_deg"]) != point(b["from_deg"])


def biggest_step(effects: dict | None, breaking_m: float | None) -> dict | None:
    """The calculation-table row that changed the height most at this break,
    against the row before, as the table states it."""

    if not effects or effects.get("buoy_hs_m") is None:
        return None
    rows = [(name, effects.get(key)) for name, key in STEPS]
    if breaking_m is not None:
        rows.append(("wave break", breaking_m))
    best, before = None, effects["buoy_hs_m"]
    for name, value in rows:
        if value is None or before is None or before <= 0:
            continue
        pct = 100.0 * (value / before - 1.0)
        if best is None or abs(pct) > abs(best["change_pct"]):
            best = {"step": name, "change_pct": round(pct)}
        before = value
    return best


def _sunset_trains(data_dir: Path, hour: datetime) -> dict[str, dict | None]:
    """Each break's biggest train at the sunset hour, rebuilt from that hour's
    own spectrum by today's chain, as the charts are. None where 46232 has no
    spectrum stamped at that hour."""

    from .measured import Rebuilder
    from .now import build as observed

    rebuild = Rebuilder(data_dir)
    spectrum = rebuild.by_time.get(hour)
    if spectrum is None:
        return {bid: None for bid in BREAKS}
    reading = observed(data_dir=data_dir, now=hour, spectrum=spectrum, as_of=True,
                       tables=rebuild.tables, profiles=rebuild.profiles)
    out = {bid: None for bid in BREAKS}
    for b in reading.breaks:
        out[b.id] = _biggest((b.nearshore or {}).get("trains") or b.trains)
    return out


def since_sunset(now: dict, series: dict | None, since: datetime, data_dir: Path,
                 trains_then: dict | None = None) -> dict | None:
    heights = _heights(series)
    newest = _utc(now.get("observed_utc"))
    if now.get("stale") or newest is None or newest not in heights:
        return None
    first = min((t for t in heights if t >= since), default=None)
    if first is None:
        return None
    span_h = (newest - since).total_seconds() / 3600.0
    measured = span_h >= MIN_SPAN_H
    newest3 = [newest - timedelta(hours=h) for h in (0, 1, 2)]
    around = [first + timedelta(hours=h) for h in (-1, 0, 1)]
    by_id = {b["id"]: b for b in now.get("breaks", [])}
    trains_then = _sunset_trains(data_dir, first) if trains_then is None else trains_then
    rows = []
    for bid in BREAKS:
        then_m, now_m = heights[first][bid], heights[newest][bid]
        med_then, med_now = _median(heights, around, bid), _median(heights, newest3, bid)
        change = None
        if measured and med_then and med_now:
            rel = med_now / med_then - 1.0
            if abs(rel) >= CHANGE_SHARE and rel * (now_m - then_m) > 0:
                change = "rose" if rel > 0 else "dropped"
            else:
                change = "little"
        b = by_id.get(bid, {})
        near = b.get("nearshore") or {}
        train_now = _biggest(near.get("trains") or b.get("trains"))
        rows.append({
            "id": bid, "then_m": then_m, "now_m": now_m, "change": change,
            "normal_deg": b.get("shore_normal_deg"),
            "train_then": trains_then.get(bid), "train_now": train_now,
            "train_changed": _differs(trains_then.get(bid), train_now),
        })
    lead_then = _leader({bid: _median(heights, around, bid) for bid in BREAKS})
    lead_now = _leader({bid: _median(heights, newest3, bid) for bid in BREAKS})
    step = None
    if lead_now:
        b = by_id.get(lead_now, {})
        near = b.get("nearshore") or {}
        step = biggest_step(near.get("effects"), (near.get("breaking") or {}).get("hs_m"))
    return {"then_utc": _iso(first), "now_utc": _iso(newest), "span_h": round(span_h, 1),
            "measured": measured, "breaks": rows, "lead_then": lead_then, "lead_now": lead_now,
            "lead_step": step}


# ------------------------------------------------------------------ arriving

def _projected(arrival: dict, at: datetime) -> float | None:
    from .briefingreport import projected_period

    class _Fit:
        distance_km = arrival["distance_km"]
        generated_utc = _utc(arrival["generated_utc"])

    period = projected_period(_Fit, at)
    return round(period) if period and period > 0 else None


def origin_story(now: dict, since: datetime, newest: datetime) -> dict:
    block = now.get("origin") or {}
    arrivals = block.get("arrivals") or []
    current, ended = {}, {}
    for site, got in (block.get("sites") or {}).items():
        if site not in BREAKS:
            continue
        for i in got.get("current") or []:
            current.setdefault(i, []).append(site)
        last = got.get("last")
        if last is not None and last not in (got.get("current") or []):
            a = arrivals[last]
            if not a.get("running") and _utc(a["last_utc"]) >= since:
                ended.setdefault(last, []).append(site)
    ahead = newest + timedelta(hours=PERIOD_AHEAD_H)
    out_current = []
    for i, sites in sorted(current.items()):
        a = arrivals[i]
        out_current.append({**_arrival_slots(a), "breaks": sites,
                            "ahead_utc": _iso(ahead), "ahead_period_s": _projected(a, ahead)})
    return {"current": out_current,
            "ended": [{**_arrival_slots(arrivals[i]), "breaks": s} for i, s in sorted(ended.items())],
            "hurricanes": block.get("hurricanes") or [],
            "station_names": block.get("station_names") or {},
            "station_cdips": block.get("station_cdips") or {}}


def _arrival_slots(a: dict) -> dict:
    keep = ("first_utc", "last_utc", "running", "hours_read", "lead_period_s", "latest_period_s",
            "distance_km", "generated_utc", "bearing_deg", "bearing_from", "bearing_lobes", "region")
    return {k: a.get(k) for k in keep}


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


def upstream_story(data_dir: Path, buoys: dict | None, since: datetime, at: datetime,
                   spectra=None) -> list[dict]:
    """46047's west and north-west sectors since sunset: one entry per sector
    that rose, its bands earliest first (a dispersed swell's long periods
    lead), each band when it rose and when deep water puts it at 46232 and
    the breaks (BRIEFING §43)."""

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


# ------------------------------------------------------------------ wind, tide, buoys

def wind_story(now: dict, windtide: dict | None, since: datetime) -> dict:
    """Since sunset, each break's hours by the card's verdict, from KNZY's
    hourly readings (`windtide`: a reading taken in the hour up to each slot,
    never carried)."""

    from .live import offshore_component

    normals = {b["id"]: b.get("shore_normal_deg") for b in now.get("breaks", [])}
    counts = {bid: {} for bid in BREAKS}
    heard = 0
    if windtide:
        start = _utc(windtide["start_utc"])
        step = timedelta(hours=windtide.get("step_h", 1))
        w = windtide.get("wind") or {}
        dirs, kts = w.get("from_deg") or [], w.get("kt") or []
        for k, kt in enumerate(kts):
            t = start + k * step
            if t < since or kt is None:
                continue
            heard += 1
            d = dirs[k] if k < len(dirs) else None
            for bid in BREAKS:
                verdict = _sense(None if d is None or normals.get(bid) is None
                                 else offshore_component(d, normals[bid]), kt)
                counts[bid][verdict] = counts[bid].get(verdict, 0) + 1
    chop = {b["id"]: ((b.get("nearshore") or {}).get("effects") or {}).get("local")
            for b in now.get("breaks", [])}
    return {"hours": heard, "by_break": counts, "now": now.get("wind"),
            "offshore_now": {b["id"]: b.get("wind_offshore") for b in now.get("breaks", [])},
            "chop_now": {bid: bool(v) for bid, v in chop.items()}}


def _sense(offshore: float | None, kt: float) -> str:
    """The page's `sense()` for the charts' counts: 0 kt calm, ≤ LIGHT_KT
    light (a side the card still names, the charts do not), no direction
    variable."""

    if kt == 0:
        return "calm"
    if kt <= 3:
        return "light"
    if offshore is None:
        return "variable"
    return "offshore" if offshore > 0.3 else "onshore" if offshore < -0.3 else "cross-shore"


def tide_story(now: dict, at: datetime) -> dict:
    from zoneinfo import ZoneInfo

    day = at.astimezone(ZoneInfo("America/Los_Angeles")).date().isoformat()
    phase = ((now.get("tide_phase") or {}).get("days") or {}).get(day)
    return {"turns": now.get("tide_turns") or [], "level": now.get("tide"),
            "departure_m": now.get("tide_departure_m"), "phase": phase, "day": day}


def buoys_story(buoys: dict | None) -> list[dict]:
    out = []
    for b in (buoys or {}).get("buoys", []):
        swell = [t for t in b.get("trains") or [] if not t.get("wind_sea")]
        out.append({"station": b["station"], "name": b.get("station_name"),
                    "stale": b.get("stale"), "observed_utc": b.get("observed_utc"),
                    "trains": [{k: t.get(k) for k in ("hs_m", "period_s", "from_deg", "share")}
                               for t in swell[:2]]})
    return out


def season_story(heights_now: dict[str, float], lead: str | None, newest: datetime,
                 data_dir: Path) -> dict | None:
    """When the leading break was last at least this big, in the archive."""

    if not lead:
        return None
    from .briefingreport import load_heights

    k = BREAKS.index(lead)
    archive = load_heights(Path(data_dir) / "series" / "46232")
    if not archive:
        return None
    level = heights_now[lead]
    before = [t for t, v in archive.items() if t < newest - timedelta(hours=24) and v[k] >= level]
    if before and newest - max(before) < timedelta(days=SEASON_MIN_DAYS):
        return None
    return {"id": lead, "now_m": level, "since_utc": _iso(max(before)) if before else None,
            "archive_from_utc": _iso(min(archive))}


# ------------------------------------------------------------------ build

def build(*, data_dir: Path = DEFAULT_DATA_DIR, at: datetime | None = None,
          live_dir: Path | None = None) -> dict:
    """`briefing.json` from the payloads this collection just wrote into
    `live_dir` (``data/live``), and the archives under `data_dir`, nothing
    after `at`."""

    live = Path(live_dir) if live_dir else Path(data_dir) / "live"
    now = _read(live / "now.json")
    at = at or utcnow()
    if not now:
        return {"generated_utc": _iso(at), "available": False,
                "why": "no observed reading was built this collection"}
    newest = _utc(now.get("observed_utc")) or at
    since = last_sunset(newest)
    series, windtide = _read(live / "series.json"), _read(live / "windtide.json")
    buoys = _read(live / "buoys.json")
    sunset = since_sunset(now, series, since, Path(data_dir))
    heights_now = {r["id"]: r["now_m"] for r in (sunset or {}).get("breaks", [])}
    return {
        "generated_utc": _iso(at), "available": True,
        "since_utc": _iso(since), "newest_utc": _iso(newest),
        "station": now.get("station"), "station_cdip": now.get("station_cdip"),
        "standing_on": standing_on(now, buoys, series, since, at),
        "since_sunset": sunset,
        "arriving": {
            "origin": origin_story(now, since, newest),
            "storms": storms_story(at, Path(data_dir)),
            "upstream": upstream_story(Path(data_dir), buoys, since, at),
        },
        "wind": wind_story(now, windtide, since),
        "tide": tide_story(now, at),
        "buoys": buoys_story(buoys),
        "season": season_story(heights_now, (sunset or {}).get("lead_now"), newest, Path(data_dir))
                  if sunset else None,
        "thresholds": {"change_share": CHANGE_SHARE, "lead_margin": LEAD_MARGIN,
                       "min_span_h": MIN_SPAN_H, "period_ahead_h": PERIOD_AHEAD_H},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    payload = build(data_dir=args.data_dir)
    out = args.out or (Path(args.data_dir) / "live" / "briefing.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
