"""Backward ray tracing from each break to deep water: refraction and shoaling.

    python -m forecast.raytrace            # build data/nearshore/<break>.csv
    python -m forecast.raytrace --check    # the planar-beach control only

PRECOMPUTE ONLY. Needs numpy (requirements-precompute.txt). The forecast never
imports this module; it reads the tables it writes.

WHAT IT DOES. `forecast.transform` treats the sea between the buoy and the
beach as bottomless: a heading reaches a break along a straight line or not at
all. Real swell bends toward shallow water (refraction) and changes height as
the depth changes (shoaling). This traces that, the way CDIP's MOP does
(O'Reilly & Guza 1991, 1993), from the beach outward:

1. For each break, a START point on the `H_REF` contour straight off the
   break's chord, on the 8 m nearshore grid.
2. For each frequency bin and each arrival heading there (every `DIR_STEP_DEG`
   across the seaward half-circle), a ray is traced BACKWARD — seaward — over
   the grids, bending by the linear-theory phase speed c(ω, h):
   dβ/ds = (1/c)(c_x sin β − c_y cos β), β the look-back direction.
3. It stops when the water is deep (h > L0, where depth changes c by under
   0.001%; stopping at L0/2 left c 0.4% short and each heading ~0.2° short of
   Snell, measured on the planar control)
   and the rest of the path is a straight line, which is then tested against
   the charted blockers in `spots.json` and walked over the grids for any
   other land (`leg_blockers`). Or it stops on land — Point Loma, the Baja
   coast and the Coronado Islands are all land in the grids (the islands
   burned in from their imaged outlines, `ISLANDS_FILE`, since GMRT lacks
   two of them), and a ray crossing an island's own shelf refracts over
   it — or at the grid's edge, counted as deep if the water there is already
   past L0/2 and flagged `grid edge` with its depth otherwise.
4. Energy along a ray: for stationary linear refraction S(f, θ)·c·c_g is
   invariant (Longuet-Higgins 1957), so the spectral density arriving at the
   start point from heading θn is S_off(f, θ0)·(c0·cg0)/(c·cg), with θ0 the
   heading the ray left deep water on. Integrating that over θn is refraction
   AND shoaling together; `tests/test_raytrace.py` checks it against Snell's
   law and the textbook Ks²·Kr² on a planar beach.

5. Diffraction at every window edge, on those bent rays (`table`): the
   islands by the two-edge Babinet factor, the Point Loma tip and the Baja
   tangent by the straight-edge one. Each ray carries a hard-edged and a
   diffracting answer, so the two effects are measured apart. A ray that
   lands on any of them gets energy only by diffraction, along the heading
   of a ray that clears it.

6. Bottom friction along each ray's path over the shelf, stored apart from
   the gain so the surface can state it as its own effect. What ships is
   Madsen's law (BRIEFING §57), which depends on the sea's height, period and
   the tide: marched along every carrying path for a grid of all three
   (`madsen_losses`) into `<break>_madsen.json`, which `nearshore.carry`
   interpolates. The JONSWAP law (`friction_rate`), a fixed factor per ray,
   stays in the table's `friction` columns as the control.

7. How long a wave group takes from 46232 to each break (`leg_table`, into
   `<break>_leg.csv`): ∫ ds / cg along each unblocked ray from its exit to the
   start depth, plus the plane-wave offset from the buoy to that exit along
   the deep-water heading. Read by the LIVE briefing (`forecast.upstreamlag`);
   it changes no gain.

WHAT IT IS NOT. Refraction and diffraction are computed separately and
combined per ray, not solved together as the mild-slope equation would; no
currents, no wind input. Breaking lives in `forecast.surfzone`, on a profile
that starts seaward of the table's start depth (`SURF_START_M`, BRIEFING §58):
the rays carry none, and on big days the sea is already breaking before 5 m.
The result is the spectrum at `H_REF` (5) metres of water off each break — still
not a face height at the sand, and still unverified: nothing observes the
beach. Depth is below MSL when the sidecar carries CO-OPS's MSL/NAVD88 offset,
and below NAVD88 (about a metre shallower) when it does not; the table header
says which.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .geometry import Blocker, Spot, load
from .swell import initial_bearing
from .transform import load_spectra
from .utm import from_utm, to_utm

ROOT = Path(__file__).resolve().parent.parent
BATHY_DIR = ROOT / "data" / "bathymetry"
OUT_DIR = ROOT / "data" / "nearshore"
BREAKS = ("coronado_north", "coronado_center", "coronado_south")

G = 9.81
#: Reference depth the nearshore spectrum is stated at. 10 m was the first
#: choice (it is where CDIP's MOP states its points) and it failed at north:
#: Coronado's north break sits on a flat shelf 7-10 m deep for 2 km offshore,
#: so the 10 m contour straight out from it lay 2.2 km away, level with the
#: Point Loma tip and OUTSIDE its shadow — the table described a different
#: place, and made north 21% bigger than south. The 5 m contour is 130-230 m
#: off all three breaks. The figure there is linear and unbroken; on big days
#: the sea is already breaking before 5 m, so the surf zone does not start at
#: H_REF: its profile runs further out (`SURF_START_M`, BRIEFING §58), the 5 m
#: sea is carried back out to it linearly and broken on the way in. Moving
#: where the surf zone starts moves nothing here.
H_REF = 5.0
#: Arrival headings are sampled this finely. Behind Point Loma the offshore
#: heading changes fast with the nearshore one, and the table has to resolve
#: that rather than smear it.
DIR_STEP_DEG = 0.5
#: Below this depth a ray is on the beach, the jetty or a shoal that dries.
H_LAND = 0.3
#: Step length as a fraction of the grid cell a ray is currently on.
STEP_FRACTION = 0.5
#: Rays longer than this without reaching deep water are stopped and flagged.
MAX_PATH_M = 80_000.0
#: Bottom friction, the JONSWAP coefficient (Hasselmann et al. 1973), m²/s³:
#: the table's `friction` columns, shipped until BRIEFING §57 and now the
#: control `nearshore.carry(friction="jonswap")` reads.
#: 0.038 is SWAN's default and what Zijlema, van Vledder & Holthuijsen (2012)
#: recommend for swell and wind sea alike. Taken from the literature, never
#: tuned: fitting it to anything is calibration, and there is nothing
#: observed at these beaches to fit it to.
C_BOTTOM = 0.038
#: Madsen bottom friction (Madsen, Poon & Graber 1988) as SWAN implements it,
#: what ships (owner's decision 2026-11-18, BRIEFING §57): C = f_w·g·U_rms/√2
#: in place of C_BOTTOM, f_w from the bed's roughness and the near-bed orbital
#: excursion. k_N = 0.05 m and m_f = −0.08 are SWAN's defaults. Literature
#: values, never tuned.
MADSEN_K_N = 0.05
MADSEN_M_F = -0.08
#: The Madsen survival table's nodes (`madsen_losses`). Madsen's rate depends
#: on the sea the ray crosses, so the share a path keeps is tabulated against
#: the break's linear (frictionless) 5 m Hs, its peak period and the tide, and
#: `nearshore.carry` interpolates: the loss linearly in Hs (zero at zero),
#: in PERIOD between peak nodes (three times more accurate than in frequency
#: at the same nodes) and in tide. Sized by measurement against the exact
#: march over 290 archived hours (BRIEFING §57): worst 0.25% of the 5 m
#: height, 99th percentile 0.19%. Coarser grids missed: 3 tide nodes 0.47%,
#: 6 period nodes 0.6-0.8%. Hs above 6 m extrapolates (the loss is near
#: linear in Hs there); the peak clamps outside 5-25 s and the tide outside
#: −1.5 to +2.25 m on MSL (the highest king tides are about +1.7 m).
MADSEN_HS_M = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0)
MADSEN_PEAK_HZ = (0.04, 0.05, 0.06, 0.07, 0.085, 0.1, 0.13, 0.17, 0.2)
MADSEN_TIDE_M = (-1.5, -0.75, 0.0, 0.75, 1.5, 2.25)
#: Each frequency's loss table (−ln survival, path × node) is stored as the
#: fewest singular components that give every path's loss back within this
#: at EVERY node, after the stored values are rounded (`compress_losses`):
#: 0.25% of one path's height at its worst node. In the sizing, keeping
#: three or four components already left the hourly 5 m height as the full
#: grid gives it; the runtime control (`forecast.shelfloss`) measures what
#: ships. A mechanical compression of the march, not a fit to anything.
MADSEN_LOSS_TOL = 0.005
#: Losses past this are the same to the chain (survival under 1e-5) and
#: are capped before compressing, so a dead path costs no components.
MADSEN_LOSS_CAP = 12.0


# ------------------------------------------------------------------ physics

def wavenumber(omega: float | np.ndarray, h: np.ndarray) -> np.ndarray:
    """k from ω² = g k tanh(k h), by Newton from Eckart's approximation."""

    h = np.maximum(h, 1e-3)
    k0 = omega * omega / G
    k = k0 / np.sqrt(np.tanh(k0 * h))
    for _ in range(6):
        th = np.tanh(k * h)
        f = G * k * th - omega * omega
        df = G * th + G * k * h * (1.0 - th * th)
        k = k - f / df
    return k


def friction_rate(omega: float, h: np.ndarray) -> np.ndarray:
    """Fraction of the energy flux bottom friction removes per metre of ray.

    The JONSWAP source term is S = −C_b·ω²/(g²·sinh²(kh))·E, linear in E, so
    along a ray d(flux)/ds = −flux·C_b·ω²/(g²·sinh²(kh)·cg). Linear is what
    makes it a per-ray FACTOR stored in the table's `friction` columns. What
    ships is Madsen's law, which depends on the wave height and is stored
    as a table over the sea's height, period and tide instead
    (`madsen_losses`); this JONSWAP factor stays as its control.
    """

    h = np.maximum(h, 1e-3)
    k = wavenumber(omega, h)
    kh = np.minimum(k * h, 300.0)
    _, cg, _ = speeds(omega, h)
    return C_BOTTOM * omega ** 2 / (G ** 2 * np.sinh(kh) ** 2 * cg)


def speeds(omega: float, h: np.ndarray):
    """(c, cg, dc/dh) at depth h for angular frequency ω."""

    k = wavenumber(omega, h)
    kh = k * np.maximum(h, 1e-3)
    th = np.tanh(kh)
    sech2 = 1.0 - th * th
    c = omega / k
    cg = 0.5 * c * (1.0 + 2.0 * kh / np.sinh(np.minimum(2.0 * kh, 700.0)))
    dc_dh = omega * sech2 / (th + kh * sech2)
    return c, cg, dc_dh


def madsen_fw(ab: np.ndarray, k_n: float = MADSEN_K_N) -> np.ndarray:
    """Madsen et al. (1988) as SWAN solves it:
    1/(4√fw) + log10(1/(4√fw)) = m_f + log10(a_b/k_N), and 0.3 below a_b/k_N = 1.57.

    `k_n` is the bottom roughness; what ships is MADSEN_K_N, everywhere.
    `forecast.reefbound` sweeps it, report only (handoff 27d)."""

    ab = np.asarray(ab, float)
    rhs = MADSEN_M_F + np.log10(np.maximum(ab, 1e-9) / k_n)
    y = np.maximum(rhs, 0.5)               # y = 1/(4√fw); Newton on y + log10 y = rhs
    for _ in range(30):
        y = y - (y + np.log10(y) - rhs) / (1.0 + 1.0 / (y * math.log(10)))
        y = np.maximum(y, 1e-3)
    fw = 1.0 / (16.0 * y * y)
    return np.where(ab / k_n > 1.57, fw, 0.3)


