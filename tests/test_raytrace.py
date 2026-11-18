"""forecast.raytrace against the one case with a textbook answer.

On a planar beach -- straight, parallel depth contours -- refraction is
Snell's law, sin(θ)/c constant along a ray, and the energy reaching a point
from a narrow offshore beam is the offshore energy times Ks²·Kr², with
Ks² = cg0/cg and Kr² = cos θ0 / cos θ. Both are pinned here through the whole
chain: rays traced backward over a grid, the gain stored per heading, and the
spectrum integrated over nearshore headings the way the forecast will do it.

A total is not a validation of a mapping (BRIEFING §15), so the heading each
ray leaves deep water on is checked ray by ray, not just the energy sum.
"""

from __future__ import annotations

import math

import pytest

np = pytest.importorskip("numpy")

from forecast.raytrace import (  # noqa: E402
    DEEP, LAND, G, Bathymetry, Grid, speeds, trace, straight_line_blocker,
)
from forecast.geometry import load  # noqa: E402

SLOPE = 0.03
CELL = 20.0
WIDTH, HEIGHT = 30_000.0, 16_000.0
SHORE_Y = 1_000.0


def planar() -> Bathymetry:
    """Shore along y = SHORE_Y, sea to the north, depth = SLOPE * distance."""

    cols, rows = int(WIDTH / CELL), int(HEIGHT / CELL)
    ys = HEIGHT - (np.arange(rows) + 0.5) * CELL          # row 0 is the top
    depth = SLOPE * (ys - SHORE_Y)
    elevation = -np.repeat(depth[:, None], cols, axis=1)
    return Bathymetry([Grid.from_elevation(elevation, 0.0, HEIGHT, CELL, 0.0)], 0.0)


def start(bathy, h=10.0):
    return WIDTH / 2.0, SHORE_Y + h / SLOPE


@pytest.mark.parametrize("period", [8.0, 12.0, 16.0])
def test_rays_obey_snells_law(period):
    bathy = planar()
    x0, y0 = start(bathy)
    omega = 2 * math.pi / period
    c_n = float(speeds(omega, np.array([10.0]))[0][0])
    c0 = G / omega
    # Only headings Snell allows: past asin(c_n/c0) the ray turns back.
    limit = math.degrees(math.asin(c_n / c0))
    near = np.array([-0.9, -0.5, -0.1, 0.0, 0.1, 0.5, 0.9]) * limit % 360.0
    rays = trace(bathy, x0, y0, near, period)
    for theta_n, theta_0, status in zip(near, rays.off_from_deg, rays.status):
        assert status == DEEP
        rel_n = math.radians(((theta_n + 180) % 360) - 180)
        rel_0 = math.radians(((theta_0 + 180) % 360) - 180)
        assert math.sin(rel_0) == pytest.approx(math.sin(rel_n) * c0 / c_n, abs=2e-3)


def test_a_heading_snell_forbids_turns_back_onto_the_beach():
    """Total internal reflection: no deep-water heading arrives at 60° off
    the normal in 10 m of water at 12 s, so the backward ray turns and lands."""

    bathy = planar()
    x0, y0 = start(bathy)
    rays = trace(bathy, x0, y0, np.array([60.0]), 12.0)
    assert rays.status[0] == LAND


def test_a_ray_aimed_at_the_beach_from_behind_lands():
    bathy = planar()
    x0, y0 = start(bathy)
    rays = trace(bathy, x0, y0, np.array([180.0]), 10.0)
    assert rays.status[0] == LAND


@pytest.mark.parametrize("period,theta0", [(10.0, 0.0), (10.0, 25.0), (14.0, -30.0)])
def test_integrated_energy_is_ks2_kr2(period, theta0):
    """A narrow offshore beam, integrated over nearshore headings through the
    stored gain, has to come out at Ks²·Kr² of the offshore energy."""

    bathy = planar()
    x0, y0 = start(bathy)
    step = 0.1
    near = (np.arange(-89.95, 90.0, step)) % 360.0
    rays = trace(bathy, x0, y0, near, period)
    omega = 2 * math.pi / period
    c_n, cg_n, _ = speeds(omega, np.array([10.0]))
    c0 = G / omega
    gain = (c0 * 0.5 * c0) / float(c_n[0] * cg_n[0])

    width = 2.0                               # degrees, a narrow beam
    def s_off(theta):                         # unit energy, Gaussian in heading
        rel = ((theta - theta0 + 180.0) % 360.0) - 180.0
        return np.exp(-0.5 * (rel / width) ** 2) / (width * math.sqrt(2 * math.pi))

    ok = rays.status == DEEP
    e_near = float(np.sum(s_off(rays.off_from_deg[ok]) * gain) * step)

    t0 = math.radians(theta0)
    tn = math.asin(math.sin(t0) * float(c_n[0]) / c0)
    ks2 = (0.5 * c0) / float(cg_n[0])
    kr2 = math.cos(t0) / math.cos(tn)
    assert e_near == pytest.approx(ks2 * kr2, rel=0.01)


