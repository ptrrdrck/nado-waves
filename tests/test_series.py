"""The hourly observed series under each Now card: gaps stay gaps, and the
oscillator is only defined where there is enough of a day to define it."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from forecast import measured, series
from forecast.transform import load_spectra

ISO = "%Y-%m-%dT%H:%M:%SZ"
DATA = Path(__file__).resolve().parent.parent / "data"
T = datetime(2026, 9, 20, 9, tzinfo=timezone.utc)


def entry(valid: datetime, *, buoy=1.2, north=1.0, south=0.9, basis="breaking",
          window=0.8) -> dict:
    """A `measured.entry`-shaped hour, without running the chain."""

    def brk(hs):
        return {"hs_m": hs, "hs_basis": basis, "depth_m": 1.8, "hs_5m_m": hs,
                "hs_window_m": window, "period_s": 14.0, "from_deg": 205}

    return {"valid_utc": valid.strftime(ISO), "gap": False,
            "buoy": {"hs_m": buoy, "hs_basis": "buoy", "period_s": 14.0, "from_deg": 205},
            "breaks": {"coronado_north": brk(north), "coronado_center": brk(1.0),
                       "coronado_south": brk(south)},
            "tide_m": 1.0, "wind_kt": 5.0, "wind_from_deg": 290}


class TestTheOscillator:
    def test_position_in_the_trailing_range(self):
        values = [float(v) for v in range(24)]
        k = series.pct_k(values)
        assert k[:23] == [None] * 23          # not a whole window yet
        assert k[23] == 100.0                 # the top of its own range
        assert series.pct_k(values[::-1])[23] == 0.0

    def test_too_few_readings_is_undefined_not_filled(self):
        values = [float(v) for v in range(24)]
        for i in range(0, 5):
            values[i] = None                  # 19 of 24 present
        assert series.pct_k(values)[23] is None
        values[4] = 4.0                       # 20 of 24: enough
        assert series.pct_k(values)[23] == 100.0

    def test_the_current_hour_missing_is_undefined(self):
        values = [float(v) for v in range(24)] + [None]
        assert series.pct_k(values)[24] is None

    def test_a_flat_range_is_undefined_not_zero(self):
        assert series.pct_k([1.0] * 24)[23] is None
        assert series.pct_k([1.0] * 23 + [1.019])[23] is None
        assert series.pct_k([1.0] * 23 + [1.03])[23] == 100.0

    def test_the_mean_needs_every_hour_of_it(self):
        assert series.pct_d([10.0, 20.0, 30.0]) == [None, None, 20.0]
        assert series.pct_d([10.0, None, 30.0, 40.0]) == [None, None, None, None]


class TestAnHourOnTheChart:
    def test_a_gap_carries_no_value(self):
        got = series.slim({"valid_utc": "2026-09-20T09:00:00Z", "gap": True, "why": "x"})
        assert got == {"valid_utc": "2026-09-20T09:00:00Z", "gap": True}

    def test_pending_is_not_a_gap(self):
        got = series.slim({"valid_utc": "2026-09-20T09:00:00Z", "gap": False, "pending": True})
        assert got["gap"] is False and got["pending"] is True

    def test_only_a_breaking_height_is_drawn(self):
        """A headline at 5 m (no tide) is another quantity; a line that
        switched to it mid-way would draw a step nothing caused."""

        got = series.slim(entry(T, basis="5m"))
        assert all(b["hs_m"] is None for b in got["breaks"].values())
        assert got["south_minus_north_m"] is None

    def test_the_differential_is_south_less_north(self):
        got = series.slim(entry(T, north=1.1, south=0.8))
        assert got["south_minus_north_m"] == pytest.approx(-0.3)

    def test_transmission_is_the_window_over_the_buoy(self):
        got = series.slim(entry(T, buoy=1.25, window=1.0))
        assert got["breaks"]["coronado_north"]["transmission"] == 0.8


class TestTheFile:
    def test_the_hours_are_consecutive_and_end_now(self):
        got = series.hours_until(datetime(2026, 9, 27, 7, 40, tzinfo=timezone.utc), 5)
        assert got[-1] == datetime(2026, 9, 27, 7, tzinfo=timezone.utc)
        assert all(b - a == timedelta(hours=1) for a, b in zip(got, got[1:]))

    def test_warm_up_hours_are_dropped_but_define_the_first_percent_k(self):
        hours = series.hours_until(T, 4 + series.WARMUP_HOURS)
        entries = {t: entry(t, buoy=1.0 + 0.01 * i) for i, t in enumerate(hours)}
        got = series.build(entries, now=T, hours=4)
        assert len(got["steps"]) == 4
        assert got["steps"][0]["buoy"]["pct_k"] == 100.0
        assert got["steps"][0]["buoy"]["pct_d"] == 100.0

    def test_a_gap_inside_the_week_stays_a_gap(self):
        hours = series.hours_until(T, 30 + series.WARMUP_HOURS)
        entries = {t: entry(t, buoy=1.0 + 0.01 * i) for i, t in enumerate(hours)}
        hole = hours[-10]
        entries[hole] = {"valid_utc": hole.strftime(ISO), "gap": True, "why": "none"}
        got = series.build(entries, now=T, hours=30)
        steps = {s["valid_utc"]: s for s in got["steps"]}
        assert steps[hole.strftime(ISO)] == {"valid_utc": hole.strftime(ISO), "gap": True}
        after = steps[(hole + timedelta(hours=1)).strftime(ISO)]
        assert after["buoy"]["pct_k"] is not None       # 23 of 24 is enough
        assert after["buoy"]["pct_d"] is None           # but the mean spans the hole

    def test_it_says_it_is_rebuilt_and_checks_nothing_at_the_beach(self):
        got = series.build({T: entry(T)}, now=T, hours=1)
        assert got["rebuilt_with"] == "the current chain"
        assert "checks nothing at the beach" in got["standing_on"]["claim"]
        assert "never filled" in got["standing_on"]["waves"]


@pytest.fixture(scope="module")
def spectra():
    got = load_spectra(DATA / "spectra" / "46232")
    if not any(s.time == T for s in got):
        pytest.skip("archive does not hold the test hour")
    return got


class TestOneRebuildFeedsBothFiles:
    def test_measured_takes_its_hours_from_the_series(self, spectra):
        around = [s for s in spectra if T - timedelta(hours=40) <= s.time <= T]
        rebuild = measured.Rebuilder(DATA, spectra=around)
        hourly = series.hourly(rebuild, T + timedelta(minutes=30), hours=6)
        got = measured.build(data_dir=DATA, now=T + timedelta(minutes=30),
                             rebuild=rebuild, entries=hourly)
        fresh = measured.build(data_dir=DATA, now=T + timedelta(minutes=30), spectra=around)
        assert got["steps"] == fresh["steps"]
        shared = [s for s in got["steps"] if s["valid_utc"] >= min(hourly).strftime(ISO)]
        assert shared and all(s is hourly[datetime.strptime(s["valid_utc"], ISO)
                                          .replace(tzinfo=timezone.utc)] for s in shared)

    def test_the_real_window_ratio_never_exceeds_the_buoy(self, spectra):
        around = [s for s in spectra if T - timedelta(hours=30) <= s.time <= T]
        rebuild = measured.Rebuilder(DATA, spectra=around)
        got = series.build(series.hourly(rebuild, T, hours=4), now=T, hours=4)
        ratios = [b["transmission"] for s in got["steps"] if not s["gap"]
                  for b in s["breaks"].values()]
        assert ratios and all(0 <= r <= 1 for r in ratios)
