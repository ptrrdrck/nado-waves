"""forecast.bending — the docs table of headings in 5 m of water.

The table and the drawing's dashed arrow are one calculation: `arriving`
takes energy ray by ray exactly as `nearshore.carry` does, and a train's
5 m heading is the mean of the same rays. These pin the two together, and
pin the docs block to what the generator writes now.
"""

from __future__ import annotations

import math

import pytest

from forecast import bending
from forecast.geometry import load
from forecast.nearshore import BREAKS, Table, carry

TABLES = {b: Table.load(b) for b in BREAKS}


class _OneBin:
    """A spectrum of one frequency bin, for `carry` with its grids given."""

    def __init__(self, freq):
        self.frequencies = [freq]

    def bin_width(self, i):
        return 0.005


def _off(a, b):
    return abs((a - b + 180.0) % 360.0 - 180.0)


@pytest.mark.parametrize("break_id", BREAKS)
@pytest.mark.parametrize("heading", [200.0, 240.0, 270.0])
def test_it_is_carry_for_one_narrow_swell(break_id, heading):
    """The table's heading is the heading `carry` gives that swell's train."""

    table = TABLES[break_id]
    deg, _ = bending.arriving(table, bending.PERIOD_HZ, heading)
    got = carry(_OneBin(bending.PERIOD_HZ), table, {0: bending.swell_grid(heading)})
    assert got.trains, "the swell reached the break"
    assert _off(got.trains[0].near_from_deg, deg) < 1e-6


def test_the_swell_is_one_unit_of_energy():
    grid = bending.swell_grid(250.0)
    assert sum(grid) * math.radians(1.0) == pytest.approx(1.0)
    assert max(range(360), key=grid.__getitem__) in (249, 250)


def test_nothing_from_behind_the_beach():
    deg, reach = bending.arriving(TABLES["coronado_center"], bending.PERIOD_HZ, 40.0)
    assert reach < bending.MIN_REACH


def test_a_wide_spread_offshore_arrives_inside_a_narrow_one():
    """Refraction gathers swell from every open heading into a narrow arc at
    5 m. It is NOT always toward the shore normal: the seabed at 5 m faces its
    own way, and some swells cross the chord's normal on the way in (Center's
    230° arrives from 205°, its normal 214°), so that is not pinned."""

    data = bending.table()
    for b in data["breaks"]:
        shown = [(h, c) for h, c in zip(data["headings"], b["cells"]) if c is not None]
        offshore = max(h for h, _ in shown) - min(h for h, _ in shown)
        near = max(c for _, c in shown) - min(c for _, c in shown)
        assert offshore >= 90 and near <= offshore / 3


def test_the_normals_are_the_spots_own():
    spots = {s.id: s for s in load()[0]}
    for b in bending.table()["breaks"]:
        assert b["normal_deg"] == round(spots[b["id"]].normal) % 360


def test_the_docs_block_is_what_the_generator_writes():
    """Change the tables or the method, run `python -m forecast.bending
    --write`, and commit the page with them."""

    text = bending.DOCS.read_text(encoding="utf-8")
    start = text.index(bending.BEGIN)
    end = text.index(bending.END) + len(bending.END)
    assert text[start:end] == bending.render(bending.table())


def test_the_prose_names_the_tables_settings():
    text = bending.DOCS.read_text(encoding="utf-8")
    section = text[text.index('<section id="swell-bend">'):]
    section = section[:section.index("</section>")]
    assert f"{1.0 / bending.PERIOD_HZ:.1f} s" in section
    assert f"&plusmn;{bending.SPREAD_DEG:g}&deg;" in section
    assert "less than a tenth" in section and bending.MIN_REACH == 0.10


def test_the_crossing_the_prose_quotes_is_the_tables():
    data = bending.table()
    center = next(b for b in data["breaks"] if b["id"] == "coronado_center")
    assert center["normal_deg"] == 214
    assert center["cells"][data["headings"].index(230)] == 205
    text = " ".join(bending.DOCS.read_text(encoding="utf-8").split())
    assert ("at Center, one from 230&deg;, west of the 214&deg; normal, arrives from 205&deg;, "
            "south of it.") in text


def test_about_half_the_rays_cross_on_the_way_in():
    """The page says so: neighbouring rays swap order between deep water and
    5 m about half the time at every break (37-59% over 10-18 s, measured
    2026-10-22), where a one-to-one bending would give none."""

    for t in TABLES.values():
        for f in (0.10, bending.PERIOD_HZ, 0.055):
            assert 0.33 <= bending.crossing_share(t, f) <= 0.65
    text = " ".join(bending.DOCS.read_text(encoding="utf-8").split())
    assert "about half of them swap order between deep water and 5 m" in text


def test_every_column_arrives_within_about_twenty_degrees():
    """The page says "within about 20° of straight in" for anything the
    windows let in: every 5 m heading shown is within 20° of its break's
    normal (16° at most, 2026-10-22)."""

    data = bending.table()
    for b in data["breaks"]:
        for c in b["cells"]:
            if c is not None:
                assert _off(c, b["normal_deg"]) <= 20
