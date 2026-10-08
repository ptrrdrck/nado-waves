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

**The match** (BRIEFING §37d) is what the card states: the same question
asked of the same track moved back in time, every 12 h from just past its
band's own length to 30 days, each as of its own moment. The match is the share
of those trials the real band beats on BOTH timing (rank) and direction
(ratio), stated only when the real band is livelier than typical on both and
there are at least `MATCH_MIN_TRIALS`. It is a count, not a probability, and it
cannot tell two sources on one bearing apart: a track moved onto another
swell's schedule from its direction scores as if it sent it. So it is read
against `CONTROL_DAYS`: every track moved later, where its swell was not.

**As of a moment.** Every score takes `until`: only band cells up to it count,
ranked against the `REFERENCE_DAYS` of spectra before it, and a control needs
`MIN_CELLS` of its own. The live card asks exactly the question the backtest
asks of every past hour (`backtest`), with no look at hours not yet measured.
"""

from __future__ import annotations

import argparse
import bisect
import math
import multiprocessing
import statistics
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
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
    """m² arriving from within `half` of `center` in one frequency bin.

    The 1° bins `center - half` to `center + half`, as `Spectrum.density` lays
    them out. Read by maximum entropy, the sector is integrated in closed form
    (`spreadmethod.mem_sector`, identical to summing the bins and ~60x faster:
    what makes the live gate affordable in a collection); a bin MEM cannot read
    falls back to the two-term series, as `Spectrum.density` does.
    """

    if spectrum.spread == "mem":
        from .spreadmethod import R1_CEILING, Unrealisable, mem_sector

        vals = (spectrum.r1[index], spectrum.r2[index], spectrum.a1[index], spectrum.a2[index])
        c11 = spectrum.c11[index]
        if (c11 is not None and not math.isnan(c11)
                and not any(v is None or math.isnan(v) for v in vals) and vals[0] < R1_CEILING):
            try:
                share = mem_sector(vals[0], vals[1], vals[2], vals[3],
                                   center - half, center + half + 1)
                return max(0.0, c11) * spectrum.bin_width(index) * share
            except (Unrealisable, ZeroDivisionError, ValueError):
                pass
        spectrum = spectrum.with_spread("fourier")
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

    def arrivals(self, freq_hz: float) -> list[datetime]:
        """Every fix's arrival time at this frequency, sorted; cached."""

        cache = self.__dict__.setdefault("_arrivals", {})
        if freq_hz not in cache:
            cache[freq_hz] = sorted(arrival(f, freq_hz, d) for f, d in zip(self.fixes, self.distances))
        return cache[freq_hz]

    def contains(self, time: datetime, freq_hz: float, shift: timedelta = timedelta(0)) -> bool:
        times = self.arrivals(freq_hz)
        if not times:
            return False
        moment = time - shift
        k = bisect.bisect_left(times, moment)
        tol = TOL_H * 3600
        return any(0 <= j < len(times) and abs((times[j] - moment).total_seconds()) <= tol
                   for j in (k - 1, k))


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
        self._cells_cache: dict = {}
        self._sorted: dict = {}

    def energy(self, center: float) -> dict[int, list[float]]:
        key = round(center) % 360
        if key not in self._cache:
            self._cache[key] = {i: [sector_energy(s, i, key) for s in self.spectra]
                                for i in self.bins}
        return self._cache[key]

    def ranked(self, center: float, lo: int, hi: int) -> dict[int, list[float]]:
        """Each bin's energies over spectra lo..hi-1, sorted, for mid-rank lookups."""

        key = (round(center) % 360, lo, hi)
        if key not in self._sorted:
            if len(self._sorted) > 512:
                self._sorted.clear()
            self._sorted[key] = {i: sorted(v[lo:hi]) for i, v in self.energy(center).items()}
        return self._sorted[key]

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
        window = self._cells(band, shift, until)
        if window is None:
            return Score(None, 0.0, 0)
        lo, hi, cells, wanted = window
        energy = self.energy(center)
        ordered = self.ranked(center, lo, hi)
        ratios, raw = [], []
        for i, k in cells:
            x, pool = energy[i][k], ordered[i]
            raw.append(x)
            below = bisect.bisect_left(pool, x)
            equal = bisect.bisect_right(pool, x) - below
            ratios.append((below + 0.5 * equal) / len(pool))
        if not ratios:
            return Score(None, 0.0, wanted, 0)
        have = len(cells)
        return Score(statistics.fmean(ratios), have / wanted if wanted else 0.0, wanted, have,
                     statistics.fmean(raw))

    def _cells(self, band: Band, shift: timedelta, until: datetime | None):
        """The band's (bin, spectrum) cells as of `until`, and how many it wanted.

        The same for every sector, so kept for the last few (band, shift,
        until) asked: a trial scores its own sector and the two turned ones
        on one set of cells.
        """

        key = (id(band), shift, until)
        hit = self._cells_cache.get(key)
        # The band is held beside its cells, so its id cannot be reused
        # while the entry lives.
        if hit is not None and hit[0] is band:
            return hit[1]
        end = self.times[-1] if until is None else min(self.times[-1], until)
        start = end - timedelta(days=REFERENCE_DAYS)
        lo = bisect.bisect_left(self.times, start)
        hi = bisect.bisect_right(self.times, end)
        out = None
        if hi - lo >= MIN_CELLS:
            cells, wanted = [], 0
            hour = timedelta(hours=1)
            for i in self.bins:
                f = self.freqs[i]
                times = band.arrivals(f)
                first, last = times[0] + shift, times[-1] + shift
                t = (first - timedelta(hours=TOL_H)).replace(minute=0, second=0, microsecond=0)
                while t <= last + timedelta(hours=TOL_H):
                    if start <= t <= end and band.contains(t, f, shift):
                        wanted += 1
                        k = self.hours.get(t)
                        if k is not None and lo <= k < hi:
                            cells.append((i, k))
                    t += hour
            out = (lo, hi, cells, wanted)
        if len(self._cells_cache) > 64:
            self._cells_cache.clear()
        self._cells_cache[key] = (band, out)
        return out


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


