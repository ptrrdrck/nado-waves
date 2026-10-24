"""Which of the buoy's trains a break's train is: the Briefing's one line a swell.

    python -m forecast.trainmatch      # the archive and the known-answer control (~30 s)

Owner's request and calls, 2026-10-24: the headline listed W at 9.1 s (South)
and WSW at 9.9 s (Center), one W swell at 46232 read through two breaks'
windows, either side of the W / WSW boundary. "One a compass point" could not
see that. Each break's train is now matched to the BUOY's train it belongs to
(`buoy_train`): the one holding its peak period, and when the buoy divided
that band by direction (BRIEFING §40), the one whose headings hold its own,
else the nearest. Trains of one buoy train are one line (`briefing.listed_trains`).

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
from collections import Counter
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
            if t.is_wind_sea or not t.bins or math.isnan(t.from_deg):
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
    args = parser.parse_args(argv)
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


if __name__ == "__main__":
    sys.exit(main())
