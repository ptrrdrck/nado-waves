"""The briefing's thresholds hold on the archive they were measured on.

Re-runs `forecast.briefingreport`'s measurements (~1 s) so a constant in
`forecast.briefing` cannot drift below the 85% rule unnoticed as the archive
grows. The doc is a dated report and is not pinned: the archive it measured
grows every collection.
"""

from __future__ import annotations

from forecast import briefing, briefingreport as br


def test_the_change_threshold_holds_on_every_break_and_span():
    heights = br.load_heights()
    for k in range(len(br.BREAKS)):
        for span in br.SPANS_H:
            n, right = br.change_precision(heights, k, span, briefing.CHANGE_SHARE)
            assert n >= 50 and right >= br.RIGHT, (br.BREAKS[k], span, n, right)


def test_the_lead_margin_holds():
    n, right = br.leader_precision(br.load_heights(), briefing.LEAD_MARGIN)
    assert n >= 100 and right >= br.RIGHT


def test_the_period_projection_holds_at_its_horizon():
    errs = br.period_projection()[briefing.PERIOD_AHEAD_H]
    assert errs and sum(abs(e) <= 1.0 for e in errs) / len(errs) >= br.RIGHT


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
