"""The live forecast for Coronado's three breaks.

Run: ``python -m forecast.live`` — writes ``data/live/forecast.json``, which is
what the app surface reads.

Chain: the latest GFS-Wave cycle at 46232 → swell partitions → each partition
integrated through each break's aperture (`forecast.transform`) → recombined by
energy → wind from KNZY and tide from 9410170 attached as context.

**Scope, by decision (2026-09-18): the three Coronado breaks only.** Breakers
and Gator are out of the forecast and out of the app. They are not the same
breaks as Coronado north and south — measured, they differ on 17.6% and 13.5%
of archive swell hours — but they are the two spots whose coordinates are still
estimated, so dropping them costs nothing that was trustworthy.

**What this is standing on, in the four levels CLAUDE.md asks for:**

* *Geometry* — digitised. Coronado's three breaks and the Point Loma tip are
  surveyed points, and the aperture follows from them.
* *Model* — GFS-Wave, unassimilated, with a measured 0.26–0.31 m low bias at
  every lead at these buoys (BRIEFING §5). Not corrected for here: the bias was
  fitted against the BUOY, and correcting a beach forecast with it would import
  a calibration nobody has checked at the beach.
  Whether that bias survives each break's windows is what `forecast.modelbias`
  measures, against the permanent log `main()` appends to
  (`forecast.forecastlog`).
* *Calibration* — **none.** No transfer from Hs to face height, and no band.
  Shoaling, refraction and breaking are modelled physics (`forecast.nearshore`,
  `forecast.surfzone`), fitted to nothing, and are not calibration.
* *Observation* — **none.** `data/beach_log/` is empty. Nothing has ever
  measured a wave at these three breaks.

So the output is a *physically derived* window height, never an accurate one,
and it is not a wave height at the beach. The honest claim is ordinal and
differential: which break holds more of today's swell, and by roughly what
ratio. That is what the verification log is built to test and what this surface
is allowed to say.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR, ISO
from collector import localwind
from collector.gfswave import Bulletin, BulletinError, fetch_bulletin, from_direction
from collector.wavespec import SpecRecord, WaveSpecError, fetch_station_spec, parse_spec

from . import ensemble, forecastlog
from .geometry import (HIGH, LOW, Blocker, Spot, geometry_line, geometry_provenance,
                       load, swell_windows, window_entry)
from .nearshore import (buoy_offset, carry, density_grids, load_tables, local_sea,
                        spectrum_from_partitions,
                        summarise, table_frequencies)
from .units import height as fmt_height, speed as fmt_speed
from .tideturns import read_turns, turns_between
from .surfzone import load_profiles
from .tidesite import (LEAD_MIN, RATIO, SITE_NAME, anomaly, coast_predicted, coast_turn,
                       forecast_level, msl_above_mllw, predicted_series)
from .transform import (
    GridSpectrum,
    at_buoy,
    SEAWARD_CLIP,
    SWELL_SPREAD_DEG,
    WIND_SEA_SPREAD_DEG,
    PartitionsThrough,
    attribution,
    lobes_payload,
    through,
    through_partitions,
)

STATION = "46232"

WIND_STATION = "KNZY"
#: The ICAO identifier's plain-language name. Typed, unlike a buoy coordinate:
#: CLAUDE.md's "never type a buoy coordinate" guards a number that changes the
#: geometry, and this is a label that changes nothing.
WIND_STATION_NAME = "NAS North Island"

TIDE_STATION = "9410170"
TIDE_STATION_NAME = "San Diego, CA"

#: What the nearshore chain stands on, shared by both tabs.
SEABED_LINE = ("MODELLED — refraction, shoaling and bottom friction over the USGS CoNED "
               "and GMRT seabed to 5 m of water off each break; diffraction at the "
               "Coronado Islands, the Point Loma tip and the Baja tangent; linear, "
               "unverified")
SURF_ZONE_LINE = ("MODELLED — Battjes-Janssen breaking straight in from 5 m on the 2016 "
                  "CoNED profile (not this season's sandbars), breaker index from "
                  "Battjes & Stive; depth from {tide} at 9410170 carried to the open "
                  "coast (x0.944, measured against La Jolla); a significant height, "
                  "not a face height")

#: Breaks the app surface covers. Coronado only, by decision.
BREAKS = ("coronado_north", "coronado_center", "coronado_south")

#: How far ahead to publish. GFS-Wave runs to +384 h, but BRIEFING §5 measured
#: the 70% band under-covering badly at +216 h and beyond, and nothing here is
#: banded at all yet. Seven days is where the archive says the model is still
#: saying something.
DEFAULT_HOURS = 168

#: When a cycle should be out. 46232's bulletin landed 5 h 22-27 min after the
#: nominal time on eight cycles measured 2026-09-28/29; one that is later
#: than this is reported as not published yet and the previous run is shown.
CYCLE_LAG_HOURS = 5.5


@dataclass
class WindAtTime:
    """What KNZY measured. One station, so one reading for all three breaks.

    The *measurement* is station-level and lives on the forecast. What each
    break makes of it is not: offshore and onshore are relative to a shore
    normal, and Coronado's three normals span 27° (194.1 / 213.9 / 220.9), so
    the same wind can be cross at the north break and onshore at the south.
    That part stays on the break, as `BreakForecast.wind_offshore`.
    """

    station: str = WIND_STATION
    station_name: str = WIND_STATION_NAME
    observed_utc: str | None = None
    from_deg: float | None = None
    speed_kt: float | None = None
    gust_kt: float | None = None
    note: str = ""

    @property
    def measured(self) -> bool:
        return self.from_deg is not None


@dataclass
class TideAtHour:
    """Water level at one forecast hour. One gauge, so not per break.

    A harmonic PREDICTION, not a measurement — `kind` carries which, and the
    surface has to say so. `collector.tide` keeps the two in separate files for
    the same reason.
    """

    valid_utc: str
    height_m: float | None = None
    kind: str | None = None
    #: How much of `height_m` is the gauge's measured departure from its
    #: prediction, carried forward, on the open coast. None when none was
    #: added: an hour logged before 2026-09-27, or no departure measured.
    departure_m: float | None = None


@dataclass
class Hour:
    valid_utc: str
    lead_h: int
    hs_offshore_m: float
    hs_window_m: float
    fraction: float
    dominant_period_s: float | None
    dominant_from_deg: float | None
    #: The model's own 10 m wind at the buoy for this hour, degrees FROM.
    #: From the same WAVEWATCH III file as the spectrum, so no second source.
    wind_from_deg: float | None = None
    wind_kt: float | None = None
    #: The LOCAL forecast wind on the sand at this hour (the NWS San Diego
    #: forecast grid at Coronado, `collector.localwind`), degrees FROM, and
    #: what it means at this break against its own shore normal: +1 straight
    #: offshore, -1 straight onshore. None where the grid had no hour or the
    #: build could not reach it. The model's wind above stays the buoy's.
    local_wind_from_deg: float | None = None
    local_wind_kt: float | None = None
    local_gust_kt: float | None = None
    local_wind_offshore: float | None = None
    #: The surviving energy split into wave trains, largest first. Only on the
    #: spectral path — partitions arrive pre-split and are not re-split here.
    trains: list[dict] = field(default_factory=list)
    #: Share of the offshore energy each blocker took, largest first. The app
    #: reads this to say WHAT is taking the swell, and to mark a reading whose
    #: dominant blocker is the estimated Coronado Islands as less certain than
    #: one governed by the digitised Point Loma tip.
    taken_by: list[dict] = field(default_factory=list)
    #: The number the card shows: the modelled spectrum carried over the
    #: seabed to 5 m of water off the break, with local chop from the model's
    #: own wind, then in to where it breaks at the hour's tide (the 5 m figure
    #: when the tide is not available). `hs_window_m` stays the straight-line
    #: window figure, and
    #: `nearshore.effects` is the chain between them (forecast.nearshore).
    hs_nearshore_m: float | None = None
    nearshore: dict = field(default_factory=dict)


@dataclass
class BreakForecast:
    id: str
    name: str
    confidence: str
    #: The arcs swell can actually arrive through — every edge blocker-derived.
    #: Three of them since 2026-09-20: the south window between the Baja coast
    #: and the southern Coronado Islands, the 6° channel between the two
    #: islands, and the west window out to the Point Loma tip. It used to be
    #: one, because the south-east arc ran across a Baja coastline that was not
    #: modelled and `swell_windows` rightly withheld it. Charting that coast is
    #: what let it be published (BRIEFING §12, §24).
    swell_window: list[list[float]]
    shore_normal_deg: float
    normal_is_a_guess: bool
    #: What the station-level wind means AT THIS BREAK: +1 straight offshore,
    #: −1 straight onshore. Derived from this break's normal, so it differs
    #: across the three even though the wind does not.
    wind_offshore: float | None = None
    #: Why that number is shakier here than the window is. The normal comes
    #: from the shoreline chord, and Coronado's north break has a digitised
    #: position with an unverified chord (BRIEFING §2a).
    wind_note: str = ""
    hours: list[Hour] = field(default_factory=list)


@dataclass
class Forecast:
    generated_utc: str
    cycle_utc: str | None
    station: str
    #: The buoy's name as NDBC publishes it, via data/station_metadata.csv.
    #: Read rather than typed — CLAUDE.md keeps station facts fetched.
    station_name: str
    standing_on: dict
    #: What the aperture itself is standing on: the ENC chart cells the
    #: blockers were read from, and which blockers came from imagery instead.
    #: Station-level, not per break, because one blocker set serves all three —
    #: and structured rather than a sentence so the card can print a
    #: provenance line without the page hardcoding a claim of its own.
    geometry: dict = field(default_factory=dict)
    #: What the model says the buoy will see, per hour, before any aperture.
    #: Station-level like the wind and tide: one buoy, not three.
    buoy: list[dict] = field(default_factory=list)
    #: Station-level context, hoisted off the breaks because one station feeds
    #: all three and repeating it three times is noise, not information.
    wind: WindAtTime = field(default_factory=WindAtTime)
    tide: list[TideAtHour] = field(default_factory=list)
    #: Predicted turning points across the forecast window, so a surface can
    #: say which way the tide is running at the hour on screen without
    #: differencing the hourly series — which locates a turn up to 29.4 min
    #: out (measured). One entry past the window, because the last hour still
    #: has a next turn and it lies beyond the window by definition.
    tide_turns: list[dict] = field(default_factory=list)
    tide_station: str = TIDE_STATION
    tide_station_name: str = TIDE_STATION_NAME
    #: Where the Tide card's numbers are: the gauge carried to the beach.
    tide_site: str = SITE_NAME
    #: Measured minus predicted at the gauge over the last 3 days, carried
    #: forward into the depth the waves break in. None when not computed.
    tide_departure_m: float | None = None
    breaks: list[BreakForecast] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    #: "spectrum" when the model's own directional grid was available, and
    #: "partitions" when it fell back. The two differ by under 6% through the
    #: aperture (measured), but they stand on different things and the surface
    #: is entitled to say which.
    wave_source: str = "partitions"
    spread_assumption: dict = field(default_factory=dict)
    #: What the page showed for each offered hour in the 48 h before this
    #: build, read back from the permanent log (`forecast.forecastlog`): per
    #: hour, the latest build generated at or before it. Headline numbers only
    #: -- the log does not keep the detail an earlier card carried.
    past: list[dict] = field(default_factory=list)
    #: What each of the last few model runs said, from the same log, for the
    #: Forecast tab's Runs chart (`forecastlog.recent_runs`): one line per run,
    #: never merged into a range or a band.
    runs: list[dict] = field(default_factory=list)
    #: GEFS-Wave's 31 members at the buoy -- their mean and spread, and how
    #: often 46232 has fallen inside that spread (`forecast.ensemble`). Total
    #: Hs only: no direction, so nothing of it reaches a break.
    ensemble: dict = field(default_factory=dict)
    #: Whose local wind forecast the hours carry, when it was issued, or why
    #: there is none (`collector.localwind`); the hours themselves are on
    #: each break's `Hour`.
    local_wind: dict = field(default_factory=dict)
    #: Every HOUR from the earliest past hour to the run's end, for the
    #: Wind and Tide cards' charts, which draw hourly where the cards step
    #: every third: the open coast's predicted tide (with the departure, as
    #: `tide` carries it) and the local wind forecast, as columns from
    #: `start_utc`. None where there is nothing for an hour. The publisher
    #: does not thin it: it is already the one row per hour the chart draws.
    hourly: dict = field(default_factory=dict)


def hourly_columns(rows, past: list[dict], bay_predicted, departure: float | None,
                   local_hours: dict[str, dict],
                   model_wind: dict[datetime, tuple[float, float]] | None = None) -> dict:
    """`Forecast.hourly`: one value an hour from the earliest past hour the
    page offers to the run's last, never filled across an hour missing.

    `model_wind` is GFS-Wave's own 10 m wind at the buoy, by valid time, for
    the hours the run carries: every hour to +120 h and every third after, so
    its column has holes the model never filled, and the page joins across
    them rather than calling them gaps."""

    start = rows[0].valid_utc
    if past:
        start = min(start, datetime.strptime(past[0]["valid_utc"], ISO).replace(tzinfo=timezone.utc))
    marks = []
    t = start
    while t <= rows[-1].valid_utc:
        marks.append(t)
        t += timedelta(hours=1)
    tide, wind_from, wind_kt, gust = [], [], [], []
    model_from, model_kt = [], []
    for t in marks:
        model = (model_wind or {}).get(t)
        model_kt.append(None if model is None or model[0] is None else round(model[0], 1))
        model_from.append(None if model is None or model[1] is None else round(model[1]) % 360)
        value = coast_predicted(bay_predicted, t, departure)
        tide.append(None if value is None else round(value, 3))
        local = local_hours.get(t.strftime(ISO))
        wind_from.append(None if not local or local.get("from_deg") is None
                         else round(local["from_deg"]) % 360)
        wind_kt.append(None if not local or local.get("speed_kt") is None
                       else round(local["speed_kt"], 1))
        gust.append(None if not local or local.get("gust_kt") is None else round(local["gust_kt"], 1))
    from . import daylight

    return {"start_utc": start.strftime(ISO), "step_h": 1, "tide_m": tide,
            # Night across the same hours, for the Tide chart's shading.
            "nights": daylight.nights(start, marks[-1]),
            "local_wind": {"from_deg": wind_from, "kt": wind_kt, "gust_kt": gust},
            "model_wind": {"from_deg": model_from, "kt": model_kt}}


def latest_cycle(now: datetime | None = None) -> datetime:
    """The most recent cycle that should have been published by now."""

    now = now or datetime.now(timezone.utc)
    anchor = now - timedelta(hours=CYCLE_LAG_HOURS)
    return anchor.replace(hour=(anchor.hour // 6) * 6, minute=0, second=0, microsecond=0)


def fetch_latest(station: str = STATION, *, now: datetime | None = None,
                 back: int = 4) -> tuple[Bulletin | None, list[str]]:
    """Walk back through cycles until one is available."""

    warnings: list[str] = []
    late: list[datetime] = []
    cycle = latest_cycle(now)
    for step in range(back):
        attempt = cycle - timedelta(hours=6 * step)
        try:
            bulletin = fetch_bulletin(station, attempt, attempts=2)
        except BulletinError as exc:
            if exc.status == 404:
                late.append(attempt)
            warnings.append(f"cycle {attempt:%Y-%m-%dT%H}Z unavailable: {str(exc)[-80:]}")
            continue
        # A newer run that 404'd is, on every cycle measured, one NCEP has not
        # finished publishing: 46232's bulletin lands ~5 h 25 min after the
        # nominal time and the directory fills over an hour. Say that, in the
        # page's words, rather than print the URL that 404'd -- which read as
        # the layout having moved (2026-09-30) when the run was only late.
        # Any other failure keeps its technical line.
        warnings = [w for w in warnings if not any(f"{c:%Y-%m-%dT%H}Z" in w for c in late)]
        if late:
            runs = " and ".join(f"{c:%H}Z" for c in sorted(late, reverse=True))
            warnings.insert(0, f"GFS-Wave's {runs} run{'s are' if len(late) > 1 else ' is'} "
                               f"not published yet; showing the {attempt:%H}Z run.")
        return bulletin, warnings
    return None, warnings


def fetch_spectra(
    cycle: datetime, *, hours: int, station: str = STATION
) -> tuple[dict[datetime, SpecRecord], str | None]:
    """The model's own directional spectra for this cycle, keyed by valid time.

    `build(use_spectra=...)` defaults to False so that fetching 617 MB is an
    explicit act. It is opted into by `main()` and by the workflow; a test that
    injects a bulletin gets no network at all. Before that default flipped, the
    suite took 122 seconds and made one download per test.

    Returns ({} , reason) when unavailable — a missing spectral product must
    fall back to partitions rather than stop the forecast. Measured cost:
    617 MB and about ten seconds, because the stream is abandoned once 46232
    is found (`collector.wavespec`).
    """

    try:
        text, _read = fetch_station_spec(station, cycle)
        return {r.time: r for r in parse_spec(text, limit_hours=hours)}, None
    except WaveSpecError as exc:
        return {}, str(exc)[-120:]


def read_latest_wind(data_dir: Path, *, until: datetime | None = None) -> dict[str, str] | None:
    """The newest KNZY row; with `until`, the newest taken at or before it."""

    path = Path(data_dir) / "wind" / f"{WIND_STATION}.csv"
    if not path.exists():
        return None
    bound = until.strftime(ISO) if until is not None else None
    with path.open(newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r.get("observed_utc")
                and (bound is None or r["observed_utc"] <= bound)]
    return max(rows, key=lambda r: r["observed_utc"]) if rows else None


def station_name(station: str, data_dir: Path) -> str:
    """The buoy's name from the fetched metadata, or its id if unplaced."""

    try:
        from collector.metadata import load_metadata

        record = load_metadata(Path(data_dir)).get(station)
        if record and record.name:
            return record.name
    except Exception:  # noqa: BLE001 — a missing name must not stop a forecast
        pass
    return station


