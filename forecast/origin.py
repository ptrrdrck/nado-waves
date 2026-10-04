"""Where a swell now arriving was born, read off 46232's own spectrum.

    python -m forecast.origin             # the arrivals in the archive
    python -m forecast.origin --report    # the measurements behind it

`forecast.forensics` reads a swell's origin off a buoy's DOMINANT period, one
number an hour. That works on the three-year historical files, whose periods
carry two decimals, and it cannot work on the live feed: NDBC's real-time
standard met rounds the dominant period to whole seconds, and between
2026-08-04 and 2026-10-02 the old method found 2 arrivals at 46232 where this
one finds the ridges by eye in the spectrogram (BRIEFING §37). It also only ever
sees the BIGGEST train, and a forerunner arrives small, under whatever swell is
already running.

So this reads each train separately. Every hour, the local maxima of 46232's
energy density in the swell band are found and refined between bins; maxima
that move steadily toward higher frequency from hour to hour are linked into a
ridge; and each ridge is fitted with the same straight line
(`dispersion.distance_from_slope`):

    f(t) = g (t − t₀) / (4π R)

The slope gives R, how far away the storm was; the line reaches f = 0 at t₀,
when it blew. The bearing is the ridge's own direction at an UNSHADOWED buoy,
46047 and then 46086, and never 46232's own: measured over the same arrivals
(BRIEFING §37) 46232 reads a north-west swell 50-74° too far south, because the
islands bend it, and a south-east one 20-37° off. An arrival neither unshadowed
buoy has keeps its distance and date and gets no place.

What it is: a measurement of the buoy's record, run backwards. What it is not:
a forecast, a storm track, or a verified position. Nothing observes the storm.
The same storm fitted independently at two buoys gives distances 18-25% apart
at the median (BRIEFING §37), which is why the card rounds to 500 and says
"about"; and the upstream "confirmed in transit" check `forensics` printed is
not on the card at all, because it never tested the distance.
A real storm is a moving area, not a point, and a storm running toward the
coast while it blows steepens the line and reads closer than it was. The region
name is a sea, never a country, for the same reason `forensics.REGIONS` gives.
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR

from .dispersion import _fit_line, distance_from_slope
from .forensics import region_name
from .swell import destination_point

ISO = "%Y-%m-%dT%H:%M:%SZ"

#: The swell band: 28.6 s to 10 s. Below 10 s the hour-to-hour maxima are
#: wind sea, which has no distant origin to read.
BAND_HZ = (0.035, 0.100)

#: A maximum counts as a train only above this energy density (m²/Hz). Low
#: enough to catch a forerunner (a 20 s train at 0.1 m reads ~0.05 here), high
#: enough that the empty long-period bins of a calm hour are not ridges.
MIN_DENSITY = 0.02

#: Linking one hour's maximum to the ridge before it. A dispersing train moves
#: UP in frequency, at g/(4πR): 0.0019 Hz an hour for a storm 1,500 km away,
#: 0.0003 for one 9,000 km away. A step may fall back by one bin's worth of
#: noise, and rise by that plus the fastest plausible slope.
STEP_DOWN_HZ = 0.003
STEP_UP_HZ_PER_H = 0.0015
#: A ridge survives this many missing hours. A missing spectrum is a gap: the
#: fit simply has no point there, nothing is put in its place.
MAX_GAP_H = 3.0

#: A ridge is an arrival when all of these hold. They are also the threshold
#: for showing one at all while it is still arriving: measured (BRIEFING §37),
#: an early fit that passes them sat within 17% of its 48-hour reading, and
#: one that fails them is withheld rather than shown with a warning.
MIN_POINTS = 12
MIN_LEAD_PERIOD_S = 13.0
MIN_PERIOD_DROP_S = 1.5
MIN_FIT_R2 = 0.8
#: The antipode is 20,015 km: a longer fit is a bad fit, not a far storm.
PLAUSIBLE_KM = (500.0, 20000.0)
#: The line is fitted on the ridge's first hours only: later, trains born
#: elsewhere drift into the same bins and the ridge stops being one storm's.
FIT_HOURS = 48.0
#: Unshadowed only, most exposed first. 46232 is deliberately absent: see the
#: module docstring.
BEARING_STATIONS = ("46047", "46086")
#: A bearing buoy's spectrum must be within this of the ridge's hour, and
#: carry at least this much energy at the ridge's frequency, at this many of
#: its hours, before its direction is read.
BEARING_MATCH_MIN = 45.0
BEARING_MIN_POINTS = 4

#: How long an arrival stays the "last readable arrival" a card can name.
LOOKBACK_DAYS = 21

#: A ridge is still running when its newest point is this close to the newest
#: spectrum; and it is a break's train when one of the card's trains sits
#: within this of the ridge's newest frequency (1.5 bins at 0.005 Hz).
CURRENT_H = 3.0
TRAIN_MATCH_HZ = 0.0075


@dataclass(frozen=True)
class Point:
    time: datetime
    freq_hz: float
    density: float
    from_deg: float


@dataclass
class Ridge:
    points: list[Point] = field(default_factory=list)

    @property
    def last(self) -> Point:
        return self.points[-1]


@dataclass(frozen=True)
class Fit:
    distance_km: float
    generated_utc: datetime
    r_squared: float
    hours: float
    points: int


@dataclass
class Arrival:
    ridge: Ridge
    fit: Fit
    bearing_deg: float | None = None
    bearing_from: str | None = None
    origin: tuple[float, float] | None = None

    @property
    def first_utc(self) -> datetime:
        return self.ridge.points[0].time

    @property
    def last_utc(self) -> datetime:
        return self.ridge.last.time

    @property
    def lead_period_s(self) -> float:
        return 1.0 / self.ridge.points[0].freq_hz

    @property
    def latest_period_s(self) -> float:
        return 1.0 / self.ridge.last.freq_hz

    @property
    def travel_days(self) -> float:
        return (self.first_utc - self.fit.generated_utc).total_seconds() / 86400.0

    @property
    def region(self) -> str | None:
        return region_name(*self.origin) if self.origin else None


def maxima(spectrum) -> list[Point]:
    """The swell band's local maxima, each refined between bins.

    The refinement is a parabola through the log-energy of the peak bin and its
    two neighbours. It matters: at 0.005 Hz bins a storm 9,000 km away moves
    one bin every fifteen hours, so a ridge read bin-to-bin is a staircase and
    its slope is mostly quantisation.
    """

    f, c = spectrum.frequencies, spectrum.c11
    out: list[Point] = []
    for i in range(1, len(f) - 1):
        if not BAND_HZ[0] <= f[i] <= BAND_HZ[1]:
            continue
        if not (c[i] >= MIN_DENSITY and c[i] > c[i - 1] and c[i] >= c[i + 1]):
            continue
        y0, y1, y2 = (math.log(max(c[j], 1e-9)) for j in (i - 1, i, i + 1))
        curve = y0 - 2.0 * y1 + y2
        shift = 0.5 * (y0 - y2) / curve if curve < 0 else 0.0
        shift = max(-0.5, min(0.5, shift))
        step = (f[i + 1] - f[i]) if shift > 0 else (f[i] - f[i - 1])
        out.append(Point(spectrum.time, f[i] + shift * step, c[i], spectrum.a1[i] % 360.0))
    return out


def ridges(spectra) -> list[Ridge]:
    """Link each hour's maxima into ridges, oldest spectrum first.

    Greedy and deterministic: the strongest running ridge claims first, each
    taking the maximum closest to where it was. A maximum nobody claims starts
    a ridge of its own.
    """

    active: list[Ridge] = []
    finished: list[Ridge] = []
    for spectrum in spectra:
        found = maxima(spectrum)
        taken: set[int] = set()
        kept: list[Ridge] = []
        for ridge in sorted(active, key=lambda r: -r.last.density):
            gap = (spectrum.time - ridge.last.time).total_seconds() / 3600.0
            if gap > MAX_GAP_H:
                finished.append(ridge)
                continue
            best = None
            for k, point in enumerate(found):
                if k in taken:
                    continue
                step = point.freq_hz - ridge.last.freq_hz
                if -STEP_DOWN_HZ <= step <= STEP_DOWN_HZ + STEP_UP_HZ_PER_H * gap:
                    if best is None or abs(step) < abs(best[1]):
                        best = (k, step)
            if best is not None:
                taken.add(best[0])
                ridge.points.append(found[best[0]])
            kept.append(ridge)
        kept.extend(Ridge([p]) for k, p in enumerate(found) if k not in taken)
        active = kept
    return finished + active


def fit_ridge(ridge: Ridge, hours: float = FIT_HOURS) -> Fit | None:
    """The dispersion line through a ridge's first `hours`, or None."""

    start = ridge.points[0].time
    used = [p for p in ridge.points if (p.time - start).total_seconds() / 3600.0 <= hours]
    if len(used) < 3:
        return None
    xs = [(p.time - start).total_seconds() / 3600.0 for p in used]
    fitted = _fit_line(xs, [p.freq_hz for p in used])
    if fitted is None:
        return None
    intercept, slope, r2 = fitted
    if slope <= 0:
        return None
    return Fit(
        distance_km=distance_from_slope(slope),
        generated_utc=start - timedelta(hours=intercept / slope),
        r_squared=r2,
        hours=xs[-1],
        points=len(used),
    )


