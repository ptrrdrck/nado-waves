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


# ------------------------------------------------------------------ spectrum and metadata

SPEC_DDS = """Dataset {
    Float32 metaLatitude;
    Float32 metaWaterDepth;
    String metaSiteLabel;
    Float32 waveFrequency[waveFrequency = 3];
    Grid {
      ARRAY:
        Float32 waveBandwidth[waveFrequency = 3];
      MAPS:
        Float32 waveFrequency[waveFrequency = 3];
    } waveBandwidth;
    Float32 waveFrequencyBounds[waveFrequency = 3][metaBoundsCount = 2];
    Int32 waveTime[waveTime = 2];
    Grid {
      ARRAY:
        Float32 waveHs[waveTime = 2];
      MAPS:
        Int32 waveTime[waveTime = 2];
    } waveHs;
    Grid {
      ARRAY:
        Float32 waveEnergyDensity[waveTime = 2][waveFrequency = 3];
      MAPS:
        Int32 waveTime[waveTime = 2];
        Float32 waveFrequency[waveFrequency = 3];
    } waveEnergyDensity;
    Float32 waveA1Value[waveTime = 2][waveFrequency = 3];
    Float32 waveB1Value[waveTime = 2][waveFrequency = 3];
    Float32 waveA2Value[waveTime = 2][waveFrequency = 3];
    Float32 waveB2Value[waveTime = 2][waveFrequency = 3];
    String waveModelInputSource[waveTime = 2];
    Float32 waveModelBinInputCoverage[waveTime = 2][waveFrequency = 3];
} cdip/model/MOP_alongshore/D0101_nowcast.nc;"""

SPEC_DAS = r"""Attributes {
    metaWaterDepth {
        String long_name "water depth";
        String units "meters";
        String comment "Depth below \"NAVD88\", rounded";
        Float32 _FillValue -999.99;
    }
    waveFrequency {
        String units "Hz";
    }
    waveEnergyDensity {
        String units "meter^2 second";
        Float32 _FillValue -999.99;
    }
    waveA1Value {
        Float32 _FillValue -999.99;
    }
    waveModelInputSource {
        String _FillValue "_";
    }
    NC_GLOBAL {
        String title "MOP nowcast";
        String history "line one
line two";
        Float32 geospatial_vertical_min 10.0, 10.5;
        Int32 count 4;
    }
    DODS_EXTRA {
        String Unlimited_Dimension "waveTime";
    }
}"""

GRID_ASCII = """Dataset {
    Grid { ARRAY: Float32 waveEnergyDensity[waveTime = 2][waveFrequency = 3]; } waveEnergyDensity;
} x;
---------------------------------------------
waveEnergyDensity.waveEnergyDensity[2][3]
[0], 0.1, 0.2, 0.3
[1], 0.4, -999.99, 0.6

waveEnergyDensity.waveTime[2]
1785801600, 1785805200

waveEnergyDensity.waveFrequency[3]
0.05, 0.1, 0.2

waveA1Value[2][3]
[0], 0.5, 0.6, 0.7
[1], 0.1, 0.2, 0.3
"""


def test_a_grid_response_keeps_the_array_and_its_maps_apart():
    v = mop.parse_ascii(GRID_ASCII)
    assert v["waveEnergyDensity"] == pytest.approx([0.1, 0.2, 0.3, 0.4, -999.99, 0.6])
    # The maps do not land in a variable of the same name fetched beside it.
    assert "waveFrequency" not in v and v["waveEnergyDensity.waveFrequency"] == pytest.approx([0.05, 0.1, 0.2])
    assert v["waveA1Value"] == pytest.approx([0.5, 0.6, 0.7, 0.1, 0.2, 0.3])


def test_the_dds_is_read_by_name_and_shape():
    d = mop.parse_dds(SPEC_DDS)
    assert d["waveEnergyDensity"]["dims"] == [("waveTime", 2), ("waveFrequency", 3)]
    assert d["waveFrequencyBounds"]["dims"] == [("waveFrequency", 3), ("metaBoundsCount", 2)]
    assert d["metaSiteLabel"] == {"type": "String", "dims": []}
    assert set(mop.small_variables(d)) == {"metaLatitude", "metaWaterDepth", "metaSiteLabel", "waveFrequency",
                                           "waveBandwidth", "waveFrequencyBounds"}


