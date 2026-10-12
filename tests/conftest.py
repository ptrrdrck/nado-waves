"""Suite-wide fixtures.

One, for time: `forecast.live.build` reads GEFS-Wave's whole ensemble archive
and pairs it with 46232's three-year record on every call, ~8 s of a ~12 s
build, and over a dozen tests build a forecast against the repository's own
data. They read the same files and get the same answer, so the first read is
kept for the session and every later caller gets a copy of it.

Only the repository's own `data/` is kept: no test writes there, and a test
that builds into a `tmp_path` reads its own files every time, as before.
"""

from __future__ import annotations

import pytest

from forecast import ensemble


@pytest.fixture(scope="session", autouse=True)
def _ensemble_read_once():
    real = ensemble.load
    home = ensemble.DEFAULT_DATA_DIR.resolve()
    kept: dict = {}

    def load(data_dir=ensemble.DEFAULT_DATA_DIR, *, spread_only=False):
        from pathlib import Path

        if Path(data_dir).resolve() != home:
            return real(data_dir, spread_only=spread_only)
        if spread_only not in kept:
            kept[spread_only] = real(data_dir, spread_only=spread_only)
        rows, matched = kept[spread_only]
        # Pairs are frozen; rows are flat dicts of strings.
        return [dict(r) for r in rows], list(matched)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(ensemble, "load", load)
        yield
