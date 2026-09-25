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
   the charted blockers in `spots.json` — the Coronado Islands and Baja lie
   south of the grid, so this is where they act. Or it stops on land (the
   heading receives nothing), or at the grid's edge — counted as deep if the
   water there is already past L0/2, and flagged `grid edge` with its depth
   otherwise.
4. Energy along a ray: for stationary linear refraction S(f, θ)·c·c_g is
   invariant (Longuet-Higgins 1957), so the spectral density arriving at the
   start point from heading θn is S_off(f, θ0)·(c0·cg0)/(c·cg), with θ0 the
   heading the ray left deep water on. Integrating that over θn is refraction
   AND shoaling together; `tests/test_raytrace.py` checks it against Snell's
   law and the textbook Ks²·Kr² on a planar beach.

WHAT IT IS NOT. No diffraction here (the islands' Fresnel correction is layered
on separately), no breaking, no bottom friction, no currents, no wind input.
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
#: off all three breaks. Linear and unbroken there while Hs stays under about
#: 3.5 m (a breaker index of ~0.7); above that the figure is an upper bound.
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
        depth = msl_above_navd88 - elevation_m
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
            grids.append(Grid.from_elevation(raw / 10.0, left, top, a, shift))
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


# ------------------------------------------------------------------ islands

#: The Coronado Islands are diffracted, not blocked. Measured (BRIEFING §10,
#: CLAUDE.md): Fresnel numbers 1.6 and 0.2 — the shadow fills in by the time
#: it reaches Coronado, and the geometric block the aperture applies is a
#: ceiling on their effect, not an estimate of it.
ISLAND_PREFIX = "Coronado Islands"
#: Island land is removed from the grid out to this far past the charted
#: extent, so rays pass through and the Fresnel factor alone decides.
ISLAND_PAD_M = 400.0
#: Depth sampled in this ring outside the disc sets the fill and the
#: wavelength the islands diffract at.
ISLAND_RING_M = 2000.0


@dataclass
class Island:
    name: str
    a: tuple[float, float]       # UTM, charted extreme vertices
    b: tuple[float, float]
    centre: tuple[float, float]
    radius: float
    depth: float = float("nan")  # ring depth, set by `transparent`


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


def transparent(bathy: "Bathymetry", islands: list[Island]) -> "Bathymetry":
    """A copy with each island's disc filled at the depth of the water around it.

    This removes the island's own shelf as well as its land, so rays neither
    stop on the island nor refract around its shoals; the Fresnel factor then
    carries the island's whole effect. That is the flat-bottom assumption the
    Fresnel solution itself makes, stated rather than hidden.
    """

    grids = []
    for grid in bathy.grids:
        depth = grid.depth.copy()
        rows, cols = depth.shape
        ys = grid.top - (np.arange(rows) + 0.5) * grid.cell
        xs = grid.left + (np.arange(cols) + 0.5) * grid.cell
        for island in islands:
            dx = xs[None, :] - island.centre[0]
            dy = ys[:, None] - island.centre[1]
            r = np.hypot(dx, dy)
            disc = r <= island.radius
            if not disc.any():
                continue
            ring = (r > island.radius) & (r <= island.radius + ISLAND_RING_M) & (depth > H_LAND)
            fill = float(np.nanmedian(depth[ring])) if ring.any() else float("nan")
            if not math.isfinite(fill):
                continue
            depth[disc] = fill
            island.depth = fill
        gy, gx = np.gradient(depth, grid.cell)
        grids.append(Grid(depth, gx, -gy, grid.left, grid.top, grid.cell))
    return Bathymetry(grids, bathy.msl_offset_m, bathy.names)


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


def trace(bathy: Bathymetry, x0: float, y0: float, near_from_deg: np.ndarray,
          period_s: float, islands: list[Island] | None = None) -> Rays:
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
        done = status[idx] != ""
        active[idx[done]] = False
        seen = covered & ~done
        exit_depth[idx[seen]] = h[seen]
        go = ~done
        if not go.any():
            break
        idx, xa, ya, ba = idx[go], xa[go], ya[go], ba[go]
        k1, ds = k1[go], STEP_FRACTION * cell[go]

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
    return Rays(compass_from(beta), status, x, y, exit_depth, path, passes)


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

FIELDS = ["period_s", "freq_hz", "near_from_deg", "near_width_deg", "off_from_deg",
          "gain", "island_factor", "island_geometric", "status", "blocker", "exit_depth_m", "path_km"]


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