def test_the_das_keeps_every_attribute_exactly():
    a = mop.parse_das(SPEC_DAS)
    assert a["metaWaterDepth"]["comment"] == 'Depth below "NAVD88", rounded'
    assert a["metaWaterDepth"]["_FillValue"] == pytest.approx(-999.99)
    assert a["NC_GLOBAL"]["history"] == "line one\nline two"
    assert a["NC_GLOBAL"]["geospatial_vertical_min"] == [10.0, 10.5]
    assert a["NC_GLOBAL"]["count"] == 4
    assert a["DODS_EXTRA"]["Unlimited_Dimension"] == "waveTime"
    assert list(mop.fill_values(a["waveEnergyDensity"])) == [pytest.approx(-999.99)]


def test_the_spectral_schema_is_read_from_the_file_and_a_missing_piece_is_reported():
    d, a = mop.parse_dds(SPEC_DDS), mop.parse_das(SPEC_DAS)
    schema, problems = mop.spectral_schema(d, a)
    assert problems == []
    assert schema["nf"] == 3 and schema["time_first"] and schema["moments"]
    assert schema["edges_from"] == "waveFrequencyBounds"
    # No bounds: the bandwidth, centred.
    no_bounds = {k: v for k, v in d.items() if k != "waveFrequencyBounds"}
    assert mop.spectral_schema(no_bounds, a)[0]["edges_from"] == "waveBandwidth"
    # One moment missing: none are taken.
    no_b2 = {k: v for k, v in d.items() if k != "waveB2Value"}
    assert mop.spectral_schema(no_b2, a)[0]["moments"] is False
    # No energy, or frequency in other units: reported, never guessed past.
    schema, problems = mop.spectral_schema({k: v for k, v in d.items() if k != "waveEnergyDensity"}, a)
    assert schema is None and "waveEnergyDensity" in problems[0]
    a2 = dict(a, waveFrequency={"units": "rad/s"})
    schema, problems = mop.spectral_schema(d, a2)
    assert schema is None and "rad/s" in problems[0]


def test_band_edges_come_from_the_bounds_else_centred_on_the_bandwidth():
    vals = {"waveFrequency": [0.05, 0.1, 0.2], "waveBandwidth": [0.02, 0.05, 0.1],
            "waveFrequencyBounds": [0.04, 0.06, 0.08, 0.13, 0.15, 0.25]}
    e = mop.band_edges({"edges_from": "waveFrequencyBounds"}, vals)
    assert e[1] == (0.1, 0.08, 0.13, 0.05)
    e = mop.band_edges({"edges_from": "waveBandwidth"}, vals)
    assert e[2] == pytest.approx((0.2, 0.15, 0.25, 0.1))


def test_unpacking_follows_the_declared_order_and_a_fill_is_a_gap():
    flat = [1, 2, 3, 4, 5, 6]
    assert mop.unpack(flat, 2, 3, True) == [[1, 2, 3], [4, 5, 6]]
    assert mop.unpack(flat, 2, 3, False) == [[1, 3, 5], [2, 4, 6]]
    with pytest.raises(ValueError):
        mop.unpack(flat, 3, 3, True)
    fills = {-999.99}
    assert mop.is_gap(-999.99, fills) and mop.is_gap(float("nan"), fills) and mop.is_gap(-9999.0, set())
    assert not mop.is_gap(0.0, fills)


def test_the_read_back_catches_a_unit_or_a_band_width_misread():
    widths = [0.01] * 10
    energy = [[0.5] * 10, [1.0] * 10]
    hs = [4 * math.sqrt(0.05), 4 * math.sqrt(0.1)]
    rb = mop.readback(energy, widths, hs)
    assert rb["ok"] and rb["median"] == pytest.approx(1.0) and rb["hours"] == 2
    assert not mop.readback(energy, [0.02] * 10, hs)["ok"]          # bandwidth doubled
    # An hour with a gap in it is not read back, rather than read as zero.
    assert mop.readback([[None] + [0.5] * 9, [1.0] * 10], widths, hs)["hours"] == 1


