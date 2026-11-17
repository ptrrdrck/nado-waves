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
    land up, the shoreline at mean high water, the chart's coastline, from
    NOAA's fetched datums (owner's decision, 2026-11-15; BRIEFING §53)."""

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
    from collector.datums import mhw_above_msl_m
    mhw = mhw_above_msl_m()
    assert mhw is not None and 0.3 < mhw < 1.0
    assert manifest["bands"][0] == -mhw
    assert manifest["coast"]["datum"] == "MHW" and manifest["coast"]["above_msl_m"] == mhw


def test_one_band_and_the_right_one_at_a_grids_edge():
    """Owner's reports, 2026-11-11 and -12: a line ran across open sea along
    the context grid's edge. First the land colour (each band simplified
    alone, and an edge straight in UTM but curved on the map, so the land
    band's one long chord bowed kilometres past the rest); then, the edges
    made one, a faint dotted line on an iPhone, because MapLibre simplifies
    each shape again as it draws and the land colour showed in the sub-pixel
    gaps. So just inside the edge exactly ONE band is drawn, and it is the
    band the water there calls for. A synthetic grid 800 km across, land
    along one side and the bands crossing the edge many times."""

    np = pytest.importorskip("numpy")
    pytest.importorskip("contourpy")
    pytest.importorskip("shapely")
    from shapely import union_all
    from shapely.geometry import shape

    from forecast import utm
    from forecast.raytrace import Grid
    from forecast.seabedvector import BANDS, features

    cell, n, left, top = 4000.0, 225, 100_000.0, 3_700_000.0
    deep = 1800 + 1700 * np.sin(np.arange(n) / 23.0) * np.cos(np.arange(n)[:, None] / 31.0)
    deep[:, :12] = -150.0                                   # land along the west
    grid = Grid.from_elevation(-deep, left, top, cell, 0.0)
    coast = -0.6
    fills = [(f["properties"]["b"], shape(f["geometry"]))
             for f in features(grid, 0.8, 80.0, 4, strip=1000.0, coast=coast)
             if f["properties"]["k"] == "fill"]
    drawn = union_all([g for _, g in fills])
    ring = max(getattr(drawn, "geoms", [drawn]), key=lambda g: g.area).buffer(-0.001).exterior
    lowers = (-1e9, coast) + BANDS
    checked = 0
    for i in range(800):
        q = ring.interpolate(i / 800, normalized=True)
        on = [b for b, g in fills if g.contains(q)]
        assert len(on) == 1, (q.x, q.y, on)
        x, y = utm.to_utm(q.y, q.x)
        c = int(np.clip((x - left) / cell, 0, n - 1))
        r = int(np.clip((top - y) / cell, 0, n - 1))
        near = deep[max(r - 3, 0):r + 4, max(c - 3, 0):c + 4]
        want = {sum(lo <= d for lo in lowers) - 2 for d in (near.min(), near.max())}
        if len(want) == 1:                                  # one band all round
            checked += 1
            assert on == [want.pop()], (q.x, q.y, on)
    assert checked > 400


def test_the_coast_is_the_grid_as_stored_and_every_band_keeps_inside_it():
    """Owner's decision, 2026-11-15 (BRIEFING §53): smoothing a cliff whose
    land stands far above shallow water carried the coast seaward, 21-43 m
    at the Point Loma tip on 32 m cells. A synthetic cliff: the drawn coast
    follows the stored grid's own contour, the smoothed grid's lies well
    seaward of it, no deeper band reaches over the coast, and a pond below
    sea level that no water joins to the sea is land, with no coast round
    it, as on a chart."""

    np = pytest.importorskip("numpy")
    contourpy = pytest.importorskip("contourpy")
    pytest.importorskip("shapely")
    from shapely.geometry import Point, shape

    from forecast import utm
    from forecast.raytrace import Grid
    from forecast.seabedvector import features, smooth

    cell, n, left, top = 32.0, 120, 480_000.0, 3_620_000.0
    xs = left + (np.arange(n) + 0.5) * cell
    depth = np.tile(np.where(np.arange(n) < 50, -15.0, 1.0 + 0.4 * (np.arange(n) - 50)), (n, 1))
    depth[50:70, 15:30] = 8.0                               # a pond below sea level, inland
    grid = Grid.from_elevation(-depth, left, top, cell, 0.0)
    coast = -0.6
    feats = features(grid, 1.0, 6.0, 6, strip=50.0, coast=coast)
    pond = utm.from_utm(xs[22], top - 60 * cell)
    assert [f["properties"]["b"] for f in feats if f["properties"]["k"] == "fill"
            and shape(f["geometry"]).contains(Point(pond[1], pond[0]))] == [-1]

    def east(lines):
        return float(np.median([utm.to_utm(la, lo)[0] for line in lines for lo, la in line]))

    coasts = [f["geometry"]["coordinates"] for f in feats if f["properties"]["k"] == "coast"]
    assert all(utm.to_utm(la, lo)[0] > xs[40] for line in coasts for lo, la in line)   # none round the pond
    drawn = east(coasts)
    ys = top - (np.arange(n) + 0.5) * cell

    def contour(d):
        lines = contourpy.contour_generator(xs, ys, d, name="serial").lines(coast)
        return float(np.median(np.concatenate(lines)[:, 0]))

    assert abs(drawn - contour(depth)) < 6.0
    assert contour(smooth(depth, 1.0)) - drawn > 10.0
    fills = [(f["properties"]["b"], shape(f["geometry"])) for f in feats if f["properties"]["k"] == "fill"]
    # A spit one cell wide, 40 m high, between water 60 m deep: smoothed, it
    # is drowned 20 m deep; drawn, it is land and no band lies over it.
    spit = np.full((n, n), 60.0)
    spit[:, 60] = -40.0
    feats = features(Grid.from_elevation(-spit, left, top, cell, 0.0), 1.0, 6.0, 6, strip=50.0, coast=coast)
    assert smooth(spit, 1.0)[n // 2, 60] > 10.0
    fills = [(f["properties"]["b"], shape(f["geometry"])) for f in feats if f["properties"]["k"] == "fill"]
    for y in ys[20:-20:10]:
        la, lo = utm.from_utm(xs[60], y)
        on = [b for b, g in fills if g.contains(Point(lo, la))]
        assert on == [-1], (y, on)


def test_the_map_multisamples_and_draws_no_fill_outlines():
    """Owner's report, 2026-11-12: faint light lines across the sea, each on
    a tile boundary (32.5468 N at zoom 9). MapLibre's anti-aliased fill
    outline also traces where a polygon is cut at a tile's edge; on the
    turned map those cuts showed. So no fill draws an outline and the canvas
    multisamples instead, which keeps the edges smooth."""

    assert "cooperativeGestures: true, fadeDuration: 0, antialias: true," in PAGE
    fills = re.findall(r'type: "fill",[^;]*?paint: \{([^}]*)\}', PAGE)
    # The swell map's two, and since 2026-11-17 the roses' seabed's one.
    assert len(fills) == 3 and all('"fill-antialias": false' in f for f in fills)
    assert "attributionControl: false, fadeDuration: 0, antialias: true, preserveDrawingBuffer: true," in PAGE


def test_the_maps_files_are_kept_on_the_device_by_their_version():
    """Owner's report, 2026-11-12: the map downloaded again on visits a few
    minutes apart. Pages lets a browser hold a file for ten minutes only and
    redeploys every collection, so the page keeps the library, the seabed and
    the rays in Cache Storage under each one's version, fetched at a URL
    carrying it: the library's in its path, the others' fingerprints in
    map.json, each the file's own SHA-256 so a redrawn file is a new copy."""

    from forecast import mapdata
    from forecast.mapdata import fingerprint

    manifest = json.loads((ROOT / "data" / "seabed_vector" / "manifest.json").read_text())
    for tier in manifest["tiers"]:
        assert tier["sha"] == fingerprint(ROOT / "data" / "seabed_vector" / tier["file"])
    paths = mapdata.build()["paths"]
    assert set(paths) == {"coronado_north", "coronado_center", "coronado_south"}
    for name, sha in paths.items():
        assert sha == fingerprint(ROOT / "data" / "nearshore" / f"{name}_paths.json")
    assert 'const KEEP = "nado-waves-map";' in PAGE
    assert 'at.searchParams.set("v", version);' in PAGE
    assert "kept(`${MAPLIBRE}.js`, LIB_VERSION)" in PAGE and "kept(`${MAPLIBRE}.css`, LIB_VERSION)" in PAGE
    assert "kept(seabedUrl(tr.file), tr.sha)" in PAGE
    assert "kept(file, ((MAPDATA || {}).paths || {})[id])" in PAGE
    assert "fetch(`${NEARSHORE_PATHS}" not in PAGE


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


