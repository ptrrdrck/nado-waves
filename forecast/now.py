"""What the beaches are getting right now, from observations only.

Run: ``python -m forecast.now`` — writes ``data/live/now.json``.

This is the observed half of the app surface. Every input is a measurement:

===========  =====================================================
waves        NDBC directional spectrum at 46232, ``data/spectra/``
wind         KNZY METAR, ``data/wind/KNZY.csv``
tide         MEASURED water level at 9410170, ``_observed.csv``
===========  =====================================================

`forecast.live` is the modelled half and shares nothing with this but the
geometry. Keeping them apart is the point: a reader can be told which of the
two they are looking at, and the four levels CLAUDE.md asks for come out
differently for each.

**What "now" does and does not mean.** It means *observed at the buoy, then
put through the beach's aperture*. 46232 is 29 km offshore. Nothing here is
shoaled, refracted, or observed at the beach, and `data/beach_log/` is still
empty — so this is not truth about the sand, it is a measurement about the
water the sand is open to. The one thing it removes is the model: no GFS-Wave,
no assumed directional spread (BRIEFING §11's weakest number), because the
spectrum carries measured `r1`/`r2`.

**Stale is not now.** NDBC has served 306-hour-old spectral content behind an
HTTP 200 (BRIEFING §8). A reading older than `STALE_HOURS` is marked stale and
must not be rendered as current; the surface shows the gap instead.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR, ISO, utcnow

from .geometry import (HIGH, LOW, Spot, geometry_line,
                       geometry_provenance, load,
                       swell_windows, window_entry)
from .units import height as fmt_height, speed as fmt_speed
from .live import (
    STATION,
    TIDE_STATION,
    TIDE_STATION_NAME,
    WIND_STATION,
    BREAKS,
    WindAtTime,
    offshore_component,
    read_latest_wind,
    station_name,
    wind_at_break,
    wind_measurement,
)
from .tideturns import read_turns, turns_between
from .transform import Spectrum, at_buoy, load_spectra, through

#: Older than this and the spectrum is not "now". NDBC publishes hourly and the
#: collector runs hourly, so a healthy reading is under two hours old. Three
#: leaves room for one missed run without lying about what it is.
STALE_HOURS = 3.0

#: How long until each measurement on this tab should have been replaced.
#:
#: Two numbers govern it and the slower one wins: how often the SOURCE
#: publishes, and how often this project COLLECTS. A reader cannot see a new
#: number sooner than we fetch it, so promising the source's cadence when the
#: collector runs hourly would be a countdown to nothing.
#:
#: Measured on the archive, 2026-09-22:
#:
#:   swell   NDBC 46232 directional spectra publish hourly; collected hourly.
#:   wind    KNZY publishes its routine METAR at :52 -- 81 of 95 archived
#:           observations sit on that minute; collected hourly at :58.
#:   tide    CO-OPS 9410170 measures every 6 minutes; collected hourly, so the
#:           hour governs. The gap is deliberate: the measured series moves a
#:           median 1.1 cm per 6-minute step, so a sub-hourly fetch would cost
#:           48 extra commits a day to sharpen a number that barely moves.
#:
#: These are what "next update expected" on a card is counting toward. They are
#: an expectation about ARRIVAL, not a promise about the reading's validity --
#: `stale` is the separate claim, and it still wins.
EXPECTED_INTERVAL_MIN = {"swell": 60, "wind": 60, "tide": 60}


def next_expected(observed_utc: str | None, source: str) -> str | None:
    """When `source` should next have replaced the reading taken at `observed_utc`.

    Absolute, never a duration. A "in 42 minutes" frozen into a file rebuilt
    once an hour is wrong for most of the hour it is on screen -- BRIEFING §18,
    which this project has already paid for once. The instant is published and
    the surface counts down to it against the reader's own clock.
    """

    if not observed_utc:
        return None
    minutes = EXPECTED_INTERVAL_MIN.get(source)
    if not minutes:
        return None
    try:
        taken = datetime.strptime(observed_utc, ISO).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None
    return (taken + timedelta(minutes=minutes)).strftime(ISO)

#: How far ahead to carry predicted turns. Two tide cycles is enough that the
#: page can keep answering "the next turn" as turns pass beneath it, without
#: carrying a week of them into a file that describes one moment.
TURN_WINDOW_HOURS = 36


@dataclass
class NowBreak:
    id: str
    name: str
    confidence: str
    #: The arcs swell can arrive through. Static geometry, identical to the
    #: forecast's — carried here so the surface renders one kind of card from
    #: either source rather than reaching across files for it.
    swell_window: list[list[float]]
    #: Offshore energy aimed at this break, as Hs. NOT a height at the beach.
    hs_in_window_m: float
    #: Share of the buoy's total energy that the aperture lets through.
    fraction: float
    #: Peak of the SURVIVING energy — which can be a different wave train from
    #: the buoy's own peak, and that difference is the project's whole claim.
    peak_period_s: float | None
    peak_direction_deg: float | None
    #: The surviving energy split into wave trains, largest first. Which one
    #: leads HERE need not be which leads at the buoy, and need not match the
    #: other two breaks: on 2026-09-19T04:00Z a 7.1 s westerly led at the buoy
    #: and at the south break while a 14.3 s south swell led at north and
    #: centre, on one spectrum.
    trains: list[dict] = field(default_factory=list)
    taken_by: list[dict] = field(default_factory=list)
    wind_offshore: float | None = None
    wind_note: str = ""
    diffraction_suspect: list[str] = field(default_factory=list)


@dataclass
class NowTide:
    """Measured water level — an observation, unlike the forecast's prediction."""

    observed_utc: str | None = None
    height_m: float | None = None
    kind: str = "observed"
    age_minutes: float | None = None
    note: str = ""