def read_tide(data_dir: Path) -> dict[str, tuple[float, str]]:
    """Predicted tide by hour. Empty when the collector has not run."""

    out: dict[str, tuple[float, str]] = {}
    path = Path(data_dir) / "tide" / f"{TIDE_STATION}_predicted.csv"
    if not path.exists():
        return out
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            stamp, height = row.get("time_utc"), row.get("height_m")
            if not stamp or not height:
                continue
            try:
                out[stamp[:13]] = (float(height), row.get("kind", "predicted"))
            except ValueError:
                continue
    return out


def offshore_component(wind_from_deg: float, normal_deg: float) -> float:
    """+1 when the wind blows straight off the land, −1 straight onshore.

    The beach normal points seaward, so a wind arriving FROM the normal is
    coming off the water. Offshore is the opposite bearing, hence the sign.
    """

    return -math.cos(math.radians(wind_from_deg - normal_deg))


def wind_measurement(row: dict[str, str] | None) -> WindAtTime:
    """What the station recorded. Nothing here depends on a beach."""

    if row is None:
        return WindAtTime(note=f"{WIND_STATION} not collected yet — run the "
                               f"'Collect beach inputs' workflow")
    if row.get("variable") == "1" or not row.get("wind_from_deg"):
        return WindAtTime(
            observed_utc=row.get("observed_utc"),
            speed_kt=float(row["wind_kt"]) if row.get("wind_kt") else None,
            note="variable or calm — no usable direction",
        )
    return WindAtTime(
        observed_utc=row.get("observed_utc"),
        from_deg=float(row["wind_from_deg"]),
        speed_kt=float(row["wind_kt"]) if row.get("wind_kt") else None,
        gust_kt=float(row["gust_kt"]) if row.get("gust_kt") else None,
    )