_FW_LOG_AB = np.linspace(-4.0, 2.0, 3001)          # log10 of a_b in metres
_FW: dict[float, np.ndarray] = {}


def fw_lookup(ab: np.ndarray, k_n: float = MADSEN_K_N) -> np.ndarray:
    """madsen_fw on a table in log10(a_b), the form `forecast.shelfloss`
    measured with (pinned to the solved form by its control and a test)."""

    fw = _FW.get(k_n)
    if fw is None:
        fw = _FW[k_n] = madsen_fw(10.0 ** _FW_LOG_AB, k_n)
    return np.interp(np.log10(np.maximum(ab, 1e-4)), _FW_LOG_AB, fw)


def madsen_losses(steps: list[tuple[np.ndarray, np.ndarray]], omega: float,
                  hs_m=MADSEN_HS_M, peak_hz=MADSEN_PEAK_HZ, tide_m=MADSEN_TIDE_M,
                  law: str = "madsen", h_ref: float = H_REF,
                  k_n: float = MADSEN_K_N) -> np.ndarray:
    """−ln(survival) per path at every node, shape (paths, peak, tide, hs).

    `steps` is each path's wet steps as `trace(..., steps=True)` records them,
    start point outward: the depth below MSL at the start of each step and its
    length, the same quadrature as the table's JONSWAP `friction`. Marched
    deep water inward, one step at a time, at depth h + tide (no shallower
    than H_LAND), with

        d ln F / ds = −C·ω²/(g²·sinh²(kh)·cg)      (SWAN's form, this ray's ω)
        C = f_w(a_b)·g·U_rms/√2                    (Madsen)
        U_rms = ω_p·H_loc/(4·sinh(k_p h)),  a_b = √2·H_loc/(4·sinh(k_p h))
        H_loc = Hs5·√(cg_p(5 m + tide)/cg_p(h))·√F

    the sea around the ray taken as the break's linear 5 m Hs at the peak
    period, de-shoaled to the local depth and reduced by the ray's own losses
    so far: `forecast.shelfloss`'s mean-field estimate, the same discrete
    equation its fixed point solves, here solved exactly in one forward pass.
    With law="jonswap" C is C_BOTTOM and, at tide 0, the result is the
    table's `friction` back (the control `tests/test_raytrace.py` holds).

    `h_ref` is the depth the `hs_m` axis is the linear Hs AT (the table's
    start, as `nearshore.carry` measures it). What ships is H_REF; a table
    started deeper (`forecast.nearshoretest`, at a buoy in 21 m) passes its
    own, or the local sea would be de-shoaled from the wrong depth.

    `k_n` is the roughness along every path (MADSEN_K_N ships), or a list
    with one array per path giving each wet step's roughness, aligned with
    `steps`; `forecast.reefbound` sweeps and locates it, report only.
    """

    hs_m = np.asarray(hs_m, float)
    peak_hz = np.asarray(peak_hz, float)
    n_p, n_t, n_h = peak_hz.size, len(tide_m), hs_m.size
    out = np.zeros((len(steps), n_p, n_t, n_h))
    lengths = np.array([len(h) for h, _ in steps], int)
    if not len(steps) or lengths.max() == 0:
        return out
    # Longest path first, right-aligned (every path ENDS at the start point
    # together): at column c the live paths are a leading block of rows.
    order = np.argsort(-lengths, kind="stable")
    n, width = len(steps), int(lengths.max())
    depth = np.full((n, width), H_REF)
    ds = np.zeros((n, width))
    per_step = not np.isscalar(k_n)
    kmat = np.full((n, width), MADSEN_K_N if per_step else float(k_n))
    for row, j in enumerate(order):
        h, d = steps[j]
        if len(h):
            depth[row, width - len(h):] = h[::-1]
            ds[row, width - len(d):] = d[::-1]
            if per_step:
                kj = np.asarray(k_n[j], float)
                if kj.shape != np.shape(h):
                    raise ValueError(f"path {j}: {kj.size} roughness values for {len(h)} steps")
                kmat[row, width - len(h):] = kj[::-1]
    kinds = np.unique(kmat)
    first = width - lengths[order]                 # first live column per row, ascending
    # live_rows[c]: rows 0..live_rows[c]-1 have a step at column c.
    live_rows = np.searchsorted(first, np.arange(width), side="right")
    w_p = 2.0 * math.pi * peak_hz
    for it, tide in enumerate(tide_m):
        ht = np.maximum(depth + tide, H_LAND)
        k = wavenumber(omega, ht)
        _, cg, _ = speeds(omega, ht)
        shape = omega ** 2 / (G ** 2 * np.sinh(np.minimum(k * ht, 300.0)) ** 2 * cg) * ds
        if law == "jonswap":
            out[order, :, it, :] = (C_BOTTOM * shape.sum(axis=1))[:, None, None]
            continue
        shp = np.empty((n_p, n, width))
        unit = np.empty((n_p, n, width))
        for ip, wp in enumerate(w_p):
            kp = wavenumber(wp, ht)
            _, cgp, _ = speeds(wp, ht)
            _, cg5, _ = speeds(wp, np.array([h_ref + tide]))
            shp[ip] = np.sinh(np.minimum(kp * ht, 300.0))
            unit[ip] = np.sqrt(cg5[0] / cgp)
        ln_f = np.zeros((n_p, n_h, n))
        for c in range(width):
            m = int(live_rows[c])
            if m == 0:
                continue
            hs_loc = hs_m[None, :, None] * unit[:, None, :m, c] * np.exp(0.5 * ln_f[:, :, :m])
            excursion = hs_loc / (4.0 * shp[:, None, :m, c])
            ab = math.sqrt(2.0) * excursion
            urms = w_p[:, None, None] * excursion
            if kinds.size == 1:
                fw = fw_lookup(ab, float(kinds[0]))
            else:
                kc = kmat[:m, c]
                fw = np.zeros_like(ab)
                for u in kinds:
                    on = kc == u
                    if on.any():
                        fw = np.where(on[None, None, :], fw_lookup(ab, float(u)), fw)
            ln_f[:, :, :m] -= fw * G * urms / math.sqrt(2.0) * shape[None, None, :m, c]
        out[order, :, it, :] = -ln_f.transpose(2, 0, 1)
    return out


def compress_losses(loss: np.ndarray, tol: float = MADSEN_LOSS_TOL,
                    cap: float = MADSEN_LOSS_CAP) -> tuple[list, list, float]:
    """(weights per path, basis rows, worst |Δloss| at any node) for a
    (paths, nodes) loss table: the fewest singular components whose ROUNDED
    stored values give every path's (capped) loss back within `tol` at
    every node. A path's loss is Σ_r weight_r·basis_r. Basis values are
    stored to 1e-5, weights (each column of unit length) to 1e-6."""

    x = np.minimum(np.asarray(loss, float), cap)
    if x.size == 0 or not np.any(x > 0):
        return [[] for _ in range(x.shape[0])], [], 0.0
    u, s, vt = np.linalg.svd(x, full_matrices=False)

    def fmt(v: float, n: int) -> float:
        v = round(float(v), n)
        return 0 if v == 0 else v

    for r in range(1, s.size + 1):
        basis = [[fmt(v, 5) for v in row] for row in (s[:r, None] * vt[:r])]
        weights = [[fmt(v, 6) for v in row] for row in u[:, :r]]
        err = float(np.max(np.abs(np.array(weights) @ np.array(basis) - x)))
        if err <= tol:
            return weights, basis, err
    return weights, basis, err


# ------------------------------------------------------------------ grids

@dataclass
class Grid:
    depth: np.ndarray        # metres of water, positive; land <= 0
    dx: np.ndarray           # d(depth)/d(easting)
    dy: np.ndarray           # d(depth)/d(northing)
    left: float
    top: float
    cell: float

    @classmethod
    def from_elevation(cls, elevation_m: np.ndarray, left: float, top: float,
                       cell: float, msl_above_navd88: float) -> "Grid":
        return cls.from_depth(msl_above_navd88 - elevation_m, left, top, cell)

    @classmethod
    def from_depth(cls, depth: np.ndarray, left: float, top: float, cell: float) -> "Grid":
        gy, gx = np.gradient(depth, cell)
        # Rows run north to south, so the row gradient is -d/d(northing).
        return cls(depth, gx, -gy, left, top, cell)

    def inside(self, x: np.ndarray, y: np.ndarray, margin: float = 1.0) -> np.ndarray:
        col = (x - self.left) / self.cell
        row = (self.top - y) / self.cell
        rows, cols = self.depth.shape
        return (col >= margin) & (col <= cols - 1 - margin) & (row >= margin) & (row <= rows - 1 - margin)

    def sample(self, x: np.ndarray, y: np.ndarray):
        """Bilinear depth and gradient at (x, y); callers keep points inside."""

        col = (x - self.left) / self.cell - 0.5
        row = (self.top - y) / self.cell - 0.5
        rows, cols = self.depth.shape
        c0 = np.clip(np.floor(col).astype(int), 0, cols - 2)
        r0 = np.clip(np.floor(row).astype(int), 0, rows - 2)
        fc = np.clip(col - c0, 0.0, 1.0)
        fr = np.clip(row - r0, 0.0, 1.0)

        def bil(a):
            return ((a[r0, c0] * (1 - fc) + a[r0, c0 + 1] * fc) * (1 - fr)
                    + (a[r0 + 1, c0] * (1 - fc) + a[r0 + 1, c0 + 1] * fc) * fr)

        return bil(self.depth), bil(self.dx), bil(self.dy)


@dataclass
class Bathymetry:
    """The nearshore grid where it covers, the regional grid elsewhere."""

    grids: list[Grid]            # finest first
    msl_offset_m: float | None   # None: CoNED depths are below NAVD88, not MSL

    #: Which grids were found, finest first; `outer` is absent until the
    #: workflow has fetched it, and rays that leave the others are then
    #: flagged at the edge rather than traced over invented seabed.
    names: tuple[str, ...] = ()

    @classmethod
    def load(cls, directory: Path = BATHY_DIR) -> "Bathymetry":
        grids, names = [], []
        offset = None
        for name in ("nearshore", "regional", "outer"):
            if not (directory / f"{name}.json").exists():
                continue
            meta = json.loads((directory / f"{name}.json").read_text())
            raw = np.load(directory / f"{name}.npz")["elevation_dm"].astype(float)
            raw[raw == meta["nodata"]] = np.nan
            a, _, left, _, _, top = meta["transform"]
            if meta["vertical_datum"] == "NAVD88":
                offset = meta["datum"].get("msl_above_navd88_m")
                shift = offset or 0.0
            else:
                shift = 0.0          # already sea level
            grid = Grid.from_elevation(raw / 10.0, left, top, a, shift)
            grids.append(with_islands(grid, name, directory))
            names.append(name)
        return cls(grids, offset, tuple(names))

    def sample(self, x: np.ndarray, y: np.ndarray):
        """(depth, dh/dx, dh/dy, cell, covered) from the finest grid covering each point."""

        h = np.full(x.shape, np.nan)
        hx = np.zeros(x.shape)
        hy = np.zeros(x.shape)
        cell = np.full(x.shape, np.nan)
        todo = np.ones(x.shape, bool)
        for grid in self.grids:
            here = todo & grid.inside(x, y)
            if here.any():
                gh, gx, gy = grid.sample(x[here], y[here])
                # A cell the source left empty is not covered by this grid;
                # the next, coarser one gets the point instead.
                ok = np.isfinite(gh) & np.isfinite(gx) & np.isfinite(gy)
                sel = np.flatnonzero(here)[ok]
                h[sel], hx[sel], hy[sel] = gh[ok], gx[ok], gy[ok]
                cell[sel] = grid.cell
                todo[sel] = False
        return h, hx, hy, cell, ~todo