def test_the_deep_water_leg_is_tested_against_the_charted_blockers():
    """From a point west of Point Loma's tip, the peninsula's bearings are
    blocked and the open ocean to the west is not."""

    _, blockers = load()
    loma = next(b for b in blockers if b.name.startswith("Point Loma"))
    lat, lon = loma.a[0], loma.a[1] - 0.05
    assert straight_line_blocker(blockers, lat, lon, 270.0) is None
    assert straight_line_blocker(blockers, lat, lon, 45.0) == loma.name


# ------------------------------------------------------------ diffraction

from forecast.raytrace import Island, fresnel, island_transmission, slit  # noqa: E402


def test_fresnel_integrals_match_the_tabulated_values():
    c, s = fresnel(np.array([1.0, 0.5, -1.0, 60.0]))
    assert c[0] == pytest.approx(0.7798934, abs=1e-6)
    assert s[0] == pytest.approx(0.4382591, abs=1e-6)
    assert c[1] == pytest.approx(0.4923442, abs=1e-6)
    assert (c[2], s[2]) == pytest.approx((-c[0], -s[0]))
    assert (c[3], s[3]) == pytest.approx((0.5, 0.5), abs=0.01)


def test_a_straight_edge_leaves_a_quarter_of_the_energy_on_the_shadow_line():
    field = 1.0 - slit(np.array([0.0]), np.array([1e6]))
    assert abs(field[0]) ** 2 == pytest.approx(0.25, abs=1e-4)


def _through_strip(width, distance, period, offset):
    """A ray passing `offset` metres from the centre of a strip `width` wide,
    `distance` from the observer, in deep water."""

    island = Island("strip", (offset - width / 2, 0.0), (offset + width / 2, 0.0),
                    (offset, 0.0), width / 2, depth=5000.0)
    n = 1
    passes = {"strip": (np.zeros(n), np.zeros(n), np.full(n, math.pi / 2),
                        np.full(n, distance), np.ones(n, bool))}
    factor, geo = island_transmission(passes, [island], period)
    return float(factor[0]), float(geo[0])


def test_a_wide_island_close_by_casts_a_real_shadow():
    """Fresnel number W²/(λD) = 3000²/(225·3000) ≈ 13: the geometric limit."""

    factor, geo = _through_strip(3000.0, 3000.0, 12.0, 0.0)
    assert geo == 0.0
    assert factor < 0.05


def test_a_small_island_far_off_barely_shadows():
    """W²/(λD) = 300²/(351·31000) ≈ 0.008: the shadow is filled in, which is
    what the locals say about the Coronado Islands and what a hard block
    cannot say."""

    factor, geo = _through_strip(300.0, 31000.0, 15.0, 0.0)
    assert geo == 0.0
    assert factor > 0.8


def test_far_to_the_side_of_an_island_the_wave_is_untouched():
    factor, geo = _through_strip(3000.0, 3000.0, 12.0, 20000.0)
    assert geo == 1.0
    assert factor == pytest.approx(1.0, abs=0.02)


# ------------------------------------------------------------ headland edges

from forecast.raytrace import edge_factor  # noqa: E402


def test_a_headland_leaves_a_quarter_of_the_energy_on_its_shadow_line():
    got = edge_factor(np.array([0.0]), np.array([30.0]), np.array([5000.0]), 12.0)
    assert got[0] == pytest.approx(0.25, abs=1e-3)


def test_deep_in_a_headlands_shadow_almost_nothing_arrives():
    got = edge_factor(np.array([-2000.0]), np.array([30.0]), np.array([5000.0]), 12.0)
    assert got[0] < 0.01


def test_well_clear_of_a_headland_the_wave_is_untouched():
    got = edge_factor(np.array([3000.0]), np.array([30.0]), np.array([5000.0]), 12.0)
    assert got[0] == 1.0


