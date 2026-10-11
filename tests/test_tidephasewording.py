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
    """Owner's request, 2026-10-11: no bullet points."""

    for cid, paras in cases.items():
        assert 1 <= len(paras) <= 3, cid
        for p in paras:
            assert not p.lstrip().startswith(("*", "-", "•")), cid


def test_the_constants_are_named_where_they_are_used(cases):
    """Owner's request, 2026-10-11: every claim read off NOAA's constants
    says so -- the phase, the next spring or neap, the one after, and the
    14 h lag the declination is read at."""

    for cid, paras in cases.items():
        assert "by NOAA's harmonic constants for San Diego (2017–2021)." in paras[0], cid
        assert "14 h late by the same constants" in paras[0], cid
        for p in paras[1:]:
            assert " by the same constants" in p, cid


def test_the_owners_late_october(cases):
    assert cases["10 Oct"][2].startswith("Late October: springs by the same constants")


def test_the_two_tides_never_the_two_highs(cases):
    for paras in cases.values():
        assert "two highs" not in " ".join(paras)
