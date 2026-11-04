"""The Tide card's measured rate on "LIVE" (forecast.tiderate, BRIEFING §50):
the gauge's last 30 minutes, slack under 0.10 m/h or across a predicted turn,
nothing at all across a gap."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from forecast import now as now_mod
from forecast import tiderate
from forecast.tidesite import RATIO

from test_now import MOMENT, spectrum, write_tide

ROOT = Path(__file__).resolve().parent.parent
NEWEST = datetime(2026, 9, 19, 0, 24, tzinfo=timezone.utc)


def series(per_hour_m: float, *, drop: int | None = None, newest: datetime = NEWEST):
    """Six gauge samples ending at `newest`, rising `per_hour_m` an hour."""
    out = {}
    for k in range(tiderate.SAMPLES):
        if k == drop:
            continue
        when = newest - timedelta(minutes=k * tiderate.STEP_MIN)
        out[when] = 1.0 - per_hour_m * k * tiderate.STEP_MIN / 60
    return out


class TestTheWindow:
    def test_six_samples_over_thirty_minutes(self):
        assert tiderate.SAMPLES == 6
        assert (tiderate.SAMPLES - 1) * tiderate.STEP_MIN == tiderate.WINDOW_MIN == 30

    def test_the_rate_is_the_gauges_slope_carried_to_the_coast(self):
        got = tiderate.reading(series(0.4), NEWEST, [])
        assert got["rate_m_h"] == pytest.approx(RATIO * 0.4, abs=1e-3)
        assert got["motion"] == tiderate.UP

    def test_falling_is_down(self):
        assert tiderate.reading(series(-0.4), NEWEST, [])["motion"] == tiderate.DOWN

    @pytest.mark.parametrize("drop", range(6))
    def test_a_missing_sample_is_no_rate_never_a_shorter_fit(self, drop):
        got = tiderate.reading(series(0.4, drop=drop), NEWEST, [])
        assert got["rate_m_h"] is None and got["motion"] is None
        assert "missing" in got["rate_note"]

    def test_a_least_squares_line_not_the_two_ends(self):
        """One wobble at the end must not decide it, as differencing would."""
        s = series(0.0)
        s[NEWEST] += 0.03
        got = tiderate.reading(s, NEWEST, [])
        assert abs(got["rate_m_h"]) < 0.06 * RATIO


class TestSlack:
    def test_the_threshold(self):
        assert tiderate.SLACK_M_H == 0.10       # 5 cm over the window: BRIEFING §50

    def test_under_the_threshold_is_slack_by_rate(self):
        got = tiderate.reading(series(0.09 / RATIO), NEWEST, [])
        assert (got["motion"], got["motion_why"]) == (tiderate.SLACK, tiderate.BY_RATE)

    def test_over_it_is_moving(self):
        assert tiderate.reading(series(0.11 / RATIO), NEWEST, [])["motion"] == tiderate.UP

    @pytest.mark.parametrize("minutes_back", [0, 12, 30])
    def test_a_turn_inside_the_window_is_slack_whatever_the_slope(self, minutes_back):
        turn = NEWEST - timedelta(minutes=minutes_back)
        got = tiderate.reading(series(-0.5), NEWEST, [turn])
        assert (got["motion"], got["motion_why"]) == (tiderate.SLACK, tiderate.BY_TURN)
        assert got["rate_m_h"] < 0               # the measured slope is still kept

    @pytest.mark.parametrize("minutes", [-31, 1])
    def test_a_turn_outside_it_is_not(self, minutes):
        turn = NEWEST + timedelta(minutes=minutes)
        assert tiderate.reading(series(-0.5), NEWEST, [turn])["motion"] == tiderate.DOWN


class TestOnTheCard:
    def test_now_json_carries_it(self, tmp_path):
        rows = [((NEWEST - timedelta(minutes=k * 6)).strftime(now_mod.ISO), f"{1.0 - 0.05 * k:.3f}")
                for k in range(8)]
        write_tide(tmp_path, rows)
        got = now_mod.build(data_dir=tmp_path, now=MOMENT, spectrum=spectrum(MOMENT))
        assert got.tide.motion == tiderate.UP
        assert got.tide.rate_m_h == pytest.approx(RATIO * 0.5, abs=1e-3)
        assert "last 30 minutes" in got.standing_on["tide"]
        assert got.standing_on["tide"].startswith("OBSERVED")

    def test_a_turn_from_the_card_makes_it_slack(self, tmp_path):
        rows = [((NEWEST - timedelta(minutes=k * 6)).strftime(now_mod.ISO), f"{1.0 - 0.05 * k:.3f}")
                for k in range(8)]
        write_tide(tmp_path, rows)
        # A bay turn LEAD_MIN later is the coast turn 10 min before the newest sample.
        from forecast.tidesite import LEAD_MIN
        bay = NEWEST - timedelta(minutes=10 - LEAD_MIN)
        path = tmp_path / "tide" / f"{now_mod.TIDE_STATION}_turns.csv"
        path.write_text("time_utc,first_seen_utc,height_m,kind,datum,event\n"
                        f"{bay.strftime(now_mod.ISO)},x,1.0,predicted,MLLW,high\n", encoding="utf-8")
        got = now_mod.build(data_dir=tmp_path, now=MOMENT, spectrum=spectrum(MOMENT))
        assert (got.tide.motion, got.tide.motion_why) == (tiderate.SLACK, tiderate.BY_TURN)

    def test_a_gap_says_so(self, tmp_path):
        rows = [((NEWEST - timedelta(minutes=k * 6)).strftime(now_mod.ISO), "1.0")
                for k in range(8) if k != 3]
        write_tide(tmp_path, rows)
        got = now_mod.build(data_dir=tmp_path, now=MOMENT, spectrum=spectrum(MOMENT))
        assert got.tide.height_m is not None and got.tide.motion is None


def test_the_archive_still_supports_the_threshold():
    """Re-measured on the archive (~1 s). The 5 cm threshold stands while the
    window's change agrees with the prediction's to under 3 cm rms, measured
    and predicted slack stay within 3 points, and outside the turn rule the
    slope runs against the turn the card names on under 0.1% of readings."""
    got = tiderate.measure(ROOT / "data")
    if got["n"] < 2000:
        pytest.skip("too little gauge archive")
    row = got["by_threshold"][5]
    assert got["scatter_cm"] < 3.0
    assert abs(row["slack_measured"] - row["slack_predicted"]) < 0.03
    assert row["against_after_turn_rule"] / got["n"] < 0.001
