"""Forecast verification: the arithmetic that decides whether a band is honest."""

from __future__ import annotations

import csv
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from collector.gfswave_backfill import FIELDS
from forecast.verify import (
    ForecastPoint,
    Pair,
    calibrate_and_test,
    error_stats,
    fit_correction,
    load_forecasts,
    pair_up,
    quantile,
    wobble,
)

UTC = timezone.utc


def point(valid: datetime, lead: int, hs: float, partitions=()) -> ForecastPoint:
    return ForecastPoint(
        cycle=valid - timedelta(hours=lead),
        valid=valid,
        lead_h=lead,
        hs_total_m=hs,
        partitions=tuple(partitions),
    )


def write_archive(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_observations(path: Path, values: dict[datetime, tuple]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp_utc", "wtmp", "wvht", "dpd", "mwd", "atmp", "wspd", "wdir"])
        for stamp, (wvht, dpd, mwd) in sorted(values.items()):
            writer.writerow([stamp.strftime("%Y-%m-%dT%H:%M:%SZ"), "", wvht, dpd, mwd, "", "", ""])


def test_south_partitions_add_in_energy_not_height():
    """Two 2 m trains make a 2.83 m sea, not a 4 m one."""

    row = point(
        datetime(2025, 7, 1, tzinfo=UTC),
        24,
        3.0,
        [(2.0, 17.0, 200, False), (2.0, 15.0, 190, False), (1.0, 5.0, 280, False)],
    )
    assert row.south_hs() == pytest.approx(math.sqrt(8.0))


def test_south_window_needs_both_direction_and_period():
    row = point(
        datetime(2025, 7, 1, tzinfo=UTC),
        24,
        2.0,
        [
            (1.0, 16.0, 285, False),  # long period, wrong quadrant
            (1.0, 9.0, 195, False),   # right quadrant, too short to be a south swell
        ],
    )
    assert row.south_hs() == pytest.approx(0.0)


def test_observations_are_matched_not_interpolated(tmp_path):
    """A gap in the buoy record must shrink the sample, never be filled."""

    valid = datetime(2025, 7, 1, 12, tzinfo=UTC)
    write_archive(
        tmp_path / "wave_forecasts" / "99999.csv",
        [
            {
                "cycle_utc": (valid - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "valid_utc": valid.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "lead_h": 24, "hs_total_m": "1.00", "n_fields": 1, "n_omitted": 0,
                "part_rank": 0, "part_hs_m": "1.00", "part_tp_s": "16.0",
                "part_from_deg": 200, "wind_sea": "0",
            }
        ],
    )
    points = load_forecasts(tmp_path / "wave_forecasts" / "99999.csv")

    # Buoy reported 90 minutes away — outside the match window, so no pair.
    write_observations(
        tmp_path / "historical" / "99999.csv",
        {valid + timedelta(minutes=90): ("1.40", "16.0", "200")},
    )
    assert pair_up(points, tmp_path, "99999") == []

    # Twenty-six minutes away is the CDIP reporting offset, and does pair.
    write_observations(
        tmp_path / "historical" / "99999.csv",
        {valid + timedelta(minutes=26): ("1.40", "16.0", "200")},
    )
    pairs = pair_up(points, tmp_path, "99999")
    assert [(p.forecast, p.observed) for p in pairs] == [(1.0, 1.4)]


def test_south_sample_keeps_totals_on_both_sides(tmp_path):
    """"south" narrows the sample, it does not swap in a partition height.

    Comparing the forecast's south partitions against the buoy's single total
    height once produced a -0.65 m "bias" that was really the windsea the buoy
    could see and the partition sum could not.
    """

    valid = datetime(2025, 7, 1, 12, tzinfo=UTC)
    rows = []
    for offset, (hs, dpd, mwd) in enumerate(
        [("1.40", "16.0", "200"), ("1.40", "8.0", "200"), ("1.40", "16.0", "285")]
    ):
        moment = valid + timedelta(days=offset)
        rows.append({
            "cycle_utc": (moment - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "valid_utc": moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "lead_h": 24, "hs_total_m": "1.00", "n_fields": 1, "n_omitted": 0,
            "part_rank": 0, "part_hs_m": "0.40", "part_tp_s": "16.0",
            "part_from_deg": 200, "wind_sea": "0",
        })
    write_archive(tmp_path / "wave_forecasts" / "99999.csv", rows)
    write_observations(
        tmp_path / "historical" / "99999.csv",
        {
            valid + timedelta(days=i, minutes=26): v
            for i, v in enumerate(
                [("1.40", "16.0", "200"), ("1.40", "8.0", "200"), ("1.40", "16.0", "285")]
            )
        },
    )
    points = load_forecasts(tmp_path / "wave_forecasts" / "99999.csv")

    assert len(pair_up(points, tmp_path, "99999", "total")) == 3
    south = pair_up(points, tmp_path, "99999", "south")
    assert len(south) == 1  # only the long-period southern hour survives
    assert south[0].forecast == 1.0  # ...still the TOTAL, not the 0.40 partition


def test_error_stats_report_scatter_against_the_sea_state():
    valid = datetime(2025, 7, 1, tzinfo=UTC)
    pairs = [
        Pair(valid + timedelta(days=i), 24, forecast, observed)
        for i, (forecast, observed) in enumerate([(1.0, 2.0), (3.0, 4.0), (2.0, 3.0)])
    ]
    stats = error_stats(pairs)
    assert stats["bias_m"] == pytest.approx(-1.0)
    assert stats["rmse_m"] == pytest.approx(1.0)
    # Every error is exactly -1, so the SPREAD is zero even though RMSE is not.
    assert stats["sd_m"] == pytest.approx(0.0)
    assert stats["scatter_index"] == pytest.approx(0.0)


def test_correction_recovers_a_planted_offset_and_gain():
    valid = datetime(2025, 7, 1, tzinfo=UTC)
    pairs = [
        Pair(valid + timedelta(days=i), 24, f, 0.3 + 1.2 * f)
        for i, f in enumerate([0.5, 1.0, 1.5, 2.0, 2.5])
    ]
    intercept, slope = fit_correction(pairs)
    assert intercept == pytest.approx(0.3, abs=1e-6)
    assert slope == pytest.approx(1.2, abs=1e-6)


def test_calibration_is_tested_out_of_sample():
    """Fitting and scoring on the same year is how a useless model looks good."""

    def series(year, noise):
        return [
            Pair(
                datetime(year, 1, 1, tzinfo=UTC) + timedelta(days=i),
                24,
                1.0 + (i % 10) * 0.1,
                0.4 + 1.0 * (1.0 + (i % 10) * 0.1) + noise[i % len(noise)],
            )
            for i in range(200)
        ]

    pairs = series(2023, [0.05, -0.05, 0.0]) + series(2025, [0.05, -0.05, 0.0])
    result = calibrate_and_test(pairs, (2023,), (2025,))
    assert result["n_train"] == 200 and result["n_test"] == 200
    assert result["intercept_m"] == pytest.approx(0.4, abs=0.02)
    # The planted 0.4 m offset is most of the raw error, so removing it helps.
    assert result["rmse_calibrated_m"] < result["rmse_raw_m"] / 4
    assert 0.6 <= result["coverage"][0.70]["actual"] <= 1.0


def test_wobble_measures_step_and_cumulative_drift():
    valid = datetime(2025, 7, 5, tzinfo=UTC)
    points = [point(valid, lead, hs) for lead, hs in [(24, 1.0), (48, 1.2), (72, 1.5)]]
    result = wobble(points)
    assert result[48]["mean_shift_m"] == pytest.approx(0.2)
    assert result[72]["mean_shift_m"] == pytest.approx(0.3)
    # Drift is measured back to the +24h call, not step by step: the 72h
    # forecast was 0.5 m away from what the model finally settled on.
    assert result[72]["mean_drift_m"] == pytest.approx(0.5)
    assert result[48]["mean_drift_m"] == pytest.approx(0.2)


def test_quantile_interpolates_between_order_statistics():
    assert quantile([1.0, 2.0, 3.0, 4.0], 0.5) == pytest.approx(2.5)
    assert quantile([1.0, 2.0, 3.0, 4.0], 0.0) == 1.0
    assert quantile([1.0, 2.0, 3.0, 4.0], 1.0) == 4.0


def test_revision_sign_says_which_way_the_model_moved():
    """Absolute drift says how far; only the sign says whether it filled in."""

    valid = datetime(2025, 7, 5, tzinfo=UTC)
    # The model talked itself DOWN: the ten-day call was the biggest.
    points = [point(valid, lead, hs) for lead, hs in [(24, 1.0), (48, 1.2), (72, 1.5)]]
    result = wobble(points)
    assert result[72]["mean_drift_m"] == pytest.approx(0.5)   # magnitude only
    assert result[72]["mean_revision_m"] == pytest.approx(-0.5)
    assert result[72]["share_revised_up"] == 0.0

    # ...and the mirror image, where it filled in late.
    rising = [point(valid, lead, hs) for lead, hs in [(24, 1.5), (48, 1.2), (72, 1.0)]]
    mirrored = wobble(rising)
    assert mirrored[72]["mean_drift_m"] == pytest.approx(0.5)  # identical
    assert mirrored[72]["mean_revision_m"] == pytest.approx(+0.5)
    assert mirrored[72]["share_revised_up"] == 1.0


def test_wobble_can_be_restricted_without_seeing_observations():
    """A caller may narrow the moments; wobble still never reads a buoy."""

    keep = datetime(2025, 7, 5, tzinfo=UTC)
    drop = datetime(2025, 7, 6, tzinfo=UTC)
    points = [point(keep, 24, 1.0), point(keep, 48, 1.2),
              point(drop, 24, 3.0), point(drop, 48, 1.0)]
    assert wobble(points)[48]["n"] == 2
    narrowed = wobble(points, only={keep})
    assert narrowed[48]["n"] == 1
    assert narrowed[48]["mean_revision_m"] == pytest.approx(-0.2)