def wind_at_break(spot: Spot, wind: WindAtTime) -> tuple[float | None, str]:
    """What that wind means at this break, and how much to trust it.

    Returns (offshore component, caveat). The component is the only part of the
    wind that is genuinely per-break: it comes from the shore normal, and the
    three normals span 29°, so one wind can be cross at the north break and
    onshore at the south.
    """

    if not wind.measured:
        return None, ""
    note = ""
    if not spot.shoreline_verified:
        # The normal comes from the chord. An unverified chord - an estimate,
        # as Breakers' and Gator's still are - leaves the window's provenance
        # intact and this reading a guess. (Coronado's north break carried
        # this flag for an imagery splice until its chord was read off the
        # ENC on 2026-09-22, BRIEFING §27.)
        note = "shore normal unverified here, so offshore/onshore is a guess"
    return round(offshore_component(wind.from_deg, spot.normal), 3), note


def _blocker_verified(name: str, spot: Spot, blockers: list[Blocker]) -> bool:
    """Is this blocker's edge drawn between two digitised points?

    The seaward clip is a chord claim, not a blocker claim, so it follows
    `shoreline_verified` (BRIEFING §2a: the two flags govern different things).
    """

    if name == SEAWARD_CLIP:
        return spot.shoreline_verified
    for blocker in blockers:
        if blocker.name == name:
            return blocker.tip_verified and spot.position_verified
    return False


