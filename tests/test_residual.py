"""The residual test: mostly about not accidentally cheating on causality."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from forecast.residual import assess_lead, autocorrelation
from forecast.verify import Pair

UTC = timezone.utc
LEAD = 240


def daily(year: int, forecast: float, offsets, start_day: int = 1) -> list[Pair]:
    """One pair a day; `offsets` supplies the observed-minus-truth wobble."""

    base = datetime(year, 1, 1, tzinfo=UTC) + timedelta(days=start_day)
    return [
        Pair(base + timedelta(days=i), LEAD, forecast, forecast + offsets[i % len(offsets)])
        for i in range(200)
    ]


def test_autocorrelation_signs():
    assert autocorrelation([1.0, 2.0, 3.0, 4.0, 5.0], 1) == pytest.approx(1.0)
    assert autocorrelation([1.0, -1.0] * 20, 1) == pytest.approx(-1.0)


def test_constant_bias_gives_expanding_no_edge_over_static():
    """When the offset never moves, tracking it recently buys nothing."""

    pairs = daily(2023, 1.0, [0.30, 0.30, 0.30]) + daily(2025, 1.0, [0.30, 0.30, 0.30])
    result = assess_lead(pairs, LEAD, (2023,), (2025,))
    assert result.static_rmse_m == pytest.approx(0.0, abs=1e-9)
    assert result.expanding_rmse_m == pytest.approx(0.0, abs=1e-9)
    assert result.windowed_rmse_m == pytest.approx(0.0, abs=1e-9)


def test_a_bias_that_actually_moves_is_detected():
    """Plant a real drift and the windowed correction must find it.

    The fit years carry one offset and the test year a different one, so the
    static correction is wrong all through the test year while a trailing
    window catches up.
    """

    pairs = daily(2023, 1.0, [0.0]) + daily(2025, 1.0, [0.5])
    result = assess_lead(pairs, LEAD, (2023,), (2025,))
    assert result.static_rmse_m == pytest.approx(0.5, abs=1e-6)
    # Not zero: at a 240-hour lead with a 30-sample window, the first weeks of
    # the test year are still averaging in the old regime. Catching up late is
    # the correct behaviour, and it is why the real-data gain is a lower bound.
    assert result.windowed_rmse_m < result.static_rmse_m / 2
    assert result.windowed_rmse_m < result.expanding_rmse_m
    assert result.drift_gain > 0.0


def test_correction_never_uses_an_observation_from_after_the_cycle():
    """The load-bearing test. Relaxing this invents a large fake improvement.

    Every test-year pair here has a residual of exactly +1.0 while everything
    knowable at cycle time is 0.0. A leaky implementation would subtract the
    +1.0 and score a perfect zero; a causal one cannot see it at all.
    """

    train = daily(2023, 1.0, [0.0])
    # The test year begins immediately after the training year ends, so at a
    # 240-hour lead the freshest knowable residual is ten days before each
    # test moment - which is still 2023, where every residual is zero.
    test = [
        Pair(datetime(2025, 1, 1, tzinfo=UTC) + timedelta(days=i), LEAD, 1.0, 2.0)
        for i in range(40)
    ]
    result = assess_lead(train + test, LEAD, (2023,), (2025,), minimum=30)
    assert result.static_rmse_m == pytest.approx(1.0, abs=1e-6)
    # Ten days into the test year the window starts seeing test-year residuals,
    # so it improves - but it can never reach zero, and it must not start at it.
    assert result.windowed_rmse_m > 0.3


def test_too_few_pairs_returns_none_rather_than_a_confident_number():
    assert assess_lead(daily(2023, 1.0, [0.1])[:5], LEAD, (2023,), (2025,)) is None


def test_transit_gate_marks_long_leads_blind():
    """A satellite cannot see a swell whose storm has not happened yet."""

    from forecast.residual import SOUTH_SWELL_PERIOD_S, SOUTHERN_OCEAN_KM
    from forecast.swell import travel_hours

    transit_h = travel_hours(SOUTHERN_OCEAN_KM, SOUTH_SWELL_PERIOD_S)
    # Eight days, give or take: long enough that a ten-day forecast is blind and
    # a five-day one is not. If this drifts, the Tier 2 argument changes.
    assert 7.0 * 24 < transit_h < 8.5 * 24
    assert 168 < transit_h < 192
