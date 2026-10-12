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
                # A named storm as a tab's last readable arrival is two lines:
                # "Arrived" ends line 2 and no count follows (2026-10-12).
                if line.endswith(", no longer arriving.") and " with winds of " in line:
                    assert lines[k + 1].startswith("Trains: "), cid
                    continue
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

    assert "away, with a split bearing (205° SSW or 285° WNW)." in cases["L2"][2]
    assert "away, with a split bearing (140° SE or 196° SSW or 254° WSW)." in cases["C2"][1]
    for cid in ("L2", "C2"):
        text = "\n".join(cases[cid])
        assert cases[cid][1 if cid[0] == "L" else 0].startswith("Unplaced storm")
        assert "does not have" not in text
        assert ("Unplaced storm: Tanner Banks, CA (NDBC 46047) holds that train from multiple "
                "directions, so no place is given.") in text
    for cid in ("L3", "C3"):
        text = "\n".join(cases[cid])
        assert cases[cid][1 if cid[0] == "L" else 0].startswith("Unplaced storm")
        assert " bearing" not in text
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

    assert cases["H1"][0] == "Hurricane Rachel {hurricane symbol}"
    assert cases["H1"][1].endswith(
        "sent Oct 1 from about 1,000 mi (1,700 km) away, bearing 196° SSW "
        "with winds of 121 mph (105 kt) and 950 mb pressure.")
    assert cases["H3"][1].endswith("with winds of 121 mph (105 kt).")
    assert "position, winds and pressure:" in cases["H1"][-1]
    assert "position and winds:" in cases["H3"][-1]


def test_a_weakened_storm_reads_as_the_fix_that_sent_its_train(cases):
    """Owner's request, 2026-10-11: a hurricane that has weakened stays named
    for the swell its tropical storm fixes sent, and is a tropical storm on
    that train, as a weakened hurricane's winds are the fix's, not today's."""

    assert cases["T1"][0] == "Tropical Storm Rachel {tropical storm symbol}"
    assert cases["T1"][1].endswith("with winds of 69 mph (60 kt) and 985 mb pressure.")
    assert cases["T1"][-1].startswith("Tropical storm position, winds and pressure: ")
    assert [cases["T2"][0], cases["T2"][3]] == ["Tropical Storm Rachel {tropical storm symbol}",
                                                "Hurricane Sergio {hurricane symbol}"]
    assert cases["T2"][-1].startswith("Storm position, winds and pressure: ")


def test_one_storms_swell_cut_into_two_rows_is_named_as_one(cases):
    """Owner's request, 2026-10-11 (BRIEFING §37h-i): rows that are one band
    at the open-ocean buoy are one storm's swell, listed together."""

    assert cases["T3"][1].startswith("The 10.5 and 11.1 s trains, sent Oct 8 ")


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


def test_nhcs_line_links_each_storm_to_its_page_by_name(cases):
    nhc = "https://www.nhc.noaa.gov/archive/2026/"
    assert cases["H1"][-1] == ("Hurricane position, winds and pressure: National Hurricane "
                               f"Center best track for [Rachel]({nhc}RACHEL_graphics.php), an analysis.")
    assert cases["H4"][-1].endswith(f"best tracks for [Rachel]({nhc}RACHEL_graphics.php) and "
                                    f"[Sergio]({nhc}SERGIO_graphics.php), an analysis.")


def test_sources_run_spectrum_then_nhc_then_unplaced(cases):
    """Owner's order, 2026-10-10, on the live pair it was written from: a
    hurricane and a split bearing."""

    heads = [line.split(" ")[0] for line in cases["M3"][-3:]]
    assert heads == ["Trains", "Hurricane", "Unplaced"]


def test_nothing_read_backwards_is_not_said_to_be(cases):
    assert cases["E0"] == ["No readable arrival in the last 21 days",
                           "Trains: Point Loma South, CA (NDBC 46232)."]
    for cid in ("H1", "H2", "H3", "H4", "M2"):
        assert "backwards" not in "\n".join(cases[cid]), cid


def test_the_last_readable_arrival_is_the_later_of_a_reading_and_a_named_storm(cases):
    """Owner's report, 2026-10-12: South read "Aleutian storm track", a
    reading ended 2 Oct, while Tropical Storm Rachel was named there to
    11 Oct. Whichever ended later is the tab's last readable arrival."""

    assert cases["L4"][1] == "Tropical Storm Rachel {tropical storm symbol}"
    assert any("best track for [Rachel]" in line for line in cases["L4"])
    assert cases["L5"][1] == "Aleutian storm track"
    assert not any("Rachel" in line for line in cases["L5"])


def test_a_last_readable_arrival_reads_as_the_owner_wrote_it(cases):
    """Owner's request, 2026-10-12, on South's Tropical Storm Rachel: a line
    naming the tab, the storm and its symbol, one sentence ending with the
    day the train SHOWN arrived (not the storm's first train at the tab), no
    counts, and the trains' source as "Trains: {buoy}"."""

    intro = "No readable trains arriving here now (Point Loma South). The last one read was:"
    for cid in ("L1", "L2", "L3", "L4", "L5"):
        assert cases[cid][0] == intro, cid
        assert "last readable arrival" not in "\n".join(cases[cid]), cid
    assert cases["L4"] == [
        intro,
        "Tropical Storm Rachel {tropical storm symbol}",
        "The 10.5 s train, sent Oct 8 from about 800 mi (1,300 km) away, bearing 200° SSW with "
        "winds of 69 mph (60 kt) and 985 mb pressure. Arrived Oct 11, no longer arriving.",
        "Trains: Point Loma South, CA (NDBC 46232).",
        "Tropical storm position, winds and pressure: National Hurricane Center best track for "
        "[Rachel](https://www.nhc.noaa.gov/archive/2026/RACHEL_graphics.php), an analysis."]


def test_a_storm_arrival_is_never_before_its_train_was_sent(cases):
    """"Arrived" is the first moment the storm was named at the tab with the
    fix that sent the train shown: the storm's first train there (Oct 8, a
    hurricane fix of Oct 2 in L4) read "sent Oct 8 ... Arrived Oct 7"."""

    assert "Arrived Oct 11," in cases["L4"][2] and "Arrived Oct 7" not in cases["L4"][2]