def test_a_longer_wave_reaches_further_into_the_shadow():
    """The shadow fills with wavelength: at the same offset, a 16 s swell
    keeps more than an 8 s one."""

    off, depth, dist = np.array([-300.0]), np.array([30.0]), np.array([5000.0])
    assert edge_factor(off, depth, dist, 16.0)[0] > edge_factor(off, depth, dist, 8.0)[0]


# ------------------------------------------------------------ bottom friction

from forecast.raytrace import C_BOTTOM, friction_rate, wavenumber  # noqa: E402


@pytest.mark.parametrize("period", [8.0, 16.0])
def test_friction_along_a_ray_is_the_jonswap_integral(period):
    """Straight out from a planar beach, the factor the tracer stores is
    exp(−∫ C_b·ω²/(g²·sinh²kh·cg) ds), integrated here independently over
    depth (ds = dh / slope) from the start depth to deep water."""

    bathy = planar()
    x0, y0 = start(bathy)
    rays = trace(bathy, x0, y0, np.array([0.0]), period)
    assert rays.status[0] == DEEP

    omega = 2 * math.pi / period
    h = np.linspace(10.0, G * period ** 2 / (2 * math.pi), 200_001)
    k = wavenumber(omega, h)
    _, cg, _ = speeds(omega, h)
    rate = C_BOTTOM * omega ** 2 / (G ** 2 * np.sinh(k * h) ** 2 * cg)
    expected = math.exp(-float(np.sum(0.5 * (rate[1:] + rate[:-1]) * np.diff(h))) / SLOPE)
    assert float(rays.friction[0]) == pytest.approx(expected, rel=0.01)
    assert expected < 1.0


def test_long_swell_loses_more_to_the_bottom_than_short():
    """A 16 s wave feels the bottom from ten times as deep as an 8 s one."""

    bathy = planar()
    x0, y0 = start(bathy)
    short = trace(bathy, x0, y0, np.array([0.0]), 8.0).friction[0]
    long_ = trace(bathy, x0, y0, np.array([0.0]), 16.0).friction[0]
    assert long_ < short < 1.0


def test_deep_water_has_no_bottom_friction():
    omega = 2 * math.pi / 10.0
    assert float(friction_rate(omega, np.array([2000.0]))[0]) < 1e-12


@pytest.mark.parametrize("period", [8.0, 16.0])
def test_travel_time_along_a_ray_is_the_group_integral(period):
    """Straight out from a planar beach, the time the tracer stores is
    ∫ ds / cg, integrated here independently over depth (ds = dh / slope)."""

    bathy = planar()
    x0, y0 = start(bathy)
    rays = trace(bathy, x0, y0, np.array([0.0]), period)
    omega = 2 * math.pi / period
    h = np.linspace(10.0, G * period ** 2 / (2 * math.pi), 200_001)
    _, cg, _ = speeds(omega, h)
    expected = float(np.sum(0.5 * (1 / cg[1:] + 1 / cg[:-1]) * np.diff(h))) / SLOPE
    assert float(rays.time_s[0]) == pytest.approx(expected, rel=0.01)
    # Slower than deep water over the same path: the shelf holds it back.
    assert float(rays.time_s[0]) > float(rays.path_m[0]) / (G * period / (4 * math.pi)) * 0.9


def test_recording_paths_changes_nothing_the_tables_read():
    """`trace(record=True)` (the map fill's paths, 2026-11-10) only records:
    every status, heading, exit, friction and travel time is the same, and
    each path starts at the start point and ends at the ray's exit."""

    from forecast.raytrace import trace

    bathy = planar()
    x0, y0 = start(bathy)
    near = np.linspace(-60.0, 60.0, 13)
    plain = trace(bathy, x0, y0, near, 12.0)
    rec = trace(bathy, x0, y0, near, 12.0, record=True)
    assert plain.paths is None and len(rec.paths) == near.size
    assert np.array_equal(plain.status, rec.status)
    for a, b in ((plain.off_from_deg, rec.off_from_deg), (plain.exit_x, rec.exit_x),
                 (plain.exit_y, rec.exit_y), (plain.friction, rec.friction), (plain.time_s, rec.time_s)):
        assert np.array_equal(a, b)
    for i, p in enumerate(rec.paths):
        assert p[0][:2] == (x0, y0)
        assert p[-1][0] == rec.exit_x[i] and p[-1][1] == rec.exit_y[i]
        assert p[-1][2] == rec.time_s[i]


