"""The Swell card map (shipped 2026-11-10): its seabed tiles, its data and the
bundled library. What can be pinned without a browser."""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "app" / "forecast.html").read_text(encoding="utf-8")
VENDOR = ROOT / "app" / "vendor"


def test_the_seabed_is_drawn_from_todays_grids():
    """A grid fetched again (the bathymetry workflows redraw the seabed after
    each fetch) or a file lost: the map would show a seabed the rays were not
    traced over."""

    pytest.importorskip("numpy")
    from forecast import seabedvector

    assert seabedvector.check() == []


def test_the_seabed_is_vectors_for_every_grid_the_rays_use():
    """Owner's request, 2026-11-11: vectors, not raster tiles. Each grid a
    file, coarsest first, the finer from a higher zoom; bands nested from the
    land up, the shoreline at the ray tracer's own land depth."""

    manifest = json.loads((ROOT / "data" / "seabed_vector" / "manifest.json").read_text())
    tiers = manifest["tiers"]
    from forecast import seabedvector
    stored = [n for n in seabedvector.TIERS if (ROOT / "data" / "bathymetry" / f"{n}.json").exists()]
    assert [t["name"] for t in tiers] == stored
    assert stored[-4:] == ["context", "outer", "regional", "nearshore"]
    assert [t["minzoom"] for t in tiers] == sorted(t["minzoom"] for t in tiers)
    assert not (ROOT / "data" / "seabed_tiles").exists()
    one = json.loads((ROOT / "data" / "seabed_vector" / "nearshore.geojson").read_text())
    kinds = {f["properties"]["k"] for f in one["features"]}
    assert kinds == {"fill", "line", "coast"}
    bands = {f["properties"]["b"] for f in one["features"] if f["properties"]["k"] == "fill"}
    assert -1 in bands and 0 in bands
    from forecast.raytrace import H_LAND
    assert manifest["bands"][0] == H_LAND


def test_every_band_ends_on_one_line_at_a_grids_edge():
    """Owner's report, 2026-11-11: a land-coloured line ran across open sea
    along the context grid's edge. Each band was simplified alone, and each
    edge straight in UTM but not on the map, so a band whose edge was one
    long chord bowed kilometres from one with vertices along it, and the
    land colour under them all showed between. A synthetic grid 800 km
    across, land along one side and the bands crossing the edge many times:
    everywhere on the edge, every band the water there is deep enough for
    must begin where the land colour does."""

    np = pytest.importorskip("numpy")
    pytest.importorskip("contourpy")
    pytest.importorskip("shapely")
    from shapely import union_all
    from shapely.geometry import Point, shape

    from forecast import utm
    from forecast.raytrace import Grid
    from forecast.seabedvector import BANDS, H_LAND, features

    cell, n, left, top = 4000.0, 225, 100_000.0, 3_700_000.0
    deep = 1800 + 1700 * np.sin(np.arange(n) / 23.0) * np.cos(np.arange(n)[:, None] / 31.0)
    deep[:, :12] = -150.0                                   # land along the west
    grid = Grid.from_elevation(-deep, left, top, cell, 0.0)
    bands: dict[int, list] = {}
    for f in features(grid, 0.8, 80.0, 4):
        if f["properties"]["k"] == "fill":
            bands.setdefault(f["properties"]["b"], []).append(shape(f["geometry"]))
    union = {b: union_all(v) for b, v in bands.items()}
    ring = union[-1].exterior
    checked = worst = 0
    for i in range(800):
        p = ring.interpolate(i / 800, normalized=True)
        x, y = utm.to_utm(p.y, p.x)
        c = int(np.clip((x - left) / cell, 0, n - 1))
        r = int(np.clip((top - y) / cell, 0, n - 1))
        depth = deep[max(r - 3, 0):r + 4, max(c - 3, 0):c + 4].min()   # the water all round
        for b, lower in enumerate((H_LAND,) + BANDS):
            if lower < depth and b in union:
                checked += 1
                worst = max(worst, union[b].distance(Point(p.x, p.y)))
    # One rounding step of the 4 decimals kept (~10 m); apart, it was 0.06 deg.
    assert checked > 2000
    assert worst < 1e-4


def test_the_map_multisamples_and_draws_no_fill_outlines():
    """Owner's report, 2026-11-12: faint light lines across the sea, each on
    a tile boundary (32.5468 N at zoom 9). MapLibre's anti-aliased fill
    outline also traces where a polygon is cut at a tile's edge; on the
    turned map those cuts showed. So no fill draws an outline and the canvas
    multisamples instead, which keeps the edges smooth."""

    assert "cooperativeGestures: true, fadeDuration: 0, antialias: true," in PAGE
    fills = re.findall(r'type: "fill",[^;]*?paint: \{([^}]*)\}', PAGE)
    assert len(fills) == 2 and all('"fill-antialias": false' in f for f in fills)


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


def test_the_maps_themes_are_the_owners_and_follow_the_page():
    """Owner's picks, 2026-11-11, from the mock: one theme for each of the
    page's, the rays the picked train's colour, and the map restyled when the
    page's theme changes."""

    assert "const MAP_THEMES = {" in PAGE
    body = PAGE[PAGE.index("const MAP_THEMES = {"):]
    body = body[:body.index("};") + 2]
    assert '"#e9e0cc"' in body and '"#38362f"' in body          # the two lands
    assert 'rays: "#e8590c"' in body and 'rays: "#ffd84d"' in body
    assert "raysGlow: false" in body and "raysGlow: true" in body
    assert "MAP_THEMES[shownTheme()]" in PAGE
    assert 'attributeFilter: ["data-theme"]' in PAGE
    assert not re.search(r"\bLIT\b(?!_)", PAGE)


def test_the_seabeds_bands_match_the_pages_colours():
    """The page colours bands -1 (land) to 11; the builder writes exactly those."""

    from forecast import seabedvector

    assert len(seabedvector.BANDS) + 1 == 12
    assert "bandColours(th, 12)" in PAGE


def test_every_break_opens_at_one_scale():
    """Owner's request, 2026-11-11: the farthest edge vertex of ANY break sets
    the opening scale, so no break tab opens nearer than another."""

    body = PAGE[PAGE.index("  frame(animate = false) {"):]
    body = body[:body.index("const mpp")]
    assert "MAPDATA.geometry.breaks.flatMap" in body
    assert "this.b.windows" not in body
