"""The buoy's spectrum carried to 5 m of water off each break, and local chop.

    python -m forecast.nearshore            # compare against the aperture, archive-wide

Pure Python; reads the transfer tables `forecast.raytrace` writes to
`data/nearshore/` and never needs numpy.

WHAT IT GIVES, per break and spectrum:

- `hs_ref` — Hs at the table's start point, `raytrace.H_REF` (5) metres of
  water off the break: refraction over the seabed (the islands' own shelves
  included), shoaling, and diffraction at every window edge — the Coronado
  Islands, the Point Loma tip and the Baja tangent. Linear theory, no breaking.
- `hs_equivalent` — the same with shoaling divided back out, per frequency,
  and without bottom friction.
- `hs_friction` — `hs_equivalent` after bottom friction along each ray's
  path (JONSWAP law, `raytrace.friction_rate`). `hs_ref` includes it.
- `hs_hard` — refraction with every window edge a HARD shadow and shoaling
  divided out. Against the aperture's `hs_in_window_m` (straight lines, hard
  edges) it is the seabed alone; `hs_equivalent` against it is diffraction
  alone, measured rather than claimed.
- `local` — fetch-limited wind sea from the measured wind, only where the
  fetch upwind of the break is closed by land (`raytrace.fetch_table`).

WHAT IT IS NOT. None of it has been observed. It is "physically derived" in
the project's sense: every step is textbook physics on charted and surveyed
inputs, and nothing has checked the result against the beach. The step from
here to a face height at the sand needs the observation log, which is empty.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .transform import (TRAIN_LOBE_SHARE, WIND_SEA_PERIOD_S, Spectrum, Train, load_spectra,
                        lobes_payload, through)

ROOT = Path(__file__).resolve().parent.parent
TABLE_DIR = ROOT / "data" / "nearshore"
BREAKS = ("coronado_north", "coronado_center", "coronado_south")
G = 9.81
KT_TO_MS = 0.514444
#: A train's headings at the buoy: the narrowest arc of offshore headings
#: holding this share of its energy that reaches the break (`_held`).
HELD_SHARE = 0.9


# ------------------------------------------------------------------ tables

@dataclass
class Ray:
    near_from: float
    width_rad: float
    off_from: float
    #: Hard window edges: the gain at `off_from`, 0 for a ray the land stops.
    gain: float
    #: Diffracting window edges: the gain at `diff_off_from` — the same heading
    #: for a ray that clears every edge, and the heading of the energy that
    #: diffracts round the edge for one that does not (raytrace.table).
    diff_off_from: float
    diff_gain: float
    #: Share of each answer's energy flux left after bottom friction along its
    #: path over the shelf. Stored apart from the gains so friction can be
    #: stated as its own effect; 1 for a table built before it was modelled.
    friction: float = 1.0
    diff_friction: float = 1.0
    #: The row's place among its frequency's rows in `<break>.csv`, which
    #: names the ray in `<break>_paths.json` (the map's fill). -1 for a ray
    #: built some other way.
    k: int = -1


@dataclass
class Table:
    break_id: str
    start_depth_m: float
    by_freq: dict[float, list[Ray]]
    fetch: list[tuple[float, bool]] = field(default_factory=list)   # index = wind_from_deg

    @classmethod
    def load(cls, break_id: str, directory: Path = TABLE_DIR) -> "Table":
        meta = json.loads((directory / f"{break_id}.json").read_text())
        by_freq: dict[float, list[Ray]] = {}
        with (directory / f"{break_id}.csv").open(newline="", encoding="utf-8") as fh:
            place: dict[float, int] = {}
            for row in csv.DictReader(fh):
                f = float(row["freq_hz"])
                k = place[f] = place.get(f, -1) + 1
                gain, diff_gain = float(row["gain"]), float(row["diff_gain"])
                if gain <= 0.0 and diff_gain <= 0.0:
                    continue          # carries nothing, hard or soft
                by_freq.setdefault(f, []).append(Ray(
                    float(row["near_from_deg"]), math.radians(float(row["near_width_deg"])),
                    float(row["off_from_deg"]), gain,
                    float(row["diff_off_from_deg"]), diff_gain,
                    float(row.get("friction") or 1.0),
                    float(row.get("diff_friction") or 1.0), k))
        fetch = []
        path = directory / f"{break_id}_fetch.csv"
        if path.exists():
            with path.open(newline="", encoding="utf-8") as fh:
                fetch = [(float(r["fetch_km"]), r["closed"] == "1") for r in csv.DictReader(fh)]
        return cls(break_id, float(meta["start_depth_m"]), by_freq, fetch)


# ------------------------------------------------------------------ physics

def wavenumber(omega: float, h: float) -> float:
    k0 = omega * omega / G
    k = k0 / math.sqrt(math.tanh(k0 * h))
    for _ in range(8):
        th = math.tanh(k * h)
        k -= (G * k * th - omega * omega) / (G * th + G * k * h * (1 - th * th))
    return k


def shoaling_squared(freq: float, h: float) -> float:
    """Ks² = cg0 / cg(h) — the part of the gain that is not refraction."""

    omega = 2 * math.pi * freq
    k = wavenumber(omega, h)
    c = omega / k
    two_kh = 2 * k * h
    # Past 2kh ~ 50 the correction is below 1e-20 and sinh overflows first.
    cg = 0.5 * c * (1 + (two_kh / math.sinh(two_kh) if two_kh < 50 else 0.0))
    return (0.5 * G / omega) / cg


# ------------------------------------------------------------------ spectra

def density_grids(spectrum) -> dict[int, list[float]]:
    """E(f, θ) on a 1° grid per frequency bin, per radian, from whatever the
    spectrum is: an NDBC `Spectrum` (Fourier or MEM, its own `spread`) or a
    WAVEWATCH III `GridSpectrum`. Computed once per spectrum and shared by
    the three breaks."""

    out = {}
    for i, c11 in enumerate(spectrum.c11):
        if c11 > 0 and not math.isnan(c11):
            out[i] = [spectrum.density(i, n + 0.5) for n in range(360)]
    return out


def at(grid: list[float], deg: float) -> float:
    """Linear interpolation on a 1°-centred circular grid."""

    pos = (deg - 0.5) % 360.0
    i = int(pos)
    frac = pos - i
    return grid[i] * (1 - frac) + grid[(i + 1) % 360] * frac


@dataclass
class Nearshore:
    break_id: str
    hs_ref: float
    hs_equivalent: float
    hs_hard: float
    #: Energy-weighted mean heading AT the start depth and where that energy
    #: came from offshore.
    near_from_deg: float
    off_from_deg: float
    peak_period_s: float
    unmatched_bins: int = 0
    #: Shoaling divided out, bottom friction in: between `hs_equivalent` and
    #: `hs_ref` in the chain of effects. None from a caller that predates it.
    hs_friction: float | None = None
    #: The arriving energy split into trains, each headed by where its energy
    #: came FROM offshore — the frame the window drawing is in.
    trains: list = field(default_factory=list)
    #: The short-period part of `hs_ref`: energy at periods under
    #: `transform.WIND_SEA_PERIOD_S` that reaches the start depth -- the wind
    #: sea the buoy already carried in, which open-water chop grows on from
    #: rather than beside (`local_sea`).
    hs_short: float = 0.0
    #: The buoy's own split it was handed (`buoy_split`), which each train's
    #: `buoy` indexes; empty when it was handed none.
    buoy: list = field(default_factory=list)


#: A break's train is divided by the buoy's own trains when a second one of
#: them carries at least this share of its energy, two pieces would each be
#: listed (`BUOY_DIVIDE_NEEDS_TWO`), and each second piece passes the
#: back-check against the buoy (`BUOY_DIVIDE_CHECKS_HEADING`): its heading
#: nearer its own buoy swell's than the row's lead swell's, else it is the
#: lead's spread across the buoy's dividing line and goes back to the lead.
#: Owner's decisions: 20% on 2026-11-03 (BRIEFING §49), 5% with the check on
#: 2026-11-04 (§49a), after North's W at 10% of its energy -- a third of its
#: height -- had no row. Measured (`forecast.trainmerge`), in the known-answer
#: control where the buoy parted two swells ≥ 3 s and ≥ 60° apart: a swell
#: ≥ 10% of a break's energy with no row 22.1% at 20% -> 9.2%, phantom rows
#: (one swell's spread named as the other) 10.0% -> 8.0%; 5% without the
#: check gave 8.8% and 13.0%. Single swells and swells the buoy did not part:
#: no rule changes them.
BUOY_DIVIDE_SHARE = 0.05
BUOY_DIVIDE_NEEDS_TWO = True
BUOY_DIVIDE_CHECKS_HEADING = True

#: Two of a break's rows that one buoy train carried are ONE swell on the
#: page -- bracketed, captioned, tapped together -- only when their energy
#: came from the same direction AT THE BUOY: each row's `buoy_from_deg`
#: (`_buoy_heading`) within this of every other in its group (owner's
#: decision, 2026-11-08, BRIEFING §49b). Until then any two rows of one buoy
#: train were bracketed, and where the buoy had merged two swells that was
#: wrong 79 of 85 times in the known-answer control (5 Nov-like cases: a big
#: W with a weak S/SW under it) -- North on 5 Nov 17Z read "one swell" over
#: a SW 16.7 s row, a W 10.5 s row and a 6.7 s row, the buoy's one train
#: being its whole spectrum. Measured (`forecast.trainmerge --brackets`,
#: 30 trials a case): single synthetic swells' rows sit within 15° on 105
#: of 111 brackets and all within 35°; at 20° 107 are kept, and wrong
#: brackets fall from 79 to 5 in the 5 Nov-like cases, and for two swells
#: the buoy merged 60° or more apart from 61 to 21 (50°: 40 to 26). Two swells 30° apart it
#: merged stay bracketed at any bar (70 of 70 wrong brackets kept): at the
#: buoy they are one swell's shape. Lower rather than higher, because a
#: missing bracket claims nothing and a wrong one claims "one swell at the
#: buoy".
#: A dip test on the buoy's own energy density did not help: a weak swell on
#: a big one's flank is a shoulder there, not a hill (§40's limit).
BRACKET_DEG = 20.0


def buoy_split(spectrum, grids: dict[int, list[float]] | None = None) -> list[Train]:
    """The buoy's own trains, from the 1° grid `carry` reads: `transform.at_buoy`'s
    split to the bin, but with NO share or height floor, so a swell too small
    to name at the buoy can still own the energy it carries behind the
    windows. `transform.floor_trains` of it is `at_buoy(spectrum).trains`
    (a test pins it). Computed once per spectrum and handed to `carry` for
    each break."""

    from .transform import split_trains

    grids = density_grids(spectrum) if grids is None else grids
    rad = math.radians(1.0)
    per_bin: list[tuple[int, float]] = []
    sins: dict[int, float] = {}
    coss: dict[int, float] = {}
    hists: dict[int, list[float]] = {}
    for i in sorted(grids):
        width = spectrum.bin_width(i)
        hist = hists[i] = [0.0] * 360
        total = sn = cs = 0.0
        for n, density in enumerate(grids[i]):
            e = density * rad * width
            if e <= 0.0:
                continue
            hist[n] = e
            total += e
            t = math.radians(n + 0.5)
            sn += e * math.sin(t); cs += e * math.cos(t)
        per_bin.append((i, total))
        sins[i], coss[i] = sn, cs
    return split_trains(per_bin, spectrum.frequencies, sins, coss, hists=hists,
                        min_share=0.0, min_hs=0.0)


def _arc_degrees(arc: tuple) -> list[int]:
    lo, hi = arc or (0, 360)
    return [k % 360 for k in range(lo, hi if hi > lo else hi + 360)]


def _buoy_owner(buoy: list[Train]):
    """`owner(i, k)`: the index of the buoy train holding bin `i` at offshore
    degree `k`, or -1. A bin one train holds is that train's at every degree;
    a band the buoy divided by direction is its trains' by their arcs."""

    holds: dict[int, list[int]] = {}
    for n, t in enumerate(buoy):
        for i in t.bins:
            holds.setdefault(i, []).append(n)
    by_deg: dict[int, list[int]] = {}
    for i, ns in holds.items():
        if len(ns) > 1 or buoy[ns[0]].arc:
            row = [-1] * 360
            for n in ns:
                for k in _arc_degrees(buoy[n].arc):
                    row[k] = n
            by_deg[i] = row

    def owner(i: int, k: int) -> int:
        row = by_deg.get(i)
        if row is not None:
            return row[k]
        ns = holds.get(i)
        return ns[0] if ns else -1

    return owner


