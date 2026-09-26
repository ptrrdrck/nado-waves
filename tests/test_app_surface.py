"""The app surface has to keep the project's central rule on screen.

CLAUDE.md: "Until a verification series exists, the output is *physically
derived*, never *accurate*. That distinction belongs in the UI, not only the
README." A README can be honest while the screen quietly is not, so the screen
gets its own test.

The caveat, the cycle line, each chain's standing-on block and its footnote
live on `app/info.html`, linked from the foot of the main page, so the rules
that govern them are pinned there (`INFO`) and the vocabulary rule is pinned on
both pages.
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
INFO_PAGE = APP.parent / "info.html"
INFO = INFO_PAGE.read_text(encoding="utf-8")
INFO_TEXT = re.sub(r"\s+", " ", INFO)


class TestItSaysWhatItIsStandingOn:
    def test_the_levels_come_from_the_data_not_a_fixed_list(self):
        """The two chains name different levels — Now has no 'model' row and
        Forecast has no 'waves observed' row — so the renderer walks whatever
        keys the file carries. That the keys are the right ones is pinned on
        the data side, in test_live and test_now."""

        assert "Object.keys(standing" in INFO

    def test_a_none_value_is_marked_rather_than_rendered_flat(self):
        """'calibration: none' and 'observation at the beach: none' are the
        two lines that matter most, so they are not allowed to read as
        ordinary prose."""

        assert '/^none/i.test(value)' in INFO
        assert '.none{' in INFO

    def test_the_page_states_nothing_has_measured_these_breaks(self):
        assert "Nothing has ever measured a wave at these three breaks" in INFO_TEXT

    def test_the_page_says_physically_derived_and_not_accurate(self):
        assert "physically derived" in INFO_TEXT
        assert "not an accurate forecast" in INFO_TEXT

    def test_the_main_page_links_to_where_that_is_said(self):
        """Moved one tap away, so the tap has to be there: Info, directly
        beneath Geometry, outside anything a render rewrites."""

        links = SOURCE[SOURCE.index('<nav class="links"'):]
        links = links[:links.index("</nav>")]
        assert '<a href="geometry.html">Geometry</a>' in links
        assert '<a href="info.html">Info</a>' in links
        assert links.index('href="geometry.html"') < links.index('href="info.html"')
        assert SOURCE.index('id="conditions"') < SOURCE.index('<nav class="links"')

    def test_info_links_back(self):
        assert 'href="./"' in INFO

    def test_the_page_refuses_the_words_a_verified_forecast_would_use(self):
        """No accuracy figure may appear without naming a verification series,
        and there is no verification series. The safest enforcement is that the
        vocabulary of accuracy is simply absent."""

        banned = ("RMSE", "accuracy", "within a foot", "confidence interval",
                  "error bar of", "% accurate")
        for page in (TEXT, INFO_TEXT):
            lowered = page.lower()
            for word in banned:
                assert word.lower() not in lowered, f"app surface claims {word!r}"

    def test_it_says_the_number_is_not_a_wave_height_at_the_beach(self):
        assert "not a wave height" in INFO_TEXT and "at the beach" in INFO_TEXT

    def test_it_names_what_is_modelled_and_what_is_still_missing(self):
        """Refraction and shoaling are modelled since 2026-09-25, friction and
        breaking since 2026-09-26, so the page says so — and says what is
        still absent: the transfer to a surf height, this season's sand, and
        any check against the beach."""

        assert "bent over the seabed" in INFO_TEXT and "shoaling" in INFO_TEXT
        assert "friction" in INFO_TEXT and "until it breaks" in INFO_TEXT
        assert "not a face height" in INFO_TEXT and "has not been fitted" in INFO_TEXT
        assert "2016 survey" in INFO_TEXT
        assert "nothing has checked it" in INFO_TEXT


class TestTheTideCardSaysWhereItIs:
    """The numbers are the open coast's; the source line says so and names
    the gauge they were carried from, on both tabs."""

    def test_both_tabs_use_one_source_line(self):
        assert SOURCE.count("tideSource(NOW)") == 1
        assert SOURCE.count("tideSource(DATA)") == 1
        fn = SOURCE[SOURCE.index("function tideSource"):]
        fn = fn[:fn.index("\n}\n")]
        assert "carried from" in fn
        assert "payload.tide_site ?" in fn        # an older payload is the gauge's own


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


class TestTheBreakCard:
    """Three windows per break, every edge on land, beneath the energy that
    gets through them."""

    def test_the_card_names_each_window_by_the_land_either_side(self):
        """Never by a hardcoded "south / channel / west". The page would keep
        saying it after the geometry moved, and this geometry moved twice in
        one day."""

        assert "opened_by" in SOURCE and "closed_by" in SOURCE
        for hardcoded in ("island channel", "south window", "west window"):
            assert hardcoded not in SOURCE.lower()

    def test_the_reading_leads_the_card_and_the_geometry_follows(self):
        """Owner's layout, 2026-09-25: the nearshore height labelled with its
        depth; the trains; the drawing; the line stating how the height was
        calculated, in the provenance style; a rule; the wind reading; then
        the windows and the shares."""

        panel = SOURCE[SOURCE.index("function breakPanel"):]
        panel = panel[:panel.index("function depthLabel")]
        order = ("depthLabel(c)", "trainList(c.trains)",
                 "drawing || windowList(c.swellWindow)", "calculationLine(c)")
        at = [panel.index(mark) for mark in order]
        assert at == sorted(at)
        # The windows and the shares are in the drawing now (2026-09-26); the
        # list's sentence survives only for when there is nothing to draw.
        assert "taking the swell" not in panel and "<hr>" not in panel
        # The wind verdict moved to the Wind card (owner's call, 2026-09-26).
        assert "wind is" not in panel and "windOffshore" not in panel
        for gone in ("window energy", "swell reaching here"):
            assert gone not in panel
        assert "from the buoy to the break" not in SOURCE

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


class TestTheDrawingIsInteractive:
    """Owner's design, 2026-09-26: tap a shadow, a window or an arrow for its
    detail in place of "facing"; tap it again for the default drawing."""

    DRAW = SOURCE[SOURCE.index("function windowDrawing"):]
    DRAW = DRAW[:DRAW.index("// The buoy's tab")]

    def test_each_kind_says_what_the_owner_asked_for(self):
        assert "blocking ${shareText(tb.share)} of this swell" in self.DRAW
        assert ("${shortBlocker(win.opened_by)} \u2192 ${shortBlocker(win.closed_by)}, "
                in self.DRAW)
        assert "° wide" in self.DRAW
        assert "${heightText(t.hs_m)} at ${t.period_s.toFixed(1)} s, ${point(t.from_deg)}" in self.DRAW

    def test_a_second_tap_returns_to_the_default(self):
        fn = SOURCE[SOURCE.index("function togglePick"):]
        fn = fn[:fn.index("\n}\n")]
        assert "PICKED[id] !== key ? key : null" in fn

    def test_each_pick_shows_only_its_own_edges_and_line(self):
        fn = SOURCE[SOURCE.index("function showPick"):]
        fn = fn[:fn.index("\n}\n")]
        assert 'const want = key || "default";' in fn
        assert '[data-show]' in fn

    def test_thin_sections_can_still_be_hit(self):
        """The island shadows are 2-5 degrees wide beside a 6-degree channel."""

        fn = SOURCE[SOURCE.index("function pickAt"):]
        fn = fn[:fn.index("\n}\n")]
        assert "s.a1 - s.a0 < 5 && off(s) <= 2.5" in fn

    def test_the_keyboard_reaches_every_section(self):
        assert self.DRAW.count('tabindex="0" role="button"') == 3   # window, shadow, arrow
        assert 'e.key !== "Enter" && e.key !== " "' in self.DRAW

    def test_the_pick_survives_a_re_render(self):
        assert '$("conditions").innerHTML = rows.join("");\n  restorePicks();' in SOURCE

    def test_swell_aimed_behind_the_beach_is_the_sand_not_a_shadow(self):
        assert "taken(AWAY)" in self.DRAW and "nothing blocks it" in self.DRAW
        assert 'geo.away ? "away" : ""' in self.DRAW

    def test_it_is_bigger_than_it_was(self):
        assert "const DRAW = {w: 320, h: 200, cx: 160, cy: 162, r: 140, rim: 1};" in SOURCE


class TestTheBreakDrawing:
    """Each break's windows drawn facing the way the break faces: blocker
    shadows shaded grey, edges as rays, the break's own trains as arrows. An
    illustration, not a chart -- no scale, no distances, no pan or zoom."""

    DRAW = SOURCE[SOURCE.index("function windowDrawing"):]
    DRAW = DRAW[:DRAW.index("// The buoy's tab")]

    def test_it_is_turned_to_the_breaks_own_normal(self):
        """The three normals span 27 degrees, so the drawing reads each
        break's from its own payload entry, on both chains."""

        assert SOURCE.count("normal: b.shore_normal_deg") == 2
        assert "b - c.normal" in self.DRAW

    def test_without_a_normal_it_is_left_out_rather_than_guessed(self):
        assert 'if (c.normal == null || !isFinite(c.normal)) return "";' in self.DRAW

    def test_nothing_about_the_coast_is_typed_in_it(self):
        """The drawing names the land now (owner's design, 2026-09-26) --
        only ever from the payload: window edges and `taken_by`."""

        for typed in ("Point Loma", "Baja", "Islands", "Coronado"):
            assert typed not in self.DRAW
        assert "win.opened_by" in self.DRAW and "tb.blocker === name" in self.DRAW

    def test_the_arrows_are_the_breaks_trains_with_the_leader_emphasised(self):
        assert "c.trains" in self.DRAW and "buoy" not in self.DRAW
        assert "const lead = i === 0;" in self.DRAW

    def test_an_arrowhead_is_the_colour_of_its_leg(self):
        """A marker's `context-stroke` fill is not supported everywhere, and
        where it is not the heads came out black and grey. The head is drawn
        as its own shape in the leg's colour, faded with it as one group."""

        assert "<marker" not in self.DRAW and "context-stroke" not in SOURCE
        assert ".aperture .swell polygon{fill:var(--surf)}" in SOURCE
        assert ".aperture .swell line{stroke:var(--surf)" in SOURCE

    def test_the_leg_stops_inside_the_head(self):
        assert "tip + 0.6 * len" in self.DRAW

    def test_shadows_and_rays_reach_the_outer_edge_of_the_rim(self):
        """The rim is a stroke centred on r; ending at r stops halfway
        through it."""

        assert "const outer = r + DRAW.rim / 2;" in self.DRAW
        assert "wedge(sh.a0, sh.a1, outer)" in self.DRAW
        assert "at(a, outer)" in self.DRAW

    def test_a_train_from_behind_the_beach_is_not_drawn(self):
        assert "a > -90 && a < 90" in self.DRAW

    def test_it_does_not_pan_or_zoom(self):
        for handler in ("wheel", "zoom", "pointerdown", "touchstart", "drag"):
            assert handler not in self.DRAW

    def test_by_default_only_the_two_outer_edges_are_labelled(self):
        """The Baja tangent and the Point Loma tip bound the whole aperture.
        The island edges are drawn as rays but carry no label until their
        section is picked -- four of them inside about thirteen degrees was
        more text than the drawing holds."""

        assert ('[label(wins[0].a0, "default"), label(wins[wins.length - 1].a1, "default")]'
                in self.DRAW)
        assert 'class="ray"' in self.DRAW
        assert 'show === "default" ? "" : " hidden"' in self.DRAW

    def test_the_shadows_are_grey_and_the_chord_is_blue(self):
        assert ".aperture .shadow{fill:var(--faint)" in SOURCE
        assert ".aperture .chord{stroke:var(--surf)" in SOURCE
        assert ".aperture .spot{fill:var(--surf)" in SOURCE


