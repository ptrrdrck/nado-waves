"""Tests for the observed reading.

The reason this file exists separately from `forecast.live` is the reason
these tests matter: `now` claims to be built only from measurements, and the
easiest way to break it is for a model to leak in — a harmonic tide prediction
standing in for a measured water level, or a stale spectrum served behind an
HTTP 200 and rendered as current (BRIEFING §8).
"""

from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from forecast import now as now_mod
from forecast.geometry import load
from forecast.transform import Spectrum

SPOTS, BLOCKERS = load()
MOMENT = datetime(2026, 9, 19, 0, 30, tzinfo=timezone.utc)


def spectrum(at: datetime, *, peak_dir: float = 200.0, tp: float = 15.0,
             hs: float = 1.2, bins: int = 48) -> Spectrum:
    freqs = [0.025 + 0.0075 * i for i in range(bins)]
    fp = 1.0 / tp
    sigma = math.radians(20.0)
    r1 = math.exp(-0.5 * sigma * sigma)
    r2 = math.exp(-2.0 * sigma * sigma)
    c11 = [math.exp(-1.25 * (fp / f) ** 4) * (f / fp) ** -5 for f in freqs]
    m0 = sum(c * (freqs[1] - freqs[0]) for c in c11)
    c11 = [c * ((hs / 4.0) ** 2 / m0) for c in c11]
    return Spectrum(at, freqs, c11, [peak_dir] * bins, [peak_dir] * bins,
                    [r1] * bins, [r2] * bins)


def write_tide(tmp_path: Path, rows, kind="observed"):
    path = tmp_path / "tide" / f"{now_mod.TIDE_STATION}_{kind}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["time_utc", "first_seen_utc", "height_m", "kind", "datum"])
        w.writeheader()
        for when, height in rows:
            w.writerow({"time_utc": when, "first_seen_utc": when,
                        "height_m": height, "kind": kind, "datum": "MLLW"})
    return path


class TestStaleIsNotNow:
    """NDBC has served 306-hour-old content behind an HTTP 200."""

    def test_a_fresh_spectrum_is_usable(self, tmp_path):
        got = now_mod.build(data_dir=tmp_path, now=MOMENT,
                            spectrum=spectrum(MOMENT - timedelta(hours=1)))
        assert not got.stale and got.usable
        assert got.age_hours == pytest.approx(1.0, abs=0.01)

    def test_an_old_spectrum_is_marked_stale_and_says_so(self, tmp_path):
        got = now_mod.build(data_dir=tmp_path, now=MOMENT,
                            spectrum=spectrum(MOMENT - timedelta(hours=9)))
        assert got.stale and not got.usable
        assert any("not current" in w for w in got.warnings)

    def test_the_boundary_is_the_documented_limit(self, tmp_path):
        inside = now_mod.build(data_dir=tmp_path, now=MOMENT,
                               spectrum=spectrum(MOMENT - timedelta(hours=now_mod.STALE_HOURS - 0.1)))
        outside = now_mod.build(data_dir=tmp_path, now=MOMENT,
                                spectrum=spectrum(MOMENT - timedelta(hours=now_mod.STALE_HOURS + 0.1)))
        assert not inside.stale and outside.stale

    def test_stale_still_reports_the_breaks_rather_than_hiding_them(self, tmp_path):
        """The surface decides what to show. The data layer says how old it is
        and refuses to call it current; it does not silently empty itself."""

        got = now_mod.build(data_dir=tmp_path, now=MOMENT,
                            spectrum=spectrum(MOMENT - timedelta(hours=9)))
        assert len(got.breaks) == 3
        assert got.stale

    def test_no_spectrum_at_all_is_reported_not_faked(self, tmp_path):
        got = now_mod.build(data_dir=tmp_path, now=MOMENT)
        assert got.breaks == [] and got.observed_utc is None
        assert any("no 'now'" in w or "no usable spectrum" in w for w in got.warnings)


