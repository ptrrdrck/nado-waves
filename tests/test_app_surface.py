"""The app surface has to keep the project's central rule on screen.

CLAUDE.md: "Until a verification series exists, the output is *physically
derived*, never *accurate*. That distinction belongs in the UI, not only the
README." A README can be honest while the screen quietly is not, so the screen
gets its own test.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parent.parent / "app" / "forecast.html"
SOURCE = APP.read_text(encoding="utf-8")
TEXT = re.sub(r"\s+", " ", SOURCE)


class TestItSaysWhatItIsStandingOn:
    def test_the_levels_come_from_the_data_not_a_fixed_list(self):
        """The two chains name different levels — Now has no 'model' row and
        Forecast has no 'waves observed' row — so the renderer walks whatever
        keys the file carries. That the keys are the right ones is pinned on
        the data side, in test_live and test_now."""

        assert "Object.keys(standing" in SOURCE

    def test_a_none_value_is_marked_rather_than_rendered_flat(self):
        """'calibration: none' and 'observation at the beach: none' are the
        two lines that matter most, so they are not allowed to read as
        ordinary prose."""

        assert '/^none/i.test(value)' in SOURCE
        assert '.none{' in SOURCE

    def test_the_page_states_nothing_has_measured_these_breaks(self):
        assert "Nothing has ever measured a wave at these three breaks" in TEXT

    def test_the_page_says_physically_derived_and_not_accurate(self):
        assert "physically derived" in TEXT
        assert "not an accurate forecast" in TEXT

    def test_the_page_refuses_the_words_a_verified_forecast_would_use(self):
        """No accuracy figure may appear without naming a verification series,
        and there is no verification series. The safest enforcement is that the
        vocabulary of accuracy is simply absent."""

        banned = ("RMSE", "accuracy", "within a foot", "confidence interval",
                  "error bar of", "% accurate")
        lowered = TEXT.lower()
        for word in banned:
            assert word.lower() not in lowered, f"app surface claims {word!r}"

    def test_it_says_the_number_is_not_a_wave_height_at_the_beach(self):
        assert "not a wave height" in TEXT and "at the beach" in TEXT

    def test_it_names_the_missing_shoaling_and_refraction(self):
        assert "no shoaling" in TEXT and "no refraction" in TEXT


class TestScope:
    def test_only_the_three_coronado_breaks_are_rendered(self):
        assert 'ORDER = ["coronado_north", "coronado_center", "coronado_south"]' in SOURCE

    def test_breakers_and_gator_are_absent(self):
        lowered = SOURCE.lower()
        assert "nasni" not in lowered and "gator" not in lowered


class TestProvenanceIsVisible:
    def test_an_unverified_blocker_is_marked_on_screen(self):
        assert "estimated" in TEXT
        assert "seg.guess" in SOURCE or "guess" in SOURCE

    def test_the_seaward_clip_is_not_dressed_up_as_land(self):
        from forecast.transform import SEAWARD_CLIP

        assert SEAWARD_CLIP in TEXT
        assert "nothing blocks it" in TEXT

    def test_the_page_publishes_the_swell_window_not_the_raw_open_arcs(self):
        """BRIEFING §12: the south-east arc ran across unmodelled Baja coast.
        It is modelled now, but the page still reads the guarded list."""

        assert "swell_window" in SOURCE
        assert "open_windows" not in SOURCE


class TestTheWindowsLeadTheCard:
    """Three windows per break, every edge on land, and they are the only
    thing on the card that is the same whichever tab you are on."""

    def test_the_card_names_each_window_by_the_land_either_side(self):
        """Never by a hardcoded "south / channel / west". The page would keep
        saying it after the geometry moved, and this geometry moved twice in
        one day."""

        assert "opened_by" in SOURCE and "closed_by" in SOURCE
        for hardcoded in ("island channel", "south window", "west window"):
            assert hardcoded not in SOURCE.lower()

    def test_the_windows_come_before_the_energy_on_the_card(self):
        card = SOURCE[SOURCE.index('<article class="card">'):]
        assert card.index("windowList") < card.index("window energy")

    def test_a_window_carries_its_span_not_just_its_edges(self):
        """23, 6 and 42 degrees. Three identical rows of numbers would read as
        three equivalent openings, so the span is printed and drawn."""

        assert "wide" in SOURCE
        assert 'class="bar"' in SOURCE

    def test_an_estimated_edge_is_marked_on_the_window_that_carries_it(self):
        assert "one edge estimated" in SOURCE
        assert ".win.soft" in SOURCE

    def test_no_open_window_is_a_sentence_not_an_empty_list(self):
        assert "no open window" in SOURCE


class TestTheGeometryProvenance:
    """The aperture is the one thing on this page with a citable source, and
    a reader who wants to check it can pull the chart."""

    def test_the_card_names_the_enc_charts(self):
        assert "NOAA ENC chart" in SOURCE
        assert "geometry modelled from" in SOURCE

    def test_the_line_is_composed_from_the_file_not_written_into_the_page(self):
        """A hardcoded provenance is a claim that stops being checked. The
        cells live in spots.json and the page reads whatever is there."""

        assert "geom.cells" in SOURCE
        for cell in ("US4CA1BX", "US4CA74M"):
            assert cell not in SOURCE

    def test_imagery_is_named_beside_the_charts(self):
        """Point Loma's tip is imagery and forms an edge printed directly
        above the line. "NOAA ENC" alone would let a reader take the whole
        aperture as charted."""

        assert "from_imagery" in SOURCE
        assert "from imagery" in SOURCE

    def test_the_provenance_reads_from_the_tab_on_screen(self):
        """The two chains carry the same geometry. Reading it from the other
        file would be the cross-tab leak the Now/Forecast split prevents."""

        assert 'provenanceLine((MODE === "now" ? NOW : DATA).geometry)' in SOURCE

    def test_the_assumed_spread_is_shown_rather_than_hidden(self):
        assert "spread_assumption" in SOURCE
        assert "Directional spread is assumed" in TEXT


class TestTheSeekBar:
    def test_it_opens_on_the_hour_nearest_now_not_the_first_hour(self):
        """A GFS-Wave cycle publishes about five hours after its nominal time,
        so hour zero is already past when anyone loads the page — it opened on
        5 a.m. for a reader standing on the sand at 2 p.m."""

        assert "Date.now()" in SOURCE
        assert "hour nearest NOW" in SOURCE

    def test_earlier_and_later_move_the_cursor(self):
        assert '$("earlier").onclick' in SOURCE and '$("later").onclick' in SOURCE
        assert "CURSOR -= 1" in SOURCE and "CURSOR += 1" in SOURCE

    def test_the_full_list_is_still_a_real_select(self):
        """Laid transparently over the label, so the native picker opens on tap
        and the control stays keyboard-reachable."""

        assert '<select id="when"' in SOURCE
        assert ".seek-when select" in SOURCE and "opacity:0" in SOURCE

    def test_the_ends_disable_rather_than_wrap(self):
        assert '$("earlier").disabled' in SOURCE and '$("later").disabled' in SOURCE


class TestWindAndTideAreHoisted:
    def test_they_render_above_the_breaks_not_inside_each_card(self):
        assert SOURCE.index('id="conditions"') < SOURCE.index('id="breaks"')

    def test_each_carries_its_source_underneath(self):
        assert "station_name" in SOURCE and "tide_station_name" in SOURCE
        assert 'class="src"' in SOURCE

    def test_the_tide_says_it_is_a_model(self):
        assert "harmonic prediction" in TEXT
        assert "a model, not a measurement" in TEXT

    def test_the_provenance_separates_a_forecast_hour_from_an_observation(self):
        """The model's wind moves with the picker; the KNZY fallback is an
        observation. Both appear, because which is shown depends on what the
        file carries — and since the titles are bare quantities now, the
        provenance line is the only thing telling them apart."""

        assert "GFS-Wave at the buoy for ${stampWhen}" in SOURCE
        assert "${wind.station_name} (${wind.station}), observed " in SOURCE
        assert "harmonic prediction for ${stampWhen}" in SOURCE

    def test_model_wind_is_named_as_a_forecast(self):
        assert "forecast, not a measurement" in TEXT

    def test_it_prefers_the_model_wind_and_falls_back(self):
        assert "hour.wind_from_deg != null" in SOURCE
        assert "wind.station_name" in SOURCE

    def test_the_per_break_offshore_reading_stays_on_the_card(self):
        """One station, so one wind — but the three shore normals span 29°, so
        what that wind MEANS is per break."""

        assert "c.windOffshore" in SOURCE
        assert "wind is <b>${senseText}</b> here" in SOURCE


class TestTheTwoChains:
    """Now and Forecast are not two views of one thing. Every input on the Now
    side is a measurement and every input on the Forecast side is a model, so
    each carries its own standing-on block and the page must not blur them."""

    def test_there_is_a_toggle_with_exactly_two_options(self):
        assert 'id="tab-now"' in SOURCE and 'id="tab-forecast"' in SOURCE
        assert 'role="tablist"' in SOURCE

    def test_it_opens_on_now(self):
        assert 'setMode("now")' in SOURCE
        assert "Opens on Now" in SOURCE

    def test_the_hour_picker_belongs_to_the_forecast_only(self):
        assert '$("seek").hidden = !forecasting' in SOURCE

    def test_each_chain_has_its_own_standing_on_block(self):
        """Rendered from whatever keys the file carries, because the two name
        different things — the Now side has no 'model' row and the Forecast
        side has no 'waves observed' row."""

        assert "Object.keys(standing" in SOURCE
        assert "renderStanding(NOW.standing_on" in SOURCE
        assert "renderStanding(DATA.standing_on" in SOURCE

    def test_now_labels_its_inputs_as_measurements(self):
        """The card titles are bare quantities, so the word that says these
        are measurements has to be in the provenance line, where the reader
        looks for where a number came from."""

        assert "observed ${observedAt(wind.observed_utc)}" in SOURCE
        assert "measured ${observedAt(tide.observed_utc)}" in SOURCE

    def test_forecast_labels_its_inputs_as_a_model(self):
        assert "forecast, not a measurement" in TEXT
        assert "a model, not a measurement" in TEXT

    def test_a_stale_observation_is_not_rendered_as_current(self):
        """NDBC has served 306-hour-old content behind an HTTP 200."""

        assert "This is not current" in TEXT
        assert "NOW.stale" in SOURCE

    def test_a_missing_observation_says_so_and_points_at_the_forecast(self):
        assert "No current observation" in TEXT
        assert "Switch to <b>Forecast</b>" in TEXT

    def test_now_shows_what_the_buoy_saw_beside_the_wind_and_tide(self):
        """The buoy's own reading is a condition like the others, so it is a
        card in the same strip rather than a dashed aside, and it carries its
        own provenance instead of leaving it stranded below the breaks."""

        assert "observed ${observedAt(NOW.observed_utc)}" in SOURCE
        assert 'id="buoy"' not in SOURCE

    def test_both_chains_render_through_one_card_shape(self):
        assert "cardsForNow" in SOURCE and "cardsForForecast" in SOURCE

    def test_the_spread_note_is_omitted_when_none_is_assumed(self):
        """The spectral path assumes no spread, and printing 'assumed at
        undefined' is worse than saying nothing."""

        assert "spread.swell_deg != null" in SOURCE
        assert "no spread is assumed" in TEXT


