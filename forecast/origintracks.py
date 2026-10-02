"""Origin's readings against the hurricanes NHC actually tracked. Reports, never edits.

    python -m forecast.origintracks          # on Actions: origin-tracks.yml

BRIEFING §37 left one check undone: about half of Origin's readings since
2026-08-04 put the storm ~3,000 km away in "the tropical Pacific" or "the
eastern North Pacific", in hurricane season. If those were hurricanes, the
National Hurricane Center's BEST TRACK says where each one was, every six
hours. A best track is a post-season analysis, not an observation of the swell,
but it is the nearest thing to a record of where a storm was, and it was made
with no reference to anything here.

So for every reading this fetches the 2026 eastern and central Pacific best
tracks (ATCF b-decks) and asks:

* **Which tracked storm came nearest the reading's origin** within the two days
  before its birth time to one day after, how near, and how strong it was.
* **What the reading would have said** had it been that storm exactly: the
  storm's own distance and bearing from 46232, against the reading's.
* **The control**: the same origin against the same storms ten days earlier and
  later. The season was busy; a reading lands near SOME storm by chance. A real
  match is much nearer at the right time than at the wrong one.

Readings without a bearing are compared on distance alone, and said so.

Run it on Actions: ftp.nhc.noaa.gov is denied at CONNECT from a session
(2026-10-02, with HURDAT, IBTrACS and JTWC). A denial exits 2, an empty
listing 1.
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR, write_step_summary

from .swell import great_circle_km, initial_bearing

BTK = "https://ftp.nhc.noaa.gov/atcf/btk/"
YEAR = 2026
#: Eastern and central Pacific: everything a ~3,000 km origin south and west
#: of 46232 could be. The western Pacific is JTWC's and 8,000 km off.
BASINS = ("ep", "cp")
USER_AGENT = "nado-waves origin check (github.com/ptrrdrck/nado-waves)"

#: Where a storm is looked for around a reading's birth time.
BEFORE_H, AFTER_H = 48.0, 24.0
#: The control's shift: the same storms at the wrong time.
SHIFT_DAYS = 10.0


@dataclass(frozen=True)
class Fix:
    storm: str
    name: str
    time: datetime
    lat: float
    lon: float
    vmax_kt: int


def _coord(text: str) -> float:
    """ATCF's "153N" / "1105W": tenths of a degree with a hemisphere."""

    text = text.strip()
    value = int(text[:-1]) / 10.0
    return -value if text[-1] in "SW" else value


def parse_bdeck(text: str) -> list[Fix]:
    """One storm's b-deck, one fix per six-hourly time.

    A b-deck repeats a time once per wind-radius threshold (34, 50, 64 kt);
    the position and peak wind are the same on each, so the first is kept.
    """

    seen: dict[datetime, Fix] = {}
    for line in text.splitlines():
        cols = [c.strip() for c in line.split(",")]
        if len(cols) < 9 or cols[4] != "BEST":
            continue
        try:
            time = datetime.strptime(cols[2], "%Y%m%d%H").replace(tzinfo=timezone.utc)
            fix = Fix(
                storm=f"{cols[0]}{cols[1]}",
                name=cols[27] if len(cols) > 27 and cols[27] else "",
                time=time,
                lat=_coord(cols[6]),
                lon=_coord(cols[7]),
                vmax_kt=int(cols[8] or 0),
            )
        except (ValueError, IndexError):
            continue
        seen.setdefault(time, fix)
    return [seen[t] for t in sorted(seen)]


def _get(url: str, timeout: float = 60.0) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", "replace")


def fetch_tracks(year: int = YEAR) -> dict[str, list[Fix]]:
    listing = _get(BTK)
    names = sorted(set(re.findall(rf'href="(b(?:{"|".join(BASINS)})\d{{2}}{year}\.dat)"', listing)))
    tracks = {}
    for name in names:
        fixes = parse_bdeck(_get(BTK + name))
        if fixes:
            tracks[fixes[0].storm] = fixes
    return tracks


@dataclass
class Match:
    fix: Fix
    miss_km: float
    distance_km: float
    bearing_deg: float


