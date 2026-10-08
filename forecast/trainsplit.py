"""How a spectrum is split into trains, measured (BRIEFING §40). Reports; never edits.

    python -m forecast.trainsplit --control [TRIALS]      synthetic spectra, known answer
    python -m forecast.trainsplit --archive 46232          the archive, three splitters

Three splitters, all over the same maximum-entropy D(f, theta):

  period only   the rule until 2026-10-08: period bands cut where the RAW energy dips
                below 0.6 of the smaller peak, one train per band, "A & B" when two
                directions each hold a fifth of it
  10° watershed the full 2-D split the owner first chose: period x 10-degree cells,
                [1,2,1] smoothing both ways, regions merged while the saddle between
                them is above 0.6 of the smaller peak
  shipped       `transform.split_trains` as it stands: bands on noise-smoothed energy at
                the derived PROMINENCE, then divided by direction (not maximum
                entropy's even twin)

The control builds spectra whose swells are known -- JONSWAP in period, wrapped normal in
direction -- turns each band into what a buoy reports (energy and four directional moments),
adds the sampling noise of BUOY_DOF degrees of freedom (chi-square in energy, Gaussian in the
moments), and reads it back by maximum entropy exactly as the chain does. A trial succeeds
when every true swell (period >= 8 s) is matched by its own train within 15% in period and
25 degrees in direction, and no other swell train appears. Seeds are fixed, so the table
reproduces.
"""

from __future__ import annotations

import argparse
import math
import random
import statistics
import sys
import zlib
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR

from . import transform as T

OLD_PROMINENCE = 0.6
WATERSHED_DEG = 10


# ---------------------------------------------------------------- spectra

def histograms(spectrum) -> dict[int, list[float]]:
    """Each band's energy over 1-degree headings FROM, as `at_buoy` integrates it."""

    s = spectrum if spectrum.spread == "mem" else spectrum.with_spread("mem")
    out = {}
    for i in range(len(s.frequencies)):
        c = s.c11[i]
        if c is None or math.isnan(c) or c <= 0:
            continue
        w = s.bin_width(i)
        out[i] = [max(0.0, s.density(i, d + 0.5)) * math.radians(1.0) * w for d in range(360)]
    return out


def _sums(hists):
    sn = {i: sum(v * math.sin(math.radians(k + 0.5)) for k, v in enumerate(h)) for i, h in hists.items()}
    cs = {i: sum(v * math.cos(math.radians(k + 0.5)) for k, v in enumerate(h)) for i, h in hists.items()}
    return sn, cs


def _mean(dist):
    sn = sum(v * math.sin(math.radians(k + 0.5)) for k, v in enumerate(dist))
    cs = sum(v * math.cos(math.radians(k + 0.5)) for k, v in enumerate(dist))
    return math.degrees(math.atan2(sn, cs)) % 360.0


# ---------------------------------------------------------------- the three splitters
# Each returns [(m0, period_s, from_deg, two_directions)].

def shipped(freqs, hists):
    per = [(i, sum(hists[i])) for i in sorted(hists)]
    sn, cs = _sums(hists)
    return [((t.hs_m / 4) ** 2, t.period_s, t.from_deg, bool(t.lobes))
            for t in T.split_trains(per, freqs, sn, cs, hists=hists, min_share=0, min_hs=0)]


def period_only(freqs, hists):
    old = T.PROMINENCE, T.BAND_SMOOTH
    T.PROMINENCE, T.BAND_SMOOTH = OLD_PROMINENCE, (1,)
    try:
        out = []
        for band in T.train_bands([(i, sum(hists[i])) for i in sorted(hists)]):
            dist = [0.0] * 360
            for i, _ in band:
                for k, v in enumerate(hists[i]):
                    dist[k] += v
            m0 = sum(e for _, e in band)
            top = max(band, key=lambda it: it[1])[0]
            out.append((m0, 1 / freqs[top], _mean(dist), len(T.split_lobes(dist)) >= 2))
        return out
    finally:
        T.PROMINENCE, T.BAND_SMOOTH = old


