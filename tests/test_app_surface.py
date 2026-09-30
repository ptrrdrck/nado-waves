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
        """Owner's layout, 2026-09-25, and the calculation's fold-out,
        2026-09-26: the nearshore height labelled with its depth, with the
        table of how it was calculated folding out beneath it; the trains;
        the drawing."""

        panel = SOURCE[SOURCE.index("function breakPanel"):]
        panel = panel[:panel.index("function depthLabel")]
        order = ("depthLabel(c)", "calculationTable(c)", 'id="calc-${c.id}"',
                 "trainList(c.trains)", "drawing || windowList(c.swellWindow)")
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


# The page's own clock formatter, for node-run tests of anything that labels an
# hour. A const arrow, so it is lifted by its statement rather than by
# `function name(`.
CLOCK = SOURCE[SOURCE.index("const clock = "):]
CLOCK = CLOCK[:CLOCK.index("});") + 3] + "\n"


class TestTheSeekBar:
    def _run(self, script):
        node = shutil.which("node")
        if node is None:
            pytest.skip("node is not available")
        fns = ""
        for name in ("currentHour", "adoptForecast", "firstUpcoming", "advancePastDefault",
                     "measuredAt", "measuredLine", "pastNearshore", "depthLabel", "depthText",
                     "compass"):
            start = SOURCE.index(f"function {name}(")
            fns += SOURCE[start:SOURCE.index("\n}\n", start) + 2]
        prelude = (
            "let DATA = null, TIDE_BY_TIME = {}, STEPS = [], CURSOR = 0, CHOSEN = null;\n"
            "let MEASURED = null; const FT_PER_M = 3.28084;\n"
            + CLOCK +
            "const height = (m) => m.toFixed(2) + ' m';\n"

            "const el = {textContent: '', innerHTML: '', hidden: true};\n"
            "const $ = () => el; const when = (v) => v;\n"
            # Friday 2026-09-25 22:00 PDT onward, 3-hourly; "now" is Saturday
            # 00:20 PDT, 07:20Z. Nearest-now would pick 06:00Z (Fri 11 p.m.).
            "const hours = [];\n"
            "for (let h = 0; h <= 12; h++) hours.push({lead_h: h,"
            " valid_utc: new Date(Date.UTC(2026, 8, 26, 3 + h)).toISOString()"
            ".replace('.000Z', 'Z')});\n"
            "const data = {breaks: [{hours}]};\n"
            "let CLOCK = Date.UTC(2026, 8, 26, 7, 20); Date.now = () => CLOCK;\n"
        )
        out = subprocess.run([node, "-e", prelude + fns + script],
                             capture_output=True, text=True, check=True).stdout
        return [line for line in out.splitlines() if line.strip()]

    def test_it_opens_on_the_first_hour_not_yet_passed(self):
        """Friday 11 p.m. is nearer 0:20 Saturday than 2 a.m. is, and it has
        already happened. The page must open on 2 a.m. — never on the past,
        and never on hour zero of a cycle published five hours late."""

        assert self._run("adoptForecast(data, null); console.log(currentHour());") \
            == ["2026-09-26T09:00:00Z"]

    def test_an_hour_on_the_dot_is_not_past(self):
        assert self._run("CLOCK = Date.UTC(2026, 8, 26, 9); adoptForecast(data, null);"
                         " console.log(currentHour());") == ["2026-09-26T09:00:00Z"]

    def test_a_default_hour_that_passes_moves_on_but_a_chosen_one_stays(self):
        """The page sits open for hours; the hour it opened on goes by. Left
        where it was, that is opening on the past one step removed. An hour
        the reader stepped to is theirs and is not moved."""

        assert self._run(
            "adoptForecast(data, null); CLOCK = Date.UTC(2026, 8, 26, 9, 30);"
            " console.log(advancePastDefault(), currentHour());"
            " CURSOR = 0; CHOSEN = currentHour();"
            " console.log(advancePastDefault(), currentHour());"
        ) == ["true 2026-09-26T12:00:00Z", "false 2026-09-26T03:00:00Z"]

    def test_a_new_cycle_does_not_keep_a_default_hour_that_has_passed(self):
        assert self._run(
            "adoptForecast(data, null); const was = currentHour();"
            " CLOCK = Date.UTC(2026, 8, 26, 10); adoptForecast(data, was);"
            " console.log(currentHour());"
        ) == ["2026-09-26T12:00:00Z"]

    def test_a_new_cycle_keeps_an_hour_the_reader_chose(self):
        assert self._run(
            "adoptForecast(data, null); CURSOR = 4; CHOSEN = currentHour();"
            " adoptForecast(data, currentHour()); console.log(currentHour());"
        ) == ["2026-09-26T15:00:00Z"]

    def test_a_spent_file_opens_on_its_last_hour_and_says_so(self):
        assert self._run("CLOCK = Date.UTC(2026, 9, 1); adoptForecast(data, null);"
                         " console.log(currentHour());") == ["2026-09-26T15:00:00Z"]
        assert "Every hour in this forecast has passed." in SOURCE

    # An earlier run's log (`past`) and this run, published at 06:30Z. The log
    # covers 00, 03 and 06Z; the run's own 03 and 06Z were already gone when
    # it appeared, so the log's entries are what a reader had for those hours.
    WITH_PAST = (
        "data.generated_utc = '2026-09-26T06:30:00Z';\n"
        "data.past = ['00', '03', '06'].map((h) => ({valid_utc: `2026-09-26T${h}:00:00Z`,"
        " lead_h: 12, cycle_utc: '2026-09-25T18:00:00Z', breaks: {}}));\n"
    )

    def test_the_log_supplies_the_hours_before_this_run(self):
        assert self._run(
            self.WITH_PAST + "adoptForecast(data, null);"
            " console.log(STEPS.map((s) => s.valid_utc.slice(11, 13) + s.from[0]).join(' '));"
            " console.log(currentHour());"
        ) == ["00p 03p 06p 09c 12c 15c", "2026-09-26T09:00:00Z"]

    def test_without_a_log_the_runs_own_early_hours_stay(self):
        assert self._run(
            "data.generated_utc = '2026-09-26T06:30:00Z'; adoptForecast(data, null);"
            " console.log(STEPS.map((s) => s.valid_utc.slice(11, 13) + s.from[0]).join(' '));"
        ) == ["03c 06c 09c 12c 15c"]

    def test_the_measured_line_only_under_an_hour_that_has_gone_by(self):
        """Value, gap, not-in-yet, nothing loaded, and nothing at all for an
        hour still ahead. A gap is never filled from the hour beside it."""

        got = self._run(
            "MEASURED = {generated_utc: '2026-09-26T07:10:00Z', station: '46232', steps: ["
            " {valid_utc: '2026-09-26T03:00:00Z', gap: false, buoy: {hs_m: 1.1}},"
            " {valid_utc: '2026-09-26T06:00:00Z', gap: true}]};\n"
            "for (const h of ['03', '06', '00', '09']) console.log(h,"
            " measuredAt(`2026-09-26T${h}:00:00Z`).state);\n"
            "CLOCK = Date.UTC(2026, 8, 26, 9, 20);"
            " console.log('09', measuredAt('2026-09-26T09:00:00Z').state);"
        )
        assert got == ["03 value", "06 gap", "00 none", "09 future", "09 pending"]

    def test_the_measured_line_names_the_hour_it_was_observed(self):
        """Owner's wording, 2026-09-27: "Observed at 8:00 AM". The hour comes
        from measuredAt, in every state, so "not in yet" names it too."""

        got = self._run(
            "MEASURED = {station: '46232', steps: [{valid_utc: '2026-09-26T03:00:00Z',"
            " gap: false, breaks: {n: {hs_m: 0.8, hs_basis: 'breaking', depth_m: 1.9,"
            " period_s: 14.3, from_deg: 205}}}]};\n"
            "const m = measuredAt('2026-09-26T03:00:00Z');\n"
            "console.log(measuredLine(m, (e) => e.breaks.n).replace(/\\s+/g, ' '));"
            "console.log(measuredLine({state: 'future'}, (e) => e) === '');"
            "console.log(measuredLine(measuredAt('2026-09-26T06:00:00Z'), (e) => e));"
            "console.log(clock('2026-09-26T03:00:00Z'));"
        )
        hour = got[3]
        assert f"Observed at {hour}" in got[0]
        assert "0.80 m" in got[0] and "breaking at 6 ft (1.9 m) depth" in got[0]
        assert got[1] == "true"
        assert f"Observed at {hour}" not in got[2] and "Observed at" in got[2]
        assert "same chain" not in got[0]

    def test_wind_is_observed_and_tide_is_measured_at_the_hour(self):
        assert '<span class="lbl">Observed at ${clock(step.valid_utc)}</span>' in SOURCE
        assert '<span class="lbl">Measured at ${clock(step.valid_utc)}</span>' in SOURCE
        assert "carried to the coast</span>" not in SOURCE

    def test_the_page_never_calls_the_measurement_what_happened(self):
        """Both numbers pass through the same physics, so their difference is
        the model's error at the buoy, not a check at the beach."""

        lowered = SOURCE.lower()
        assert "actual" not in lowered and "what happened" not in lowered

    def test_earlier_and_later_move_the_cursor(self):
        assert '$("earlier").onclick' in SOURCE and '$("later").onclick' in SOURCE
        assert "choose(CURSOR - 1)" in SOURCE and "choose(CURSOR + 1)" in SOURCE

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
        # The correction sits under the hour it applies to, the place under it.
        assert ("`Harmonic tide for ${stampWhen}`, departureLine(tide), tideSource(DATA)"
                in SOURCE)

    def test_the_forecast_tide_says_when_it_carries_the_measured_departure(self):
        """The card's height is the prediction plus the gauge's measured
        departure, the level the breaking used. An hour without one gets no
        line, so the card never claims an offset its number does not carry."""

        line = SOURCE[SOURCE.index("function departureLine"):]
        line = line[:line.index("\n}\n")]
        assert 'if (d == null) return "";' in line
        assert "`Gauge departure correction (last 3 days): ${d < 0 ?" in line

    def test_the_provenance_separates_a_forecast_hour_from_an_observation(self):
        """The model's wind moves with the picker; the KNZY fallback is an
        observation. Both appear, because which is shown depends on what the
        file carries — and since the titles are bare quantities now, the
        provenance line is the only thing telling them apart."""

        assert "GFS-Wave wind at the buoy, ${DATA.station_name} (NDBC ${DATA.station})" in SOURCE
        assert "METAR, ${fallback.station_name} (${fallback.station})" in SOURCE
        assert "METAR, ${wind.station_name} (${wind.station})" in SOURCE
        assert "`Harmonic tide for ${stampWhen}`" in SOURCE

    def test_model_wind_is_named_as_a_forecast(self):
        wind = SOURCE[SOURCE.index("GFS-Wave wind at the buoy, ${DATA") - 200:]
        assert "`Forecast for ${stampWhen}`" in wind[:200]

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
        assert "What NOW(ISH) is standing on" in INFO
        assert "What Forecast is standing on" in INFO

    def test_now_labels_its_inputs_as_measurements(self):
        """The card titles are bare quantities, so the word that says these
        are measurements has to be in the provenance line, where the reader
        looks for where a number came from."""

        assert "Observed ${observedAt(wind.observed_utc)}" in SOURCE
        assert "Measured ${observedAt(tide.observed_utc)}" in SOURCE

    def test_forecast_labels_its_inputs_as_a_model(self):
        """The verb that opens each line says which chain it is: "Forecast"
        and "Harmonic tide" here, where Now says "Observed" and "Measured"."""

        # swell, the model's wind at the buoy, and the Local wind forecast
        assert SOURCE.count("`Forecast for ${stampWhen}`") == 3
        assert "`Harmonic tide for ${stampWhen}`" in SOURCE

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

        assert "Observed ${observedAt(NOW.observed_utc)}" in SOURCE
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
        known |= {"detail"}  # `past` entries: forecastlog.past_hours

        for accessor in re.findall(r"\b(?:hour|entry|data|t|spread)\.([a-z_]{3,})\b", SOURCE):
            if accessor in {"map", "filter", "find", "join", "length", "split",
                            "toFixed", "textContent", "innerHTML"}:
                continue
            assert accessor in known, f"page reads unknown field {accessor!r}"


