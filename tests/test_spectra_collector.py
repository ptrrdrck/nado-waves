"""Tests for the directional-spectra archive.

The rule under test is the one CLAUDE.md puts first: never infer, interpolate
or substitute a missing observation. A spectrum is five files that have to
agree, so it is the easiest place in the repository to accidentally invent data.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone

import pytest

from collector.spectra import (
    COMPONENTS,
    SpectraError,
    append_rows,
    collect_component,
    component_path,
    format_summary,
    parse_spectral,
    read_existing,
)
from collector.spectra import CollectResult, ComponentResult

FREQS = [0.0325, 0.0375, 0.0425]


def rows(*hours: int) -> list[tuple[datetime, list[float]]]:
    return [
        (datetime(2026, 9, 18, h, 40, tzinfo=timezone.utc), [1.0 + h, 2.0 + h, 3.0 + h])
        for h in hours
    ]


class TestAppendRows:
    def test_writes_header_with_the_frequency_bins(self, tmp_path):
        path = tmp_path / "c11.csv"
        added, newest = append_rows(path, FREQS, rows(0))
        assert added == 1
        header, stored = read_existing(path)
        assert header == ["0.0325", "0.0375", "0.0425"]
        assert newest == "2026-09-18T00:40:00Z"

    def test_is_append_only_and_idempotent(self, tmp_path):
        path = tmp_path / "c11.csv"
        append_rows(path, FREQS, rows(0, 1))
        added, _ = append_rows(path, FREQS, rows(0, 1, 2))
        assert added == 1
        _, stored = read_existing(path)
        assert len(stored) == 3

    def test_a_rebinned_file_is_refused_not_appended_under_the_old_header(self, tmp_path):
        """NDBC could change the bins. Writing new values under an old header
        misaligns every column, and a wrong spectrum parses perfectly."""

        path = tmp_path / "c11.csv"
        append_rows(path, FREQS, rows(0))
        with pytest.raises(SpectraError, match="frequency bins changed"):
            append_rows(path, [0.03, 0.04], [(datetime(2026, 9, 18, 2, tzinfo=timezone.utc), [1.0, 2.0])])

    def test_nothing_is_padded_to_match_the_header(self, tmp_path):
        path = tmp_path / "c11.csv"
        short = [(datetime(2026, 9, 18, 3, tzinfo=timezone.utc), [1.0])]
        append_rows(path, FREQS, short)
        with path.open() as fh:
            data = list(csv.reader(fh))[1]
        assert data == ["2026-09-18T03:00:00Z", "1"]   # short, not zero-filled


class TestComponentFetch:
    def test_a_refused_tunnel_is_classified_as_a_denial(self, tmp_path, monkeypatch):
        import urllib.error

        def boom(url, timeout=45.0):
            raise urllib.error.URLError("CONNECT tunnel failed, response 403")

        monkeypatch.setattr("collector.spectra.fetch", boom)
        result = collect_component("46232", "swden", "c11", tmp_path)
        assert result.denied and not result.ok
        assert result.added == 0

    def test_a_parsed_file_is_stored(self, tmp_path, monkeypatch):
        text = (
            "#YY  MM DD hh mm  .0325 .0375 .0425\n"
            "2026 09 18 05 40  1.11 2.22 3.33\n"
        )
        monkeypatch.setattr("collector.spectra.fetch", lambda url, timeout=45.0: text.encode())
        result = collect_component("46232", "swden", "c11", tmp_path)
        assert result.ok and result.added == 1
        assert component_path(tmp_path, "46232", "c11").exists()

    def test_an_unparseable_body_is_an_error_not_an_empty_success(self, tmp_path, monkeypatch):
        monkeypatch.setattr("collector.spectra.fetch", lambda url, timeout=45.0: b"<html>down</html>")
        result = collect_component("46232", "swden", "c11", tmp_path)
        assert not result.ok and result.added == 0


class TestSummary:
    def test_a_denial_says_so_rather_than_reporting_zero_rows(self):
        result = CollectResult("46232", [
            ComponentResult(kind=k, column=c, denied=True, error="URLError")
            for k, c in COMPONENTS.items()
        ])
        assert "Denied at CONNECT" in format_summary(result)
        assert result.denied and not result.complete

    def test_a_complete_set_is_reported_complete(self):
        result = CollectResult("46232", [
            ComponentResult(kind=k, column=c, added=1, newest="2026-09-18T05:40:00Z")
            for k, c in COMPONENTS.items()
        ])
        assert result.complete
        assert "All five components stored" in format_summary(result)

    def test_four_of_five_is_not_complete(self):
        parts = [ComponentResult(kind=k, column=c, added=1) for k, c in COMPONENTS.items()]
        parts[-1].error = "parsed no frequency bins or no rows"
        assert not CollectResult("46232", parts).complete
