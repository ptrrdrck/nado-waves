"""The Tide card's phase fold (`forecast.tidephase`, BRIEFING §41).

The constants are NOAA's, fetched (`collector.harcon`); the thresholds are
re-measured here over the same 19 years `forecast.tidephasereport` reads
them off (~10 s), so a threshold edited without its measurement fails.
"""

import csv
import json
import statistics
from datetime import date, datetime, timedelta, timezone

import pytest

from forecast import tidephase as tp
from forecast import tidephasereport as report
from forecast.tidesite import anomaly, coast_turn
from forecast.tideturns import Turn

UTC = timezone.utc


@pytest.fixture(scope="module")
def c():
    got = tp.load()
    assert got is not None, "data/tide/9410170_harcon.json is missing: run collector.harcon on Actions"
    return got


@pytest.fixture(scope="module")
def measured(c):
    _, fig = report.measure(c, report.START, report.END)
    return fig


# ------------------------------------------------------------------ the constants

def test_the_station_is_mixed_mainly_twice_a_day(c):
    """Form factor 0.25-1.5 is mixed, mainly semidiurnal; San Diego's is 0.72."""

    assert tp.form_factor(c) == pytest.approx(0.718, abs=0.005)


def test_the_station_lags(c):
    """Springs ~3 h before new or full moon, the declination felt ~14 h
    late, perigee ~37 h."""

    assert tp.phase_age_h(c) == pytest.approx(-2.9, abs=0.3)
    assert tp.diurnal_age_h(c) == pytest.approx(14.4, abs=0.3)
    assert tp.parallax_age_h(c) == pytest.approx(37.1, abs=0.5)


def test_local_phases_are_not_greenwich_phases(c):
    """The trap: NOAA's `phase_local` is `phase_GMT` moved by speed × 8 h, so
    two constituents' local phases are not comparable. Read naively they put
    springs 11 h before new or full moon instead of 3 h."""

    stored = json.loads(tp.harcon_path().read_text())["response"]["HarmonicConstituents"]
    for row in stored:
        if row["amplitude"] == 0:
            continue
        moved = (row["phase_local"] + 8 * row["speed"] - row["phase_GMT"] + 180) % 360 - 180
        assert abs(moved) < 0.2, row["name"]
    m2 = next(r for r in stored if r["name"] == "M2")
    s2 = next(r for r in stored if r["name"] == "S2")
    naive = (s2["phase_local"] - m2["phase_local"]) / (s2["speed"] - m2["speed"])
    assert naive == pytest.approx(-10.8, abs=0.3)


def test_the_constants_reproduce_coops_own_prediction(c):
    """The hourly predictions CO-OPS publishes, and its high and low water,
    from the same constants here: 1.1 cm RMS, turns within minutes."""

    got = report.check_against_coops(c, tp.DEFAULT_DATA_DIR)
    assert got["rms_cm"] < 2.0
    assert got["turns"] == got["of"]
    assert got["turn_min_mean"] < 5 and got["turn_cm_max"] < 3


# ------------------------------------------------------------------ the thresholds

def test_the_phase_window_is_the_best_agreement(measured):
    assert measured["phase_best_h"] == tp.PHASE_WINDOW_H


def test_the_moon_slot_is_always_filled(measured):
    assert measured["moon_gap_max_h"] <= tp.MOON_WINDOW_H


@pytest.mark.parametrize("key,used,looser", [
    ("equator_by_deg", "DEC_EQUATOR_DEG", 5),
    ("far_by_deg", "DEC_FAR_DEG", 24),
    ("distance_by_h", "DISTANCE_WINDOW_H", 96),
    ("small_by_m", "SMALL_SWING_M", 0.25),
])
def test_each_threshold_is_the_loosest_that_is_right_often_enough(measured, key, used, looser):
    """Right on at least RIGHT_SHARE where it fires, and the next step
    looser on the measured grid is not."""

    value = getattr(tp, used)
    assert measured[key][value] >= tp.RIGHT_SHARE, (key, measured[key])
    assert measured[key][looser] < tp.RIGHT_SHARE, (key, measured[key])


def test_larger_or_smaller_is_said_only_past_the_margin(measured):
    by = measured["similar_by_share"]
    assert by[tp.SIMILAR_SHARE] >= tp.RIGHT_SHARE
    assert by[0.05] < tp.RIGHT_SHARE


def test_heading_away_or_toward_the_equator_says_which_way_tomorrow_goes(measured):
    assert measured["heading_right"] >= tp.RIGHT_SHARE


def test_the_declination_shows_in_the_lows_so_the_wording_says_tides(measured):
    """Why "the day's two tides" and never "the two highs": the lows carry
    more of the inequality here."""

    assert measured["lows_r"] > measured["highs_r"] + 0.1


