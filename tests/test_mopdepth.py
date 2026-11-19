"""forecast.mopdepth: the chain's own rays from CDIP MOP's points (BRIEFING §56b).

Report-only and precompute-side (numpy). What is pinned here is that it
starts where it says, sums energy exactly as `nearshore.carry` does, and
compares to MOP without a de-shoaling or normalisation slipped onto one side.
The row-for-row rebuild of the committed tables is `python -m
forecast.mopdepth --control` (~3 min a table), recorded in docs/mop_depth.md.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")

from forecast import mopcheck, mopdepth, raytrace as RT  # noqa: E402
from forecast.geometry import load  # noqa: E402

POINTS = json.loads((mopdepth.MOP_DIR / "points.json").read_text())["breaks"]


def committed(break_id):
    meta = json.loads((RT.OUT_DIR / f"{break_id}.json").read_text())
    return RT.committed_rows(break_id), meta


def test_each_start_is_where_it_says():
    bathy = RT.Bathymetry.load()
    spots = {s.id: s for s in load()[0]}
    for b, p in POINTS.items():
        spot = spots[b]
        # The shipped start is the default: h_ref changes nothing unless given.
        _, meta = committed(b)
        x, y, h = RT.start_point(bathy, mopdepth.spot_for("break_5m", spot, p),
                                 mopdepth.h_ref_for("break_5m", bathy, p))
        lat, lon = RT.from_utm(x, y)
        assert (round(lat, 6), round(lon, 6), round(h, 2)) == (
            meta["start_lat"], meta["start_lon"], meta["start_depth_m"])
        # At the MOP point: one 2 m step seaward of it, at the seabed's depth.
        mx, my = RT.to_utm(p["lat"], p["lon"])
        for v in ("mop", "mop_back"):
            x, y, h = RT.start_point(bathy, mopdepth.spot_for(v, spot, p), mopdepth.h_ref_for(v, bathy, p))
            assert math.hypot(x - mx, y - my) == pytest.approx(2.0, abs=1e-6), (b, v)
            assert h == pytest.approx(mopdepth.seabed_at(bathy, p["lat"], p["lon"]), abs=0.1)
        # The reversed chord's initial bearing is a great circle's: 0.003° off exact.
        assert mopdepth.spot_for("mop_back", spot, p).normal == pytest.approx((spot.normal + 180) % 360, abs=0.01)
        # Along the break's own normal, out to the MOP point's depth.
        x, y, h = RT.start_point(bathy, spot, mopdepth.h_ref_for("normal_mop", bathy, p))
        assert h >= mopdepth.seabed_at(bathy, p["lat"], p["lon"]) - 0.01


def test_the_vectorised_sum_is_nearshore_carrys():
    """`carry_parts` against `nearshore.carry` (its e_eq and e_hard) on the
    committed Center table and real spectra; the kinds partition the total."""

    from forecast.nearshore import carry, density_grids, load_tables
    from forecast.transform import load_spectra

    rows, meta = committed("coronado_center")
    arrays = mopdepth.Arrays(rows, float(meta["start_depth_m"]))
    table = load_tables()["coronado_center"]
    spectra = list(load_spectra(Path(mopcheck.ROOT) / "data" / "spectra" / "46232", limit=5))
    for sp in spectra:
        mem = sp.with_spread("mem")
        grids = density_grids(mem)
        n = carry(mem, table, grids)
        p = mopdepth.carry_parts(mem, grids, arrays)
        assert 4 * math.sqrt(p["eq"]) == pytest.approx(n.hs_equivalent, rel=1e-9)
        assert 4 * math.sqrt(p["hard"]) == pytest.approx(n.hs_hard, rel=1e-9)
        assert p["kinds"].sum() == pytest.approx(p["eq"], rel=1e-12)
        assert p["heading"].sum() == pytest.approx(p["eq"], rel=1e-12)


def test_the_two_half_fans_add_without_double_counting():
    rows, meta = committed("coronado_center")
    a = mopdepth.Arrays(rows, float(meta["start_depth_m"]))
    empty = mopdepth.Arrays([], float(meta["start_depth_m"]))
    both = a.merged(a)
    for f in a.freqs:
        assert both.f[f]["dgain"].size == 2 * a.f[f]["dgain"].size
        assert a.merged(empty).f[f]["dgain"].size == a.f[f]["dgain"].size


def test_a_mop_series_made_from_the_chain_at_mop_compares_as_exactly_one(tmp_path):
    """Known answer, as mopcheck's: a MOP series that says what the chain's
    table says (shoaled to MOP's depth at MOP's period) compares as 1."""

    from forecast.nearshore import density_grids
    from forecast.transform import load_spectra

    rows, meta = committed("coronado_south")
    arrays = mopdepth.Arrays(rows, float(meta["start_depth_m"]))
    spectra = list(load_spectra(Path(mopcheck.ROOT) / "data" / "spectra" / "46232", limit=6))
    depth, tp = 10.0, 13.0
    path = tmp_path / "coronado_south.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["valid_utc", "hs_m", "tp_s", "dp_deg"])
        for sp in spectra:
            mem = sp.with_spread("mem")
            h0 = 4 * math.sqrt(mopdepth.carry_parts(mem, density_grids(mem), arrays)["eq"])
            w.writerow([sp.time.strftime("%Y-%m-%dT%H:%M:%SZ"), f"{h0 * mopcheck.ks(tp, depth):.9f}", tp, 250])
    tables = {v: arrays for v in ("break_5m", "normal_mop", "mop")}
    out = mopdepth.hours("coronado_south", mopcheck.read_mop(path), spectra, tables, depth, depth + 0.765)
    assert len(out) == len(spectra)
    for r in out:
        assert r["mop_eq"] / r["mop"] == pytest.approx(1.0, rel=1e-6)
        # De-shoaled from deeper water, MOP's deep-water figure is larger.
        assert r["mop_navd"] > r["mop"]


def test_splitting_into_bands_keeps_every_bit_of_energy():
    freqs = [0.025 + 0.005 * i for i in range(20)] + [0.13 + 0.01 * i for i in range(20)]
    edges = mopdepth.bin_edges(freqs)
    assert all(abs(edges[i][1] - edges[i + 1][0]) < 1e-12 for i in range(len(edges) - 1))
    vals = [(1.0 + i, lo, hi) for i, (lo, hi) in enumerate(edges)]
    coarse = [(edges[0][0], 0.06), (0.06, 0.1), (0.1, 0.2), (0.2, edges[-1][1])]
    assert sum(mopdepth.split(vals, coarse)) == pytest.approx(sum(v for v, _, _ in vals), rel=1e-12)
    # The common range is clipped to what both sides cover.
    got = mopdepth.common_bands([(0.05, 0.04, 0.06), (0.3, 0.29, 0.31)], freqs)
    assert got[0][0] == pytest.approx(0.04) and got[-1][1] == pytest.approx(0.31)


def _spec_from_chain(spectra, arrays, depth, moments_from=None):
    """A MOP spectrum on 46232's own bins that says exactly what chain-at-MOP
    says, shoaled to MOP's depth band by band."""

    from forecast.nearshore import density_grids

    freqs = spectra[0].frequencies
    bands = [(f, lo, hi) for f, (lo, hi) in zip(freqs, mopdepth.bin_edges(freqs))]
    energy, moments, series = {}, {}, {}
    for sp in spectra:
        mem = sp.with_spread("mem")
        by_f = mopdepth.carry_parts(mem, density_grids(mem), arrays)["by_f"]
        row = [by_f.get(f, 0.0) / (hi - lo) * mopdepth.rt_shoaling(f, depth) for f, lo, hi in bands]
        energy[sp.time] = row
        hs = 4 * math.sqrt(sum(e * (hi - lo) for e, (_, lo, hi) in zip(row, bands)))
        series[sp.time] = (hs, 13.0, 250.0)
        if moments_from is not None:
            th = math.radians(moments_from)
            moments[sp.time] = [math.cos(th)] * len(bands) + [math.sin(th)] * len(bands) + [0.0] * (2 * len(bands))
    spec = {"bands": bands, "energy": energy, "moments": moments or None,
            "meta": {"spectrum": {"readback": {"ok": True}}}}
    return spec, series