def test_the_map_is_the_only_view_and_the_drawing_its_unseen_source():
    """Owner's request, 2026-11-16: no drawing / map switch and no kept choice;
    the drawing stays on the plate as what the map reads, unseen but in the
    Tab order and spoken (opacity, never visibility or display, which would
    take it out of both), and the part in focus lights on the map."""

    assert "sm-switch" not in PAGE and "VIEW_KEY" not in PAGE and "setView" not in PAGE
    assert "nado-waves.swell-view" not in PAGE
    assert 'let view = GL ? "map" : "drawing";' in PAGE
    assert ".sm-face.on-map .sm-plate > svg.aperture{opacity:0;pointer-events:none}" in PAGE
    assert not re.search(r"\.on-map[^{]*svg\.aperture\{[^}]*(visibility|display)", PAGE)
    assert 'document.addEventListener("focusin"' in PAGE
    assert ".sm-face.on-map svg.aperture [data-pick]" in PAGE


def test_the_drawing_shows_only_where_the_map_cannot_be_drawn():
    """Owner's request, 2026-11-16. No WebGL, asked for as MapLibre 4.7.1 asks
    (WebGL 2, else 1): the drawing from the first paint and nothing of the
    map fetched. The library or map.json failing to load, or the map failing
    to start, falls back the same way rather than leave an empty plate (before
    this, MapLibre's "Failed to initialize WebGL" went uncaught)."""

    lib = (VENDOR / "maplibre-gl-4.7.1" / "maplibre-gl.js").read_text(encoding="utf-8")
    assert 'getContext("webgl2",t)||this._canvas.getContext("webgl",t)' in lib
    probe = PAGE[PAGE.index("  const GL = (() => {"):]
    probe = probe[:probe.index("})();")]
    assert 'c.getContext("webgl2") || c.getContext("webgl")' in probe
    assert "loseContext()" in probe
    show = PAGE[PAGE.index("    show() {"):]
    show = show[:show.index("    turnFrom(prev) {")]
    assert "if (!on || !this.box.offsetWidth) return;" in show
    assert show.index("if (!on || !this.box.offsetWidth) return;") < show.index("ready()")
    assert "if (!this.b) { noMap(); return; }" in show
    assert "try { this.make(); } catch (e) { noMap(); return; }" in show
    body = PAGE[PAGE.index("  function noMap() {"):]
    body = body[:body.index("  }\n")]
    assert 'view = "drawing";' in body and "faces.forEach((f) => f.show());" in body


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


