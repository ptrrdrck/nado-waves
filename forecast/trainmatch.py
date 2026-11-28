"""Which of the buoy's trains a break's train is, and the Briefing's one line a swell.

    python -m forecast.trainmatch           # the archive and the known-answer control (~30 s)
    python -m forecast.trainmatch --lines   # one line a SWELL, the rules scored (~9 min, 4 cores)

**Since 2026-11-28 the headline is ONE LINE A SWELL** (owner's call, docs/
handoff.md item 30; `briefing.same_swell`, `fcSwellTrains`): a row is left
unsaid only when a said line peaks within x1.25 of its period and is the same
buoy train or within 45° of its heading. `--lines` (below) is what measured
it; this docstring's first half is how one line a buoy train was measured.
Measured 2026-11-28 (2,395 archived spectra; 1,140 control trials, 30 a
case; every Forecast build hour logged since 4 Nov), each rule scored a
headline at a time -- a swell unsaid, said twice, or neither ("right"):

    control, all            right   unsaid  twice   one swell, one line
      a buoy train          61.9%   37.5%   1.1%    99.2%
      x1.25, 45° (shipped)  75.0%   24.0%   1.4%    98.3%
      x1.12, 45°            79.0%   13.3%   8.0%    92.5%
      by its peak bin       62.3%   37.2%   0.7%    99.2%
    two swells 3 s+ apart, under 30°: right 72.1% -> 97.9%; 60°+ 66.7 -> 81.0%;
        1-2 s apart, 60°+: 25.3 -> 34.7% (what the buoy merged stays merged)
    archive (the buoy's split as the yardstick, which favours a buoy train):
        a buoy train in two lines 1.0% -> 25.8% of hours, lines 1.65 -> 1.91 an
        hour; mostly one buoy train at two breaks peaking 25-50% apart in
        period -- one swell or two, nothing here says which
    Forecast log: the headline changes on 262 of 1,888 build hours, lines
        1.63 -> 1.76; 28 Nov 03Z: "W at 19.0 s" (twice, then merged) ->
        "W at 19.0 s", "W at 12.7 s"

Keying each row by the buoy train holding its PEAK BIN instead of the one
carrying most of it fixes 28 Nov 03Z's pattern and almost nothing else: the
control's unsaid swells are swells the buoy merged into one train.

Owner's request and calls, 2026-10-24: the headline listed W at 9.1 s (South)
and WSW at 9.9 s (Center), one W swell at 46232 read through two breaks'
windows, either side of the W / WSW boundary. "One a compass point" could not
see that. Each break's train is now matched to the BUOY's train it belongs to
(`buoy_train`): the one holding its peak period, and when the buoy divided
that band by direction (BRIEFING §40), the one whose headings hold its own,
else the nearest. Trains of one buoy train are one line (`briefing.listed_trains`).

**Since 2026-11-03 (BRIEFING §49) the chains name it by energy instead**:
`nearshore.carry`, handed the buoy's own split, credits every row to the buoy
trains that carried it, divides a row two of them carried, and sets
`Train.buoy` to the one that carried most of it (`forecast.trainmerge`
measured why: a break's own split had made one row of two buoy trains on
4-12% of rows). `buoy_train` below is the fallback for a row with no such
credit, and this report measures the rule as it was built.

**Measured before it was built, and this is the report that measured it.**
Every archived 46232 spectrum, by maximum entropy as the page reads it,
through the three breaks; each pair of trains at two breaks joined or kept
apart by each rule:

- **Periods alone** (each one's peak inside the other's band, the first
  proposal) joined two different buoy trains on 24% of its joins, nearly all a
  band the buoy divided by direction -- a SSW groundswell and a W swell over
  the same periods. Rejected.
- **The buoy's trains** agree with the buoy's split by construction, so the
  archive cannot fault them; the compass point there joined two buoy trains
  on 20% of its joins and caught 28% of the duplicates. The **known-answer
  control** can: two synthetic swells with buoy noise (`trainsplit.synthetic`),
  carried to the breaks, each train credited to the swell carrying `PURE` of
  its energy in its band and held headings -- a train no swell carries that
  much of IS both swells, and pairs with one are counted, not scored. Swells
  3 s or more apart: wrong on 18 of 297 joins (6.1%), 17 of them 15 s from
  200° with 12 s from 250-270°, which the buoy itself reads as one train
  (maximum entropy keeps an even pair under 60° as one, §40), so each break
  holds one train, mostly one swell or the other; 97% of duplicates caught,
  where the compass point was wrong on 34% and caught 46%. 1-2 s apart:
  wrong on 25%, the compass point 28%. Measured 2026-10-24, 15 trials a case.

Reports, never edits.
"""