def qualifies(ridge: Ridge, fit: Fit | None) -> bool:
    if fit is None or fit.points < MIN_POINTS or fit.r_squared < MIN_FIT_R2:
        return False
    lead = 1.0 / ridge.points[0].freq_hz
    if lead < MIN_LEAD_PERIOD_S:
        return False
    start = ridge.points[0].time
    within = [p for p in ridge.points if (p.time - start).total_seconds() / 3600.0 <= FIT_HOURS]
    if lead - 1.0 / within[-1].freq_hz < MIN_PERIOD_DROP_S:
        return False
    return PLAUSIBLE_KM[0] < fit.distance_km < PLAUSIBLE_KM[1]


def _nearest(by_time: dict[datetime, object], times: list[datetime], moment: datetime):
    """The record nearest `moment` within BEARING_MATCH_MIN, else None."""

    import bisect

    k = bisect.bisect_left(times, moment)
    best = None
    for j in (k - 1, k):
        if 0 <= j < len(times):
            gap = abs((times[j] - moment).total_seconds()) / 60.0
            if gap <= BEARING_MATCH_MIN and (best is None or gap < best[0]):
                best = (gap, times[j])
    return by_time[best[1]] if best else None


def ridge_bearing(ridge: Ridge, archives: dict[str, list],
                  stations: tuple[str, ...] = BEARING_STATIONS) -> tuple[float, str] | None:
    """The ridge's direction FROM, at the most exposed buoy that has it.

    At each of the ridge's fitted hours, the bearing buoy's bin nearest the
    ridge's frequency must itself carry `MIN_DENSITY`; its `a1` is weighted by
    that energy into a circular mean. A buoy that has the train at fewer than
    `BEARING_MIN_POINTS` hours is passed over rather than read on what it has.
    """

    start = ridge.points[0].time
    fitted = [p for p in ridge.points if (p.time - start).total_seconds() / 3600.0 <= FIT_HOURS]
    for station in stations:
        spectra = archives.get(station) or []
        if not spectra:
            continue
        by_time = {s.time: s for s in spectra}
        times = sorted(by_time)
        x = y = 0.0
        n = 0
        for point in fitted:
            spectrum = _nearest(by_time, times, point.time)
            if spectrum is None:
                continue
            i = min(range(len(spectrum.frequencies)),
                    key=lambda j: abs(spectrum.frequencies[j] - point.freq_hz))
            energy = spectrum.c11[i]
            if energy is None or math.isnan(energy) or energy < MIN_DENSITY:
                continue
            direction = spectrum.a1[i]
            if direction is None or math.isnan(direction):
                continue
            x += energy * math.cos(math.radians(direction))
            y += energy * math.sin(math.radians(direction))
            n += 1
        if n >= BEARING_MIN_POINTS and (x or y):
            return math.degrees(math.atan2(y, x)) % 360.0, station
    return None