@dataclass
class Now:
    generated_utc: str
    #: When the buoy recorded the spectrum this is built from.
    observed_utc: str | None
    age_hours: float | None
    stale: bool
    station: str
    station_name: str
    standing_on: dict
    #: What the aperture itself is standing on: the ENC chart cells the
    #: blockers were read from, and which blockers came from imagery instead.
    #: Station-level, not per break, because one blocker set serves all three —
    #: and structured rather than a sentence so the card can print a
    #: provenance line without the page hardcoding a claim of its own.
    geometry: dict = field(default_factory=dict)
    #: Predicted turning points of the tide. A MODEL, on a tab that is
    #: otherwise measurements only, and named as one everywhere it shows.
    tide_turns: list = field(default_factory=list)
    #: The limit `stale` was decided against, carried so a surface can re-apply
    #: it to the reader's own clock instead of keeping a second copy of it.
    stale_hours: float = STALE_HOURS
    #: When each measurement on this tab should next have been replaced, keyed
    #: by card: `swell`, `wind`, `tide`. Absolute instants, so the surface
    #: counts down against the reader's clock rather than displaying a duration
    #: that was true only at build time (BRIEFING §18).
    #:
    #: Per card rather than one number for the page, because that is the whole
    #: value of it: when all three are collected on the same hourly cycle they
    #: count down together and say little, but when ONE source stops -- 46232
    #: went dark for 16.2 days without the staleness alert visibly firing -- its
    #: card is the only one that runs overdue. A single banner over all three
    #: could not say which.
    next_expected: dict = field(default_factory=dict)
    #: What the buoy itself saw, before any aperture — so a reader can see how
    #: much the geometry changed the answer.
    buoy: dict = field(default_factory=dict)
    wind: WindAtTime = field(default_factory=WindAtTime)
    tide: NowTide = field(default_factory=NowTide)
    tide_station: str = TIDE_STATION
    tide_station_name: str = TIDE_STATION_NAME
    breaks: list[NowBreak] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        return bool(self.breaks) and not self.stale


def read_measured_tide(data_dir: Path, *, now: datetime) -> NowTide:
    """The most recent MEASURED water level, if it is recent enough to be now.

    Not the harmonic prediction. CO-OPS publishes both and
    `collector.tide` keeps them in separate files precisely so that a surface
    claiming to show an observation cannot quietly show a model instead.
    """

    path = Path(data_dir) / "tide" / f"{TIDE_STATION}_observed.csv"
    if not path.exists():
        return NowTide(note="measured water level not collected yet")

    newest: tuple[datetime, float] | None = None
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            stamp, height = row.get("time_utc"), row.get("height_m")
            if not stamp or not height:
                continue
            try:
                when = datetime.strptime(stamp, ISO).replace(tzinfo=timezone.utc)
                value = float(height)
            except ValueError:
                continue
            if newest is None or when > newest[0]:
                newest = (when, value)

    if newest is None:
        return NowTide(note="measured water level file has no usable rows")

    age = (now - newest[0]).total_seconds() / 60.0
    tide = NowTide(
        observed_utc=newest[0].strftime(ISO),
        height_m=round(newest[1], 3),
        age_minutes=round(age, 1),
    )
    # The gauge reports every six minutes. An hour behind is a stalled feed,
    # and a stalled feed reported as "now" is the fault this file exists to
    # avoid, just at a different source.
    if age > 60:
        tide.note = f"last measurement is {age/60:.1f} h old"
    return tide