# ------------------------------------------------------------------ islands as land

#: The Coronado Islands' outlines, imaged (BRIEFING §55): GMRT's 90 m grid has
#: only South Coronado as land, Middle Coronado a shoal (its shallowest stored
#: cell 5.2 m deep) and North Coronado 22 m and more, and its 400 m grid none. Until 2026-11-15 rays
#: refracted over a shoal where North Coronado stands and carried up to 18% of
#: North's 5 m energy on some hours across it, and the map drew open water.
ISLANDS_FILE = "islands.json"
#: A grid cell is island where at least this share of it is inside an outline.
ISLAND_COVER = 0.25
#: The share is counted on this many points a side in each cell.
ISLAND_SAMPLES = 8


def island_outlines(directory: Path = BATHY_DIR) -> tuple[list[dict], tuple[str, ...]]:
    """The imaged island outlines in UTM, and the grids they are burned into."""

    path = directory / ISLANDS_FILE
    if not path.exists():
        return [], ()
    data = json.loads(path.read_text(encoding="utf-8"))
    out = [{"name": isl["name"], "height_m": float(isl["height_m"]),
            "parts": [np.array([to_utm(la, lo) for la, lo in ring]) for ring in isl["parts"]]}
           for isl in data["islands"]]
    return out, tuple(data.get("burned_into", ()))