def test_the_plates_go_back_before_anything_reads_the_layout():
    """Owner's report, 2026-11-15: the page jumped on a Units change. The cards
    are rewritten whole; left to the map's MutationObserver, the plates came
    back only after `restorePicks` and the rest had laid the page out without
    them (176 px shorter at 390 x 664 with the map open), and WebKit, with no
    scroll anchoring, clamped a reader near the foot up by that much. So every
    rewrite of the cards puts them back first."""

    writes = PAGE.count('$("conditions").innerHTML = rows.join("");')
    assert writes == PAGE.count('$("conditions").innerHTML = rows.join("");\n      replate();') + PAGE.count(
        '$("conditions").innerHTML = rows.join("");\n  replate();')
    assert writes == 2
    assert "window.swellMapAttach = attach;" in PAGE


def test_a_face_opens_in_the_view_the_page_shows():
    """Owner's report, 2026-11-15: made as a drawing, a face on a page opening
    on the map slid from the drawing's height to the map's on every load and
    moved everything under it ~100 px. Since 2026-11-16 that view is the map,
    or the drawing where the map cannot be drawn."""

    body = PAGE[PAGE.index("  class Face {"):]
    body = body[:body.index("    adopt(svg) {")]
    assert 'this.box.classList.toggle("on-map", view === "map");' in body
    assert 'this.el.hidden = view !== "map";' in body


