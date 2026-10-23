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

def test_the_swell_is_each_breaks_card_number_and_the_biggest_breaks_trains(tmp_path):
    now = {"observed_utc": "2026-10-22T14:00:00Z", "stale": False, "breaks": [
        {"id": "coronado_north", "hs_nearshore_m": 1.31, "peak_period_s": 16.7, "peak_direction_deg": 215,
         "trains": [{"period_s": 16.7, "from_deg": 215, "hs_m": 1.2, "near_from_deg": 192, "lobes": []}]},
        {"id": "coronado_center", "hs_nearshore_m": 1.00, "peak_period_s": 16.7, "peak_direction_deg": 231,
         "trains": [{"period_s": 16.7, "from_deg": 231, "hs_m": 0.9, "near_from_deg": 206, "lobes": []}]},
        {"id": "coronado_south", "hs_nearshore_m": 0.74, "peak_period_s": 13.3, "peak_direction_deg": 266,
         "trains": [{"period_s": 13.3, "from_deg": 266, "hs_m": 0.7, "near_from_deg": 224, "lobes": []}]}]}
    got = bf.swell_story(now, None, _at("2026-10-22T14:16:00Z"), tmp_path)
    assert got["breaks"] == [{"id": "coronado_north", "hs_m": 1.31}, {"id": "coronado_center", "hs_m": 1.00},
                             {"id": "coronado_south", "hs_m": 0.74}]
    # no band at the buoy in the reading: no status, never a guessed one
    assert got["trains"] == [{"period_s": 16.7, "from_deg": 215, "hs_m": 1.2, "trend": None}]
    assert got["coming"] == []


def test_every_swell_train_at_half_the_leads_height_is_listed_from_any_point():
    """Owner's calls, 2026-10-23: half its height, any point; never wind
    sea or local chop; a train of two directions by its larger, as its row
    names it, never its 5 m heading."""
    site = {"trains": [
        {"period_s": 15.4, "from_deg": 230, "hs_m": 1.0, "near_from_deg": 210, "lobes": [[258, 0.6], [180, 0.4]],
         "band_hz": [0.05, 0.08], "held_deg": [200, 270]},
        {"period_s": 14.3, "from_deg": 208, "hs_m": 0.5, "lobes": []},
        {"period_s": 4.8, "from_deg": 240, "hs_m": 0.9, "wind_sea": True, "lobes": []},
        {"period_s": 3.5, "from_deg": 250, "hs_m": 0.9, "wind_sea": True, "local": True},
        {"period_s": 10.0, "from_deg": 268, "hs_m": 0.49, "lobes": []}]}
    got = bf.listed_trains(site)
    assert [(t["period_s"], t["from_deg"]) for t in got] == [(15.4, 258), (14.3, 208)]
    assert got[0]["band_hz"] == [0.05, 0.08] and got[0]["held_deg"] == [200, 270]
    assert bf.listed_trains({"trains": [], "peak_period_s": 13.3, "peak_direction_deg": 200,
                             "hs_nearshore_m": 1.0})[0]["from_deg"] == 200
    assert bf.listed_trains({"trains": [{"period_s": 13.3, "from_deg": None, "hs_m": 1.0, "lobes": []}]}) \
        == [{"period_s": 13.3, "from_deg": None, "hs_m": 1.0, "band_hz": None, "held_deg": None}]


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
    assert got["day"] == "2026-10-17" and got["turns"] and got["station"] == "9410170"
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


def _energies(values, start=T0):
    return [(start + timedelta(hours=k), v) for k, v in enumerate(values) if v is not None]


def test_the_trend_words_are_energy_over_three_hours():
    """Owner's calls, 2026-10-23: up 25% in energy over 3 h is building,
    down 25% fading; the day's highest within 3 h peaking; else holding."""

    flat = [1.0] * 27
    assert bf.trend_word(_energies(flat)) == "holding"
    assert bf.trend_word(_energies(flat[:-4] + [1.2, 1.4, 1.7, 2.0])) == "building"
    assert bf.trend_word(_energies(flat[:-4] + [0.8, 0.7, 0.6, 0.5])) == "fading"
    rise_and_turn = [0.64 + 0.016 * k for k in range(25)] + [1.08, 1.06]
    assert bf.trend_word(_energies(rise_and_turn)) == "peaking"


def test_the_swell_headline_sparkline_is_the_biggest_breaking_height_over_24_hours():
    """Owner's choice, 2026-10-23: the beach line a headline, its last 24 h
    a sparkline: the biggest of the three breaks each hour, a gap a gap."""

    heights = [1.0 + 0.01 * k for k in range(30)]
    heights[27] = None
    spark = bf.beach_spark(_steps(heights))
    assert len(spark) == bf.SPARK_H["beach"] - 1                    # 24 h back, the missing hour missing
    assert spark[-1][1] == round(heights[-1], 3)                   # the north break's, the biggest here
    assert spark[-1][0] - spark[0][0] == 23 * 3600
    assert bf.beach_spark([]) == []


def test_no_trend_without_the_hour_three_back():
    assert bf.trend_word(_energies([1.0] * 23 + [None, 1.0, 1.0, 1.0])[:-3]
                         + _energies([1.0], T0 + timedelta(hours=30))) is None
    assert bf.trend_word([]) is None


