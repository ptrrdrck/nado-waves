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

    def test_each_break_carries_its_own_shore_normal(self, tmp_path):
        """The page turns each break's drawing to face its own normal, and
        the three span 27 degrees, so one shared figure would misdraw two."""

        normals = {s.id: round(s.normal, 1) for s in SPOTS}
        got = now_mod.build(data_dir=tmp_path, now=MOMENT, spectrum=spectrum(MOMENT))
        for b in got.breaks:
            assert b.shore_normal_deg == normals[b.id]
            assert b.normal_is_a_guess is False


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
        assert "never measured at the beach" in text
        assert "not a surf height" in text


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

    def test_the_straight_line_window_never_exceeds_the_buoy(self, tmp_path):
        """The aperture only ever removes energy. The nearshore number may
        exceed it, legitimately: shoaling into 5 m lifts long-period swell, so
        the old "no larger than the buoy" rule now holds for the window only."""

        got = now_mod.build(data_dir=tmp_path, now=MOMENT, spectrum=spectrum(MOMENT))
        for entry in got.breaks:
            assert entry.hs_in_window_m <= got.buoy["hs_m"] + 1e-9
            effects = entry.nearshore["effects"]
            assert effects["window_hs_m"] == pytest.approx(entry.hs_in_window_m, abs=1e-3)

    def test_each_break_carries_the_chain_from_buoy_to_nearshore(self, tmp_path):
        got = now_mod.build(data_dir=tmp_path, now=MOMENT, spectrum=spectrum(MOMENT))
        for entry in got.breaks:
            effects = entry.nearshore["effects"]
            assert set(effects) >= {"buoy_hs_m", "window_hs_m", "seabed_hs_m",
                                    "shoaled_hs_m", "islands_pct", "local"}
            assert entry.hs_nearshore_m == entry.nearshore["hs_m"]
            assert entry.nearshore["depth_m"] == pytest.approx(5.0, abs=0.2)

    def test_the_shipped_spread_is_maximum_entropy(self, tmp_path):
        got = now_mod.build(data_dir=tmp_path, now=MOMENT, spectrum=spectrum(MOMENT))
        assert "maximum entropy" in got.standing_on["waves"]
        assert got.standing_on["seabed"].startswith("MODELLED")

    def test_trains_are_ordered_largest_first(self, tmp_path):
        got = now_mod.build(data_dir=tmp_path, now=MOMENT, spectrum=spectrum(MOMENT))
        for entry in got.breaks:
            # Local chop is appended after the swell trains, tagged; the
            # swell trains themselves are largest first.
            heights = [t["hs_m"] for t in entry.trains if not t.get("local")]
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
    """`next_expected` is what the surface counts down to. Three real events on
    the clock -- the next publish, the lag until it is fetchable, the next
    collection -- rather than intervals added to the reading on screen."""

    def test_it_lands_on_the_next_collection_after_the_next_publish(self):
        """The tide publishes every six minutes from :00 and is collected at
        :05/:15/:25/:35/:45/:55. A sample stamped :24 is followed by one at :30,
        which CO-OPS does not write at :30 -- the measured floor is about five
        minutes -- so it becomes fetchable at :35 and the :35 run carries it.

        The LATE bound is what differs: eight minutes puts it at :38, and the
        next collection is still :45. So `overdue_after` sits a slot behind, and
        the card has a real window in which the update is due without being a
        fault."""

        assert now_mod.next_expected("2026-09-25T04:24:00Z", "tide") == "2026-09-25T04:35:00Z"

    def test_no_source_is_charged_slack_on_top_of_the_rounding(self):
        """The bug this replaces, stated as a mechanism rather than a number.

        The old formula added `source interval + 2 x collection interval` to the
        reading on screen: a tide sample due in ninety seconds was charged a
        full six minutes and then twenty more as slack. The slack term is gone,
        and what bounds it now is that rounding up to a collection mark can only
        ever cost LESS than one collection interval -- never two, and never a
        fixed cushion on top.

        Deliberately not asserted as "the tide waits under N minutes". It can
        legitimately wait 21: six for the next sample, seven until CO-OPS
        publishes it, eight to the following collection. Every one of those is
        measured, and an assertion on the total would fail on a real lag
        rather than on an invented one."""

        for source, marks in now_mod.PUBLISH_MINUTES.items():
            lag = timedelta(minutes=now_mod.PUBLISH_LAG_MIN.get(source, 0))
            for minute in range(60):
                stamped = f"2026-09-25T04:{minute:02d}:00Z"
                due = datetime.strptime(now_mod.next_expected(stamped, source), now_mod.ISO)
                published = now_mod._next_mark(
                    datetime.strptime(stamped, now_mod.ISO), marks
                )
                fetchable = published + lag
                rounding = (due - fetchable).total_seconds() / 60
                assert 0 <= rounding < now_mod.COLLECT_INTERVAL_MIN, (
                    f"{source} stamped :{minute:02d} is fetchable at "
                    f"{fetchable:%H:%M} but not promised until {due:%H:%M} -- "
                    f"{rounding:.0f} min of rounding against a "
                    f"{now_mod.COLLECT_INTERVAL_MIN}-minute cadence"
                )

    def test_the_wind_waits_for_its_own_minute(self):
        """KNZY publishes at :52 and nowhere else, so a 03:52 reading is not
        followed until 04:52 however often anything is collected. The :55 run
        is the first that can carry it."""

        assert now_mod.next_expected("2026-09-25T03:52:00Z", "wind") == "2026-09-25T04:55:00Z"

    @pytest.mark.parametrize(
        "source,path,stamp_column",
        [
            ("tide", "data/tide/9410170_observed.csv", "time_utc"),
            ("wind", "data/wind/KNZY.csv", "observed_utc"),
        ],
    )
    def test_no_source_claims_a_lag_the_archive_has_never_achieved(
        self, source, path, stamp_column
    ):
        """The bug that produced a red tide card on a reading eight minutes old.

        `PUBLISH_LAG_MIN["tide"]` was 0, on the reasoning that the collection
        schedule absorbs whatever lag there is. The archive says otherwise: it
        carries `first_seen_utc` beside every stamp, and the smallest gap
        between them is over four minutes for the tide and over three for the
        wind. Nothing has ever been fetchable at its own stamp minute.

        A lag of zero for a source that is never instant does not merely
        mis-time the countdown, it promises data that does not exist yet, and
        for a six-minute source a seven-minute error costs a whole collection
        slot. So this asserts the shape rather than a number: if the archive has
        never seen a source inside a minute of its stamp, the model may not
        claim it is fetchable there.

        Measured (bracketing each sample between the last collection without it
        and the first with it) the tide runs about H+3 to H+7 and the wind sits
        near H+3; the constants take the upper end, as the swell's 27 does."""

        rows = list(csv.DictReader((Path(path)).open()))
        if not rows:
            pytest.skip(f"{path} is empty")

        gaps = []
        for row in rows:
            try:
                stamp = datetime.strptime(row[stamp_column], now_mod.ISO)
                seen = datetime.strptime(row["first_seen_utc"], now_mod.ISO)
            except (ValueError, KeyError, TypeError):
                continue
            gaps.append((seen - stamp).total_seconds() / 60)

        assert gaps, f"{path} has no usable first_seen_utc"
        floor = min(gaps)
        if floor <= 1.0:
            pytest.skip(f"{source} has been seen at its own stamp ({floor:.1f} min)")

        assert now_mod.PUBLISH_LAG_MIN[source] >= int(floor), (
            f"{source} is modelled as fetchable {now_mod.PUBLISH_LAG_MIN[source]} "
            f"min after its stamp, but the archive has never had one sooner "
            f"than {floor:.1f} min -- the countdown is promising a reading the "
            f"source has not published"
        )

    def test_the_swell_is_charged_its_publication_jitter_at_both_ends(self):
        """The spectrum stamped 05:00 is not fetchable at 05:00. Bracketed
        against the collection log, four of six measured hours landed by H+15
        and one took until H+35.3 -- so the two ends of SPECTRA_PUBLISHED_MIN
        carry the two deadlines, the typical one for the countdown and the
        measured worst for the accusation.

        The single value that used to do both was 27: above the typical, below
        the observed worst, and therefore wrong for both jobs at once. It made
        an hourly source promise 100 minutes from stamp to screen when 80 was
        honest, and it would still have gone red on the H+35 hour."""

        assert now_mod.PUBLISH_LAG_MIN["swell"] == now_mod.SPECTRA_PUBLISHED_MIN[0]
        assert now_mod.PUBLISH_LAG_LATE_MIN["swell"] == now_mod.SPECTRA_PUBLISHED_MIN[1]
        assert now_mod.next_expected("2026-09-25T04:00:00Z", "swell") == "2026-09-25T05:15:00Z"
        assert now_mod.overdue_after("2026-09-25T04:00:00Z", "swell") == "2026-09-25T05:45:00Z"

    def test_no_source_is_accused_before_it_is_merely_expected(self):
        """`overdue_after` may equal `next_expected` -- at today's cadence the
        tide's two lags round to the same collection -- but it may never precede
        it. A card that reddened before its own countdown expired would be
        accusing a source of missing a deadline it had not reached."""

        for source in now_mod.PUBLISH_MINUTES:
            assert (
                now_mod.PUBLISH_LAG_LATE_MIN[source] >= now_mod.PUBLISH_LAG_MIN[source]
            ), f"{source} is late before it is expected"
            for minute in range(60):
                stamped = f"2026-09-25T04:{minute:02d}:00Z"
                due = now_mod.next_expected(stamped, source)
                late = now_mod.overdue_after(stamped, source)
                assert late >= due, f"{source} stamped :{minute:02d}: {late} < {due}"

    def test_the_publish_minutes_are_the_measured_ones(self):
        """46232 also publishes standard met at :26 and :56. That is a
        different product, in data/observations/, that no card reads -- the Now
        tab's swell is the directional spectrum, stamped on the hour."""

        assert now_mod.PUBLISH_MINUTES["swell"] == (0,)
        assert now_mod.PUBLISH_MINUTES["wind"] == (52,)
        assert now_mod.PUBLISH_MINUTES["tide"] == tuple(range(0, 60, 6))
        assert 26 not in now_mod.PUBLISH_MINUTES["swell"]

    def test_the_collection_marks_come_from_the_trigger_that_keeps_them(self):
        """Not from a second copy of the schedule. The cron is the one place
        the collection times are written down."""

        assert now_mod._collect_minutes() == (5, 15, 25, 35, 45, 55)

    def test_a_deadline_is_never_before_the_reading_it_follows(self):
        """Swept across a whole hour of stamps, for every source: the next
        publish is strictly after the reading, and collection cannot precede
        it."""

        base = datetime(2026, 9, 25, 4, 0, tzinfo=timezone.utc)
        for minute in range(60):
            stamped = (base + timedelta(minutes=minute)).strftime(now_mod.ISO)
            for source in now_mod.PUBLISH_MINUTES:
                due = now_mod.next_expected(stamped, source)
                assert due > stamped, f"{source} at :{minute:02d} due {due} <= {stamped}"

    def test_a_missing_or_unparseable_reading_expects_nothing(self):
        assert now_mod.next_expected(None, "tide") is None
        assert now_mod.next_expected("not-a-timestamp", "tide") is None
        assert now_mod.next_expected("2026-09-25T04:00:00Z", "nonesuch") is None

    def test_each_card_tracks_its_own_source(self, tmp_path):
        """The whole point of three countdowns rather than one banner: when a
        single source stops, only its card runs overdue. 46232 went dark for
        16.2 days while wind and tide kept arriving."""

        got = now_mod.build(data_dir=tmp_path, now=MOMENT,
                            spectrum=spectrum(MOMENT))
        assert set(got.next_expected) == {"swell", "wind", "tide"}
        # The spectrum is the only source with a reading in this fixture, so it
        # is the only one that can name a deadline.
        assert got.next_expected["swell"] is not None
        assert got.next_expected["wind"] is None
        assert got.next_expected["tide"] is None

    def test_the_deadline_follows_the_reading_not_the_build(self, tmp_path):
        """An old reading does not get a fresh deadline because the build ran.
        If it did, a dead source would look punctual for as long as the
        collector kept publishing."""

        old = MOMENT - timedelta(hours=9)
        got = now_mod.build(data_dir=tmp_path, now=MOMENT, spectrum=spectrum(old))
        assert got.next_expected["swell"] < got.generated_utc
        assert got.stale

    def test_there_is_no_slack_term_any_more(self, tmp_path):
        """There used to be one, because GitHub's scheduler delivered about a
        quarter of what it was asked for and a card with no tolerance was red
        more often than not. The trigger is external now and lands on time to
        the second, so a missed collection is a real failure and the card
        should say so."""

        assert not hasattr(now_mod, "MISSED_CYCLES_TOLERATED")

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
