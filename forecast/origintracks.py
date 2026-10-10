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

The tracks are read from `data/besttracks/` (`collector.besttracks`, archived
by origin-tracks.yml: ftp.nhc.noaa.gov is denied at CONNECT from a session),
so this runs anywhere. No archive, exit 1.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR, write_step_summary

from .swell import great_circle_km, initial_bearing

YEAR = 2026

#: Where a storm is looked for around a reading's birth time.
BEFORE_H, AFTER_H = 48.0, 24.0
#: The control's shift: the same storms at the wrong time.
SHIFT_DAYS = 10.0
#: Only fixes at hurricane strength count by default. NHC's b-decks also
#: carry 15-25 kt "Genesis" and "Invest" disturbances; the first run
#: (2026-10-02) matched most readings to those, which make no 13-15 s swell,
#: and the season was busy enough that the +/-10 d control matched them as
#: well. A 64 kt fix is a storm that could have sent the train.
MIN_KT = 64


@dataclass(frozen=True)
class Fix:
    storm: str
    name: str
    time: datetime
    lat: float
    lon: float
    vmax_kt: int
    #: Minimum sea-level pressure, hPa; None where the b-deck writes 0 or
    #: nothing (an invest's early fixes).
    mslp_mb: int | None = None


def _coord(text: str) -> float:
    """ATCF's "153N" / "1105W": tenths of a degree with a hemisphere."""

    text = text.strip()
    value = int(text[:-1]) / 10.0
    return -value if text[-1] in "SW" else value


def parse_bdeck(text: str) -> list[Fix]:
    """One storm's b-deck, one fix per six-hourly time.

    A b-deck repeats a time once per wind-radius threshold (34, 50, 64 kt);
    the position, peak wind and pressure are the same on each, so the first
    is kept.
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
                mslp_mb=int(cols[9]) if len(cols) > 9 and cols[9] and int(cols[9]) > 0 else None,
            )
        except (ValueError, IndexError):
            continue
        seen.setdefault(time, fix)
    return [seen[t] for t in sorted(seen)]


def load_tracks(data_dir: Path = DEFAULT_DATA_DIR, year: int = YEAR) -> dict[str, list[Fix]]:
    """Every archived b-deck for `year` (`collector.besttracks`), by storm.

    Read from the repository, never fetched here: the check is reproducible
    against the files it read, and it runs in a session, where NHC is denied.
    """

    tracks = {}
    for path in sorted((Path(data_dir) / "besttracks" / str(year)).glob("b*.dat")):
        fixes = parse_bdeck(path.read_text(encoding="utf-8"))
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
            shift_days: float = 0.0, min_kt: int = 0) -> Match | None:
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
            if not lo <= fix.time <= hi or fix.vmax_kt < min_kt:
                continue
            here = (fix.lat, fix.lon)
            distance = great_circle_km(home, here)
            miss = (great_circle_km(tuple(reading["origin"]), here) if reading.get("origin")
                    else abs(distance - reading["distance_km"]))
            if best is None or miss < best.miss_km:
                best = Match(fix, miss, distance, initial_bearing(home, here))
    return best


def report(readings: list[dict], tracks: dict[str, list[Fix]], home: tuple[float, float],
           min_kt: int = 0) -> str:
    strong = sum(1 for v in tracks.values() for f in v if f.vmax_kt >= min_kt)
    lines = [
        f"Origin readings against NHC best tracks, {YEAR} eastern and central Pacific "
        f"({len(tracks)} systems, {sum(len(v) for v in tracks.values())} six-hourly fixes; "
        f"{strong} fixes at {min_kt} kt or more, the only ones counted)",
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
        m = nearest(r, tracks, home, min_kt=min_kt)
        control = [nearest(r, tracks, home, shift_days=d, min_kt=min_kt)
                   for d in (-SHIFT_DAYS, SHIFT_DAYS)]
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
    parser.add_argument("--min-kt", type=int, default=MIN_KT,
                        help="Count only best-track fixes at least this strong (kt).")
    args = parser.parse_args(argv)

    from .siting import load_coordinates

    tracks = load_tracks(args.data_dir)
    if not tracks:
        print(f"no {YEAR} b-decks archived in data/besttracks/: run collector.besttracks "
              f"on Actions (origin-tracks.yml)")
        return 1
    text = report(readings_from_archive(args.data_dir), tracks, load_coordinates()["46232"],
                  min_kt=args.min_kt)
    print(text)
    write_step_summary(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
