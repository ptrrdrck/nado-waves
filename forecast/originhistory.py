"""The Origin chart's marks: every readable arrival, and every hurricane the card would have named.

    python -m forecast.originhistory           # the archive (series-archive.yml)
    python -m forecast.originhistory --live    # the page's file (each collection)

Two kinds of mark, over time, for the chart under each LIVE swell tab (owner's
request, 2026-10-03):

* **Unnamed**: each arrival `forecast.origin` reads off 46232's spectrum, at
  its dispersion distance and its bearing at an unshadowed buoy, over the
  hours it was arriving. It belongs to the sites (breaks, or "buoy") whose
  card trains it was at its peak hour, as Origin's "Last readable arrival"
  does: which trains reach a break is the aperture's answer.
* **Named**: every `STEP_H` hours, the hurricanes `forecast.stormtrack.live`
  would have named AS OF that moment, with the match it would have stated and,
  per site, the NHC fix that sent the train arriving there. On a site where a
  named storm's train is the arrival's own, the arrival is that storm's and is
  not drawn as unnamed, as the card replaces Origin's reading of a named train.

Both are REBUILT with today's chain, like every other Now chart, and say so on
docs.html. The whole archive costs about a minute and a half (the match at each
moment a hurricane's band is arriving), so it is rebuilt by series-archive.yml,
the only writer of ``data/series/``, into `ARCHIVE`. Each collection writes
`LIVE` from it plus what it does not yet cover: the arrivals of the last
`origin.LOOKBACK_DAYS`, the named moments since its end, and now.json's own
hurricanes at the newest spectrum. A moment with no 46232 spectrum names the
storm with no site, and a storm with no site is drawn on no tab: a gap.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR, utcnow

from . import origin, stormtrack

ISO = "%Y-%m-%dT%H:%M:%SZ"
STATION = "46232"
#: How often a named moment is asked: the backtest's own step.
STEP_H = stormtrack.BACKTEST_STEP_H
ARCHIVE = Path("series") / f"{STATION}_origins.json"
LIVE = Path("live") / "origins.json"
#: The most the collection will rebuild of named moments the archive does not
#: cover; an archive older than this leaves the rest a gap, not a slow build.
TAIL_DAYS = 7
GRAVITY = 9.81
#: An arrival read from a bearing is a named storm's train only from within
#: this of the storm's own: the match's turned sectors sit 45° either side and
#: count as somewhere else. Period alone is not enough: on 29 Sep a north-west
#: ridge (304°) shared a 13 s train with Polo (161°).
SAME_SOURCE_DEG = 45.0


def _iso(t: datetime) -> str:
    return t.strftime(ISO)


def _time(text: str) -> datetime:
    return datetime.strptime(text, ISO).replace(tzinfo=timezone.utc)


def ridge_freq_hz(arrival: dict, at: datetime) -> float:
    """The arrival's fitted frequency at `at`: f = g (t - t0) / (4 pi R)."""

    dt = (at - _time(arrival["generated_utc"])).total_seconds()
    return GRAVITY * dt / (4.0 * math.pi * arrival["distance_km"] * 1000.0)


def arrival_marks(found: list, trains_at) -> list[dict]:
    """Each arrival as a mark, with the sites it was a card train of at its peak."""

    out, rebuilt = [], {}
    for a in found:
        peak = origin.peak_point(a)
        if peak.time not in rebuilt:
            rebuilt[peak.time] = trains_at(peak.time) or {}
        mark = origin._arrival_dict(a, False)
        mark.pop("running")
        mark["peak_utc"] = _iso(peak.time)
        mark["sites"] = sorted(site for site, trains in rebuilt[peak.time].items()
                               if origin.match(a, trains, peak) is not None)
        out.append(mark)
    return out


def moments(since: datetime, until: datetime) -> list[datetime]:
    """Every STEP_H-hour moment of the UTC day in (since, until]."""

    t = since.replace(minute=0, second=0, microsecond=0)
    t -= timedelta(hours=t.hour % STEP_H)
    out = []
    while t <= until:
        if t > since:
            out.append(t)
        t += timedelta(hours=STEP_H)
    return out


