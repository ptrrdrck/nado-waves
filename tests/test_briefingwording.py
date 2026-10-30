"""The LIVE Briefing's wording, rendered by the page's own code
(docs/briefing_wording.md, docs/briefing_sentences.md). Pins the docs to the
page, and the claims the formula exists to get right."""

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


def _all(got):
    """The page's own words: NWS's alerts are NWS's names, quoted with their
    tag, so a "Rip Current Statement" is NWS calling it that."""
    return " ".join([got["line"] or ""] + got["swell"] + got["conditions"] + got["tides"] + got["water_quality"])


def test_the_line_names_the_update_and_no_condition(cases):
    assert cases["Q1"]["line"] == "Briefing updated 7:16 AM"
    assert cases["Y1"]["line"] == "Briefing updated Oct 21, 12:06 PM"
    for got in cases.values():
        assert not got["line"] or (" ft" not in got["line"] and "°" not in got["line"])


def test_the_swell_reads_as_the_owner_wrote_it(cases):
    """Owner's wording and calls, 2026-10-23: the beach's range, a line a
    train with its own status, then what Tanner Banks holds, each opening on
    its point, its trend said as offshore's (owner's wording, 2026-10-24)."""
    assert cases["Q1"]["swell"] == ["3–4 ft (0.9–1.2 m).", "SSW at 13.3 s, holding."]
    assert cases["B1"]["swell"][2:] == ["W 10–12 s, building offshore; due at Point Loma South "
                                        "around 1:32 PM, and at the breaks 39–53 min later."]


def test_each_swell_offshore_is_its_own_line_with_its_due_time(cases):
    """Owner's calls, 2026-10-24: no "first", and no "arriving since": a
    swell offshore is said only while a band of it is still to reach the
    breaks (the build decides, `briefing.next_band`)."""
    assert cases["C1"]["swell"][2] == ("NW 14–17 s, fading offshore; due at Point Loma South around 9:50 AM, "
                                       "and at the breaks 39–53 min later.")
    assert cases["C1"]["swell"][3].endswith("s, building offshore; due at Point Loma South around 1:32 PM, "
                                            "and at the breaks 39–53 min later.")
    assert not any("arriving" in line or " first" in line for case in cases.values() for line in case["swell"])


def test_a_mix_is_a_line_a_train_each_with_its_own_status(cases):
    """Owner's calls, 2026-10-23: every swell train at half the lead's height
    or more, from any point, a line each."""
    assert cases["M1"]["swell"] == ["3–4 ft (0.9–1.2 m).", "SSW at 15.4 s, fading.",
                                    "SSW at 14.3 s, holding.", "W at 10.0 s, building."]


def test_the_range_spans_all_three_breaks_and_the_heading_and_period_are_the_biggest_breaks(cases):
    assert cases["B1"]["swell"][:2] == ["2–5 ft (0.6–1.5 m).", "S at 18.2 s, building."]


def test_a_lead_train_with_no_heading_drops_its_slot(cases):
    assert cases["H1"]["swell"] == ["3–4 ft (0.9–1.2 m).", "At 13.3 s."]


def test_a_dark_buoy_says_so_and_nothing_else(cases):
    assert cases["D1"]["swell"] == ["No spectrum from CDIP 191 since Oct 21, 3:00 PM."]


def test_rain_shows_both_when_either_is_above_zero_and_neither_otherwise(cases):
    """"Rain", not "Precipitation" (owner's call, 2026-10-23)."""
    assert not any(line.startswith("Rain") for line in cases["Q1"]["conditions"])
    assert cases["B1"]["conditions"][-1] == \
        "Rain 0.03 in (0.8 mm) in the last hour (rain), 0.11 in (2.8 mm) in 24 h"
    assert cases["C1"]["conditions"][-1] == \
        "Rain 0.00 in (0.0 mm) in the last hour, 0.24 in (6.1 mm) in 24 h"


def test_the_conditions_are_a_ledger_with_arrows_and_pressure(cases):
    """Owner's calls, 2026-10-23: water, air, humidity, pressure, then rain,
    each with its arrow's direction; none where nothing earlier was read."""
    assert cases["Q1"]["conditions"] == ["Water 67 °F (19.4 °C), up", "Air 61 °F (16 °C), down",
                                         "Humidity 88%, steady", "Pressure 30.05 inHg (1018 hPa)"]


def test_the_tides_are_the_days_turns_am_and_pm(cases):
    assert cases["Q1"]["tides"] == ["AM low 0.7 ft (0.21 m) at 3:15 AM", "AM high 5.3 ft (1.62 m) at 9:32 AM",
                                    "PM low 1.8 ft (0.55 m) at 3:48 PM", "PM high 6.3 ft (1.92 m) at 10:05 PM"]
    assert cases["K1"]["tides"][0] == "AM low −0.7 ft (−0.21 m) at 6:40 AM"


