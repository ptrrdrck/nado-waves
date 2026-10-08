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

**A train's petals** (owner's request, 2026-10-08): the trains listed above
a rose are the NEWEST spectrum's, and nothing here follows a train from one
spectrum to the next (its period, split and direction all move). So a tapped
train is highlighted as its period range -- the frequency bins it holds in the
newest spectrum, and for a train divided from a band of two directions
(BRIEFING §40) the arc of headings it holds, so its twin on the same range
lights the other side -- and every frame carries each sector's share of the
energy in that same range. Exact in every frame; in an older one the range may hold a
different swell, and the page names the range, never the train, there.

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


def bin_energies(spectrum: Spectrum, *, step: float = STEP_DEG) -> dict[int, list[float]]:
    """Energy (m²) in each sector, per frequency bin: {bin index: [sector]}.

    Integrated as `transform.at_buoy` integrates: the whole circle in `step`
    degree slices of `Spectrum.density`."""

    steps = max(int(round(360.0 / step)), 1)
    d_theta = 360.0 / steps
    radians_step = math.radians(d_theta)
    out: dict[int, list[float]] = {}
    for index, freq in enumerate(spectrum.frequencies):
        density = spectrum.c11[index]
        if density <= 0.0 or math.isnan(density) or freq <= 0.0:
            continue
        width = spectrum.bin_width(index)
        row = out[index] = [0.0] * SECTORS
        for n in range(steps):
            theta = (n + 0.5) * d_theta
            energy = spectrum.density(index, theta) * radians_step * width
            if energy > 0.0:
                row[sector_of(theta)] += energy
    return out


def energies(spectrum: Spectrum, *, step: float = STEP_DEG,
             bins: dict[int, list[float]] | None = None) -> list[list[float]]:
    """Energy (m²) in each sector and period band: [sector][band]."""

    bins = bin_energies(spectrum, step=step) if bins is None else bins
    out = [[0.0] * (len(PERIOD_EDGES_S) + 1) for _ in range(SECTORS)]
    for index, row in bins.items():
        band = band_of(1.0 / spectrum.frequencies[index])
        for sector, energy in enumerate(row):
            out[sector][band] += energy
    return out


def train_range(spectrum: Spectrum, train) -> tuple[float, float, tuple]:
    """Where a train sits in the spectrum it was split from: the frequency
    range (Hz, lowest and highest bin centre, `Train.bins`), and the headings
    it holds (`Train.arc`, empty for all of them). A band from two directions
    is two trains on one range since BRIEFING §40, told apart by their arcs."""

    freqs = [spectrum.frequencies[i] for i in train.bins]
    return (min(freqs), max(freqs), tuple(train.arc))


def in_arc(theta: float, arc: tuple) -> bool:
    """Is heading `theta` (deg FROM) inside `arc`, (first degree, one past the
    last) clockwise? An empty arc holds every heading."""

    if not arc:
        return True
    lo, hi = arc
    return (int(theta) - lo) % 360 < ((hi - lo) % 360 or 360)


def arc_energies(spectrum: Spectrum, index: int, arc: tuple, *,
                 step: float = STEP_DEG) -> list[float]:
    """One bin's energy in each sector, from the headings in `arc` only,
    integrated as `bin_energies` integrates the whole circle."""

    steps = max(int(round(360.0 / step)), 1)
    d_theta = 360.0 / steps
    width = spectrum.bin_width(index)
    row = [0.0] * SECTORS
    for n in range(steps):
        theta = (n + 0.5) * d_theta
        if in_arc(theta, arc):
            energy = spectrum.density(index, theta) * math.radians(d_theta) * width
            if energy > 0.0:
                row[sector_of(theta)] += energy
    return row


def frame(spectrum: Spectrum, ranges: list[tuple] | None = None) -> dict:
    """One spectrum's rose, as the page draws it. With `ranges` (Hz, and the
    headings of a divided train), each sector's share of the whole energy
    within each range, too."""

    per_bin = bin_energies(spectrum)
    grid = energies(spectrum, bins=per_bin)
    total = sum(sum(row) for row in grid)
    out = {
        "time_utc": spectrum.time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "hs_m": round(4.0 * math.sqrt(max(total, 0.0)), 3),
        # Each sector's energy as a height.
        "sector_hs_m": [round(4.0 * math.sqrt(max(sum(row), 0.0)), 3) for row in grid],
        # Each sector's energy in each band, as a share of the whole.
        "period_share": [[round(e / total, 4) if total > 0 else 0.0 for e in row]
                         for row in grid],
    }
    if ranges is not None:
        shares = []
        for lo, hi, *arc in ranges:
            arc = arc[0] if arc else ()
            inside = [arc_energies(spectrum, i, arc) if arc else row for i, row in per_bin.items()
                      if lo - 1e-9 <= spectrum.frequencies[i] <= hi + 1e-9]
            shares.append([round(sum(row[k] for row in inside) / total, 4) if total > 0 else 0.0
                           for k in range(SECTORS)])
        out["train_share"] = shares
    return out


def frames(spectra: list[Spectrum], moment: datetime,
           hours: float = WINDOW_HOURS,
           ranges: list[tuple] | None = None) -> list[dict]:
    """A rose for every spectrum stamped in the `hours` up to `moment`, oldest
    first. Only what was measured: a missing stamp is a missing frame, never
    the one beside it."""

    start = moment - timedelta(hours=hours)
    return [frame(sp, ranges) for sp in spectra if start < sp.time <= moment]


def payload(spectra: list[Spectrum], moment: datetime, interval_min: float,
            trains: list | None = None) -> dict:
    """One buoy's loop. `interval_min` is the buoy's own stamp spacing, so the
    page can tell a stamp that is late from one that is simply not due yet:
    it shows a frame until its successor was due and a gap after that.

    `trains` are the newest spectrum's (`at_buoy(...).trains`, in the order
    the reading lists them): each one's period range is carried, and every
    frame's share within it. `trains_from_utc` names that spectrum, so the
    page highlights only under the reading built from it."""

    start = moment - timedelta(hours=WINDOW_HOURS)
    newest = spectra[-1] if spectra else None
    ranges = [train_range(newest, t) for t in trains] if (trains and newest) else None
    out = {
        "window_start_utc": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_end_utc": moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "interval_min": interval_min,
        "frames": frames(spectra, moment, ranges=ranges),
    }
    if ranges:
        out["trains_from_utc"] = newest.time.strftime("%Y-%m-%dT%H:%M:%SZ")
        out["trains"] = [{"period_lo_s": round(1.0 / hi, 1), "period_hi_s": round(1.0 / lo, 1),
                          **({"from_lo_deg": arc[0], "from_hi_deg": arc[1] % 360} if arc else {})}
                         for lo, hi, arc in ranges]
    return out