# --- GFS-Wave's hindcast: does the model have this storm's train? ----------

#: The frequencies a band is asked about when no spectrum fixes them.
MODEL_FREQS = tuple(round(0.04 + 0.005 * k, 3) for k in range(13))


def load_hindcast(data_dir: Path, station: str) -> dict[datetime, list[tuple]]:
    """`collector.wavehindcast`'s partitions by valid hour: (hs, tp, from, wind_sea)."""

    import csv

    path = Path(data_dir) / "wave_hindcast" / f"{station}.csv"
    out: dict[datetime, list[tuple]] = {}
    if not path.exists():
        return out
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            t = datetime.fromisoformat(row["valid_utc"].replace("Z", "+00:00"))
            parts = out.setdefault(t, [])
            if row["part_tp_s"]:
                parts.append((float(row["part_hs_m"]), float(row["part_tp_s"]),
                              float(row["part_from_deg"]), row["wind_sea"] == "1"))
    return out


def model_share(band: Band, hindcast: dict, shift: timedelta = timedelta(0)) -> tuple[float | None, int]:
    """Of the hours the band is open at some frequency, the share in which the
    model has a swell partition from within the sector, at a period the band
    holds at that hour. A MODEL: it says the attribution is consistent with
    what WAVEWATCH III, which knows the storm, put in the water; it is never
    the evidence that a swell arrived."""

    open_hours = agree = 0
    for t, parts in hindcast.items():
        if not any(band.contains(t, f, shift) for f in MODEL_FREQS):
            continue
        open_hours += 1
        if any(not wind and tp > 0
               and abs((frm - band.bearing + 180) % 360 - 180) <= SECTOR_HALF_DEG
               and band.contains(t, 1.0 / tp, shift)
               for _, tp, frm, wind in parts):
            agree += 1
    return (agree / open_hours if open_hours else None), open_hours


# --- The match: how far the real band outscores the wrong ones -------------