def confidence_for(spot: Spot, blockers: list[Blocker]) -> str:
    if not spot.position_verified:
        return LOW
    # Both edges of the swell-side window are blocker-derived, so the window is
    # a function of position and the blockers and NOT of the chord (BRIEFING
    # section 2a). Point Loma is digitised; the islands are not, but they carry
    # ~11% of the energy (section 10), below the material share.
    return HIGH


def build(
    *,
    data_dir: Path = DEFAULT_DATA_DIR,
    hours: int = DEFAULT_HOURS,
    now: datetime | None = None,
    bulletin: Bulletin | None = None,
    spectra: dict | None = None,
    use_spectra: bool = False,
    local_wind: dict | None = None,
) -> Forecast:
    spots, blockers = load()
    by_id = {s.id: s for s in spots}
    warnings: list[str] = []

    if bulletin is None:
        bulletin, warnings = fetch_latest(now=now)

    generated = (now or datetime.now(timezone.utc)).strftime(ISO)
    forecast = Forecast(
        generated_utc=generated,
        cycle_utc=bulletin.cycle_utc.strftime(ISO) if bulletin else None,
        station=STATION,
        station_name=station_name(STATION, data_dir),
        geometry=geometry_provenance(blockers, [by_id[b] for b in BREAKS]),
        standing_on={
            "geometry": geometry_line(blockers, [by_id[b] for b in BREAKS]),
            "model": "GFS-Wave, unassimilated; 0.9–1.0 ft (0.26–0.31 m) low bias at the buoy, not corrected here",
            "seabed": SEABED_LINE,
            "local chop": "MODELLED — fetch-limited growth from the local forecast wind (the "
                          "NWS grid at Coronado; the model's wind at the buoy only for an hour "
                          "the grid did not give): fresh over water closed by land, and grown "
                          "on from the carried wind sea over the open water between the buoy "
                          "and the break",
            "tide": f"PREDICTED — the harmonic prediction at {TIDE_STATION}, inside San "
                    f"Diego Bay, plus the last 3 days' measured departure from it when there "
                    f"is one, carried to Coronado's open coast (x{RATIO:.3f} on MLLW, "
                    f"{LEAD_MIN} min earlier, measured against La Jolla)",
            "surf zone": SURF_ZONE_LINE.format(
                tide="the harmonic prediction plus the last 3 days' measured departure"),
            "calibration": "none — nothing has been fitted to an observation; "
                           "no offshore-to-face transfer, no band",
            "observation": "none — data/beach_log/ is empty; nothing has measured these breaks",
            "claim": "physically derived, not accurate; ordinal and differential, not a height at the beach",
        },
        warnings=warnings,
        spread_assumption={
            "swell_deg": SWELL_SPREAD_DEG,
            "wind_sea_deg": WIND_SEA_SPREAD_DEG,
            "note": "GFS-Wave publishes no directional spread. These are conventional "
                    "values, not fitted ones, and are replaced by measured r1/r2 once "
                    "collector.spectra has a series.",
        },
    )

    # Before this build is logged, so the past is only what earlier builds said.
    # Each with the full hour its own build showed, where that was kept. A
    # build is picked only for hours after it was published, and keeps them
    # up to 48 h ahead, so builds up to 96 h old can still be the one shown.
    since = (datetime.strptime(generated, ISO)
             - timedelta(hours=forecastlog.PAST_HOURS)).strftime(ISO)
    logged = forecastlog.read(forecastlog.log_dir(data_dir))
    forecast.past = forecastlog.past_hours(
        logged, generated,
        shown=forecastlog.read_shown(forecastlog.shown_dir(data_dir), since=since))
    # The earlier runs, never this one: a rebuild of the same cycle is this run.
    forecast.runs = forecastlog.recent_runs(logged, forecast.cycle_utc or generated)
    # The ensemble at the buoy, from the archive the workflow has just topped
    # up (collector.gefswave): the newest cycle at or before this run, over
    # this run's hours, with its measured coverage beside it.
    try:
        rows, matched = ensemble.load(data_dir, spread_only=True)
        until = ((datetime.strptime(forecast.cycle_utc, ISO) + timedelta(hours=hours)).strftime(ISO)
                 if forecast.cycle_utc else None)
        forecast.ensemble = ensemble.for_forecast(rows, matched, forecast.cycle_utc,
                                                  until_utc=until)
    except (OSError, ValueError, KeyError) as error:
        forecast.ensemble = {"available": False, "why": f"the ensemble archive could not be read: {error}"}

    if bulletin is None:
        forecast.warnings.append("No GFS-Wave cycle available; no forecast produced.")
        return forecast

    # The local wind forecast, by hour: what `main` fetched, if anything.
    local_hours = {h["valid_utc"]: h for h in ((local_wind or {}).get("hours") or [])}
    forecast.local_wind = ({k: v for k, v in local_wind.items() if k != "hours"} | {"available": bool(local_hours)}
                           if local_wind else {"available": False, "why": "not fetched for this build"})
    if local_hours:
        forecast.standing_on["local wind"] = (
            "FORECAST — the National Weather Service's hourly forecast grid at Coronado's "
            f"center break ({forecast.local_wind.get('office') or 'NWS'} "
            f"{forecast.local_wind.get('grid_x')},{forecast.local_wind.get('grid_y')}): the wind "
            "on the sand the offshore reading is made from; not the model's wind at the buoy, "
            "and not a measurement")

    wind_row = read_latest_wind(data_dir)
    tide = read_tide(data_dir)
    # The card's tide is the gauge's prediction carried to the open coast
    # (forecast.tidesite): the height on the coast's MLLW, 3 min earlier.
    bay_predicted = predicted_series(data_dir)
    forecast.wind = wind_measurement(wind_row)
    if wind_row is None:
        forecast.warnings.append(f"{WIND_STATION} wind not collected yet.")
    if not tide:
        forecast.warnings.append(f"{TIDE_STATION} tide not collected yet.")
    # The gauge has run ~0.2 m above its 1983-2001 epoch prediction (BRIEFING
    # §32), so the forecast carries the last three days' measured departure
    # forward. Breaking has always used it; the card, its turns and its depth
    # now use the same one, so the Tide card shows the level the swell was
    # computed at rather than a bare prediction ~9 in under it. None when the
    # gauge measured nothing in that window: then the card is the bare
    # prediction, it says so by omission, and there is no breaking.
    departure, _ = anomaly(data_dir, datetime.strptime(generated, ISO)
                           .replace(tzinfo=timezone.utc))
    if departure is not None:
        forecast.tide_departure_m = round(departure, 3)
    all_turns = [coast_turn(t, departure) for t in read_turns(data_dir, TIDE_STATION)]
    if not all_turns:
        forecast.warnings.append(
            f"{TIDE_STATION} predicted high/low turns not collected yet."
        )

    rows = [r for r in bulletin.rows if r.lead_hours <= hours]

    # The model's own directional grid, when it can be had: it carries a real
    # directional spread where the partitions need one assumed.
    if spectra is None and use_spectra:
        spectra, reason = fetch_spectra(bulletin.cycle_utc, hours=hours)
        if reason:
            forecast.warnings.append(f"spectral product unavailable ({reason}); using partitions")
    spectra = spectra or {}
    forecast.wave_source = "spectrum" if spectra else "partitions"
    forecast.standing_on["model"] = (
        "GFS-Wave, unassimilated; 0.9–1.0 ft (0.26–0.31 m) low bias at the buoy, not corrected here"
        + ("; its own directional spectrum, so no assumed spread"
           if spectra else "; swell partitions with an assumed directional spread")
    )
    if spectra:
        forecast.spread_assumption = {
            "note": "not used — the model's directional spectrum carries its own spread"
        }

    # One gauge, so the tide series is station-level and sits beside the breaks
    # rather than being repeated inside each of them.
    for row in rows:
        record = spectra.get(row.valid_utc)
        if record is not None:
            view = at_buoy(GridSpectrum(record.time, record.frequencies,
                                        record.directions, record.energy))
            forecast.buoy.append({
                "valid_utc": row.valid_utc.strftime(ISO),
                "hs_m": round(view.hs_m, 3),
                "peak_period_s": (None if math.isnan(view.peak_period_s)
                                  else round(view.peak_period_s, 1)),
                "peak_direction_deg": (None if math.isnan(view.peak_direction_deg)
                                       else round(view.peak_direction_deg)),
                "frequency_bins": view.frequency_bins,
                "trains": [
                    {"hs_m": round(t.hs_m, 3), "period_s": round(t.period_s, 1),
                     "from_deg": None if math.isnan(t.from_deg) else round(t.from_deg),
                     "share": round(t.share, 4), "wind_sea": t.is_wind_sea,
                     "lobes": lobes_payload(t)}
                    for t in view.trains[:3]
                ],
            })

        value = coast_predicted(bay_predicted, row.valid_utc, departure)
        forecast.tide.append(TideAtHour(
            valid_utc=row.valid_utc.strftime(ISO),
            height_m=round(value, 3) if value is not None else None,
            kind="predicted" if value is not None else None,
            departure_m=(round(RATIO * departure, 3)
                         if value is not None and departure is not None else None),
        ))

    if rows and all_turns:
        # From the earliest past hour too, or a past card's tide line would
        # name the first turn of THIS run rather than the one after its hour.
        start = rows[0].valid_utc
        if forecast.past:
            start = min(start, datetime.strptime(forecast.past[0]["valid_utc"], ISO)
                        .replace(tzinfo=timezone.utc))
        forecast.tide_turns = [
            t.as_dict() for t in turns_between(all_turns, start, rows[-1].valid_utc)
        ]

    if rows:
        forecast.hourly = hourly_columns(
            rows, forecast.past, bay_predicted, departure, local_hours,
            {t: (r.wind_kt, r.wind_from_deg) for t, r in spectra.items()})

    try:
        tables = load_tables()
    except (FileNotFoundError, ValueError) as exc:
        tables = {}
        forecast.warnings.append(f"nearshore tables unavailable ({exc}); showing window energy")
    freqs = table_frequencies(tables)

    # The tide at the open coast for each hour: the bay's prediction carried
    # through the measured transfer, plus the departure the gauge has measured
    # from that prediction over the last three days (persistence — the epoch
    # prediction alone put every break ~0.2 m too shallow, BRIEFING §32). No
    # measured departure, no breaking: the 5 m figure is shown instead.
    profiles, tide_series, msl = {}, [], None
    if tables:
        try:
            profiles = load_profiles()
            msl = msl_above_mllw(data_dir)
            tide_series = predicted_series(data_dir)
        except (FileNotFoundError, KeyError, ValueError) as exc:
            profiles = {}
            forecast.warnings.append(f"surf zone unavailable ({exc}); no breaking")
        if profiles and departure is None:
            profiles = {}
            forecast.warnings.append(f"no measured departure from the {TIDE_STATION} "
                                     "prediction in the last 3 days; no breaking")

    # One spectrum per hour, shared by the three breaks: the model's own grid
    # when there is one, otherwise the partitions rebuilt into a spectrum and
    # read by maximum entropy like the observed buoy.
    carried_input: dict = {}
    if tables:
        for row in rows:
            record = spectra.get(row.valid_utc)
            if record is not None:
                sp = GridSpectrum(record.time, record.frequencies, record.directions, record.energy)
                wind = (record.wind_kt, record.wind_from_deg)
            else:
                parts = [(p.hs_m, p.tp_s, float(from_direction(p.toward_deg)), p.wind_sea)
                         for p in row.partitions]
                sp = spectrum_from_partitions(parts, row.valid_utc, freqs)
                wind = (None, None)
            carried_input[row.valid_utc] = (sp, density_grids(sp), wind)
    # Where the buoy sits from each break: how much water the buoy's spectrum
    # has not seen, along a given wind (`nearshore.local_sea`).
    buoy_offsets = {b: buoy_offset(by_id[b].position) for b in BREAKS}

    for break_id in BREAKS:
        spot = by_id[break_id]
        entry = BreakForecast(
            id=spot.id,
            name=spot.name,
            confidence=confidence_for(spot, blockers),
            swell_window=[window_entry(w) for w in swell_windows(spot, blockers)],
            shore_normal_deg=round(spot.normal, 1),
            normal_is_a_guess=not spot.shoreline_verified,
        )
        entry.wind_offshore, entry.wind_note = wind_at_break(spot, forecast.wind)

        for row in rows:
            record = spectra.get(row.valid_utc)
            if record is not None:
                grid = GridSpectrum(record.time, record.frequencies,
                                    record.directions, record.energy)
                survived = through(grid, spot, blockers)
                hs_offshore = survived.hs_total_m
                hs_window = survived.hs_in_window_m
                fraction = survived.fraction
                dominant_tp = (None if math.isnan(survived.peak_period_s)
                               else round(survived.peak_period_s, 1))
                dominant_dir = (None if math.isnan(survived.peak_direction_deg)
                                else round(survived.peak_direction_deg))
                shares = {r.blocker: r.share for r in survived.removed}
                hour_wind_deg = round(record.wind_from_deg)
                hour_wind_kt = round(record.wind_kt, 1)
                hour_trains = [
                    {"hs_m": round(t.hs_m, 3), "period_s": round(t.period_s, 1),
                     "from_deg": None if math.isnan(t.from_deg) else round(t.from_deg),
                     "share": round(t.share, 4), "wind_sea": t.is_wind_sea,
                     "lobes": lobes_payload(t)}
                    for t in survived.trains[:3]
                ]
            else:
                parts = [
                    (p.hs_m, p.tp_s, float(from_direction(p.toward_deg)), p.wind_sea)
                    for p in row.partitions
                ]
                got: PartitionsThrough = through_partitions(spot, blockers, parts)
                dominant = got.dominant
                hs_offshore = got.hs_offshore_m
                hs_window = got.hs_in_window_m
                fraction = got.fraction
                dominant_tp = round(dominant.tp_s, 1) if dominant else None
                dominant_dir = round(dominant.from_deg) if dominant else None
                hour_wind_deg = hour_wind_kt = None
                hour_trains = []
                shares = {}

                # Energy-weighted across partitions: a blocker shadowing a
                # small train matters less than one shadowing the main swell.
                energy = sum(p.hs_offshore_m ** 2 for p in got.parts) or 1.0
                for part in got.parts:
                    weight = part.hs_offshore_m ** 2 / energy
                    for name, share in attribution(
                        spot, blockers, part.from_deg, part.spread_deg
                    ).items():
                        shares[name] = shares.get(name, 0.0) + weight * share

            taken_by = [
                {
                    "blocker": name,
                    "share": round(share, 4),
                    "verified": _blocker_verified(name, spot, blockers),
                }
                for name, share in sorted(shares.items(), key=lambda kv: -kv[1])
                if share >= 0.005
            ]
            near: dict = {}
            if row.valid_utc in carried_input:
                sp, grids, (wind_kt, wind_from) = carried_input[row.valid_utc]
                table = tables[break_id]
                # Local chop grows on the water off the break, so it takes the
                # LOCAL forecast wind (the NWS grid at Coronado), as the observed
                # chain takes KNZY's; the model's wind at the buoy stands in
                # only for an hour the grid did not give, and says so.
                here = local_hours.get(row.valid_utc.strftime(ISO))
                if here:
                    chop_kt, chop_from, chop_wind = here["speed_kt"], here["from_deg"], "NWS forecast"
                else:
                    chop_kt, chop_from, chop_wind = wind_kt, wind_from, "GFS-Wave at the buoy"
                carried = carry(sp, table, grids)
                chop = local_sea(table, spot.normal, chop_kt, chop_from,
                                 carried_short_hs=carried.hs_short,
                                 buoy=buoy_offsets.get(break_id), wind=chop_wind)
                level = (forecast_level(tide_series, row.valid_utc, departure, msl)
                         if profiles else None)
                near = summarise(carried, chop, buoy_hs_m=hs_offshore,
                                 window_hs_m=hs_window, depth_m=table.start_depth_m,
                                 profile=profiles.get(break_id), tide_m=level,
                                 normal_deg=spot.normal)
                hour_trains = near["trains"]
                if near["trains"]:
                    dominant_tp = near["trains"][0]["period_s"]
                    dominant_dir = near["trains"][0]["from_deg"]
            local = local_hours.get(row.valid_utc.strftime(ISO))
            entry.hours.append(Hour(
                local_wind_from_deg=local["from_deg"] if local else None,
                local_wind_kt=local["speed_kt"] if local else None,
                local_gust_kt=local.get("gust_kt") if local else None,
                local_wind_offshore=(round(offshore_component(local["from_deg"], spot.normal), 3)
                                     if local else None),
                valid_utc=row.valid_utc.strftime(ISO),
                lead_h=row.lead_hours,
                hs_offshore_m=round(hs_offshore, 3),
                hs_window_m=round(hs_window, 3),
                fraction=round(fraction, 4) if not math.isnan(fraction) else None,
                dominant_period_s=dominant_tp,
                dominant_from_deg=dominant_dir,
                wind_from_deg=hour_wind_deg,
                wind_kt=hour_wind_kt,
                trains=hour_trains,
                taken_by=taken_by,
                hs_nearshore_m=near.get("hs_m"),
                nearshore=near,
            ))
        forecast.breaks.append(entry)

    return forecast


