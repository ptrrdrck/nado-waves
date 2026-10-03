"""Each hurricane NHC tracked, run forward to the buoys. Reports, never edits.

    python -m forecast.stormtrack

`forecast.origintracks` asks whether a reading's pin lands near a storm. That
is weak: a busy season puts SOME storm near most points, and a pin is one
number. This asks the converse, with the whole track and the buoy's direction:

**If this storm sent swell, when and from where must it have arrived?** Every
best-track fix at hurricane strength is a source at a known place and time.
From each, a train of frequency f reaches a buoy d / cg(f) later, cg = g/(4πf)
in deep water. Over all of a storm's fixes that sweeps a BAND across the
buoy's time-frequency plane: where its swell can be, and nowhere else.

The buoy's own spectrum, read by maximum entropy, gives the energy at each
hour and frequency arriving from within `SECTOR_HALF_DEG` of the storm's
bearing. Inside the band it should stand above that frequency's typical level
for the same sector; outside it, not. The score is the **rank**: each band
cell's place in its own frequency's distribution over the whole archive (0.5
typical, 1 the most energetic hour on record), averaged over the band. A rank
and not a ratio, because the long-period bins are empty most hours and a ratio
to a median of nothing is unbounded (measured: lifts of 10⁵ on the first run).

And it has to beat its controls, which are what the pin test never had:

* **Time**: the same band moved 5, 10 and 15 days either way. A sector that is
  simply always lively (south swell from the Southern Hemisphere sits next to
  the south-south-east) lifts as much at the wrong time as the right one.
* **Direction**: in the same cells, the energy from the storm's sector against
  the energy from the sectors 45° either side. A rank cannot do this one: a
  swell's directional spread lifts its neighbours' ranks too (measured on a
  synthetic arrival: 0.97 at the storm's bearing and 0.97 at 45° off). Energy
  that arrived on schedule but mostly from somewhere else is not this storm's.

A storm **explains** its band at a buoy when its rank is at least `MIN_RANK`
and beats every time control by `MARGIN`, its sector carries at least
`DIR_RATIO` times either turned sector's energy, and the band had data on at
least `MIN_COVERAGE` of its cells. Then
each Origin ridge is tested against the explained bands: the share of its
points inside a band, against the same share for the time-shifted band.

The path: a great circle over deep water, and a fix whose path to a buoy
crosses land is dropped for that buoy (`forecast.landpath`, Natural Earth
1:10m; BRIEFING §37c). That is what stops Polo's strongest days, behind the
Baja peninsula, diluting the days its swell had open water. Refraction near the
buoy is not modelled, which matters most at 46232 for storms in the
south-south-east (BRIEFING §37: it reads them 20-37° off), so the GATE is read
at the unshadowed buoys only (`GATE_STATIONS`). A best track is NHC's analysis,
not an observation of the swell.

**As of a moment.** Every score takes `until`: only band cells up to it count,
ranked against the `REFERENCE_DAYS` of spectra before it, and a control needs
`MIN_CELLS` of its own. The live card asks exactly the question the backtest
asks of every past hour (`backtest`), with no look at hours not yet measured.
"""

from __future__ import annotations

import argparse
import bisect
import math
import statistics
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR, write_step_summary

from .origintracks import MIN_KT, Fix, load_tracks
from .swell import great_circle_km, initial_bearing

#: Which buoys a storm is run forward to: the unshadowed one first.
STATIONS = ("46047", "46086", "46232")
#: Where a storm must explain its band before anything is shown: the buoys the
#: islands do not shadow. 46232 says WHICH breaks, through their card trains.
GATE_STATIONS = ("46047", "46086")
#: The distribution a cell is ranked in: this many days of spectra up to `until`.
REFERENCE_DAYS = 40
#: A band, or a control, scored on fewer cells than this has no score.
MIN_CELLS = 24
#: The swell band, 25 s to 10 s: what a hurricane sends this far.
BAND_HZ = (0.04, 0.10)
#: Half-width of the direction sector around the storm's bearing. A buoy's
#: direction per bin is broad (BRIEFING §28), and a storm's bearing moves a few
#: degrees over its life.
SECTOR_HALF_DEG = 20
#: Timing tolerance either side of a fix's predicted arrival: a hurricane's
#: swell-making winds span ~250 km, ~7 h at 10 m/s, and six-hourly fixes
#: leave up to 3 h between them.
TOL_H = 8.0
#: The controls.
SHIFT_DAYS = (-15, -10, -5, 5, 10, 15)
TURN_DEG = (-45, 45)
#: What "explains" means: the band ranks at least this high...
MIN_RANK = 0.7
#: ...and beats the best control by this much...
MARGIN = 0.1
#: ...its sector carries this many times the energy of either turned sector...
DIR_RATIO = 1.5
#: ...on a band that had spectra for at least this share of its cells.
MIN_COVERAGE = 0.5
#: How a ridge point sits in a band: within TOL_H of a fix's arrival at its
#: own frequency, at 46232, whose ridges these are.
RIDGE_STATION = "46232"
GRAVITY = 9.81