def test_save_extras_writes_the_meta_and_spectrum_files(tmp_path):
    class Fake:
        def __init__(self):
            self.urls = []

        def fetch(self, url, timeout=120.0):
            self.urls.append(url)
            if "waveModelInputSource[" in url:
                return ("x\n---------------------------------------------\n"
                        "waveModelInputSource[2]\n\"46232 46225\", \"_\"\n"
                        "waveModelBinInputCoverage[2][3]\n[0], 1.0, 0.9, 0.5\n[1], 1.0, -999.99, 0.0\n")
            if "waveEnergyDensity[" in url:
                return GRID_ASCII.replace("[1], 0.4, -999.99, 0.6", "[1], 0.4, 0.5, 0.6") + (
                    "waveB1Value[2][3]\n[0], 0, 0, 0\n[1], 0, 0, 0\n"
                    "waveA2Value[2][3]\n[0], 0, 0, 0\n[1], 0, 0, 0\n"
                    "waveB2Value[2][3]\n[0], 0, 0, 0\n[1], 0, 0, 0\n")
            return ("Dataset { } x;\n---------------------------------------------\n"
                    "metaLatitude, 32.6\nmetaWaterDepth, 10.0\nmetaSiteLabel, \"D0101 Coronado\"\n"
                    "waveFrequency[3]\n0.05, 0.1, 0.2\n"
                    "waveBandwidth.waveBandwidth[3]\n0.02, 0.05, 0.1\n"
                    "waveBandwidth.waveFrequency[3]\n0.05, 0.1, 0.2\n"
                    "waveFrequencyBounds[3][2]\n[0], 0.04, 0.06\n[1], 0.08, 0.13\n[2], 0.15, 0.25\n")

    f = Fake()
    m0 = [0.1 * 0.02 + 0.2 * 0.05 + 0.3 * 0.1, 0.4 * 0.02 + 0.5 * 0.05 + 0.6 * 0.1]
    lines, ok = mop.save_extras(f, "coronado_center", "D0101", "cdip/x.nc", SPEC_DDS, SPEC_DAS,
                                (0, 1, [1785801600, 1785805200]), [4 * math.sqrt(m) for m in m0], tmp_path)
    assert ok, lines
    assert len(f.urls) == 3
    assert "waveEnergyDensity[0:1:1][0:1:2]" in f.urls[1]
    meta = json.loads((tmp_path / "coronado_center_meta.json").read_text())
    assert meta["metaWaterDepth"]["comment"] == 'Depth below "NAVD88", rounded'
    assert meta["global"]["title"] == "MOP nowcast"
    assert "D0101 Coronado" in meta["small_variables"]["ascii"]
    assert meta["spectrum"]["readback"]["ok"]
    bands = list(csv.DictReader((tmp_path / "coronado_center_bands.csv").open()))
    assert [b["lower_hz"] for b in bands] == ["0.04", "0.08", "0.15"]
    spec = list(csv.DictReader((tmp_path / "coronado_center_spectrum.csv").open()))
    assert spec[0]["valid_utc"] == "2026-08-04T00:00:00Z" and spec[1]["e01"] == "0.5"
    mom = list(csv.DictReader((tmp_path / "coronado_center_moments.csv").open()))
    assert mom[0]["a1_02"] == "0.700" and mom[1]["b2_00"] == "0.000"
    # What drove each hour, as the file says; a fill is a gap.
    inp = list(csv.DictReader((tmp_path / "coronado_center_inputs.csv").open()))
    assert inp[0]["input_source"] == "46232 46225" and inp[1]["input_source"] == ""
    assert inp[0]["cov02"] == "0.500" and inp[1]["cov01"] == ""
    assert meta["inputs"]["sources"] == {"46232 46225": 1, "": 1}