class TestTheGeometryProvenance:
    """The aperture is the one thing on this page with a citable source, and
    a reader who wants to check it can pull the chart.

    Taken off the break cards 2026-09-25 by decision. It is not lost:
    geometry.html, linked from the foot of the live page, names the ENC cell
    behind every vertex and marks anything still traced from imagery."""

    GEOMETRY = (APP.parent / "geometry.html").read_text(encoding="utf-8")

    def test_the_break_card_no_longer_carries_it(self):
        assert "geometry modelled from" not in SOURCE
        assert "provenanceLine" not in SOURCE

    def test_the_geometry_page_names_the_charts_and_the_imagery(self):
        assert "NOAA ENC" in self.GEOMETRY
        assert "traced from imagery" in self.GEOMETRY

    def test_the_live_page_still_links_to_it(self):
        assert 'href="geometry.html"' in SOURCE

    def test_the_assumed_spread_is_shown_rather_than_hidden(self):
        assert "spread_assumption" in INFO
        assert "Directional spread is assumed" in INFO_TEXT


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
    def test_they_are_cards_of_their_own_not_inside_a_break_tab(self):
        """The breaks are tabs of the swell card now, so wind and tide sit
        beside that card rather than above three. What the rule is for is
        unchanged: one station feeds all three breaks, so its reading is never
        repeated inside a break's tab."""

        panel = SOURCE[SOURCE.index("function breakPanel"):SOURCE.index("function buoyPanel")]
        for reading in ("wind.from_deg", "wind.speed_kt", "tide.height_m", ">Wind<", ">Tide<"):
            assert reading not in panel, reading
        block = SOURCE[SOURCE.index("function renderConditions"):]
        swell = block.index("rows.push(swellCard({")
        assert swell < block.index('<span class="lbl">Wind</span>')
        assert swell < block.index('<span class="lbl">Tide</span>')

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

    def test_the_per_break_offshore_reading_stays_per_break(self):
        """One station, so one wind — but the three shore normals span 27°, so
        what that wind MEANS is per break. It sits on the Wind card as one
        line per break, shown only for the break whose swell tab is open, and
        says so ("at this break")."""

        fn = SOURCE[SOURCE.index("function windAtBreaks"):]
        fn = fn[:fn.index("\n}\n")]
        assert "c.windOffshore" in fn
        assert "<b>${s}</b> at this break" in fn
        assert 'data-wind-for="${c.id}"' in fn and "c.id === SWELL_TAB" in fn
        select = SOURCE[SOURCE.index("function selectSwellTab"):]
        select = select[:select.index("\n}\n")]
        assert "[data-wind-for]" in select        # it follows the tab

    def test_the_verdict_is_on_the_observed_tab_only(self):
        """The forecast's wind is GFS-Wave's at the buoy, not KNZY's at the
        beach, and a verdict against the shore normal needs the local wind."""

        assert SOURCE.count("? windAtBreaks(cards) :") == 1      # one call, not the definition
        now = SOURCE[SOURCE.index('if (MODE === "now") {'):]
        now = now[:now.index("  } else {")]
        assert "windAtBreaks(cards)" in now

    def test_it_is_styled_as_the_tides_next_turn(self):
        fn = SOURCE[SOURCE.index("function windAtBreaks"):]
        assert '<span class="turn"' in fn[:800]