def watershed(freqs, hists, db=WATERSHED_DEG, prom=OLD_PROMINENCE):
    fi = sorted(hists)
    if not fi:
        return []
    nd, nf = 360 // db, len(fi)
    E = [[sum(hists[i][j * db:(j + 1) * db]) for j in range(nd)] for i in fi]
    S = [[0.0] * nd for _ in range(nf)]
    for a in range(nf):
        for b in range(nd):
            tot = wt = 0.0
            for da, wa in ((-1, 1), (0, 2), (1, 1)):
                if 0 <= a + da < nf:
                    for dbb, wb in ((-1, 1), (0, 2), (1, 1)):
                        tot += E[a + da][(b + dbb) % nd] * wa * wb
                        wt += wa * wb
            S[a][b] = tot / wt
    up = {}
    for a in range(nf):
        for b in range(nd):
            best, to = S[a][b], (a, b)
            for da in (-1, 0, 1):
                for dbb in (-1, 0, 1):
                    if (da or dbb) and 0 <= a + da < nf and S[a + da][(b + dbb) % nd] > best:
                        best, to = S[a + da][(b + dbb) % nd], (a + da, (b + dbb) % nd)
            up[(a, b)] = to
    label = {}
    for c in up:
        path = [c]
        while up[path[-1]] != path[-1] and path[-1] not in label:
            path.append(up[path[-1]])
        root = label.get(path[-1], path[-1])
        for q in path:
            label[q] = root
    peak = {r: S[r[0]][r[1]] for r in set(label.values())}
    sad = {}
    for a in range(nf):
        for b in range(nd):
            for da, dbb in ((1, 0), (0, 1), (1, 1), (1, -1)):
                if a + da >= nf:
                    continue
                ra, rb = label[(a, b)], label[(a + da, (b + dbb) % nd)]
                if ra != rb:
                    k = (ra, rb) if ra < rb else (rb, ra)
                    sad[k] = max(sad.get(k, -1.0), min(S[a][b], S[a + da][(b + dbb) % nd]))
    parent = {r: r for r in peak}

    def find(r):
        while parent[r] != r:
            parent[r] = parent[parent[r]]
            r = parent[r]
        return r

    while True:
        best = None
        for (x, y), v in sad.items():
            x, y = find(x), find(y)
            low = min(peak[x], peak[y])
            if x != y and low > 0 and v / low > prom and (best is None or v / low > best[0]):
                best = (v / low, x, y)
        if best is None:
            break
        _, x, y = best
        keep, drop = (x, y) if peak[x] >= peak[y] else (y, x)
        parent[drop] = keep
    groups = {}
    for (a, b), r in label.items():
        groups.setdefault(find(r), []).append((a, b))
    out = []
    for cells in groups.values():
        per_bin, dist = {}, [0.0] * 360
        for a, b in cells:
            seg = hists[fi[a]][b * db:(b + 1) * db]
            per_bin[fi[a]] = per_bin.get(fi[a], 0.0) + sum(seg)
            for k, v in enumerate(seg):
                dist[b * db + k] += v
        m0 = sum(per_bin.values())
        if m0 > 0:
            out.append((m0, 1 / freqs[max(per_bin, key=per_bin.get)], _mean(dist),
                        len(T.split_lobes(dist)) >= 2))
    return out


SPLITTERS = {"period only": period_only, f"{WATERSHED_DEG}° watershed": watershed, "shipped": shipped}


def shown(trains, total):
    return [t for t in trains if total > 0 and t[0] / total >= T.MIN_TRAIN_SHARE
            and 4 * math.sqrt(t[0]) >= T.MIN_TRAIN_HS_M]


# ---------------------------------------------------------------- the synthetic control

