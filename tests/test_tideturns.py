"""The tide's next turn, and why its direction is not measured.

The card says "rising to 5.6 ft at 11:42 AM". Both halves of that sentence
come from the same harmonic prediction, on purpose: a direction differenced
from the measured water level and a target read from the model can disagree,
and they disagree worst at the turn, which is when someone is looking.
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from forecast.tideturns import (
    Turn, next_turn, read_turns, turns_between, turns_path,
)

UTC = timezone.utc


def write(tmp_path: Path, rows: list[tuple[str, float, str]], station="9410170") -> Path:
    path = turns_path(tmp_path, station)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["time_utc", "first_seen_utc", "height_m", "kind", "datum", "event"])
        for stamp, height, event in rows:
            w.writerow([stamp, "2026-09-19T06:00:00Z", f"{height:.3f}",
                        "predicted", "MLLW", event])
    return path


ROWS = [
    ("2026-09-19T11:42:00Z", 1.712, "high"),
    ("2026-09-19T18:06:00Z", 0.134, "low"),
    ("2026-09-20T00:18:00Z", 1.401, "high"),
]


class TestTheDirectionComesFromTheTurn:
    def test_a_high_is_risen_into_and_a_low_fallen_into(self):
        assert Turn("2026-09-19T11:42:00Z", 1.712, "high").direction == "rising"
        assert Turn("2026-09-19T18:06:00Z", 0.134, "low").direction == "falling"

    def test_an_unrecognised_event_names_no_direction(self):
        """CO-OPS emits HH and LL at some stations. A turn whose direction
        cannot be named is left unnamed rather than guessed, and the surfaces
        render nothing for it."""

        assert Turn("2026-09-19T11:42:00Z", 1.712, "hh").direction is None

    def test_the_direction_ships_in_the_json_rather_than_being_re_derived(self):
        """Two surfaces read this. Deriving 'rising' from 'high' in each of
        them is how the two drift apart."""

        assert Turn("2026-09-19T11:42:00Z", 1.712, "high").as_dict()["direction"] == "rising"


class TestReadingTheArchive:
    def test_a_missing_file_is_empty_not_an_error(self, tmp_path):
        assert read_turns(tmp_path, "9410170") == []

    def test_rows_are_returned_oldest_first(self, tmp_path):
        write(tmp_path, list(reversed(ROWS)))
        got = read_turns(tmp_path, "9410170")
        assert [t.valid_utc for t in got] == [r[0] for r in ROWS]

    def test_a_row_without_an_event_is_dropped(self, tmp_path):
        write(tmp_path, ROWS + [("2026-09-20T06:00:00Z", 0.2, "")])
        assert len(read_turns(tmp_path, "9410170")) == 3

    def test_an_unparseable_row_is_skipped_not_zero_filled(self, tmp_path):
        path = write(tmp_path, ROWS)
        with path.open("a", encoding="utf-8") as fh:
            fh.write("not-a-time,x,not-a-height,predicted,MLLW,high\n")
        assert len(read_turns(tmp_path, "9410170")) == 3

    def test_there_is_no_fallback_to_the_hourly_predictions(self, tmp_path):
        """Deriving a turn from the hourly grid puts its time up to 29.4 min
        out. A surface that silently swapped one for the other would present
        the worse number in the same words as the better one."""

        hourly = tmp_path / "tide" / "9410170_predicted.csv"
        hourly.parent.mkdir(parents=True, exist_ok=True)
        hourly.write_text(
            "time_utc,first_seen_utc,height_m,kind,datum\n"
            "2026-09-19T12:00:00Z,2026-09-19T06:00:00Z,1.700,predicted,MLLW\n"
        )
        assert read_turns(tmp_path, "9410170") == []


class TestPickingTheNextOne:
    TURNS = [Turn(*r) for r in ROWS]

    def test_it_is_the_first_turn_strictly_after_the_moment(self):
        got = next_turn(self.TURNS, datetime(2026, 9, 19, 9, 0, tzinfo=UTC))
        assert got.valid_utc == "2026-09-19T11:42:00Z" and got.direction == "rising"

    def test_a_moment_past_a_turn_gets_the_one_after_it(self):
        got = next_turn(self.TURNS, datetime(2026, 9, 19, 12, 0, tzinfo=UTC))
        assert got.event == "low"

    def test_a_moment_exactly_on_a_turn_gets_the_next_one(self):
        """At slack water the turn being reached is no longer the one being
        run toward."""

        got = next_turn(self.TURNS, datetime(2026, 9, 19, 11, 42, tzinfo=UTC))
        assert got.event == "low"

    def test_past_the_archive_there_is_no_next_turn(self, ):
        """None, not the last one. The tail of the collected window is a gap
        and a gap is a gap."""

        assert next_turn(self.TURNS, datetime(2026, 9, 25, tzinfo=UTC)) is None

    def test_an_empty_archive_yields_nothing(self):
        assert next_turn([], datetime(2026, 9, 19, tzinfo=UTC)) is None


class TestTheWindowCarriesOnePast:
    TURNS = [Turn(*r) for r in ROWS]

    def test_the_last_hour_on_screen_still_has_a_next_turn(self):
        """It lies beyond the window by definition, so a window clipped at the
        end would leave the final hour with nothing to say."""

        got = turns_between(
            self.TURNS,
            datetime(2026, 9, 19, 6, tzinfo=UTC),
            datetime(2026, 9, 19, 15, tzinfo=UTC),
        )
        assert [t.event for t in got] == ["high", "low"]
        assert next_turn(got, datetime(2026, 9, 19, 15, tzinfo=UTC)) is not None

    def test_turns_before_the_window_are_dropped(self):
        got = turns_between(
            self.TURNS,
            datetime(2026, 9, 19, 15, tzinfo=UTC),
            datetime(2026, 9, 20, 12, tzinfo=UTC),
        )
        assert [t.event for t in got] == ["low", "high"]

    def test_an_empty_archive_yields_an_empty_window(self):
        assert turns_between([], datetime(2026, 9, 19, tzinfo=UTC),
                             datetime(2026, 9, 20, tzinfo=UTC)) == []


class TestWhyTheDirectionIsNotDifferenced:
    """The numbers behind the design, pinned against the measured series this
    project actually collects, so the decision can be re-checked rather than
    taken on trust. If a future gauge or a longer archive makes differencing
    reliable, this test is where that shows up."""

    def measured(self):
        path = Path("data/tide/9410170_observed.csv")
        if not path.exists():
            pytest.skip("measured water level not collected")
        rows = []
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                try:
                    rows.append((
                        datetime.strptime(row["time_utc"], "%Y-%m-%dT%H:%M:%SZ")
                            .replace(tzinfo=UTC),
                        float(row["height_m"]),
                    ))
                except (ValueError, KeyError):
                    continue
        return sorted(rows)

    def test_differencing_two_samples_reads_the_tide_backwards_often(self):
        rows = self.measured()
        if len(rows) < 300:
            pytest.skip("archive too short to measure a trend against")
        by = dict(rows)
        wrong = total = 0
        for t, h in rows:
            before = [v for s, v in rows if timedelta(minutes=-66) <= s - t <= timedelta(minutes=-54)]
            after = [v for s, v in rows if timedelta(minutes=54) <= s - t <= timedelta(minutes=66)]
            if not before or not after:
                continue
            truth = after[0] - before[0]
            if abs(truth) < 0.02:          # genuinely at the turn
                continue
            prev = by.get(t - timedelta(minutes=6))
            if prev is None:
                continue
            total += 1
            if (h - prev) * truth < 0:
                wrong += 1
        assert total > 100
        assert wrong / total > 0.10, (
            f"differencing got the direction right {100*(1-wrong/total):.1f}% of the "
            f"time; if that has genuinely improved, the design note in "
            f"forecast/tideturns.py needs revisiting rather than this assertion "
            f"being relaxed"
        )
