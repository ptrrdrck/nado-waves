"""Does the beach log agree with the geometry? And the control that would kill it.

    python -m forecast.beachverify

The geometry says Coronado's three breaks hold 41.1, 47.7 and 54.9 degrees of
west window, cutting off at 241.7, 250.3 and 260.0 degrees. That is the
project's central claim and nothing has ever checked it against the ocean.

This module is what checks it, and the thing that makes it a test rather than a
tally is the control.

**The prediction is conditional, and only some days discriminate.** A swell
from 210 degrees is inside all three windows, so the geometry predicts NO
ordering between the breaks that day. A swell from 245 degrees is outside the
north break's window and inside the other two, so the geometry predicts the
north break is smaller. Only the second kind of day is evidence.

**The control is the first kind of day.** If the south break reads bigger than
the north break on days when the geometry predicts no difference, then
something other than the aperture is producing the ordering — sandbars, beach
shape, where the observer stands, the order they walk in — and the agreement on
discriminating days means nothing, because it would have appeared anyway.

That is the same shape as the expanding-window control in BRIEFING section 4,
which turned a promising 2-9% improvement into a sub-inch non-result. It is the
control that was missing from three years of this project's predecessor, and it
is built in here before there is a single observation to run it on.

Swell direction comes from the buoy's own record (NDBC `MWD`, degrees FROM), so
classifying a day costs nothing and contaminates nothing: the observation was
already logged blind, and using a measurement to sort days afterwards is not the
same as showing a forecast to an observer beforehand.

**No accuracy figure comes out of this module** and none should until the series
is long enough to hold one. It reports counts. CLAUDE.md: never state an
accuracy figure for a beach without naming the verification series it was
measured against — and a series of eleven observations is not one.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from dataclasses import dataclass

from collector.beachlog import BODY_SCALE, Observation, load
from collector.common import DEFAULT_DATA_DIR
from .geometry import load as load_spots, reaches

#: Below this the module reports counts and refuses to characterise them. Not a
#: significance threshold — a floor below which the question is not yet asked.
MEANINGFUL = 20


@dataclass
class Session:
    """One trip, one observer, two or more breaks — the comparable unit."""

    session_id: str
    entries: list[Observation]

    @property
    def observer(self) -> str:
        return self.entries[0].observer

    @property
    def observed_utc(self) -> str:
        return min(e.observed_utc for e in self.entries)

    @property
    def breaks(self) -> list[str]:
        return [e.break_id for e in self.entries]

    def ranking(self) -> list[tuple[str, int]]:
        """Breaks with their ordinal size, largest first.

        Ranks on `typical`, breaking ties on `sets`. Both are categories on one
        ordered scale, so no length conversion happens anywhere here — which is
        the point: the comparison is immune to whether the observer's sense of
        "chest high" drifts, as long as it drifts the same way at both breaks
        half an hour apart.
        """

        def size(entry: Observation) -> tuple[int, int]:
            typical = BODY_SCALE.index(entry.typical) if entry.typical else -1
            sets = BODY_SCALE.index(entry.sets) if entry.sets else typical
            return typical, sets

        ordered = sorted(self.entries, key=size, reverse=True)
        return [(e.break_id, BODY_SCALE.index(e.typical)) for e in ordered]


def sessions(entries: list[Observation], *, min_breaks: int = 2) -> list[Session]:
    grouped: dict[str, list[Observation]] = defaultdict(list)
    for entry in entries:
        grouped[entry.session_id].append(entry)
    out = [
        Session(sid, rows)
        for sid, rows in grouped.items()
        if len({r.break_id for r in rows}) >= min_breaks
    ]
    return sorted(out, key=lambda s: s.observed_utc)


def open_breaks(bearing: float, break_ids: list[str]) -> list[str]:
    """Which of these breaks the geometry says can receive swell from `bearing`."""

    spots, blockers = load_spots()
    by_id = {s.id: s for s in spots}
    return [b for b in break_ids if b in by_id and reaches(by_id[b], blockers, bearing)]


def discriminates(bearing: float, break_ids: list[str]) -> bool:
    """Does the geometry predict an ordering between these breaks at this bearing?

    It does when the bearing is open to some and blocked to others. When every
    break is open — or every one blocked — the geometry has nothing to say, and
    a day like that is a control, not evidence.
    """

    open_now = open_breaks(bearing, break_ids)
    return 0 < len(open_now) < len(break_ids)


def which_edge(bearing: float, break_ids: list[str]) -> str | None:
    """Which window edge is doing the blocking — and this is the sharp control.

    Coronado's two window edges predict OPPOSITE orderings, which is a much
    stronger test than either one alone:

    - **West edge**, the Point Loma shadow (swell from roughly 242-260 deg):
      the north break is cut off first, so the geometry says SOUTH IS BIGGER.
    - **East edge**, the Coronado Islands shadow (swell from roughly 199-204
      deg): the south break is cut off first, so the geometry says NORTH IS
      BIGGER.

    A confound — a sandbar that favours one end, where the observer habitually
    stands, the order they walk the beach in, a bias that creeps in because they
    always check the south end last when the light has changed — produces a
    CONSISTENT ordering. It would agree on one edge and disagree on the other.
    Only a real aperture effect flips with the swell.

    So agreement is counted per edge, and agreement on both edges is worth far
    more than twice the agreement on either.
    """

    open_now = set(open_breaks(bearing, break_ids))
    if not 0 < len(open_now) < len(break_ids):
        return None
    spots, _ = load_spots()
    by_id = {s.id: s for s in spots}
    known = [b for b in break_ids if b in by_id]
    if not known:
        return None
    # North-to-south by latitude, so the answer does not depend on break naming.
    north_first = sorted(known, key=lambda b: by_id[b].position[0], reverse=True)
    return "east" if north_first[0] in open_now else "west"


def check(session: Session, bearing: float) -> str | None:
    """Did this session's ordering match the geometry? 'agree', 'disagree', or None.

    None means the day did not discriminate — the control group, which is kept
    and counted rather than discarded.
    """

    ids = sorted({e.break_id for e in session.entries})
    if not discriminates(bearing, ids):
        return None

    open_now = set(open_breaks(bearing, ids))
    blocked = set(ids) - open_now
    sizes = {b: rank for b, rank in session.ranking()}

    # The prediction: every open break reads at least as big as every blocked one.
    smallest_open = min((sizes[b] for b in open_now if b in sizes), default=None)
    largest_blocked = max((sizes[b] for b in blocked if b in sizes), default=None)
    if smallest_open is None or largest_blocked is None:
        return None
    return "agree" if smallest_open >= largest_blocked else "disagree"


def report(
    entries: list[Observation],
    directions: dict[str, float],
    *,
    include_tests: bool = False,
) -> list[str]:
    """What the log can and cannot yet say. Counts only."""

    # Rehearsal rows prove the pipeline carries an entry end to end. They are
    # not observations of an ocean and must never reach a count that is read as
    # evidence — so they are dropped here, by their stored flag, and the drop is
    # announced rather than silent.
    rehearsals = [e for e in entries if e.is_rehearsal]
    if not include_tests:
        entries = [e for e in entries if not e.is_rehearsal]

    multi = sessions(entries)
    lines = [
        "## Beach log vs geometry",
        "",
        f"{len(entries)} observation(s), {len(multi)} multi-break session(s).",
        "",
    ]
    if rehearsals:
        lines += [
            f"{len(rehearsals)} test row(s) "
            + ("INCLUDED by --include-tests — they are not observations and this "
               "is not evidence." if include_tests
               else "excluded. `python -m collector.beachlog prune-tests` removes them."),
            "",
        ]

    if not entries:
        lines += [
            "**The log is empty, which is the honest state of this project.**",
            "",
            "Every accuracy claim here is unfalsifiable until this file has",
            "something in it. Nothing below runs until it does.",
            "",
            "    python -m collector.beachlog sweep -o <you>",
            "",
        ]
        return lines

    evidence: list[tuple[Session, str, str | None]] = []
    control: list[Session] = []
    undated: list[Session] = []
    for session in multi:
        bearing = directions.get(session.observed_utc[:13])
        if bearing is None:
            undated.append(session)
            continue
        verdict = check(session, bearing)
        ids = sorted({e.break_id for e in session.entries})
        if verdict is None:
            control.append(session)
        else:
            evidence.append((session, verdict, which_edge(bearing, ids)))

    agree = sum(1 for _, v, _ in evidence if v == "agree")
    lines += [
        f"- **{len(evidence)} discriminating session(s)** — swell open to some "
        f"breaks and blocked to others, so the geometry predicts an ordering. "
        f"{agree} agreed, {len(evidence) - agree} did not.",
        f"- **{len(control)} control session(s)** — swell inside every break's "
        "window, so the geometry predicts nothing.",
        f"- {len(undated)} session(s) with no buoy direction to classify them.",
        "",
    ]

    # The sharp control: the two edges predict opposite orderings, so a
    # confound agrees on one and disagrees on the other.
    by_edge: dict[str, list[str]] = defaultdict(list)
    for _, verdict, edge in evidence:
        if edge:
            by_edge[edge].append(verdict)
    if by_edge:
        lines += ["### Agreement per window edge", ""]
        for edge, verdicts in sorted(by_edge.items()):
            predicts = "south bigger" if edge == "west" else "north bigger"
            hits = verdicts.count("agree")
            lines.append(
                f"- **{edge} edge** ({'Point Loma' if edge == 'west' else 'Coronado Islands'}"
                f", predicts {predicts}): {hits}/{len(verdicts)} agreed"
            )
        if len(by_edge) < 2:
            have = next(iter(by_edge))
            missing = "east" if have == "west" else "west"
            lines += [
                "",
                f"**Only {have}-edge days so far.** Agreement on one edge alone "
                "cannot separate the aperture from a fixed bias that always "
                f"favours the same end. The {missing}-edge days are the ones that "
                "can, because there the geometry predicts the ordering REVERSES.",
            ]
        lines.append("")

    if len(evidence) < MEANINGFUL:
        lines += [
            f"**Too few discriminating sessions to characterise ({len(evidence)} "
            f"< {MEANINGFUL}).** No rate, no accuracy figure, no claim. Counts only.",
            "",
        ]

    if control:
        lines += [
            "### The control",
            "",
            "On control days the geometry predicts no ordering, so any consistent",
            "ordering there is being produced by something else — sandbars, beach",
            "shape, where the observer stands, the order they walk the beach in.",
            "**If the same ordering shows up on control days as on discriminating",
            "days, the agreement above is worthless** and the aperture is not what",
            "is being measured.",
            "",
        ]
        tally: dict[str, int] = defaultdict(int)
        for session in control:
            ranked = session.ranking()
            if ranked:
                tally[ranked[0][0]] += 1
        for break_id, count in sorted(tally.items(), key=lambda kv: -kv[1]):
            lines.append(f"- biggest on a no-prediction day: `{break_id}` × {count}")
        lines.append("")

    contaminated = [e for e in entries if e.forecast_seen == "true"]
    if contaminated:
        lines += [
            f"{len(contaminated)} of {len(entries)} entries were logged by someone "
            "who had already seen a forecast. Kept, flagged, and worth excluding "
            "as a sensitivity check once there are enough to spare.",
            "",
        ]
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Count rehearsal rows too. They are not observations; this exists "
             "for checking the pipeline, never for reading a result.",
    )
    parser.add_argument(
        "--station", default="46232",
        help="Buoy whose MWD classifies each day. Direction is used only to sort "
             "days after the fact; it never reaches an observer.",
    )
    args = parser.parse_args(argv)

    entries = load()
    directions = _buoy_directions(args.station)
    print("\n".join(report(entries, directions, include_tests=args.include_tests)))
    return 0


def _buoy_directions(station: str) -> dict[str, float]:
    """Hour -> mean wave direction (degrees FROM) from the archived buoy record.

    Keyed to the hour because CDIP and NDBC report on different minutes and an
    exact-timestamp join silently drops every cross-type pair (BRIEFING §1).
    """

    path = DEFAULT_DATA_DIR / "observations" / f"{station}.csv"
    if not path.exists():
        return {}
    out: dict[str, float] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            raw = (row.get("mwd") or "").strip()
            stamp = (row.get("timestamp_utc") or "").strip()
            if raw and stamp:
                try:
                    out[stamp[:13]] = float(raw)
                except ValueError:
                    continue
    return out


if __name__ == "__main__":
    sys.exit(main())
