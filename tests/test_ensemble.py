"""GEFS-Wave's ensemble at 46232: matched to the buoy without filling a
missing hour, its spread scored by how often the buoy fell inside it, and the
page given a band only with that score beside it."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from forecast import ensemble

ISO = "%Y-%m-%dT%H:%M:%SZ"
T0 = datetime(2026, 8, 1, tzinfo=timezone.utc)


def row(cycle, lead, mean, spread="0.1", p1="1", p2="0.2"):
    valid = cycle + timedelta(hours=lead)
    return {"cycle_utc": cycle.strftime(ISO), "valid_utc": valid.strftime(ISO),
            "lead_h": str(lead), "hs_mean_m": str(mean), "hs_spread_m": spread,
            "p_col2": p1, "p_col3": p2}


def obs(values: dict):
    """An observations index in the shape `observations` returns."""
    from forecast.verify import _indexed
    return {"wvht": _indexed(values), "dpd": _indexed({}), "mwd": _indexed({})}


def test_an_hour_the_buoy_did_not_report_is_dropped_not_filled():
    rows = [row(T0, 0, 1.0), row(T0, 3, 1.0)]
    got = ensemble.pairs(rows, obs({T0 + timedelta(minutes=26): 1.05}))
    assert [p.lead_h for p in got] == [0]


def test_coverage_counts_the_buoy_inside_one_and_two_spreads():
    rows, seen = [], {}
    for k in range(ensemble.MIN_PAIRS):
        cycle = T0 + timedelta(hours=6 * k)
        rows.append(row(cycle, 30, 1.0, spread="0.1"))
        # A quarter inside one spread, half inside two, the rest outside both.
        miss = (0.05, 0.15, 0.3, 0.3)[k % 4]
        seen[cycle + timedelta(hours=30)] = 1.0 + miss
    got = ensemble.coverage(ensemble.pairs(rows, obs(seen)))
    bucket = next(c for c in got if c["lead_from_h"] == 24)
    assert bucket["n"] == ensemble.MIN_PAIRS
    assert bucket["inside_1"] == 0.25 and bucket["inside_2"] == 0.5
    assert round(bucket["mean_spread_m"], 3) == 0.1


def test_a_thin_bucket_reports_its_count_and_nothing_else():
    rows = [row(T0, 0, 1.0)]
    got = ensemble.coverage(ensemble.pairs(rows, obs({T0: 1.0})))
    first = got[0]
    assert first["n"] == 1 and "inside_1" not in first


def test_a_means_only_row_carries_no_spread_and_is_not_scored():
    rows = [row(T0, 0, 1.0, spread="", p1="", p2="")]
    matched = ensemble.pairs(rows, obs({T0: 1.0}))
    assert matched[0].spread is None and matched[0].p2 is None
    assert ensemble.coverage(matched)[0]["n"] == 0


def test_the_page_gets_the_newest_run_at_or_before_the_model_run_on_screen():
    rows = [row(T0, 0, 1.0), row(T0, 3, 1.1), row(T0, 4, 1.2),
            row(T0 + timedelta(hours=6), 0, 2.0),
            row(T0 - timedelta(hours=6), 0, 0.5, spread="")]
    got = ensemble.for_forecast(rows, [], T0.strftime(ISO))
    assert got["available"] and got["cycle_utc"] == T0.strftime(ISO)
    # Every third hour only, and the shares read by what they hold.
    assert [h["lead_h"] for h in got["hours"]] == [0, 3]
    assert got["hours"][0]["p_gt_2m"] == 0.2 and "p_gt_3m" not in got["hours"][0]
    until = ensemble.for_forecast(rows, [], T0.strftime(ISO),
                                  until_utc=(T0 + timedelta(hours=1)).strftime(ISO))
    assert [h["lead_h"] for h in until["hours"]] == [0]


def test_without_a_spread_there_is_no_band():
    rows = [row(T0, 0, 1.0, spread="")]
    got = ensemble.for_forecast(rows, [], T0.strftime(ISO))
    assert got == {"available": False,
                   "why": "no GEFS-Wave cycle with a spread at or before this run"}


def test_the_shares_are_read_from_the_columns_measured_for_them():
    assert ensemble.P_ABOVE == {1.0: "p_col2", 2.0: "p_col3"}
