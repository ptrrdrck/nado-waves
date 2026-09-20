"""Enumerating what NOAA's ENC chart services carry near the harbour entrance.

`collector.shoreline` found the coastline and stopped, because a coastline was
all it asked for. Zuniga Jetty is a rubble mound awash for much of its length,
so it is not on any shoreline product — it is S-57 class SLCONS on a chart.
Zuniga Shoals is submerged and has no shoreline at all.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from collector import enc_layers as mod


def layer(name, **kw):
    return mod.Layer(service=kw.pop("service", "enc_approach"),
                     id=kw.pop("id", 0), name=name,
                     geometry=kw.pop("geometry", "Polyline"), **kw)


class TestTheBoxCoversWhatItIsFor:
    """`collector.shoreline.BBOX` was drawn around Coronado's sand. Measured,
    three of the five geometries still to be dialled in fall outside it."""

    TARGETS = {
        "Point Loma tip": (32.6648144, -117.2427037),
        "Zuniga jetty root": (32.6860, -117.2260),
        "Coronado north break": (32.6866337, -117.1975652),
        "Coronado south break": (32.6737318, -117.1723572),
        "Imperial Beach": (32.5790, -117.1350),
    }

    def test_every_harbour_entrance_target_is_inside(self):
        xmin, ymin, xmax, ymax = mod.BBOX
        for name, (lat, lon) in self.TARGETS.items():
            if name == "Imperial Beach":
                continue        # south of the box on purpose; see below
            assert xmin <= lon <= xmax, name
            assert ymin <= lat <= ymax, name

    def test_it_is_wider_than_the_beach_box(self):
        """The control: if this box were the shoreline one, the test above
        would pass for the breaks and silently miss the tip."""

        from collector.shoreline import BBOX as BEACH
        tip_lat, tip_lon = self.TARGETS["Point Loma tip"]
        assert not (BEACH[0] <= tip_lon <= BEACH[2]), "beach box grew; re-check"
        assert mod.BBOX[0] <= tip_lon <= mod.BBOX[2]

    def test_the_point_loma_tip_in_spots_json_is_covered(self):
        """It is the highest-leverage coordinate in the repository — 100 m of
        error there moves every west edge about a degree."""

        import json
        blockers = json.load(open("forecast/spots.json"))["blockers"]
        tip = next(b for b in blockers if "Point Loma" in b["name"])["a"]
        xmin, ymin, xmax, ymax = mod.BBOX
        assert xmin <= tip[1] <= xmax and ymin <= tip[0] <= ymax


class TestClassDetection:
    def test_it_finds_the_acronym_inside_a_longer_name(self):
        assert layer("SLCONS_Shoreline_Construction").klass == "SLCONS"
        assert layer("Depth Contour (DEPCNT)").klass == "DEPCNT"

    def test_case_does_not_matter(self):
        assert layer("slcons_line").klass == "SLCONS"

    def test_navigation_furniture_is_not_interesting(self):
        for name in ("Buoy Lateral", "Light", "Pilot Boarding", "Anchorage"):
            assert layer(name).klass == "", name

    def test_the_classes_asked_about_cover_the_three_open_geometries(self):
        """Jetty, shoals, island silhouettes — the reason this exists."""

        assert "SLCONS" in mod.WANTED_CLASSES     # Zuniga Jetty
        assert "DEPCNT" in mod.WANTED_CLASSES     # Zuniga Shoals
        assert "DEPARE" in mod.WANTED_CLASSES
        assert "LNDARE" in mod.WANTED_CLASSES     # islands


class TestCountingRatherThanFetching:
    def test_it_asks_for_a_count_not_geometry(self):
        """A fraction of the payload, and the whole question at this stage:
        does this layer have anything HERE."""

        url = mod.count_url("svc/0", mod.BBOX)
        assert "returnCountOnly=true" in url
        assert "returnGeometry=true" not in url
        assert "outFields" not in url

    def test_a_count_is_recorded(self, monkeypatch):
        monkeypatch.setattr(mod, "fetch_json", lambda url, **k: {"count": 7})
        got = layer("SLCONS", id=45)
        mod.count_features(got, "svc", mod.BBOX)
        assert got.count == 7 and not got.note

    def test_a_layer_that_refuses_is_reported_not_hidden(self, monkeypatch):
        """Layers 19 and 87 answered "Invalid or missing input parameters" on
        2026-09-20. A layer that cannot be queried and a layer that is empty
        are different facts."""

        def refuse(url, **k):
            raise mod.ShorelineError("ArcGIS error in a 200 body: Invalid")
        monkeypatch.setattr(mod, "fetch_json", refuse)
        got = layer("DEPCNT", id=19)
        mod.count_features(got, "svc", mod.BBOX)
        assert got.count is None and "Invalid" in got.note

    def test_a_missing_count_key_is_not_read_as_zero(self, monkeypatch):
        monkeypatch.setattr(mod, "fetch_json", lambda url, **k: {})
        got = layer("DEPARE")
        mod.count_features(got, "svc", mod.BBOX)
        assert got.count is None and got.note


class TestTheSurvey:
    def meta(self, names):
        return {"layers": [{"id": i, "name": n, "geometryType": "esriGeometryPolyline"}
                           for i, n in enumerate(names)]}

    def test_only_interesting_layers_are_queried(self, monkeypatch):
        """A chart service carries well over a hundred layers. This is a probe,
        not a crawl."""

        queried = []

        def fake(url, **k):
            if url.endswith("?f=json"):
                return self.meta(["Buoy", "SLCONS", "Light", "DEPCNT", "Beacon"])
            queried.append(url)
            return {"count": 3}

        monkeypatch.setattr(mod, "fetch_json", fake)
        got = mod.survey(("https://example.test/services/encdirect/x/MapServer",))
        assert len(got.layers) == 5
        assert len(queried) == 2, queried

    def test_the_budget_caps_the_queries(self, monkeypatch):
        def fake(url, **k):
            if url.endswith("?f=json"):
                return self.meta([f"SLCONS_{i}" for i in range(200)])
            return {"count": 1}

        monkeypatch.setattr(mod, "fetch_json", fake)
        got = mod.survey(("https://example.test/services/encdirect/x/MapServer",))
        assert len([l for l in got.layers if l.count is not None]) <= mod.QUERY_BUDGET

    def test_a_dead_service_does_not_stop_the_others(self, monkeypatch):
        calls = {"n": 0}

        def fake(url, **k):
            calls["n"] += 1
            if calls["n"] == 1:
                raise OSError("boom")
            if url.endswith("?f=json"):
                return self.meta(["SLCONS"])
            return {"count": 2}

        monkeypatch.setattr(mod, "fetch_json", fake)
        got = mod.survey(("https://a.test/services/encdirect/x/MapServer",
                          "https://b.test/services/encdirect/y/MapServer"))
        assert got.errors and got.layers

    def test_all_services_denied_is_reported_as_denial(self, monkeypatch):
        def boom(url, **k):
            raise OSError("gateway answered 403 to CONNECT")
        monkeypatch.setattr(mod, "fetch_json", boom)
        got = mod.survey(("https://a.test/services/encdirect/x/MapServer",))
        assert got.denied


class TestTheSummaryIsHonest:
    def test_nothing_enumerated_claims_nothing(self):
        text = mod.format_summary(mod.Result())
        assert "Nothing is inferred" in text

    def test_a_class_absent_from_the_box_is_said_so(self, monkeypatch):
        got = mod.Result(layers=[layer("SLCONS", count=4)])
        text = mod.format_summary(got)
        assert "not found in box" in text          # the ones with no features
        assert "SLCONS" in text

    def test_it_says_it_does_not_decide_anything(self):
        got = mod.Result(layers=[layer("SLCONS", count=4)])
        text = mod.format_summary(got)
        assert "stores nothing and edits nothing" in text
        assert "a shoal is not a blocker" in text

    def test_zero_is_distinguished_from_unqueryable(self):
        got = mod.Result(layers=[
            layer("SLCONS", id=1, count=0),
            layer("DEPCNT", id=2, note="Invalid"),
        ])
        text = mod.format_summary(got)
        assert "| 0 |" in text and "Invalid" in text


class TestItDoesNotWrite:
    def test_no_data_file_is_produced(self):
        source = Path("collector/enc_layers.py").read_text(encoding="utf-8")
        for writing in (".write_text(", '"w"', "'w'", "csv.DictWriter"):
            assert writing not in source, writing
