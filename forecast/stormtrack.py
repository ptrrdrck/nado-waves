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

What it does not know: the path. Deep water and a great circle are assumed;
Baja's coast, the islands and refraction near the buoy are not modelled, which
matters most at 46232 for storms south of ~150° (BRIEFING §37: 46232 reads the
south-south-east 20-37° off). 46047 is read first for that reason. A best
track is NHC's analysis, not an observation of the swell.
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

    def contains(self, time: datetime, freq_hz: float, shift: timedelta = timedelta(0)) -> bool:
        for fix, d in zip(self.fixes, self.distances):
            if abs((time - shift - arrival(fix, freq_hz, d)).total_seconds()) <= TOL_H * 3600:
                return True
        return False


def bands(tracks: dict[str, list[Fix]], positions: dict[str, tuple[float, float]],
          min_kt: int = MIN_KT) -> list[Band]:
    out = []
    for storm, fixes in tracks.items():
        strong = [f for f in fixes if f.vmax_kt >= min_kt]
        if not strong:
            continue
        name = next((f.name for f in fixes if f.name), "") or storm
        for station in STATIONS:
            home = positions.get(station)
            if home is None:
                continue
            ds = [great_circle_km(home, (f.lat, f.lon)) for f in strong]
            bs = [initial_bearing(home, (f.lat, f.lon)) for f in strong]
            x = sum(math.cos(math.radians(b)) for b in bs)
            y = sum(math.sin(math.radians(b)) for b in bs)
            out.append(Band(storm, name, station, strong, ds,
                            math.degrees(math.atan2(y, x)) % 360.0,
                            max(f.vmax_kt for f in strong)))
    return out


@dataclass
class Score:
    rank: float | None
    coverage: float
    cells: int
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
        ranks = [s.rank for s in self.shifted.values() if s.rank is not None]
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
                and a.coverage >= MIN_COVERAGE and a.rank >= MIN_RANK
                and a.rank >= c + MARGIN and d >= DIR_RATIO)


class Field:
    """One buoy's sector energy, computed once per (center, bin, hour)."""

    def __init__(self, spectra, spread: str = "mem"):
        self.spectra = [s.with_spread(spread) for s in spectra]
        self.times = [s.time for s in self.spectra]
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

    def ranked(self, center: float) -> dict[int, list[float]]:
        """Each bin's energies sorted, for mid-rank lookups."""

        key = ("sorted", round(center) % 360)
        if key not in self._cache:
            self._cache[key] = {i: sorted(v) for i, v in self.energy(center).items()}
        return self._cache[key]

    def score(self, band: Band, center: float, shift: timedelta = timedelta(0)) -> Score:
        """Mean in-band rank within each bin's own distribution, and coverage.

        Coverage is the share of the band's (hour, bin) cells inside the
        archive's span that have a spectrum: a band over a 16-day outage is not
        evidence either way, and says so.
        """

        if not self.times:
            return Score(None, 0.0, 0)
        energy = self.energy(center)
        ordered = self.ranked(center)
        start, end = self.times[0], self.times[-1]
        by_time = {t: k for k, t in enumerate(self.times)}
        ratios, raw, wanted, have = [], [], 0, 0
        hour = timedelta(hours=1)
        for i in self.bins:
            f = self.freqs[i]
            lo = min(arrival(x, f, d) for x, d in zip(band.fixes, band.distances)) + shift
            hi = max(arrival(x, f, d) for x, d in zip(band.fixes, band.distances)) + shift
            t = (lo - timedelta(hours=TOL_H)).replace(minute=0, second=0, microsecond=0)
            while t <= hi + timedelta(hours=TOL_H):
                if start <= t <= end and band.contains(t, f, shift):
                    wanted += 1
                    k = by_time.get(t)
                    if k is None:
                        k = next((by_time[u] for u in (t + timedelta(minutes=20),
                                                       t - timedelta(minutes=40))
                                  if u in by_time), None)
                    if k is not None:
                        have += 1
                        x, pool = energy[i][k], ordered[i]
                        raw.append(x)
                        below = bisect.bisect_left(pool, x)
                        equal = bisect.bisect_right(pool, x) - below
                        ratios.append((below + 0.5 * equal) / len(pool))
                t += hour
        if not ratios:
            return Score(None, 0.0, wanted)
        return Score(statistics.fmean(ratios), have / wanted if wanted else 0.0, wanted,
                     statistics.fmean(raw))


def evaluate(band: Band, field_: Field) -> Result:
    result = Result(band, field_.score(band, band.bearing))
    for d in SHIFT_DAYS:
        result.shifted[d] = field_.score(band, band.bearing, timedelta(days=d))
    for t in TURN_DEG:
        result.turned[t] = field_.score(band, (band.bearing + t) % 360.0)
    return result


def ridge_share(arrival_, band: Band, shift: timedelta = timedelta(0)) -> float:
    pts = arrival_.ridge.points
    return sum(band.contains(p.time, p.freq_hz, shift) for p in pts) / len(pts)


def _fmt(score: Score) -> str:
    return "—" if score.rank is None else f"{score.rank:.2f}"


def report(results: list[Result], ridges: list, ridge_bands: list[Band]) -> str:
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
    lines += ["", "Origin's ridges at 46232 against every storm's band there "
              "(share of the ridge's points inside the band; control = best share "
              "with the band shifted):", "",
              "| ridge first seen | reading | best storm | share | control |",
              "|---|---|---|---|---|"]
    for a in ridges:
        best = None
        for band in ridge_bands:
            share = ridge_share(a, band)
            if share and (best is None or share > best[0]):
                best = (share, band)
        what = (f"{a.fit.distance_km:,.0f} km"
                + (f" at {a.bearing_deg:.0f}°" if a.bearing_deg is not None else ", no bearing"))
        if best is None:
            lines.append(f"| {a.first_utc:%Y-%m-%d %H}Z | {what} | none | 0% | |")
            continue
        share, band = best
        control = max(ridge_share(a, band, timedelta(days=d)) for d in SHIFT_DAYS)
        lines.append(f"| {a.first_utc:%Y-%m-%d %H}Z | {what} | {band.name.title()} "
                     f"({band.storm.upper()}), {band.bearing:.0f}° | {share:.0%} | {control:.0%} |")
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
    return report(results, ridges, ridge_bands)


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