def write(forecast: Forecast, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(forecast), indent=1), encoding="utf-8")


def format_table(forecast: Forecast, *, rows: int = 8) -> str:
    lines = [
        f"Coronado — GFS-Wave {forecast.cycle_utc or 'NO CYCLE'} "
        f"at {forecast.station_name} ({forecast.station})",
        "",
    ]
    for warning in forecast.warnings:
        lines.append(f"  ! {warning}")
    if forecast.warnings:
        lines.append("")

    wind = forecast.wind
    if wind.measured:
        gust = f", gusting {fmt_speed(wind.gust_kt)}" if wind.gust_kt else ""
        lines.append(f"wind  {wind.from_deg:.0f}° at {fmt_speed(wind.speed_kt)}{gust}"
                     f"   {wind.station_name} ({wind.station}), {wind.observed_utc}")
    else:
        lines.append(f"wind  — {wind.note or 'not collected'}")
    covered = [t for t in forecast.tide if t.height_m is not None]
    lines.append(
        f"tide  {len(covered)}/{len(forecast.tide)} hours covered   "
        f"{forecast.tide_site}, harmonic prediction carried from "
        f"{forecast.tide_station_name} ({forecast.tide_station})"
        if forecast.tide else "tide  — not collected"
    )
    lines.append("")

    tide_by_time = {t.valid_utc: t for t in forecast.tide}
    for entry in forecast.breaks:
        sense = ""
        if entry.wind_offshore is not None:
            sense = ("offshore" if entry.wind_offshore > 0.3
                     else "onshore" if entry.wind_offshore < -0.3 else "cross")
            sense = f"   wind {sense}" + (f" ({entry.wind_note})" if entry.wind_note else "")
        lines.append(f"{entry.name}   [{entry.confidence} confidence]{sense}")
        lines.append(f"  {'valid':>17s} {'lead':>5s} {'offshore':>16s} {'window':>16s} "
                     f"{'thru':>6s} {'T':>6s} {'from':>6s} {'tide':>16s}")
        for hour in entry.hours[:rows]:
            water = tide_by_time.get(hour.valid_utc)
            tide = fmt_height(water.height_m if water else None)
            lines.append(
                f"  {hour.valid_utc:>17s} {hour.lead_h:4d}h "
                f"{fmt_height(hour.hs_offshore_m):>16s} {fmt_height(hour.hs_window_m):>16s} "
                f"{100*(hour.fraction or 0):5.0f}% "
                f"{hour.dominant_period_s or 0:5.1f}s {hour.dominant_from_deg or 0:5.0f}° {tide:>16s}"
            )
        lines.append("")

    lines += [
        "Window height is offshore energy aimed at the break; the nearshore figure",
        "carries it over the seabed to 5 m of water and in to where it breaks at the",
        "hour's tide. Neither is a surf height at the sand: a significant height,",
        "with no offshore-to-face transfer.",
        "No verification series exists, so nothing here carries an error bar.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--hours", type=int, default=DEFAULT_HOURS)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--rows", type=int, default=8)
    parser.add_argument("--no-spectra", action="store_true",
                        help="skip the 617 MB spectral fetch and use partitions")
    args = parser.parse_args(argv)

    # The local wind forecast at the center break, fetched here rather than
    # in `build` so tests and rebuilds never touch the network for it. A
    # failure costs the card's local wind, never the forecast.
    center = next(s for s in load()[0] if s.id == "coronado_center")
    try:
        local = localwind.fetch(*center.position)
    except localwind.LocalWindError as error:
        local = {"available": False, "why": str(error)}
    forecast = build(data_dir=args.data_dir, hours=args.hours,
                     use_spectra=not args.no_spectra, local_wind=local)
    print(format_table(forecast, rows=args.rows))

    out = args.out or (Path(args.data_dir) / "live" / "forecast.json")
    write(forecast, out)
    print(f"\nWrote {out}")
    # The permanent record of what was built -- only for the live data
    # directory's own forecast, never for a copy written somewhere else.
    if args.out is None:
        built = json.loads(out.read_text(encoding="utf-8"))
        logged = forecastlog.append(built, forecastlog.log_dir(args.data_dir),
                                    build_sha=os.environ.get("GITHUB_SHA", "")[:7])
        print(f"Logged {logged} row(s) to {forecastlog.log_dir(args.data_dir)}")
        # And the hours it can be shown for, in full, for its past cards.
        shown = forecastlog.append_shown(built, forecastlog.shown_dir(args.data_dir))
        print(f"Logged {shown} shown hour(s) to {forecastlog.shown_dir(args.data_dir)}")
    return 0 if forecast.breaks else 1


if __name__ == "__main__":
    sys.exit(main())
