"""The LIVE briefing: when an issue is written and how it is kept, and each
entry from the files the collection wrote, each judging word on its
measured threshold (docs/briefing_thresholds.md)."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from forecast import briefing as bf

T0 = datetime(2026, 10, 9, 2, tzinfo=timezone.utc)
ISO = "%Y-%m-%dT%H:%M:%SZ"
DAY = date(2026, 10, 16)


def _at(stamp: str) -> datetime:
    return datetime.strptime(stamp, ISO).replace(tzinfo=timezone.utc)


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


# ------------------------------------------------------------------ issues

def test_the_slots_are_six_and_noon_pacific_in_either_offset():
    assert bf.slot(DAY, "morning") == _at("2026-10-16T13:00:00Z")      # PDT
    assert bf.slot(DAY, "midday") == _at("2026-10-16T19:00:00Z")
    assert bf.slot(date(2026, 12, 1), "morning") == _at("2026-12-01T14:00:00Z")   # PST


def test_an_issue_is_due_from_its_slot_until_it_is_written_or_too_late():
    assert bf.due(_at("2026-10-16T12:59:00Z"), {}) is None           # yesterday's Midday, too late
    got = bf.due(_at("2026-10-16T13:04:00Z"), {})
    assert got[:2] == (DAY, "morning")
    assert bf.due(_at("2026-10-16T13:04:00Z"), {"2026-10-16-morning": {}}) is None
    late = _at("2026-10-16T13:00:00Z") + timedelta(hours=bf.MAX_LATE_H, minutes=1)
    assert bf.due(late, {}) is None
    assert bf.due(_at("2026-10-16T19:01:00Z"), {"2026-10-16-morning": {}})[:2] == (DAY, "midday")


def test_a_missed_morning_is_never_written_at_midday():
    """A gap is a gap: the newest slot is the only candidate."""
    got = bf.due(_at("2026-10-16T19:10:00Z"), {})
    assert got[1] == "midday"


def test_each_issue_follows_the_one_before():
    assert bf.previous_slot(DAY, "midday")[:2] == (DAY, "morning")
    assert bf.previous_slot(DAY, "morning")[:2] == (date(2026, 10, 15), "midday")


def test_the_record_is_append_only_and_idempotent(tmp_path):
    issue = {"key": "2026-10-16-morning", "day": "2026-10-16", "slot_utc": "2026-10-16T13:00:00Z",
             "edition": "morning", "available": True}
    assert bf.append(tmp_path, issue)
    assert not bf.append(tmp_path, dict(issue, edition="changed"))
    later = dict(issue, key="2026-10-16-midday", slot_utc="2026-10-16T19:00:00Z", edition="midday")
    assert bf.append(tmp_path, later)
    lines = (tmp_path / "briefings" / "2026-10.jsonl").read_text().splitlines()
    assert [json.loads(x)["key"] for x in lines] == ["2026-10-16-morning", "2026-10-16-midday"]
    assert json.loads(lines[0])["edition"] == "morning"
    assert bf.newest(tmp_path)["key"] == "2026-10-16-midday"


def test_the_record_files_by_the_issues_pacific_month(tmp_path):
    issue = {"key": "2026-10-31-midday", "day": "2026-10-31", "slot_utc": "2026-10-31T19:00:00Z"}
    bf.append(tmp_path, issue)
    assert (tmp_path / "briefings" / "2026-10.jsonl").exists()


def test_the_page_file_is_the_newest_kept_issue_and_nothing_is_rebuilt_between(tmp_path):
    issue = {"key": "2026-10-16-morning", "day": "2026-10-16", "slot_utc": "2026-10-16T13:00:00Z",
             "available": True}
    path = tmp_path / "issue.json"
    path.write_text(json.dumps(issue))
    out = tmp_path / "live" / "briefing.json"
    assert bf.main(["--data-dir", str(tmp_path), "--record", str(path), "--out", str(out)]) == 0
    assert json.loads(out.read_text())["key"] == "2026-10-16-morning"
    # A collection with no issue due leaves the page on the kept one.
    assert bf.main(["--data-dir", str(tmp_path), "--at", "2026-10-16T17:00:00Z", "--out", str(out)]) == 0
    assert json.loads(out.read_text())["key"] == "2026-10-16-morning"


def test_no_observed_reading_is_said_as_such(tmp_path):
    got = bf.build(data_dir=tmp_path, at=_at("2026-10-16T13:05:00Z"))
    assert got["available"] is False and got["key"] == "2026-10-16-morning"
    assert got["why"] == "no observed reading was built this collection"


# ------------------------------------------------------------------ swell

def test_a_rise_past_the_threshold_is_filling_and_one_under_it_is_little_change():
    up = [1.0] * 3 + [1.0 + 0.05 * k for k in range(1, 11)]       # +50% by the end
    small = [1.0] * 3 + [1.0 + 0.01 * k for k in range(1, 11)]    # +10%
    s = _series({"coronado_north": up, "coronado_center": small, "coronado_south": _flat(1.0)})
    got = bf.change(_now(T0 + timedelta(hours=12)), s, T0 + timedelta(hours=1))
    assert {r["id"]: r["change"] for r in got["breaks"]} == {
        "coronado_north": "filling", "coronado_center": "little", "coronado_south": "little"}
    assert got["measured"] and got["span_h"] == 11.0


def test_a_fall_past_the_threshold_is_fading():
    down = [1.0] * 3 + [1.0 - 0.05 * k for k in range(1, 11)]
    s = _series({"coronado_north": down, "coronado_center": _flat(1.0), "coronado_south": _flat(1.0)})
    got = bf.change(_now(T0 + timedelta(hours=12)), s, T0 + timedelta(hours=1))
    assert got["breaks"][0]["change"] == "fading"


def test_a_short_span_gives_the_readings_and_no_word():
    s = _series({bid: [1.0, 1.0, 2.0, 2.0] for bid in bf.BREAKS})
    got = bf.change(_now(T0 + timedelta(hours=3)), s, T0)
    assert not got["measured"]
    assert all(r["change"] is None and r["then_m"] == 1.0 for r in got["breaks"])


def test_the_midday_span_is_the_measured_six_hours():
    """Morning reads the 5 AM spectrum and Midday the 11 AM one, so Midday's
    comparison is exactly the shortest span the threshold was measured on."""
    assert bf.MIN_SPAN_H == 6
    assert (bf.slot(DAY, "midday") - bf.slot(DAY, "morning")) == timedelta(hours=bf.MIN_SPAN_H)


def test_no_earlier_hour_gives_now_alone():
    s = _series({bid: _flat(1.0) for bid in bf.BREAKS})
    got = bf.change(_now(T0 + timedelta(hours=12)), s, None)
    assert got["then_utc"] is None and all(r["then_m"] is None for r in got["breaks"])


def test_the_leader_needs_its_margin():
    s = _series({"coronado_north": _flat(1.10), "coronado_center": _flat(1.0),
                 "coronado_south": _flat(1.03)})
    assert bf.change(_now(T0 + timedelta(hours=12)), s, T0 + timedelta(hours=1))["lead_now"] == "coronado_north"
    s = _series({"coronado_north": _flat(1.03), "coronado_center": _flat(1.0),
                 "coronado_south": _flat(1.0)})
    assert bf.change(_now(T0 + timedelta(hours=12)), s, T0 + timedelta(hours=1))["lead_now"] is None


def test_dark_or_missing_newest_hour_stands_the_story_down():
    s = _series({bid: _flat(1.0) for bid in bf.BREAKS}, gaps={12})
    assert bf.change(_now(T0 + timedelta(hours=12)), s, T0) is None
    stale = _now(T0 + timedelta(hours=11)) | {"stale": True}
    assert bf.change(stale, s, T0) is None


def test_what_was_out_there_is_what_the_previous_issue_read():
    s = _series({bid: _flat(1.0, 30) for bid in bf.BREAKS})
    prior = (DAY, "morning", T0 + timedelta(hours=20))
    record = {"2026-10-16-morning": {"swell": {"newest_utc": (T0 + timedelta(hours=18)).strftime(ISO)}}}
    assert bf.then_hour(record, prior, s) == T0 + timedelta(hours=18)
    # Not kept: the series' newest hour at or before the previous slot.
    assert bf.then_hour({}, prior, s) == T0 + timedelta(hours=20)


def test_the_buoys_trains_then_are_its_own_spectrum_or_none():
    hour = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)
    got = bf.trains_at(Path("data"), hour)
    assert got and all(set(t) == {"hs_m", "period_s", "from_deg", "wind_sea"} for t in got)
    assert bf.trains_at(Path("data"), hour + timedelta(minutes=30)) is None


def test_origin_reads_the_sites_as_now_writes_them():
    """now.json's `current` entries are {"arrival", "train_period_s"}, not bare
    indexes: read as indexes they crashed the Morning issue of 2026-10-18."""
    since, newest = T0, T0 + timedelta(hours=12)
    arrival = {"first_utc": (T0 - timedelta(hours=30)).strftime(ISO), "running": True,
               "last_utc": newest.strftime(ISO), "distance_km": 10000.0,
               "generated_utc": (T0 - timedelta(days=8)).strftime(ISO), "latest_period_s": 16.7}
    ended = dict(arrival, running=False, last_utc=(T0 + timedelta(hours=2)).strftime(ISO))
    now = {"origin": {"arrivals": [ended, arrival], "hurricanes": [{"name": "TRUDY"}], "sites": {
        "coronado_north": {"current": [{"arrival": 1, "train_period_s": 16.7}], "last": 0},
        "coronado_center": {"current": [{"arrival": 1, "train_period_s": 18.2}], "last": 1},
        "coronado_south": {"current": [], "last": 0},
        "buoy": {"current": [{"arrival": 1, "train_period_s": 16.7}], "last": 1}}}}
    got = bf.origin_story(now, since, newest)
    assert [a["breaks"] for a in got["arriving"]] == [["coronado_north", "coronado_center"]]
    assert [a["breaks"] for a in got["finished"]] == [["coronado_north", "coronado_south"]]
    assert got["named"] == ["TRUDY"]


def test_an_issue_builds_on_this_collections_own_files():
    """The whole build, on the payloads forecast.now writes from the archive:
    every story read from the real shapes, not a fixture's."""
    from forecast import now as observed

    live = Path("data/live")
    if not (live / "now.json").exists():
        pytest.skip("no now.json built in data/live")
    at = datetime.strptime(json.loads((live / "now.json").read_text())["generated_utc"], ISO) \
        .replace(tzinfo=timezone.utc)
    got = bf.build(at=at, issue=bf.latest_slot(at), record={})
    assert got["available"] and set(got) >= {"overview", "swell", "tide", "wind", "watching"}


