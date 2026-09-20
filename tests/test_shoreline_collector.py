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


class TestA403MeansTwoDifferentThings:
    """From a Claude session a 403 is the proxy refusing CONNECT and the host
    may be perfectly fine. From an Actions runner there is no such proxy, so a
    403 is the origin refusing — measured 2026-09-20, coast.noaa.gov/htdata/
    answers 403 to a runner because directory listing is switched off.

    Conflating them files "this directory is not browsable" under "we could not
    reach this host", which is the same class of fault as reading NCEP's 404 as
    "no cycle today"."""

    def test_an_http_status_is_never_an_egress_denial(self):
        import urllib.error
        for code in (401, 403, 404, 500):
            exc = urllib.error.HTTPError("u", code, "no", {}, None)
            assert not mod.is_denial(exc), code

    def test_a_refused_tunnel_still_is(self):
        assert mod.is_denial(OSError("gateway answered 403 to CONNECT"))
        import urllib.error
        assert mod.is_denial(urllib.error.URLError("unreachable"))

    def test_the_summary_does_not_cry_denial_over_a_server_403(self):
        import urllib.error
        attempt = mod.Attempt(url="https://example.test/htdata/")
        exc = urllib.error.HTTPError("u", 403, "Forbidden", {}, None)
        attempt.denied = mod.is_denial(exc)
        attempt.note = f"{exc.__class__.__name__}: {exc}"[:160]
        text = mod.format_summary(mod.Result(attempts=[attempt]))
        assert "Denied at CONNECT" not in text
        assert "403" in text


class TestChartScaleIsARanking:
    """ENC usage bands are a documented quality ordering. The first version of
    this collector ignored them: it took whichever coastline layer answered
    first and never asked whether a better one existed. Measured (BRIEFING
    §22), enc_harbour/84 carries 97 features in the Coronado box where
    enc_approach/88 carries 61 — and §21 fitted the 61."""

    def test_harbour_outranks_approach_outranks_general(self):
        rank = mod.scale_of
        harbour = "https://x/services/encdirect/enc_harbour/MapServer/84"
        approach = "https://x/services/encdirect/enc_approach/MapServer/88"
        general = "https://x/services/encdirect/enc_general/MapServer/58"
        assert rank(harbour) > rank(approach) > rank(general)

    def test_an_unbanded_service_does_not_outrank_a_banded_one(self):
        assert mod.scale_of("https://x/services/MCS/ENCOnline/MapServer") == 0
        assert mod.scale_of("https://x/services/encdirect/enc_coastal/MapServer") > 0

    def test_candidates_are_sorted_finest_first(self):
        import inspect
        source = inspect.getsource(mod.collect)
        assert "sort(key=lambda url: -scale_of(url))" in source
        assert source.index("sort(key") < source.index("for service in result.candidates")


class TestOneFilePerSource:
    """A single fixed filename made comparison impossible: the finer fetch
    would overwrite the coarser one and the disagreement would never show."""

    def test_the_name_carries_the_band_and_the_layer(self):
        assert mod.store_name(
            "https://x/services/encdirect/enc_harbour/MapServer/84"
        ) == "enc_harbour_84_coronado.csv"

    def test_two_bands_do_not_collide(self):
        a = mod.store_name("https://x/services/encdirect/enc_harbour/MapServer/84")
        b = mod.store_name("https://x/services/encdirect/enc_approach/MapServer/88")
        assert a != b

    def test_storing_one_does_not_remove_the_other(self, tmp_path):
        pts = [[(32.68, -117.18), (32.67, -117.17)]]
        first = mod.store(pts, "https://x/services/encdirect/enc_approach/MapServer/88",
                          tmp_path)
        second = mod.store(pts, "https://x/services/encdirect/enc_harbour/MapServer/84",
                           tmp_path)
        assert first.exists() and second.exists() and first != second

    def test_the_same_source_twice_overwrites_itself(self, tmp_path):
        """A survey, not a series — re-fetching the same layer destroys
        nothing, and git is the version log."""

        pts = [[(32.68, -117.18), (32.67, -117.17)]]
        url = "https://x/services/encdirect/enc_harbour/MapServer/84"
        mod.store(pts, url, tmp_path)
        again = mod.store(pts, url, tmp_path)
        assert len(list((tmp_path / "shoreline").glob("*.csv"))) == 1
        assert again.exists()

    def test_more_than_one_source_is_kept(self):
        assert mod.SOURCE_BUDGET >= 2


