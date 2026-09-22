"""Reading a blocker's edges off a charted coastline.

The two coordinates per blocker in `forecast/spots.json` are the whole claim
a window stands on, and two of the three blockers had never been near a chart:
the Coronado Islands were an estimate, and the Baja mainland was absent, which
is why every Coronado window's southern edge is currently the seaward
half-plane rather than land.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from forecast import blockeredge as mod
from forecast.geometry import load

SPOTS, BLOCKERS = load()
BY_ID = {s.id: s for s in SPOTS}
REAL = Path(__file__).resolve().parent.parent / "data" / "shoreline"


def write(path: Path, points):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["part", "seq", "lat", "lon",
                                           "source_layer", "fetched_utc"])
        w.writeheader()
        for i, (lat, lon) in enumerate(points):
            w.writerow({"part": 0, "seq": i, "lat": lat, "lon": lon,
                        "source_layer": "x", "fetched_utc": "2026-09-20T00:00:00Z"})


class TestEdges:
    def test_two_points_give_the_low_and_the_high(self):
        spot = BY_ID["coronado_south"]
        got = mod.edges(spot, [(32.45, -117.30), (32.40, -117.24)])
        assert got is not None
        low, high = got
        assert low.bearing_deg < high.bearing_deg

    def test_one_point_is_not_an_edge_pair(self):
        assert mod.edges(BY_ID["coronado_south"], [(32.45, -117.30)]) is None

    def test_the_range_is_the_distance_to_the_vertex(self):
        spot = BY_ID["coronado_south"]
        low, high = mod.edges(spot, [(32.45, -117.30), (32.40, -117.24)])
        assert 25.0 < low.range_km < 35.0 and 25.0 < high.range_km < 35.0

    def test_a_far_edge_is_less_sensitive_than_a_near_one(self):
        """Why the Baja tangent is a softer problem than the Point Loma tip:
        the same 100 m of error is divided by the range."""

        near = mod.Edge(bearing_deg=0.0, vertex=(0.0, 0.0), range_km=5.0)
        far = mod.Edge(bearing_deg=0.0, vertex=(0.0, 0.0), range_km=23.0)
        assert far.moves_by(100.0) < near.moves_by(100.0)
        assert round(far.moves_by(100.0), 2) == 0.25


class TestDataLimitAlarm:
    """A maximum at the southern end of the extract is the chart running out,
    not the coast turning away. Getting this backwards would publish a window
    edge that is really the query envelope."""

    def test_it_fires_when_a_continuing_coast_peaks_at_the_data_edge(self):
        spot = BY_ID["coronado_south"]
        # A coast still turning toward due south where the vertices stop, so
        # its bearing from the beach is still rising at the last one.
        pts = [(32.50, -117.12), (32.45, -117.13), (32.40, -117.14)]
        _, high = mod.edges(spot, pts, continues=True)
        assert high.vertex == (32.40, -117.14)
        assert high.at_data_limit

    def test_it_stays_quiet_when_the_coast_turns_away_inside_the_data(self):
        """Which is what the real Baja extract does: the maximum sits 9.6 km
        north of the last charted vertex."""

        spot = BY_ID["coronado_south"]
        pts = [(32.50, -117.12), (32.45, -117.13), (32.40, -117.06)]
        _, high = mod.edges(spot, pts, continues=True)
        assert high.vertex == (32.45, -117.13)
        assert not high.at_data_limit

    def test_an_island_never_raises_it(self):
        """An island's southern tip IS the southern end of the feature. The
        first version flagged the Coronado Islands on exactly this, which is
        an alarm firing on the geometry it exists to exonerate."""

        spot = BY_ID["coronado_south"]
        pts = [(32.44, -117.30), (32.39, -117.24), (32.42, -117.27)]
        low, high = mod.edges(spot, pts, continues=False)
        assert not low.at_data_limit and not high.at_data_limit


class TestFeatures:
    def test_no_vertex_belongs_to_two_features(self):
        keeps = [spec["keep"] for spec in mod.FEATURES.values()]
        for lat in (32.39, 32.42, 32.43, 32.45, 32.48, 32.52, 32.60):
            for lon in (-117.31, -117.25, -117.20, -117.19, -117.10):
                assert sum(1 for k in keeps if k(lat, lon)) <= 1, (lat, lon)

    def test_the_two_islands_split_where_the_channel_is(self):
        south = mod.FEATURES["Coronado Islands (south group)"]["keep"]
        north = mod.FEATURES["Coronado Islands (north)"]["keep"]
        assert south(32.42, -117.26) and not north(32.42, -117.26)
        assert north(32.44, -117.30) and not south(32.44, -117.30)

    def test_the_mainland_stops_at_the_border(self):
        """Otherwise the Silver Strand and San Diego Bay are counted as the
        Baja coast, and the reported width is redundancy, not a measurement."""

        main = mod.FEATURES["Baja mainland"]["keep"]
        assert main(32.45, -117.10)
        assert not main(32.60, -117.13)

    def test_point_loma_stops_at_the_channel(self):
        """North Island is the far side of the harbour entrance. Counted as
        Point Loma it could not lower the edge from Coronado - it bears higher
        than the tip - but a drawing of 'the vertices the model uses' would
        then show land the model never meant."""

        loma = mod.FEATURES["Point Loma peninsula"]["keep"]
        assert loma(32.665, -117.243)           # the tip
        assert loma(32.686, -117.2335)          # Ballast Point
        assert not loma(32.688, -117.2175)      # Zuniga Point, North Island
        assert not loma(32.44, -117.30)         # the northern island

    def test_point_loma_claims_only_its_low_edge(self):
        """The peninsula continues north; its high side is the half-plane."""

        assert mod.FEATURES["Point Loma peninsula"]["edge"] == "low"

    def test_only_the_mainland_continues(self):
        assert mod.FEATURES["Baja mainland"]["continues"]
        for name in mod.FEATURES:
            if "Islands" in name:
                assert not mod.FEATURES[name]["continues"]

    def test_a_continuing_feature_reports_one_edge(self):
        assert mod.FEATURES["Baja mainland"]["edge"] == "high"
        for name in mod.FEATURES:
            if "Islands" in name:
                assert mod.FEATURES[name]["edge"] == "both"

    def test_every_feature_names_a_blocker_in_the_spot_file(self):
        """Otherwise the 'vs spots.json' column silently reads 'not in
        spots.json' for a blocker that IS there under another name, which is
        what happened the moment the islands were split in two."""

        names = {b.name for b in BLOCKERS}
        assert set(mod.FEATURES) <= names


class TestReport:
    def test_no_extract_is_not_a_finding(self, tmp_path):
        text = mod.format_report(mod.report(tmp_path))
        assert "Nothing is inferred from the" in text

    def test_it_never_edits_the_spot_file(self, tmp_path):
        before = (Path(__file__).resolve().parent.parent
                  / "forecast" / "spots.json").read_bytes()
        mod.report(tmp_path)
        after = (Path(__file__).resolve().parent.parent
                 / "forecast" / "spots.json").read_bytes()
        assert before == after

    def test_a_continuing_feature_prints_no_width(self, tmp_path):
        write(tmp_path / "shoreline" / "enc_coastal_70_baja.csv",
              [(32.50, -117.12), (32.47, -117.124), (32.40, -117.09)])
        rows = mod.report(tmp_path)
        main = [r for r in rows if r.feature == "Baja mainland"]
        assert main and all(r.width_deg is None for r in main)


@pytest.mark.skipif(not (REAL / "enc_approach_88_baja.csv").exists(),
                    reason="the Baja extract has not been collected")
class TestAgainstTheStoredExtract:
    """Measured 2026-09-20 on the extract NOAA's ENC actually served."""

    def rows(self, feature, source):
        got = mod.report()
        return {r.spot_id: r for r in got
                if r.feature == feature and r.source == source}

    def test_the_mainland_tangent_is_not_at_the_data_edge(self):
        """The whole result depends on this. If it fired, the number would be
        a floor rather than a tangent and no window could be widened."""

        for row in self.rows("Baja mainland", "enc_approach_88_baja").values():
            assert row.high is not None and not row.high.at_data_limit

    def test_two_chart_bands_agree_on_the_tangent(self):
        """0.18 degrees between independent bands, against the 18.6 the same
        two disagreed by at 1500 m on Coronado's own curve (BRIEFING 23).
        An edge-on tangent 23 km out is a far better conditioned measurement
        than a principal axis on a bending beach."""

        a = self.rows("Baja mainland", "enc_approach_88_baja")
        c = self.rows("Baja mainland", "enc_coastal_70_baja")
        for sid in ("coronado_north", "coronado_center", "coronado_south"):
            assert abs(a[sid].high.bearing_deg - c[sid].high.bearing_deg) < 0.3

    def test_the_tangent_falls_south_of_the_beach_and_north_of_rosarito(self):
        row = self.rows("Baja mainland", "enc_approach_88_baja")["coronado_south"]
        assert 32.40 < row.high.vertex[0] < 32.53
        assert 20.0 < row.high.range_km < 30.0

    def test_all_three_breaks_take_the_tangent_from_one_vertex(self):
        """A far tangent is the same physical headland for every break; the
        13.5 degrees of spread along Coronado's sand comes from the Point Loma
        end of the window, not this one."""

        rows = self.rows("Baja mainland", "enc_approach_88_baja")
        seen = {rows[s].high.vertex for s in
                ("coronado_north", "coronado_center", "coronado_south")}
        assert len(seen) == 1

    @pytest.mark.parametrize("feature", ["Coronado Islands (south group)",
                                         "Coronado Islands (north)"])
    def test_spots_json_now_carries_what_the_chart_draws(self, feature):
        """The check this module exists to make. The estimate these replaced
        was good — both edges within 1.6 degrees — and systematically NARROW,
        which is what CLAUDE.md's 'a full kilometre costs under 2 degrees'
        predicts. What it was not was checkable."""

        rows = self.rows(feature, "enc_approach_88_baja")
        for sid in ("coronado_north", "coronado_center", "coronado_south"):
            low_move, high_move = rows[sid].moves
            assert abs(low_move) < 0.1 and abs(high_move) < 0.1

    @pytest.mark.parametrize("feature", ["Coronado Islands (south group)",
                                         "Coronado Islands (north)"])
    def test_two_bands_agree_on_the_islands_too(self, feature):
        a = self.rows(feature, "enc_approach_88_baja")
        c = self.rows(feature, "enc_coastal_70_baja")
        for sid in ("coronado_north", "coronado_center", "coronado_south"):
            assert abs(a[sid].low.bearing_deg - c[sid].low.bearing_deg) < 0.3
            assert abs(a[sid].high.bearing_deg - c[sid].high.bearing_deg) < 0.3

    def test_the_channel_between_the_two_islands_is_six_degrees(self):
        """The measurement that made splitting them necessary. As one screen
        the group claimed 13.5 degrees of solid land and a Fresnel number of
        about 7 at 15 s; split, it is two islands at 1.6 and 0.2 with 6.1
        degrees of water between them. The one-screen reading silenced the
        diffraction flag, which is the binary-blocker error at one scale up."""

        south = self.rows("Coronado Islands (south group)", "enc_approach_88_baja")
        north = self.rows("Coronado Islands (north)", "enc_approach_88_baja")
        for sid in ("coronado_north", "coronado_center", "coronado_south"):
            gap = north[sid].low.bearing_deg - south[sid].high.bearing_deg
            assert 5.9 < gap < 6.4


