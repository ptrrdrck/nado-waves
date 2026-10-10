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
        for k, line in enumerate(lines):
            if line.startswith("The ") and " s train, sent " in line:
                assert lines[k + 1].startswith(("Read backwards off the swell",
                                                "Timing and direction beat")), cid


def test_line_two_is_one_sentence_with_away(cases):
    """Owner's rewrite, 2026-10-10: "The … train, sent … from about … away"
    on every kind, the direction after a comma."""

    for cid, lines in cases.items():
        for line in lines:
            if " s train, sent " in line:
                assert line.startswith("The ") and " away" in line and line.endswith("."), (cid, line)


def test_a_split_bearing_is_unplaced_and_says_why(cases):
    """46047 HAS a split train, from several directions: the source may not
    say it does not, and every direction is named."""

    assert "away, with a split bearing (205° SSW or 285° WNW)." in cases["L2"][1]
    assert "away, with a split bearing (140° SE or 196° SSW or 254° WSW)." in cases["C2"][1]
    for cid in ("L2", "C2"):
        text = "\n".join(cases[cid])
        assert cases[cid][0].startswith("Unplaced storm")
        assert "does not have" not in text
        assert ("Unplaced storm: Tanner Banks, CA (NDBC 46047) holds that train from multiple "
                "directions, so no place is given.") in text
    for cid in ("L3", "C3"):
        text = "\n".join(cases[cid])
        assert cases[cid][0].startswith("Unplaced storm") and " bearing" not in text
        assert "Unplaced storm: Tanner Banks, CA (NDBC 46047) does not have that train." in text


def test_no_neither_without_a_nor(cases):
    for cid, lines in cases.items():
        for line in lines:
            assert "neither" not in line or " nor " in line, (cid, line)


def test_a_fitted_date_is_about_and_nhcs_is_not(cases):
    assert all(" sent about " in line for line in cases["C1"] if " s train, " in line)
    assert all(" sent Oct " in line for line in cases["H1"] if " s train, " in line)


def test_a_hurricanes_strength_is_the_fix_that_sent_its_train(cases):
    """Line 1 is the name alone; the winds and pressure follow the day the
    train was sent, so they never read as the storm now."""

    assert cases["H1"][0] == "Hurricane Rachel"
    assert cases["H1"][1].endswith(
        "sent Oct 1 from about 1,000 mi (1,700 km) away, bearing 196° SSW "
        "with winds of 121 mph (105 kt) and 950 mb pressure.")
    assert cases["H3"][1].endswith("with winds of 121 mph (105 kt).")
    assert "position, winds and pressure:" in cases["H1"][-1]
    assert "position and winds:" in cases["H3"][-1]


def test_the_match_is_counts_beaten_never_a_word_or_a_percentage(cases):
    """Owner's calls, 2026-10-10: no percentage, no strong / partial / weak.
    The verb is "beat": the count is copies of the track moved earlier that
    the real timing and direction did better than, not matches."""

    for cid in ("H1", "H2", "H3", "H4", "M1", "M2"):
        text = "\n".join(cases[cid])
        assert "%" not in text and "match" not in text.lower(), cid
    assert cases["H2"][2] == (
        "Timing and direction beat NHC's track moved earlier 39 of 50 times at Tanner Banks, "
        "CA (NDBC 46047) over 30 h, and 28 of 40 times at San Clemente Basin, CA (NDBC 46086) "
        "over 26 h.")


def test_nhcs_line_links_each_storm_by_name(cases):
    btk = "https://ftp.nhc.noaa.gov/atcf/btk/"
    assert cases["H1"][-1] == ("Hurricane position, winds and pressure: National Hurricane "
                               f"Center best track for [Rachel]({btk}bep182026.dat), an analysis.")
    assert cases["H4"][-1].endswith(f"best tracks for [Rachel]({btk}bep182026.dat) and "
                                    f"[Sergio]({btk}bep202026.dat), an analysis.")


def test_sources_run_spectrum_then_nhc_then_unplaced(cases):
    """Owner's order, 2026-10-10, on the live pair it was written from: a
    hurricane and a split bearing."""

    heads = [line.split(" ")[0] for line in cases["M3"][-3:]]
    assert heads == ["Trains", "Hurricane", "Unplaced"]


def test_nothing_read_backwards_is_not_said_to_be(cases):
    assert cases["E0"] == ["No readable arrival in the last 21 days",
                           "Trains read off the spectrum at Point Loma South, CA (NDBC 46232)."]
    for cid in ("H1", "H2", "H3", "H4", "M2"):
        assert "backwards" not in "\n".join(cases[cid]), cid