class TestTheCalculationTable:
    """Each break card states how its number was made from the buoy's, one
    effect per row, in a table folding out under the headline."""

    LINE = SOURCE[SOURCE.index("function calculationTable"):]
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

    def test_its_columns_are_the_owners(self):
        heads = re.findall(r'<th scope="col">([^<]+)</th>', self.LINE)
        assert heads == ["Calc", "Change", "%", "Hs"]

    def test_each_effect_has_its_row_in_order(self):
        rows = re.findall(r'row\("([^"]+)"', self.LINE)
        assert rows == ["Buoy", "Windows", "Refraction", "Diffraction",
                        "Bottom friction", "Shoaling", "Local chop", "Wave break"]

    def test_each_change_is_against_the_step_before(self):
        for call in ('row("Windows", e.window_hs_m, e.buoy_hs_m)',
                     'row("Diffraction", diffracted, refracted)',
                     'row("Bottom friction", e.friction_hs_m, diffracted)',
                     'row("Shoaling", e.shoaled_hs_m, before',
                     'row("Local chop", withChop, e.shoaled_hs_m',
                     'row("Wave break", b.hs_m, withChop'):
            assert call in self.LINE, call
        # The percentage is the change as a share of the step before it.
        assert "pct(to, from)" in self.LINE and "change(to, from)" in self.LINE
        fn = SOURCE[SOURCE.index("function pct("):]
        assert "100 * (to / from - 1)" in fn[:fn.index("\n}\n")]

    def test_refraction_and_diffraction_are_separated_honestly(self):
        """The window treats every edge as a hard shadow, so refraction is
        measured with hard edges too, and diffraction is only what softening
        the edges — islands, Point Loma tip, Baja tangent — changes."""

        assert 'row("Refraction", refracted, e.window_hs_m)' in self.LINE
        assert 'row("Diffraction", diffracted, refracted)' in self.LINE
        from forecast.nearshore import Nearshore, summarise

        near = Nearshore("x", 1.0, 0.9, 0.8, 200.0, 210.0, 12.0)
        effects = summarise(near, None, buoy_hs_m=1.2, window_hs_m=0.8, depth_m=5.0)["effects"]
        assert effects["refracted_hs_m"] == 0.8     # every edge hard
        assert effects["diffracted_hs_m"] == 0.9    # every edge diffracting

    def test_friction_and_chop_rows_appear_only_when_modelled(self):
        assert "if (e.friction_hs_m != null) {" in self.LINE
        assert "if (e.local && withChop != null) {" in self.LINE

    def test_heights_use_the_one_conversion(self):
        assert "FT_PER_M" not in self.LINE and "3.28" not in self.LINE
        assert "height(to)" in self.LINE and "height(Math.abs(d))" in self.LINE

    def test_the_headline_names_its_depth(self):
        label = SOURCE[SOURCE.index("function depthLabel"):]
        label = label[:label.index("\n}\n")]
        assert "ft (${Math.round(d)} m) depth" in label
        assert '"in window"' in label           # an older payload says what its number is

    def test_a_break_under_way_at_the_start_depth_is_a_bound(self):
        """Not claimed as a break point found: its height is marked as an
        upper bound in the table and said so beneath it."""

        assert "bound: !!b.outside_start" in self.LINE
        assert '${bound ? "\\u2264 " : ""}' in self.LINE
        assert "is an upper bound" in self.LINE

    def test_the_caret_folds_the_table_under_the_headline(self):
        """Owner's design, 2026-09-26: a caret at the right end of the
        headline, up while closed and down while open, one state for every
        break, kept across a refresh like the tab choices."""

        toggle = SOURCE[SOURCE.index("function calcToggle"):]
        toggle = toggle[:toggle.index("\n}\n")]
        assert 'aria-controls="calc-${id}"' in toggle
        assert 'aria-expanded="${CALC_OPEN}"' in toggle
        assert "<path d=\"M3.5 10 8 5.5 12.5 10\"/>" in toggle     # drawn pointing up
        assert '.calc-toggle[aria-expanded="true"] svg{transform:rotate(180deg)}' in SOURCE
        assert 'calc: "nado-waves.calc"' in SOURCE
        assert 'CALC_OPEN = recall(KEEP.calc) === "open";' in SOURCE
        assert 'if (e.target.closest("[data-calc-toggle]")) setCalcOpen(!CALC_OPEN);' in SOURCE
        panel = SOURCE[SOURCE.index("function breakPanel"):]
        panel = panel[:panel.index("function depthText")]
        # An earlier run's hour keeps only its headline: no caret, no table.
        past = panel[panel.index("if (c.past) {"):panel.index("const drawing")]
        assert "calcToggle" not in past and "calculationTable" not in past
        # Nothing to tabulate: no caret, and the buoy's figure stays a footnote.
        assert "const offshore = !table && c.hsOffshore != null" in panel

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
        assert "Spectral wave data, ${NOW.station_name} (NDBC ${NOW.station})" in SOURCE

    def test_the_forecast_card_names_its_model(self):
        assert '"partitions" : "spectrum"}, ${DATA.station_name} (NDBC ${DATA.station})' in SOURCE
        assert "? `GFS-Wave ${" in SOURCE

    def test_every_forecast_hour_names_its_run_past_or_future(self):
        """One run line on every hour (owner's decision, 2026-09-27): "from the
        ... model run" is itself what tells a past hour from the current run,
        so past and future swell cards carry the same three lines and nothing
        is appended to a past one."""

        assert "return `From the ${when(run)} model run${lead}`;" in SOURCE
        assert "const lead = step.lead_h != null ? `, ${step.lead_h} h ahead` : \"\";" in SOURCE
        assert "what this page showed for that hour" not in SOURCE
        assert "fromLine" not in SOURCE
        # Swell and model wind both end on it.
        assert SOURCE.count("        run,\n") + SOURCE.count("                    run])") == 2

    def test_the_forecast_card_reads_the_per_hour_buoy_series(self):
        assert "(DATA.buoy || []).find" in SOURCE
        assert "b.valid_utc === step.valid_utc" in SOURCE

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
        assert card.rindex('class="pane"') < card.index("${srcLines(source, due)}")
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
        `period` is applied at the card, not trusted to the note. The one
        exception is the countdown's own line, whose text `tickDue` writes
        with its full stop already on it."""

        assert "const period = (s) =>" in SOURCE
        assert "Update in ${hms(due - now)}.`" in SOURCE
        bare = [m for m in re.findall(r'<span class="src">\$\{(.{0,40})', SOURCE)
                if not m.startswith(("period(", "period (", "due}"))]
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
        assert "STEPS.findIndex((step) => step.valid_utc === keep)" in SOURCE

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

        # swell, then wind/tide on both tabs, and wind/tide again for an
        # earlier run's hour, which carries only the measurement
        assert SOURCE.count('data-card="') == 7
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

        assert SOURCE.count("showAndFlash()") == 4          # the definition, and three callers
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

        assert "dueSpan(due.wind, late.wind))\n        : srcLines(wind.note)}" in SOURCE
        assert "dueSpan(due.tide, late.tide))\n        : srcLines(tide.note)}" in SOURCE


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
        assert SOURCE.count("fetch(fresh(MEASURED_SOURCE)") == 2
        assert SOURCE.count("fetch(fresh(SERIES_SOURCE)") == 2
        assert SOURCE.count("fetch(fresh(SERIES_ALL_SOURCE)") == 2   # asked for + hourly

    def test_no_store_is_kept_as_well(self):
        """Different caches. The query parameter defeats shared ones; `no-store`
        defeats this browser's own. Dropping either leaves a gap."""

        assert SOURCE.count('{cache: "no-store"}') == 10

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

        assert "turnLine(DATA.tide_turns || [], step.valid_utc)" in SOURCE

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
        for site in ("Observed ${observedAt(NOW.observed_utc)}",
                     "Observed ${observedAt(wind.observed_utc)}",
                     "Measured ${observedAt(tide.observed_utc)}"):
            assert site in SOURCE, site

    def test_the_forecast_tabs_observed_wind_fallback_is_aged_too(self):
        """It only appears when the model has no wind for that hour, which is
        exactly when how old the substitute is matters."""

        wind_block = SOURCE[SOURCE.index("GFS-Wave wind at the buoy, ${DATA"):]
        assert "Observed ${observedAt(fallback.observed_utc)}" in wind_block[:400]

    def test_a_prediction_is_never_given_an_age(self):
        """A modelled wind or a harmonic tide is a forecast FOR a moment, not a
        reading taken AT one. "23 h ago" under next Tuesday would be nonsense,
        so those lines use `stampWhen` and never `observedAt`."""

        for predicted in ("`Forecast for ${stampWhen}`",
                          "`Harmonic tide for ${stampWhen}`"):
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


