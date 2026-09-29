"""GEFS-Wave's station bulletin: both of its formats, read without inventing
the columns the older one did not print."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from collector import gefswave
from collector.gfswave import BulletinError

HEAD = """
 Location : 46232      (32.530N  -117.421W)
 Model    : NCEP Global Wave Ensemble System (gefs.wave)
 Cycle    : {cycle} t00z UTC

+-------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
| day   | Hs avg | Hs spr | Tp avg | Tp spr | U10avg | U10spr | P(Hs>) | P(Hs>) | P(Hs>) | P(Hs>) | P(Hs>) | P(Hs>) |
|  hour |  (m)   |  (m)   |  (s)   |  (m)   |  (m/s) |  (m/s) |  1.00m |  2.00m | 3.00m  |  5.50m |  7.00m |  9.00m |
+-------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
"""
FULL = HEAD.format(cycle="20260930") + """\
| 30 00 |  1.49  |  0.03  | 13.10  |  1.32  |  4.58  |  1.22  |  1.00  |  1.00  |  0.00  |  0.00  |  0.00  |  0.00  |
| 30 03 |  1.50  |  0.03  | 14.90  |  1.46  |  5.50  |  1.28  |  1.00  |  0.40  |  0.00  |  0.00  |  0.00  |  0.00  |
| 01 00 |  1.88  |  0.09  | 13.20  |  0.78  |  6.49  |  0.75  |  1.00  |  1.00  |  0.25  |  0.00  |  0.00  |  0.00  |
+-------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+--------+
                                                               spr : Spread (standard deviation) of ensemble members
"""
MEANS = HEAD.format(cycle="20230101") + """\
| 01 00 |  1.57  | 13.70  |  5.21  |
| 01 03 |  1.65  | 13.60  |  8.21  |
"""


def test_the_full_format():
    got = gefswave.parse_bulletin(FULL)
    assert got.station_id == "46232" and got.longitude == -117.421 and got.latitude == 32.53
    assert got.cycle == datetime(2026, 9, 30, tzinfo=timezone.utc)
    first = got.rows[0]
    assert (first.hs_mean_m, first.hs_spread_m, first.tp_mean_s, first.u10_spread_ms) == (1.49, 0.03, 13.1, 1.22)
    assert got.rows[1].p_exceed[:3] == (1.0, 0.4, 0.0)
    # Day 01 after day 30 is the next month, 21 h later rather than a month back.
    assert got.rows[2].valid_utc == datetime(2026, 10, 1, tzinfo=timezone.utc)
    assert got.rows[2].lead_h == 24


def test_the_means_only_format_invents_nothing():
    """Before 2026-02-25 12Z the rows held three means under the same header."""

    got = gefswave.parse_bulletin(MEANS)
    row = got.rows[0]
    assert (row.hs_mean_m, row.tp_mean_s, row.u10_mean_ms) == (1.57, 13.7, 5.21)
    assert row.hs_spread_m is None and row.tp_spread_s is None and row.p_exceed == ()
    out = gefswave.csv_rows(got)[0]
    assert out["hs_spread_m"] == "" and out["p_col1"] == "" and out["hs_mean_m"] == "1.57"


def test_changed_thresholds_fail_loudly():
    with pytest.raises(BulletinError, match="thresholds"):
        gefswave.parse_bulletin(FULL.replace("2.00m", "2.50m"))


def test_a_row_of_another_width_fails_loudly():
    with pytest.raises(BulletinError, match="a row of"):
        gefswave.parse_bulletin(FULL.replace("|  0.00  |  0.00  |  0.00  |\n| 30 03", "|\n| 30 03", 1))


def test_the_archive_is_idempotent_and_keeps_the_leads_the_page_uses(tmp_path):
    got = gefswave.parse_bulletin(FULL)
    path = tmp_path / "46232.csv"
    assert gefswave.append([got], path) == 3
    assert gefswave.append([got], path) == 0
    assert gefswave.logged_cycles(path) == {"2026-09-30T00:00:00Z"}
    late = gefswave.EnsembleRow(datetime(2026, 10, 12, tzinfo=timezone.utc), 288,
                                1.0, 0.1, 10, 1, 3, 1, (1, 0, 0, 0, 0, 0))
    far = gefswave.EnsembleBulletin("46232", 0, 0, got.cycle, got.rows + (late,))
    assert len(gefswave.csv_rows(far)) == 3


def test_the_tar_is_on_the_gefs_bucket():
    url = gefswave.bulletin_tar_url(datetime(2026, 9, 28, 6, tzinfo=timezone.utc))
    assert url == ("https://noaa-gefs-pds.s3.amazonaws.com/gefs.20260928/06/wave/station/"
                   "gefs.wave.t06z.bull_tar")


def test_the_shares_are_archived_by_column_not_by_their_printed_label():
    """The column printed "2.00m" behaves as P(Hs > 1 m), measured; so the
    archive keeps positions and never files a share under a label it fails."""

    out = gefswave.csv_rows(gefswave.parse_bulletin(FULL))[1]
    assert [out[f"p_col{k}"] for k in range(1, 7)] == ["1", "0.4", "0", "0", "0", "0"]
    assert not any(name.startswith("p_hs_gt") for name in gefswave.FIELDS)
