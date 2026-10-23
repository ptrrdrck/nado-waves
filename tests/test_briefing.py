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


def _built(stamp, swell=("3–4 ft (0.9–1.2 m) SSW at 13.3 s, holding.",),
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
    assert bf.settle(kept, _built("2026-10-22T15:16:00Z", swell=("3–4 ft (0.9–1.2 m) SSW at 14.3 s, holding.",)))[1]
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
        swell = (f"3–4 ft (0.9–1.2 m) SSW at {period} s, holding.",)
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
        {"id": "coronado_north", "hs_nearshore_m": 1.31, "peak_period_s": 16.7, "peak_direction_deg": 215,
         "trains": [{"period_s": 16.7, "from_deg": 215, "near_from_deg": 192, "lobes": []}]},
        {"id": "coronado_center", "hs_nearshore_m": 1.00, "peak_period_s": 16.7, "peak_direction_deg": 231,
         "trains": [{"period_s": 16.7, "from_deg": 231, "near_from_deg": 206, "lobes": []}]},
        {"id": "coronado_south", "hs_nearshore_m": 0.74, "peak_period_s": 13.3, "peak_direction_deg": 266,
         "trains": [{"period_s": 13.3, "from_deg": 266, "near_from_deg": 224, "lobes": []}]}]}
    got = bf.swell_story(now, None, _at("2026-10-22T14:16:00Z"), tmp_path)
    assert got["breaks"] == [{"id": "coronado_north", "hs_m": 1.31, "period_s": 16.7, "from_deg": 215, "also": []},
                             {"id": "coronado_center", "hs_m": 1.00, "period_s": 16.7, "from_deg": 231, "also": []},
                             {"id": "coronado_south", "hs_m": 0.74, "period_s": 13.3, "from_deg": 266, "also": []}]
    assert got["coming"] == []


def test_the_lead_heading_is_the_rows_offshore_one_never_its_5_m_one():
    """Owner's call, 2026-10-23: "SSW at 13.3 s" names the heading the train row
    shows; a train of two directions names the larger, as the row's
    shortest form does."""
    one = {"trains": [{"from_deg": 215, "near_from_deg": 192, "lobes": []}]}
    two = {"trains": [{"from_deg": 230, "near_from_deg": 210, "lobes": [[258, 0.6], [180, 0.4]]}]}
    assert bf.lead_heading(one) == 215
    assert bf.lead_heading(two) == 258
    assert bf.lead_heading({"trains": [], "peak_direction_deg": 200}) == 200
    assert bf.lead_heading({"trains": [{"from_deg": None, "lobes": []}]}) is None


def test_a_dark_buoy_is_said_and_nothing_else():
    got = bf.swell_story({"observed_utc": "2026-10-21T22:00:00Z", "stale": True}, None,
                         _at("2026-10-22T14:16:00Z"), Path("."))
    assert got == {"dark": True, "newest_utc": "2026-10-21T22:00:00Z"}


def test_a_rise_is_carried_as_its_first_band():
    at = datetime(2026, 10, 9, 14, 30, tzinfo=timezone.utc)
    got = bf.swell_story({"observed_utc": "2026-10-09T14:00:00Z", "stale": False, "breaks": []},
                         {"buoys": [{"station": "46047", "stale": False}]}, at, Path("data"))
    nw = next(c for c in got["coming"] if c["sector"] == "north-west")
    full = next(u for u in bf.upstream_story(Path("data"), {"buoys": [{"station": "46047", "stale": False}]}, at)
                if u["sector"] == "north-west")
    assert nw["band_s"] == full["bands"][0]["band_s"]            # the earliest rise, "… s first"
    assert all(b["since_utc"] >= nw["since_utc"] for b in full["bands"])
    assert nw["due_buoy_utc"] > nw["since_utc"] and {l["id"] for l in nw["legs"]} == set(bf.BREAKS)
    assert nw["trend"] in ("building", "peaking", "fading")
    first_in = min(_at(nw["due_buoy_utc"]) + timedelta(minutes=l["lo_min"]) for l in nw["legs"])
    assert _at(nw["arrives_utc"]) == first_in                     # "arriving since about …"


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

    at = datetime(2026, 10, 9, 14, 30, tzinfo=timezone.utc)
    got = bf.upstream_story(Path("data"), {"buoys": [{"station": "46047", "stale": False}]}, at)
    nw = next(g for g in got if g["sector"] == "north-west")
    first = nw["bands"][0]
    assert first["band_s"] == [14.0, 17.0]
    due = _at(first["due_buoy_utc"])
    rose = _at(first["since_utc"])
    assert (due - rose).total_seconds() / 3600 == pytest.approx(first["lag_h"], abs=0.05)
    assert {l["id"] for l in first["legs"]} == set(bf.BREAKS)


def test_a_stale_tanner_banks_says_nothing_upstream():
    assert bf.upstream_story(Path("data"), {"buoys": [{"station": "46047", "stale": True}]},
                             T0 + timedelta(hours=12)) == []


