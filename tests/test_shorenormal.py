"""Fitting a shore normal to a surveyed shoreline.

The offshore/onshore/cross-shore reading on the app surface stands entirely on
each break's normal, and measured (BRIEFING §20) one degree of error there
changes the verdict on 4.2% of readings. So the fit that would replace a
hand-traced chord has to be shown to recover an orientation it was given,
before it is trusted to discover one it was not.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import pytest

from forecast.geometry import load
from forecast.shorenormal import (
    MIN_VERTICES, REPORT_SCALE_M, SCALES_M, fit_at, format_report,
    principal_axis, read_vertices, report,
)
from forecast.swell import destination_point

SPOTS, _ = load()
BY_ID = {s.id: s for s in SPOTS}


def straight(spot, trend_deg: float, *, n: int = 41, span_m: float = 2000.0,
             offset_m: float = 0.0, jitter_m: float = 0.0):
    """A synthetic shoreline through (or beside) a break at a known trend."""

    import random
    rng = random.Random(7)
    centre = spot.position
    if offset_m:
        centre = destination_point(centre, (trend_deg + 90.0) % 360.0, offset_m / 1000.0)
    out = []
    for i in range(n):
        along = (i / (n - 1) - 0.5) * span_m
        point = destination_point(centre, trend_deg, along / 1000.0)
        if jitter_m:
            point = destination_point(
                point, (trend_deg + 90.0) % 360.0,
                rng.uniform(-jitter_m, jitter_m) / 1000.0)
        out.append(point)
    return out


def walk(spot, base_trend: float, *, bend_after_m: float = 0.0,
         bend_deg_per_km: float = 0.0, span_m: float = 4000.0, step_m: float = 25.0):
    """A shoreline built by stepping along a bearing that may turn.

    Built incrementally rather than by offsetting from one origin, because a
    bearing that changes has to be integrated along the line — evaluating it
    against a fixed origin draws a fan, not a coast.
    """

    half = span_m / 2.0
    out = []
    for direction in (-1, 1):
        point = spot.position
        along = 0.0
        while along < half:
            out.append(point)
            bend = 0.0
            if bend_after_m and direction > 0 and along > bend_after_m:
                bend = bend_deg_per_km * (along - bend_after_m) / 1000.0
            heading = (base_trend + bend) % 360.0
            if direction < 0:
                heading = (heading + 180.0) % 360.0
            point = destination_point(point, heading, step_m / 1000.0)
            along += step_m
    return out


def write_store(tmp_path: Path, points) -> Path:
    path = tmp_path / "shoreline" / "noaa_shoreline_coronado.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["part", "seq", "lat", "lon",
                                           "source_layer", "fetched_utc"])
        w.writeheader()
        for seq, (lat, lon) in enumerate(points):
            w.writerow({"part": 0, "seq": seq, "lat": f"{lat:.7f}",
                        "lon": f"{lon:.7f}", "source_layer": "test",
                        "fetched_utc": "2026-09-20T00:00:00Z"})
    return path


class TestItRecoversAnOrientationItWasGiven:
    """The falsification test. A fit that cannot return a trend it was handed
    cannot be trusted with one it was not."""

    @pytest.mark.parametrize("trend", [0.0, 45.0, 102.8, 124.2, 131.5, 200.0, 315.0])
    def test_a_straight_shoreline_returns_its_own_normal(self, trend):
        spot = BY_ID["coronado_center"]
        fit = fit_at(straight(spot, trend), spot, 800.0)
        assert fit.normal_deg is not None, fit.note
        # Either normal is correct geometry; the resolved one must be the
        # seaward-side pick, so compare against both and require one.
        want = [(trend + 90.0) % 360.0, (trend - 90.0) % 360.0]
        off = min(abs(((fit.normal_deg - w + 180.0) % 360.0) - 180.0) for w in want)
        assert off < 0.5, f"trend {trend} -> normal {fit.normal_deg}"

    def test_a_north_south_beach_does_not_degenerate(self):
        """The control for using the principal axis instead of an ordinary
        y-on-x regression: OLS has infinite slope here and returns nonsense,
        while the principal axis has no preferred direction."""

        spot = BY_ID["coronado_center"]
        fit = fit_at(straight(spot, 0.0), spot, 800.0)
        assert fit.normal_deg is not None
        assert min(abs(((fit.normal_deg - w + 180.0) % 360.0) - 180.0)
                   for w in (90.0, 270.0)) < 0.5

    def test_the_resolved_normal_is_the_seaward_one(self):
        """An implicit sign once pointed Coronado into San Diego Bay."""

        spot = BY_ID["coronado_center"]
        fit = fit_at(straight(spot, spot.shore_bearing), spot, 800.0)
        assert abs(((fit.normal_deg - spot.normal + 180.0) % 360.0) - 180.0) < 0.5

    def test_a_straight_line_has_almost_no_residual(self):
        spot = BY_ID["coronado_center"]
        fit = fit_at(straight(spot, 124.0), spot, 800.0)
        assert fit.residual_m < 0.5

    def test_noise_raises_the_residual_without_moving_the_normal(self):
        """`residual_m` is what says whether the beach is straight at this
        scale, so it has to respond to scatter while the normal does not."""

        spot = BY_ID["coronado_center"]
        clean = fit_at(straight(spot, 124.0), spot, 800.0)
        noisy = fit_at(straight(spot, 124.0, jitter_m=8.0), spot, 800.0)
        assert noisy.residual_m > 3.0 > clean.residual_m
        assert abs(((noisy.normal_deg - clean.normal_deg + 180.0) % 360.0) - 180.0) < 3.0


class TestOrientationSurvivesATranslation:
    """NOAA's shoreline is referenced to a tidal datum; a traced waterline is
    not. The two sit at different cross-shore positions and that separation is
    not an error — but it must not leak into the angle."""

    def test_the_same_trend_offset_seaward_gives_the_same_normal(self):
        spot = BY_ID["coronado_center"]
        here = fit_at(straight(spot, 124.0), spot, 800.0)
        moved = fit_at(straight(spot, 124.0, offset_m=60.0), spot, 800.0)
        assert moved.normal_deg is not None
        assert abs(((moved.normal_deg - here.normal_deg + 180.0) % 360.0) - 180.0) < 0.5

    def test_the_offset_is_reported_rather_than_hidden(self):
        spot = BY_ID["coronado_center"]
        moved = fit_at(straight(spot, 124.0, offset_m=60.0), spot, 800.0)
        assert abs(abs(moved.offset_m) - 60.0) < 5.0


class TestTheNormalIsAPropertyOfAScale:
    def test_a_curved_shoreline_answers_differently_at_different_scales(self):
        """Not a failure of the fit — a fact about the beach, and the reason
        the report is a sweep instead of a number.

        The bend is on ONE side only. A window centred on the break samples
        symmetrically, so a constant-curvature arc averages to the same trend
        at every radius and would show nothing; it takes curvature that is not
        the same either side of the break to move the answer with scale. Real
        coasts are asymmetric that way — a straight stretch that hooks at one
        end — and the symmetric case is the control below."""

        spot = BY_ID["coronado_center"]
        points = walk(spot, 104.0, bend_after_m=500.0, bend_deg_per_km=60.0)
        near = fit_at(points, spot, 400.0)
        far = fit_at(points, spot, 3000.0)
        assert near.normal_deg is not None and far.normal_deg is not None
        assert abs(((far.normal_deg - near.normal_deg + 180.0) % 360.0) - 180.0) > 3.0
        # The residual is the louder signal of the two, and the one the report
        # leans on: a gently hooking beach moves its normal by a few degrees
        # while its straightness collapses by orders of magnitude.
        assert far.residual_m > 50.0 * max(near.residual_m, 1e-6)

    def test_a_straight_shoreline_answers_the_same_at_every_scale(self):
        """The control. Scale-dependence has to mean curvature, or it means
        nothing."""

        spot = BY_ID["coronado_center"]
        points = straight(spot, 124.0, n=201, span_m=6000.0)
        normals = [fit_at(points, spot, s).normal_deg for s in SCALES_M]
        assert all(n is not None for n in normals)
        assert max(normals) - min(normals) < 1.0


class TestItRefusesRatherThanGuesses:
    def test_too_few_vertices_yields_no_normal_and_says_why(self):
        spot = BY_ID["coronado_center"]
        fit = fit_at(straight(spot, 124.0, n=MIN_VERTICES - 1, span_m=50.0), spot, 200.0)
        assert fit.normal_deg is None and "vertices" in fit.note

    def test_an_empty_archive_yields_no_normals(self, tmp_path):
        got = report(tmp_path)
        assert len(got) == 3
        assert all(r.headline is None for r in got)

    def test_a_missing_file_reads_as_empty_not_an_error(self, tmp_path):
        assert read_vertices(tmp_path) == []

    def test_an_unparseable_row_is_skipped(self, tmp_path):
        path = write_store(tmp_path, [(32.68, -117.18), (32.69, -117.19)])
        with path.open("a", encoding="utf-8") as fh:
            fh.write("0,9,not-a-lat,not-a-lon,test,2026-09-20T00:00:00Z\n")
        assert len(read_vertices(tmp_path)) == 2

    def test_a_shapeless_cloud_has_no_axis(self):
        assert principal_axis([(0.0, 0.0)]) is None
        assert principal_axis([]) is None

    def test_the_absent_report_does_not_claim_the_chords_are_fine(self, tmp_path):
        text = format_report(report(tmp_path))
        assert "Nothing is inferred from the absence" in text
        assert "denied at CONNECT" in text


class TestItReportsRatherThanEdits:
    def test_spots_json_is_never_written(self):
        source = Path("forecast/shorenormal.py").read_text(encoding="utf-8")
        assert "spots.json" in source          # it is named, in the prose
        # Read-mode opens are fine and necessary; what must not exist is any
        # write, to spots.json or anywhere else.
        for writing in (".write_text(", "json.dump", '"w"', "'w'", '"a"', "'a'"):
            assert writing not in source, writing

    def test_the_report_says_so_out_loud(self, tmp_path):
        spot = BY_ID["coronado_center"]
        write_store(tmp_path, straight(spot, 124.0))
        text = format_report(report(tmp_path))
        assert "does not edit" in text

    def test_a_disagreement_is_shown_against_the_chord(self, tmp_path):
        """The whole point: the surveyed normal beside the one in use."""

        spot = BY_ID["coronado_center"]
        # 15 degrees off the chord's own trend, so a disagreement must appear.
        write_store(tmp_path, straight(spot, (spot.shore_bearing + 15.0) % 360.0))
        got = {r.id: r for r in report(tmp_path)}["coronado_center"]
        assert got.headline is not None
        assert abs(abs(got.disagreement_deg) - 15.0) < 1.0
        assert "coronado_center" in format_report(report(tmp_path))


class TestAnAbsenceSaysWhy:
    """A dash on its own cannot tell "no survey vertices here" from "vertices,
    but too few" from "fitted, and the normal came out on the wrong side". Those
    want three different responses, and a silent absence is the fault BRIEFING
    §8 and §13 both turn on."""

    def test_a_break_with_no_vertices_near_it_is_named_and_explained(self, tmp_path):
        spot = BY_ID["coronado_north"]
        # A survey covering only the north break.
        write_store(tmp_path, straight(spot, 104.0, span_m=300.0))
        text = format_report(report(tmp_path))
        assert "Not fitted, and why" in text
        assert "coronado_south" in text.split("Not fitted, and why")[1]

    def test_the_reason_distinguishes_too_few_from_none(self):
        spot = BY_ID["coronado_center"]
        sparse = fit_at(straight(spot, 124.0, n=MIN_VERTICES - 1, span_m=100.0),
                        spot, 400.0)
        assert "vertices" in sparse.note and sparse.normal_deg is None

    def test_a_fitted_break_is_not_listed_as_unfitted(self, tmp_path):
        """The control: the section must not appear when everything fitted."""

        pts = []
        for b in BREAKS_IDS:
            pts += straight(BY_ID[b], BY_ID[b].shore_bearing, span_m=600.0)
        text = format_report(report(tmp_path if False else _stored(tmp_path, pts)))
        assert "Not fitted, and why" not in text


BREAKS_IDS = ("coronado_north", "coronado_center", "coronado_south")


def _stored(tmp_path: Path, points) -> Path:
    write_store(tmp_path, points)
    return tmp_path


class TestDuplicateVerticesDoNotWeightTheFit:
    """The ENC coastline repeats a vertex wherever two chart segments meet —
    166 of 689 in the Coronado extract. A principal axis weights a repeated
    point twice, so the fit leans toward whichever stretch is stitched most
    often."""

    def test_a_repeated_point_does_not_move_the_normal(self):
        spot = BY_ID["coronado_center"]
        clean = straight(spot, 124.0, n=9, span_m=400.0)
        # Stack copies onto one end, which is where a lop-sided weight bites.
        loaded = clean + [clean[0]] * 6 + [clean[1]] * 6
        a = fit_at(clean, spot, 800.0)
        b = fit_at(loaded, spot, 800.0)
        assert a.normal_deg is not None and b.normal_deg is not None
        assert abs(((b.normal_deg - a.normal_deg + 180.0) % 360.0) - 180.0) < 0.01

    def test_duplicates_do_not_inflate_the_vertex_count(self):
        """`vertices` is what the MIN_VERTICES refusal is judged on, so a
        window of three points repeated twice must not read as six."""

        spot = BY_ID["coronado_center"]
        three = straight(spot, 124.0, n=3, span_m=300.0)
        assert fit_at(three + three, spot, 800.0).vertices == 3

    def test_a_window_of_repeats_refuses_rather_than_fitting(self):
        spot = BY_ID["coronado_center"]
        two = straight(spot, 124.0, n=2, span_m=200.0)
        got = fit_at(two * 8, spot, 400.0)
        assert got.normal_deg is None and "vertices" in got.note


class TestEverySourceIsRead:
    """§21 fitted normals to whichever source the collector reached first and
    could not know a finer chart existed. Reading one fixed filename is what
    made that invisible."""

    def test_sources_come_back_finest_band_first(self, tmp_path):
        spot = BY_ID["coronado_center"]
        folder = tmp_path / "shoreline"
        folder.mkdir(parents=True)
        for name in ("enc_approach_88_coronado", "enc_harbour_84_coronado",
                     "enc_general_58_coronado"):
            _write(folder / f"{name}.csv", straight(spot, 124.0, n=9))
        from forecast.shorenormal import read_sources
        assert list(read_sources(tmp_path)) == [
            "enc_harbour_84_coronado", "enc_approach_88_coronado",
            "enc_general_58_coronado"]

    def test_another_region_is_not_read_as_this_beach(self, tmp_path):
        """`data/shoreline/` holds more than one coast now. A Baja extract fed
        to a fit of Coronado's chord would lose every vertex to the scale
        filter and report as nothing at all, which is the worst way to be
        wrong: a contaminated source that looks like an absent one."""

        spot = BY_ID["coronado_center"]
        folder = tmp_path / "shoreline"
        folder.mkdir(parents=True)
        _write(folder / "enc_harbour_84_coronado.csv", straight(spot, 124.0, n=9))
        _write(folder / "enc_coastal_70_baja.csv", straight(spot, 124.0, n=9))
        from forecast.shorenormal import read_sources
        assert list(read_sources(tmp_path)) == ["enc_harbour_84_coronado"]
        assert list(read_sources(tmp_path, "baja")) == ["enc_coastal_70_baja"]

    def test_read_vertices_takes_the_finest(self, tmp_path):
        spot = BY_ID["coronado_center"]
        folder = tmp_path / "shoreline"
        folder.mkdir(parents=True)
        _write(folder / "enc_approach_88_coronado.csv", straight(spot, 124.0, n=5))
        _write(folder / "enc_harbour_84_coronado.csv", straight(spot, 124.0, n=41))
        from forecast.shorenormal import read_vertices
        assert len(read_vertices(tmp_path)) == 41

    def test_an_empty_folder_is_no_sources(self, tmp_path):
        from forecast.shorenormal import read_sources
        assert read_sources(tmp_path) == {}

    def test_the_comparison_shows_each_source(self, tmp_path):
        from forecast.shorenormal import compare_sources
        spot = BY_ID["coronado_center"]
        folder = tmp_path / "shoreline"
        folder.mkdir(parents=True)
        _write(folder / "enc_harbour_84_coronado.csv", straight(spot, 124.0, n=41))
        _write(folder / "enc_approach_88_coronado.csv", straight(spot, 130.0, n=41))
        text = compare_sources(tmp_path)
        assert "enc_harbour_84_coronado" in text
        assert "enc_approach_88_coronado" in text

    def test_one_source_alone_prints_no_comparison(self, tmp_path):
        """Nothing to compare is not a table with one row."""

        from forecast.shorenormal import compare_sources
        spot = BY_ID["coronado_center"]
        folder = tmp_path / "shoreline"
        folder.mkdir(parents=True)
        _write(folder / "enc_harbour_84_coronado.csv", straight(spot, 124.0, n=41))
        assert compare_sources(tmp_path) == ""

    def test_the_comparison_shows_the_vertex_count(self, tmp_path):
        """A normal from three points is a line through three points. The
        count is why §21 could not fit north, so it belongs in the table."""

        from forecast.shorenormal import compare_sources
        spot = BY_ID["coronado_center"]
        folder = tmp_path / "shoreline"
        folder.mkdir(parents=True)
        _write(folder / "enc_harbour_84_coronado.csv", straight(spot, 124.0, n=41))
        _write(folder / "enc_approach_88_coronado.csv", straight(spot, 124.0, n=41))
        assert "v)" in compare_sources(tmp_path)


def _write(path, points):
    import csv as _csv
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = _csv.DictWriter(fh, fieldnames=["part", "seq", "lat", "lon",
                                            "source_layer", "fetched_utc"])
        w.writeheader()
        for seq, (lat, lon) in enumerate(points):
            w.writerow({"part": 0, "seq": seq, "lat": f"{lat:.7f}",
                        "lon": f"{lon:.7f}", "source_layer": "test",
                        "fetched_utc": "2026-09-20T00:00:00Z"})
