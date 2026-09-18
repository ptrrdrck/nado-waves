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
    spread, the differential would be an artifact of an unfitted number."""

    @pytest.mark.parametrize("partitions,tolerance", [(SOUTH, 0.02), (WEST, 0.06)])
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

        south = live.build(bulletin=bulletin(SOUTH), now=CYCLE)
        west = live.build(bulletin=bulletin(WEST), now=CYCLE)
        south_ratio = south.breaks[-1].ratio_to_smallest
        west_ratio = west.breaks[-1].ratio_to_smallest
        assert west_ratio > south_ratio
        assert south_ratio < 1.10 < west_ratio


class TestItDegradesHonestly:
    def test_missing_wind_says_so_rather_than_guessing(self, tmp_path):
        got = live.build(bulletin=bulletin(SOUTH), now=CYCLE, data_dir=tmp_path)
        assert any("wind not collected" in w for w in got.warnings)
        assert all(b.wind.from_deg is None for b in got.breaks)

    def test_missing_tide_leaves_the_field_empty_not_zero(self, tmp_path):
        got = live.build(bulletin=bulletin(SOUTH), now=CYCLE, data_dir=tmp_path)
        assert all(h.tide_m is None for b in got.breaks for h in b.hours)

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

    def test_an_unverified_chord_flags_the_offshore_call(self, tmp_path):
        """The window does not depend on the chord, but offshore/onshore does —
        it is computed from the normal. Coronado's north break has a digitised
        position and an unverified chord, so the two claims differ there."""

        wind = live.wind_for(BY_ID["coronado_north"],
                             {"observed_utc": "2026-09-18T05:56:00Z",
                              "wind_from_deg": "280", "wind_kt": "8", "gust_kt": "",
                              "variable": ""})
        assert "unverified" in wind.note

    def test_a_variable_wind_yields_no_direction(self):
        wind = live.wind_for(BY_ID["coronado_center"],
                             {"observed_utc": "x", "variable": "1", "wind_kt": "3"})
        assert wind.from_deg is None and "variable" in wind.note


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
