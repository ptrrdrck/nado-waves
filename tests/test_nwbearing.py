"""46232's north-west bearing (BRIEFING §38): the pieces the report stands on.

The report itself runs over the archive and is not re-run here; what is pinned
is the arithmetic each number goes through, and that the charted islands load
as the eight islands the regions were drawn round.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

from collector import shoreline
from forecast import nwbearing as mod
from forecast.transform import split_trains, train_bands

ROOT = Path(__file__).resolve().parent.parent
SHORE = ROOT / "data" / "shoreline"


def lobe_at(center: float, width: float, weight: float) -> list[float]:
    return [weight * math.exp(-0.5 * (mod.angular(k + 0.5, center) / width) ** 2) for k in range(360)]


def norm(d):
    total = sum(d)
    return [v / total for v in d]


class TestLobes:
    def test_two_lobes_are_found_and_the_mean_falls_between(self):
        """The case §38 is about: a southerly and a westerly lobe at one
        period. The mean lands where neither is."""

        d = norm([a + b for a, b in zip(lobe_at(180, 8, 0.6), lobe_at(280, 8, 0.4))])
        got = mod.lobes(d)
        assert [round(h) for h, _ in got[:2]] == [180, 280]
        assert got[0][1] == pytest.approx(0.6, abs=0.02)
        mean = mod.mean_heading(d)
        assert 200 < mean < 240
        assert mod.off_lobe(d, mean) > mod.OFF_DEG

    def test_two_maxima_closer_than_the_separation_are_one_lobe(self):
        d = norm([a + b for a, b in zip(lobe_at(250, 5, 0.5), lobe_at(265, 5, 0.5))])
        assert len([s for _, s in mod.lobes(d) if s >= 0.2]) == 1

    def test_a_single_lobe_keeps_its_mean(self):
        d = norm(lobe_at(205, 10, 1.0))
        assert mod.off_lobe(d, mod.mean_heading(d)) < 1.0

    def test_the_westerly_lobe_ignores_the_south(self):
        d = norm([a + b for a, b in zip(lobe_at(185, 8, 0.7), lobe_at(272, 8, 0.3))])
        assert mod.westerly_lobe(d) == pytest.approx(272, abs=1)
        assert mod.westerly_lobe(norm(lobe_at(185, 8, 1.0))) is None

    def test_the_lobe_wraps_north(self):
        d = norm(lobe_at(355, 8, 1.0))
        assert abs(mod.angular(mod.lobes(d)[0][0], 355)) <= 1

    def test_angular_is_signed_and_wraps(self):
        assert mod.angular(10, 350) == 20
        assert mod.angular(350, 10) == -20

    def test_slope_one_is_tracking_and_zero_is_pinned(self):
        xs = [290, 300, 310, 320]
        assert mod.slope(xs, [x - 40 for x in xs]) == pytest.approx(1.0)
        assert mod.slope(xs, [268, 270, 269, 270]) == pytest.approx(0.06, abs=0.05)


class TestIslands:
    def test_parts_close_together_join_and_far_ones_do_not(self):
        a = [(33.000, -118.500), (33.001, -118.500)]
        b = [(33.004, -118.500), (33.005, -118.501)]      # ~0.4 km from a
        c = [(33.200, -118.500), (33.201, -118.500)]      # ~22 km away
        groups = mod.cluster([a, b, c])
        assert sorted(len(g) for g in groups) == [2, 4]

    def test_edges_are_the_two_extreme_bearings(self):
        observer = (32.5, -117.4)
        points = [(32.6, -118.4), (32.9, -118.4), (32.75, -118.3)]
        lo, hi = mod.edges(observer, points)
        assert lo < hi
        assert 270 < lo < 285 and 285 < hi < 300

    def test_nearest_edge_says_when_a_heading_is_inside_an_island(self):
        observer = (32.5, -117.4)
        islands = {"X": [(32.6, -118.4), (32.9, -118.4)]}
        lo, hi = mod.edges(observer, islands["X"])
        assert mod.nearest_edge(observer, islands, (lo + hi) / 2)[2] is True
        d, name, inside = mod.nearest_edge(observer, islands, lo - 10)
        assert (name, inside) == ("X", False) and d == pytest.approx(-10, abs=0.01)

    @pytest.mark.skipif(not (SHORE / "enc_approach_88_channel_islands_south.csv").exists(),
                        reason="channel_islands extracts not fetched")
    def test_the_charted_extracts_are_the_eight_islands(self):
        """Not a rock, not a box corner, not the mainland: eight islands, each
        named by the island it was drawn round, each inside its region."""

        got = mod.load_islands(ROOT / "data")
        assert sorted(got) == sorted(mod.ISLAND_NAMES)
        for name, points in got.items():
            region = "channel_islands_south" if mod.ISLAND_NAMES[name][0] < 33.7 else "channel_islands_north"
            xmin, ymin, xmax, ymax = shoreline.REGIONS[region]
            assert all(ymin <= la <= ymax and xmin <= lo <= xmax for la, lo in points), name


class TestTrainBands:
    """`split_trains` now takes its bands from `train_bands`; the report reads
    the same bands. Nothing about the trains may have moved."""

    ENERGIES = [(0, 0.0), (1, 0.2), (2, 1.0), (3, 0.3), (4, 0.05), (5, 0.4), (6, 0.9), (7, 0.2)]
    FREQS = [0.04 + 0.01 * i for i in range(8)]

    def test_bands_cover_every_live_bin_once(self):
        bands = train_bands(self.ENERGIES)
        covered = [i for band in bands for i, _ in band]
        assert covered == [i for i, e in self.ENERGIES if e > 0]

    def test_each_train_is_one_band(self):
        sins = {i: e * 0.5 for i, e in self.ENERGIES}
        coss = {i: e * 0.5 for i, e in self.ENERGIES}
        trains = split_trains(self.ENERGIES, self.FREQS, sins, coss, min_share=0, min_hs=0)
        bands = train_bands(self.ENERGIES)
        assert sorted(round(t.hs_m, 9) for t in trains) == sorted(
            round(4 * math.sqrt(sum(e for _, e in b)), 9) for b in bands)
        assert len(bands) == 2

    def test_empty_is_empty(self):
        assert train_bands([]) == [] and train_bands([(0, 0.0)]) == []


def test_nothing_shipped_imports_the_report():
    """Reports, never edits: no module on a chain reads it."""

    for path in (ROOT / "forecast").glob("*.py"):
        if path.name in ("nwbearing.py", "originreport.py"):    # reports themselves
            continue
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"^\s*(from|import)\s+[.\w]*nwbearing", text, re.M), path.name
