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
* *Calibration* — **none.** No transfer from offshore Hs to face height, no
  shoaling, no refraction, no band.
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
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR, ISO
from collector.gfswave import Bulletin, BulletinError, fetch_bulletin, from_direction
from collector.wavespec import SpecRecord, WaveSpecError, fetch_station_spec, parse_spec

from .geometry import HIGH, LOW, Blocker, Spot, load, swell_windows
from .transform import (
    GridSpectrum,
    SEAWARD_CLIP,
    SWELL_SPREAD_DEG,
    WIND_SEA_SPREAD_DEG,
    PartitionsThrough,
    attribution,
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

#: Breaks the app surface covers. Coronado only, by decision.
BREAKS = ("coronado_north", "coronado_center", "coronado_south")

#: How far ahead to publish. GFS-Wave runs to +384 h, but BRIEFING §5 measured
#: the 70% band under-covering badly at +216 h and beyond, and nothing here is
#: banded at all yet. Seven days is where the archive says the model is still
#: saying something.
DEFAULT_HOURS = 168

#: Cycles are published roughly 5 hours after their nominal time.
CYCLE_LAG_HOURS = 5.5


@dataclass
class WindAtTime:
    """What KNZY measured. One station, so one reading for all three breaks.

    The *measurement* is station-level and lives on the forecast. What each
    break makes of it is not: offshore and onshore are relative to a shore
    normal, and Coronado's three normals span 29° (192.8 / 214.2 / 221.5), so
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
    #: Share of the offshore energy each blocker took, largest first. The app
    #: reads this to say WHAT is taking the swell, and to mark a reading whose
    #: dominant blocker is the estimated Coronado Islands as less certain than
    #: one governed by the digitised Point Loma tip.
    taken_by: list[dict] = field(default_factory=list)


@dataclass
class BreakForecast:
    id: str
    name: str
    confidence: str
    #: The arcs swell can actually arrive through — both edges blocker-derived.
    #: The south-east arc `open_window` also returns is excluded: it spans the
    #: Baja coastline, which is not modelled as a blocker, so the model calls it
    #: open water (BRIEFING §12).
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
    #: Station-level context, hoisted off the breaks because one station feeds
    #: all three and repeating it three times is noise, not information.
    wind: WindAtTime = field(default_factory=WindAtTime)
    tide: list[TideAtHour] = field(default_factory=list)
    tide_station: str = TIDE_STATION
    tide_station_name: str = TIDE_STATION_NAME
    breaks: list[BreakForecast] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    #: "spectrum" when the model's own directional grid was available, and
    #: "partitions" when it fell back. The two differ by under 6% through the
    #: aperture (measured), but they stand on different things and the surface
    #: is entitled to say which.
    wave_source: str = "partitions"
    spread_assumption: dict = field(default_factory=dict)


def latest_cycle(now: datetime | None = None) -> datetime:
    """The most recent cycle that should have been published by now."""

    now = now or datetime.now(timezone.utc)
    anchor = now - timedelta(hours=CYCLE_LAG_HOURS)
    return anchor.replace(hour=(anchor.hour // 6) * 6, minute=0, second=0, microsecond=0)


def fetch_latest(station: str = STATION, *, now: datetime | None = None,
                 back: int = 4) -> tuple[Bulletin | None, list[str]]:
    """Walk back through cycles until one is available."""

    warnings: list[str] = []
    cycle = latest_cycle(now)
    for step in range(back):
        attempt = cycle - timedelta(hours=6 * step)
        try:
            return fetch_bulletin(station, attempt, attempts=2), warnings
        except BulletinError as exc:
            warnings.append(f"cycle {attempt:%Y-%m-%dT%H}Z unavailable: {str(exc)[-80:]}")
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


def read_latest_wind(data_dir: Path) -> dict[str, str] | None:
    path = Path(data_dir) / "wind" / f"{WIND_STATION}.csv"
    if not path.exists():
        return None
    with path.open(newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r.get("observed_utc")]
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
        # The normal comes from the chord. Coronado's north break has a
        # digitised position and an unverified chord sitting ~19° off the local
        # coast trend (BRIEFING §9), so this is the one thing about that break
        # the window's provenance does NOT cover.
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
        standing_on={
            "geometry": "digitised — Coronado's three breaks and the Point Loma tip",
            "model": "GFS-Wave, unassimilated; 0.26–0.31 m low bias at the buoy, not corrected here",
            "calibration": "none — no offshore-to-face transfer, no shoaling, no refraction, no band",
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

    if bulletin is None:
        forecast.warnings.append("No GFS-Wave cycle available; no forecast produced.")
        return forecast

    wind_row = read_latest_wind(data_dir)
    tide = read_tide(data_dir)
    forecast.wind = wind_measurement(wind_row)
    if wind_row is None:
        forecast.warnings.append(f"{WIND_STATION} wind not collected yet.")
    if not tide:
        forecast.warnings.append(f"{TIDE_STATION} tide not collected yet.")

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
        "GFS-Wave, unassimilated; 0.26–0.31 m low bias at the buoy, not corrected here"
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
        value = tide.get(row.valid_utc.strftime(ISO)[:13])
        forecast.tide.append(TideAtHour(
            valid_utc=row.valid_utc.strftime(ISO),
            height_m=round(value[0], 3) if value else None,
            kind=value[1] if value else None,
        ))

    for break_id in BREAKS:
        spot = by_id[break_id]
        entry = BreakForecast(
            id=spot.id,
            name=spot.name,
            confidence=confidence_for(spot, blockers),
            swell_window=[[round(w.low.bearing, 1), round(w.high.bearing, 1)]
                          for w in swell_windows(spot, blockers)],
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
            entry.hours.append(Hour(
                valid_utc=row.valid_utc.strftime(ISO),
                lead_h=row.lead_hours,
                hs_offshore_m=round(hs_offshore, 3),
                hs_window_m=round(hs_window, 3),
                fraction=round(fraction, 4) if not math.isnan(fraction) else None,
                dominant_period_s=dominant_tp,
                dominant_from_deg=dominant_dir,
                wind_from_deg=hour_wind_deg,
                wind_kt=hour_wind_kt,
                taken_by=taken_by,
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
        gust = f" gusting {wind.gust_kt:.0f}" if wind.gust_kt else ""
        lines.append(f"wind  {wind.from_deg:.0f}° at {wind.speed_kt or 0:.0f} kt{gust}"
                     f"   {wind.station_name} ({wind.station}), {wind.observed_utc}")
    else:
        lines.append(f"wind  — {wind.note or 'not collected'}")
    covered = [t for t in forecast.tide if t.height_m is not None]
    lines.append(
        f"tide  {len(covered)}/{len(forecast.tide)} hours covered   "
        f"{forecast.tide_station_name} ({forecast.tide_station}), harmonic prediction"
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
        lines.append(f"  {'valid':>17s} {'lead':>5s} {'offshore':>9s} {'window':>8s} "
                     f"{'thru':>6s} {'T':>6s} {'from':>6s} {'tide':>7s}")
        for hour in entry.hours[:rows]:
            water = tide_by_time.get(hour.valid_utc)
            tide = f"{water.height_m:6.2f}m" if water and water.height_m is not None else "     —"
            lines.append(
                f"  {hour.valid_utc:>17s} {hour.lead_h:4d}h {hour.hs_offshore_m:8.2f}m "
                f"{hour.hs_window_m:7.2f}m {100*(hour.fraction or 0):5.0f}% "
                f"{hour.dominant_period_s or 0:5.1f}s {hour.dominant_from_deg or 0:5.0f}° {tide}"
            )
        lines.append("")

    lines += [
        "Window height is offshore energy aimed at the break, not a wave height",
        "at the beach: no shoaling, no refraction, no offshore-to-face transfer.",
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

    forecast = build(data_dir=args.data_dir, hours=args.hours,
                     use_spectra=not args.no_spectra)
    print(format_table(forecast, rows=args.rows))

    out = args.out or (Path(args.data_dir) / "live" / "forecast.json")
    write(forecast, out)
    print(f"\nWrote {out}")
    return 0 if forecast.breaks else 1


if __name__ == "__main__":
    sys.exit(main())
