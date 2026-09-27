"""Does GFS-Wave's bias at the buoys follow the islands' shadow?

Run: ``python -m forecast.exposurebias``

BRIEFING §5 measured GFS-Wave's analysis 0.26–0.31 m LOW at 46232, 46224 and
46222, at every lead including +0h, and read that as "model geometry at an
unresolved nearshore point". All three of those buoys sit in the Channel
Islands' shadow (§3), so that reading was never tested against a buoy that is
NOT shadowed. This report adds the ones that make the test possible: 46047
(Tanner Banks, §3's unshadowed denominator), 46086 (partly shadowed) and 46258
(shadowed like 46232, on the far side of Point Loma).

Two measurements, both at one lead (the analysis, +0h, by default, where a
forecast error has had no time to grow and what is left is the model's
picture of the place):

* **Bias by station**, in metres and as a share of the mean sea, because
  46047's sea is larger than 46232's and a fixed offset in metres would read
  as a gradient that is only a difference in scale.
* **Shadow, measured against modelled, by direction.** For each hour, each
  station's height over 46047's, once from the buoys and once from the model.
  The buoys' ratio is the islands' shadow as it happened (§3's method). The
  model's ratio is the shadow the model thinks there is. Where the two agree
  the model resolves the islands; where the model's stays near 1 while the
  buoys' falls, it does not. Sectors are keyed on 46047's own mean direction,
  because it is the one buoy nothing upstream bends.

It reports and never edits: nothing here changes a forecast number, and
nothing here says anything about a beach. Gaps are dropped, never filled.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR

from .stats import load_column
from .verify import _indexed, _lookup, load_forecasts

#: The unshadowed reference, §3's denominator.
REFERENCE = "46047"

#: Every station with archived GFS-Wave cycles: the reference, then five buoys
#: the islands shadow (§3's ratios to Tanner Banks on SW swell: 0.82, 0.72,
#: 0.75, 0.64, 0.50).
DEFAULT_STATIONS = ("46047", "46086", "46258", "46232", "46224", "46222")

#: Swell hours, as §3 defined them: long period, not flat. Read at the
#: reference, so every station is judged over the same hours.
SWELL_MIN_PERIOD_S = 12.0
SWELL_MIN_HS_M = 0.5

#: Direction sectors, degrees FROM at 46047. §3's own boundaries were not
#: recorded in code, so these are this report's and are stated rather than
#: implied to match.
SECTORS = (
    ("S", 160.0, 200.0),
    ("SW", 200.0, 240.0),
    ("W", 240.0, 275.0),
    ("WNW", 275.0, 300.0),
    ("NW", 300.0, 330.0),
)

#: Below this a median describes a handful of storms, not a sector.
MIN_CELL = 30


@dataclass(frozen=True)
class Hour:
    """One valid time, at one station, with its reference alongside."""

    valid: datetime
    model: float
    observed: float
    ref_model: float
    ref_observed: float
    ref_period: float | None
    ref_from: float | None

    @property
    def swell(self) -> bool:
        return (
            self.ref_period is not None
            and self.ref_period >= SWELL_MIN_PERIOD_S
            and self.ref_observed >= SWELL_MIN_HS_M
        )

    @property
    def sector(self) -> str | None:
        if self.ref_from is None:
            return None
        for name, low, high in SECTORS:
            if low <= self.ref_from < high:
                return name
        return None


def _observations(data_dir: Path, station: str, column: str):
    return _indexed(load_column(Path(data_dir) / "historical" / f"{station}.csv", column))


def hours(data_dir: Path, station: str, lead_h: int, reference: str = REFERENCE) -> list[Hour]:
    """Every valid time where both stations have a forecast and an observation.

    An hour missing any of the four heights is dropped; one missing only the
    reference's period or direction is kept for the all-hours table and falls
    out of the swell and sector ones.
    """

    data_dir = Path(data_dir)
    model = {
        p.valid: p.hs_total_m
        for p in load_forecasts(data_dir / "wave_forecasts" / f"{station}.csv")
        if p.lead_h == lead_h
    }
    ref_model = {
        p.valid: p.hs_total_m
        for p in load_forecasts(data_dir / "wave_forecasts" / f"{reference}.csv")
        if p.lead_h == lead_h
    }
    observed = _observations(data_dir, station, "wvht")
    ref_observed = _observations(data_dir, reference, "wvht")
    ref_period = _observations(data_dir, reference, "dpd")
    ref_from = _observations(data_dir, reference, "mwd")

    out = []
    for valid in sorted(model.keys() & ref_model.keys()):
        seen = _lookup(observed, valid)
        ref_seen = _lookup(ref_observed, valid)
        if seen is None or ref_seen is None or ref_seen <= 0.0 or ref_model[valid] <= 0.0:
            continue
        out.append(Hour(
            valid=valid,
            model=model[valid],
            observed=seen,
            ref_model=ref_model[valid],
            ref_observed=ref_seen,
            ref_period=_lookup(ref_period, valid),
            ref_from=_lookup(ref_from, valid),
        ))
    return out


def bias(sample: list[Hour]) -> dict:
    """Model minus buoy, as `forecast.verify` signs it: negative is LOW."""

    if len(sample) < 2:
        return {"n": len(sample)}
    errors = [h.model - h.observed for h in sample]
    mean_observed = statistics.fmean(h.observed for h in sample)
    return {
        "n": len(sample),
        "bias_m": statistics.fmean(errors),
        "relative": statistics.fmean(errors) / mean_observed,
        "mean_observed_m": mean_observed,
    }


def shadow(sample: list[Hour]) -> dict:
    """The station over the reference: as measured, and as the model has it.

    Medians of per-hour ratios, as §3 took them. `agreement` is the model's
    ratio over the buoys': 1.00 means the model has the shadow right, above 1
    that it lets through energy the islands took (a smooth-ocean model), below
    1 that it takes more than the islands do.
    """

    if len(sample) < MIN_CELL:
        return {"n": len(sample)}
    measured = statistics.median(h.observed / h.ref_observed for h in sample)
    modelled = statistics.median(h.model / h.ref_model for h in sample)
    return {
        "n": len(sample),
        "measured": measured,
        "modelled": modelled,
        "agreement": modelled / measured,
        "model_over_buoy": statistics.median(h.model / h.observed for h in sample if h.observed > 0),
    }


def report(
    data_dir: Path = DEFAULT_DATA_DIR,
    stations: tuple[str, ...] = DEFAULT_STATIONS,
    lead_h: int = 0,
    reference: str = REFERENCE,
) -> list[str]:
    per_station = {s: hours(data_dir, s, lead_h, reference) for s in stations}
    years = sorted({h.valid.year for sample in per_station.values() for h in sample})

    lines = [
        f"# GFS-Wave bias against exposure — +{lead_h} h",
        "",
        f"Model minus buoy (negative = model LOW). Reference {reference}; "
        f"swell hours are {reference} DPD >= {SWELL_MIN_PERIOD_S:.0f} s and "
        f"Hs >= {SWELL_MIN_HS_M} m.",
        "",
        "## Bias by station, all hours",
        "",
        "station |     n | obs mean m | bias m | bias % of sea | "
        + " | ".join(f"{y} %" for y in years),
        "--------+-------+------------+--------+---------------+-"
        + "-+-".join("-" * (len(str(y)) + 2) for y in years),
    ]
    for station, sample in per_station.items():
        stats = bias(sample)
        if stats["n"] < 2:
            lines.append(f"{station:7} | {stats['n']:5d} |   (no pairs: archive the cycles)")
            continue
        by_year = []
        for year in years:
            part = bias([h for h in sample if h.valid.year == year])
            by_year.append(f"{part['relative']:+6.1%}" if part["n"] >= MIN_CELL else f"{'-':>6}")
        lines.append(
            f"{station:7} | {stats['n']:5d} | {stats['mean_observed_m']:10.2f} | "
            f"{stats['bias_m']:+6.2f} | {stats['relative']:+13.1%} | " + " | ".join(by_year)
        )

    lines += [
        "",
        "## Shadow against the reference, swell hours, by direction at the reference",
        "",
        "'buoys' is the station's height over the reference's as measured; 'model'",
        "the same ratio in GFS-Wave; 'agree' is model over buoys: 1.00 = the model",
        "has the shadow right, above 1 = it lets through what the islands took, below",
        "1 = it takes more than they do. 'model/buoy' is the station's own median",
        "model over its own buoy.",
    ]
    ref_swell = [h for h in per_station.get(reference, []) if h.swell and h.observed > 0]
    if len(ref_swell) >= MIN_CELL:
        lines += [
            "",
            f"{reference} itself, same hours: model/buoy "
            f"{statistics.median(h.model / h.observed for h in ref_swell):.2f} "
            f"(n {len(ref_swell)}).",
        ]
    for station, sample in per_station.items():
        if station == reference:
            continue
        swell = [h for h in sample if h.swell]
        lines += [
            "",
            f"### {station}",
            "",
            "sector |    n | buoys | model | agree | model/buoy",
            "-------+------+-------+-------+-------+-----------",
        ]
        cells = [("all", swell)] + [
            (name, [h for h in swell if h.sector == name]) for name, _, _ in SECTORS
        ]
        for name, cell in cells:
            stats = shadow(cell)
            if "measured" not in stats:
                lines.append(f"{name:6} | {stats['n']:4d} |   (too few)")
                continue
            lines.append(
                f"{name:6} | {stats['n']:4d} | {stats['measured']:5.2f} | "
                f"{stats['modelled']:5.2f} | {stats['agreement']:5.2f} | "
                f"{stats['model_over_buoy']:10.2f}"
            )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--stations", default=",".join(DEFAULT_STATIONS))
    parser.add_argument("--lead", type=int, default=0, help="Lead time in hours.")
    args = parser.parse_args(argv)

    stations = tuple(s.strip() for s in args.stations.split(",") if s.strip())
    print("\n".join(report(args.data_dir, stations, args.lead)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
