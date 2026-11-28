"""collector.seabed: which layers it takes, what it asks for, what it stores."""

from urllib.parse import parse_qs, urlsplit

from collector import kelp, seabed


def test_seabed_layers_by_acronym_or_name():
    for name in ("SBDARE", "Seabed area", "Approach.Seabed_Area_area", "Bottom characteristics"):
        assert seabed.SEABED.search(name)
    for name in ("Coastline", "Depth area", "Weed_Kelp_point", "Wreck"):
        assert not seabed.SEABED.search(name)


def test_the_query_asks_for_its_own_box_and_kelp_keeps_its_own():
    q = parse_qs(urlsplit(kelp.query_url("https://x/MapServer/3", count_only=False,
                                         bbox=seabed.BBOX)).query)
    assert [float(v) for v in q["geometry"][0].split(",")] == list(seabed.BBOX)
    k = parse_qs(urlsplit(kelp.query_url("https://x/MapServer/3", count_only=False)).query)
    assert [float(v) for v in k["geometry"][0].split(",")] == list(kelp.BBOX)


class _Layer:
    id, name = 61, "Approach.Seabed_Area_line"


def test_a_line_keeps_its_vertices_and_is_neither_area_nor_point():
    g = {"paths": [[[-117.25, 32.66], [-117.24, 32.67]]]}
    assert seabed.line_rows("enc_approach", _Layer, 5, g) == [
        ["enc_approach", 61, "Approach.Seabed_Area_line", 5, 0, 0, "32.660000", "-117.250000"],
        ["enc_approach", 61, "Approach.Seabed_Area_line", 5, 0, 1, "32.670000", "-117.240000"]]
    assert kelp.ring_rows("enc_approach", _Layer, 5, g) == []
    assert kelp.point_rows("enc_approach", _Layer, 5, g) == []


def test_natsur_is_read_whatever_its_case_and_decoded_only_for_the_summary():
    assert seabed.natsur_of({"natsur": "9"}) == "9"
    assert seabed.natsur_of({"NATSUR": "4,9"}) == "4,9"
    assert seabed.natsur_of({"NATSUR": ""}) is None
    assert seabed.decode("4,9") == "sand+rock"
    assert seabed.decode(None) == "no NATSUR"
    assert seabed.decode("99") == "code 99"


def _fake(monkeypatch, feats, geometry="esriGeometryPoint"):
    class L:
        id, name = 60, "Approach.Seabed_Area_point"
    L.geometry = geometry
    monkeypatch.setattr(seabed, "SERVICES", ["https://x/enc_approach/MapServer"])
    monkeypatch.setattr(seabed, "enumerate_service", lambda s: ([L], None))
    monkeypatch.setattr(seabed, "fetch_json", lambda url, timeout: {"count": len(feats)})
    monkeypatch.setattr(seabed, "features", lambda url, bbox: feats)
    monkeypatch.setattr(seabed, "write_step_summary", lambda text: None)


def test_points_only_is_its_own_exit_and_writes_no_empty_outline(tmp_path, monkeypatch):
    _fake(monkeypatch, [{"attributes": {"OBJECTID": 3, "NATSUR": "9"},
                         "geometry": {"x": -117.25, "y": 32.66}}])
    (tmp_path / "seabed").mkdir()
    (tmp_path / "seabed" / "enc_sbdare.csv").write_text(",".join(seabed.FIELDS) + "\n")
    assert seabed.run(tmp_path, probe=False) == seabed.EXIT_NO_AREA == 4
    assert not (tmp_path / "seabed" / "enc_sbdare.csv").exists()
    assert (tmp_path / "seabed" / "enc_sbdare_points.csv").exists()


def test_an_area_is_stored_with_its_attributes(tmp_path, monkeypatch):
    ring = [[-117.25, 32.66], [-117.24, 32.66], [-117.24, 32.67], [-117.25, 32.66]]
    _fake(monkeypatch, [{"attributes": {"OBJECTID": 8, "NATSUR": "9", "SORDAT": "2001"},
                         "geometry": {"rings": [ring]}}], "esriGeometryPolygon")
    assert seabed.run(tmp_path, probe=False) == 0
    assert len((tmp_path / "seabed" / "enc_sbdare.csv").read_text().splitlines()) == 5
    import json
    doc = json.loads((tmp_path / "seabed" / "enc_sbdare.json").read_text())
    assert doc["features"][0]["attributes"]["NATSUR"] == "9"


def test_no_feature_in_the_box_writes_nothing(tmp_path, monkeypatch):
    _fake(monkeypatch, [])
    assert seabed.run(tmp_path, probe=False) == 1
    assert not (tmp_path / "seabed").exists()