def arrival(fix: Fix, freq_hz: float, distance_km: float) -> datetime:
    cg = GRAVITY / (4.0 * math.pi * freq_hz)
    return fix.time + timedelta(seconds=distance_km * 1000.0 / cg)


def sector_energy(spectrum, index: int, center: float, half: int = SECTOR_HALF_DEG) -> float:
    """m² arriving from within `half` of `center` in one frequency bin."""

    total = 0.0
    for d in range(-half, half + 1):
        total += spectrum.density(index, (center + d) % 360.0)
    return total * math.radians(1.0) * spectrum.bin_width(index)


@dataclass
class Band:
    """A storm's swell window in one buoy's time-frequency plane."""

    storm: str
    name: str
    station: str
    fixes: list[Fix]
    distances: list[float]
    bearing: float
    peak_kt: int
    station_position: tuple[float, float] | None = None
    #: Fixes at strength whose path to this buoy crosses land: dropped.
    blocked: int = 0

    def contains(self, time: datetime, freq_hz: float, shift: timedelta = timedelta(0)) -> bool:
        for fix, d in zip(self.fixes, self.distances):
            if abs((time - shift - arrival(fix, freq_hz, d)).total_seconds()) <= TOL_H * 3600:
                return True
        return False


def bands(tracks: dict[str, list[Fix]], positions: dict[str, tuple[float, float]],
          min_kt: int = MIN_KT, land=()) -> list[Band]:
    """One band per storm and buoy, from the fixes at strength with open water
    to it. A storm with none at a buoy gets a band with no fixes, kept so the
    report can say it was blocked rather than leaving it out."""

    from .landpath import blocked as crosses

    out = []
    for storm, fixes in tracks.items():
        strong = [f for f in fixes if f.vmax_kt >= min_kt]
        if not strong:
            continue
        # A b-deck is named INVEST or GENESISnnn until the storm is; the last
        # real name is the storm's.
        names = [f.name for f in fixes
                 if f.name and not f.name.upper().startswith(("INVEST", "GENESIS"))]
        name = names[-1] if names else storm
        for station in STATIONS:
            home = positions.get(station)
            if home is None:
                continue
            open_ = [f for f in strong if not crosses((f.lat, f.lon), home, land)]
            ds = [great_circle_km(home, (f.lat, f.lon)) for f in open_]
            out.append(Band(storm, name, station, open_, ds,
                            _mean_bearing(home, open_ or strong),
                            max(f.vmax_kt for f in strong), home,
                            blocked=len(strong) - len(open_)))
    return out


@dataclass
class Score:
    rank: float | None
    coverage: float
    cells: int
    #: Cells actually scored (had a spectrum).
    have: int = 0
    #: Mean sector energy over the band's cells, m².
    energy: float | None = None


@dataclass
class Result:
    band: Band
    actual: Score
    shifted: dict[int, Score] = field(default_factory=dict)
    turned: dict[int, Score] = field(default_factory=dict)

    @property
    def best_control(self) -> float | None:
        ranks = [s.rank for s in self.shifted.values()
                 if s.rank is not None and s.have >= MIN_CELLS]
        return max(ranks) if ranks else None

    @property
    def direction_ratio(self) -> float | None:
        """The storm's sector over the stronger turned one, in the same cells."""

        others = [s.energy for s in self.turned.values() if s.energy is not None]
        if self.actual.energy is None or not others:
            return None
        return self.actual.energy / max(max(others), 1e-12)

    @property
    def explains(self) -> bool:
        a, c, d = self.actual, self.best_control, self.direction_ratio
        return (a.rank is not None and c is not None and d is not None
                and a.have >= MIN_CELLS
                and a.coverage >= MIN_COVERAGE and a.rank >= MIN_RANK
                and a.rank >= c + MARGIN and d >= DIR_RATIO)