def _divide_by_buoy(trains: list[Train], buoy: list[Train], frequencies, hists, near_sin,
                    near_cos, total: float, share: float = BUOY_DIVIDE_SHARE,
                    need_two: bool = BUOY_DIVIDE_NEEDS_TWO,
                    own_heading: bool = BUOY_DIVIDE_CHECKS_HEADING) -> list[Train]:
    """Each break train as the buoy's trains carried it: kept whole, its
    `buoy` the one carrying most of it, unless a second carries at least
    BUOY_DIVIDE_SHARE -- then one train per buoy train, each its own energy
    only (its band, heading, peak period, lobes, 5 m heading and held arc),
    under the same floors as any train. Energy is never moved: what a piece
    below the floors carried leaves the list, as a band below them does."""

    from .transform import _real_lobes, floor_trains

    owner = _buoy_owner(buoy)
    out: list[Train] = []
    for t in trains:
        degrees = _arc_degrees(t.arc)
        # parts[n][i][k]: energy at 5 m of bin i, offshore degree k, that
        # buoy train n carried.
        parts: dict[int, dict[int, dict[int, float]]] = {}
        for i in t.bins:
            h = hists.get(i)
            if not h:
                continue
            for k in degrees:
                v = h[k]
                if v > 0:
                    parts.setdefault(owner(i, k), {}).setdefault(i, {})[k] = v
        sums = {n: sum(sum(d.values()) for d in per.values()) for n, per in parts.items()}
        whole = sum(sums.values())
        ranked = sorted((n for n in sums if n >= 0), key=lambda n: -sums[n])
        if not ranked or whole <= 0:
            out.append(t)
            continue
        if len(ranked) < 2 or sums[ranked[1]] < share * whole:
            t.buoy = ranked[0]
            out.append(t)
            continue
        held_by: dict[int, list[int]] = {}
        if own_heading:
            # The back-check against the buoy: a piece is the second swell's
            # only if its own heading sits nearer that swell's heading at the
            # buoy than the row's lead swell's. Otherwise it is read as the
            # lead swell's spread across the buoy's dividing line, and its
            # energy goes back to the lead.
            lead = ranked[0]
            for n in ranked[1:]:
                held_by.setdefault(n, [n])
                sn = sum(v * math.sin(math.radians(k + 0.5)) for d in parts[n].values() for k, v in d.items())
                cs = sum(v * math.cos(math.radians(k + 0.5)) for d in parts[n].values() for k, v in d.items())
                h = math.degrees(math.atan2(sn, cs)) % 360.0
                off = lambda b: abs((h - buoy[b].from_deg + 180.0) % 360.0 - 180.0)
                if off(n) >= off(lead):
                    for i, by_k in parts.pop(n).items():
                        into = parts[lead].setdefault(i, {})
                        for k, v in by_k.items():
                            into[k] = into.get(k, 0.0) + v
                    sums[lead] += sums.pop(n)
                    held_by.setdefault(lead, [lead]).extend(held_by.pop(n))
            ranked = sorted((n for n in sums if n >= 0), key=lambda n: -sums[n])
            if len(ranked) < 2 or sums[ranked[1]] < share * whole:
                t.buoy = ranked[0]
                out.append(t)
                continue
        pieces = []
        for n in ranked:
            per = parts[n]
            e = sums[n]
            dist = [0.0] * 360
            m_hists, m_sin, m_cos, m_bin = {}, {}, {}, {}
            for i, by_k in per.items():
                hist = m_hists[i] = [0.0] * 360
                ms, mc = m_sin[i], m_cos[i] = [0.0] * 360, [0.0] * 360
                for k, v in by_k.items():
                    hist[k] = v
                    dist[k] += v
                    ms[k], mc[k] = near_sin[i][k], near_cos[i][k]
                m_bin[i] = (sum(ms), sum(mc))
            top = max(per, key=lambda i: sum(per[i].values()))
            sn = sum(v * math.sin(math.radians(k + 0.5)) for k, v in enumerate(dist))
            cs = sum(v * math.cos(math.radians(k + 0.5)) for k, v in enumerate(dist))
            piece = Train(
                hs_m=4.0 * math.sqrt(e),
                period_s=1.0 / frequencies[top] if frequencies[top] > 0 else float("nan"),
                from_deg=math.degrees(math.atan2(sn, cs)) % 360.0,
                share=e / total,
                lobes=_real_lobes(dist),
                bins=tuple(sorted(per)),
                # Its headings are its parent's arc AND its buoy train's:
                # `arc` keeps the first, `buoy` names the second.
                arc=t.arc,
                buoy=n,
                buoys=tuple(sorted(held_by.get(n, [n]))),
            )
            _arrive(piece, m_bin, m_sin, m_cos)
            piece.held = _held(piece, m_hists)
            pieces.append(piece)
        kept = floor_trains(pieces)
        if need_two and len(kept) < 2:
            # Only one piece would be listed: dividing would only drop the
            # rest of the row's energy from it, so it stays whole.
            t.buoy = ranked[0]
            out.append(t)
            continue
        out.extend(kept)
    out.sort(key=lambda t: -t.hs_m)
    return out


