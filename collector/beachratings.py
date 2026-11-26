"""Surf ratings — shape, surface and power, rated by an observer on the page.

    python -m collector.beachratings show --days 30

The ratings are the first observation the forecast page itself gathers. An
observer with a code (`docs/design/observe.md`) switches on Observe in the
page's footer, and each LIVE break tab gains three rows of chips. This module
is the series those rows land in: `data/beach_ratings/ratings.csv`.

**It is its own series, not the beach log.** The beach log never shows a
forecast, and the page these ratings come from is nothing but one. The owner's
call (2026-11-26) is that shape and power cannot be steered by the page — it
forecasts neither — so a rating made after reading it is still a witness. That
call is recorded on every row as `entered_on`, rather than trusted silently:
surface is the one quality the page does hint at, because it shows each
break's offshore/onshore wind, and only a column on the row can let that
question be asked of the series later.

**Size is not here.** A rating describes how the wave broke, not how big it
was; the body-scale height stays the log's, and a gap in one series is never
filled from the other.

Decisions, each a refusal of the obvious thing:

- **Three words a row, each ordered.** Shape and surface run worse to better
  as they are shown; power runs soft to steep, which is NOT worse to better —
  a hollow close-out is the worst day there is. Any rating worked out from
  these on read must treat power on its own terms, never as a third score.
- **All three, or no row.** A row is what one person saw at one break at one
  time, and three taps is the whole cost. A partial row would be compared
  with full ones as if it were the same kind of evidence.
- **No flat.** There is nothing to rate on a flat day; the log's body scale
  records it. A rating of a flat day would be a rating of nothing.
- **The observer is the code's, never the client's.** The page sends its code
  with each batch and the service attaches `observer_id`; a row that names
  its own observer could name anyone. Only the id is kept here — this
  repository is public, and the names live with the codes, in the service.
- **`is_test` is decided at entry**, on the page, by the observer. Never read
  back out of anything else (BRIEFING section 8; CLAUDE.md).
- **Refuse, never coerce**, as the beach log does.

The pull from the service into this file is single-writer and append-only:
`import_rows` skips an `entry_id` it already holds and never rewrites a row.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict, dataclass, fields
from datetime import timedelta
from pathlib import Path

from .beachlog import known_breaks
from .common import DEFAULT_DATA_DIR, ISO, parse_iso, utcnow

RATINGS_DIR = DEFAULT_DATA_DIR / "beach_ratings"
RATINGS = RATINGS_DIR / "ratings.csv"

#: How the wave broke. Worse to better, as the chips run left to right.
SHAPE = ("walled", "sections", "corners")
#: The water's face. Worse to better. "choppy" includes blown out.
SURFACE = ("choppy", "textured", "glassy")
#: How hard it broke. Soft to steep — NOT worse to better.
POWER = ("mushy", "punchy", "hollow")

#: Where the rating was made. One value today; a column so the next surface
#: (the log, if it gathers ratings too) is a value and not a migration.
ENTERED_ON = ("forecast_page",)

COLUMNS = (
    #: Minted on the phone; what makes a re-sent batch idempotent.
    "entry_id",
    "observed_utc",
    #: The phone's clock when Save was tapped.
    "logged_utc",
    #: The service's clock when the row arrived. Far from `logged_utc` means it
    #: sat in the phone's queue without signal, which is not a fault.
    "received_utc",
    "break_id",
    #: Attached by the service from the code. Never sent by the page.
    "observer_id",
    "shape",
    "surface",
    "power",
    "entered_on",
    "is_test",
)


class RatingError(ValueError):
    """A refused rating. Never a silently corrected one."""


@dataclass
class Rating:
    entry_id: str
    observed_utc: str
    logged_utc: str
    received_utc: str
    break_id: str
    observer_id: str
    shape: str
    surface: str
    power: str
    entered_on: str
    is_test: str

    @property
    def is_rehearsal(self) -> bool:
        """Read the stored flag. Never re-inspect anything else."""

        return self.is_test == "true"


def _one_of(value: str, allowed: tuple[str, ...], name: str) -> str:
    # Case only: a value from an older page in other letters is the same word.
    # Anything else — a synonym, a misspelling, a blank — is refused.
    value = (value or "").strip().lower()
    if value not in allowed:
        raise RatingError(f"{name}: {value!r} is not one of {', '.join(allowed)}")
    return value


def validate(row: Rating, *, breaks: list[str] | None = None, now=None) -> Rating:
    """Refuse anything that would poison the series. Never coerce."""

    breaks = breaks if breaks is not None else known_breaks()
    if not row.entry_id.strip():
        raise RatingError("entry_id: required — it is what makes a re-sent batch idempotent")
    if row.break_id not in breaks:
        raise RatingError(f"break_id: {row.break_id!r} is not in spots.json")
    if not row.observer_id.strip():
        raise RatingError("observer_id: required — the service attaches it from the code")

    row.shape = _one_of(row.shape, SHAPE, "shape")
    row.surface = _one_of(row.surface, SURFACE, "surface")
    row.power = _one_of(row.power, POWER, "power")
    row.entered_on = _one_of(row.entered_on, ENTERED_ON, "entered_on")

    value = (row.is_test or "").strip().lower()
    if value not in ("true", "false"):
        # Not blank: the page always decides, and a row that arrives without
        # the decision is from something that never asked.
        raise RatingError(f"is_test: {value!r} must be true or false, decided at entry")
    row.is_test = value

    observed = parse_iso(row.observed_utc)
    logged = parse_iso(row.logged_utc)
    if observed is None:
        raise RatingError(f"observed_utc: {row.observed_utc!r} is not {ISO}")
    if logged is None:
        raise RatingError(f"logged_utc: {row.logged_utc!r} is not {ISO}")
    if observed > logged:
        raise RatingError("observed_utc is after logged_utc — rated before it was seen")
    # A phone's clock runs a little fast or slow; ten minutes of grace keeps a
    # real "now" rating, and a row stamped hours ahead is still refused.
    if observed > (now or utcnow()) + timedelta(minutes=10):
        raise RatingError("observed_utc is in the future")
    if row.received_utc and parse_iso(row.received_utc) is None:
        raise RatingError(f"received_utc: {row.received_utc!r} is not {ISO}")
    return row


def from_row(row: dict) -> Rating:
    """One row as the service hands it over: absent keys blank, extras ignored.

    Tolerant of keys it does not know, so a page that grows a field does not
    stop a pull; strict about every value it takes, in `validate`.
    """

    names = {f.name for f in fields(Rating)}
    return Rating(**{k: str(row.get(k, "") or "") for k in names})


def load(*, path: Path = RATINGS) -> list[Rating]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        rows = [from_row(r) for r in csv.DictReader(handle)]
    return sorted(rows, key=lambda r: r.observed_utc)


def import_rows(rows: list[dict], *, path: Path = RATINGS,
                breaks: list[str] | None = None) -> dict:
    """Append the rows not already held. Returns what happened to each kind.

    Idempotent on `entry_id`, append-only, and a refused row is reported with
    its reason, never stored and never fixed up.
    """

    breaks = breaks if breaks is not None else known_breaks()
    held = {r.entry_id for r in load(path=path)}
    added, skipped, refused = [], 0, []
    for raw in rows:
        row = from_row(raw)
        if row.entry_id in held:
            skipped += 1
            continue
        try:
            validate(row, breaks=breaks)
        except RatingError as exc:
            refused.append((row.entry_id or "?", str(exc)))
            continue
        held.add(row.entry_id)
        added.append(row)

    if added:
        path.parent.mkdir(parents=True, exist_ok=True)
        new_file = not path.exists() or path.stat().st_size == 0
        with path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(COLUMNS))
            if new_file:
                writer.writeheader()
            for row in added:
                writer.writerow(asdict(row))
    return {"added": len(added), "skipped": skipped, "refused": refused}


#: The Observe service's copy of this vocabulary (`docs/design/observe.md`).
#: Generated, never edited: `python -m collector.beachratings vocab`, and
#: `tests/test_observe_service.py` fails when it has drifted from this module.
SERVICE_VOCAB = Path(__file__).resolve().parent.parent / "service" / "observe" / "src" / "vocab.js"


def service_vocab(*, breaks: list[str] | None = None) -> str:
    """The words, breaks and columns the service refuses a row against.

    The service checks a row at the door so a bad one is refused while the
    observer is still there to see why; `import_rows` checks it again at the
    pull, because the service is not the series' authority. Both read the
    same lists, so they cannot disagree about a word.
    """

    data = {
        "shape": list(SHAPE),
        "surface": list(SURFACE),
        "power": list(POWER),
        "entered_on": list(ENTERED_ON),
        "breaks": breaks if breaks is not None else known_breaks(),
        "columns": list(COLUMNS),
    }
    return ("// Generated by `python -m collector.beachratings vocab` from\n"
            "// collector/beachratings.py and forecast/spots.json. Do not edit.\n"
            f"export default {json.dumps(data, indent=2)};\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    show = sub.add_parser("show", help="print recent ratings")
    show.add_argument("--days", type=int, default=30)
    show.add_argument("--tests", action="store_true", help="include rehearsal rows")
    sub.add_parser("vocab", help=f"rewrite {SERVICE_VOCAB.name} for the Observe service")
    args = parser.parse_args(argv)

    if args.cmd == "vocab":
        SERVICE_VOCAB.parent.mkdir(parents=True, exist_ok=True)
        SERVICE_VOCAB.write_text(service_vocab(), encoding="utf-8")
        print(f"wrote {SERVICE_VOCAB}")
        return 0

    since = utcnow() - timedelta(days=args.days)
    rows = [r for r in load() if (parse_iso(r.observed_utc) or since) >= since
            and (args.tests or not r.is_rehearsal)]
    if not rows:
        print("no ratings in that window")
        return 0
    for r in rows:
        flag = "  (test)" if r.is_rehearsal else ""
        print(f"{r.observed_utc}  {r.break_id:<16} {r.observer_id:<10} "
              f"{r.shape:<9} {r.surface:<9} {r.power}{flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
