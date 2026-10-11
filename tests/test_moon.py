"""The Moon's phases, distance and declination (`forecast.moon`), against an
independent ephemeris.

The expected times are PyEphem's for October 2026 (phases from its own
next_* functions, the rest from its positions every 5 min), so this pins the
truncated lunar theory against a different implementation, not against
itself. BRIEFING §41: over 2026-2027 phases agree within 4 min.
"""

from datetime import datetime, timedelta, timezone

import pytest

from forecast import moon

UTC = timezone.utc

PYEPHEM = [
    ("perigee", datetime(2026, 10, 1, 20, 40, tzinfo=UTC), 30),
    ("farthest north", datetime(2026, 10, 2, 11, 25, tzinfo=UTC), 30),
    ("last quarter", datetime(2026, 10, 3, 13, 25, tzinfo=UTC), 5),
    ("over the equator", datetime(2026, 10, 8, 22, 50, tzinfo=UTC), 10),
    ("new moon", datetime(2026, 10, 10, 15, 50, tzinfo=UTC), 5),
    ("farthest south", datetime(2026, 10, 16, 2, 40, tzinfo=UTC), 30),
    ("apogee", datetime(2026, 10, 16, 22, 50, tzinfo=UTC), 30),
    ("first quarter", datetime(2026, 10, 18, 16, 13, tzinfo=UTC), 5),
    ("over the equator", datetime(2026, 10, 23, 10, 25, tzinfo=UTC), 10),
    ("full moon", datetime(2026, 10, 26, 4, 12, tzinfo=UTC), 5),
    ("perigee", datetime(2026, 10, 28, 18, 0, tzinfo=UTC), 30),
    ("farthest north", datetime(2026, 10, 29, 17, 30, tzinfo=UTC), 30),
]


@pytest.fixture(scope="module")
def october():
    return moon.events(datetime(2026, 10, 1, tzinfo=UTC), datetime(2026, 11, 1, tzinfo=UTC))


def test_every_event_of_october_2026_and_nothing_else(october):
    assert [n for n, _ in october] == [n for n, _, _ in PYEPHEM]


@pytest.mark.parametrize("name,when,minutes", PYEPHEM)
def test_each_event_lands_where_pyephem_puts_it(october, name, when, minutes):
    got = min((t for n, t in october if n == name), key=lambda t: abs(t - when))
    assert abs(got - when) <= timedelta(minutes=minutes), (name, got, when)


def test_mean_elements_are_not_good_enough():
    """Why a lunar theory at all: the mean elongation puts this new moon on
    the 11th, the real one is the 10th."""

    from forecast import tidephase as tp

    a = tp._args(datetime(2026, 10, 10, 15, 50, tzinfo=UTC))
    mean = (a["s"] - a["h"]) % 360
    assert 340 < mean < 355                     # ~13 h short of new
    assert moon.elongation(datetime(2026, 10, 10, 15, 50, tzinfo=UTC)) < 0.1 \
        or moon.elongation(datetime(2026, 10, 10, 15, 50, tzinfo=UTC)) > 359.9


def test_declination_reaches_the_standstill():
    """2026 is near the major lunar standstill: the Moon passes 27.5°, where
    in a minor standstill year (2034) it stops near 18°."""

    t = datetime(2026, 10, 16, 2, 40, tzinfo=UTC)
    assert moon.declination(t) < -27.5
