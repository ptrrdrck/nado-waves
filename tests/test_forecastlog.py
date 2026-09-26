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


class TestTheShownLog:
    """Past cards are drawn from what their own build showed, in full."""

    def test_only_hours_from_publication_to_48_h_ahead(self, tmp_path):
        f = forecast(CYCLE, GENERATED, hours=72)
        lines = forecastlog.shown_lines(f)
        valid = [l["valid_utc"] for l in lines]
        assert valid[0] == "2026-09-26T06:00:00Z"     # first offered hour after 05:40
        assert valid[-1] <= stamp(GENERATED + timedelta(hours=48))
        assert all(set(l["breaks"]) == set(BREAKS) for l in lines)
        assert lines[0]["breaks"]["coronado_north"]["nearshore"]["effects"]["with_chop_hs_m"] == 0.35
        assert lines[0]["buoy"]["hs_m"] == 1.0

    def test_idempotent_on_the_build(self, tmp_path):
        f = forecast(CYCLE, GENERATED, hours=24)
        n = forecastlog.append_shown(f, tmp_path)
        assert n > 0 and forecastlog.append_shown(f, tmp_path) == 0
        assert len(forecastlog.read_shown(tmp_path)) == n

    def test_past_carries_the_detail_of_its_own_build_only(self, tmp_path):
        early = forecast(CYCLE - timedelta(hours=6), GENERATED - timedelta(hours=6),
                         hours=30, base=1.0)
        late = forecast(CYCLE, GENERATED, hours=24, base=2.0)
        for f in (early, late):
            forecastlog.append(f, tmp_path / "log")
        # Only the EARLY build kept detail: the late one's hours must not
        # borrow it, and must not borrow the early build's either.
        forecastlog.append_shown(early, tmp_path / "shown")
        past = forecastlog.past_hours(
            forecastlog.read(tmp_path / "log"), stamp(GENERATED + timedelta(hours=9)),
            shown=forecastlog.read_shown(tmp_path / "shown"))
        by = {p["valid_utc"]: p for p in past}
        assert by["2026-09-26T03:00:00Z"]["detail"]["buoy"]["hs_m"] == 1.0
        assert by["2026-09-26T06:00:00Z"]["detail"] is None

    def test_old_months_are_not_opened(self, tmp_path):
        tmp_path.mkdir(exist_ok=True)
        (tmp_path / "2026-07.jsonl").write_text("not json\n")
        forecastlog.append_shown(forecast(CYCLE, GENERATED), tmp_path)
        assert forecastlog.read_shown(tmp_path, since="2026-09-24T00:00:00Z")


class TestTheSeed:
    """Builds logged before the shown log existed are filled from what the
    delivery repository published -- only where that file IS the logged build."""

    def test_a_published_file_matching_the_log_is_seeded(self, tmp_path):
        f = forecast(CYCLE, GENERATED, hours=24)
        forecastlog.append(f, forecastlog.log_dir(tmp_path))
        published = publish.thin(f)
        report = forecastlog.seed_shown([published], tmp_path)
        assert "headlines match" in report[0] and "seeded" in report[0]
        assert forecastlog.read_shown(forecastlog.shown_dir(tmp_path))
        assert "already seeded" in forecastlog.seed_shown([published], tmp_path)[0]

    def test_a_file_whose_headlines_differ_is_refused(self, tmp_path):
        forecastlog.append(forecast(CYCLE, GENERATED, hours=24), forecastlog.log_dir(tmp_path))
        other = forecast(CYCLE, GENERATED, hours=24, base=1.5)
        assert "differ" in forecastlog.seed_shown([other], tmp_path)[0]
        assert not forecastlog.read_shown(forecastlog.shown_dir(tmp_path))

    def test_an_unlogged_build_is_refused(self, tmp_path):
        report = forecastlog.seed_shown([forecast(CYCLE, GENERATED)], tmp_path)
        assert "not in the headline log" in report[0]