class TestUnits:
    """Imperial leads, metric in parentheses, everywhere a number is shown.
    The data model stays SI: NDBC and WAVEWATCH III publish metres and knots,
    and putting a conversion between the source and every cross-check is how a
    3.28 ends up somewhere it should not be."""

    def test_there_is_one_place_each_conversion_happens(self):
        assert "const FT_PER_M = 3.28084" in SOURCE
        assert "const MPH_PER_KT = 1.15078" in SOURCE
        assert SOURCE.count("3.28084") == 1
        assert SOURCE.count("1.15078") == 1

    def test_height_puts_feet_first(self):
        assert 'FT_PER_M).toFixed(1)} ft <span class="unit">(${m.toFixed(2)} m)' in SOURCE

    def test_speed_puts_mph_first(self):
        assert 'MPH_PER_KT)} mph <span class="unit">(${Math.round(kt)} kt)' in SOURCE

    def test_nothing_still_renders_a_bare_metric_value(self):
        assert "metres(" not in SOURCE and "feet(" not in SOURCE
        assert "} kt`" not in SOURCE

    def test_the_python_side_shares_the_same_rule(self):
        from forecast.units import height, speed

        assert height(0.71) == "2.3 ft (0.71 m)"
        assert speed(8) == "9 mph (8 kt)"
        assert height(None) == "\u2014" and speed(None) == "\u2014"

    def test_the_measured_bias_is_stated_in_both(self):
        """It is a measurement shown to a reader like any other."""

        from forecast.live import build

        from tests.test_live import SOUTH, bulletin, CYCLE

        got = build(bulletin=bulletin(SOUTH), now=CYCLE)
        assert "0.9\u20131.0 ft (0.26\u20130.31 m)" in got.standing_on["model"]


