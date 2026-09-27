"""Bias against exposure: the arithmetic that separates a shadow from an offset."""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from collector.gfswave_backfill import FIELDS
from forecast.exposurebias import MIN_CELL, bias, hours, report, shadow

UTC = timezone.utc
START = datetime(2024, 1, 1, tzinfo=UTC)
DAYS = MIN_CELL + 10


def write_forecasts(path: Path, heights: dict[datetime, float], lead: int = 0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for valid, hs in sorted(heights.items()):
            writer.writerow({
                "cycle_utc": (valid - timedelta(hours=lead)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "valid_utc": valid.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "lead_h": lead, "hs_total_m": f"{hs:.2f}", "n_fields": 1, "n_omitted": 0,
                "part_rank": "", "part_hs_m": "", "part_tp_s": "", "part_from_deg": "",
                "wind_sea": "",
            })


def write_buoy(path: Path, values: dict[datetime, tuple[float, float, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp_utc", "wtmp", "wvht", "dpd", "mwd", "atmp", "wspd", "wdir"])
        for stamp, (wvht, dpd, mwd) in sorted(values.items()):
            # CDIP-style :26 stamps, to prove the match window is used.
            stamp = stamp + timedelta(minutes=26)
            writer.writerow([stamp.strftime("%Y-%m-%dT%H:%M:%SZ"), "", wvht, dpd, mwd, "", "", ""])


def build(tmp_path: Path, station_model: float, *, station_from: float = 210.0,
          ref_from: float = 210.0, drop: int | None = None) -> Path:
    """46047 sees 2.0 m; the station's buoy sees 1.0 m, a measured shadow of 0.5."""

    days = [START + timedelta(days=d) for d in range(DAYS)]
    write_forecasts(tmp_path / "wave_forecasts" / "46047.csv", {d: 2.0 for d in days})
    write_forecasts(tmp_path / "wave_forecasts" / "46232.csv", {d: station_model for d in days})
    write_buoy(tmp_path / "historical" / "46047.csv", {d: (2.0, 14.0, ref_from) for d in days})
    write_buoy(tmp_path / "historical" / "46232.csv", {
        d: (1.0, 14.0, station_from) for i, d in enumerate(days) if i != drop
    })
    return tmp_path


def test_a_model_with_the_shadow_right_agrees_and_has_no_bias(tmp_path):
    sample = hours(build(tmp_path, station_model=1.0), "46232", 0)
    assert len(sample) == DAYS
    stats = shadow(sample)
    assert stats["measured"] == pytest.approx(0.5)
    assert stats["modelled"] == pytest.approx(0.5)
    assert stats["agreement"] == pytest.approx(1.0)
    assert bias(sample)["bias_m"] == pytest.approx(0.0)


def test_a_smooth_ocean_model_lets_the_shadow_through(tmp_path):
    """A model blind to the islands reads the reference's height at the station:
    the model's ratio stays at 1 while the buoys' is 0.5, and it runs HIGH."""

    sample = hours(build(tmp_path, station_model=2.0), "46232", 0)
    assert shadow(sample)["agreement"] == pytest.approx(2.0)
    assert bias(sample)["bias_m"] == pytest.approx(+1.0)


def test_a_model_that_over_shadows_reads_low_and_below_one(tmp_path):
    sample = hours(build(tmp_path, station_model=0.75), "46232", 0)
    assert shadow(sample)["agreement"] == pytest.approx(0.75)
    stats = bias(sample)
    assert stats["bias_m"] == pytest.approx(-0.25)          # negative is LOW
    assert stats["relative"] == pytest.approx(-0.25)


def test_the_sector_is_read_at_the_reference_not_at_the_station(tmp_path):
    """The station's own direction has been bent by whatever shadows it."""

    sample = hours(build(tmp_path, 1.0, station_from=300.0, ref_from=210.0), "46232", 0)
    assert {h.sector for h in sample} == {"SW"}


def test_a_missing_observation_drops_the_hour_and_is_never_filled(tmp_path):
    sample = hours(build(tmp_path, 1.0, drop=3), "46232", 0)
    assert len(sample) == DAYS - 1
    assert START + timedelta(days=3) not in {h.valid for h in sample}


def test_short_period_hours_are_not_swell_hours(tmp_path):
    path = build(tmp_path, 1.0)
    days = [START + timedelta(days=d) for d in range(DAYS)]
    write_buoy(path / "historical" / "46047.csv", {d: (2.0, 8.0, 210.0) for d in days})
    assert not any(h.swell for h in hours(path, "46232", 0))


def test_a_thin_cell_says_so_rather_than_quoting_a_median(tmp_path):
    sample = hours(build(tmp_path, 1.0), "46232", 0)[: MIN_CELL - 1]
    assert "measured" not in shadow(sample)


def test_the_report_runs_end_to_end_and_names_the_reference(tmp_path):
    lines = report(build(tmp_path, 0.75), ("46047", "46232"), 0)
    text = "\n".join(lines)
    assert "Reference 46047" in text
    assert "### 46232" in text and "### 46047" not in text
    assert any(line.startswith("SW ") and "0.75" in line for line in lines)


def test_a_station_with_no_archived_cycles_says_so(tmp_path):
    text = "\n".join(report(build(tmp_path, 1.0), ("46047", "46232", "46086"), 0))
    assert "46086   |     0 |   (no pairs: archive the cycles)" in text