def test_tanner_banks_north_west_rise_on_the_night_of_8_october():
    """On the archive: 46047's north-west sector rose overnight 8–9 October,
    14–17 s first, due at 46232 by deep-water speed and at every break."""

    since = datetime(2026, 10, 9, 1, 24, tzinfo=timezone.utc)
    at = datetime(2026, 10, 9, 14, 30, tzinfo=timezone.utc)
    got = bf.upstream_story(Path("data"), {"buoys": [{"station": "46047", "stale": False}]}, since, at)
    nw = next(g for g in got if g["sector"] == "north-west")
    first = nw["bands"][0]
    assert first["band_s"] == [14.0, 17.0]
    due = _at(first["due_buoy_utc"])
    rose = _at(first["since_utc"])
    assert (due - rose).total_seconds() / 3600 == pytest.approx(first["lag_h"], abs=0.05)
    assert {l["id"] for l in first["legs"]} == set(bf.BREAKS)


def test_a_stale_tanner_banks_says_nothing_upstream():
    assert bf.upstream_story(Path("data"), {"buoys": [{"station": "46047", "stale": True}]},
                             T0, T0 + timedelta(hours=12)) == []


# ------------------------------------------------------------------ overview

def test_the_metar_t_group_and_hourly_precipitation_are_read():
    raw = ("METAR KNZY 161352Z 00000KT 10SM -RA BR OVC008 16/15 A2995 RMK AO2 SLP141 "
           "P0003 T01610150")
    got = bf.parse_metar(raw)
    assert got == {"air_c": 16.1, "dew_c": 15.0, "precip_in": 0.03, "kinds": ["rain"]}


