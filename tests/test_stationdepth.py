"""Each shown buoy's water depth off NDBC's station page (`collector.stationdepth`)."""

from __future__ import annotations

import json

import pytest

from collector import stationdepth


def test_it_reads_the_lines_the_live_pages_carry():
    """The three forms the probe read on 2026-11-10, inside the page's markup."""

    assert stationdepth.parse("<b>Water depth:</b> 1049.8 m<br>") == (1049.8, "Water depth: 1049.8 m")
    assert stationdepth.parse("<td>Water depth: 1862 m</td>")[0] == 1862.0
    assert stationdepth.parse("Site elevation: sea level<br><b>Water depth:</b>\n 1,390 m")[0] == 1390.0


def test_no_line_or_two_depths_or_a_wild_one_is_refused():
    with pytest.raises(stationdepth.DepthError):
        stationdepth.parse("<b>Site elevation:</b> sea level")
    with pytest.raises(stationdepth.DepthError):
        stationdepth.parse("Water depth: 1390 m ... Water depth: 1400 m")
    with pytest.raises(stationdepth.DepthError):
        stationdepth.parse("Water depth: 0.2 m")


def test_a_failed_read_keeps_the_stored_record(tmp_path):
    pages = {"46232": "Water depth: 1049.8 m", "46086": "Water depth: 1862 m", "46047": "Water depth: 1390 m"}
    stationdepth.collect(data_dir=tmp_path, fetcher=pages.__getitem__)

    def broken(station):
        raise OSError("refused")

    stored, problems = stationdepth.collect(data_dir=tmp_path, fetcher=broken)
    assert {s: r["depth_m"] for s, r in stored.items()} == {"46232": 1049.8, "46086": 1862.0, "46047": 1390.0}
    assert len(problems) == 3
    on_disk = json.loads((tmp_path / "station_depth.json").read_text())
    assert on_disk["46047"]["read"] == "Water depth: 1390 m"


def test_a_young_record_is_not_fetched_again(tmp_path):
    stationdepth.collect(data_dir=tmp_path, fetcher=lambda s: "Water depth: 1390 m")

    def never(station):
        raise AssertionError("fetched a record younger than the limit")

    stationdepth.collect(data_dir=tmp_path, max_age_days=30, fetcher=never)


def test_it_reads_the_buoys_the_tab_shows():
    from forecast import buoys

    assert stationdepth.STATIONS == (buoys.ANCHOR, *buoys.STATIONS)
