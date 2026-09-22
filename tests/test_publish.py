"""Tests for the public delivery bundle.

Two failure modes matter here, and both are invisible to a reader of the code.
The bundle is built from files that live at different relative paths than they
do when published, so a page that works in the repository can fetch a 404 on
the web; and thinning the data is only safe while the page and the publisher
agree on which hours are rendered.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from forecast import publish

PAGE = Path(__file__).resolve().parent.parent / "app" / "forecast.html"
PAGE_SOURCE = PAGE.read_text(encoding="utf-8")


def forecast(hours: int = 25, breaks: int = 3) -> dict:
    return {
        "generated_utc": "2026-09-18T12:00:00Z",
        "cycle_utc": "2026-09-18T12:00:00Z",
        "station": "46232",
        "standing_on": {"observation": "none"},
        "geometry": {
            "chart_product": "NOAA ENC, approach band (usage band 4)",
            "cells": ["US4CA1BX.000", "US4CA74M.000"],
            "from_imagery": ["Point Loma peninsula"],
            "unverified": [],
        },
        "warnings": [],
        "spread_assumption": {"swell_deg": 20.0, "wind_sea_deg": 35.0, "note": "not fitted"},
        "breaks": [
            {
                "id": f"coronado_{name}",
                "name": name,
                "confidence": "high",
                "swell_window": [
                    {"from": 202.6, "to": 250.3,
                     "opened_by": "Coronado Islands (north)",
                     "closed_by": "Point Loma peninsula", "confidence": "high"},
                ],
                "shore_normal_deg": 214.2,
                "normal_is_a_guess": False,
                "wind": {},
                "hours": [
                    {"valid_utc": f"2026-09-18T{h % 24:02d}:00:00Z", "lead_h": h,
                     "hs_offshore_m": 0.8, "hs_window_m": 0.6, "fraction": 0.6,
                     "dominant_period_s": 15.0, "dominant_from_deg": 196.0,
                     "taken_by": [], "tide_m": None, "tide_kind": None}
                    for h in range(hours)
                ],
            }
            for name in list(("north", "center", "south"))[:breaks]
        ],
        "tide": [
            {"valid_utc": f"2026-09-18T{h % 24:02d}:00:00Z", "height_m": float(h), "kind": "predicted"}
            for h in range(hours)
        ],
        "buoy": [
            {"valid_utc": f"2026-09-18T{h % 24:02d}:00:00Z", "hs_m": 1.0,
             "peak_period_s": 14.0, "peak_direction_deg": 200, "frequency_bins": 50,
             "trains": []}
            for h in range(hours)
        ],
    }


def write(tmp_path: Path, data: dict) -> Path:
    live = tmp_path / "live"
    live.mkdir(parents=True, exist_ok=True)
    (live / "forecast.json").write_text(json.dumps(data), encoding="utf-8")
    return tmp_path


class TestTheDataPathIsRepointed:
    """The bundle is flat; the repository is not. A page that still fetches
    ../data/live/forecast.json renders an empty shell on the web."""

    def test_the_published_page_fetches_the_flat_path(self, tmp_path):
        publish.build(tmp_path / "site", data_dir=write(tmp_path / "d", forecast()))
        index = (tmp_path / "site" / "index.html").read_text()
        assert publish.BUNDLE_DATA_PATH in index
        assert publish.REPO_DATA_PATH not in index

    def test_the_page_in_the_repository_still_uses_the_repository_path(self):
        """The repointing is a publish-time rewrite, not an edit to the page —
        app/forecast.html has to keep working when served from the repo root."""

        assert publish.REPO_DATA_PATH in PAGE_SOURCE

    def test_the_observed_path_is_repointed_too(self, tmp_path):
        publish.build(tmp_path / "site", data_dir=write(tmp_path / "d", forecast()))
        index = (tmp_path / "site" / "index.html").read_text()
        assert publish.BUNDLE_NOW_PATH in index
        assert publish.REPO_NOW_PATH not in index

    def test_a_page_that_stopped_using_that_path_fails_loudly(self):
        with pytest.raises(ValueError, match="no longer fetches"):
            publish.repoint("<title>x</title><script>fetch('somewhere/else.json')</script>")


class TestThinningMatchesWhatThePageRenders:
    def test_the_publisher_and_the_page_agree_on_the_step(self):
        """If the page's filter and HOUR_STEP drift apart, the bundle either
        carries rows nobody sees or drops rows the picker offers."""

        match = re.search(r"h\.lead_h % (\d+) === 0", PAGE_SOURCE)
        assert match, "the page no longer filters hours by lead_h"
        assert int(match.group(1)) == publish.HOUR_STEP

    def test_thinning_keeps_every_third_lead_hour(self):
        thinned = publish.thin(forecast(hours=25))
        leads = [h["lead_h"] for h in thinned["breaks"][0]["hours"]]
        assert leads == [0, 3, 6, 9, 12, 15, 18, 21, 24]

    def test_thinning_is_idempotent(self):
        """It runs every cycle; thinning an already-thin file must not thin
        it again, which indexing by position rather than lead_h would do."""

        once = publish.thin(forecast(hours=25))
        twice = publish.thin(once)
        assert once["breaks"][0]["hours"] == twice["breaks"][0]["hours"]

    def test_the_step_is_recorded_in_the_published_file(self, tmp_path):
        publish.build(tmp_path / "site", data_dir=write(tmp_path / "d", forecast()))
        payload = json.loads((tmp_path / "site" / "forecast.json").read_text())
        assert payload["hour_step_h"] == publish.HOUR_STEP

    def test_thinning_drops_no_break(self, tmp_path):
        publish.build(tmp_path / "site", data_dir=write(tmp_path / "d", forecast()))
        payload = json.loads((tmp_path / "site" / "forecast.json").read_text())
        assert len(payload["breaks"]) == 3


class TestTheTideSeriesStaysAlignedWithTheHours:
    """The tide series and each break's hours are separate lists filtered
    separately, so indexing them in parallel pairs the wrong rows — it showed a
    3 p.m. tide against a 9 p.m. forecast. Both sides key on valid_utc."""

    def test_thinning_keeps_tide_only_for_hours_that_survive(self):
        thinned = publish.thin(forecast(hours=25))
        kept = {h["valid_utc"] for h in thinned["breaks"][0]["hours"]}
        assert {t["valid_utc"] for t in thinned["tide"]} == kept

    def test_the_two_lists_end_up_the_same_length(self):
        thinned = publish.thin(forecast(hours=25))
        assert len(thinned["tide"]) == len(thinned["breaks"][0]["hours"])

    def test_the_buoy_series_is_thinned_with_the_hours_too(self):
        """It is per hour like the tide. Unthinned it shipped 169 entries for
        a page that renders 57."""

        thinned = publish.thin(forecast(hours=25))
        kept = {h["valid_utc"] for h in thinned["breaks"][0]["hours"]}
        assert {b["valid_utc"] for b in thinned["buoy"]} == kept

    def test_position_and_timestamp_agree_after_thinning(self):
        """The bug was positional lookup against an unthinned series. Even
        though the page now keys on time, drift here would waste bytes and
        mislead anyone who does index in parallel."""

        thinned = publish.thin(forecast(hours=25))
        for hour, tide in zip(thinned["breaks"][0]["hours"], thinned["tide"]):
            assert hour["valid_utc"] == tide["valid_utc"]

    def test_the_page_looks_tide_up_by_timestamp(self):
        assert "TIDE_BY_TIME[stamp.valid_utc]" in PAGE_SOURCE
        assert "(DATA.tide || [])[index]" not in PAGE_SOURCE


class TestItRefusesToPublishNothing:
    def test_a_missing_forecast_is_an_error_not_an_empty_bundle(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="forecast.live"):
            publish.build(tmp_path / "site", data_dir=tmp_path / "empty")

    def test_a_forecast_with_no_breaks_is_refused(self, tmp_path):
        """forecast.live returns an empty breaks list when no cycle was
        available. Publishing that puts a blank page in front of readers."""

        data = forecast()
        data["breaks"] = []
        with pytest.raises(ValueError, match="no breaks"):
            publish.build(tmp_path / "site", data_dir=write(tmp_path / "d", data))

    def test_main_reports_rather_than_raising(self, tmp_path, capsys):
        assert publish.main(["--out", str(tmp_path / "site"),
                             "--data-dir", str(tmp_path / "empty")]) == 1
        assert "Not published" in capsys.readouterr().out


class TestTheBundleIsServable:
    def test_every_file_pages_needs_is_present(self, tmp_path):
        written = publish.build(tmp_path / "site", data_dir=write(tmp_path / "d", forecast()))
        assert set(written) == {"index.html", "forecast.json", ".nojekyll", "README.md"}
        for name in written:
            assert (tmp_path / "site" / name).exists()

    def test_nojekyll_is_present_so_pages_serves_files_as_is(self, tmp_path):
        publish.build(tmp_path / "site", data_dir=write(tmp_path / "d", forecast()))
        assert (tmp_path / "site" / ".nojekyll").exists()

    def test_index_is_a_standalone_document(self, tmp_path):
        publish.build(tmp_path / "site", data_dir=write(tmp_path / "d", forecast()))
        index = (tmp_path / "site" / "index.html").read_text()
        assert index.startswith("<!doctype html>")
        assert index.rstrip().endswith("</html>")
        assert "<title>" in index

    def test_the_readme_says_where_to_edit_and_what_the_page_is_not(self, tmp_path):
        publish.build(tmp_path / "site", data_dir=write(tmp_path / "d", forecast()))
        readme = (tmp_path / "site" / "README.md").read_text()
        assert "nado-waves" in readme and "Edit them there" in readme
        assert "physically derived" in readme
        assert "not a wave height" in readme.replace("\n", " ")

    def test_the_readme_explains_the_split_from_the_observation_log(self, tmp_path):
        """The log never shows a forecast. Someone will eventually ask why
        these are two repositories; the answer belongs next to the answer."""

        publish.build(tmp_path / "site", data_dir=write(tmp_path / "d", forecast()))
        readme = (tmp_path / "site" / "README.md").read_text()
        assert "nado-waves-log" in readme
        assert "not a browser security boundary" in readme

    def test_rebuilding_replaces_rather_than_accumulates(self, tmp_path):
        data_dir = write(tmp_path / "d", forecast())
        publish.build(tmp_path / "site", data_dir=data_dir)
        (tmp_path / "site" / "stale.html").write_text("old", encoding="utf-8")
        publish.build(tmp_path / "site", data_dir=data_dir)
        assert not (tmp_path / "site" / "stale.html").exists()


class TestTheTideTurnsSurviveThinning:
    """The per-hour series are thinned by kept `valid_utc`. The turns are not
    a per-hour series — CO-OPS puts them at 11:42, not 11:00 — so filtering
    them the same way would delete very nearly all of them, and the card would
    silently lose its second line on the published page only."""

    TURNS = [
        {"valid_utc": "2026-09-19T11:42:00Z", "height_m": 1.712,
         "event": "high", "direction": "rising"},
        {"valid_utc": "2026-09-19T18:06:00Z", "height_m": 0.134,
         "event": "low", "direction": "falling"},
    ]

    def forecast(self):
        return {
            "breaks": [{"id": "coronado_north", "hours": [
                {"lead_h": h, "valid_utc": f"2026-09-19T{h:02d}:00:00Z"}
                for h in range(6)
            ]}],
            "tide": [{"valid_utc": f"2026-09-19T{h:02d}:00:00Z", "height_m": 1.0}
                     for h in range(6)],
            "tide_turns": list(self.TURNS),
        }

    def test_no_turn_is_dropped_for_sitting_off_the_hour(self):
        out = publish.thin(self.forecast(), step=3)
        assert out["tide_turns"] == self.TURNS

    def test_the_per_hour_series_are_still_thinned(self):
        """The control: thinning is working, so the test above is not passing
        because nothing is filtered at all."""

        out = publish.thin(self.forecast(), step=3)
        assert len(out["tide"]) == 2 and len(out["breaks"][0]["hours"]) == 2

    def test_thinning_stays_idempotent_with_turns_present(self):
        once = publish.thin(self.forecast(), step=3)
        assert publish.thin(once, step=3) == once


class TestTheObservedJobShipsThePageToo:
    """The page and its payload must not reach the public repository on
    different cadences.

    They did. `index.html` and `forecast.json` ship from the forecast job, four
    times a day; `now.json` ships from the observed job, every ten minutes.
    BRIEFING §35 caught that gap one way round -- a newer page met an
    older-shaped `now.json`. On 2026-09-22 it bit the other way: `now.json`
    carried `next_expected` for fifteen minutes before the page that reads it
    was published, so the countdown simply did not appear.

    Publishing the page from BOTH jobs closes the gap in both directions. It is
    45 KB of static HTML that git sees as unchanged whenever it has not
    changed.
    """

    def test_the_now_only_bundle_carries_the_page(self, tmp_path):
        (tmp_path / "live").mkdir()
        (tmp_path / "live" / "now.json").write_text(
            json.dumps({"generated_utc": "2026-09-22T08:00:00Z"}), encoding="utf-8"
        )
        out = tmp_path / "bundle"
        written = publish.build_now_only(out, data_dir=tmp_path)

        assert "index.html" in written
        assert "now.json" in written
        assert (out / "index.html").exists()

    def test_it_is_the_same_page_the_forecast_job_publishes(self, tmp_path):
        """Two jobs writing the same filename must write the same bytes, or
        whichever ran last would decide which page the reader got."""

        (tmp_path / "live").mkdir()
        (tmp_path / "live" / "now.json").write_text(
            json.dumps({"generated_utc": "2026-09-22T08:00:00Z"}), encoding="utf-8"
        )
        (tmp_path / "live" / "forecast.json").write_text(
            json.dumps(forecast()), encoding="utf-8"
        )
        only_now = tmp_path / "a"
        publish.build_now_only(only_now, data_dir=tmp_path)

        full = tmp_path / "b"
        publish.build(full, data_dir=tmp_path)

        assert (only_now / "index.html").read_bytes() == (full / "index.html").read_bytes()

    def test_it_still_refuses_to_ship_the_forecast(self, tmp_path):
        """The reason the observed job is separate: `forecast.json` is rebuilt
        from a live NOAA fetch four times a day, and copying it every ten
        minutes would leave it byte-identical almost every time."""

        (tmp_path / "live").mkdir()
        (tmp_path / "live" / "now.json").write_text(
            json.dumps({"generated_utc": "2026-09-22T08:00:00Z"}), encoding="utf-8"
        )
        out = tmp_path / "bundle"
        written = publish.build_now_only(out, data_dir=tmp_path)

        assert "forecast.json" not in written
        assert not (out / "forecast.json").exists()