def test_tracing_with_edges_and_islands_runs_and_recording_changes_nothing():
    """The table build passes headland edges and islands to `trace`. From
    2026-11-10 to -15 the recorded paths shared a name with the edge and island
    bookkeeping, so any call with edges failed ('numpy.ndarray' object has no
    attribute 'append') and `python -m forecast.raytrace` could not rebuild the
    tables. With and without `record`, every ray and every edge and island
    record must come out the same."""

    from forecast.raytrace import Island

    bathy = planar()
    x0, y0 = start(bathy)
    near = np.linspace(-40.0, 40.0, 9) % 360.0
    edges = {"Point Loma": np.array([[x0 - 2_000.0, y0 + 3_000.0]])}

    def islands():
        return [Island("strip", (x0 + 1_000.0, 9_000.0), (x0 + 3_000.0, 9_000.0),
                       (x0 + 2_000.0, 9_000.0), 1_400.0)]

    plain = trace(bathy, x0, y0, near, 12.0, islands(), edges)
    rec = trace(bathy, x0, y0, near, 12.0, islands(), edges, record=True)
    assert plain.paths is None and len(rec.paths) == near.size
    assert np.array_equal(plain.status, rec.status)
    for a, b in ((plain.off_from_deg, rec.off_from_deg), (plain.exit_x, rec.exit_x),
                 (plain.time_s, rec.time_s)):
        assert np.array_equal(a, b)
    for name in edges:
        for a, b in zip(plain.edges[name], rec.edges[name]):
            assert np.array_equal(a, b, equal_nan=True)
    for a, b in zip(plain.passes["strip"], rec.passes["strip"]):
        assert np.array_equal(a, b, equal_nan=True)
    for i, p in enumerate(rec.paths):
        assert p[0][:2] == (x0, y0)
        assert p[-1][0] == rec.exit_x[i] and p[-1][1] == rec.exit_y[i]


# ------------------------------------------------------------ Madsen friction (BRIEFING §57)

from forecast import raytrace as RT  # noqa: E402


def test_recording_steps_changes_nothing_and_gives_the_friction_back():
    """`trace(steps=True)` records each ray's wet steps exactly as the
    friction integral sums them: every ray comes out the same, and the
    JONSWAP law marched over those steps at tide 0 is the stored friction to
    rounding — the control the Madsen table is built on."""

    bathy = planar()
    x0, y0 = start(bathy)
    near = np.linspace(-50.0, 50.0, 11)
    plain = trace(bathy, x0, y0, near, 13.0)
    rec = trace(bathy, x0, y0, near, 13.0, steps=True)
    assert plain.steps is None and len(rec.steps) == near.size
    for a, b in ((plain.status, rec.status), (plain.off_from_deg, rec.off_from_deg),
                 (plain.friction, rec.friction), (plain.time_s, rec.time_s)):
        assert np.array_equal(a, b)
    loss = RT.madsen_losses(rec.steps, 2 * math.pi / 13.0, tide_m=(0.0,), law="jonswap")
    assert np.allclose(np.exp(-loss[:, 0, 0, 0]), rec.friction, rtol=1e-12, atol=0)


def _madsen_by_depth(period, hs5, slope, h_start, tide=0.0, n=400_001):
    """Madsen's survival straight out from a planar beach, integrated here
    independently: over depth (ds = dh/slope), deep water inward, f_w solved
    (not looked up), the local height de-shoaled at the peak (= the period)."""

    omega = 2 * math.pi / period
    h = np.linspace(G * period ** 2 / (2 * math.pi), h_start, n)    # deep -> start
    hh = np.maximum(h + tide, RT.H_LAND)
    k = RT.wavenumber(omega, hh)
    _, cg, _ = speeds(omega, hh)
    _, cg5, _ = speeds(omega, np.array([RT.H_REF + tide]))
    sh = np.sinh(np.minimum(k * hh, 300.0))
    shape = omega ** 2 / (G ** 2 * sh ** 2 * cg)
    ln_f = 0.0
    ds = abs(h[1] - h[0]) / slope
    for i in range(h.size - 1):
        hs_loc = hs5 * math.sqrt(cg5[0] / cg[i]) * math.exp(0.5 * ln_f)
        exc = hs_loc / (4.0 * sh[i])
        c = float(RT.madsen_fw(np.array([math.sqrt(2.0) * exc]))[0]) * G * omega * exc / math.sqrt(2.0)
        ln_f -= c * shape[i] * ds
    return math.exp(ln_f)


