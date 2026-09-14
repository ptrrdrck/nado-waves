"""The forecast experiment: coordinates from NDBC, forecasts archived as-published.

Framing matters here and is asserted, not just documented: this archive is an
experiment, not the scoring baseline (SPEC section 3 is undecided).
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from collector.forecast import (
    SOURCE,
    ForecastError,
    append_forecast,
    build_url,
    collect_station,
    fetch_forecast,
    forecast_path,
    parse_forecast,
)
from collector.metadata import (
    StationMetadata,
    build_metadata,
    load_metadata,
    parse_location,
    parse_station_table,
    write_metadata,
)
from collector.stations import Station

FIXTURES = Path(__file__).parent / "fixtures"

SOCAL = Station(id="46222", name="San Pedro, CA", region="socal")
FAR_AWAY = Station(id="41001", name="East Hatteras", region="socal")
BROKEN = Station(id="99999", name="Broken", region="socal")
MISSING = Station(id="46999", name="Not in table", region="socal")


def table():
    return parse_station_table((FIXTURES / "station_table.txt").read_text(encoding="utf-8"))


# --- coordinates -----------------------------------------------------------

def test_station_table_parses_by_header():
    rows = table()
    assert rows["46222"]["NAME"] == "San Pedro, CA"
    assert rows["46086"]["OWNER"] == "NDBC"


def test_location_becomes_signed_decimal_degrees():
    # West and South are negative; the entity-encoded degree symbols in the
    # parenthetical must not confuse the parse.
    assert parse_location("33.618 N 118.317 W (33&#176;37'5\" N 118&#176;19'1\" W)") == (
        33.618,
        -118.317,
    )
    assert parse_location("20.500 S 150.250 E") == (-20.5, 150.25)


def test_unparseable_location_returns_none():
    assert parse_location("not a location at all") is None
    assert parse_location("") is None


def test_socal_station_is_usable():
    meta = build_metadata([SOCAL], table())[0]
    assert meta.usable
    assert meta.latitude == pytest.approx(33.618)
    assert meta.longitude == pytest.approx(-118.317)


def test_a_station_outside_its_region_is_rejected_not_used():
    # An east-coast buoy tagged socal means something is wrong. Pulling a
    # forecast for it would look fine and be silently meaningless.
    meta = build_metadata([FAR_AWAY], table())[0]
    assert not meta.usable
    assert "outside the expected bounds" in meta.note


def test_an_unparseable_location_is_recorded_not_guessed():
    meta = build_metadata([BROKEN], table())[0]
    assert not meta.usable
    assert meta.latitude is None
    assert "could not parse" in meta.note


def test_a_station_absent_from_the_table_is_flagged():
    meta = build_metadata([MISSING], table())[0]
    assert not meta.usable
    assert "not present" in meta.note


def test_metadata_round_trips(tmp_path):
    records = build_metadata([SOCAL, FAR_AWAY], table())
    write_metadata(tmp_path, records)
    loaded = load_metadata(tmp_path)
    assert loaded["46222"].usable
    assert loaded["46222"].latitude == pytest.approx(33.618)
    assert not loaded["41001"].usable


# --- forecasts -------------------------------------------------------------

PAYLOAD = {
    "latitude": 33.625,
    "longitude": -118.3125,
    "hourly": {
        "time": ["2026-09-13T06:00", "2026-09-13T07:00", "2026-09-13T08:00"],
        "sea_surface_temperature": [23.5, None, 23.6],
    },
}


def test_url_carries_the_stations_own_coordinates():
    url = build_url(33.618, -118.317)
    assert "latitude=33.6180" in url
    assert "longitude=-118.3170" in url


def test_hourly_series_is_normalised_to_the_archive_timestamp_format():
    rows = parse_forecast(PAYLOAD)
    assert rows[0] == ("2026-09-13T06:00:00Z", "23.5")


def test_a_null_forecast_value_is_kept_empty_not_dropped(tmp_path):
    rows = parse_forecast(PAYLOAD)
    assert len(rows) == 3
    assert rows[1] == ("2026-09-13T07:00:00Z", "")


def test_archiving_records_what_was_published_and_when(tmp_path):
    append_forecast(
        tmp_path, "46222", parse_forecast(PAYLOAD),
        latitude=33.618, longitude=-118.317, fetched_at="2026-09-13T13:35:00Z",
    )
    with forecast_path(tmp_path, "46222").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 3
    assert rows[0]["fetched_at_utc"] == "2026-09-13T13:35:00Z"
    assert rows[0]["valid_time_utc"] == "2026-09-13T06:00:00Z"
    assert rows[0]["source"] == SOURCE
    assert rows[0]["latitude"] == "33.6180"


def test_a_later_issue_is_appended_never_overwrites_the_earlier_one(tmp_path):
    # The round was scored against what was published at round open. A revised
    # forecast is a second fact, not a correction of the first.
    first = parse_forecast(PAYLOAD)
    append_forecast(tmp_path, "46222", first, latitude=33.6, longitude=-118.3,
                    fetched_at="2026-09-13T13:35:00Z")
    revised = [(t, "99.9") for t, _ in first]
    result = append_forecast(tmp_path, "46222", revised, latitude=33.6, longitude=-118.3,
                             fetched_at="2026-09-14T13:35:00Z")
    assert result.added == 3
    with forecast_path(tmp_path, "46222").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 6
    assert rows[0]["sea_surface_temperature_c"] == "23.5"  # first issue intact


def test_re_archiving_the_same_issue_is_a_no_op(tmp_path):
    rows = parse_forecast(PAYLOAD)
    kwargs = dict(latitude=33.6, longitude=-118.3, fetched_at="2026-09-13T13:35:00Z")
    append_forecast(tmp_path, "46222", rows, **kwargs)
    again = append_forecast(tmp_path, "46222", rows, **kwargs)
    assert again.added == 0


def test_a_station_without_usable_coordinates_is_skipped_not_guessed(tmp_path):
    metadata = {"41001": StationMetadata(id="41001", usable=False, note="outside bounds")}
    result = collect_station(
        FAR_AWAY, tmp_path, metadata, fetched_at="2026-09-13T13:35:00Z",
        timeout=1, retries=1, dry_run=False,
        fetch=lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not fetch")),
    )
    assert not result.ok
    assert "outside bounds" in result.skipped_reason
    assert not forecast_path(tmp_path, "41001").exists()


def test_collect_station_archives_for_a_usable_station(tmp_path):
    metadata = {
        "46222": StationMetadata(id="46222", latitude=33.618, longitude=-118.317, usable=True)
    }
    result = collect_station(
        SOCAL, tmp_path, metadata, fetched_at="2026-09-13T13:35:00Z",
        timeout=1, retries=1, dry_run=False, fetch=lambda *a, **k: PAYLOAD,
    )
    assert result.ok
    assert result.added == 3


def test_dry_run_writes_nothing(tmp_path):
    metadata = {
        "46222": StationMetadata(id="46222", latitude=33.618, longitude=-118.317, usable=True)
    }
    collect_station(
        SOCAL, tmp_path, metadata, fetched_at="2026-09-13T13:35:00Z",
        timeout=1, retries=1, dry_run=True, fetch=lambda *a, **k: PAYLOAD,
    )
    assert not forecast_path(tmp_path, "46222").exists()


def test_client_errors_are_not_retried():
    import urllib.error

    attempts = {"n": 0}

    def opener(request, timeout=None):
        attempts["n"] += 1
        raise urllib.error.HTTPError(request.full_url, 400, "Bad Request", {}, None)

    with pytest.raises(ForecastError, match="HTTP 400"):
        fetch_forecast(33.6, -118.3, retries=3, sleep=lambda _: None, opener=opener)
    assert attempts["n"] == 1


def test_transient_errors_are_retried():
    attempts = {"n": 0}

    class Response:
        def read(self):
            return b'{"hourly": {"time": [], "sea_surface_temperature": []}}'

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def opener(request, timeout=None):
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise OSError("connection reset")
        return Response()

    fetch_forecast(33.6, -118.3, retries=3, sleep=lambda _: None, opener=opener)
    assert attempts["n"] == 2
