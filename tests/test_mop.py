"""collector.mop and forecast.mopcheck, offline: CDIP is refused from a session
(BRIEFING §8), so every response here is a fixture in the form THREDDS serves."""

from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone

import pytest

from collector import mop
from forecast import mopcheck

CATALOG = """<?xml version="1.0" encoding="UTF-8"?>
<catalog xmlns="http://www.unidata.ucar.edu/namespaces/thredds/InvCatalog/v1.0"
         xmlns:xlink="http://www.w3.org/1999/xlink">
  <dataset name="MOP_alongshore" ID="MOP">
    <dataset name="D0101_hindcast.nc" ID="a" urlPath="cdip/model/MOP_alongshore/D0101_hindcast.nc"/>
    <dataset name="D0101_nowcast.nc" ID="b" urlPath="cdip/model/MOP_alongshore/D0101_nowcast.nc"/>
    <dataset name="D0102_nowcast.nc" ID="c" urlPath="cdip/model/MOP_alongshore/D0102_nowcast.nc"/>
    <dataset name="L0005_nowcast.nc" ID="d" urlPath="cdip/model/MOP_alongshore/L0005_nowcast.nc"/>
  </dataset>
</catalog>"""

SCALARS = """Dataset {
    Float32 metaLatitude;
    Float32 metaLongitude;
    Float32 metaWaterDepth;
} cdip/model/MOP_alongshore/D0101_nowcast.nc;
---------------------------------------------
metaLatitude, 32.6809
metaLongitude, -117.1863
metaWaterDepth, 10.2
"""

ARRAYS = """Dataset {
    Float32 waveHs[waveTime = 4];
    Float32 waveTp[waveTime = 4];
} cdip/model/MOP_alongshore/D0101_nowcast.nc;
---------------------------------------------
waveHs[4]
0.51, 0.52,
 0.53, 0.54
waveTp[4]
14.3, 14.3, 15.4, 15.4
"""

DAS = """Attributes {
    waveTime {
        String long_name "UTC wave parameter time";
        String units "seconds since 1970-01-01 00:00:00 UTC";
    }
}"""


def test_the_catalogue_lists_one_product_and_one_region():
    got = mop.list_points(CATALOG, "nowcast")
    assert list(got) == ["D0101", "D0102"]
    assert got["D0101"].endswith("D0101_nowcast.nc")
    assert list(mop.list_points(CATALOG, "hindcast")) == ["D0101"]


def test_opendap_ascii_scalars_and_wrapped_arrays():
    s = mop.parse_ascii(SCALARS)
    assert s["metaLatitude"] == [pytest.approx(32.6809)]
    assert s["metaWaterDepth"] == [pytest.approx(10.2)]
    a = mop.parse_ascii(ARRAYS)
    assert a["waveHs"] == pytest.approx([0.51, 0.52, 0.53, 0.54])
    assert a["waveTp"] == pytest.approx([14.3, 14.3, 15.4, 15.4])


def test_not_an_opendap_response_is_refused():
    with pytest.raises(ValueError):
        mop.parse_ascii("<html>403</html>")


def test_time_units_and_a_renamed_variable_are_reported_not_guessed():
    assert mop.time_units(DAS).startswith("seconds since 1970-01-01")
    dds = "Dataset { Float32 waveHs[waveTime = 4]; Int32 waveTime[waveTime = 4]; } x;"
    assert set(mop.check_dds(dds)) == {"metaLatitude", "metaLongitude", "metaWaterDepth", "waveTp", "waveDp"}


def test_the_search_finds_the_nearest_point_on_a_synthetic_coast_in_few_requests():
    """Points every ~100 m up a straight coast; the target sits by point 637."""

    ids = [f"D{i:04d}" for i in range(1, 1201)]
    coast = {pid: (32.53 + 0.0009 * i, -117.12 - 0.0002 * i, 10.0) for i, pid in enumerate(ids)}
    calls = []

    def where(pid):
        calls.append(pid)
        return coast[pid]

    target = coast["D0637"][:2]
    pid, dist, meta = mop.nearest(ids, (target[0] + 0.0001, target[1]), where)
    assert pid == "D0637"
    assert dist < 20
    assert len(set(calls)) < 45          # within the module's request budget, with the other breaks


def test_ks_is_one_in_deep_water_and_matches_linear_theory_in_ten_metres():
    assert mopcheck.ks(8.0, 500.0) == pytest.approx(1.0, abs=1e-6)
    # 14 s in 10 m: kh from the dispersion relation, then sqrt(cg0/cg).
    omega = 2 * math.pi / 14.0
    k = omega ** 2 / 9.81
    for _ in range(100):                  # Newton: plain fixed point crawls in shallow water
        th = math.tanh(k * 10.0)
        k -= (9.81 * k * th - omega ** 2) / (9.81 * th + 9.81 * k * 10.0 * (1 - th * th))
    cg = 0.5 * omega / k * (1 + 2 * k * 10.0 / math.sinh(2 * k * 10.0))
    assert mopcheck.ks(14.0, 10.0) == pytest.approx(math.sqrt(9.81 / (2 * omega) / cg), rel=1e-9)
    assert mopcheck.ks(14.0, 10.0) > 1.0


def test_a_mop_series_made_from_the_chain_itself_compares_as_exactly_one(tmp_path):
    """Known answer: if MOP said what the chain says (its deep-water-equivalent
    height, shoaled to MOP's depth at MOP's period), chain / MOP is 1 every
    hour. Catches a de-shoaling or a buoy normalisation applied on one side."""

    from forecast.nearshore import carry, density_grids, load_tables
    from forecast.transform import load_spectra
    from pathlib import Path

    spectra = list(load_spectra(Path(mopcheck.ROOT) / "data" / "spectra" / "46232", limit=6))
    table = load_tables()["coronado_center"]
    depth, tp = 10.4, 13.0
    path = tmp_path / "coronado_center.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["valid_utc", "hs_m", "tp_s", "dp_deg"])
        for sp in spectra:
            mem = sp.with_spread("mem")
            h0 = carry(mem, table, density_grids(mem)).hs_equivalent
            w.writerow([sp.time.strftime("%Y-%m-%dT%H:%M:%SZ"), f"{h0 * mopcheck.ks(tp, depth):.9f}", tp, 250])
    rows = mopcheck.pairs("coronado_center", mopcheck.read_mop(path), spectra, table, depth)
    assert len(rows) == len(spectra)
    for r in rows:
        assert r["chain"] / r["mop"] == pytest.approx(1.0, rel=1e-6)


def test_the_report_names_the_comparison_a_model_against_a_model():
    rows = [{"time": datetime(2026, 11, 17, tzinfo=timezone.utc), "buoy": 3.0, "from": 285.0,
             "mop": 0.4, "chain": 0.6, "chain_hard": 0.55, "tp_mop": 14.0, "dp_mop": 250.0}]
    text = mopcheck.report({"coronado_center": rows}, {"coronado_center": {"point": "D0101", "product": "nowcast",
                                                                           "distance_m": 300, "depth_m": 10.2}})
    assert "model against a model" in text
    assert "| W-WNW (270–295°) | 1 |" in text
    assert "1.50" in text