def named_marks(data_dir: Path, asked: list[datetime], trains_at) -> list[dict]:
    """The hurricanes the card would have named at each moment asked."""

    from .landpath import load_land
    from .origintracks import load_tracks
    from .siting import load_coordinates
    from .transform import load_spectra

    if not asked:
        return []
    tracks = {}
    for year in sorted({t.year for t in asked}):
        tracks.update(load_tracks(data_dir, year))
    if not tracks:
        return []
    positions = load_coordinates()
    land = load_land(str(data_dir))
    gate = [b for b in stormtrack.bands(tracks, positions, land=land)
            if b.station in stormtrack.GATE_STATIONS and b.fixes]
    open_at = {t: {b.storm for b in gate
                   if any(b.contains(t, f) for f in stormtrack.MODEL_FREQS)} for t in asked}
    need = [t for t in asked if open_at[t]]
    if not need:
        return []
    start = min(need) - timedelta(days=stormtrack.LIVE_DAYS)
    fields = {}
    for station in {b.station for b in gate}:
        try:
            spectra = load_spectra(Path(data_dir) / "spectra" / station)
        except (FileNotFoundError, ValueError):
            continue
        fields[station] = stormtrack.Field([s for s in spectra if start <= s.time <= max(need)])
    out = []
    for t in need:
        got = stormtrack.live({k: tracks[k] for k in open_at[t]}, fields, t, positions,
                              trains_at(t) or {}, land)
        out += [named_mark(t, h) for h in got]
    return out


def named_mark(at: datetime, hurricane: dict) -> dict:
    keep = ("storm", "name", "best", "word", "match", "sites")
    return {"time_utc": _iso(at), **{k: hurricane.get(k) for k in keep}}


def same_source(arrival: dict, storm_bearing: float) -> bool:
    """Could this arrival be that storm's train, by direction? Within
    `SAME_SOURCE_DEG` of its bearing; or, when its bearing was withheld
    because 46047's energy was split (BRIEFING §38), of one of the
    directions it held -- withholding a place never makes a name easier;
    with no reading at all, direction says nothing either way."""

    from .stats import angular_difference

    if arrival.get("bearing_deg") is not None:
        return abs(angular_difference(arrival["bearing_deg"], storm_bearing)) <= SAME_SOURCE_DEG
    lobes = arrival.get("bearing_lobes") or []
    if lobes:
        return any(abs(angular_difference(h, storm_bearing)) <= SAME_SOURCE_DEG for h, _ in lobes)
    return True


def link(arrivals: list[dict], named: list[dict]) -> None:
    """`named` on each arrival: {site: storm} where a named moment inside its
    hours has, at that site, a train within Origin's tolerance of the ridge's
    own frequency then, and, when the arrival has a bearing, from within
    `SAME_SOURCE_DEG` of the storm's (`same_source`). The card shows that train
    as the storm, not as Origin's reading, and so does the chart."""

    for a in arrivals:
        first, last = _time(a["first_utc"]), _time(a["last_utc"])
        hit = {}
        for n in named:
            t = _time(n["time_utc"])
            if not first <= t <= last:
                continue
            f = ridge_freq_hz(a, t)
            for site in a["sites"]:
                train = (n.get("sites") or {}).get(site)
                if not train or abs(1.0 / train["train_period_s"] - f) > origin.TRAIN_MATCH_HZ:
                    continue
                if same_source(a, train["bearing_deg"]):
                    hit.setdefault(site, n["name"])
        a["named"] = hit


def _chain(data_dir: Path, spectra):
    from .geometry import load
    from .nearshore import load_tables
    from .now import trains_builder

    spots, blockers = load()
    try:
        tables = load_tables()
    except (FileNotFoundError, ValueError):
        tables = {}
    return trains_builder(spectra, {s.id: s for s in spots}, blockers, tables)