def table(bathy: Bathymetry, spot: Spot, blockers: list[Blocker],
          freqs: list[float]) -> tuple[list[dict], dict]:
    """One break's transfer table.

    `gain` is (c0·cg0)/(c·cg) at the start depth for a ray that reaches the
    offshore wave field, 0 for one that lands or runs into Point Loma or Baja.
    `island_factor` multiplies it: the Fresnel-diffraction energy factor from
    the Coronado Islands (1 where they are far off the ray). `island_geometric`
    is what a hard shadow would have done instead (0 or 1), kept so the effect
    of diffraction can be measured rather than asserted.
    """

    islands = islands_from(blockers)
    see_through = transparent(bathy, islands)
    xs, ys, hs = start_point(bathy, spot)
    near = (spot.normal - 90.0 + DIR_STEP_DEG / 2.0
            + DIR_STEP_DEG * np.arange(int(round(180.0 / DIR_STEP_DEG)))) % 360.0
    rows = []
    for f in freqs:
        period = 1.0 / f
        omega = 2.0 * math.pi * f
        rays = trace(see_through, xs, ys, near, period, islands)
        factor, geometric = island_transmission(rays.passes or {}, islands, period)
        c_n, cg_n, _ = speeds(omega, np.array([hs]))
        c0 = G / omega
        gain = (c0 * 0.5 * c0) / float(c_n[0] * cg_n[0])
        for i, theta in enumerate(near):
            status = rays.status[i]
            if status == LAND:
                blocker = landed_on(blockers, rays.exit_x[i], rays.exit_y[i])
            else:
                lat, lon = from_utm(rays.exit_x[i], rays.exit_y[i])
                blocker = straight_line_blocker(blockers, lat, lon, float(rays.off_from_deg[i])) or ""
            open_ = status != LAND and not blocker
            rows.append({
                "period_s": f"{period:.3f}", "freq_hz": f"{f:.4f}",
                "near_from_deg": f"{theta:.2f}", "near_width_deg": f"{DIR_STEP_DEG:g}",
                "off_from_deg": f"{rays.off_from_deg[i]:.2f}",
                "gain": f"{gain:.5f}" if open_ else "0",
                "island_factor": f"{factor[i]:.4f}" if factor is not None else "1",
                "island_geometric": f"{geometric[i]:.0f}" if geometric is not None else "1",
                "status": status, "blocker": blocker,
                "exit_depth_m": f"{rays.exit_depth[i]:.1f}" if np.isfinite(rays.exit_depth[i]) else "",
                "path_km": f"{rays.path_m[i] / 1000.0:.2f}",
            })
    lat, lon = from_utm(xs, ys)
    meta = {"break": spot.id, "start_lat": round(lat, 6), "start_lon": round(lon, 6),
            "start_depth_m": round(hs, 2), "h_ref_m": H_REF, "dir_step_deg": DIR_STEP_DEG,
            "depth_datum": "MSL" if bathy.msl_offset_m is not None else
            "NAVD88 (MSL offset not fetched; depths about a metre shallow)",
            "msl_above_navd88_m": bathy.msl_offset_m, "grids": list(bathy.names),
            "islands": [{"name": i.name, "ring_depth_m": round(i.depth, 1),
                         "radius_m": round(i.radius)} for i in islands]}
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


def write(rows: list[dict], meta: dict, out_dir: Path = OUT_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{meta['break']}.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    (out_dir / f"{meta['break']}.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return path


def write_fetch(rows: list[dict], break_id: str, out_dir: Path = OUT_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{break_id}_fetch.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FETCH_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--break", dest="only", choices=BREAKS)
    parser.add_argument("--fetch-only", action="store_true",
                        help="rebuild the local-sea fetch tables and nothing else")
    args = parser.parse_args(argv)

    bathy = Bathymetry.load()
    spots, blockers = load()
    by_id = {s.id: s for s in spots}
    freqs = frequencies()
    for sid in BREAKS:
        if args.only and sid != args.only:
            continue
        fetch = write_fetch(fetch_table(bathy, by_id[sid]), sid)
        print(f"{sid}: fetch -> {fetch}")
        if args.fetch_only:
            continue
        rows, meta = table(bathy, by_id[sid], blockers, freqs)
        path = write(rows, meta)
        kept = sum(1 for r in rows if r["gain"] != "0")
        print(f"{sid}: start {meta['start_depth_m']} m at {meta['start_lat']}, {meta['start_lon']}; "
              f"{len(rows)} rays, {kept} reach deep water unblocked -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