def _jonswap(f, tp, gamma=3.3):
    fp = 1 / tp
    s = 0.07 if f <= fp else 0.09
    return f ** -5 * math.exp(-1.25 * (fp / f) ** 4) * gamma ** math.exp(-((f - fp) ** 2) / (2 * s * s * fp * fp))


def synthetic(freqs, swells, dof, rng):
    """A buoy's report of `swells` [(hs_m, tp_s, from_deg, spread_deg)], with sampling noise."""

    widths = [T.Spectrum(None, freqs, [1] * len(freqs), *([[0] * len(freqs)] * 4)).bin_width(i)
              for i in range(len(freqs))]
    comps = []
    for hs, tp, frm, sg in swells:
        raw = [_jonswap(f, tp) for f in freqs]
        scale = (hs / 4) ** 2 / sum(r * w for r, w in zip(raw, widths))
        s = math.radians(sg)
        comps.append(([r * scale for r in raw], math.radians(frm), math.exp(-s * s / 2), math.exp(-2 * s * s)))
    c11, a1s, a2s, r1s, r2s = [], [], [], [], []
    for i in range(len(freqs)):
        e = sum(c[0][i] for c in comps)
        if e <= 0:
            c11.append(0.0); a1s.append(0.0); a2s.append(0.0); r1s.append(0.0); r2s.append(0.0)
            continue
        a1 = sum(c[0][i] * c[2] * math.cos(c[1]) for c in comps) / e
        b1 = sum(c[0][i] * c[2] * math.sin(c[1]) for c in comps) / e
        a2 = sum(c[0][i] * c[3] * math.cos(2 * c[1]) for c in comps) / e
        b2 = sum(c[0][i] * c[3] * math.sin(2 * c[1]) for c in comps) / e
        r1, r2 = math.hypot(a1, b1), math.hypot(a2, b2)
        n1 = math.sqrt(max(1e-6, 1 - r1 * r1) / dof)
        n2 = math.sqrt(max(1e-6, 1 - r2 * r2) / dof)
        a1, b1 = a1 + rng.gauss(0, n1), b1 + rng.gauss(0, n1)
        a2, b2 = a2 + rng.gauss(0, n2), b2 + rng.gauss(0, n2)
        c11.append(e * rng.gammavariate(dof / 2, 2) / dof)
        r1s.append(min(math.hypot(a1, b1), 0.98))
        r2s.append(min(math.hypot(a2, b2), 0.98))
        a1s.append(math.degrees(math.atan2(b1, a1)) % 360)
        a2s.append((math.degrees(math.atan2(b2, a2)) / 2) % 360)
    return T.Spectrum(None, freqs, c11, a1s, a2s, r1s, r2s, spread="mem")


CASES = {
    "one swell, 15° wide": [(1.0, 14, 200, 15)],
    "one swell, 20° wide": [(1.0, 14, 300, 20)],
    "one swell, 30° wide": [(1.0, 14, 300, 30)],
    "one broad swell, 35°": [(1.0, 14, 230, 35)],
    "swell + wind sea": [(1.0, 14, 200, 15), (0.5, 5, 290, 35)],
    "S 15 s + NW 12 s + sea": [(0.8, 15, 190, 12), (1.0, 12, 285, 15), (0.5, 6, 290, 35)],
    "NW 12 s swell + NW 6 s sea": [(1.0, 12, 295, 15), (0.8, 6, 305, 35)],
    "two at 14 s, 60° apart": [(1.0, 14, 200, 12), (0.7, 14, 260, 12)],
    "two at 14 s, 90° apart": [(1.0, 14, 200, 12), (0.7, 14, 290, 12)],
    "two at 14 s, 120° apart": [(1.0, 14, 200, 12), (0.7, 14, 320, 12)],
    "one direction, 16 & 13 s": [(1.0, 16, 270, 12), (0.7, 13, 270, 12)],
    "one direction, 16 & 11 s": [(1.0, 16, 270, 12), (0.7, 11, 270, 12)],
}


