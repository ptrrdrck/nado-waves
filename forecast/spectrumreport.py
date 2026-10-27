"""How much of a drawn spectrum is the buoy's own sampling noise; reports, never edits.

    python -m forecast.spectrumreport                  both halves (~3 min on four cores)
    python -m forecast.spectrumreport --archive        46232's archive only
    python -m forecast.spectrumreport --control [N]    the known answer only, N trials a case

Asked before a curve of energy against period is drawn anywhere (owner's request,
2026-10-27): each of the buoy's frequency bins carries about `transform.BUOY_DOF`
degrees of freedom, so one bin's energy is uncertain by ~±25%, and a curve drawn raw
would show that as swell. Two curves are measured, each as the page would draw it:

  buoy    46232's own energy density, c11, m²/Hz -- measured
  north / center / south
          the density at the transfer tables' start, 5 m of water off each break
          (`nearshore.carry`'s bins over each bin's width) -- physically derived

and four ways of drawing each:

  raw        the bins as they are
  [1,2,1]    each bin with its two neighbours, weights 1, 2, 1, renormalised at the
             ends: the smoothing the train splitter reads energy through
  3 h mean   the mean of the last three hourly spectra, only where all three exist
             (a missing hour is a gap, never filled)
  both       the 3 h mean of the [1,2,1] curves

THE ARCHIVE says how much a drawn curve moves from one hour to the next: noise AND the
sea changing. Per pair of spectra exactly an hour apart, in every bin a reader could see
on a linear axis (both curves' mean there at least `VISIBLE` of its highest), the change
|a - b| / ((a + b) / 2). By period: wind sea (< 8 s), 8-14 s, and 14 s and longer. Beside
it, how often the curve's peak moves two bins or more, and the bumps it draws (local
maxima of at least `BUMP` of its highest).

THE CONTROL says how much of that is noise, from a known answer: `trainsplit.synthetic`
builds a buoy's report of known swells with 32-dof noise and reads it back by maximum
entropy, as the chain does; `components_report` makes the same report with moments that
are always realisable, and the control is run under both (its docstring says why). The truth is the sea itself (`KnownSea`: JONSWAP times a
wrapped normal, carried through the same tables), never a noiseless buoy report, which
is maximum entropy's own reading of the sea and differs from it at 5 m by up to ~15%.
Per trial six independent reports of the same sea are drawn: against the truth (how far
the drawn shape wanders), two against each other (the hour-to-hour jitter a sea that did
not change would still show; for the 3 h mean, reports 1-3 against 2-4, sharing two, as
consecutive trailing means do), and all six averaged (the floor: what no smoothing
removes -- at the buoy the six reports' own leftover noise, at 5 m mostly the chain
reading a noisy narrow swell differently from the sea itself).
A stationary sea is the best case for the 3 h mean: in the water it also blurs a sea
that is changing. Seeds are fixed, so the tables reproduce.
"""

from __future__ import annotations

import argparse
import math
import os
import random
import statistics
import sys
import zlib
from concurrent.futures import ProcessPoolExecutor
from datetime import timedelta
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR

from . import nearshore as N
from . import trainsplit as TS
from . import transform as T

CURVES = ("buoy",) + N.BREAKS
TREATMENTS = ("raw", "[1,2,1]", "3 h mean", "both")
#: A bin is in the comparison where the curve there is at least this share of the
#: curve's highest: what a reader could see on a linear axis.
VISIBLE = 0.05
#: A local maximum of at least this share of the curve's highest is a bump a reader
#: would read as a swell.
BUMP = 0.10
GROUPS = (("< 8 s", 0.0, 8.0), ("8-14 s", 8.0, 14.0), ("14 s +", 14.0, math.inf))
#: The control's seas: trainsplit's known swells, the ones that reach the breaks.
CONTROL_CASES = ("one swell, 15° wide", "one broad swell, 35°", "swell + wind sea",
                 "S 15 s + NW 12 s + sea", "one direction, 16 & 13 s")
CONTROL_CURVES = ("buoy", "coronado_center")


# ---------------------------------------------------------------- the curves

