"""The train-split report (BRIEFING §40): its control has a known answer, so it
is held to it, and the old rule it compares against is put back after use."""

from __future__ import annotations

import pytest

from forecast import trainsplit as TS
from forecast import transform as T


@pytest.fixture(scope="module")
def freqs():
    return T.load_spectra(TS.DEFAULT_DATA_DIR / "spectra" / "46232", limit=1)[0].frequencies


def test_a_single_clean_swell_stays_one_train(freqs):
    """The case that sank the 10° watershed: maximum entropy reads one swell as
    two peaks, and noise lets a fine split keep them."""

    hits = [TS.trial(freqs, "one swell, 20° wide", 32, seed, {"shipped": TS.shipped})["shipped"]
            for seed in range(8)]
    assert sum(hits) >= 7


def test_the_combo_is_divided_where_period_alone_could_not(freqs):
    found = {"shipped": 0, "period only": 0}
    for seed in range(8):
        r = TS.trial(freqs, "S 15 s + NW 12 s + sea", 32, seed,
                     {"shipped": TS.shipped, "period only": TS.period_only})
        for k in found:
            found[k] += r[k]
    assert found["shipped"] > found["period only"]


def test_the_old_rule_is_put_back(freqs):
    before = T.PROMINENCE, T.BAND_SMOOTH
    TS.trial(freqs, "one swell, 15° wide", 32, 1, {"period only": TS.period_only})
    assert (T.PROMINENCE, T.BAND_SMOOTH) == before
