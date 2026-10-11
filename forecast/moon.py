"""Where the Moon is: phase, distance and declination, computed, pure Python.

The Tide card's phase line (`forecast.tidephase`) names new and full moon,
the quarters, perigee and apogee by date, and says where the Moon is in
declination. Mean orbital elements are not good enough for that: they put
the new moon of October 2026 on the 11th (it was the 10th) and that month's
perigee on the 30th (it was the 28th). So this is the truncated lunar theory
of Meeus, *Astronomical Algorithms* (2nd ed.), ch. 47 — the largest terms of
ELP-2000/82 — and the Sun of ch. 25.

Checked against an independent ephemeris (PyEphem's) over 2026-2027
(BRIEFING §41): phases within 4 min, perigee and apogee within 47 min (their
minima are flat), the declination's extremes within 33 min and its equator
crossings within an hour (PyEphem's sampled hourly there), the declination
itself within 0.02°. `tests/test_moon.py` pins the
events of October 2026 to PyEphem's times. Times are UTC; the difference
from dynamical time (~69 s) is ignored, as it moves no date.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

J2000 = datetime(2000, 1, 1, 12, tzinfo=timezone.utc)

# Meeus Table 47.A: D, M, M', F, then longitude (1e-6 deg) and distance (1e-3 km).
LR = (
    (0, 0, 1, 0, 6288774, -20905355), (2, 0, -1, 0, 1274027, -3699111),
    (2, 0, 0, 0, 658314, -2955968), (0, 0, 2, 0, 213618, -569925),
    (0, 1, 0, 0, -185116, 48888), (0, 0, 0, 2, -114332, -3149),
    (2, 0, -2, 0, 58793, 246158), (2, -1, -1, 0, 57066, -152138),
    (2, 0, 1, 0, 53322, -170733), (2, -1, 0, 0, 45758, -204586),
    (0, 1, -1, 0, -40923, -129620), (1, 0, 0, 0, -34720, 108743),
    (0, 1, 1, 0, -30383, 104755), (2, 0, 0, -2, 15327, 10321),
    (0, 0, 1, 2, -12528, 0), (0, 0, 1, -2, 10980, 79661),
    (4, 0, -1, 0, 10675, -34782), (0, 0, 3, 0, 10034, -23210),
    (4, 0, -2, 0, 8548, -21636), (2, 1, -1, 0, -7888, 24208),
    (2, 1, 0, 0, -6766, 30824), (1, 0, -1, 0, -5163, -8379),
    (1, 1, 0, 0, 4987, -16675), (2, -1, 1, 0, 4036, -12831),
    (2, 0, 2, 0, 3994, -10445), (4, 0, 0, 0, 3861, -11650),
    (2, 0, -3, 0, 3665, 14403), (0, 1, -2, 0, -2689, -7003),
    (2, 0, -1, 2, -2602, 0), (2, -1, -2, 0, 2390, 10056),
    (1, 0, 1, 0, -2348, 6322), (2, -2, 0, 0, 2236, -9884),
)

# Meeus Table 47.B: D, M, M', F, latitude (1e-6 deg).
B = (
    (0, 0, 0, 1, 5128122), (0, 0, 1, 1, 280602), (0, 0, 1, -1, 277693),
    (2, 0, 0, -1, 173237), (2, 0, -1, 1, 55413), (2, 0, -1, -1, 46271),
    (2, 0, 0, 1, 32573), (0, 0, 2, 1, 17198), (2, 0, 1, -1, 9266),
    (0, 0, 2, -1, 8822), (2, -1, 0, -1, 8216), (2, 0, -2, -1, 4324),
    (2, 0, 1, 1, 4200), (2, 1, 0, -1, -3359), (2, -1, -1, 1, 2463),
    (2, -1, 0, 1, 2211), (2, -1, -1, -1, 2065),
)

#: The four phases by the Moon's elongation from the Sun, in degrees.
PHASES = {0.0: "new moon", 90.0: "first quarter", 180.0: "full moon", 270.0: "last quarter"}


def _t(when: datetime) -> float:
    return (when - J2000) / timedelta(days=36525)


def _sin(deg: float) -> float:
    return math.sin(math.radians(deg))


def moon(when: datetime) -> tuple[float, float, float]:
    """Geocentric ecliptic longitude and latitude (degrees) and distance (km)."""

    t = _t(when)
    lp = 218.3164477 + 481267.88123421 * t - 0.0015786 * t * t
    d = 297.8501921 + 445267.1114034 * t - 0.0018819 * t * t
    m = 357.5291092 + 35999.0502909 * t - 0.0001536 * t * t
    mp = 134.9633964 + 477198.8675055 * t + 0.0087414 * t * t
    f = 93.2720950 + 483202.0175233 * t - 0.0036539 * t * t
    a1, a2, a3 = 119.75 + 131.849 * t, 53.09 + 479264.290 * t, 313.45 + 481266.484 * t
    e = 1 - 0.002516 * t - 0.0000074 * t * t

    sl = sr = sb = 0.0
    for cd, cm, cmp_, cf, l, r in LR:
        arg = math.radians(cd * d + cm * m + cmp_ * mp + cf * f)
        k = e ** abs(cm)
        sl += k * l * math.sin(arg)
        sr += k * r * math.cos(arg)
    for cd, cm, cmp_, cf, b in B:
        sb += e ** abs(cm) * b * math.sin(math.radians(cd * d + cm * m + cmp_ * mp + cf * f))
    sl += 3958 * _sin(a1) + 1962 * _sin(lp - f) + 318 * _sin(a2)
    sb += (-2235 * _sin(lp) + 382 * _sin(a3) + 175 * _sin(a1 - f)
           + 175 * _sin(a1 + f) + 127 * _sin(lp - mp) - 115 * _sin(lp + mp))
    return (lp + sl / 1e6) % 360.0, sb / 1e6, 385000.56 + sr / 1000.0


def sun_longitude(when: datetime) -> float:
    """The Sun's apparent ecliptic longitude (Meeus ch. 25, low precision)."""

    t = _t(when)
    l0 = 280.46646 + 36000.76983 * t
    m = 357.52911 + 35999.05029 * t
    c = ((1.914602 - 0.004817 * t) * _sin(m) + (0.019993 - 0.000101 * t) * _sin(2 * m)
         + 0.000289 * _sin(3 * m))
    omega = 125.04 - 1934.136 * t
    return (l0 + c - 0.00569 - 0.00478 * _sin(omega)) % 360.0


