"""Fetching NOAA's surveyed shoreline.

No network here: every NOAA coastal host is denied at CONNECT from a session
(measured 2026-09-20), so the parsing and the discovery walk are tested against
fixtures and the job itself runs on Actions.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from collector import shoreline as mod


def catalog(services=(), folders=()):
    return json.dumps({
        "services": [{"name": n, "type": t} for n, t in services],
        "folders": list(folders),
    }).encode()


class TestItDiscoversRatherThanGuesses:
    """`probe_mop` says in its own docstring that guessing a deep URL produced
    two wrong verdicts earlier in this project. This walks the catalogue."""

    def test_no_layer_path_is_hardcoded(self):
        """Catalogue roots and folders are fine — they are things to walk. A
        LAYER path is the thing that must be discovered, because guessing one
        is what `probe_mop` records as having produced two wrong verdicts."""

        source = Path("collector/shoreline.py").read_text(encoding="utf-8")
        for root in mod.CATALOG_ROOTS:
            assert "/rest/services" in root, root
            assert "MapServer" not in root and "FeatureServer" not in root, root
            assert not root.rstrip("/").split("/")[-1].isdigit(), root
        assert "MapServer/" not in source.split("def ")[0]

    def test_the_listing_is_reported_even_when_nothing_matches(self):
        """The first run of this probe returned "0 candidate services" from a
        catalogue it had barely opened, which is a statement about the filter
        and not about NOAA. What was actually there is now the finding."""

        attempt = mod.Attempt(url="https://example.test/arcgis/rest/services",
                              ok=True, note="0 candidate service(s)",
                              listing=["Bathymetry (MapServer)", "chartdata/ (folder)"])
        text = mod.format_summary(mod.Result(attempts=[attempt]))
        assert "Bathymetry (MapServer)" in text and "chartdata/" in text

    def test_a_non_json_body_is_sampled_so_it_can_be_identified(self):
        """"not JSON" cannot tell an HTML error page from a login redirect, and
        a second Actions run to find out is a wasted round trip."""

        attempt = mod.Attempt(url="https://example.test", note="not JSON",
                              sample="<!DOCTYPE html><title>Sign in</title>")
        assert "Sign in" in mod.format_summary(mod.Result(attempts=[attempt]))

    def test_folders_are_opened_regardless_of_their_name(self, monkeypatch):
        """A shoreline layer can live in a folder called anything. Filtering
        folders by name is how the first run missed the catalogue entirely."""

        def fake(url, **k):
            if url.endswith("services?f=json"):
                return {"services": [], "folders": ["chartdata"]}
            return {"services": [{"name": "chartdata/CUSP", "type": "MapServer"}]}
        monkeypatch.setattr(mod, "fetch_json", fake)
        got = mod.discover(("https://example.test/arcgis/rest/services",))
        assert any("CUSP" in c for c in got.candidates), got.candidates

    def test_it_matches_shoreline_services_case_insensitively(self):
        for name in ("CUSP", "cusp_shoreline", "Coastal_Survey", "MHW_Shoreline"):
            assert mod.WANTED.search(name), name

    def test_it_ignores_unrelated_services(self):
        for name in ("Bathymetry", "ElevationTiles", "Hurricanes"):
            assert not mod.WANTED.search(name), name

    def test_only_map_and_feature_servers_are_candidates(self, monkeypatch):
        monkeypatch.setattr(mod, "fetch_json", lambda url, **k: json.loads(
            catalog(services=[("CUSP", "MapServer"), ("CUSP_Image", "ImageServer")])))
        got = mod.discover(("https://example.test/arcgis/rest/services",))
        assert len(got.candidates) == 1 and got.candidates[0].endswith("MapServer")

    def test_a_denied_root_is_classified_not_swallowed(self, monkeypatch):
        def boom(url, **k):
            raise OSError("gateway answered 403 to CONNECT")
        monkeypatch.setattr(mod, "fetch_json", boom)
        got = mod.discover(("https://example.test/arcgis/rest/services",))
        assert got.denied and "403" in got.attempts[0].note
        assert "Denied at CONNECT" in mod.format_summary(got)


class TestParsingTheGeometry:
    def test_arcgis_gives_x_y_and_it_is_flipped_once(self):
        """Longitude first. Reading it as lat/lon would put Coronado in the
        Indian Ocean, so the flip happens on the way in and nowhere else."""

        payload = {"features": [{"geometry": {"paths": [[
            [-117.1866, 32.6828], [-117.1841, 32.6814],
        ]]}}]}
        got = mod.parse_paths(payload)
        assert got == [[(32.6828, -117.1866), (32.6814, -117.1841)]]

    def test_a_one_point_path_is_not_a_line(self):
        payload = {"features": [{"geometry": {"paths": [[[-117.18, 32.68]]]}}]}
        assert mod.parse_paths(payload) == []

    def test_a_malformed_vertex_is_skipped_not_zero_filled(self):
        payload = {"features": [{"geometry": {"paths": [[
            [-117.18, 32.68], [None], [-117.17, 32.67],
        ]]}}]}
        assert len(mod.parse_paths(payload)[0]) == 2

    def test_an_error_in_a_200_body_is_caught(self, monkeypatch):
        """ArcGIS reports failure inside a 200, the same shape CO-OPS does."""

        body = json.dumps({"error": {"message": "Invalid or missing input"}}).encode()

        class FakeResponse:
            headers = {"Content-Encoding": ""}
            def read(self): return body
            def __enter__(self): return self
            def __exit__(self, *a): return False

        monkeypatch.setattr(mod.urllib.request, "urlopen", lambda *a, **k: FakeResponse())
        with pytest.raises(mod.ShorelineError, match="200 body"):
            mod.fetch_json("https://example.test")

    def test_vertices_outside_the_bbox_are_dropped(self):
        assert mod.in_bbox(32.68, -117.18, mod.BBOX)
        assert not mod.in_bbox(32.90, -117.18, mod.BBOX)   # up the coast
        assert not mod.in_bbox(32.68, -117.05, mod.BBOX)   # inland

    def test_the_bbox_covers_every_digitised_break_with_room(self):
        """A fit at the kilometre scale needs vertices past both ends of the
        beach, not up to them."""

        import json as _json
        spots = _json.load(open("forecast/spots.json"))
        pts = [p for s in spots["spots"] if s["id"].startswith("coronado")
               for p in s["shoreline"]]
        xmin, ymin, xmax, ymax = mod.BBOX
        for lat, lon in pts:
            assert xmin < lon < xmax and ymin < lat < ymax
        # Roughly 2 km of margin on the along-shore axis.
        assert min(p[0] for p in pts) - ymin > 0.015
        assert ymax - max(p[0] for p in pts) > 0.015


class TestStoring:
    def test_vertices_round_trip_through_the_csv(self, tmp_path):
        parts = [[(32.6828, -117.1866), (32.6814, -117.1841)]]
        path = mod.store(parts, "layer/0", tmp_path)
        rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
        assert [r["lat"] for r in rows] == ["32.6828000", "32.6814000"]
        assert {r["source_layer"] for r in rows} == {"layer/0"}

    def test_the_layer_it_came_from_is_recorded_on_every_row(self, tmp_path):
        """A survey with no provenance is a number someone typed."""

        path = mod.store([[(32.68, -117.18), (32.67, -117.17)]], "svc/2", tmp_path)
        rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
        assert all(r["source_layer"] and r["fetched_utc"] for r in rows)

    def test_parts_stay_separate(self, tmp_path):
        """Two disjoint shoreline segments must not be joined into one line —
        the fit would run straight across the gap between them."""

        path = mod.store([[(32.68, -117.18), (32.67, -117.17)],
                          [(32.60, -117.13), (32.59, -117.12)]], "svc/2", tmp_path)
        rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
        assert {r["part"] for r in rows} == {"0", "1"}


class TestTheSummaryIsHonestWhenItFindsNothing:
    def test_nothing_found_claims_nothing(self):
        text = mod.format_summary(mod.Result())
        assert "No shoreline layer found" in text
        assert "nothing is inferred" in text.lower()

    def test_it_points_at_the_analysis_when_it_succeeds(self, tmp_path):
        got = mod.Result(layer="svc/0", parts=1, vertices=42,
                         stored=tmp_path / "x.csv")
        assert "forecast.shorenormal" in mod.format_summary(got)


class TestItMatchesLayerNamesNotOnlyServiceNames:
    """The second probe run walked NOAA's chart catalogue and reported nothing,
    because it filtered at the SERVICE level. NOAA's ENC chart services are
    called things like `NOAACharts`, and the coastline lives inside them as a
    feature class named COALNE."""

    def test_the_pattern_knows_what_a_coastline_is_called(self):
        for name in ("COALNE", "Coastline", "coast_line", "MHW", "CUSP_shoreline"):
            assert mod.WANTED.search(name), name

    def test_shoreline_named_layers_are_tried_first(self, monkeypatch):
        monkeypatch.setattr(mod, "fetch_json", lambda url, **k: {"layers": [
            {"id": 0, "name": "Depth Areas", "geometryType": "esriGeometryPolyline"},
            {"id": 1, "name": "COALNE", "geometryType": "esriGeometryPolyline"},
        ]})
        got = mod.line_layers("https://example.test/svc/MapServer")
        assert got[0].endswith("/1"), got

    def test_polygon_layers_are_not_offered_as_lines(self, monkeypatch):
        monkeypatch.setattr(mod, "fetch_json", lambda url, **k: {"layers": [
            {"id": 0, "name": "COALNE", "geometryType": "esriGeometryPolygon"},
        ]})
        assert mod.line_layers("https://example.test/svc/MapServer") == []

    def test_a_chart_service_is_not_crawled_end_to_end(self, monkeypatch):
        """Dozens of unnamed layers is a crawl, not a probe."""

        monkeypatch.setattr(mod, "fetch_json", lambda url, **k: {"layers": [
            {"id": i, "name": f"Layer {i}", "geometryType": "esriGeometryPolyline"}
            for i in range(40)
        ]})
        assert len(mod.line_layers("https://example.test/svc/MapServer")) <= 8

    def test_the_observed_services_are_tried_whatever_they_are_called(self):
        """These came out of a real catalogue walk on 2026-09-20, not a guess,
        and none of them would pass a name filter."""

        assert mod.KNOWN_SERVICES
        for url in mod.KNOWN_SERVICES:
            assert url.endswith("/MapServer") and "charttools.noaa.gov" in url

    def test_one_catalogue_cannot_bury_the_others(self):
        """4,060 services from one root pushed the other three out of the
        summary entirely in the second run."""

        attempt = mod.Attempt(url="https://example.test", ok=True,
                              listing=[f"svc{i} (MapServer)" for i in range(500)])
        text = mod.format_summary(mod.Result(attempts=[attempt]))
        assert f"…and {500 - mod.LISTING_CAP} more" in text


class TestContentEncoding:
    """coast.noaa.gov serves gzip whether or not it was asked for, and urllib
    does not decompress on its own. Three probe runs read that as "not JSON"
    and wrote off the Digital Coast host — the likeliest home of a surveyed
    shoreline. Caught only because the summary began sampling bodies it could
    not parse, and the sample started with the gzip magic number."""

    RAW = b'{"services": []}'

    def test_gzip_is_undone_by_its_magic_number(self):
        import gzip
        assert mod.decompress(gzip.compress(self.RAW)) == self.RAW

    def test_gzip_is_undone_by_the_header_too(self):
        """Header AND magic number, because the header is what the server says
        and the magic number is what it did, and those can disagree."""

        import gzip
        assert mod.decompress(gzip.compress(self.RAW), "gzip") == self.RAW

    def test_deflate_is_undone_raw_or_wrapped(self):
        import zlib
        assert mod.decompress(zlib.compress(self.RAW), "deflate") == self.RAW
        assert mod.decompress(zlib.compress(self.RAW)[2:-4], "deflate") == self.RAW

    def test_an_uncompressed_body_passes_through(self):
        assert mod.decompress(self.RAW) == self.RAW
        assert mod.decompress(self.RAW, "identity") == self.RAW

    def test_a_truncated_body_is_returned_not_raised(self):
        """A truncated gzip raises EOFError, which is NOT an OSError — the
        first version caught only OSError and would have crashed. That would
        turn "the response was cut short" into "the host is dead", which is
        the exact distinction this module exists to make."""

        import gzip
        broken = gzip.compress(self.RAW)[:6]
        assert mod.decompress(broken) == broken

    def test_a_body_that_merely_starts_like_gzip_survives(self):
        assert mod.decompress(b"\x1f\x8bnope") == b"\x1f\x8bnope"

    def test_the_request_asks_for_what_it_can_undo(self):
        source = Path("collector/shoreline.py").read_text(encoding="utf-8")
        assert "Accept-Encoding" in source and "gzip, deflate" in source


class TestTheFolderBudgetCoversTheCatalogue:
    def test_the_survey_office_is_opened_before_the_alphabet_runs_out(self):
        """charttools carries 22 folders. The budget was 12, sorted
        alphabetically among non-matching names, so `NGS/` — the National
        Geodetic Survey, the office that publishes the US shoreline — was
        never opened."""

        assert mod.FOLDER_BUDGET >= 22
        for name in ("NGS", "encdirect", "Hydrographic_Services"):
            assert mod.PRIORITY_FOLDERS.search(name), name

    def test_priority_folders_sort_ahead_of_ordinary_ones(self, monkeypatch):
        opened = []

        def fake(url, **k):
            if url.endswith("services?f=json"):
                return {"services": [], "folders": ["AAA", "NGS", "ZZZ"]}
            opened.append(url)
            return {"services": []}

        monkeypatch.setattr(mod, "fetch_json", fake)
        mod.discover(("https://example.test/arcgis/rest/services",))
        assert "NGS" in opened[0], opened

    def test_a_priority_folder_offers_its_services_whatever_they_are_called(self, monkeypatch):
        """The coastline inside an NGS or ENC service is not going to be in
        the service's name."""

        def fake(url, **k):
            if url.endswith("services?f=json"):
                return {"services": [], "folders": ["NGS"]}
            return {"services": [{"name": "NGS/Anything", "type": "MapServer"}]}

        monkeypatch.setattr(mod, "fetch_json", fake)
        got = mod.discover(("https://example.test/arcgis/rest/services",))
        assert any("Anything" in c for c in got.candidates), got.candidates


