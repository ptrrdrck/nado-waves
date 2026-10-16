"""The LIVE briefing's payload: each story from the files the collection
wrote, each judging word on its measured threshold (docs/briefing_thresholds.md)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from forecast import briefing as bf

T0 = datetime(2026, 10, 9, 2, tzinfo=timezone.utc)
ISO = "%Y-%m-%dT%H:%M:%SZ"


def _series(levels: dict[str, list[float]], start=T0, gaps=()):
    n = len(next(iter(levels.values())))
    steps = []
    for k in range(n):
        t = start + timedelta(hours=k)
        if k in gaps:
            steps.append({"valid_utc": t.strftime(ISO), "gap": True})
            continue
        steps.append({"valid_utc": t.strftime(ISO), "gap": False,
                      "breaks": {bid: {"hs_m": levels[bid][k]} for bid in bf.BREAKS}})
    return {"steps": steps}


def _now(newest, breaks=None):
    return {"observed_utc": newest.strftime(ISO), "stale": False,
            "breaks": breaks or [{"id": bid, "shore_normal_deg": n, "nearshore": {"trains": []}}
                                 for bid, n in zip(bf.BREAKS, (194.1, 213.9, 220.9))]}


def _flat(v, n=13):
    return [v] * n


def test_a_rise_past_the_threshold_is_said_and_one_under_it_is_little_change():
    up = [1.0] * 3 + [1.0 + 0.05 * k for k in range(1, 11)]       # +50% by the end
    small = [1.0] * 3 + [1.0 + 0.01 * k for k in range(1, 11)]    # +10%
    s = _series({"coronado_north": up, "coronado_center": small, "coronado_south": _flat(1.0)})
    got = bf.since_sunset(_now(T0 + timedelta(hours=12)), s, T0 - timedelta(minutes=20),
                          Path("."), trains_then={})
    change = {r["id"]: r["change"] for r in got["breaks"]}
    assert change == {"coronado_north": "rose", "coronado_center": "little",
                      "coronado_south": "little"}
    assert got["measured"] and got["span_h"] == pytest.approx(12.3, abs=0.1)


def test_a_short_night_gives_the_readings_and_no_word():
    s = _series({bid: [1.0, 1.0, 2.0, 2.0] for bid in bf.BREAKS})
    got = bf.since_sunset(_now(T0 + timedelta(hours=3)), s, T0, Path("."), trains_then={})
    assert not got["measured"]
    assert all(r["change"] is None for r in got["breaks"])


def test_the_leader_needs_its_margin():
    s = _series({"coronado_north": _flat(1.10), "coronado_center": _flat(1.0),
                 "coronado_south": _flat(1.03)})
    got = bf.since_sunset(_now(T0 + timedelta(hours=12)), s, T0, Path("."), trains_then={})
    assert got["lead_now"] == "coronado_north"
    s = _series({"coronado_north": _flat(1.03), "coronado_center": _flat(1.0),
                 "coronado_south": _flat(1.0)})
    got = bf.since_sunset(_now(T0 + timedelta(hours=12)), s, T0, Path("."), trains_then={})
    assert got["lead_now"] is None


def test_dark_or_missing_newest_hour_stands_the_story_down():
    s = _series({bid: _flat(1.0) for bid in bf.BREAKS}, gaps={12})
    assert bf.since_sunset(_now(T0 + timedelta(hours=12)), s, T0, Path("."), trains_then={}) is None
    stale = _now(T0 + timedelta(hours=11)) | {"stale": True}
    assert bf.since_sunset(stale, s, T0, Path("."), trains_then={}) is None


def test_gaps_since_sunset_are_named_as_runs():
    s = _series({bid: _flat(1.0) for bid in bf.BREAKS}, gaps={3, 4, 5, 9})
    got = bf.standing_on(_now(T0 + timedelta(hours=12)), None, s, T0, T0 + timedelta(hours=12))
    assert got["gaps"] == [
        {"from_utc": (T0 + timedelta(hours=3)).strftime(ISO), "to_utc": (T0 + timedelta(hours=5)).strftime(ISO)},
        {"from_utc": (T0 + timedelta(hours=9)).strftime(ISO), "to_utc": (T0 + timedelta(hours=9)).strftime(ISO)}]


def test_lateness_is_left_to_the_readers_clock():
    now = _now(T0) | {"overdue_after": {"swell": "2026-10-09T03:00:00Z"}}
    feed = bf.standing_on(now, None, None, T0, T0)["feeds"][0]
    assert feed["overdue_after_utc"] == "2026-10-09T03:00:00Z" and "overdue" not in feed


def test_the_biggest_step_is_the_tables_own_row():
    effects = {"buoy_hs_m": 1.0, "window_hs_m": 0.6, "refracted_hs_m": 0.66,
               "diffracted_hs_m": 0.66, "friction_hs_m": 0.62, "shoaled_hs_m": 0.70,
               "with_chop_hs_m": 0.70}
    assert bf.biggest_step(effects, 0.84) == {"step": "windows", "change_pct": -40}
    effects["window_hs_m"] = 0.95
    effects["refracted_hs_m"] = 0.70
    assert bf.biggest_step(effects, 0.84)["step"] == "refraction"


def test_a_train_differs_at_the_pages_own_precision():
    a = {"period_s": 14.3, "from_deg": 244}
    assert not bf._differs(a, {"period_s": 14.4, "from_deg": 248})
    assert bf._differs(a, {"period_s": 16.7, "from_deg": 244})
    assert bf._differs(a, {"period_s": 14.3, "from_deg": 290})


def test_the_wind_counts_match_the_cards_verdict():
    assert bf._sense(0.9, 0.0) == "calm"
    assert bf._sense(0.9, 3.0) == "light"
    assert bf._sense(None, 6.0) == "variable"
    assert bf._sense(0.9, 6.0) == "offshore"
    assert bf._sense(-0.9, 6.0) == "onshore"
    assert bf._sense(0.0, 6.0) == "cross-shore"


def test_sunset_is_the_last_one_before_the_reading():
    morning = datetime(2026, 10, 9, 14, tzinfo=timezone.utc)      # 7 AM Pacific
    evening = datetime(2026, 10, 9, 4, tzinfo=timezone.utc)       # 9 PM Pacific, Oct 8
    for at in (morning, evening):
        s = bf.last_sunset(at)
        assert s <= at and at - s < timedelta(hours=24)
        local_h = (s - timedelta(hours=7)).hour
        assert 17 <= local_h <= 19


def test_tanner_banks_north_west_rise_on_the_night_of_8_october():
    """On the archive: 46047's north-west sector rose overnight 8–9 October,
    14–17 s first, due at 46232 by deep-water speed and at every break."""

    since = datetime(2026, 10, 9, 1, 24, tzinfo=timezone.utc)
    at = datetime(2026, 10, 9, 14, 30, tzinfo=timezone.utc)
    got = bf.upstream_story(Path("data"), {"buoys": [{"station": "46047", "stale": False}]}, since, at)
    nw = next(g for g in got if g["sector"] == "north-west")
    first = nw["bands"][0]
    assert first["band_s"] == [14.0, 17.0]
    assert first["since_utc"] < nw["bands"][-1]["since_utc"] or len(nw["bands"]) == 1
    due = datetime.strptime(first["due_buoy_utc"], ISO).replace(tzinfo=timezone.utc)
    rose = datetime.strptime(first["since_utc"], ISO).replace(tzinfo=timezone.utc)
    assert (due - rose).total_seconds() / 3600 == pytest.approx(first["lag_h"], abs=0.05)
    assert {l["id"] for l in first["legs"]} == set(bf.BREAKS)


def test_a_stale_tanner_banks_says_nothing_upstream():
    assert bf.upstream_story(Path("data"), {"buoys": [{"station": "46047", "stale": True}]},
                             T0, T0 + timedelta(hours=12)) == []


def test_nothing_after_the_moment_is_read_upstream():
    since = datetime(2026, 10, 9, 1, 24, tzinfo=timezone.utc)
    before = bf.upstream_story(Path("data"), {"buoys": [{"station": "46047", "stale": False}]},
                               since, since + timedelta(minutes=30))
    assert before == []


def test_no_observed_reading_is_said_as_such(tmp_path):
    got = bf.build(data_dir=tmp_path, at=T0)
    assert got == {"generated_utc": T0.strftime(ISO), "available": False,
                   "why": "no observed reading was built this collection"}


def test_the_briefing_never_reads_the_model():
    """GFS-Wave and its ensemble are the Forecast tab's (owner's call,
    2026-10-16)."""

    src = Path(bf.__file__).read_text(encoding="utf-8")
    code = src.split('"""', 2)[2]
    for word in ("forecast.json", "gfswave", "wavespec", "gefswave", "ensemble", "forecast.live import build"):
        assert word not in code, word


def test_the_sun_story_carries_last_night_today_and_tomorrow():
    """now.json's sun block starts today; a morning read needs last night's."""

    at = datetime(2026, 10, 16, 14, 30, tzinfo=timezone.utc)       # 7:30 AM Pacific
    got = bf.sun_story(at)
    assert list(got["days"]) == ["2026-10-15", "2026-10-16", "2026-10-17"]
    assert set(got["seasons"]) == set(bf.BREAKS)
    last = got["days"]["2026-10-15"]
    assert datetime.strptime(last["sunset_utc"], ISO).replace(tzinfo=timezone.utc) < at