def curves(spectrum, tables) -> dict[str, list[float]]:
    """Density per bin, m²/Hz: the buoy's own, and in 5 m of water off each break."""

    s = spectrum if spectrum.spread == "mem" else spectrum.with_spread("mem")
    n = len(s.frequencies)
    out = {"buoy": [c if c is not None and not math.isnan(c) and c > 0 else 0.0 for c in s.c11]}
    grids = N.density_grids(s)
    for break_id, table in tables.items():
        row = [0.0] * n
        for i, e in N.carry(s, table, grids).bins:
            row[i] = e / s.bin_width(i)
        out[break_id] = row
    return out


def smooth(curve: list[float]) -> list[float]:
    """[1, 2, 1] across neighbouring bins, renormalised where a neighbour is missing."""

    n = len(curve)
    out = []
    for k in range(n):
        tot = wt = 0.0
        for d, w in zip((-1, 0, 1), T.BAND_SMOOTH):
            if 0 <= k + d < n:
                tot += curve[k + d] * w
                wt += w
        out.append(tot / wt)
    return out


def mean(rows: list[list[float]]) -> list[float]:
    return [sum(col) / len(col) for col in zip(*rows)]


def treated(by_time: dict, name: str) -> dict[str, dict]:
    """Each treatment of one curve, by stamp; the 3 h means only where all three are."""

    raw = {t: c[name] for t, c in by_time.items()}
    smoothed = {t: smooth(c) for t, c in raw.items()}
    hour = timedelta(hours=1)

    def trailing(src):
        out = {}
        for t in src:
            got = [src.get(t - k * hour) for k in range(3)]
            if all(g is not None for g in got):
                out[t] = mean(got)
        return out

    return {"raw": raw, "[1,2,1]": smoothed, "3 h mean": trailing(raw), "both": trailing(smoothed)}


# ---------------------------------------------------------------- measures

def changes(a: list[float], b: list[float], periods: list[float]) -> dict[str, list[float]]:
    """|a - b| over their mean, per period group, in the bins a reader could see."""

    m = [(x + y) / 2 for x, y in zip(a, b)]
    top = max(m) if m else 0.0
    out = {g: [] for g, _, _ in GROUPS}
    if top <= 0:
        return out
    for x, y, mm, p in zip(a, b, m, periods):
        if mm >= VISIBLE * top:
            for g, lo, hi in GROUPS:
                if lo <= p < hi:
                    out[g].append(abs(x - y) / mm)
    return out


def errors(drawn: list[float], truth: list[float], periods: list[float]) -> dict[str, list[float]]:
    """|drawn - truth| over the truth, per period group, where the truth is visible."""

    top = max(truth)
    out = {g: [] for g, _, _ in GROUPS}
    for x, t, p in zip(drawn, truth, periods):
        if t >= VISIBLE * top:
            for g, lo, hi in GROUPS:
                if lo <= p < hi:
                    out[g].append(abs(x - t) / t)
    return out


def bumps(curve: list[float]) -> int:
    top = max(curve) if curve else 0.0
    if top <= 0:
        return 0
    n = len(curve)
    return sum(1 for k in range(n)
               if curve[k] >= BUMP * top
               and (k == 0 or curve[k] > curve[k - 1])
               and (k == n - 1 or curve[k] >= curve[k + 1]))


def peak(curve: list[float]) -> int:
    return max(range(len(curve)), key=lambda k: curve[k])


def _q(values, q):
    if not values:
        return math.nan
    v = sorted(values)
    return v[min(len(v) - 1, int(q * len(v)))]


# ---------------------------------------------------------------- the archive

_TABLES: dict = {}


def _tables(only=None) -> dict:
    """The transfer tables, read once a process."""

    if not _TABLES:
        _TABLES.update(N.load_tables())
    return {b: t for b, t in _TABLES.items() if only is None or b in only}


def _curves_of(spectrum):
    return spectrum.time, curves(spectrum, _tables())


