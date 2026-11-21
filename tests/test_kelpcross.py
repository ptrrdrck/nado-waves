"""forecast.kelpcross: length of a path inside a charted outline."""

import pytest

from forecast import kelpcross as K


def test_length_inside_a_square_with_a_hole():
    outer = [(0.0, 0.0), (1000.0, 0.0), (1000.0, 1000.0), (0.0, 1000.0)]
    hole = [(400.0, 400.0), (600.0, 400.0), (600.0, 600.0), (400.0, 600.0)]
    feats = [[outer, hole]]
    boxes = [(0.0, 0.0, 1000.0, 1000.0)]
    # Straight across at y = 500: 1000 m inside, less the 200 m hole.
    got = K.length_in([(-500.0, 500.0), (1500.0, 500.0)], feats, boxes)
    assert got == pytest.approx(800.0, abs=2 * K.STEP_M)
    assert K.length_in([(-500.0, 1500.0), (1500.0, 1500.0)], feats, boxes) == 0.0
    assert K._area(feats[0]) == pytest.approx(1e6 - 4e4)
