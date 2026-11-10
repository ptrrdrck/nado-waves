"""The context buoys on the LIVE tab's Buoys tab: what each MEASURED, nothing more.

Run: ``python -m forecast.buoys``  (writes ``data/live/buoys.json``)

The Buoys tab (owner's request, 2026-10-06) shows 46232 -- the anchor every
break's card is derived from, read by `forecast.now` -- and under it 46086,
San Clemente Basin (owner's request, 2026-10-12), then 46047, Tanner Bank,
the least shadowed buoy in the array (`STATIONS`). Each is shown the way 46232 is at the
buoy: the combined height of its directional spectrum read by maximum
entropy, and its wave trains (`transform.at_buoy`, the same peak split and the
same two-direction rule, BRIEFING §38a).

**They are not carried to any break, and this module is why that stays true.**
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
import csv
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR, ISO, utcnow

from . import rose, siting
from .live import station_name
from .now import PUBLISH_MINUTES as ANCHOR_MINUTES
from .now import PUBLISH_LAG_MIN as ANCHOR_LAG_MIN
from .now import STALE_HOURS, as_trains, deadline
from .transform import STEP_DEG, at_buoy, combined_hs, load_spectra
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

#: What each context buoy's windows are, said in the standing-on line.
#: `forecast.siting`'s verdicts, pinned to it by a test: 46086 is inside
#: South's window and no other, which is why its line may not say "outside
#: every break's windows" as 46047's does.
WITNESS = {
    "46047": {"windows": "outside every break's windows"},
    "46086": {"windows": "inside South's window alone"},
}

#: The anchor, whose reading is `forecast.now`'s. Named here for its rose (a
#: picture of 46232's spectrum at the buoy, not carried to any break) and
#: for the sentence under it.
ANCHOR = "46232"

#: What each buoy is used for here, one line each and each as important as
#: the next (owner's request, 2026-11-10, replacing the one sentence of
#: 2026-10-12 under each rose; its window clause went with it, the owner's
#: call). Typed, because a use is a decision, not a measurement; the
#: standing-on line (`WITNESS`) still says which windows each sits in.
USES = {
    "46232": ("Every break's swell numbers",
              "The Briefing's water temperature when the shark buoys have none"),
    "46086": ("The wind-sea tag, with KNZY's wind",
              "Hurricane track matching"),
    "46047": ("Origin's storm bearings",
              "The Briefing's offshore swell lines",
              "Hurricane track matching"),
}

#: How old a standard-met value may be and still be shown, with its own
#: time, in the station block. Past the page's three hours it greys as every
#: LIVE number does; past this it is not shown at all: a day-old wind is no
#: reading of the buoy now.
STDMET_WITHIN_H = 24

#: NDBC publishes wind in m/s; the page, like the rest of its JSON, takes
#: knots (collector.wavespec converts WAVEWATCH III's the same way).
KT_PER_MS = 1.943844

#: Each buoy's public page: NDBC's station page, 46232's too (owner's
#: request, 2026-11-06, replacing CDIP's page for a buoy CDIP runs).
NDBC_PAGE = "https://www.ndbc.noaa.gov/station_page.php?station={}"

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


def bin_energies(spectrum) -> list[tuple[int, float]]:
    """Each bin's energy over the whole circle, m², as `combined_hs` sums it:
    a maximum-entropy bin's c11 x width, a bin MEM cannot read by the clamped
    Fourier integral. So a mean period from these is the headline's own."""

    steps = max(int(round(360.0 / STEP_DEG)), 1)
    d_theta = 360.0 / steps
    radians_step = math.radians(d_theta)
    out = []
    for index in range(len(spectrum.frequencies)):
        density = spectrum.c11[index]
        if density <= 0.0 or math.isnan(density):
            continue
        width = spectrum.bin_width(index)
        if spectrum.spread == "mem" and spectrum.mem_ok(index):
            out.append((index, density * width))
            continue
        total = 0.0
        for n in range(steps):
            energy = spectrum.density(index, (n + 0.5) * d_theta) * radians_step * width
            if energy > 0.0:
                total += energy
        out.append((index, total))
    return out


def spectrum_reading(spectrum) -> dict:
    """The station block's numbers from one spectrum (owner's request,
    2026-11-10): the peak, as `at_buoy` takes it (the most energetic bin, its
    period and its mean direction from the buoy's own first moment); the mean
    period Tm02 = sqrt(m0 / m2) over the same energies as the headline; and
    the directional spread at the peak, sqrt(2(1 - r1)) in degrees (Kuik et
    al. 1988), which the four moments give whichever way D(θ) is drawn.
    """

    out = {"spectrum_utc": spectrum.time.strftime(ISO), "peak_period_s": None,
           "peak_from_deg": None, "mean_period_s": None, "spread_deg": None}
    energies = bin_energies(spectrum)
    if not energies:
        return out
    f = spectrum.frequencies
    m0 = sum(e for _, e in energies)
    m2 = sum(e * f[i] ** 2 for i, e in energies)
    best, best_energy = max(energies, key=lambda item: item[1])
    if best_energy > 0 and f[best] > 0:
        out["peak_period_s"] = round(1.0 / f[best], 1)
        out["peak_from_deg"] = round(spectrum.a1[best] % 360.0)
    if m0 > 0 and m2 > 0:
        out["mean_period_s"] = round(math.sqrt(m0 / m2), 1)
    r1 = spectrum.r1[best]
    if r1 is not None and not math.isnan(r1) and 0.0 <= r1 <= 1.0:
        out["spread_deg"] = round(math.degrees(math.sqrt(2.0 * (1.0 - r1))))
    return out


