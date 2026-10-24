"""NWS's coast and ocean alerts: which are in force, and over which hours.

    python -m forecast.alerts      # data/live/alerts.json, from data/alerts/

Owner's request and calls, 2026-10-24: NWS warnings like the Coastal Flood
Warning at Coronado shown while they are in force -- a line each at the top
of the LIVE Briefing (`forecast.briefing`), and on the Forecast tab above the
Swell card over the hours each covers. Read from the archive
`collector.nwsalerts` keeps, never fetched here.

**Coast and ocean only** (owner's choice): from the land zone (CAZ043), the
events in `COASTAL_EVENTS`; from the coastal waters (PZZ750), every alert.
Heat, fire weather and wind on land are not shown. A test, exercise or
draft is never shown (``status`` must be ``Actual``).

**In force** is NWS's own times, never inferred: from the hazard's onset (its
``effective`` without one), and never before the alert was sent, to its
``ends`` (its ``expires`` without one). A later alert that references it
replaces it from when that one was sent, and an alert that only ends others
(a ``Cancel``, or VTEC actions all CAN / EXP / UPG) is never shown itself.
Each version is its own `segment`, so a past hour reads the version in force
then. An alert missed between collections is a gap: nothing here fills it.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR, ISO, utcnow
from collector.nwsalerts import ARCHIVE_DIR, COUNTY, LAND_ZONE, MARINE_ZONE

#: The land zone's coast and ocean events, as NWS names them.
COASTAL_EVENTS = frozenset({
    "Coastal Flood Warning", "Coastal Flood Watch", "Coastal Flood Advisory", "Coastal Flood Statement",
    "High Surf Warning", "High Surf Advisory", "Rip Current Statement", "Beach Hazards Statement",
    "Tsunami Warning", "Tsunami Watch", "Tsunami Advisory", "Storm Surge Warning", "Storm Surge Watch",
})
#: VTEC actions that end an event rather than carry it.
ENDING = frozenset({"CAN", "EXP", "UPG"})
#: How far back alerts.json reaches: the Forecast tab's 48 h of past hours.
PAST_H = 48

#: NWS's page for an alert, as the owner's link has it (2026-10-24): the land
#: zone with its county and fire zone, Coronado's place, and the event.
PAGE = "https://forecast.weather.gov/showsigwx.php"
LINK = {"warnzone": LAND_ZONE, "warncounty": COUNTY, "firewxzone": "CAZ243",
        "local_place1": "Coronado CA", "lat": "32.6858", "lon": "-117.182"}


def _utc(stamp: str | None) -> datetime | None:
    if not stamp:
        return None
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(timezone.utc)


def _iso(t: datetime | None) -> str | None:
    return t.strftime(ISO) if t else None


def load(data_dir: Path) -> list[dict]:
    """Every archived alert's properties, oldest sent first."""

    out = []
    for path in sorted((Path(data_dir) / ARCHIVE_DIR).glob("*/*.json")):
        try:
            props = json.loads(path.read_text(encoding="utf-8")).get("properties") or {}
        except ValueError:
            continue
        if props.get("id") and props.get("sent"):
            out.append(props)
    return sorted(out, key=lambda p: _utc(p["sent"]))


def zones(props: dict) -> list[str]:
    return list((props.get("geocode") or {}).get("UGC") or [])


def marine(props: dict) -> bool:
    return MARINE_ZONE in zones(props)


def relevant(props: dict) -> bool:
    """Coast and ocean, actual: every coastal-waters alert, and the land
    zone's coast and ocean events."""

    if props.get("status") != "Actual":
        return False
    return marine(props) or (LAND_ZONE in zones(props) and props.get("event") in COASTAL_EVENTS)


def actions(props: dict) -> list[str]:
    """Each VTEC line's action: "/O.CON.KSGX.CF.W.0003.../" -> "CON"."""

    out = []
    for line in (props.get("parameters") or {}).get("VTEC") or []:
        parts = line.strip("/").split(".")
        if len(parts) > 1:
            out.append(parts[1])
    return out


def ending(props: dict) -> bool:
    """Whether the alert only ends others: a Cancel, or every VTEC line an end."""

    acts = actions(props)
    return props.get("messageType") == "Cancel" or (bool(acts) and all(a in ENDING for a in acts))


