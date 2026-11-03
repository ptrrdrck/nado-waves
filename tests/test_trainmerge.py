"""A break's train divided by the buoy's own trains where two carried it
(owner's decision 2026-11-03, BRIEFING §49; forecast.nearshore and
forecast.trainmerge)."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import pytest

from collector.common import DEFAULT_DATA_DIR
from forecast import trainmerge as M
from forecast.nearshore import (BUOY_DIVIDE_SHARE, _buoy_owner, buoy_split, carry, density_grids,
                                load_tables)
from forecast.transform import TRAIN_LOBE_SHARE, at_buoy, floor_trains, load_spectra

NORTH_DAY = datetime(2026, 11, 3, 16, tzinfo=timezone.utc)


@lru_cache(maxsize=1)
def _archive():
    return load_spectra(Path(DEFAULT_DATA_DIR) / "spectra" / "46232")


@lru_cache(maxsize=1)
def _tables():
    return load_tables()


def _at(moment):
    sp = next(s for s in _archive() if s.time == moment).with_spread("mem")
    grids = density_grids(sp)
    return sp, grids, buoy_split(sp, grids)


def test_the_share_is_the_one_that_divides_a_band_by_direction():
    assert BUOY_DIVIDE_SHARE == TRAIN_LOBE_SHARE == 0.2


def test_the_buoy_split_floored_is_the_buoys_own_trains():
    """Read off carry's grid with no floor, then floored, it is at_buoy's
    list to the bin and the arc -- so a break's `buoy` index maps onto the
    trains the Buoys tab names."""

    spectra = _archive()
    for sp in spectra[:: max(1, len(spectra) // 6)][:6]:
        sp = sp.with_spread("mem")
        want = at_buoy(sp).trains
        got = floor_trains(buoy_split(sp))
        assert [(t.bins, t.arc, round(t.period_s, 6)) for t in got] == \
               [(t.bins, t.arc, round(t.period_s, 6)) for t in want]
        assert [t.hs_m for t in got] == pytest.approx([t.hs_m for t in want], rel=1e-9)


def test_north_on_3_november_is_two_swells_not_one():
    """The owner's example: 46232 held a W 18.2 s and an SSW 14.3 s over the
    same periods; North's own split made one row of them, 16.7 s from 228°,
    neither swell's. Divided, it is each swell's own row."""

    sp, grids, split = _at(NORTH_DAY)
    north = _tables()["coronado_north"]
    whole = carry(sp, north, grids)
    assert len(whole.trains) == 1 and round(whole.trains[0].from_deg) == 228
    rows = carry(sp, north, grids, split).trains
    assert len(rows) == 2
    ssw = next(t for t in rows if t.from_deg < 230)
    w = next(t for t in rows if t.from_deg > 240)
    assert round(ssw.period_s, 1) == 14.3 and ssw.hs_m == pytest.approx(1.03, abs=0.01)
    assert w.hs_m == pytest.approx(0.69, abs=0.01)
    assert split[ssw.buoy].from_deg < 230 < split[w.buoy].from_deg
    # The two rows are the row they came from, in energy, less the buoy's
    # 7.7 s wind sea's 3% of it: a piece under the floors leaves the list,
    # as a band under them does.
    assert 0.95 * whole.trains[0].hs_m ** 2 < ssw.hs_m ** 2 + w.hs_m ** 2 < whole.trains[0].hs_m ** 2


def test_the_heights_never_change_and_a_row_one_buoy_train_carried_is_untouched():
    sp, grids, split = _at(NORTH_DAY)
    for b, table in _tables().items():
        whole, divided = carry(sp, table, grids), carry(sp, table, grids, split)
        assert divided.hs_ref == whole.hs_ref and divided.hs_equivalent == whole.hs_equivalent
    center = _tables()["coronado_center"]
    a, b = carry(sp, center, grids).trains, carry(sp, center, grids, split).trains
    assert [(t.hs_m, t.period_s, t.from_deg, t.bins, t.held) for t in a] == \
           [(t.hs_m, t.period_s, t.from_deg, t.bins, t.held) for t in b]
    assert all(t.buoy is not None for t in b)


def test_a_divided_row_is_one_buoy_trains_energy_and_nothing_else():
    sp, grids, split = _at(NORTH_DAY)
    table = _tables()["coronado_north"]
    rays = M._rays(sp, table, grids)
    owner = _buoy_owner(split)
    owners = [owner(i, int(d) % 360) for i, d, _, _ in rays]
    rows = M._rows(sp, table, grids, split, "divided at 20%")
    one = lambda m: [rays[m][2] if owners[m] == j else 0.0 for j in range(len(split))]
    for (t, whole), c in zip(rows, M._contents(rays, owners, rows, len(split), one)):
        assert not whole
        assert c[t.buoy] == pytest.approx(sum(c)) and 4 * math.sqrt(sum(c)) == pytest.approx(t.hs_m, rel=1e-6)


def test_the_control_still_reads_as_measured():
    """North's case, an SSW groundswell under a long W swell 72° and 4 s
    apart: where the buoy parted them, dividing leaves a swell without a row
    of its own far less often than keeping rows whole."""

    S = M.control(trials=6, cases=[((1.0, 14, 200, 12), (1.0, 18, 272, 15))], workers=1,
                  singles=False)
    group = "3 s or more and 60° or more apart, the buoy parted them"
    whole, divided = S[(group, "whole")], S[(group, "divided at 20%")]
    assert whole["break-hours"] >= 6
    hide = "a swell >= 20% leads no row"
    assert divided[hide] < whole[hide]
    assert divided["rows"] > whole["rows"]
    # Where the buoy did not part them, there is nothing to divide by.
    other = "3 s or more and 60° or more apart, the buoy did not"
    assert dict(S[(other, "whole")]) == dict(S[(other, "divided at 20%")])


def test_rows_of_one_swell_carry_it_and_what_it_was_at_the_buoy():
    """For the page's bracket and tap (owner's call, 2026-11-03): every row
    names its swell, and only rows that share one say what it was at the
    buoy. Center at 3 Nov 15Z: the W 18.2 s reaches it as two rows."""

    from forecast.nearshore import train_dicts

    sp, grids, split = _at(datetime(2026, 11, 3, 15, tzinfo=timezone.utc))
    near = carry(sp, _tables()["coronado_center"], grids, split)
    rows = train_dicts(near.trains[:3], near.buoy)
    swells = [r["swell"] for r in rows]
    assert len(rows) == 3 and swells[0] == swells[2] != swells[1]
    shared = [r for r in rows if "swell_at_buoy" in r]
    assert shared == [rows[0], rows[2]]
    assert shared[0]["swell_at_buoy"] == {"period_s": 18.2, "from_deg": 273, "lobes": []}
    # Without the buoy's split, nothing is said.
    assert all("swell" not in r for r in train_dicts(carry(sp, _tables()["coronado_center"], grids).trains))
