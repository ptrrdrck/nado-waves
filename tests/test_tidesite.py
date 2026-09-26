"""forecast.tidesite: the bay gauge's level carried to the open coast.

The transfer constants are MEASURED. This re-fits them from the comparison
series `collector.tidestations` stores, so the constants cannot drift from the
evidence without a test failing.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from forecast.tidesite import (LEAD_MIN, OFFSET_M, RATIO, coast_level, forecast_level,
                               interpolate, measure, msl_above_mllw)


def test_the_constants_are_what_the_comparison_measures():
    got = measure()
    assert got["ratio"] == pytest.approx(RATIO, abs=0.005)
    assert got["offset_m"] == pytest.approx(OFFSET_M, abs=0.005)
    assert abs(got["lead_min"] - LEAD_MIN) <= 3
    assert got["rms_m"] < 0.05


def test_the_open_coast_swings_less_than_the_bay():
    msl = msl_above_mllw()
    high, low = msl + 1.0, msl - 1.0
    assert coast_level(high, msl) - coast_level(low, msl) == pytest.approx(2 * RATIO)
    assert coast_level(msl, msl) == pytest.approx(OFFSET_M)


def test_msl_is_read_from_co_ops_datums():
    assert 0.8 < msl_above_mllw() < 1.0


T0 = datetime(2026, 9, 26, tzinfo=timezone.utc)
HOURLY = [(T0 + timedelta(hours=i), float(i)) for i in range(4)]


def test_interpolation_is_linear_and_refuses_gaps():
    assert interpolate(HOURLY, T0 + timedelta(minutes=30)) == pytest.approx(0.5)
    assert interpolate(HOURLY, T0 - timedelta(minutes=1)) is None
    gappy = [HOURLY[0], HOURLY[3]]
    assert interpolate(gappy, T0 + timedelta(hours=1)) is None


def test_the_forecast_level_leads_and_carries_the_departure():
    msl = 1.0
    got = forecast_level(HOURLY, T0 + timedelta(hours=1), 0.2, msl)
    bay = 1.0 + LEAD_MIN / 60.0 + 0.2
    assert got == pytest.approx(OFFSET_M + RATIO * (bay - msl))
    assert forecast_level(HOURLY, T0 + timedelta(hours=5), 0.2, msl) is None


def test_the_cards_forecast_height_is_the_bay_prediction_carried_to_the_coast():
    from forecast.tidesite import coast_predicted

    got = coast_predicted(HOURLY, T0 + timedelta(hours=1))
    assert got == pytest.approx(RATIO * (1.0 + LEAD_MIN / 60.0))
    assert coast_predicted(HOURLY, T0 + timedelta(hours=3)) is None   # past the series