from __future__ import annotations

import argparse
import itertools
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR

from . import transform as T


def _inarc(deg: float, arc) -> bool:
    if not arc or (arc[1] - arc[0]) % 360 == 0:
        return True
    return (deg - arc[0]) % 360 < (arc[1] - arc[0]) % 360


def _adiff(a: float, b: float) -> float:
    return abs((a - b + 180) % 360 - 180)


def peak_bin(train, frequencies) -> int | None:
    """The bin of a train's band its peak period reads."""

    if not train.bins or not train.period_s or math.isnan(train.period_s):
        return None
    f = 1 / train.period_s
    return min(train.bins, key=lambda i: abs(frequencies[i] - f))


def buoy_train(train, buoy_trains, frequencies) -> int | None:
    """The index, in the buoy's own split, of the train a break's train
    belongs to: the one holding its peak period; of a band the buoy divided
    by direction, the one whose headings hold its heading, else the nearest.
    None when no buoy train holds its peak."""

    pk = peak_bin(train, frequencies)
    if pk is None:
        return None
    hold = [k for k, b in enumerate(buoy_trains) if pk in (b.bins or ())]
    if len(hold) > 1 and not math.isnan(train.from_deg):
        held = [k for k in hold if _inarc(train.from_deg, buoy_trains[k].arc)]
        hold = [min(held or hold, key=lambda k: _adiff(buoy_trains[k].from_deg, train.from_deg))]
    return hold[0] if hold else None


# ------------------------------------------------------------------ the report

BREAKS = ("coronado_north", "coronado_center", "coronado_south")
#: The headline's bar: half the biggest train (`briefing.MIX_SHARE`).
LISTED = 0.5


def _rows(spectrum, tables):
    from .nearshore import carry, density_grids

    buoy = T.at_buoy(spectrum).trains
    grids = density_grids(spectrum)
    rows = []
    for b in BREAKS:
        for t in carry(spectrum, tables[b], grids).trains[:3]:
            if t.is_short or not t.bins or math.isnan(t.from_deg):
                continue
            rows.append({"break": b, "train": t, "ref": buoy_train(t, buoy, spectrum.frequencies),
                         "peak": peak_bin(t, spectrum.frequencies)})
    return rows


def _pairs(rows):
    """Each listed pair of trains at two breaks, and what each rule does with it."""

    big = max((r["train"].hs_m for r in rows), default=0.0)
    for a, b in itertools.combinations(rows, 2):
        if a["break"] == b["break"] or min(a["train"].hs_m, b["train"].hs_m) < LISTED * big:
            continue
        ta, tb = a["train"], b["train"]
        yield a, b, {
            "periods alone": a["peak"] in tb.bins and b["peak"] in ta.bins,
            "buoy's trains": a["ref"] is not None and a["ref"] == b["ref"],
            "compass point": round(ta.from_deg / 22.5) % 16 == round(tb.from_deg / 22.5) % 16,
        }


RULES = ("periods alone", "buoy's trains", "compass point")


def archive(data_dir: Path = DEFAULT_DATA_DIR, station: str = "46232"):
    """Each rule's joins over the archive, against the buoy's own split."""

    from .nearshore import load_tables

    tables = load_tables()
    counts = Counter()
    for sp in T.load_spectra(Path(data_dir) / "spectra" / station):
        rows = _rows(sp.with_spread("mem"), tables)
        for a, b, joined in _pairs(rows):
            if a["ref"] is None or b["ref"] is None:
                continue
            same = a["ref"] == b["ref"]
            for rule, on in joined.items():
                counts[(rule, on, same)] += 1
    return counts


