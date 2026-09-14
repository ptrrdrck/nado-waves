"""Event-driven rounds, and the dispersion maths behind the storm-origin call."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from forecast.dispersion import (
    GRAVITY,
    MIN_FIT_R2,
    distance_from_slope,
    origin_from_series,
)


def slope_for(distance_km: float) -> float:
    """Inverse of distance_from_slope, for building synthetic arrivals."""
    return GRAVITY * 3600.0 / (4 * math.pi * distance_km * 1000.0)


def synthetic_arrival(distance_km: float, hours: int = 36, lead_period: float = 20.0,
                      noise: float = 0.0):
    """A textbook dispersive arrival from a known distance."""
    import random

    rnd = random.Random(4)
    slope = slope_for(distance_km)
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    stamps, periods = [], {}
    for hour in range(hours):
        t = start + timedelta(hours=hour)
        inverse = 1.0 / lead_period + slope * hour + rnd.gauss(0, noise)
        stamps.append(t)
        periods[t] = 1.0 / inverse
    return periods, stamps


def test_distance_from_slope_inverts_cleanly():
    for km in (3000.0, 5000.0, 10000.0):
        assert distance_from_slope(slope_for(km)) == pytest.approx(km, rel=1e-6)


def test_a_known_storm_distance_is_recovered():
    periods, stamps = synthetic_arrival(5000.0)
    origin = origin_from_series(periods, stamps)
    assert origin is not None
    assert origin.distance_km == pytest.approx(5000.0, rel=0.02)
    assert origin.r_squared > 0.99


def test_a_nearer_storm_gives_a_steeper_decline_and_a_shorter_distance():
    near = origin_from_series(*synthetic_arrival(3000.0))
    far = origin_from_series(*synthetic_arrival(10000.0))
    assert near.distance_km < far.distance_km
    # A nearby storm's periods collapse fast; a distant one trickles down.
    assert near.trailing_period_s < far.trailing_period_s


def test_generation_time_is_before_the_arrival():
    periods, stamps = synthetic_arrival(5000.0)
    origin = origin_from_series(periods, stamps)
    age = (stamps[0] - origin.generated_at).total_seconds() / 86400
    # 5000 km at 20s group velocity is roughly three and a half days.
    assert 2.0 < age < 6.0


def test_noise_degrades_the_fit_and_is_rejected():
    # A messy arrival - overlapping swells, windswell on top - must not be
    # handed to a player as though the origin were known.
    periods, stamps = synthetic_arrival(5000.0, noise=0.02)
    origin = origin_from_series(periods, stamps, min_r2=MIN_FIT_R2)
    assert origin is None or origin.r_squared >= MIN_FIT_R2


def test_a_rising_period_is_not_an_arrival():
    # Period climbing means the swell is still filling, not dispersing past.
    periods, stamps = synthetic_arrival(5000.0)
    reversed_periods = {t: periods[stamps[-1 - i]] for i, t in enumerate(stamps)}
    assert origin_from_series(reversed_periods, stamps) is None


def test_a_flat_period_has_no_origin_to_report():
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    stamps = [start + timedelta(hours=h) for h in range(36)]
    assert origin_from_series({t: 15.0 for t in stamps}, stamps) is None


def test_too_few_points_is_declined_rather_than_guessed():
    periods, stamps = synthetic_arrival(5000.0, hours=4)
    assert origin_from_series(periods, stamps) is None


def test_an_implausible_distance_is_rejected():
    # A near-flat slope implies a storm further away than the Pacific is wide.
    periods, stamps = synthetic_arrival(50000.0)
    assert origin_from_series(periods, stamps) is None
