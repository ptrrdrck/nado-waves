"""Bring rows from the phone form into the repository's copy of the log.

    python -m collector.beachlog_import rows.json
    python -m collector.beachlog_import rows.json --dry-run

The phone form (`app/beachlog.html`, published as an Artifact) is the CAPTURE
surface. It has to be: nobody carries a laptop to the waterline, and the entry
has to survive a beach with no signal. But the artifact's store is not the
system of record — `data/beach_log/observations.csv` is, for the same reason
every other series in this repository is committed here: a file in this
repository is the only copy that cannot quietly disappear.

So this is the bridge. Read the rows out of the artifact store with the
Artifact tool's `read_db`, save them as JSON, and hand them to this.

Three properties it has to have, and each one is a failure it prevents:

**Idempotent.** Every row carries an `entry_id` minted on the phone. Importing
the same export twice must not double-count an observation into a session,
because a session is the unit the geometry test compares against itself — a
duplicated break would look like a real second look at the same spot.

**Validating.** Rows arrive from a form that runs on someone else's phone,
possibly a version of it older than this file. They go through the same
`validate` as anything typed at the CLI, and a bad row is refused with a reason
rather than coerced into the file.

**Non-destructive.** It only ever appends. A row already present is skipped, not
rewritten — the same rule the NDBC archive lives by, where a published value is
never overwritten by a later blank.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import fields
from pathlib import Path

from .beachlog import (
    OBSERVATIONS,
    BeachLogError,
    Observation,
    append,
    load,
)


def from_row(row: dict) -> Observation:
    """Build an Observation from one exported row, filling absent keys blank.

    Deliberately tolerant about EXTRA keys and strict about the values it does
    take: the form may grow fields before this file knows about them, and that
    should not stop an import, but nothing it does send gets guessed at.
    """

    names = {f.name for f in fields(Observation)}
    return Observation(**{k: str(row.get(k, "") or "") for k in names})


def import_rows(
    rows: list[dict],
    *,
    path: Path = OBSERVATIONS,
    dry_run: bool = False,
) -> tuple[int, int, list[str]]:
    """Returns (imported, skipped_as_duplicate, refusals)."""

    known = {e.entry_id for e in load(path=path) if e.entry_id}
    imported = 0
    duplicate = 0
    refused: list[str] = []

    for row in rows:
        entry = from_row(row)
        if entry.entry_id and entry.entry_id in known:
            duplicate += 1
            continue
        try:
            if not dry_run:
                append(entry, path=path)
            else:
                from .beachlog import validate

                validate(entry)
        except BeachLogError as exc:
            refused.append(f"{entry.entry_id or '(no id)'} {entry.break_id}: {exc}")
            continue
        known.add(entry.entry_id)
        imported += 1

    return imported, duplicate, refused


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import beach log rows from the phone form.")
    parser.add_argument("source", type=Path, help="JSON: a list of rows, or {rows: [...]}")
    parser.add_argument("--dry-run", action="store_true", help="Validate without writing.")
    parser.add_argument("--path", type=Path, default=OBSERVATIONS)
    args = parser.parse_args(argv)

    payload = json.loads(args.source.read_text(encoding="utf-8"))
    rows = payload if isinstance(payload, list) else payload.get("rows", [])
    if not isinstance(rows, list):
        print("Expected a JSON list of rows, or an object with a `rows` list.", file=sys.stderr)
        return 2

    imported, duplicate, refused = import_rows(rows, path=args.path, dry_run=args.dry_run)

    verb = "would import" if args.dry_run else "imported"
    print(f"{verb} {imported}, skipped {duplicate} already present, refused {len(refused)}")

    # Not an error — the ordinal comparisons work without it — but it must not
    # be silent, because it is invisible in the row and costs the metres.
    blank = sum(1 for r in rows if not str(r.get("observer_height_cm") or "").strip())
    if blank:
        print(f"  {blank} row(s) carry no observer height; their approximate "
              "metres cannot be derived. The categories are unaffected.")
    for line in refused:
        print(f"  REFUSED {line}", file=sys.stderr)
    # A refusal is not a failed import: the good rows are in, and the bad ones
    # are named so they can be fixed rather than silently dropped.
    return 1 if refused else 0


if __name__ == "__main__":
    sys.exit(main())
