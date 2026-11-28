"""One swell, one line: a break's train matched to the buoy's train it is
(forecast.trainmatch, owner's call 2026-10-24), and the measurement behind
it, re-run small."""

from __future__ import annotations

import math

import pytest

from forecast import trainmatch as M
from forecast.transform import Train

FREQS = [0.03 + 0.01 * i for i in range(40)]


def _t(period, frm, bins, arc=()):
    return Train(1.0, period, frm, 0.5, bins=tuple(bins), arc=tuple(arc))


def test_a_break_train_is_the_buoy_train_holding_its_peak():
    buoy = [_t(1 / 0.065, 200, range(2, 6)), _t(1 / 0.11, 278, range(6, 30))]
    assert M.buoy_train(_t(1 / 0.11, 264, range(5, 30)), buoy, FREQS) == 1
    assert M.buoy_train(_t(1 / 0.10, 256, range(7, 25)), buoy, FREQS) == 1   # W and WSW: one swell
    assert M.buoy_train(_t(1 / 0.065, 221, range(2, 30)), buoy, FREQS) == 0  # a whole-band train: its peak decides
    assert M.buoy_train(_t(1 / 0.36, 270, range(33, 36)), buoy, FREQS) is None


def test_of_a_band_the_buoy_divided_by_direction_the_side_holding_its_heading():
    """The failure that rejected periods alone: one band, a SSW and a W
    swell, which the buoy divides by direction (BRIEFING §40)."""

    buoy = [_t(1 / 0.08, 205, range(3, 20), arc=(150, 240)), _t(1 / 0.15, 272, range(3, 20), arc=(240, 330))]
    assert M.buoy_train(_t(1 / 0.08, 220, range(3, 20)), buoy, FREQS) == 0
    assert M.buoy_train(_t(1 / 0.11, 253, range(3, 20)), buoy, FREQS) == 1
    # No arc holds it: the nearest heading.
    buoy[1] = _t(1 / 0.15, 272, range(3, 20), arc=(250, 330))
    assert M.buoy_train(_t(1 / 0.11, 245, range(3, 20)), buoy, FREQS) == 1


def test_the_known_answer_control_still_reads_as_measured():
    """Two swells 6 s apart, from SSW and W: rarely a wrong join, nearly
    every duplicate caught, where the compass point catches far fewer."""

    c = M.control(trials=4, cases=[((1.0, 15, 200, 12), (0.8, 9, 270, 15))])["3 s or more apart"]
    rule = "buoy's trains"
    joins = c[(rule, True, True)] + c[(rule, True, False)]
    dups = c[(rule, True, True)] + c[(rule, False, True)]
    assert joins and c[(rule, True, False)] <= 0.05 * joins
    assert c[(rule, True, True)] >= 0.9 * dups
    assert c[("compass point", True, True)] < c[(rule, True, True)]


def test_the_page_never_reads_it():
    from pathlib import Path

    page = (Path(__file__).resolve().parent.parent / "app" / "forecast.html").read_text()
    assert "buoy_train" not in page


def test_the_scored_one_line_a_swell_rule_is_the_one_the_briefing_ships():
    """`trainmatch --lines` scored `SHIPPED_LINES`; the headline must list
    exactly what it scored, row for row (docs/handoff.md item 30)."""

    import random

    from forecast import briefing as bf

    rng = random.Random(30)
    for _ in range(400):
        pool = []
        for b in M.BREAKS:
            for _ in range(rng.randint(0, 3)):
                pool.append({"hs": round(rng.uniform(0.1, 1.5), 3), "brk": b, "src": None,
                             "period": rng.choice([7.7, 9.1, 9.9, 11.1, 12.5, 13.3, 14.3, 15.4, 16.7, 19.0]),
                             "heading": rng.randint(180, 300), "key": rng.choice([None, 0, 1, 2])})
        sites = [{"id": b, "trains": [{"hs_m": r["hs"], "period_s": r["period"], "from_deg": r["heading"],
                                       "lobes": [], "buoy_train": r["key"]} for r in pool if r["brk"] == b]}
                 for b in M.BREAKS]
        want = [(r["period"], r["heading"]) for r in M.lines(pool, M.SHIPPED_LINES)]
        got = [(t["period_s"], t["from_deg"]) for t in bf.listed_trains(sites)] if pool else []
        assert got == want, (pool, got, want)