def trial(freqs, case, dof, seed, splitters=SPLITTERS):
    swells = CASES[case]
    truth = [(tp, frm) for _, tp, frm, _ in swells if tp >= T.WIND_SEA_PERIOD_S]
    hists = histograms(synthetic(freqs, swells, dof, random.Random(seed)))
    total = sum(sum(h) for h in hists.values())
    out = {}
    for name, fn in splitters.items():
        sw = [t for t in shown(fn(freqs, hists), total) if t[1] >= T.WIND_SEA_PERIOD_S]
        ok = len(sw) == len(truth)
        free = list(sw)
        for tp, frm in truth if ok else []:
            hit = [t for t in free if abs(t[1] - tp) <= 0.15 * tp and abs((t[2] - frm + 180) % 360 - 180) <= 25]
            if not hit:
                ok = False
                break
            free.remove(hit[0])
        out[name] = ok
    return out


def control(freqs, trials=100, dofs=(T.BUOY_DOF, 16)):
    rows = {}
    for dof in dofs:
        for case in CASES:
            seeds = [1000 * k + zlib.crc32(case.encode()) % 997 for k in range(trials)]
            res = [trial(freqs, case, dof, s) for s in seeds]
            rows[(dof, case)] = {n: sum(r[n] for r in res) / trials for n in SPLITTERS}
    return rows


# ---------------------------------------------------------------- the archive

def archive(station: str, data_dir: Path = DEFAULT_DATA_DIR):
    spectra = T.load_spectra(Path(data_dir) / "spectra" / station)
    stats = {n: dict(n=0, swell=0, two=0, counts=[], listed=[]) for n in SPLITTERS}
    for s in spectra:
        hists = histograms(s)
        total = sum(sum(h) for h in hists.values())
        if total <= 0:
            continue
        for name, fn in SPLITTERS.items():
            sh = shown(fn(s.frequencies, hists), total)
            st = stats[name]
            st["n"] += len(sh)
            st["swell"] += sum(t[1] >= T.WIND_SEA_PERIOD_S for t in sh)
            st["two"] += sum(t[3] for t in sh if t[1] >= T.WIND_SEA_PERIOD_S)
            st["counts"].append(len(sh))
            st["listed"].append(sum(t[0] for t in sh) / total)
    return len(spectra), stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--control", nargs="?", const=100, type=int, metavar="TRIALS")
    parser.add_argument("--archive", metavar="STATION")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = parser.parse_args(argv)
    names = list(SPLITTERS)
    if args.control:
        freqs = T.load_spectra(Path(args.data_dir) / "spectra" / "46232", limit=1)[0].frequencies
        rows = control(freqs, args.control)
        for dof in sorted({d for d, _ in rows}, reverse=True):
            print(f"\nSynthetic control, {dof} degrees of freedom, {args.control} trials: "
                  f"share finding exactly the swells that are there")
            print(f"{'case':30s}" + "".join(f"{n:>16s}" for n in names))
            for case in CASES:
                print(f"{case:30s}" + "".join(f"{rows[(dof, case)][n]:16.0%}" for n in names))
    if args.archive:
        n_spec, stats = archive(args.archive, args.data_dir)
        print(f"\n{args.archive}: {n_spec} spectra")
        print(f"{'':16s}{'trains':>8s}{'swell':>8s}{'two dirs':>10s}{'churn':>8s}{'> 4':>7s}{'listed':>9s}")
        for name, st in stats.items():
            c = st["counts"]
            print(f"{name:16s}{st['n'] / len(c):8.2f}{st['swell'] / len(c):8.2f}"
                  f"{st['two'] / max(st['swell'], 1):10.1%}"
                  f"{statistics.mean(abs(a - b) for a, b in zip(c, c[1:])):8.2f}"
                  f"{sum(x > 4 for x in c) / len(c):7.1%}{statistics.median(st['listed']):9.1%}")
    if not (args.control or args.archive):
        parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
