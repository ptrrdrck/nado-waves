"""Display units.

**Imperial leads, metric follows in parentheses, everywhere a number is shown
to a reader.** Nothing upstream of a display converts: the JSON, the transform
and the collectors stay in metres and knots, because that is what NDBC and
WAVEWATCH III publish and putting a unit change between the source and every
cross-check is how a 3.28 ends up somewhere it should not be.

So these are the only place the conversion happens on the Python side, and
`app/forecast.html` carries the same three constants for the same reason.
"""

from __future__ import annotations

FT_PER_M = 3.28084
MPH_PER_KT = 1.15078
MI_PER_KM = 0.621371


def height(metres: float | None, *, dash: str = "\u2014") -> str:
    """Wave height or water level, feet first."""

    if metres is None:
        return dash
    return f"{metres * FT_PER_M:.1f} ft ({metres:.2f} m)"


def speed(knots: float | None, *, dash: str = "\u2014") -> str:
    """Wind speed, miles per hour first."""

    if knots is None:
        return dash
    return f"{knots * MPH_PER_KT:.0f} mph ({knots:.0f} kt)"


def _about(value: float, step: int) -> str:
    return f"{max(step, round(value / step) * step):,}"


def distance(km: float | None, *, step: int = 500, dash: str = "\u2014") -> str:
    """A swell's distance from its origin, miles first, each rounded to `step`.

    500 for Origin's dispersion distances, said "about" because that is the
    precision measured: two buoys reading one storm independently differ by
    ~18-25% at the median (BRIEFING §37). 100 for a position from NHC's best
    track. The page rounds the same way (`farAway`).
    """

    if km is None:
        return dash
    return f"about {_about(km * MI_PER_KM, step)} mi ({_about(km, step)} km)"
