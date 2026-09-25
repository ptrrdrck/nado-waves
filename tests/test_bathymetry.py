"""collector.bathymetry — what can be pinned without the network.

The grid read itself needs rasterio and the network, and neither is in the
test environment on purpose (requirements-dev.txt). What is pinned here is
what decides whether a stored grid can be trusted: where its anchors come
from, how the datum is read, and — when numpy is present — that the stored
grid agrees with the charted coastline, which is a LOCATED check a total
could not stand in for (BRIEFING §15).
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest

from collector import bathymetry

ROOT = Path(__file__).resolve().parent.parent


def test_the_buoy_is_read_from_ndbc_metadata_not_typed():
    lat, lon = bathymetry.buoy_position()
    assert 32.0 < lat < 33.0 and -118.0 < lon < -117.0
    assert "32.517" not in Path(bathymetry.__file__).read_text()


def test_an_unplaced_buoy_is_an_error_not_a_guess(tmp_path):
    path = tmp_path / "stations.csv"
    path.write_text("station,name,owner,type,lat,lon,active,notes\n", encoding="utf-8")
    with pytest.raises(LookupError):
        bathymetry.buoy_position(path)


def test_the_regional_grid_is_anchored_on_the_breaks_point_loma_and_the_buoy():
    regional = bathymetry.anchors("regional")
    nearshore = bathymetry.anchors("nearshore")
    assert len(nearshore) == 6            # three chords, two ends each
    assert len(regional) > len(nearshore)
    assert bathymetry.buoy_position() in regional


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_the_datum_offset_is_msl_minus_navd88(monkeypatch):
    body = {"epoch": "1983-2001", "datums": [
        {"name": "MLLW", "value": 0.0}, {"name": "MSL", "value": 0.95},
        {"name": "NAVD88", "value": 0.10}]}
    monkeypatch.setattr(bathymetry.urllib.request, "urlopen",
                        lambda url, timeout: _Resp(json.dumps(body).encode()))
    got = bathymetry.fetch_datum()
    assert got["msl_above_navd88_m"] == pytest.approx(0.85)
    assert got["station"] == "9410170"


def test_a_datum_response_without_navd88_is_refused(monkeypatch):
    body = {"datums": [{"name": "MSL", "value": 0.95}]}
    monkeypatch.setattr(bathymetry.urllib.request, "urlopen",
                        lambda url, timeout: _Resp(json.dumps(body).encode()))
    with pytest.raises(LookupError):
        bathymetry.fetch_datum()


def test_a_grid_stored_without_a_datum_says_so():
    """Checked on whichever grids are stored: `outer` comes only from the
    workflow, because gmrt.org is denied from a session."""

    stored = [g for g in bathymetry.GRIDS if (ROOT / "data" / "bathymetry" / f"{g}.json").exists()]
    assert {"nearshore", "regional"} <= set(stored)
    for grid in stored:
        meta = json.loads((ROOT / "data" / "bathymetry" / f"{grid}.json").read_text())
        datum = meta["datum"]
        assert datum["msl_above_navd88_m"] is None or isinstance(datum["msl_above_navd88_m"], float)
        if datum["msl_above_navd88_m"] is None:
            assert "not fetched" in datum["note"]
        if bathymetry.GRIDS[grid][2] == "coned":
            assert meta["vertical_datum"] == "NAVD88"
            assert "Coronado Islands" in meta["not_covered"]
        else:
            assert meta["vertical_datum"] == "MSL"


def test_the_stored_grid_puts_the_charted_coast_near_mean_high_water():
    """ENC coastline is MHW. On the nearshore grid, the elevation under every
    charted Coronado vertex should sit a metre or two above NAVD88, not metres
    off: a grid shifted, flipped or mis-registered would fail this while
    still having a plausible depth range."""

    np = pytest.importorskip("numpy")
    meta = json.loads((ROOT / "data" / "bathymetry" / "nearshore.json").read_text())
    z = np.load(ROOT / "data" / "bathymetry" / "nearshore.npz")["elevation_dm"] / 10.0
    a, _, c, _, e, f = meta["transform"]
    from forecast.utm import to_utm

    rows = list(csv.DictReader((ROOT / "data" / "shoreline" / "enc_harbour_84_coronado.csv").open()))
    vals = []
    for r in rows:
        x, y = to_utm(float(r["lat"]), float(r["lon"]))
        col, row = int((x - c) / a), int((y - f) / e)
        if 0 <= row < z.shape[0] and 0 <= col < z.shape[1]:
            vals.append(z[row, col])
    assert len(vals) > 500
    assert 0.5 < float(np.median(vals)) < 2.5
