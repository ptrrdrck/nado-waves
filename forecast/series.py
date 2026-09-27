"""The observed chain, hour by hour, for the chart under each Now card.

Written by ``python -m forecast.measured`` beside ``measured.json``, as
``data/live/series.json``: the last 168 hours (owner's choice, 2026-09-27),
every hour rather than every third, because the chart is about how the buoy
and the breaks move against each other and a 3-hourly line would skip most of
a swell's arrival.

**Rebuilt, not saved.** Nothing hourly was ever kept: `now.json` is the latest
hour and `measured.json` every third. Every INPUT is committed — 46232's
spectra, KNZY, the gauge — so each hour is rebuilt from scratch through
`measured.Rebuilder`, with TODAY's chain. A past point is therefore what the
current windows, seabed and surf zone make of that hour's spectrum, not what
the page showed at the time; the chart says so. Measured 2026-09-27 on a
4-core session: 0.18 s an hour, 31 s for 168, on top of a 1.1 s load.

**A missing observation is a gap.** An hour with no spectrum stamped at it is
`{"gap": true}` and the page breaks the line there — never joined across,
never filled from a neighbour. The same holds per line: a break whose headline
is not a breaking height at that hour (no tide) has no height on the chart,
because a line that switched quantity mid-way would draw a step nothing
caused.

What each hour carries, beyond the heights:

- ``south_minus_north_m``: south's breaking height less north's. Its sign is
  the ordering the observation log verifies (`forecast.beachverify`), and a
  zero crossing is the ordering flipping.
- ``transmission``: a break's height in its windows over the buoy's — the
  straight-line window figure, not breaking, which lifts ~20% (BRIEFING §32)
  and would hide the windows opening and closing.
- ``pct_k`` / ``pct_d``: a stochastic oscillator. Where a height sits in its
  own trailing 24-hour range, 0 at the bottom and 100 at the top, and the
  three-hour mean of that. Taken only over readings that exist, only when
  the hour itself is present and at least 20 of the 24 are, and never over a
  range under 2 cm, where it is undefined rather than zero. It is a position
  in a range, not a height, and says nothing the heights do not; the page
  plots the buoy's minus the break's, which is positive when the buoy sits
  higher in its own range than the break does in its.

Derived and gitignored like `measured.json`. Nothing here is a comparison with
a forecast, and nothing here checks the beach.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from collector.common import ISO

from .measured import STATION, Rebuilder, _r

#: How far back the chart reaches (owner's choice, 2026-09-27).
SERIES_HOURS = 168
#: The oscillator's trailing window, and how much of it must be present.
K_LOOKBACK_H = 24
K_MIN_HOURS = 20
#: Below this the range is flat and %K is undefined, not zero.
K_MIN_RANGE_M = 0.02
#: %D is the mean of this many consecutive %K.
D_HOURS = 3

#: Hours rebuilt before the first one shown, so the oscillator is defined from
#: the first hour on screen rather than a day and a bit in.
WARMUP_HOURS = K_LOOKBACK_H - 1 + D_HOURS - 1

SOUTH, NORTH = "coronado_south", "coronado_north"


def hours_until(until: datetime, hours: int) -> list[datetime]:
    """`hours` consecutive UTC hours ending at the one `until` falls in."""

    last = until.replace(minute=0, second=0, microsecond=0)
    return [last - timedelta(hours=n) for n in range(hours - 1, -1, -1)]


def hourly(rebuild: Rebuilder, until: datetime, hours: int = SERIES_HOURS) -> dict[datetime, dict]:
    """One `measured` entry per hour, warm-up hours included, oldest first."""

    return {t: rebuild.at(t) for t in hours_until(until, hours + WARMUP_HOURS)}


def slim(entry: dict) -> dict:
    """The fields the chart draws, from one `measured.entry`."""

    if entry.get("gap"):
        return {"valid_utc": entry["valid_utc"], "gap": True}
    if entry.get("pending"):
        return {"valid_utc": entry["valid_utc"], "gap": False, "pending": True}
    buoy_hs = (entry.get("buoy") or {}).get("hs_m")
    breaks = {}
    for bid, b in (entry.get("breaks") or {}).items():
        window = b.get("hs_window_m")
        # The window height itself is not kept: the chart draws only its ratio
        # to the buoy, and the payload ships every collection.
        breaks[bid] = {
            "hs_m": b.get("hs_m") if b.get("hs_basis") == "breaking" else None,
            "transmission": _r(window / buoy_hs) if window is not None and buoy_hs else None,
        }
    south, north = (breaks.get(SOUTH) or {}).get("hs_m"), (breaks.get(NORTH) or {}).get("hs_m")
    return {
        "valid_utc": entry["valid_utc"],
        "gap": False,
        "buoy": {"hs_m": buoy_hs, "from_deg": (entry.get("buoy") or {}).get("from_deg")},
        "breaks": breaks,
        "south_minus_north_m": _r(south - north) if south is not None and north is not None else None,
    }


def _heights(steps: list[dict], pick) -> list[float | None]:
    out = []
    for step in steps:
        v = None
        if not step.get("gap") and not step.get("pending"):
            v = pick(step)
        out.append(v)
    return out


def pct_k(values: list[float | None], *, lookback: int = K_LOOKBACK_H,
          min_hours: int = K_MIN_HOURS, min_range: float = K_MIN_RANGE_M) -> list[float | None]:
    """%K per hour over the trailing `lookback` hours, current hour included.

    `values` is one entry per consecutive hour, None where there is no reading.
    Nothing is filled: the range is the readings that exist, and a window with
    too few of them has no %K at all.
    """

    out: list[float | None] = []
    for i, v in enumerate(values):
        if v is None or i + 1 < lookback:
            out.append(None)
            continue
        present = [x for x in values[i + 1 - lookback:i + 1] if x is not None]
        lo, hi = min(present), max(present)
        if len(present) < min_hours or hi - lo < min_range:
            out.append(None)
            continue
        out.append(round(100 * (v - lo) / (hi - lo), 1))
    return out


def pct_d(k: list[float | None], *, hours: int = D_HOURS) -> list[float | None]:
    """The mean of the last `hours` %K, only when every one of them exists."""

    out: list[float | None] = []
    for i in range(len(k)):
        window = k[max(0, i + 1 - hours):i + 1]
        ok = len(window) == hours and all(x is not None for x in window)
        out.append(round(sum(window) / hours, 1) if ok else None)
    return out


def oscillate(steps: list[dict]) -> None:
    """Add `pct_k` and `pct_d` to the buoy and every break, in place."""

    ids = sorted({bid for s in steps for bid in (s.get("breaks") or {})})
    lines = [("buoy", lambda s: (s.get("buoy") or {}).get("hs_m"))]
    lines += [(bid, lambda s, bid=bid: ((s.get("breaks") or {}).get(bid) or {}).get("hs_m"))
              for bid in ids]
    for key, pick in lines:
        k = pct_k(_heights(steps, pick))
        d = pct_d(k)
        for step, kv, dv in zip(steps, k, d):
            if step.get("gap") or step.get("pending"):
                continue
            target = step["buoy"] if key == "buoy" else (step.get("breaks") or {}).get(key)
            if target is not None:
                target["pct_k"], target["pct_d"] = kv, dv


def build(entries: dict[datetime, dict], *, now: datetime,
          hours: int = SERIES_HOURS) -> dict:
    """`series.json` from the entries `hourly` rebuilt, warm-up dropped."""

    ordered = [slim(entries[t]) for t in sorted(entries)]
    oscillate(ordered)
    return {
        "generated_utc": now.strftime(ISO),
        "station": STATION,
        "hours": hours,
        "k_lookback_h": K_LOOKBACK_H,
        "k_min_hours": K_MIN_HOURS,
        "d_hours": D_HOURS,
        "rebuilt_with": "the current chain",
        "standing_on": {
            "waves": f"OBSERVED — the NDBC directional spectrum at {STATION} stamped at "
                     f"each hour; an hour without one is a gap, never filled",
            "chain": "today's windows, seabed and surf zone, applied to every past hour",
            "claim": "how the buoy and the breaks moved against each other; it checks "
                     "nothing at the beach",
        },
        "steps": ordered[-hours:],
    }