def url(props: dict) -> str:
    """NWS's page for it: the owner's link for the land zone, the coastal
    waters' own zone for a marine alert."""

    query = dict(LINK, product1=props.get("event") or "")
    if marine(props) and LAND_ZONE not in zones(props):
        query.update(warnzone=MARINE_ZONE, warncounty="marine", firewxzone="")
    return f"{PAGE}?{urllib.parse.urlencode(query)}"


def headline(props: dict) -> str | None:
    """NWS's own headline: the alert's, else its NWSheadline."""

    got = props.get("headline")
    if got:
        return got
    nws = (props.get("parameters") or {}).get("NWSheadline") or []
    return nws[0] if nws else None


def segments(alerts: list[dict]) -> list[dict]:
    """Each coast and ocean version's time in force, oldest first: from its
    onset (never before it was sent) to its end, or to when a later alert
    replaced it."""

    replaced: dict[str, datetime] = {}
    for props in alerts:
        sent = _utc(props["sent"])
        for ref in props.get("references") or []:
            rid = ref.get("identifier")
            if rid and (rid not in replaced or sent < replaced[rid]):
                replaced[rid] = sent
    out = []
    for props in alerts:
        if not relevant(props) or ending(props):
            continue
        sent = _utc(props["sent"])
        start = max(_utc(props.get("onset") or props.get("effective")) or sent, sent)
        ends = _utc(props.get("ends"))
        end = ends or _utc(props.get("expires"))
        cut = [t for t in (end, replaced.get(props["id"])) if t]
        stop = min(cut) if cut else None
        if stop is not None and stop <= start:
            continue
        out.append({"id": props["id"], "event": props.get("event"), "headline": headline(props),
                    "url": url(props), "severity": props.get("severity"), "marine": marine(props),
                    "sent_utc": _iso(sent), "start_utc": _iso(start), "stop_utc": _iso(stop),
                    "ends_utc": _iso(ends)})
    return out


def _covers(seg: dict, a: datetime, b: datetime) -> bool:
    stop = _utc(seg["stop_utc"])
    return _utc(seg["start_utc"]) < b and (stop is None or stop > a)


def in_force(segs: list[dict], at: datetime) -> list[dict]:
    """The alerts in force at `at`, a line an event: when two are in force
    for one event (the land's and the waters'), the one ending last."""

    best: dict[str, dict] = {}
    for seg in segs:
        if _utc(seg["sent_utc"]) <= at and _covers(seg, at, at + timedelta(seconds=1)):
            have = best.get(seg["event"])
            if have is None or (seg["stop_utc"] or "~") > (have["stop_utc"] or "~"):
                best[seg["event"]] = seg
    return sorted(best.values(), key=lambda s: (s["start_utc"], s["event"]))


def briefing(data_dir: Path, at: datetime) -> list[dict]:
    """The Briefing's alerts: those in force at the build, as the page words
    them -- the event, its NWS end, its headline and its page."""

    seen = [p for p in load(data_dir) if _utc(p["sent"]) <= at]
    return [{k: s[k] for k in ("id", "event", "headline", "url", "start_utc", "ends_utc")}
            for s in in_force(segments(seen), at)]


def build(data_dir: Path = DEFAULT_DATA_DIR, at: datetime | None = None) -> dict:
    """alerts.json: every version in force at some moment from 48 h back on,
    as NWS had it by `at`, for the Forecast tab's hours."""

    at = at or utcnow()
    seen = [p for p in load(data_dir) if _utc(p["sent"]) <= at]
    since = at - timedelta(hours=PAST_H)
    segs = [s for s in segments(seen) if s["stop_utc"] is None or _utc(s["stop_utc"]) > since]
    return {"generated_utc": _iso(at.replace(microsecond=0)), "zones": [LAND_ZONE, MARINE_ZONE],
            "provider": "NWS", "alerts": segs}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--out", type=Path, default=None, help="default DATA_DIR/live/alerts.json")
    args = parser.parse_args(argv)
    out = args.out or Path(args.data_dir) / "live" / "alerts.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    got = build(args.data_dir)
    out.write_text(json.dumps(got, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(got['alerts'])} coast and ocean alert version(s) from {PAST_H} h back -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
