"""The LIVE Briefing's wording, rendered by the page's own code
(docs/briefing_wording.md). Pins the doc to the page, and the claims the
formula exists to get right."""

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


def _text(entries):
    return " ".join(h + " " + b for h, b in entries)


def test_stories_come_in_one_order(cases):
    order = ["Standing on", "Since sunset", "Wind", "Tide", "Buoys and season"]
    for cid, entries in cases.items():
        heads = [h for h, _ in entries if h in order]
        assert heads == [h for h in order if h in heads], cid


def test_every_number_is_imperial_first(cases):
    import re
    for cid, entries in cases.items():
        for _, body in entries:
            for ft in re.findall(r"(\d+\.\d) ft \((\d+\.\d\d) m\)", body):
                assert abs(float(ft[0]) / 3.28084 - float(ft[1])) < 0.06


def test_a_dark_buoy_stands_the_break_stories_down_and_says_so_once(cases):
    text = _text(cases["D1"])
    assert "has not reported since" in text
    assert "Since sunset" not in [h for h, _ in cases["D1"]]
    assert text.count("CDIP 191 at") == 0


def test_a_short_night_judges_nothing(cases):
    text = _text(cases["U1"])
    assert "rose" not in text and "dropped" not in text and "changed little" not in text


def test_the_model_never_appears(cases):
    for entries in cases.values():
        text = _text(entries)
        assert "GFS" not in text and "model" not in text.lower() and "ensemble" not in text.lower()


def test_tanner_banks_is_due_never_arrived(cases):
    text = _text(cases["B1"])
    assert "due at CDIP 191" in text and "Due, not seen" in text
    assert "arrives at" not in text and "arrived at" not in text


def test_a_storm_names_its_source_for_each_edge(cases):
    assert "from the fixes NHC has logged" in _text(cases["B1"])
    assert "on NHC's forecast" in _text(cases["H1"])
    assert "behind land, so nothing it has sent reaches the breaks" in _text(cases["B1"])


def test_nothing_is_called_safe_or_dangerous(cases):
    for entries in cases.values():
        text = _text(entries).lower()
        for word in ("safe", "danger", "hazard", "rip", "accurate", "mellow", "pumping"):
            assert word not in text, word


def test_no_briefing_draws_no_fold(cases):
    assert cases["X1"] == []
