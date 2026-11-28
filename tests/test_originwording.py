"""An origin's words under its train, rendered by the page's own code (owner's
formula, 2026-10-10; one paragraph under the train since 2026-11-28;
docs/origin_wording.md).

`forecast.originwording` runs the page's Origin functions in Node on one
made-up Origin block per branch, its trains made to carry every origin. These
pin that the doc is that output, and check each claim the formula exists to
get right.
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


NHC = "https://www.nhc.noaa.gov/archive/2026/"
RACHEL = f"[Rachel]({NHC}RACHEL_graphics.php)"
SERGIO = f"[Sergio]({NHC}SERGIO_graphics.php)"
WHAT = ("Hurricane ", "Tropical Storm ", "South Pacific.", "Unplaced storm.")


def test_every_origin_is_one_paragraph(cases):
    """Owner's call, 2026-11-28: one style, no head of its own. What it is
    opens the paragraph as its first sentence; then sent when and from
    where, where the direction was read and how it is known, run on.
    Nothing follows it."""

    for cid, lines in cases.items():
        assert lines, cid
        for line in lines:
            assert line.startswith(WHAT), (cid, line)
            assert ". Sent " in line, (cid, line)
            assert line.endswith((" so far.", " at that time.")), (cid, line)


def test_the_row_says_the_period_and_the_line_does_not(cases):
    """Owner's call, 2026-11-28: "The {T} s train" went, the tapped row
    saying the period; a storm's swell cut into two rows is one line under
    their bracket, with no periods either (T3)."""

    for cid, lines in cases.items():
        text = "\n".join(lines)
        assert " s train" not in text and " s trains" not in text, cid
        assert "15.1" not in text and "14.3" not in text and "10.5" not in text, cid
    assert cases["T3"] == cases["T1"]


def test_no_storm_symbol_in_the_line(cases):
    """Owner's call, 2026-11-28: the row carries the storm's symbol as its
    mark; the paragraph does not repeat it."""

    for cid, lines in cases.items():
        assert "symbol" not in "\n".join(lines), cid


def test_no_provenance_follows_the_paragraph(cases):
    """Owner's call, 2026-10-14: storm matching is explained on docs.html."""

    for cid, lines in cases.items():
        text = "\n".join(lines)
        for gone in ("Trains:", "Trains read off", "National Hurricane Center", "best track",
                     "Unplaced storm:", "an analysis"):
            assert gone not in text, (cid, gone)


def test_the_second_sentence_is_when_and_how_far_away(cases):
    """Owner's rewrite, 2026-10-10, without the train since 2026-11-28:
    "Sent … from about … away." on every kind."""

    for cid, lines in cases.items():
        for line in lines:
            sent = line[line.index(". Sent ") + 2:]
            assert sent[:sent.index(".") + 1].endswith(" away."), (cid, line)


def test_a_readings_direction_names_the_buoy_it_is_read_at(cases):
    """Owner's rewrite, 2026-10-14: placed, split and unseen each say it in a
    sentence of its own naming 46047, after the day it was sent."""

    assert cases["C1"] == [
        "South Pacific. Sent about Oct 1 from about 4,500 mi (7,500 km) away. Tanner Bank "
        "(NDBC 46047) holds this train from 212° SSW. Arriving for 18 h so far."]
    assert ("away. Tanner Bank (NDBC 46047) holds this train from 140° SE, 196° SSW and "
            "254° WSW, so no place is given. Arriving for 18 h so far.") in cases["C2"][0]
    line = cases["C3"][0]
    assert ("away. Tanner Bank (NDBC 46047) does not have this train, so no place is "
            "given. ") in line
    assert " bearing" not in line and " holds " not in line
    for cid in ("C2", "C3"):
        assert cases[cid][0].startswith("Unplaced storm. Sent about "), cid
    for cid, lines in cases.items():
        assert "split bearing" not in "\n".join(lines), cid


def test_no_neither_without_a_nor(cases):
    for cid, lines in cases.items():
        for line in lines:
            assert "neither" not in line.lower() or " nor " in line, (cid, line)


