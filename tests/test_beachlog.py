"""The beach observation log, and the control that is supposed to kill it.

The log is the series every accuracy claim in this project waits on, so the
tests that matter are the ones about what it REFUSES: a coerced value, an
invented height, an absence recorded as a flat day. A verification series that
tidies up its own inputs is not a record of what was seen.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

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
        entry_id="e" + str(abs(hash(str(kwargs))) % 10**9),
        session_id="s1",
        observed_utc=to_iso(utcnow()) or "",
        logged_utc=to_iso(utcnow()) or "",
        break_id="coronado_center",
        observer="pete",
        observer_id="pete",
        observer_height_cm="180",
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
        is_test="",
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
    composed = compose("coronado_center", "pete", session_id="s1", heights={"pete": 180.0},
                       reader=lambda _: next(answers))

    assert composed.typical == "chest"
    assert composed.sets == "head"
    assert composed.wind == "glassy"
    assert composed.forecast_seen == "false"
    assert not hasattr(composed, "tide")


def test_a_flat_day_skips_the_sets_question_entirely():
    """One fewer prompt on the day it obviously does not apply."""

    answers = iter(["f", "n", "c", "n", "l", "3", "n", "n", "nothing"])
    composed = compose("coronado_north", "pete", session_id="s1", heights={"pete": 180.0},
                       reader=lambda _: next(answers))
    assert composed.typical == "flat"
    assert composed.sets == ""


def test_seeing_a_forecast_flags_the_entry_rather_than_rejecting_it():
    answers = iter(["c", "h", "g", "s", "y", "h", "10", "y", "y", ""])
    composed = compose("coronado_center", "pete", session_id="s1", heights={"pete": 180.0},
                       reader=lambda _: next(answers))
    assert composed.forecast_seen == "true"


# --- the geometry test, and its controls -----------------------------------


def session(sid: str, sizes: dict[str, str]) -> Session:
    return Session(sid, [entry(session_id=sid, break_id=b, typical=t, sets="") for b, t in sizes.items()])


def test_only_some_days_discriminate():
    """A swell inside every window predicts nothing and is a control, not evidence."""

    assert not discriminates(210.0, BREAKS)  # open to all three
    assert not discriminates(265.0, BREAKS)  # blocked at all three
    assert discriminates(245.0, BREAKS)      # north cut off
    assert discriminates(194.0, BREAKS)      # south cut off


def test_the_two_window_edges_predict_opposite_orderings():
    """The sharpest control available, and it is free.

    A confound — a sandbar, where the observer stands, the order they walk the
    beach — produces a CONSISTENT ordering, so it agrees on one edge and
    disagrees on the other. Only a real aperture effect flips with the swell.
    """

    assert which_edge(245.0, BREAKS) == "west"   # Point Loma: south bigger
    assert which_edge(194.0, BREAKS) == "east"   # Islands: north bigger
    assert which_edge(210.0, BREAKS) is None     # no prediction

    assert "coronado_north" not in open_breaks(245.0, BREAKS)
    assert "coronado_south" not in open_breaks(194.0, BREAKS)


def test_charting_baja_and_the_islands_added_discriminating_bands():
    """The control got sharper on 2026-09-20, and it did so without a single
    observation being logged.

    It used to rest on two edges, one per ordering. Splitting the Coronado
    Islands at their channel and adding the Baja coast gives six bands:
    165.0-168.5 east, 187.5-191.5 west, 193.0-197.0 east, 199.0-201.0 west,
    201.0-205.5 east, 242.5-260.0 west. Both orderings now appear at more
    than one edge, so a confound has to survive several independent flips
    rather than one.

    The 165-168.5 band is the Baja tangent, and it is the only one in the
    file whose width is set by a coordinate south of the border.
    """

    east = [b / 2.0 for b in range(320, 540)
            if which_edge(b / 2.0, BREAKS) == "east"]
    west = [b / 2.0 for b in range(320, 540)
            if which_edge(b / 2.0, BREAKS) == "west"]
    assert east and west
    # The Baja tangent band, which did not exist before the coast was charted.
    assert any(165.0 <= b <= 168.5 for b in east)
    # And Point Loma's, which has been there all along.
    assert any(242.5 <= b <= 260.0 for b in west)


def test_the_geometry_is_confirmed_when_the_ordering_matches():
    west = session("w", {"coronado_north": "knee", "coronado_south": "head"})
    assert check(west, 245.0) == "agree"

    east = session("e", {"coronado_north": "head", "coronado_south": "knee"})
    assert check(east, 194.0) == "agree"


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
    east = check(session("e", always_south_bigger), 194.0)

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


# --- importing from the phone form -----------------------------------------


def test_importing_the_same_export_twice_does_not_double_count(tmp_path):
    """The failure this prevents is subtle and would not look like an error.

    A session is the unit the geometry test compares against itself. A
    duplicated break inside one would read as a genuine second look at the same
    spot and quietly weight it twice.
    """

    from collector.beachlog_import import import_rows

    path = tmp_path / "observations.csv"
    rows = [
        {"entry_id": "a1", "session_id": "s9", "break_id": "coronado_north",
         "observer": "pete", "observer_id": "pete", "observer_height_cm": "180", "typical": "waist", "sets": "chest",
         "wind": "glassy", "rideable": "yes", "method": "from_sand",
         "confidence": "high", "observed_utc": to_iso(utcnow()),
         "logged_utc": to_iso(utcnow()), "minutes_watched": "10",
         "saw_sets": "true", "forecast_seen": "false", "is_test": "", "note": ""},
    ]

    first = import_rows(rows, path=path)
    second = import_rows(rows, path=path)

    assert first[0] == 1 and first[1] == 0
    assert second[0] == 0 and second[1] == 1, "the second import must recognise the row"
    assert len(load(path=path)) == 1


def test_a_bad_row_is_refused_by_name_and_the_good_ones_still_land(tmp_path):
    """One malformed entry from someone else's phone must not cost the rest."""

    from collector.beachlog_import import import_rows

    path = tmp_path / "observations.csv"
    good = {"entry_id": "g1", "session_id": "s1", "break_id": "coronado_south",
            "observer": "pete", "observer_id": "pete", "observer_height_cm": "180", "typical": "chest", "sets": "head",
            "wind": "glassy", "rideable": "yes", "method": "from_sand",
            "confidence": "high", "observed_utc": to_iso(utcnow()),
            "logged_utc": to_iso(utcnow()), "minutes_watched": "5",
            "saw_sets": "true", "forecast_seen": "false", "is_test": "", "note": ""}
    bad = dict(good, entry_id="b1", break_id="trestles")

    imported, duplicate, refused = import_rows([good, bad], path=path)

    assert imported == 1
    assert len(refused) == 1 and "trestles" in refused[0]
    assert [e.entry_id for e in load(path=path)] == ["g1"]


