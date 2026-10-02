"""Running a best track forward to a buoy: the band, the score and its controls."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from forecast import stormtrack as S
from forecast.origintracks import Fix
from forecast.swell import destination_point
from forecast.transform import Spectrum

UTC = timezone.utc
HOME = (32.4, -119.5)
FREQS = [0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10]
T0 = datetime(2026, 9, 1, tzinfo=UTC)
DAYS = 40


def storm(bearing=150.0, distance=2000.0, at=T0 + timedelta(days=20)):
    lat, lon = destination_point(HOME, bearing, distance)
    return [Fix("ep17", "TEST", at + timedelta(hours=6 * k), lat, lon, 120) for k in range(8)]


def spectra(signal_from=150.0, delay=timedelta(0), fixes=None):
    """Hourly spectra: a weak westerly everywhere, and the storm's swell
    from `signal_from` in the cells its band predicts, `delay` late."""

    fixes = fixes or storm()
    band = S.Band("ep17", "TEST", "x", fixes, [S.great_circle_km(HOME, (f.lat, f.lon)) for f in fixes],
                  150.0, 120)
    out = []
    for h in range(DAYS * 24):
        t = T0 + timedelta(hours=h)
        c11, a1 = [], []
        for f in FREQS:
            hit = band.contains(t - delay, f)
            c11.append(0.5 if hit else 0.02)
            a1.append(signal_from if hit else 250.0)
        n = len(FREQS)
        out.append(Spectrum(time=t, frequencies=FREQS, c11=c11, a1=a1, a2=a1,
                            r1=[0.9] * n, r2=[0.7] * n))
    return out, band


def test_a_wave_reaches_the_buoy_at_the_group_speed():
    fix = storm()[0]
    got = S.arrival(fix, 1 / 14.0, 2000.0)
    cg = 9.81 * 14.0 / (4 * math.pi)
    assert (got - fix.time).total_seconds() == pytest.approx(2000e3 / cg)


def test_a_storm_whose_swell_arrived_on_schedule_from_its_bearing_explains_its_band():
    sp, band = spectra()
    result = S.evaluate(band, S.Field(sp, spread="fourier"))
    assert result.actual.coverage == 1.0
    assert result.actual.rank > 0.9
    assert result.explains


def test_the_same_swell_ten_days_late_is_not_this_storm():
    sp, band = spectra(delay=timedelta(days=10))
    result = S.evaluate(band, S.Field(sp, spread="fourier"))
    assert not result.explains
    assert result.shifted[10].rank > result.actual.rank


def test_on_schedule_but_from_somewhere_else_is_not_this_storm():
    sp, band = spectra(signal_from=240.0)
    result = S.evaluate(band, S.Field(sp, spread="fourier"))
    assert not result.explains


def test_a_band_over_missing_spectra_says_so():
    sp, band = spectra()
    gap = [s for s in sp if not (T0 + timedelta(days=19) <= s.time <= T0 + timedelta(days=26))]
    result = S.evaluate(band, S.Field(gap, spread="fourier"))
    assert result.actual.coverage < S.MIN_COVERAGE and not result.explains


def test_only_hurricane_strength_fixes_make_a_band():
    weak = [Fix(f.storm, f.name, f.time, f.lat, f.lon, 40) for f in storm()]
    assert S.bands({"ep17": weak}, {"46047": HOME}) == []
    assert len(S.bands({"ep17": storm()}, {"46047": HOME})) == 1
