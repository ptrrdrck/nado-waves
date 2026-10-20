"""The Shark Lab probe's parse, offline: the server is denied from a session."""

from collector import probe_sharklab as p


TABLEDAP = """station,time,latitude,longitude,temperature
,UTC,degrees_north,degrees_east,degree_C
hub1,2026-10-19T12:00:00Z,32.68,-117.18,18.4
"""

INFO = """Row Type,Variable Name,Attribute Name,Data Type,Value
attribute,NC_GLOBAL,cdm_timeseries_variables,String,"station,latitude,longitude"
variable,station,,String,
variable,latitude,,double,
variable,longitude,,double,
variable,time,,double,
"""


def test_tabledap_units_row_is_split_off():
    header, units, rows = p.parse_erddap_csv(TABLEDAP)
    assert header[0] == "station"
    assert units[1] == "UTC"
    assert rows == [["hub1", "2026-10-19T12:00:00Z", "32.68", "-117.18", "18.4"]]


def test_info_page_has_no_units_row():
    header, units, rows = p.parse_erddap_csv(INFO)
    assert units == []
    assert rows[0][2] == "cdm_timeseries_variables"


def test_station_variables_come_from_the_cdm_attribute_only():
    info = p.DatasetInfo("x", ["station", "latitude", "longitude", "time"],
                         {("NC_GLOBAL", "cdm_timeseries_variables"): "station,latitude,longitude"})
    assert info.station_variables() == ["station"]
    assert p.DatasetInfo("y", ["station", "latitude", "longitude"]).station_variables() == []


def test_nearest_break_reads_spots_json():
    spots = p.breaks()
    assert {s.id for s in spots} == set(p.CORONADO)
    centre = next(s for s in spots if s.id == "coronado_center").position
    assert p.nearest_break(*centre, spots) == ("coronado_center", 0.0)


def test_a_timeout_is_not_a_denial():
    import socket
    import urllib.error

    refused = urllib.error.URLError(OSError("Tunnel connection failed: 403 Forbidden"))
    timed_out = urllib.error.URLError(socket.timeout("timed out"))
    assert p.is_denial(refused) and not p.is_timeout(refused)
    assert p.is_timeout(timed_out) and not p.is_denial(timed_out)
    assert p.is_timeout(TimeoutError("The read operation timed out"))
