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