@pytest.mark.parametrize("period,hs5", [(10.0, 1.0), (16.0, 2.5)])
def test_madsen_along_a_ray_is_the_madsen_integral(period, hs5):
    """The table's march on the tracer's own steps against an independent
    integral of the same law over depth: the same survival to 1%."""

    bathy = planar()
    x0, y0 = start(bathy)
    rays = trace(bathy, x0, y0, np.array([0.0]), period, steps=True)
    got = RT.madsen_losses(rays.steps, 2 * math.pi / period, hs_m=(hs5,),
                           peak_hz=(1.0 / period,), tide_m=(0.0,))
    expected = _madsen_by_depth(period, hs5, SLOPE, 10.0)
    assert math.exp(-float(got[0, 0, 0, 0])) == pytest.approx(expected, rel=0.01)
    assert expected < 1.0


def test_madsen_takes_more_from_a_bigger_sea_and_less_at_high_tide():
    """Madsen's loss grows with the height (the orbital velocity), JONSWAP's
    does not; deeper water at high tide takes less."""

    bathy = planar()
    x0, y0 = start(bathy)
    rays = trace(bathy, x0, y0, np.array([0.0, 20.0]), 14.0, steps=True)
    loss = RT.madsen_losses(rays.steps, 2 * math.pi / 14.0, hs_m=(0.5, 1.0, 2.0, 4.0),
                            peak_hz=(1 / 14.0,), tide_m=(-1.0, 0.0, 1.0))
    assert np.all(np.diff(loss, axis=3) > 0)          # with height
    assert np.all(np.diff(loss, axis=2) < 0)          # with tide
    jons = RT.madsen_losses(rays.steps, 2 * math.pi / 14.0, hs_m=(0.5, 4.0),
                            peak_hz=(1 / 14.0,), tide_m=(0.0,), law="jonswap")
    assert np.allclose(jons[..., 0], jons[..., 1])


def test_the_looked_up_friction_factor_is_madsens():
    ab = np.geomspace(1e-3, 50.0, 997)
    assert np.max(np.abs(RT.fw_lookup(ab) / RT.madsen_fw(ab) - 1)) < 1e-3


def test_the_compressed_table_gives_every_path_back_within_tolerance():
    bathy = planar()
    x0, y0 = start(bathy)
    rays = trace(bathy, x0, y0, np.linspace(-60.0, 60.0, 25), 12.0, steps=True)
    loss = RT.madsen_losses(rays.steps, 2 * math.pi / 12.0).reshape(25, -1)
    weights, basis, err = RT.compress_losses(loss)
    rebuilt = np.array(weights) @ np.array(basis)
    assert err <= RT.MADSEN_LOSS_TOL
    assert np.max(np.abs(rebuilt - np.minimum(loss, RT.MADSEN_LOSS_CAP))) == pytest.approx(err)
    assert len(basis) < loss.shape[1]


@pytest.mark.parametrize("break_id", RT.BREAKS)
def test_the_committed_madsen_tables_describe_their_nodes(break_id):
    import json

    doc = json.loads((RT.OUT_DIR / f"{break_id}_madsen.json").read_text())
    meta = doc["meta"]
    assert meta["hs_m"] == list(RT.MADSEN_HS_M)
    assert meta["peak_hz"] == list(RT.MADSEN_PEAK_HZ)
    assert meta["tide_m"] == list(RT.MADSEN_TIDE_M)
    assert meta["k_n_m"] == RT.MADSEN_K_N and meta["m_f"] == RT.MADSEN_M_F
    assert meta["max_error"] <= RT.MADSEN_LOSS_TOL
    nodes = len(RT.MADSEN_HS_M) * len(RT.MADSEN_PEAK_HZ) * len(RT.MADSEN_TIDE_M)
    for v in doc["freqs"].values():
        assert len(v["basis"]) == v["rank"]
        assert all(len(row) == nodes for row in v["basis"])
        assert all(len(w) == v["rank"] for w in v["paths"])


def test_the_committed_madsen_table_is_what_the_code_builds():
    """One frequency of one break rebuilt from the seabed: the same table,
    number for number, so the committed file is the code's."""

    import json

    from forecast.geometry import load as load_geometry

    bathy = Bathymetry.load()
    spots, blockers = load_geometry()
    spot = {s.id: s for s in spots}["coronado_center"]
    built: dict = {}
    rows, _ = RT.table(bathy, spot, blockers, [0.101], madsen_out=built)
    doc = json.loads((RT.OUT_DIR / "coronado_center_madsen.json").read_text())
    assert built["0.1010"] == doc["freqs"]["0.1010"]


