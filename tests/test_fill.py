"""forecast.fill — the Swell card map's fill on LIVE (2026-11-10): each train's
energy credited ray by ray, against the chain's own 5 m height."""

import json
from pathlib import Path

import pytest

from forecast import fill

ROOT = Path(__file__).resolve().parent.parent
NEARSHORE = ROOT / "data" / "nearshore"
BREAKS = ("coronado_north", "coronado_center", "coronado_south")


def test_the_band_is_the_paths_band():
    pytest.importorskip("numpy")
    from forecast import raytrace

    assert fill.PATH_BAND_HZ == raytrace.PATH_BAND_HZ


@pytest.mark.parametrize("break_id", BREAKS)
def test_every_drawn_ray_is_a_clearing_row_of_its_table(break_id):
    """A path names its table row by (frequency, place); that row must clear
    every edge and read the same offshore heading."""

    import csv

    paths = json.loads((NEARSHORE / f"{break_id}_paths.json").read_text())
    rows: dict[str, list] = {}
    with (NEARSHORE / f"{break_id}.csv").open(newline="") as fh:
        for r in csv.DictReader(fh):
            rows.setdefault(r["freq_hz"], []).append(r)
    assert paths["band_hz"] == list(fill.PATH_BAND_HZ)
    assert paths["rays"]
    for key, rays in paths["rays"].items():
        lo, hi = fill.PATH_BAND_HZ
        assert lo <= float(key) <= hi
        clearing = [k for k, r in enumerate(rows[key]) if float(r["gain"]) > 0]
        assert [k for k, _, _ in rays] == clearing
        for k, off, pts in rays:
            assert abs((off - float(rows[key][k]["off_from_deg"]) + 180) % 360 - 180) <= 0.02
            times = [t for _, _, t in pts]
            assert times == sorted(times)            # in toward the break, in time order


def test_the_rays_rebuild_every_trains_5_m_height():
    """On the newest archived spectrum, every train a break would list: its
    rays' credited energy gives the chain's own 5 m height to 2 mm, and the
    fill leaves no row out."""

    from forecast.nearshore import _buoy_owner, buoy_split, carry, density_grids, load_tables
    from forecast.transform import load_spectra

    spectrum = load_spectra(ROOT / "data" / "spectra" / "46232", limit=1)[0].with_spread("mem")
    grids = density_grids(spectrum)
    split = buoy_split(spectrum, grids)
    owner = _buoy_owner(split)
    for break_id, table in load_tables().items():
        trains = carry(spectrum, table, grids, split).trains[:3]
        shown = [{"period_s": round(t.period_s, 1), "from_deg": round(t.from_deg), "hs_m": t.hs_m}
                 for t in trains]
        rows, notes = fill.rows_for(spectrum, table, grids, split, owner, trains, shown)
        assert notes == [] and len(rows) == len(trains)
        for row in rows:
            assert 0.5 < row["drawn_share"] <= 1.0
            assert all(0 < share <= 1 for _, _, share in row["rays"])


def test_a_row_that_does_not_match_now_json_gets_no_fill():
    """now.json and the rebuilt chain must name the same train, or the page
    would draw one train's rays under another's row."""

    from forecast.nearshore import _buoy_owner, buoy_split, carry, density_grids, load_tables
    from forecast.transform import load_spectra

    spectrum = load_spectra(ROOT / "data" / "spectra" / "46232", limit=1)[0].with_spread("mem")
    grids = density_grids(spectrum)
    split = buoy_split(spectrum, grids)
    table = load_tables()["coronado_center"]
    trains = carry(spectrum, table, grids, split).trains[:1]
    shown = [{"period_s": round(trains[0].period_s, 1) + 1.0, "from_deg": 0, "hs_m": 1.0}]
    rows, notes = fill.rows_for(spectrum, table, grids, split, _buoy_owner(split), trains, shown)
    assert rows == [] and "disagree" in notes[0]


def test_the_fill_is_its_own_file_never_a_key_in_now_json():
    src = (ROOT / "forecast" / "now.py").read_text()
    assert "fill" not in src.split("def build(")[1].split("def write(")[0].lower().replace("fill_", "")