class TestTheSourceLine:
    def test_the_page_has_no_title_heading(self):
        assert "<h1>" not in SOURCE

    def test_the_cycle_line_explains_itself_and_sits_below_the_breaks(self):
        """Forecast only. On the observed side the provenance moved up onto
        the swell card, so there is nothing left to say down here."""

        assert SOURCE.index('id="breaks"') < SOURCE.index('id="cycle"')
        assert "Latest data from the" in TEXT
        assert '$("cycle").innerHTML = "";' in SOURCE
        assert "Latest data from the" in TEXT
        assert "model run of" in TEXT and "offshore buoy" in TEXT

    def test_it_names_the_buoy_rather_than_only_its_number(self):
        assert "DATA.station_name" in SOURCE and "NDBC ${DATA.station}" in SOURCE
        assert "NOW.station_name" in SOURCE and "NDBC ${NOW.station}" in SOURCE


class TestItDegradesVisibly:
    def test_a_failed_load_tells_the_reader_what_to_run(self):
        assert "Could not load" in TEXT
        assert "forecast.live" in TEXT

    def test_missing_wind_and_tide_render_as_not_collected(self):
        assert "not collected yet" in TEXT


class TestThePageIsSelfContainedAndThemed:
    def test_it_declares_a_title_that_is_a_name(self):
        title = re.search(r"<title>(.*?)</title>", SOURCE).group(1)
        assert title and len(title.split()) <= 5

    def test_dark_mode_is_defined_both_ways(self):
        assert 'prefers-color-scheme: dark' in SOURCE
        assert ':root[data-theme="dark"]' in SOURCE

    def test_body_has_an_explicit_background(self):
        assert re.search(r"body\{[^}]*background:var\(--paper\)", TEXT.replace(" ", ""))

    def test_it_loads_no_script_from_a_third_party(self):
        assert not re.search(r"<script[^>]+src=", SOURCE)


