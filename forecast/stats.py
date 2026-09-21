"""Shared numerical helpers: CSV columns, least squares, RMSE, circular angles.

Stdlib only, like everything else in this repository. Nothing here knows about
beaches or buoys — `verify.py`, `residual.py`, `swell.py`, `dispersion.py` and
`forensics.py` import from it, and it imports from none of them.

The circular helper exists because directions wrap. 359 degrees and 1 degree
are two degrees apart, not 358, so a difference taken the ordinary way is wrong
by a full turn exactly where the interesting readings are.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

#: Every beach in this project is in one timezone, and daily aggregation has to
#: happen in local days rather than UTC days or the "day" straddles two
#: afternoons' sea breeze.
LOCAL_TZ = ZoneInfo("America/Los_Angeles")


def load_column(path: Path, column: str) -> dict[datetime, float]:
    out: dict[datetime, float] = {}
    if not path.exists():
        return out
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            raw = (row.get(column) or "").strip()
            if not raw:
                continue
            try:
                value = float(raw)
                stamp = datetime.strptime(
                    row["timestamp_utc"], "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=timezone.utc)
            except (ValueError, KeyError):
                continue
            out[stamp] = value
    return dict(sorted(out.items()))


def angular_difference(later: float, earlier: float) -> float:
    """Signed degrees from `earlier` to `later`, wrapped to [-180, 180).

    An exact half-turn is equally far in both directions; it resolves to -180.
    Arbitrary, but deterministic, which is what a repeatable comparison needs.
    """

    return (later - earlier + 180.0) % 360.0 - 180.0


def least_squares(rows: list[list[float]], targets: list[float]) -> list[float]:
    """Gauss-Jordan on the normal equations. Stdlib only, like everything here."""

    n, k = len(rows), len(rows[0])
    a = [[sum(rows[i][x] * rows[i][y] for i in range(n)) for y in range(k)] for x in range(k)]
    b = [sum(rows[i][x] * targets[i] for i in range(n)) for x in range(k)]
    for col in range(k):
        pivot = max(range(col, k), key=lambda r: abs(a[r][col]))
        a[col], a[pivot] = a[pivot], a[col]
        b[col], b[pivot] = b[pivot], b[col]
        if abs(a[col][col]) < 1e-12:
            continue
        for row in range(k):
            if row == col:
                continue
            factor = a[row][col] / a[col][col]
            for c in range(col, k):
                a[row][c] -= factor * a[col][c]
            b[row] -= factor * b[col]
    return [b[i] / a[i][i] if abs(a[i][i]) > 1e-12 else 0.0 for i in range(k)]


def rmse(errors: list[float]) -> float:
    return (sum(e * e for e in errors) / len(errors)) ** 0.5 if errors else float("nan")
