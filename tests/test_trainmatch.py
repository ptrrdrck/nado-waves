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
