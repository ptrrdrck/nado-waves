"""The app surface has to keep the project's central rule on screen.

CLAUDE.md: "Until a verification series exists, the output is *physically
derived*, never *accurate*. That distinction belongs in the UI, not only the
README." A README can be honest while the screen quietly is not, so the screen
gets its own test.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parent.parent / "app" / "forecast.html"
SOURCE = APP.read_text(encoding="utf-8")
TEXT = re.sub(r"\s+", " ", SOURCE)


class TestItSaysWhatItIsStandingOn:
    def test_the_four_levels_are_all_rendered(self):
        for level in ("geometry", "model", "calibration", "observation"):
            assert f'["{level}"' in SOURCE or f'"{level}"' in SOURCE

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
        """BRIEFING §12: the south-east arc runs across unmodelled Baja coast."""

        assert "swell_window" in SOURCE
        assert "open_windows" not in SOURCE

    def test_the_assumed_spread_is_shown_rather_than_hidden(self):
        assert "spread_assumption" in SOURCE
        assert "Directional spread is assumed" in TEXT


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

        for accessor in re.findall(r"\b(?:hour|entry|data|t|spread)\.([a-z_]{3,})\b", SOURCE):
            if accessor in {"map", "filter", "find", "join", "length", "split",
                            "toFixed", "textContent", "innerHTML"}:
                continue
            assert accessor in known, f"page reads unknown field {accessor!r}"
