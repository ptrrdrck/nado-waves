"""collector.nearshore_census, offline: NDBC and CDIP are refused from a session
(BRIEFING §8), so every response here is a fixture in the form each serves."""

from __future__ import annotations

import json

from collector import mop
from collector import nearshore_census as nc

LISTING = """<html><body><pre>
<a href="46235w2019.txt.gz">46235w2019.txt.gz</a>  2020-01-10 12:00  210K
<a href="46235w2020.txt.gz">46235w2020.txt.gz</a>
<a href="46235w2021.txt.gz">46235w2021.txt.gz</a>
<a href="46232w2020.txt.gz">46232w2020.txt.gz</a>
<a href="46232w2021.txt.gz">46232w2021.txt.gz</a>
<a href="4623520w2019.txt.gz">not a station file</a>
</pre></body></html>"""

META_XML = """<?xml version="1.0"?>
<stationmetadata>
 <station id="46235" name="Imperial Beach Nearshore, CA (155)" owner="CDIP" pgm="IOOS Partners" type="buoy">
  <history start="2019-01-01" stop="2021-06-30" lat="32.570" lng="-117.169" met="n" hull="WR"/>
 </station>
 <station id="46225" name="Torrey Pines Outer, CA (100)" owner="CDIP" type="buoy">
  <history start="2004-01-01" lat="32.933" lng="-117.391"/>
 </station>
 <station id="46232" name="Point Loma South, CA (191)" owner="CDIP" type="buoy">
  <history start="2009-01-01" lat="32.517" lng="-117.425"/>
 </station>
</stationmetadata>"""

PAGE = """<html><b>Imperial Beach Nearshore, CA (155)</b><br>
<b>32.570 N 117.169 W (32&#176;34'12" N 117&#176;10'8" W)</b><br>
<b>Water depth:</b> 18.9 m<br></html>"""


def listing(letter: str) -> str:
    return LISTING.replace("w20", f"{letter}20").replace("w2019", f"{letter}2019")


def test_historical_listing_keeps_only_station_files():
    got = nc.parse_historical(LISTING)
    assert got == {"46235": {"w": [2019, 2020, 2021]}, "46232": {"w": [2020, 2021]}}


def test_directional_years_need_all_five_files():
    kinds = {"w": [2019, 2020, 2021], "d": [2019, 2020, 2021], "i": [2020, 2021],
             "j": [2020, 2021], "k": [2021]}
    assert nc.directional_years(kinds) == [2021]
    assert nc.directional_years({"w": [2020]}) == []      # density alone is not directional


def test_station_metadata_positions_and_history():
    got = nc.parse_station_metadata(META_XML)
    assert got["46235"]["positions"] == [(32.57, -117.169, "2019-01-01", "2021-06-30")]
    assert got["46225"]["owner"] == "CDIP"


def test_station_page_position_and_depth():
    got = nc.parse_page(PAGE)
    assert got["position"] == (32.57, -117.169)
    assert got["water_depth_m"] == 18.9


def test_grids_from_the_chains_own_bounds():
    bounds = nc.grid_bounds()
    assert set(bounds) == set(nc.GRIDS)
    assert nc.grids_covering(32.5785, -117.140, bounds) == ["regional", "outer"]   # Imperial Beach
    assert nc.grids_covering(32.6822, -117.1853, bounds) == list(nc.GRIDS)         # Coronado Center
    assert nc.grids_covering(34.0, -120.0, bounds) == []                           # Santa Barbara Channel


def test_span_reads_runs():
    assert nc.span([2009, 2010, 2011, 2014, 2016, 2017]) == "2009–2011, 2014, 2016–2017"
    assert nc.span([]) == "none"