def test_the_plate_leaves_room_for_every_heading_a_pick_can_show():
    """Owner's report, 2026-11-15: a pick's headings above the rim were cut off,
    getBBox skipping the hidden ones, until a resize re-trimmed round them and
    the drawing dropped. The trim takes every heading, shown or not, so the
    plate is one height whatever is picked."""

    body = PAGE[PAGE.index("    space() {"):]
    body = body[:body.index("this.foot = ")]
    assert 'querySelectorAll("text.deg")' in body
    assert "y0 = Math.min(y0, Math.max(0, y - fs))" in body


def test_another_breaks_dot_is_its_tab():
    """Owner's request, 2026-11-15: tapping another break on the map opens its
    tab, through the switch the tab itself uses, before any other hit."""

    assert "point(o.position, {on: o.id === this.id, id: o.id})" in PAGE
    body = PAGE[PAGE.index("    click(e) {"):]
    body = body[:body.index("const hit = this.arrowAt(e.point);")]
    assert 'layers: ["sm-spots"]' in body and "!f.properties.on" in body
    assert "selectSwellTab(spot.properties.id)" in body


def test_a_switch_to_another_breaks_map_moves_as_the_mocks_one_map_does():
    """Owner's pick, 2026-11-15, from the "Seabed Map Themes" mock: a switch to
    another break's map eases it over 400 ms from the last tab's view to its own
    opening view -- centre, zoom and bearing together, as the mock's one map
    does. The owner saw that the first build, a turn round the break alone,
    moved differently. Set in the click, the clock started after the shown
    map's first frame, and not at all under reduced motion."""

    assert "const TURN_MS = 400;" in PAGE
    body = PAGE[PAGE.index("    turnFrom(prev) {"):]
    body = body[:body.index("    preTurn() {")]
    assert "prefers-reduced-motion: reduce" in body
    assert "prev.map.getCenter(), zoom: prev.map.getZoom(), bearing: prev.map.getBearing()" in body
    assert "const to = this.viewFor(this.b);" in body
    assert "this.map.easeTo({...to, duration: TURN_MS})" in body
    assert 'this.map.once("render"' in body
    assert "around" not in body
    assert "faces.forEach((f) => f.preTurn());" in PAGE


def test_a_changed_island_outline_asks_for_a_redraw_and_a_note_does_not(tmp_path):
    """The map draws the imaged Coronado Islands burned into the grids
    (BRIEFING §55), so the manifest fingerprints what is drawn: the
    outlines, their heights and the grids they go into, not the notes."""

    from forecast import seabedvector

    data = json.loads((ROOT / "data" / "bathymetry" / "islands.json").read_text())
    (tmp_path / "islands.json").write_text(json.dumps(data))
    base = seabedvector.retrieved(tmp_path)["islands"]
    data["_comment"] = "edited"
    (tmp_path / "islands.json").write_text(json.dumps(data))
    assert seabedvector.retrieved(tmp_path)["islands"] == base
    data["islands"][0]["height_m"] += 1.0
    (tmp_path / "islands.json").write_text(json.dumps(data))
    assert seabedvector.retrieved(tmp_path)["islands"] != base


def test_the_layer_list_is_the_owners_and_kept_on_the_device():
    """Owner's picks, 2026-11-16, from the "Seabed Map Themes" mock: a layer
    button top right, 4 px inside the hairline, the source line left of it;
    Windows, Shadows and Window edges, then Grayscale and Lines only, one look
    at a time; one choice for every map, kept through `stored` / `store`."""

    assert 'const LAYERS_KEY = "nado-waves.map-layers";' in PAGE
    assert "stored(LAYERS_KEY)" in PAGE and "store(LAYERS_KEY, JSON.stringify(layers));" in PAGE
    body = PAGE[PAGE.index('class="sm-lyrs"'):]
    body = body[:body.index("</div>`")]
    labels = re.findall(r"</span>([A-Z][\w ]+)</label>|data-(?:lyr|look)=\"\w+\">([A-Z][\w ]+)</label>", body)
    assert [a or b for a, b in labels] == ["Windows", "Shadows", "Window edges", "Grayscale", "Lines only"]
    # One look at a time: a look switched on replaces the other, off is colour.
    assert 'layers.look = box.checked ? box.dataset.look : "colour";' in PAGE
    assert ".sm-lyr{position:absolute;top:4px;right:4px;" in PAGE
    assert ".sm-attr{position:absolute;top:8px;left:40px;right:40px;" in PAGE
    # A switched-off window or shadow still lights when picked.
    assert '["case", ["get", "lit"], lit(th.windowOpacity), layers.win ? th.windowOpacity : 0]' in PAGE
    assert 'map.setLayoutProperty(id, "visibility", layers.edges ? "visible" : "none")' in PAGE


