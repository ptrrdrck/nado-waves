"""Print fresh Observe codes: two Coronado streets and a house number.

    python3 service/observe/newcode.py                # one code
    python3 service/observe/newcode.py o01 o02 o03    # CODES, ready to paste

Prints to the terminal only and writes no file: a code goes in no file in
either repository (docs/design/observe.md). With observer ids it prints the
whole CODES secret as JSON, for `npx wrangler secret put CODES`; keep your own
copy in a password manager, because adding or revoking one person later means
putting the whole map again.

Each code is two different streets from streets.txt and a house number, all
chosen by `secrets`, e.g. glorietta-adella-1121. The list is public; the
strength is the random choice. The number has four digits while that gives
at least 2^24 codes, five when the list is too short for four, and the script
refuses when even five are not enough. With the service's limit on tries
(observe.js LIMITS: 200 wrong tries an hour across every client) 2^24 codes
take more than nine years of guessing to cover.
"""

from __future__ import annotations

import json
import math
import re
import secrets
import sys
from pathlib import Path

STREETS = Path(__file__).resolve().parent / "streets.txt"
FLOOR = 2 ** 24
#: As the worker's OBSERVER_ID: a short id, never a name.
OBSERVER_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,23}$")
WORD = re.compile(r"^[a-z]+$")


class CodeError(ValueError):
    pass


def streets(path: Path = STREETS) -> list[str]:
    names, seen = [], set()
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        word = line.split("#", 1)[0].strip()
        if not word:
            continue
        if not WORD.match(word):
            raise CodeError(f"{path.name} line {n}: {word!r} is not one lowercase word")
        if word in seen:
            raise CodeError(f"{path.name} line {n}: {word!r} is listed twice")
        seen.add(word)
        names.append(word)
    return names


def digits_for(n_streets: int) -> int:
    """The fewest house-number digits (4 or 5) that give FLOOR codes."""

    for digits in (4, 5):
        numbers = 9 * 10 ** (digits - 1)
        if n_streets * (n_streets - 1) * numbers >= FLOOR:
            return digits
    raise CodeError(f"{n_streets} streets give fewer than 2^24 codes even with five-digit "
                    f"numbers; add streets to {STREETS.name}")


def space(n_streets: int) -> int:
    return n_streets * (n_streets - 1) * 9 * 10 ** (digits_for(n_streets) - 1)


def new_code(names: list[str]) -> str:
    digits = digits_for(len(names))
    first = secrets.choice(names)
    second = secrets.choice([s for s in names if s != first])
    number = 10 ** (digits - 1) + secrets.randbelow(9 * 10 ** (digits - 1))
    return f"{first}-{second}-{number}"


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    try:
        names = streets()
        for oid in argv:
            if not OBSERVER_ID.match(oid):
                raise CodeError(f"{oid!r}: an observer id is short and lowercase, like o01, never a name")
        if len(set(argv)) != len(argv):
            raise CodeError("an observer id is given twice")
        bits = math.log2(space(len(names)))
    except CodeError as exc:
        print(f"newcode: {exc}", file=sys.stderr)
        return 2
    print(f"{len(names)} streets, {digits_for(len(names))}-digit numbers: "
          f"{space(len(names)):,} possible codes ({bits:.1f} bits)", file=sys.stderr)
    if not argv:
        print(new_code(names))
        return 0
    issued: set[str] = set()
    pairs = {}
    for oid in argv:
        code = new_code(names)
        while code in issued:
            code = new_code(names)
        issued.add(code)
        pairs[code] = oid
    for code, oid in pairs.items():
        print(f"{oid:<8} {code}", file=sys.stderr)
    print(json.dumps(pairs, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
