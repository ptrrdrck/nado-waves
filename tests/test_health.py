"""Station liveness and the app-facing status file.

The product rule these pin (SPEC section 5): a dark buoy stays discoverable with
its rounds paused and an explanation, rather than disappearing from the list.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from collector.archive import merge_station
from collector.health import (
    DARK,
    LIVE,
    NEVER_SEEN,
    build_status,
    load_status,
    newly_dark,
    status_path,
    write_status,
)
from collector.ndbc import parse_realtime2
from collector.stations import Station

HEADER = (
    "#YY  MM DD hh mm WDIR WSPD GST  WVHT   DPD   APD MWD   PRES  ATMP  WTMP  DEWP  VIS PTDY  TIDE\n"
    "#yr  mo dy hr mn degT m/s  m/s     m   sec   sec degT   hPa  degC  degC  degC  nmi  hPa    ft\n"
)

LIVE_STATION = Station(id="46222", name="San Pedro, CA", region="socal")
DARK_STATION = Station(id="46232", name="Point Loma South, CA", region="socal")

NOW = datetime(2026, 9, 13, 2, 0, tzinfo=timezone.utc)


def archive(tmp_path: Path, station: Station, *, hours_old: float, wtmp: str = " 20.1"):
    t = NOW - timedelta(hours=hours_old)
    row = (
        t.strftime("%Y %m %d %H %M")
        + f"  MM   MM   MM   0.7  13.8   6.7 203     MM    MM {wtmp}    MM   MM   MM    MM"
    )
    merge_station(tmp_path, station.id, parse_realtime2(HEADER + row + "\n"))


def test_a_fresh_station_is_live_and_takes_calls(tmp_path):
    archive(tmp_path, LIVE_STATION, hours_old=1)
    entry = build_status(tmp_path, [LIVE_STATION], now=NOW)["stations"][0]
    assert entry["state"] == LIVE
    assert entry["rounds_paused"] is False
    assert entry["paused_reason"] is None


def test_a_dark_buoy_stays_listed_with_rounds_paused(tmp_path):
    # 46232 went dark on 2026-09-01 in the real archive. It keeps its league
    # page; it just cannot take a call.
    archive(tmp_path, DARK_STATION, hours_old=274)
    entry = build_status(tmp_path, [DARK_STATION], now=NOW)["stations"][0]
    assert entry["state"] == DARK
    assert entry["rounds_paused"] is True
    assert entry["id"] == "46232"
    assert entry["name"] == "Point Loma South, CA"
    # Still discoverable: history and identity survive.
    assert entry["observation_rows"] == 1


def test_the_paused_reason_names_the_date_it_stopped(tmp_path):
    archive(tmp_path, DARK_STATION, hours_old=274)
    entry = build_status(tmp_path, [DARK_STATION], now=NOW)["stations"][0]
    assert "2026-09-01" in entry["paused_reason"]
    assert "Past results are still here" in entry["paused_reason"]


def test_went_dark_at_its_last_observation_not_when_we_noticed(tmp_path):
    archive(tmp_path, DARK_STATION, hours_old=274)
    entry = build_status(tmp_path, [DARK_STATION], now=NOW)["stations"][0]
    assert entry["state_since_utc"] == entry["newest_observation_utc"]
    assert entry["state_since_utc"].startswith("2026-09-01")


def test_state_since_survives_later_runs(tmp_path):
    archive(tmp_path, DARK_STATION, hours_old=274)
    first = build_status(tmp_path, [DARK_STATION], now=NOW)
    write_status(tmp_path, first)
    later = build_status(tmp_path, [DARK_STATION], now=NOW + timedelta(days=5))
    assert (
        later["stations"][0]["state_since_utc"] == first["stations"][0]["state_since_utc"]
    )


def test_a_reporting_buoy_with_no_water_temp_cannot_host_a_round(tmp_path):
    archive(tmp_path, LIVE_STATION, hours_old=1, wtmp="   MM")
    entry = build_status(tmp_path, [LIVE_STATION], now=NOW)["stations"][0]
    assert entry["state"] == LIVE
    assert entry["rounds_paused"] is True
    assert "water temperature" in entry["paused_reason"]


def test_a_station_with_no_file_is_never_seen(tmp_path):
    entry = build_status(tmp_path, [LIVE_STATION], now=NOW)["stations"][0]
    assert entry["state"] == NEVER_SEEN
    assert entry["rounds_paused"] is True


def test_a_buoy_that_just_went_dark_is_worth_an_alert(tmp_path):
    archive(tmp_path, DARK_STATION, hours_old=60)
    status = build_status(tmp_path, [DARK_STATION], now=NOW)
    assert [e["id"] for e in newly_dark(status, now=NOW)] == ["46232"]


def test_a_long_dark_buoy_does_not_re_alert(tmp_path):
    # The alert-fatigue rule: 46232 has been dark for 11 days and is already
    # shown as paused in the app. Re-alerting daily trains you to ignore it.
    archive(tmp_path, DARK_STATION, hours_old=274)
    status = build_status(tmp_path, [DARK_STATION], now=NOW)
    assert newly_dark(status, now=NOW) == []


def test_status_round_trips_to_disk(tmp_path):
    archive(tmp_path, LIVE_STATION, hours_old=1)
    payload = build_status(tmp_path, [LIVE_STATION], now=NOW)
    write_status(tmp_path, payload)
    assert status_path(tmp_path).name == "station_status.json"
    assert load_status(tmp_path) == payload


def test_corrupt_status_file_does_not_break_a_run(tmp_path):
    archive(tmp_path, LIVE_STATION, hours_old=1)
    status_path(tmp_path).write_text("{not json", encoding="utf-8")
    assert load_status(tmp_path) == {}
    assert build_status(tmp_path, [LIVE_STATION], now=NOW)["stations"][0]["state"] == LIVE


def test_status_reports_what_a_buoy_is_for_not_just_whether_it_is_alive(tmp_path):
    """A dark anchor and a dark off-axis buoy are different news.

    The role is derived by `forecast.siting` and injected, so the status file
    can say which one just went dark without this module depending on the
    beach geometry.
    """

    archive(tmp_path, DARK_STATION, hours_old=274)
    entry = build_status(
        tmp_path, [DARK_STATION], now=NOW, roles={"46232": "window"}
    )["stations"][0]
    assert entry["state"] == DARK
    assert entry["constrains_window"] == "window"


def test_a_station_siting_could_not_place_is_unclassified_not_absent(tmp_path):
    """Missing geometry must never read as "this buoy doesn't matter"."""

    archive(tmp_path, LIVE_STATION, hours_old=1)
    entry = build_status(tmp_path, [LIVE_STATION], now=NOW, roles={})["stations"][0]
    assert entry["constrains_window"] == "unclassified"
    entry = build_status(tmp_path, [LIVE_STATION], now=NOW)["stations"][0]
    assert entry["constrains_window"] == "unclassified"


def test_a_never_seen_station_stops_alerting_once_it_is_old_news(tmp_path):
    """A buoy registered while dark must not alert on every run forever.

    46235 was added to the registry before it had ever reported, deliberately,
    so that archiving starts the day it comes back. It has no last observation
    to date "dark since" from, and before `first_checked_utc` existed that made
    it permanently "newly dark".
    """

    from collector.health import newly_dark

    station = Station(id="46235", name="46235 (unconfirmed)", region="socal")
    first = build_status(tmp_path, [station], now=NOW)
    assert first["stations"][0]["state"] == NEVER_SEEN
    assert first["stations"][0]["first_checked_utc"] is not None
    # Worth one alert when it first appears...
    assert [e["id"] for e in newly_dark(first, now=NOW)] == ["46235"]

    # ...and silent a week later, still never having reported.
    later = NOW + timedelta(days=7)
    second = build_status(tmp_path, [station], now=later, previous=first)
    assert second["stations"][0]["first_checked_utc"] == first["stations"][0]["first_checked_utc"]
    assert newly_dark(second, now=later) == []


def test_first_checked_survives_a_station_coming_back_to_life(tmp_path):
    station = Station(id="46235", name="46235 (unconfirmed)", region="socal")
    first = build_status(tmp_path, [station], now=NOW)
    archive(tmp_path, station, hours_old=1)
    back = build_status(tmp_path, [station], now=NOW, previous=first)
    assert back["stations"][0]["state"] == LIVE
    assert back["stations"][0]["first_checked_utc"] == first["stations"][0]["first_checked_utc"]
