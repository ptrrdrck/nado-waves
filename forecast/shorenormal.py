"""Shore normals fitted to a surveyed shoreline, against the digitised chords.

    python -m forecast.shorenormal

Reads `data/shoreline/noaa_shoreline_coronado.csv` (written by
`collector.shoreline`, which must run on Actions) and, for each Coronado break,
fits the shoreline vertices near it and reports the normal that falls out —
beside the normal the hand-traced chord in `forecast/spots.json` currently
claims.

**It reports; it does not edit `spots.json`.** Changing a coordinate is a
decision with a provenance record attached, and this file's job is to put the
number in front of the person making it.

THE NORMAL IS NOT A PROPERTY OF A POINT. It is a property of a chord, and the
answer moves with the chord's length. Measured on the existing digitised
coordinates alone, before any survey data: 102.8 degrees of coast trend over
north's own 547 m chord, 124.2 over centre's 285 m, 131.5 over south's 471 m,
121.3 over the whole 2.8 km beach. That is a 28.7-degree spread at one beach,
all of it real, none of it error.

So the output is a SWEEP over scales, not a single number. A break whose normal
is stable across 200 m to 2 km sits on a straight stretch and the number can be
trusted. One that swings is on a curve, and no single normal is right for it —
which is a finding about the beach, not a failure of the fit, and `residual_m`
is what says which case you are in.

WHY TOTAL LEAST SQUARES. The fit is the principal axis of the vertex cloud, not
an ordinary y-on-x regression. Ordinary least squares minimises error in one
axis only, so its answer depends on which way the coast happens to run relative
to north — it degenerates completely for a north-south beach. The principal
axis has no preferred direction. `forecast/stats.py:least_squares` is the
ordinary kind and is deliberately not used here.

WHAT THIS VERIFIES. Orientation, for the wind reading. NOAA's shoreline is
referenced to a tidal datum and a traced waterline is not, so the two sit at
different cross-shore positions; `offset_m` reports that separation rather than
hiding it, and it is not an error term. It does not verify the normal that
refraction wants, which belongs to the depth contours at breaking depth.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR

from .geometry import Spot, load

#: Chord lengths to fit at, metres. Spans a single peak to the whole beach.
SCALES_M = (200.0, 400.0, 800.0, 1500.0, 3000.0)

#: The scale the app surface's wind reading should use. A few hundred metres is
#: the stretch a person standing at one peak is actually on; the kilometre-scale
#: fits are here to show whether the beach is straight, not to be published.
REPORT_SCALE_M = 400.0

#: Fewer than this and a "fit" is two points with extra steps.
MIN_VERTICES = 4

EARTH_R = 6371000.0

BREAKS = ("coronado_north", "coronado_center", "coronado_south")

#: Every source chart band the collector stored, finest first. Reading ONE
#: fixed file is how §21 came to fit normals to the approach chart without
#: noticing a finer one existed.
STORE_DIR = "shoreline"

#: Finer first, so the headline is the best available and the rest are the
#: cross-check. Matches `collector.shoreline.SCALE_RANK`.
BAND_ORDER = ("enc_berthing", "enc_harbour", "enc_approach",
              "enc_coastal", "enc_general", "enc_overview")


def band_of(name: str) -> int:
    for index, band in enumerate(BAND_ORDER):
        if band in name:
            return index
    return len(BAND_ORDER)


@dataclass
class Fit:
    scale_m: float
    normal_deg: float | None = None
    vertices: int = 0
    #: RMS distance of the vertices from the fitted line. How straight the
    #: beach is at this scale, in metres.
    residual_m: float | None = None
    #: Signed distance from the chord's midpoint to the fitted line, along the
    #: chord normal. Datum difference, not error.
    offset_m: float | None = None
    note: str = ""


@dataclass
class BreakReport:
    id: str
    chord_normal_deg: float
    shoreline_verified: bool
    fits: list[Fit] = field(default_factory=list)

    def at(self, scale_m: float) -> Fit | None:
        for fit in self.fits:
            if fit.scale_m == scale_m and fit.normal_deg is not None:
                return fit
        return None

    @property
    def headline(self) -> Fit | None:
        return self.at(REPORT_SCALE_M)

    @property
    def disagreement_deg(self) -> float | None:
        """How far the chord's normal sits from the survey's, signed, ±180."""

        fit = self.headline
        if fit is None:
            return None
        return ((fit.normal_deg - self.chord_normal_deg + 180.0) % 360.0) - 180.0

    @property
    def spread_deg(self) -> float | None:
        """Widest disagreement between scales. Large means a curved beach."""

        got = [f.normal_deg for f in self.fits if f.normal_deg is not None]
        if len(got) < 2:
            return None
        base = got[0]
        rel = [((n - base + 180.0) % 360.0) - 180.0 for n in got]
        return max(rel) - min(rel)


def read_file(path: Path) -> list[tuple[float, float]]:
    """Vertices from one stored source, in file order."""

    out: list[tuple[float, float]] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                out.append((float(row["lat"]), float(row["lon"])))
            except (KeyError, TypeError, ValueError):
                continue
    return out


def read_sources(data_dir: Path) -> dict[str, list[tuple[float, float]]]:
    """Every stored source, finest chart band first. Empty when not collected.

    A dict and not a list, because the whole point is telling the sources
    apart: two charts of the same coast at two scales disagree, and that
    disagreement is the only cross-check available here.
    """

    folder = Path(data_dir) / STORE_DIR
    if not folder.exists():
        return {}
    found = sorted(folder.glob("*.csv"), key=lambda p: (band_of(p.name), p.name))
    return {p.stem: read_file(p) for p in found if p.is_file()}


def read_vertices(data_dir: Path) -> list[tuple[float, float]]:
    """The finest available source. Kept for callers wanting just one."""

    sources = read_sources(data_dir)
    return next(iter(sources.values()), [])


def to_local(points: list[tuple[float, float]], origin: tuple[float, float]):
    """Equirectangular metres about `origin`. Exact enough over a few km."""

    lat0 = math.radians(origin[0])
    cos0 = math.cos(lat0)
    return [
        ((lon - origin[1]) * math.radians(1.0) * EARTH_R * cos0,
         (lat - origin[0]) * math.radians(1.0) * EARTH_R)
        for lat, lon in points
    ]


def principal_axis(xy: list[tuple[float, float]]) -> tuple[float, float] | None:
    """Unit vector along the cloud's long axis, or None if it has no shape."""

    n = len(xy)
    if n < 2:
        return None
    mx = sum(p[0] for p in xy) / n
    my = sum(p[1] for p in xy) / n
    sxx = sum((p[0] - mx) ** 2 for p in xy)
    syy = sum((p[1] - my) ** 2 for p in xy)
    sxy = sum((p[0] - mx) * (p[1] - my) for p in xy)
    if sxx + syy <= 0:
        return None
    # Larger eigenvalue of the 2x2 covariance, in closed form.
    theta = 0.5 * math.atan2(2.0 * sxy, sxx - syy)
    return (math.cos(theta), math.sin(theta))