def test_the_briefings_bands_are_s43s_and_8_to_10_s():
    """Owner's request, 2026-10-23: 8–10 s too; the other three are §43's."""

    from forecast import upstreamlag as ul
    assert bf.UPSTREAM_BANDS_S == ((8.0, 10.0),) + tuple(ul.BANDS_S)


def _rise(hours):
    from forecast.upstreamlag import Rise
    mid = T0 + timedelta(hours=hours)
    return Rise(mid - timedelta(hours=3), mid, mid + timedelta(hours=3), 4.0)


def test_one_swell_is_its_newest_rise_and_the_longer_bands_before_it():
    """Dispersion orders a swell: its long periods rise first. A shorter band
    that rose earlier is another swell, and so is a longer one that rose
    later; a band with no rise of its own is passed over."""

    a, b, c, d = bf.UPSTREAM_BANDS_S
    risen = {a: [_rise(-30), _rise(20)],        # the 8–10 s rise a day before is another swell
             b: [],                             # rode in under its neighbours
             c: [_rise(10)],
             d: [_rise(2), _rise(15)]}          # 14–17 s at +15 rose after 12–14 s: not this swell's
    got = bf.disperse(risen, T0)
    assert [(band, r.mid) for band, r in got] == [(a, T0 + timedelta(hours=20)), (c, T0 + timedelta(hours=10)),
                                                 (d, T0 + timedelta(hours=2))]
    assert bf.disperse({a: [_rise(-5)], b: [], c: [], d: []}, T0) == []     # nothing new: no swell


def test_a_longer_band_more_than_a_day_before_is_another_swell():
    a, b, c, d = bf.UPSTREAM_BANDS_S
    got = bf.disperse({a: [_rise(30)], b: [], c: [], d: [_rise(30 - bf.UPSTREAM_GROUP_H - 1)]}, T0)
    assert [band for band, _ in got] == [a]


def test_tanner_banks_says_a_swell_for_as_long_as_it_holds_it():
    """Owner's call, 2026-10-23: a rise finds the swell, its presence keeps
    it. On the archive, the west swell that rose at 46047 on 22 October is
    still said after 03:25Z on the 23rd, when the old six-hour keep had
    dropped it, and has reached the breaks."""

    at = datetime(2026, 10, 23, 3, 30, tzinfo=timezone.utc)
    got = bf.upstream_story(Path("data"), {"buoys": [{"station": "46047", "stale": False}]}, at)
    west = next(g for g in got if g["sector"] == "west")
    assert west["now_m2"] >= west["peak_m2"] * bf.UPSTREAM_GONE_SHARE
    assert _at(west["arrives_utc"]) <= at


def _steps(heights, start=T0):
    return [{"valid_utc": (start + timedelta(hours=k)).strftime("%Y-%m-%dT%H:%M:%SZ"), "gap": h is None,
             "breaks": {} if h is None else {"coronado_north": {"hs_m": h}, "coronado_center": {"hs_m": h * 0.8},
                                              "coronado_south": {"hs_m": h * 0.7}}}
            for k, h in enumerate(heights)]


def test_the_beach_trend_is_the_biggest_breaking_height_over_three_hours():
    """Owner's calls, 2026-10-23: up 25% in energy over 3 h is building,
    down 25% fading; the day's highest within 3 h peaking; else holding."""

    flat = [1.0] * 27
    assert bf.beach_trend(_steps(flat)) == "holding"
    assert bf.beach_trend(_steps(flat[:-4] + [1.1, 1.2, 1.3, 1.4])) == "building"
    assert bf.beach_trend(_steps(flat[:-4] + [0.9, 0.85, 0.8, 0.75])) == "fading"
    rise_and_turn = [0.8 + 0.01 * k for k in range(25)] + [1.04, 1.03]
    assert bf.beach_trend(_steps(rise_and_turn)) == "peaking"
    # the south break is never the biggest here: only the biggest is read
    assert bf.beach_trend(_steps(flat[:-1] + [None])) == "holding"


def test_no_trend_without_the_hour_three_back():
    assert bf.beach_trend(_steps([1.0] * 23 + [None, 1.0, 1.0, 1.0])[:-3] + _steps([1.0], T0 + timedelta(hours=30))) \
        is None
    assert bf.beach_trend([]) is None


def test_a_mix_is_another_swell_train_at_seven_tenths_of_the_lead():
    """Owner's call, 2026-10-23: never wind sea, at least 70% of the lead's
    height; the page names the first from another compass point."""

    site = {"trains": [{"hs_m": 1.0, "period_s": 15.4, "from_deg": 203, "lobes": []},
                       {"hs_m": 0.9, "period_s": 5.0, "from_deg": 280, "lobes": [], "wind_sea": True},
                       {"hs_m": 0.75, "period_s": 10.0, "from_deg": 268, "lobes": [[268, 0.6], [200, 0.4]]},
                       {"hs_m": 0.6, "period_s": 12.5, "from_deg": 250, "lobes": []}]}
    assert bf.mix_trains(site) == [{"period_s": 10.0, "from_deg": 268, "hs_m": 0.75}]
    assert bf.mix_trains({"trains": []}) == []


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