class TestTheTwoChains:
    """Now and Forecast are not two views of one thing. Every input on the Now
    side is a measurement and every input on the Forecast side is a model, so
    each carries its own standing-on block and the page must not blur them."""

    def test_there_is_a_toggle_with_exactly_two_options(self):
        assert 'id="tab-now"' in SOURCE and 'id="tab-forecast"' in SOURCE
        assert 'role="tablist"' in SOURCE

    def test_it_opens_on_now(self):
        """On a fresh visit. Only a value the page itself stored can open it
        on Forecast; anything else in storage opens on Now."""

        assert 'setMode("now")' in SOURCE
        assert "Opens on Now" in SOURCE
        assert 'setMode(recall(KEEP.mode) === "forecast" ? "forecast" : "now")' in SOURCE

    def test_the_tab_choices_survive_a_refresh_but_not_a_new_visit(self):
        """sessionStorage, not localStorage: a reload keeps the reader where
        they were, and a new visit still opens on Now."""

        assert "remember(KEEP.mode, mode)" in SOURCE
        assert "remember(KEEP.swell, id)" in SOURCE
        assert "SWELL_TAB = recall(KEEP.swell)" in SOURCE
        assert "localStorage." not in SOURCE

    def test_storage_that_throws_does_not_break_the_page(self):
        """Private modes and blocked site data throw on the accessor itself."""

        for fn in ("function recall", "function remember"):
            body = SOURCE[SOURCE.index(fn):]
            body = body[:body.index("\n}\n")]
            assert "try {" in body and "sessionStorage" in body

    def test_the_hour_picker_belongs_to_the_forecast_only(self):
        assert '$("seek").hidden = !forecasting' in SOURCE

    def test_each_chain_has_its_own_standing_on_block(self):
        """Rendered from whatever keys the file carries, because the two name
        different things — the Now side has no 'model' row and the Forecast
        side has no 'waves observed' row. On info.html both are shown, each
        under its own heading and each from its own file."""

        assert "Object.keys(standing" in INFO
        assert 'renderStanding($("standing-now"), NOW.standing_on' in INFO
        assert 'renderStanding($("standing-forecast"), DATA.standing_on' in INFO
        assert "What Now is standing on" in INFO
        assert "What Forecast is standing on" in INFO

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
        """NDBC has served 306-hour-old content behind an HTTP 200.

        The banner that used to say so above the cards is gone. It spoke for
        all three cards at once while naming only the spectrum, so a fresh wind
        reading sat under a notice calling it not current and a dead wind
        station sat under nothing at all. The judgement now lands on the card
        whose own source is late: the swell card is forced overdue by the
        build's flag, and overdue renders in the signal colour.

        What must not come back is a page that renders a stale reading with no
        mark on it at all, so the three halves are pinned together here.
        """

        assert "NOW.stale" in SOURCE
        assert "forceOver: nowIsStale()" in SOURCE
        assert "function nowIsStale()" in SOURCE
        assert ".due.over{color:var(--signal)" in SOURCE

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

        assert "spread.swell_deg != null" in INFO
        assert "no spread is assumed" in INFO_TEXT


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

    def test_the_cycle_line_explains_itself_and_sits_with_the_forecast(self):
        """Forecast only, on info.html inside the Forecast block. On the
        observed side the provenance is on the swell card."""

        assert 'id="cycle"' not in SOURCE and 'id="breaks"' not in SOURCE
        forecast = INFO.index("What Forecast is standing on")
        assert INFO.index('id="cycle"') > forecast
        assert "Latest data from the" in INFO_TEXT
        assert "model run of" in INFO_TEXT and "offshore buoy" in INFO_TEXT

    def test_it_names_the_buoy_rather_than_only_its_number(self):
        assert "DATA.station_name" in INFO and "NDBC ${DATA.station}" in INFO
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
        known |= {"hs_m", "period_s", "from_deg", "wind_sea", "local"}  # train entries
        known |= {"peak_period_s", "peak_direction_deg", "frequency_bins"}  # buoy
        known |= {"age_hours", "observed_utc", "trains", "height_m", "kind"}

        for accessor in re.findall(r"\b(?:hour|entry|data|t|spread)\.([a-z_]{3,})\b", SOURCE):
            if accessor in {"map", "filter", "find", "join", "length", "split",
                            "toFixed", "textContent", "innerHTML"}:
                continue
            assert accessor in known, f"page reads unknown field {accessor!r}"


