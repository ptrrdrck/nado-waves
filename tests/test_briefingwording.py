"""The LIVE Briefing's wording, rendered by the page's own code
(docs/briefing_wording.md). Pins the doc to the page, and the claims the
formula exists to get right."""

import re
import shutil

import pytest

from forecast import briefingwording

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


@pytest.fixture(scope="module")
def cases():
    return briefingwording.render()


def test_the_doc_is_what_the_page_prints(cases):
    doc = briefingwording.DOC.read_text(encoding="utf-8")
    assert briefingwording.build(doc, cases) == doc, \
        "docs/briefing_wording.md is out of date: run python -m forecast.briefingwording"


def test_the_sentence_list_is_what_the_page_prints(cases):
    assert briefingwording.SENTENCES.read_text(encoding="utf-8") == briefingwording.sentences(cases), \
        "docs/briefing_sentences.md is out of date: run python -m forecast.briefingwording"


def _entries(got):
    return got["entries"]


def _text(got):
    return " ".join(h + " " + b for h, b in got["entries"])


def _body(cases, cid, head):
    return next(b for h, b in cases[cid]["entries"] if h == head)


def test_five_entries_in_one_order(cases):
    order = ["Overview", "Swell", "Tide", "Wind", "Watching"]
    for cid, got in cases.items():
        heads = [h for h, _ in got["entries"]]
        assert heads == [h for h in order if h in heads], cid
        assert set(heads) <= set(order), cid


def test_the_line_names_the_issue_and_no_condition(cases):
    assert cases["Q1"]["line"] == "Morning briefing 6:05 AM"
    assert cases["M1"]["line"] == "Midday briefing 12:05 PM"
    assert cases["Y1"]["line"] == "Midday briefing 15 Oct, 12:05 PM"
    for got in cases.values():
        assert not got["line"] or (" ft" not in got["line"] and " mph" not in got["line"])


def test_every_number_is_imperial_first(cases):
    for cid, got in cases.items():
        for _, body in got["entries"]:
            for ft in re.findall(r"(\d+\.\d) ft \((\d+\.\d\d) m\)", body):
                assert abs(float(ft[0]) / 3.28084 - float(ft[1])) < 0.06, cid
            for f, c in re.findall(r"(\d+) °F \((\d+(?:\.\d)?) °C\)", body):
                assert abs((float(f) - 32) * 5 / 9 - float(c)) < 0.6, cid


def test_the_tide_reads_as_the_owner_wrote_it(cases):
    body = _body(cases, "Q1", "Tide")
    assert body.startswith("The tide is pushing to 5.4 ft (1.65 m) at 9:30 AM then dropping to 1.8 ft (0.55 m) at 3:45 PM.")
    assert "The previous AM low was 3.3 ft (1.01 m) at 3:15 AM and the PM high will be 6.3 ft (1.92 m) at 10:05 PM." in body
    assert "The gauge is running 1.1 ft (0.34 m) over the harmonic prediction" in body
    assert "Today's range is 4.5 ft (1.37 m)" in body


def test_a_previous_turn_yesterday_says_so(cases):
    assert "at 10:10 PM yesterday" in _body(cases, "T1", "Tide")


def test_the_overview_opens_on_sunrise_and_daylight(cases):
    assert _body(cases, "Q1", "Overview").startswith("Sunrise is at 6:54 AM with 11 h 20 m of daylight.")
    assert _body(cases, "M1", "Overview").startswith("Sunrise was at 6:54 AM")


def test_rain_is_said_with_its_amount_and_hours(cases):
    assert "rain from 1:52 AM to 3:52 AM, 0.07 in (1.8 mm)" in _body(cases, "B1", "Overview")
    assert "drizzle reported, too little to measure" in _body(cases, "N1", "Overview")
    assert "no rain" in _body(cases, "Q1", "Overview")


def test_a_dark_buoy_stands_the_swell_down_and_says_so_once(cases):
    body = _body(cases, "D1", "Swell")
    assert body == "No spectrum from CDIP 191 since 3:00 PM yesterday, so the swell waits for it."


def test_a_short_span_judges_nothing(cases):
    body = _body(cases, "U1", "Swell")
    for word in ("filling", "fading", "little change", "leads"):
        assert word not in body


def test_filling_and_fading_are_the_measured_words(cases):
    body = _body(cases, "B1", "Swell")
    assert "filling from" in body and "fading from" in body and "North leads." in body
    assert "rose from" not in body and "dropped from" not in body


def test_tanner_banks_is_due_never_arrived(cases):
    body = _body(cases, "B1", "Swell")
    assert "due at CDIP 191" in body and "Due, not seen" in body
    assert "arrives at" not in body and "arrived at" not in body


def test_the_wind_is_a_count_never_a_habit(cases):
    for cid, got in cases.items():
        text = _text(got).lower()
        for word in ("usual", "normal", "typical", "habit", "expect", "will turn", "should"):
            assert word not in text, (cid, word)
    assert "At this hour on the 28 days before: offshore on 18, 19 and 17 days at North, Center and South." \
        in _body(cases, "Q1", "Wind")


def test_a_storm_names_its_source_for_each_edge(cases):
    assert "from the fixes NHC has logged" in _body(cases, "B1", "Watching")
    assert "on NHC's forecast" in _body(cases, "H1", "Watching")
    assert "behind land from Point Loma South" in _body(cases, "B1", "Watching")


def test_every_word_is_as_of_the_issue_not_the_readers_clock():
    """The same issue reads the same whenever it is read: only the fold's
    line takes the reader's clock, to name the day of an issue not today's."""
    src = briefingwording.PAGE.read_text(encoding="utf-8")
    block = src[src.index("const BRIEF_EDITION = "):src.index("// Whether the Briefing is open")]
    assert block.count("Date.now()") == 1 and "function briefIssue(B, nowMs = Date.now())" in block


def test_nothing_is_called_safe_or_dangerous(cases):
    for got in cases.values():
        text = _text(got).lower()
        for word in ("safe", "danger", "hazard", "rip", "accurate", "mellow", "pumping"):
            assert word not in text, word


def test_the_model_never_appears(cases):
    for got in cases.values():
        text = _text(got)
        assert "GFS" not in text and "model" not in text.lower() and "ensemble" not in text.lower()


def test_no_issue_draws_no_fold(cases):
    assert cases["X1"] == {"line": None, "entries": []}


def test_one_real_issue_renders_for_the_record():
    got = briefingwording.render_issue(briefingwording.QUIET)
    assert got["line"] == "Morning briefing 6:05 AM"
    assert [h for h, _ in got["entries"]] == ["Overview", "Swell", "Tide", "Wind"]