def test_import_tolerates_extra_keys_the_form_sends(tmp_path):
    """The form may grow a field before this file knows about it."""

    from collector.beachlog_import import import_rows

    path = tmp_path / "observations.csv"
    row = {"entry_id": "x1", "session_id": "s1", "break_id": "coronado_center",
           "observer": "pete", "observer_id": "pete", "observer_height_cm": "180", "typical": "knee", "sets": "",
           "wind": "onshore", "rideable": "no", "method": "from_window",
           "confidence": "low", "observed_utc": to_iso(utcnow()),
           "logged_utc": to_iso(utcnow()), "minutes_watched": "2",
           "saw_sets": "false", "forecast_seen": "false", "is_test": "", "note": "",
           "some_future_field": "whatever", "app_version": "3"}

    imported, _, refused = import_rows([row], path=path)
    assert imported == 1 and not refused


def test_the_observer_id_survives_a_rename(tmp_path):
    """The generic names are placeholders and will be edited.

    Keying the series on a name would orphan every earlier row the moment
    `observer2` becomes a real person's name.
    """

    from collector.beachlog_import import import_rows

    path = tmp_path / "observations.csv"
    base = {"session_id": "s1", "break_id": "coronado_north", "observer_id": "obs2",
            "observer_height_cm": "175",
            "typical": "waist", "sets": "", "wind": "glassy", "rideable": "yes",
            "method": "from_sand", "confidence": "high",
            "observed_utc": to_iso(utcnow()), "logged_utc": to_iso(utcnow()),
            "minutes_watched": "10", "saw_sets": "true", "forecast_seen": "false", "is_test": "", "note": ""}

    import_rows([dict(base, entry_id="r1", observer="observer2")], path=path)
    import_rows([dict(base, entry_id="r2", observer="Jake")], path=path)

    rows = load(path=path)
    assert {r.observer for r in rows} == {"observer2", "Jake"}
    assert {r.observer_id for r in rows} == {"obs2"}, "one person, one durable key"