def carry(spectrum, table: Table, grids: dict[int, list[float]] | None = None,
          buoy: list[Train] | None = None, divide_share: float = BUOY_DIVIDE_SHARE,
          divide_need_two: bool = BUOY_DIVIDE_NEEDS_TWO,
          divide_own_heading: bool = BUOY_DIVIDE_CHECKS_HEADING) -> Nearshore:
    """Integrate S_off(f, θ0)·gain over the nearshore headings, per frequency.

    With `buoy`, the buoy's own split of the same spectrum (`buoy_split`),
    each train is credited to the buoy trains that carried it and divided
    where a second carried `divide_share` of it (`_divide_by_buoy`, BRIEFING
    §49; any other share is for `forecast.trainmerge` to measure). The
    heights are the same either way: only the rows change."""

    from .transform import split_trains

    grids = density_grids(spectrum) if grids is None else grids
    freqs = sorted(table.by_freq)
    e10 = e_eq = e_hard = e_fric = e_short = 0.0
    sn = cn = so = co = 0.0
    per_bin: list[tuple[int, float]] = []
    bin_sin: dict[int, float] = {}
    bin_cos: dict[int, float] = {}
    hists: dict[int, list[float]] = {}
    # Beside each bin's offshore histogram, where that energy heads at the
    # start depth: sin and cos of its rays' 5 m headings, by offshore degree.
    near_sin: dict[int, list[float]] = {}
    near_cos: dict[int, list[float]] = {}
    near_bin: dict[int, tuple[float, float]] = {}
    unmatched = 0
    for i, f in enumerate(spectrum.frequencies):
        grid = grids.get(i)
        if grid is None:
            continue
        near = min(freqs, key=lambda t: abs(t - f))
        if abs(near - f) > 0.05 * f:
            unmatched += 1
            continue
        width = spectrum.bin_width(i)
        short = f > 1.0 / WIND_SEA_PERIOD_S
        ks2 = shoaling_squared(f, table.start_depth_m)
        bin_e = bs = bc = bns = bnc = 0.0
        hist = hists[i] = [0.0] * 360
        ns = near_sin[i] = [0.0] * 360
        nc = near_cos[i] = [0.0] * 360
        for ray in table.by_freq[near]:
            if ray.gain > 0:
                e_hard += at(grid, ray.off_from) * width * ray.width_rad * ray.gain / ks2
            if ray.diff_gain <= 0:
                continue
            e = at(grid, ray.diff_off_from) * width * ray.width_rad * ray.diff_gain
            e_eq += e / ks2
            e *= ray.diff_friction
            e_fric += e / ks2
            e10 += e
            if short:
                e_short += e
            bin_e += e
            t = math.radians(ray.near_from)
            s_near, c_near = e * math.sin(t), e * math.cos(t)
            sn += s_near; cn += c_near
            t = math.radians(ray.diff_off_from)
            so += e * math.sin(t); co += e * math.cos(t)
            bs += e * math.sin(t); bc += e * math.cos(t)
            k = int(ray.diff_off_from) % 360
            hist[k] += e
            ns[k] += s_near; nc[k] += c_near
            bns += s_near; bnc += c_near
        per_bin.append((i, bin_e))
        bin_sin[i], bin_cos[i] = bs, bc
        near_bin[i] = (bns, bnc)
    peak = max(per_bin, key=lambda item: item[1]) if per_bin else None
    hs = lambda m0: 4.0 * math.sqrt(max(m0, 0.0))
    trains = split_trains(per_bin, spectrum.frequencies, bin_sin, bin_cos, hists=hists) if e10 > 0 else []
    for train in trains:
        _arrive(train, near_bin, near_sin, near_cos)
        train.held = _held(train, hists)
    if buoy and trains:
        trains = _divide_by_buoy(trains, buoy, spectrum.frequencies, hists, near_sin, near_cos,
                                 sum(e for _, e in per_bin), divide_share, divide_need_two,
                                 divide_own_heading)
        owner = _buoy_owner(buoy)
        lobes_at: dict = {}
        for train in trains:
            if train.buoy is not None:
                train.buoy_from_deg = _buoy_heading(train, buoy, grids, hists, owner, lobes_at)
    return Nearshore(
        table.break_id, hs(e10), hs(e_eq), hs(e_hard),
        math.degrees(math.atan2(sn, cn)) % 360 if e10 > 0 else float("nan"),
        math.degrees(math.atan2(so, co)) % 360 if e10 > 0 else float("nan"),
        1.0 / spectrum.frequencies[peak[0]] if peak and peak[1] > 0 else float("nan"),
        unmatched,
        hs(e_fric),
        trains,
        hs(e_short),
        list(buoy or ()),
    )