def archive(station: str = "46232", data_dir: Path = DEFAULT_DATA_DIR, workers: int | None = None):
    spectra = T.load_spectra(Path(data_dir) / "spectra" / station)
    periods = [1 / f for f in spectra[0].frequencies]
    with ProcessPoolExecutor(workers or os.cpu_count()) as pool:
        by_time = dict(pool.map(_curves_of, spectra, chunksize=16))
    hour = timedelta(hours=1)
    rows = {}
    for name in CURVES:
        for treatment, series in treated(by_time, name).items():
            got = {g: [] for g, _, _ in GROUPS}
            hops = pairs = 0
            for t, a in series.items():
                b = series.get(t + hour)
                if b is None or max(a) <= 0 or max(b) <= 0:
                    continue
                pairs += 1
                for g, v in changes(a, b, periods).items():
                    got[g].extend(v)
                hops += abs(peak(a) - peak(b)) >= 2
            rows[(name, treatment)] = dict(
                pairs=pairs, change=got, hop=hops / max(pairs, 1),
                bumps=statistics.mean(bumps(c) for c in series.values()))
    span = (spectra[0].time, spectra[-1].time)
    return len(spectra), span, rows, by_time


# ---------------------------------------------------------------- the control

class KnownSea:
    """The control's answer: the sea itself, JONSWAP in period times a wrapped
    normal in direction, with no buoy between it and the tables. Duck-types the
    parts of `transform.Spectrum` that `nearshore.carry` reads. Its c11 is the
    buoy curve's truth; carried through a table, the 5 m curve's."""

    spread = "mem"

    def __init__(self, freqs, swells):
        self.frequencies = list(freqs)
        self._shape = T.Spectrum(None, self.frequencies, [1] * len(freqs), *([[0] * len(freqs)] * 4))
        widths = [self.bin_width(i) for i in range(len(freqs))]
        self.parts = []
        for hs, tp, frm, sg in swells:
            raw = [TS._jonswap(f, tp) for f in freqs]
            scale = (hs / 4) ** 2 / sum(r * w for r, w in zip(raw, widths))
            self.parts.append(([r * scale for r in raw], frm, math.radians(sg)))
        self.c11 = [sum(p[0][i] for p in self.parts) for i in range(len(freqs))]

    def bin_width(self, index: int) -> float:
        return self._shape.bin_width(index)

    def density(self, index: int, theta: float) -> float:
        """m²/Hz/radian."""

        out = 0.0
        for e, frm, sg in self.parts:
            x = math.radians((theta - frm + 180.0) % 360.0 - 180.0)
            out += e[index] * sum(math.exp(-(x + 2 * math.pi * k) ** 2 / (2 * sg * sg))
                                  for k in (-1, 0, 1)) / (sg * math.sqrt(2 * math.pi))
        return out


def components_report(freqs, swells, dof, rng):
    """A buoy's report of `swells` whose moments are always realisable: each bin
    is dof / 2 wave components, each from one swell (chosen by its energy in
    that bin) at a heading drawn from its wrapped normal, with an exponential
    energy, so c11 carries the same chi-square noise as `trainsplit.synthetic`
    and the four moments are those of a real distribution. Gaussian noise on
    the moments instead (`trainsplit.synthetic`) makes 46-63% of a swell's
    energy unreadable by maximum entropy at 32 dof, which then falls back to
    the Fourier shape; in 46232's archive 15% of spectra hold any such energy.
    Neither model is a measurement of the buoy."""

    sea = KnownSea(freqs, swells)
    n = max(1, round(dof / 2))
    c11, a1s, a2s, r1s, r2s = [], [], [], [], []
    for i in range(len(freqs)):
        e = [part[0][i] for part in sea.parts]
        total = sum(e)
        if total <= 0:
            for col in (c11, a1s, a2s, r1s, r2s):
                col.append(0.0)
            continue
        w_sum = a1 = b1 = a2 = b2 = 0.0
        for _ in range(n):
            _, frm, sg = sea.parts[rng.choices(range(len(e)), weights=e)[0]]
            th = math.radians(frm) + rng.gauss(0.0, sg)
            w = rng.expovariate(1.0)
            w_sum += w
            a1 += w * math.cos(th); b1 += w * math.sin(th)
            a2 += w * math.cos(2 * th); b2 += w * math.sin(2 * th)
        a1, b1, a2, b2 = (v / w_sum for v in (a1, b1, a2, b2))
        c11.append(total * w_sum / n)
        r1s.append(math.hypot(a1, b1)); r2s.append(math.hypot(a2, b2))
        a1s.append(math.degrees(math.atan2(b1, a1)) % 360)
        a2s.append((math.degrees(math.atan2(b2, a2)) / 2) % 360)
    return T.Spectrum(None, list(freqs), c11, a1s, a2s, r1s, r2s, spread="mem")


