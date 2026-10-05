"""The measurements behind `forecast.origin`. Reports, never edits.

    python -m forecast.origin --report

Five questions, each with the test that could have killed the idea:

1. **Does reading the spectrum find more than the old method?** Both run over
   the span 46232's spectra are archived for; the old one on the real-time
   standard met, the only dominant period that exists for those months.
2. **Is a distance reproducible from another instrument?** Every buoy with an
   archived spectrum is run as if it were 46232, and its arrivals matched to
   46232's by birth time and lead period. Agreement is not truth -- the buoys
   share the storm and every bias of the method -- but disagreement would be
   the method failing on its own terms.
3. **When has a reading settled?** Each long arrival fitted on its first k
   hours against its full fit; this sets `SETTLED_HOURS`.
4. **Does "confirmed in transit" test the distance at all?** The old witness
   check, re-run on the three-year archive with every distance scaled by 0.7
   and 1.3 (the line pivoted on its own first hour, as a different slope
   through the same data would be) and with every bearing turned by 20°. If
   the hit rate does not move with distance, it never tested distance.
5. **What does test the distance?** A far upstream buoy fitting its OWN
   dispersion line: two independent distances along one path should differ by
   the buoys' separation.

Plus the bearing: how far 46232's own direction sits from the unshadowed
buoy's, for the arrivals both read.
"""

from __future__ import annotations

import statistics
from pathlib import Path

from .dispersion import dispersive_arrivals, origin_from_series
from .forensics import (
    _column,
    find_witnesses,
    investigate,
)
from .origin import (
    FIT_HOURS,
    MIN_FIT_R2,
    MIN_POINTS,
    arrivals,
    fit_ridge,
    load_archives,
    qualifies,
    ridge_bearing,
    ridges,
)
from .swell import POSITIONS, destination_point, great_circle_km

#: The old method's own run: the stations `forensics` was built on, and 46232.
TARGETS = ("46232", "46222", "46221", "46224", "46225", "46258")
WITNESSES = ("46001", "46005", "46006", "46059", "51101", "51002", "46219")
#: Far enough upstream that its own fit is a second, independent distance.
FAR = ("46001", "46005", "46006", "46059", "51101", "51002")
MIN_R2 = 0.75