def test_a_mop_spectrum_made_from_the_chain_compares_as_exactly_one_in_every_band():
    """Known answer: catches a de-shoaling, a band width or a bin edge
    applied on one side only."""

    from forecast.transform import load_spectra

    rows, meta = committed("coronado_south")
    arrays = mopdepth.Arrays(rows, float(meta["start_depth_m"]))
    spectra = list(load_spectra(Path(mopcheck.ROOT) / "data" / "spectra" / "46232", limit=4))
    depth = 10.0
    spec, series = _spec_from_chain(spectra, arrays, depth, moments_from=250.0)
    coarse = mopdepth.common_bands(spec["bands"], spectra[0].frequencies)
    conv, med = mopdepth.convention(spec, series)
    assert conv.startswith("from, clockwise from north") and med[conv] == pytest.approx(0.0, abs=1e-6)
    tables = {v: arrays for v in ("break_5m", "normal_mop", "mop")}
    out = mopdepth.hours("coronado_south", series, spectra, tables, depth, depth + 0.765, spec, coarse, conv)
    assert len(out) == len(spectra)
    for r in out:
        b = r["band"]
        for k in range(len(coarse)):
            assert b["chain"][k] == pytest.approx(b["mop"][k], rel=1e-9, abs=1e-15)
        assert r["mop_eq"] / r["mop_bandwise"] == pytest.approx(1.0, rel=1e-9)
        assert b["point_hs"] == pytest.approx(r["hs_mop"], rel=1e-12)
        assert r["mop_bandwise_navd"] > r["mop_bandwise"]
        assert all(d == pytest.approx(250.0) for d in b["mop_dir"])
    text = "\n".join(mopdepth.band_report(out, spec, "", coarse, conv, med))
    assert "1.00 [1.00, 1.00]" in text