class TestPastHoursAreExplained:
    """The measured line is the observed chain inside a forecast card. info.html
    says what it is and what the comparison cannot show."""

    def test_info_names_the_comparison_and_its_limit(self):
        assert 'id="past-hours"' in INFO
        assert "what this page showed for that hour" in INFO_TEXT
        assert "the same chain" in INFO_TEXT
        assert "does not check the beach" in INFO_TEXT


class TestAPastHourKeepsItsCard:
    """Owner's report, 2026-09-26: the 11 AM hour, once past, had lost the
    drawing and the calculation it showed as a forecast. A past hour whose
    build kept its full hour is drawn from it, through the same card as a
    current hour; one that kept only a headline says so."""

    def _cards(self, detail):
        node = shutil.which("node")
        if node is None:
            pytest.skip("node is not available")
        fns = ""
        for name in ("cardsForForecast", "measuredAt", "pastNearshore"):
            start = SOURCE.index(f"function {name}(")
            fns += SOURCE[start:SOURCE.index("\n}\n", start) + 2]
        order = SOURCE[SOURCE.index("const ORDER ="):]
        order = order[:order.index("\n") + 1]
        hour = {"valid_utc": "2026-09-26T18:00:00Z", "hs_nearshore_m": 0.55,
                "nearshore": {"effects": {"window_hs_m": 0.8, "shoaled_hs_m": 0.41}},
                "trains": [{"hs_m": 0.51, "period_s": 10.4, "from_deg": 215}],
                "taken_by": [{"blocker": "Point Loma peninsula", "share": 0.3}]}
        entry = {"valid_utc": "2026-09-26T18:00:00Z", "cycle_utc": "2026-09-26T12:00:00Z",
                 "breaks": {"coronado_south": {"hs_m": 0.55, "hs_basis": "breaking",
                                               "depth_m": 1.4}},
                 "detail": {"breaks": {"coronado_south": hour}} if detail else None}
        script = (
            order + "let MEASURED = null; Date.now = () => Date.UTC(2026, 8, 26, 23);\n"
            "const DATA = {breaks: [{id: 'coronado_south', name: 'South', swell_window: [],"
            " hours: [{valid_utc: '2026-09-26T21:00:00Z', trains: [], nearshore: {}}]}]};\n"
            + fns +
            f"const step = {{valid_utc: '2026-09-26T18:00:00Z', from: 'past', entry: {json.dumps(entry)}}};\n"
            "const c = cardsForForecast(step)[0];\n"
            "console.log(JSON.stringify({past: !!c.past, trains: c.trains.length,"
            " takenBy: c.takenBy.length, effects: !!(c.nearshore && c.nearshore.effects),"
            " hs: c.hsWindow}));\n"
            "const cycle = cardsForForecast({valid_utc: '2026-09-26T21:00:00Z', from: 'cycle',"
            " index: 0})[0]; console.log(JSON.stringify({past: !!cycle.past}));\n"
        )
        out = subprocess.run([node, "-e", script], capture_output=True, text=True,
                             check=True).stdout.splitlines()
        return [json.loads(line) for line in out if line.strip()]

    def test_with_its_builds_detail_it_is_the_full_card(self):
        got, cycle = self._cards(detail=True)
        assert got == {"past": False, "trains": 1, "takenBy": 1, "effects": True, "hs": 0.55}
        assert cycle == {"past": False}

    def test_without_it_the_card_says_the_calculation_was_not_kept(self):
        got, _ = self._cards(detail=False)
        assert got["past"] is True and got["effects"] is False
        assert "The calculation for this hour was not kept." in SOURCE
        assert "Only the headline is kept" not in SOURCE