def _pct(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return float("nan")
    k = (len(ordered) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def _hourly(path: Path):
    """The real-time file kept to one row an hour (it carries :26 and :56)."""

    from .stats import load_column

    out = {}
    for column in ("wvht", "dpd"):
        seen = {}
        for stamp, value in load_column(path, column).items():
            key = stamp.replace(minute=0, second=0)
            seen.setdefault(key, (stamp, value))
        out[column] = {stamp: value for stamp, value in seen.values()}
    return out


def counts(data_dir: Path, spectra) -> list[str]:
    start, end = spectra[0].time, spectra[-1].time
    new = [a for a in arrivals(spectra)]
    cols = _hourly(data_dir / "observations" / "46232.csv")
    heights, periods = cols["wvht"], cols["dpd"]
    stamps = sorted(t for t in set(heights) & set(periods) if start <= t <= end)
    old, index = 0, 0
    while index < len(stamps) - 36:
        group = stamps[index:index + 36]
        if (periods[group[0]] >= 13.0 and max(heights[t] for t in group) >= 0.8
                and origin_from_series(periods, group) is not None):
            old += 1
            index += 36
            continue
        index += 6
    whole = sorted({round(v, 2) for v in periods.values()})
    return [
        f"1. Arrivals at 46232, {start:%Y-%m-%d} to {end:%Y-%m-%d} ({len(spectra)} spectra)",
        f"   spectral ridges (forecast.origin): {len(new)}",
        f"   dominant period, real-time standard met (forensics' method): {old}",
        f"   the real-time dominant period takes {len(whole)} distinct values: "
        f"{', '.join(f'{v:g}' for v in whole[:12])}{' ...' if len(whole) > 12 else ''}",
    ]


def reproducibility(archives: dict[str, list]) -> list[str]:
    base = arrivals(archives["46232"])
    lines = ["2. The same arrival read independently at another buoy's spectrum "
             "(matched on birth within 24 h, lead period within 2 s)"]
    ratios: list[float] = []
    for station in ("46047", "46086", "46258"):
        spectra = archives.get(station) or []
        if not spectra:
            lines.append(f"   {station}: no spectra")
            continue
        other = arrivals(spectra)
        for a in base:
            best = None
            for b in other:
                born = abs((b.fit.generated_utc - a.fit.generated_utc).total_seconds()) / 3600.0
                if born <= 24.0 and abs(b.lead_period_s - a.lead_period_s) <= 2.0:
                    if best is None or born < best[0]:
                        best = (born, b)
            if best:
                b = best[1]
                ratios.append(b.fit.distance_km / a.fit.distance_km)
                lines.append(
                    f"   {a.first_utc:%m-%d %H}Z 46232 {a.fit.distance_km:6,.0f} km | "
                    f"{station} {b.fit.distance_km:6,.0f} km  (x{ratios[-1]:.2f}, "
                    f"born {best[0]:.0f} h apart)")
    if ratios:
        off = [abs(r - 1.0) for r in ratios]
        lines.append(f"   n = {len(ratios)}: |ratio - 1| median {statistics.median(off):.0%}, "
                     f"90th pct {_pct(off, 0.9):.0%}, worst {max(off):.0%}")
    return lines


def convergence(spectra) -> list[str]:
    lines = ["3. A reading on its first k hours against the full fit "
             f"(arrivals read for >= 36 h, fitted to {FIT_HOURS:.0f} h)"]
    long = []
    for ridge in ridges(spectra):
        fit = fit_ridge(ridge)
        if qualifies(ridge, fit) and fit.hours >= 36.0:
            long.append((ridge, fit))
    lines.append(f"   n = {len(long)}; counted only where the early fit would itself be "
                 f"shown (R² >= {MIN_FIT_R2}, >= {MIN_POINTS} hours read)")
    for k in (12, 18, 24, 30, 36):
        off, hidden = [], 0
        for ridge, full in long:
            early = fit_ridge(ridge, hours=k)
            if early is None or early.r_squared < MIN_FIT_R2 or early.points < MIN_POINTS:
                hidden += 1
                continue
            off.append(early.distance_km / full.distance_km - 1.0)
        shown = ", ".join(f"{v:+.0%}" for v in off)
        lines.append(f"   {k:2d} h: {len(off)} shown ({shown}), {hidden} not yet readable")
    return lines


def historical_convergence(data_dir: Path) -> list[str]:
    lines = ["   the same on the three-year historical dominant period (36 obs, all targets)"]
    per_k: dict[int, list[float]] = {k: [] for k in (6, 9, 12, 18, 24)}
    for station in TARGETS:
        periods = _column(data_dir, station, "dpd")
        heights = _column(data_dir, station, "wvht")
        stamps = sorted(set(periods) & set(heights))
        for arrival, full in dispersive_arrivals(data_dir, station):
            window = [t for t in stamps if t >= arrival][:36]
            for k in per_k:
                early = origin_from_series(periods, window[:k], min_r2=0.0)
                if early:
                    per_k[k].append(abs(early.distance_km / full.distance_km - 1.0))
    for k, off in per_k.items():
        if off:
            lines.append(f"   {k:2d} obs: median {statistics.median(off):.0%}, 90th pct "
                         f"{_pct(off, 0.9):.0%} (n = {len(off)})")
    return lines


def witness_control(data_dir: Path) -> list[str]:
    cases = []
    for station in TARGETS:
        for case in investigate(data_dir, station, WITNESSES):
            if case.r_squared >= MIN_R2:
                cases.append(case)
    lines = [f"4. The old witness check, {len(cases)} arrivals at "
             f"{', '.join(TARGETS)}, 2023-2025"]

    def rate(scale: float, turn: float, far_only: bool) -> tuple[int, int]:
        hits = total = 0
        for case in cases:
            position = POSITIONS[case.station]
            first = case.arrival_utc
            generated = first - (first - case.generated_utc) * scale
            origin = destination_point(position, (case.bearing_deg + turn) % 360.0,
                                       case.distance_km * scale)
            pool = FAR if far_only else WITNESSES
            for w in find_witnesses(data_dir, case.station, origin, generated,
                                    case.lead_period_s, pool):
                total += 1
                hits += w.confirms
        return hits, total

    for far_only in (False, True):
        label = "far buoys only" if far_only else "all witnesses"
        lines.append(f"   {label}:")
        for scale, turn, name in ((1.0, 0.0, "as fitted"), (0.7, 0.0, "distance x0.7"),
                                  (1.3, 0.0, "distance x1.3"), (1.0, 20.0, "bearing +20°"),
                                  (1.0, -20.0, "bearing -20°")):
            hits, total = rate(scale, turn, far_only)
            share = f"{hits / total:.0%}" if total else "-"
            lines.append(f"     {name:<15} {hits:3d} sightings of {total:3d} candidates ({share})")
    return lines, cases


def far_distance_test(data_dir: Path, cases) -> list[str]:
    lines = ["5. Two independent distances along one path: the target's own fit "
             "against a far upstream buoy's own fit"]
    rows = []
    found_arrivals = {s: dispersive_arrivals(data_dir, s) for s in FAR}
    for case in cases:
        for w in case.witnesses:
            if w.station not in FAR or not w.confirms:
                continue
            best = None
            for arrival, fit in found_arrivals[w.station]:
                gap = abs((arrival - w.seen_utc).total_seconds()) / 3600.0
                if gap <= 24.0 and (best is None or gap < best[0]):
                    best = (gap, fit)
            if not best:
                continue
            expected = case.distance_km - great_circle_km(case.origin, POSITIONS[w.station])
            measured = case.distance_km - best[1].distance_km
            rows.append((case, w.station, expected, measured, best[1].distance_km))
    # The far buoy's own distance against the one the target's origin implies
    # for it: two independent fits of one storm, seen 1,000-4,000 km apart.
    lines.append(f"   pairs: {len(rows)} (a confirmed far witness that also has a "
                 f"readable arrival of its own within 24 h)")
    for case, station, expected, measured, own in rows:
        lines.append(f"   {case.arrival_utc:%Y-%m-%d} {case.station} {case.distance_km:6,.0f} km | "
                     f"{station} {own:6,.0f} km: separation expected {expected:6,.0f}, "
                     f"measured {measured:6,.0f}")
    if len(rows) >= 3:
        errs = [abs(m - e) for _, _, e, m, _ in rows]
        lines.append(f"   |measured - expected| median {statistics.median(errs):,.0f} km "
                     f"against a median expected separation of "
                     f"{statistics.median(e for _, _, e, _, _ in rows):,.0f} km")
        implied = [own / (case.distance_km - e) - 1.0 for case, _, e, _, own in rows]
        lines.append(f"   far buoy's own distance against the one the target's origin implies: "
                     f"|ratio - 1| median {statistics.median(abs(v) for v in implied):.0%}, "
                     f"90th pct {_pct([abs(v) for v in implied], 0.9):.0%}, "
                     f"signed median {statistics.median(implied):+.0%}")
        xs = [e for _, _, e, _, _ in rows]
        ys = [m for _, _, _, m, _ in rows]
        if len(set(xs)) > 1 and len(set(ys)) > 1:
            lines.append(f"   correlation {statistics.correlation(xs, ys):+.2f}")
    return lines


def bearing_shadow(archives: dict[str, list]) -> list[str]:
    """46232's mean heading for each ridge against the bearing buoy's, and
    46232's westerly lobe beside it (BRIEFING §38): on a north-west swell the
    mean averages a westerly and a southerly lobe and lands between them, so
    roughly half the gap is the average and half the lobe. The lobe is read
    off the band 11-20 s at the ridge's first hour, by `forecast.nwbearing`."""

    from .nwbearing import band_distribution, westerly_lobe

    lines = ["6. Bearing: 46232's own direction against the bearing buoy (46047, else 46086) that has the ridge",
             "   (mean: the a1 average Origin would have used; lobe: 46232's westerly lobe, §38)"]
    diffs = []
    lobe_diffs = []
    for a in arrivals(archives["46232"], archives):
        own = ridge_bearing(a.ridge, archives, ("46232",))
        if not own or a.bearing_from == "46232" or a.bearing_deg is None:
            continue
        d = (own[0] - a.bearing_deg + 180.0) % 360.0 - 180.0
        diffs.append(d)
        first = next((s for s in archives["46232"] if s.time == a.ridge.points[0].time), None)
        lobe = None
        if first is not None:
            dist, _ = band_distribution(first.with_spread("mem"))
            lobe = westerly_lobe(dist) if dist else None
        text = ""
        if lobe is not None and a.bearing_deg >= 270.0:
            ld = (lobe - a.bearing_deg + 180.0) % 360.0 - 180.0
            lobe_diffs.append(ld)
            text = f" | lobe {lobe:4.0f}° ({ld:+.0f}°)"
        lines.append(f"   {a.first_utc:%m-%d %H}Z {a.bearing_from} {a.bearing_deg:5.0f}° | "
                     f"46232 mean {own[0]:5.0f}°  ({d:+.0f}°){text}")
    if diffs:
        lines.append(f"   n = {len(diffs)}: median {statistics.median(diffs):+.0f}°, "
                     f"largest {max(diffs, key=abs):+.0f}°")
    if lobe_diffs:
        lines.append(f"   north-west ridges (bearing >= 270°), lobe against the bearing buoy: "
                     f"n = {len(lobe_diffs)}, median {statistics.median(lobe_diffs):+.0f}°")
    return lines


def report(data_dir: Path) -> str:
    data_dir = Path(data_dir)
    archives = load_archives(data_dir)
    from .transform import load_spectra
    try:
        archives["46258"] = load_spectra(data_dir / "spectra" / "46258")
    except (FileNotFoundError, ValueError):
        archives["46258"] = []
    spectra = archives["46232"]
    out: list[str] = []
    out += counts(data_dir, spectra) + [""]
    out += reproducibility(archives) + [""]
    out += convergence(spectra)
    out += historical_convergence(data_dir) + [""]
    control, cases = witness_control(data_dir)
    out += control + [""]
    out += far_distance_test(data_dir, cases) + [""]
    out += bearing_shadow(archives)
    return "\n".join(out)
