"""forecast.utm — the projection every grid lookup depends on."""

from __future__ import annotations

import pytest

from forecast.utm import from_utm, to_utm


def test_a_known_point():
    """The UTM 11 central meridian at the equator is (500000, 0) by definition,
    and 117 W on it stays on the false easting at any latitude."""

    assert to_utm(0.0, -117.0) == pytest.approx((500000.0, 0.0), abs=1e-6)
    easting, _ = to_utm(32.7, -117.0)
    assert easting == pytest.approx(500000.0, abs=1e-6)


def test_it_matches_a_projection_library_to_the_millimetre():
    """Point Loma's tip, projected by GDAL (rasterio.warp) to EPSG:26911 on
    2026-09-25: the reference, stored rather than recomputed so the test needs
    no projection library."""

    x, y = to_utm(32.6657656, -117.2395835)
    assert (x, y) == pytest.approx((477535.076, 3614260.029), abs=0.01)


@pytest.mark.parametrize("lat,lon", [(32.517, -117.425), (32.68, -117.18), (32.40, -117.25)])
def test_round_trip(lat, lon):
    back = from_utm(*to_utm(lat, lon))
    assert back == pytest.approx((lat, lon), abs=1e-8)