def _buoy_heading(train, buoy: list[Train], grids, hists, owner, cache: dict) -> float:
    """Where this row's energy came from AT THE BUOY: each of its rays (bin,
    offshore degree) given the nearest direction lobe of its buoy train in
    that bin -- lobes of ≥ 10% of the bin, an even pair maximum entropy makes
    of one swell (`mem_twin`) read as their mean -- and those headings
    energy-weighted. Two rows of one buoy train from different lobes are two
    swells the buoy could not part (BRACKET_DEG)."""

    from .transform import lobes as find_lobes, mem_twin

    k = train.buoy
    bt = buoy[k]
    arc = set(_arc_degrees(bt.arc)) if bt.arc else None
    degrees = _arc_degrees(train.arc)
    sx = sy = 0.0
    for i in train.bins:
        h = hists.get(i)
        grid = grids.get(i)
        if not h or grid is None:
            continue
        key = (k, i)
        if key not in cache:
            dist = [v if arc is None or d in arc else 0.0 for d, v in enumerate(grid)]
            found = [(hd, sh) for hd, sh in find_lobes(dist) if sh >= 0.1]
            if len(found) == 2 and mem_twin(found):
                ms = sum(v * math.sin(math.radians(d + 0.5)) for d, v in enumerate(dist))
                mc = sum(v * math.cos(math.radians(d + 0.5)) for d, v in enumerate(dist))
                found = [(math.degrees(math.atan2(ms, mc)) % 360.0, 1.0)]
            cache[key] = [hd for hd, _ in found]
        heads = cache[key]
        for d in degrees:
            e = h[d]
            if e <= 0 or (train.buoys and owner(i, d) not in train.buoys):
                continue
            to = (min(heads, key=lambda hd: abs((d + 0.5 - hd + 180.0) % 360.0 - 180.0))
                  if heads else d + 0.5)
            sx += e * math.cos(math.radians(to)); sy += e * math.sin(math.radians(to))
    return math.degrees(math.atan2(sy, sx)) % 360.0 if (sx or sy) else math.nan