def stdmet_reading(station: str, data_dir: Path, moment: datetime) -> dict:
    """The station's standard met as the block shows it: water temperature,
    wind and gust, pressure, each the newest valid value within
    `STDMET_WITHIN_H` with its own time. A column the archive has never held
    a value in is `never` -- 46232 is a Waverider and reports no wind -- so the
    page can say "not measured" rather than "none lately"."""

    from collector.ndbc import is_missing

    columns = {"water": ("wtmp",), "wind": ("wspd", "wdir", "gst"), "pressure": ("pres",)}
    seen = {k: False for k in columns}
    best: dict = {}
    path = Path(data_dir) / "observations" / f"{station}.csv"
    try:
        with path.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
    except FileNotFoundError:
        rows = []
    for row in rows:
        try:
            t = datetime.strptime(row["timestamp_utc"], ISO).replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            continue
        for key, cols in columns.items():
            lead = cols[0]
            token = (row.get(lead) or "").strip()
            if not token or is_missing(lead.upper(), token):
                continue
            seen[key] = True
            if t > moment or moment - t > timedelta(hours=STDMET_WITHIN_H):
                continue
            if key in best and best[key][0] >= t:
                continue
            values = {}
            for col in cols:
                tok = (row.get(col) or "").strip()
                values[col] = (None if not tok or is_missing(col.upper(), tok) else float(tok))
            best[key] = (t, values)
    out: dict = {"never": sorted(k for k, v in seen.items() if not v), "stdmet_within_h": STDMET_WITHIN_H}
    if "water" in best:
        t, v = best["water"]
        out["water_c"], out["water_utc"] = v["wtmp"], t.strftime(ISO)
    if "wind" in best:
        t, v = best["wind"]
        out["wind_kt"] = round(v["wspd"] * KT_PER_MS, 1)
        out["gust_kt"] = None if v["gst"] is None else round(v["gst"] * KT_PER_MS, 1)
        out["wind_from_deg"] = None if v["wdir"] is None else round(v["wdir"])
        out["wind_utc"] = t.strftime(ISO)
    if "pressure" in best:
        t, v = best["pressure"]
        out["pressure_hpa"], out["pressure_utc"] = v["pres"], t.strftime(ISO)
    return out


def cadence(station: str) -> dict:
    """How often the buoy stamps a spectrum and how soon one is usually
    collected: the same measured constants the countdown runs on."""

    if station == ANCHOR:
        marks, lag = ANCHOR_MINUTES["swell"], ANCHOR_LAG_MIN["swell"]
    else:
        marks, lag = PUBLISH_MINUTES[station], PUBLISH_LAG_MIN[station]
    return {"every_min": round(60 / len(marks)), "marks": list(marks), "lag_min": lag}


def about(data_dir: Path, moment: datetime | None = None) -> dict:
    """Each buoy's station block under its rose, as values the page sets.

    Owner's request, 2026-11-10, replacing the one sentence of 2026-10-12:
    the readings (`spectrum_reading`, `stdmet_reading`), then where it is --
    `forecast.siting`'s range and bearing from Center break in kilometres and
    degrees, NDBC's coordinates, and the depth `collector.stationdepth` read
    off NDBC's page -- how often it reports, and what it is used for here.
    Nothing is converted or typed: a buoy siting cannot place has no
    distance, and one whose depth was never read has none.
    """

    from collector.stationdepth import load as load_depths

    moment = moment or utcnow()
    metadata = Path(data_dir) / "station_metadata.csv"
    try:
        placed = {s.station.id: s for s in siting.survey(metadata_path=metadata)}
    except (FileNotFoundError, ValueError):
        placed = {}
    depths = load_depths(data_dir)
    out = {}
    for station in (ANCHOR, *STATIONS):
        sited = placed.get(station)
        newest = _spectra(data_dir, station, limit=1)
        depth = (depths.get(station) or {}).get("depth_m")
        out[station] = {
            "place": station_name(station, data_dir).split(",")[0].strip(),
            "feed": f"NDBC {station}",
            "url": NDBC_PAGE.format(station),
            "range_km": None if sited is None or sited.range_km is None else round(sited.range_km, 2),
            "bearing_deg": None if sited is None or sited.bearing is None else round(sited.bearing, 2),
            "latitude": None if sited is None or sited.latitude is None else round(sited.latitude, 3),
            "longitude": None if sited is None or sited.longitude is None else round(sited.longitude, 3),
            "depth_m": depth,
            "cadence": cadence(station),
            "uses": list(USES[station]),
            "readings": {
                **(spectrum_reading(newest[-1].with_spread("mem")) if newest else {"spectrum_utc": None}),
                **stdmet_reading(station, data_dir, moment),
            },
        }
    return out


def _spectra(data_dir: Path, station: str, limit: int | None = None) -> list:
    try:
        return load_spectra(Path(data_dir) / "spectra" / station, limit=limit)
    except (FileNotFoundError, ValueError):
        return []


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
                + f" ({WITNESS[b['station']]['windows']})"
                for b in shown
            ) + "; shown at the buoy on the Buoys tab and not carried to any break",
        },
        "buoys": shown,
        # The station block under each rose, 46232's included (owner's
        # request, 2026-11-10).
        "about": about(data_dir, moment),
        "roses": roses(data_dir, moment),
        # The context buoys' own heights over the week, for the Height chart.
        "heights": {station: heights(_spectra(data_dir, station),
                                     since=moment - timedelta(days=HEIGHT_DAYS))
                    for station in STATIONS},
    }


def format_table(payload: dict) -> str:
    lines = [f"Context buoys, built {payload['generated_utc']} (not carried to any break)"]
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
