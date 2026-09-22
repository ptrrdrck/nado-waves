"""Where a blocker's edges really sit, read off a charted coastline.

Run: ``python -m forecast.blockeredge``

`forecast/geometry.py` turns two coordinates per blocker into a blocked
sector. Those two coordinates are the whole claim, and until now two of the
three came from somewhere other than a chart: the Coronado Islands were an
estimate, and the Baja mainland was not in the file at all — which is why
every Coronado window's southern edge is currently formed by the seaward
half-plane instead of by land, the raw-arc problem BRIEFING §12 describes.

This module reads `data/shoreline/*_<region>.csv` and reports, per break, the
two vertices of extreme bearing: the blocker's edges as the chart draws them.
Like `forecast.shorenormal` it REPORTS AND NEVER EDITS. A coordinate in
`spots.json` is a claim with a provenance block attached, and a program that
rewrites it silently would make the provenance a lie.

Two things about the geometry here that are not obvious:

**The southern edge is a tangent, not a chord end.** Measured 2026-09-20, the
Baja coast is seen almost exactly edge-on from Coronado: charted vertices from
the border to Rosarito span 147–168° from the south break, and public landmark
positions put everything on to Punta Eugenia, 573 km away, inside 152–165°. So
the edge is set by whichever single vertex sits furthest seaward, and nothing
either side of it matters. That is the Point Loma tip's geometry again — but
23 km out instead of 5, so 100 m of error costs 0.25° rather than 1°.

**A maximum at the edge of the data is not a tangent.** If the extreme vertex
is the southernmost one the extract holds, the chart ran out before the coast
turned away and the real edge is somewhere unseen. `Edge.at_data_limit` is
that alarm, and it is the reason the first Baja fetch was run with a query
floor 90 km south of any coastline NOAA turned out to carry.
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass, field
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR
from .geometry import Blocker, Spot, load
from .shorenormal import STORE_DIR, band_of
from .swell import great_circle_km, initial_bearing

#: How the two charted features in the Baja extract are told apart. The
#: Coronado Islands sit 8 km off the mainland and the gap is unambiguous at
#: any chart scale, so one meridian separates them cleanly. Written as a
#: filter rather than inferred from part numbers because ENC part numbering is
#: a property of the query response, not of the coast.
#: The land border at the coast. Everything south of it is the Baja mainland;
#: the US coast between here and the beach is land too, but it sits at LOWER
#: bearing than the tangent and is therefore already inside the shadow, so
#: including it would only widen a reported width with redundancy.
BORDER_LAT = 32.5343

#: The two islands are split at 32.43 N, where the charted outlines put 6.1
#: degrees of open channel. That split is stable: single-link clustering of
#: the vertices gives the same two groups at every link distance from 0.3 km
#: to 3 km, on both chart bands, and the channel measures 6.12 and 6.17
#: degrees on the two. At 0.3 km the southern group resolves further into
#: three islands, but those gaps are 0.98 and 0.25 degrees and they move with
#: the link distance, so they are not modelled.
ISLAND_SPLIT_LAT = 32.43

#: The far side of the harbour channel. The `point_loma` box already stops
#: at -117.226 so North Island is not fetched at all; this is the same line
#: written as a filter, so a wider box later cannot quietly let Zuniga Point
#: into the peninsula. Ballast Point, the Point Loma side of the channel, sits
#: at about -117.234.
CHANNEL_LON = -117.226

#: A floor under the peninsula, well south of the tip (about 32.665) and well
#: north of the Coronado Islands (32.45), so no charted vertex can be claimed
#: by two features even if a box is widened later.
PENINSULA_FLOOR_LAT = 32.62

FEATURES: dict[str, dict] = {
    "Point Loma peninsula": {
        "region": "point_loma",
        "keep": lambda lat, lon: lon < CHANNEL_LON and lat >= PENINSULA_FLOOR_LAT,
        "note": "the tip, 5-7 km out; its LOW edge is the west edge of every window",
        # The land continues NORTH, not south: the vertex that forms the edge
        # is the southern end of the peninsula by construction, so the
        # southern data-limit alarm would fire on exactly the geometry it
        # exists to exonerate (the islands' mistake, see DATA_LIMIT_DEG). The
        # envelope floor sits 2.5 km of open water south of the tip instead.
        "continues": False,
        "edge": "low",
    },
    "Coronado Islands (south group)": {
        "region": "baja",
        "keep": lambda lat, lon: lon < -117.20 and lat < ISLAND_SPLIT_LAT,
        "note": "three islands close together, 29-32 km out",
        # An island closes on both sides: its southern tip is the southern end
        # of the feature, not the southern end of the chart.
        "continues": False,
        "edge": "both",
    },
    "Coronado Islands (north)": {
        "region": "baja",
        "keep": lambda lat, lon: (lon < -117.20 and lat < 32.50
                                  and lat >= ISLAND_SPLIT_LAT),
        "note": "the northern island, 28 km out, 1427 m across",
        "continues": False,
        "edge": "both",
    },
    "Baja mainland": {
        "region": "baja",
        "keep": lambda lat, lon: lon > -117.20 and lat < BORDER_LAT,
        "note": "the coast running south from the border, seen edge-on",
        # The coast runs on past anything NOAA charts, so a maximum sitting at
        # the extract's southern end would be the chart ending rather than the
        # coast turning away.
        "continues": True,
        "edge": "high",
    },
}

#: A vertex this close to the extract's southern limit is not trusted as a
#: tangent: the chart may simply have ended before the coast turned away.
#: One arc-minute, about 1.8 km.
#:
#: Applied only to a feature declared `continues`. The first version applied
#: it to everything and flagged the Coronado Islands' southern tip, which is
#: the southern end of an island and could not be anything else — an alarm
#: that fires on the geometry it was built to exonerate is worse than none,
#: because the real one then reads as noise.
DATA_LIMIT_DEG = 1.0 / 60.0


@dataclass(frozen=True)
class Edge:
    """One end of a blocker's shadow, and the vertex that forms it."""

    bearing_deg: float
    vertex: tuple[float, float]
    range_km: float
    #: True when the vertex sits at the southern limit of the extract, so the
    #: chart may have run out rather than the coast turned away.
    at_data_limit: bool = False

    def moves_by(self, metres: float) -> float:
        """Degrees this edge swings if the vertex is wrong by `metres`."""

        if self.range_km <= 0:
            return float("nan")
        return math.degrees(metres / 1000.0 / self.range_km)


