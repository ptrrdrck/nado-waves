"""Tests for the live forecast.

Two things matter here. One is that the forecast degrades honestly — a missing
wind file or an unavailable cycle has to say so rather than emit a plausible
number. The other is BRIEFING §11: the directional spread is assumed rather
than measured, so the claim has to survive being wrong about it.
"""

from __future__ import annotations

import json
from dataclasses import asdict
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
        assert south["opened_by"] == "Baja peninsula"
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


class TestTheForecastTideCarriesTheMeasuredDeparture:
    """The card's tide is the level the breaking used: the prediction plus the
    gauge's measured departure over the last three days, carried to the coast.
    Without a measured departure it is the bare prediction and says so by
    carrying no `departure_m`."""

    @staticmethod
    def gauge(tmp_path, observed: float | None):
        tide = tmp_path / "tide"
        tide.mkdir()
        head = "time_utc,first_seen_utc,height_m,kind,datum\n"
        hours = [CYCLE + timedelta(hours=h) for h in range(-72, 12)]
        stamp = lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ")
        (tide / "9410170_predicted.csv").write_text(
            head + "".join(f"{stamp(t)},{stamp(CYCLE)},1.0,predicted,MLLW\n" for t in hours))
        if observed is not None:
            (tide / "9410170_observed.csv").write_text(
                head + "".join(f"{stamp(t)},{stamp(CYCLE)},{observed},observed,MLLW\n"
                               for t in hours if t <= CYCLE))
        (tide / "9410170_turns.csv").write_text(
            "time_utc,first_seen_utc,height_m,kind,datum,event\n"
            f"{stamp(CYCLE + timedelta(hours=2))},{stamp(CYCLE)},1.5,predicted,MLLW,high\n")

    def test_the_height_and_the_turn_carry_it(self, tmp_path):
        from forecast.tidesite import RATIO

        self.gauge(tmp_path, observed=1.2)
        got = live.build(bulletin=bulletin(SOUTH), now=CYCLE, data_dir=tmp_path)
        assert got.tide_departure_m == pytest.approx(0.2)
        covered = [t for t in got.tide if t.height_m is not None]
        assert covered
        for t in covered:
            assert t.height_m == pytest.approx(RATIO * 1.2, abs=1e-3)
            assert t.departure_m == pytest.approx(RATIO * 0.2, abs=1e-3)
        assert [t["height_m"] for t in got.tide_turns] == [pytest.approx(RATIO * 1.7, abs=1e-3)]

    def test_no_measured_departure_is_the_bare_prediction(self, tmp_path):
        from forecast.tidesite import RATIO

        self.gauge(tmp_path, observed=None)
        got = live.build(bulletin=bulletin(SOUTH), now=CYCLE, data_dir=tmp_path)
        assert got.tide_departure_m is None
        covered = [t for t in got.tide if t.height_m is not None]
        assert covered and all(t.departure_m is None for t in covered)
        assert all(t.height_m == pytest.approx(RATIO * 1.0, abs=1e-3) for t in covered)

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
    NOW = datetime(2026, 9, 30, 6, 33, tzinfo=timezone.utc)

    def _fetch(self, monkeypatch, failures):
        from collector.gfswave import BulletinError

        def fake(station, cycle, attempts=2):
            if cycle.hour in failures:
                raise BulletinError(f"https://x/gfs/{cycle:%H}.bull_tar: HTTP {failures[cycle.hour]}",
                                    failures[cycle.hour])
            return f"bulletin {cycle:%H}Z"
        monkeypatch.setattr(live, "fetch_bulletin", fake)
        return live.fetch_latest(now=self.NOW)

    def test_a_run_not_out_yet_is_said_plainly_with_the_run_shown(self, monkeypatch):
        # 2026-09-30: the 00Z run was an hour late; the banner printed a 404 URL.
        got, warnings = self._fetch(monkeypatch, {0: 404})
        assert got == "bulletin 18Z"
        assert warnings == ["GFS-Wave's 00Z run is not published yet; showing the 18Z run."]
        assert not any("HTTP" in w or "http" in w for w in warnings)

    def test_two_late_runs_are_both_named(self, monkeypatch):
        got, warnings = self._fetch(monkeypatch, {0: 404, 18: 404})
        assert got == "bulletin 12Z"
        assert warnings == ["GFS-Wave's 00Z and 18Z runs are not published yet; showing the 12Z run."]

    def test_a_failure_that_is_not_a_404_keeps_its_technical_line(self, monkeypatch):
        got, warnings = self._fetch(monkeypatch, {0: 503})
        assert got == "bulletin 18Z"
        assert len(warnings) == 1 and "HTTP 503" in warnings[0]

    def test_no_run_at_all_keeps_every_reason(self, monkeypatch):
        got, warnings = self._fetch(monkeypatch, {0: 404, 18: 404, 12: 404, 6: 404})
        assert got is None
        assert len(warnings) == 4 and all("HTTP 404" in w for w in warnings)

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

    def test_the_table_never_calls_the_number_a_surf_height(self):
        """Refraction and shoaling are modelled since 2026-09-25, so the old
        "no shoaling, no refraction" disclaimer would now be false. What is
        still true, and still said: it is not a surf height at the sand."""

        text = " ".join(live.format_table(live.build(bulletin=bulletin(SOUTH), now=CYCLE)).split())
        assert "Neither is a surf height at the sand" in text
        assert "no offshore-to-face transfer" in text
        assert "nothing here carries an error bar" in text

    def test_every_hour_carries_the_nearshore_chain(self):
        got = live.build(bulletin=bulletin(SOUTH), now=CYCLE)
        for entry in got.breaks:
            for hour in entry.hours:
                assert hour.hs_nearshore_m is not None
                effects = hour.nearshore["effects"]
                assert effects["window_hs_m"] == pytest.approx(hour.hs_window_m, abs=1e-3)
                assert effects["buoy_hs_m"] == pytest.approx(hour.hs_offshore_m, abs=1e-3)
        assert got.standing_on["seabed"].startswith("MODELLED")


