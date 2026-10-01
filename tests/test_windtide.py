"""forecast.windtide: the measured wind and tide each hour, for the Wind and
Tide cards' charts.

What matters is that a slot is a reading or a gap and nothing else: a METAR
lands in exactly one slot and is never carried into the next, the tide is the
sample at the hour and never the one six minutes later, and the one modelled
series -- the next day's tide -- is kept apart and carries the departure the
card's own turn heights carry.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from forecast import windtide
from forecast.tidesite import RATIO

NOW = datetime(2026, 9, 30, 17, 20, tzinfo=timezone.utc)
ISO = "%Y-%m-%dT%H:%M:%SZ"


def stamp(t: datetime) -> str:
    return t.strftime(ISO)


def write_wind(tmp_path, rows):
    wind = tmp_path / "wind"
    wind.mkdir(exist_ok=True)
    head = "observed_utc,first_seen_utc,wind_from_deg,wind_kt,gust_kt,variable,raw\n"
    (wind / "KNZY.csv").write_text(head + "".join(
        f"{stamp(t)},{stamp(t)},{d},{kt},{g},{v},METAR\n" for t, d, kt, g, v in rows))


def write_tide(tmp_path, observed, predicted=()):
    tide = tmp_path / "tide"
    tide.mkdir(exist_ok=True)
    head = "time_utc,first_seen_utc,height_m,kind,datum\n"
    (tide / "9410170_observed.csv").write_text(head + "".join(
        f"{stamp(t)},{stamp(t)},{h},observed,MLLW\n" for t, h in observed))
    (tide / "9410170_predicted.csv").write_text(head + "".join(
        f"{stamp(t)},{stamp(t)},{h},predicted,MLLW\n" for t, h in predicted))


HOUR = datetime(2026, 9, 30, 17, tzinfo=timezone.utc)


def at(got, hour):
    k = (hour - datetime.strptime(got["start_utc"], ISO).replace(tzinfo=timezone.utc)) // timedelta(hours=1)
    return k


class TestTheWind:
    def test_a_report_lands_in_the_hour_it_is_in_force_for(self, tmp_path):
        write_wind(tmp_path, [(HOUR - timedelta(hours=2, minutes=8), 280, 9, "", ""),
                              (HOUR - timedelta(minutes=8), 290, 11, 18, "")])
        write_tide(tmp_path, [])
        got = windtide.build(tmp_path, now=NOW)
        k = at(got, HOUR)
        assert got["wind"]["from_deg"][k] == 290 and got["wind"]["kt"][k] == 11
        assert got["wind"]["gust_kt"][k] == 18 and got["wind"]["age_min"][k] == 8

    def test_a_missed_report_is_a_gap_not_the_one_before(self, tmp_path):
        """measured.py carries a report for up to two hours; a chart must not,
        or the carried reading draws as a second measurement."""

        write_wind(tmp_path, [(HOUR - timedelta(hours=2, minutes=8), 280, 9, "", "")])
        write_tide(tmp_path, [])
        got = windtide.build(tmp_path, now=NOW)
        k = at(got, HOUR - timedelta(hours=2))          # 14:52 is 15:00's report
        assert got["wind"]["kt"][k] == 9
        assert got["wind"]["kt"][k + 1] is None and got["wind"]["from_deg"][k + 1] is None

    def test_a_later_report_in_the_same_hour_wins(self, tmp_path):
        write_wind(tmp_path, [(HOUR - timedelta(minutes=52), 200, 5, "", ""),
                              (HOUR - timedelta(minutes=8), 210, 7, "", "")])
        write_tide(tmp_path, [])
        got = windtide.build(tmp_path, now=NOW)
        assert got["wind"]["from_deg"][at(got, HOUR)] == 210

    def test_calm_and_variable_have_a_speed_and_no_direction(self, tmp_path):
        write_wind(tmp_path, [(HOUR - timedelta(hours=1, minutes=8), 0, 0, "", ""),
                              (HOUR - timedelta(minutes=8), 250, 3, "", "1")])
        write_tide(tmp_path, [])
        got = windtide.build(tmp_path, now=NOW)
        k = at(got, HOUR)
        assert (got["wind"]["kt"][k - 1], got["wind"]["from_deg"][k - 1]) == (0, None)
        assert (got["wind"]["kt"][k], got["wind"]["from_deg"][k]) == (3, None)


class TestTheTide:
    def test_the_sample_at_the_hour_carried_to_the_open_coast(self, tmp_path):
        write_wind(tmp_path, [])
        write_tide(tmp_path, [(HOUR - timedelta(hours=1), 1.5), (HOUR, 2.0)])
        got = windtide.build(tmp_path, now=NOW)
        k = at(got, HOUR)
        assert got["tide_m"][k] == pytest.approx(RATIO * 2.0, abs=1e-3)

    def test_never_the_sample_six_minutes_later(self, tmp_path):
        write_wind(tmp_path, [])
        write_tide(tmp_path, [(HOUR - timedelta(hours=1), 1.5),
                              (HOUR + timedelta(minutes=6), 2.0)])
        got = windtide.build(tmp_path, now=NOW)
        assert got["tide_m"][at(got, HOUR)] is None

    def test_it_starts_where_the_archives_do(self, tmp_path):
        """Before anything was collected is not a gap; it is not drawn at all."""

        write_wind(tmp_path, [])
        write_tide(tmp_path, [(HOUR - timedelta(hours=3), 1.0)])
        got = windtide.build(tmp_path, now=NOW)
        assert got["start_utc"] == stamp(HOUR - timedelta(hours=3))
        assert got["hours"] == 4 == len(got["tide_m"]) == len(got["wind"]["kt"])


class TestThePrediction:
    def test_the_next_day_carries_the_measured_departure(self, tmp_path):
        """As the card's turn heights do: bare, it sits under the measured line."""

        hours = [HOUR + timedelta(hours=h) for h in range(-72, 30)]
        write_wind(tmp_path, [])
        write_tide(tmp_path, [(t, 1.25) for t in hours if t <= HOUR],
                   predicted=[(t, 1.0) for t in hours])
        got = windtide.build(tmp_path, now=NOW)["prediction"]
        assert got["start_utc"] == stamp(HOUR)
        assert len(got["heights_m"]) == windtide.PREDICT_HOURS + 1
        assert all(h == pytest.approx(RATIO * 1.25, abs=1e-3) for h in got["heights_m"])
        assert got["departure_m"] == pytest.approx(RATIO * 0.25, abs=1e-3)

    def test_without_a_departure_it_is_the_bare_prediction(self, tmp_path):
        hours = [HOUR + timedelta(hours=h) for h in range(0, 30)]
        write_wind(tmp_path, [])
        write_tide(tmp_path, [], predicted=[(t, 1.0) for t in hours])
        got = windtide.build(tmp_path, now=NOW)["prediction"]
        assert got["departure_m"] is None
        assert got["heights_m"][0] == pytest.approx(RATIO * 1.0, abs=1e-3)

    def test_the_measured_and_the_modelled_are_kept_apart(self, tmp_path):
        write_wind(tmp_path, [])
        write_tide(tmp_path, [(HOUR, 2.0)], predicted=[(HOUR, 1.0)])
        got = windtide.build(tmp_path, now=NOW)
        assert "OBSERVED" in got["standing_on"]["tide"]
        assert "PREDICTED" in got["standing_on"]["prediction"]
        assert got["tide_m"][-1] == pytest.approx(RATIO * 2.0, abs=1e-3)