class TestTheWeekChart:
    """The hourly observed series under each Now card (forecast.series). It is
    the observed chain, so it is on the Now tab only; a missing hour breaks the
    line at every zoom rather than being joined across; the archive's older
    hours join the week without anything being filled between them."""

    SECTION = SOURCE[SOURCE.index("// THE CHARTS, under each card"):
                     SOURCE.index("// The swell card, for either chain.")]

    def _run(self, script):
        node = shutil.which("node")
        if node is None:
            pytest.skip("node is not available")
        start = SOURCE.index("function compass(")
        compass = SOURCE[start:SOURCE.index("\n}\n", start) + 2]
        start = SOURCE.index("function point(")
        compass += SOURCE[start:SOURCE.index("\n}\n", start) + 2]
        prelude = (
            "const FT_PER_M = 3.28084;\n"
            "const ORDER = ['coronado_north', 'coronado_center', 'coronado_south'];\n"
            "const SHORT = {coronado_north: 'North', coronado_center: 'Center',"
            " coronado_south: 'South'};\n"
            "const BUOY_TAB = 'buoy';\n"
            "const height = (m) => (m == null ? '-' : m.toFixed(2) + ' m');\n"
            "const svgText = (v) => String(v);\n"
            "const srcLines = () => ''; const remember = () => {}; const KEEP = {};\n"
            "const $ = () => null; let SHOWN = 0; const show = () => { SHOWN += 1; };\n"
            "const fresh = (u) => u; const SERIES_ALL_SOURCE = 'series_all.json';\n"
            "let FETCHED = []; globalThis.fetch = (u) => { FETCHED.push(u);"
            " return new Promise(() => {}); };\n"
            "let SERIES = null, SERIES_ALL = null, NOW = null;\n"
            "const stamp = (i) => new Date(Date.UTC(2026, 8, 20) + i * 3600000).toISOString()"
            ".replace('.000Z', 'Z');\n"
            "const hour = (i, hs) => ({valid_utc: stamp(i), gap: false,"
            " buoy: {hs_m: 1.2, pct_k: 60.4, pct_d: 50, from_deg: 200},"
            " breaks: {coronado_north: {hs_m: hs, transmission: 0.7, pct_k: 20.4, pct_d: 30}},"
            " south_minus_north_m: 0.1});\n"
            "const gap = (i) => ({valid_utc: stamp(i), gap: true});\n"
            "const week = (from, n, holes = []) => Array.from({length: n}, (_, k) =>"
            " holes.includes(from + k) ? gap(from + k) : hour(from + k, 1 + 0.1 * Math.sin(k)));\n"
        )
        out = subprocess.run([node, "-e", prelude + compass + self.SECTION + script],
                             capture_output=True, text=True, check=True,
                             env={**os.environ, "TZ": "America/Los_Angeles"}).stdout
        return [line for line in out.splitlines() if line.strip()]

    def test_each_tab_draws_its_own_chain(self):
        """The Now tab's chart is the observed series and nothing else; the
        Forecast tab's charts are drawn from the model's own hours. Neither
        reads the other's file, and the tab decides which is on screen."""

        now = SOURCE[SOURCE.index("function nowSteps"):]
        now = now[:now.index("\n}\n")]
        fc = SOURCE[SOURCE.index("function fcSteps"):]
        fc = fc[:fc.index("\n}\n")]
        assert "SERIES" in now and "DATA" not in now
        assert "DATA" in fc and "SERIES" not in fc
        assert 'useChain(MODE === "now" ? "now" : "fc");' in SOURCE
        assert "${c.chart ? seriesChart(c.id) : \"\"}" in SOURCE

    def test_a_gap_breaks_the_line_and_a_lone_hour_is_a_dot(self):
        got = self._run(
            "SERIES = {station: '46232', generated_utc: 'x', steps: [hour(0, 1), hour(1, 1.1),"
            " gap(2), hour(3, 1.2), gap(4), hour(5, 1.0), hour(6, 0.9)]};\n"
            "const svg = chartPlot('coronado_north', chartSpec('coronado_north', 'height'),"
            " chartIndex());\n"
            "const main = svg.match(/<path class=\"ln main\" d=\"([^\"]+)\"/)[1];\n"
            "console.log((main.match(/M/g) || []).length, (main.match(/L/g) || []).length);\n"
            "console.log((svg.match(/<circle class=\"pt main\"/g) || []).length);\n"
            "console.log((svg.match(/class=\"gapband\"/g) || []).length);"
        )
        # Two runs of two hours, joined once each; the lone hour 3 is a dot.
        assert got == ["2 2", "1", "2"]

    def test_zoomed_out_a_single_missing_hour_still_breaks_the_line(self):
        """At a year's zoom a column covers dozens of hours. A column holding a
        gap is drawn on its own, so the break survives, and the band is never
        thinner than a pixel."""

        got = self._run(
            "SERIES = {station: '46232', generated_utc: 'x', steps: week(0, 4000, [2000])};\n"
            "setChartRange(Infinity);\n"
            "const svg = chartPlot('coronado_north', chartSpec('coronado_north', 'height'),"
            " chartIndex());\n"
            "const main = svg.match(/<path class=\"ln main\" d=\"([^\"]+)\"/)[1];\n"
            "console.log((main.match(/M/g) || []).length);\n"
            "const band = svg.match(/class=\"gapband\" x=\"[^\"]+\" y=\"[^\"]+\" width=\"([^\"]+)\"/);\n"
            "console.log(Number(band[1]) >= 1);\n"
            "console.log((main.match(/[ML]/g) || []).length < 1200);"
        )
        assert int(got[0]) >= 2
        assert got[1:] == ["true", "true"]

    def test_the_archive_joins_the_week_and_nothing_between_is_filled(self):
        got = self._run(
            "SERIES = {station: '46232', generated_utc: 'g', steps: week(200, 168)};\n"
            "SERIES_ALL = {available: true, start_utc: stamp(0), hours: 150,"
            " breaks: ['coronado_north'], gaps: [3],"
            " from_deg: Array(150).fill(205),"
            " hs_mm: {buoy: Array(150).fill(1216), coronado_north: Array(150).fill(987)},"
            " tr_pm: {coronado_north: Array(150).fill(700)},"
            " k: {buoy: Array(150).fill(60), coronado_north: Array(150).fill(40)},"
            " d: {buoy: Array(150).fill(55), coronado_north: Array(150).fill(45)}};\n"
            "const all = chartSteps();\n"
            "console.log(all.length, all[0].valid_utc === stamp(0), all[3].gap === true);\n"
            "console.log(all[1].buoy.hs_m, all[1].breaks.coronado_north.hs_m,"
            " all[1].breaks.coronado_north.transmission);\n"
            "console.log(all.slice(150, 200).every((s) => s.unbuilt && !s.gap));\n"
            "console.log(all[200] === SERIES.steps[0]);\n"
            "console.log(chartReadout(chartSpec('coronado_north', 'height'), 160));\n"
            "SERIES_ALL = {available: false, why: 'x'};\n"
            "console.log(chartSteps() === SERIES.steps);"
        )
        assert got[0] == "368 true true"
        assert got[1] == "1.216 0.987 0.7"
        assert got[2] == "true" and got[3] == "true"
        assert "not rebuilt yet" in got[4]
        assert got[5] == "true"

    def test_the_window_opens_on_the_last_day_and_asks_for_the_archive_past_it(self):
        got = self._run(
            "SERIES = {station: '46232', generated_utc: 'g', steps: week(0, 191)};\n"
            "let v = chartView(SERIES.steps); console.log(v.v1 - v.v0, v.v1);\n"
            "setChartView(SERIES.steps, 100, 102); v = chartView(SERIES.steps);\n"
            "console.log(v.v1 - v.v0);\n"
            "console.log(FETCHED.length);\n"
            "setChartView(SERIES.steps, -50, 150);\n"
            "console.log(FETCHED.length, ALL_STATE);\n"
            "v = chartView(SERIES.steps); console.log(v.v0 >= 0, v.v1 <= 190);\n"
            "console.log(chartNote(SERIES.steps));"
        )
        assert got[0] == "24 190"                 # owner's default, 2026-09-27
        assert got[1] == "12"                     # never narrower than 12 hours
        assert got[2] == "0"                      # nothing fetched inside the week
        assert got[3] == "1 loading"              # past its left edge asks once
        assert got[4] == "true true"              # but only draws what is loaded
        assert "Loading earlier hours" in got[5]

    def test_a_withheld_archive_says_why_the_view_stops(self):
        got = self._run(
            "SERIES = {station: '46232', generated_utc: 'g', steps: week(0, 191)};\n"
            "setChartRange(Infinity); ALL_STATE = 'loaded';\n"
            "SERIES_ALL = {available: false, why: 'the chain changed'};\n"
            "console.log(chartNote(chartSteps()));\n"
            "SERIES_ALL = {available: false, why: 'no archive yet'};\n"
            "console.log(chartNote(chartSteps()));"
        )
        assert "being rebuilt with today's chain" in got[0]
        assert got[1] == "No earlier hours are archived yet."

    def test_the_time_axis_marks_hours_days_or_months_with_the_window(self):
        got = self._run(
            "SERIES = {station: '46232', generated_utc: 'g', steps: week(0, 6000)};\n"
            "const labels = (a, b) => timeTicks(SERIES.steps, a, b).map((t) => t.label).join(',');\n"
            "console.log(labels(100, 124));\n"
            "console.log(labels(0, 168));\n"
            "console.log(labels(0, 5000));"
        )
        assert "AM" in got[0] or "PM" in got[0]
        assert got[1].startswith(("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"))
        # 208 days: every second month, and January named by its year.
        assert got[2] == "Nov,2027,Mar"

    def test_a_gap_reads_out_as_a_gap(self):
        got = self._run(
            "SERIES = {station: '46232', generated_utc: 'g', steps: [hour(0, 1), gap(1)]};\n"
            "CHART_AT = stamp(1);\n"
            "console.log(chartReadout(chartSpec('coronado_north', 'height'), chartIndex()));"
        )
        assert "left as a gap" in got[0]

    def test_the_default_hour_is_the_newest_reading(self):
        got = self._run(
            "SERIES = {station: '46232', generated_utc: 'g', steps: [hour(0, 1), hour(1, 1),"
            " {valid_utc: stamp(2), gap: false, pending: true}]};\n"
            "console.log(chartIndex());"
        )
        assert got == ["1"]

    def test_the_range_difference_is_the_difference_of_what_it_prints(self):
        got = self._run(
            "SERIES = {station: '46232', generated_utc: 'g', steps: [hour(0, 1), hour(1, 1)]};\n"
            "console.log(chartSpec('coronado_north', 'range').read(0));"
        )
        assert "Buoy %K 60" in got[0] and "North %K 20" in got[0] and "difference +40" in got[0]

    def test_swiping_reads_pinching_zooms_and_the_page_still_scrolls(self):
        """The gestures are the owner's (2026-09-27): swipe along the lines to
        read them, zoom and pan the x axis. Pinned by what makes them work."""

        css = SOURCE[:SOURCE.index("</style>")]
        assert ".chart .plot{touch-action:pan-y;" in css          # vertical = page scroll
        assert "}, {passive: false});" in self.SECTION            # the wheel can be taken
        assert "if (GESTURE) return;" in SOURCE          # nothing rebuilt under a finger
        assert 'g.kind = p.type === "mouse" ? "pan" : Math.abs(dx) >= Math.abs(dy) ? "scrub" : "scroll";' \
            in self.SECTION
        assert "CHART_AT = steps[g.at].valid_utc;" in self.SECTION  # lifting keeps the hour
        # The readout sits above the plot, where a finger does not cover it.
        body = self.SECTION[self.SECTION.index("function chartBody("):]
        assert body.index('class="readout"') < body.index('class="plot"')

    def test_it_folds_out_from_its_own_line_with_the_calculations_caret(self):
        """Owner's design, 2026-09-27: a "Charts" line below the
        drawing, with the calculation's caret -- up while closed, down while
        open -- closed until opened, one state for every tab, kept across a
        refresh."""

        toggle = SOURCE[SOURCE.index("function chartToggle"):]
        toggle = toggle[:toggle.index("\n}\n")]
        assert 'class="calc-toggle" data-chart-toggle' in toggle
        assert 'aria-controls="chart-fold-${id}" aria-expanded="${CHART_OPEN}"' in toggle
        assert "<path d=\"M3.5 10 8 5.5 12.5 10\"/>" in toggle     # drawn pointing up
        chart = SOURCE[SOURCE.index("function seriesChart"):]
        chart = chart[:chart.index("\n}\n")]
        assert "<span>Charts</span>${chartToggle(id)}" in chart
        assert 'id="chart-fold-${id}"${CHART_OPEN ? "" : " hidden"}' in chart
        assert "let CHART_OPEN = false;" in SOURCE
        assert 'CHART_OPEN = recall(KEEP.chartOpen) === "open";' in SOURCE
        assert "setChartOpen(!CHART_OPEN);" in SOURCE
        # Below the drawing, not above it.
        panel = SOURCE[SOURCE.index("function breakPanel"):]
        assert panel.index("${drawing ||") < panel.index("seriesChart(c.id)")

    def test_the_chart_is_picked_from_a_menu_and_opens_on_one_day(self):
        """Owner's design, 2026-09-27: a dropdown, not a row of tabs, and the
        1D window by default."""

        got = self._run(
            "SERIES = {station: '46232', generated_utc: 'g', steps: week(0, 191)};\n"
            "console.log(chartRanges().match(/data-chart-range=\"(\\w+)\" aria-pressed=\"true\"/g).length,"
            " /data-chart-range=\"1d\" aria-pressed=\"true\"/.test(chartRanges()));"
        )
        assert got == ["1 true"]
        body = self.SECTION[self.SECTION.index("function chartBody("):]
        body = body[:body.index("\n}\n")]
        assert '<select class="pick" data-chart-mode aria-label="Which chart">' in body
        assert "<button" not in body
        assert 'strip.addEventListener("change"' in self.SECTION

    def test_each_tab_plots_its_own_line_only_in_ink(self):
        """Owner's call, 2026-09-28: the break tabs and the buoy's tab each plot
        their own series and nothing else, in ink like every other chart.
        Comparing the breaks on one plot is for another part of the page."""

        css = SOURCE[:SOURCE.index("</style>")]
        assert "--buoy:" not in css and "--brk-" not in css
        assert ".series .ln{stroke:var(--ink)}" in css
        assert "b-north" not in SOURCE and "BREAK_KEY" not in SOURCE
        got = self._run(
            "SERIES = {station: '46232', generated_utc: 'g', steps: [hour(0, 1), hour(1, 1.3)]};\n"
            "for (const [tab, mode] of [['buoy', 'height'], ['coronado_north', 'height'],"
            " ['coronado_north', 'window'], ['coronado_north', 'diff'], ['coronado_north', 'range']]) {\n"
            "  const spec = chartSpec(tab, mode);\n"
            "  console.log(mode, spec.lines.map((l) => l.cls + ':' + l.values.join('/')).join(','));\n"
            "}"
        )
        assert got == ["height main:1.2/1.2", "height main:1/1.3", "window main:0.7/0.7",
                       "diff main:-0.1/-0.1", "range slow:20/20,main:40/40"]

    def test_a_chart_of_one_line_has_no_key(self):
        got = self._run(
            "SERIES = {station: '46232', generated_utc: 'g', steps: [hour(0, 1), hour(1, 1)]};\n"
            "console.log(JSON.stringify(chartLegend(chartSpec('coronado_center', 'height'))));\n"
            "console.log(chartLegend(chartSpec('coronado_center', 'window'))"
            ".match(/<\\/i>([^<]+)/g).map((m) => m.slice(4)).join(','));"
        )
        assert got == ['""', "Center's share,Center's windows,Buoy peak from"]

    def test_the_readout_names_only_the_tabs_own_value(self):
        got = self._run(
            "SERIES = {station: '46232', generated_utc: 'g', steps: [hour(0, 1), hour(1, 1)]};\n"
            "console.log(chartSpec('coronado_north', 'height').read(0));\n"
            "console.log(chartSpec('buoy', 'height').read(0));\n"
            "console.log(chartSpec('coronado_north', 'window').read(0));"
        )
        assert got[0] == '<span class="v">North 1.00 m</span>'
        assert got[1] == '<span class="v">Buoy 1.20 m</span>'
        assert got[2] == ('<span class="v">North 70%</span> of the buoy\'s height'
                          ' &middot; buoy peak from <span class="v">SSW 200°</span>')

    def test_the_window_chart_carries_the_buoys_direction_under_it(self):
        """A strip under the Window plot on the same hours: a dot an hour where
        the buoy's peak came from, never joined, over the break's own windows
        shaded. The height chart has no strip."""

        got = self._run(
            "NOW = {breaks: [{id: 'coronado_north', swell_window: ["
            "{from: 164.6, to: 187.4}, {from: 192.5, to: 198.6}, {from: 200.6, to: 241.9}]}]};\n"
            "const steps = [hour(0, 1), hour(1, 1), gap(2), hour(3, 1)];\n"
            "steps[1].buoy.from_deg = 280; steps[3].buoy.from_deg = null;\n"
            "SERIES = {station: '46232', generated_utc: 'g', steps};\n"
            "const svg = chartPlot('coronado_north', chartSpec('coronado_north', 'window'), 1);\n"
            "console.log(svg.match(/viewBox=\"([^\"]+)\"/)[1]);\n"
            "console.log((svg.match(/class=\"winband\"/g) || []).length);\n"
            "console.log((svg.match(/class=\"dir\"/g) || []).length);\n"
            "console.log((svg.match(/class=\"hot\"/g) || []).length);\n"
            "console.log([...svg.matchAll(/class=\"tick ytick\"[^>]*>([^<]+)</g)].map((m) => m[1]).join(','));\n"
            "const flat = chartPlot('coronado_north', chartSpec('coronado_north', 'height'), 1);\n"
            "console.log(flat.match(/viewBox=\"([^\"]+)\"/)[1], /winband|class=\"dir\"/.test(flat));"
        )
        assert got[0] == "0 0 320 218"
        assert got[1] == "3"        # one band per open window
        assert got[2] == "2"        # the gap and the hour with no direction draw nothing
        assert got[3] == "2"        # the hour picked, on the line and on the strip
        assert got[4] == "0%,50%,100%,S,SW,W"
        assert got[5] == "0 0 320 150 false"

    def test_a_direction_off_the_strips_axis_widens_it(self):
        got = self._run(
            "const steps = [hour(0, 1), hour(1, 1)]; steps[0].buoy.from_deg = 100;\n"
            "SERIES = {station: '46232', generated_utc: 'g', steps};\n"
            "const svg = chartPlot('coronado_north', chartSpec('coronado_north', 'window'), 1);\n"
            "console.log([...svg.matchAll(/class=\"tick ytick\"[^>]*>([^<]+)</g)].map((m) => m[1]).slice(3).join(','));"
        )
        assert got == ["SE,S,SW,W"]

    def test_north_vs_south_is_north_less_south(self):
        """Named North vs. South, so the line is north less south: above zero,
        the first-named break is the bigger. The payload keeps south less
        north and the page only flips its sign."""

        got = self._run(
            "const steps = [hour(0, 1), hour(1, 1)]; steps[0].south_minus_north_m = -0.3;\n"
            "SERIES = {station: '46232', generated_utc: 'g', steps};\n"
            "const spec = chartSpec('coronado_center', 'diff');\n"
            "console.log(CHART_MODES.find((m) => m.id === 'diff').label);\n"
            "console.log(spec.lines[0].values[0], spec.above, '|', spec.below);\n"
            "console.log(spec.read(0).replace(/<[^>]+>/g, ''));"
        )
        # North and South are the breaks' names, so they are capitalised.
        assert got == ["North vs. South", "0.3 North bigger | South bigger",
                       "North less South +1.0 ft (+0.30 m)"]

    def test_every_heights_axis_is_framed_by_gridlines(self):
        """The top and bottom of the plot are always ticks, so the frame is
        drawn on every chart: the step is chosen with the rounded ends, never
        from a span the rounding has already widened."""

        got = self._run(
            "let bad = [];\n"
            "for (let r = 0; r <= 12; r += 0.01) {\n"
            "  for (const signed of [false, true]) {\n"
            "    const {domain, ticks} = feetAxis(r, {floor: signed ? 0.1 : 0.3, signed});\n"
            "    const ends = [ticks[0].at, ticks[ticks.length - 1].at];\n"
            "    if (Math.abs(ends[0] - domain[0]) > 1e-9 || Math.abs(ends[1] - domain[1]) > 1e-9"
            " || !(domain[1] > r) || ticks.length > (signed ? 7 : 5)) bad.push([r, signed]);\n"
            "  }\n"
            "}\n"
            "console.log(bad.length);\n"
            "console.log(feetAxis(0.6, {floor: 0.1, signed: true}).ticks.map((t) => t.text).join(','));"
        )
        assert got == ["0", "−3 ft,−2 ft,−1 ft,0,+1 ft,+2 ft,+3 ft"]

    def test_the_readout_sits_against_the_plot_and_grows_upward(self):
        """Owner's design, 2026-09-28: the values hug the chart rather than the
        menu, and a reading that wraps to a third line grows toward the menu."""

        css = SOURCE[:SOURCE.index("</style>")]
        rule = css[css.index(".chart .readout{"):]
        rule = rule[:rule.index("}")]
        assert "justify-content:flex-end" in rule and "min-height" in rule
        assert "readout: `<div>${chartReadout(spec, at, steps)}</div>`," in self.SECTION

    def test_the_plot_runs_to_the_left_edge(self):
        """The y labels moved inside the plot, above their gridlines, so no
        margin is kept for them."""

        assert "const CHART = {w: 320, h: 150, l: 4, r: 6, t: 10, b: 20};" in SOURCE
        assert '<text class="tick ytick" x="${l + 2}"' in self.SECTION

    def test_the_menu_draws_its_carets_at_its_right_edge(self):
        css = SOURCE[:SOURCE.index("</style>")]
        assert "appearance:none" in css[css.index(".chart .pick{"):]
        assert ".chart .pick-wrap::before,.chart .pick-wrap::after{" in css
        assert '<span class="pick-wrap"><select class="pick"' in self.SECTION

    def test_the_foot_line_is_gone_and_info_still_says_it(self):
        """Owner's decision, 2026-09-27: "Observed at 46232 every hour for the
        last 7 days, each carried in by today's chain" is obvious under the
        chart. info.html still says where the hours come from."""

        assert "each carried in by today's chain" not in SOURCE
        assert "function chartFoot" not in SOURCE
        assert "today's" in INFO_TEXT and "rebuilt" in INFO_TEXT