def test_a_fitted_date_is_about_and_nhcs_is_not(cases):
    assert ". Sent about Oct 1 " in cases["C1"][0]
    assert ". Sent Oct 1 " in cases["H1"][0]


def test_a_hurricanes_place_and_strength_are_nhcs_in_a_sentence_of_their_own(cases):
    """The bearing, winds and pressure follow the day the train was sent, so
    they never read as the storm now, in a sentence naming NHC as a
    reading's names its buoy (owner's calls, 2026-10-14: "had", and "at that
    time" after the strength)."""

    assert cases["H1"] == [
        f"Hurricane {RACHEL}. Sent Oct 1 from about 1,000 mi (1,700 km) away. NHC had it at "
        "196° SSW, with winds of 121 mph (105 kt) and 950 mb pressure at that time. Arriving "
        "for 30 h so far."]
    # No hours at any gate buoy: the sentence drops (H3).
    assert cases["H3"][0].endswith("NHC had it at 196° SSW, with winds of 121 mph (105 kt) at "
                                   "that time.")


def test_a_weakened_storm_reads_as_the_fix_that_sent_its_train(cases):
    """Owner's request, 2026-10-11: a hurricane that has weakened stays named
    for the swell its tropical storm fixes sent, and is a tropical storm on
    that train, as a weakened hurricane's winds are the fix's, not today's."""

    assert cases["T1"][0].startswith(f"Tropical Storm {RACHEL}. Sent Oct 8 ")
    assert "with winds of 69 mph (60 kt) and 985 mb pressure at that time. Arriving for 40 h" \
        in cases["T1"][0]
    assert [cases["T2"][0][:len(f"Tropical Storm {RACHEL}.")],
            cases["T2"][1][:len(f"Hurricane {SERGIO}.")]] == [f"Tropical Storm {RACHEL}.",
                                                              f"Hurricane {SERGIO}."]


def test_the_match_stays_off_the_card_and_its_hours_say_how_long(cases):
    """Owner's calls: no percentage or match word (2026-10-10), and since
    2026-10-14 no counts either, storm matching being explained on
    docs.html. What stays is how long the storm's swell has been arriving
    by its track, the longest at any gate buoy (H2: 30 h at 46047, 26 h at
    46086), and no buoy is named for it."""

    for cid in ("H1", "H2", "H3", "H4", "M1"):
        text = "\n".join(cases[cid])
        assert "%" not in text and "match" not in text.lower(), cid
        assert " of 50 " not in text and "copies" not in text and "beat" not in text, cid
    assert cases["H2"][0].endswith("pressure at that time. Arriving for 30 h so far.")
    assert "NDBC" not in cases["H2"][0]


def test_the_storms_name_alone_links_to_its_nhc_page(cases):
    """Owner's call, 2026-10-14: the link is on the storm's name, and only
    the name."""

    assert cases["H1"][0].startswith(f"Hurricane {RACHEL}. ")
    assert cases["H4"][0].startswith(f"Hurricane {RACHEL}. ")
    assert cases["H4"][1].startswith(f"Hurricane {SERGIO}. ")
    for cid, lines in cases.items():
        assert "\n".join(lines).count("](") == sum(line.startswith(("Hurricane", "Tropical"))
                                                   for line in lines), cid


def test_storms_come_first_then_readings(cases):
    assert cases["M1"][0].startswith(f"Hurricane {RACHEL}. ")
    assert cases["M1"][1].startswith("South Pacific. ")
    assert cases["M3"][1].startswith("Unplaced storm. ")


def test_nothing_read_backwards_is_not_said_to_be(cases):
    for cid in ("H1", "H2", "H3", "H4"):
        assert "backwards" not in "\n".join(cases[cid]), cid


def test_only_what_is_arriving_now(cases):
    """Owner's call, 2026-11-28: a last readable arrival has no train to sit
    under, and is not on the card."""

    for cid, lines in cases.items():
        text = "\n".join(lines)
        assert "no longer arriving" not in text and "The last one" not in text, cid
        assert "No readable swell" not in text, cid