def test_the_next_entrys_consequences_hold(measured):
    """"nearly vanishes" at a neap with the Moon far from the equator: a
    single-pair day or a tiny swing within two days, every time. And a spring
    with the Moon over the equator is the SMALLEST spring, so it is called
    big against the neaps and alike, never the biggest."""

    assert measured["vanish"][("neap", "far")] >= tp.RIGHT_SHARE
    sizes = measured["sizes"]
    springs = [v for (k, s), v in sizes.items() if k == "spring"]
    neaps = [v for (k, s), v in sizes.items() if k == "neap"]
    assert sizes[("spring", "equator")] == min(springs)
    assert sizes[("spring", "equator")] > max(neaps)
    assert sizes[("spring", "far")] == max(springs)


# ------------------------------------------------------------------ the summary

def _turns_seen(by):
    rows = {}
    for r in csv.DictReader((tp.DEFAULT_DATA_DIR / "tide" / "9410170_turns.csv").open()):
        if tp._parse(r["first_seen_utc"]) <= by:
            rows[r["time_utc"]] = r
    dep, _ = anomaly(tp.DEFAULT_DATA_DIR, by)
    return [coast_turn(Turn(k, float(r["height_m"]), r["event"]), dep).as_dict()
            for k, r in sorted(rows.items())]


def test_the_10_october_summary(c):
    at = datetime(2026, 10, 10, 19, tzinfo=UTC)
    block = tp.block(tp.DEFAULT_DATA_DIR, [date(2026, 10, 10)], _turns_seen(at), now=at)
    assert block["analysis"] == "2017–2021"
    s = block["days"]["2026-10-10"]
    assert s["phase"] == "spring"
    assert s["today"]["moon"]["name"] == "new moon"
    assert s["today"]["declination"]["state"] == "away"
    assert s["today"]["pair"]["event"] == "high"
    n = s["next"]
    assert n["kind"] == "neap" and n["utc"].startswith("2026-10-17")
    assert n["coincide"] == ["apogee", "maximum declination"]
    kinds = {(e["kind"], e["day"]) for e in n["evidence"]}
    assert ("small", "2026-10-15") in kinds and ("single", "2026-10-16") in kinds
    single = next(e for e in n["evidence"] if e["kind"] == "single")
    assert single["last_day"] == "2026-10-17"
    a = s["after"]
    assert (a["kind"], a["moon"]["name"], a["distance"]["name"], a["compare"]) == \
        ("spring", "full moon", "perigee", "larger")


def test_no_constants_no_fold(tmp_path):
    assert tp.load(tmp_path) is None
    assert tp.block(tmp_path, [date(2026, 10, 10)], []) is None


def _t(day, hour, h, ev):
    return {"valid_utc": datetime(2026, 11, day, hour, tzinfo=UTC).strftime(tp.ISO),
            "height_m": h, "event": ev}


def test_a_day_is_counted_only_when_the_turns_cover_it_whole():
    """Two turns on the LAST day the turns reach say nothing about that day."""

    turns = tp._turns([_t(10, 20, 1.8, "high"), _t(11, 3, 0.4, "low"),
                       _t(11, 20, 1.6, "high"), _t(12, 6, 0.9, "low"), _t(12, 20, 1.5, "high")])
    days = tp._complete_days(turns)
    assert date(2026, 11, 11) in days
    assert date(2026, 11, 12) not in days and date(2026, 11, 10) not in days


def test_the_pair_shown_is_the_one_that_differs_more():
    turns = tp._turns([_t(10, 2, 1.0, "low"), _t(10, 14, 1.9, "high"), _t(10, 20, 1.0, "low"),
                       _t(11, 3, 1.8, "high"), _t(11, 10, 0.2, "low"), _t(11, 16, 1.7, "high"),
                       _t(11, 22, 0.9, "low"), _t(12, 4, 1.8, "high"), _t(12, 12, 0.3, "low")])
    pair = tp.day_pair(turns, date(2026, 11, 11))
    assert pair == {"event": "low", "heights_m": [0.2, 0.9]}


def test_neap_evidence_reads_runs_of_single_days():
    turns = tp._turns([_t(9, 22, 1.4, "high"),
                       _t(10, 16, 0.6, "low"), _t(11, 4, 1.5, "high"),
                       _t(11, 17, 0.5, "low"), _t(12, 5, 1.4, "high"),
                       _t(12, 18, 0.5, "low"), _t(13, 2, 1.3, "high"), _t(13, 6, 1.2, "low"),
                       _t(13, 19, 1.6, "high"), _t(14, 3, 0.4, "low")])
    # Days are Pacific: 10 and 11 Nov each hold one high and one low, and
    # read as one run.
    ev = tp.neap_evidence(turns, datetime(2026, 11, 11, 20, tzinfo=UTC))
    assert {"kind": "single", "day": "2026-11-10", "last_day": "2026-11-11"} in ev
    assert any(e["kind"] == "small" and e["day"] == "2026-11-12" for e in ev)


def test_a_build_is_cheap(c):
    import time

    t = time.time()
    days = [date(2026, 10, 10) + timedelta(days=k) for k in range(9)]
    tp.block(tp.DEFAULT_DATA_DIR, days, [], now=datetime(2026, 10, 10, 19, tzinfo=UTC))
    assert time.time() - t < 5