#: The trials: the whole question moved BACK in time by every MATCH_STEP_H,
#: from just past the band's own length (a shorter shift overlaps the real
#: arrival and scores it) to MATCH_SHIFT_DAYS. Back only: live, a later hour
#: does not exist yet. The band AND its "as of" move together, so each trial is
#: ranked against its own preceding REFERENCE_DAYS, as the real one is: a fixed
#: reference made every late-September band beat quiet early August, and four
#: storms the gate had rejected scored a perfect 1.0 on timing (2026-10-03).
MATCH_SHIFT_DAYS = 30
MATCH_STEP_H = 12
#: Fewer trials than this and there is no percentage: the archive's first
#: weeks offer a band only a handful of earlier moments with a reference of
#: their own, and beating six of them is not a measurement (Lala at 46047 on
#: 27 Aug scored 6 of 6 with a typical rank and its own sector the weaker).
MATCH_MIN_TRIALS = 20


@dataclass
class Trial:
    rank: float
    direction: float


@dataclass
class MatchScore:
    """How unusual the real schedule and direction are against the same test
    on the same storm, moved back in time to when its swell was not arriving.

    `score` is the share of those trials the real one beats on BOTH counts:
    in-band rank (timing) and its sector's energy over the stronger of the two
    sectors 45° either side (direction). NOT a probability that the swell came
    from the storm, which needs a prior and an independent check this project
    does not have; and not, ever, anything about a height at the beach.

    There is no score at all unless the real band is itself above typical on
    both counts (rank over 0.5, its own sector the stronger): beating trials
    that were quieter still is not a sign of anything arriving.
    """

    actual: Trial | None
    trials: list[Trial] = field(default_factory=list)

    @property
    def above_typical(self) -> bool:
        a = self.actual
        return a is not None and a.rank > 0.5 and a.direction > 1.0

    @property
    def beaten(self) -> int:
        a = self.actual
        if a is None:
            return 0
        return sum(1 for t in self.trials if t.rank < a.rank and t.direction < a.direction)

    @property
    def score(self) -> float | None:
        if not self.above_typical or len(self.trials) < MATCH_MIN_TRIALS:
            return None
        return self.beaten / len(self.trials)


def trial(band: Band, field_: Field, until: datetime | None,
          shift: timedelta = timedelta(0)) -> Trial | None:
    """The band's rank and direction ratio, as of `until`, moved by `shift`."""

    at = None if until is None else until + shift
    own = field_.score(band, band.bearing, shift, at)
    if own.rank is None or own.have < MIN_CELLS or own.energy is None:
        return None
    turned = [field_.score(band, (band.bearing + t) % 360.0, shift, at) for t in TURN_DEG]
    others = [t.energy for t in turned if t.energy is not None]
    if not others:
        return None
    return Trial(own.rank, own.energy / max(max(others), 1e-12))


def _span_h(band: Band, freqs) -> float:
    """How long the band lasts at the buoy, at its longest-lasting frequency."""

    return max((band.arrivals(f)[-1] - band.arrivals(f)[0]).total_seconds() / 3600.0
               for f in freqs) + 2 * TOL_H


def match(band: Band, field_: Field, until: datetime | None = None) -> MatchScore:
    """The match as of `until`: the real band against itself moved back."""

    if not band.fixes or not field_.times:
        return MatchScore(None)
    if until is None:
        until = field_.times[-1]
    real = trial(band, field_, until)
    if real is None:
        return MatchScore(None)
    out = MatchScore(real)
    shift = max(_span_h(band, field_.freqs.values()) + 24.0, 72.0)
    while shift <= MATCH_SHIFT_DAYS * 24:
        t = trial(band, field_, until, timedelta(hours=-shift))
        if t is not None:
            out.trials.append(t)
        shift += MATCH_STEP_H
    return out


# --- As of each past hour: what the card would have said ------------------

#: How often the backtest asks.
BACKTEST_STEP_H = 6
#: The control: every storm's own track moved this many days LATER, where its
#: swell was not arriving, asked the same question at the same moments of its
#: band. How often a misplaced track would have been named, and how strongly,
#: is what the words on the card are read against (BRIEFING §37d). Later only:
#: the spectra start 2026-08-04, so an earlier move leaves no trials.
CONTROL_DAYS = (8, 12, 16, 20, 24)


def arriving_now(band: Band, field_: Field, at: datetime) -> bool:
    return bool(band.fixes) and any(band.contains(at, f) for f in field_.freqs.values())


