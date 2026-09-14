"""The beach observation log — the verification series everything else waits on.

    python -m collector.beachlog log          # interactive, the normal way
    python -m collector.beachlog sweep        # all three Coronado breaks, one trip
    python -m collector.beachlog show --days 30

CLAUDE.md: "Logged human observation at the beach is the intended primary
verification — observer, time and method recorded, stored as its own series,
never silently blended into the forecast it judges."

BRIEFING section 9 asks the question this module is an answer to: *what does a
verification log actually look like, such that a person will fill it in daily
for a year?* The honest answer is that nothing makes a person do anything daily
for a year, so the design is built to survive irregularity rather than to
demand consistency. Every entry is independently useful. A fortnight of silence
costs nothing structurally. There are no streaks to break.

Six decisions do the real work, and each of them is a decision not to do the
obvious thing.

**1. The first job is the DIFFERENTIAL, not the absolute height.**

People are unreliable at "that is 3.2 feet" and reliable at "the south end is
bigger than the north end today". The project's whole premise is that these
breaks differ — 42.8 / 49.1 / 56.3 degrees of open window across 2.8 km of
Coronado — and a within-session comparison by one observer, at one tide, in one
light, cancels nearly every source of calibration error that makes absolute
height hard. So the schema is built around a `session_id` that can span breaks,
and the highest-value entry in the whole design is a sweep of all three in one
trip. That entry can falsify the project's central claim on its own, before any
height calibration exists at all.

**2. Store the category. Derive the metres.**

Heights are recorded on a body-referenced scale — flat, knee, waist, chest,
head, overhead — anchored to the observer's own measured height. A body is a
stable physical ruler; "feet" is a local convention that drifts with mood, with
company, and with whether the scale is Hawaiian. The category is what was
observed, so the category is what is stored. Metres are derived on read, from
fractions that are conventional anthropometry and NOT measured for any
particular observer — which is exactly why they must never be frozen into the
file as though they were data.

**3. The tool never shows a forecast, and contamination is recorded.**

An observer who checks the forecast before logging is no longer an independent
witness, and a series contaminated that way cannot judge the forecast that
shaped it. That is a structural property, not a matter of discipline, so this
module has no forecast display and never will. `forecast_seen` records the
honest answer when someone saw one anyway on the drive over — knowing which
entries are contaminated is worth more than pretending none are.

**4. There is no "did not look" entry.**

`flat` is an observation: the ocean was flat and someone checked. Not looking is
a gap. CLAUDE.md's non-negotiable — never infer, interpolate or substitute a
missing observation — applies to verification exactly as it applies to the
archive, so the log offers no way to record an absence as a flat day.

**5. The observer is not asked for the tide.**

Tide is deterministic from the timestamp and NOAA 9410170. Asking a person for
it adds a field that gets guessed, skipped, or filled in wrong, and buys nothing
that the clock does not already give. What the observer records is what only the
observer can know. The same argument mostly applies to wind — KNZY is minutes
away — but a coarse wind impression is kept, because it costs one keystroke and
it cross-checks KNZY against the beach.

**6. How long they watched is part of the observation.**

A two-minute look from a car window systematically misses set waves and biases
low. That bias is correctable if `minutes_watched` and `saw_sets` are recorded
and uncorrectable if they are not, and it is invisible in the height alone.

What this module deliberately does NOT do: convert an observation into anything
the forecast predicts. Face height and significant wave height are different
quantities, and the transfer between them is a fitted function nobody has fitted
yet. Until that exists, this series verifies ordinal and differential claims,
and says so rather than manufacturing a comparison.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import uuid
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path

from .common import DEFAULT_DATA_DIR, ISO, parse_iso, to_iso, utcnow

LOG_DIR = DEFAULT_DATA_DIR / "beach_log"
OBSERVATIONS = LOG_DIR / "observations.csv"
OBSERVERS = LOG_DIR / "observers.csv"
SPOTS_FILE = Path(__file__).resolve().parent.parent / "forecast" / "spots.json"

#: Ordered smallest to largest, so comparisons are ordinal without any
#: conversion to length. This ordering is the part that does real work — it is
#: what lets one session say "south was bigger than north" with no calibration.
BODY_SCALE = (
    "flat",
    "ankle",
    "knee",
    "thigh",
    "waist",
    "chest",
    "shoulder",
    "head",
    "overhead",
    "double_overhead",
)

#: Fraction of the observer's standing height, for deriving an approximate face
#: height on read.
#:
#: THESE ARE CONVENTIONAL ANTHROPOMETRY, NOT MEASUREMENTS. They are not fitted,
#: not observer-specific, and not verified against anything. They exist so a
#: category can be turned into a rough length for plotting; they are not a claim
#: about how big the wave was, and a number derived through them must never be
#: reported as an observed height. The observation is the category.
SCALE_FRACTIONS = {
    "flat": 0.00,
    "ankle": 0.07,
    "knee": 0.27,
    "thigh": 0.42,
    "waist": 0.53,
    "chest": 0.72,
    "shoulder": 0.82,
    "head": 1.00,
    "overhead": 1.25,
    "double_overhead": 2.00,
}

METHODS = ("from_water", "from_sand", "from_window", "from_camera")
CONFIDENCE = ("high", "medium", "low")
WIND = ("glassy", "offshore", "cross", "light_onshore", "onshore", "storm")
RIDEABLE = ("yes", "marginal", "no")

COLUMNS = (
    #: Stable per-entry key, minted where the entry is made. It is what makes
    #: importing from the phone form idempotent: the same row arriving twice is
    #: recognised and skipped rather than double-counted into a session.
    "entry_id",
    "session_id",
    "observed_utc",
    "logged_utc",
    "break_id",
    #: Observer NAME at the time of logging, kept for reading the file by eye,
    #: and `observer_id` beside it as the durable key. The names start generic
    #: and get edited once it is known who was actually helping; a series keyed
    #: on a name would orphan every earlier row the moment that happened.
    "observer",
    "observer_id",
    #: The observer's standing height AT THE TIME OF LOGGING, carried on the row
    #: itself rather than looked up later.
    #:
    #: Observers set their own height on their own phone, and that phone is the
    #: only place it lives — so a lookup table here would be permanently empty
    #: for everyone but Pete, and the body scale would have no calibration at
    #: all. Riding along with the row also means a re-measurement never silently
    #: rewrites what an old observation was judged against.
    "observer_height_cm",
    "method",
    "minutes_watched",
    "saw_sets",
    "typical",
    "sets",
    "typical_ft",
    "sets_ft",
    "confidence",
    "wind",
    "rideable",
    "forecast_seen",
    "note",
)


class BeachLogError(ValueError):
    """A refused entry. Never a silently corrected one."""


@dataclass
class Observation:
    """One look at one break at one time.

    `observed_utc` and `logged_utc` are separate on purpose: an entry written
    six hours after the fact is weaker evidence than one written on the sand,
    and only the pair can say which this was.
    """

    entry_id: str
    session_id: str
    observed_utc: str
    logged_utc: str
    break_id: str
    observer: str
    observer_id: str
    observer_height_cm: str
    method: str
    minutes_watched: str
    saw_sets: str
    typical: str
    sets: str
    typical_ft: str
    sets_ft: str
    confidence: str
    wind: str
    rideable: str
    forecast_seen: str
    note: str

    @property
    def observed(self) -> datetime | None:
        return parse_iso(self.observed_utc)

    @property
    def height_cm(self) -> float | None:
        """The height this observation was judged against, from the row itself."""

        try:
            return float(self.observer_height_cm) or None
        except ValueError:
            return None

    def height_m(self, observer_height_cm: float | None) -> tuple[float | None, float | None]:
        """Approximate face heights in metres. DERIVED, not observed.

        Returns (typical, sets). None when the observer's height is unknown —
        which is the honest answer, not a default height standing in for a
        measurement nobody took.
        """

        if not observer_height_cm:
            return None, None
        metres = observer_height_cm / 100.0
        return (
            SCALE_FRACTIONS[self.typical] * metres if self.typical else None,
            SCALE_FRACTIONS[self.sets] * metres if self.sets else None,
        )


def known_breaks() -> list[str]:
    """Break ids, read from spots.json so the two files cannot drift apart.

    An observation against a break the geometry does not know about cannot be
    compared to anything, so it is refused rather than stored.
    """

    data = json.loads(SPOTS_FILE.read_text(encoding="utf-8"))
    return [spot["id"] for spot in data["spots"]]


def _one_of(value: str, allowed: tuple[str, ...], field_name: str) -> str:
    value = (value or "").strip().lower()
    if value not in allowed:
        raise BeachLogError(f"{field_name}: {value!r} is not one of {', '.join(allowed)}")
    return value


def validate(entry: Observation, *, breaks: list[str] | None = None) -> Observation:
    """Refuse anything that would poison the series. Never coerce.

    A verification log that quietly fixes up its own inputs is not a record of
    what was seen, and the whole value of this file is that it is a record of
    what was seen.
    """

    breaks = breaks if breaks is not None else known_breaks()

    if entry.break_id not in breaks:
        raise BeachLogError(
            f"break_id: {entry.break_id!r} is not in spots.json ({', '.join(breaks)})"
        )
    if not entry.observer.strip():
        raise BeachLogError("observer: required — an anonymous observation cannot be weighted")
    if not entry.entry_id.strip():
        raise BeachLogError("entry_id: required — it is what makes an import idempotent")

    entry.method = _one_of(entry.method, METHODS, "method")
    entry.confidence = _one_of(entry.confidence, CONFIDENCE, "confidence")
    entry.wind = _one_of(entry.wind, WIND, "wind")
    entry.rideable = _one_of(entry.rideable, RIDEABLE, "rideable")
    entry.typical = _one_of(entry.typical, BODY_SCALE, "typical")

    # `sets` may be blank: on a flat day there are no sets to describe, and
    # inventing one would be substituting a value for a missing observation.
    if entry.sets:
        entry.sets = _one_of(entry.sets, BODY_SCALE, "sets")
        if BODY_SCALE.index(entry.sets) < BODY_SCALE.index(entry.typical):
            raise BeachLogError(
                f"sets ({entry.sets}) smaller than typical ({entry.typical}) — "
                "sets are the occasional BIGGER waves"
            )

    observed = parse_iso(entry.observed_utc)
    if observed is None:
        raise BeachLogError(f"observed_utc: {entry.observed_utc!r} is not {ISO}")
    if observed > utcnow():
        raise BeachLogError("observed_utc is in the future")

    #: Blank is allowed and an implausible number is not.
    #:
    #: The form refuses to save without a height, which is where the rule
    #: belongs. Refusing the ROW here would be the wrong trade: every comparison
    #: this log actually makes is ordinal, and works perfectly without a height —
    #: the height only feeds the approximate metres, which are a reading aid.
    #: Throwing away a real observation to protect a derived convenience would
    #: cost more than it saves. `beachlog_import` counts what arrives without
    #: one so it stays visible rather than silent.
    if entry.observer_height_cm:
        try:
            height = float(entry.observer_height_cm)
        except ValueError as exc:
            raise BeachLogError(
                f"observer_height_cm: {entry.observer_height_cm!r} is not a number"
            ) from exc
        if not 100.0 <= height <= 230.0:
            raise BeachLogError(
                f"observer_height_cm: {height:.0f} cm is outside 100-230 — "
                "a standing height, not a wave"
            )

    for name in ("minutes_watched", "typical_ft", "sets_ft"):
        raw = getattr(entry, name)
        if raw:
            try:
                if float(raw) < 0:
                    raise BeachLogError(f"{name}: negative")
            except ValueError as exc:
                raise BeachLogError(f"{name}: {raw!r} is not a number") from exc

    for name in ("saw_sets", "forecast_seen"):
        value = (getattr(entry, name) or "").strip().lower()
        if value not in ("true", "false", ""):
            raise BeachLogError(f"{name}: {value!r} must be true, false or blank")
        setattr(entry, name, value)

    return entry


def append(entry: Observation, *, path: Path = OBSERVATIONS) -> Observation:
    """Append one validated observation. Append-only, like the revisions log."""

    validate(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(COLUMNS))
        if new_file:
            writer.writeheader()
        writer.writerow(asdict(entry))
    return entry


def load(*, path: Path = OBSERVATIONS) -> list[Observation]:
    if not path.exists():
        return []
    names = {f.name for f in fields(Observation)}
    with path.open(encoding="utf-8", newline="") as handle:
        rows = [
            Observation(**{k: (row.get(k) or "") for k in names})
            for row in csv.DictReader(handle)
        ]
    return sorted(rows, key=lambda o: o.observed_utc)


def load_observers(*, path: Path = OBSERVERS) -> dict[str, float]:
    """Observer -> standing height in cm. The calibration for the body scale."""

    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        out = {}
        for row in csv.DictReader(handle):
            try:
                out[row["observer"]] = float(row["height_cm"])
            except (KeyError, TypeError, ValueError):
                continue
        return out


# --- entry -----------------------------------------------------------------
#
# Single-key prompts with working defaults, because the time cost of the log is
# the thing most likely to kill it. Everything that can be defaulted is; the
# fields that cannot be reconstructed later (what was seen, how long for) are
# the ones that get asked.

_KEYS = {
    "typical": {
        "f": "flat", "a": "ankle", "k": "knee", "t": "thigh", "w": "waist",
        "c": "chest", "s": "shoulder", "h": "head", "o": "overhead", "d": "double_overhead",
    },
    "wind": {
        "g": "glassy", "o": "offshore", "c": "cross", "l": "light_onshore",
        "n": "onshore", "s": "storm",
    },
    "method": {
        "w": "from_water", "s": "from_sand", "c": "from_window", "m": "from_camera",
    },
    "rideable": {"y": "yes", "m": "marginal", "n": "no"},
    "confidence": {"h": "high", "m": "medium", "l": "low"},
}
#: Sets are measured on the same scale as the typical wave — same keys, so the
#: observer is not learning two alphabets at the water's edge.
_KEYS["sets"] = _KEYS["typical"]

_PROMPTS = {
    "typical": "typical  [f]lat [a]nkle [k]nee [t]high [w]aist [c]hest [s]hldr [h]ead [o]ver [d]ouble",
    "sets": "sets     same keys, or Enter if there were none bigger",
    "wind": "wind     [g]lassy [o]ffshore [c]ross [l]ight onshore [n] onshore [s]torm",
    "method": "method   [w]ater [s]and [c]ar window [m]camera",
    "rideable": "rideable [y]es [m]arginal [n]o",
    "confidence": "sure?    [h]igh [m]edium [l]ow",
}


def _ask(field: str, *, default: str = "", allow_blank: bool = False, reader=input) -> str:
    table = _KEYS[field]
    suffix = f"  [{default}]" if default else ""
    while True:
        raw = reader(f"  {_PROMPTS[field]}{suffix}\n  > ").strip().lower()
        if not raw:
            if default:
                return default
            if allow_blank:
                return ""
            continue
        if raw in table:
            return table[raw]
        if raw in table.values():
            return raw
        print(f"  not one of {', '.join(sorted(table))}")


def compose(
    break_id: str,
    observer: str,
    *,
    session_id: str,
    reader=input,
    now: datetime | None = None,
    heights: dict[str, float] | None = None,
) -> Observation:
    """Walk one entry, interactively. No forecast is shown, here or anywhere."""

    stamp = now or utcnow()
    heights = load_observers() if heights is None else heights
    if not heights.get(observer):
        raise BeachLogError(
            f"{observer} has no standing height in {OBSERVERS.name}. Add one "
            "before logging — the body scale is anchored to it."
        )
    print(f"\n{break_id}  ({observer})")
    typical = _ask("typical", reader=reader)
    sets = "" if typical == "flat" else _ask("sets", allow_blank=True, reader=reader)
    wind = _ask("wind", reader=reader)
    method = _ask("method", default="from_sand", reader=reader)
    rideable = _ask("rideable", reader=reader)
    confidence = _ask("confidence", default="medium", reader=reader)
    minutes = reader("  minutes watched? (Enter to skip)\n  > ").strip()
    saw_sets = reader("  did you actually see a set? [y/N]\n  > ").strip().lower()
    seen = reader("  seen any forecast today? [y/N]  (honest answer; it flags the entry)\n  > ").strip().lower()
    note = reader("  note? (Enter to skip)\n  > ").strip()

    return Observation(
        entry_id=uuid.uuid4().hex[:16],
        session_id=session_id,
        observed_utc=to_iso(stamp) or "",
        logged_utc=to_iso(utcnow()) or "",
        break_id=break_id,
        observer=observer,
        observer_id=observer,
        observer_height_cm=str(int(heights[observer])),
        method=method,
        minutes_watched=minutes,
        saw_sets="true" if saw_sets.startswith("y") else "false",
        typical=typical,
        sets=sets,
        typical_ft="",
        sets_ft="",
        confidence=confidence,
        wind=wind,
        rideable=rideable,
        forecast_seen="true" if seen.startswith("y") else "false",
        note=note,
    )


def new_session() -> str:
    return uuid.uuid4().hex[:12]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The beach observation log.")
    sub = parser.add_subparsers(dest="command", required=True)

    one = sub.add_parser("log", help="Log one break.")
    one.add_argument("--break-id", "-b", required=True)
    one.add_argument("--observer", "-o", required=True)

    sweep = sub.add_parser(
        "sweep",
        help="Log several breaks in one trip. The highest-value entry in the log: "
        "a within-session comparison cancels most of what makes absolute height hard.",
    )
    sweep.add_argument("--observer", "-o", required=True)
    sweep.add_argument(
        "--breaks",
        default="coronado_north,coronado_center,coronado_south",
        help="Comma-separated, in the order you will visit them.",
    )

    show = sub.add_parser("show", help="Read the log back.")
    show.add_argument("--days", type=int, default=30)

    args = parser.parse_args(argv)

    if args.command == "show":
        return _show(args.days)

    session = new_session()
    breaks = [args.break_id] if args.command == "log" else [
        b.strip() for b in args.breaks.split(",") if b.strip()
    ]

    written = 0
    for break_id in breaks:
        try:
            entry = compose(break_id, args.observer, session_id=session)
            append(entry)
            written += 1
            print(f"  logged {break_id}: {entry.typical}"
                  + (f", sets {entry.sets}" if entry.sets else ""))
        except BeachLogError as exc:
            # Refused, not corrected, and the rest of the sweep still runs: one
            # bad entry must not cost the two good ones beside it.
            print(f"  REFUSED {break_id}: {exc}", file=sys.stderr)
        except (KeyboardInterrupt, EOFError):
            print("\n  stopped. Nothing further written.", file=sys.stderr)
            break

    if written and len(breaks) > 1:
        print(f"\n  session {session}: {written} break(s) — this one can be compared "
              "against itself, which is the point.")
    return 0 if written else 1


def _show(days: int) -> int:
    entries = load()
    if not entries:
        print("The log is empty. `python -m collector.beachlog log -b coronado_center -o you`")
        return 0

    cutoff = utcnow().timestamp() - days * 86400
    recent = [e for e in entries if (e.observed or datetime.now(timezone.utc)).timestamp() >= cutoff]
    heights = load_observers()

    print(f"{len(recent)} observation(s) in the last {days} days "
          f"({len(entries)} in the log, first {entries[0].observed_utc}).\n")
    for entry in recent:
        typical_m, sets_m = entry.height_m(entry.height_cm or heights.get(entry.observer))
        approx = f"  ~{typical_m:.1f} m" if typical_m else ""
        print(
            f"  {entry.observed_utc}  {entry.break_id:17s} {entry.typical:16s}"
            f"{('sets ' + entry.sets) if entry.sets else '':22s}"
            f"{entry.wind:14s} {entry.rideable:9s}{approx}"
            + ("   [forecast seen]" if entry.forecast_seen == "true" else "")
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
