"""The permanent forecast log, and the 48 h of it the page reads back."""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone

from forecast import forecastlog, publish

ISO = "%Y-%m-%dT%H:%M:%SZ"
BREAKS = ("coronado_north", "coronado_center", "coronado_south")


def stamp(moment: datetime) -> str:
    return moment.strftime(ISO)


def forecast(cycle: datetime, generated: datetime, *, hours: int = 12,
             base: float = 1.0, spectral: bool = True) -> dict:
    """A forecast shaped as `live.write` writes it, hourly, with a nearshore chain."""

    valid = [cycle + timedelta(hours=h) for h in range(hours + 1)]
    breaks = []
    for n, bid in enumerate(BREAKS):
        breaks.append({"id": bid, "hours": [
            {"valid_utc": stamp(v), "lead_h": h, "hs_offshore_m": base,
             "hs_window_m": base * 0.5, "dominant_period_s": 14.0,
             "dominant_from_deg": 200, "hs_nearshore_m": base * 0.4 + n / 100,
             "nearshore": {"hs_m": base * 0.4 + n / 100, "depth_m": 5.0,
                           "breaking": {"hs_m": base * 0.4, "depth_m": 1.83},
                           "effects": {"with_chop_hs_m": base * 0.35}}}
            for h, v in enumerate(valid)]})
    return {
        "generated_utc": stamp(generated), "cycle_utc": stamp(cycle),
        "wave_source": "spectrum" if spectral else "partitions",
        "buoy": [{"valid_utc": stamp(v), "hs_m": base, "peak_period_s": 14.3,
                  "peak_direction_deg": 205} for v in valid] if spectral else [],
        "breaks": breaks,
    }


CYCLE = datetime(2026, 9, 26, 0, tzinfo=timezone.utc)
GENERATED = CYCLE + timedelta(hours=5, minutes=40)


class TestRows:
    def test_every_third_hour_one_row_per_site(self):
        got = forecastlog.rows(forecast(CYCLE, GENERATED))
        assert {r["lead_h"] for r in got} == {0, 3, 6, 9, 12}
        assert len(got) == 5 * 4
        assert {r["site"] for r in got} == {"buoy", *BREAKS}

    def test_the_step_agrees_with_what_the_page_offers(self):
        assert forecastlog.HOUR_STEP == publish.HOUR_STEP

    def test_the_headline_and_what_it_was(self):
        row = next(r for r in forecastlog.rows(forecast(CYCLE, GENERATED))
                   if r["site"] == "coronado_south")
        assert (row["hs_m"], row["hs_basis"], row["depth_m"]) == ("0.42", "breaking", "1.83")
        assert row["hs_5m_m"] == "0.35"

    def test_the_partitions_path_logs_the_buoy_from_the_offshore_total(self):
        row = next(r for r in forecastlog.rows(forecast(CYCLE, GENERATED, spectral=False))
                   if r["site"] == "buoy")
        assert row["hs_m"] == "1.0" and row["period_s"] == ""

    def test_no_cycle_no_rows(self):
        assert forecastlog.rows({"generated_utc": stamp(GENERATED), "breaks": []}) == []


class TestAppend:
    def test_monthly_file_and_idempotent_on_the_build(self, tmp_path):
        f = forecast(CYCLE, GENERATED)
        assert forecastlog.append(f, tmp_path) == 20
        assert forecastlog.append(f, tmp_path) == 0
        assert [p.name for p in tmp_path.iterdir()] == ["2026-09.csv"]
        with (tmp_path / "2026-09.csv").open() as fh:
            assert len(list(csv.DictReader(fh))) == 20

    def test_a_rebuild_of_the_same_cycle_is_a_new_build(self, tmp_path):
        forecastlog.append(forecast(CYCLE, GENERATED), tmp_path)
        again = forecast(CYCLE, GENERATED + timedelta(hours=6))
        assert forecastlog.append(again, tmp_path) == 20
        assert len(forecastlog.read(tmp_path)) == 40


class TestPastHours:
    def log(self, tmp_path, *builds):
        for f in builds:
            forecastlog.append(f, tmp_path)
        return forecastlog.read(tmp_path)

    def test_the_latest_build_generated_before_the_hour_wins(self, tmp_path):
        early = forecast(CYCLE - timedelta(hours=6), GENERATED - timedelta(hours=6),
                         hours=30, base=1.0)
        late = forecast(CYCLE, GENERATED, hours=24, base=2.0)
        rows = self.log(tmp_path, early, late)
        past = forecastlog.past_hours(rows, stamp(GENERATED + timedelta(hours=9)))
        by = {p["valid_utc"]: p for p in past}
        # 03Z: `late` was generated at 05:40, after it -- it was never a
        # forecast for 03Z. `early` (generated 23:40 the day before) was.
        assert by["2026-09-26T03:00:00Z"]["buoy"]["hs_m"] == 1.0
        assert by["2026-09-26T03:00:00Z"]["cycle_utc"] == "2026-09-25T18:00:00Z"
        # 06Z onward: `late` had been published, so it is what was on screen.
        assert by["2026-09-26T06:00:00Z"]["buoy"]["hs_m"] == 2.0
        assert by["2026-09-26T12:00:00Z"]["lead_h"] == 12

    def test_an_hour_no_build_covered_in_advance_is_left_out(self, tmp_path):
        rows = self.log(tmp_path, forecast(CYCLE, GENERATED, hours=24))
        past = forecastlog.past_hours(rows, stamp(GENERATED + timedelta(hours=9)))
        assert [p["valid_utc"] for p in past] == [
            "2026-09-26T06:00:00Z", "2026-09-26T09:00:00Z", "2026-09-26T12:00:00Z"]

    def test_only_the_48_hours_before_the_build(self, tmp_path):
        old = forecast(CYCLE - timedelta(days=4), GENERATED - timedelta(days=4), hours=168)
        rows = self.log(tmp_path, old)
        past = forecastlog.past_hours(rows, stamp(GENERATED))
        first = datetime.strptime(past[0]["valid_utc"], ISO).replace(tzinfo=timezone.utc)
        assert GENERATED - first <= timedelta(hours=48)
        assert past[-1]["valid_utc"] < stamp(GENERATED)

    def test_every_break_and_the_buoy_carry_through(self, tmp_path):
        rows = self.log(tmp_path, forecast(CYCLE, GENERATED, hours=24))
        entry = forecastlog.past_hours(rows, stamp(CYCLE + timedelta(hours=12)))[0]
        assert set(entry["breaks"]) == set(BREAKS)
        assert entry["breaks"]["coronado_north"]["hs_basis"] == "breaking"
        assert entry["breaks"]["coronado_north"]["depth_m"] == 1.83

    def test_empty_log_empty_past(self, tmp_path):
        assert forecastlog.past_hours(forecastlog.read(tmp_path / "none"),
                                      stamp(GENERATED)) == []