def bracket_groups(trains, deg: float = BRACKET_DEG) -> list[list[int]]:
    """The rows (indices into `trains`) a page brackets as one swell: ALL the
    rows one buoy train carried, when every one's `buoy_from_deg` sits within
    `deg` of every other's; otherwise none of them. A subset was measured
    too and added about as many wrong brackets as right ones (5 Nov-like
    control: 9 right, 7 wrong). Any other `deg` is for `forecast.trainmerge
    --brackets` to measure."""

    by: dict[int, list[int]] = {}
    for n, t in enumerate(trains):
        if t.buoy is not None:
            by.setdefault(t.buoy, []).append(n)
    out = []
    for rows in by.values():
        heads = [trains[n].buoy_from_deg for n in rows]
        if len(rows) > 1 and not any(math.isnan(h) for h in heads) and all(
                abs((a - b + 180.0) % 360.0 - 180.0) < deg for a in heads for b in heads):
            out.append(rows)
    return sorted(out)


def _held(train, hists: dict[int, list[float]]) -> tuple:
    """The narrowest arc of offshore headings, (first degree FROM, one past
    the last) clockwise, holding HELD_SHARE of the energy this train carried
    to the break: its own bins and, for a train divided by direction, its
    own arc. Empty when it carried none."""

    lo, hi = train.arc or (0, 360)
    inside = {k % 360 for k in range(lo, hi if hi > lo else hi + 360)}
    dist = [0.0] * 360
    for i in train.bins:
        h = hists.get(i)
        if h:
            for k in inside:
                dist[k] += h[k]
    total = sum(dist)
    if total <= 0:
        return ()
    run = [0.0]
    for v in dist + dist:
        run.append(run[-1] + v)

    def start(width: int) -> int | None:
        best = max(range(360), key=lambda k: run[k + width] - run[k])
        return best if run[best + width] - run[best] >= HELD_SHARE * total - 1e-12 else None

    low, high = 1, 360
    while low < high:
        mid = (low + high) // 2
        if start(mid) is None:
            low = mid + 1
        else:
            high = mid
    first = start(low)
    return (first, (first + low) % 360)


def _arrive(train, near_bin: dict[int, tuple[float, float]],
            near_sin: dict[int, list[float]], near_cos: dict[int, list[float]]) -> None:
    """Set a train's 5 m heading, and each lobe's, from the rays its energy
    took: its own bins and, for a train divided by direction, its own arc of
    offshore headings. A lobe holds the offshore degrees nearer it than any
    other lobe, as `transform._divide_by_direction` divides a band. A whole
    band with one direction -- most trains -- sums its bins and never walks
    the degrees."""

    deg = lambda s, c: math.degrees(math.atan2(s, c)) % 360.0 if (s or c) else math.nan
    if not train.arc and not train.lobes:
        s = sum(near_bin[i][0] for i in train.bins if i in near_bin)
        c = sum(near_bin[i][1] for i in train.bins if i in near_bin)
        train.near_from_deg = deg(s, c)
        return
    lo, hi = train.arc or (0, 360)
    degrees = [k % 360 for k in range(lo, hi if hi > lo else hi + 360)]
    heads = [h for h, _ in train.lobes]
    owner = ([min(range(len(heads)), key=lambda m: abs((k + 0.5 - heads[m] + 180.0) % 360.0 - 180.0))
              for k in range(360)] if heads else [0] * 360)
    sums = [[0.0, 0.0] for _ in range(max(len(heads), 1))]
    for i in train.bins:
        ns, nc = near_sin.get(i), near_cos.get(i)
        if ns is None:
            continue
        for k in degrees:
            s, c = ns[k], nc[k]
            if s or c:
                part = sums[owner[k]]
                part[0] += s; part[1] += c
    train.near_from_deg = deg(sum(p[0] for p in sums), sum(p[1] for p in sums))
    train.near_lobes = tuple(deg(s, c) for s, c in sums) if heads else ()


# ------------------------------------------------------------------ local sea

@dataclass
class LocalSea:
    hs_m: float
    tp_s: float
    from_deg: float
    fetch_km: float
    #: "closed": grown fresh over water that ends on land, whose sea no buoy
    #: offshore could have seen. "open": grown ON from the wind sea the buoy
    #: already carried in, over the water between the buoy and the break.
    kind: str = "closed"
    #: Whose wind: "KNZY" on the observed chain, "NWS forecast" on the
    #: forecast (no other wind grows it).
    wind: str = ""
    #: For "open": the carried wind sea it grew on from, at the start depth.
    carried_hs_m: float | None = None