# ------------------------------------------------------------ the fill's starts

from forecast.raytrace import PATH_LEG_DEPTH, deep_leg  # noqa: E402


def test_a_deep_leg_runs_to_where_the_seabed_ends():
    """Over water that only deepens, a ray's straight leg runs back from its
    exit to the grid's edge: as far out as anything is traced."""

    bathy = planar()
    period = 8.0
    l0 = G * period ** 2 / (2 * math.pi)
    x0, y0 = WIDTH / 2.0, SHORE_Y + l0 / SLOPE           # the exit, at L0
    got = float(deep_leg(bathy, np.array([x0]), np.array([y0]), np.array([0.0]), period)[0])
    to_edge = HEIGHT - CELL - y0                          # `inside` keeps one cell clear
    assert to_edge - CELL <= got <= to_edge


def test_a_deep_leg_stops_short_of_water_that_would_bend_it():
    """A bank shallower than L0/2 across the leg ends it on the near side: a
    straight line over it would not be physics."""

    bathy = planar()
    period = 8.0
    l0 = G * period ** 2 / (2 * math.pi)
    grid = bathy.grids[0]
    rows = grid.depth.shape[0]
    ys = HEIGHT - (np.arange(rows) + 0.5) * CELL
    bank = (ys > 12_000.0) & (ys < 12_500.0)
    grid.depth[bank, :] = 0.4 * l0
    x0, y0 = WIDTH / 2.0, SHORE_Y + l0 / SLOPE
    got = float(deep_leg(bathy, np.array([x0]), np.array([y0]), np.array([0.0]), period)[0])
    assert 12_000.0 - y0 - 2 * CELL <= got <= 12_000.0 - y0 + CELL
    assert PATH_LEG_DEPTH == 0.5


def test_every_drawn_ray_starts_as_far_out_as_it_is_traced():
    """BRIEFING §52: a fill ray starts where the grids the rays are traced
    over end, or where the next step out along its offshore heading is land
    or water shallower than L0/2 -- never on the line through 46232 for its
    own sake. Its clock there is still minutes after the swell passed 46232:
    the plane-wave offset from that line, at the deep-water group speed."""

    import json
    from pathlib import Path

    from forecast.raytrace import H_LAND, OUT_DIR, STEP_FRACTION, Bathymetry
    from forecast.siting import load_coordinates
    from forecast.utm import to_utm

    bathy = Bathymetry.load()
    bx, by = to_utm(*load_coordinates()["46232"])
    step = STEP_FRACTION * max(g.cell for g in bathy.grids)
    for break_id in ("coronado_north", "coronado_center", "coronado_south"):
        paths = json.loads((Path(OUT_DIR) / f"{break_id}_paths.json").read_text())
        assert paths["leg_depth_l0"] == PATH_LEG_DEPTH
        for key, rays in paths["rays"].items():
            period = 1.0 / float(key)
            l0 = G * period ** 2 / (2 * math.pi)
            cg0 = G * period / (4 * math.pi)
            xs, ys, us, vs = [], [], [], []
            for _, off, pts in rays:
                sx, sy = to_utm(*pts[0][:2])
                th = math.radians(off)
                offset = (sx - bx) * -math.sin(th) + (sy - by) * -math.cos(th)
                assert pts[0][2] == pytest.approx(offset / cg0 / 60.0, abs=0.02), (break_id, key, off)
                xs.append(sx); ys.append(sy); us.append(math.sin(th)); vs.append(math.cos(th))
            # One step out, with room for the file's rounding (1e-5 degree,
            # about a metre, and 0.01 degree of heading): 5 m more, and 2% on
            # the depth -- of ~7,000 rays, one starts that close to a grid's
            # edge and one runs along the L0/2 contour itself (4.5 s, 16.1 m).
            out = step + 5.0
            x, y = np.array(xs) + out * np.array(us), np.array(ys) + out * np.array(vs)
            h, _, _, _, covered = bathy.sample(x, y)
            stopped = ~covered | ~np.isfinite(h) | (h <= H_LAND) | (h < 1.02 * PATH_LEG_DEPTH * l0)
            assert stopped.all(), (break_id, key, int((~stopped).sum()))


