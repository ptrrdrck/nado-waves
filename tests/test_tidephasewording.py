"""The Tide card's phase fold, worded by the page's own code
(docs/tide_phase_wording.md, `forecast.tidephasewording`)."""

import shutil

import pytest

from forecast import tidephasewording

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


@pytest.fixture(scope="module")
def cases():
    return tidephasewording.render()


def test_the_doc_is_what_the_page_prints(cases):
    doc = tidephasewording.DOC.read_text(encoding="utf-8")
    assert tidephasewording.build(doc, cases) == doc, \
        "docs/tide_phase_wording.md is out of date: run python -m forecast.tidephasewording"


def test_three_paragraphs_never_bullets(cases):
    """Owner's request, 2026-10-11: no bullet points. Each paragraph is a
    heading over a body."""

    for cid, paras in cases.items():
        assert 1 <= len(paras) <= 3, cid
        for head, body in paras:
            assert head and body, cid
            assert not body.lstrip().startswith(("*", "-", "\u2022")), cid


def test_the_headings_are_the_owners(cases):
    """"Today", "Around 17 Oct", "Late October" (owner's edit, 2026-10-11)."""

    assert [h for h, _ in cases["10 Oct"]] == ["Today", "Around 17 Oct", "Late October"]
    assert cases["10 Oct"][0][1].startswith("Spring tides. New moon is 10 Oct")
    assert cases["10 Oct"][1][1].startswith("Neap tide, coinciding with apogee")
    assert cases["10 Oct"][2][1].startswith("Springs, at full moon (25 Oct)")


def test_the_constants_are_named_in_the_provenance_not_the_text(cases):
    """Owner's edit, 2026-10-11: "by NOAA's harmonic constants" and "by the
    same constants" came out of the paragraphs; the provenance names them."""

    for cid, paras in cases.items():
        text = " ".join(b for _, b in paras)
        assert "constants" not in text, cid
        assert "as the tide feels it 14 h late," in paras[0][1], cid


def test_the_turns_are_the_upcoming_ones(cases):
    text = " ".join(b for _, b in cases["10 Oct"])
    assert "The upcoming turns show it:" in text and "CO-OPS turns" not in text


def test_the_two_tides_never_the_two_highs(cases):
    for paras in cases.values():
        assert "two highs" not in " ".join(b for _, b in paras)


def test_the_fold_line_stays_the_same():
    page = tidephasewording.PAGE.read_text(encoding="utf-8")
    assert 'const PHASE_FOLD_TITLE = "Phase";' in page
    assert "Where Coronado is" not in page
