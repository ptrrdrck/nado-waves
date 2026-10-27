"""The spectrum-noise report (forecast.spectrumreport): its known answer and its
second noise model are held to what they claim; nothing here reads the archive."""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone

import pytest

from forecast import spectrumreport as R
from forecast import trainsplit as TS
from forecast import transform as T

FREQS = [0.025 + 0.005 * k for k in range(15)] + [0.1 + 0.01 * k for k in range(49)]
SWELLS = TS.CASES["S 15 s + NW 12 s + sea"]


def test_the_known_sea_holds_its_swells_energy():
    sea = R.KnownSea(FREQS, SWELLS)
    m0 = sum(c * sea.bin_width(i) for i, c in enumerate(sea.c11))
    assert m0 == pytest.approx(sum((hs / 4) ** 2 for hs, *_ in SWELLS), rel=1e-9)
    # Its direction integrates to the bin's energy, per radian.
    i = max(range(len(FREQS)), key=lambda k: sea.c11[k])
    total = sum(sea.density(i, d + 0.5) for d in range(360)) * math.radians(1.0)
    assert total == pytest.approx(sea.c11[i], rel=1e-6)


def test_the_components_model_is_always_readable_and_unbiased_in_energy():
    """What it exists for: moments of a real distribution, so maximum entropy
    reads every bin, with c11 noise of the same size as trainsplit's."""

    sea = R.KnownSea(FREQS, SWELLS)
    reports = [R.components_report(FREQS, SWELLS, T.BUOY_DOF, random.Random(k)) for k in range(12)]
    assert all(R.fallback_share(r) == 0.0 for r in reports)
    i = max(range(len(FREQS)), key=lambda k: sea.c11[k])
    ratios = [r.c11[i] / sea.c11[i] for r in reports]
    assert sum(ratios) / len(ratios) == pytest.approx(1.0, abs=0.15)
    assert max(ratios) - min(ratios) > 0.1                       # it is noisy


def test_smoothing_is_the_splitters_and_keeps_a_flat_curve_flat():
    assert R.smooth([1.0] * 5) == pytest.approx([1.0] * 5)
    assert R.smooth([0.0, 4.0, 0.0]) == pytest.approx([4 / 3, 2.0, 4 / 3])
    assert T.BAND_SMOOTH == (1, 2, 1)


def test_a_three_hour_mean_needs_all_three_hours():
    t0 = datetime(2026, 10, 1, tzinfo=timezone.utc)
    hours = [0, 1, 2, 4, 5, 6]                                    # 03Z missing
    by_time = {t0 + timedelta(hours=h): {"buoy": [float(h)]} for h in hours}
    got = R.treated(by_time, "buoy")["3 h mean"]
    assert sorted((t - t0).total_seconds() / 3600 for t in got) == [2, 6]
    assert got[t0 + timedelta(hours=2)] == [1.0]


def test_bumps_count_what_a_reader_would_see():
    assert R.bumps([0, 1, 5, 1, 0]) == 1
    assert R.bumps([0, 5, 1, 4, 0]) == 2
    assert R.bumps([0, 5, 1, 0.2, 0]) == 1                        # under BUMP of the highest
