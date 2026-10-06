"""The context buoys on the LIVE tab's Buoys tab: what each MEASURED, nothing more.

Run: ``python -m forecast.buoys``  (writes ``data/live/buoys.json``)

The Buoys tab (owner's request, 2026-10-06) shows 46232 -- the anchor every
break's card is derived from, read by `forecast.now` -- and under it 46047,
Tanner Banks, the least shadowed buoy in the array. 46047 is shown the way
46232 is at the buoy: the combined height of its directional spectrum read by
maximum entropy, and its wave trains (`transform.at_buoy`, the same peak split
and the same two-direction rule, BRIEFING §38a).

**It is carried to no break, and this module is why that stays true.** 46047
sits 20.7 / 12.8 / 3.4° outside North / Center / South's windows (BRIEFING
§3a); it is the open ocean before the Channel Islands and the Bight, not the
sea at Coronado, and §3a forbids it as a stand-in for 46232. So it is read here
and nowhere on the chain: `forecast.now` and the rest of the forecast path may
not even name it (`tests/test_spectra_collector.py`), this module calls
`at_buoy` and never `through`, `carry` or the surf zone (`tests/test_buoys.py`),
and its file is its own, not a key inside now.json.

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
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR, ISO, utcnow

from .live import station_name
from .now import STALE_HOURS, as_trains, deadline
from .transform import at_buoy, load_spectra
from .units import height as fmt_height

#: The buoys shown under 46232 on the Buoys tab, in order. 46086 is not here:
#: its wave sensor has been dark since 2026-09-25 (BRIEFING §38a).
STATIONS = ("46047",)

#: When 46047 stamps a spectrum, minutes past the hour: 2,542 archived stamps
#: (13 Aug - 6 Oct), all on :20 or :50 but for a stray :40 (3 in the newest
#: 200). Half-hourly, where 46232 is hourly on :00.
PUBLISH_MINUTES = {"46047": (20, 50)}

#: Minutes from a stamp until the collection that typically has it, and the
#: worst seen -- bracketed in the module docstring.
PUBLISH_LAG_MIN = {"46047": 25}
PUBLISH_LAG_LATE_MIN = {"46047": 85}


def reading(station: str, data_dir: Path, moment: datetime) -> dict:
    """One buoy's newest spectrum at the buoy, with no aperture at all."""

    out: dict = {
        "station": station,
        "station_name": station_name(station, data_dir),
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
                for b in shown
            ) + ", shown at the buoy on the Buoys tab; outside every break's windows, "
                "so carried to no break",
        },
        "buoys": shown,
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