class TestTheFileTreeProbe:
    """coast.noaa.gov's REST catalogue carries 374 entries across 16 folders
    and not one matches a shoreline pattern (measured 2026-09-20). Digital
    Coast serves its bulk products as files under /htdata/, so if CUSP is
    reachable at all it is a download and not a service."""

    INDEX = ('<html><body>'
             '<a href="../">Parent Directory</a>'
             '<a href="CUSP/">CUSP/</a>'
             '<a href="NGS_MHW/">NGS_MHW/</a>'
             '<a href="readme.txt">readme.txt</a>'
             '<a href="/elsewhere">elsewhere</a>'
             '<a href="?C=N;O=D">sort</a>'
             '</body></html>')

    def test_it_lists_what_is_there(self, monkeypatch):
        monkeypatch.setattr(mod, "fetch_text", lambda url, **k: self.INDEX)
        assert mod.list_directory("https://example.test/htdata/") == [
            "CUSP/", "NGS_MHW/", "readme.txt"]

    def test_navigation_chrome_is_not_a_listing_entry(self, monkeypatch):
        """Parent links, absolute paths and column-sort links are the page,
        not its contents."""

        monkeypatch.setattr(mod, "fetch_text", lambda url, **k: self.INDEX)
        got = mod.list_directory("https://example.test/htdata/")
        for chrome in ("../", "/elsewhere", "?C=N;O=D"):
            assert chrome not in got

    def test_a_shoreline_name_is_called_out_in_the_note(self, monkeypatch):
        monkeypatch.setattr(mod, "fetch_text", lambda url, **k: self.INDEX)
        got = mod.probe_htdata(("https://example.test/htdata/",))
        assert got[0].ok and "CUSP/" in got[0].note

    def test_a_denial_is_classified_not_swallowed(self, monkeypatch):
        def boom(url, **k):
            raise OSError("gateway answered 403 to CONNECT")
        monkeypatch.setattr(mod, "fetch_text", boom)
        got = mod.probe_htdata(("https://example.test/htdata/",))
        assert got[0].denied and not got[0].ok

    def test_a_missing_directory_is_reported_not_fatal(self, monkeypatch):
        def missing(url, **k):
            raise urllib_error_404()
        import urllib.error
        def urllib_error_404():
            return urllib.error.HTTPError("u", 404, "Not Found", {}, None)
        monkeypatch.setattr(mod, "fetch_text", missing)
        got = mod.probe_htdata(("https://example.test/htdata/",))
        assert not got[0].ok and "404" in got[0].note

    def test_it_reports_beside_the_services_rather_than_instead_of_them(self):
        """One run answers both questions. The file tree must not
        short-circuit the service walk or a future CUSP service is invisible."""

        import inspect
        source = inspect.getsource(mod.collect)
        assert "probe_htdata()" in source
        assert source.index("probe_htdata()") < source.index("for service in result.candidates")

    def test_no_filename_is_assumed(self):
        """The rule this module was built around: report what is there, never
        guess a deep path and believe the answer."""

        for root in mod.HTDATA_ROOTS:
            assert root.endswith("/"), root
            assert "." not in root.rsplit("/", 2)[-2], root
