"""collector.kelp: which layers it takes, and what it asks for."""

from urllib.parse import parse_qs, urlsplit

from collector import kelp


def test_kelp_layers_by_acronym_or_name():
    for name in ("WEDKLP", "Weed/Kelp", "Kelp_area", "weed kelp (area)"):
        assert kelp.KELP.search(name)
    for name in ("Coastline", "Depth area", "Seabed area", "Wreck"):
        assert not kelp.KELP.search(name)


def test_the_query_asks_for_geometry_in_lon_lat_inside_the_box():
    q = parse_qs(urlsplit(kelp.query_url("https://x/MapServer/3", count_only=False, offset=500)).query)
    assert q["outSR"] == ["4326"] and q["inSR"] == ["4326"] and q["returnGeometry"] == ["true"]
    assert q["resultOffset"] == ["500"]
    assert [float(v) for v in q["geometry"][0].split(",")] == list(kelp.BBOX)
    c = parse_qs(urlsplit(kelp.query_url("https://x/MapServer/3", count_only=True)).query)
    assert c["returnCountOnly"] == ["true"] and "returnGeometry" not in c


class _Layer:
    id, name = 78, "Approach.Weed_Kelp_point"


def test_a_point_symbol_keeps_its_position_and_makes_no_ring():
    g = {"x": -117.25, "y": 32.66}
    assert kelp.point_rows("enc_approach", _Layer, 7, g) == [
        ["enc_approach", 78, "Approach.Weed_Kelp_point", 7, "32.660000", "-117.250000"]]
    assert kelp.ring_rows("enc_approach", _Layer, 7, g) == []
    assert len(kelp.point_rows("enc_approach", _Layer, 7, {"points": [[-117.2, 32.6], [-117.3, 32.7]]})) == 2


def test_an_area_makes_rings_and_no_point():
    g = {"rings": [[[-117.25, 32.66], [-117.24, 32.66], [-117.24, 32.67], [-117.25, 32.66]]]}
    assert len(kelp.ring_rows("enc_harbour", _Layer, 1, g)) == 4
    assert kelp.point_rows("enc_harbour", _Layer, 1, g) == []


def test_points_only_is_its_own_exit_and_writes_no_empty_outline(tmp_path, monkeypatch):
    class L:
        id, name, geometry = 78, "Approach.Weed_Kelp_point", "esriGeometryPoint"
    monkeypatch.setattr(kelp, "SERVICES", ["https://x/enc_approach/MapServer"])
    monkeypatch.setattr(kelp, "enumerate_service", lambda s: ([L], None))
    monkeypatch.setattr(kelp, "fetch_json", lambda url, timeout: {"count": 1})
    monkeypatch.setattr(kelp, "features", lambda url: [
        {"attributes": {"OBJECTID": 3}, "geometry": {"x": -117.25, "y": 32.66}}])
    monkeypatch.setattr(kelp, "write_step_summary", lambda text: None)
    (tmp_path / "kelp").mkdir()
    (tmp_path / "kelp" / "enc_wedklp.csv").write_text(",".join(kelp.FIELDS) + "\n")
    assert kelp.run(tmp_path, probe=False) == kelp.EXIT_POINTS_ONLY == 4
    assert not (tmp_path / "kelp" / "enc_wedklp.csv").exists()
    assert (tmp_path / "kelp" / "enc_wedklp_points.csv").read_text().splitlines()[1].endswith("32.660000,-117.250000")