def test_main_end_to_end_against_a_fake_server(tmp_path, monkeypatch):
    """The whole run, offline: discovery, the series, then the meta and
    spectrum files for each break, and exit 0 only when all read back."""

    from forecast.geometry import load
    from forecast.nearshore import BREAKS

    spots = {s.id: s for s in load()[0]}
    pos = {f"D{i + 101:04d}": spots[b].position for i, b in enumerate(BREAKS)}
    pos["D0050"] = mop.EXTRA_POINTS["imperial_beach"][0]
    pos = dict(sorted(pos.items()))
    t0 = 1785801600                                       # 2026-08-04T00Z
    dds = SPEC_DDS.replace("} cdip", "    Float32 metaLongitude;\n    Float32 waveTp[waveTime = 2];\n"
                           "    Float32 waveDp[waveTime = 2];\n} cdip")
    das = SPEC_DAS.replace("    NC_GLOBAL {", '    waveTime {\n        String units "seconds since 1970-01-01 00:00:00 UTC";\n'
                           "    }\n    NC_GLOBAL {")
    m0 = [0.1 * 0.02 + 0.2 * 0.05 + 0.3 * 0.1, 0.4 * 0.02 + 0.5 * 0.05 + 0.6 * 0.1]
    rule = "\n---------------------------------------------\n"

    def fetch(self, url, timeout=120.0):
        self.left -= 1
        if url.endswith("catalog.xml"):
            return "<catalog>" + "".join(f'<dataset name="{p}_nowcast.nc" urlPath="cdip/m/{p}_nowcast.nc"/>'
                                         for p in pos) + "</catalog>"
        pid = url.split("/m/")[1][:5]
        if url.endswith(".dds"):
            return dds
        if url.endswith(".das"):
            return das
        q = url.split("?", 1)[1]
        if q.startswith("metaLatitude,metaLongitude,metaWaterDepth"):
            return f"x{rule}metaLatitude, {pos[pid][0]}\nmetaLongitude, {pos[pid][1]}\nmetaWaterDepth, 10.0\n"
        if q == "waveTime":
            return f"x{rule}waveTime[2]\n{t0}, {t0 + 3600}\n"
        if q.startswith("waveHs["):
            hs = ", ".join(f"{4 * math.sqrt(m):.6f}" for m in m0)
            return f"x{rule}waveHs.waveHs[2]\n{hs}\nwaveHs.waveTime[2]\n{t0}, {t0 + 3600}\nwaveTp.waveTp[2]\n14.3, 14.3\nwaveDp.waveDp[2]\n250, 251\n"
        if q.startswith("waveModelInputSource["):
            return (f"x{rule}waveModelInputSource[2]\n\"46232\", \"46232\"\n"
                    "waveModelBinInputCoverage[2][3]\n[0], 1, 1, 1\n[1], 1, 1, 1\n")
        if "waveEnergyDensity[" in q:
            zeros = "[0], 0, 0, 0\n[1], 0, 0, 0\n"
            return (GRID_ASCII.replace("-999.99", "0.5") + f"waveB1Value[2][3]\n{zeros}waveA2Value[2][3]\n{zeros}"
                    f"waveB2Value[2][3]\n{zeros}")
        return (f"x{rule}metaLatitude, 32.6\nwaveFrequency[3]\n0.05, 0.1, 0.2\n"
                "waveBandwidth.waveBandwidth[3]\n0.02, 0.05, 0.1\n"
                "waveFrequencyBounds[3][2]\n[0], 0.04, 0.06\n[1], 0.08, 0.13\n[2], 0.15, 0.25\n")

    monkeypatch.setattr(mop.Budget, "fetch", fetch)
    monkeypatch.setattr(mop, "write_step_summary", lambda text: None)
    assert mop.main(["--out", str(tmp_path)]) == 0
    for b in BREAKS:
        assert (tmp_path / f"{b}.csv").exists()
        assert json.loads((tmp_path / f"{b}_meta.json").read_text())["spectrum"]["readback"]["ok"]
        assert (tmp_path / f"{b}_moments.csv").exists()
        assert json.loads((tmp_path / f"{b}_meta.json").read_text())["inputs"]["sources"] == {"46232": 2}
    # The point that is not a break: its own files, filed under "points",
    # and the breaks still in points.json.
    assert mop.main(["--out", str(tmp_path), "--points", "extra"]) == 0
    doc = json.loads((tmp_path / "points.json").read_text())
    assert set(doc["breaks"]) == set(BREAKS)
    assert doc["points"]["imperial_beach"]["point"] == "D0050"
    assert doc["points"]["imperial_beach"]["search_from"] == list(mop.EXTRA_POINTS["imperial_beach"][0])
    assert (tmp_path / "imperial_beach_spectrum.csv").exists()
    assert json.loads((tmp_path / "imperial_beach_meta.json").read_text())["spectrum"]["readback"]["ok"]
    # A spectrum that does not read back: the series stand, the run says 3.
    monkeypatch.setattr(mop, "READBACK_TOL", -1.0)
    assert mop.main(["--out", str(tmp_path)]) == 3
    assert (tmp_path / "coronado_center.csv").exists()