def test_a_metar_without_the_t_group_falls_back_to_whole_degrees():
    got = bf.parse_metar("METAR KNZY 161352Z 29008KT 10SM CLR M01/M05 A3001 RMK AO2")
    assert got["air_c"] == -1 and got["dew_c"] == -5 and got["precip_in"] is None and got["kinds"] == []


def test_a_special_reports_weather_but_its_precipitation_is_not_summed():
    """A SPECI's P group repeats the routine hour's running total."""
    got = bf.parse_metar("SPECI KNZY 161310Z 18006KT 3SM SHRA OVC010 17/16 A2990 RMK AO2 P0002 T01720161")
    assert got["precip_in"] is None and got["kinds"] == ["showers", "rain"]


def test_vicinity_showers_are_not_precipitation_here():
    assert bf.parse_metar("METAR KNZY 161352Z 18006KT 10SM VCSH SCT020 17/16 A2990 RMK AO2")["kinds"] == []


def test_humidity_is_magnus():
    assert bf.humidity(20.0, 20.0) == pytest.approx(100.0)
    assert bf.humidity(25.0, 15.0) == pytest.approx(53.8, abs=0.3)


def test_the_weather_covers_the_window_alone(tmp_path):
    (tmp_path / "wind").mkdir()
    rows = [("2026-10-16T01:52:00Z", "METAR KNZY 160152Z 27008KT 10SM CLR 20/12 A2990 RMK AO2 T02000120"),
            ("2026-10-16T09:52:00Z", "METAR KNZY 160952Z 00000KT 5SM -RA BR 17/16 A2990 RMK AO2 P0004 T01720161"),
            ("2026-10-16T12:52:00Z", "METAR KNZY 161252Z 00000KT 10SM OVC010 16/15 A2990 RMK AO2 T01610150")]
    with (tmp_path / "wind" / "KNZY.csv").open("w") as fh:
        fh.write("observed_utc,first_seen_utc,wind_from_deg,wind_kt,gust_kt,variable,raw\n")
        for t, raw in rows:
            fh.write(f"{t},{t},0,0,,,{raw}\n")
    got = bf.weather_story(tmp_path, _at("2026-10-16T02:00:00Z"), _at("2026-10-16T13:05:00Z"))
    assert got["reports"] == 2
    assert got["air_c"] == {"min": 16.1, "max": 17.2, "now": 16.1, "now_utc": "2026-10-16T12:52:00Z"}
    assert got["precip_in"] == 0.04 and got["precip_kinds"] == ["rain"]
    assert got["wet_from_utc"] == got["wet_to_utc"] == "2026-10-16T09:52:00Z"