def test_the_direction_convention_is_read_off_mops_own_dp():
    from forecast.transform import load_spectra

    rows, meta = committed("coronado_south")
    arrays = mopdepth.Arrays(rows, float(meta["start_depth_m"]))
    spectra = list(load_spectra(Path(mopcheck.ROOT) / "data" / "spectra" / "46232", limit=2))
    # Moments that point the way the waves go: the "toward" mapping is taken.
    spec, series = _spec_from_chain(spectra, arrays, 10.0, moments_from=70.0)
    conv, med = mopdepth.convention(spec, series)
    assert conv.startswith("toward, clockwise from north")
    # Moments unrelated to Dp: none is taken, rather than the least bad.
    spec, series = _spec_from_chain(spectra, arrays, 10.0, moments_from=10.0)
    series = {t: (h, tp, 205.0 if i % 2 else 115.0) for i, (t, (h, tp, _)) in enumerate(series.items())}
    assert mopdepth.convention(spec, series)[0] is None


def test_a_spectrum_that_did_not_read_back_is_refused(tmp_path):
    (tmp_path / "coronado_center_meta.json").write_text(json.dumps({"spectrum": {"readback": {"ok": False}}}))
    (tmp_path / "coronado_center_spectrum.csv").write_text("valid_utc,e00\n")
    (tmp_path / "coronado_center_bands.csv").write_text("band,freq_hz,lower_hz,upper_hz,bandwidth_hz\n")
    spec, why = mopdepth.read_mop_spectrum(tmp_path, "coronado_center")
    assert spec is None and "read-back" in why
    assert mopdepth.read_mop_spectrum(tmp_path, "coronado_south")[0] is None


