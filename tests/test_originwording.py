"""The Origin fold's wording, rendered by the page's own code (owner's
formula, 2026-10-10; docs/origin_wording.md).

`forecast.originwording` runs the page's Origin functions in Node on one
made-up Origin block per branch. These pin that the doc is that output, and
check each claim the formula exists to get right.
"""

import shutil

import pytest

from forecast import originwording

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


@pytest.fixture(scope="module")
def cases():
    return originwording.render()


def test_the_doc_is_what_the_page_prints(cases):
    doc = originwording.DOC.read_text(encoding="utf-8")
    assert originwording.build(doc, cases) == doc, \
        "docs/origin_wording.md is out of date: run python -m forecast.originwording"


def test_every_entry_is_three_lines(cases):
    """What; sent when and from where; how it is known."""

    for cid, lines in cases.items():
        heads = [k for k, line in enumerate(lines) if " s train, sent " in line]
        for k in heads:
            assert lines[k + 1].startswith(("Read backwards off the swell", "Strong match",
                                            "Partial match", "Weak match")), cid


def test_a_split_direction_is_not_an_unplaced_storm(cases):
    """46047 HAS a split direction's train, from two directions: the source
    may not say it does not, and both directions are named."""

    for cid in ("L2", "C2"):
        text = "\n".join(cases[cid])
        assert cases[cid][0].startswith("Split direction")
        assert "bearing 205° SSW or 285° WNW." in text
        assert "does not have" not in text and "Unplaced" not in text
        assert "holds that train from two directions, so no place is given." in text
    for cid in ("L3", "C3"):
        text = "\n".join(cases[cid])
        assert cases[cid][0].startswith("Unplaced storm") and " bearing " not in text
        assert "Tanner Banks, CA (NDBC 46047) does not have that train." in text


def test_no_neither_without_a_nor(cases):
    for cid, lines in cases.items():
        for line in lines:
            assert "neither" not in line or " nor " in line, (cid, line)


def test_a_fitted_date_is_about_and_nhcs_is_not(cases):
    assert all(" sent about " in line for line in cases["C1"] if " s train, " in line)
    assert all(" sent Oct " in line for line in cases["H1"] if " s train, " in line)


def test_a_hurricane_says_its_winds_and_pressure_were_when_sent(cases):
    assert cases["H1"][0] == "Hurricane Rachel  winds 121 mph (105 kt), 950 mb when sent"
    assert cases["H3"][0] == "Hurricane Rachel  winds 121 mph (105 kt) when sent"
    assert "position, winds and pressure:" in cases["H1"][-1]
    assert "position and winds:" in cases["H3"][-1]


def test_the_match_is_counts_never_a_percentage(cases):
    for cid in ("H1", "H2", "H3", "M1", "M2"):
        assert not any("%" in line for line in cases[cid]), cid
    assert ("39 of 50 times at Tanner Banks, CA (NDBC 46047) over 30 h, and 28 of 40 at "
            "San Clemente Basin, CA (NDBC 46086) over 26 h.") in cases["H2"][2]


def test_nothing_read_backwards_is_not_said_to_be(cases):
    assert cases["E0"] == ["No readable arrival in the last 21 days",
                           "Trains read off the spectrum at Point Loma South, CA (NDBC 46232)."]
    for cid in ("H1", "H2", "H3", "M2"):
        assert "backwards" not in "\n".join(cases[cid]), cid
