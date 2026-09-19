"""Tests for the KNZY wind and 9410170 tide collectors.

Both hosts are denied at CONNECT from a Claude session (BRIEFING §8), so these
run entirely against fixtures. What they pin is the handling that would
otherwise only be exercised in production: missing values, the direction
convention, and — for tide — that a model is never filed as an observation.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone

import pytest

from collector import tide as tide_mod
from collector import wind as wind_mod


class TestWindParsing:
    def test_direction_is_stored_as_degrees_from(self):
        payload = json.dumps([
            {"obsTime": 1789000000, "wdir": 280, "wspd": 12, "wgst": 18, "rawOb": "KNZY ..."}
        ]).encode()
        row = wind_mod.parse(payload)[0]
        assert row["wind_from_deg"] == "280"      # FROM, never flipped
        assert row["wind_kt"] == "12"
        assert row["gust_kt"] == "18"

    def test_a_missing_gust_is_empty_not_zero(self):
        payload = json.dumps([{"obsTime": 1789000000, "wdir": 280, "wspd": 12}]).encode()
        row = wind_mod.parse(payload)[0]
        assert row["gust_kt"] == ""

    def test_a_variable_wind_is_flagged_not_stored_as_due_north(self):
        """VRB is not a bearing. Storing 0 would make a calm look northerly."""

        payload = json.dumps([{"obsTime": 1789000000, "wdir": "VRB", "wspd": 3}]).encode()
        row = wind_mod.parse(payload)[0]
        assert row["variable"] == "1"
        assert row["wind_from_deg"] == ""

    def test_rows_without_a_timestamp_are_dropped(self):
        payload = json.dumps([{"wdir": 280, "wspd": 12}]).encode()
        assert wind_mod.parse(payload) == []

    def test_non_json_is_an_error_not_an_empty_list(self):
        with pytest.raises(wind_mod.WindError):
            wind_mod.parse(b"<html>service unavailable</html>")

    def test_iso_timestamps_parse_as_well_as_epoch(self):
        payload = json.dumps([{"reportTime": "2026-09-18T05:56:00Z", "wdir": 250, "wspd": 8}]).encode()
        assert wind_mod.parse(payload)[0]["observed_utc"] == "2026-09-18T05:56:00Z"


class TestWindStorage:
    def _payload(self, *times):
        return json.dumps([
            {"obsTime": t, "wdir": 250, "wspd": 8, "rawOb": "KNZY"} for t in times
        ]).encode()

    def test_append_is_idempotent_and_keeps_first_seen(self, tmp_path, monkeypatch):
        monkeypatch.setattr(wind_mod, "fetch", lambda url, timeout=30.0: self._payload(1789000000))
        first = wind_mod.collect("KNZY", tmp_path)
        assert first.added == 1
        again = wind_mod.collect("KNZY", tmp_path)
        assert again.added == 0

        with wind_mod.wind_path(tmp_path).open() as fh:
            stored = list(csv.DictReader(fh))
        assert len(stored) == 1 and stored[0]["first_seen_utc"]

    def test_a_denial_is_classified_and_stores_nothing(self, tmp_path, monkeypatch):
        import urllib.error

        def boom(url, timeout=30.0):
            raise urllib.error.URLError("CONNECT tunnel failed, response 403")

        monkeypatch.setattr(wind_mod, "fetch", boom)
        result = wind_mod.collect("KNZY", tmp_path)
        assert result.denied and result.added == 0
        assert "Denied at CONNECT" in wind_mod.format_summary(result)


class TestTideKeepsTheModelApartFromTheMeasurement:
    OBSERVED = json.dumps({"data": [{"t": "2026-09-18 05:00", "v": "1.234"}]}).encode()
    PREDICTED = json.dumps({"predictions": [{"t": "2026-09-18 09:00", "v": "0.512"}]}).encode()

    def test_the_two_products_land_in_different_files(self, tmp_path):
        assert (tide_mod.tide_path(tmp_path, "9410170", "water_level")
                != tide_mod.tide_path(tmp_path, "9410170", "predictions"))
        assert "observed" in tide_mod.tide_path(tmp_path, "9410170", "water_level").name
        assert "predicted" in tide_mod.tide_path(tmp_path, "9410170", "predictions").name

    def test_each_row_records_which_kind_it_is(self):
        assert tide_mod.parse(self.OBSERVED, "water_level")[0]["kind"] == "observed"
        assert tide_mod.parse(self.PREDICTED, "predictions")[0]["kind"] == "predicted"

    def test_the_datum_is_recorded_not_assumed(self):
        assert tide_mod.parse(self.OBSERVED, "water_level")[0]["datum"] == "MLLW"

    def test_an_error_in_a_200_body_is_caught(self):
        """CO-OPS reports failure as HTTP 200 with an error object — the exact
        'stale content behind a 200' class BRIEFING §8 lists."""

        body = json.dumps({"error": {"message": "No data was found."}}).encode()
        with pytest.raises(tide_mod.TideError, match="200 body"):
            tide_mod.parse(body, "water_level")

    def test_a_blank_value_is_skipped_not_zero_filled(self):
        body = json.dumps({"data": [
            {"t": "2026-09-18 05:00", "v": ""},
            {"t": "2026-09-18 05:06", "v": "1.1"},
        ]}).encode()
        parsed = tide_mod.parse(body, "water_level")
        assert len(parsed) == 1 and parsed[0]["height_m"] == "1.100"

    def test_predictions_are_written_once_and_not_revisited(self, tmp_path):
        """Overwriting a prediction with a later one destroys the comparison
        that makes it worth storing at all."""

        path = tide_mod.tide_path(tmp_path, "9410170", "predictions")
        rows = tide_mod.parse(self.PREDICTED, "predictions")
        assert tide_mod.append(path, rows, seen_at="2026-09-18T06:00:00Z") == 1
        assert tide_mod.append(path, rows, seen_at="2026-09-18T12:00:00Z") == 0

    def test_url_carries_the_datum_units_and_gmt(self):
        url = tide_mod.build_url(
            "9410170", "predictions",
            begin=datetime(2026, 9, 18, tzinfo=timezone.utc),
            end=datetime(2026, 9, 22, tzinfo=timezone.utc),
            interval="h",
        )
        assert "datum=MLLW" in url and "units=metric" in url
        assert "time_zone=gmt" in url and "interval=h" in url


class TestTheTideTurns:
    """CO-OPS computes the high and low water times from the constituents.
    Deriving them from the hourly prediction grid instead puts the time 14.5
    minutes out on average and up to 29.4 (measured, 32 extrema in the
    archive), while the height barely moves — so the hourly file can say how
    high the next high water is and not when, and when is the half anyone
    plans around."""

    HILO = json.dumps({"predictions": [
        {"t": "2026-09-19 11:42", "v": "1.712", "type": "H"},
        {"t": "2026-09-19 18:06", "v": "0.134", "type": "L"},
    ]}).encode()

    def test_the_turns_land_in_their_own_file(self, tmp_path):
        path = tide_mod.tide_path(tmp_path, "9410170", "turns")
        assert "turns" in path.name
        assert path != tide_mod.tide_path(tmp_path, "9410170", "predictions")

    def test_it_asks_co_ops_for_hilo_not_an_interval(self):
        assert tide_mod.REQUESTS["turns"] == ("predictions", "hilo")
        assert tide_mod.api_product("turns") == "predictions"

    def test_a_turn_records_which_way_the_tide_is_going(self):
        rows = tide_mod.parse(self.HILO, "turns")
        assert [r["event"] for r in rows] == ["high", "low"]

    def test_a_turn_is_still_the_same_harmonic_model(self):
        """Not a third kind of thing — the same prediction, reported at its own
        turning points instead of on a clock."""

        assert {r["kind"] for r in tide_mod.parse(self.HILO, "turns")} == {"predicted"}

    def test_an_unlabelled_hilo_row_is_dropped_not_guessed(self):
        """A turning point that cannot say which way the tide is going is a
        number, not a turn."""

        body = json.dumps({"predictions": [
            {"t": "2026-09-19 11:42", "v": "1.712", "type": ""},
            {"t": "2026-09-19 18:06", "v": "0.134", "type": "L"},
        ]}).encode()
        rows = tide_mod.parse(body, "turns")
        assert len(rows) == 1 and rows[0]["event"] == "low"

    def test_an_unknown_label_is_kept_verbatim_not_mapped(self):
        """CO-OPS emits HH and LL at some stations. Forcing one of those into
        'high' or 'low' would be inventing a claim; the reader names it or
        nothing does."""

        body = json.dumps({"predictions": [
            {"t": "2026-09-19 11:42", "v": "1.712", "type": "HH"},
        ]}).encode()
        assert tide_mod.parse(body, "turns")[0]["event"] == "hh"

    def test_the_older_files_are_not_widened_to_match(self, tmp_path):
        """The observed and predicted CSVs are already written and have five
        columns. Appending a six-column row to them would misalign every row
        after it."""

        assert "event" not in tide_mod.fields_for("predictions")
        assert "event" in tide_mod.fields_for("turns")

        path = tide_mod.tide_path(tmp_path, "9410170", "turns")
        tide_mod.append(path, tide_mod.parse(self.HILO, "turns"),
                        seen_at="2026-09-19T06:00:00Z", fields=tide_mod.TURN_FIELDS)
        header = path.read_text().splitlines()[0]
        assert header.endswith("event")
        assert len(path.read_text().splitlines()[1].split(",")) == len(header.split(","))

    def test_all_three_products_are_collected(self):
        import inspect
        source = inspect.getsource(tide_mod.collect)
        for product in ("water_level", "predictions", "turns"):
            assert f'"{product}"' in source