class TestTheDeparture:
    """The gauge's measured departure from its own harmonic prediction, each
    hour, and the trailing 3-day mean of it the forecast's tide carries --
    both scaled to the open coast as the card's correction is."""

    def test_each_hour_and_the_mean_the_forecast_would_have_added(self, tmp_path):
        hours = [HOUR + timedelta(hours=h) for h in range(-80, 1)]
        write_wind(tmp_path, [])
        write_tide(tmp_path, [(t, 1.0 + (0.4 if t >= HOUR - timedelta(hours=2) else 0.2))
                              for t in hours],
                   predicted=[(t, 1.0) for t in hours])
        got = windtide.build(tmp_path, now=NOW)
        assert got["departure_m"][-1] == pytest.approx(RATIO * 0.4, abs=1e-3)
        assert got["departure_m"][-4] == pytest.approx(RATIO * 0.2, abs=1e-3)
        # 73 hourly pairs in the 72 h up to and including the hour, 3 of them 0.4.
        assert got["departure_mean_m"][-1] == pytest.approx(RATIO * (70 * 0.2 + 3 * 0.4) / 73, abs=1e-3)
        # The newest mean is exactly what the forecast carries now.
        assert got["departure_mean_m"][-1] == got["prediction"]["departure_m"]

    def test_an_hour_without_its_sample_or_its_prediction_is_a_gap(self, tmp_path):
        write_wind(tmp_path, [])
        write_tide(tmp_path, [(HOUR - timedelta(hours=1), 1.2), (HOUR, 1.3)],
                   predicted=[(HOUR - timedelta(hours=1), 1.0)])
        got = windtide.build(tmp_path, now=NOW)
        assert got["departure_m"][-2] == pytest.approx(RATIO * 0.2, abs=1e-3)
        assert got["departure_m"][-1] is None
        assert got["departure_mean_m"][-1] == pytest.approx(RATIO * 0.2, abs=1e-3)
