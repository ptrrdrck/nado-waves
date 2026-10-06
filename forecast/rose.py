"""A height rose and a period rose from ONE directional spectrum, at the buoy.

The Buoys tab on "LIVE" draws one under each buoy's reading, redrawn for every
spectrum and looped over the last six hours (owner's request, 2026-10-06).
Built into `buoys.json` by `forecast.buoys`; this module only does the
arithmetic.

A rose here is not a climatology of hours. It is one spectrum's energy summed
into the sixteen compass sectors, each 22.5° wide and centred on its point,
and within each sector into five period bands:

- **Height**: each sector's energy as a height, 4·√(energy in the sector). The
  petals do NOT add up to the combined height above them; heights combine in
  energy, so the root of the sum of their squares does, exactly.
- **Period**: each sector's share of the spectrum's whole energy, split by the
  period of the frequency bins that carry it.

The energy is integrated exactly as `transform.at_buoy` integrates it -- the
whole circle in 1° steps, `Spectrum.density`, maximum entropy when the
spectrum says so -- so the sectors sum to the same m0 and the rose's height is
the block's own combined height (a test pins it). Nothing is carried to a
break, and a bin is filed under its centre period whole, never split between
bands.

Sector shapes are the maximum-entropy reading of four moments, not a
measurement at each bearing. 46047's moments are broad (r1 ~0.2-0.5, BRIEFING
§38), so its petals spread over more sectors than 46232's, and the two can
read different bearings for one swell on purpose: 46232 is the sea after the
Channel Islands, 46047 the open ocean before them (§38, §39).
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from .transform import STEP_DEG, Spectrum

#: Sixteen sectors, N first, clockwise, each centred on its compass point --
#: the same points the page's `compass()` names.
SECTORS = 16
SECTOR_DEG = 360.0 / SECTORS
POINTS = ("N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
          "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW")

#: Band edges in seconds: under 8 s, 8-11, 11-14, 14-17, 17 s and over. 8 s is
#: `transform.WIND_SEA_PERIOD_S`, where the page starts calling a train wind
#: sea; the rest are three-second steps through the surf periods.
PERIOD_EDGES_S = (8.0, 11.0, 14.0, 17.0)

#: How far back the loop reaches from the build, in hours.
WINDOW_HOURS = 6


def sector_of(theta: float) -> int:
    return int(((theta + SECTOR_DEG / 2.0) % 360.0) // SECTOR_DEG) % SECTORS


def band_of(period_s: float) -> int:
    return sum(1 for edge in PERIOD_EDGES_S if period_s >= edge)


def energies(spectrum: Spectrum, *, step: float = STEP_DEG) -> list[list[float]]:
    """Energy (m²) in each sector and period band: [sector][band]."""

    steps = max(int(round(360.0 / step)), 1)
    d_theta = 360.0 / steps
    radians_step = math.radians(d_theta)
    out = [[0.0] * (len(PERIOD_EDGES_S) + 1) for _ in range(SECTORS)]
    for index, freq in enumerate(spectrum.frequencies):
        density = spectrum.c11[index]
        if density <= 0.0 or math.isnan(density) or freq <= 0.0:
            continue
        width = spectrum.bin_width(index)
        band = band_of(1.0 / freq)
        for n in range(steps):
            theta = (n + 0.5) * d_theta
            energy = spectrum.density(index, theta) * radians_step * width
            if energy > 0.0:
                out[sector_of(theta)][band] += energy
    return out


def frame(spectrum: Spectrum) -> dict:
    """One spectrum's rose, as the page draws it."""

    grid = energies(spectrum)
    total = sum(sum(row) for row in grid)
    return {
        "time_utc": spectrum.time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "hs_m": round(4.0 * math.sqrt(max(total, 0.0)), 3),
        # Each sector's energy as a height.
        "sector_hs_m": [round(4.0 * math.sqrt(max(sum(row), 0.0)), 3) for row in grid],
        # Each sector's energy in each band, as a share of the whole.
        "period_share": [[round(e / total, 4) if total > 0 else 0.0 for e in row]
                         for row in grid],
    }


def frames(spectra: list[Spectrum], moment: datetime,
           hours: float = WINDOW_HOURS) -> list[dict]:
    """A rose for every spectrum stamped in the `hours` up to `moment`, oldest
    first. Only what was measured: a missing stamp is a missing frame, never
    the one beside it."""

    start = moment - timedelta(hours=hours)
    return [frame(sp) for sp in spectra if start < sp.time <= moment]


def payload(spectra: list[Spectrum], moment: datetime, interval_min: float) -> dict:
    """One buoy's loop. `interval_min` is the buoy's own stamp spacing, so the
    page can tell a stamp that is late from one that is simply not due yet:
    it shows a frame until its successor was due and a gap after that."""

    start = moment - timedelta(hours=WINDOW_HOURS)
    return {
        "window_start_utc": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_end_utc": moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "interval_min": interval_min,
        "frames": frames(spectra, moment),
    }