class TestTheCalculationLine:
    """Each break card states how its number was made from the buoy's, one
    effect at a time, in the provenance style under the drawing."""

    LINE = SOURCE[SOURCE.index("function calculationLine"):]
    LINE = LINE[:LINE.index("\n}\n")]

    def test_every_field_it_reads_is_one_the_forecast_writes(self):
        from forecast.nearshore import LocalSea, Nearshore, summarise

        near = Nearshore("x", 1.0, 0.9, 0.8, 200.0, 210.0, 12.0)
        out = summarise(near, LocalSea(0.1, 1.2, 290.0, 3.0),
                        buoy_hs_m=1.2, window_hs_m=0.8, depth_m=5.0)
        effects, local = out["effects"], out["effects"]["local"]
        found = re.findall(r"\be\.([a-z_]+)", self.LINE)
        assert found
        # `seabed_hs_m` is read only as the older payload's name for the
        # diffracted figure (a now.json can lag the page); it is the one
        # name allowed to be absent from what the forecast writes today.
        legacy = {"seabed_hs_m"}
        for key in found:
            if key != "local" and key not in legacy:
                assert key in effects, key
        for key in re.findall(r"\be\.local\.([a-z_]+)", self.LINE):
            assert key in local, key
        for key in re.findall(r"\bn\.([a-z_]+)", self.LINE):
            assert key in out, key

    def test_each_effect_is_stated_in_one_form(self):
        for effect in ("through the windows of",
                       "Refraction and diffraction at the windows' edges change the swell by",
                       "respectively", "Bottom friction over the shelf", "Shoaling into",
                       "Local wind chop at", "At this tide it breaks in"):
            assert effect in self.LINE
        assert self.LINE.count("pct(") >= 4

    def test_refraction_and_diffraction_are_separated_honestly(self):
        """The window treats every edge as a hard shadow, so refraction is
        measured with hard edges too, and diffraction is only what softening
        the edges — islands, Point Loma tip, Baja tangent — changes."""

        assert "change(refracted, e.window_hs_m)" in self.LINE
        assert "change(diffracted, refracted)" in self.LINE
        from forecast.nearshore import Nearshore, summarise

        near = Nearshore("x", 1.0, 0.9, 0.8, 200.0, 210.0, 12.0)
        effects = summarise(near, None, buoy_hs_m=1.2, window_hs_m=0.8, depth_m=5.0)["effects"]
        assert effects["refracted_hs_m"] == 0.8     # every edge hard
        assert effects["diffracted_hs_m"] == 0.9    # every edge diffracting

    def test_it_is_styled_as_the_leading_train_line(self):
        """Owner's call, 2026-09-25: the train line's size and grey, with the
        heights and percentages in its ink and weight."""

        assert '<div class="calc">${steps.join(" ")}</div>' in self.LINE
        assert ".calc{font-size:14px;color:var(--soft)" in SOURCE
        assert ".calc b{color:var(--ink);font-weight:600;white-space:nowrap}" in SOURCE
        assert "const ht = (m) => `<b>${height(m)}</b>`;" in self.LINE

    def test_the_headline_names_its_depth(self):
        label = SOURCE[SOURCE.index("function depthLabel"):]
        label = label[:label.index("\n}\n")]
        assert "ft (${Math.round(d)} m) depth" in label
        assert '"in window"' in label           # an older payload says what its number is

    def test_friction_and_breaking_are_stated_in_the_same_form(self):
        assert "Bottom friction over the shelf changes it by ${change(e.friction_hs_m, diffracted)}" in self.LINE
        assert "At this tide it breaks in ${depthText(b.depth_m)} of water at ${ht(b.hs_m)}" in self.LINE
        # A break already under way at the start depth is not claimed as found.
        assert "is an upper bound" in self.LINE

    def test_every_breaking_field_it_reads_is_one_the_surf_zone_writes(self):
        from forecast.surfzone import Breaking

        written = Breaking(1.0, 2.0, 50.0, 0.3, 0.55, 0.1, False).as_dict()
        for text in (self.LINE, SOURCE[SOURCE.index("function depthLabel"):]):
            for key in re.findall(r"\bb\.([a-z_]+)", text[:3000]):
                assert key in written, key

    def test_the_headline_names_where_it_breaks(self):
        label = SOURCE[SOURCE.index("function depthLabel"):]
        label = label[:label.index("\n}\n")]
        assert "breaking at ${depthText(b.depth_m)} depth" in label

    def test_the_trains_still_sum_to_the_breaking_headline(self):
        """Breaking scales every train by one factor, so the list under the
        number adds up to it in energy, as it did at 5 m."""

        import math

        from forecast.nearshore import LocalSea, Nearshore, summarise
        from forecast.surfzone import Profile
        from forecast.transform import Train

        near = Nearshore("x", 1.0, 0.9, 0.8, 200.0, 210.0, 12.0,
                         trains=[Train(0.9, 12.0, 205.0, 0.81),
                                 Train(math.sqrt(0.19), 7.0, 250.0, 0.19)])
        flat = Profile("p", [2.0 * i for i in range(300)], [5.0 - 0.06 * i for i in range(300)])
        out = summarise(near, LocalSea(0.2, 2.0, 280.0, 3.0), buoy_hs_m=1.2, window_hs_m=0.8,
                        depth_m=5.0, profile=flat, tide_m=0.2, normal_deg=200.0)
        assert out["breaking"] is not None
        assert out["hs_m"] == out["breaking"]["hs_m"]
        total = math.sqrt(sum(t["hs_m"] ** 2 for t in out["trains"]))
        assert total == pytest.approx(out["hs_m"], rel=0.01)

    def test_no_tide_no_breaking_height(self):
        from forecast.nearshore import Nearshore, summarise
        from forecast.surfzone import Profile

        near = Nearshore("x", 1.0, 0.9, 0.8, 200.0, 210.0, 12.0)
        flat = Profile("p", [0.0, 400.0], [5.0, -3.0])
        out = summarise(near, None, buoy_hs_m=1.2, window_hs_m=0.8, depth_m=5.0,
                        profile=flat, tide_m=None, normal_deg=200.0)
        assert out["breaking"] is None and out["hs_m"] == 1.0

    def test_it_does_not_call_the_physics_calibration(self):
        """Calibration is the level reserved for fitting to observations."""

        assert "calibrat" not in self.LINE.lower()

    def test_the_headline_prefers_the_nearshore_figure(self):
        assert "b.hs_nearshore_m != null ? b.hs_nearshore_m : b.hs_in_window_m" in SOURCE
        assert "h.hs_nearshore_m != null ? h.hs_nearshore_m : h.hs_window_m" in SOURCE

    def test_local_chop_is_listed_but_not_drawn_as_arriving_from_the_ocean(self):
        assert "local chop" in SOURCE
        assert "!t.local && isFinite(t.from_deg)" in SOURCE


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

    def test_the_break_card_lists_its_own_trains_under_the_window_figure(self):
        """Untitled since 2026-09-25, as the buoy tab's are. What says these
        are the trains reaching the break rather than the buoy's is that they
        are the break's own list, directly under its "in window" figure, on
        its own tab."""

        card = SOURCE[SOURCE.index("function breakPanel"):]
        card = card[:card.index("function buoyPanel")]
        assert "trainList(c.trains)" in card and "buoy.trains" not in card
        assert card.index("in window") < card.index("trainList(c.trains)")

    def test_the_swell_card_is_styled_like_wind_and_tide(self):
        """Same .cond card in the same strip, not a dashed aside."""

        swell = SOURCE.index('label: "Swell"')
        assert SOURCE.count('class="cond"') >= 2
        assert SOURCE.rindex('<div class="cond swell"', 0, swell) > 0

    def test_the_footer_does_not_describe_the_forecast_on_the_observed_tab(self):
        """Printing a model's build time and spread under a measurement would
        attribute the model's properties to the observation."""

        now = INFO[INFO.index("function renderNow"):]
        now = now[:now.index("\n}\n")]
        assert "nothing here is measured at the sand" in re.sub(r"\s+", " ", now)
        assert "DATA" not in now and "spread_assumption" not in now


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