def nearest(reading: dict, tracks: dict[str, list[Fix]], home: tuple[float, float],
            shift_days: float = 0.0) -> Match | None:
    """The tracked fix nearest the reading's origin around its birth time.

    Without an origin (no bearing), nearest in DISTANCE FROM 46232 instead,
    which is a much weaker test and is reported as one.
    """

    born = datetime.fromisoformat(reading["generated_utc"].replace("Z", "+00:00"))
    born += timedelta(days=shift_days)
    lo, hi = born - timedelta(hours=BEFORE_H), born + timedelta(hours=AFTER_H)
    best = None
    for fixes in tracks.values():
        for fix in fixes:
            if not lo <= fix.time <= hi:
                continue
            here = (fix.lat, fix.lon)
            distance = great_circle_km(home, here)
            miss = (great_circle_km(tuple(reading["origin"]), here) if reading.get("origin")
                    else abs(distance - reading["distance_km"]))
            if best is None or miss < best.miss_km:
                best = Match(fix, miss, distance, initial_bearing(home, here))
    return best


def report(readings: list[dict], tracks: dict[str, list[Fix]], home: tuple[float, float]) -> str:
    lines = [
        f"Origin readings against NHC best tracks, {YEAR} eastern and central Pacific "
        f"({len(tracks)} storms, {sum(len(v) for v in tracks.values())} six-hourly fixes)",
        "",
        "| first seen at 46232 | reading | nearest tracked storm, born -2 d to +1 d | "
        "miss | storm from 46232 | control: same storms +/-10 d |",
        "|---|---|---|---|---|---|",
    ]
    for r in readings:
        placed = bool(r.get("origin"))
        what = (f"{r['distance_km']:,} km at {r['bearing_deg']}° ({r['region']}), "
                f"born {r['generated_utc'][5:13]}Z" if placed
                else f"{r['distance_km']:,} km, no bearing, born {r['generated_utc'][5:13]}Z")
        m = nearest(r, tracks, home)
        control = [nearest(r, tracks, home, shift_days=d) for d in (-SHIFT_DAYS, SHIFT_DAYS)]
        control = [c.miss_km for c in control if c]
        ctl = f"{min(control):,.0f} km" if control else "no storm"
        if m is None:
            lines.append(f"| {r['first_utc'][:13]}Z | {what} | none tracked | | | {ctl} |")
            continue
        f = m.fix
        storm = (f"{f.name.title() or f.storm.upper()} ({f.storm.upper()}), {f.vmax_kt} kt, "
                 f"{f.time:%m-%d %H}Z at {abs(f.lat):.1f}{'N' if f.lat >= 0 else 'S'} "
                 f"{abs(f.lon):.1f}{'W' if f.lon < 0 else 'E'}")
        miss = f"{m.miss_km:,.0f} km" + ("" if placed else " (distance only)")
        lines.append(
            f"| {r['first_utc'][:13]}Z | {what} | {storm} | {miss} | "
            f"{m.distance_km:,.0f} km at {m.bearing_deg:.0f}° "
            f"(x{r['distance_km'] / m.distance_km:.2f}) | {ctl} |")
    lines += [
        "",
        "miss: great-circle distance from the reading's origin to the storm's fix "
        "(for an unplaced reading, |storm's distance from 46232 - reading's distance|). "
        "x: reading's distance over the storm's. A best track is NHC's analysis, not an "
        "observation of the swell.",
    ]
    return "\n".join(lines)


def readings_from_archive(data_dir: Path) -> list[dict]:
    from . import origin
    from .siting import load_coordinates

    archives = origin.load_archives(data_dir)
    position = load_coordinates().get("46232")
    out = []
    for a in origin.arrivals(archives["46232"], archives, position):
        d = origin._arrival_dict(a, False)
        out.append(d)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = parser.parse_args(argv)

    from .siting import load_coordinates

    try:
        tracks = fetch_tracks()
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        print(f"best tracks not reachable from here: {reason}")
        write_step_summary(f"**Best tracks not reachable:** {reason}")
        return 2 if "403" in str(reason) or "Tunnel" in str(reason) else 1
    if not tracks:
        print(f"no {YEAR} eastern or central Pacific b-decks listed at {BTK}")
        return 1
    text = report(readings_from_archive(args.data_dir), tracks, load_coordinates()["46232"])
    print(text)
    write_step_summary(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