# --- the two published builds ----------------------------------------------


def test_the_two_form_builds_differ_only_in_their_title():
    """One source, two artifacts, and no build step to keep them in step.

    `app/beachlog.html` is published with the `db` capability and is Pete's
    page; `app/beachlog-observer.html` is published without it, for helpers who
    are not signing in to anything. They are the same file because the schema
    they write is the same schema, and two hand-maintained copies would drift
    the moment one of them gained a field.

    Only the <title> may differ, so the two are told apart in a gallery. If this
    fails, copy the owner build over the observer build and re-apply the title
    rather than patching them separately.
    """

    owner = Path("app/beachlog.html").read_text(encoding="utf-8").splitlines()
    observer = Path("app/beachlog-observer.html").read_text(encoding="utf-8").splitlines()

    strip = lambda lines: [ln for ln in lines if not ln.lstrip().startswith("<title>")]
    assert strip(owner) == strip(observer), "the two form builds have drifted apart"

    titles = [ln for ln in observer if ln.lstrip().startswith("<title>")]
    assert titles and "Observer" in titles[0], "the observer build needs its own name"


def test_the_form_never_fetches_anything():
    """The no-forecast rule, enforced against the file rather than stated in it.

    An observer who has already seen a forecast is not an independent witness.
    The page therefore has no way to show one: no network call of any kind, so
    there is nothing for a future edit to quietly point at a surf API.
    """

    page = Path("app/beachlog.html").read_text(encoding="utf-8")
    for reaching_out in ("fetch(", "XMLHttpRequest", "WebSocket", "EventSource",
                         "import(", "<iframe", "navigator.sendBeacon"):
        assert reaching_out not in page, f"the form reaches the network via {reaching_out}"


def test_the_form_offers_no_way_to_record_not_having_looked():
    """The same rule as the CSV, checked where an observer actually taps."""

    page = Path("app/beachlog.html").read_text(encoding="utf-8")
    scale = page.split('var SCALE = [')[1].split('];')[0]
    assert '"flat"' in scale
    for absence in ('"unknown"', '"skipped"', '"none"', '"didnt_look"', '"na"'):
        assert absence not in scale


# --- the observer's own height, carried on the row -------------------------


def test_the_height_rides_on_the_row_not_a_lookup_table():
    """Observers set their height on their own phone, and it lives nowhere else.

    A lookup table in this repository would be permanently empty for everyone
    but Pete, so the body scale would have no calibration for exactly the
    entries that most need it. Carrying it on the row also means a later
    re-measurement never silently rewrites what an old observation was judged
    against.
    """

    row = entry(observer_height_cm="180", typical="head")
    assert row.height_cm == 180.0
    typical, _ = row.height_m(row.height_cm)
    assert typical == pytest.approx(1.80)


def test_an_implausible_height_is_refused():
    with pytest.raises(BeachLogError, match="outside 100-230"):
        validate(entry(observer_height_cm="12"))
    with pytest.raises(BeachLogError, match="not a number"):
        validate(entry(observer_height_cm="tall"))


def test_a_missing_height_is_allowed_and_costs_only_the_metres():
    """Deliberate, and the opposite of what it looks like.

    Every comparison this log actually makes is ordinal and works perfectly
    without a height — the height only feeds the approximate metres, which the
    form itself labels a reading aid. Refusing the row would throw away a real
    observation to protect a derived convenience. The form is where the rule is
    enforced; the archive's job is to keep what was seen.
    """

    row = validate(entry(observer_height_cm=""))
    assert row.height_cm is None
    assert row.height_m(None) == (None, None)
    # And it is still a usable observation.
    assert row.typical == "chest"


def test_the_cli_refuses_to_log_for_an_observer_with_no_height():
    """The CLI's equivalent of the form's gate."""

    with pytest.raises(BeachLogError, match="no standing height"):
        compose("coronado_center", "ghost", session_id="s1", heights={},
                reader=lambda _: "c")