class TestTheBreaksAreTabsOfTheSwellCard:
    """One Swell card: a tab per break, ranked by window energy, and the buoy
    always last. The ranking is the page's claim -- which break holds more of
    the swell -- stated before a number is read."""

    RANK_CASES = [
        # (window energies north, center, south) -> expected tab order
        ((0.683, 0.750, 0.822), ["coronado_south", "coronado_center", "coronado_north"]),
        ((0.90, 0.40, 0.60), ["coronado_north", "coronado_south", "coronado_center"]),
        # A tie falls back to north-to-south, never to file order.
        ((0.50, 0.50, 0.50), ["coronado_north", "coronado_center", "coronado_south"]),
        # A missing number is not ranked above a real one, even a zero.
        ((None, 0.0, 0.30), ["coronado_south", "coronado_center", "coronado_north"]),
    ]

    def test_breaks_are_ranked_by_window_energy(self):
        """Ran in node: the comparator's handling of ties and missing numbers
        is arithmetic, and a grep cannot tell a correct sort from a wrong one.
        The cards are fed in south-to-north order so a sort that fell back to
        input order on a tie would fail the tie case."""

        node = shutil.which("node")
        if node is None:
            pytest.skip("node is not available")

        order = SOURCE[SOURCE.index("const ORDER ="):]
        order = order[:order.index("\n") + 1]
        start = SOURCE.index("function rankByEnergy(cards) {")
        body = SOURCE[start:SOURCE.index("\n}\n", start) + 2]
        ids = ["coronado_north", "coronado_center", "coronado_south"]
        lines = []
        for energies, _ in self.RANK_CASES:
            cards = [{"id": i, "hsWindow": e} for i, e in zip(ids, energies)][::-1]
            lines.append(f"console.log(JSON.stringify(rankByEnergy({json.dumps(cards)})"
                         ".map((c) => c.id)));")
        out = subprocess.run([node, "-e", order + body + "\n" + "\n".join(lines)],
                             capture_output=True, text=True, check=True).stdout
        got = [json.loads(line) for line in out.splitlines() if line.strip()]
        assert got == [want for _, want in self.RANK_CASES]

    def test_the_buoy_tab_is_always_last(self):
        card = SOURCE[SOURCE.index("function swellCard"):]
        card = card[:card.index("\n}\n")]
        assert card.index("rankByEnergy(cards") < card.index("tabs.push({id: BUOY_TAB")

    def test_the_buoy_tab_is_titled_from_the_file_not_typed(self):
        assert "`Buoy ${station}`" in SOURCE
        assert "station: NOW && NOW.station" in SOURCE
        assert "station: DATA.station" in SOURCE
        assert "Buoy 46232" not in SOURCE

    def test_the_break_tabs_carry_the_break_names(self):
        assert 'SHORT = {coronado_north: "North", coronado_center: "Center", coronado_south: "South"}' in SOURCE
        assert "title: SHORT[c.id] || c.name" in SOURCE

    def test_the_provenance_and_countdown_show_whichever_tab_is_open(self):
        """Every tab is the one spectrum, through an aperture or not. Inside
        the buoy's tab an overdue reading would sit behind three tabs of
        window energy derived from it with no mark on any of them."""

        card = SOURCE[SOURCE.index("function swellCard"):]
        card = card[:card.index("\n}\n")]
        assert card.rindex('class="pane"') < card.index('<span class="src">${period(source)}${due}')
        panel = SOURCE[SOURCE.index("function buoyPanel"):]
        panel = panel[:panel.index("\n}\n")]
        assert 'class="src"' not in panel and "dueSpan" not in panel

    def test_it_is_a_real_tablist(self):
        assert 'class="subtabs" role="tablist"' in SOURCE
        assert 'role="tab" id="swell-tab-${tab.id}"' in SOURCE
        assert 'role="tabpanel" id="swell-pane-${tab.id}"' in SOURCE
        assert 'aria-controls="swell-pane-${tab.id}"' in SOURCE
        assert '"ArrowRight"' in SOURCE and '"ArrowLeft"' in SOURCE

    def test_the_readers_choice_survives_a_re_render(self):
        """The minute tick and the seek bar rebuild the card. A choice held by
        id survives that and a re-ranking; with no choice made, the card opens
        on the leader of the moment on screen."""

        assert "let SWELL_TAB = null" in SOURCE
        assert "tabs.some((tab) => tab.id === SWELL_TAB) ? SWELL_TAB : tabs[0].id" in SOURCE
        assert "SWELL_TAB = id" in SOURCE


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


