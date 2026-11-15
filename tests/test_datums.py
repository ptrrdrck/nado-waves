"""Fetching NOAA's tidal datums (`collector.datums`): what is refused, and
what the map reads from them."""

import json

import pytest

from collector import datums


def _body(**over):
    values = {"STND": 0.0, "MLLW": 0.4, "MSL": 1.3, "MHW": 1.9, "NAVD88": 0.5}
    body = {"units": "meters", "epoch": "1983-2001",
            "datums": [{"name": k, "value": v} for k, v in values.items()]}
    body.update(over)
    return json.dumps(body).encode()


def test_a_whole_response_parses():
    assert datums.by_name(datums.parse(_body()))["MHW"] == 1.9


def test_an_error_in_a_200_body_is_refused():
    with pytest.raises(datums.DatumsError):
        datums.parse(json.dumps({"error": {"message": "No data"}}).encode())


def test_a_missing_datum_is_refused_not_read_as_zero():
    body = json.loads(_body())
    body["datums"] = [d for d in body["datums"] if d["name"] != "MHW"]
    with pytest.raises(datums.DatumsError):
        datums.parse(json.dumps(body).encode())


def test_feet_are_refused():
    with pytest.raises(datums.DatumsError):
        datums.parse(_body(units="feet"))


def test_mhw_must_sit_just_above_msl():
    body = json.loads(_body())
    for d in body["datums"]:
        if d["name"] == "MHW":
            d["value"] = 0.9
    with pytest.raises(datums.DatumsError):
        datums.parse(json.dumps(body).encode())


def test_mhw_above_msl_is_read_off_the_stored_response(tmp_path):
    assert datums.mhw_above_msl_m(tmp_path) is None
    path = datums.datums_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"station": "9410170", "response": json.loads(_body())}))
    assert datums.mhw_above_msl_m(tmp_path) == pytest.approx(0.6)


def test_the_stored_file_is_a_response_from_coops():
    path = datums.datums_path()
    if not path.exists():
        pytest.skip("not fetched yet: tide-stations.yml or the hourly collection fetches it")
    stored = json.loads(path.read_text())
    assert stored["station"] == "9410170"
    assert stored["source"].startswith(datums.MDAPI)
    datums.parse(json.dumps(stored["response"]).encode())


def test_the_stored_mhw_agrees_with_the_stations_own_constants():
    """A cross-check, not a source: MHW above MSL from the stored harmonic
    constants (`data/tide/9410170_harcon.json`) summed with no nodal
    correction, every high water averaged: 0.603 m over 19 years, 0.602 m
    over the 4 summed here (BRIEFING §53). CO-OPS's epoch datum comes from
    observation, so a few cm apart is expected and more is a wrong file."""

    np = pytest.importorskip("numpy")
    mhw = datums.mhw_above_msl_m()
    if mhw is None:
        pytest.skip("datums not fetched yet")
    from collector import harcon
    rows = json.loads(harcon.harcon_path().read_text())["response"]["HarmonicConstituents"]
    t = np.arange(0.0, 4 * 365.25 * 24, 0.1)
    h = sum(r["amplitude"] * np.cos(np.radians(r["speed"] * t - r["phase_GMT"])) for r in rows)
    w = 30
    padded = np.pad(h, w, mode="edge")
    peak = np.lib.stride_tricks.sliding_window_view(padded, 2 * w + 1).max(axis=1)
    idx = np.flatnonzero(h >= peak)
    idx = idx[np.concatenate([[True], np.diff(idx) > 1])]
    assert abs(h[idx].mean() - mhw) < 0.05
