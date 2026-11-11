"""The Swell card map (shipped 2026-11-10): its seabed tiles, its data and the
bundled library. What can be pinned without a browser."""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "app" / "forecast.html").read_text(encoding="utf-8")
VENDOR = ROOT / "app" / "vendor"


def test_the_tiles_are_drawn_from_todays_grids():
    """A grid fetched again (the bathymetry workflows redraw the tiles after
    each fetch) or a tile lost: the map would show a seabed the rays were not
    traced over."""

    pytest.importorskip("numpy")
    from forecast import seabedtiles

    assert seabedtiles.check() == []


def test_the_tiles_cover_every_layer_the_page_asks_for():
    manifest = json.loads((ROOT / "data" / "seabed_tiles" / "manifest.json").read_text())
    names = [layer["name"] for layer in manifest["layers"]]
    assert names == ["context", "inner", "near"]
    for layer in manifest["layers"]:
        assert layer["tiles"] > 0
        z0, z1 = layer["zooms"]
        assert z0 <= z1


def test_the_map_library_is_bundled_with_its_licence_and_loaded_only_when_shown():
    """BSD-3, bundled (owner's call, 2026-11-10), and never in the page's own
    head: it is fetched by `ready()` the first time a map is shown."""

    lib = VENDOR / "maplibre-gl-4.7.1"
    assert (lib / "maplibre-gl.js").exists() and (lib / "maplibre-gl.css").exists()
    assert "Redistribution and use in source and binary forms" in (lib / "LICENSE.txt").read_text()
    assert 'const MAPLIBRE = "vendor/maplibre-gl-4.7.1/maplibre-gl";' in PAGE
    assert "maplibre-gl.js" not in PAGE.replace('const MAPLIBRE = "vendor/maplibre-gl-4.7.1/maplibre-gl";', "")
    assert not re.search(r"<script[^>]+src=", PAGE)


def test_no_gpl_code_ships_with_the_page():
    """The map turns with MapLibre's own bearing: leaflet-rotate (GPL-3.0) was
    the mock's, and nothing GPL is bundled (owner's call, 2026-11-10)."""

    assert "leaflet" not in PAGE.lower()
    for path in VENDOR.rglob("*"):
        if path.is_file() and path.suffix in {".js", ".txt", ".css"}:
            assert "GNU GENERAL PUBLIC LICENSE" not in path.read_text(encoding="utf-8", errors="ignore")


def test_the_map_view_is_a_device_setting_through_the_pages_helpers():
    """One choice for every tab, kept on this device (the mock's), through
    `stored` / `store` like the page's other device settings."""

    assert 'const VIEW_KEY = "nado-waves.swell-view";' in PAGE
    assert 'stored(VIEW_KEY) === "map"' in PAGE and "store(VIEW_KEY, v);" in PAGE


def test_the_map_is_turned_to_the_shore_normal_and_never_by_the_reader():
    assert "bearing: this.b.normal" in PAGE
    assert "dragRotate: false" in PAGE and "touchZoomRotate.disableRotation()" in PAGE


def test_the_map_data_names_no_coordinate_by_hand():
    """Every point is fetched metadata or spots.json, through forecast.mapdata."""

    from forecast import mapdata

    src = (ROOT / "forecast" / "mapdata.py").read_text()
    assert not re.search(r"-11[0-9]\.\d{2}", src)
    assert mapdata.OTHER_BUOYS == ("46086", "46047")


def test_the_fill_is_live_only_and_reads_its_own_files():
    """The fill (owner's request, 2026-11-10) is offered on LIVE alone, from
    fill.json and the break's paths, fetched only when a train is picked on
    the map; it never draws on the Forecast tab."""

    assert 'const FILL_SOURCE = PARAM.get("fill") || "../data/live/fill.json";' in PAGE
    assert 'const NEARSHORE_PATHS = "../data/nearshore/";' in PAGE
    assert 'const live = MODE === "now" && view === "map"' in PAGE
    # fill.json and now.json must name the same spectrum, or no fill.
    assert "d.observed_utc === NOW.observed_utc" in PAGE


def test_the_fill_says_what_it_is():
    """Rays the calculation follows, never waves, timed from NDBC 46232."""

    assert 'aria-label="Minutes after NDBC 46232"' in PAGE
    assert "98% in by" in PAGE


def test_the_tiles_are_drawn_at_twice_the_size_the_page_asks_for():
    """Owner's report, 2026-11-11: grainy on a phone. The page asks for 256 px
    tiles and each is drawn at 512, anti-aliased."""

    from PIL import Image

    manifest = json.loads((ROOT / "data" / "seabed_tiles" / "manifest.json").read_text())
    assert manifest["tile"] == 256 and manifest["drawn_px"] == 512
    assert "tileSize: 256," in PAGE
    one = next((ROOT / "data" / "seabed_tiles").rglob("*.png"))
    assert Image.open(one).size == (512, 512)


def test_a_contour_is_drawn_only_where_its_level_is_crossed():
    """The distance test alone drew a flat lying near a level as a blob of
    line; a crossing within a pixel is what makes a contour."""

    np = pytest.importorskip("numpy")
    from forecast import seabedtiles

    flat = np.full((20, 20), 9.9)               # near 10 m, never crossing it
    rgba = seabedtiles.shade(flat, np.ones(flat.shape, bool))
    assert len({tuple(p) for p in rgba[3:-3, 3:-3].reshape(-1, 4)}) == 1
    slope = np.tile(np.linspace(5.5, 14.5, 40), (20, 1))   # crosses 10 m once
    rgba = seabedtiles.shade(slope, np.ones(slope.shape, bool))
    row = rgba[10, :, 0].astype(int)
    assert row[20] > row[5] + 20 and row[20] > row[35] + 20


def test_every_break_opens_at_one_scale():
    """Owner's request, 2026-11-11: the farthest edge vertex of ANY break sets
    the opening scale, so no break tab opens nearer than another."""

    body = PAGE[PAGE.index("  frame(animate = false) {"):]
    body = body[:body.index("const mpp")]
    assert "MAPDATA.geometry.breaks.flatMap" in body
    assert "this.b.windows" not in body