class TestItMatchesTheLiveOutput:
    """The page reads fields the forecast actually writes. A rename in
    forecast.live that silently blanks the screen is the failure this catches."""

    def test_every_field_the_page_reads_exists_in_the_dataclasses(self):
        from dataclasses import fields

        from forecast.live import BreakForecast, Forecast, Hour, WindAtTime

        known = set()
        for cls in (Forecast, BreakForecast, Hour, WindAtTime):
            known |= {f.name for f in fields(cls)}
        known |= {"blocker", "share", "verified"}       # taken_by entries
        known |= {"swell_deg", "wind_sea_deg", "note"}  # spread_assumption
        known |= {"hs_m", "period_s", "from_deg", "wind_sea"}  # train entries
        known |= {"peak_period_s", "peak_direction_deg", "frequency_bins"}  # buoy
        known |= {"age_hours", "observed_utc", "trains", "height_m", "kind"}

        for accessor in re.findall(r"\b(?:hour|entry|data|t|spread)\.([a-z_]{3,})\b", SOURCE):
            if accessor in {"map", "filter", "find", "join", "length", "split",
                            "toFixed", "textContent", "innerHTML"}:
                continue
            assert accessor in known, f"page reads unknown field {accessor!r}"


class TestWaveTrainsOnScreen:
    """When the geometry takes the dominant swell, the secondary leads at the
    beach. That re-ordering happened on 92 of 400 archived spectra, so the
    surface lists the trains rather than collapsing them to one 'dominant'."""

    def test_there_is_a_train_renderer_shared_by_both_chains(self):
        assert "function trainList" in SOURCE
        assert "trainList(buoy.trains)" in SOURCE
        assert "trainList(c.trains" in SOURCE

    def test_a_train_shows_height_period_and_heading(self):
        assert "height(t.hs_m)" in SOURCE
        assert "t.period_s.toFixed(1)" in SOURCE
        assert "compass(t.from_deg)" in SOURCE

    def test_the_leading_train_is_emphasised(self):
        assert 'i === 0 ? " lead"' in SOURCE
        assert ".train.lead" in SOURCE

    def test_wind_sea_is_labelled(self):
        assert "wind sea" in TEXT

    def test_the_break_card_says_these_are_the_ones_reaching_here(self):
        assert "swell reaching here" in TEXT

    def test_the_swell_card_is_styled_like_wind_and_tide(self):
        """Same .cond card in the same strip, not a dashed aside."""

        swell = SOURCE.index('label: "Swell"')
        assert SOURCE.count('class="cond"') >= 3
        assert SOURCE.rindex('<div class="cond">', 0, swell) > 0

    def test_the_footer_does_not_describe_the_forecast_on_the_observed_tab(self):
        """Printing a model's build time and spread under a measurement would
        attribute the model's properties to the observation."""

        assert "function renderFooter" in SOURCE
        assert 'if (MODE === "now")' in SOURCE
        assert "nothing here is measured at the sand" in TEXT