def moments(band: Band, field_: Field, step_h: int = BACKTEST_STEP_H) -> list[datetime]:
    """Every `step_h`-hour moment some of the band is arriving, in the archive."""

    if not band.fixes or not field_.times:
        return []
    freqs = list(field_.freqs.values())
    first = min(band.arrivals(f)[0] for f in freqs) - timedelta(hours=TOL_H)
    last = max(band.arrivals(f)[-1] for f in freqs) + timedelta(hours=TOL_H)
    t = max(first, field_.times[0]).replace(minute=0, second=0, microsecond=0)
    last = min(last, field_.times[-1])
    out = []
    while t <= last:
        if arriving_now(band, field_, t):
            out.append(t)
        t += timedelta(hours=step_h)
    return out


def backtest(band: Band, field_: Field) -> list[tuple[datetime, float | None]]:
    """The match the card would have stated at each moment, None where none."""

    return [(t, match(band, field_, until=t).score) for t in moments(band, field_)]


def misplaced(band: Band, days: float) -> Band:
    """The same storm, its every fix `days` later: a track whose swell was not there."""

    moved = [Fix(f.storm, f.name, f.time + timedelta(days=days), f.lat, f.lon, f.vmax_kt)
             for f in band.fixes]
    return Band(band.storm, band.name, band.station, moved, band.distances, band.bearing,
                band.peak_kt, band.station_position, band.blocked)


# --- Live: the storms whose swell is arriving now, and how well they match ---

#: A card train is this storm's when its period sits within 1.5 bins of a
#: frequency the band says is arriving now (Origin's own tolerance).
TRAIN_MATCH_HZ = 0.0075

#: How far a direction may sit from a storm's bearing and still be that
#: storm's: the match's turned sectors sit 45° either side and count as
#: somewhere else. Read by `originhistory` for Origin's arrivals, and here for
#: which card train the storm names.
SAME_SOURCE_DEG = 45.0

#: Spectra loaded for the live match: the reference window behind the
#: furthest trial, plus the longest band.
LIVE_DAYS = REFERENCE_DAYS + MATCH_SHIFT_DAYS + 20
#: The card names a storm whose match is at least this, and says how strong
#: with the first word whose floor it reaches.
MATCH_SHOW = 0.5
MATCH_WORDS = ((0.9, "strong"), (0.7, "partial"), (0.5, "weak"), (0.0, "none"))


def _sent_by(band: Band, freq_hz: float, at: datetime) -> tuple[Fix, float] | None:
    """The fix whose train at `freq_hz` reaches the buoy nearest `at`."""

    best = None
    for fix, d in zip(band.fixes, band.distances):
        gap = abs((arrival(fix, freq_hz, d) - at).total_seconds())
        if gap <= TOL_H * 3600 and (best is None or gap < best[0]):
            best = (gap, fix, d)
    return (best[1], best[2]) if best else None


def live(tracks: dict[str, list[Fix]], fields: dict[str, Field], at: datetime,
         positions: dict[str, tuple[float, float]], trains_now: dict[str, list[dict]],
         land=(), min_kt: int = MIN_KT) -> list[dict]:
    """Every storm the card may name at `at`, as `now.json` carries it.

    Named when some of its swell is arriving now at one of the
    `GATE_STATIONS` and, AS OF `at`, its band so far there matches at least
    `MATCH_SHOW` (`match`), with the match beside it at each gate buoy where
    it has one. Where it is shown is 46232's question: a site (a break, or
    "buoy") shows it when one of its card trains has a period the storm's band
    at 46232 says is arriving now, from fixes with open water to 46232. The
    position quoted is NHC's fix that sent that train, never Origin's
    dispersion distance.
    """

    found: dict[str, dict] = {}
    for band in bands(tracks, positions, min_kt, land):
        if band.station not in GATE_STATIONS or band.station not in fields:
            continue
        field_ = fields[band.station]
        if not band.fixes or not any(band.contains(at, f) for f in field_.freqs.values()):
            continue
        m = match(band, field_, until=at)
        if m.score is None:
            continue
        entry = found.setdefault(band.storm, {
            "storm": band.storm, "name": band.name.title(), "peak_kt": band.peak_kt,
            "match": {}})
        # How long its band has been arriving at this buoy, as of `at`: the
        # hours the match has read so far (from the archive's first spectrum
        # when the band began before it).
        began = max(min(band.arrivals(f)[0] for f in field_.freqs.values())
                    - timedelta(hours=TOL_H), field_.times[0])
        entry["match"][band.station] = {"score": round(m.score, 2), "beaten": m.beaten,
                                        "trials": len(m.trials),
                                        "hours": max(0, round((at - began).total_seconds() / 3600))}
    out = []
    for entry in found.values():
        best = max(v["score"] for v in entry["match"].values())
        if best < MATCH_SHOW:
            continue
        entry["best"] = best
        entry["word"] = match_word(best)
        entry["sites"] = _sites(tracks[entry["storm"]], entry["storm"], at, positions,
                                trains_now, land, min_kt)
        out.append(entry)
    return sorted(out, key=lambda e: -e["best"])


