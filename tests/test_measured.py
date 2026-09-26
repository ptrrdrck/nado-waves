"""The observed chain rebuilt for past hours: only what existed at that hour."""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from forecast import live, measured, now
from forecast.transform import load_spectra

ISO = "%Y-%m-%dT%H:%M:%SZ"
DATA = Path(__file__).resolve().parent.parent / "data"
T = datetime(2026, 9, 20, 9, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def spectra():
    got = load_spectra(DATA / "spectra" / "46232")
    if not any(s.time == T for s in got):
        pytest.skip("archive does not hold the test hour")
    return got


class TestMarks:
    def test_every_third_utc_hour_back_48(self):
        got = measured.marks(datetime(2026, 9, 26, 16, 30, tzinfo=timezone.utc))
        assert got[-1] == datetime(2026, 9, 26, 15, tzinfo=timezone.utc)
        assert all(t.hour % 3 == 0 and t.minute == 0 for t in got)
        assert len(got) == 16
        assert got[-1] - got[0] <= timedelta(hours=48)


class TestOnlyWhatExistedAtThatHour:
    def test_the_exact_stamp_or_a_gap_never_a_neighbour(self, spectra):
        neighbours = [s for s in spectra if abs(s.time - T) == timedelta(hours=1)]
        assert len(neighbours) == 2
        rebuild = measured.Rebuilder(DATA, spectra=neighbours)
        got = rebuild.at(T)
        assert got["gap"] is True and "stamped at this hour" in got["why"]

    def test_an_hour_newer_than_the_archive_is_pending_not_a_gap(self, spectra):
        older = [s for s in spectra if s.time < T]
        got = measured.Rebuilder(DATA, spectra=older).at(T)
        assert got["gap"] is False and got["pending"] is True

    def test_a_present_hour_carries_every_break_and_the_buoy(self, spectra):
        got = measured.Rebuilder(DATA, spectra=spectra).at(T)
        assert got["gap"] is False
        assert set(got["breaks"]) == {"coronado_north", "coronado_center", "coronado_south"}
        assert got["buoy"]["hs_m"] > 0

    def test_the_tide_and_wind_are_not_from_after_the_hour(self):
        tide = now.read_measured_tide(DATA, now=T, until=T)
        wind = live.read_latest_wind(DATA, until=T)
        assert tide.observed_utc <= T.strftime(ISO)
        assert wind["observed_utc"] <= T.strftime(ISO)
        # And the control: unbounded, both find something later.
        assert now.read_measured_tide(DATA, now=T).observed_utc > T.strftime(ISO)
        assert live.read_latest_wind(DATA)["observed_utc"] > T.strftime(ISO)

    def test_a_wind_reading_hours_old_is_not_the_wind_then(self, spectra, tmp_path):
        (tmp_path / "wind").mkdir()
        with (tmp_path / "wind" / "KNZY.csv").open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["observed_utc", "first_seen_utc", "wind_from_deg", "wind_kt",
                        "gust_kt", "variable", "raw"])
            w.writerow([(T - timedelta(hours=5)).strftime(ISO), "", "290", "12", "", "", ""])
        spectrum = next(s for s in spectra if s.time == T)
        reading = now.build(data_dir=tmp_path, now=T, spectrum=spectrum, as_of=True)
        assert not reading.wind.measured
        live_like = now.build(data_dir=tmp_path, now=T, spectrum=spectrum)
        assert live_like.wind.measured


class TestTheFile:
    def test_it_says_what_it_is_standing_on_and_what_it_is_not(self, spectra):
        got = measured.build(data_dir=DATA, now=T + timedelta(minutes=30), spectra=spectra)
        assert "checks nothing at the beach" in got["standing_on"]["claim"]
        assert got["steps"][-1]["valid_utc"] == T.strftime(ISO)
        assert all(s["valid_utc"] <= T.strftime(ISO) for s in got["steps"])
