"""Read the swell's return address off the buoy's own record.

Run: ``python -m forecast.forensics``

Everything else in this repository tried to predict the ocean and failed on
honest tests. This does the opposite and works: it looks *backwards*. When a
long-period swell arrives, the buoy records a signature that is not a guess and
not a forecast — it is a measurement of where the swell was born.

The physics is a century old and still feels like a magic trick. Deep-water
waves travel at ``Cg = gT/4π``, so a 20-second component outruns a 14-second
one. A storm radiates every period at once; by the time the energy has crossed
an ocean the long periods have pulled thousands of kilometres ahead. At the
buoy they arrive in order, longest first, and ``1/T`` falls *linearly* with
arrival time. The slope of that line is ``g/4πR``. Invert it and R is the
distance to the storm. The line's intercept — where ``1/T`` reaches zero, the
moment an infinitely fast wave would have left — is when the storm blew.

So one buoy gives distance and date. The buoy's mean wave direction gives the
bearing. Together they put a pin in the map for a storm nobody watched, days
after it has gone.

**The part that makes it checkable rather than merely charming**: if the pin is
right, the swell must have passed the upstream buoys on its way, and it must
have passed them *at the times the same physics predicts*. The North Pacific
sentinels in `data/historical/` are witnesses. This module back-projects the
origin, finds which sentinels sit on the great circle, predicts when each should
have seen the forerunner, and then goes and looks. A wrong origin fails that
test; a right one is confirmed by buoys that were never part of the fit.

No prediction, no contested skill, nothing to score. Just the ocean's mail,
opened after the fact.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from functools import lru_cache
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR

from .dispersion import SETTLE_HOURS, _fit_line, dispersive_arrivals
from .stats import load_column
from .swell import (
    POSITIONS,
    cross_track_km,
    destination_point,
    great_circle_km,
    travel_hours,
)

#: Hours after arrival used to read the swell's bearing. Kept short on purpose:
#: the forerunner is the cleanest, least contaminated part of the arrival, and
#: by a day in the local wind sea has usually muddied the mean direction.
BEARING_HOURS = 12

#: **Bearing is the weak measurement here and this list is why.** Distance and
#: date come from the dispersion slope, which is a clock and needs no geometry.
#: Direction comes from the buoy's mean wave direction, which is refracted by
#: the shelf and shadowed by the Channel Islands — the same January swell reads
#: 307 degrees at Tanner Banks and 279 at Mission Bay, a 28-degree spread that
#: is 4,000 km of error at the far end. So the bearing is taken from the most
#: EXPOSED buoy that has this swell as its dominant peak, not from the buoy the
#: swell was timed at, and the station used is reported rather than hidden.
BEARING_STATIONS = ("46047", "46086", "46219", "46222", "46225", "46258")

#: A direction reading only counts if the buoy's dominant period matches the
#: forerunner. Otherwise an exposed buoy reports the wind sea it can see instead
#: of the swell it cannot, and answers confidently about the wrong wave.
BEARING_PERIOD_TOLERANCE_S = 2.5
BEARING_MIN_HOURS = 4

#: A sentinel this far off the great circle is not a witness to this swell.
#: Generous, because swell spreads as it travels and the origin is a point
#: estimate of a storm hundreds of kilometres across.
WITNESS_CORRIDOR_KM = 1200.0

#: How far from the predicted time to look for the forerunner at a witness, and
#: how different its period may be and still be the same swell.
WITNESS_WINDOW_H = 18
WITNESS_PERIOD_TOLERANCE_S = 2.5
WITNESS_MIN_HEIGHT_M = 0.8

#: Broad, honest labels. A dispersion fit locates a storm to within hundreds of
#: kilometres, so naming a country would be false precision; naming a sea is not.
REGIONS = (
    # (lat_low, lat_high, lon_low, lon_high, label). Longitudes are in
    # [-180, 180) and no band is allowed to wrap the dateline, so the western
    # Pacific gets its own entries rather than a clever modulus.
    (-90.0, -45.0, -180.0, 180.0, "the Southern Ocean"),
    (-45.0, -20.0, -180.0, -70.0, "the South Pacific"),
    (-45.0, -20.0, 140.0, 180.0, "the Tasman and Southern Ocean"),
    (-20.0, 10.0, -180.0, -70.0, "the tropical Pacific"),
    (-20.0, 10.0, 120.0, 180.0, "the tropical western Pacific"),
    (10.0, 35.0, 120.0, 180.0, "the western North Pacific"),
    (35.0, 52.0, 130.0, 180.0, "the Kuril and Japan storm track"),
    (10.0, 35.0, -180.0, -140.0, "the central North Pacific"),
    (35.0, 52.0, -180.0, -150.0, "the Aleutian storm track"),
    (52.0, 90.0, -180.0, -120.0, "the Gulf of Alaska"),
    (35.0, 52.0, -150.0, -115.0, "the eastern North Pacific"),
    (10.0, 35.0, -140.0, -100.0, "the eastern North Pacific"),
)


@lru_cache(maxsize=None)
def _column(data_dir: Path, station: str, column: str) -> dict:
    """Memoised column read.

    Witness checking asks the same three columns of the same seven buoys for
    every candidate arrival. Re-reading a 26,000-row CSV each time is the exact
    mistake `origin_from_series` was split out to avoid, one layer up.
    """

    return load_column(data_dir / "historical" / f"{station}.csv", column)


def region_name(latitude: float, longitude: float) -> str:
    for low_lat, high_lat, low_lon, high_lon, label in REGIONS:
        if low_lat <= latitude < high_lat and low_lon <= longitude < high_lon:
            return label
    return "open ocean"


@dataclass(frozen=True)
class Witness:
    station: str
    distance_from_origin_km: float
    off_path_km: float
    predicted_utc: datetime
    seen_utc: datetime | None
    seen_period_s: float | None
    offset_hours: float | None

    @property
    def confirms(self) -> bool:
        return self.seen_utc is not None


@dataclass(frozen=True)
class Forensic:
    station: str
    arrival_utc: datetime
    distance_km: float
    bearing_deg: float
    origin: tuple[float, float]
    generated_utc: datetime
    r_squared: float
    lead_period_s: float
    trailing_period_s: float
    peak_height_m: float
    #: Which buoy supplied the bearing. Usually not `station`: see
    #: BEARING_STATIONS for why that matters.
    bearing_from: str
    witnesses: tuple[Witness, ...]

    @property
    def travel_days(self) -> float:
        return (self.arrival_utc - self.generated_utc).total_seconds() / 86400.0

    @property
    def region(self) -> str:
        return region_name(*self.origin)

    def sentence(self) -> str:
        """The whole point, in one line a person would actually enjoy reading."""

        confirmed = [w for w in self.witnesses if w.confirms]
        tail = ""
        if confirmed:
            names = ", ".join(w.station for w in confirmed)
            tail = f" Confirmed in transit by {names}."
        return (
            f"{self.arrival_utc:%-d %b %Y}: a {self.lead_period_s:.0f}-second "
            f"forerunner reached {self.station} from {self.bearing_deg:.0f}° "
            f"(read at {self.bearing_from}). "
            f"Born {self.travel_days:.1f} days earlier and "
            f"{self.distance_km:,.0f} km away, in {self.region}, "
            f"around {self.generated_utc:%-d %b}.{tail}"
        )


def arrival_bearing(
    data_dir: Path,
    station: str,
    arrival: datetime,
    lead_period_s: float,
    hours: int = BEARING_HOURS,
) -> tuple[float, str] | None:
    """Where the forerunner came from, and which buoy was trusted to say so.

    Walks `BEARING_STATIONS` from most exposed inward and takes the first that
    has this swell as its dominant peak for at least `BEARING_MIN_HOURS`. The
    period gate is what stops an exposed buoy from confidently reporting the
    direction of a wind sea that has nothing to do with the arrival.
    """

    order = list(BEARING_STATIONS)
    if station not in order:
        order.append(station)

    for candidate in order:
        directions = _column(data_dir, candidate, "mwd")
        periods = _column(data_dir, candidate, "dpd")
        matched = [
            directions[stamp]
            for stamp in directions
            if arrival <= stamp <= arrival + timedelta(hours=hours)
            and stamp in periods
            and abs(periods[stamp] - lead_period_s) <= BEARING_PERIOD_TOLERANCE_S
        ]
        if len(matched) < BEARING_MIN_HOURS:
            continue
        x = statistics.fmean(math.cos(math.radians(v)) for v in matched)
        y = statistics.fmean(math.sin(math.radians(v)) for v in matched)
        if x == 0.0 and y == 0.0:
            continue
        return math.degrees(math.atan2(y, x)) % 360.0, candidate
    return None


def find_witnesses(
    data_dir: Path,
    station: str,
    origin: tuple[float, float],
    generated: datetime,
    lead_period_s: float,
    candidates: tuple[str, ...],
) -> tuple[Witness, ...]:
    """Which upstream buoys should have seen this swell, and did they?

    The prediction uses nothing from the witness's own record — only the origin
    derived at the target buoy and the same group velocity. So a hit is real
    corroboration rather than a restatement of the fit.
    """

    target = POSITIONS.get(station)
    if target is None:
        return ()
    to_target = great_circle_km(origin, target)

    found: list[Witness] = []
    for other in candidates:
        position = POSITIONS.get(other)
        if position is None or other == station:
            continue
        to_witness = great_circle_km(origin, position)
        # Must be genuinely upstream, and genuinely near the path.
        if to_witness >= to_target:
            continue
        off_path = cross_track_km(origin, target, position)
        if off_path > WITNESS_CORRIDOR_KM:
            continue

        predicted = generated + timedelta(
            hours=travel_hours(to_witness, lead_period_s)
        )
        heights = _column(data_dir, other, "wvht")
        periods = _column(data_dir, other, "dpd")

        best = None
        for stamp, period in periods.items():
            gap = abs((stamp - predicted).total_seconds() / 3600.0)
            if gap > WITNESS_WINDOW_H:
                continue
            if abs(period - lead_period_s) > WITNESS_PERIOD_TOLERANCE_S:
                continue
            if heights.get(stamp, 0.0) < WITNESS_MIN_HEIGHT_M:
                continue
            if best is None or gap < best[0]:
                best = (gap, stamp, period)

        found.append(
            Witness(
                station=other,
                distance_from_origin_km=to_witness,
                off_path_km=off_path,
                predicted_utc=predicted,
                seen_utc=best[1] if best else None,
                seen_period_s=best[2] if best else None,
                offset_hours=(
                    (best[1] - predicted).total_seconds() / 3600.0 if best else None
                ),
            )
        )
    return tuple(found)


def investigate(
    data_dir: Path, station: str, candidates: tuple[str, ...]
) -> list[Forensic]:
    heights = _column(data_dir, station, "wvht")
    results: list[Forensic] = []
    for arrival, origin in dispersive_arrivals(data_dir, station):
        read = arrival_bearing(data_dir, station, arrival, origin.lead_period_s)
        position = POSITIONS.get(station)
        if read is None or position is None:
            continue
        bearing, bearing_from = read
        point = destination_point(position, bearing, origin.distance_km)
        peak = max(
            (
                value
                for stamp, value in heights.items()
                if arrival <= stamp <= arrival + timedelta(hours=48)
            ),
            default=0.0,
        )
        results.append(
            Forensic(
                station=station,
                arrival_utc=arrival,
                distance_km=origin.distance_km,
                bearing_deg=bearing,
                origin=point,
                generated_utc=origin.generated_at,
                r_squared=origin.r_squared,
                lead_period_s=origin.lead_period_s,
                trailing_period_s=origin.trailing_period_s,
                peak_height_m=peak,
                bearing_from=bearing_from,
                witnesses=find_witnesses(
                    data_dir,
                    station,
                    point,
                    origin.generated_at,
                    origin.lead_period_s,
                    candidates,
                ),
            )
        )
    return results


def dispersion_points(data_dir: Path, station: str, arrival: datetime) -> dict:
    """The exact (hours since arrival, 1/T) pairs the fit was made on, plus the fit.

    Exported so the straight line can be *shown* rather than asserted. The whole
    claim of this module rests on those points lying on a line, and a reader
    should be able to see that for themselves.

    The window is reconstructed the way `dispersive_arrivals` built it — the
    next `SETTLE_HOURS` observations at or after the arrival, counted as
    observations rather than as hours — so the drawn line is the line that
    produced the distance, not a second fit that nearly agrees with it.
    """

    heights = _column(data_dir, station, "wvht")
    periods = _column(data_dir, station, "dpd")
    stamps = sorted(set(heights) & set(periods))
    window = [t for t in stamps if t >= arrival][:SETTLE_HOURS]

    elapsed = [(t - arrival).total_seconds() / 3600.0 for t in window]
    inverse = [1.0 / periods[t] for t in window]
    fit = _fit_line(elapsed, inverse)

    return {
        "points": [
            [round(h, 2), round(v, 5), periods[t], heights[t]]
            for h, v, t in zip(elapsed, inverse, window)
        ],
        "intercept": round(fit[0], 6) if fit else None,
        "slope": round(fit[1], 8) if fit else None,
        "r_squared": round(fit[2], 4) if fit else None,
    }


def as_dict(case: Forensic, data_dir: Path) -> dict:
    return {
        "station": case.station,
        "arrival_utc": case.arrival_utc.isoformat(),
        "generated_utc": case.generated_utc.isoformat(),
        "travel_days": round(case.travel_days, 2),
        "distance_km": round(case.distance_km),
        "bearing_deg": round(case.bearing_deg, 1),
        "bearing_from": case.bearing_from,
        "origin": [round(v, 3) for v in case.origin],
        "region": case.region,
        "r_squared": round(case.r_squared, 3),
        "lead_period_s": case.lead_period_s,
        "trailing_period_s": case.trailing_period_s,
        "peak_height_m": round(case.peak_height_m, 2),
        "sentence": case.sentence(),
        "station_position": list(POSITIONS[case.station]),
        "dispersion": dispersion_points(data_dir, case.station, case.arrival_utc),
        "witnesses": [
            {
                "station": w.station,
                "position": list(POSITIONS[w.station]),
                "distance_from_origin_km": round(w.distance_from_origin_km),
                "distance_from_target_km": round(
                    great_circle_km(POSITIONS[w.station], POSITIONS[case.station])
                ),
                "off_path_km": round(w.off_path_km),
                "predicted_utc": w.predicted_utc.isoformat(),
                "seen_utc": w.seen_utc.isoformat() if w.seen_utc else None,
                "seen_period_s": w.seen_period_s,
                "offset_hours": (
                    round(w.offset_hours, 2) if w.offset_hours is not None else None
                ),
            }
            for w in case.witnesses
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--stations", default="46222,46221,46224,46225,46258")
    parser.add_argument(
        "--witnesses", default="46001,46005,46006,46059,51101,51002,46219"
    )
    parser.add_argument("--min-r2", type=float, default=0.75)
    parser.add_argument("--confirmed-only", action="store_true")
    parser.add_argument("--json", type=Path, help="Write the full case file here.")
    args = parser.parse_args(argv)

    candidates = tuple(s.strip() for s in args.witnesses.split(",") if s.strip())
    total = confirmed = 0
    exported: list[dict] = []
    for station in [s.strip() for s in args.stations.split(",") if s.strip()]:
        for case in investigate(args.data_dir, station, candidates):
            if case.r_squared < args.min_r2:
                continue
            total += 1
            if args.json:
                exported.append(as_dict(case, args.data_dir))
            hits = [w for w in case.witnesses if w.confirms]
            if hits:
                confirmed += 1
            elif args.confirmed_only:
                continue
            print(case.sentence())
            for witness in case.witnesses:
                if witness.confirms:
                    print(
                        f"    {witness.station}: predicted "
                        f"{witness.predicted_utc:%d %b %H:%M}Z, saw "
                        f"{witness.seen_period_s:.1f}s at "
                        f"{witness.seen_utc:%d %b %H:%M}Z "
                        f"({witness.offset_hours:+.0f} h, "
                        f"{witness.off_path_km:,.0f} km off path)"
                    )
            print()
    print(f"{total} readable arrivals, {confirmed} corroborated by an upstream buoy.")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(exported, indent=1), encoding="utf-8")
        print(f"wrote {len(exported)} cases to {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