def test_the_maps_looks_are_the_owners():
    """Grayscale is the shipped themes at their own OKLab lightness, but the
    light page's rays near-black; Lines only is the mock's pair. The colour
    themes stay the default."""

    body = PAGE[PAGE.index("const MAP_LOOKS = {"):]
    body = body[:body.index("\n  };") + 4]
    grey, lines = body[:body.index("lines: {")], body[body.index("lines: {"):]
    assert 'land: "#e1e1e1"' in grey and 'land: "#363636"' in grey
    assert 'rays: "#25292c"' in grey and 'rays: "#dbdbdb"' in grey
    assert 'land: "#e3e8e6"' in lines and 'land: "#1d2c34"' in lines
    assert 'ink: "#16232b"' in lines
    assert "(MAP_LOOKS[layers.look] || {})[shownTheme()] || MAP_THEMES[shownTheme()]" in PAGE


def test_the_grey_look_is_each_colour_at_its_own_lightness():
    """Every grey in Grayscale is its colour theme's colour with a and b set to
    zero in OKLab (the page's own conversion), but the light page's rays."""

    def lab_l(h):
        lin = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        r, g, b = (lin(int(h[i:i + 2], 16) / 255) for i in (1, 3, 5))
        l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
        m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
        s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
        return 0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s

    def grey(h):
        L = lab_l(h)
        v = L ** 3                       # a = b = 0: l = m = s = L, so each channel is L^3
        c = 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055
        return "#" + f"{round(max(0, min(1, c)) * 255):02x}" * 3

    def block(src, start, mode):
        body = src[src.index(start):]
        body = body[body.index(f"{mode}: {{"):]
        return dict(re.findall(r'(\w+): "(#[0-9a-f]{6})"', body[:body.index("}")]))

    for mode in ("light", "dark"):
        colour = block(PAGE, "const MAP_THEMES = {", mode)
        looks = block(PAGE, "grey: {", mode)
        for key, hexval in colour.items():
            if mode == "light" and key == "rays":
                continue
            assert looks[key] == grey(hexval), (mode, key)


def test_window_edges_run_past_the_widest_view():
    """The dashed edge lines run EDGE_KM, past the farthest ground any view
    shows: the widest zoom `limits` allows, panned as far as `pull` lets it,
    on a 260 px map (map.md: ~1,030 km)."""

    import math

    from forecast import geomviz
    from forecast.siting import load_coordinates

    edge_km = int(re.search(r"const EDGE_KM = (\d+);", PAGE).group(1))
    assert "radial(p, e.bearing, e.range_km, EDGE_KM)" in PAGE
    tanner = load_coordinates()["46047"]

    def bearing(a, b):
        la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
        y = math.sin(lo2 - lo1) * math.cos(la2)
        x = math.cos(la1) * math.sin(la2) - math.sin(la1) * math.cos(la2) * math.cos(lo2 - lo1)
        return math.degrees(math.atan2(y, x))

    for b in geomviz.build()["breaks"]:
        p = b["position"]
        reach = geomviz.km(p, tanner) + 25
        rel = math.radians(bearing(p, tanner) - b["normal"])
        for w in (260, 390, 600):
            across, along = abs(math.sin(rel)) * reach, max(0.0, math.cos(rel)) * reach
            mpp = max(across * 1000 / (0.5 * w - 76), along * 1000 / (0.85 * w), 1)
            farthest = reach + math.hypot(w / 2, w / 2) * mpp / 1000
            assert farthest < edge_km, (b["id"], w, farthest)