@pytest.mark.skipif(not (REAL / "enc_approach_88_point_loma.csv").exists(),
                    reason="the Point Loma extract has not been collected")
class TestPointLomaAgainstTheStoredExtract:
    """Measured 2026-09-22 on the extract NOAA's ENC actually served."""

    CORONADO = ("coronado_north", "coronado_center", "coronado_south")

    def rows(self, source):
        return {r.spot_id: r for r in mod.report()
                if r.feature == "Point Loma peninsula" and r.source == source}

    def test_spots_json_now_carries_what_the_chart_draws(self):
        """The outline in spots.json is a hull of the approach extract, so it
        must reproduce the extract's own tangent at every spot exactly."""

        for sid, row in self.rows("enc_approach_88_point_loma").items():
            assert abs(row.moves[0]) < 0.01, sid

    def test_two_chart_bands_agree_on_the_tip(self):
        a = self.rows("enc_approach_88_point_loma")
        c = self.rows("enc_coastal_70_point_loma")
        for sid in self.CORONADO:
            assert abs(a[sid].low.bearing_deg - c[sid].low.bearing_deg) < 0.3

    def test_the_breaks_see_three_different_vertices(self):
        rows = self.rows("enc_approach_88_point_loma")
        assert len({rows[s].low.vertex for s in self.CORONADO}) == 3

    def test_the_harbour_band_has_a_hole_at_the_tip(self):
        """Why the finer band is NOT the one used. Its coastline stops 336 m
        short across the tip, and its south-break tangent sits on that line
        end - an edge formed by missing data, reading 0.17 degrees wide. If
        this ever fails, NOAA has filled the hole and the harbour band should
        be reconsidered."""

        import csv
        from collections import defaultdict
        from forecast.swell import great_circle_km

        parts = defaultdict(list)
        with (REAL / "enc_harbour_84_point_loma.csv").open() as fh:
            for r in csv.DictReader(fh):
                parts[r["part"]].append((float(r["lat"]), float(r["lon"])))
        ends = [(k, p) for k, v in parts.items() for p in (v[0], v[-1])]
        loose = [p for k, p in ends
                 if p[0] < 32.672 and p[1] < -117.23
                 and min(great_circle_km(p, q) for j, q in ends
                         if (j, q) != (k, p)) > 0.1]
        assert loose, "the harbour band's tip hole has closed"