class TestTheForecastCharts:
    """The Forecast tab's charts (owner's request, 2026-09-29): the model's
    3-hourly hours, what the page showed then for the hours already gone, and
    46232 carried in beside them. Nothing is a band, and no difference between
    the forecast and the observed line goes on screen."""

    FIXTURE = (
        "Date.now = () => Date.parse('2026-09-20T07:30:00Z');\n"
        "const when = (iso) => iso;\n"
        "const at = (h) => new Date(Date.UTC(2026, 8, 20, h)).toISOString().replace('.000Z', 'Z');\n"
        "const hourOf = (h, hs, extra = {}) => ({valid_utc: at(h), lead_h: h, hs_nearshore_m: hs,"
        " nearshore: {breaking: {hs_m: hs, depth_m: 2}}, trains: [{hs_m: hs, period_s: 14, from_deg: 205},"
        " {hs_m: 0.2, period_s: 6, from_deg: 280, wind_sea: true}, {hs_m: 0.05, period_s: 1, from_deg: 270,"
        " local: true}], ...extra});\n"
        "let DATA = {generated_utc: at(5), cycle_utc: at(0), station: '46232', breaks: ["
        "{id: 'coronado_north', swell_window: [{from: 200, to: 240}], hours: [0, 3, 6, 9, 12].map((h) => hourOf(h, 1.0 + h / 100))},"
        "{id: 'coronado_south', hours: [0, 3, 6, 9, 12].map((h) => hourOf(h, 0.7))}],"
        " buoy: [0, 3, 6, 9, 12].map((h) => ({valid_utc: at(h), hs_m: 1.5, trains: []})),"
        " runs: [{cycle_utc: at(-6), start_utc: at(-6), step_h: 3,"
        " hs_m: {buoy: [1.4, 1.4, 1.4, 1.4], coronado_north: [0.9, 0.9, 0.9, null]}}],"
        " ensemble: {available: true, cycle_utc: at(0), hours: [0, 3, 12].map((h) => ({valid_utc: at(h),"
        " lead_h: h, hs_mean_m: 1.8, hs_spread_m: 0.1, p_gt_1m: 1, p_gt_2m: 0.3})),"
        " coverage: [{lead_from_h: 0, lead_to_h: 24, n: 400, first_utc: at(-48), last_utc: at(0),"
        " inside_1: 0.07}, {lead_from_h: 24, lead_to_h: 72, n: 12}]}};\n"
        "const past = (h) => ({valid_utc: at(h), from: 'past', lead_h: h + 6, entry: {cycle_utc: at(-6),"
        " buoy: {hs_m: 1.4}, breaks: {coronado_north: {hs_m: 0.9, hs_basis: 'breaking'},"
        " coronado_south: {hs_m: 0.6, hs_basis: '5m'}}, detail: null}});\n"
        "let STEPS = [past(-3), past(0), past(3), {valid_utc: at(6), from: 'cycle', index: 2, lead_h: 6},"
        " {valid_utc: at(12), from: 'cycle', index: 4, lead_h: 12}];\n"
        "let CURSOR = 3;\n"
        "let MEASURED = {generated_utc: at(4), steps: ["
        "{valid_utc: at(0), gap: false, buoy: {hs_m: 1.6}, breaks: {coronado_north: {hs_m: 1.1, hs_basis: 'breaking'},"
        " coronado_south: {hs_m: 0.8, hs_basis: 'breaking'}}},"
        "{valid_utc: at(3), gap: true}]};\n"
        "useChain('fc');\n"
        "const plain = (h) => h.replace(/<[^>]+>/g, '').replace(/&middot;/g, '·');\n"
    )

    def _run(self, script):
        return TestTheWeekChart()._run(self.FIXTURE + script)

    def test_the_hours_are_every_three_and_a_missing_one_is_a_gap(self):
        got = self._run(
            "const st = fcSteps();\n"
            "console.log(st.map((s) => s.valid_utc.slice(11, 13)).join(','));\n"
            "console.log(st.map((s) => { const b = s.shown.breaks.coronado_north;"
            " return b ? b.hs_m : 'none'; }).join(','));\n"
            "console.log(st.map((s) => { const b = s.run.breaks.coronado_north;"
            " return b ? b.hs_m : 'none'; }).join(','));"
        )
        # 09Z is covered by neither the log nor an offered hour: a gap.
        assert got[0] == "21,00,03,06,09,12"
        # Before this run was published, the log's figure; after, this run's.
        assert got[1] == "0.9,0.9,0.9,1.06,none,1.12"
        assert got[2] == "none,1,1.03,1.06,1.09,1.12"

    def test_only_a_breaking_height_is_drawn(self):
        got = self._run(
            "console.log(fcSteps().map((s) => { const b = s.shown.breaks.coronado_south;"
            " return b ? String(b.hs_m) : 'none'; }).join(','));"
        )
        assert got == ["null,null,null,0.7,none,0.7"]

    def test_observed_only_once_the_hour_has_passed_and_a_gap_stays_one(self):
        got = self._run(
            "console.log(fcSteps().map((s) => s.state).join(','));\n"
            "console.log(fcSteps()[1].observed.breaks.coronado_north, fcSteps()[1].observed.buoy);"
        )
        # 06Z has passed but no collection has rebuilt it yet: not a gap.
        assert got[0] == "none,value,gap,pending,future,future"
        assert got[1] == "1.1 1.6"

    def test_earlier_runs_line_up_by_time(self):
        got = self._run(
            "console.log(fcSteps().map((s) => { const e = s.earlier[0];"
            " return e ? String(e.breaks.coronado_north) : 'none'; }).join(','));"
        )
        assert got == ["0.9,0.9,null,none,none,none"]

    def test_forecast_and_observed_is_the_runs_view_and_opens_first(self):
        """Owner's call, 2026-09-30: the separate "Forecast & observed" view is
        gone; the runs view took its name and opens first."""

        got = self._run(
            "console.log(FC_MODES.map((m) => m.id + ':' + m.label).join('|'));\n"
            "console.log(FC_MODE0, chartModeFor('coronado_north'));\n"
            "CHART_MODE = 'height'; console.log(chartModeFor('coronado_north'));\n"
            "const spec = chartSpec('coronado_north', 'height');\n"
            "console.log(spec.lines.map((l) => l.cls).join(','), spec.now);"
        )
        assert got[0] == ("runs:Forecast + Observed|trains:Swell trains|diff:North vs. South"
                          "|ensemble:Ensemble")
        # A view remembered from before falls to the first on offer.
        assert got[1:] == ["runs runs", "runs", "run,obs,main 3.5"]

    def test_the_runs_chart_draws_each_run_and_calls_the_spread_no_range(self):
        got = self._run(
            "const spec = chartSpec('coronado_north', 'runs');\n"
            "console.log(spec.lines.map((l) => l.cls).join(','));\n"
            "console.log(plain(spec.read(1)));\n"
            "console.log(spec.says);"
        )
        assert got[0] == "run,obs,main"
        assert got[1] == "Newest GFS-Wave run 1.00 m · 1 earlier run 0.90 m · observed 1.10 m"
        assert "not a range the swell will fall in" in got[2]

    def test_the_trains_are_dots_without_the_local_chop(self):
        got = self._run(
            "const spec = chartSpec('coronado_north', 'trains');\n"
            "console.log(spec.lines.length, spec.dots.filter((d) => d.i === 3).map((d) => d.cls).join('|'));\n"
            "console.log(spec.lane.points.filter((p) => p.i === 3).map((p) => p.v).join(','));\n"
            "console.log(spec.lane.arcs.length);\n"
            "console.log(spec.read(0));\n"
            "const svg = chartPlot('coronado_north', spec, 3, fcSteps(), {v0: 0, v1: 5});\n"
            "console.log((svg.match(/class=\"tr[^\"]*\"/g) || []).length, (svg.match(/ on\"/g) || []).length);"
        )
        assert got[0] == "0 tr|tr ws"
        assert got[1] == "205,280"
        assert got[2] == "1"
        assert got[3] == "the trains for this hour were not kept"
        # The first three hours are an earlier run's whose trains were not
        # kept; the two this run offers carry two trains each.
        assert got[4] == "4 2"

    def test_north_vs_south_is_north_less_south(self):
        got = self._run(
            "const spec = chartSpec('coronado_north', 'diff');\n"
            "console.log(spec.lines[1].values.map((v) => v == null ? 'none' : v.toFixed(2)).join(','));\n"
            "console.log(spec.lines[0].values[1].toFixed(2));"
        )
        # South's past figures were at 5 m, not breaking, so no difference.
        assert got == ["none,none,none,0.36,none,0.42", "0.30"]

    def test_the_buoy_tab_offers_no_difference_between_breaks(self):
        got = self._run(
            "console.log(chartModes('buoy').map((m) => m.id).join(','));\n"
            "console.log(chartModes('coronado_north').map((m) => m.id).join(','));"
        )
        # The ensemble is total height at the buoy, with no direction for a
        # break's windows: the buoy's tab only.
        assert got == ["runs,trains,ensemble", "runs,trains,diff"]

    def test_the_ensemble_band_comes_with_how_often_the_buoy_fell_inside_it(self):
        got = self._run(
            "const spec = chartSpec('buoy', 'ensemble');\n"
            "console.log(spec.lines.map((l) => l.cls).join(','));\n"
            "console.log(spec.band.hi.map((v) => v == null ? 'none' : v.toFixed(1)).join(','));\n"
            "console.log(spec.says);\n"
            "console.log(plain(spec.read(1)));\n"
            "const svg = chartPlot('buoy', spec, 1, fcSteps(), {v0: 0, v1: 5});\n"
            "console.log((svg.match(/<polygon class=\"ensband\"/g) || []).length);"
        )
        assert got[0] == "obs,main,ens"
        # 06Z and 09Z have no ensemble hour: a gap in the band, never bridged.
        assert got[1] == "none,1.9,1.9,none,none,1.9"
        assert "fell inside the band on 7% of hours within a day (400 forecast hours" in got[2]
        assert "about 68%" in got[2] and "no direction" in got[2]
        assert got[3].startswith("Ensemble mean 1.80 m ±0.3 ft (±0.10 m) · 30% of members above")
        # One run of two hours is a polygon; the lone 12Z hour cannot be one.
        assert got[4] == "1"

    def test_an_unmeasured_band_says_so(self):
        got = self._run(
            "DATA.ensemble.coverage = [];\n"
            "console.log(chartSpec('buoy', 'ensemble').says);"
        )
        assert "has not been measured yet" in got[0]

    def test_the_two_chains_keep_their_own_window_hour_and_view(self):
        got = self._run(
            "CHART_MODE = 'runs'; CHART_AT = at(6); setChartRange(24);\n"
            "useChain('now');\n"
            "console.log(CHART_MODE, CHART_AT, CHART_VIEW);\n"
            "CHART_MODE = 'window';\n"
            "useChain('fc');\n"
            "console.log(CHART_MODE, CHART_AT, (CHART_VIEW.to - CHART_VIEW.from) / 3600000);\n"
            "useChain('now');\n"
            "console.log(CHART_MODE);"
        )
        assert got == ["height null null", f"runs 2026-09-20T06:00:00Z 24", "window"]

    def test_the_opening_view_puts_the_present_a_quarter_in(self):
        got = self._run(
            "const st = fcSteps();\n"
            "const v = chartView(st); console.log(v.v0, v.v1);\n"
            "console.log(chartIndex(st));"
        )
        # Six 3-hourly hours cover 15 h; the whole of it is shown, and the
        # picked hour is the one the page is on.
        assert got == ["0 5", "3"]

    def test_a_three_hourly_axis_still_marks_midnight(self):
        got = self._run(
            "const st = Array.from({length: 17}, (_, k) => ({valid_utc: at(3 * k)}));\n"
            "console.log(timeTicks(st, 0, 16).map((t) => t.i.toFixed(2) + ':' + t.label).join(','));"
        )
        # Local midnight (07Z in September) falls between two 3-hourly hours.
        assert got[0].startswith("2.33:") and got[0].count(":") >= 2

    def test_nothing_on_the_forecast_charts_reads_as_a_score(self):
        """No band and no score, except the ensemble's band, which is drawn only
        beside the share of hours 46232 fell inside it (tested above)."""

        section = SOURCE[SOURCE.index("function fcSpec"):SOURCE.index("// The y axis for the hours in view:")]
        section = (section[:section.index('if (mode === "ensemble" && buoy) {')]
                   + section[section.index("// Forecast + Observed (owner's name"):])
        for word in ("band", "%", "error of", "actual", "confiden"):
            text = [line for line in section.splitlines() if word in line and "`" in line
                    and not line.strip().startswith("//")]
            if word == "band":
                assert not [line for line in text if re.search(r"\bbands?\b", line)], text
            elif word == "%":
                assert not [line for line in text if "%K" not in line], text
            else:
                assert not text, text


