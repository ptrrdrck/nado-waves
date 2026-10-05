"""A swell's origin off the live spectrum: what it reads, and what it refuses.

The numbers behind the constants are BRIEFING §37; these pin the behaviour
those measurements chose, on synthetic arrivals whose answer is known.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from forecast import origin
from forecast.dispersion import GRAVITY
from forecast.origin import (
    BEARING_STATIONS,
    PLAUSIBLE_KM,
    Point,
    Ridge,
    arrivals,
    match,
    maxima,
    reading,
    ridge_bearing,
    ridges,
)
from forecast.transform import Spectrum

UTC = timezone.utc
START = datetime(2026, 9, 20, tzinfo=UTC)
#: 46232's own bins below 0.1 Hz, and coarser above, as the buoy reports them.
FREQS = [round(0.025 + 0.005 * k, 3) for k in range(16)] + [0.11, 0.12, 0.13, 0.14, 0.15]


def slope_hz_per_hour(distance_km: float) -> float:
    return GRAVITY / (4 * math.pi * distance_km * 1000.0) * 3600.0


def spectrum(time: datetime, peaks: list[tuple[float, float]], *, from_deg: float = 200.0) -> Spectrum:
    """A spectrum carrying one Gaussian bump per (frequency, height in m²/Hz)."""

    c11 = [0.002 + sum(h * math.exp(-((f - fp) / 0.006) ** 2) for fp, h in peaks) for f in FREQS]
    n = len(FREQS)
    return Spectrum(time=time, frequencies=FREQS, c11=c11, a1=[from_deg] * n,
                    a2=[from_deg] * n, r1=[0.8] * n, r2=[0.5] * n)


def arrival_series(distance_km: float, hours: int, *, lead_s: float = 20.0,
                   start: datetime = START, skip: set[int] = frozenset(),
                   from_deg: float = 200.0, height: float = 0.3) -> list[Spectrum]:
    """A textbook dispersive arrival from a known distance, one spectrum an hour."""

    slope = slope_hz_per_hour(distance_km)
    return [
        spectrum(start + timedelta(hours=h), [(1.0 / lead_s + slope * h, height)], from_deg=from_deg)
        for h in range(hours) if h not in skip
    ]


class TestReadingARidge:
    def test_a_known_distance_comes_back(self):
        """The refined maxima put the line where the synthetic storm is."""

        for distance in (3000.0, 9000.0):
            spectra = arrival_series(distance, 40)
            found = arrivals(spectra)
            assert len(found) == 1
            assert found[0].fit.distance_km == pytest.approx(distance, rel=0.08)

    def test_the_birth_time_is_where_the_line_reaches_zero(self):
        spectra = arrival_series(6000.0, 40)
        got = arrivals(spectra)[0]
        slope = slope_hz_per_hour(6000.0)
        born = START - timedelta(hours=(1.0 / 20.0) / slope)
        assert abs((got.fit.generated_utc - born).total_seconds()) < 6 * 3600

    def test_the_maximum_is_refined_between_bins(self):
        """At 0.005 Hz bins a 9,000 km storm moves one bin in ~15 hours; read
        bin to bin the slope would be mostly staircase."""

        point = maxima(spectrum(START, [(0.0612, 0.3)]))[0]
        assert point.freq_hz == pytest.approx(0.0612, abs=0.0008)
        assert point.freq_hz not in FREQS

    def test_a_missing_hour_is_a_gap_not_a_point(self):
        """Up to `MAX_GAP_H` missing hours, the ridge carries on with one point
        fewer; nothing is put in the hole."""

        spectra = arrival_series(5000.0, 30, skip={10, 11})
        found = arrivals(spectra)
        assert len(found) == 1
        times = {p.time for p in found[0].ridge.points}
        assert START + timedelta(hours=10) not in times
        assert len(found[0].ridge.points) == 28

    def test_a_longer_silence_ends_the_ridge(self):
        spectra = arrival_series(5000.0, 30, skip=set(range(10, 15)))
        assert all(len(r.points) <= 20 for r in ridges(spectra))

    def test_a_steady_swell_is_not_an_arrival(self):
        """No dispersion, no line: a train that holds its period has no
        distance to read."""

        spectra = [spectrum(START + timedelta(hours=h), [(0.065, 0.3)]) for h in range(40)]
        assert arrivals(spectra) == []

    def test_wind_sea_has_no_origin(self):
        """A ridge that starts below `MIN_LEAD_PERIOD_S` is not read."""

        assert arrivals(arrival_series(2000.0, 30, lead_s=11.0)) == []

    def test_the_antipode_bounds_the_distance(self):
        assert PLAUSIBLE_KM[1] <= 20015.0


class TestTheBearing:
    def test_46232_is_never_a_bearing_buoy(self):
        """Measured (BRIEFING §37-38): its mean reads a north-west swell 50-74°
        too far south -- half the average of two lobes, half a westerly lobe
        that pins near 270° whatever 46047 reads."""

        assert "46232" not in BEARING_STATIONS
        assert BEARING_STATIONS[0] == "46047"

    def test_46086_is_not_a_bearing_buoy(self):
        """Owner's decision 2026-10-05 (§38): its north-west lobe stays near
        279° whatever 46047 reads, so it carries no reading of where a
        north-west swell came from. It stays in the hurricane gate."""

        from forecast.stormtrack import GATE_STATIONS

        assert BEARING_STATIONS == ("46047",)
        assert "46086" in GATE_STATIONS

    @staticmethod
    def witness(here, r1, r2, a1, a2):
        """46047's spectra over the same hours: the same energy, given moments."""

        out = []
        for s in here:
            n = len(s.frequencies)
            out.append(Spectrum(time=s.time, frequencies=s.frequencies, c11=list(s.c11),
                                a1=[a1] * n, a2=[a2] * n, r1=[r1] * n, r2=[r2] * n))
        return out

    def test_a_split_sea_at_the_bearing_buoy_withholds_the_place(self):
        """Two directions holding ~44% each: the mean (240°) sits where
        neither is, and which one is the ridge's is not known (§38)."""

        here = arrival_series(5000.0, 30)
        split = self.witness(here, 0.45, 0.45, 240.0, 150.0)
        got = arrivals(here, {"46232": here, "46047": split}, (32.517, -117.425))[0]
        assert got.bearing_deg is None and got.origin is None
        assert got.bearing_from == "46047"
        assert sorted(round(h, -1) for h, _ in got.bearing_lobes) == [180.0, 300.0]
        assert all(share >= origin.SPLIT_SHARE for _, share in got.bearing_lobes)

    def test_one_direction_at_the_bearing_buoy_keeps_the_place(self):
        here = arrival_series(5000.0, 30)
        one = self.witness(here, 0.8, 0.5, 200.0, 200.0)
        got = arrivals(here, {"46232": here, "46047": one}, (32.517, -117.425))[0]
        assert got.bearing_deg == pytest.approx(200.0, abs=0.5)
        assert got.origin is not None and got.bearing_lobes == []

    def test_the_most_exposed_buoy_that_has_the_train_is_read(self):
        here = arrival_series(5000.0, 30, from_deg=230.0)
        exposed = arrival_series(5000.0, 30, from_deg=300.0)
        ridge = ridges(here)[0]
        got = ridge_bearing(ridge, {"46232": here, "46047": exposed})
        assert got is not None and got[1] == "46047"
        assert got[0] == pytest.approx(300.0, abs=0.5)

    def test_without_an_unshadowed_buoy_there_is_no_place(self):
        here = arrival_series(5000.0, 30)
        found = arrivals(here, {"46232": here}, (32.517, -117.425))
        assert len(found) == 1
        assert found[0].bearing_deg is None and found[0].origin is None
        assert found[0].fit.distance_km > 0

    def test_a_buoy_without_the_train_is_passed_over(self):
        here = arrival_series(5000.0, 30)
        empty = [spectrum(s.time, []) for s in here]
        ridge = ridges(here)[0]
        assert ridge_bearing(ridge, {"46047": empty, "46086": empty}) is None


