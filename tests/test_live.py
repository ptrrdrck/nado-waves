"""Tests for the live forecast.

Two things matter here. One is that the forecast degrades honestly — a missing
wind file or an unavailable cycle has to say so rather than emit a plausible
number. The other is BRIEFING §11: the directional spread is assumed rather
than measured, so the claim has to survive being wrong about it.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from collector.gfswave import Bulletin, BulletinRow, Partition
from forecast import live
from forecast.geometry import load
from forecast.transform import through_partitions

SPOTS, BLOCKERS = load()
BY_ID = {s.id: s for s in SPOTS}
CYCLE = datetime(2026, 9, 18, 0, tzinfo=timezone.utc)


def bulletin(partitions, hours: int = 3) -> Bulletin:
    rows = [
        BulletinRow(
            valid_utc=CYCLE + timedelta(hours=h),
            lead_hours=h,
            hs_total_m=round(sum(p.hs_m ** 2 for p in partitions) ** 0.5, 2),
            fields_found=len(partitions),
            fields_omitted=0,
            partitions=tuple(partitions),
        )
        for h in range(hours)
    ]
    return Bulletin(station_id="46232", latitude=32.52, longitude=-117.42,
                    cycle_utc=CYCLE, rows=rows)


SOUTH = [Partition(hs_m=0.5, tp_s=15.3, toward_deg=16, wind_sea=False)]
WEST = [Partition(hs_m=1.2, tp_s=16.0, toward_deg=75, wind_sea=False)]


class TestTheSwellWindowExcludesUnmodelledCoast:
    """BRIEFING §12, and what became of it on 2026-09-20.

    The rule stands: an edge formed by the seaward half-plane means the arc
    ran out of MODELLED land, and publishing it shows land as open water. The
    south-east arc was withheld because Imperial Beach, the Tijuana river
    mouth and Rosarito were not in spots.json. They are now — the Baja coast
    is charted and blocked — so the half-plane forms no edge anywhere and
    three land-bounded windows are published per break instead of one.
    """

    def test_every_published_edge_stands_on_land(self):
        got = live.build(bulletin=bulletin(SOUTH), now=CYCLE)
        for entry in got.breaks:
            assert len(entry.swell_window) == 3
            south, channel, west = entry.swell_window
            assert 160 <= south["from"] <= 172 and 185 <= south["to"] <= 195
            assert 190 <= channel["from"] <= 200 and 196 <= channel["to"] <= 206
            assert 198 <= west["from"] <= 208 and 240 <= west["to"] <= 262

    def test_each_window_says_what_forms_its_edges(self):
        """The surface has to name these windows, and the only honest name
        for a window is the land either side of it. Hardcoding
        'south / channel / west' into the page would keep saying it after the
        geometry moved — and there are three windows here only because the
        geometry moved."""

        got = live.build(bulletin=bulletin(SOUTH), now=CYCLE)
        south, channel, west = got.breaks[0].swell_window
        assert south["opened_by"] == "Baja mainland"
        assert "Islands" in south["closed_by"]
        assert "Islands" in channel["opened_by"] and "Islands" in channel["closed_by"]
        assert channel["opened_by"] != channel["closed_by"]
        assert west["closed_by"] == "Point Loma peninsula"
        assert all(w["confidence"] == "high" for w in (south, channel, west))

    def test_the_west_window_matches_the_briefing_figures(self):
        """41.3 / 47.6 / 54.9 degrees. The low edge moved when the Coronado
        Islands were charted (2026-09-20, from 42.8 / 49.1 / 56.3); the high
        edge when the Point Loma tip was (2026-09-22, to 41.1 / 47.7 / 54.9),
        each break taking its own tangent off the charted tip; and north's
        again the same day when the break chords were read off the ENC and
        its position moved 30 m (BRIEFING §27). The spread across the beach,
        which is what §2a is about, is 13.6 degrees. Edges are published rounded to 0.1°, so a span taken
        from them can differ by that much; the tolerance is the rounding."""

        got = live.build(bulletin=bulletin(SOUTH), now=CYCLE)
        expected = {"coronado_north": 41.3, "coronado_center": 47.6,
                    "coronado_south": 54.9}
        for entry in got.breaks:
            west = entry.swell_window[-1]
            assert west["to"] - west["from"] == pytest.approx(expected[entry.id], abs=0.1)

    def test_the_south_east_arc_is_now_a_published_window(self):
        """It was never deleted from the model, only withheld. What it was
        waiting for was the coastline it crossed, and the shoreline collector
        fetched it."""

        from forecast.geometry import load, open_window, swell_window

        spots, blockers = load()
        north = [s for s in spots if s.id == "coronado_north"][0]
        assert len(open_window(north, blockers)) == 3
        assert swell_window(north, blockers) == open_window(north, blockers)


class TestScope:
    def test_only_the_three_coronado_breaks_are_published(self):
        got = live.build(bulletin=bulletin(SOUTH), now=CYCLE)
        assert [b.id for b in got.breaks] == list(live.BREAKS)
        assert all(b.id.startswith("coronado") for b in got.breaks)

    def test_breakers_and_gator_are_not_in_the_output(self):
        got = live.build(bulletin=bulletin(SOUTH), now=CYCLE)
        blob = json.dumps([b.id for b in got.breaks])
        assert "nasni" not in blob and "gator" not in blob


class TestTheDifferentialIsRobust:
    """BRIEFING §11. If the ratio between breaks swung with the assumed
    spread, the differential would be an artifact of an unfitted number.

    The south fixture's tolerance went from 0.02 to 0.03 on 2026-09-20. It
    arrives from 196 degrees, which the charted island outlines put next to
    the edge of the 6-degree channel between the two islands, so widening the
    spread now trades energy across that edge as well as across the Point Loma
    one. 2.4% across a fourfold spread change instead of 2.0%: the section's
    claim is unchanged in kind, and the number is worse because the geometry
    is finer, not because the model is.
    """

    @pytest.mark.parametrize("partitions,tolerance", [(SOUTH, 0.03), (WEST, 0.06)])
    def test_the_ratio_barely_moves_across_a_fourfold_spread_change(self, partitions, tolerance):
        from collector.gfswave import from_direction

        parts = [(p.hs_m, p.tp_s, float(from_direction(p.toward_deg)), p.wind_sea)
                 for p in partitions]
        ratios = []
        for spread in (10.0, 20.0, 30.0, 40.0):
            heights = [
                through_partitions(BY_ID[i], BLOCKERS, parts, spread_override=spread).hs_in_window_m
                for i in live.BREAKS
            ]
            ratios.append(heights[-1] / heights[0])
        assert max(ratios) - min(ratios) < tolerance

    def test_a_west_swell_separates_the_breaks_and_a_south_swell_does_not(self):
        """The control: the gradient has to come from Point Loma's parallax,
        not from the method. A south swell must treat the three alike."""

        def spread(forecast):
            heights = [b.hours[0].hs_window_m for b in forecast.breaks]
            return max(heights) / min(heights)

        south = spread(live.build(bulletin=bulletin(SOUTH), now=CYCLE))
        west = spread(live.build(bulletin=bulletin(WEST), now=CYCLE))
        assert west > south
        assert south < 1.10 < west


class TestItDegradesHonestly:
    def test_missing_wind_says_so_rather_than_guessing(self, tmp_path):
        got = live.build(bulletin=bulletin(SOUTH), now=CYCLE, data_dir=tmp_path)
        assert any("wind not collected" in w for w in got.warnings)
        assert not got.wind.measured
        assert all(b.wind_offshore is None for b in got.breaks)

    def test_missing_tide_leaves_the_field_empty_not_zero(self, tmp_path):
        got = live.build(bulletin=bulletin(SOUTH), now=CYCLE, data_dir=tmp_path)
        assert got.tide and all(t.height_m is None for t in got.tide)

    def test_no_cycle_produces_no_breaks_and_says_why(self, monkeypatch, tmp_path):
        monkeypatch.setattr(live, "fetch_latest", lambda **kw: (None, ["cycle unavailable"]))
        got = live.build(now=CYCLE, data_dir=tmp_path)
        assert got.breaks == []
        assert any("No GFS-Wave cycle" in w for w in got.warnings)

    def test_every_output_states_what_it_is_standing_on(self):
        got = live.build(bulletin=bulletin(SOUTH), now=CYCLE)
        for key in ("geometry", "model", "calibration", "observation", "claim"):
            assert key in got.standing_on
        assert "none" in got.standing_on["observation"]
        assert "not accurate" in got.standing_on["claim"]

    def test_the_spread_assumption_is_published_not_hidden(self):
        got = live.build(bulletin=bulletin(SOUTH), now=CYCLE)
        assert got.spread_assumption["swell_deg"] == live.SWELL_SPREAD_DEG
        assert "not fitted" in got.spread_assumption["note"]


class TestWind:
    def test_offshore_is_positive_when_the_wind_comes_off_the_land(self):
        centre = BY_ID["coronado_center"]
        offshore_bearing = (centre.normal + 180.0) % 360.0
        assert live.offshore_component(offshore_bearing, centre.normal) == pytest.approx(1.0)
        assert live.offshore_component(centre.normal, centre.normal) == pytest.approx(-1.0)

    def test_an_unverified_chord_flags_the_offshore_call(self):
        """The window does not depend on the chord, but offshore/onshore does -
        it is computed from the normal. A break with a digitised position and
        an unverified chord must say so on the wind line. Coronado's north
        break was that case until its chord was charted (BRIEFING §27), so the
        case is built here rather than borrowed from the file."""

        from dataclasses import replace

        wind = live.wind_measurement({"observed_utc": "2026-09-18T05:56:00Z",
                                      "wind_from_deg": "280", "wind_kt": "8",
                                      "gust_kt": "", "variable": ""})
        unverified = replace(BY_ID["coronado_north"], shoreline_verified=False)
        _, note = live.wind_at_break(unverified, wind)
        assert "unverified" in note
        for sid in ("coronado_north", "coronado_center", "coronado_south"):
            assert live.wind_at_break(BY_ID[sid], wind)[1] == "", sid

    def test_a_variable_wind_yields_no_direction(self):
        wind = live.wind_measurement({"observed_utc": "x", "variable": "1", "wind_kt": "3"})
        assert wind.from_deg is None and "variable" in wind.note
        assert live.wind_at_break(BY_ID["coronado_center"], wind) == (None, "")

    def test_the_wind_measurement_is_hoisted_and_the_sense_is_not(self):
        """One station, so one reading — but the three shore normals span 29°,
        so what that wind MEANS is per break and must stay there."""

        wind = live.wind_measurement({"observed_utc": "x", "wind_from_deg": "290",
                                      "wind_kt": "10", "gust_kt": "", "variable": ""})
        assert not hasattr(wind, "offshore")
        senses = {sid: live.wind_at_break(BY_ID[sid], wind)[0] for sid in live.BREAKS}
        assert len(set(senses.values())) == 3, senses
        assert senses["coronado_north"] > senses["coronado_south"]


class TestCycleSelection:
    def test_the_latest_cycle_respects_publication_lag(self):
        # 04:00Z is less than CYCLE_LAG_HOURS after 00Z, so 18Z the day before
        # is the newest cycle that should exist.
        assert live.latest_cycle(datetime(2026, 9, 18, 4, tzinfo=timezone.utc)).hour == 18
        assert live.latest_cycle(datetime(2026, 9, 18, 12, tzinfo=timezone.utc)).hour == 6


class TestOutput:
    def test_json_round_trips(self, tmp_path):
        got = live.build(bulletin=bulletin(SOUTH), now=CYCLE, data_dir=tmp_path)
        path = tmp_path / "live" / "forecast.json"
        live.write(got, path)
        blob = json.loads(path.read_text())
        assert blob["station"] == "46232"
        assert len(blob["breaks"]) == 3

    def test_the_table_never_calls_the_number_a_wave_height(self):
        text = " ".join(live.format_table(live.build(bulletin=bulletin(SOUTH), now=CYCLE)).split())
        assert "not a wave height at the beach" in text
        assert "no shoaling, no refraction" in text
        assert "nothing here carries an error bar" in text
