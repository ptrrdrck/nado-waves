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