class Field:
    """One buoy's sector energy, computed once per (center, bin, hour).

    One spectrum an hour: 46047 and 46086 report twice an hour (:20, :50) and
    a band is scored hourly, so the second would be read by nothing.
    """

    def __init__(self, spectra, spread: str = "mem"):
        kept, seen = [], set()
        for s in sorted(spectra, key=lambda s: s.time):
            hour = s.time.replace(minute=0, second=0, microsecond=0)
            if hour not in seen:
                seen.add(hour)
                kept.append(s)
        self.spectra = [s.with_spread(spread) for s in kept]
        self.times = [s.time for s in self.spectra]
        self.hours = {s.time.replace(minute=0, second=0, microsecond=0): k
                      for k, s in enumerate(self.spectra)}
        f = self.spectra[0].frequencies if self.spectra else []
        self.bins = [i for i, x in enumerate(f) if BAND_HZ[0] <= x <= BAND_HZ[1]]
        self.freqs = {i: f[i] for i in self.bins}
        self._cache: dict = {}

    def energy(self, center: float) -> dict[int, list[float]]:
        key = round(center) % 360
        if key not in self._cache:
            self._cache[key] = {i: [sector_energy(s, i, key) for s in self.spectra]
                                for i in self.bins}
        return self._cache[key]

    def ranked(self, center: float, lo: int, hi: int) -> dict[int, list[float]]:
        """Each bin's energies over spectra lo..hi-1, sorted, for mid-rank lookups."""

        key = ("sorted", round(center) % 360, lo, hi)
        if key not in self._cache:
            self._cache[key] = {i: sorted(v[lo:hi]) for i, v in self.energy(center).items()}
        return self._cache[key]

    def score(self, band: Band, center: float, shift: timedelta = timedelta(0),
              until: datetime | None = None) -> Score:
        """Mean in-band rank within each bin's own distribution, and coverage.

        As of `until` (the archive's end when None): a cell after it does not
        exist yet, and the distribution is the `REFERENCE_DAYS` before it.
        Coverage is the share of the band's (hour, bin) cells in that window
        that have a spectrum: a band over an outage is not evidence either way,
        and says so.
        """

        if not self.times or not band.fixes:
            return Score(None, 0.0, 0)
        end = self.times[-1] if until is None else min(self.times[-1], until)
        start = end - timedelta(days=REFERENCE_DAYS)
        lo = bisect.bisect_left(self.times, start)
        hi = bisect.bisect_right(self.times, end)
        if hi - lo < MIN_CELLS:
            return Score(None, 0.0, 0)
        energy = self.energy(center)
        ordered = self.ranked(center, lo, hi)
        ratios, raw, wanted, have = [], [], 0, 0
        hour = timedelta(hours=1)
        for i in self.bins:
            f = self.freqs[i]
            first = min(arrival(x, f, d) for x, d in zip(band.fixes, band.distances)) + shift
            last = max(arrival(x, f, d) for x, d in zip(band.fixes, band.distances)) + shift
            t = (first - timedelta(hours=TOL_H)).replace(minute=0, second=0, microsecond=0)
            while t <= last + timedelta(hours=TOL_H):
                if start <= t <= end and band.contains(t, f, shift):
                    wanted += 1
                    k = self.hours.get(t)
                    if k is not None and lo <= k < hi:
                        have += 1
                        x, pool = energy[i][k], ordered[i]
                        raw.append(x)
                        below = bisect.bisect_left(pool, x)
                        equal = bisect.bisect_right(pool, x) - below
                        ratios.append((below + 0.5 * equal) / len(pool))
                t += hour
        if not ratios:
            return Score(None, 0.0, wanted, 0)
        return Score(statistics.fmean(ratios), have / wanted if wanted else 0.0, wanted, have,
                     statistics.fmean(raw))


def evaluate(band: Band, field_: Field, until: datetime | None = None) -> Result:
    result = Result(band, field_.score(band, band.bearing, until=until))
    for d in SHIFT_DAYS:
        result.shifted[d] = field_.score(band, band.bearing, timedelta(days=d), until)
    for t in TURN_DEG:
        result.turned[t] = field_.score(band, (band.bearing + t) % 360.0, until=until)
    return result


def ridge_share(arrival_, band: Band, shift: timedelta = timedelta(0)) -> float:
    pts = arrival_.ridge.points
    return sum(band.contains(p.time, p.freq_hz, shift) for p in pts) / len(pts)


#: Ridge attribution: the share of a ridge's points inside a storm-day's band,
#: the most the shifted band may hold, and how far the bearings may differ.
RIDGE_SHARE = 0.8
RIDGE_SHARE_CONTROL = 0.2
RIDGE_BEARING_DEG = 15
PERMUTATIONS = 2000