def test_a_trains_status_is_its_band_at_the_buoy():
    """Owner's call, 2026-10-23: each train's status is its band at 46232 --
    its bins and the headings it held -- through the same words. Read on
    the archive at 23 Oct 05Z: the band's energy is the bins' within the
    held headings, never more than the whole band's, and a band the newest
    spectrum does not reach has no status."""

    from forecast.transform import load_spectra

    spectra = load_spectra(Path("data/spectra/46232"))
    newest = datetime(2026, 10, 23, 5, tzinfo=timezone.utc)
    sp = next(s for s in spectra if s.time == newest)
    band = [0.045, 0.14]
    whole, held = bf.band_energy(sp, band, []), bf.band_energy(sp, band, [197, 235])
    assert 0 < held < whole
    assert bf.band_energy(sp, band, [197, 197]) == whole           # a full circle is every heading
    train = {"band_hz": band, "held_deg": [197, 235]}
    assert bf.train_trend(spectra, train, newest) in ("building", "fading", "peaking", "holding")
    assert bf.train_trend(spectra, train, newest + timedelta(hours=30)) is None
    assert bf.train_trend(spectra, {"band_hz": None}, newest) is None


# ------------------------------------------------------------------ overview

def test_the_metar_t_group_and_hourly_precipitation_are_read():
    raw = ("METAR KNZY 161352Z 00000KT 10SM -RA BR OVC008 16/15 A2995 RMK AO2 SLP141 "
           "P0003 T01610150")
    got = bf.parse_metar(raw)
    assert got == {"air_c": 16.1, "dew_c": 15.0, "precip_in": 0.03, "kinds": ["rain"], "altimeter_inhg": 29.95}


def test_the_altimeter_is_the_bodys_a_group_never_the_remarks():
    """Owner's request, 2026-10-23: pressure, as METAR publishes it (inHg);
    SLP in the remarks is another quantity and never read."""

    assert bf.parse_metar("METAR KNZY 230352Z 27006KT 10SM CLR 19/12 A2999 RMK AO2 SLP155")["altimeter_inhg"] == 29.99
    assert bf.parse_metar("METAR KNZY 230352Z 27006KT 10SM CLR 19/12 RMK AO2 SLP155")["altimeter_inhg"] is None


def _series(start, values, step_min=60):
    return [(start + timedelta(minutes=step_min * k), v) for k, v in enumerate(values)]


def test_water_and_air_are_compared_three_hours_back_the_others_with_the_report_before():
    """Owner's calls, 2026-10-23, measured: the previous reading was the same
    on 64% of 46232's half-hours and 32% of KNZY's hours; 3 h back, 22% and
    15%. A change under half a source's step is steady."""

    water = _series(T0, [20.0, 20.0, 20.0, 20.1, 20.1, 20.1, 20.1], step_min=30)
    got = bf._trend("water", water, bf.TREND_BACK_H)
    assert got["dir"] == "up" and got["was_utc"] == bf._iso(T0)
    assert bf._trend("air", _series(T0, [18.0, 18.3, 18.9, 18.0]), bf.TREND_BACK_H)["dir"] == "steady"
    assert bf._trend("pressure", _series(T0, [30.01, 29.99]), None)["dir"] == "down"
    assert bf._trend("pressure", _series(T0, [29.99]), None)["dir"] is None        # nothing to compare: no arrow
    assert bf._trend("air", _series(T0, [18.0, 19.0]), bf.TREND_BACK_H)["dir"] is None  # no reading 3 h back


def test_humidity_is_compared_as_the_page_shows_it():
    """Computed from temperature and dewpoint, not measured: 65.3 to 65.6%
    reads 65% then 66% on the page, so the arrow says up."""

    assert bf._trend("humidity", _series(T0, [65.3, 65.6]), None)["dir"] == "up"
    assert bf._trend("humidity", _series(T0, [65.1, 65.4]), None)["dir"] == "steady"


def test_a_sparkline_is_an_hour_a_point_and_never_fills_a_gap():
    ser = _series(T0, [1.0, 1.1, 1.2], step_min=30) + _series(T0 + timedelta(hours=5), [2.0])
    spark = bf._trend("air", ser, None)["spark"]
    assert [p[1] for p in spark] == [1.1, 1.2, 2.0]           # the hour's newest; hours 2–4 stay empty
    assert spark[-1][0] - spark[-2][0] == 4 * 3600


def test_the_record_keeps_the_arrows_not_the_sparklines():
    line = {"built_utc": "x", "conditions": {"trends": {"air": {"dir": "up", "spark": [[1, 2.0]]},
                                                         "rain": {"days": [["2026-10-22", 0.0]]}}},
            "swell": {"trend": "building", "spark": [[1, 1.2]], "window_h": 24}}
    kept = bf.unsparked(line)
    assert kept["conditions"]["trends"] == {"air": {"dir": "up"}, "rain": {}}
    assert kept["swell"] == {"trend": "building", "window_h": 24}
    assert line["conditions"]["trends"]["air"]["spark"]                  # the page's copy is untouched


def test_the_trends_on_the_archive():
    """On 23 October at 04:30Z: each row the block shows has its arrow and
    sparkline, from its own source, over its own window."""

    at = datetime(2026, 10, 23, 4, 30, tzinfo=timezone.utc)
    water, weather = bf.water_now(Path("data"), at), bf.weather_now(Path("data"), at)
    got = bf.trends(Path("data"), at, water, weather)
    assert set(got) == {"water", "air", "humidity", "pressure", "rain"}
    assert got["water"]["window_h"] == 14 * 24 and got["air"]["window_h"] == 24 and got["pressure"]["window_h"] == 72
    assert all(got[k]["dir"] in ("up", "down", "steady") for k in ("water", "air", "humidity", "pressure"))
    assert len(got["rain"]["days"]) == bf.RAIN_DAYS and got["rain"]["days"][-1][0] == "2026-10-22"
    assert weather["pressure_inhg"] == 29.99


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
