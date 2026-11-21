"""A headland's diffracted fill is read across the Fresnel zone (BRIEFING §61)."""

import math

import numpy as np
import pytest

from forecast import raytrace as rt
from forecast.fillshift import nearest_rule
from forecast.nearshore import BREAKS, load_tables


@pytest.fixture(scope="module")
def tables():
    return load_tables()


@pytest.fixture(scope="module")
def normals():
    from forecast.geometry import load

    return {s.id: s.normal for s in load()[0]}


def _west(r, normal):
    """Point Loma's side of the break: a start heading west of the normal."""

    return ((r.near_from - normal + 180.0) % 360.0) - 180.0 > 0.0


def test_the_fan_is_uniform_in_u_inside_the_zone():
    u = np.array([0.5, 1.5, 3.5, 4.5, -1.0, np.nan, 2.5])
    off = np.array([260.0, 270.0, 280.0, 290.0, 300.0, 310.0, 275.0])
    lit = np.array([True, True, True, True, True, True, False])
    fan = rt.edge_fan(u, off, lit)
    # Inside 0 < u <= EDGE_U_MAX and lit only; cells half-way to neighbours.
    assert [h for h, _ in fan] == [260.0, 270.0, 280.0]
    assert [w for _, w in fan] == pytest.approx([1.0 / 4, 1.5 / 4, 1.5 / 4])
    assert sum(w for _, w in fan) == pytest.approx(1.0)
    assert rt.edge_fan(np.array([5.0]), np.array([1.0]), np.array([True])) == []


def test_edge_factor_is_unchanged_by_the_refactor():
    got = rt.edge_factor(np.array([0.0, 50.0, -50.0]), np.array([10.0] * 3),
                         np.array([3000.0] * 3), 14.3)
    assert got[0] == pytest.approx(0.25)
    assert got[1] > 0.25 > got[2] > 0.0


@pytest.mark.parametrize("break_id", BREAKS)
def test_every_swell_fill_behind_point_loma_has_a_fan(break_id):
    """Every row Point Loma stops that carries diffracted energy at a swell
    period (up to 0.13 Hz, 7.7 s) reads the sea across a fan."""

    for row in rt.committed_rows(break_id):
        if (row["blocker"].startswith("Point Loma") and float(row["freq_hz"]) <= 0.13
                and row["gain"] == "0" and float(row["diff_gain"]) > 0):
            assert row["diff_fan"], (row["freq_hz"], row["near_from_deg"])


def _spread(headings):
    """Circular range: the smallest arc holding every heading."""

    hs = sorted(h % 360.0 for h in headings)
    gaps = [(hs[(i + 1) % len(hs)] - hs[i]) % 360.0 for i in range(len(hs))]
    return 360.0 - max(gaps)


def _fill_heading(table, f, normal):
    """The mean heading Point Loma's fill rows at this frequency read at."""

    fan = [r for r in table.by_freq[f] if r.gain <= 0 < r.diff_gain and r.fan and _west(r, normal)]
    if fan:
        s = sum(w * math.sin(math.radians(h)) for h, w in fan[0].fan)
        c = sum(w * math.cos(math.radians(h)) for h, w in fan[0].fan)
        return math.degrees(math.atan2(s, c)) % 360.0
    return None


@pytest.mark.parametrize("break_id", ["coronado_center", "coronado_south"])
def test_the_fill_no_longer_wanders_from_period_to_period(tables, normals, break_id):
    """The falsification test of §61: over 7.7-22 s the fan's mean heading
    holds within 60°; the old rule's nearest-ray heading spread over more
    than 90° (Center 2° to 351°, South 235-349°)."""

    table = tables[break_id]
    freqs = [f for f in table.by_freq if 0.045 <= f <= 0.13]
    normal = normals[break_id]
    fan = [h for h in (_fill_heading(table, f, normal) for f in freqs) if h is not None]
    assert len(fan) >= 10 and _spread(fan) <= 60.0
    old = nearest_rule(table)
    olds = []
    for f in freqs:
        idx = [i for i, r in enumerate(table.by_freq[f]) if r.fan and _west(r, normal)]
        if idx:
            heads = [old.by_freq[f][i].diff_off_from for i in idx]
            olds.append(max(set(heads), key=heads.count))
    assert _spread(olds) > 90.0


def test_the_old_rule_leaves_a_table_without_fans_alone(tables):
    once = nearest_rule(tables["coronado_center"])
    t = nearest_rule(once)
    for f, rays in t.by_freq.items():
        for r, o in zip(rays, once.by_freq[f]):
            assert r.diff_off_from == o.diff_off_from and r.fan is None