def _inside(ring: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Even-odd point-in-polygon test for points (x, y) against one ring."""

    x0, y0 = ring[:, 0][None, :], ring[:, 1][None, :]
    x1, y1 = np.roll(ring[:, 0], -1)[None, :], np.roll(ring[:, 1], -1)[None, :]
    px, py = x[:, None], y[:, None]
    straddles = (y0 > py) != (y1 > py)
    with np.errstate(divide="ignore", invalid="ignore"):
        cross = x0 + (py - y0) * (x1 - x0) / (y1 - y0)
    return (np.sum(straddles & (px < cross), axis=1) % 2) == 1


def burn_islands(depth: np.ndarray, left: float, top: float, cell: float,
                 outlines: list[dict]) -> int:
    """Raise the cells an island covers (`ISLAND_COVER`) to land, in place.

    A burned cell is the island's height or the grid's own elevation,
    whichever is higher: GMRT's South Coronado peaks at 149 m and keeps it.
    Returns how many cells changed."""

    rows, cols = depth.shape
    sub = (np.arange(ISLAND_SAMPLES) + 0.5) / ISLAND_SAMPLES
    changed = 0
    for isl in outlines:
        pts = np.vstack(isl["parts"])
        c0 = max(int((pts[:, 0].min() - left) // cell), 0)
        c1 = min(int((pts[:, 0].max() - left) // cell), cols - 1)
        r0 = max(int((top - pts[:, 1].max()) // cell), 0)
        r1 = min(int((top - pts[:, 1].min()) // cell), rows - 1)
        if c0 > c1 or r0 > r1:
            continue
        cc, rr = np.meshgrid(np.arange(c0, c1 + 1), np.arange(r0, r1 + 1))
        px = left + (cc[..., None, None] + sub[None, None, None, :]) * cell
        py = top - (rr[..., None, None] + sub[None, None, :, None]) * cell
        px, py = np.broadcast_arrays(px, py)
        inside = np.zeros(px.size, bool)
        for ring in isl["parts"]:
            inside |= _inside(ring, px.ravel(), py.ravel())
        share = inside.reshape(px.shape).mean(axis=(2, 3))
        r, c = np.nonzero(share >= ISLAND_COVER)
        r, c = r + r0, c + c0
        land = -isl["height_m"]
        lower = ~(depth[r, c] <= land)          # deeper than the island, or no data
        depth[r[lower], c[lower]] = land
        changed += int(lower.sum())
    return changed


def with_islands(grid: "Grid", name: str, directory: Path = BATHY_DIR) -> "Grid":
    """The grid with the imaged islands burned in, if it is one they are for;
    the stored grid is never edited, so a fetch keeps them."""

    outlines, into = island_outlines(directory)
    if name not in into:
        return grid
    depth = grid.depth.copy()
    burn_islands(depth, grid.left, grid.top, grid.cell, outlines)
    return Grid.from_depth(depth, grid.left, grid.top, grid.cell)


# ------------------------------------------------------------------ islands

#: The Coronado Islands are diffracted, not blocked. Measured (BRIEFING §10,
#: docs/design/geometry.md): Fresnel numbers 1.6 and 0.2 — the shadow fills in by the time
#: it reaches Coronado, and the geometric block the aperture applies is a
#: ceiling on their effect, not an estimate of it.
ISLAND_PREFIX = "Coronado Islands"
#: An island reaches this far past its charted extent: the ring the wavelength
#: it diffracts at is read in starts here, and land met inside it on a ray's
#: straight leg is the island's (diffracted), not a blocker's. Until
#: 2026-11-15 it also sized the "see-through" disc rays were re-traced over,
#: and moving it 50 m moved single hours by up to a third (BRIEFING §52, §55).
ISLAND_PAD_M = 400.0
#: Depth sampled in this ring outside the island sets the wavelength the
#: islands diffract at.
ISLAND_RING_M = 2000.0


@dataclass
class Island:
    name: str
    a: tuple[float, float]       # UTM, charted extreme vertices
    b: tuple[float, float]
    centre: tuple[float, float]
    radius: float
    depth: float = float("nan")  # ring depth, set by `ring_depths`


def islands_from(blockers: list[Blocker]) -> list[Island]:
    out = []
    for blocker in blockers:
        if not blocker.name.startswith(ISLAND_PREFIX):
            continue
        a, b = to_utm(*blocker.a), to_utm(*blocker.b)
        centre = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        radius = math.hypot(a[0] - b[0], a[1] - b[1]) / 2.0 + ISLAND_PAD_M
        out.append(Island(blocker.name, a, b, centre, radius))
    return out


def ring_depths(bathy: "Bathymetry", islands: list[Island]) -> None:
    """Set each island's `depth`: the median water depth in the ring round it,
    where the wavelength it diffracts at is read. The finest grid that
    reaches the island sets it."""

    for island in islands:
        for grid in bathy.grids:
            rows, cols = grid.depth.shape
            ys = grid.top - (np.arange(rows) + 0.5) * grid.cell
            xs = grid.left + (np.arange(cols) + 0.5) * grid.cell
            r = np.hypot(xs[None, :] - island.centre[0], ys[:, None] - island.centre[1])
            if not (r <= island.radius).any():
                continue
            ring = (r > island.radius) & (r <= island.radius + ISLAND_RING_M) & (grid.depth > H_LAND)
            fill = float(np.nanmedian(grid.depth[ring])) if ring.any() else float("nan")
            if math.isfinite(fill):
                island.depth = fill
                break


_FRESNEL_U = np.linspace(-40.0, 40.0, 800_001)
_step = _FRESNEL_U[1] - _FRESNEL_U[0]
_cos = np.cos(0.5 * math.pi * _FRESNEL_U ** 2)
_sin = np.sin(0.5 * math.pi * _FRESNEL_U ** 2)
_C = np.concatenate([[0.0], np.cumsum(0.5 * (_cos[1:] + _cos[:-1]) * _step)])
_S = np.concatenate([[0.0], np.cumsum(0.5 * (_sin[1:] + _sin[:-1]) * _step)])
_mid = _FRESNEL_U.size // 2
_C -= _C[_mid]
_S -= _S[_mid]
del _cos, _sin


def fresnel(u: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """C(u), S(u) with the π/2 convention: C(∞) = S(∞) = 1/2.

    Tabulated by trapezoid to |u| = 40 and asymptotic beyond, where the
    remainder is under 1/(π·40) ≈ 0.008 and oscillating.
    """

    u = np.asarray(u, float)
    inside = np.abs(u) <= 40.0
    c = np.empty_like(u)
    s = np.empty_like(u)
    c[inside] = np.interp(u[inside], _FRESNEL_U, _C)
    s[inside] = np.interp(u[inside], _FRESNEL_U, _S)
    far = ~inside
    if far.any():
        uf = u[far]
        sign = np.sign(uf)
        arg = 0.5 * math.pi * uf * uf
        c[far] = sign * 0.5 + np.sin(arg) / (math.pi * uf)
        s[far] = sign * 0.5 - np.cos(arg) / (math.pi * uf)
    return c, s


def slit(u1: np.ndarray, u2: np.ndarray) -> np.ndarray:
    """Complex field through a slit from u1 to u2, relative to the open wave."""

    c1, s1 = fresnel(np.minimum(u1, u2))
    c2, s2 = fresnel(np.maximum(u1, u2))
    return ((c2 - c1) + 1j * (s2 - s1)) / (1.0 + 1j)


def island_transmission(passes: dict[str, tuple], islands: list[Island],
                        period_s: float) -> tuple[np.ndarray, np.ndarray]:
    """Energy factor per ray from diffraction by the islands, and the
    geometric-shadow factor for comparison.

    Babinet: an obstacle is the open wave minus the wave through a slit its
    shape. With several obstacles in (roughly) one plane, U = 1 − Σ U_slit.
    Each slit's edges are the island's charted extremes, placed transverse to
    the ray where the island is abeam, and scaled by the Fresnel variable
    u = x·sqrt(2/(λ·D)), D the path from there to the start point.
    """

    omega = 2.0 * math.pi / period_s
    field = None
    geo = None
    for island in islands:
        rec = passes.get(island.name)
        if rec is None:
            continue
        qx, qy, beta, dist, seen = rec
        if field is None:
            field = np.ones(qx.shape, complex)
            geo = np.ones(qx.shape)
        k = wavenumber(omega, np.array([island.depth if math.isfinite(island.depth) else 1e4]))[0]
        lam = 2.0 * math.pi / k
        ux, uy = np.cos(beta), np.sin(beta)
        xa = ux * (island.a[1] - qy) - uy * (island.a[0] - qx)
        xb = ux * (island.b[1] - qy) - uy * (island.b[0] - qx)
        scale = np.sqrt(2.0 / (lam * np.maximum(dist, 1.0)))
        u_slit = slit(xa * scale, xb * scale)
        field = field - np.where(seen, u_slit, 0.0)
        inside = seen & (np.minimum(xa, xb) <= 0.0) & (np.maximum(xa, xb) >= 0.0)
        geo = np.where(inside, 0.0, geo)
    if field is None:
        return None, None
    return np.abs(field) ** 2, geo


def shadow_factor(rec: tuple, side: tuple[int, int], w: float, island: Island,
                  period_s: float) -> float:
    """Babinet energy factor for a ray that lands on `island`, from the slit
    geometry of the clear rays either side of it (`side`, indices into
    `rec`, the island's `passes` record) interpolated a share `w` of the way
    from the first to the second: each edge's offset from the ray's line and
    the distance on to the break, as `island_transmission` takes them at the
    point where a ray has the island abeam."""

    qx, qy, beta, dist, _ = rec

    def geometry(j):
        ux, uy = math.cos(beta[j]), math.sin(beta[j])
        return (ux * (island.a[1] - qy[j]) - uy * (island.a[0] - qx[j]),
                ux * (island.b[1] - qy[j]) - uy * (island.b[0] - qx[j]), dist[j])

    one, two = geometry(side[0]), geometry(side[1])
    xa, xb, d = (p * (1.0 - w) + q * w for p, q in zip(one, two))
    k = wavenumber(2.0 * math.pi / period_s,
                   np.array([island.depth if math.isfinite(island.depth) else 1e4]))[0]
    scale = math.sqrt(2.0 / ((2.0 * math.pi / k) * max(d, 1.0)))
    return float(np.abs(1.0 - slit(np.array([xa * scale]), np.array([xb * scale])))[0] ** 2)


#: Past this Fresnel distance from an edge the straight-edge factor is left at
#: 1. The lit-side ripple decays only as 1/u and sums to nothing across a
#: spectrum; applying it to every ray in the table would add noise, not
#: physics.
EDGE_U_MAX = 4.0


def edge_u(offset_m, depth_m, dist_m, period_s: float) -> np.ndarray:
    """The Fresnel parameter of a straight edge: u = offset·sqrt(2/(λ·D)),
    λ at the depth beside the edge, D the path from there to the break."""

    omega = 2.0 * math.pi / period_s
    k = wavenumber(omega, np.maximum(np.asarray(depth_m, float), 1.0))
    lam = 2.0 * math.pi / k
    return np.asarray(offset_m, float) * np.sqrt(2.0 / (lam * np.maximum(dist_m, 1.0)))


def edge_fan(u: np.ndarray, off_deg: np.ndarray, lit: np.ndarray) -> list[tuple[float, float]]:
    """What arrives at a diffracting edge: the offshore headings of the clear
    rays that pass it inside the Fresnel transition zone, 0 < u <= EDGE_U_MAX
    (the edge factor's own limit, beyond which it is 1), each weighted by the
    share of that strip of u it stands for (half-way to its neighbours, the
    ends at 0 and EDGE_U_MAX), so a heading where rays bunch is not counted
    twice. (heading, weight) pairs, weights summing to 1; [] when no clear ray
    passes inside the zone.

    The field diffracted into a shadow is the incident field across the strip
    beside the edge (Fresnel-Kirchhoff), not along one ray: until 2026-11-21 a
    fill took the offshore heading of the single clear ray nearest it in start
    heading, and rays grazing Point Loma leave the shelf anywhere from 250° to
    350° half a degree apart, so the fill's heading wandered from frequency to
    frequency (BRIEFING §60)."""

    pick = np.flatnonzero(lit & np.isfinite(u) & (u > 0.0) & (u <= EDGE_U_MAX))
    if not pick.size:
        return []
    order = pick[np.argsort(u[pick], kind="stable")]
    us = u[order]
    edges = np.concatenate([[0.0], 0.5 * (us[1:] + us[:-1]), [EDGE_U_MAX]])
    w = np.diff(edges) / EDGE_U_MAX
    return [(float(off_deg[i]), float(wi)) for i, wi in zip(order, w)]


def fan_heading(fan: list[tuple[float, float]]) -> float:
    """The fan's weighted circular mean heading (for bookkeeping only: the
    energy is read across the whole fan)."""

    sx = sum(w * math.sin(math.radians(h)) for h, w in fan)
    cx = sum(w * math.cos(math.radians(h)) for h, w in fan)
    return math.degrees(math.atan2(sx, cx)) % 360.0


def edge_factor(offset_m: np.ndarray, depth_m: np.ndarray, dist_m: np.ndarray,
                period_s: float) -> np.ndarray:
    """Energy factor from diffraction by a straight edge (a headland tip).

    Babinet again: a half-plane is the open wave minus the wave through a
    slit from the edge to infinity. `offset_m` is signed: positive where the
    ray clears the edge by that much, negative where it runs that far into
    the land's shadow. At the edge itself the factor is exactly 1/4.
    u = offset·sqrt(2/(λ·D)), λ at the depth beside the edge, D the path from
    there to the break.
    """

    u = edge_u(offset_m, depth_m, dist_m, period_s)
    field = 1.0 - slit(u, np.full_like(u, 1e6))
    out = np.abs(field) ** 2
    return np.where(u > EDGE_U_MAX, 1.0, out)


# ------------------------------------------------------------------ rays

LAND, DEEP, EDGE, LONG = "land", "deep", "grid edge", "too long"


def compass_from(beta: np.ndarray) -> np.ndarray:
    """Look-back direction (maths radians, from +east) -> compass bearing FROM."""

    return (90.0 - np.degrees(beta)) % 360.0


def beta_from_compass(deg: np.ndarray) -> np.ndarray:
    return np.radians(90.0 - np.asarray(deg, float))


@dataclass
class Rays:
    off_from_deg: np.ndarray
    status: np.ndarray
    exit_x: np.ndarray
    exit_y: np.ndarray
    exit_depth: np.ndarray
    path_m: np.ndarray
    #: island name -> (x, y, beta, path, seen) where each ray has the island
    #: abeam; `seen` is False for rays that never get there (landed first).
    passes: dict | None = None
    #: edge name -> (closest distance, path there, depth there) per ray: how
    #: near each ray comes to a headland's charted edge vertices, for the
    #: straight-edge diffraction factor.
    edges: dict | None = None
    #: exp(−∫ friction_rate ds) along the traced path: the share of the energy
    #: flux bottom friction leaves. The straight deep-water leg adds nothing.
    friction: np.ndarray | None = None
    #: ∫ ds / cg along the traced path, in seconds: how long a wave group takes
    #: from the exit point to the start depth (`forecast.upstreamlag`). The
    #: tables do not store it.
    time_s: np.ndarray | None = None
    #: With `record`, each ray's path from the start point outward: a list of
    #: (x, y, elapsed seconds) per step, for the Swell card map's fill
    #: (`paths_table`). None otherwise; no gain or table reads it.
    paths: list | None = None
    #: With `steps`, each ray's wet steps, start point outward: (depth below
    #: MSL at the start of each step, step length), exactly the terms the
    #: `friction` integral sums, for the Madsen table (`madsen_losses`).
    steps: list | None = None
    #: With `step_xy`, each wet step's start position (UTM x, y), aligned
    #: with `steps` one for one: where a step is, for a seabed that varies
    #: along the path (`forecast.reefbound`, report only). None otherwise.
    step_xy: list | None = None


def trace(bathy: Bathymetry, x0: float, y0: float, near_from_deg: np.ndarray,
          period_s: float, islands: list[Island] | None = None,
          edges: dict[str, np.ndarray] | None = None, record: bool = False,
          steps: bool = False, step_xy: bool = False) -> Rays:
    """Trace every heading at one period, seaward, until deep water, land or edge.

    With `islands`, also records where each ray has each island abeam — the
    along-track point where the island's centre stops being ahead of it —
    extrapolating the straight deep-water leg for rays that exit first.
    """

    omega = 2.0 * math.pi / period_s
    l0 = G * period_s ** 2 / (2.0 * math.pi)
    h_deep = l0

    n = near_from_deg.size
    x = np.full(n, float(x0))
    y = np.full(n, float(y0))
    beta = beta_from_compass(near_from_deg)
    path = np.zeros(n)
    status = np.full(n, "", dtype=object)
    exit_depth = np.full(n, np.nan)
    active = np.ones(n, bool)
    islands = islands or []
    abeam = {i.name: [np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan),
                      np.full(n, np.nan), np.zeros(n, bool)] for i in islands}
    edges = edges or {}
    near_edge = {name: [np.full(n, np.inf), np.zeros(n), np.full(n, np.nan)] for name in edges}
    lost = np.zeros(n)
    # The recorded paths have a name of their own: the edge and island loops
    # below each keep their bookkeeping in a local `rec`, and while the paths
    # shared that name (2026-11-10 to -15) any call with edges appended to
    # those arrays and failed, so the full table build could not run.
    walked = [[(float(x0), float(y0), 0.0)] for _ in range(n)] if record else None
    stepped: list | None = [] if steps else None
    stepped_xy: list | None = [] if (steps and step_xy) else None
    elapsed = np.zeros(n)

    def ahead(island, xa, ya, ba):
        return np.cos(ba) * (island.centre[0] - xa) + np.sin(ba) * (island.centre[1] - ya)

    def rhs(xa, ya, ba):
        h, hx, hy, cell, covered = bathy.sample(xa, ya)
        c, _, dc_dh = speeds(omega, np.where(np.isfinite(h), h, 1.0))
        cx, cy = dc_dh * hx, dc_dh * hy
        dbeta = (cx * np.sin(ba) - cy * np.cos(ba)) / c
        return dbeta, h, cell, covered

    while active.any():
        idx = np.flatnonzero(active)
        xa, ya, ba = x[idx], y[idx], beta[idx]
        k1, h, cell, covered = rhs(xa, ya, ba)

        land = covered & (h <= H_LAND)
        deep = covered & (h >= h_deep)
        # A ray leaving the grid in water already past L0/2 is within ~0.2°
        # of its deep-water heading; call it deep. Shallower than that, the
        # grid ran out while depth was still bending it, and it is flagged.
        last = np.where(np.isfinite(exit_depth[idx]), exit_depth[idx], 0.0)
        edge = ~covered
        edge_deep = edge & (last >= 0.5 * l0)
        edge = edge & ~edge_deep
        deep = deep | edge_deep
        long_ = path[idx] >= MAX_PATH_M
        for mask, label in ((land, LAND), (deep, DEEP), (edge, EDGE), (long_, LONG)):
            hit = mask & (status[idx] == "")
            status[idx[hit]] = label
            exit_depth[idx[hit]] = np.where(covered[hit], h[hit], exit_depth[idx[hit]])
        for name, points in edges.items():
            rec = near_edge[name]
            d = np.min(np.hypot(xa[:, None] - points[None, :, 0],
                                ya[:, None] - points[None, :, 1]), axis=1)
            closer = covered & (d < rec[0][idx])
            j = idx[closer]
            rec[0][j], rec[1][j], rec[2][j] = d[closer], path[j], h[closer]
        done = status[idx] != ""
        active[idx[done]] = False
        seen = covered & ~done
        exit_depth[idx[seen]] = h[seen]
        go = ~done
        if not go.any():
            break
        idx, xa, ya, ba = idx[go], xa[go], ya[go], ba[go]
        k1, ds = k1[go], STEP_FRACTION * cell[go]
        wet = covered[go] & np.isfinite(h[go])
        if wet.any():
            lost[idx[wet]] += friction_rate(omega, h[go][wet]) * ds[wet]
            if stepped is not None:
                stepped.append((idx[wet], h[go][wet], ds[wet]))
            if stepped_xy is not None:
                stepped_xy.append((xa[wet], ya[wet]))
            _, cg_here, _ = speeds(omega, h[go][wet])
            elapsed[idx[wet]] += ds[wet] / cg_here

        # Midpoint (RK2) step along the look-back direction.
        xm = xa + 0.5 * ds * np.cos(ba)
        ym = ya + 0.5 * ds * np.sin(ba)
        bm = ba + 0.5 * ds * k1
        k2, _, _, cov2 = rhs(xm, ym, bm)
        k2 = np.where(cov2, k2, k1)
        x[idx] = xa + ds * np.cos(bm)
        y[idx] = ya + ds * np.sin(bm)
        beta[idx] = ba + ds * k2
        path[idx] += ds
        if walked is not None:
            for j, xj, yj, ej in zip(idx.tolist(), x[idx].tolist(), y[idx].tolist(), elapsed[idx].tolist()):
                walked[j].append((xj, yj, ej))
        for island in islands:
            rec = abeam[island.name]
            passed = (~rec[4][idx]) & (ahead(island, xa, ya, ba) > 0) & (ahead(island, x[idx], y[idx], beta[idx]) <= 0)
            if passed.any():
                j = idx[passed]
                rec[0][j], rec[1][j], rec[2][j], rec[3][j] = x[j], y[j], beta[j], path[j]
                rec[4][j] = True

    # Rays that left deep water with an island still ahead meet it on the
    # straight leg: extrapolate to where it is abeam.
    for island in islands:
        rec = abeam[island.name]
        straight = (~rec[4]) & (status != LAND)
        t = ahead(island, x, y, beta)
        go = straight & (t > 0)
        rec[0][go] = x[go] + t[go] * np.cos(beta[go])
        rec[1][go] = y[go] + t[go] * np.sin(beta[go])
        rec[2][go] = beta[go]
        rec[3][go] = path[go] + t[go]
        rec[4][go] = True
        # A ray that landed never reaches the island.
        rec[4][status == LAND] = False

    passes = {name: tuple(v) for name, v in abeam.items()} if islands else None
    per_ray = None
    if stepped is not None:
        per_ray = [(np.zeros(0), np.zeros(0)) for _ in range(n)]
        if stepped:
            who = np.concatenate([a for a, _, _ in stepped])
            hh = np.concatenate([b for _, b, _ in stepped])
            dd = np.concatenate([c for _, _, c in stepped])
            order = np.argsort(who, kind="stable")      # each ray's steps stay in step order
            who, hh, dd = who[order], hh[order], dd[order]
            cuts = np.searchsorted(who, np.arange(n + 1))
            per_ray = [(hh[cuts[j]:cuts[j + 1]], dd[cuts[j]:cuts[j + 1]]) for j in range(n)]
    per_xy = None
    if stepped_xy is not None:
        per_xy = [(np.zeros(0), np.zeros(0)) for _ in range(n)]
        if stepped_xy:
            sx = np.concatenate([a for a, _ in stepped_xy])[order]
            sy = np.concatenate([b for _, b in stepped_xy])[order]
            per_xy = [(sx[cuts[j]:cuts[j + 1]], sy[cuts[j]:cuts[j + 1]]) for j in range(n)]
    return Rays(compass_from(beta), status, x, y, exit_depth, path, passes,
                {name: tuple(v) for name, v in near_edge.items()} if edges else None,
                np.exp(-lost), elapsed, walked, per_ray, per_xy)


# ------------------------------------------------------------------ blockers

def straight_line_blocker(blockers: list[Blocker], lat: float, lon: float,
                          from_deg: float) -> str | None:
    """The first charted blocker the deep-water leg runs into, if any.

    From the ray's exit point the path is straight; a heading inside the
    angular extent of a blocker's charted points, seen from there, is shadowed.
    Every blocker is tested, including Point Loma, because a ray can leave the
    grid heading back past the headland's northern shore.
    """

    for blocker in blockers:
        if blocker.name.startswith(ISLAND_PREFIX):
            continue             # diffracted, never a hard block (above)
        points = [blocker.a, blocker.b, *blocker.outline]
        bearings = [initial_bearing((lat, lon), p) for p in points]
        ref = bearings[0]
        rel = [((b - ref + 180.0) % 360.0) - 180.0 for b in bearings]
        lo, hi = min(rel), max(rel)
        off = ((from_deg - ref + 180.0) % 360.0) - 180.0
        if lo <= off <= hi and hi - lo < 180.0:
            return blocker.name
    return None


def leg_land(bathy: Bathymetry, islands: list[Island], x: np.ndarray, y: np.ndarray,
             from_deg: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Whether each straight deep-water leg, walked back from its exit `(x, y)`
    toward `from_deg` over the grids, meets land before they end, and where.

    Land inside an island's reach (`ISLAND_PAD_M`) is the island's and is
    passed over: the islands are diffracted on the straight leg, never
    blocked. Walked at half the cell under each point, the tracer's own step.
    """

    th = np.radians(from_deg)
    ux, uy = np.sin(th), np.cos(th)
    run = np.zeros(x.size)
    hit = np.zeros(x.size, bool)
    hx, hy = np.full(x.size, np.nan), np.full(x.size, np.nan)
    active = np.ones(x.size, bool)
    while active.any():
        idx = np.flatnonzero(active)
        px, py = x[idx] + ux[idx] * run[idx], y[idx] + uy[idx] * run[idx]
        h, _, _, cell, covered = bathy.sample(px, py)
        land = covered & np.isfinite(h) & (h <= H_LAND)
        for island in islands:
            land &= np.hypot(px - island.centre[0], py - island.centre[1]) > island.radius
        hit[idx[land]] = True
        hx[idx[land]], hy[idx[land]] = px[land], py[land]
        stop = land | ~covered | (run[idx] > MAX_PATH_M)
        active[idx[stop]] = False
        go = ~stop
        run[idx[go]] += STEP_FRACTION * cell[go]
    return hit, hx, hy


def leg_blockers(bathy: Bathymetry, blockers: list[Blocker], islands: list[Island],
                 rays: "Rays") -> list[str]:
    """What stops each ray, "" for none: the charted land it landed on
    (`landed_on`), or the land its straight deep-water leg runs into.

    The leg is tested twice. Against the charted blockers' angular spans
    (`straight_line_blocker`), which reach past the grids; and walked over
    the grids themselves (`leg_land`), the land the rays stop on. Until
    2026-11-15 only the first: a blocker that `continues` is land past its
    end too, and the Coronado shore south of the breaks is no blocker at
    all, so a short-period ray leaving deep water near the beach, heading
    back across the Silver Strand, the Mexican coast north of the Baja
    tangent or Point Loma north of its tip, counted as clear (BRIEFING §54,
    §55; 1,300-2,100 rows a break, all but one of them 3.4 s and under).
    """

    out = [""] * rays.status.size
    wet = np.flatnonzero(rays.status != LAND)
    hit, hx, hy = leg_land(bathy, islands, rays.exit_x[wet], rays.exit_y[wet],
                           rays.off_from_deg[wet])
    walked = dict(zip(wet.tolist(), zip(hit, hx, hy)))
    for i in range(rays.status.size):
        if rays.status[i] == LAND:
            out[i] = landed_on(blockers, rays.exit_x[i], rays.exit_y[i])
            continue
        lat, lon = from_utm(rays.exit_x[i], rays.exit_y[i])
        out[i] = straight_line_blocker(blockers, lat, lon, float(rays.off_from_deg[i])) or ""
        met, mx, my = walked[i]
        if not out[i] and met:
            out[i] = landed_on(blockers, mx, my)
    return out


# ------------------------------------------------------------------ starts

def start_point(bathy: Bathymetry, spot: Spot, h_ref: float = H_REF) -> tuple[float, float, float]:
    """(x, y, depth) where the break's seaward normal first reaches h_ref."""

    x0, y0 = to_utm(*spot.position)
    beta = float(beta_from_compass(np.array([spot.normal]))[0])
    step = 2.0
    for i in range(1, 5000):
        x = np.array([x0 + i * step * math.cos(beta)])
        y = np.array([y0 + i * step * math.sin(beta)])
        h, *_ = bathy.sample(x, y)
        if np.isfinite(h[0]) and h[0] >= h_ref:
            return float(x[0]), float(y[0]), float(h[0])
    raise ValueError(f"{spot.id}: no {h_ref} m water within 10 km along the normal")


# ------------------------------------------------------------------ tables

FIELDS = ["period_s", "freq_hz", "near_from_deg", "near_width_deg",
          "off_from_deg", "gain", "diff_off_from_deg", "diff_gain",
          "friction", "diff_friction",
          "status", "blocker", "exit_depth_m", "path_km", "diff_fan"]

#: How a headland's diffracted fill reads the offshore sea: "fan" (since
#: 2026-11-21, BRIEFING §61) across the clear rays passing the edge inside the
#: Fresnel zone (`edge_fan`); "nearest" the single nearest clear ray's
#: heading, as before, kept as the control.
FILL_RULE = "fan"


def frequencies() -> list[float]:
    """NDBC's own bins for 46232, read off the archive so the tables match it."""

    spectra = load_spectra(ROOT / "data" / "spectra" / "46232", limit=1)
    return list(spectra[0].frequencies)


def landed_on(blockers: list[Blocker], x: float, y: float) -> str:
    """Which charted land a ray stopped on, by the nearest charted point within
    3 km; the Coronado shore and shoals otherwise."""

    lat, lon = from_utm(x, y)
    best, name = 3.0, "Coronado shore or shoal"
    from .swell import great_circle_km
    for blocker in blockers:
        for p in (blocker.a, blocker.b, *blocker.outline):
            d = great_circle_km((lat, lon), p)
            if d < best:
                best, name = d, blocker.name
    return name


#: Headlands whose EDGES diffract: Point Loma's tip (every west edge) and the
#: Baja tangent (every south edge). Named by prefix so the charted names in
#: spots.json stay the only spelling.
EDGE_BLOCKERS = ("Point Loma", "Baja")


def edge_points(blockers: list[Blocker]) -> dict[str, np.ndarray]:
    """UTM vertices a headland's shadow edge can sit on: the tangent vertex
    and, for Point Loma, the charted hull of its rounded tip."""

    out = {}
    for blocker in blockers:
        if blocker.name.startswith(EDGE_BLOCKERS):
            pts = [blocker.a, *blocker.outline]
            out[blocker.name] = np.array([to_utm(*p) for p in pts])
    return out


def madsen_freq(rays: Rays, path_of: np.ndarray, carries: np.ndarray, omega: float,
                h_ref: float = H_REF, k_n=MADSEN_K_N) -> dict:
    """One frequency's Madsen table: each carrying path's weights on this
    frequency's basis, which path each carrying row (by its place k among the
    frequency's rows) crosses the shelf on, the basis over the nodes (peak,
    tide, hs; C order), the components kept and the worst |Δloss| at any node
    after rounding."""

    rows = np.flatnonzero(carries)
    src = sorted({int(path_of[i]) for i in rows})
    if not src:
        return {"rank": 0, "basis": [], "paths": [], "rows": {}, "max_error": 0.0}
    k_src = k_n if np.isscalar(k_n) else [k_n[j] for j in src]   # per ray -> per path
    loss = madsen_losses([rays.steps[j] for j in src], omega, h_ref=h_ref, k_n=k_src)
    weights, basis, err = compress_losses(loss.reshape(len(src), -1))
    at_src = {j: n for n, j in enumerate(src)}
    out = {"rank": len(basis), "basis": basis, "max_error": err, "paths": weights,
           "rows": {str(int(i)): at_src[int(path_of[i])] for i in rows}}
    if not np.isscalar(k_n):
        # A located seabed (report only): each path's share of its wet length
        # rougher than what ships. Never in a shipped table.
        out["rough_share"] = [
            round(float(np.sum(d[np.asarray(k_src[n]) > MADSEN_K_N]) / np.sum(d)), 6)
            if np.sum(d) > 0 else 0.0
            for n, (_, d) in enumerate(rays.steps[j] for j in src)]
    return out


def table(bathy: Bathymetry, spot: Spot, blockers: list[Blocker],
          freqs: list[float], madsen_out: dict | None = None,
          h_ref: float = H_REF, dir_step: float = DIR_STEP_DEG,
          fill: str = FILL_RULE, madsen_k_n=MADSEN_K_N) -> tuple[list[dict], dict]:
    """One break's transfer table, with every window edge both hard and soft.

    For each ray, two answers:

    - `gain` at `off_from_deg`: HARD shadows. (c0·cg0)/(c·cg) at the start
      depth for a ray that reaches the offshore wave field over the real
      seabed — the islands' own shelves included — and 0 for one that lands or
      whose deep-water leg runs into Point Loma or Baja.
    - `diff_gain` at `diff_off_from_deg`: the same with every window edge
      DIFFRACTING. The Coronado Islands by the two-edge (Babinet) factor at
      the point each ray has them abeam; a ray that lands on an island takes
      the heading of the nearer clear ray either side of the island's shadow
      and the factor for the slit geometry interpolated across it
      (`shadow_factor`), small deep in the shadow.
      Point Loma's tip and the Baja tangent by the straight-edge factor: a ray
      clearing the edge gets its lit-side ripple, and a ray that lands on the
      headland gets the energy of the nearest ray that clears it, scaled by
      how far into the shadow it runs.

    Diffraction is computed on the BENT rays, not straight lines: the ray
    that grazes an edge is itself refracted between the edge and the beach,
    and that bent ray is where the shadow boundary sits as seen from the
    break. Hard minus window is the seabed; soft minus hard is diffraction.

    With `madsen_out`, the Madsen survival table is built from the same
    traces and put there by frequency (`madsen_freq`): every row that carries
    energy, along the path whose friction the row takes — its own, or the
    clear ray's a diffracted fill takes. Tracing with `steps` changes no
    arithmetic, so the rows are the table's own.

    `h_ref` is the start depth along the normal; what ships is H_REF.
    `forecast.mopdepth` starts at CDIP MOP's 10 m points with it, report
    only (BRIEFING §56b).

    `fill` is how a headland's shadow reads the sea (`FILL_RULE`): "fan",
    across the clear rays inside the edge's Fresnel zone, written to the
    row's `diff_fan` as heading:weight pairs with their mean heading in
    `diff_off_from_deg`; "nearest", the nearest clear ray's heading alone.
    Friction and the path stay the nearest clear ray's either way.

    `dir_step` is the spacing of the start headings; what ships is
    DIR_STEP_DEG. `forecast.wrapbudget` traces finer combs with it, report
    only (handoff 27b).

    `madsen_k_n` is the roughness the Madsen table is built at; what ships is
    MADSEN_K_N. `forecast.reefbound` builds rougher ones, report only
    (handoff 27d); the rows do not depend on it. It may also be a function
    of UTM positions, (x, y) arrays -> roughness array, giving each wet step
    the roughness where it starts (a located seabed).
    """

    if fill not in ("fan", "nearest"):
        raise ValueError(f"fill is 'fan' or 'nearest', not {fill!r}")
    islands = islands_from(blockers)
    ring_depths(bathy, islands)
    edges = edge_points(blockers)
    xs, ys, hs = start_point(bathy, spot, h_ref)
    near = (spot.normal - 90.0 + dir_step / 2.0
            + dir_step * np.arange(int(round(180.0 / dir_step)))) % 360.0
    rows = []
    for f in freqs:
        period = 1.0 / f
        omega = 2.0 * math.pi * f
        located = callable(madsen_k_n)
        rays = trace(bathy, xs, ys, near, period, islands, edges, steps=madsen_out is not None,
                     step_xy=located and madsen_out is not None)
        c_n, cg_n, _ = speeds(omega, np.array([hs]))
        c0 = G / omega
        gain = (c0 * 0.5 * c0) / float(c_n[0] * cg_n[0])

        who = leg_blockers(bathy, blockers, islands, rays)
        clear = np.array([not w for w in who]) & (rays.status != LAND)

        # Diffraction, ray by ray.
        diff_off = rays.off_from_deg.copy()
        diff_t = np.zeros(near.size)
        diff_fric = rays.friction.copy()
        # Whose path each row's energy crosses the shelf on: the ray whose
        # friction it takes (its own, or a diffracted fill's nearest clear ray).
        path_of = np.arange(near.size)
        isl, _ = island_transmission(rays.passes or {}, islands, period)
        isl = np.ones(near.size) if isl is None else isl
        edge_t = np.ones(near.size)
        for name, (dist, along, depth) in (rays.edges or {}).items():
            lit = clear & np.isfinite(depth)
            if lit.any():
                edge_t[lit] *= edge_factor(dist[lit], depth[lit], along[lit], period)
        diff_t[clear] = (isl * edge_t)[clear]

        # A ray that lands on an island: the island is land and its shadow is
        # diffraction only, as at Point Loma and Baja (owner's decision,
        # 2026-11-15, BRIEFING §55). Until then it was re-traced over a
        # "see-through" disc, a seabed made up where the island stands, and
        # its heading through that disc jumped by tens of degrees when the
        # disc moved 50 m. Now it takes the heading and friction of the
        # nearer of the clear rays either side that have the island abeam,
        # and the Babinet factor for the slit geometry interpolated between
        # theirs, so nothing is read off where or how it lands.
        by_name = {island.name: island for island in islands}
        abeam = np.arange(near.size)
        for i in np.flatnonzero(np.array([w.startswith(ISLAND_PREFIX) for w in who])
                                & (rays.status == LAND)):
            island = by_name.get(who[i])
            rec = (rays.passes or {}).get(who[i])
            if island is None or rec is None:
                continue
            seen = clear & rec[4]
            lo, hi = np.flatnonzero(seen & (abeam < i)), np.flatnonzero(seen & (abeam > i))
            if not lo.size or not hi.size:
                continue                 # no clear ray past the island on one side: nothing
            side = (lo[-1], hi[0])
            w = (i - side[0]) / (side[1] - side[0])
            got = shadow_factor(rec, side, w, island, period)
            nearest = side[0] if w <= 0.5 else side[1]
            diff_off[i] = rays.off_from_deg[nearest]
            diff_fric[i] = rays.friction[nearest]
            path_of[i] = nearest
            diff_t[i] = got * edge_t[nearest]

        clear_idx = np.flatnonzero(clear)
        fans: dict[str, list] = {}
        diff_fan = [""] * near.size
        for i in np.flatnonzero(rays.status == LAND):
            name = who[i]
            if not name.startswith(EDGE_BLOCKERS) or not clear_idx.size or rays.edges is None:
                continue
            dist, along, depth = rays.edges[name]
            if not np.isfinite(depth[i]):
                continue
            nearest = clear_idx[np.argmin(np.abs(((near[clear_idx] - near[i] + 180.0) % 360.0) - 180.0))]
            diff_off[i] = rays.off_from_deg[nearest]
            if fill == "fan":
                if name not in fans:
                    fans[name] = edge_fan(edge_u(dist, depth, along, period),
                                          rays.off_from_deg, clear)
                if fans[name]:
                    diff_off[i] = fan_heading(fans[name])
                    diff_fan[i] = ";".join(f"{h:.2f}:{w:.5f}" for h, w in fans[name])
            # The energy that bends round the edge crosses the shelf beside the
            # ray that clears it, and takes that ray's friction.
            diff_fric[i] = rays.friction[nearest]
            path_of[i] = nearest
            diff_t[i] = float(edge_factor(np.array([-dist[i]]), np.array([depth[i]]),
                                          np.array([along[i]]), period)[0]) * isl[nearest]

        if madsen_out is not None:
            k_here = ([madsen_k_n(x, y) for x, y in rays.step_xy] if located else madsen_k_n)
            madsen_out[f"{f:.4f}"] = madsen_freq(rays, path_of, diff_t > 0, omega, h_ref=h_ref,
                                                    k_n=k_here)
        for i, theta in enumerate(near):
            rows.append({
                "period_s": f"{period:.3f}", "freq_hz": f"{f:.4f}",
                "near_from_deg": f"{theta:.2f}" if dir_step == DIR_STEP_DEG else f"{theta:.4f}",
                "near_width_deg": f"{dir_step:g}",
                "off_from_deg": f"{rays.off_from_deg[i]:.2f}",
                "gain": f"{gain:.5f}" if clear[i] else "0",
                "diff_off_from_deg": f"{diff_off[i]:.2f}",
                "diff_gain": f"{gain * diff_t[i]:.5f}" if diff_t[i] > 0 else "0",
                "friction": f"{rays.friction[i]:.5f}",
                "diff_friction": f"{diff_fric[i]:.5f}",
                "status": rays.status[i], "blocker": who[i],
                "exit_depth_m": f"{rays.exit_depth[i]:.1f}" if np.isfinite(rays.exit_depth[i]) else "",
                "path_km": f"{rays.path_m[i] / 1000.0:.2f}",
                "diff_fan": diff_fan[i] if diff_t[i] > 0 else "",
            })
    lat, lon = from_utm(xs, ys)
    meta = {"break": spot.id, "start_lat": round(lat, 6), "start_lon": round(lon, 6),
            "start_depth_m": round(hs, 2), "h_ref_m": h_ref, "dir_step_deg": dir_step,
            "depth_datum": "MSL" if bathy.msl_offset_m is not None else
            "NAVD88 (MSL offset not fetched; depths about a metre shallow)",
            "msl_above_navd88_m": bathy.msl_offset_m, "grids": list(bathy.names),
            "islands": [{"name": i.name, "ring_depth_m": round(i.depth, 1),
                         "radius_m": round(i.radius)} for i in islands],
            "diffracting_edges": sorted(edges),
            "bottom_friction": {"law": "JONSWAP", "c_bottom_m2_s3": C_BOTTOM},
            "edge_fill": fill}
    return rows, meta


FETCH_FIELDS = ["wind_from_deg", "fetch_km", "closed"]


def fetch_table(bathy: Bathymetry, spot: Spot, step_m: float = 20.0) -> list[dict]:
    """Open water upwind of the start point, per wind direction.

    Straight line from the start point toward where the wind comes FROM,
    until land (the fetch is closed: local sea is all the break gets from that
    wind) or the edge of the grids (open: the offshore wind sea the buoy sees
    arrives through the transfer table instead, and adding local growth on
    top would count it twice). Islands count as land here: wind waves do not
    diffract around them into existence.
    """

    xs, ys, _ = start_point(bathy, spot)
    rows = []
    for deg in range(360):
        beta = math.radians(90.0 - deg)
        closed = False
        dist = 0.0
        while dist < MAX_PATH_M:
            dist += step_m
            x = np.array([xs + dist * math.cos(beta)])
            y = np.array([ys + dist * math.sin(beta)])
            h, _, _, _, covered = bathy.sample(x, y)
            if not covered[0]:
                break
            if h[0] <= H_LAND:
                closed = True
                break
        rows.append({"wind_from_deg": deg, "fetch_km": f"{dist / 1000.0:.2f}",
                     "closed": "1" if closed else "0"})
    return rows


PROFILE_FIELDS = ["distance_m", "depth_m"]
#: Profile spacing. The nearshore grid is 8 m; 2 m keeps the bilinear
#: interpolation's own shape without adding anything the survey did not see.
PROFILE_STEP_M = 2.0
#: Where a profile stops: this far above MSL is dry at any tide the gauge has
#: recorded (MHHW is about 0.85 m above MSL at 9410170, and the present
#: anomaly adds ~0.3 m).
PROFILE_DRY_M = 2.5
#: Where the surf zone STARTS, per break: the depth below MSL its profile runs
#: seaward to from the table's start point (BRIEFING §58, 2026-11-18). The
#: tables still stop at H_REF; the surf zone takes the 5 m sea, carries it
#: back out linearly to here, and lets it break on the way in, so a sea already
#: breaking at 5 m finds its break point instead of a ceiling there.
#: Measured, not chosen: over 1,484 archived hours no hour has more than
#: 1.1e-4 of its waves breaking at these starts (Battjes-Janssen's Qb), a
#: 12 m start changes no breaking height by more than 0.04%, and the start
#: flags again only above about 6.6 m (Center) and 5.8 m (South) at 46232.
#: Center's and South's contours run within 1 degree of the chord normal over
#: the extension (526 m and 378 m out). North never breaks deeper than 3.5 m
#: in the archive and is converged by 7 m (66 m out); its 10 m water is 2.1 km
#: out on the flat shelf, outside Point Loma's shadow (the edge moves 26
#: degrees), the same reason the tables stop at 5 m (§29), so it stops at 7.
SURF_START_M = {"coronado_north": 7.0, "coronado_center": 10.0, "coronado_south": 10.0}
#: A seaward walk that finds no such water within this distance is an error,
#: never a shallower start (Center's 10 m is the furthest, 526 m out).
SURF_SEAWARD_MAX_M = 1000.0


def profile(bathy: Bathymetry, spot: Spot) -> list[dict]:
    """Depth below MSL along the break's normal, from `SURF_START_M` of water
    seaward of the table's start point to where the sand is `PROFILE_DRY_M`
    above MSL.

    What `forecast.surfzone` breaks the waves on. `distance_m` is measured
    from the table's start point, shoreward: the rows seaward of it (where the
    surf zone starts, BRIEFING §58) are negative, and the rows from 0 in are
    exactly the profile that started at the table's start point before (the
    `--profile-only` guard holds them to it). One line, straight in: the wave
    field is treated as alongshore-uniform, which is the assumption every 1-D
    surf-zone model makes. It is the 2016 CoNED survey's beach; sandbars move
    with the seasons and nothing here knows where they are now.
    """

    xs, ys, _ = start_point(bathy, spot)
    seaward = float(beta_from_compass(np.array([spot.normal]))[0])
    shoreward = seaward + math.pi
    target = SURF_START_M[spot.id]
    outside = []
    for i in range(1, int(SURF_SEAWARD_MAX_M / PROFILE_STEP_M) + 1):
        d = i * PROFILE_STEP_M
        h, *_, covered = bathy.sample(np.array([xs + d * math.cos(seaward)]),
                                      np.array([ys + d * math.sin(seaward)]))
        if not covered[0] or not np.isfinite(h[0]):
            raise ValueError(f"{spot.id}: the seabed ends {d:.0f} m seaward of the start point")
        outside.append({"distance_m": f"{-d:.1f}", "depth_m": f"{h[0]:.3f}"})
        if h[0] >= target:
            break
    else:
        raise ValueError(f"{spot.id}: no {target} m water within {SURF_SEAWARD_MAX_M:.0f} m "
                         f"seaward of the start point")
    rows = outside[::-1]
    for i in range(5000):
        d = i * PROFILE_STEP_M
        h, *_ , covered = bathy.sample(np.array([xs + d * math.cos(shoreward)]),
                                       np.array([ys + d * math.sin(shoreward)]))
        if not covered[0] or not np.isfinite(h[0]):
            break
        rows.append({"distance_m": f"{d:.1f}", "depth_m": f"{h[0]:.3f}"})
        if h[0] <= -PROFILE_DRY_M:
            break
    return rows


def write_profile(rows: list[dict], break_id: str, out_dir: Path = OUT_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{break_id}_profile.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=PROFILE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def committed_profile(break_id: str, out_dir: Path = OUT_DIR) -> list[dict]:
    with (out_dir / f"{break_id}_profile.csv").open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def inshore(rows: list[dict]) -> list[dict]:
    """A profile's rows from the table's start point in (distance ≥ 0)."""

    return [r for r in rows if float(r["distance_m"]) >= 0.0]


def write(rows: list[dict], meta: dict, out_dir: Path = OUT_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{meta['break']}.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    (out_dir / f"{meta['break']}.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return path


def madsen_meta() -> dict:
    """What a Madsen table's numbers mean; `nearshore.MadsenTable` reads it."""

    return {"law": "Madsen (Madsen, Poon & Graber 1988), as SWAN implements it",
            "k_n_m": MADSEN_K_N, "m_f": MADSEN_M_F,
            "quantity": "-ln(energy flux surviving bottom friction), deep water to the start depth",
            "nodes": "peak_hz x tide_m x hs_m, C order (hs fastest)",
            "hs_m": list(MADSEN_HS_M), "peak_hz": list(MADSEN_PEAK_HZ), "tide_m": list(MADSEN_TIDE_M),
            "hs": "the break's linear (frictionless) Hs at the start depth",
            "tide": "coast level on MSL; depths along the path are h + tide, no shallower than H_LAND",
            "loss_tol": MADSEN_LOSS_TOL, "loss_cap": MADSEN_LOSS_CAP,
            "rows": "row k (its place among its frequency's rows in <break>.csv) -> the path "
                    "it crosses the shelf on; a path's loss = sum of its weights times the "
                    "frequency's basis rows"}


def write_madsen(by_freq: dict, break_id: str, out_dir: Path = OUT_DIR) -> Path:
    """`<break>_madsen.json`: one line per frequency so a rebuild diffs by frequency."""

    meta = madsen_meta()
    meta["break"] = break_id
    meta["max_error"] = max((v["max_error"] for v in by_freq.values()), default=0.0)
    lines = ["{", f'"meta": {json.dumps(meta)},', '"freqs": {']
    keys = sorted(by_freq, key=float)
    for n, key in enumerate(keys):
        lines.append(f"{json.dumps(key)}: {json.dumps(by_freq[key], separators=(',', ':'))}"
                     + ("," if n < len(keys) - 1 else ""))
    lines += ["}", "}"]
    path = out_dir / f"{break_id}_madsen.json"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def committed_rows(break_id: str, out_dir: Path = OUT_DIR) -> list[dict]:
    with (out_dir / f"{break_id}.csv").open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


LEG_FIELDS = ["period_s", "freq_hz", "off_from_deg", "ray_min", "from_buoy_min"]

#: The swell band the leg is tabled over: 8 to 22 s. Shorter is local sea,
#: which no upstream buoy carries to the beach; longer has too little energy
#: in the archive to have been measured (`docs/upstream_lag.md`).
LEG_PERIODS_S = (8.0, 22.0)

#: The buoy the leg starts from. Its coordinate is fetched metadata
#: (`forecast.siting.load_coordinates`), never typed.
LEG_FROM = "46232"


def leg_table(bathy: Bathymetry, spot: Spot, blockers: list[Blocker],
              freqs: list[float], buoy: tuple[float, float]) -> list[dict]:
    """Minutes from `buoy` to the start depth, per unblocked ray and period.

    A wave group passing the buoy reaches a ray's deep-water exit after the
    plane-wave offset (exit − buoy)·û / cg0, û the direction it travels, then
    the start depth after ∫ ds / cg along the bent ray. Rays that land or whose
    straight leg runs into a blocker carry nothing to the break and are left
    out. Negative offsets are kept: an exit up-swell of the buoy is reached
    first.
    """

    bx, by = to_utm(*buoy)
    xs, ys, _ = start_point(bathy, spot)
    near = (spot.normal - 90.0 + DIR_STEP_DEG / 2.0
            + DIR_STEP_DEG * np.arange(int(round(180.0 / DIR_STEP_DEG)))) % 360.0
    islands = islands_from(blockers)
    rows = []
    for f in freqs:
        period = 1.0 / f
        if not LEG_PERIODS_S[0] <= period <= LEG_PERIODS_S[1]:
            continue
        rays = trace(bathy, xs, ys, near, period)
        cg0 = G * period / (4.0 * math.pi)
        who = leg_blockers(bathy, blockers, islands, rays)
        for i in range(near.size):
            if rays.status[i] == LAND or who[i]:
                continue
            heading = float(rays.off_from_deg[i])
            toward = math.radians(heading + 180.0)
            offset_s = ((rays.exit_x[i] - bx) * math.sin(toward)
                        + (rays.exit_y[i] - by) * math.cos(toward)) / cg0
            rows.append({
                "period_s": f"{period:.3f}", "freq_hz": f"{f:.4f}",
                "off_from_deg": f"{heading:.2f}",
                "ray_min": f"{rays.time_s[i] / 60.0:.1f}",
                "from_buoy_min": f"{(offset_s + rays.time_s[i]) / 60.0:.1f}",
            })
    return rows


def write_leg(rows: list[dict], break_id: str, buoy: tuple[float, float],
              out_dir: Path = OUT_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{break_id}_leg.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=LEG_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    (out_dir / f"{break_id}_leg.json").write_text(json.dumps(
        {"break": break_id, "from_station": LEG_FROM,
         "from_lat": buoy[0], "from_lon": buoy[1],
         "periods_s": list(LEG_PERIODS_S)}, indent=2) + "\n", encoding="utf-8")
    return path


def write_fetch(rows: list[dict], break_id: str, out_dir: Path = OUT_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{break_id}_fetch.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FETCH_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path



# ------------------------------------------------------------------ the map's ray paths

#: The swell band the map fill draws rays for, Hz: 4 to 33 s. NOT every train
#: a card lists: the buoy's own short-period sea is carried through the rays
#: like any swell and listed (2.6-3.8 s rows, 0.2-0.55 Hz), and a row's
#: energy above 0.25 Hz has no path to draw; `fill`'s `drawn_share` says how
#: much is. Local chop, grown beside the buoy's spectrum, has no rays at all.
PATH_BAND_HZ = (0.03, 0.25)
#: Paths are simplified to this, metres (Douglas-Peucker in UTM).
PATH_SIMPLIFY_M = 12.0
#: The surf zone's middle depth, for how long 5 m to the break takes (m).
SURF_MID_DEPTH_M = 2.5
#: A drawn ray's straight deep-water leg runs back from its exit only over
#: water at least this fraction of its deep-water wavelength deep: shallower,
#: the seabed would be bending it, and a straight line there is no longer
#: physics. L0/2, the same depth `trace` accepts as deep where a grid runs out
#: (`edge_deep`; c within ~0.4% of deep water there, each heading ~0.2°).
PATH_LEG_DEPTH = 0.5


def deep_leg(bathy: Bathymetry, x: np.ndarray, y: np.ndarray, from_deg: np.ndarray,
             period_s: float) -> np.ndarray:
    """How far (m) each ray's straight deep-water leg runs back from its exit
    `(x, y)` toward where it came from, `from_deg`, before the grids the rays
    are traced over end or the water under it shoals past `PATH_LEG_DEPTH`
    of L0, or meets land: as far out as the physics supports it (owner's
    request, 2026-11-15, BRIEFING §52). Walked at half the coarsest cell, the
    tracer's own step there, so a shoal no ray could cross is not stepped
    over."""

    l0 = G * period_s ** 2 / (2.0 * math.pi)
    step = STEP_FRACTION * max(g.cell for g in bathy.grids)
    th = np.radians(from_deg)
    ux, uy = np.sin(th), np.cos(th)
    run = np.zeros(x.size)
    active = np.ones(x.size, bool)
    while active.any():
        idx = np.flatnonzero(active)
        nxt = run[idx] + step
        h, _, _, _, covered = bathy.sample(x[idx] + ux[idx] * nxt, y[idx] + uy[idx] * nxt)
        ok = covered & np.isfinite(h) & (h > H_LAND) & (h >= PATH_LEG_DEPTH * l0) & (nxt <= MAX_PATH_M)
        run[idx[ok]] = nxt[ok]
        active[idx[~ok]] = False
    return run


def simplify(pts: np.ndarray, tol: float) -> np.ndarray:
    """Douglas-Peucker on (x, y, ...) rows, keeping both ends."""

    if len(pts) < 3:
        return pts
    keep = np.zeros(len(pts), bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        if b <= a + 1:
            continue
        p, q = pts[a, :2], pts[b, :2]
        d = q - p
        seg = float(np.hypot(*d)) or 1.0
        mid = pts[a + 1:b, :2]
        dist = np.abs(d[0] * (mid[:, 1] - p[1]) - d[1] * (mid[:, 0] - p[0])) / seg
        k = int(np.argmax(dist))
        if dist[k] > tol:
            m = a + 1 + k
            keep[m] = True
            stack += [(a, m), (m, b)]
    return pts[keep]


def paths_table(bathy: Bathymetry, spot: Spot, buoy: tuple[float, float],
                table_dir: Path = OUT_DIR) -> dict:
    """Where each of the break's table rays that clears every edge actually
    went, for the Swell card map's fill (owner's request, 2026-11-10).

    Every row of `<break>.csv` with a hard gain, per frequency bin in
    `PATH_BAND_HZ`, re-traced with `trace(record=True)` -- the same start,
    headings and step -- and checked against the table: each ray's offshore
    heading must equal its row's, or nothing is written. A path runs from as
    far out as the physics supports it (`deep_leg`: where the grids the rays
    are traced over end, or nearer where water shallower than L0/2 or land
    lies across its straight leg), straight to the ray's deep-water exit,
    along the traced path to the 5 m start, then along the break's normal to
    the break -- the surf zone's own line, at the shallow-water speed of its
    middle depth. Each point carries its minutes after the swell passed
    46232, the clock's 0, `leg_table`'s arithmetic: the plane-wave offset from
    the line through `buoy` square to the ray's heading, where the chain
    takes the buoy's spectrum to hold. No gain is computed here: the fill
    credits each ray from the table, as `nearshore.carry` does.

    Until 2026-11-15 a path started on that line, or at its exit where the
    exit lay up-swell of it, so 20 / 21 / 28% of rays (north / center /
    south) started past 46232 and the rest on its line -- south swell,
    periods of 25 s and more, and rays bending round Point Loma the former.
    Measured then (BRIEFING §52): most rays at 14 s and over at North, and
    from about 10 s at Center and South, are still turning by more than 0.1°
    where they leave the `outer` grid, so the traced physics
    ends at that grid's edge, and the straight leg back from each exit stays
    over water deeper than L0/2 to that edge for 89-95% of rays."""

    import csv as _csv

    by_freq: dict[str, list[dict]] = {}
    with (table_dir / f"{spot.id}.csv").open(newline="", encoding="utf-8") as fh:
        for row in _csv.DictReader(fh):
            by_freq.setdefault(row["freq_hz"], []).append(row)
    xs, ys, _ = start_point(bathy, spot)
    near = (spot.normal - 90.0 + DIR_STEP_DEG / 2.0
            + DIR_STEP_DEG * np.arange(int(round(180.0 / DIR_STEP_DEG)))) % 360.0
    bx, by = to_utm(*buoy)
    sx, sy = to_utm(*spot.position)
    run = math.hypot(sx - xs, sy - ys)
    out: dict[str, list] = {}
    for key, rows in sorted(by_freq.items(), key=lambda kv: float(kv[0])):
        f = float(key)
        if not PATH_BAND_HZ[0] <= f <= PATH_BAND_HZ[1]:
            continue
        if len(rows) != near.size:
            raise ValueError(f"{spot.id} {key} Hz: {len(rows)} table rows, {near.size} headings")
        period = 1.0 / f
        rays = trace(bathy, xs, ys, near, period, record=True)
        cg0 = G * period / (4.0 * math.pi)
        drawn = []
        keep = [k for k, row in enumerate(rows) if float(row["gain"]) > 0]
        leg = dict(zip(keep, deep_leg(bathy, rays.exit_x[keep], rays.exit_y[keep],
                                      rays.off_from_deg[keep], period))) if keep else {}
        for k, row in enumerate(rows):
            if float(row["gain"]) <= 0:
                continue
            off = float(rays.off_from_deg[k])
            if abs((off - float(row["off_from_deg"]) + 180.0) % 360.0 - 180.0) > 0.02:
                raise ValueError(f"{spot.id} {key} Hz ray {k}: traced {off:.2f}, table {row['off_from_deg']}")
            p = np.array(rays.paths[k])
            total = p[-1, 2]
            ex, ey = p[-1, 0], p[-1, 1]
            toward = math.radians(off + 180.0)
            offset_s = ((ex - bx) * math.sin(toward) + (ey - by) * math.cos(toward)) / cg0
            t_exit = offset_s / 60.0
            back = float(leg[k])
            pts = ([(ex - back * math.sin(toward), ey - back * math.cos(toward), t_exit - back / cg0 / 60.0)]
                   if back > 0 else [])
            for x, y, e in simplify(p[::-1].copy(), PATH_SIMPLIFY_M):
                pts.append((x, y, t_exit + (total - e) / 60.0))
            pts.append((sx, sy, pts[-1][2] + run / math.sqrt(G * SURF_MID_DEPTH_M) / 60.0))
            drawn.append([k, round(off, 2), [[round(la, 5), round(lo, 5), round(t, 2)]
                                             for la, lo, t in ((*from_utm(x, y), t) for x, y, t in pts)]])
        out[key] = drawn
    return {"break": spot.id, "from_station": LEG_FROM, "band_hz": list(PATH_BAND_HZ),
            "simplify_m": PATH_SIMPLIFY_M, "leg_depth_l0": PATH_LEG_DEPTH,
            "grids": list(bathy.names), "rays": out}


def write_paths(paths: dict, break_id: str, out_dir: Path = OUT_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{break_id}_paths.json"
    path.write_text(json.dumps(paths, separators=(",", ":")), encoding="utf-8")
    return path

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--break", dest="only", choices=BREAKS)
    parser.add_argument("--fetch-only", action="store_true",
                        help="rebuild the local-sea fetch tables and nothing else")
    parser.add_argument("--profile-only", action="store_true",
                        help="rebuild the surf-zone profiles and nothing else")
    parser.add_argument("--leg-only", action="store_true",
                        help=f"rebuild the {LEG_FROM}-to-break travel times and nothing else")
    parser.add_argument("--paths-only", action="store_true",
                        help="rebuild the map fill's ray paths and nothing else")
    parser.add_argument("--fill-only", action="store_true",
                        help="rebuild the tables for a new headland fill rule (FILL_RULE) and "
                             "nothing else; refuses unless every row but a headland fill's "
                             "heading and fan comes back as committed")
    parser.add_argument("--madsen-only", action="store_true",
                        help="rebuild the Madsen friction tables and nothing else; refuses "
                             "unless the re-trace gives the committed table back row for row")
    args = parser.parse_args(argv)

    bathy = Bathymetry.load()
    spots, blockers = load()
    by_id = {s.id: s for s in spots}
    freqs = frequencies()
    for sid in BREAKS:
        if args.only and sid != args.only:
            continue
        if args.paths_only:
            from .siting import load_coordinates
            buoy = load_coordinates()[LEG_FROM]
            out = write_paths(paths_table(bathy, by_id[sid], buoy), sid)
            print(f"{sid}: paths -> {out} ({out.stat().st_size / 1e3:.0f} KB)")
            continue
        if args.leg_only:
            from .siting import load_coordinates
            buoy = load_coordinates()[LEG_FROM]
            leg = write_leg(leg_table(bathy, by_id[sid], blockers, freqs, buoy), sid, buoy)
            print(f"{sid}: leg -> {leg}")
            continue
        if args.fill_only:
            # A fill's friction and path stay its nearest clear ray's, so the
            # Madsen tables do not move; only the fill rows' headings do.
            rows, meta = table(bathy, by_id[sid], blockers, freqs)
            old = committed_rows(sid)
            keep = [k for k in FIELDS if k not in ("diff_off_from_deg", "diff_fan")]
            bad = sum(1 for a, b in zip(rows, old)
                      if any(str(a[k]) != b.get(k) for k in keep)
                      or (not a["diff_fan"] and str(a["diff_off_from_deg"]) != b["diff_off_from_deg"]))
            if len(rows) != len(old) or bad:
                print(f"{sid}: {bad} rows differ beyond a headland fill's heading "
                      f"({len(rows)} vs {len(old)}): rebuild the table", file=sys.stderr)
                return 1
            path = write(rows, meta)
            fans = sum(1 for r in rows if r["diff_fan"])
            print(f"{sid}: fill -> {path} ({fans} headland fill rows read across a fan)")
            continue
        if args.madsen_only:
            madsen: dict = {}
            rows, _ = table(bathy, by_id[sid], blockers, freqs, madsen_out=madsen)
            old = committed_rows(sid)
            bad = sum(1 for a, b in zip(rows, old) if {k: str(v) for k, v in a.items()} != b)
            if len(rows) != len(old) or bad:
                print(f"{sid}: the re-trace does not give the committed table back "
                      f"({bad} rows differ, {len(rows)} vs {len(old)}): rebuild the table, "
                      f"not only its Madsen friction", file=sys.stderr)
                return 1
            out = write_madsen(madsen, sid)
            ranks = [v["rank"] for v in madsen.values()]
            print(f"{sid}: madsen -> {out} ({out.stat().st_size / 1e3:.0f} KB; components "
                  f"{min(ranks)}-{max(ranks)}; worst |Δloss| "
                  f"{max(v['max_error'] for v in madsen.values()):.4f})")
            continue
        rows = profile(bathy, by_id[sid])
        if args.profile_only:
            # Moving where the surf zone starts must not move anything from the
            # table's start point in: those rows are what every breaking height
            # before BRIEFING §58 was computed on.
            old = inshore(committed_profile(sid))
            if inshore(rows) != old:
                print(f"{sid}: the profile from the start point in does not come back as "
                      f"committed ({len(inshore(rows))} vs {len(old)} rows): the seabed or the "
                      f"start point changed, so rebuild the tables, not only the profile",
                      file=sys.stderr)
                return 1
        prof = write_profile(rows, sid)
        print(f"{sid}: profile -> {prof} ({len(rows) - len(inshore(rows))} rows seaward of "
              f"the start point, to {rows[0]['depth_m']} m)")
        if args.profile_only:
            continue
        fetch = write_fetch(fetch_table(bathy, by_id[sid]), sid)
        print(f"{sid}: fetch -> {fetch}")
        if args.fetch_only:
            continue
        madsen = {}
        rows, meta = table(bathy, by_id[sid], blockers, freqs, madsen_out=madsen)
        path = write(rows, meta)
        write_madsen(madsen, sid)
        kept = sum(1 for r in rows if r["gain"] != "0")
        print(f"{sid}: start {meta['start_depth_m']} m at {meta['start_lat']}, {meta['start_lon']}; "
              f"{len(rows)} rays, {kept} reach deep water unblocked -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