def _source_energy(freqs, swell, bins, held) -> float:
    """A synthetic swell's energy at the buoy in a train's band and headings."""

    hs, tp, frm, sg = swell
    widths = [T.Spectrum(None, freqs, [1] * len(freqs), *([[0] * len(freqs)] * 4)).bin_width(i)
              for i in range(len(freqs))]
    from .trainsplit import _jonswap
    raw = [_jonswap(f, tp) for f in freqs]
    scale = (hs / 4) ** 2 / sum(r * w for r, w in zip(raw, widths))
    e = sum(raw[i] * scale * widths[i] for i in bins)
    if held and (held[1] - held[0]) % 360:
        g = [math.exp(-_adiff(d, frm) ** 2 / (2 * sg * sg)) for d in range(360)]
        e *= sum(g[d] for d in range(360) if _inarc(d, held)) / sum(g)
    return e


#: Two swells each, (Hs m, Tp s, from °, spread °): periods 3 s or more apart
#: and 1-2 s apart, each from the south-west and from further west.
CONTROL = [((1.0, t1, d1, 12), (0.8, t2, d2, 15))
           for t1, t2 in ((15, 9), (15, 12), (15, 14), (12, 10))
           for d1, d2 in ((200, 230), (200, 250), (200, 270), (210, 290), (240, 270), (260, 280))]


#: A train is one swell's when that swell carries this share of its energy
#: in its band and headings. Below it the train IS both swells -- a break that
#: kept them as one band, or one swell's tail under the other's peak -- and no
#: rule can be right or wrong about it: such pairs are counted, not scored.
PURE = 2 / 3


def control(trials: int = 15, cases=CONTROL):
    """Each rule's joins against the known sources: {apart_s: Counter}."""

    from .nearshore import load_tables
    from .trainsplit import synthetic

    tables = load_tables()
    freqs = T.load_spectra(DEFAULT_DATA_DIR / "spectra" / "46232", limit=1)[-1].frequencies
    out: dict[str, Counter] = {}
    for swells in cases:
        apart = "3 s or more apart" if abs(swells[0][1] - swells[1][1]) >= 3 else "1-2 s apart"
        counts = out.setdefault(apart, Counter())
        for k in range(trials):
            sp = synthetic(freqs, swells, T.BUOY_DOF, random.Random(1000 * k + swells[1][1] * 31 + swells[1][2]))
            rows = _rows(sp, tables)
            for r in rows:
                t = r["train"]
                es = [_source_energy(freqs, s, t.bins, t.held or t.arc) for s in swells]
                top = max(range(len(swells)), key=lambda i: es[i])
                r["source"] = top if es[top] >= PURE * sum(es) else None
            for a, b, joined in _pairs(rows):
                if a["source"] is None or b["source"] is None:
                    counts["mixed"] += 1
                    continue
                for rule, on in joined.items():
                    counts[(rule, on, a["source"] == b["source"])] += 1
    return out


def _line(name: str, c: Counter, rule: str) -> str:
    joins = c[(rule, True, True)] + c[(rule, True, False)]
    pairs = c[(rule, True, True)] + c[(rule, False, True)]
    wrong = c[(rule, True, False)]
    return (f"  {name:20s} {rule:14s} joins {joins:5d}, wrong {wrong:4d} ({100 * wrong / max(joins, 1):4.1f}%), "
            f"duplicates caught {c[(rule, True, True)]}/{pairs} ({100 * c[(rule, True, True)] / max(pairs, 1):.0f}%)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--trials", type=int, default=15)
    parser.add_argument("--lines", action="store_true",
                        help="one line a swell: the headline's rules, scored (item 30)")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)
    if args.lines:
        return lines_main(args)
    print("The archive, against the buoy's own split (its own rule agrees by construction):")
    got = archive(args.data_dir)
    for rule in RULES:
        print(_line("46232", got, rule))
    print("\nThe known-answer control (two synthetic swells, buoy noise):")
    for apart, c in control(args.trials).items():
        for rule in RULES:
            print(_line(apart, c, rule))
        print(f"  {apart:20s} and {c['mixed']} pairs with a train no swell carries {PURE:.0%} of: not scored")
    return 0



