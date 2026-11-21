"""forecast.westerlygap: the 'then' chain is the chain BRIEFING §56 measured."""

from datetime import datetime, timezone

import pytest

from forecast import now as live
from forecast import westerlygap as W
from forecast.fillshift import nearest_rule
from forecast.nearshore import load_tables
from forecast.surfzone import load_profiles
from forecast.transform import load_spectra


@pytest.fixture(scope="module")
def hour_22z():
    at = datetime(2026, 11, 17, 22, tzinfo=timezone.utc)
    got = [s for s in load_spectra(W.ROOT / "data" / "spectra" / "46232") if s.time == at]
    assert got, "17 Nov 22Z is in the tracked archive"
    return got[0]


def test_then_gives_back_s56_step_table(hour_22z):
    profiles = load_profiles()
    with W._chain("then") as chain:
        tables = {b: nearest_rule(t) for b, t in load_tables().items()}      # the fill of 17 Nov
        got = chain.build(now=hour_22z.time, spectrum=hour_22z, as_of=True, tables=tables,
                          profiles={b: p.inshore() for b, p in profiles.items()})
    # To §56's printed precision: it printed 2.135 m as 2.14.
    keys = [k for _, k in W.STEPS[:5]]
    for brk in got.breaks:
        row = W._row(brk)
        printed = W.S56_22Z[brk.id]
        for key, want in zip(keys, printed[:5]):
            assert row[key] == pytest.approx(want, abs=0.005 + 1e-9), (brk.id, key)
        assert row["hs"] == pytest.approx(printed[5], abs=0.005 + 1e-9), brk.id


def test_chain_puts_now_back():
    carry, local = live.carry, live.local_sea
    for variant in W.VARIANTS:
        with pytest.raises(RuntimeError):
            with W._chain(variant):
                raise RuntimeError
        assert live.carry is carry and live.local_sea is local