def _grow(u10: float, fetch_m: float) -> tuple[float, float]:
    """Hm0 and Tp for a steady wind over a fetch (CEM 2002, II-2)."""

    ustar = math.sqrt(0.001 * (1.1 + 0.035 * u10)) * u10
    x = G * fetch_m / ustar ** 2
    hs = min(4.13e-2 * math.sqrt(x), 211.5) * ustar ** 2 / G
    tp = min(0.751 * x ** (1.0 / 3.0), 239.8) * ustar / G
    return hs, tp


def _fetch_for(u10: float, hs: float) -> float:
    """The fetch, in metres, over which this wind grows `hs` from calm: the
    inverse of `_grow`. Infinite once `hs` is at or past fully developed."""

    ustar = math.sqrt(0.001 * (1.1 + 0.035 * u10)) * u10
    scaled = G * hs / ustar ** 2
    if scaled >= 211.5:
        return math.inf
    return (scaled / 4.13e-2) ** 2 * ustar ** 2 / G


def buoy_offset(position: tuple[float, float], station: str = "46232") -> tuple[float, float] | None:
    """Distance (km) and bearing (degrees) from a break to the buoy, from the
    coordinates `collector.metadata` fetched -- never typed. None when the
    buoy is not placed, and the open-water growth then does not run."""

    from .siting import load_coordinates
    from .swell import great_circle_km, initial_bearing

    buoy = load_coordinates().get(station)
    if buoy is None:
        return None
    return great_circle_km(position, buoy), initial_bearing(position, buoy)


def local_sea(table: Table, normal_deg: float, wind_kt: float | None,
              wind_from_deg: float | None, *, carried_short_hs: float | None = None,
              buoy: tuple[float, float] | None = None, wind: str = "") -> LocalSea | None:
    """Wind sea the local wind makes on the water off the break.

    Fetch-limited growth (Coastal Engineering Manual, 2002, II-2): with
    u*² = C_D·U10², C_D = 0.001·(1.1 + 0.035·U10),
      g·Hm0/u*² = 4.13e-2·(g·X/u*²)^½,  g·Tp/u* = 0.751·(g·X/u*²)^⅓,
    capped at the fully developed 211.5 and 239.8. Steady wind assumed; a gust
    front younger than its fetch-limited growth time would be overstated.

    Only for a wind blowing FROM the break's seaward half-plane (its waves run
    downwind, onto the beach), and two cases, by the fetch table:

    - **Closed** (the upwind line ends on land within the grid -- Point Loma's
      lee, the islands and Baja): grown fresh over that water. No buoy
      offshore could have seen it.
    - **Open** (the wind blows from inside the windows): the buoy's spectrum
      already holds the wind sea grown upwind of it, carried in; what it
      cannot hold is growth over the water BETWEEN the buoy and the break
      (owner's point, 2026-09-30; measured, a stronger wind near shore -- the
      sea breeze -- grows more there than the buoy carried on ~17–19% of
      onshore open-water hours at North and Center, BRIEFING §36). So it is
      grown ON, by equivalent fetch: the carried short-period sea at the start
      depth (`Nearshore.hs_short`) sets the fetch this wind would have needed
      to make it, that fetch is extended by the buoy-to-break distance along
      the wind (`buoy`, capped at the table's fetch), and only the extra
      energy is added. In this growth law energy rises linearly with fetch,
      so below full development the extra is exactly what the reach grows
      from calm; the carried sea matters as the ceiling: a wind adds nothing
      to a sea already as big as it could ever make (fully developed), which
      is what keeps a light onshore breeze from being counted on top of the
      swell's own short sea. Without `buoy` or `carried_short_hs` the open
      case adds nothing, as before.
    """

    if wind_kt is None or wind_from_deg is None or not table.fetch or wind_kt <= 0:
        return None
    off = ((wind_from_deg - normal_deg + 180.0) % 360.0) - 180.0
    if abs(off) >= 90.0:
        return None
    fetch_km, closed = table.fetch[int(round(wind_from_deg)) % 360]
    u10 = wind_kt * KT_TO_MS
    if closed:
        hs, tp = _grow(u10, fetch_km * 1000.0)
        return LocalSea(hs, tp, wind_from_deg, fetch_km, "closed", wind)

    if buoy is None or carried_short_hs is None:
        return None
    distance_km, bearing = buoy
    reach_km = min(fetch_km, distance_km * math.cos(math.radians(wind_from_deg - bearing)))
    if reach_km <= 0:
        return None
    before = _fetch_for(u10, carried_short_hs)
    if math.isinf(before):
        return None
    hs, tp = _grow(u10, before + reach_km * 1000.0)
    added = math.sqrt(max(0.0, hs ** 2 - carried_short_hs ** 2))
    if added < 0.005:
        return None
    return LocalSea(added, tp, wind_from_deg, reach_km, "open", wind,
                    round(carried_short_hs, 3))


# ------------------------------------------------------------------ surfaces

