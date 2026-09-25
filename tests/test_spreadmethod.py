"""The two spreading functions compared by `forecast.spreadmethod`.

Neither can be tested against the truth -- there is no directional observation
at the beach -- so these pin what CAN be pinned: each is a distribution, each
gives back the buoy's own four numbers, MEM's exact integral agrees with brute
force, and the shipped form here is the forecast's to the last digit.
"""

from __future__ import annotations

import cmath
import math

import pytest

from forecast.geometry import _relative, load
from forecast.spreadmethod import (
    BREAKS,
    IN_WINDOW,
    Unrealisable,
    fourier,
    labels,
    mem,
    moments,
    split,
)
from forecast.transform import through
from tests.test_transform import synthetic

SPOTS, BLOCKERS = load()
BY_ID = {s.id: s for s in SPOTS}

CASES = [
    (0.60, 0.30, 200.0, 195.0),   # broad
    (0.87, 0.70, 248.0, 248.0),   # 2026-09-25T18Z's peak bin
    (0.93, 0.91, 180.0, 176.0),   # narrow enough to hide inside one degree
]


@pytest.mark.parametrize("r1,r2,a1,a2", CASES)
def test_both_are_distributions(r1, r2, a1, a2):
    for method in (fourier, mem):
        dist = method(r1, r2, a1, a2)
        assert len(dist) == 360
        assert min(dist) >= 0.0
        assert sum(dist) == pytest.approx(1.0, abs=1e-12)


@pytest.mark.parametrize("r1,r2,a1,a2", CASES)
def test_mem_gives_back_the_buoys_own_moments(r1, r2, a1, a2):
    """Sampled at bin centres, MEM missed this by up to 0.17 in r1 and 34°
    in α1 on archived spectra, because a narrow swell is a spike thinner than
    a degree. Integrated exactly, it does not."""

    got_r1, got_a1, got_r2, got_a2 = moments(mem(r1, r2, a1, a2))
    assert got_r1 == pytest.approx(r1, abs=2e-3)
    assert abs(_relative(got_a1, a1)) < 0.25
    assert got_r2 == pytest.approx(r2, abs=2e-3)
    assert abs(_relative(2 * got_a2, 2 * a2)) / 2 < 0.25


def test_mem_exact_integral_matches_brute_force():
    r1, r2, a1, a2 = CASES[2]
    c1 = r1 * cmath.exp(1j * math.radians(a1))
    c2 = r2 * cmath.exp(2j * math.radians(a2))
    p1 = (c1 - c2 * c1.conjugate()) / (1 - abs(c1) ** 2)
    p2 = c2 - c1 * p1
    per = 200
    fine = []
    for n in range(360):
        fine.append(sum(
            1.0 / abs(1 - p1 * cmath.exp(-1j * t) - p2 * cmath.exp(-2j * t)) ** 2
            for t in (math.radians(n + (k + 0.5) / per) for k in range(per))))
    total = sum(fine)
    exact = mem(r1, r2, a1, a2)
    assert max(abs(e - f / total) for e, f in zip(exact, fine)) < 5e-4


def test_mem_is_narrower_than_fourier_for_the_same_numbers():
    """The reason the comparison exists: same four numbers, different tails."""

    r1, r2, a1, a2 = CASES[1]
    far = [n for n in range(360) if abs(_relative(n + 0.5, a1)) > 60]
    assert sum(mem(r1, r2, a1, a2)[n] for n in far) < sum(fourier(r1, r2, a1, a2)[n] for n in far)


def test_moments_no_distribution_can_have_are_refused_not_patched():
    """r2 = 1 with r1 = 0.5 violates the Toeplitz condition."""

    with pytest.raises(Unrealisable):
        mem(0.5, 1.0, 200.0, 200.0)


def test_the_shipped_form_here_is_the_forecasts():
    """The control that makes the comparison mean anything: the labels and
    the integration here reproduce `transform.through` exactly."""

    marks = {sid: labels(BY_ID[sid], BLOCKERS) for sid in BREAKS}
    for direction in (190.0, 225.0, 255.0, 290.0):
        spectrum = synthetic(direction, spread_deg=25.0)
        out, _, _ = split(spectrum, marks, {"all": None})
        for sid in BREAKS:
            here = out["all"]["shipped"][sid].shares.get(IN_WINDOW, 0.0)
            there = through(spectrum, BY_ID[sid], BLOCKERS).fraction
            assert here == pytest.approx(there, abs=1e-12)
