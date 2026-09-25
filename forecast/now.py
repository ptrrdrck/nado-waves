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

#: When 46232's hourly spectrum actually becomes FETCHABLE, past its own hour.
#:
#: Measured 2026-09-25 by bracketing: for each spectrum hour, the latest
#: collection that did not yet have it and the earliest that did. Three usable
#: brackets, and they do not agree on a minute:
#:
#:     hour        not there at   there at
#:     09-25 01Z      H+0.5         H+15.0
#:     09-24 23Z      H+16.7        H+27.0
#:     09-24 22Z      H+7.0         H+76.7
#:
#: 23Z was still absent at H+16.7 while 01Z had already landed by H+15.0, so
#: publication is not on a schedule -- it jitters across roughly H+7 to H+27.
#:
#: **This is why the trigger is not phase-locked to the swell.** A cadence
#: aligned to one minute would be early on some hours and twenty minutes late
#: on others. Against a jittering source the only thing that bounds staleness
#: is the INTERVAL, so the phase is spent on the one source that is pinned:
#: KNZY's :52 METAR.
SPECTRA_PUBLISHED_MIN = (15, 36)

#: The schedule the external trigger actually keeps, and the cadence the
#: countdown promises. These two must agree; the rest is arithmetic.
#:
#: `5,15,25,35,45,55` -- every ten minutes, offset five. The offset is chosen
#: for the wind: KNZY publishes at :52 and the :55 run catches it three minutes
#: later, against a measured median of 110 minutes before any of this.
#:
#: **The GitHub cron is NOT this schedule.** It is an hourly backstop, and it
#: is deliberately slower: GitHub throttles scheduled runs to about 0.2 an hour
#: whatever is asked (see docs/collection_trigger.md), so a cron written to
#: match this would be a promise GitHub cannot keep.
#:
#: Nothing in this repository can verify the external schedule. A test pins
#: that COLLECT_INTERVAL_MIN matches it and that the backstop cron is not
#: faster; keeping EXTERNAL_TRIGGER_CRON true to what cron-job.org is set to is
#: a human obligation.
EXTERNAL_TRIGGER_CRON = "5,15,25,35,45,55 * * * *"
COLLECT_INTERVAL_MIN = 10

#: WHEN each source publishes, as minutes past the hour. Measured on the
#: archive 2026-09-25, on the newest rows of each file:
#:
#:   swell   spectra stamps, 864 of 864 on :00. Hourly, on the hour.
#:   wind    KNZY routine METAR, 152 of 174 on :52; the rest are SPECIs
#:           between, which arrive early and cost nothing to wait for.
#:   tide    CO-OPS 9410170, every 6 minutes from :00, all ten marks even.
#:
#: 46232 also publishes STANDARD MET at :26 and :56 — a different product, in
#: `data/observations/`, that no card on this page reads. The Now tab's swell
#: is the directional spectrum, and that is hourly.
PUBLISH_MINUTES = {
    "swell": (0,),
    "wind": (52,),
    "tide": tuple(range(0, 60, 6)),
}

