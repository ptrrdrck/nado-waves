"""How long swell takes from Tanner Banks to Point Loma South, and on to the breaks.

    python -m forecast.upstreamlag            # the report
    python -m forecast.upstreamlag --write    # ... into docs/upstream_lag.md

The owner's request (2026-10-16): when the LIVE briefing says "Tanner Banks
has had a west-northwest train since midnight", say when it reaches the coast.
46047 is the one unshadowed buoy (BRIEFING §3a, §33), 198 km west of 46232,
so swell from the west passes it first.

Two legs, measured apart:

1. **46047 → 46232**, from the archived spectra at both. In deep water a
   group travels at cg = gT/4π, and a train from heading θ passes 46232 after
   the projection of the buoy-to-buoy offset onto the direction it travels,
   over cg (`deep_water_lag_h`). That is physics; the archive is the check.
   Three ways of reading the lag off the archive were tried, each with its
   control (the report says which survived):

   - ridge to ridge: Origin's ridges at both buoys, a common-slope line
     through each pair, the lag the offset between them;
   - onset to onset: a band's energy in 46047's sector rising ×3, timed at the
     midpoint of the rise in log energy at both buoys, against the same search
     with 46232's series moved by whole days;
   - the whole series: the band-and-sector log energy, smoothed and with its
     72 h mean removed, cross-correlated over lags, with 90% intervals by
     resampling 3-day blocks, and the south sector as the direction control
     (the geometry puts its lag 2–3 h shorter than the north-west's).

2. **46232 → each break**, computed along the refracted rays
   (`forecast.raytrace.leg_table` → `data/nearshore/<break>_leg.csv`):
   ∫ ds/cg from the ray's exit to the 5 m start, plus the plane-wave offset
   from the buoy to that exit. Not measured: nothing observes the beach.

Reports, never edits. Pure Python down to the report's statistics, which use
numpy (the precompute's requirement); the briefing imports only the pure part.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from .spreadmethod import Unrealisable, mem_sector
from .swell import group_velocity

ROOT = Path(__file__).resolve().parent.parent
SPECTRA = ROOT / "data" / "spectra"
NEARSHORE = ROOT / "data" / "nearshore"
DOC = ROOT / "docs" / "upstream_lag.md"

UPSTREAM = "46047"
ANCHOR = "46232"

#: 46047's sectors, degrees FROM, clockwise. "west" and "north-west" are what
#: the briefing may time; "south" is the control: the geometry puts its lag
#: 2–3 h under the north-west's, so a method that cannot tell them apart is
#: measuring its own window, not the swell.
SECTORS = {"west": (250.0, 280.0), "north-west": (280.0, 330.0), "south": (170.0, 230.0)}
TIMED = ("west", "north-west")

#: The same swell at 46232, which reads north-west swell 50–74° too far south
#: and pins a westerly lobe near 270° (BRIEFING §37, §38): its energy is taken
#: over the whole westerly half there, never at 46047's bearing.
ANCHOR_SECTORS = {"west": (240.0, 330.0), "north-west": (240.0, 330.0), "south": (160.0, 240.0)}

#: Period bands, seconds. Past 17 s the archive's swell bands hold too little
#: energy to time (their correlations peak below 0.55 and at negative lags).
BANDS_S = ((10.0, 12.0), (12.0, 14.0), (14.0, 17.0))

#: A rise is energy up by this factor (×3, height ×1.7) within RISE_WITHIN_H,
#: from its lowest point, and above RISE_FLOOR_M2 (a band Hs of ~0.18 m).
RISE_FACTOR = 3.0
RISE_WITHIN_H = 30.0
RISE_FLOOR_M2 = 0.002

#: Smoothing: a running median over ± this many hours. Onsets use the short
#: one, the whole-series correlation the long one; its trend is removed over
#: ± HIGHPASS_H.
SMOOTH_ONSET_H = 1.5
SMOOTH_SERIES_H = 3.0
HIGHPASS_H = 36.0

#: Two stamps are the same moment within this many minutes. 46047 reports at
#: :20 and :50, 46232 at :00; nothing is interpolated between them.
PAIR_MIN = 15.0

LAGS_H = [k / 2.0 for k in range(-24, 49)]
BOOTSTRAP = 200
BLOCK_DAYS = 3


# ------------------------------------------------------------------ geometry

def offset_km(coords: dict[str, tuple[float, float]] | None = None) -> tuple[float, float]:
    """(east, north) km from 46047 to 46232, flat over 200 km (the great circle
    differs by under 0.1%)."""

    if coords is None:
        from .siting import load_coordinates
        coords = load_coordinates()
    a, b = coords[UPSTREAM], coords[ANCHOR]
    east = (b[1] - a[1]) * 111.32 * math.cos(math.radians((a[0] + b[0]) / 2.0))
    north = (b[0] - a[0]) * 110.57
    return east, north


def deep_water_lag_h(period_s: float, from_deg: float,
                     coords: dict[str, tuple[float, float]] | None = None) -> float:
    """Hours from 46047 to 46232 for a plane wave group of this period and
    heading in deep water. Negative when 46232 is up-swell."""

    east, north = offset_km(coords)
    toward = math.radians(from_deg + 180.0)
    along_km = east * math.sin(toward) + north * math.cos(toward)
    return along_km * 1000.0 / group_velocity(period_s) / 3600.0


@dataclass(frozen=True)
class Leg:
    break_id: str
    period_s: float
    lo_min: float
    hi_min: float


def load_leg(break_id: str, directory: Path = NEARSHORE) -> list[dict]:
    path = directory / f"{break_id}_leg.csv"
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return [{k: float(v) for k, v in row.items()} for row in csv.DictReader(fh)]


#: A heading at 46232 is matched to rays leaving deep water within this many
#: degrees of it.
LEG_HEADING_DEG = 5.0


def leg(break_id: str, period_s: float, from_deg: float,
        rows: list[dict] | None = None) -> Leg | None:
    """Minutes from 46232 to the break at this period and offshore heading:
    the range over the unblocked rays within LEG_HEADING_DEG of it, at the
    tabled period nearest. None when no ray from that heading reaches it."""

    rows = load_leg(break_id) if rows is None else rows
    if not rows:
        return None
    periods = sorted({r["period_s"] for r in rows})
    nearest = min(periods, key=lambda p: abs(p - period_s))
    hits = [r["from_buoy_min"] for r in rows if r["period_s"] == nearest
            and abs((r["off_from_deg"] - from_deg + 180.0) % 360.0 - 180.0) <= LEG_HEADING_DEG]
    if not hits:
        return None
    return Leg(break_id, nearest, min(hits), max(hits))


#: Over a sector the leg is quoted as the middle half of its rays: the few
#: that wrap round Point Loma's tip from the north-north-west leave deep water
#: far up-swell of 46232 (north at 13 s: one ray of six at 329°, 1.9 min) and
#: would stretch a min-to-max range to nothing.
LEG_SPREAD = (0.25, 0.75)


def leg_over(break_id: str, period_s: float, sector: tuple[float, float],
             rows: list[dict] | None = None) -> Leg | None:
    """The leg over every unblocked ray whose offshore heading is inside
    `sector` (clockwise), LEG_SPREAD of them: what the briefing quotes before a train reaches
    46232, whose own heading for it is not yet read."""

    rows = load_leg(break_id) if rows is None else rows
    if not rows:
        return None
    periods = sorted({r["period_s"] for r in rows})
    nearest = min(periods, key=lambda p: abs(p - period_s))
    lo, hi = sector
    span = (hi - lo) % 360.0
    hits = [r["from_buoy_min"] for r in rows if r["period_s"] == nearest
            and (r["off_from_deg"] - lo) % 360.0 <= span]
    if not hits:
        return None
    return Leg(break_id, nearest, _pct(hits, LEG_SPREAD[0]), _pct(hits, LEG_SPREAD[1]))


# ------------------------------------------------------------------ series

def band_energy(spectrum, band_s: tuple[float, float], sector: tuple[float, float]) -> float | None:
    """m² in a period band from a sector, by maximum entropy in closed form.
    None when any bin in the band cannot be read by MEM: never a Fourier
    stand-in, never a partial sum."""

    lo_hz, hi_hz = 1.0 / band_s[1], 1.0 / band_s[0]
    total = 0.0
    for i, f in enumerate(spectrum.frequencies):
        if not lo_hz <= f < hi_hz:
            continue
        vals = (spectrum.r1[i], spectrum.r2[i], spectrum.a1[i], spectrum.a2[i])
        if any(v is None or math.isnan(v) for v in vals):
            return None
        try:
            share = mem_sector(*vals, *sector)
        except (Unrealisable, ValueError, ZeroDivisionError):
            return None
        total += spectrum.c11[i] * spectrum.bin_width(i) * share
    return total


def series(spectra, band_s, sector) -> list[tuple[datetime, float]]:
    out = []
    for s in spectra:
        e = band_energy(s, band_s, sector)
        if e is not None:
            out.append((s.time, e))
    return out


def smooth_log(ser: list[tuple[datetime, float]], half_h: float) -> list[tuple[datetime, float]]:
    """Running median of log energy over ± half_h, at each stamp's own time."""

    times = [t for t, _ in ser]
    logs = [math.log(max(v, 1e-6)) for _, v in ser]
    out = []
    for k, t in enumerate(times):
        lo = bisect.bisect_left(times, t - timedelta(hours=half_h))
        hi = bisect.bisect_right(times, t + timedelta(hours=half_h))
        w = sorted(logs[lo:hi])
        out.append((t, w[len(w) // 2]))
    return out


def highpass(ser, half_h: float = HIGHPASS_H, min_points: int = 20):
    times = [t for t, _ in ser]
    out = []
    for t, v in ser:
        lo = bisect.bisect_left(times, t - timedelta(hours=half_h))
        hi = bisect.bisect_right(times, t + timedelta(hours=half_h))
        if hi - lo < min_points:
            continue
        out.append((t, v - sum(x for _, x in ser[lo:hi]) / (hi - lo)))
    return out


def nearest(by_time: dict, times: list[datetime], moment: datetime, tol_min: float = PAIR_MIN):
    k = bisect.bisect_left(times, moment)
    best = None
    for j in (k - 1, k):
        if 0 <= j < len(times):
            gap = abs((times[j] - moment).total_seconds()) / 60.0
            if gap <= tol_min and (best is None or gap < best[0]):
                best = (gap, times[j])
    return by_time[best[1]] if best else None


# ------------------------------------------------------------------ rises

@dataclass(frozen=True)
class Rise:
    start: datetime      # the lowest point it rose from
    mid: datetime        # where log energy crossed halfway, between stamps
    peak: datetime
    factor: float        # energy at the peak over the start


def _crossing(seg, level):
    for m in range(1, len(seg)):
        a, b = seg[m - 1], seg[m]
        if a[1] < level <= b[1]:
            frac = (level - a[1]) / (b[1] - a[1])
            return a[0] + (b[0] - a[0]) * frac
    return seg[0][0]


def rises(smoothed: list[tuple[datetime, float]], factor: float = RISE_FACTOR,
          within_h: float = RISE_WITHIN_H, floor_m2: float = RISE_FLOOR_M2) -> list[Rise]:
    """Every rise of `factor` in a smoothed log-energy series, oldest first.

    From each low, the highest point within `within_h` before the series falls
    below that low again; a rise that clears `factor` and `floor_m2` is kept,
    and the search resumes at its peak."""

    need, floor = math.log(factor), math.log(floor_m2)
    out: list[Rise] = []
    n, k = len(smoothed), 0
    while k < n:
        t0, v0 = smoothed[k]
        best, j = None, k + 1
        while j < n and (smoothed[j][0] - t0).total_seconds() <= within_h * 3600.0:
            if smoothed[j][1] < v0:
                break
            if best is None or smoothed[j][1] > smoothed[best][1]:
                best = j
            j += 1
        if best is not None and smoothed[best][1] - v0 >= need and smoothed[best][1] >= floor:
            mid = _crossing(smoothed[k:best + 1], (v0 + smoothed[best][1]) / 2.0)
            out.append(Rise(t0, mid, smoothed[best][0], math.exp(smoothed[best][1] - v0)))
            k = best
        elif j < n and smoothed[j][1] < v0:
            k = j
        else:
            k += 1
    return out


def rise_in(smoothed, lo: datetime, hi: datetime, factor: float = 2.0):
    """The midpoint of the biggest rise from the lowest point in [lo, hi], if
    it clears `factor`: how the onset method times a rise at 46232."""

    seg = [(t, v) for t, v in smoothed if lo <= t <= hi]
    if len(seg) < 6:
        return None
    i_lo = min(range(len(seg)), key=lambda i: seg[i][1])
    after = seg[i_lo:]
    i_hi = max(range(len(after)), key=lambda i: after[i][1])
    if after[i_hi][1] - seg[i_lo][1] < math.log(factor):
        return None
    return _crossing(after[:i_hi + 1], (seg[i_lo][1] + after[i_hi][1]) / 2.0)


# ------------------------------------------------------------------ report

def _pct(values, q):
    v = sorted(values)
    if not v:
        return float("nan")
    return v[min(len(v) - 1, int(q * len(v)))]


def _load(station):
    from .transform import load_spectra
    return load_spectra(SPECTRA / station)


def ridge_section(s47, s232) -> list[str]:
    import numpy as np

    from . import origin

    def long_ridges(spectra):
        return [r for r in origin.ridges(spectra) if len(r.points) >= 10]

    lags = []
    for ra in long_ridges(s47):
        fa = [p.freq_hz for p in ra.points]
        for rb in long_ridges(s232):
            fb = [p.freq_hz for p in rb.points]
            lo, hi = max(min(fa), min(fb)), min(max(fa), max(fb))
            if hi - lo < 0.004:
                continue
            pa = [p for p in ra.points if lo <= p.freq_hz <= hi]
            pb = [p for p in rb.points if lo <= p.freq_hz <= hi]
            if len(pa) < 6 or len(pb) < 6:
                continue
            ta, tb = pa[len(pa) // 2].time, pb[len(pb) // 2].time
            if abs((tb - ta).total_seconds()) > 36 * 3600:
                continue
            ref = pa[0].time
            rows = [(1.0, 0.0, (p.time - ref).total_seconds() / 3600.0, p.freq_hz) for p in pa]
            rows += [(0.0, 1.0, (p.time - ref).total_seconds() / 3600.0, p.freq_hz) for p in pb]
            x = np.array([r[:3] for r in rows])
            y = np.array([r[3] for r in rows])
            (a0, a1, slope), *_ = np.linalg.lstsq(x, y, rcond=None)
            if slope > 0:
                lags.append((a0 - a1) / slope)
    slope_hz_h = [9.81 / (4 * math.pi * r * 1000.0) * 3600.0 for r in (5000.0, 15000.0)]
    return [
        "## 1. Ridge to ridge: cannot resolve it",
        "",
        f"A ridge's frequency climbs g/(4πR): {slope_hz_h[0]:.1e} Hz/h from 5,000 km, "
        f"{slope_hz_h[1]:.1e} from 15,000. A 5 h lag therefore shifts a ridge by "
        f"{5 * slope_hz_h[1]:.4f}–{5 * slope_hz_h[0]:.4f} Hz, under a third of one 0.005 Hz bin, and "
        f"the refined peaks scatter ~0.001–0.002 Hz about their line.",
        "",
        f"Measured: {len(lags)} pairs of ridges (≥ 10 points each, overlapping ≥ 0.004 Hz, "
        f"within 36 h). Lag median {_pct(lags, .5):+.1f} h, interquartile "
        f"{_pct(lags, .25):+.1f} to {_pct(lags, .75):+.1f} h, against a prediction of 2–6 h. "
        "**Dropped**: the time a ridge reaches a frequency is too soft to time a few hours by.",
        "",
    ]


def onset_section(s47, s232) -> list[str]:
    lines = ["## 2. Onset to onset: not distinguishable from its window", "",
             "Each ×3 rise in a band at 46047's sector, timed at its midpoint in log "
             "energy; at 46232 the biggest rise from the lowest point in [start − 6 h, peak + 18 h]. "
             "Control: the same search with 46232's series moved ±3, ±5, ±7 days.", "",
             "| sector | rises | seen at 46232 | lag median [IQR] | within ±2 h of predicted | control seen | control lag median [IQR] | control within ±2 h |",
             "|---|---|---|---|---|---|---|---|"]
    rows = []
    for name in SECTORS:
        real, hits, n = [], 0, 0
        ctrl, chits, cn = [], 0, 0
        for band in BANDS_S:
            a = smooth_log(series(s47, band, SECTORS[name]), SMOOTH_ONSET_H)
            b = smooth_log(series(s232, band, ANCHOR_SECTORS[name]), SMOOTH_ONSET_H)
            pred = deep_water_lag_h(sum(band) / 2.0, sum(SECTORS[name]) / 2.0)
            for r in rises(a):
                n += 1
                m = rise_in(b, r.start - timedelta(hours=6), r.peak + timedelta(hours=18))
                if m:
                    lag = (m - r.mid).total_seconds() / 3600.0
                    real.append(lag)
                    hits += abs(lag - pred) <= 2.0
                for days in (-7, -5, -3, 3, 5, 7):
                    cn += 1
                    shift = timedelta(days=days)
                    m = rise_in(b, r.start - timedelta(hours=6) + shift, r.peak + timedelta(hours=18) + shift)
                    if m:
                        lag = (m - shift - r.mid).total_seconds() / 3600.0
                        ctrl.append(lag)
                        chits += abs(lag - pred) <= 2.0
        rows.append((name, hits, n, chits, cn))
        lines.append(
            f"| {name} | {n} | {len(real)} ({100 * len(real) / max(n, 1):.0f}%) | "
            f"{_pct(real, .5):+.1f} [{_pct(real, .25):+.1f}, {_pct(real, .75):+.1f}] | "
            f"{100 * hits / max(n, 1):.0f}% | {100 * len(ctrl) / max(cn, 1):.0f}% | "
            f"{_pct(ctrl, .5):+.1f} [{_pct(ctrl, .25):+.1f}, {_pct(ctrl, .75):+.1f}] | "
            f"{100 * chits / max(cn, 1):.0f}% |")
    timed = [r for r in rows if r[0] in TIMED]
    real_hit = sum(r[1] for r in timed) / max(sum(r[2] for r in timed), 1)
    ctrl_hit = sum(r[3] for r in timed) / max(sum(r[4] for r in timed), 1)
    lines += ["", "**Dropped for timing a single swell**: the shifted search finds a rise "
              f"nearly as often, at nearly the same lag. West and north-west together, "
              f"{100 * real_hit:.0f}% of rises land within 2 h of the prediction against "
              f"{100 * ctrl_hit:.0f}% shifted: the signal is there, too weakly to time one swell by.", ""]
    return lines


def _xcorr_arrays(a, b):
    """For each lag, (block, x, y): 46047's value at t − lag and 46232's at t."""

    import numpy as np

    b_map = dict(b)
    b_times = sorted(b_map)
    start = min(t for t, _ in a)
    out = {}
    for lag in LAGS_H:
        rows = []
        for t, y in a:
            x = nearest(b_map, b_times, t - timedelta(hours=lag))
            if x is not None:
                rows.append(((t - start).days // BLOCK_DAYS, x, y))
        out[lag] = np.array(rows) if rows else np.zeros((0, 3))
    return out


def _peak(arrays, weights=None):
    import numpy as np

    best = None
    for lag, arr in arrays.items():
        if len(arr) < 50:
            continue
        w = np.ones(len(arr)) if weights is None else weights[arr[:, 0].astype(int)]
        if w.sum() < 50:
            continue
        x, y = arr[:, 1], arr[:, 2]
        mx, my = np.average(x, weights=w), np.average(y, weights=w)
        cov = np.average((x - mx) * (y - my), weights=w)
        r = cov / math.sqrt(np.average((x - mx) ** 2, weights=w) * np.average((y - my) ** 2, weights=w))
        if best is None or r > best[1]:
            best = (lag, float(r))
    return best


@dataclass(frozen=True)
class SeriesLag:
    sector: str
    band_s: tuple[float, float]
    predicted_h: float
    lag_h: float
    r: float
    ci_h: tuple[float, float]
    minus_south_ci_h: tuple[float, float] | None


def series_lags(s47, s232, seed: int = 1) -> list[SeriesLag]:
    import numpy as np

    rng = np.random.default_rng(seed)
    out = []
    for band in BANDS_S:
        arrays = {}
        for name in SECTORS:
            a = highpass(smooth_log(series(s232, band, ANCHOR_SECTORS[name]), SMOOTH_SERIES_H))
            b = highpass(smooth_log(series(s47, band, SECTORS[name]), SMOOTH_SERIES_H))
            arrays[name] = _xcorr_arrays(a, b)
        n_blocks = int(max(arr[:, 0].max() for arrs in arrays.values() for arr in arrs.values() if len(arr))) + 1
        boots = {name: [] for name in SECTORS}
        diffs = {name: [] for name in TIMED}
        for _ in range(BOOTSTRAP):
            weights = np.bincount(rng.integers(0, n_blocks, n_blocks), minlength=n_blocks).astype(float)
            peaks = {name: _peak(arrays[name], weights) for name in SECTORS}
            for name in SECTORS:
                if peaks[name]:
                    boots[name].append(peaks[name][0])
            for name in TIMED:
                if peaks[name] and peaks["south"]:
                    diffs[name].append(peaks[name][0] - peaks["south"][0])
        for name in SECTORS:
            lag, r = _peak(arrays[name])
            out.append(SeriesLag(
                name, band, deep_water_lag_h(sum(band) / 2.0, sum(SECTORS[name]) / 2.0),
                lag, r, (_pct(boots[name], .05), _pct(boots[name], .95)),
                (_pct(diffs[name], .05), _pct(diffs[name], .95)) if name in TIMED else None))
    return out


def series_section(lags: list[SeriesLag]) -> list[str]:
    lines = ["## 3. The whole series: the lag is there on average", "",
             f"Log energy, a running median over ±{SMOOTH_SERIES_H:g} h, its ±{HIGHPASS_H:g} h mean removed; "
             f"46047's value at t − lag against 46232's at t, stamps paired within {PAIR_MIN:g} min "
             f"(never interpolated). 90% intervals from {BOOTSTRAP} resamples of {BLOCK_DAYS}-day blocks.", "",
             "| band | sector | predicted (deep water) | measured lag | 90% | r | lag − south's, 90% |",
             "|---|---|---|---|---|---|---|"]
    for s in lags:
        diff = f"{s.minus_south_ci_h[0]:+.1f} to {s.minus_south_ci_h[1]:+.1f}" if s.minus_south_ci_h else "control"
        lines.append(f"| {s.band_s[0]:g}–{s.band_s[1]:g} s | {s.sector} | {s.predicted_h:+.1f} h | "
                     f"{s.lag_h:+.1f} h | {s.ci_h[0]:+.1f} to {s.ci_h[1]:+.1f} | {s.r:.2f} | {diff} |")
    timed = [s for s in lags if s.sector in TIMED]
    inside = sum(1 for s in timed if s.ci_h[0] <= s.predicted_h <= s.ci_h[1])
    apart = sum(1 for s in timed if s.minus_south_ci_h and s.minus_south_ci_h[0] > 0)
    lines += ["", f"The deep-water prediction sits inside the measured 90% interval on {inside} of "
              f"{len(timed)} west and north-west bands, and the lag exceeds the south control's on "
              f"{apart} of {len(timed)} (interval above zero): the direction dependence the geometry "
              "predicts is in the archive. The fall with period it also predicts (1/T) is not resolved, "
              "and the south swell's lag runs shorter than predicted.", ""]
    return lines


def leg_section() -> list[str]:
    from .raytrace import BREAKS

    lines = ["## 4. 46232 to the breaks: computed along the rays", "",
             "`data/nearshore/<break>_leg.csv` (`python -m forecast.raytrace --leg-only`). Minutes, "
             "the range over unblocked rays within 5° of each offshore heading; blank where no ray "
             "from it reaches the break.", "",
             "| break | period | 200° | 230° | 260° | 290° |", "|---|---|---|---|---|---|"]
    for bid in BREAKS:
        rows = load_leg(bid)
        for period in (10.0, 12.0, 14.0, 16.0):
            cells = []
            for heading in (200.0, 230.0, 260.0, 290.0):
                lg = leg(bid, period, heading, rows)
                cells.append(f"{lg.lo_min:.0f}–{lg.hi_min:.0f}" if lg else "")
            lines.append(f"| {bid.replace('coronado_', '')} | {period:g} s | " + " | ".join(cells) + " |")
    lines += ["", "Straight-line plane-wave check: 46232 is 29 km from the center break; at 230° and "
              "12 s that is 52 min, against the rays' 50.", ""]
    return lines


def report() -> str:
    s47, s232 = _load(UPSTREAM), _load(ANCHOR)
    east, north = offset_km()
    lines = ["# Upstream lag: Tanner Banks to Point Loma South to the breaks", "",
             "Generated by `python -m forecast.upstreamlag --write`; the method is in the module's "
             "docstring. Reports, never edits.", "",
             f"Spectra: 46047 {s47[0].time:%Y-%m-%d} to {s47[-1].time:%Y-%m-%d} ({len(s47)}), "
             f"46232 {s232[0].time:%Y-%m-%d} to {s232[-1].time:%Y-%m-%d} ({len(s232)}; dark "
             "2026-09-01 to 09-17). 46232 sits "
             f"{math.hypot(east, north):.0f} km from 46047, {east:.0f} km east and {north:.0f} km north.", ""]
    lines += ridge_section(s47, s232)
    lines += onset_section(s47, s232)
    lines += series_section(series_lags(s47, s232))
    lines += leg_section()
    lines += ["## What the briefing may say", "",
              "- **A time, from physics, labelled as such**: when 46047's west or north-west sector "
              "has risen, the deep-water travel time to 46232 for its period and heading, then the rays' "
              "leg to each break. The archive agrees with it on average (§3); nothing here can time one "
              "swell (§1–2), so it is \"due\", never \"arrives at\", and never confirmed at 46232 by "
              "this method.",
              "- **Never a height**: nothing here measures how much of 46047's swell survives the "
              "Channel Islands to 46232; the breaks' heights come from 46232's own spectrum once it is there.",
              "- **Not past 17 s, not south**: unmeasured and wrong-signed respectively.",
              "", "## Not done", "",
              "- Two months, one season. Winter's north-west swell is the case this exists for; re-run "
              "then.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--write", action="store_true", help=f"write {DOC.relative_to(ROOT)}")
    args = parser.parse_args(argv)
    text = report()
    if args.write:
        DOC.write_text(text, encoding="utf-8")
        print(f"wrote {DOC}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
