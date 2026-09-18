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
        "warnings": [],
        "spread_assumption": {"swell_deg": 20.0, "wind_sea_deg": 35.0, "note": "not fitted"},
        "breaks": [
            {
                "id": f"coronado_{name}",
                "name": name,
                "confidence": "high",
                "swell_window": [[201.2, 250.3]],
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