def test_daylight_is_the_sea_horizons(tmp_path):
    got = bf.overview_story(tmp_path, DAY, _at("2026-10-16T01:15:00Z"), _at("2026-10-16T13:05:00Z"))
    rise, sets = _at(got["sunrise_utc"]), _at(got["sunset_utc"])
    assert abs((sets - rise).total_seconds() / 60 - got["daylight_min"]) <= 1
    assert 660 <= got["daylight_min"] <= 700                  # mid-October at 32.7° N
    assert got["water"] is None and got["weather"]["reports"] == 0


def test_the_water_is_46232s_standard_met_in_the_window():
    got = bf.water_story(Path("data"), _at("2026-10-16T01:00:00Z"), _at("2026-10-16T13:05:00Z"))
    assert got["station"] == "46232" and got["min_c"] <= got["now_c"] <= got["max_c"]
    assert got["now_utc"] <= "2026-10-16T13:05:00Z"


# ------------------------------------------------------------------ tide, wind

def test_the_tide_keeps_the_turn_before_the_two_after_and_the_rest_of_the_day():
    at = _at("2026-10-17T15:00:00Z")                          # 8 AM Pacific
    got = bf.tide_story({"tide_station": "9410170"}, Path("data"), date(2026, 10, 17), at)
    roles = [t["role"] for t in got["turns"]]
    assert roles[0] == "previous" and roles.count("previous") == 1
    assert got["turns"][0]["valid_utc"] <= "2026-10-17T15:00:00Z" < got["turns"][1]["valid_utc"]
    assert got["range"] is None or got["range"]["m"] > 0


