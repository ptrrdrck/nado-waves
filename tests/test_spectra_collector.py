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


class TestContextStations:
    """Three buoys archived for checks. None is a stand-in for the anchor."""

    def test_the_anchor_is_not_a_context_station(self):
        from collector.spectra import CONTEXT_STATIONS, DEFAULT_STATION

        assert DEFAULT_STATION not in CONTEXT_STATIONS
        assert set(CONTEXT_STATIONS) == {"46086", "46047", "46258"}

    def test_every_context_station_is_in_the_registry(self):
        import json
        from pathlib import Path

        from collector.spectra import CONTEXT_STATIONS

        registry = Path(__file__).resolve().parent.parent / "collector" / "stations.json"
        ids = {s["id"] for s in json.loads(registry.read_text())["stations"]}
        assert set(CONTEXT_STATIONS) <= ids

    def test_nothing_on_the_forecast_path_reads_a_context_station(self):
        """The Now tab and the forecast read 46232's spectrum and nothing else.
        A context buoy wired in there is §3a's substitution, done quietly."""

        from pathlib import Path

        from collector.spectra import CONTEXT_STATIONS

        forecast = Path(__file__).resolve().parent.parent / "forecast"
        for name in ("now.py", "live.py", "measured.py", "nearshore.py",
                     "surfzone.py", "transform.py", "publish.py"):
            text = (forecast / name).read_text()
            for station in CONTEXT_STATIONS:
                assert station not in text, f"{name} names {station}"


def complete(station: str) -> CollectResult:
    return CollectResult(station, [
        ComponentResult(kind=k, column=c, added=1) for k, c in COMPONENTS.items()
    ])


def denied(station: str) -> CollectResult:
    return CollectResult(station, [
        ComponentResult(kind=k, column=c, denied=True, error="URLError")
        for k, c in COMPONENTS.items()
    ])


def incomplete(station: str) -> CollectResult:
    result = complete(station)
    result.components[0].error = "parsed no frequency bins or no rows"
    return result


class TestSeveralStations:
    def test_context_collects_each_context_station(self, tmp_path, monkeypatch):
        from collector.spectra import CONTEXT_STATIONS, main

        seen = []
        monkeypatch.setattr("collector.spectra.collect",
                            lambda station, data_dir: seen.append(station) or complete(station))
        assert main(["--context", "--data-dir", str(tmp_path)]) == 0
        assert seen == ["46258"] and set(seen) < set(CONTEXT_STATIONS)

    def test_hourly_collects_both_witnesses_and_context_does_not(self, tmp_path, monkeypatch):
        """Each file has one writer: 46047 and 46086 hourly, 46258 on
        collect.yml. `--bearing` is the old name and still does the same."""

        from collector.spectra import HOURLY_STATIONS, main

        seen = []
        monkeypatch.setattr("collector.spectra.collect",
                            lambda station, data_dir: seen.append(station) or complete(station))
        assert main(["--hourly", "--data-dir", str(tmp_path)]) == 0
        assert seen == ["46047", "46086"] == list(HOURLY_STATIONS)
        seen.clear()
        assert main(["--bearing", "--data-dir", str(tmp_path)]) == 0
        assert seen == list(HOURLY_STATIONS)
        seen.clear()
        main(["--context", "--data-dir", str(tmp_path)])
        assert not set(seen) & set(HOURLY_STATIONS)

    def test_every_reader_of_a_context_buoy_is_served_hourly(self):
        """Origin and the hurricane gate read these within the hour. A reader
        that drops a buoy (Origin dropped 46086 on 2026-10-05, BRIEFING §38)
        must never take its collection with it: the hourly list is held to
        the union of its readers, not to any one of them."""

        from collector.spectra import HOURLY_STATIONS
        from forecast.origin import BEARING_STATIONS
        from forecast.stormtrack import GATE_STATIONS

        assert set(BEARING_STATIONS) | set(GATE_STATIONS) <= set(HOURLY_STATIONS)
        assert "46086" in HOURLY_STATIONS

    def test_every_buoy_any_report_reads_is_collected(self):
        """Directional data at every buoy keeps flowing: 46232 by default,
        the hourly two, and the rest of the context list on collect.yml."""

        from collector.spectra import CONTEXT_STATIONS, DEFAULT_STATION, HOURLY_STATIONS
        from forecast.nwbearing import REFERENCE, STATIONS as NW
        from forecast.stormtrack import STATIONS as STORM

        collected = {DEFAULT_STATION} | set(HOURLY_STATIONS) | set(CONTEXT_STATIONS)
        assert set(NW) | {REFERENCE} | set(STORM) <= collected
        assert collected == {"46232", "46047", "46086", "46258"}

    def test_the_workflows_split_them(self):
        from pathlib import Path

        flows = Path(__file__).resolve().parent.parent / ".github" / "workflows"
        beach = (flows / "collect-beach-inputs.yml").read_text()
        assert "collector.spectra --hourly" in beach
        assert 'collector.spectra --station "${STATION:-46232}"' in beach
        collect = (flows / "collect.yml").read_text()
        assert "collector.spectra --context" in collect
        assert "--hourly" not in collect and "--bearing" not in collect

    def test_a_comma_list_is_several_stations(self, tmp_path, monkeypatch):
        from collector.spectra import main

        seen = []
        monkeypatch.setattr("collector.spectra.collect",
                            lambda station, data_dir: seen.append(station) or complete(station))
        main(["--station", "46086, 46047", "--data-dir", str(tmp_path)])
        assert seen == ["46086", "46047"]

    def test_one_failure_is_not_hidden_by_the_others_succeeding(self, tmp_path, monkeypatch):
        """And the stations after it are still fetched."""

        from collector.spectra import main

        seen = []
        results = {"46086": incomplete, "46047": complete, "46258": complete}
        monkeypatch.setattr("collector.spectra.collect",
                            lambda station, data_dir: seen.append(station) or results[station](station))
        assert main(["--station", "46086,46047,46258", "--data-dir", str(tmp_path)]) == 1
        assert seen == ["46086", "46047", "46258"]

    def test_a_denial_outranks_an_incomplete_set(self):
        from collector.spectra import exit_code

        assert exit_code([incomplete("46086"), denied("46047"), complete("46258")]) == 2
        assert exit_code([complete("46086"), complete("46047")]) == 0


