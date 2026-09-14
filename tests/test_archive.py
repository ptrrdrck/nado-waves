import csv
from pathlib import Path

from collector.archive import (
    OBSERVATION_FIELDS,
    merge_station,
    observations_path,
    read_rows,
    revisions_path,
)
from collector.ndbc import parse_realtime2

FIXTURES = Path(__file__).parent / "fixtures"


def sample(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def observations(name: str = "46222_sample.txt"):
    return parse_realtime2(sample(name))


def read_csv_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_first_merge_writes_every_row(tmp_path):
    result = merge_station(tmp_path, "46222", observations(), now="2026-09-12T21:00:00Z")
    assert result.added == 4
    assert result.total_rows == 4
    rows = read_csv_rows(observations_path(tmp_path, "46222"))
    assert [row["timestamp_utc"] for row in rows] == [
        "2026-09-12T17:26:00Z",
        "2026-09-12T18:26:00Z",
        "2026-09-12T19:26:00Z",
        "2026-09-12T20:26:00Z",
    ]
    assert rows[0].keys() == dict.fromkeys(OBSERVATION_FIELDS).keys()


def test_reruns_are_idempotent(tmp_path):
    merge_station(tmp_path, "46222", observations(), now="2026-09-12T21:00:00Z")
    before = observations_path(tmp_path, "46222").read_text()
    result = merge_station(tmp_path, "46222", observations(), now="2026-09-12T22:00:00Z")
    assert result.added == 0
    assert not result.changed
    assert observations_path(tmp_path, "46222").read_text() == before


def test_overlapping_windows_only_append_the_new_rows(tmp_path):
    first = observations()[:2]
    merge_station(tmp_path, "46222", first, now="2026-09-12T19:00:00Z")
    result = merge_station(tmp_path, "46222", observations(), now="2026-09-12T21:00:00Z")
    assert result.added == 2
    assert result.total_rows == 4


def test_first_seen_records_when_we_learned_the_value_and_never_moves(tmp_path):
    merge_station(tmp_path, "46222", observations()[:2], now="2026-09-12T19:00:00Z")
    merge_station(tmp_path, "46222", observations(), now="2026-09-12T21:00:00Z")
    rows = {r["timestamp_utc"]: r for r in read_csv_rows(observations_path(tmp_path, "46222"))}
    assert rows["2026-09-12T17:26:00Z"]["first_seen_utc"] == "2026-09-12T19:00:00Z"
    assert rows["2026-09-12T20:26:00Z"]["first_seen_utc"] == "2026-09-12T21:00:00Z"


def test_revised_value_updates_the_cell_and_is_logged(tmp_path):
    merge_station(tmp_path, "46222", observations(), now="2026-09-12T21:00:00Z")
    revised = parse_realtime2(sample("46222_sample.txt").replace("20.1", "20.4"))
    result = merge_station(tmp_path, "46222", revised, now="2026-09-13T03:00:00Z")

    assert result.revised == 1
    rows = {r["timestamp_utc"]: r for r in read_csv_rows(observations_path(tmp_path, "46222"))}
    assert rows["2026-09-12T20:26:00Z"]["wtmp"] == "20.4"

    log = read_csv_rows(revisions_path(tmp_path, "46222"))
    assert log == [
        {
            "timestamp_utc": "2026-09-12T20:26:00Z",
            "field": "wtmp",
            "old_value": "20.1",
            "new_value": "20.4",
            "observed_at_utc": "2026-09-13T03:00:00Z",
        }
    ]


def test_a_late_filled_value_is_stored_and_logged(tmp_path):
    merge_station(tmp_path, "46222", observations(), now="2026-09-12T21:00:00Z")
    backfilled = parse_realtime2(
        sample("46222_sample.txt").replace(
            "2026 09 12 18 26  MM   MM   MM   0.8  14.3   6.8 201     MM    MM    MM",
            "2026 09 12 18 26  MM   MM   MM   0.8  14.3   6.8 201     MM    MM  20.0",
        )
    )
    result = merge_station(tmp_path, "46222", backfilled, now="2026-09-13T03:00:00Z")

    assert result.revised == 1
    rows = {r["timestamp_utc"]: r for r in read_csv_rows(observations_path(tmp_path, "46222"))}
    assert rows["2026-09-12T18:26:00Z"]["wtmp"] == "20.0"
    assert read_csv_rows(revisions_path(tmp_path, "46222"))[0]["old_value"] == ""


def test_a_published_value_is_never_replaced_by_a_missing_one(tmp_path):
    merge_station(tmp_path, "46222", observations(), now="2026-09-12T21:00:00Z")
    blanked = parse_realtime2(sample("46222_sample.txt").replace("  20.1  ", "    MM  "))
    result = merge_station(tmp_path, "46222", blanked, now="2026-09-13T03:00:00Z")

    assert result.blanked == 1
    rows = {r["timestamp_utc"]: r for r in read_csv_rows(observations_path(tmp_path, "46222"))}
    assert rows["2026-09-12T20:26:00Z"]["wtmp"] == "20.1"
    log = read_csv_rows(revisions_path(tmp_path, "46222"))
    assert log[0]["new_value"] == ""
    assert log[0]["old_value"] == "20.1"


def test_missing_values_are_stored_empty_not_interpolated(tmp_path):
    merge_station(tmp_path, "46222", observations(), now="2026-09-12T21:00:00Z")
    rows = {r["timestamp_utc"]: r for r in read_csv_rows(observations_path(tmp_path, "46222"))}
    assert rows["2026-09-12T18:26:00Z"]["wtmp"] == ""
    neighbours = {rows["2026-09-12T17:26:00Z"]["wtmp"], rows["2026-09-12T19:26:00Z"]["wtmp"]}
    assert neighbours == {"19.9", "20.2"}


def test_newest_water_temperature_skips_trailing_missing_rows(tmp_path):
    text = sample("46222_sample.txt").replace(
        "2026 09 12 20 26  MM   MM   MM   0.7  13.8   6.7 203     MM    MM  20.1",
        "2026 09 12 20 26  MM   MM   MM   0.7  13.8   6.7 203     MM    MM    MM",
    )
    result = merge_station(tmp_path, "46222", parse_realtime2(text), now="2026-09-12T21:00:00Z")
    assert result.newest_timestamp == "2026-09-12T20:26:00Z"
    assert result.newest_primary_timestamp == "2026-09-12T19:26:00Z"


def test_dry_run_writes_nothing(tmp_path):
    result = merge_station(
        tmp_path, "46222", observations(), now="2026-09-12T21:00:00Z", dry_run=True
    )
    assert result.added == 4
    assert not observations_path(tmp_path, "46222").exists()


def test_station_id_is_normalised_to_upper_case(tmp_path):
    merge_station(tmp_path, "bdsp1", observations(), now="2026-09-12T21:00:00Z")
    assert observations_path(tmp_path, "BDSP1").exists()


def test_read_rows_round_trips(tmp_path):
    merge_station(tmp_path, "46222", observations(), now="2026-09-12T21:00:00Z")
    rows = read_rows(observations_path(tmp_path, "46222"))
    assert len(rows) == 4
    assert rows["2026-09-12T20:26:00Z"]["wtmp"] == "20.1"
