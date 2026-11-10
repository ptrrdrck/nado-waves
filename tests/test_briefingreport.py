"""The briefing's thresholds, against the archive they were measured on.

Re-runs `forecast.briefingreport`'s measurements (~1 s). The doc is a dated
report and is not pinned: the archive it measured grows every collection.

The 2026-10-17 design's three measured words -- rose / dropped, which break
leads, a ridge's period ahead -- are no longer said (CLAUDE.md, the
Briefing). Their constants stay in `forecast.briefing` for the report only,
so their hit rates are REPORTED here, never asserted against the 85% rule
(owner's call, 2026-11-10, after North's 6 h rose / dropped slid from 88.8%
on 18 Oct to 84.98% on 8 Nov, 215 of 253, and the test flipped with every
collection). What is asserted is that nothing live reads them. If one of
those words returns, its 85% assertion returns with it.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

from forecast import briefing, briefingreport as br

ROOT = Path(__file__).resolve().parent.parent

#: Kept in `forecast.briefing` for the report, read by nothing live.
REPORT_ONLY = ("CHANGE_SHARE", "MIN_SPAN_H", "LEAD_MARGIN", "PERIOD_AHEAD_H")


def test_the_retired_thresholds_drive_nothing_live():
    """Each is defined once in briefing.py and read only by the report:
    no other module, workflow or page names it."""

    sources = [*ROOT.glob("forecast/*.py"), *ROOT.glob("collector/*.py"),
               *ROOT.glob("app/*.html"), *ROOT.glob(".github/workflows/*.yml")]
    for name in REPORT_ONLY:
        word = re.compile(rf"\b{name}\b")
        readers = {p.name for p in sources if word.search(p.read_text(encoding="utf-8"))}
        assert readers <= {"briefing.py", "briefingreport.py"}, (name, readers)
        defined = [line for line in (ROOT / "forecast" / "briefing.py").read_text(encoding="utf-8").splitlines()
                   if word.search(line)]
        assert defined == [f"{name} = {getattr(briefing, name)!r}"], (name, defined)


def test_the_retired_thresholds_are_still_measured():
    """Reported, not asserted against RIGHT: each case still fires and
    scores, so the report's tables stay filled."""

    heights = br.load_heights()
    for k in range(len(br.BREAKS)):
        for span in br.SPANS_H:
            n, right = br.change_precision(heights, k, span, briefing.CHANGE_SHARE)
            assert n > 0 and 0.0 <= right <= 1.0, (br.BREAKS[k], span, n, right)
    n, right = br.leader_precision(heights, briefing.LEAD_MARGIN)
    assert n > 0 and 0.0 <= right <= 1.0
    errs = br.period_projection()[briefing.PERIOD_AHEAD_H]
    assert errs and all(math.isfinite(e) for e in errs)


def test_the_wind_habit_stays_out_while_it_fails():
    """If winter's archive makes it pass, the briefing may carry it: this
    test is what says so."""

    habit = br.wind_habit()
    assert all(hits / n < br.RIGHT for hits, n in habit.values() if n)
    assert not hasattr(briefing, "WIND_HABIT")


def test_long_period_energy_stays_out_while_it_fails():
    """Measured 2026-10-27 at the owner's request, on one autumn: 46232's
    long-period energy doubling comes before a bigger beach no more often
    than any hour does. If winter's archive makes a row pass, the briefing
    may carry it: this test is what says so."""

    for row in br.long_period_ahead():
        for name in ("rise", "bigger"):
            hits, n = row[name]
            assert not n or hits / n < br.RIGHT, (row, name)
    assert not hasattr(briefing, "LONG_PERIOD_AHEAD")