def matches(ridges: list, ridge_bands: list[Band]):
    """(attributed, timing-only) lists of (ridge, day band, share)."""

    timed = []
    for a in ridges:
        for band in ridge_bands:
            for day in by_day(band):
                share = ridge_share(a, day)
                if share < RIDGE_SHARE:
                    continue
                control = max(ridge_share(a, day, timedelta(days=k)) for k in SHIFT_DAYS)
                if control < RIDGE_SHARE_CONTROL:
                    timed.append((a, day, share))
    attributed = [(a, d, sh) for a, d, sh in timed
                  if a.bearing_deg is not None
                  and abs((a.bearing_deg - d.bearing + 180) % 360 - 180) <= RIDGE_BEARING_DEG]
    return attributed, timed


def bearing_chance(ridges: list, timed: list) -> tuple[int, float]:
    """How many ridges' timing matches also agree in bearing, and how often
    shuffled bearings do as well: the ridges' own bearings, dealt to each other."""

    import random

    placed = [a for a in ridges if a.bearing_deg is not None]
    def agree(bearing_of) -> int:
        # Distinct ridges, not pairs: one ridge in two of a storm's days is
        # one attribution.
        return len({id(a) for a, d, _ in timed if id(a) in bearing_of
                    and abs((bearing_of[id(a)] - d.bearing + 180) % 360 - 180)
                    <= RIDGE_BEARING_DEG})
    actual = agree({id(a): a.bearing_deg for a in placed})
    rng = random.Random(37)
    bearings = [a.bearing_deg for a in placed]
    hits = 0
    for _ in range(PERMUTATIONS):
        rng.shuffle(bearings)
        hits += agree(dict(zip(map(id, placed), bearings))) >= actual
    return actual, hits / PERMUTATIONS


def _fmt(score: Score) -> str:
    return "—" if score.rank is None else f"{score.rank:.2f}"


def by_day(band: Band) -> list[Band]:
    """The band cut into one band per day of the storm's track.

    A whole track can be mostly unreachable: Polo's strongest days sat where a
    straight path to the buoys runs up the Baja peninsula, which is not
    modelled, and those cells dilute the days whose swell had open water. Per
    day, the open days show for themselves. Read with care: ~60 day-tests in a
    season will pass the gate by chance now and then; the whole-track verdict
    is the claim, the days are where to look.
    """

    days: dict = {}
    for fix, d in zip(band.fixes, band.distances):
        days.setdefault(fix.time.date(), []).append((fix, d))
    return [Band(band.storm, band.name, band.station, [f for f, _ in v], [d for _, d in v],
                 _mean_bearing(band.station_position, [f for f, _ in v]),
                 max(f.vmax_kt for f, _ in v), band.station_position)
            for _, v in sorted(days.items())]


def arriving(band: Band, at: datetime, freqs: list[float]) -> list[float]:
    """The frequencies whose train from this storm is at the buoy at `at`."""

    return [f for f in freqs if band.contains(at, f)]


def _mean_bearing(home: tuple[float, float], fixes: list[Fix]) -> float:
    bs = [initial_bearing(home, (f.lat, f.lon)) for f in fixes]
    x = sum(math.cos(math.radians(b)) for b in bs)
    y = sum(math.sin(math.radians(b)) for b in bs)
    return math.degrees(math.atan2(y, x)) % 360.0


#: The per-day table is drawn at the buoy the islands do not shadow.
DAY_STATION = "46047"