class TestThePastComesFromTheLog:
    """The page reaches 48 h back into what it said. That can only come from
    the permanent log, read BEFORE this build is appended to it -- otherwise
    a build could claim to have been on screen for hours it was not."""

    def test_past_is_read_from_the_data_directory_log(self, tmp_path):
        from forecast import forecastlog

        earlier = live.build(bulletin=bulletin(SOUTH, hours=13), now=CYCLE,
                             data_dir=tmp_path)
        forecastlog.append(json.loads(json.dumps(asdict(earlier))),
                           forecastlog.log_dir(tmp_path))
        later = live.build(bulletin=bulletin(SOUTH, hours=13),
                           now=CYCLE + timedelta(hours=12), data_dir=tmp_path)
        assert [p["valid_utc"] for p in later.past] == [
            "2026-09-18T00:00:00Z", "2026-09-18T03:00:00Z",
            "2026-09-18T06:00:00Z", "2026-09-18T09:00:00Z"]
        assert later.past[0]["generated_utc"] == "2026-09-18T00:00:00Z"

    def test_no_log_no_past(self, tmp_path):
        assert live.build(bulletin=bulletin(SOUTH), now=CYCLE, data_dir=tmp_path).past == []

    def test_past_hours_carry_their_own_builds_detail(self, tmp_path):
        from forecast import forecastlog

        earlier = json.loads(json.dumps(asdict(
            live.build(bulletin=bulletin(SOUTH, hours=13), now=CYCLE, data_dir=tmp_path))))
        forecastlog.append(earlier, forecastlog.log_dir(tmp_path))
        forecastlog.append_shown(earlier, forecastlog.shown_dir(tmp_path))
        later = live.build(bulletin=bulletin(SOUTH, hours=13),
                           now=CYCLE + timedelta(hours=12), data_dir=tmp_path)
        detail = later.past[1]["detail"]
        assert set(detail["breaks"]) == {b.id for b in later.breaks}
        assert detail["breaks"]["coronado_north"]["valid_utc"] == later.past[1]["valid_utc"]


class TestTheLocalWindForecast:
    """The NWS grid's wind on the sand, per hour, beside the model's wind at
    the buoy; what it means is worked out per break, against its own normal."""

    LOCAL = {"provider": "NWS", "office": "SGX", "grid_x": 55, "grid_y": 12,
             "updated_utc": "2026-09-17T22:00:00Z",
             "hours": [{"valid_utc": "2026-09-18T00:00:00Z", "from_deg": 30, "speed_kt": 8.0, "gust_kt": 14.0},
                       {"valid_utc": "2026-09-18T01:00:00Z", "from_deg": 210, "speed_kt": 12.0, "gust_kt": None}]}

    def test_each_hour_carries_the_local_wind_and_each_break_its_own_reading(self):
        got = live.build(bulletin=bulletin(SOUTH), now=CYCLE, local_wind=self.LOCAL)
        assert got.local_wind["available"] is True and got.local_wind["office"] == "SGX"
        assert "hours" not in got.local_wind
        for entry in got.breaks:
            by = {h.valid_utc: h for h in entry.hours}
            first, onshore = by["2026-09-18T00:00:00Z"], by["2026-09-18T01:00:00Z"]
            assert (first.local_wind_from_deg, first.local_wind_kt, first.local_gust_kt) == (30, 8.0, 14.0)
            assert first.local_wind_offshore > 0.9 and onshore.local_wind_offshore < -0.9
            # The model's own wind at the buoy is untouched beside it.
            assert first.wind_from_deg != 30 or first.wind_kt != 8.0

    def test_an_hour_the_grid_did_not_give_carries_nothing(self):
        got = live.build(bulletin=bulletin(SOUTH), now=CYCLE, local_wind=self.LOCAL)
        later = [h for h in got.breaks[0].hours if h.valid_utc > "2026-09-18T01:00:00Z"]
        assert later and all(h.local_wind_from_deg is None and h.local_wind_offshore is None
                             for h in later)

    def test_no_fetch_says_why(self):
        got = live.build(bulletin=bulletin(SOUTH), now=CYCLE)
        assert got.local_wind == {"available": False, "why": "not fetched for this build"}
        failed = live.build(bulletin=bulletin(SOUTH), now=CYCLE,
                            local_wind={"available": False, "why": "api.weather.gov: HTTP 503"})
        assert failed.local_wind == {"available": False, "why": "api.weather.gov: HTTP 503"}