class TestTideIsAMeasurementNotAPrediction:
    def test_it_reads_the_observed_file_not_the_predicted_one(self, tmp_path):
        write_tide(tmp_path, [("2026-09-19T00:24:00Z", "1.476")], kind="observed")
        write_tide(tmp_path, [("2026-09-19T00:24:00Z", "9.999")], kind="predicted")
        got = now_mod.build(data_dir=tmp_path, now=MOMENT, spectrum=spectrum(MOMENT))
        assert got.tide.height_m == 1.476
        assert got.tide.kind == "observed"

    def test_only_a_predicted_file_yields_no_tide_rather_than_a_model(self, tmp_path):
        write_tide(tmp_path, [("2026-09-19T00:24:00Z", "1.476")], kind="predicted")
        got = now_mod.build(data_dir=tmp_path, now=MOMENT, spectrum=spectrum(MOMENT))
        assert got.tide.height_m is None
        assert any("water level" in w for w in got.warnings)

    def test_it_takes_the_newest_row_not_the_last_written(self, tmp_path):
        write_tide(tmp_path, [("2026-09-19T00:24:00Z", "1.476"),
                              ("2026-09-19T00:00:00Z", "1.100")])
        got = now_mod.build(data_dir=tmp_path, now=MOMENT, spectrum=spectrum(MOMENT))
        assert got.tide.height_m == 1.476

    def test_a_stalled_gauge_is_flagged(self, tmp_path):
        write_tide(tmp_path, [("2026-09-18T12:00:00Z", "1.000")])
        got = now_mod.build(data_dir=tmp_path, now=MOMENT, spectrum=spectrum(MOMENT))
        assert "old" in got.tide.note

    def test_a_blank_height_is_skipped_not_zeroed(self, tmp_path):
        write_tide(tmp_path, [("2026-09-19T00:24:00Z", ""),
                              ("2026-09-19T00:18:00Z", "1.2")])
        got = now_mod.build(data_dir=tmp_path, now=MOMENT, spectrum=spectrum(MOMENT))
        assert got.tide.height_m == 1.2


class TestItSaysItIsObserved:
    def test_every_input_is_named_as_an_observation(self, tmp_path):
        got = now_mod.build(data_dir=tmp_path, now=MOMENT, spectrum=spectrum(MOMENT))
        for key in ("waves", "wind", "tide"):
            assert got.standing_on[key].startswith("OBSERVED")

    def test_the_beach_is_still_unobserved_and_it_says_so(self, tmp_path):
        """The word 'observed' appearing three times above must not let this
        line lose its force — it is the rule the whole project runs on."""

        got = now_mod.build(data_dir=tmp_path, now=MOMENT, spectrum=spectrum(MOMENT))
        assert got.standing_on["observation at the beach"].startswith("none")
        assert "beach_log" in got.standing_on["observation at the beach"]

    def test_no_assumed_spread_appears_anywhere(self, tmp_path):
        """The spectrum carries measured r1/r2, so BRIEFING §11's weakest
        number is simply absent from this path."""

        got = now_mod.build(data_dir=tmp_path, now=MOMENT, spectrum=spectrum(MOMENT))
        assert "no assumed spread" in got.standing_on["waves"]
        assert "spread" not in json.dumps([b.__dict__ for b in got.breaks])

    def test_the_claim_does_not_say_accurate(self, tmp_path):
        got = now_mod.build(data_dir=tmp_path, now=MOMENT, spectrum=spectrum(MOMENT))
        assert "accurate" not in json.dumps(got.standing_on).lower()


class TestTheApertureStillApplies:
    def test_all_three_breaks_are_reported(self, tmp_path):
        got = now_mod.build(data_dir=tmp_path, now=MOMENT, spectrum=spectrum(MOMENT))
        assert [b.id for b in got.breaks] == list(now_mod.BREAKS)

    def test_a_west_swell_separates_the_breaks(self, tmp_path):
        got = now_mod.build(data_dir=tmp_path, now=MOMENT,
                            spectrum=spectrum(MOMENT, peak_dir=255.0))
        heights = [b.hs_in_window_m for b in got.breaks]
        assert heights[2] > heights[1] > heights[0]

    def test_the_buoys_own_reading_is_published_beside_the_breaks(self, tmp_path):
        """So a reader can see how much of the answer is geometry."""

        got = now_mod.build(data_dir=tmp_path, now=MOMENT, spectrum=spectrum(MOMENT))
        assert got.buoy["hs_m"] > 0
        assert all(b.hs_in_window_m <= got.buoy["hs_m"] for b in got.breaks)

    def test_the_peak_is_taken_after_the_aperture(self, tmp_path):
        """On a day the geometry shadows the biggest train, the break's peak is
        a different wave from the buoy's — that difference is the claim."""

        got = now_mod.build(data_dir=tmp_path, now=MOMENT, spectrum=spectrum(MOMENT))
        assert got.breaks[0].peak_period_s is not None
        assert got.breaks[0].peak_direction_deg is not None