def test_import_reports_rows_that_arrive_without_a_height(tmp_path, capsys):
    from collector.beachlog_import import main as import_main
    import json

    rows = [{"entry_id": "h1", "session_id": "s1", "break_id": "coronado_north",
             "observer": "pete", "observer_id": "pete", "observer_height_cm": "",
             "typical": "waist", "sets": "", "wind": "glassy", "rideable": "yes",
             "method": "from_sand", "confidence": "high",
             "observed_utc": to_iso(utcnow()), "logged_utc": to_iso(utcnow()),
             "minutes_watched": "10", "saw_sets": "false",
             "forecast_seen": "false", "is_test": "", "note": ""}]
    source = tmp_path / "rows.json"
    source.write_text(json.dumps(rows), encoding="utf-8")

    import_main([str(source), "--path", str(tmp_path / "observations.csv")])
    out = capsys.readouterr().out
    assert "imported 1" in out
    assert "carry no observer height" in out
    assert "categories are unaffected" in out


# --- rehearsal entries ------------------------------------------------------


def test_a_test_note_is_recognised_without_catching_real_ones():
    """The whole reason this is a flag and not a substring match.

    BRIEFING section 8 lists `"NOAA" in "...not NOAA"` first among the four
    faults that produced confident wrong answers in the predecessor. "contest"
    contains "test", and a surf contest at Coronado is not a hypothetical.
    """

    from collector.beachlog import looks_like_a_test

    for note in ("test", "Test", "TEST", "  test  ", "test: second try", "test - north"):
        assert looks_like_a_test(note), note
    for note in ("contest day", "testing the water", "biggest set of the day",
                 "fastest I have seen it", "", "protest on the strand"):
        assert not looks_like_a_test(note), note


def test_the_flag_is_stored_not_re_derived_from_the_note():
    """Downstream reads the flag. It never looks at the note again.

    So an entry whose note is edited later — or one whose note happens to start
    with the word — is whatever it was RECORDED as, decided once where somebody
    could see the decision.
    """

    marked = entry(is_test="true", note="anything at all")
    assert marked.is_rehearsal

    unmarked = entry(is_test="", note="test")
    assert not unmarked.is_rehearsal, "the note must not override the stored flag"


def test_rehearsals_are_excluded_from_the_geometry_report():
    """They prove the pipeline carries a row. They are not observations."""

    real = session("r", {"coronado_north": "knee", "coronado_south": "head"}).entries
    fake = [e for e in session("f", {"coronado_north": "flat",
                                     "coronado_south": "double_overhead"}).entries]
    for e in fake:
        e.is_test = "true"
        e.note = "test"

    stamp = real[0].observed_utc[:13]
    text = "\n".join(report(real + fake, {stamp: 245.0}))

    assert "2 test row(s) excluded" in text
    assert "prune-tests" in text
    # The absurd rehearsal must not have reached the session count.
    assert "1 multi-break session(s)" in text


def test_rehearsals_can_be_counted_but_the_report_says_it_is_not_evidence():
    real = session("r", {"coronado_north": "knee", "coronado_south": "head"}).entries
    fake = session("f", {"coronado_north": "waist", "coronado_south": "chest"}).entries
    for e in fake:
        e.is_test = "true"

    stamp = real[0].observed_utc[:13]
    text = "\n".join(report(real + fake, {stamp: 245.0}, include_tests=True))

    assert "2 multi-break session(s)" in text
    assert "not observations and this is not evidence" in text


def test_prune_removes_only_the_rehearsals(tmp_path):
    from collector.beachlog import _prune

    path = tmp_path / "observations.csv"
    append(entry(entry_id="real1", break_id="coronado_north", typical="waist",
                 sets="chest"), path=path)
    append(entry(entry_id="fake1", break_id="coronado_south", typical="head",
                 sets="", is_test="true", note="test"), path=path)
    append(entry(entry_id="real2", break_id="coronado_center", typical="chest",
                 sets="head"), path=path)

    assert len(load(path=path)) == 3
    _prune(path)

    left = load(path=path)
    assert [e.entry_id for e in left] == ["real1", "real2"]
    assert not any(e.is_rehearsal for e in left)


def test_prune_dry_run_changes_nothing(tmp_path):
    """It rewrites an append-only file, so it can be looked at first."""

    from collector.beachlog import _prune

    path = tmp_path / "observations.csv"
    append(entry(entry_id="fake1", is_test="true", note="test"), path=path)
    _prune(path, dry_run=True)
    assert len(load(path=path)) == 1
