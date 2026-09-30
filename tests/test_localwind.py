"""The local wind forecast at the beach: read from the NWS grid without
filling an hour it did not give, and carried onto each break's forecast hour
with what it means against that break's own shore normal."""

from __future__ import annotations

import io
import json
import urllib.error

import pytest

from collector import localwind
from collector.localwind import LocalWindError

GRID = {"properties": {
    "updateTime": "2026-09-30T04:12:00+00:00",
    "windDirection": {"uom": "wmoUnit:degree_(angle)", "values": [
        {"validTime": "2026-09-30T05:00:00+00:00/PT2H", "value": 290},
        {"validTime": "2026-09-30T07:00:00+00:00/PT1H", "value": 300},
        {"validTime": "2026-09-30T08:00:00+00:00/PT1H", "value": None}]},
    "windSpeed": {"uom": "wmoUnit:km_h-1", "values": [
        {"validTime": "2026-09-30T05:00:00+00:00/PT3H", "value": 18.52},
        {"validTime": "2026-09-30T08:00:00+00:00/PT1H", "value": 9.26}]},
    "windGust": {"uom": "wmoUnit:km_h-1", "values": [
        {"validTime": "2026-09-30T06:00:00+00:00/PT1H", "value": 27.78}]},
}}


def test_intervals_become_hours_and_kmh_becomes_knots():
    got = localwind.parse_grid(GRID)
    assert got["updated_utc"] == "2026-09-30T04:12:00Z"
    assert [h["valid_utc"][11:13] for h in got["hours"]] == ["05", "06", "07"]
    assert got["hours"][0] == {"valid_utc": "2026-09-30T05:00:00Z", "from_deg": 290,
                               "speed_kt": 10.0, "gust_kt": None}
    assert got["hours"][1]["gust_kt"] == 15.0


def test_an_hour_without_a_direction_is_left_out_not_filled():
    # 08Z has a speed but its direction is null: no hour, not 07Z's bearing.
    assert "2026-09-30T08:00:00Z" not in {h["valid_utc"] for h in localwind.parse_grid(GRID)["hours"]}


def test_a_unit_it_does_not_know_is_refused():
    odd = json.loads(json.dumps(GRID))
    odd["properties"]["windSpeed"]["uom"] = "wmoUnit:mi_h-1"
    with pytest.raises(LocalWindError, match="not a unit"):
        localwind.parse_grid(odd)


def test_fetch_follows_the_point_to_its_grid_cell():
    asked = []

    def opener(request, timeout):
        asked.append(request.full_url)
        body = ({"properties": {"gridId": "SGX", "gridX": 55, "gridY": 12,
                                "forecastGridData": "https://api.weather.gov/gridpoints/SGX/55,12"}}
                if "/points/" in request.full_url else GRID)
        return io.BytesIO(json.dumps(body).encode())

    got = localwind.fetch(32.6822, -117.1853, opener=opener)
    assert asked == ["https://api.weather.gov/points/32.6822,-117.1853",
                     "https://api.weather.gov/gridpoints/SGX/55,12"]
    assert (got["office"], got["grid_x"], got["grid_y"]) == ("SGX", 55, 12)
    assert len(got["hours"]) == 3


def test_a_denied_host_is_an_error_not_an_empty_forecast():
    def opener(request, timeout):
        raise urllib.error.URLError("Tunnel connection failed: 403")

    with pytest.raises(LocalWindError, match="403"):
        localwind.fetch(32.68, -117.18, opener=opener)