def test_string_values_are_read_whole_with_their_commas_and_quotes():
    body = ("x\n---------------------------------------------\n"
            "waveModelInputSource.waveModelInputSource[3]\n"
            '"46225, 46232", "a\\"b",\n"_"\n'
            "waveModelInputSource.waveTime[3]\n1, 2, 3\n")
    assert mop.parse_ascii_strings(body, "waveModelInputSource") == ["46225, 46232", 'a"b', "_"]


def test_points_json_merges_so_one_set_never_drops_the_other(tmp_path):
    """Handoff 24b: a run for a point that is not a break must not drop the
    breaks from `points.json` (mopcheck and mopdepth read them), nor a run
    for the breaks drop the points."""

    path = tmp_path / "points.json"
    mop.write_points(path, {"breaks": {"coronado_center": {"point": "D0179"}}, "points": {}}, 90)
    doc = mop.write_points(path, {"breaks": {}, "points": {"imperial_beach": {"point": "D0050"}}}, 30)
    assert doc["breaks"] == {"coronado_center": {"point": "D0179"}}
    assert doc["points"] == {"imperial_beach": {"point": "D0050"}}
    doc = mop.write_points(path, {"breaks": {"coronado_center": {"point": "D0180"}}, "points": {}}, 90)
    assert doc["breaks"]["coronado_center"]["point"] == "D0180"
    assert doc["points"] == {"imperial_beach": {"point": "D0050"}}
    assert json.loads(path.read_text()) == doc


def test_the_breaks_stay_the_default_and_a_point_is_never_filed_as_a_break(tmp_path, monkeypatch):
    """`--points` defaults to the breaks, so the workflow's default dispatch
    is today's run; `extra` fetches only `EXTRA_POINTS`, files them under
    "points" with the search target and why, and leaves the breaks alone."""

    from forecast.nearshore import BREAKS

    seen = []

    def nearest(ids, position, where):
        seen.append(tuple(position))
        return "D0050", 120.0, {"lat": position[0], "lon": position[1], "depth_m": 10.0}

    monkeypatch.setattr(mop, "nearest", nearest)
    monkeypatch.setattr(mop, "write_step_summary", lambda text: None)

    class Stop(Exception):
        pass

    def fetch(self, url, timeout=120.0):
        if url.endswith("catalog.xml"):
            return '<catalog><dataset name="D0050_nowcast.nc" urlPath="cdip/m/D0050_nowcast.nc"/></catalog>'
        raise Stop(url)

    monkeypatch.setattr(mop.Budget, "fetch", fetch)
    mop.main(["--out", str(tmp_path)])
    from forecast.geometry import load
    spots = {s.id: s for s in load()[0]}
    assert seen == [tuple(spots[b].position) for b in BREAKS]
    seen.clear()
    mop.main(["--out", str(tmp_path), "--points", "extra"])
    assert seen == [tuple(pos) for pos, _ in mop.EXTRA_POINTS.values()]
    assert "imperial_beach" in mop.EXTRA_POINTS and not set(mop.EXTRA_POINTS) & set(BREAKS)