def match_word(score: float) -> str:
    return next(word for floor, word in MATCH_WORDS if score >= floor)


def _sites(fixes: list[Fix], storm: str, at: datetime, positions: dict,
           trains_now: dict[str, list[dict]], land, min_kt: int) -> dict:
    """{site: the card train this storm's band at 46232 says is arriving}."""

    here = next((b for b in bands({storm: fixes}, positions, min_kt, land)
                 if b.station == RIDGE_STATION), None)
    sites = {}
    if here is None or not here.fixes:
        return sites
    for site, trains in trains_now.items():
        found = []
        for train in trains or []:
            period = train.get("period_s")
            if not period or train.get("local") or train.get("wind_sea"):
                continue
            f = 1.0 / period
            # Only the swell band the match itself scored: a 7 s train can be
            # on the schedule of a storm 2,000 km off, and it is still the
            # local sea.
            if not BAND_HZ[0] - TRAIN_MATCH_HZ <= f <= BAND_HZ[1] + TRAIN_MATCH_HZ:
                continue
            if not any(abs(g - f) <= TRAIN_MATCH_HZ and here.contains(at, g)
                       for g in MODEL_FREQS + (f,)):
                continue
            sent = _sent_by(here, f, at) or next(
                (_sent_by(here, g, at) for g in MODEL_FREQS
                 if abs(g - f) <= TRAIN_MATCH_HZ and _sent_by(here, g, at)), None)
            if sent is None:
                continue
            fix, d = sent
            bearing = initial_bearing(positions[RIDGE_STATION], (fix.lat, fix.lon))
            found.append((train, {
                "train_period_s": period,
                "fix_utc": fix.time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "lat": fix.lat, "lon": fix.lon,
                "distance_km": round(d),
                "bearing_deg": round(bearing),
                "vmax_kt": fix.vmax_kt,
            }))
        # A band from two directions is two trains since BRIEFING §40, often a
        # second apart and both on the storm's schedule: the storm's is the one
        # from its side. Card order (the first that fits) only when none is.
        if found:
            sites[site] = next((hit for train, hit in found
                                if _from_storm(train, hit["bearing_deg"])), found[0][1])
    return sites


def _from_storm(train: dict, bearing: float) -> bool:
    """Does this train come from within `SAME_SOURCE_DEG` of the storm's
    bearing from the buoy? Either of its directions, when it holds two."""

    heads = [h for h, _ in train.get("lobes") or []] or [train.get("from_deg")]
    return any(h is not None and abs((h - bearing + 180.0) % 360.0 - 180.0) <= SAME_SOURCE_DEG
               for h in heads)


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


def _tier_row(label: str, group: list[list[tuple[datetime, float | None]]]) -> str:
    """One row of shares: per moment, and per track ever reaching each word."""

    words = [(lo, w) for lo, w in MATCH_WORDS if lo >= MATCH_SHOW]
    scored = [x for series in group for _, x in series if x is not None]
    tracks = [[x for _, x in series if x is not None] for series in group if series]
    share = lambda n, d: f"{n / d:.0%}" if d else "—"
    per_moment = [share(sum(1 for x in scored if match_word(x) == w), len(scored))
                  for _, w in words]
    ever = [share(sum(1 for t in tracks if any(x >= lo for x in t)), len(tracks))
            for lo, _ in words]
    moments_ = sum(len(series) for series in group)
    return (f"| {label} | {len(tracks)} | {moments_} | {len(scored)} | "
            f"{share(sum(1 for x in scored if x >= MATCH_SHOW), len(scored))} | "
            + " | ".join(per_moment) + " | "
            + " | ".join([ever[-1]] + ever) + " |")


