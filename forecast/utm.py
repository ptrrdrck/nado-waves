"""Latitude/longitude to UTM zone 11 metres, and back, in pure Python.

The bathymetry grid (`data/bathymetry/`) is in EPSG:26911 — NAD83 / UTM 11N —
and everything that walks across it (rays, the break positions they start
from) needs the same metres. Kept dependency-free so the forecast path and the
test suite never need a projection library.

Transverse Mercator by the Krüger series to third order (Snyder 1987, Karney
2011), GRS80. NAD83 and WGS84 differ by about a metre here, far below the 8 m
cell of the finest grid; `tests/test_utm.py` pins the round trip and a known
point.
"""

from __future__ import annotations

import math

ZONE = 11
_A = 6378137.0
_F = 1 / 298.257222101           # GRS80
_K0 = 0.9996
_E0 = 500000.0
_LON0 = math.radians(-183.0 + 6.0 * ZONE)

_N = _F / (2 - _F)
_AR = _A / (1 + _N) * (1 + _N ** 2 / 4 + _N ** 4 / 64)
_ALPHA = (_N / 2 - 2 * _N ** 2 / 3 + 5 * _N ** 3 / 16,
          13 * _N ** 2 / 48 - 3 * _N ** 3 / 5,
          61 * _N ** 3 / 240)
_BETA = (_N / 2 - 2 * _N ** 2 / 3 + 37 * _N ** 3 / 96,
         _N ** 2 / 48 + _N ** 3 / 15,
         17 * _N ** 3 / 480)
_DELTA = (2 * _N - 2 * _N ** 2 / 3 - 2 * _N ** 3,
          7 * _N ** 2 / 3 - 8 * _N ** 3 / 5,
          56 * _N ** 3 / 15)
_E = math.sqrt(_F * (2 - _F))


def to_utm(lat: float, lon: float) -> tuple[float, float]:
    """(easting, northing) in metres, zone 11 north."""

    phi, lam = math.radians(lat), math.radians(lon) - _LON0
    t = math.sinh(math.atanh(math.sin(phi)) - _E * math.atanh(_E * math.sin(phi)))
    xi = math.atan2(t, math.cos(lam))
    eta = math.atanh(math.sin(lam) / math.sqrt(1 + t * t))
    x = eta + sum(a * math.cos(2 * j * xi) * math.sinh(2 * j * eta)
                  for j, a in enumerate(_ALPHA, 1))
    y = xi + sum(a * math.sin(2 * j * xi) * math.cosh(2 * j * eta)
                 for j, a in enumerate(_ALPHA, 1))
    return _E0 + _K0 * _AR * x, _K0 * _AR * y


def from_utm(easting: float, northing: float) -> tuple[float, float]:
    """(lat, lon) in degrees from zone-11 metres."""

    xi = northing / (_K0 * _AR)
    eta = (easting - _E0) / (_K0 * _AR)
    xp = xi - sum(b * math.sin(2 * j * xi) * math.cosh(2 * j * eta)
                  for j, b in enumerate(_BETA, 1))
    ep = eta - sum(b * math.cos(2 * j * xi) * math.sinh(2 * j * eta)
                   for j, b in enumerate(_BETA, 1))
    chi = math.asin(math.sin(xp) / math.cosh(ep))
    phi = chi + sum(d * math.sin(2 * j * chi) for j, d in enumerate(_DELTA, 1))
    lam = _LON0 + math.atan2(math.sinh(ep), math.cos(xp))
    return math.degrees(phi), math.degrees(lam)