# ------------------------------------------------- one line a SWELL (item 30)
#
#     python -m forecast.trainmatch --lines     # archive, control, forecast log
#
# The owner's call, 2026-11-27 (docs/handoff.md item 30): the headline says one
# line a BUOY TRAIN, and a row two buoy trains reach can read as the other one.
# At 28 Nov 03Z (run of 27 Nov 15:33Z) Center's one row peaked at 19.0 s and
# was credited to the 12.7 s buoy train, South's 19.0 s row to the 19.0 s one:
# "W at 19.0 s" twice, and South's 12.7 s row, its train "already said", never
# said. The aim is one line a swell. A line's WORDS are its row's peak period
# and heading, so what a line says is the swell holding the row's PEAK BIN --
# not the one carrying most of the row, which is what `Train.buoy` names.
#
# Each rule is a join: a row is left unsaid when it joins a line already said.
# Scored on the headline as a whole, an hour (or a trial) at a time:
#   due        the swells the eligible rows' words name (rows >= LISTED of the
#              biggest, pooled), each row's words its peak bin's swell when
#              that swell holds PURE of the bin, else "mixed" and not scored
#   unsaid     a due swell no line names
#   twice      a swell two lines name
#   right      neither
# In the CONTROL the swell is the truth (each synthetic swell's own energy,
# ray by ray, exactly); in the ARCHIVE it is the buoy's own split (no floor),
# a proxy, credited the same way. Heights pooled at 5 m, as trainmerge pools
# them; the page pools breaking heights, the same factor for every row of a
# break.

POINTS = ("N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
          "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW")


def compass(deg: float) -> str:
    """The page's 16-point name (`point` in app/forecast.html)."""

    return POINTS[round(deg / 22.5) % 16]


def words(row: dict) -> str:
    """A line's words as the page prints them, less the units."""

    return f"{compass(row['heading'])} {row['period']:.1f}"


def _ratio(a: float, b: float) -> float:
    return max(a, b) / max(min(a, b), 1e-9)


def _swell_join(ratio: float, deg: float):
    return lambda r, l: (_ratio(r["period"], l["period"]) <= ratio
                         and _adiff(r["heading"], l["heading"]) <= deg)


def _train_period_join(ratio: float):
    return lambda r, l: ((r["key"] is not None and r["key"] == l["key"]
                          and _ratio(r["period"], l["period"]) <= ratio) or words(r) == words(l))


def _either_join(ratio: float, deg: float):
    one, two = _swell_join(ratio, deg), _train_period_join(ratio)
    return lambda r, l: one(r, l) or two(r, l)


def _peak_join(also=None):
    """One line a buoy train, each row keyed by the buoy train holding most of
    its PEAK BIN -- the swell its words name -- not of the whole row; a row
    with no such train is its own line. `also`: a second test that joins."""

    return lambda r, l: ((r.get("pkey") is not None and r.get("pkey") == l.get("pkey"))
                         or words(r) == words(l) or (also is not None and also(r, l)))


#: The rules scored. "a buoy train" is LIVE's shipped rule and "+ words" the
#: Forecast tab's (fcSwellTrains, then lines whose words match are one).
#: "a swell" joins a row to a line whose period is within the ratio and
#: heading within the degrees, whatever buoy train either is; "a buoy train
#: and its period" joins only a row of the line's buoy train within the ratio
#: (or with the same words); "either" joins on either test -- a swell's two
#: rows far apart in heading (one swell through two windows, BRIEFING §49)
#: stay one line when one buoy train carried both.
LINE_RULES = {
    "a buoy train (LIVE)": None,
    "a buoy train + words (Forecast)": None,
    **{f"a swell: x{r:.2f}, {d:.0f}°": _swell_join(r, d)
       for r in (1.0, 1.12, 1.25) for d in (22.5, 30.0, 45.0)},
    **{f"a buoy train and its period: x{r:.2f}": _train_period_join(r) for r in (1.0, 1.12, 1.25)},
    **{f"either: x{r:.2f}, {d:.0f}°": _either_join(r, d) for r in (1.12, 1.25) for d in (30.0, 45.0)},
    "a buoy train by its peak bin": _peak_join(None),
    **{f"by its peak bin, or a swell: x{r:.2f}, 45°": _peak_join(_swell_join(r, 45.0)) for r in (1.12, 1.25)},
}