def arrivals(spectra, archives: dict[str, list] | None = None,
             position: tuple[float, float] | None = None) -> list[Arrival]:
    """Every readable arrival in `spectra` (46232's), oldest first.

    `archives` maps a bearing station to its spectra;
    `position` is 46232's, from `data/station_metadata.csv`, never typed.
    Without a bearing an arrival keeps its distance and date and has no origin.
    """

    found: list[Arrival] = []
    for ridge in ridges(spectra):
        fit = fit_ridge(ridge)
        if not qualifies(ridge, fit):
            continue
        arrival = Arrival(ridge=ridge, fit=fit)
        read = ridge_bearing(ridge, archives or {})
        if read is not None:
            arrival.bearing_deg, arrival.bearing_from = read
            if position is not None:
                arrival.origin = destination_point(position, read[0], fit.distance_km)
        found.append(arrival)
    found.sort(key=lambda a: a.first_utc)
    return found


def load_archives(data_dir: Path = DEFAULT_DATA_DIR) -> dict[str, list]:
    """46232's spectra and each bearing buoy's, by station; missing is empty."""

    from .transform import load_spectra

    out: dict[str, list] = {}
    for station in ("46232",) + BEARING_STATIONS:
        try:
            out[station] = load_spectra(Path(data_dir) / "spectra" / station)
        except (FileNotFoundError, ValueError):
            out[station] = []
    return out