def as_trains(trains) -> list[dict]:
    return [
        {
            "hs_m": round(t.hs_m, 3),
            "period_s": round(t.period_s, 1),
            "from_deg": None if math.isnan(t.from_deg) else round(t.from_deg),
            "share": round(t.share, 4),
            "wind_sea": t.is_wind_sea,
        }
        for t in trains
    ]


def build(
    *,
    data_dir: Path = DEFAULT_DATA_DIR,
    now: datetime | None = None,
    spectrum: Spectrum | None = None,
) -> Now:
    spots, blockers = load()
    by_id = {s.id: s for s in spots}
    moment = now or utcnow()
    warnings: list[str] = []

    if spectrum is None:
        try:
            spectra = load_spectra(Path(data_dir) / "spectra" / STATION, limit=1)
        except (FileNotFoundError, ValueError) as exc:
            spectra = []
            warnings.append(f"no usable spectrum: {exc}")
        spectrum = spectra[-1] if spectra else None

    reading = Now(
        generated_utc=moment.strftime(ISO),
        observed_utc=spectrum.time.strftime(ISO) if spectrum else None,
        age_hours=None,
        stale=True,
        station=STATION,
        station_name=station_name(STATION, data_dir),
        geometry=geometry_provenance(blockers),
        standing_on={
            "geometry": geometry_line(blockers),
            "waves": f"OBSERVED — NDBC directional spectrum at {STATION}, "
                     f"measured r1/r2, no assumed spread",
            "wind": f"OBSERVED — {WIND_STATION} METAR",
            # Rewritten below once the turn is known: the card carries a measured
        # level AND a predicted turn, and a row claiming the whole thing was
        # observed would be the exact confusion this block exists to prevent.
        "tide": f"OBSERVED — measured water level at {TIDE_STATION}, not a prediction",
            "calibration": "none — no offshore-to-face transfer, no shoaling, no refraction",
            "observation at the beach": "none — data/beach_log/ is empty; "
                                        "nothing has measured these breaks",
            "claim": "observed at a buoy 29 km offshore and put through the beach's "
                     "aperture; not a wave height at the beach, and not verified there",
        },
        warnings=warnings,
    )

    if spectrum is None:
        reading.warnings.append("No spectrum available, so there is no 'now' to show.")
        return reading

    age = (moment - spectrum.time).total_seconds() / 3600.0
    reading.age_hours = round(age, 2)
    reading.stale = age > STALE_HOURS
    if reading.stale:
        reading.warnings.append(
            f"The newest spectrum is {age:.1f} h old, over the {STALE_HOURS:.0f} h "
            f"limit — this is not current and must not be shown as now."
        )

    wind_row = read_latest_wind(data_dir)
    reading.wind = wind_measurement(wind_row)
    if wind_row is None:
        reading.warnings.append(f"{WIND_STATION} wind not collected yet.")
    reading.tide = read_measured_tide(data_dir, now=moment)
    if reading.tide.height_m is None:
        reading.warnings.append(f"{TIDE_STATION} measured water level not available.")

    # The turns the tide is running toward. Predicted, and the only modelled
    # numbers on this tab.
    #
    # A window rather than just the next one, for BRIEFING §18's reason: "the
    # next turn" is relative to NOW, and a single turn baked in at build time
    # would go stale the moment it passed, on a page that may sit open for
    # hours. The surface picks from the list against the reader's own clock.
    turns = turns_between(
        read_turns(data_dir, TIDE_STATION),
        moment, moment + timedelta(hours=TURN_WINDOW_HOURS),
    )
    reading.tide_turns = [t.as_dict() for t in turns]
    if not turns:
        reading.warnings.append(
            f"{TIDE_STATION} predicted high/low turns not collected yet."
        )
    # What each card is counting down to. Computed from the reading each card
    # actually shows, so a source that stops taking readings stops advancing
    # its own expectation and the card goes overdue on its own.
    reading.next_expected = {
        "swell": next_expected(reading.observed_utc, "swell"),
        "wind": next_expected(reading.wind.observed_utc, "wind"),
        "tide": next_expected(reading.tide.observed_utc, "tide"),
    }

    reading.standing_on["tide"] = (
        f"OBSERVED — measured water level at {TIDE_STATION}"
        + ("; the next turn is a harmonic PREDICTION, not a measurement"
           if turns else ", and no predicted turn is collected")
    )

    # What the buoy saw with no aperture at all, so the surface can show how
    # much of the answer is geometry rather than weather. `at_buoy` and not
    # `through(..., [])`: the latter still clips to a spot's seaward half-plane,
    # which dropped 12-26% of the energy out of the train list while leaving the
    # headline Hs whole, so the trains did not sum to the number above them.
    raw = at_buoy(spectrum)
    reading.buoy = {
        "hs_m": round(raw.hs_m, 3),
        "peak_period_s": None if math.isnan(raw.peak_period_s) else round(raw.peak_period_s, 1),
        "peak_direction_deg": (
            None if math.isnan(raw.peak_direction_deg) else round(raw.peak_direction_deg)
        ),
        "frequency_bins": raw.frequency_bins,
        "trains": as_trains(raw.trains),
    }

    for break_id in BREAKS:
        spot: Spot = by_id[break_id]
        got = through(spectrum, spot, blockers)
        offshore, note = wind_at_break(spot, reading.wind)
        reading.breaks.append(NowBreak(
            id=spot.id,
            name=spot.name,
            confidence=HIGH if spot.position_verified else LOW,
            swell_window=[window_entry(w) for w in swell_windows(spot, blockers)],
            hs_in_window_m=round(got.hs_in_window_m, 3),
            fraction=round(got.fraction, 4) if not math.isnan(got.fraction) else None,
            peak_period_s=None if math.isnan(got.peak_period_s) else round(got.peak_period_s, 1),
            peak_direction_deg=(
                None if math.isnan(got.peak_direction_deg) else round(got.peak_direction_deg)
            ),
            trains=as_trains(got.trains),
            taken_by=[
                {"blocker": r.blocker, "share": round(r.share, 4), "verified": r.verified}
                for r in got.removed if r.share >= 0.005
            ],
            wind_offshore=offshore,
            wind_note=note,
            diffraction_suspect=got.diffraction_suspect,
        ))

    return reading