class TestTheSwellCardIsOnBothTabs:
    """It was built into the Now branch only, so the Forecast tab had wind and
    tide but nothing for the swell the page is actually about."""

    def test_one_builder_serves_both_chains(self):
        assert "function swellCard" in SOURCE
        assert SOURCE.count("rows.push(swellCard({") == 2

    def test_the_observed_card_names_its_measurement(self):
        assert "${NOW.station_name} (NDBC ${NOW.station}), observed " in SOURCE

    def test_the_forecast_card_names_its_model(self):
        assert "GFS-Wave at ${DATA.station_name}" in SOURCE
        assert "forecast, not a measurement" in TEXT

    def test_the_forecast_card_reads_the_per_hour_buoy_series(self):
        assert "(DATA.buoy || []).find" in SOURCE
        assert "b.valid_utc === stamp.valid_utc" in SOURCE

    def test_a_cycle_without_a_spectrum_says_why_there_are_no_trains(self):
        assert "spectral product was unavailable" in TEXT


class TestTheProvenanceLines:
    """The card titles were carrying what the tab and the provenance already
    said. Stripping them to the bare quantity only works if the provenance
    line underneath actually carries the rest — which moment, whose
    measurement, and how old."""

    def test_the_titles_are_bare_quantities(self):
        for label in ('label: "Swell"', '<span class="lbl">Wind</span>',
                      '<span class="lbl">Tide</span>'):
            assert label in SOURCE, label
        # The hour left the titles, so it has to be in the model's provenance
        # or the forecast card no longer says which moment it describes.
        assert "for ${stampWhen}" in SOURCE

    def test_every_provenance_line_ends_in_a_full_stop(self):
        """Including the collector's own notes, which do not all carry one —
        `period` is applied at the card, not trusted to the note."""

        assert "const period = (s) =>" in SOURCE
        bare = [m for m in re.findall(r'<span class="src">\$\{(.{0,40})', SOURCE)
                if not m.startswith(("period(", "period ("))]
        assert not bare, f"provenance not routed through period(): {bare}"

    def test_the_age_is_derived_from_the_timestamp_not_read_from_the_file(self):
        """now.json's `age_hours` freezes the instant the file is written, and
        the file is rebuilt once an hour, so a page showing it reported an age
        that was wrong on load and never moved afterwards."""

        assert "NOW.age_hours" not in SOURCE
        assert "Date.now() - new Date(iso).getTime()" in SOURCE
        assert "setInterval(() => { if (MODE === \"now\") show(); }, 60000)" in SOURCE

    def test_the_clock_can_only_add_staleness_never_remove_it(self):
        """The build refused to call a reading current for reasons the page
        cannot see, so the flag is a floor. NOW.stale_hours carries the limit
        rather than the page keeping a second copy of it."""

        assert "NOW.stale || (observedAge != null && observedAge > limit)" in SOURCE
        assert "NOW.stale_hours" in SOURCE

        from forecast.now import STALE_HOURS, Now

        assert "stale_hours" in Now.__dataclass_fields__
        assert Now.__dataclass_fields__["stale_hours"].default == STALE_HOURS


