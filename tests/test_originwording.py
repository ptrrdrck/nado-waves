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


NHC = "https://www.nhc.noaa.gov/archive/2026/"
RACHEL = f"[Rachel]({NHC}RACHEL_graphics.php)"
SERGIO = f"[Sergio]({NHC}SERGIO_graphics.php)"
INTRO = "No readable swell arriving here now. The last one was:"


def test_every_entry_is_a_head_and_one_paragraph(cases):
    """Owner's rewrite, 2026-10-14: what; then sent when and from where,
    where the direction was read and how it is known, run on as one
    paragraph. Nothing follows the entries."""

    for cid, lines in cases.items():
        for k, line in enumerate(lines):
            if line.startswith("The ") and " s train" in line:
                assert k >= 1 and not lines[k - 1].startswith("The "), cid
                assert k + 1 == len(lines) or not lines[k + 1].startswith((
                    "Arriving for", "NHC had", "Tanner Banks", "Trains")), cid
                assert line.endswith((" so far.", " h.", ", no longer arriving.", " at that time."))


def test_no_provenance_follows_the_entries(cases):
    """Owner's call, 2026-10-14: storm matching is explained on docs.html."""

    for cid, lines in cases.items():
        text = "\n".join(lines)
        for gone in ("Trains:", "Trains read off", "National Hurricane Center", "best track",
                     "Unplaced storm:", "an analysis"):
            assert gone not in text, (cid, gone)


def test_line_two_is_one_sentence_with_away(cases):
    """Owner's rewrite, 2026-10-10: "The … train, sent … from about … away"
    on every kind, a named storm's bearing after a comma."""

    for cid, lines in cases.items():
        for line in lines:
            if " s train, sent " in line or " s trains, sent " in line:
                assert line.startswith("The ") and " away" in line, (cid, line)


def test_a_readings_direction_names_the_buoy_it_is_read_at(cases):
    """Owner's rewrite, 2026-10-14: placed, split and unseen each say it in a
    sentence of its own naming 46047, after the train's."""

    assert cases["L2"][2] == (
        "The 15.4 s train, sent about Oct 1 from about 4,500 mi (7,500 km) away. Tanner Banks "
        "(NDBC 46047) holds this train from 205° SSW and 285° WNW, so no place is given. "
        "Arrived Oct 6, no longer arriving.")
    assert ("away. Tanner Banks (NDBC 46047) holds this train from 140° SE, 196° SSW and "
            "254° WSW, so no place is given. Arriving for 18 h so far.") in cases["C2"][1]
    assert ("away. Tanner Banks (NDBC 46047) holds this train from 212° SSW. Arriving for 18 h "
            "so far.") in cases["C1"][1]
    for cid in ("L3", "C3"):
        line = cases[cid][2 if cid[0] == "L" else 1]
        assert ("away. Tanner Banks (NDBC 46047) does not have this train, so no place is "
                "given. ") in line
        assert " bearing" not in line and " holds " not in line
    for cid in ("L2", "L3", "C2", "C3"):
        assert cases[cid][1 if cid[0] == "L" else 0] == "Unplaced storm", cid
    for cid, lines in cases.items():
        assert "split bearing" not in "\n".join(lines), cid


def test_no_neither_without_a_nor(cases):
    for cid, lines in cases.items():
        for line in lines:
            assert "neither" not in line.lower() or " nor " in line, (cid, line)


def test_a_fitted_date_is_about_and_nhcs_is_not(cases):
    assert all(" sent about " in line for line in cases["C1"] if " s train, " in line)
    assert all(" sent Oct " in line for line in cases["H1"] if " s train, " in line)


def test_a_hurricanes_place_and_strength_are_nhcs_in_a_sentence_of_their_own(cases):
    """Line 1 is the name alone; the bearing, winds and pressure follow the
    day the train was sent, so they never read as the storm now, in a
    sentence naming NHC as a reading's names its buoy (owner's calls,
    2026-10-14: "had", and "at that time" after the strength)."""

    assert cases["H1"][0] == f"Hurricane {RACHEL} {{hurricane symbol}}"
    assert cases["H1"][1] == (
        "The 14.3 s train, sent Oct 1 from about 1,000 mi (1,700 km) away. NHC had it at "
        "196° SSW, with winds of 121 mph (105 kt) and 950 mb pressure at that time. Arriving "
        "for 30 h so far.")
    # No hours at any gate buoy: the sentence drops (H3).
    assert cases["H3"][1].endswith("NHC had it at 196° SSW, with winds of 121 mph (105 kt) at "
                                   "that time.")