def test_a_missing_reading_drops_its_line(cases):
    assert cases["K1"]["conditions"] == []


def test_every_number_is_imperial_first(cases):
    for cid, got in cases.items():
        text = _all(got)
        for ft in re.findall(r"(−?\d+\.\d) ft \((−?\d+\.\d\d) m\)", text):
            assert abs(float(ft[0].replace("−", "-")) / 3.28084 - float(ft[1].replace("−", "-"))) < 0.06, cid
        for f, c in re.findall(r"(\d+) °F \((\d+(?:\.\d)?) °C\)", text):
            assert abs((float(f) - 32) * 5 / 9 - float(c)) < 0.6, cid


def test_nothing_is_called_safe_or_dangerous(cases):
    for got in cases.values():
        text = _all(got).lower()
        for word in ("safe", "danger", "hazard", "rip", "accurate", "mellow", "pumping"):
            assert word not in text, word


def test_the_model_never_appears(cases):
    for got in cases.values():
        text = _all(got)
        assert "GFS" not in text and "model" not in text.lower() and "ensemble" not in text.lower()


def test_nothing_built_draws_no_fold(cases):
    assert cases["X1"] == {"line": None, "alerts": [], "swell": [], "conditions": [], "tides": [],
                           "water_quality": []}


def test_nws_alerts_are_the_top_line_by_nws_name_and_end(cases):
    assert cases["A1"]["alerts"] == ["Coastal Flood Warning until 2 PM Sun", "Small Craft Advisory in effect"]
    # None anywhere else, and one that ended by the reader's clock drops.
    assert all(not got["alerts"] for cid, got in cases.items() if cid != "A1")
    assert "High Surf Advisory" not in " ".join(cases["A1"]["alerts"])


def test_an_alert_is_an_update():
    from forecast import briefing

    quiet = briefing.with_text(briefingwording.QUIET)
    alerted = briefing.with_text({**briefingwording.QUIET, "alerts": [briefingwording.COASTAL_FLOOD]})
    assert alerted["update_words"][0] == "Coastal Flood Warning until 2 PM Sun"
    assert alerted["update_words"][1:] == quiet["update_words"]
    # A changed end is new words; the same alert re-sent is not.
    moved = {**briefingwording.COASTAL_FLOOD, "ends_utc": "2026-10-25T23:00:00Z"}
    assert briefing.with_text({**briefingwording.QUIET, "alerts": [moved]})["update_words"] != alerted["update_words"]
    resent = {**briefingwording.COASTAL_FLOOD, "id": "urn:oid:2.49.0.1.840.0.other.001.1"}
    assert briefing.with_text({**briefingwording.QUIET, "alerts": [resent]})["update_words"] == alerted["update_words"]


def test_water_quality_is_a_row_a_break_with_its_status_and_newest_sample(cases):
    assert cases["Q1"]["water_quality"] == [
        "North Open · Enterococcus 1,379 copies/100 mL on 21 Oct",
        "Center Open · Enterococcus 793 copies/100 mL on 21 Oct",
        "South Open · Enterococcus <195 copies/100 mL on 22 Oct"]        # "<" kept, "=" dropped


def test_an_advisory_says_the_countys_end_and_a_closure_with_none_says_none(cases):
    assert cases["R1"]["water_quality"][0] == "North Advisory until 11 AM Sat · Enterococcus 1,379 copies/100 mL on 21 Oct"
    south = cases["Z1"]["water_quality"][2]
    assert south.startswith("South Closed · ") and "until" not in south


def test_a_day_of_several_results_leads_with_ddpcr_enterococcus(cases):
    north, center = cases["Z1"]["water_quality"][:2]
    assert north == "North Open · Enterococcus 2,957 copies/100 mL on 20 Oct"
    assert center == "Center Open · no sample yet"


def test_a_status_read_too_long_ago_is_not_said_and_when_it_was_read_is(cases):
    for row in cases["S1"]["water_quality"]:
        assert "Open" not in row and "Status not read since 2:35 AM" in row and "copies/100 mL on" in row


def test_water_quality_words_are_an_update():
    from forecast import briefing

    quiet = briefing.with_text(briefingwording.QUIET)
    rain = briefing.with_text(next(b for cid, _, b in briefingwording.CASES if cid == "R1"))
    assert quiet["update_words"][-3:] == quiet["text"]["water_quality"]
    assert rain["update_words"] != quiet["update_words"]


def test_one_build_renders_for_the_record():
    got = briefingwording.render_issue(briefingwording.QUIET)
    assert got["line"] is None and got["swell"] and got["tides"]