class TestThePageRefetchesWhatItShows:
    """The page fetched both payloads once, at load, and never again.

    The minute tick re-rendered from memory, so a tab left open showed the age
    climbing and the countdown running against a payload that had stopped
    moving. With collection every ten minutes the repository was six times
    fresher than any open tab, and every improvement upstream stopped at the
    browser.
    """

    def test_both_payloads_are_refetched_on_a_timer(self):
        assert "setInterval(refreshNow, NOW_REFRESH_MS)" in SOURCE
        assert "setInterval(refreshForecast, FORECAST_REFRESH_MS)" in SOURCE

    def test_the_observed_chain_is_refetched_at_least_as_often_as_it_is_collected(self):
        """If the page refreshed more slowly than the collector publishes, the
        page would be the bottleneck rather than the trigger — the same class
        of mismatch as a countdown promising a cadence nobody keeps."""

        from forecast.now import COLLECT_INTERVAL_MIN

        found = re.search(r"const NOW_REFRESH_MS = (\d+) \* 60 \* 1000", SOURCE)
        assert found, "NOW_REFRESH_MS is not in the minutes form this test reads"
        assert int(found.group(1)) <= COLLECT_INTERVAL_MIN, (
            f"page refreshes every {found.group(1)} min, collector runs every "
            f"{COLLECT_INTERVAL_MIN}"
        )

    def test_the_forecast_is_refetched_far_less_often_than_the_observation(self):
        """now.json is ~6 KB and changes every collection; forecast.json is
        ~128 KB and changes four times a day. Refetching them together would be
        twenty times the bytes for nothing, on a phone at the beach."""

        now_min = int(re.search(r"const NOW_REFRESH_MS = (\d+) \* 60 \* 1000", SOURCE).group(1))
        fc = re.search(r"const FORECAST_REFRESH_MS = (\d+) \* 60 \* 1000", SOURCE)
        assert fc, "FORECAST_REFRESH_MS is not in the minutes form this test reads"
        assert int(fc.group(1)) >= now_min * 4, (
            f"forecast refreshes every {fc.group(1)} min against the observation's "
            f"{now_min} — not enough separation to be worth two timers"
        )

    def test_a_failed_refresh_keeps_what_is_on_screen(self):
        """A lost request is the normal case on a phone at the beach, not the
        exception. Blanking the page for one would be worse than showing a
        reading whose own age line already says how old it is."""

        for fn in ("function refreshNow()", "function refreshForecast()"):
            start = SOURCE.index(fn)
            body = SOURCE[start:SOURCE.index("\n}\n", start)]
            assert ".catch(() => {})" in body, f"{fn} does not swallow a failed fetch"
            assert "r.ok ? r.json() : null" in body, f"{fn} treats a non-200 as data"

    def test_an_unchanged_payload_does_not_re_render(self):
        assert "observed.generated_utc === NOW.generated_utc" in SOURCE
        assert "data.generated_utc === DATA.generated_utc" in SOURCE

    def test_a_new_cycle_keeps_the_hour_the_reader_chose(self):
        """A refresh that yanked someone from +48 h back to now would be a
        worse bug than the staleness it fixes. `adoptForecast` takes the
        valid_utc on screen and puts them back on it when the new cycle still
        carries that hour."""

        assert "adoptForecast(data, currentHour())" in SOURCE
        assert "function currentHour()" in SOURCE
        assert "STEPS.findIndex((i) => first[i].valid_utc === keep)" in SOURCE

    def test_boot_and_the_refresh_build_the_forecast_state_the_same_way(self):
        """A new cycle changes which hours exist, so the picker has to be
        rebuilt against them. Two code paths doing that separately is how one
        of them ends up offering indices into an array that no longer has that
        shape."""

        assert SOURCE.count("function adoptForecast(") == 1
        assert "if (!adoptForecast(data, null)) return;" in SOURCE