class TestTheProvenanceDivider:
    """Owner's design, 2026-09-27: a rule above the provenance lines on every
    card, on both tabs -- set once on the block every card's provenance goes
    through, so no card can be left out."""

    def test_it_is_drawn_by_the_provenance_block_itself(self):
        css = SOURCE[:SOURCE.index("</style>")]
        rule = css[css.index(".cond .srcs{"):]
        rule = rule[:rule.index("}")]
        assert "border-top:1px solid var(--line)" in rule
        assert "padding-top" in rule

    def test_every_provenance_line_goes_through_that_block(self):
        assert 'return body ? `<div class="srcs">${body}</div>` : "";' in SOURCE
        # Cards build their provenance with srcLines, never a bare src line
        # outside it (the chart's own explanation is inside its fold).
        cards = SOURCE[SOURCE.index("function renderConditions("):]
        cards = cards[:cards.index("\nfunction renderBreaks(")]
        assert "srcLines(" in cards and '<span class="src">' not in cards

    def test_a_measured_box_under_a_value_gets_room_above_it(self):
        """Owner's design, 2026-09-27: on the wind and tide cards the green box
        sat in the card's 2 px gap, tight against the value above it."""

        css = SOURCE[:SOURCE.index("</style>")]
        assert ".cond > .measured{margin-top:8px}" in css

    def test_the_chart_no_longer_draws_its_own(self):
        css = SOURCE[:SOURCE.index("</style>")]
        assert ".chart{display:flex;flex-direction:column;gap:6px}" in css

    def test_the_charts_own_explanation_is_not_a_second_provenance_block(self):
        """It explains the chart, not where the card came from: inside the
        block it drew a second rule a line above the card's own."""

        body = SOURCE[SOURCE.index("function chartBody("):]
        body = body[:body.index("\n}\n")]
        assert "srcLines(" not in body
        assert '<span class="src">${period(spec.says)}</span>' in body


