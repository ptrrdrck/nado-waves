"""forecast.nearshoretest's pieces that need no year of data: the conversion
of CDIP's moments to NDBC's form, the band sums and directions, the bands."""

from __future__ import annotations

import math
from datetime import datetime, timezone

import pytest

from forecast import nearshoretest as nt

T = datetime(2024, 1, 1, tzinfo=timezone.utc)


def spec_of(energy, a1, b1, a2, b2, bands):
    return {"energy": {T: energy}, "moments": {T: a1 + b1 + a2 + b2}, "bands": bands}


def test_cdip_moments_become_ndbc_directions_from():
    # Swell FROM 270° (west): a1 = cos 270 = 0, b1 = sin 270 = -1 ("from,
    # clockwise from north", BRIEFING §56c); a narrow spread.
    th = math.radians(270)
    s = spec_of([1.0], [0.9 * math.cos(th)], [0.9 * math.sin(th)],
                [0.7 * math.cos(2 * th)], [0.7 * math.sin(2 * th)], [(0.07, 0.065, 0.075)])
    sp = nt.to_spectrum(T, s, [0.07])
    assert sp.a1[0] == pytest.approx(270.0)
    assert sp.r1[0] == pytest.approx(0.9) and sp.r2[0] == pytest.approx(0.7)
    assert sp.a2[0] % 180 == pytest.approx(90.0)          # principal axis, ±180 alike
    # Most of the density points where the swell comes from.
    assert sp.density(0, 270.0) > 5 * sp.density(0, 90.0)


def test_a_gap_in_energy_or_moments_drops_the_record():
    s = spec_of([1.0, None], [0, 0], [0, 0], [0, 0], [0, 0], [(0.07, 0.065, 0.075), (0.08, 0.075, 0.085)])
    assert nt.to_spectrum(T, s, [0.07, 0.08]) is None


def test_bands_are_clipped_to_what_every_series_covers():
    got = nt.coarse_bands([0.0225, 0.0325], [0.585, 0.45])
    assert got[0][0] == 0.0325 and got[-1][1] == 0.45
    assert all(b > a for a, b in got)


def test_series_bands_conserve_energy_and_direction_follows_a1_b1():
    bands = [(0.05, 0.04, 0.06), (0.1, 0.09, 0.11)]
    coarse = [(0.0, 0.075), (0.075, 0.2)]
    e = nt.series_bands([2.0, 1.0], bands, coarse)
    assert e.tolist() == pytest.approx([0.04, 0.02])
    th = [math.radians(200), math.radians(280)]
    d = nt.series_direction([2.0, 1.0], [math.cos(x) for x in th] + [math.sin(x) for x in th],
                            bands, coarse)
    assert d.tolist() == pytest.approx([200.0, 280.0])
    # De-shoaling divides by Ks² > 0: deep-water-equivalent differs, finitely.
    deq = nt.series_bands([2.0, 1.0], bands, coarse, depth=21.0)
    assert all(x > 0 for x in deq)


def test_a_band_too_small_to_read_is_not_scored():
    r = {"a": [1.0, 1e-6], "b": [1.0, 1e-6]}
    assert nt.ratio(r, "a", "b", 0) == 1.0
    assert math.isnan(nt.ratio(r, "a", "b", 1))           # 4·sqrt(1e-6) = 0.004 m < MIN_HS