class TestTheAgeFormatter:
    """Ran in node, because "1.02 h ago" versus "1 h 1 min ago" is a property
    of the arithmetic and a grep cannot tell them apart."""

    CASES = [
        (0.0, "just now"),
        (0.4 / 60, "just now"),
        (1.0 / 60, "1 min ago"),
        (59.0 / 60, "59 min ago"),
        (1.0, "1 h ago"),
        (1.02, "1 h 1 min ago"),
        (2.5, "2 h 30 min ago"),
        (25.0, "25 h ago"),
        (-1.0, "just now"),          # a reader's clock behind the buoy's
    ]

    def test_it_reads_in_hours_and_minutes(self):
        node = shutil.which("node")
        if node is None:
            pytest.skip("node is not available")

        start = SOURCE.index("function ago(hours) {")
        body = SOURCE[start:SOURCE.index("\n}\n", start) + 2]

        script = body + "\n" + "\n".join(
            f"console.log(JSON.stringify(ago({hours!r})));" for hours, _ in self.CASES
        )
        out = subprocess.run([node, "-e", script], capture_output=True, text=True,
                             check=True).stdout.split("\n")
        got = [json.loads(line) for line in out if line.strip()]
        assert got == [want for _, want in self.CASES]

    def test_a_missing_timestamp_produces_no_age_rather_than_a_guess(self):
        node = shutil.which("node")
        if node is None:
            pytest.skip("node is not available")

        start = SOURCE.index("function ageHours(iso) {")
        body = SOURCE[start:SOURCE.index("\n}\n", start) + 2]
        out = subprocess.run(
            [node, "-e", body + '\nconsole.log(JSON.stringify(['
                          'ageHours(null), ageHours(""), ageHours("not a date")]));'],
            capture_output=True, text=True, check=True).stdout
        assert json.loads(out) == [None, None, None]