class TestHousekeeping20260930:
    """Owner's calls, 2026-09-30."""

    def test_the_observed_tab_is_now_ish(self):
        assert 'aria-controls="panel">NOW(ISH)</button>' in SOURCE
        assert "What NOW(ISH) is standing on" in INFO

    def test_the_readout_keeps_room_for_three_lines(self):
        """A reading that grows onto a third line while scrubbing must not push
        the plot down under the finger."""

        css = SOURCE[:SOURCE.index("</style>")]
        rule = css[css.index(".chart .readout{"):]
        assert "min-height:calc(3 * 1.45em)" in rule[:rule.index("}")]

    def test_the_breaks_are_named_with_capitals(self):
        for lower in ("North less south", "less south's", "north less south"):
            assert lower not in SOURCE and lower not in INFO, lower


class TestTheLocalWindOnTheForecastTab:
    """The NWS grid's wind on the sand under the model's wind at the buoy, and
    the per-break offshore reading made from it -- never from the buoy's."""

    def _run(self, script):
        node = shutil.which("node")
        if node is None:
            pytest.skip("node is not available")

        def fn(name):
            start = SOURCE.index(f"function {name}(")
            return SOURCE[start:SOURCE.index("\n}\n", start) + 2]

        prelude = (
            "const FT_PER_M = 3.28084; const MPH_PER_KT = 1.15078; let SWELL_TAB = 'coronado_north';\n"
            "const speed = (kt) => `${Math.round(kt * MPH_PER_KT)} mph (${Math.round(kt)} kt)`;\n"
            "const when = (iso) => iso; const period = (t) => t;\n"
            "const srcLines = (lines) => [].concat(lines || []).filter(Boolean).map((l) => `<src>${l}</src>`).join('');\n"
            "let DATA = {local_wind: {available: true, office: 'SGX', grid_x: 55, grid_y: 12,"
            " updated_utc: '2026-09-30T04:00:00Z'}};\n"
        )
        body = "".join(fn(n) for n in ("compass", "sense", "windAtBreaks", "localWindBlock"))
        out = subprocess.run([node, "-e", prelude + body + script], capture_output=True,
                             text=True, check=True).stdout
        return out.strip()

    def test_the_local_wind_and_each_breaks_reading(self):
        got = self._run(
            "const hour = {local_wind_from_deg: 30, local_wind_kt: 8, local_gust_kt: 14};\n"
            "const cards = [{id: 'coronado_north', windOffshore: 0.96}, {id: 'coronado_south', windOffshore: -0.5}];\n"
            "console.log(localWindBlock(hour, cards, 'Tue 3 PM', false).replace(/\\s+/g, ' '));"
        )
        assert "Local</span>" in got and "NNE 30°" in got and "9 mph (8 kt)" in got
        assert "gusting 16 mph" in got
        assert "<b>offshore</b> at this break" in got and "<b>onshore</b> at this break" in got
        assert "<src>Forecast for Tue 3 PM</src>" in got
        assert "NWS forecast grid SGX 55,12 at Coronado, updated 2026-09-30T04:00:00Z" in got

    def test_an_hour_without_it_says_so_and_a_past_hour_borrows_nothing(self):
        got = self._run(
            "console.log(JSON.stringify(localWindBlock({}, [], 'x', true)));\n"
            "DATA.local_wind = {available: false, why: 'api.weather.gov: HTTP 503'};\n"
            "console.log(localWindBlock({}, [], 'x', false).replace(/\\s+/g, ' '));"
        )
        first, second = got.splitlines()
        assert first == '""'
        assert "no local forecast" in second and "api.weather.gov: HTTP 503" in second

    def test_the_forecast_cards_read_offshore_from_the_local_wind(self):
        cards = SOURCE[SOURCE.index("function cardsForForecast"):]
        cards = cards[:cards.index("\n}\n")]
        assert "windOffshore: h.local_wind_offshore" in cards
        assert "windOffshore: b.wind_offshore" not in cards
