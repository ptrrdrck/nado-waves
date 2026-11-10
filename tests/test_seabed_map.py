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
