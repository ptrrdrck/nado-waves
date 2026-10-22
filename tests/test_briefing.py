"""The LIVE briefing: what it reads from the collection's files, and when a
build is an update. It updates only when its swell or tide words change
(owner's call, 2026-10-22); the conditions refresh without one."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from forecast import briefing as bf

T0 = datetime(2026, 10, 9, 2, tzinfo=timezone.utc)
ISO = "%Y-%m-%dT%H:%M:%SZ"


def _at(stamp: str) -> datetime:
    return datetime.strptime(stamp, ISO).replace(tzinfo=timezone.utc)


def _built(stamp, swell=("Significant waves breaking in the 3–4 ft (0.9–1.2 m) range with a 13.3 s period.",),
           tides=("AM low 0.7 ft (0.21 m) at 3:15 AM",), water=19.4):
    return {"built_utc": stamp, "available": True, "conditions": {"water": {"c": water}},
            "update_words": list(swell) + list(tides), "text": {"swell": list(swell), "tides": list(tides)}}


def _knzy(tmp_path, rows):
    (tmp_path / "wind").mkdir(exist_ok=True)
    with (tmp_path / "wind" / "KNZY.csv").open("w") as fh:
        fh.write("observed_utc,first_seen_utc,wind_from_deg,wind_kt,gust_kt,variable,raw\n")
        for t, raw in rows:
            fh.write(f"{t},{t},0,0,,,{raw}\n")


# ------------------------------------------------------------------ updates

def test_a_first_build_is_an_update():
    page, update = bf.settle(None, _built("2026-10-22T14:16:00Z"))
    assert update and page["key"] == page["updated_utc"] == "2026-10-22T14:16:00Z"


def test_the_same_words_are_no_update_and_keep_the_updates_time():
    kept, _ = bf.settle(None, _built("2026-10-22T14:16:00Z"))
    page, update = bf.settle(kept, _built("2026-10-22T15:16:00Z", water=19.9))
    assert not update
    assert page["key"] == page["updated_utc"] == "2026-10-22T14:16:00Z"
    assert page["built_utc"] == "2026-10-22T15:16:00Z" and page["conditions"]["water"]["c"] == 19.9


def test_changed_swell_or_tide_words_are_an_update():
    kept, _ = bf.settle(None, _built("2026-10-22T14:16:00Z"))
    assert bf.settle(kept, _built("2026-10-22T15:16:00Z", swell=("Significant waves breaking in the "
                                                                "3–4 ft (0.9–1.2 m) range with a 14.3 s period.",)))[1]
    assert bf.settle(kept, _built("2026-10-22T15:16:00Z", tides=("AM low 0.8 ft (0.24 m) at 3:15 AM",)))[1]


def test_a_line_of_the_old_design_never_matches():
    old = {"key": "2026-10-22-midday", "issued_utc": "2026-10-22T19:06:00Z", "updated_utc": None}
    assert bf.settle(old, _built("2026-10-22T20:16:00Z"))[1]


def test_a_build_without_words_is_always_an_update():
    kept, _ = bf.settle(None, _built("2026-10-22T14:16:00Z"))
    assert bf.settle(kept, {**_built("2026-10-22T15:16:00Z"), "update_words": None})[1]


def test_the_record_keeps_updates_only_and_the_page_gets_every_build(tmp_path):
    out = tmp_path / "live" / "briefing.json"
    built = tmp_path / "built.json"
    for stamp, water, period in (("2026-10-22T14:16:00Z", 19.4, "13.3"), ("2026-10-22T15:16:00Z", 19.9, "13.3"),
                                 ("2026-10-22T16:16:00Z", 20.1, "14.3")):
        swell = (f"Significant waves breaking in the 3–4 ft (0.9–1.2 m) range with a {period} s period.",)
        built.write_text(json.dumps(_built(stamp, swell=swell, water=water)))
        assert bf.main(["--data-dir", str(tmp_path), "--record", str(built), "--out", str(out)]) == 0
        page = json.loads(out.read_text())
        assert page["built_utc"] == stamp and page["conditions"]["water"]["c"] == water
    lines = (tmp_path / "briefings" / "2026-10.jsonl").read_text().splitlines()
    assert [json.loads(x)["key"] for x in lines] == ["2026-10-22T14:16:00Z", "2026-10-22T16:16:00Z"]
    assert page["updated_utc"] == "2026-10-22T16:16:00Z"


def test_the_record_files_by_the_pacific_month(tmp_path):
    bf.append(tmp_path, bf.settle(None, _built("2026-11-01T02:00:00Z"))[0])     # 31 Oct, 7 PM Pacific
    assert (tmp_path / "briefings" / "2026-10.jsonl").exists()


def test_the_newest_kept_line_is_read_across_both_designs(tmp_path):
    (tmp_path / "briefings").mkdir()
    (tmp_path / "briefings" / "2026-10.jsonl").write_text(
        json.dumps({"key": "2026-10-22-midday", "issued_utc": "2026-10-22T19:06:00Z"}) + "\n"
        + json.dumps(bf.settle(None, _built("2026-10-22T20:16:00Z"))[0]) + "\n")
    assert bf.newest(tmp_path)["key"] == "2026-10-22T20:16:00Z"


def test_no_observed_reading_is_said_as_such(tmp_path):
    got = bf.build(data_dir=tmp_path, at=_at("2026-10-22T14:16:00Z"))
    assert got["available"] is False and got["why"] == "no observed reading was built this collection"


# ------------------------------------------------------------------ swell

def test_the_swell_is_each_breaks_card_number_and_lead_period(tmp_path):
    now = {"observed_utc": "2026-10-22T14:00:00Z", "stale": False, "breaks": [
        {"id": "coronado_north", "hs_nearshore_m": 1.31, "peak_period_s": 16.7},
        {"id": "coronado_center", "hs_nearshore_m": 1.00, "peak_period_s": 16.7},
        {"id": "coronado_south", "hs_nearshore_m": 0.74, "peak_period_s": 13.3}]}
    got = bf.swell_story(now, None, _at("2026-10-22T14:16:00Z"), tmp_path)
    assert got["breaks"] == [{"id": "coronado_north", "hs_m": 1.31, "period_s": 16.7},
                             {"id": "coronado_center", "hs_m": 1.00, "period_s": 16.7},
                             {"id": "coronado_south", "hs_m": 0.74, "period_s": 13.3}]
    assert got["coming"] == []


def test_a_dark_buoy_is_said_and_nothing_else():
    got = bf.swell_story({"observed_utc": "2026-10-21T22:00:00Z", "stale": True}, None,
                         _at("2026-10-22T14:16:00Z"), Path("."))
    assert got == {"dark": True, "newest_utc": "2026-10-21T22:00:00Z"}


def test_a_rise_is_carried_as_its_first_band():
    at = datetime(2026, 10, 9, 14, 30, tzinfo=timezone.utc)
    got = bf.swell_story({"observed_utc": "2026-10-09T14:00:00Z", "stale": False, "breaks": []},
                         {"buoys": [{"station": "46047", "stale": False}]}, at, Path("data"))
    nw = next(c for c in got["coming"] if c["sector"] == "north-west")
    full = next(u for u in bf.upstream_story(Path("data"), {"buoys": [{"station": "46047", "stale": False}]},
                                             at - timedelta(hours=bf.UPSTREAM_LOOKBACK_H), at)
                if u["sector"] == "north-west")
    assert nw["band_s"] == full["bands"][0]["band_s"]            # the earliest rise, "… s first"
    assert all(b["since_utc"] >= nw["since_utc"] for b in full["bands"])
    assert nw["due_buoy_utc"] > nw["since_utc"] and {l["id"] for l in nw["legs"]} == set(bf.BREAKS)


# ------------------------------------------------------------------ conditions

def test_the_conditions_are_the_newest_report_and_the_rain_two_ways(tmp_path):
    _knzy(tmp_path, [
        ("2026-10-21T16:52:00Z", "METAR KNZY 211652Z 27008KT 5SM -RA BR 17/16 A2990 RMK AO2 P0004 T01720161"),
        ("2026-10-22T12:52:00Z", "METAR KNZY 221252Z 00000KT 10SM -RA OVC010 16/15 A2990 RMK AO2 P0002 T01610150"),
        ("2026-10-22T13:10:00Z", "SPECI KNZY 221310Z 00000KT 10SM -RA OVC010 16/15 A2990 RMK AO2 P0001 T01610150"),
        ("2026-10-22T13:52:00Z", "METAR KNZY 221352Z 00000KT 10SM OVC010 16/15 A2990 RMK AO2 T01670150")])
    got = bf.weather_now(tmp_path, _at("2026-10-22T14:05:00Z"))
    assert got["air_c"] == 16.7 and got["observed_utc"] == "2026-10-22T13:52:00Z"
    assert got["humidity_pct"] == pytest.approx(bf.humidity(16.7, 15.0), abs=0.05)
    assert got["precip_hour_in"] == 0.0          # the newest routine report had none
    assert got["precip_day_in"] == 0.06          # 0.04 + 0.02; the SPECI repeats its hour
    assert got["precip_kinds"] == ["rain"]       # the SPECI at 13:10 is within the hour


def test_a_stale_report_is_not_current(tmp_path):
    _knzy(tmp_path, [("2026-10-22T10:52:00Z", "METAR KNZY 221052Z 00000KT 10SM CLR 16/15 A2990 RMK AO2 T01610150")])
    got = bf.weather_now(tmp_path, _at("2026-10-22T14:16:00Z"))
    assert got["air_c"] is None and got["humidity_pct"] is None and got["precip_hour_in"] is None


def test_the_water_is_46232s_newest_within_three_hours():
    got = bf.water_now(Path("data"), _at("2026-10-16T13:05:00Z"))
    assert got["station"] == "46232" and got["observed_utc"] <= "2026-10-16T13:05:00Z"
    assert _at("2026-10-16T13:05:00Z") - _at(got["observed_utc"]) <= timedelta(hours=bf.WATER_FRESH_H)


# ------------------------------------------------------------------ tide

def test_the_tides_are_the_pacific_days_turns():
    got = bf.tide_story({"tide_station": "9410170"}, Path("data"), _at("2026-10-17T15:00:00Z"))
    assert got["day"] == "2026-10-17" and got["turns"]
    for t in got["turns"]:
        local = _at(t["valid_utc"]) - timedelta(hours=7)
        assert local.date().isoformat() == "2026-10-17"


def test_a_build_reads_this_collections_own_files():
    """The whole build on the payloads forecast.now writes, so every story
    reads the real shapes, not a fixture's."""

    live = Path("data/live")
    if not (live / "now.json").exists():
        pytest.skip("no now.json built in data/live")
    at = _at(json.loads((live / "now.json").read_text())["generated_utc"])
    got = bf.build(at=at)
    assert got["available"] and set(got) >= {"swell", "conditions", "tide"}


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