class TestWhichBreakShowsIt:
    def ridge_at(self, freq: float) -> origin.Arrival:
        ridge = Ridge([Point(START, freq, 0.3, 200.0)])
        return origin.Arrival(ridge=ridge, fit=None)

    def test_a_card_train_within_one_and_a_half_bins_is_this_train(self):
        a = self.ridge_at(1 / 15.0)
        assert match(a, [{"period_s": 15.4}, {"period_s": 8.0}]) == 15.4
        assert match(a, [{"period_s": 12.5}]) is None

    def test_a_past_hour_is_matched_at_its_own_frequency(self):
        ridge = Ridge([Point(START, 1 / 16.0, 0.3, 200.0), Point(START, 1 / 11.0, 0.3, 200.0)])
        a = origin.Arrival(ridge=ridge, fit=None)
        assert match(a, [{"period_s": 16.0}]) is None
        assert match(a, [{"period_s": 16.0}], ridge.points[0]) == 16.0


class TestTheBlock:
    def build(self, *, newest_after_h: float):
        spectra = arrival_series(5000.0, 30)
        exposed = arrival_series(5000.0, 30, from_deg=290.0)
        newest = START + timedelta(hours=newest_after_h)
        latest = 1.0 / max(p.freq_hz for p in ridges(spectra)[0].points)
        asked = []

        at = {p.time: p for p in ridges(spectra)[0].points}

        def trains_at(moment):
            asked.append(moment)
            return {"coronado_north": [{"period_s": 1 / at[moment].freq_hz}],
                    "coronado_south": [], "buoy": []}

        block = reading(spectra, {"46232": spectra, "46047": exposed}, (32.517, -117.425),
                        newest=newest,
                        trains_now={"coronado_north": [{"period_s": latest}],
                                    "coronado_south": [{"period_s": 7.0}], "buoy": []},
                        trains_at=trains_at)
        return block, asked

    def test_a_running_arrival_shows_where_it_is_a_train(self):
        block, _ = self.build(newest_after_h=29)
        assert len(block["arrivals"]) == 1 and block["arrivals"][0]["running"]
        assert block["sites"]["coronado_north"]["current"][0]["arrival"] == 0
        assert block["sites"]["coronado_south"]["current"] == []
        assert block["arrivals"][0]["region"] and block["arrivals"][0]["bearing_from"] == "46047"

    def test_a_finished_one_is_the_last_readable_arrival_where_it_was_a_train(self):
        block, asked = self.build(newest_after_h=60)
        assert not block["arrivals"][0]["running"]
        north, south = block["sites"]["coronado_north"], block["sites"]["coronado_south"]
        assert north["current"] == [] and north["last"] == 0
        assert south["last"] is None
        assert len(asked) == 1

    def test_an_arrival_older_than_the_lookback_is_dropped(self):
        block, _ = self.build(newest_after_h=24 * (origin.LOOKBACK_DAYS + 3))
        assert block["arrivals"] == []

    def test_distances_are_kept_whole_and_rounded_only_for_display(self):
        from forecast.units import distance

        block, _ = self.build(newest_after_h=29)
        km = block["arrivals"][0]["distance_km"]
        assert isinstance(km, int)
        assert distance(km).startswith("about ") and distance(km).endswith("00 km)")
        assert distance(8700) == "about 5,500 mi (8,500 km)"
        assert distance(100) == "about 500 mi (500 km)"


def test_a_failing_origin_never_costs_the_reading(monkeypatch, tmp_path):
    """The swell, wind and tide on the LIVE tab do not depend on Origin."""

    from forecast import now

    def broken(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(now, "origin_reading", broken)
    s = spectrum(START, [(0.065, 0.3)])
    got = now.build(data_dir=tmp_path, now=START + timedelta(minutes=30), spectrum=s)
    assert got.breaks and got.origin == {}
    assert any("no origin reading: RuntimeError" in w for w in got.warnings)