def train_dicts(trains, buoy: list | None = None) -> list[dict]:
    """The rows a surface shows. With `buoy`, the split the trains were
    divided by (`Nearshore.buoy`), each row also carries `swell`, the buoy
    train that carried most of it (`Train.buoy`). Rows a page shows as ONE
    swell at the buoy (owner's call, 2026-11-03, BRIEFING §49: bracketed
    together, tapped together) carry `group`, the same number for each, and
    `swell_at_buoy`, what that swell was at the buoy, for the drawing's
    caption: rows of one buoy train from one direction there
    (`bracket_groups`, BRACKET_DEG; since 2026-11-08, §49b)."""

    group_of = {n: g for g, rows in enumerate(bracket_groups(trains) if buoy else []) for n in rows}

    def at_buoy(n, k):
        if not buoy or n not in group_of or k is None or not 0 <= k < len(buoy):
            return {}
        b = buoy[k]
        return {"group": group_of[n],
                "swell_at_buoy": {"period_s": round(b.period_s, 1),
                                  "from_deg": None if math.isnan(b.from_deg) else round(b.from_deg),
                                  "lobes": lobes_payload(b)}}

    return [
        {
            "hs_m": round(t.hs_m, 3),
            "period_s": round(t.period_s, 1),
            "from_deg": None if math.isnan(t.from_deg) else round(t.from_deg),
            "share": round(t.share, 4),
            "wind_sea": t.wind_sea,
            "lobes": lobes_payload(t),
            # Where it arrives from in 5 m of water, and each lobe's: the
            # break drawing's inner arrow, never a train row.
            "near_from_deg": None if math.isnan(t.near_from_deg) else round(t.near_from_deg) % 360,
            "near_lobes": [None if math.isnan(d) else round(d) % 360 for d in t.near_lobes],
            **({"swell": t.buoy} if buoy and t.buoy is not None else {}),
            **at_buoy(n, t.buoy),
        }
        for n, t in enumerate(trains)
    ]


def summarise(near: Nearshore, local: LocalSea | None, *, buoy_hs_m: float,
              window_hs_m: float, depth_m: float, profile=None, tide_m: float | None = None,
              normal_deg: float | None = None) -> dict:
    """What a surface shows for one break: the number, its trains, and the
    chain of effects that turned the buoy's reading into it.

    The swell at the start depth and local chop add in energy — different
    waves on the same water, and heights of independent trains add as
    squares. Local chop is listed as its own train, tagged.

    With a `profile` and the open-coast `tide_m`, that sea is then carried in
    to where it breaks (`forecast.surfzone`), and `hs_m` is the breaking
    height. The trains are scaled with it, all by the same factor: a bulk
    breaking model dissipates each part of the spectrum in proportion to its
    energy (as SWAN distributes Battjes-Janssen), so the trains still sum to
    the number above them. Without a profile or a tide, `hs_m` stays the
    figure at the start depth and `breaking` is None — never a breaking height
    at an assumed tide.
    """

    from .surfzone import break_on

    local_hs = local.hs_m if local else 0.0
    total = math.sqrt(near.hs_ref ** 2 + local_hs ** 2)
    trains = train_dicts(near.trains[:3], near.buoy)
    if local:
        trains.append({"hs_m": round(local.hs_m, 3), "period_s": round(local.tp_s, 1),
                       "from_deg": round(local.from_deg), "share": None,
                       "wind_sea": True, "local": True})
    broke = None
    if profile is not None and tide_m is not None and total > 0:
        period = near.peak_period_s if near.peak_period_s == near.peak_period_s else (
            local.tp_s if local else float("nan"))
        angle = (((near.near_from_deg - normal_deg + 180.0) % 360.0) - 180.0
                 if normal_deg is not None and near.near_from_deg == near.near_from_deg else 0.0)
        broke = break_on(profile, hs_start_m=total, period_s=period,
                         start_depth_m=depth_m, angle_deg=angle, tide_m=tide_m)
    headline = broke.hs_m if broke else total
    if broke and total > 0:
        scale = headline / total
        for t in trains:
            t["hs_m"] = round(t["hs_m"] * scale, 3)
    return {
        "hs_m": round(headline, 3),
        "depth_m": round(depth_m, 1),
        "trains": trains,
        "breaking": broke.as_dict() if broke else None,
        "effects": {
            "buoy_hs_m": round(buoy_hs_m, 3),
            "window_hs_m": round(window_hs_m, 3),
            # Refraction alone: bent rays with every window edge still a hard
            # shadow, as the straight-line window treats them, so window ->
            # refracted is the seabed and nothing else. Diffraction alone:
            # the same rays with every edge diffracting (islands, Point Loma
            # tip, Baja tangent), so refracted -> diffracted is that and
            # nothing else. Then bottom friction, then shoaling divided
            # back in.
            "refracted_hs_m": round(near.hs_hard, 3),
            "diffracted_hs_m": round(near.hs_equivalent, 3),
            # Bottom friction along each ray's path, shoaling still out.
            "friction_hs_m": round(near.hs_friction if near.hs_friction is not None
                                   else near.hs_equivalent, 3),
            "shoaled_hs_m": round(near.hs_ref, 3),
            # Swell and local chop together at the start depth: what breaking
            # starts from.
            "with_chop_hs_m": round(total, 3),
            "local": ({"hs_m": round(local.hs_m, 3), "tp_s": round(local.tp_s, 1),
                       "from_deg": round(local.from_deg), "fetch_km": round(local.fetch_km, 1),
                       "fetch": local.kind, "wind": local.wind,
                       "carried_hs_m": local.carried_hs_m}
                      if local else None),
        },
    }


