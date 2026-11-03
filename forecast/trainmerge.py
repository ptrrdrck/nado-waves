"""Is a break's train two of the buoy's trains? And does dividing it fix that?

    python -m forecast.trainmerge      # the archive and the known-answer control (~3 min, 4 cores)

The owner's question (2026-11-03, BRIEFING §49): North showed one train, "16.7
s from 228°", while 46232 held two -- a W 18.2 s and an SSW 14.3 s over the
same periods, which the buoy had divided by direction (§40). The aperture
trims both, what is left of the W sits beside the SSW, and the break's own
split (period bands, then lobes of the carried energy) found one band and
one lobe: a row whose period and heading were neither swell's, which the
Briefing then named as the SSW. 30% of North's energy at 5 m was the W.

Every ray's energy at 5 m is credited to the buoy train holding its (bin,
offshore heading) -- the buoy's own split with no floor
(`nearshore.buoy_split`). The chain is linear to 5 m, so that is exact. Three
rules for a break's rows, all through `nearshore.carry`:

- **whole** -- the break's own split, every row kept whole (shipped until
  2026-11-03; the Briefing named a row's buoy train by `trainmatch.buoy_train`)
- **divided at 20%** -- a row is divided into its buoy trains when a second
  one carries `nearshore.BUOY_DIVIDE_SHARE` of it (shipped)
- **divided at a third** -- the same at ⅓

Inheriting the buoy's split outright was measured too, and is not offered:
one swell through two of a break's windows (the Baja-islands gap and the main
window) became one row headed between them, North's fault reversed, and
where the buoy merged two swells it was the worst of the four.

THE ARCHIVE judges against the buoy's split, which favours dividing by it
by construction. THE CONTROL judges against the truth: two synthetic swells
with buoy noise (`trainsplit.synthetic`), each one's own energy carried to
every ray exactly, grouped by whether the buoy's split parted them.

Measured 2026-11-03 (1,811 spectra, 4 Aug - 3 Nov 2026; 30 trials a case):

    archive, a swell >= 20% of a break's energy leading no row:
        North 14.6% -> 0.4% of hours, Center 24.1% -> 0.3%, South 11.4% -> 0.8%
        (a third: 7.3%, 8.4%, 6.9%); mixed rows 4-12% -> 0.1%
    the Briefing missing a swell >= half the biggest: 123 -> 45 of 1,812 hours;
        lines that were two buoy trains: 344 of 2,699 -> 7
    control, swells >= 60° and >= 3 s apart that the buoy parted:
        a swell >= 20% leading no row 21.4% -> 3.7% (a third: 13.3%);
        1-2 s apart 52.2% -> 2.2% (25.6%)
    control, the buoy did not part them: no rule changes anything
    the cost: one swell as two rows a little more often (South 48% -> 52%
        of hours, mostly a swell through two windows, which was already
        so); swells 30° apart that the buoy parted: mixed rows 23.9% ->
        26.4%, a hidden swell 5.6% -> 4.5%; one broad 35° swell as two
        rows 5.6% -> 7.8%

A row is "mixed" when no buoy train (archive) or source (control) carries
`PURE` of it -- `trainmatch`'s bar.

Reports, never edits.
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR

from . import transform as T

BREAKS = ("coronado_north", "coronado_center", "coronado_south")
#: The rows a break tab shows.
SHOWN = 3
#: The Briefing's bar: half the biggest swell train anywhere (`briefing.MIX_SHARE`).
LISTED = 0.5
#: A row is one source's when that source carries this share of it (`trainmatch.PURE`).
PURE = 2 / 3
#: A swell this share of a break's energy is one a reader should see a row for.
VISIBLE = 0.2

RULES = {"whole": math.inf, "divided at 20%": None, "divided at a third": 1 / 3}


def _share(rule: str) -> float:
    from .nearshore import BUOY_DIVIDE_SHARE

    v = RULES[rule]
    return BUOY_DIVIDE_SHARE if v is None else v


def _rays(spectrum, table, grids, extra=()) -> list[tuple]:
    """(bin, offshore heading, energy at 5 m, [each extra grid's energy]) per
    diffracting ray, as `nearshore.carry` integrates them."""

    from .nearshore import at

    freqs = sorted(table.by_freq)
    out = []
    for i, f in enumerate(spectrum.frequencies):
        g = grids.get(i)
        if g is None:
            continue
        near = min(freqs, key=lambda t: abs(t - f))
        if abs(near - f) > 0.05 * f:
            continue
        w = spectrum.bin_width(i)
        for r in table.by_freq[near]:
            if r.diff_gain <= 0:
                continue
            k = w * r.width_rad * r.diff_gain * r.diff_friction
            e = at(g, r.diff_off_from) * k
            if e > 0:
                out.append((i, r.diff_off_from, e,
                            [at(x[i], r.diff_off_from) * k if i in x else 0.0 for x in extra]))
    return out


def _inarc(deg: int, arc: tuple) -> bool:
    if not arc:
        return True
    lo, hi = arc
    return (deg - lo) % 360 < ((hi - lo) % 360 or 360)


def _rows(spectrum, table, grids, split, rule: str):
    """A rule's rows at one break, biggest first, each with `whole` -- False
    for a row divided out of a bigger one, whose energy is one buoy train's."""

    from .nearshore import carry

    whole = {(t.bins, t.arc, round(t.hs_m, 9)) for t in carry(spectrum, table, grids).trains}
    rows = carry(spectrum, table, grids, split, divide_share=_share(rule)).trains
    return [(t, (t.bins, t.arc, round(t.hs_m, 9)) in whole) for t in rows]


def _contents(rays, owners, rows, n_src, source):
    """Each row's energy by source: `source(ray index)` -> list of n_src."""

    out = []
    for t, whole in rows:
        c = [0.0] * n_src
        bins = set(t.bins)
        for m, (i, d, _, _) in enumerate(rays):
            if i in bins and _inarc(int(d) % 360, t.arc) and (whole or owners[m] == t.buoy):
                for j, v in enumerate(source(m)):
                    c[j] += v
        out.append(c)
    return out


def _score(c: Counter, rows, contents, break_share, wind):
    """Count a break's rows against the sources' shares of its energy."""

    shown = list(zip(rows, contents))[:SHOWN]
    c["break-hours"] += 1
    c["rows"] += len(shown)
    leads = Counter()
    for _, cont in shown:
        tot = sum(cont)
        if tot <= 0:
            continue
        top = max(range(len(cont)), key=lambda j: cont[j])
        if cont[top] < PURE * tot:
            c["mixed rows"] += 1
        else:
            leads[top] += 1
    c["one swell in two rows"] += any(v >= 2 for v in leads.values())
    c["a swell >= 20% leads no row"] += any(
        s >= VISIBLE and not wind[j] and j not in leads for j, s in enumerate(break_share))
    return leads


def _archive_one(args):
    data_dir, index = args
    from .nearshore import buoy_split, density_grids, load_tables
    from .trainmatch import buoy_train

    global _CACHE
    if _CACHE is None:
        _CACHE = (load_tables(), T.load_spectra(Path(data_dir) / "spectra" / "46232"))
    tables, spectra = _CACHE
    sp = spectra[index].with_spread("mem")
    grids = density_grids(sp)
    split = buoy_split(sp, grids)
    floored = T.floor_trains(split)
    to_split = {m: n for n, t in enumerate(split) for m, f in enumerate(floored)
                if t.bins == f.bins and t.arc == f.arc}
    from .nearshore import _buoy_owner
    owner = _buoy_owner(split)
    wind = [t.is_wind_sea for t in split]
    out = {}
    for b in BREAKS:
        rays = _rays(sp, tables[b], grids)
        if not rays:
            continue
        owners = [owner(i, int(d) % 360) for i, d, _, _ in rays]
        tot = sum(e for _, _, e, _ in rays)
        per = [0.0] * len(split)
        for (_, _, e, _), o in zip(rays, owners):
            if o >= 0:
                per[o] += e
        source = lambda m: [rays[m][2] if owners[m] == j else 0.0 for j in range(len(split))]
        rules = {}
        for rule in RULES:
            rows = _rows(sp, tables[b], grids, split, rule)
            cont = _contents(rays, owners, rows, len(split), source)
            ids = []
            for t, whole in rows:
                if rule == "whole":
                    k = buoy_train(t, floored, sp.frequencies)
                    ids.append(to_split.get(k) if k is not None else None)
                else:
                    ids.append(t.buoy)
            rules[rule] = [(t.hs_m, t.is_wind_sea, k, c) for (t, _), k, c in zip(rows, ids, cont)]
        out[b] = {"share": [x / tot for x in per], "wind": wind, "rules": rules,
                  "heights": [4 * math.sqrt(x) for x in per]}
    return out


_CACHE = None


def archive(data_dir: Path = DEFAULT_DATA_DIR, workers: int = 4, limit: int | None = None):
    """{rule: Counter} over every archived 46232 spectrum, by break and for the Briefing."""

    n = len(T.load_spectra(Path(data_dir) / "spectra" / "46232"))
    idx = range(max(0, n - limit) if limit else 0, n)
    if workers > 1:
        with Pool(workers) as pool:
            hours = pool.map(_archive_one, [(str(data_dir), i) for i in idx], chunksize=20)
    else:
        hours = [_archive_one((str(data_dir), i)) for i in idx]
    S = defaultdict(Counter)
    for hour in hours:
        if not hour:
            continue
        for rule in RULES:
            pool_ = []
            for b, d in hour.items():
                rows = d["rules"][rule]
                _score(S[(rule, b)], rows, [r[3] for r in rows], d["share"], d["wind"])
                pool_ += [(hs, k, c) for hs, wind, k, c in rows[:SHOWN] if not wind]
            _brief(S[(rule, "briefing")], pool_, hour)
    return S


def _brief(c: Counter, pool_, hour):
    """The Briefing's lines: pooled rows >= LISTED of the biggest, one a buoy train."""

    pool_.sort(key=lambda x: -x[0])
    named, lines = set(), 0
    if pool_:
        big = pool_[0][0]
        for hs, k, cont in pool_:
            if hs < LISTED * big:
                break
            if k is not None and k in named:
                continue
            named.add(k)
            lines += 1
            c["lines mixed"] += max(cont) < PURE * (sum(cont) or 1)
    want = set()
    tops = [h for d in hour.values() for j, h in enumerate(d["heights"]) if not d["wind"][j]]
    if tops:
        big = max(tops)
        want = {j for d in hour.values() for j, h in enumerate(d["heights"])
                if not d["wind"][j] and h >= LISTED * big}
    c["hours"] += 1
    c["lines"] += lines
    c["hours missing a swell"] += bool(want - named)


# ------------------------------------------------------------------ the control

def _truth(freqs, swell) -> dict[int, list[float]]:
    """A synthetic swell's own E(f, θ) on the 1° grid, per Hz per radian."""

    from .trainsplit import _jonswap

    hs, tp, frm, sg = swell
    sp0 = T.Spectrum(None, freqs, [1] * len(freqs), *([[0] * len(freqs)] * 4))
    widths = [sp0.bin_width(i) for i in range(len(freqs))]
    raw = [_jonswap(f, tp) for f in freqs]
    scale = (hs / 4) ** 2 / sum(r * w for r, w in zip(raw, widths))
    g = [math.exp(-(((d + 0.5 - frm + 180) % 360 - 180) ** 2) / (2 * sg * sg)) for d in range(360)]
    gs = sum(g) * math.radians(1)
    return {i: [raw[i] * scale * x / gs for x in g] for i in range(len(freqs)) if raw[i] > 0}


def _parted(split, truth, sp) -> bool:
    """Did the buoy's split part the swells: each one holding PURE of a train
    of its own that carries at least half of it?"""

    rad = math.radians(1)
    totals = [sum(sum(g) * rad * sp.bin_width(i) for i, g in t.items()) for t in truth]
    got = set()
    for bt in split:
        cont = [sum(t[i][d] * rad * sp.bin_width(i) for i in bt.bins if i in t
                    for d in range(360) if _inarc(d, bt.arc)) for t in truth]
        j = max(range(len(truth)), key=lambda q: cont[q])
        if cont[j] >= PURE * (sum(cont) or 1) and cont[j] >= 0.5 * totals[j]:
            got.add(j)
    return len(got) == len(truth)


def _control_one(args):
    name, swells, seed = args
    from .nearshore import _buoy_owner, buoy_split, density_grids, load_tables
    from .trainsplit import synthetic

    global _CACHE
    if _CACHE is None:
        _CACHE = (load_tables(), T.load_spectra(DEFAULT_DATA_DIR / "spectra" / "46232", limit=1))
    tables, spectra = _CACHE
    freqs = spectra[-1].frequencies
    sp = synthetic(freqs, swells, T.BUOY_DOF, random.Random(seed))
    grids = density_grids(sp)
    split = buoy_split(sp, grids)
    truth = [_truth(freqs, s) for s in swells]
    group = name if len(swells) < 2 else name + (", the buoy parted them" if _parted(split, truth, sp)
                                                 else ", the buoy did not")
    out = []
    owner = _buoy_owner(split)
    for b in BREAKS:
        rays = _rays(sp, tables[b], grids, truth)
        if not rays:
            continue
        owners = [owner(i, int(d) % 360) for i, d, _, _ in rays]
        true_tot = [sum(r[3][j] for r in rays) for j in range(len(swells))]
        share = [x / (sum(true_tot) or 1) for x in true_tot]
        for rule in RULES:
            rows = _rows(sp, tables[b], grids, split, rule)
            out.append((group, rule, rows and [(t.hs_m,) for t, _ in rows],
                        _contents(rays, owners, rows, len(swells), lambda m: rays[m][3]), share))
    return out


#: Two swells each, (Hs m, Tp s, from °, spread °): trainmatch's cases, and
#: four like North's on 3 Nov -- an SSW groundswell under a long W swell.
CONTROL = [
    *[((1.0, t1, d1, 12), (0.8, t2, d2, 15))
      for t1, t2 in ((15, 9), (15, 12), (15, 14), (12, 10))
      for d1, d2 in ((200, 230), (200, 250), (200, 270), (210, 290), (240, 270), (260, 280))],
    ((1.0, 14, 200, 12), (1.0, 18, 272, 15)), ((1.0, 14, 200, 12), (0.8, 17, 275, 15)),
    ((0.8, 15, 195, 12), (1.0, 13, 270, 15)), ((1.0, 16, 205, 12), (0.6, 12, 265, 15)),
]


def _group(a, b) -> str:
    sep = abs(((a[2] - b[2]) + 180) % 360 - 180)
    per = "3 s or more" if abs(a[1] - b[1]) >= 3 else "1-2 s"
    ang = "60° or more" if sep >= 60 else "50°" if sep >= 50 else "30° or less"
    return f"{per} and {ang} apart"


def control(trials: int = 30, cases=CONTROL, workers: int = 4, singles: bool = True):
    """{(group, rule): Counter} against the known sources."""

    from .trainsplit import CASES

    jobs = []
    named = [(_group(a, b), [a, b]) for a, b in cases]
    if singles:
        named = [(f"single: {n}", s) for n, s in CASES.items() if len(s) == 1] + named
    for ci, (name, swells) in enumerate(named):
        for k in range(trials):
            jobs.append((name, swells, 1000 * k + 7 * ci))
    if workers > 1:
        with Pool(workers) as pool:
            got = pool.map(_control_one, jobs, chunksize=4)
    else:
        got = [_control_one(j) for j in jobs]
    S = defaultdict(Counter)
    for trial in got:
        for group, rule, rows, contents, share in trial:
            _score(S[(group, rule)], rows or [], contents, share, [False] * len(share))
    return S


def _table(S, groups, title):
    lines = [title, f"  {'':44s}" + "".join(f"{r:>20s}" for r in RULES)]
    for g in groups:
        c0 = S[(g, "whole")]
        if not c0["break-hours"]:
            continue
        lines.append(f"  {g}  ({c0['break-hours']})")
        for key in ("mixed rows", "one swell in two rows", "a swell >= 20% leads no row"):
            vals = []
            for r in RULES:
                c = S[(g, r)]
                den = c["rows"] if key == "mixed rows" else c["break-hours"]
                vals.append(f"{100 * c[key] / max(den, 1):5.1f}%")
            lines.append(f"    {key:42s}" + "".join(f"{v:>20s}" for v in vals))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--trials", type=int, default=30)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)
    S = archive(args.data_dir, args.workers)
    print(_table({(b, r): S[(r, b)] for r in RULES for b in BREAKS}, BREAKS,
                 "THE ARCHIVE, against the buoy's own split (break-hours; rows for 'mixed'):"))
    print("\n  the Briefing (pooled, >= half the biggest, one line a buoy train):")
    for key in ("lines", "lines mixed", "hours missing a swell"):
        print(f"    {key:42s}" + "".join(f"{S[(r, 'briefing')][key]:>20d}" for r in RULES))
    print(f"    {'hours':42s}{S[('whole', 'briefing')]['hours']:>20d}")
    C = control(args.trials, workers=args.workers)
    print()
    print(_table(C, sorted({g for g, _ in C}), "THE CONTROL, against the known sources (break-trials):"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