def _arrival_dict(a: Arrival, running: bool) -> dict:
    return {
        "first_utc": a.first_utc.strftime(ISO),
        "last_utc": a.last_utc.strftime(ISO),
        "running": running,
        "hours_read": round(a.fit.hours, 1),
        "points": a.fit.points,
        "lead_period_s": round(a.lead_period_s, 1),
        "latest_period_s": round(a.latest_period_s, 1),
        "distance_km": round(a.fit.distance_km),
        "generated_utc": a.fit.generated_utc.strftime(ISO),
        "travel_days": round(a.travel_days, 1),
        "r_squared": round(a.fit.r_squared, 3),
        "bearing_deg": None if a.bearing_deg is None else round(a.bearing_deg),
        "bearing_from": a.bearing_from,
        "origin": None if a.origin is None else [round(v, 1) for v in a.origin],
        "region": a.region,
        # The train it was at its peak hour, where a past arrival is matched to
        # a tab's trains: the card's "last readable arrival" names it by this.
        "peak_period_s": round(1.0 / peak_point(a).freq_hz, 1),
    }


def match(arrival: Arrival, trains: list[dict], at: Point | None = None) -> float | None:
    """The period of the card train this arrival IS, or None.

    A card lists a break's trains by their peak bin's period; the ridge is at
    its refined frequency at `at`, its newest point unless a past hour is
    being asked about. Within `TRAIN_MATCH_HZ` they are the same
    train. The origin belongs to the train, and a break shows it only when the
    train is on that break's card: which trains reach a break is the aperture's
    answer, never a test of one bearing against the window (BRIEFING §10).
    """

    best = None
    for train in trains or []:
        period = train.get("period_s")
        if not period:
            continue
        gap = abs(1.0 / period - (at or arrival.ridge.last).freq_hz)
        if gap <= TRAIN_MATCH_HZ and (best is None or gap < best[0]):
            best = (gap, period)
    return best[1] if best else None


