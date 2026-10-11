"""Fetching NOAA's harmonic constants (`collector.harcon`): what is refused."""

import json

import pytest

from collector import harcon


def _body(**over):
    rows = [{"name": n, "amplitude": 0.1, "phase_GMT": 10.0, "phase_local": 20.0, "speed": 15.0}
            for n in ("M2", "S2", "N2", "K1", "O1")]
    body = {"units": "meters", "HarmonicConstituents": rows}
    body.update(over)
    return json.dumps(body).encode()


def test_a_whole_response_parses():
    assert len(harcon.parse(_body())["HarmonicConstituents"]) == 5


def test_an_error_in_a_200_body_is_refused():
    with pytest.raises(harcon.HarconError):
        harcon.parse(json.dumps({"error": {"message": "No data"}}).encode())


def test_a_constituent_without_a_phase_is_refused():
    """A missing phase read as zero would move every tide it touches."""

    body = json.loads(_body())
    del body["HarmonicConstituents"][0]["phase_GMT"]
    with pytest.raises(harcon.HarconError):
        harcon.parse(json.dumps(body).encode())


def test_the_main_constituents_must_all_be_there():
    body = json.loads(_body())
    body["HarmonicConstituents"] = [r for r in body["HarmonicConstituents"] if r["name"] != "K1"]
    with pytest.raises(harcon.HarconError):
        harcon.parse(json.dumps(body).encode())


def test_the_stored_file_is_a_response_from_coops():
    stored = json.loads(harcon.harcon_path().read_text())
    assert stored["station"] == "9410170"
    assert stored["source"].startswith(harcon.MDAPI)
    harcon.parse(json.dumps(stored["response"]).encode())