#: The rule the headline ships since 2026-11-28 (`briefing.same_swell`,
#: `fcSwellTrains`): a test pins that it lists what the Briefing lists.
SHIPPED_LINES = "either: x1.25, 45°"


def lines(pool: list[dict], rule: str) -> list[dict]:
    """The rows a rule lists, from pooled rows {hs, period, heading, key, brk}."""

    order = {b: k for k, b in enumerate(BREAKS)}
    pool = sorted(pool, key=lambda r: (-r["hs"], order.get(r["brk"], 9)))
    if not pool:
        return []
    big, out, said = pool[0]["hs"], [], set()
    join = LINE_RULES[rule]
    for r in pool:
        if r["hs"] < LISTED * big:
            break
        if join is None:                      # the shipped rules, as built
            if r["key"] is not None:
                if r["key"] in said:
                    continue
                said.add(r["key"])
            if rule.endswith("(Forecast)") and any(words(r) == words(l) for l in out):
                continue
        elif any(join(r, l) for l in out):
            continue
        out.append(r)
    return out


def _due(pool: list[dict]) -> set:
    if not pool:
        return set()
    big = max(r["hs"] for r in pool)
    return {r["src"] for r in pool if r["hs"] >= LISTED * big and r["src"] is not None}


def _score_lines(c: Counter, pool: list[dict]):
    due = _due(pool)
    c["hours"] += 1
    for rule in LINE_RULES:
        got = lines(pool, rule)
        named = Counter(r["src"] for r in got if r["src"] is not None)
        unsaid, twice = bool(due - set(named)), any(v > 1 for v in named.values())
        c[(rule, "lines")] += len(got)
        c[(rule, "mixed")] += sum(r["src"] is None for r in got)
        c[(rule, "unsaid")] += unsaid
        c[(rule, "twice")] += twice
        c[(rule, "right")] += not (unsaid or twice)


def _peak_rows(sp, table, grids, split, truth=None):
    """A break's shown rows (the shipped carry), each with its peak bin's
    swell: the true one (`truth`, the control) or the buoy train (archive)."""

    from .nearshore import _buoy_owner, carry
    from .trainmerge import _inarc as inarc, _rays

    rays = _rays(sp, table, grids, truth or ())
    owner = _buoy_owner(split)
    owners = [owner(i, int(d) % 360) for i, d, _, _ in rays]
    carried = carry(sp, table, grids, split).trains
    whole = {(t.bins, t.arc, round(t.hs_m, 9)) for t in carry(sp, table, grids).trains}
    out = []
    for t in carried[:SHOWN_ROWS]:
        pk = peak_bin(t, sp.frequencies)
        if pk is None or math.isnan(t.from_deg):
            continue
        is_whole = (t.bins, t.arc, round(t.hs_m, 9)) in whole
        n = len(truth) if truth else len(split)
        c, by_buoy = [0.0] * n, [0.0] * len(split)
        for m, (i, d, e, extra) in enumerate(rays):
            if i != pk or not inarc(int(d) % 360, t.arc):
                continue
            if not (is_whole or owners[m] in (t.buoys or (t.buoy,))):
                continue
            if owners[m] >= 0:
                by_buoy[owners[m]] += e
            if truth:
                for j, v in enumerate(extra):
                    c[j] += v
        if not truth:
            c = by_buoy
        pkey = max(range(len(split)), key=lambda j: by_buoy[j]) if any(by_buoy) else None
        top = max(range(n), key=lambda j: c[j]) if n else None
        src = top if top is not None and c[top] > 0 and c[top] >= PURE * sum(c) else None
        heading = t.lobes[0][0] if len(t.lobes) >= 2 else t.from_deg
        out.append({"hs": t.hs_m, "period": round(t.period_s, 1), "heading": round(heading),
                    "key": t.buoy, "pkey": pkey, "src": src, "short": t.is_short})
    return out