def fit_at(
    vertices: list[tuple[float, float]],
    spot: Spot,
    scale_m: float,
) -> Fit:
    """Fit the vertices within `scale_m`/2 of the break, and take the normal."""

    origin = spot.position
    near_ll = [
        p for p in vertices
        if abs((p[0] - origin[0]) * math.radians(1.0) * EARTH_R) <= scale_m
        and abs((p[1] - origin[1]) * math.radians(1.0) * EARTH_R
                * math.cos(math.radians(origin[0]))) <= scale_m
    ]
    xy = to_local(near_ll, origin)
    xy = [p for p in xy if math.hypot(*p) <= scale_m / 2.0]

    # Deduplicate. The ENC coastline repeats a vertex wherever two chart
    # segments meet — 166 of 689 in the Coronado extract — and a principal
    # axis weights a repeated point twice, so the fit would lean toward
    # whichever stretch happens to be stitched most often. Measured on that
    # extract, north's 400 m window holds 5 vertices at 3 distinct positions.
    seen, unique = set(), []
    for point in xy:
        key = (round(point[0], 2), round(point[1], 2))
        if key not in seen:
            seen.add(key)
            unique.append(point)
    xy = unique
    fit = Fit(scale_m=scale_m, vertices=len(xy))
    if len(xy) < MIN_VERTICES:
        fit.note = f"only {len(xy)} vertices within {scale_m/2:.0f} m"
        return fit

    axis = principal_axis(xy)
    if axis is None:
        fit.note = "vertices have no long axis"
        return fit

    # Compass bearing of the axis. atan2(east, north), not the maths convention.
    trend = math.degrees(math.atan2(axis[0], axis[1])) % 360.0
    # Two normals, 180 apart. Take the one on the same side as the chord's,
    # which is an explicit convention for the same reason Spot.normal is: an
    # implicit sign once pointed Coronado into San Diego Bay.
    for candidate in ((trend + 90.0) % 360.0, (trend - 90.0) % 360.0):
        if abs(((candidate - spot.normal + 180.0) % 360.0) - 180.0) <= 90.0:
            fit.normal_deg = candidate
            break
    if fit.normal_deg is None:
        fit.note = "fitted normal is more than 90 deg from the chord's; not resolved"
        return fit

    mx = sum(p[0] for p in xy) / len(xy)
    my = sum(p[1] for p in xy) / len(xy)
    # Perpendicular distance of each vertex from the fitted line.
    nx, ny = -axis[1], axis[0]
    fit.residual_m = math.sqrt(
        sum(((p[0] - mx) * nx + (p[1] - my) * ny) ** 2 for p in xy) / len(xy)
    )
    # The break sits at the local origin, so the line's offset from it is the
    # projection of the fitted centroid onto the normal.
    fit.offset_m = mx * nx + my * ny
    return fit


def report(data_dir: Path = DEFAULT_DATA_DIR, spots_path: Path | None = None,
           vertices: list | None = None) -> list[BreakReport]:
    spot_list, _ = load(spots_path) if spots_path else load()
    spots = {s.id: s for s in spot_list}
    if vertices is None:
        vertices = read_vertices(data_dir)

    out = []
    for break_id in BREAKS:
        spot = spots[break_id]
        entry = BreakReport(
            id=break_id,
            chord_normal_deg=spot.normal,
            shoreline_verified=spot.shoreline_verified,
        )
        for scale in SCALES_M:
            entry.fits.append(fit_at(vertices, spot, scale))
        out.append(entry)
    return out


