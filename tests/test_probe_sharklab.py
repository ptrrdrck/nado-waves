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


def test_gps_jitter_clusters_into_one_hub_and_nan_is_left_out():
    text = """serial,latitude,longitude
,degrees_north,degrees_east
A,32.68271,-117.18874
A,32.68274,-117.18871
A,NaN,NaN
B,35.16732,-120.74277
"""
    fetched = p.Fetched(url="x", ok=True)
    fetched.header, fetched.units, fetched.rows = p.parse_erddap_csv(text)
    clusters = p.cluster_positions(fetched, ["serial"], "latitude", "longitude", p.breaks())
    assert [(c.key, c.rows) for c in clusters] == [(("A",), 2), (("B",), 1)]
    assert clusters[0].spot == "coronado_center" and clusters[0].km < 1


def test_time_variable_prefers_time_then_an_erddap_time():
    info = p.DatasetInfo("x", ["device_time_utc", "serial_number"])
    assert p.time_variable(info) == "device_time_utc"
    info = p.DatasetInfo("y", ["datetime_pt", "In_UTC"],
                         {("In_UTC", "units"): "seconds since 1970-01-01T00:00:00Z"})
    assert p.time_variable(info) == "In_UTC"


def test_latest_row_per_group_by_parsed_time():
    text = """device_time_utc,hub_serial,type
2026-10-21 23:00:00,660494,det
2026-10-22 01:00:00,660494,det
2026-10-22 00:30:00,660495,status
not a time,660495,det
"""
    fetched = p.Fetched(url="x", ok=True)
    fetched.header, fetched.units, fetched.rows = p.parse_erddap_csv(text)
    latest = p.latest_rows(fetched, ["hub_serial"], "device_time_utc")
    assert [(g.key, g.rows, g.newest.hour) for g in latest] == [
        (("660494",), 2, 1), (("660495",), 1, 0)]


def test_epoch_numbers_are_read_by_their_size_and_windowed_in_kind():
    assert p.parse_time("1761110000").year == 2025
    assert p.parse_time("1761110000000").year == 2025
    assert p.parse_time("660494") is None
    assert p.window_start(["1761110000", "1761000000"], "double") == str(1761110000 - 2 * 86400)
    assert p.window_start(["1761110000000"], "long") == str((1761110000 - 2 * 86400) * 1000)
    assert p.window_start(["2026-10-22 01:00:00"], "String") == '"2026-10-20"'
    assert p.window_start(["1761110000000"], "String") == f'"{(1761110000 - 2 * 86400) * 1000}"'


def test_a_hub_on_land_reads_landward_and_offshore_reads_seaward():
    spots = p.breaks()
    # Run 7: the newest fix ~190 m inland of Center, the deployed one ~480 m out.
    assert p.seaward_m(32.6838331, -117.1845298, spots) < -150
    assert p.seaward_m(32.67813, -117.18736, spots) > 400


def test_stretches_split_on_side_and_on_silence():
    from datetime import datetime, timedelta, timezone

    t0 = datetime(2026, 6, 1, tzinfo=timezone.utc)
    fixes = [(t0 + timedelta(hours=h), True) for h in range(3)]
    fixes += [(t0 + timedelta(hours=50 + h), True) for h in range(2)]
    fixes += [(t0 + timedelta(hours=52 + h), False) for h in range(2)]
    runs = p.stretches(fixes)
    assert [(r.in_water, r.fixes) for r in runs] == [(True, 3), (None, 0), (True, 2), (False, 2)]


def test_coverage_names_missing_and_partial_days():
    from datetime import datetime, timedelta, timezone

    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    day0 = today - timedelta(days=3)
    fixes = [(day0 + timedelta(minutes=2 * i), True) for i in range(720)]
    fixes += [(day0 + timedelta(days=2, minutes=2 * i), False) for i in range(100)]
    text = "\n".join(p.coverage(fixes))
    assert f"Missing days since {day0.date()}: {day0 + timedelta(days=1):%m-%d}." in text
    assert f"{day0 + timedelta(days=2):%m-%d} (100)" in text