def report(results: list[Result], ridges: list, ridge_bands: list[Band],
           days: list[Result] = ()) -> str:
    lines = [
        f"Hurricanes run forward to the buoys (fixes >= the strength asked; sector "
        f"+/-{SECTOR_HALF_DEG}°, timing +/-{TOL_H:.0f} h; rank = in-band cells' mean place in "
        f"their frequency's own distribution, 0.5 typical)",
        "",
        "| storm | buoy | bearing | distance | rank | coverage | time controls "
        f"({', '.join(f'{d:+d} d' for d in SHIFT_DAYS)}) | own sector / turned ±45° | explains? |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        b = r.band
        if r.actual.cells == 0:
            continue
        lines.append(
            f"| {b.name.title()} ({b.storm.upper()}), {b.peak_kt} kt | {b.station} | "
            f"{b.bearing:.0f}° | {min(b.distances):,.0f}-{max(b.distances):,.0f} km | "
            f"{_fmt(r.actual)} | {r.actual.coverage:.0%} | "
            f"{' '.join(_fmt(r.shifted[d]) for d in SHIFT_DAYS)} | "
            f"{'—' if r.direction_ratio is None else f'x{r.direction_ratio:.1f}'} | "
            f"{'**yes**' if r.explains else 'no'} |")
    if days:
        lines += ["", f"Day by day at {DAY_STATION} (each day's fixes alone, at that day's "
                  "own bearing):", "",
                  "| storm | day | where | kt | bearing | distance | rank | best time control | "
                  "own sector / turned | explains? |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        for r in days:
            b, f = r.band, r.band.fixes[0]
            if r.actual.cells == 0 or r.actual.rank is None:
                continue
            lines.append(
                f"| {b.name.title()} | {f.time:%m-%d} | {abs(f.lat):.1f}N {abs(f.lon):.1f}W | "
                f"{b.peak_kt} | {b.bearing:.0f}° | {min(b.distances):,.0f}-{max(b.distances):,.0f} km | "
                f"{_fmt(r.actual)} | {'—' if r.best_control is None else f'{r.best_control:.2f}'} | "
                f"{'—' if r.direction_ratio is None else f'x{r.direction_ratio:.1f}'} | "
                f"{'**yes**' if r.explains else 'no'} |")
    lines += ["", "Origin's ridges at 46232 against each storm-DAY's band there. Timing "
              f"alone matches almost anything (a whole track's band is days wide), so a "
              f"ridge is attributed only when >= {RIDGE_SHARE:.0%} of its points sit in a "
              f"day's band, under {RIDGE_SHARE_CONTROL:.0%} with that band shifted, AND its "
              f"bearing is within {RIDGE_BEARING_DEG}° of the storm's that day:", "",
              "| ridge first seen | reading | timing matches (storm, day, share, bearing) | "
              "attributed |", "|---|---|---|---|"]
    attributed, timed_pairs = matches(ridges, ridge_bands)
    for a in ridges:
        what = (f"{a.fit.distance_km:,.0f} km"
                + (f" at {a.bearing_deg:.0f}°" if a.bearing_deg is not None else ", no bearing"))
        timed = [m for m in timed_pairs if m[0] is a]
        listed = "; ".join(f"{d.name.title()} {d.fixes[0].time:%m-%d} {sh:.0%} at {d.bearing:.0f}°"
                           for _, d, sh in timed) or "none"
        hit = [m for m in attributed if m[0] is a]
        lines.append(f"| {a.first_utc:%Y-%m-%d %H}Z | {what} | {listed} | "
                     + ("; ".join(f"**{d.name.title()}** ({d.fixes[0].time:%m-%d}), "
                                  f"storm {d.distances[0]:,.0f} km" for _, d, _ in hit) or "no")
                     + " |")
    observed, p = bearing_chance(ridges, timed_pairs)
    lines += ["", f"Chance: {observed} ridge(s) agree in bearing with a timing match; with the ridges' "
              f"bearings shuffled among themselves ({PERMUTATIONS} times), as many or more "
              f"agree in {p:.0%} of shuffles."]
    lines += ["", f"A storm explains its band when it ranks at least {MIN_RANK}, beats "
              f"every time control by {MARGIN}, its sector carries x{DIR_RATIO} either "
              f"turned sector's energy, and coverage is at least {MIN_COVERAGE:.0%}. A best "
              "track is NHC's analysis; the swell path is assumed open deep water."]
    return "\n".join(lines)


def run(data_dir: Path, min_kt: int = MIN_KT) -> str:
    from . import origin
    from .siting import load_coordinates
    from .transform import load_spectra

    tracks = load_tracks(data_dir)
    if not tracks:
        return ("no b-decks archived in data/besttracks/: run collector.besttracks on "
                "Actions (origin-tracks.yml)")
    positions = load_coordinates()
    all_bands = bands(tracks, positions, min_kt)
    fields: dict[str, Field] = {}
    results = []
    for band in all_bands:
        if band.station not in fields:
            try:
                fields[band.station] = Field(load_spectra(Path(data_dir) / "spectra" / band.station))
            except (FileNotFoundError, ValueError):
                fields[band.station] = Field([])
        results.append(evaluate(band, fields[band.station]))
    archives = origin.load_archives(data_dir)
    ridges = origin.arrivals(archives["46232"], archives, positions.get("46232"))
    ridge_bands = [b for b in all_bands if b.station == RIDGE_STATION]
    days = [evaluate(d, fields[DAY_STATION]) for b in all_bands if b.station == DAY_STATION
            for d in by_day(b)] if DAY_STATION in fields else []
    return report(results, ridges, ridge_bands, days)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--min-kt", type=int, default=MIN_KT)
    args = parser.parse_args(argv)
    text = run(args.data_dir, args.min_kt)
    print(text)
    write_step_summary(text)
    return 0 if not text.startswith("no b-decks") else 1


if __name__ == "__main__":
    sys.exit(main())