class TestRegions:
    """A stored extract is clipped by its own envelope on every edge, and the
    filename is the only place that says which envelope. The three Coronado
    files sit on their bbox at all four corners: read without that, the fact
    that they stop 2.8 km south of the south break looks like the chart running
    out of coast, when it is only the query running out of box."""

    def test_the_region_is_in_the_filename(self):
        assert mod.store_name(
            "https://x/services/encdirect/enc_harbour/MapServer/84", "baja"
        ) == "enc_harbour_84_baja.csv"

    def test_the_same_layer_in_two_regions_does_not_collide(self):
        url = "https://x/services/encdirect/enc_harbour/MapServer/84"
        assert mod.store_name(url, "coronado") != mod.store_name(url, "baja")

    def test_the_default_region_keeps_the_existing_names(self):
        """The three files already in `data/shoreline/` are named this way and
        `forecast.shorenormal` reads them by that name."""

        assert mod.store_name(
            "https://x/services/encdirect/enc_harbour/MapServer/84"
        ).endswith("_coronado.csv")

    def test_baja_reaches_past_the_border(self):
        """The whole point of the region: NOAA's charts are the question, and a
        box that stops at 32.535 cannot answer it."""

        _, ymin, _, ymax = mod.REGIONS["baja"]
        assert ymin < 32.0 < ymax

    def test_baja_covers_the_tangent_stretch(self):
        """Measured from public landmark positions: the Baja coast from the
        Tijuana river mouth to Punta Eugenia sits inside 152-165 degrees from
        Coronado, and the seaward-most bearing comes from the near stretch
        between Playas de Tijuana and Rosarito. The box must contain it."""

        xmin, ymin, xmax, ymax = mod.REGIONS["baja"]
        for lat, lon in ((32.553, -117.130), (32.525, -117.124), (32.362, -117.060)):
            assert ymin <= lat <= ymax and xmin <= lon <= xmax

    def test_every_region_is_a_well_formed_box(self):
        for name, (xmin, ymin, xmax, ymax) in mod.REGIONS.items():
            assert xmin < xmax and ymin < ymax, name

    def test_the_summary_states_the_envelope(self):
        """Without it the vertex count is unreadable — 904 points is a dense
        coastline or a clipped one and the number alone does not say."""

        text = mod.format_summary(mod.Result(region="baja", bbox=mod.REGIONS["baja"]))
        assert "baja" in text
        assert "-117.4" in text and "31.6" in text


class TestTransferLimit:
    """The Coronado box returned 97 features and never met a page limit, so
    nothing here had ever seen one. A 130 km box will, and a silently truncated
    coastline drops exactly the seaward-most vertex the fetch exists to find —
    the same shape as the 404 that meant `bull_tar` and was read as `skipped`."""

    def paged(self, pages):
        seen = []

        def fetch(url):
            seen.append(url)
            return pages[len(seen) - 1]

        return fetch, seen

    def line(self, lat):
        return {"geometry": {"paths": [[[-117.1, lat], [-117.2, lat]]]}}

    def test_one_clean_page_asks_once(self):
        fetch, seen = self.paged([{"features": [self.line(32.6)]}])
        paths, truncated, _ = mod.fetch_paths("u", mod.BBOX, fetch=fetch)
        assert len(paths) == 1 and not truncated and len(seen) == 1

    def test_a_truncated_page_is_followed(self):
        fetch, seen = self.paged([
            {"features": [self.line(32.6)], "exceededTransferLimit": True},
            {"features": [self.line(32.5)]},
        ])
        paths, truncated, _ = mod.fetch_paths("u", mod.BBOX, fetch=fetch)
        assert len(paths) == 2 and not truncated
        assert "resultOffset=1" in seen[1]

    def test_the_first_page_does_not_send_an_offset(self):
        fetch, seen = self.paged([{"features": []}])
        mod.fetch_paths("u", mod.BBOX, fetch=fetch)
        assert "resultOffset" not in seen[0]

    def test_a_server_that_never_stops_is_bounded(self):
        page = {"features": [self.line(32.6)], "exceededTransferLimit": True}
        seen = []

        def fetch(url):
            seen.append(url)
            return page

        paths, truncated, _ = mod.fetch_paths("u", mod.BBOX, fetch=fetch)
        assert truncated
        assert len(seen) == mod.PAGE_BUDGET

    def test_an_empty_page_ends_it_even_when_the_flag_is_set(self):
        """Otherwise a server that sets the flag and returns nothing spins to
        the budget on every run."""

        page = {"features": [], "exceededTransferLimit": True}
        seen = []

        def fetch(url):
            seen.append(url)
            return page

        _, truncated, _ = mod.fetch_paths("u", mod.BBOX, fetch=fetch)
        assert len(seen) == 1 and not truncated

    def test_the_summary_says_the_coastline_is_incomplete(self):
        result = mod.Result(region="baja", bbox=mod.REGIONS["baja"])
        result.truncated.append("https://x/enc_coastal/MapServer/70")
        result.vertices, result.parts = 8000, 40
        text = mod.format_summary(result)
        assert "Incomplete" in text
        assert "enc_coastal" in text