# ------------------------------------------------------------ islands as land
#
# Owner's decisions, 2026-11-15 (group 2d, BRIEFING §55): the imaged islands
# are burned into the grids GMRT left them out of; a ray that lands on an
# island gets energy by diffraction only, along a clear neighbour's heading,
# instead of being re-traced over a made-up "see-through" seabed; and the
# straight deep-water leg is walked over the grids for land.

from forecast.raytrace import (  # noqa: E402
    BATHY_DIR, ISLAND_PREFIX, H_LAND, burn_islands, island_outlines, leg_land,
    shadow_factor, with_islands,
)


def _square(x0, y0, side):
    return np.array([(x0, y0), (x0 + side, y0), (x0 + side, y0 + side), (x0, y0 + side)])


def test_a_cell_is_burned_where_a_quarter_of_it_is_island():
    """A 100 m cell grid at 30 m depth; an island 150 m square starting half
    way into the top-left cell covers that cell by a quarter, the two beside
    it by a half and the one diagonal to it whole: all island. The cells
    beyond it are untouched, and land the grid already had higher than the
    island keeps its own height."""

    depth = np.full((4, 4), 30.0)
    depth[3, 3] = -80.0                                   # a grid's own peak
    island = {"name": "test", "height_m": 20.0,
              "parts": [_square(50.0, 400.0 - 50.0 - 150.0, 150.0)]}
    island2 = {"name": "peak", "height_m": 20.0, "parts": [_square(300.0, 0.0, 100.0)]}
    changed = burn_islands(depth, 0.0, 400.0, 100.0, [island, island2])
    assert (depth[0:2, 0:2] == -20.0).all()          # 25-50% covered: land
    assert (depth[2:, :2] == 30.0).all() and (depth[:2, 2:] == 30.0).all()
    assert depth[3, 3] == -80.0                      # higher land keeps its height
    assert changed == 4


def test_the_islands_are_burned_only_into_the_grids_named_for_them():
    outlines, into = island_outlines()
    assert {o["name"] for o in outlines} == {"South Coronado", "Middle Coronado", "North Coronado"}
    assert into == ("outer", "context")
    grid = Grid.from_elevation(np.zeros((3, 3)) - 10.0, 0.0, 300.0, 100.0, 0.0)
    assert with_islands(grid, "regional") is grid


def test_every_island_is_land_where_the_rays_are_traced():
    """GMRT's 90 m grid had only South Coronado as land: Middle Coronado read
    10-14 m deep and North Coronado 22 m and more (BRIEFING §52). Burned in,
    each island's imaged vertex (spots.json) and the middle of its outline
    are land for the rays."""

    from forecast.utm import to_utm

    bathy = Bathymetry.load()
    _, blockers = load()
    outlines, _ = island_outlines()
    for o in outlines:
        main = max(o["parts"], key=len)
        x, y = main.mean(axis=0)
        h, *_ = bathy.sample(np.array([x]), np.array([y]))
        assert h[0] <= H_LAND, o["name"]
    # Each vertex is within one 90 m cell of land, read the way the rays read
    # it. Not on it: North Coronado's `a` is the tip of a 2,565 m2 islet,
    # too small to fill a quarter of a cell, and its shadow comes in through
    # `a` itself, the Babinet edge.
    ring = np.radians(np.arange(0.0, 360.0, 45.0))
    for b in blockers:
        if b.name.startswith(ISLAND_PREFIX):
            for p in (b.a, b.b):
                x, y = to_utm(*p)
                h, *_ = bathy.sample(x + 90.0 * np.sin(ring), y + 90.0 * np.cos(ring))
                assert h.min() <= H_LAND, (b.name, p)


def test_each_imaged_vertex_sits_on_its_islands_outline():
    """The outlines and spots.json come from the same imagery: South
    Coronado's tip and North Coronado's ends lie within a few metres of an
    outline (measured 3, 1.5 and 0.2 m)."""

    from forecast.utm import to_utm

    _, blockers = load()
    rings = [r for o in island_outlines()[0] for r in o["parts"]]

    def gap(p):
        x, y = to_utm(*p)
        best = np.inf
        for r in rings:
            a, b = r, np.roll(r, -1, axis=0)
            d = b - a
            t = np.clip(((x - a[:, 0]) * d[:, 0] + (y - a[:, 1]) * d[:, 1]) / np.maximum((d ** 2).sum(1), 1e-9), 0, 1)
            best = min(best, float(np.min(np.hypot(a[:, 0] + t * d[:, 0] - x, a[:, 1] + t * d[:, 1] - y))))
        return best

    south = next(b for b in blockers if b.name.startswith("Coronado Islands (South"))
    north = next(b for b in blockers if b.name.startswith("Coronado Islands (North"))
    for p in (south.a, north.a, north.b):
        assert gap(p) < 8.0, p