#: How long after its own stamp each source is EXPECTED to be fetchable, and
#: how long before it is genuinely LATE. **Two numbers, because one cannot do
#: both jobs.**
#:
#: A stamp minute is not a publication minute for any of the three, and the
#: delay is a distribution rather than a constant. A single value has to choose
#: which end of it to stand on, and both choices are wrong in public:
#:
#:   * the TYPICAL case makes the card red on every cycle that runs late, which
#:     is what "jitter" means -- and a card that cries wolf is the one nobody
#:     reads on the day collection actually dies;
#:   * the WORST case makes the countdown quote a deadline that almost never
#:     applies. The swell sat here: 27 minutes, against a measured typical of
#:     15, so an hourly source was promised 100 minutes from stamp to screen
#:     when 80 was the honest figure. A countdown you learn to discount is not
#:     information either.
#:
#: So the countdown runs to PUBLISH_LAG_MIN and the card only turns red past
#: PUBLISH_LAG_LATE_MIN. Between the two it says the update is due without
#: claiming anything is wrong, which is the truth in that window.
#:
#: **swell, 15 expected / 36 late.** 46232's spectra, bracketed 2026-09-25
#: against the collection log (git history is the first-seen record, since the
#: spectra files carry no first_seen_utc column):
#:
#:     spectrum   absent at   present by
#:     09-24 23Z    H+16.4      H+27.0
#:     09-25 01Z    H+ 0.2      H+15.0
#:     09-25 02Z    H+25.1      H+35.3
#:     09-25 03Z    H+ 5.1      H+15.3
#:     09-25 04Z    H+10.9      H+15.3
#:     09-25 05Z    H+ 5.1      H+15.3
#:
#: Four of six land by H+15 -- three consecutive hours on exactly the same
#: collection -- and 02Z did not appear until H+35.3. The old 27 was neither:
#: twelve minutes pessimistic on the common hour AND still red on 02Z. n = 6,
#: which is thin; revisit as the archive fills.
#:
#: **tide, 5 expected / 8 late.** 9410170 was modelled at 0 on the claim that a
#: :24 sample was in hand by the :25 collection, and the archive falsifies it:
#: no sample has ever been fetchable within 4.9 minutes of its own stamp.
#: Bracketed the same way, 01:36 was in hand by H+4.9 while 00:54 was still
#: absent at H+6.4. Over the window where the 10-minute cadence ran unbroken,
#: first-seen runs H+5.2 to H+13.4, median 9.3.
#:
#: Three minutes is narrower than the collection interval, so the rounding
#: absorbs the difference on 6 of the tide's 10 stamp phases and separates them
#: by one slot on the other 4 -- checked, not assumed. That is a fact about the
#: interval rather than about the tide: change the cadence and the proportion
#: moves.
#:
#: **wind, 3 expected / 4 late.** KNZY's routine METAR at :52, measured floor
#: H+3.2 with one still absent at H+0.7. Three minutes past :52 rounds onto the
#: :55 collection, measured to catch it at :55:15, so the countdown lands where
#: it already did -- but it is now the REASON that works rather than luck, and
#: an offset moved inside three minutes of :52 would say so instead of silently
#: claiming a run catches a METAR it cannot see. The fourth minute crosses the
#: mark, which is the point: it buys the card one collection of grace before it
#: accuses a station that publishes on a pinned minute 81 times in 95.
PUBLISH_LAG_MIN = {"swell": SPECTRA_PUBLISHED_MIN[0], "wind": 3, "tide": 5}
PUBLISH_LAG_LATE_MIN = {"swell": SPECTRA_PUBLISHED_MIN[1], "wind": 4, "tide": 8}


def _collect_minutes() -> tuple[int, ...]:
    """The minutes past the hour the external trigger fires, from its cron."""

    field = EXTERNAL_TRIGGER_CRON.split()[0]
    if field.startswith("*/"):
        return tuple(range(0, 60, int(field[2:])))
    if field == "*":
        return tuple(range(60))
    return tuple(sorted(int(m) for m in field.split(",")))


def _next_mark(after: datetime, minutes: tuple[int, ...]) -> datetime:
    """The first instant STRICTLY after `after` landing on one of `minutes`."""

    t = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    while t.minute not in minutes:
        t += timedelta(minutes=1)
    return t


def _mark_at_or_after(moment: datetime, minutes: tuple[int, ...]) -> datetime:
    """The first instant AT OR AFTER `moment` landing on one of `minutes`."""

    t = moment.replace(second=0, microsecond=0)
    if t < moment:
        t += timedelta(minutes=1)
    while t.minute not in minutes:
        t += timedelta(minutes=1)
    return t