@dataclass
class FeatureReport:
    feature: str
    source: str
    spot_id: str
    #: Which edge of this feature is a claim. A peninsula or a coast that
    #: continues has one real edge; the other end of its shadow is the seaward
    #: half-plane, and reporting a width across it would be reporting
    #: redundancy as a measurement.
    meaningful: str = "both"
    low: Edge | None = None
    high: Edge | None = None
    vertices: int = 0
    #: What `spots.json` claims today, when it carries this blocker at all.
    claimed: tuple[float, float] | None = None

    @property
    def width_deg(self) -> float | None:
        """Angular extent — only for a feature whose BOTH edges are its own."""

        if self.low is None or self.high is None or self.meaningful != "both":
            return None
        return self.high.bearing_deg - self.low.bearing_deg

    @property
    def moves(self) -> tuple[float, float] | None:
        """How far each claimed edge moves if the chart is believed."""

        if self.claimed is None or self.low is None or self.high is None:
            return None
        return (self.low.bearing_deg - self.claimed[0],
                self.high.bearing_deg - self.claimed[1])


def read_file(path: Path) -> list[tuple[float, float]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return [(float(r["lat"]), float(r["lon"])) for r in csv.DictReader(fh)]


def sources(data_dir: Path, region: str) -> dict[str, list[tuple[float, float]]]:
    """Every stored extract of one region, finest chart band first."""

    folder = Path(data_dir) / STORE_DIR
    if not folder.exists():
        return {}
    found = sorted(folder.glob(f"*_{region}.csv"),
                   key=lambda p: (band_of(p.name), p.name))
    return {p.stem: read_file(p) for p in found if p.is_file()}


def edges(
    spot: Spot,
    points: list[tuple[float, float]],
    *,
    continues: bool = False,
) -> tuple[Edge, Edge] | None:
    """The lowest- and highest-bearing vertices of a cloud, seen from `spot`.

    No wrap handling, deliberately. Every feature this is used on subtends far
    less than 180° from the beach and sits well away from due north, so a
    plain min and max are correct and a circular treatment would only hide a
    feature that had been filtered wrong.
    """

    if len(points) < 2:
        return None
    floor = min(p[0] for p in points)
    def make(p: tuple[float, float]) -> Edge:
        return Edge(
            bearing_deg=initial_bearing(spot.position, p),
            vertex=p,
            range_km=great_circle_km(spot.position, p),
            at_data_limit=continues and (p[0] - floor) < DATA_LIMIT_DEG,
        )
    return (make(min(points, key=lambda p: initial_bearing(spot.position, p))),
            make(max(points, key=lambda p: initial_bearing(spot.position, p))))


def claimed_edges(spot: Spot, blocker: Blocker) -> tuple[float, float]:
    """What `spots.json` says this blocker's edges are, low first."""

    a = initial_bearing(spot.position, blocker.a_seen_from(spot.position))
    b = initial_bearing(spot.position, blocker.b)
    return (min(a, b), max(a, b))


def report(
    data_dir: Path = DEFAULT_DATA_DIR,
    spots_path: Path | None = None,
) -> list[FeatureReport]:
    spots, blockers = load(spots_path) if spots_path else load()
    by_name = {b.name: b for b in blockers}
    out: list[FeatureReport] = []
    for feature, spec in FEATURES.items():
        for source, points in sources(data_dir, spec["region"]).items():
            kept = [p for p in points if spec["keep"](*p)]
            for spot in spots:
                got = edges(spot, kept, continues=spec["continues"])
                blocker = by_name.get(feature)
                out.append(FeatureReport(
                    feature=feature, source=source, spot_id=spot.id,
                    meaningful=spec["edge"],
                    low=got[0] if got else None,
                    high=got[1] if got else None,
                    vertices=len(kept),
                    claimed=claimed_edges(spot, blocker) if blocker else None,
                ))
    return out


def format_report(rows: list[FeatureReport]) -> str:
    lines = ["### Blocker edges, read off the charted coastline", ""]
    if not rows:
        lines.append(
            "No coastline extract stored. Nothing is inferred from the "
            "absence: run the shoreline workflow for the region first."
        )
        return "\n".join(lines)

    for feature in dict.fromkeys(r.feature for r in rows):
        lines.append(f"**{feature}** — {FEATURES[feature]['note']}")
        lines.append("")
        lines.append("| source | break | pts | low edge | high edge | width | "
                     "vs spots.json | 100 m costs |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for row in [r for r in rows if r.feature == feature]:
            if row.low is None or row.high is None:
                lines.append(f"| `{row.source}` | {row.spot_id} | {row.vertices} "
                             "| — | — | — | — | — |")
                continue
            lo = f"{row.low.bearing_deg:.2f}"
            hi = f"{row.high.bearing_deg:.2f}"
            if row.low.at_data_limit:
                lo += " ⚠"
            if row.high.at_data_limit:
                hi += " ⚠"
            if row.meaningful == "high":
                lo = "(half-plane)"
            elif row.meaningful == "low":
                hi = "(half-plane)"
            moves = row.moves
            if moves is None:
                vs = "not in spots.json"
            elif row.meaningful == "low":
                vs = f"{moves[0]:+.2f} / —"
            elif row.meaningful == "high":
                vs = f"— / {moves[1]:+.2f}"
            else:
                vs = f"{moves[0]:+.2f} / {moves[1]:+.2f}"
            width = "—" if row.width_deg is None else f"{row.width_deg:.2f}"
            edge = row.high if row.meaningful != "low" else row.low
            lines.append(
                f"| `{row.source}` | {row.spot_id} | {row.vertices} | {lo} | {hi} "
                f"| {width} | {vs} | {edge.moves_by(100.0):.2f}° |"
            )
        lines.append("")

    if any(r.low and r.low.at_data_limit or r.high and r.high.at_data_limit
           for r in rows):
        lines.append(
            "⚠ — the vertex forming this edge sits at the southern limit of "
            "the extract. The chart may have ended before the coast turned "
            "away, in which case the real edge is somewhere unseen and this "
            "number is a floor, not a tangent."
        )
        lines.append("")
    lines.append(
        "Reported only. Nothing in `forecast/spots.json` is edited by this "
        "module: a coordinate there carries a provenance block, and a program "
        "that rewrote it silently would make that provenance a lie."
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = parser.parse_args(argv)
    print(format_report(report(args.data_dir)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
