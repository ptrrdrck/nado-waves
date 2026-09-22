"""The geometry drawing is read from the model, not copied into the page."""

from __future__ import annotations

from forecast import geomviz as mod
from forecast.geometry import load


def test_every_blocker_in_the_file_is_drawn():
    _, blockers = load()
    got = mod.build()
    assert [b["name"] for b in got["blockers"]] == [b.name for b in blockers]


def test_each_west_ray_ends_on_that_breaks_own_tangent():
    """The ray the page draws is the vertex the model uses, per break."""

    spots, blockers = load()
    loma = next(b for b in blockers if b.name == "Point Loma peninsula")
    by_id = {s.id: s for s in spots}
    for brk in mod.build()["breaks"]:
        west = brk["windows"][-1]["edges"][-1]
        assert west["blocker"] == "Point Loma peninsula"
        assert tuple(west["vertex"]) == loma.a_seen_from(by_id[brk["id"]].position)


def test_every_edge_has_a_vertex():
    """No edge in the file is the seaward clip (BRIEFING §24), so every ray
    has somewhere to end. If one appears, the page would draw nothing there."""

    for brk in mod.build()["breaks"]:
        for w in brk["windows"]:
            assert all(e["blocker"] and e["vertex"] for e in w["edges"])


def test_the_break_positions_are_labelled_imagery():
    assert {b["source"] for b in mod.build()["breaks"]} == {"imagery"}


def test_the_buoy_is_read_not_typed():
    got = mod.build()["buoy"]
    assert got["id"] == "46232" and got["position"] is not None


def test_render_fills_the_placeholder(tmp_path):
    html = mod.render(mod.build())
    assert mod.PLACEHOLDER not in html
    assert "const MODEL = {" in html