class TestAnUpdateAnnouncesItself:
    """A refresh that silently swapped the numbers would make the whole point
    of collecting every ten minutes invisible."""

    def test_every_card_carries_a_stable_key(self):
        """Keyed rather than positional: the swell tabs re-rank by energy, so a
        card can move in the strip without its contents changing."""

        assert SOURCE.count('data-card="') == 5   # swell, then wind/tide on both tabs
        assert 'data-card="swell"' in SOURCE

    def test_the_flash_compares_either_side_of_the_same_render(self):
        """The snapshot and the comparison must straddle one re-render. Across
        any longer gap every card differs, because the age and the countdown
        are always moving."""

        start = SOURCE.index("function showAndFlash()")
        body = SOURCE[start:SOURCE.index("\n}\n", start)]
        assert body.index("cardText()") < body.index("show()") < body.index("flashChanged")

    def test_clock_derived_text_is_excluded_from_the_comparison(self):
        """Measured: without this the wind card flashed alongside the tide on a
        refresh that only moved the tide. `show()` re-runs `tickDue`, so a
        snapshot and a render either side of a second boundary disagree on the
        countdown — and at a minute boundary, on the age.

        Both are marked in the DOM rather than stripped by pattern, so the rule
        survives the wording changing."""

        assert 'const VOLATILE = "[data-due], .age"' in SOURCE
        assert 'copy.querySelectorAll(VOLATILE).forEach((v) => v.remove())' in SOURCE
        assert '<span class="age">${age}</span>' in SOURCE

    def test_navigation_does_not_flash(self):
        """Stepping the forecast to +48 h re-renders without a refresh. Only
        the two refresh paths go through `showAndFlash`."""

        assert SOURCE.count("showAndFlash()") == 3          # the definition, and two callers
        for nav in ('$("earlier").onclick', '$("later").onclick', '$("when").onchange'):
            start = SOURCE.index(nav)
            assert "showAndFlash" not in SOURCE[start:start + 200], f"{nav} flashes"

    def test_the_flash_settles_back_rather_than_ending_on_a_literal(self):
        """Animating to a fixed colour would be wrong in one of the two themes.
        Each keyframe sets only `from`, so the card returns to whatever it
        rests at."""

        assert "@keyframes freshen" in SOURCE
        assert "from { border-color: var(--surf); background: var(--surf-wash); }" in SOURCE
        assert "from { color: var(--surf); }" in SOURCE
        assert ".cond.fresh .val, .cond.fresh .src" in SOURCE

    def test_an_update_is_worth_noticing_not_enduring(self):
        assert "prefers-reduced-motion: reduce" in SOURCE
        start = SOURCE.index("prefers-reduced-motion: reduce")
        assert "animation: none" in SOURCE[start:start + 200]


class TestTheUpdateCountdown:
    """"Next update expected in h:mm:ss" is a claim about ARRIVAL, and a claim
    that can be wrong needs to be able to say so on screen."""

    def test_the_countdown_targets_when_it_will_be_DISPLAYED(self):
        """`next_expected` is when a newer reading should be in now.json. The
        reader sees nothing until the page refetches, so the last leg is added
        on the page, where it is known. Without it the countdown reached zero
        while the file was already fresh and the screen had not caught up —
        the page reporting its own latency as the source being late."""

        assert "new Date(ms + NOW_REFRESH_MS).toISOString()" in SOURCE
        # Applied to BOTH instants: a late bound that skipped the refresh leg
        # would redden the card for the page's own latency.
        assert "plusRefresh(at)" in SOURCE
        assert "plusRefresh(Number.isFinite(lateAt)" in SOURCE

    def test_the_refresh_interval_is_declared_before_the_countdown_uses_it(self):
        """`dueSpan` reads NOW_REFRESH_MS. A `const` used above its own line is
        a ReferenceError waiting for the first caller that moves."""

        assert SOURCE.index("const NOW_REFRESH_MS") < SOURCE.index("function dueSpan")

    def test_the_deadline_is_published_absolute_and_counted_down_here(self):
        """BRIEFING §18: a now-relative number frozen into a static file is
        wrong for most of the hour it spends on screen. now.json publishes the
        INSTANT each card is waiting on; the page does the arithmetic against
        the reader's own clock, exactly as it already does for "2 h ago"."""

        from forecast.now import Now

        assert "next_expected" in Now.__dataclass_fields__
        assert "NOW.next_expected" in SOURCE
        # Derived in the browser, not read out of the file.
        assert "Date.now()" in SOURCE

    def test_an_elapsed_deadline_goes_overdue_rather_than_rolling_on(self):
        """A countdown that silently restarted at the next slot would have
        looked healthy through all 16.2 days 46232 was dark. Same fault as the
        staleness alert that never visibly fired and the archive job that read
        a 404 as "no cycle this hour" for three days: monitoring that only
        shows the failure it expects."""

        assert "Overdue by ${hms(now - late)}" in SOURCE
        assert "Update in ${hms(due - now)}" in SOURCE
        assert 'el.classList.toggle("over", now >= late || forced)' in SOURCE

    def test_a_due_update_is_not_yet_an_accusation(self):
        """Red is reserved for `overdue_after`, not `next_expected`.

        A publication delay is a distribution, so the instant an update becomes
        expected is not the instant its absence is a fault. The swell is the
        case that forced the split: its spectra usually land by H+15 but one
        measured hour took H+35, so a single deadline either reddened that hour
        or quoted H+27 to every other one -- and it quoted H+27, which is how an
        hourly source came to promise 100 minutes from stamp to screen.

        Between the two the card says the update is due, in the resting colour.
        A card that is red whenever a source runs at the slow end of its own
        measured range is the card nobody reads on the day collection dies."""

        assert 'now >= due ? "Update due."' in SOURCE
        # And the red class keys off `late`, never `due`.
        assert 'toggle("over", now >= due' not in SOURCE

    def test_both_instants_are_published_and_read(self):
        """`overdue_after` is computed in now.py beside `next_expected`, from the
        same reading, so the two cannot drift apart per card."""

        from forecast.now import Now

        assert "overdue_after" in Now.__dataclass_fields__
        assert "NOW.overdue_after" in SOURCE
        for source in ("swell", "wind", "tide"):
            assert f"late.{source}" in SOURCE

    def test_a_payload_without_the_late_bound_still_reddens(self):
        """`overdue_after` is newer than the pages already published. A bundle
        that predates it must behave as it did before the split -- the old
        single deadline doing both jobs -- rather than never turning red, which
        is the failure mode this project has now met three times."""

        assert "Math.max(lateAt, at) : at" in SOURCE
        assert "Math.max(parsedLate, due) : due" in SOURCE

    def test_a_forced_overdue_with_no_elapsed_deadline_shows_no_figure(self):
        """`forceOver` says the build refused the reading for a reason that is
        not its age. "Overdue by -0:04:11" would be worse than saying nothing,
        so only a genuinely elapsed deadline gets a number."""

        assert 'forced ? "Overdue."' in SOURCE

    def test_each_card_counts_down_its_own_source(self):
        """The point of three countdowns rather than one banner: when a single
        source stops, its card is the only one that runs overdue. A banner over
        all three could not say which."""

        assert "due.swell" in SOURCE
        assert "due.wind" in SOURCE
        assert "due.tide" in SOURCE

    def test_the_second_tick_does_not_redraw_the_whole_page(self):
        """The minute tick re-renders and is right for "2 h ago". A clock that
        moves every second rewriting every card sixty times a minute is not."""

        assert "setInterval(tickDue, 1000)" in SOURCE
        assert "document.querySelectorAll(\"[data-due]\")" in SOURCE

    HMS_CASES = [
        (0, "0:00"),
        (1_000, "0:01"),
        (42_000, "0:42"),
        (59_000, "0:59"),
        (60_000, "1:00"),
        (3_542_000, "59:02"),
        (3_599_000, "59:59"),
        (3_600_000, "1:00:00"),         # the hour appears only once there is one
        (45_296_000, "12:34:56"),
        (86_399_000, "23:59:59"),       # last second before a day exists
        (86_400_000, "1d 0:00:00"),
        (360_000_000, "4d 4:00:00"),
        (1_400_000_000, "16d 4:53:20"),  # 46232's outage, as a reader meets it
        (-5_000, "0:05"),               # sign is carried by the wording, not here
    ]

    def test_the_clock_drops_units_it_does_not_need(self):
        """Ran in node: "0:1:5" versus "0:01:05" is a property of the
        arithmetic and a grep cannot tell them apart.

        Leading units are dropped while they are zero, so a card read at a
        glance does not spend three characters saying "0:".

        Hours previously ran on without wrapping, so an outage would read as
        one number. That produced "389:00:00" for 46232's sixteen dark days,
        which is one number and not a legible one; past 24 h it now reads
        "16d 4:53:20"."""

        node = shutil.which("node")
        if node is None:
            pytest.skip("node is not available")

        start = SOURCE.index("const pad2 =")
        body = SOURCE[start:SOURCE.index("\n}\n", SOURCE.index("function hms(ms) {")) + 2]
        script = body + "\n" + "\n".join(
            f"console.log(JSON.stringify(hms({ms!r})));" for ms, _ in self.HMS_CASES
        )
        out = subprocess.run([node, "-e", script], capture_output=True, text=True,
                             check=True).stdout.split("\n")
        got = [json.loads(line) for line in out if line.strip()]
        assert got == [want for _, want in self.HMS_CASES]

    def test_a_card_with_no_reading_gets_no_countdown(self):
        """Counting down to the next wind observation under "not collected"
        would promise a replacement for something that was never there."""

        assert 'wind.from_deg != null ? dueSpan(due.wind, late.wind) : ""' in SOURCE
        assert 'tide.height_m != null ? dueSpan(due.tide, late.tide) : ""' in SOURCE