#: How the control's buoy reports are made noisy (see `components_report`).
NOISE = {"gaussian moments": TS.synthetic, "dof/2 components": components_report}


def fallback_share(spectrum) -> float:
    """Share of a spectrum's energy in bins maximum entropy cannot read."""

    s = spectrum if spectrum.spread == "mem" else spectrum.with_spread("mem")
    live = [i for i, c in enumerate(s.c11) if c is not None and not math.isnan(c) and c > 0]
    total = sum(s.c11[i] * s.bin_width(i) for i in live)
    return sum(s.c11[i] * s.bin_width(i) for i in live if not s.mem_ok(i)) / total if total > 0 else 0.0


def _trial(args):
    """One sea, drawn from six independent buoy reports of it. Error: the first
    report (and the mean of the first three) against the sea. Jitter: the
    first against the second, and for the 3 h mean, reports 1-3 against 2-4,
    which share two of three, as consecutive trailing means do. Floor: the
    mean of all six against the sea, the part no smoothing removes."""

    case, seed, freqs, noise = args
    tables = _tables(CONTROL_CURVES)
    swells = TS.CASES[case]
    truth = curves(KnownSea(freqs, swells), tables)
    reports = [NOISE[noise](freqs, swells, T.BUOY_DOF, random.Random(seed * 7 + k + 1)) for k in range(6)]
    draws = [curves(r, tables) for r in reports]
    unread = statistics.mean(fallback_share(r) for r in reports)
    periods = [1 / f for f in freqs]
    out = {}
    for name in CONTROL_CURVES:
        raw = [d[name] for d in draws]
        sm = [smooth(c) for c in raw]
        one = {"raw": raw[0], "[1,2,1]": sm[0], "3 h mean": mean(raw[:3]), "both": mean(sm[:3])}
        other = {"raw": raw[1], "[1,2,1]": sm[1], "3 h mean": mean(raw[1:4]), "both": mean(sm[1:4])}
        true = truth[name]
        if max(true) <= 0:
            continue
        floor = errors(mean(raw), true, periods)
        for treatment in TREATMENTS:
            out[(name, treatment)] = dict(
                error=errors(one[treatment], true, periods),
                jitter=changes(one[treatment], other[treatment], periods),
                floor=[v for g in floor.values() for v in g],
                unread=unread,
                same_bumps=bumps(one[treatment]) == bumps(true),
                extra=bumps(one[treatment]) - bumps(true),
                peak=abs(peak(one[treatment]) - peak(true)) <= 1)
    return (noise, case), out


def control(freqs, trials: int = 60, workers: int | None = None):
    jobs = [(case, 1000 * k + zlib.crc32(case.encode()) % 997, freqs, noise)
            for noise in NOISE for case in CONTROL_CASES for k in range(trials)]
    with ProcessPoolExecutor(workers or os.cpu_count()) as pool:
        results = list(pool.map(_trial, jobs, chunksize=4))
    rows = {}
    for (noise, case), out in results:
        for key, r in out.items():
            row = rows.setdefault((noise, case) + key, dict(error={g: [] for g, _, _ in GROUPS},
                                                       jitter={g: [] for g, _, _ in GROUPS},
                                                       floor=[], unread=[], same=[], extra=[], peak=[]))
            for g in r["error"]:
                row["error"][g].extend(r["error"][g])
                row["jitter"][g].extend(r["jitter"][g])
            row["floor"].extend(r["floor"])
            row["unread"].append(r["unread"])
            row["same"].append(r["same_bumps"])
            row["extra"].append(r["extra"])
            row["peak"].append(r["peak"])
    return rows


# ---------------------------------------------------------------- printing

def _pct(values) -> str:
    if not values:
        return f"{'--':>13s}"
    return f"{_q(values, 0.5):6.0%} {_q(values, 0.9):5.0%} "


