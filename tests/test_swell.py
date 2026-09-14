"""Swell propagation: the physics, on known answers."""

from __future__ import annotations

import math

import pytest

from forecast.swell import (
    aimed_at,
    great_circle_km,
    group_velocity,
    initial_bearing,
    travel_hours,
)


def test_group_velocity_is_half_the_phase_speed():
    # Deep water: C = gT/2pi, Cg = C/2 = gT/4pi. Getting this wrong doubles
    # every travel time and puts the swell a day and a half early.
    for period in (10.0, 16.0, 20.0):
        phase = 9.81 * period / (2 * math.pi)
        assert group_velocity(period) == pytest.approx(phase / 2)


def test_longer_swell_travels_faster():
    assert group_velocity(20) > group_velocity(13)


def test_gulf_of_alaska_travel_times_match_the_physics():
    # 3383 km: a 20s swell in ~2.5 days, a 13s one in ~3.9.
    assert travel_hours(3383, 20) == pytest.approx(60, abs=4)
    assert travel_hours(3383, 13) == pytest.approx(92, abs=6)


def test_dispersion_spreads_arrival_over_more_than_a_day():
    # Why resolution must be a window peak and never a spot reading.
    spread = travel_hours(3383, 13) - travel_hours(3383, 20)
    assert spread > 24


def test_great_circle_distance_is_sane():
    gulf, san_pedro = (56.23, -148.02), (33.62, -118.32)
    assert great_circle_km(gulf, san_pedro) == pytest.approx(3400, abs=200)
    assert great_circle_km(san_pedro, san_pedro) == pytest.approx(0, abs=1e-6)


def test_bearing_from_the_gulf_to_socal_points_southeast():
    b = initial_bearing((56.23, -148.02), (33.62, -118.32))
    assert 90 < b < 160


def test_aiming_uses_the_direction_waves_travel_not_where_they_came_from():
    # mwd is where swell comes FROM. Swell from 315 (NW) travels toward 135
    # (SE) — which is roughly Gulf of Alaska to SoCal.
    assert aimed_at(315.0, 135.0)
    # The same swell is NOT heading northwest.
    assert not aimed_at(315.0, 315.0)


def test_a_swell_aimed_elsewhere_is_excluded():
    # Counting swell pointed at Baja as if it were ours is noise, and at long
    # range most readings are pointed somewhere else.
    assert not aimed_at(315.0, 240.0, tolerance=60.0)
    assert aimed_at(315.0, 180.0, tolerance=60.0)


def test_aim_wraps_across_north():
    assert aimed_at(170.0, 355.0, tolerance=30.0)   # travels toward 350