def test_a_weakened_storm_reads_as_the_fix_that_sent_its_train(cases):
    """Owner's request, 2026-10-11: a hurricane that has weakened stays named
    for the swell its tropical storm fixes sent, and is a tropical storm on
    that train, as a weakened hurricane's winds are the fix's, not today's."""

    assert cases["T1"][0] == f"Tropical Storm {RACHEL} {{tropical storm symbol}}"
    assert "with winds of 69 mph (60 kt) and 985 mb pressure at that time. Arriving for 40 h" \
        in cases["T1"][1]
    assert [cases["T2"][0], cases["T2"][2]] == [f"Tropical Storm {RACHEL} {{tropical storm symbol}}",
                                                f"Hurricane {SERGIO} {{hurricane symbol}}"]


def test_one_storms_swell_cut_into_two_rows_is_named_as_one(cases):
    """Owner's request, 2026-10-11 (BRIEFING §37h-i): rows that are one band
    at the open-ocean buoy are one storm's swell, listed together."""

    assert cases["T3"][1].startswith("The 10.5 and 11.1 s trains, sent Oct 8 ")


def test_the_match_stays_off_the_card_and_its_hours_say_how_long(cases):
    """Owner's calls: no percentage or match word (2026-10-10), and since
    2026-10-14 no counts either, storm matching being explained on
    docs.html. What stays is how long the storm's swell has been arriving
    by its track, the longest at any gate buoy (H2: 30 h at 46047, 26 h at
    46086), and no buoy is named for it."""

    for cid in ("H1", "H2", "H3", "H4", "M1", "M2"):
        text = "\n".join(cases[cid])
        assert "%" not in text and "match" not in text.lower(), cid
        assert " of 50 " not in text and "copies" not in text and "beat" not in text, cid
    assert cases["H2"][1].endswith("pressure at that time. Arriving for 30 h so far.")
    assert "NDBC" not in cases["H2"][1]


def test_the_storms_name_alone_links_to_its_nhc_page(cases):
    """Owner's call, 2026-10-14: with the provenance gone, the link is on the
    name in the head, and only the name."""

    assert cases["H1"][0] == f"Hurricane {RACHEL} {{hurricane symbol}}"
    assert cases["H4"][0].startswith(f"Hurricane {RACHEL}")
    assert cases["H4"][2].startswith(f"Hurricane {SERGIO}")


def test_nothing_read_backwards_is_not_said_to_be(cases):
    assert cases["E0"] == ["No readable swell in the last 21 days."]
    for cid in ("H1", "H2", "H3", "H4", "M2"):
        assert "backwards" not in "\n".join(cases[cid]), cid


def test_the_last_readable_arrival_is_the_later_of_a_reading_and_a_named_storm(cases):
    """Owner's report, 2026-10-12: South read "Aleutian storm track", a
    reading ended 2 Oct, while Tropical Storm Rachel was named there to
    11 Oct. Whichever ended later is the tab's last readable arrival."""

    assert cases["L4"][1] == f"Tropical Storm {RACHEL} {{tropical storm symbol}}"
    assert cases["L5"][1] == "Aleutian storm track"
    assert not any("Rachel" in line for line in cases["L5"])


def test_a_last_readable_arrival_reads_as_the_owner_wrote_it(cases):
    """Owner's requests, 2026-10-12 and -14: an opening line without the
    tab, the storm and its symbol, one sentence ending with the day the train
    SHOWN arrived (not the storm's first train at the tab), no counts, and
    nothing under it."""

    for cid in ("L1", "L2", "L3", "L4", "L5"):
        assert cases[cid][0] == INTRO, cid
        assert "last readable arrival" not in "\n".join(cases[cid]), cid
    assert cases["L4"] == [
        INTRO,
        f"Tropical Storm {RACHEL} {{tropical storm symbol}}",
        "The 10.5 s train, sent Oct 8 from about 800 mi (1,300 km) away. NHC had it at "
        "200° SSW, with winds of 69 mph (60 kt) and 985 mb pressure at that time. Arrived "
        "Oct 11, no longer arriving."]


def test_a_storm_arrival_is_never_before_its_train_was_sent(cases):
    """"Arrived" is the first moment the storm was named at the tab with the
    fix that sent the train shown: the storm's first train there (Oct 8, a
    hurricane fix of Oct 2 in L4) read "sent Oct 8 ... Arrived Oct 7"."""

    assert "Arrived Oct 11," in cases["L4"][2] and "Arrived Oct 7" not in cases["L4"][2]