class TestOutput:
    def test_json_round_trips(self, tmp_path):
        got = now_mod.build(data_dir=tmp_path, now=MOMENT, spectrum=spectrum(MOMENT))
        path = tmp_path / "live" / "now.json"
        now_mod.write(got, path)
        blob = json.loads(path.read_text())
        assert blob["station"] == now_mod.STATION
        assert len(blob["breaks"]) == 3

    def test_the_table_labels_the_three_breaks_distinctly(self, tmp_path):
        got = now_mod.build(data_dir=tmp_path, now=MOMENT, spectrum=spectrum(MOMENT))
        text = now_mod.format_table(got)
        for label in ("north", "center", "south"):
            assert label in text

    def test_the_table_marks_a_stale_reading(self, tmp_path):
        got = now_mod.build(data_dir=tmp_path, now=MOMENT,
                            spectrum=spectrum(MOMENT - timedelta(hours=9)))
        assert "STALE" in now_mod.format_table(got)

    def test_the_table_never_calls_it_a_height_at_the_beach(self, tmp_path):
        got = now_mod.build(data_dir=tmp_path, now=MOMENT, spectrum=spectrum(MOMENT))
        text = " ".join(now_mod.format_table(got).split())
        assert "never measured at the beach itself" in text


class TestWaveTrains:
    """A reader wants to know which swell is running their break, and that is
    not always the one running the buoy."""

    def test_the_buoy_reading_carries_its_trains(self, tmp_path):
        got = now_mod.build(data_dir=tmp_path, now=MOMENT, spectrum=spectrum(MOMENT))
        assert got.buoy["trains"]
        first = got.buoy["trains"][0]
        assert {"hs_m", "period_s", "from_deg", "share", "wind_sea"} <= set(first)

    def test_every_break_carries_its_own_trains(self, tmp_path):
        got = now_mod.build(data_dir=tmp_path, now=MOMENT, spectrum=spectrum(MOMENT))
        assert all(b.trains for b in got.breaks)

    def test_a_breaks_trains_are_no_larger_than_the_buoys(self, tmp_path):
        """The aperture only ever removes energy."""

        got = now_mod.build(data_dir=tmp_path, now=MOMENT, spectrum=spectrum(MOMENT))
        biggest_at_buoy = max(t["hs_m"] for t in got.buoy["trains"])
        for entry in got.breaks:
            assert max(t["hs_m"] for t in entry.trains) <= biggest_at_buoy + 1e-9

    def test_trains_are_ordered_largest_first(self, tmp_path):
        got = now_mod.build(data_dir=tmp_path, now=MOMENT, spectrum=spectrum(MOMENT))
        for entry in got.breaks:
            heights = [t["hs_m"] for t in entry.trains]
            assert heights == sorted(heights, reverse=True)

    def test_the_table_lists_the_buoys_trains(self, tmp_path):
        got = now_mod.build(data_dir=tmp_path, now=MOMENT, spectrum=spectrum(MOMENT))
        assert "swell trains at the buoy" in now_mod.format_table(got)


class TestTheBuoyViewIsUnclipped:
    """`through(spectrum, spot, [])` still applies the spot's seaward
    half-plane, so using it for "what the buoy saw" dropped everything
    arriving from behind that beach — 12-26% of the energy across the
    archive. The headline Hs stayed whole, so the symptom was a train list
    that did not sum to the number above it."""

    def test_the_trains_sum_to_the_headline(self, tmp_path):
        got = now_mod.build(data_dir=tmp_path, now=MOMENT, spectrum=spectrum(MOMENT))
        from_trains = math.sqrt(sum((t["hs_m"] / 4.0) ** 2 for t in got.buoy["trains"]))
        assert 4.0 * from_trains == pytest.approx(got.buoy["hs_m"], rel=0.08)

    def test_it_does_not_go_through_a_spot(self):
        import inspect

        source = inspect.getsource(now_mod.build)
        assert "at_buoy(spectrum)" in source
        assert "through(spectrum, by_id[BREAKS[1]], [])" not in source

    def test_a_northerly_swell_is_not_dropped(self, tmp_path):
        """The clip excluded 304-124 degrees, which is where NW swell lives —
        3,771 hours of it in the archive (BRIEFING §2)."""

        north = spectrum(MOMENT, peak_dir=320.0)
        got = now_mod.build(data_dir=tmp_path, now=MOMENT, spectrum=north)
        assert got.buoy["hs_m"] > 0.5
        assert got.buoy["trains"]
        # And the beaches still get almost none of it.
        assert all(b.fraction < 0.35 for b in got.breaks)