class TestTheTideSaysWhichWayItIsGoing:
    """A water level alone does not tell anyone whether to go now or in three
    hours. The turn does — and it is a prediction sitting on a tab that is
    otherwise measurements only, so the card has to say so."""

    def test_the_direction_word_is_the_bright_one(self):
        assert "<b>${turn.direction}</b> to ${height(turn.height_m)}" in SOURCE
        assert ".cond .turn b{color:var(--ink)" in SOURCE

    def test_the_direction_is_read_off_the_turn_not_differenced(self):
        """Measured, differencing the water level reads backwards on 19.5% of
        6-minute samples. The page has the measured series available and must
        not be tempted by it."""

        assert "turn.direction" in SOURCE
        assert "nextTurn(turns, afterIso)" in SOURCE
        for tempting in ("tide.height_m -", "- prevTide", "slope("):
            assert tempting not in SOURCE, tempting

    def test_the_observed_tab_marks_the_turn_as_a_prediction(self):
        """The level beside it is measured. An unlabelled turn would make the
        whole card read as an observation."""

        assert "{tagged: true}" in SOURCE
        assert '<span class="tag">predicted</span>' in SOURCE

    def test_the_forecast_tab_does_not_repeat_the_tag(self):
        """Everything on that tab is a model and its provenance says so."""

        assert "turnLine(DATA.tide_turns || [], stamp.valid_utc)" in SOURCE

    def test_the_observed_turn_is_asked_for_against_the_readers_clock(self):
        """BRIEFING §18: a 'next turn' baked in at build time stops being the
        next turn the moment it passes, on a page that sits open for hours."""

        assert "new Date().toISOString(), {tagged: true}" in SOURCE

    def test_a_far_off_turn_carries_its_weekday(self):
        """'at 11:42 AM' is not an answer six days out. Run in node against a
        fixed timezone, because same-local-day is the whole question and a
        grep cannot tell a correct comparison from a wrong one."""

        node = shutil.which("node")
        if node is None:
            pytest.skip("node is not available")

        start = SOURCE.index("const clock = (iso) =>")
        body = SOURCE[start:SOURCE.index("\n}\n", SOURCE.index("function turnClock")) + 2]

        cases = [
            # (turn, asked-about, expects a weekday)
            ("2026-09-19T18:42:00Z", "2026-09-19T13:00:00Z", False),  # later today
            ("2026-09-20T14:00:00Z", "2026-09-19T13:00:00Z", True),   # tomorrow
            ("2026-09-25T14:00:00Z", "2026-09-19T13:00:00Z", True),   # next week
            # Crosses UTC midnight but not the LOCAL one: still today.
            ("2026-09-20T03:00:00Z", "2026-09-19T22:00:00Z", False),
        ]
        script = body + "\n" + "\n".join(
            f'console.log(JSON.stringify(turnClock({t!r}, {f!r})));' for t, f, _ in cases
        )
        out = subprocess.run(
            [node, "-e", script], capture_output=True, text=True, check=True,
            env={**os.environ, "TZ": "America/Los_Angeles"},
        ).stdout.splitlines()
        got = [json.loads(line) for line in out if line.strip()]
        assert len(got) == len(cases)
        for text, (turn, _asked, wants_day) in zip(got, cases):
            has_day = any(d in text for d in
                          ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"))
            assert has_day == wants_day, f"{turn} -> {text!r}"

    def test_an_uncollected_turn_renders_nothing_rather_than_a_guess(self):
        assert "if (!turn || !turn.direction || turn.height_m == null) return \"\"" in SOURCE


class TestEveryMeasurementSaysHowOldItIs:
    """A reading's timestamp answers "when", not "is this current". 4:52 AM is
    twelve minutes ago at breakfast and nine hours ago after work, and the
    second is a different card."""

    def test_all_four_measurement_lines_go_through_one_helper(self):
        """Three cards on Now plus the forecast tab's KNZY fallback. Four
        hand-rolled age expressions is four chances to drift."""

        assert "function observedAt" in SOURCE
        assert SOURCE.count("observedAt(") == 5      # the definition plus four uses
        for site in ("observed ${observedAt(NOW.observed_utc)}",
                     "observed ${observedAt(wind.observed_utc)}",
                     "measured ${observedAt(tide.observed_utc)}"):
            assert site in SOURCE, site

    def test_the_forecast_tabs_observed_wind_fallback_is_aged_too(self):
        """It only appears when the model has no wind for that hour, which is
        exactly when how old the substitute is matters."""

        wind_block = SOURCE[SOURCE.index("GFS-Wave at the buoy for ${stampWhen}"):]
        assert "observed ${observedAt(wind.observed_utc)}" in wind_block[:400]

    def test_a_prediction_is_never_given_an_age(self):
        """A modelled wind or a harmonic tide is a forecast FOR a moment, not a
        reading taken AT one. "23 h ago" under next Tuesday would be nonsense,
        so those lines use `stampWhen` and never `observedAt`."""

        for predicted in ("GFS-Wave at the buoy for ${stampWhen}",
                          "harmonic prediction for ${stampWhen}",
                          "(NDBC ${DATA.station}) for ${stampWhen}"):
            assert predicted in SOURCE, predicted
        assert "observedAt(stamp" not in SOURCE
        assert "observedAt(t." not in SOURCE

    def test_the_age_is_not_read_from_the_frozen_field(self):
        """now.json carries `tide.age_minutes` computed at build time, and the
        file is rebuilt once an hour — BRIEFING §18 flagged it as the next
        instance of the same trap if it were ever displayed. It is displayed
        now, and it is not read from there."""

        code = "\n".join(line for line in SOURCE.splitlines()
                          if not line.lstrip().startswith("//"))
        assert "age_minutes" not in code
        assert "age_hours" not in code
        # The control: the prose explaining why they are unused is still there,
        # so this passes because the fields are unread rather than because the
        # comment stripper ate the whole file.
        assert "age_hours" in SOURCE and "age_minutes" in SOURCE