class TestTheHourlyColumns:
    """`hourly`: one value an hour for the Wind and Tide cards' charts, from
    the earliest hour the page offers to the run's end. The tide is the card's
    (with the departure); the wind is the local forecast; an hour neither
    covers is None, never the hour beside it."""

    def test_the_tide_and_the_local_wind_every_hour(self, tmp_path):
        from forecast.tidesite import RATIO

        TestTheForecastTideCarriesTheMeasuredDeparture.gauge(tmp_path, observed=1.2)
        got = live.build(bulletin=bulletin(SOUTH), now=CYCLE, data_dir=tmp_path,
                         local_wind=TestTheLocalWindForecast.LOCAL)
        h = got.hourly
        assert h["start_utc"] == "2026-09-18T00:00:00Z" and h["step_h"] == 1
        assert len(h["tide_m"]) == 3 == len(h["local_wind"]["kt"])
        assert all(v == pytest.approx(RATIO * 1.2, abs=1e-3) for v in h["tide_m"])
        assert h["local_wind"]["kt"] == [8.0, 12.0, None]
        assert h["local_wind"]["from_deg"] == [30, 210, None]
        assert h["local_wind"]["gust_kt"] == [14.0, None, None]
        # Night over the same hours, for the Tide chart's shading: 00Z-02Z on
        # 18 Sep is 5-7 PM in San Diego, so sunset falls inside the window.
        assert h["nights"] and h["nights"][0][1] == "2026-09-18T02:00:00Z"

    def test_it_reaches_back_to_the_earliest_past_hour(self):
        past = [{"valid_utc": "2026-09-17T21:00:00Z"}]
        got = live.hourly_columns(bulletin(SOUTH).rows, past, [], None, {})
        assert got["start_utc"] == "2026-09-17T21:00:00Z"
        assert len(got["tide_m"]) == 6 and got["tide_m"] == [None] * 6

    def test_the_models_own_wind_is_kept_where_the_run_gives_it(self):
        """GFS-Wave's wind at the buoy, by valid time; an hour the run does
        not carry is None, for the page to join across as the model's spacing."""

        rows = bulletin(SOUTH, hours=4).rows
        model = {CYCLE: (10.04, 281.4), CYCLE + timedelta(hours=3): (12.0, 359.6)}
        got = live.hourly_columns(rows, [], [], None, {}, model)["model_wind"]
        assert got["kt"] == [10.0, None, None, 12.0]
        assert got["from_deg"] == [281, None, None, 0]

    def test_publishing_leaves_it_whole(self):
        from forecast.publish import thin

        got = live.build(bulletin=bulletin(SOUTH, hours=7), now=CYCLE,
                         local_wind=TestTheLocalWindForecast.LOCAL)
        out = thin(json.loads(json.dumps(asdict(got))))
        assert len(out["hourly"]["local_wind"]["kt"]) == 7


class TestLocalChopTakesTheLocalWind:
    """Local chop grows on the water off the break, so the forecast grows it
    from the LOCAL forecast wind, as the observed chain uses KNZY's."""

    def test_the_chop_is_made_from_the_nws_wind_and_says_so(self):
        got = live.build(bulletin=bulletin(SOUTH), now=CYCLE,
                         local_wind=TestTheLocalWindForecast.LOCAL)
        centre = next(b for b in got.breaks if b.id == "coronado_center")
        onshore = next(h for h in centre.hours if h.valid_utc == "2026-09-18T01:00:00Z")
        offshore = next(h for h in centre.hours if h.valid_utc == "2026-09-18T00:00:00Z")
        local = (onshore.nearshore.get("effects") or {}).get("local")
        if not onshore.nearshore:
            pytest.skip("no nearshore tables in this checkout")
        # 210° at 12 kt is onshore over open water at the center break.
        assert local and local["wind"] == "NWS forecast" and local["fetch"] == "open"
        assert local["hs_m"] > 0.05
        # 30° blows off the land: no chop reaches the beach.
        assert (offshore.nearshore.get("effects") or {}).get("local") is None