class TestWhenEachSourceIsNextDue:
    """`next_expected` is what the surface counts down to. It is an expectation
    about ARRIVAL, computed per source, and deliberately not a claim that the
    reading is still good — `stale` is that, separately."""

    def test_it_is_an_instant_not_a_duration(self):
        """A "in 42 minutes" baked into a file rebuilt every ten minutes is
        wrong for most of the time it is on screen. BRIEFING §18, already paid
        for once."""

        got = now_mod.next_expected("2026-09-19T00:00:00Z", "wind")
        assert got == "2026-09-19T01:20:00Z"   # 60 source + 10 collect + 10 slack

    def test_the_deadline_includes_the_time_it_takes_to_COLLECT(self):
        """The term that is easy to leave out, and was.

        KNZY publishes at :52. A collector that visits ten minutes later is not
        late, it is a collector — but a deadline of observed+60 has already
        passed by then, so every card went red for a few minutes of every cycle
        with nothing wrong. A deadline a healthy system misses on schedule
        teaches a reader to ignore it."""

        taken = "2026-09-19T00:00:00Z"
        for name, src in now_mod.SOURCE_INTERVAL_MIN.items():
            due = datetime.strptime(now_mod.next_expected(taken, name), now_mod.ISO)
            gap = (due - datetime.strptime(taken, now_mod.ISO)).total_seconds() / 60
            assert gap > src, f"{name} allows no time to fetch the next reading"

    def test_a_healthy_cycle_never_reaches_its_deadline(self):
        """The property the whole change exists for. Worst case in normal
        operation: a reading is taken, the collector misses one cycle, and
        catches it on the next. That must still land inside the deadline."""

        taken = datetime(2026, 9, 19, 0, 52, tzinfo=timezone.utc)
        for name, src in now_mod.SOURCE_INTERVAL_MIN.items():
            due = datetime.strptime(
                now_mod.next_expected(taken.strftime(now_mod.ISO), name), now_mod.ISO
            ).replace(tzinfo=timezone.utc)
            # next reading exists at taken+src; seen one missed cycle later.
            worst = taken + timedelta(
                minutes=src + now_mod.COLLECT_INTERVAL_MIN * (1 + now_mod.MISSED_CYCLES_TOLERATED)
            )
            assert worst <= due, f"{name} would redden on a healthy cycle"

    def test_the_tolerance_is_small_enough_to_still_catch_a_dead_source(self):
        """Widening the slack to cover the scheduler's real behaviour — 28%
        delivery, 3.8 h median gap — would make the countdown agree with the
        collector no matter how badly the collector was doing. One cycle."""

        assert now_mod.MISSED_CYCLES_TOLERATED == 1

    def test_the_tide_is_not_promised_its_own_six_minutes(self):
        """CO-OPS measures every 6 minutes and this project collects every 10.
        A countdown promising the source's cadence would reach zero before
        anything could possibly appear."""

        assert now_mod.SOURCE_INTERVAL_MIN["tide"] == 6
        got = now_mod.next_expected("2026-09-19T00:00:00Z", "tide")
        assert got == "2026-09-19T00:26:00Z"   # 6 + 10 + 10, not 6

    def test_a_missing_or_unparseable_reading_expects_nothing(self):
        assert now_mod.next_expected(None, "tide") is None
        assert now_mod.next_expected("not-a-timestamp", "tide") is None
        assert now_mod.next_expected("2026-09-19T00:00:00Z", "nonesuch") is None

    def test_each_card_tracks_its_own_source(self, tmp_path):
        """The whole point of three countdowns rather than one banner: when a
        single source stops, only its card runs overdue. 46232 went dark for
        16.2 days while wind and tide kept arriving."""

        got = now_mod.build(data_dir=tmp_path, now=MOMENT,
                            spectrum=spectrum(MOMENT))
        assert set(got.next_expected) == {"swell", "wind", "tide"}
        # The spectrum is the only source with a reading in this fixture, so it
        # is the only one that can name a deadline.
        assert got.next_expected["swell"] == "2026-09-19T01:50:00Z"
        assert got.next_expected["wind"] is None
        assert got.next_expected["tide"] is None

    def test_the_deadline_follows_the_reading_not_the_build(self, tmp_path):
        """An old reading does not get a fresh deadline because the build ran.
        If it did, a dead source would look punctual for as long as the
        collector kept publishing."""

        old = MOMENT - timedelta(hours=9)
        got = now_mod.build(data_dir=tmp_path, now=MOMENT, spectrum=spectrum(old))
        assert got.next_expected["swell"] == "2026-09-18T16:50:00Z"
        assert got.next_expected["swell"] < got.generated_utc
        assert got.stale

    def test_the_promised_cadence_matches_the_schedule_that_keeps_it(self):
        """The bug this pins cost half a day of cards that were red for no
        reason: the workflow asked for `*/10` while GitHub delivered about one
        run every four hours, and COLLECT_INTERVAL_MIN said 10 to match the
        request rather than the reality.

        The trigger is now external, so what the countdown must agree with is
        EXTERNAL_TRIGGER_CRON, not the workflow. Nothing here can reach
        cron-job.org to check that constant is true -- keeping it true is a
        human obligation, stated where it is declared. What a test CAN do is
        refuse to let the two numbers drift apart in the file."""

        minute = now_mod.EXTERNAL_TRIGGER_CRON.split()[0]
        if minute.startswith("*/"):
            every = int(minute[2:])
        elif "," in minute:
            marks = sorted(int(m) for m in minute.split(","))
            gaps = {b - a for a, b in zip(marks, marks[1:])}
            gaps.add(60 - marks[-1] + marks[0])
            assert len(gaps) == 1, f"{minute} is not evenly spaced: gaps {gaps}"
            every = gaps.pop()
        else:
            every = 60

        assert now_mod.COLLECT_INTERVAL_MIN == every, (
            f"external trigger runs every {every} min, COLLECT_INTERVAL_MIN "
            f"says {now_mod.COLLECT_INTERVAL_MIN}"
        )

    def test_the_github_cron_is_a_backstop_and_not_the_promise(self):
        """GitHub throttles scheduled runs to about 0.2 an hour whatever the
        cron asks, so a workflow schedule written to match the promised cadence
        would be a promise GitHub cannot keep. It must be slower, and the
        countdown must not be derived from it."""

        import re
        from pathlib import Path

        workflow = (Path(__file__).resolve().parent.parent
                    / ".github" / "workflows" / "collect-beach-inputs.yml").read_text()
        crons = re.findall(r'- cron: "([^"]+)"', workflow)
        assert len(crons) == 1, f"expected one backstop schedule, found {crons}"

        minute, hour = crons[0].split()[0], crons[0].split()[1]
        assert not minute.startswith("*/"), (
            f"backstop cron {crons[0]!r} asks for sub-hourly runs GitHub will not deliver"
        )
        assert "," not in minute and hour == "*", (
            f"backstop cron {crons[0]!r} is not the plain hourly schedule expected"
        )
        assert now_mod.COLLECT_INTERVAL_MIN < 60, (
            "the external trigger should be faster than the hourly backstop; "
            "if it is not, the backstop is the real trigger and this file is "
            "describing a schedule nobody keeps"
        )

    def test_the_phase_is_spent_on_the_source_that_is_pinned(self):
        """The spectra jitter across roughly H+7..H+27, so no offset can be
        right for them on every hour -- only the interval bounds their
        staleness. KNZY's :52 is pinned, so the offset is chosen there: the
        last run of each hour must land after :52 and inside the same hour."""

        lo, hi = now_mod.SPECTRA_PUBLISHED_MIN
        assert hi - lo >= 10, (
            "if the spectra stopped jittering, phase-locking to them would beat "
            "spending the offset on the wind — revisit this"
        )

        marks = sorted(int(m) for m in now_mod.EXTERNAL_TRIGGER_CRON.split()[0].split(","))
        assert 52 < marks[-1] <= 59, (
            f"last run of the hour is :{marks[-1]:02d}; KNZY publishes at :52 and "
            f"would wait for the next hour"
        )
        assert marks[-1] - 52 <= 5, (
            f"last run is {marks[-1] - 52} min after KNZY's :52 — the offset is "
            f"the only thing buying that, so it should be tight"
        )