class TestSentinels:
    """NDBC's 999 in a direction or moment file is a gap, never a value."""

    PAYLOAD = (
        "#YY  MM DD hh mm r1_1 (freq_1) r1_2 (freq_2) r1_3 (freq_3) ... >\n"
        "2026 09 27 05 20 999.00 (0.033) 0.29 (0.053) 0.11 (0.058)\n"
    )

    def test_a_999_moment_is_stored_as_an_empty_cell(self, tmp_path, monkeypatch):
        monkeypatch.setattr("collector.spectra.fetch", lambda url, timeout=45.0: self.PAYLOAD.encode())
        result = collect_component("46047", "swr1", "r1", tmp_path)
        assert result.ok and result.added == 1
        with component_path(tmp_path, "46047", "r1").open() as fh:
            row = list(csv.reader(fh))[1]
        assert row == ["2026-09-27T05:20:00Z", "", "0.29", "0.11"]

    def test_the_gap_reads_back_as_nan_not_999(self, tmp_path, monkeypatch):
        import math

        from forecast.transform import load_spectra

        # As 46047 publishes it: no energy in the bins it has no direction for.
        energy = self.PAYLOAD.replace("999.00 (0.033)", "0.000 (0.033)")
        for kind, column in COMPONENTS.items():
            text = energy if kind == "swden" else self.PAYLOAD
            monkeypatch.setattr("collector.spectra.fetch", lambda url, timeout=45.0, t=text: t.encode())
            collect_component("46047", kind, column, tmp_path)
        spectrum = load_spectra(tmp_path / "spectra" / "46047")[0]
        assert math.isnan(spectrum.r1[0]) and math.isnan(spectrum.a1[0])
        assert spectrum.r1[1:] == [0.29, 0.11]

    def test_999_energy_density_is_stored_as_a_value(self, tmp_path, monkeypatch):
        """C11 has no bound that makes 999 impossible, so it is not masked."""

        monkeypatch.setattr("collector.spectra.fetch", lambda url, timeout=45.0: self.PAYLOAD.encode())
        collect_component("46047", "swden", "c11", tmp_path)
        with component_path(tmp_path, "46047", "c11").open() as fh:
            assert list(csv.reader(fh))[1][1] == "999"
