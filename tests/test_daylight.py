"""forecast.daylight: sunrise and sunset at Coronado's center break, for the
night shading behind the Tide charts.

The reference times are from `astral` 3.2, an independent implementation of
the full solar-position series, run for the center break's own position on
2026-10-02; it agreed with this module to within a minute on all three dates.
(The US Naval Observatory's API, the better reference, is denied at CONNECT
from a session.) Two minutes' tolerance is far finer than the shading shows.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from forecast import daylight


def minutes(t: datetime) -> float:
    return t.hour * 60 + t.minute + t.second / 60


@pytest.mark.parametrize("day,rise,sets", [
    # astral, at the center break, in UTC: (sunrise, sunset).
    (date(2026, 6, 21), (12, 42), (2, 59)),
    (date(2026, 10, 1), (13, 43), (1, 34)),
    (date(2026, 12, 21), (14, 47), (0, 46)),
])
def test_sunrise_and_sunset_match_the_published_times(day, rise, sets):
    lat, lon = daylight.position()
    up = daylight._sun(day, lat, lon, rising=True)
    down = daylight._sun(day, lat, lon, rising=False)
    assert abs(minutes(up) - (rise[0] * 60 + rise[1])) <= 2
    assert abs(minutes(down) - (sets[0] * 60 + sets[1])) <= 2


def test_the_position_is_read_from_spots_json_not_typed():
    from forecast.geometry import load

    spot = next(s for s in load()[0] if s.id == daylight.BREAK)
    assert daylight.position() == spot.position


def test_nights_are_sunset_to_sunrise_clipped_to_the_window():
    start = datetime(2026, 10, 1, 6, tzinfo=timezone.utc)      # night already running
    end = datetime(2026, 10, 3, 6, tzinfo=timezone.utc)
    got = daylight.nights(start, end)
    assert got[0][0] == "2026-10-01T06:00:00Z"                  # clipped at the start
    assert got[-1][1] == "2026-10-03T06:00:00Z"                 # and at the end
    assert len(got) == 3
    for a, b in got:
        assert a < b