class TestTheCdnCannotServeAStalePayload:
    """GitHub Pages serves everything through Fastly with `Cache-Control:
    max-age=600` and offers no way to change it. Ten minutes of permitted
    staleness against a ten-minute collection cadence means a cache HIT can hand
    a reader a payload one whole collection behind -- whose own age line would
    then be honest about a reading that had already been superseded.

    Measured on the live bundle 2026-09-25T15:48:58Z: `max-age=600`, `Age: 0`,
    `x-cache: MISS`, `Last-Modified 15:45:44`. That response came from origin and
    was not stale, so `cache: "no-store"` was honoured there -- but honouring a
    client `no-cache` is Fastly configuration rather than a guarantee, and it
    says nothing about what another edge node holds for the next reader."""

    def test_every_payload_fetch_carries_a_unique_url(self):
        """A bare `fetch(SOURCE)` is one a shared cache is free to answer."""

        assert 'fetch(SOURCE,' not in SOURCE
        assert 'fetch(NOW_SOURCE,' not in SOURCE
        assert SOURCE.count("fetch(fresh(SOURCE)") == 2       # boot + refresh
        assert SOURCE.count("fetch(fresh(NOW_SOURCE)") == 2

    def test_no_store_is_kept_as_well(self):
        """Different caches. The query parameter defeats shared ones; `no-store`
        defeats this browser's own. Dropping either leaves a gap."""

        assert SOURCE.count('{cache: "no-store"}') == 4

    def test_fresh_appends_without_breaking_an_existing_query(self):
        """`SOURCE` is overridable via `?data=`, so the URL may already carry a
        query string. Ran in node: whether the separator is `?` or `&` is
        arithmetic on the input, and a grep cannot tell a correct one from a
        broken one."""

        node = shutil.which("node")
        if node is None:
            pytest.skip("node is not available")

        start = SOURCE.index("function fresh(url) {")
        body = SOURCE[start:SOURCE.index("\n}\n", start) + 2]
        script = body + """
const plain = fresh("now.json");
const queried = fresh("d.json?data=x");
console.log(JSON.stringify({
  plain, queried,
  plainOnce: (plain.match(/\\?/g) || []).length,
  queriedKeeps: queried.includes("data=x"),
  queriedJoins: queried.includes("?data=x&v="),
  unique: fresh("a") !== fresh("a") || Date.now() === Date.now(),
}));
"""
        got = json.loads(subprocess.run([node, "-e", script], capture_output=True,
                                        text=True, check=True).stdout)
        assert got["plainOnce"] == 1, got["plain"]
        assert got["plain"].startswith("now.json?v=")
        assert got["queriedKeeps"], got["queried"]
        assert got["queriedJoins"], got["queried"]


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


class TestTheWindowBlockSurvivesAnOlderPayload:
    """`index.html` and `forecast.json` ship in one commit and cannot drift.
    `now.json` is optional, and the publish script keeps the previous one when
    a build fails — so the page can meet an older payload shape."""

    def test_bearings_are_checked_before_they_are_drawn(self):
        assert "isFinite(w.from)" in SOURCE and "isFinite(w.to)" in SOURCE

    def test_an_unreadable_payload_is_not_reported_as_a_fact_about_the_coast(self):
        """"No open window" is a claim about the beach. A payload this page
        cannot read is a claim about the payload. Printing the first for both
        puts a false statement about the geometry on screen every time a file
        goes stale -- which is exactly when nobody is watching."""

        block = SOURCE[SOURCE.index("function windowList"):]
        block = block[:block.index("function compass")]
        assert "no open window" in block
        assert "older than the page" in block
        assert block.index("given.length") < block.index("no open window")