def write(reading: Now, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(reading), indent=1), encoding="utf-8")


def format_table(reading: Now) -> str:
    lines = []
    if reading.observed_utc:
        flag = "  ** STALE **" if reading.stale else ""
        lines.append(f"Coronado now — observed spectrum at {reading.station_name} "
                     f"({reading.station})")
        lines.append(f"  {reading.observed_utc}, {reading.age_hours:.1f} h old{flag}")
    else:
        lines.append("Coronado now — no spectrum available")
    lines.append("")
    for warning in reading.warnings:
        lines.append(f"  ! {warning}")
    if reading.warnings:
        lines.append("")

    if reading.buoy:
        b = reading.buoy
        lines.append(f"the buoy itself:  Hs {fmt_height(b['hs_m'])}, peak {b['peak_period_s']} s "
                     f"from {b['peak_direction_deg']}°  ({b['frequency_bins']} bins)")
    wind = reading.wind
    if wind.measured:
        lines.append(f"wind  {wind.from_deg:.0f}° at {fmt_speed(wind.speed_kt)}   "
                     f"{wind.station_name} ({wind.station}), {wind.observed_utc}")
    tide = reading.tide
    if tide.height_m is not None:
        lines.append(f"tide  {fmt_height(tide.height_m)} MEASURED   {reading.tide_station_name} "
                     f"({reading.tide_station}), {tide.observed_utc}")
    lines.append("")

    if reading.buoy.get("trains"):
        lines.append("swell trains at the buoy:")
        for t in reading.buoy["trains"]:
            lines.append(f"    {fmt_height(t['hs_m']):>16s}  {t['period_s']:5.1f} s  "
                         f"from {t['from_deg']:3}°  {'(wind sea)' if t['wind_sea'] else ''}")
        lines.append("")

    lines.append(f"{'break':10s} {'window Hs':>16s} {'thru':>6s} {'peak T':>7s} {'from':>6s}  wind")
    for entry in reading.breaks:
        # "Coronado Central Beach - north break" truncates to an identical
        # prefix for all three, which is the one thing the table must not do.
        label = entry.name.split("—")[-1].replace("break", "").strip() or entry.id
        sense = ""
        if entry.wind_offshore is not None:
            sense = ("offshore" if entry.wind_offshore > 0.3
                     else "onshore" if entry.wind_offshore < -0.3 else "cross")
        lines.append(
            f"{label:10s} {fmt_height(entry.hs_in_window_m):>16s} "
            f"{100*(entry.fraction or 0):5.0f}% {entry.peak_period_s or 0:6.1f}s "
            f"{entry.peak_direction_deg or 0:5.0f}°  {sense}"
        )
    lines += [
        "",
        "Observed at a buoy 29 km offshore and put through each beach's aperture.",
        "Not shoaled, not refracted, and never measured at the beach itself.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    reading = build(data_dir=args.data_dir)
    print(format_table(reading))

    out = args.out or (Path(args.data_dir) / "live" / "now.json")
    write(reading, out)
    print(f"\nWrote {out}")
    return 0 if reading.usable else 1


if __name__ == "__main__":
    sys.exit(main())