def payload(by_time) -> str:
    """What a time-by-period chart of 46232 would weigh, a column a spectrum."""

    n_bins = len(next(iter(by_time.values()))["buoy"])
    week, every = 7 * 24, len(by_time)
    lines = [f"\nPayload of a time-by-period chart, 46232, {n_bins} bins a column:"]
    for label, cols in (("the week", week), (f"the archive ({every} spectra)", every)):
        # Three significant figures as JSON numbers average ~6 bytes with the comma;
        # one character per bin is one of up to ~90 greys.
        lines.append(f"  {label:28s} numbers ~{cols * n_bins * 6 / 1024:6.0f} KB"
                     f"    one character a bin ~{cols * (n_bins + 3) / 1024:5.0f} KB  (before gzip)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--archive", action="store_true")
    parser.add_argument("--control", nargs="?", const=60, type=int, metavar="TRIALS")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = parser.parse_args(argv)
    both = not args.archive and args.control is None
    groups = [g for g, _, _ in GROUPS]
    head = "".join(f"{g:>13s}" for g in groups)
    if args.archive or both:
        n, (first, last), rows, by_time = archive("46232", args.data_dir)
        print(f"46232 archive: {n} spectra, {first:%Y-%m-%d} to {last:%Y-%m-%d}")
        unread = [fallback_share(sp) for sp in T.load_spectra(Path(args.data_dir) / "spectra" / "46232")]
        held = [u for u in unread if u > 0]
        print(f"Energy maximum entropy cannot read: in {len(held) / len(unread):.0%} of spectra, "
              f"median {statistics.median(held) if held else 0:.1%} of those spectra's energy")
        print(f"\nHour-to-hour change of the drawn curve, |a - b| / mean, in bins >= {VISIBLE:.0%} "
              f"of the curve's highest: median, 90th percentile.")
        print(f"Peak moves = share of hours its peak moves >= 2 bins; bumps = mean local "
              f"maxima >= {BUMP:.0%} of the highest.")
        print(f"{'curve':17s}{'drawn':10s}{'pairs':>6s}{head}{'peak moves':>12s}{'bumps':>7s}")
        for name in CURVES:
            for treatment in TREATMENTS:
                r = rows[(name, treatment)]
                print(f"{name:17s}{treatment:10s}{r['pairs']:6d}"
                      + "".join(_pct(r["change"][g]) for g in groups)
                      + f"{r['hop']:12.0%}{r['bumps']:7.2f}")
        print(payload(by_time))
    if args.control or both:
        trials = args.control or 60
        freqs = T.load_spectra(Path(args.data_dir) / "spectra" / "46232", limit=1)[0].frequencies
        rows = control(freqs, trials)
        print(f"\nKnown-answer control, {T.BUOY_DOF} dof, {trials} trials a case "
              f"(trainsplit.synthetic, read by maximum entropy):")
        print("error = |drawn - truth| / truth; jitter = the same sea drawn twice, |a - b| / mean;")
        print("floor = the mean of six reports against the truth, median, all periods (what no "
              "smoothing removes);")
        print("bumps right = share drawing exactly the truth's bumps; extra = mean bumps too many; "
              "peak = within a bin of the truth's")
        for noise in NOISE:
            for name in CONTROL_CURVES:
                unread = statistics.mean(v for k, r in rows.items() if k[0] == noise for v in r["unread"])
                print(f"\n{name}, noise as {noise} (energy maximum entropy cannot read: {unread:.0%})")
                print(f"{'case':28s}{'drawn':10s}" + "".join(f"{'err ' + g:>13s}" for g in groups)
                      + "".join(f"{'jit ' + g:>13s}" for g in groups)
                      + f"{'floor':>7s}{'bumps right':>12s}{'extra':>7s}{'peak':>6s}")
                for case in CONTROL_CASES:
                    for treatment in TREATMENTS:
                        r = rows.get((noise, case, name, treatment))
                        if r is None:
                            continue
                        print(f"{case:28s}{treatment:10s}"
                              + "".join(_pct(r["error"][g]) for g in groups)
                              + "".join(_pct(r["jitter"][g]) for g in groups)
                              + f"{_q(r['floor'], 0.5):7.0%}"
                              + f"{statistics.mean(r['same']):12.0%}{statistics.mean(r['extra']):7.2f}"
                              + f"{statistics.mean(r['peak']):6.0%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