def test_a_leg_across_land_is_blocked_and_one_across_an_island_is_not():
    """The straight leg is walked over the grids: a ray leaving deep water
    and heading back across a spit of land is stopped by it, one crossing an
    island's land is not (the island is diffracted on the leg), and open
    water stays open."""

    bathy = planar()
    depth = bathy.grids[0].depth.copy()
    rows, cols = depth.shape
    ys = HEIGHT - (np.arange(rows) + 0.5) * CELL
    xs = (np.arange(cols) + 0.5) * CELL
    spit = (np.abs(xs[None, :] - 20_000.0) < 100.0) & (ys[:, None] > 5_000.0)
    isle = (np.hypot(xs[None, :] - 10_000.0, ys[:, None] - 12_000.0) < 200.0)
    depth[spit | isle] = -5.0
    bathy = Bathymetry([Grid.from_depth(depth, 0.0, HEIGHT, CELL)], 0.0)
    island = Island("isle", (9_800.0, 12_000.0), (10_200.0, 12_000.0), (10_000.0, 12_000.0), 600.0)
    x = np.array([15_000.0, 15_000.0, 15_000.0])
    y = np.array([12_000.0, 12_000.0, 12_000.0])
    hit, hx, _ = leg_land(bathy, [island], x, y, np.array([90.0, 270.0, 0.0]))
    assert hit.tolist() == [True, False, False]
    assert 19_800.0 < hx[0] < 20_000.0


def test_a_ray_heading_back_across_the_silver_strand_is_blocked():
    """BRIEFING §55: from North's 5 m start point a short ray leaving deep
    water from the south-east crosses the Coronado shore within a few
    kilometres; the charted blockers' spans never saw that land. Swell from
    the south-west stays open."""

    from forecast.raytrace import islands_from, start_point
    from forecast.utm import to_utm  # noqa: F401

    spots, blockers = load()
    bathy = Bathymetry.load()
    north = next(s for s in spots if s.id == "coronado_north")
    x0, y0, _ = start_point(bathy, north)
    hit, _, _ = leg_land(bathy, islands_from(blockers), np.array([x0, x0]), np.array([y0, y0]),
                         np.array([140.0, 230.0]))
    assert hit.tolist() == [True, False]


def test_a_shadowed_ray_takes_the_slit_geometry_between_its_neighbours():
    """`shadow_factor` at either end of the interpolation is the Babinet factor
    of that neighbour's own geometry, and half way across the shadow of a
    wide, near island it is deep shadow."""

    island = Island("strip", (-1_500.0, 0.0), (1_500.0, 0.0), (0.0, 0.0), 1_500.0, depth=5000.0)
    beta = np.full(2, math.pi / 2)
    rec = (np.array([-2_000.0, 2_000.0]), np.zeros(2), beta, np.full(2, 3_000.0), np.ones(2, bool))
    for j in (0, 1):
        one = {"strip": tuple(np.array([v[j]]) for v in rec)}
        want, _ = island_transmission(one, [island], 12.0)
        assert shadow_factor(rec, (0, 1), float(j), island, 12.0) == pytest.approx(float(want[0]))
    assert shadow_factor(rec, (0, 1), 0.5, island, 12.0) < 0.05


def test_every_shadowed_island_ray_carries_a_clear_neighbours_heading():
    """In the committed tables, every row that landed on an island and still
    carries energy goes out along the offshore heading of a clear row of the
    same period: nothing comes through a made-up seabed any more."""

    import csv

    for brk in ("coronado_north", "coronado_center", "coronado_south"):
        clear, shadowed = {}, []
        path = BATHY_DIR.parent / "nearshore" / f"{brk}.csv"
        with path.open(newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if float(r["gain"]) > 0:
                    clear.setdefault(r["freq_hz"], set()).add(r["off_from_deg"])
                elif r["status"] == "land" and r["blocker"].startswith(ISLAND_PREFIX) and float(r["diff_gain"]) > 0:
                    shadowed.append(r)
        assert shadowed, brk
        for r in shadowed:
            assert r["diff_off_from_deg"] in clear[r["freq_hz"]], (brk, r["period_s"], r["near_from_deg"])