def build_archive(data_dir: Path = DEFAULT_DATA_DIR) -> dict:
    """Every arrival and named moment the archive holds, rebuilt whole."""

    from .siting import load_coordinates

    archives = origin.load_archives(data_dir)
    spectra = archives.get(STATION, [])
    if not spectra:
        return {"station": STATION, "until_utc": None, "arrivals": [], "named": []}
    trains_at = _chain(data_dir, spectra)
    arrivals = arrival_marks(origin.arrivals(spectra, archives, load_coordinates().get(STATION)),
                             trains_at)
    until = spectra[-1].time
    named = named_marks(data_dir, moments(spectra[0].time - timedelta(seconds=1), until),
                        trains_at)
    link(arrivals, named)
    return {"station": STATION, "generated_utc": _iso(utcnow()), "until_utc": _iso(until),
            "step_h": STEP_H, "arrivals": arrivals, "named": named}


def build_live(data_dir: Path = DEFAULT_DATA_DIR) -> dict:
    """The archive, and what the newest spectra add to it.

    Arrivals: the archive's up to `cut`, and every arrival read in the last
    `origin.LOOKBACK_DAYS` (+ the fit's 2 days of lead-in) from `cut` on, so a
    ridge the archive caught still running is taken whole from the newer read.
    Named: the archive's to its end, the moments since (at most `TAIL_DAYS`),
    and now.json's hurricanes at its own spectrum.
    """

    from .siting import load_coordinates

    path = Path(data_dir) / ARCHIVE
    archive = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    archives = origin.load_archives(data_dir)
    spectra = archives.get(STATION, [])
    if not spectra:
        return {"station": STATION, "newest_utc": None, "arrivals": [], "named": []}
    newest = spectra[-1].time
    lead_in = timedelta(hours=origin.FIT_HOURS)
    start = newest - timedelta(days=origin.LOOKBACK_DAYS) - lead_in
    cut = start + lead_in
    window = [s for s in spectra if s.time >= start]
    trains_at = _chain(data_dir, window)
    recent = [a for a in origin.arrivals(window, archives, load_coordinates().get(STATION))
              if a.first_utc >= cut]
    arrivals = [a for a in archive.get("arrivals", []) if _time(a["first_utc"]) < cut]
    arrivals += arrival_marks(recent, trains_at)

    until = _time(archive["until_utc"]) if archive.get("until_utc") else newest - timedelta(days=TAIL_DAYS)
    since = max(until, newest - timedelta(days=TAIL_DAYS))
    named = [n for n in archive.get("named", []) if _time(n["time_utc"]) <= since]
    named += named_marks(data_dir, moments(since, newest), trains_at)
    named += current_named(data_dir, newest)
    link(arrivals, named)
    for a in arrivals:
        a["running"] = _time(a["last_utc"]) >= newest - timedelta(hours=origin.CURRENT_H)
    return {"station": STATION, "generated_utc": _iso(utcnow()), "newest_utc": _iso(newest),
            "archive_until_utc": archive.get("until_utc"), "step_h": STEP_H,
            "arrivals": arrivals, "named": named}


def current_named(data_dir: Path, newest: datetime) -> list[dict]:
    """now.json's hurricanes, at now.json's own spectrum: the card's last word.
    Only when that spectrum is the newest one read here: a now.json from
    another hour says nothing about this one."""

    path = Path(data_dir) / "live" / "now.json"
    if not path.exists():
        return []
    reading = json.loads(path.read_text(encoding="utf-8"))
    stamp = reading.get("observed_utc")
    found = ((reading.get("origin") or {}).get("hurricanes")) or []
    if not stamp:
        return []
    at = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    if abs((at - newest).total_seconds()) > 3600:
        return []
    # A grid moment the tail already asked is the same question; keep one.
    return [named_mark(at, h) for h in found
            if h.get("best") is not None and (at.hour % STEP_H or at.minute)]


def write(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--live", action="store_true",
                        help="write data/live/origins.json from the archive and the newest spectra")
    args = parser.parse_args(argv)
    payload = build_live(args.data_dir) if args.live else build_archive(args.data_dir)
    path = Path(args.data_dir) / (LIVE if args.live else ARCHIVE)
    write(payload, path)
    print(f"{len(payload['arrivals'])} arrivals, {len(payload['named'])} named moments -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
