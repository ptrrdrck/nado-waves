"""The beach observation log, and the control that is supposed to kill it.

The log is the series every accuracy claim in this project waits on, so the
tests that matter are the ones about what it REFUSES: a coerced value, an
invented height, an absence recorded as a flat day. A verification series that
tidies up its own inputs is not a record of what was seen.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from collector.beachlog import (
    BODY_SCALE,
    SCALE_FRACTIONS,
    BeachLogError,
    Observation,
    append,
    compose,
    known_breaks,
    load,
    new_session,
    validate,
)
from collector.common import to_iso, utcnow
from forecast.beachverify import (
    Session,
    check,
    discriminates,
    open_breaks,
    report,
    sessions,
    which_edge,
)

BREAKS = ["coronado_north", "coronado_center", "coronado_south"]


def entry(**kwargs) -> Observation:
    base = dict(
        session_id="s1",
        observed_utc=to_iso(utcnow()) or "",
        logged_utc=to_iso(utcnow()) or "",
        break_id="coronado_center",
        observer="pete",
        method="from_sand",
        minutes_watched="10",
        saw_sets="true",
        typical="chest",
        sets="head",
        typical_ft="",
        sets_ft="",
        confidence="high",
        wind="glassy",
        rideable="yes",
        forecast_seen="false",
        note="",
    )
    base.update(kwargs)
    return Observation(**base)


# --- what the log refuses --------------------------------------------------


def test_an_observation_against_an_unknown_break_is_refused():
    """It could not be compared to anything, so it is not stored."""

    with pytest.raises(BeachLogError, match="not in spots.json"):
        validate(entry(break_id="trestles"))


def test_sets_smaller_than_typical_is_refused_not_swapped():
    """Sets are the occasional BIGGER waves. Swapping them would invent data."""

    with pytest.raises(BeachLogError, match="smaller than typical"):
        validate(entry(typical="head", sets="knee"))


def test_an_anonymous_observation_is_refused():
    with pytest.raises(BeachLogError, match="observer"):
        validate(entry(observer="  "))


def test_a_future_observation_is_refused():
    ahead = to_iso(utcnow() + timedelta(hours=2))
    with pytest.raises(BeachLogError, match="future"):
        validate(entry(observed_utc=ahead))


def test_an_unknown_category_is_refused_rather_than_guessed():
    with pytest.raises(BeachLogError, match="not one of"):
        validate(entry(typical="biggish"))


def test_there_is_no_way_to_record_not_having_looked():
    """CLAUDE.md: never infer, interpolate or substitute a missing observation.

    `flat` means the ocean was flat and somebody checked. Not looking is a gap,
    and a gap must stay a gap — in verification exactly as in the archive. So
    the scale offers no "unknown", "skipped" or "didn't go" value to hide an
    absence in.
    """

    assert "flat" in BODY_SCALE
    for absence in ("unknown", "skipped", "none", "na", "n/a", "didnt_look"):
        assert absence not in BODY_SCALE
        with pytest.raises(BeachLogError):
            validate(entry(typical=absence))


def test_a_flat_day_needs_no_sets_and_none_are_invented():
    validated = validate(entry(typical="flat", sets=""))
    assert validated.sets == ""


# --- what the log derives, and what it refuses to derive --------------------


def test_height_is_none_without_a_measured_observer_height():
    """Not a default height standing in for a measurement nobody took."""

    typical, sets = entry().height_m(None)
    assert typical is None and sets is None


def test_height_is_derived_from_the_category_never_stored():
    observed = entry(typical="head", sets="overhead")
    typical, sets = observed.height_m(180.0)
    assert typical == pytest.approx(1.80)
    assert sets == pytest.approx(2.25)
    # The stored row carries the category. The metres exist only on read.
    assert "1.8" not in str(observed.typical)
    assert observed.typical == "head"


def test_every_category_has_a_fraction_and_they_are_ordered():
    assert set(SCALE_FRACTIONS) == set(BODY_SCALE)
    values = [SCALE_FRACTIONS[c] for c in BODY_SCALE]
    assert values == sorted(values), "the body scale must increase monotonically"


# --- round trip ------------------------------------------------------------


def test_append_and_load_round_trip(tmp_path):
    path = tmp_path / "observations.csv"
    append(entry(break_id="coronado_north", typical="waist", sets="chest"), path=path)
    append(entry(break_id="coronado_south", typical="chest", sets="head"), path=path)

    rows = load(path=path)
    assert len(rows) == 2
    assert {r.break_id for r in rows} == {"coronado_north", "coronado_south"}
    assert rows[0].observer == "pete"


def test_the_breaks_come_from_spots_json_so_the_files_cannot_drift():
    for break_id in BREAKS:
        assert break_id in known_breaks()


# --- the interactive entry path --------------------------------------------


def test_compose_never_asks_for_the_tide():
    """Tide is deterministic from the timestamp and NOAA 9410170.

    Asking a person for it adds a field that gets guessed or skipped and buys
    nothing the clock does not already give.
    """

    answers = iter(["c", "h", "g", "s", "y", "h", "12", "y", "n", ""])
    composed = compose("coronado_center", "pete", session_id="s1", reader=lambda _: next(answers))

    assert composed.typical == "chest"
    assert composed.sets == "head"
    assert composed.wind == "glassy"
    assert composed.forecast_seen == "false"
    assert not hasattr(composed, "tide")


def test_a_flat_day_skips_the_sets_question_entirely():
    """One fewer prompt on the day it obviously does not apply."""

    answers = iter(["f", "n", "c", "n", "l", "3", "n", "n", "nothing"])
    composed = compose("coronado_north", "pete", session_id="s1", reader=lambda _: next(answers))
    assert composed.typical == "flat"
    assert composed.sets == ""


def test_seeing_a_forecast_flags_the_entry_rather_than_rejecting_it():
    answers = iter(["c", "h", "g", "s", "y", "h", "10", "y", "y", ""])
    composed = compose("coronado_center", "pete", session_id="s1", reader=lambda _: next(answers))
    assert composed.forecast_seen == "true"


# --- the geometry test, and its controls -----------------------------------


def session(sid: str, sizes: dict[str, str]) -> Session:
    return Session(sid, [entry(session_id=sid, break_id=b, typical=t, sets="") for b, t in sizes.items()])


def test_only_some_days_discriminate():
    """A swell inside every window predicts nothing and is a control, not evidence."""

    assert not discriminates(210.0, BREAKS)  # open to all three
    assert not discriminates(265.0, BREAKS)  # blocked at all three
    assert discriminates(245.0, BREAKS)      # north cut off
    assert discriminates(200.0, BREAKS)      # south cut off


def test_the_two_window_edges_predict_opposite_orderings():
    """The sharpest control available, and it is free.

    A confound — a sandbar, where the observer stands, the order they walk the
    beach — produces a CONSISTENT ordering, so it agrees on one edge and
    disagrees on the other. Only a real aperture effect flips with the swell.
    """

    assert which_edge(245.0, BREAKS) == "west"   # Point Loma: south bigger
    assert which_edge(200.0, BREAKS) == "east"   # Islands: north bigger
    assert which_edge(210.0, BREAKS) is None     # no prediction

    assert "coronado_north" not in open_breaks(245.0, BREAKS)
    assert "coronado_south" not in open_breaks(200.0, BREAKS)


def test_the_geometry_is_confirmed_when_the_ordering_matches():
    west = session("w", {"coronado_north": "knee", "coronado_south": "head"})
    assert check(west, 245.0) == "agree"

    east = session("e", {"coronado_north": "head", "coronado_south": "knee"})
    assert check(east, 200.0) == "agree"


def test_the_geometry_is_contradicted_when_it_does_not():
    backwards = session("b", {"coronado_north": "head", "coronado_south": "knee"})
    assert check(backwards, 245.0) == "disagree"


def test_a_control_day_returns_no_verdict_and_is_not_counted_as_agreement():
    """The failure this prevents: banking a confirmation from a day that
    predicted nothing, which would make the agreement rate meaningless."""

    quiet = session("c", {"coronado_north": "knee", "coronado_south": "head"})
    assert check(quiet, 210.0) is None


def test_a_fixed_bias_agrees_on_one_edge_and_disagrees_on_the_other():
    """The control doing its job on a synthetic confound.

    An observer whose south end always reads bigger — a sandbar, or simply
    checking it last when the light has changed — agrees with the geometry on
    west-edge days and contradicts it on east-edge days. A real aperture effect
    agrees on both. This is what separates them, and it is why agreement on one
    edge alone is not evidence.
    """

    always_south_bigger = {"coronado_north": "knee", "coronado_south": "head"}

    west = check(session("w", always_south_bigger), 245.0)
    east = check(session("e", always_south_bigger), 200.0)

    assert west == "agree"
    assert east == "disagree"
    assert west != east, "a fixed bias must not agree on both edges"


def test_the_report_refuses_to_characterise_a_thin_series():
    """CLAUDE.md: no accuracy figure without naming the series behind it.

    Three sessions is not a series, and the report must say counts rather than
    a rate that reads like skill.
    """

    entries = [
        e
        for sid, bearing in (("a", 245.0), ("b", 245.0))
        for e in session(sid, {"coronado_north": "knee", "coronado_south": "head"}).entries
    ]
    stamp = entries[0].observed_utc[:13]
    text = "\n".join(report(entries, {stamp: 245.0}))

    assert "Too few discriminating sessions" in text
    assert "No rate, no accuracy figure, no claim" in text
    assert "%" not in text.split("### ")[0]


def test_the_report_says_so_when_only_one_edge_has_been_seen():
    entries = session("a", {"coronado_north": "knee", "coronado_south": "head"}).entries
    text = "\n".join(report(entries, {entries[0].observed_utc[:13]: 245.0}))

    assert "Only west-edge days so far" in text
    assert "the ordering REVERSES" in text


def test_an_empty_log_says_the_project_is_unfalsifiable():
    text = "\n".join(report([], {}))
    assert "log is empty" in text
    assert "unfalsifiable" in text


def test_sessions_needs_two_breaks_to_be_comparable():
    single = [entry(session_id="x", break_id="coronado_center")]
    assert sessions(single) == []

    pair = [
        entry(session_id="y", break_id="coronado_north"),
        entry(session_id="y", break_id="coronado_south"),
    ]
    assert len(sessions(pair)) == 1


def test_ranking_is_ordinal_and_needs_no_height_conversion():
    """Immune to the observer's sense of 'chest high' drifting, as long as it
    drifts the same way at both breaks half an hour apart."""

    ranked = session("r", {
        "coronado_north": "waist", "coronado_center": "chest", "coronado_south": "head",
    }).ranking()
    assert [b for b, _ in ranked] == ["coronado_south", "coronado_center", "coronado_north"]


def test_new_sessions_are_distinct():
    assert new_session() != new_session()