class TestChartCells:
    """A usage band is a mosaic of chart cells, not a chart. "Digitised from
    the approach band" names the drawer; the cell names the chart, and that is
    what a provenance line on the app surface has to say."""

    def feature(self, attrs):
        return {"attributes": attrs,
                "geometry": {"paths": [[[-117.1, 32.6], [-117.2, 32.6]]]}}

    def test_a_named_cell_is_taken(self):
        assert mod.cell_of({"DSNM": "US5CA72M.000"}) == "US5CA72M.000"

    def test_the_field_name_is_matched_whatever_its_case(self):
        assert mod.cell_of({"dsnm": "US5CA72M.000"}) == "US5CA72M.000"

    def test_the_best_field_wins_when_several_are_present(self):
        got = mod.cell_of({"LNAM": "xyz", "DSNM": "US5CA72M.000"})
        assert got == "US5CA72M.000"

    def test_a_sorind_citation_gives_up_its_cell(self):
        """S-57 SORIND is a comma-joined citation: agency, source, method,
        id. The second field is the chart."""

        assert mod.cell_of({"SORIND": "US,US,graph,US4CA11M"}) == "US4CA11M"

    def test_no_cell_field_is_an_empty_string_not_a_guess(self):
        assert mod.cell_of({"OBJNAM": "COASTLINE"}) == ""
        assert mod.cell_of({}) == ""

    def test_an_empty_value_does_not_count_as_a_cell(self):
        assert mod.cell_of({"DSNM": ""}) == ""
        assert mod.cell_of({"DSNM": None}) == ""

    def test_the_cell_rides_with_the_geometry(self):
        payload = {"features": [self.feature({"DSNM": "US5CA72M.000"})]}
        (points, cell), = mod.parse_features(payload)
        assert cell == "US5CA72M.000" and len(points) == 2

    def test_parse_paths_still_returns_bare_geometry(self):
        payload = {"features": [self.feature({"DSNM": "US5CA72M.000"})]}
        assert mod.parse_paths(payload) == [[(32.6, -117.1), (32.6, -117.2)]]

    def test_the_stored_file_carries_the_cell(self, tmp_path):
        path = mod.store([([(32.68, -117.18), (32.67, -117.17)], "US5CA72M.000")],
                         "https://x/services/encdirect/enc_harbour/MapServer/84",
                         tmp_path, "coronado")
        rows = list(csv.DictReader(path.open()))
        assert all(r["cell"] == "US5CA72M.000" for r in rows)

    def test_a_part_with_no_cell_still_stores(self, tmp_path):
        """The column is an addition to what a part carries, not a change of
        what a part IS — the older call shape has to keep working."""

        path = mod.store([[(32.68, -117.18), (32.67, -117.17)]],
                         "https://x/services/encdirect/enc_harbour/MapServer/84",
                         tmp_path, "coronado")
        rows = list(csv.DictReader(path.open()))
        assert all(r["cell"] == "" for r in rows)

    def test_the_summary_names_the_cells(self):
        result = mod.Result(region="baja", bbox=mod.REGIONS["baja"])
        result.cells = ["US4CA11M", "US3CA52M"]
        result.vertices, result.parts = 10, 2
        text = mod.format_summary(result)
        assert "US4CA11M" in text and "US3CA52M" in text

    def test_an_absent_cell_attribute_lists_what_was_there_instead(self):
        """A blank column with no explanation is the fault this repository
        keeps paying for: a probe that reports only its own matches says
        nothing at all when there are none."""

        result = mod.Result(region="baja", bbox=mod.REGIONS["baja"])
        result.attribute_keys = ["OBJECTID", "OBJNAM", "SCAMIN"]
        text = mod.format_summary(result)
        assert "No ENC cell attribute" in text
        assert "OBJNAM" in text