def format_report(reports: list[BreakReport]) -> str:
    lines = ["### Shore normals — surveyed shoreline vs digitised chord", ""]
    if not any(r.headline for r in reports):
        lines.append(
            "No surveyed shoreline vertices near the breaks. Run "
            "`python -m collector.shoreline` on Actions first — every NOAA "
            "coastal host is denied at CONNECT from a session (BRIEFING §8). "
            "**Nothing is inferred from the absence**; the chords keep the "
            "`shoreline_verified` flags they already have."
        )
        return "\n".join(lines)

    lines += [
        f"At the {REPORT_SCALE_M:.0f} m scale — the stretch a person standing "
        f"at one peak is on.", "",
        "| break | chord | surveyed | disagreement | straightness | datum offset | verified |",
        "|---|---|---|---|---|---|---|",
    ]
    unfitted: list[tuple[str, str]] = []
    for r in reports:
        fit = r.headline
        if fit is None:
            # WHY there is no fit, not just that there is none. A dash on its
            # own cannot tell "no survey vertices here" from "vertices, but too
            # few to fit" from "fitted, and the normal came out more than 90
            # degrees from the chord's" — and those want three different
            # responses. A silent absence is the fault BRIEFING §8 and §13 both
            # turn on.
            why = next((f.note for f in r.fits
                        if f.scale_m == REPORT_SCALE_M and f.note), "no vertices near this break")
            lines.append(f"| {r.id} | {r.chord_normal_deg:.1f} | — | — | — | — | "
                         f"{'yes' if r.shoreline_verified else 'NO'} |")
            unfitted.append((r.id, why))
            continue
        lines.append(
            f"| {r.id} | {r.chord_normal_deg:.1f} | {fit.normal_deg:.1f} | "
            f"**{r.disagreement_deg:+.1f}** | {fit.residual_m:.1f} m rms | "
            f"{fit.offset_m:+.0f} m | {'yes' if r.shoreline_verified else 'NO'} |"
        )
    if unfitted:
        lines += ["", "**Not fitted, and why:**"]
        lines += [f"- `{name}` — {why}" for name, why in unfitted]
    lines += ["", "Scale sweep — a normal that moves with scale is a curved beach, "
                  "not a bad fit:", "",
              "| break | " + " | ".join(f"{s:.0f} m" for s in SCALES_M) + " | spread |",
              "|---" * (len(SCALES_M) + 2) + "|"]
    for r in reports:
        cells = []
        for scale in SCALES_M:
            fit = r.at(scale)
            cells.append(f"{fit.normal_deg:.1f}" if fit else "—")
        spread = r.spread_deg
        lines.append(f"| {r.id} | " + " | ".join(cells) + " | "
                     + (f"{spread:.1f}" if spread is not None else "—") + " |")
    lines += ["", "The datum offset is NOT an error: NOAA's shoreline is referenced "
                  "to a tidal datum and the traced waterline is not. Orientation is "
                  "what is being checked, and orientation survives a translation.", ""]
    lines.append(
        "This reports. It does not edit `forecast/spots.json` — changing a "
        "coordinate carries a provenance record and is a decision, not a "
        "derivation."
    )
    return "\n".join(lines)


def compare_sources(data_dir: Path = DEFAULT_DATA_DIR) -> str:
    """Every stored chart band, side by side, at the reporting scale.

    This exists because §21's conclusions rested on whichever source the
    collector reached first. Two charts of the same coast disagreeing is
    information; one chart alone is an assumption.
    """

    sources = read_sources(data_dir)
    if len(sources) < 2:
        return ""

    lines = ["", "### The same coast at more than one chart scale", "",
             "Finer bands first. A disagreement here is the cross-check §21 "
             "did not have — it fitted whichever source the collector reached "
             "first and could not know a finer one existed.", "",
             "| source | vertices | " + " | ".join(
                 b.split("_")[-1] for b in BREAKS) + " |",
             "|---" * (len(BREAKS) + 2) + "|"]
    for name, points in sources.items():
        cells = []
        for break_id in BREAKS:
            entry = next(r for r in report(data_dir, vertices=points)
                         if r.id == break_id)
            fit = entry.headline
            cells.append(f"{fit.normal_deg:.1f} ({fit.vertices}v)" if fit
                         else "—")
        lines.append(f"| `{name}` | {len(points)} | " + " | ".join(cells) + " |")
    lines += ["", "`(Nv)` is how many DISTINCT vertices the fit had at "
                  f"{REPORT_SCALE_M:.0f} m. A normal from three points is a "
                  "line through three points, not a shoreline."]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = parser.parse_args(argv)
    reports = report(args.data_dir)
    print(format_report(reports))
    comparison = compare_sources(args.data_dir)
    if comparison:
        print(comparison)
    return 0 if any(r.headline for r in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