def spectrum_from_partitions(parts: list[tuple[float, float, float, bool]], time,
                             frequencies: list[float]) -> Spectrum:
    """A buoy-style spectrum rebuilt from GFS-Wave partitions, for the
    fallback path when the model's own directional grid is unavailable.

    Each (hs, tp, from_deg, wind_sea) becomes a Pierson-Moskowitz shape with
    the energy its Hs demands, and the assumed spread
    (`transform.spread_for`, BRIEFING §11) as its circular moments; the
    partitions add per frequency as energy and as moment vectors. Read back
    by maximum entropy, like the observed buoy. The assumed spread is exactly
    what the spectral path exists to avoid, and the forecast says which it
    used (`wave_source`).
    """

    import cmath

    from .transform import moments_for_spread, spread_for

    n = len(frequencies)
    width = [(frequencies[min(i + 1, n - 1)] - frequencies[max(i - 1, 0)])
             / (2.0 if 0 < i < n - 1 else 1.0) for i in range(n)]
    c11 = [0.0] * n
    m1 = [0j] * n
    m2 = [0j] * n
    for hs, tp, from_deg, wind_sea in parts:
        if not hs or not tp or hs <= 0 or tp <= 0:
            continue
        fp = 1.0 / tp
        shape = [math.exp(-1.25 * (fp / f) ** 4) * (f / fp) ** -5 if f > 0 else 0.0
                 for f in frequencies]
        m0 = sum(v * w for v, w in zip(shape, width)) or 1.0
        scale = (hs / 4.0) ** 2 / m0
        r1, r2 = moments_for_spread(spread_for(tp, wind_sea))
        a = math.radians(from_deg)
        for i, v in enumerate(shape):
            e = v * scale
            c11[i] += e
            m1[i] += e * r1 * cmath.exp(1j * a)
            m2[i] += e * r2 * cmath.exp(2j * a)
    a1, a2, r1s, r2s = [], [], [], []
    for i in range(n):
        if c11[i] > 0:
            v1, v2 = m1[i] / c11[i], m2[i] / c11[i]
            r1s.append(abs(v1)); a1.append(math.degrees(cmath.phase(v1)) % 360.0)
            r2s.append(abs(v2)); a2.append((math.degrees(cmath.phase(v2)) / 2.0) % 180.0)
        else:
            r1s.append(0.0); a1.append(0.0); r2s.append(0.0); a2.append(0.0)
    return Spectrum(time, list(frequencies), c11, a1, a2, r1s, r2s, spread="mem")


def table_frequencies(tables: dict[str, "Table"]) -> list[float]:
    return sorted(next(iter(tables.values())).by_freq) if tables else []


def load_tables(directory: Path = TABLE_DIR) -> dict[str, Table]:
    return {sid: Table.load(sid, directory) for sid in BREAKS}


# ------------------------------------------------------------------ report

def _pct(values, q):
    ordered = sorted(v for v in values if v == v)
    if not ordered:
        return float("nan")
    k = (len(ordered) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def report(spectra: list[Spectrum]) -> str:
    from .geometry import load

    spots, blockers = load()
    by_id = {s.id: s for s in spots}
    tables = {sid: Table.load(sid) for sid in BREAKS}
    rows = {sid: [] for sid in BREAKS}
    for sp in spectra:
        # What ships reads the buoy by maximum entropy; so does this report.
        sp = sp.with_spread("mem")
        grids = density_grids(sp)
        for sid in BREAKS:
            ap = through(sp, by_id[sid], blockers)
            if not (ap.hs_in_window_m > 0):
                continue
            ns = carry(sp, tables[sid], grids)
            rows[sid].append((ap.hs_in_window_m, ns, math.degrees(0)))
    out = [f"{len(spectra)} spectra from 46232. Ratios are nearshore / aperture, "
           "median [10th, 90th]."]
    for sid in BREAKS:
        r = rows[sid]
        if not r:
            continue
        ap = [a for a, _, _ in r]
        eq = [n.hs_equivalent / a for a, n, _ in r]
        h10 = [n.hs_ref / a for a, n, _ in r]
        refr = [n.hs_hard / a for a, n, _ in r]
        diff = [n.hs_equivalent / n.hs_hard - 1 for _, n, _ in r if n.hs_hard > 0]
        fric = [n.hs_friction / n.hs_equivalent - 1 for _, n, _ in r
                if n.hs_equivalent > 0 and n.hs_friction is not None]
        out.append(f"\n  {sid}  (n = {len(r)}, aperture Hs median {_pct(ap, .5):.2f} m)")
        out.append(f"    refraction, hard edges:               {_pct(refr, .5):.3f} "
                   f"[{_pct(refr, .1):.3f}, {_pct(refr, .9):.3f}]")
        out.append(f"    + diffraction at every edge:          {_pct(eq, .5):.3f} "
                   f"[{_pct(eq, .1):.3f}, {_pct(eq, .9):.3f}]")
        out.append(f"    at {tables[sid].start_depth_m:.0f} m with shoaling:         {_pct(h10, .5):.3f} "
                   f"[{_pct(h10, .1):.3f}, {_pct(h10, .9):.3f}]")
        out.append(f"    height diffraction adds to hard edges: {100 * _pct(diff, .5):+.1f}% "
                   f"[{100 * _pct(diff, .1):+.1f}, {100 * _pct(diff, .9):+.1f}]")
        if fric:
            out.append(f"    height bottom friction takes:         {100 * _pct(fric, .5):+.2f}% "
                       f"[{100 * _pct(fric, .1):+.2f}, {100 * _pct(fric, .9):+.2f}]; "
                       f"worst {100 * min(fric):+.1f}%")
    south = rows["coronado_south"]
    north = rows["coronado_north"]
    if south and north and len(south) == len(north):
        ap_ratio = [s[0] / n[0] for s, n in zip(south, north)]
        ns_ratio = [s[1].hs_equivalent / n[1].hs_equivalent for s, n in zip(south, north)
                    if n[1].hs_equivalent > 0]
        out.append("\n  south / north (the differential, BRIEFING §11):")
        out.append(f"    aperture   {_pct(ap_ratio, .5):.3f} [{_pct(ap_ratio, .1):.3f}, {_pct(ap_ratio, .9):.3f}]")
        out.append(f"    nearshore  {_pct(ns_ratio, .5):.3f} [{_pct(ns_ratio, .1):.3f}, {_pct(ns_ratio, .9):.3f}]")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)
    spectra = load_spectra(ROOT / "data" / "spectra" / "46232", limit=args.limit)
    print(report(spectra))
    return 0


if __name__ == "__main__":
    sys.exit(main())