#: The rows a break tab shows (`nearshore.summarise`).
SHOWN_ROWS = 3


def _keyed(rows, split):
    """`buoy_train` as now.py writes it: None for a buoy train under the floors."""

    floored = {(f.bins, f.arc) for f in T.floor_trains(split)}
    for r in rows:
        for k in ("key", "pkey"):
            if r.get(k) is not None and (split[r[k]].bins, split[r[k]].arc) not in floored:
                r[k] = None
    return rows


_LCACHE = None


def _lines_archive_one(args):
    data_dir, index = args
    from .nearshore import buoy_split, density_grids, load_tables

    global _LCACHE
    if _LCACHE is None:
        _LCACHE = (load_tables(), T.load_spectra(Path(data_dir) / "spectra" / "46232"))
    tables, spectra = _LCACHE
    sp = spectra[index].with_spread("mem")
    grids = density_grids(sp)
    split = buoy_split(sp, grids)
    pool = []
    for b in BREAKS:
        for r in _keyed(_peak_rows(sp, tables[b], grids, split), split):
            pool.append({**r, "brk": b})
    return pool


def lines_archive(data_dir: Path = DEFAULT_DATA_DIR, workers: int = 4, limit: int | None = None):
    from multiprocessing import Pool

    n = len(T.load_spectra(Path(data_dir) / "spectra" / "46232"))
    idx = range(max(0, n - limit) if limit else 0, n)
    with Pool(workers) as p:
        pools = p.map(_lines_archive_one, [(str(data_dir), i) for i in idx], chunksize=20)
    c = Counter()
    for pool in pools:
        _score_lines(c, pool)
    return c, pools


#: Two swells from (nearly) one direction at two periods the buoy can part:
#: 28 Nov 03Z's W 12.7 s with a W 19.0 s over it, and its neighbours.
ONE_DIRECTION = [
    ((1.0, 12.7, 275, 15), (0.5, 19.0, 281, 12)), ((1.0, 13, 270, 15), (0.7, 18, 275, 12)),
    ((1.0, 12, 265, 15), (0.7, 17, 280, 12)), ((0.8, 16, 270, 12), (1.0, 11, 275, 15)),
    ((1.0, 14, 255, 15), (0.6, 19, 270, 12)), ((1.0, 11, 280, 15), (0.8, 15, 265, 12)),
]


def _lines_control_one(args):
    name, swells, seed = args
    from .nearshore import buoy_split, density_grids, load_tables
    from .trainmerge import _truth
    from .trainsplit import synthetic

    global _LCACHE
    if _LCACHE is None:
        _LCACHE = (load_tables(), T.load_spectra(DEFAULT_DATA_DIR / "spectra" / "46232", limit=1))
    tables, spectra = _LCACHE
    freqs = spectra[-1].frequencies
    sp = synthetic(freqs, swells, T.BUOY_DOF, random.Random(seed))
    grids = density_grids(sp)
    split = buoy_split(sp, grids)
    truth = [_truth(freqs, s) for s in swells]
    pool = []
    for b in BREAKS:
        for r in _keyed(_peak_rows(sp, tables[b], grids, split, truth), split):
            pool.append({**r, "brk": b})
    return name, pool


def _lines_group(swells) -> str:
    if len(swells) == 1:
        return "one swell"
    a, b = swells[:2]
    sep = _adiff(a[2], b[2])
    per = "3 s or more" if abs(a[1] - b[1]) >= 3 else "1-2 s"
    ang = "under 30°" if sep < 30 else "30-59°" if sep < 60 else "60° or more"
    return f"two, {per} and {ang} apart"


