"""forecast.wrapbudget's pieces that need no archive run."""

import math

import pytest

from forecast import wrapbudget as W
from forecast.geometry import load


@pytest.fixture(scope="module")
def center():
    spots, blockers = load()
    spot = {s.id: s for s in spots}["coronado_center"]
    return spot, W.arcs_for(spot, blockers)


def test_parts_of_the_straight_line_view(center):
    spot, arcs = center
    assert W.part_of(230.0, spot.normal, arcs) == "direct"
    assert W.part_of(285.0, spot.normal, arcs) == "wrap"      # behind Point Loma
    assert W.part_of(192.0, spot.normal, arcs) == "islands"   # between the window's arcs
    assert W.part_of(150.0, spot.normal, arcs) == "baja"


def test_smoothing_keeps_each_bins_energy():
    grid = [0.0] * 360
    grid[280] = 7.0
    grid[10] = 1.0                                            # across north, wraps round
    got = W.smoothed({0: grid}, 5)[0]
    assert sum(got) == pytest.approx(8.0, rel=1e-12)
    assert max(got) < 7.0 and got[355] > 0.0


def test_rows_read_as_the_shipped_table_reads_them():
    from forecast.nearshore import Table

    rows = [{"freq_hz": "0.0700", "near_from_deg": "200.25", "near_width_deg": "0.5",
             "off_from_deg": "250.00", "gain": "1.2", "diff_off_from_deg": "250.00",
             "diff_gain": "1.3", "friction": "0.9", "diff_friction": "0.8"},
            {"freq_hz": "0.0700", "near_from_deg": "200.75", "near_width_deg": "0.5",
             "off_from_deg": "260.00", "gain": "0", "diff_off_from_deg": "0",
             "diff_gain": "0", "friction": "1", "diff_friction": "1"}]
    t = W.table_from_rows("x", rows, 5.0)
    assert isinstance(t, Table) and t.madsen is None
    (ray,) = t.by_freq[0.07]
    assert ray.k == 0 and ray.width_rad == pytest.approx(math.radians(0.5))
    assert (ray.diff_gain, ray.diff_friction) == (1.3, 0.8)