def next_expected(observed_utc: str | None, source: str) -> str | None:
    """When a reading newer than `observed_utc` should be IN THIS FILE.

    Not when a reader sees one. The surface refetches on its own interval and
    adds that leg itself, because this module cannot know it.

    Three steps, each a real event on the clock rather than an interval added
    to the last reading:

        1. the next time this source PUBLISHES, from PUBLISH_MINUTES
        2. plus however long it takes to become fetchable, PUBLISH_LAG_MIN
        3. rounded up to the next COLLECTION, from EXTERNAL_TRIGGER_CRON

    The earlier version added `source interval + 2 x collection interval` to
    the reading on screen, which was wrong in both directions at once. It
    ignored where in its own cycle the source actually was -- a tide sample due
    in ninety seconds got a full six minutes -- and then doubled the collection
    interval as slack. For the tide that produced a countdown over twenty
    minutes for a source that publishes every six, which is what made it
    obviously wrong on screen.

    There is no slack term now. There used to be one because GitHub's scheduler
    delivered about a quarter of what it was asked for, so a card with no
    tolerance was red more often than not. The trigger is external now and
    lands on time to the second, so a missed collection is a real failure and
    the card should say so.

    Absolute, never a duration. A "in 42 minutes" frozen into a file rebuilt
    every ten minutes is wrong for most of the time it is on screen --
    BRIEFING §18, which this project has already paid for once. The instant is
    published and the surface counts down to it against the reader's own clock.
    """

    return _deadline(observed_utc, source, PUBLISH_LAG_MIN)


def overdue_after(observed_utc: str | None, source: str) -> str | None:
    """When a reading newer than `observed_utc` is genuinely LATE.

    The same three steps as `next_expected`, on PUBLISH_LAG_LATE_MIN instead of
    PUBLISH_LAG_MIN. This is the instant a surface may start calling a source
    overdue; `next_expected` is only the instant it stops promising more.

    Between the two the honest report is that the update is due and nothing is
    wrong yet. Collapsing them into one number forces a choice between a card
    that cries wolf on every late cycle and a countdown quoting a deadline that
    almost never applies -- see PUBLISH_LAG_MIN for what each cost.
    """

    return _deadline(observed_utc, source, PUBLISH_LAG_LATE_MIN)


def _deadline(observed_utc: str | None, source: str, lags: dict) -> str | None:
    """`next_expected` and `overdue_after` differ only in which lag they use."""

    if not observed_utc:
        return None
    marks = PUBLISH_MINUTES.get(source)
    if not marks:
        return None
    try:
        taken = datetime.strptime(observed_utc, ISO).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None

    published = _next_mark(taken, marks)
    fetchable = published + timedelta(minutes=lags.get(source, 0))
    return _mark_at_or_after(fetchable, _collect_minutes()).strftime(ISO)


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
    #: The seaward normal, which the page turns to face up when it draws the
    #: windows. Same names as the forecast's, for the same one-card reason.
    shore_normal_deg: float
    normal_is_a_guess: bool
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
    overdue_after: dict = field(default_factory=dict)
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
        geometry=geometry_provenance(blockers, [by_id[b] for b in BREAKS]),
        standing_on={
            "geometry": geometry_line(blockers, [by_id[b] for b in BREAKS]),
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
    # What each card is counting down to, and when it may start calling the
    # source late -- two instants, not one. Computed from the reading each card
    # actually shows, so a source that stops taking readings stops advancing its
    # own expectation and the card goes overdue on its own.
    stamps = {
        "swell": reading.observed_utc,
        "wind": reading.wind.observed_utc,
        "tide": reading.tide.observed_utc,
    }
    reading.next_expected = {k: next_expected(v, k) for k, v in stamps.items()}
    reading.overdue_after = {k: overdue_after(v, k) for k, v in stamps.items()}

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
            shore_normal_deg=round(spot.normal, 1),
            normal_is_a_guess=not spot.shoreline_verified,
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
