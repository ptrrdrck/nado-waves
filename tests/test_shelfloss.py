"""forecast.shelfloss's physics, on synthetic paths: what it must get right
before its archive numbers mean anything (BRIEFING §56)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from forecast import raytrace as R
from forecast import shelfloss as S
from forecast.surfzone import fraction_breaking


def paths(depths: list[float], step: float = 20.0, freq: float = 0.07) -> S.FreqPaths:
    omega = 2 * math.pi * freq
    d = np.array([depths], float)
    return S.FreqPaths(freq, omega, d, np.full(d.shape, step), R.wavenumber(omega, S._DEPTHS),
                       R.speeds(omega, S._DEPTHS)[1], np.ones(1), np.zeros(1, int))


@pytest.mark.parametrize("ab", [0.08, 0.5, 2.0, 10.0])
def test_madsen_fw_solves_its_own_equation(ab):
    fw = float(S.madsen_fw(np.array([ab]))[0])
    y = 1 / (4 * math.sqrt(fw))
    assert y + math.log10(y) == pytest.approx(S.M_F + math.log10(ab / S.K_N), abs=1e-9)


def test_madsen_fw_limits_and_order():
    assert float(S.madsen_fw(np.array([0.05]))[0]) == 0.3        # a_b/K_N under 1.57
    fw = S.madsen_fw(np.array([0.5, 2.0, 10.0]))
    assert fw[0] > fw[1] > fw[2]                                   # rougher, relatively, at small excursion


def test_vectorised_qb_is_surfzones():
    r = np.linspace(0.0, 1.3, 131)
    for v, q in zip(r, S.fraction_breaking_v(r)):
        assert q == pytest.approx(fraction_breaking(float(v)), abs=1e-12)


def test_jonswap_march_without_breaking_is_the_tracers_friction_factor():
    """Control: the shipped law along a path is exp(−∫ friction_rate ds),
    whatever the height — linear, as the table stores it."""

    depths = list(np.linspace(60.0, 5.0, 400))
    fp = paths(depths)
    peak = fp
    expect = math.exp(-float(np.sum(R.friction_rate(fp.omega, np.array(depths)) * 20.0)))
    for hs in (0.5, 3.0):
        F = S.march(fp, hs, 0.0, peak, 0.6, "jonswap", False)
        assert F[0] == pytest.approx(expect, rel=1e-3)


def test_breaking_takes_nothing_in_deep_water_and_more_the_bigger_the_sea_on_a_shelf():
    deep = paths([200.0] * 200)
    assert S.march(deep, 3.0, 0.0, deep, 0.6, "jonswap", True)[0] == pytest.approx(
        S.march(deep, 3.0, 0.0, deep, 0.6, "jonswap", False)[0], rel=1e-9)
    shelf = paths([40.0] * 50 + [7.0] * 200 + list(np.linspace(7.0, 5.0, 50)))
    lost = []
    for hs in (1.0, 2.0, 2.6):
        with_b = S.march(shelf, hs, 0.0, shelf, 0.55, "jonswap", True)[0]
        without = S.march(shelf, hs, 0.0, shelf, 0.55, "jonswap", False)[0]
        lost.append(1 - with_b / without)
    assert lost[0] < 1e-3                  # a 1 m sea does not break in 7 m of water
    assert lost[0] < lost[1] < lost[2]


def test_madsen_takes_a_larger_share_of_a_bigger_sea_and_jonswap_the_same():
    shelf = paths([40.0] * 50 + [8.0] * 300 + list(np.linspace(8.0, 5.0, 50)))
    j = [S.march(shelf, hs, 0.0, shelf, 0.55, "jonswap", False)[0] for hs in (0.8, 2.5)]
    m = [S.march(shelf, hs, 0.0, shelf, 0.55, "madsen", False)[0] for hs in (0.8, 2.5)]
    assert j[0] == pytest.approx(j[1], rel=1e-9)
    assert m[1] < m[0]