def test_the_wind_counts_match_the_cards_verdict():
    assert bf._sense(0.9, 0.0) == "calm"
    assert bf._sense(0.9, 3.0) == "light"
    assert bf._sense(None, 6.0) == "variable"
    assert bf._sense(0.9, 6.0) == "offshore"
    assert bf._sense(-0.9, 6.0) == "onshore"
    assert bf._sense(0.0, 6.0) == "cross-shore"


def test_the_wind_history_is_the_same_clock_hour_on_each_earlier_day():
    now = _now(T0)
    at = _at("2026-10-16T13:05:00Z")
    got = bf.wind_story(now, Path("data"), at)
    assert got["now"]["observed_utc"] <= "2026-10-16T13:05:00Z"
    h = got["history"]
    assert h["days"] > 20
    for bid in bf.BREAKS:
        assert sum(h["by_break"][bid].values()) == h["days"]


def test_a_stale_wind_is_not_now():
    got = bf.wind_story(_now(T0), Path("data"), _at("2026-09-01T12:00:00Z"))
    assert got == {"now": None, "history": None}


def test_sunset_is_the_last_one_before_the_reading():
    morning = datetime(2026, 10, 9, 14, tzinfo=timezone.utc)      # 7 AM Pacific
    evening = datetime(2026, 10, 9, 4, tzinfo=timezone.utc)       # 9 PM Pacific, Oct 8
    for at in (morning, evening):
        s = bf.last_sunset(at)
        assert s <= at and at - s < timedelta(hours=24)
        local_h = (s - timedelta(hours=7)).hour
        assert 17 <= local_h <= 19


def test_the_briefing_never_reads_the_model():
    """GFS-Wave and its ensemble are the Forecast tab's (owner's call,
    2026-10-16)."""

    src = Path(bf.__file__).read_text(encoding="utf-8")
    code = src.split('"""', 2)[2]
    for word in ("forecast.json", "gfswave", "wavespec", "gefswave", "ensemble", "forecast.live import build"):
        assert word not in code, word


def test_the_workflow_records_from_a_fresh_tip_and_never_rebases():
    """CLAUDE.md: a rejected push of an append-only log re-appends; it never
    rebases. The record step works in its own worktree on the newest tip."""

    flow = Path(".github/workflows/collect-beach-inputs.yml").read_text(encoding="utf-8")
    step = flow[flow.index("- name: Record the briefing"):]
    step = step[:step.index("\n      - name:")]
    assert "git worktree add" in step and "python -m forecast.briefing --record" in step
    assert "--rebase" not in step and "git rebase" not in step and "git pull" not in step
    main = flow[flow.index("- name: Commit and push"):]
    main = main[:main.index("\n      - name:")]
    assert "git add data/briefings" not in main and "data/briefings 2" not in main