def lines_control(trials: int = 30, workers: int = 4):
    from multiprocessing import Pool

    from .trainmerge import CONTROL as PAIRS
    from .trainsplit import CASES

    named = ([("one swell", s) for s in CASES.values() if len(s) == 1]
             + [(_lines_group(p), list(p)) for p in PAIRS + ONE_DIRECTION])
    jobs = [(name, s, 1000 * k + 7 * ci) for ci, (name, s) in enumerate(named) for k in range(trials)]
    with Pool(workers) as p:
        got = p.map(_lines_control_one, jobs, chunksize=4)
    S = defaultdict(Counter)
    for name, pool in got:
        _score_lines(S[name], pool)
        _score_lines(S["all"], pool)
    return S


def lines_forecast_log(data_dir: Path = DEFAULT_DATA_DIR, since: str = "2026-11-04"):
    """The Forecast tab's lines over every logged build hour since `since`:
    {rule: Counter}, and each rule's lines at 28 Nov 03Z on the 27 Nov 15:33Z run.
    No truth here: lines a build hour, identical words, and how often it differs from the Forecast as shipped."""

    import glob
    import json

    out = defaultdict(Counter)
    case = {}
    for f in sorted(glob.glob(str(Path(data_dir) / "forecast_log" / "46232_shown" / "*.jsonl"))):
        for line in open(f):
            h = json.loads(line)
            if h["generated_utc"] < since:
                continue
            pool = []
            for b, x in (h.get("breaks") or {}).items():
                for t in ((x.get("nearshore") or {}).get("trains") or []):
                    if t.get("local") or t.get("from_deg") is None or t.get("period_s") is None:
                        continue
                    lobes = t.get("lobes") or []
                    pool.append({"hs": t.get("hs_m") or 0.0, "period": t["period_s"],
                                 "heading": lobes[0][0] if len(lobes) >= 2 else t["from_deg"],
                                 "key": t.get("swell"), "brk": b, "src": None})
            if not pool:
                continue
            shipped = [words(r) for r in lines(pool, "a buoy train + words (Forecast)")]
            for rule in LINE_RULES:
                if "peak bin" in rule:          # the log has no peak-bin credit
                    continue
                got = lines(pool, rule)
                w = [words(r) for r in got]
                c = out[rule]
                c["hours"] += 1
                c["lines"] += len(got)
                c["same words twice"] += len(w) != len(set(w))
                c["differs from the shipped Forecast"] += w != shipped
                if h["generated_utc"].startswith("2026-11-27T15:33") and h["valid_utc"] == "2026-11-28T03:00:00Z":
                    case[rule] = w
    return out, case


def _lines_report(c: Counter, title: str):
    n = c["hours"]
    print(f"  {title} ({n} {'hours' if 'archive' in title else 'trials'})")
    for rule in LINE_RULES:
        print(f"    {rule:38s} right {100 * c[(rule, 'right')] / max(n, 1):5.1f}%  "
              f"unsaid {100 * c[(rule, 'unsaid')] / max(n, 1):5.1f}%  "
              f"twice {100 * c[(rule, 'twice')] / max(n, 1):5.1f}%  "
              f"lines {c[(rule, 'lines')] / max(n, 1):.2f}  mixed {c[(rule, 'mixed')]}")


def lines_main(args) -> int:
    print("One line a swell: the headline scored an hour at a time.\n")
    c, _ = lines_archive(args.data_dir, args.workers, args.limit)
    _lines_report(c, "46232 archive, against the buoy's own split")
    S = lines_control(args.trials, args.workers)
    print()
    for name in ["all", *sorted(k for k in S if k != "all")]:
        _lines_report(S[name], f"control: {name}")
    fl, case = lines_forecast_log(args.data_dir)
    print("\n  Forecast log, every logged build hour since 4 Nov (no truth)")
    for rule, x in fl.items():
        n = x["hours"]
        print(f"    {rule:38s} lines {x['lines'] / max(n, 1):.2f}  same words twice {x['same words twice']}/{n}  "
              f"differs {x['differs from the shipped Forecast']}/{n}  28 Nov 03Z: {' | '.join(case.get(rule, []))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