# ------------------------------------------------------------------ a point that is not a break (24b)

def test_a_point_that_is_not_a_break_holds_mops_own_normal_exactly():
    """`point_spot` takes MOP's metaShoreNormal as the normal, exactly; the
    back half is +180 exactly; the synthesised chord agrees with it (it is
    only there so anything reading a chord finds a consistent one)."""

    for b, p in POINTS.items():
        n = mopdepth.mop_normal(json.loads((mopdepth.MOP_DIR / f"{b}_meta.json").read_text()))
        assert n is not None and 200 < n < 230, b
        s = mopdepth.point_spot("somewhere", p, n)
        assert s.normal == n % 360 and s.id == "somewhere"
        assert mopdepth.point_spot("somewhere", p, n, back=True).normal == pytest.approx((n + 180) % 360, abs=1e-12)
        assert (s.shore_bearing + 90) % 360 == pytest.approx(n, abs=1e-3)
        assert not s.position_verified and not s.shoreline_verified
    assert mopdepth.mop_normal({"small_variables": {"ascii": "metaSiteLabel, \"D0001\"\n"}}) is None


def test_the_point_path_starts_where_the_break_path_does():
    """Given Center's MOP point and Center's own normal, the point path starts
    at the same place and depth as the break path's `mop` start (the full
    row-for-row table control is in the report: ~2 min a table)."""

    bathy = RT.Bathymetry.load()
    spots = {s.id: s for s in load()[0]}
    for b, p in POINTS.items():
        a = RT.start_point(bathy, mopdepth.spot_for("mop", spots[b], p), mopdepth.MOP_H_REF)
        c = RT.start_point(bathy, mopdepth.point_spot(b, p, spots[b].normal), mopdepth.MOP_H_REF)
        assert a == c, b


def test_a_point_that_is_not_a_break_has_no_break_starts():
    p = POINTS["coronado_center"]
    for v in ("break_5m", "normal_mop"):
        with pytest.raises(ValueError):
            mopdepth.build("imperial_beach", v, p, normal=250.0)


def test_the_windows_at_the_coronado_mop_points_are_56bs():
    """The straight-line Point Loma edge at D0181 / D0179 / D0168 is
    BRIEFING §56b's 258.8 / 258.9 / 265.8°, with MOP's own normals."""

    want = {"coronado_north": "258.8", "coronado_center": "258.9", "coronado_south": "265.8"}
    for b, p in POINTS.items():
        n = mopdepth.mop_normal(json.loads((mopdepth.MOP_DIR / f"{b}_meta.json").read_text()))
        pl = [w for w in mopdepth.windows_at(b, p, n) if "Point Loma" in w]
        assert pl[-1].split(" – ")[-1].startswith(want[b] + "°"), (b, pl)


def test_the_side_by_side_is_on_the_hours_every_place_shares():
    from datetime import datetime, timedelta, timezone

    t0 = datetime(2026, 8, 4, tzinfo=timezone.utc)
    coarse = [(0.05, 0.1), (0.1, 0.2)]

    def row(h, ratio):
        return {"time": t0 + timedelta(hours=h), "from": 280.0, "mop_eq": ratio, "mop_bandwise": 1.0,
                "band": {"mop": [1.0, 1.0], "chain": [ratio ** 2, ratio ** 2], "buoy": [1.0, 1.0]}}

    places = {"a": [row(0, 1.2), row(1, 1.2), row(2, 9.0)], "b": [row(0, 1.0), row(1, 1.0)]}
    text = "\n".join(mopdepth.exposed_report(places, coarse, {"a": "x", "b": "y"}))
    assert "on the 2 hours" in text
    assert "| W-WNW | a (x) | 2 | 1.20 | 1.20 | 1.20 |" in text
    assert "| W-WNW | b (y) | 2 | 1.00 | 1.00 | 1.00 |" in text