def peak_point(arrival: Arrival) -> Point:
    """The ridge's most energetic hour inside the fit: where a past arrival's
    card trains are rebuilt to ask which breaks it reached."""

    start = arrival.first_utc
    fitted = [p for p in arrival.ridge.points
              if (p.time - start).total_seconds() / 3600.0 <= FIT_HOURS]
    return max(fitted, key=lambda p: p.density)


def reading(spectra, archives: dict[str, list], position, *, newest: datetime,
            trains_now: dict[str, list[dict]], trains_at) -> dict:
    """The Origin block of `now.json`.

    `trains_now` is each site's card trains on the newest spectrum (the three
    breaks and "buoy"); `trains_at(time)` rebuilds them for a past hour. Per
    site: `current`, the running arrivals that are one of its trains now, and
    `last`, the newest finished arrival that was one of its trains at its peak
    hour, within `LOOKBACK_DAYS`. Both index `arrivals`.
    """

    window = [s for s in spectra
              if newest - timedelta(days=LOOKBACK_DAYS + FIT_HOURS / 24.0) <= s.time <= newest]
    found = [a for a in arrivals(window, archives, position)
             if a.last_utc >= newest - timedelta(days=LOOKBACK_DAYS)]
    running = [a.last_utc >= newest - timedelta(hours=CURRENT_H) for a in found]

    sites: dict[str, dict] = {}
    for site, trains in trains_now.items():
        current = []
        for k, a in enumerate(found):
            period = match(a, trains) if running[k] else None
            if period is not None:
                current.append({"arrival": k, "train_period_s": period})
        current.sort(key=lambda c: -c["train_period_s"])
        sites[site] = {"current": current, "last": None}

    rebuilt: dict[datetime, dict] = {}
    for k in sorted(range(len(found)), key=lambda k: found[k].last_utc, reverse=True):
        if running[k]:
            continue
        waiting = [site for site, v in sites.items() if v["last"] is None]
        if not waiting:
            break
        peak = peak_point(found[k])
        if peak.time not in rebuilt:
            rebuilt[peak.time] = trains_at(peak.time) or {}
        for site in waiting:
            if match(found[k], rebuilt[peak.time].get(site, []), peak) is not None:
                sites[site]["last"] = k

    return {
        "station": "46232",
        "bearing_stations": list(BEARING_STATIONS),
        "lookback_days": LOOKBACK_DAYS,
        "arrivals": [_arrival_dict(a, r) for a, r in zip(found, running)],
        "sites": sites,
    }


def describe(arrival: Arrival) -> str:
    where = (f"{arrival.region}, {arrival.fit.distance_km:,.0f} km on "
             f"{arrival.bearing_deg:.0f}° (read at {arrival.bearing_from})"
             if arrival.origin else f"{arrival.fit.distance_km:,.0f} km, no bearing")
    return (f"{arrival.first_utc:%Y-%m-%d %H}Z  "
            f"{arrival.lead_period_s:4.1f}->{arrival.latest_period_s:4.1f} s over "
            f"{arrival.fit.hours:3.0f} h ({arrival.fit.points} h read, R² "
            f"{arrival.fit.r_squared:.2f})  born {arrival.fit.generated_utc:%m-%d %H}Z, "
            f"{arrival.travel_days:.1f} d  {where}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--report", action="store_true",
                        help="The measurements behind the constants (BRIEFING §37).")
    args = parser.parse_args(argv)

    if args.report:
        from .originreport import report
        print(report(args.data_dir))
        return 0

    from .siting import load_coordinates

    archives = load_archives(args.data_dir)
    position = load_coordinates().get("46232")
    for arrival in arrivals(archives["46232"], archives, position):
        print(describe(arrival))
    return 0


if __name__ == "__main__":
    sys.exit(main())