def test_census_end_to_end(monkeypatch):
    """Every fetch a fixture: the station is placed, gets the CDIP and MOP
    lookups, its overlap with 46232 is the intersection, and a failed request
    is reported, never guessed past."""

    ndbc = {nc.STATION_TABLE_URL: "# STATION_ID | OWNER | TTYPE | HULL | NAME | PAYLOAD | LOCATION | TIMEZONE | FORECAST | NOTE\n"
                                  "46232|CDIP|Waverider|WR|Point Loma South, CA (191)||32.517 N 117.425 W (x)|P||\n",
            nc.STATION_META_URL: META_XML,
            nc.STATION_PAGE_URL.format(sid="46235"): PAGE}
    for kind, letter in nc.KINDS.items():
        ndbc[nc.HISTORICAL_URL.format(kind=kind)] = listing(letter)

    def get(url, timeout=60.0):
        if url not in ndbc:
            raise OSError(f"no fixture for {url}")
        return ndbc[url]

    catalog = """<catalog xmlns:xlink="http://www.w3.org/1999/xlink">
      <dataset name="D0052_nowcast.nc" urlPath="cdip/model/MOP_alongshore/D0052_nowcast.nc"/>
      <dataset name="D0052_hindcast.nc" urlPath="cdip/model/MOP_alongshore/D0052_hindcast.nc"/>
      <dataset name="D0060_nowcast.nc" urlPath="cdip/model/MOP_alongshore/D0060_nowcast.nc"/>
      <dataset name="D0060_ecmwf_fc.nc" urlPath="cdip/model/MOP_alongshore/D0060_ecmwf_fc.nc"/>
    </catalog>"""
    das = 'Attributes {\n NC_GLOBAL {\n  String time_coverage_start "2000-01-01T00:00:00Z";\n' \
          '  String time_coverage_end "2026-11-19T23:00:00Z";\n  String title "x";\n }\n}\n'
    cdip = {
        mop.CATALOG: catalog,
        f"{mop.SERVER}/thredds/catalog/cdip/archive/catalog.xml":
            '<catalogRef xlink:href="155p1/catalog.xml" xlink:title="155p1"/>',
        f"{mop.SERVER}/thredds/catalog/cdip/realtime/catalog.xml": '<dataset name="191p1_rt.nc"/>',
        f"{mop.SERVER}/thredds/catalog/cdip/archive/155p1/catalog.xml":
            '<dataset name="155p1_d01.nc" urlPath="cdip/archive/155p1/155p1_d01.nc"/>',
        f"{mop.DODS}cdip/archive/155p1/155p1_historic.nc.das": das.replace("2000-01-01", "2019-01-02"),
        f"{mop.DODS}cdip/model/MOP_alongshore/D0052_nowcast.nc.das": das.replace("2000-01-01", "2019-03-01"),
        f"{mop.DODS}cdip/model/MOP_alongshore/D0052_hindcast.nc.das": das,
    }
    where = {"D0052": "32.5701, -117.1690, 10.0", "D0060": "32.60, -117.13, 10.0"}
    for pid, vals in where.items():
        lat, lon, dep = vals.split(", ")
        cdip[f"{mop.DODS}cdip/model/MOP_alongshore/{pid}_nowcast.nc.ascii?metaLatitude,metaLongitude,metaWaterDepth"] = (
            f"Dataset {{}}\n---------\nmetaLatitude, {lat}\nmetaLongitude, {lon}\nmetaWaterDepth, {dep}\n")

    def fetch(self, url, timeout=120.0):
        self.left -= 1
        if url not in cdip:
            raise OSError(f"no fixture for {url}")
        return cdip[url]

    monkeypatch.setattr(nc, "get", get)
    monkeypatch.setattr(mop.Budget, "fetch", fetch)
    log: list[str] = []
    data = nc.census(log)

    assert data["input"]["directional_years"] == [2020, 2021]
    assert data["mop_products"] == {"ecmwf_fc": 1, "hindcast": 1, "nowcast": 2}
    ib = data["stations"]["46235"]
    assert ib["cdip_id"] == "155" and ib["water_depth_m"] == 18.9
    assert ib["grids"] == ["regional", "outer"]
    assert ib["directional_years"] == [2019, 2020, 2021]
    assert ib["cdip"]["in_archive"] and not ib["cdip"]["reporting_now"]
    assert ib["mop"]["point"] == "D0052" and ib["mop"]["distance_m"] < 20
    assert ib["mop"]["hindcast"]["time_coverage_start"].startswith("2000")
    assert "46225" not in data["stations"]                 # Torrey Pines: outside every grid
    assert "46232" in data["stations"] and "cdip" not in data["stations"]["46232"]   # the input: no lookups
    # 46232's station page has no fixture: reported, and its position still the table's.
    assert any("station page 46232" in x for x in log)

    text = nc.report(data, log)
    assert "| 46235 | 155 |" in text and "2020–2021" in text
    assert "## What failed" in text and "station page 46232" in text
    json.dumps(data)                                         # what main() writes
