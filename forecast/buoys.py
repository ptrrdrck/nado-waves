"""The context buoys on the LIVE tab's Buoys tab: what each MEASURED, nothing more.

Run: ``python -m forecast.buoys``  (writes ``data/live/buoys.json``)

The Buoys tab (owner's request, 2026-10-06) shows 46232 -- the anchor every
break's card is derived from, read by `forecast.now` -- and under it 46086,
San Clemente Basin (owner's request, 2026-10-12), then 46047, Tanner Banks,
the least shadowed buoy in the array (`STATIONS`). Each is shown the way 46232 is at the
buoy: the combined height of its directional spectrum read by maximum
entropy, and its wave trains (`transform.at_buoy`, the same peak split and the
same two-direction rule, BRIEFING §38a).

**They are carried to no break, and this module is why that stays true.**
46047 sits 21.0 / 12.8 / 3.2° outside North / Center / South's windows
(`forecast.siting`, BRIEFING §3a); it is the open ocean before the Channel
Islands and the Bight, not the sea at Coronado. 46086 is inside South's
window alone, 5.9° outside Center's -- "the nearest thing to a stand-in, and
partial" (§3a) -- and an NDBC hull whose north-west lobe pins near 279°
whatever 46047 reads (§38). §3a forbids either as a stand-in for 46232. So
they are read here and nowhere on the chain: `forecast.now` and the rest of
the forecast path may not even name them (`tests/test_spectra_collector.py`),
this module calls `at_buoy` and never `through`, `carry` or the surf zone
(`tests/test_buoys.py`), and their file is their own, not a key inside
now.json. What each one's block says about the windows (`WITNESS`) is pinned
to `forecast.siting` by a test, so it cannot outlive the geometry.

**Each buoy's roses ride in the same file** (`roses`, `forecast.rose`): the
last six hours of spectra at 46232 and at 46047, one rose each, for the loop
under each buoy's reading. 46232's are a picture of the anchor's spectrum at
the buoy, as its block is; nothing reads them back.

**Its countdown is its own, measured.** 46047's spectra are stamped at :20 and
:50, not on the hour, and they reach the collection on a different lag from
46232's. Bracketed 2026-10-06 against the collection log -- master's commit
history, since the spectra files carry no first_seen_utc -- for every stamp
from 2026-10-02 20Z, when 46047 joined the hourly collection
(collect-beach-inputs.yml every ten minutes, :05, :15, ... ), to 10-06 00Z.
148 stamps (74 at :20, 73 at :50, one stray :40), each between the last
collection without it and the first with it, in COLLECTION-RUN time (the
commits land ~1.7 min after each run starts; the run is what fetched):

    in the run at   share of stamps   cumulative
        H+15              0%              0%      (absent there every time)
        H+25             56%             56%
        H+35             24%             80%
        H+45             15%             95%
        H+55              3%             98%
        H+85              1%            100%      (10-05 08:20 and 08:50,
                                                   which arrived together)

So it is never fetchable within 15 minutes of its stamp, usually by 25, and
the worst seen is 85 -- the countdown runs to the first and the card turns red
only past the second, as `now.PUBLISH_LAG_MIN` / `PUBLISH_LAG_LATE_MIN` do for
46232 (CLAUDE.md, Infrastructure: the lag is a distribution, two numbers).
Both stamps behave alike (median 26.7 and 30.9 min by commit time). n = 148
over three and a half days; revisit as the archive fills. Before 10-02 the
lag was the collector's, not NDBC's: 46047 was fetched by collect.yml and
first seen a median ~100 min after its stamp.

**46086's, bracketed 2026-10-12 the same way**, from 2026-10-08 03:20Z, when
its wave sensor came back after twelve days dark (2026-09-25 19:20Z, BRIEFING
§38a), to 10-12 02:20Z. It has been in the hourly collection since 10-02, so
every stamp it sent was fetched every ten minutes. 188 stamps (94 at :20, 88
at :50, four :40, two :10):

    in the run at   share of stamps   cumulative
        H+15             13%             13%
        H+25             58%             71%
        H+35             18%             88%
        H+45              7%             95%
        H+55              2%             97%
        H+75              2%             98%
        H+85              1%             99%
       H+105              1%             99%      (10-08 09:50)
       H+115              1%            100%      (10-10 07:50)

Typical 25, worst seen 115. Both stamps alike (median 27.0 and 27.1 min by
commit time). The three past H+85 are NDBC's, not the collector's: every
collection in those hours committed, and 46047's same stamps were as late
(10-10 07:50 at H+125 there) -- which is past 46047's own shipped 85, left
for the owner, as §39 left 46232's 36. n = 188 over four days; revisit as
the archive fills.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR, ISO, utcnow

from . import rose
from .live import station_name
from .now import PUBLISH_MINUTES as ANCHOR_MINUTES
from .now import STALE_HOURS, as_trains, deadline
from .transform import at_buoy, combined_hs, load_spectra
from .units import height as fmt_height

#: The buoys shown under 46232 on the Buoys tab, in order (owner's call).
#: 46086 joined 2026-10-12 (owner's request), its wave sensor back since 10-08
#: after twelve days dark (BRIEFING §38a), under 46047; the owner swapped the
#: two the same day. The Height chart does not follow it: the page reads
#: `heights` by key, and JavaScript orders numeric keys ascending.
STATIONS = ("46086", "46047")

#: When each stamps a spectrum, minutes past the hour. 46047: 2,542 archived
#: stamps (13 Aug - 6 Oct), all on :20 or :50 but for a stray :40 (3 in the
#: newest 200). 46086: 2,335 (11 Aug - 12 Oct), 98.8% on :20 or :50, the rest
#: :40 and :10. Half-hourly, where 46232 is hourly on :00.
PUBLISH_MINUTES = {"46047": (20, 50), "46086": (20, 50)}

#: Minutes from a stamp until the collection that typically has it, and the
#: worst seen -- bracketed in the module docstring, each buoy on its own.
PUBLISH_LAG_MIN = {"46047": 25, "46086": 25}
PUBLISH_LAG_LATE_MIN = {"46047": 85, "46086": 115}

#: What each buoy is, said under its rose (`note`) and in the standing-on
#: line (`windows`). 46047's note is the owner's wording (2026-10-06). The
#: window claims are `forecast.siting`'s verdicts, pinned to it by a test:
#: 46086 is inside South's window and no other, which is why its block may
#: not say "outside every break's windows" as 46047's line does.
WITNESS = {
    "46047": {"note": "Open ocean witness, not carried to any break.",
              "windows": "outside every break's windows"},
    "46086": {"note": "Inside South's window, not carried to any break.",
              "windows": "inside South's window alone"},
}

#: The anchor, whose reading is `forecast.now`'s. Named here only for its
#: rose: a picture of 46232's spectrum at the buoy, carried to no break.
ANCHOR = "46232"

#: How far back buoys.json's heights reach: the LIVE tab's week
#: (`forecast.series`), and a day over so its first hour always has a stamp
#: either side. Older stamps are in buoys_all.json, fetched only when the
#: reader zooms out past the week, as series_all.json is.
HEIGHT_DAYS = 8


def heights(spectra: list, since: datetime | None = None) -> dict:
    """Each spectrum's combined height, at its own stamp, for the Height chart.

    Owner's request, 2026-10-09: 46047 on the LIVE Buoys tab's Height chart,
    beside 46232. Maximum entropy, as the reading above it (`combined_hs` is
    `at_buoy`'s m0 without the trains). At the buoy's OWN stamps -- :20 and
    :50, never moved onto 46232's hours -- as minutes from the first, so the
    page draws each where it was measured and a missing stamp is a gap.
    """

    kept = [sp for sp in spectra if since is None or sp.time >= since]
    if not kept:
        return {"start_utc": None, "t_min": [], "hs_m": []}
    start = kept[0].time
    return {
        "start_utc": start.strftime(ISO),
        "t_min": [round((sp.time - start).total_seconds() / 60.0) for sp in kept],
        "hs_m": [round(combined_hs(sp.with_spread("mem")), 3) for sp in kept],
    }


def all_heights(data_dir: Path, moment: datetime) -> dict:
    """buoys_all.json: every archived stamp's height, for each context buoy."""

    out = {station: heights(_spectra(data_dir, station)) for station in STATIONS}
    return {"generated_utc": moment.strftime(ISO), "spread": "mem", "heights": out}


def roses(data_dir: Path, moment: datetime) -> dict:
    """Each buoy's last six hours of roses, 46232 first (`forecast.rose`).

    Owner's request, 2026-10-06: under each buoy's reading on the Buoys tab, a
    rose redrawn for every spectrum and looped. Maximum entropy, as the reading
    above it. A buoy with no spectrum in the window has no frames; nothing is
    borrowed from the other.
    """

    out: dict = {}
    for station in (ANCHOR, *STATIONS):
        marks = ANCHOR_MINUTES["swell"] if station == ANCHOR else PUBLISH_MINUTES[station]
        spectra = _spectra(data_dir, station)
        recent = [sp.with_spread("mem") for sp in spectra
                  if sp.time > moment - timedelta(hours=rose.WINDOW_HOURS)]
        # The newest spectrum's trains, as the reading above the rose lists
        # them (the same `at_buoy` on the same spectrum), so a tapped row can
        # light its period range in every frame.
        trains = at_buoy(recent[-1]).trains if recent else None
        out[station] = rose.payload(recent, moment, 60.0 / len(marks), trains)
    return out


def _spectra(data_dir: Path, station: str) -> list:
    try:
        return load_spectra(Path(data_dir) / "spectra" / station)
    except (FileNotFoundError, ValueError):
        return []


def reading(station: str, data_dir: Path, moment: datetime) -> dict:
    """One buoy's newest spectrum at the buoy, with no aperture at all."""

    out: dict = {
        "station": station,
        "station_name": station_name(station, data_dir),
        "note": WITNESS.get(station, {}).get("note"),
        "observed_utc": None,
        "age_hours": None,
        "stale": True,
        "stale_hours": STALE_HOURS,
        "next_expected": None,
        "overdue_after": None,
        "warnings": [],
    }
    try:
        spectra = load_spectra(Path(data_dir) / "spectra" / station, limit=1)
    except (FileNotFoundError, ValueError) as exc:
        out["warnings"].append(f"no usable {station} spectrum: {exc}")
        return out
    if not spectra:
        out["warnings"].append(f"no usable {station} spectrum")
        return out

    spectrum = spectra[-1]
    observed = spectrum.time.strftime(ISO)
    age = (moment - spectrum.time).total_seconds() / 3600.0
    marks = PUBLISH_MINUTES.get(station)
    # Maximum entropy, as on every number the LIVE tab shows (owner's
    # decision, 2026-09-25, BRIEFING §28); `at_buoy`, the whole circle with
    # nothing in the way, as 46232's own block is built in `forecast.now`.
    raw = at_buoy(spectrum.with_spread("mem"))
    out.update({
        "observed_utc": observed,
        "age_hours": round(age, 2),
        "stale": age > STALE_HOURS,
        "next_expected": deadline(observed, marks, PUBLISH_LAG_MIN.get(station, 0)),
        "overdue_after": deadline(observed, marks, PUBLISH_LAG_LATE_MIN.get(station, 0)),
        "hs_m": round(raw.hs_m, 3),
        "peak_period_s": None if math.isnan(raw.peak_period_s) else round(raw.peak_period_s, 1),
        "peak_direction_deg": (
            None if math.isnan(raw.peak_direction_deg) else round(raw.peak_direction_deg)
        ),
        "frequency_bins": raw.frequency_bins,
        "trains": as_trains(raw.trains),
    })
    if out["stale"]:
        out["warnings"].append(f"{station}'s newest spectrum is {age:.1f} h old")
    return out


def build(*, data_dir: Path = DEFAULT_DATA_DIR, now: datetime | None = None) -> dict:
    moment = now or utcnow()
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    shown = [reading(station, data_dir, moment) for station in STATIONS]
    return {
        "generated_utc": moment.strftime(ISO),
        "spread": "mem",
        # docs.html renders this under the LIVE tab's own block, from this
        # file: a level of its own, because it feeds none of the others.
        "standing_on": {
            "context buoys": "; ".join(
                f"OBSERVED — NDBC directional spectrum at {b['station']}"
                + (f", {b['station_name']}" if b["station_name"] != b["station"] else "")
                + f" ({WITNESS[b['station']]['windows']})"
                for b in shown
            ) + "; shown at the buoy on the Buoys tab and carried to no break",
        },
        "buoys": shown,
        "roses": roses(data_dir, moment),
        # The context buoys' own heights over the week, for the Height chart.
        "heights": {station: heights(_spectra(data_dir, station),
                                     since=moment - timedelta(days=HEIGHT_DAYS))
                    for station in STATIONS},
    }


def format_table(payload: dict) -> str:
    lines = [f"Context buoys, built {payload['generated_utc']} (carried to no break)"]
    for b in payload["buoys"]:
        head = f"{b['station_name']} ({b['station']})"
        if b.get("hs_m") is None:
            lines.append(f"  {head}: no spectrum. {' '.join(b['warnings'])}")
            continue
        lines.append(f"  {head}: Hs {fmt_height(b['hs_m'])} combined, observed "
                     f"{b['observed_utc']} ({b['age_hours']} h); next expected "
                     f"{b['next_expected']}, late after {b['overdue_after']}")
        for t in b["trains"]:
            lobes = " & ".join(f"{d}° {s:.0%}" for d, s in t["lobes"])
            lines.append(f"    {fmt_height(t['hs_m']):>18}  {t['period_s']:4.1f} s  from "
                         f"{lobes or str(t['from_deg']) + '°'}"
                         + ("  wind sea" if t["wind_sea"] else ""))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    payload = build(data_dir=args.data_dir)
    print(format_table(payload))
    out = args.out or (Path(args.data_dir) / "live" / "buoys.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"\nWrote {out}")
    # Every archived stamp, beside it: ~0.7 s for 46047's two months, and
    # fetched by the page only when the chart is zoomed out past the week.
    whole = all_heights(args.data_dir, datetime.strptime(payload["generated_utc"], ISO)
                        .replace(tzinfo=timezone.utc))
    every = out.with_name("buoys_all.json")
    every.write_text(json.dumps(whole, separators=(",", ":")), encoding="utf-8")
    counts = ", ".join(f"{s}: {len(h['hs_m'])} stamps" for s, h in whole["heights"].items())
    print(f"Wrote {every} ({counts})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
