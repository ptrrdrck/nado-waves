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
            # A CoNED grid needs the offset and says it is missing; a GMRT
            # grid is already sea level and says it needs none (the context
            # grid, fetched with --skip-datum by bathymetry-context.yml).
            want = "not fetched" if bathymetry.GRIDS[grid][2] == "coned" else ("not fetched", "not needed")
            assert any(w in datum["note"] for w in ([want] if isinstance(want, str) else want))
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


def test_the_context_grid_holds_the_page_buoys_and_feeds_no_chain():
    """Owner's request, 2026-11-10: a coarse GMRT seabed out past Tanner Bank
    for a map's context. It must hold every buoy the page shows, and the ray
    tracer must never load it: it is for drawing, not for refraction."""

    from forecast import raytrace

    assert bathymetry.GRIDS["context"][2] == "gmrt"
    points = bathymetry.anchors("context")
    for station in bathymetry.CONTEXT_BUOYS:
        assert bathymetry.buoy_position(station=station) in points
    src = Path(raytrace.__file__).read_text()
    assert 'for name in ("nearshore", "regional", "outer"):' in src
    assert '"context"' not in src


def test_the_wide_grid_reaches_the_maps_widest_view_and_feeds_no_chain():
    """Owner's report, 2026-11-11: the map's widest view ran off the context
    grid. The wide grid's margin must reach the farthest corner of that view,
    the break where the map keeps it and 46047 and 25 km in view, on a 260 px
    map, panned to its limit (the page's own `limits()` arithmetic)."""

    import math

    from forecast import raytrace
    from forecast.geometry import load
    from forecast.siting import load_coordinates
    from forecast.swell import great_circle_km, initial_bearing

    assert bathymetry.GRIDS["wide"][2] == "gmrt"
    tanner = load_coordinates()["46047"]
    far = 0.0
    for spot in load()[0]:
        if not spot.id.startswith("coronado_"):
            continue
        p = spot.position
        reach = great_circle_km(p, tanner) + 25
        rel = math.radians(initial_bearing(p, tanner) - spot.normal)
        w = h = 260
        mpp = max(abs(math.sin(rel)) * reach * 1000 / (0.5 * w - 76),
                  max(0.0, math.cos(rel)) * reach * 1000 / (0.85 * h), 1)
        far = max(far, reach + math.hypot(w, h) / 2 * mpp / 1000)
    assert bathymetry.WIDE_MARGIN_M / 1000 > far
    assert '"wide"' not in Path(raytrace.__file__).read_text()