def elongation(when: datetime) -> float:
    """The Moon's longitude less the Sun's, 0-360: 0 new, 180 full."""

    return (moon(when)[0] - sun_longitude(when)) % 360.0


def declination(when: datetime) -> float:
    lam, beta, _ = moon(when)
    eps = 23.4392911 - 0.0130042 * _t(when)
    s = (math.sin(math.radians(beta)) * math.cos(math.radians(eps))
         + math.cos(math.radians(beta)) * math.sin(math.radians(eps)) * math.sin(math.radians(lam)))
    return math.degrees(math.asin(s))


def distance(when: datetime) -> float:
    return moon(when)[2]


def _refine(fn, a: datetime, b: datetime, minutes: float = 1.0) -> datetime:
    """Bisect a sign change of `fn` between `a` and `b` to `minutes`."""

    fa = fn(a)
    while (b - a) > timedelta(minutes=minutes):
        mid = a + (b - a) / 2
        fm = fn(mid)
        if (fa <= 0) == (fm <= 0):
            a, fa = mid, fm
        else:
            b = mid
    return a + (b - a) / 2


def _state(when: datetime) -> tuple[float, float, float]:
    """Elongation, declination and distance from one evaluation of the Moon."""

    lam, beta, dist = moon(when)
    eps = math.radians(23.4392911 - 0.0130042 * _t(when))
    b, l = math.radians(beta), math.radians(lam)
    dec = math.degrees(math.asin(math.sin(b) * math.cos(eps) + math.cos(b) * math.sin(eps) * math.sin(l)))
    return (lam - sun_longitude(when)) % 360.0, dec, dist


def events(start: datetime, end: datetime) -> list[tuple[str, datetime]]:
    """Every phase, perigee, apogee, farthest north, farthest south and
    equator crossing between `start` and `end`, in time order.

    The Moon is sampled once an hour; a phase or an equator crossing is a
    sign change between two samples, a distance or declination extreme a
    change in the sign of its slope across three, and each is then bisected
    to a minute."""

    step = timedelta(hours=1)
    rate = timedelta(minutes=10)
    times, el, dec, dist = [], [], [], []
    t = start - step
    while t <= end + step:
        e, d, r = _state(t)
        times.append(t)
        el.append(e)
        dec.append(d)
        dist.append(r)
        t += step

    def phase_fn(target):
        return lambda w: ((elongation(w) - target + 180.0) % 360.0) - 180.0

    def slope(fn):
        return lambda w: fn(w + rate) - fn(w - rate)

    out: list[tuple[str, datetime]] = []
    for i in range(1, len(times) - 1):
        a, b = times[i], times[i + 1]
        if not start <= a < end:
            continue
        for target, name in PHASES.items():
            x = ((el[i] - target + 180.0) % 360.0) - 180.0
            y = ((el[i + 1] - target + 180.0) % 360.0) - 180.0
            if x < 0 <= y and y - x < 90:
                out.append((name, _refine(phase_fn(target), a, b)))
        if (dec[i] < 0) != (dec[i + 1] < 0):
            out.append(("over the equator", _refine(declination, a, b)))
        for series, fn, hi, lo in ((dist, distance, "apogee", "perigee"),
                                   (dec, declination, "farthest north", "farthest south")):
            if series[i] > series[i - 1] and series[i] >= series[i + 1]:
                out.append((hi, _refine(slope(fn), times[i - 1], times[i + 1])))
            elif series[i] < series[i - 1] and series[i] <= series[i + 1]:
                out.append((lo, _refine(slope(fn), times[i - 1], times[i + 1])))
    out.sort(key=lambda e: e[1])
    return out