#: The per-day table is drawn at the buoy the islands do not shadow.
DAY_STATION = "46047"


def report(results: list[Result], ridges: list, ridge_bands: list[Band],
           days: list[Result] = (), models: dict | None = None,
           shown: dict | None = None, controls: list | None = None) -> str:
    lines = [
        f"Hurricanes run forward to the buoys (fixes >= the strength asked; sector "
        f"+/-{SECTOR_HALF_DEG}°, timing +/-{TOL_H:.0f} h; rank = in-band cells' mean place in "
        f"their frequency's own distribution, 0.5 typical)",
        "",
        "| storm | buoy | fixes open (blocked by land) | bearing | distance | rank | coverage | "
        f"time controls ({', '.join(f'{d:+d} d' for d in SHIFT_DAYS)}) | own sector / turned "
        "±45° | explains? | GFS-Wave has it (best shifted) |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        b = r.band
        if not b.fixes:
            lines.append(f"| {b.name.title()} ({b.storm.upper()}), {b.peak_kt} kt | {b.station} | "
                         f"0 ({b.blocked}) | every fix behind land | | | | | | no | |")
            continue
        if r.actual.cells == 0:
            continue
        model = models.get((b.storm, b.station)) if models else None
        model_text = ("—" if not model or model[0] is None
                      else f"{model[0]:.0%} ({model[1]:.0%})")
        lines.append(
            f"| {b.name.title()} ({b.storm.upper()}), {b.peak_kt} kt | {b.station} | "
            f"{len(b.fixes)} ({b.blocked}) | "
            f"{b.bearing:.0f}° | {min(b.distances):,.0f}-{max(b.distances):,.0f} km | "
            f"{_fmt(r.actual)} | {r.actual.coverage:.0%} | "
            f"{' '.join(_fmt(r.shifted[d]) for d in SHIFT_DAYS)} | "
            f"{'—' if r.direction_ratio is None else f'x{r.direction_ratio:.1f}'} | "
            f"{'**yes**' if r.explains else 'no'} | {model_text} |")
    if shown is not None:
        lines += ["", "The match the card would have stated, asked every "
                  f"{BACKTEST_STEP_H} h while the band was arriving, as of that moment (the "
                  f"band so far against itself moved back {MATCH_SHIFT_DAYS} days at most, each "
                  f"ranked against the {REFERENCE_DAYS} days before it; no later hour seen), at "
                  f"the buoys that name a storm ({', '.join(GATE_STATIONS)}). Named at "
                  f"{MATCH_SHOW:.0%} or more; " + ", ".join(
                      f"{w} from {lo:.0%}" for lo, w in MATCH_WORDS if lo >= MATCH_SHOW) + ".", "",
                  "| storm | buoy | moments arriving | with a match | named | "
                  + " / ".join(w for lo, w in MATCH_WORDS if lo >= MATCH_SHOW)
                  + " | highest | first named | last named |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for (name, station), series in shown.items():
            if not series:
                continue
            scored = [x for _, x in series if x is not None]
            named = [(t, x) for t, x in series if x is not None and x >= MATCH_SHOW]
            tiers = " / ".join(str(sum(1 for _, x in named if match_word(x) == w))
                               for lo, w in MATCH_WORDS if lo >= MATCH_SHOW)
            lines.append(
                f"| {name} | {station} | {len(series)} | {len(scored)} | {len(named)} | {tiers} | "
                + (f"{max(scored):.0%}" if scored else "—") + " | "
                + (f"{named[0][0]:%m-%d %H}Z | {named[-1][0]:%m-%d %H}Z |" if named
                   else "never | |"))
    if controls is not None:
        lines += ["", f"Control: every track above moved {', '.join(str(d) for d in CONTROL_DAYS)} "
                  "days LATER, where its swell was not arriving, asked the same question at "
                  "the same moments of its band. What a misplaced track would have been "
                  "called:", "",
                  "| | tracks | moments arriving | with a match | named, of those | "
                  + " | ".join(w for lo, w in MATCH_WORDS if lo >= MATCH_SHOW)
                  + " | tracks ever named | " + " | ".join(
                      f"ever {w}" for lo, w in MATCH_WORDS if lo >= MATCH_SHOW) + " |",
                  "|---|---|---|---|---|" + "---|" * (2 * len(
                      [w for lo, w in MATCH_WORDS if lo >= MATCH_SHOW]) + 1)]
        for label, group in (("real tracks", list(shown.values()) if shown else []),
                             ("misplaced", controls)):
            lines.append(_tier_row(label, group))
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
    lines += [""] + ridge_lines(ridges, ridge_bands)
    lines += ["", f"A storm explains its band when it ranks at least {MIN_RANK}, beats "
              f"every time control by {MARGIN}, its sector carries x{DIR_RATIO} either "
              f"turned sector's energy, and coverage is at least {MIN_COVERAGE:.0%}. A best "
              "track is NHC's analysis; the swell path is assumed open deep water."]
    return "\n".join(lines)


def _reading(a) -> str:
    """A ridge's reading as the report states it: a bearing, a bearing
    withheld because 46047's energy was split (BRIEFING §38), or none."""

    if a.bearing_deg is not None:
        return f"{a.fit.distance_km:,.0f} km at {a.bearing_deg:.0f}°"
    lobes = getattr(a, "bearing_lobes", None) or []
    if lobes:
        split = ", ".join(f"{h:.0f}° {share:.0%}" for h, share in lobes)
        return f"{a.fit.distance_km:,.0f} km, bearing withheld ({a.bearing_from} split: {split})"
    return f"{a.fit.distance_km:,.0f} km, no bearing"


def ridge_lines(ridges: list, ridge_bands: list[Band]) -> list[str]:
    """Origin's ridges against each storm-day's band: the table and the
    shuffle. A withheld bearing attributes nothing and takes no part in the
    shuffle: it is not a bearing."""

    lines = ["Origin's ridges at 46232 against each storm-DAY's band there. Timing "
             f"alone matches almost anything (a whole track's band is days wide), so a "
             f"ridge is attributed only when >= {RIDGE_SHARE:.0%} of its points sit in a "
             f"day's band, under {RIDGE_SHARE_CONTROL:.0%} with that band shifted, AND its "
             f"bearing is within {RIDGE_BEARING_DEG}° of the storm's that day:", "",
             "| ridge first seen | reading | timing matches (storm, day, share, bearing) | "
             "attributed |", "|---|---|---|---|"]
    attributed, timed_pairs = matches(ridges, ridge_bands)
    for a in ridges:
        timed = [m for m in timed_pairs if m[0] is a]
        listed = "; ".join(f"{d.name.title()} {d.fixes[0].time:%m-%d} {sh:.0%} at {d.bearing:.0f}°"
                           for _, d, sh in timed) or "none"
        hit = [m for m in attributed if m[0] is a]
        lines.append(f"| {a.first_utc:%Y-%m-%d %H}Z | {_reading(a)} | {listed} | "
                     + ("; ".join(f"**{d.name.title()}** ({d.fixes[0].time:%m-%d}), "
                                  f"storm {d.distances[0]:,.0f} km" for _, d, _ in hit) or "no")
                     + " |")
    observed, p = bearing_chance(ridges, timed_pairs)
    lines += ["", f"Chance: {observed} ridge(s) agree in bearing with a timing match; with the ridges' "
              f"bearings shuffled among themselves ({PERMUTATIONS} times), as many or more "
              f"agree in {p:.0%} of shuffles."]
    return lines


def ridges_run(data_dir: Path, min_kt: int = MIN_KT, until: datetime | None = None) -> str:
    """Only the ridge section, on the spectra archived to `until`: what
    re-checks the ridges after a change to how Origin reads a bearing,
    without moving every other number the full report states."""

    from . import origin
    from .landpath import load_land
    from .siting import load_coordinates

    tracks = load_tracks(data_dir)
    if not tracks:
        return "no b-decks archived in data/besttracks/"
    positions = load_coordinates()
    ridge_bands = [b for b in bands(tracks, positions, min_kt, load_land(str(data_dir)))
                   if b.station == RIDGE_STATION]
    archives = origin.load_archives(data_dir)
    if until is not None:
        archives = {k: [s for s in v if s.time <= until] for k, v in archives.items()}
    ridges = origin.arrivals(archives["46232"], archives, positions.get("46232"))
    head = (f"Spectra to {until:%Y-%m-%d %H}Z; " if until else "") + \
        f"bearing buoys {', '.join(origin.BEARING_STATIONS)}; split share {origin.SPLIT_SHARE:.0%}."
    return "\n".join([head, ""] + ridge_lines(ridges, ridge_bands))


def run(data_dir: Path, min_kt: int = MIN_KT) -> str:
    from . import origin
    from .siting import load_coordinates
    from .transform import load_spectra

    tracks = load_tracks(data_dir)
    if not tracks:
        return ("no b-decks archived in data/besttracks/: run collector.besttracks on "
                "Actions (origin-tracks.yml)")
    from .landpath import load_land

    positions = load_coordinates()
    all_bands = bands(tracks, positions, min_kt, load_land(str(data_dir)))
    fields: dict[str, Field] = {}
    hindcasts: dict[str, dict] = {}
    results, models = [], {}
    for band in all_bands:
        if band.station not in fields:
            try:
                fields[band.station] = Field(load_spectra(Path(data_dir) / "spectra" / band.station))
            except (FileNotFoundError, ValueError):
                fields[band.station] = Field([])
            hindcasts[band.station] = load_hindcast(data_dir, band.station)
        results.append(evaluate(band, fields[band.station]))
        if band.fixes and hindcasts[band.station]:
            share, _ = model_share(band, hindcasts[band.station])
            controls = [model_share(band, hindcasts[band.station], timedelta(days=d))[0]
                        for d in SHIFT_DAYS]
            controls = [c for c in controls if c is not None]
            models[(band.storm, band.station)] = (share, max(controls) if controls else 0.0)
    archives = origin.load_archives(data_dir)
    ridges = origin.arrivals(archives["46232"], archives, positions.get("46232"))
    ridge_bands = [b for b in all_bands if b.station == RIDGE_STATION]
    days = [evaluate(d, fields[DAY_STATION]) for b in all_bands if b.station == DAY_STATION
            for d in by_day(b)] if DAY_STATION in fields else []
    gated = [b for b in all_bands if b.station in GATE_STATIONS and b.fixes]
    jobs = [(b, 0) for b in gated] + [(b, d) for b in gated for d in CONTROL_DAYS]
    global _FIELDS
    _FIELDS = fields
    with multiprocessing.get_context("fork").Pool() as pool:
        series = pool.map(_backtest_job, jobs, chunksize=1)
    shown = {(b.name.title(), b.station): out for (b, d), out in zip(jobs, series) if d == 0}
    controls = [out for (_, d), out in zip(jobs, series) if d]
    return report(results, ridges, ridge_bands, days, models, shown, controls)


#: The fields a forked backtest worker reads: set by `run` before it forks.
_FIELDS: dict = {}


def _backtest_job(job: tuple[Band, float]) -> list[tuple[datetime, float | None]]:
    band, days = job
    return backtest(misplaced(band, days) if days else band, _FIELDS[band.station])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--min-kt", type=int, default=MIN_KT)
    parser.add_argument("--ridges", action="store_true",
                        help="only Origin's ridges against the storm-day bands")
    parser.add_argument("--until", help="with --ridges: spectra to this UTC time, YYYY-MM-DDTHH")
    args = parser.parse_args(argv)
    if args.ridges:
        until = (datetime.strptime(args.until, "%Y-%m-%dT%H").replace(tzinfo=timezone.utc)
                 if args.until else None)
        text = ridges_run(args.data_dir, args.min_kt, until)
        print(text)
        return 0
    text = run(args.data_dir, args.min_kt)
    print(text)
    write_step_summary(text)
    return 0 if not text.startswith("no b-decks") else 1


if __name__ == "__main__":
    sys.exit(main())
