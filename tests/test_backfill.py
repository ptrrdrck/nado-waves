"""Historical backfill: reduced on purpose, and never the system of record."""

from __future__ import annotations

import csv
from pathlib import Path

from collector.backfill import (
    HISTORICAL_FIELDS,
    KEPT_COLUMNS,
    BackfillError,
    backfill_year,
    downsample_hourly,
    historical_path,
    manifest_path,
    read_manifest,
    append_manifest,
)
from collector.ndbc import parse_realtime2
from collector.stations import Station

FIXTURES = Path(__file__).parent / "fixtures"
STATION = Station(id="46222", name="San Pedro, CA", region="socal")

HEADER = (
    "#YY  MM DD hh mm WDIR WSPD GST  WVHT   DPD   APD MWD   PRES  ATMP  WTMP  DEWP  VIS  TIDE\n"
    "#yr  mo dy hr mn degT m/s  m/s     m   sec   sec degT   hPa  degC  degC  degC  nmi    ft\n"
)


def year_file(rows: list[str]) -> str:
    return HEADER + "\n".join(rows) + "\n"


HALF_HOURLY = year_file([
    "2021 01 01 00 21 999 99.0 99.0  1.93  7.69  6.23 271 9999.0 999.0  15.1 999.0 99.0 99.00",
    "2021 01 01 00 51 999 99.0 99.0  1.88  7.69  6.11 268 9999.0 999.0  15.0 999.0 99.0 99.00",
    "2021 01 01 01 21 999 99.0 99.0  1.85  7.69  6.05 265 9999.0 999.0  14.9 999.0 99.0 99.00",
])


def read_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_downsampling_keeps_one_row_per_hour():
    observations = parse_realtime2(HALF_HOURLY)
    assert len(observations) == 3
    hourly = downsample_hourly(observations)
    assert len(hourly) == 2
    # The first reading in the hour, not the last.
    assert hourly[0].get("WTMP") == "15.1"


def test_backfill_writes_only_the_columns_we_use(tmp_path):
    backfill_year(tmp_path, STATION, 2021, fetch=lambda *a, **k: HALF_HOURLY)
    rows = read_rows(historical_path(tmp_path, "46222"))
    assert list(rows[0].keys()) == HISTORICAL_FIELDS
    # Pressure, dew point, tide and the wave periods are re-fetchable from NDBC
    # and are deliberately dropped.
    assert "pres" not in rows[0]
    assert "dewp" not in rows[0]


def test_historical_sentinels_survive_the_round_trip_as_blanks(tmp_path):
    # The whole trap: 999.0 must not land in the archive as an air temperature.
    backfill_year(tmp_path, STATION, 2021, fetch=lambda *a, **k: HALF_HOURLY)
    rows = read_rows(historical_path(tmp_path, "46222"))
    assert rows[0]["wtmp"] == "15.1"
    assert rows[0]["atmp"] == ""
    assert rows[0]["wspd"] == ""
    assert rows[0]["wdir"] == ""
    assert rows[0]["wvht"] == "1.93"


def test_backfill_never_touches_the_live_observation_archive(tmp_path):
    # The live archive is the only thing that can resolve a round. Backfill is
    # quality-controlled after the fact and must stay in its own lane.
    (tmp_path / "observations").mkdir(parents=True)
    live = tmp_path / "observations" / "46222.csv"
    live.write_text("timestamp_utc,first_seen_utc,wtmp\n2021-01-01T00:21:00Z,x,99.9\n")
    before = live.read_text()
    backfill_year(tmp_path, STATION, 2021, fetch=lambda *a, **k: HALF_HOURLY)
    assert live.read_text() == before
    assert historical_path(tmp_path, "46222").exists()


def test_a_second_year_merges_without_losing_the_first(tmp_path):
    backfill_year(tmp_path, STATION, 2021, fetch=lambda *a, **k: HALF_HOURLY)
    later = year_file([
        "2022 06 01 12 21 180  4.0  5.0  0.90 10.00  5.00 200 1013.0  18.0  19.4  12.0 99.0 99.00",
    ])
    backfill_year(tmp_path, STATION, 2022, fetch=lambda *a, **k: later)
    rows = read_rows(historical_path(tmp_path, "46222"))
    assert len(rows) == 3
    assert rows[0]["timestamp_utc"].startswith("2021")
    assert rows[-1]["timestamp_utc"].startswith("2022")


def test_re_running_a_year_is_idempotent(tmp_path):
    backfill_year(tmp_path, STATION, 2021, fetch=lambda *a, **k: HALF_HOURLY)
    before = historical_path(tmp_path, "46222").read_text()
    backfill_year(tmp_path, STATION, 2021, fetch=lambda *a, **k: HALF_HOURLY)
    assert historical_path(tmp_path, "46222").read_text() == before


def test_a_missing_year_is_recorded_not_fatal(tmp_path):
    def fetch(*a, **k):
        raise BackfillError("no archive published for 46222 2019")

    result = backfill_year(tmp_path, STATION, 2019, fetch=fetch)
    assert not result.ok
    assert "no archive published" in result.note
    assert not historical_path(tmp_path, "46222").exists()


def test_dry_run_writes_nothing(tmp_path):
    result = backfill_year(tmp_path, STATION, 2021, dry_run=True,
                           fetch=lambda *a, **k: HALF_HOURLY)
    assert result.rows_kept == 2
    assert not historical_path(tmp_path, "46222").exists()


def test_manifest_records_provenance(tmp_path):
    result = backfill_year(tmp_path, STATION, 2021, fetch=lambda *a, **k: HALF_HOURLY)
    append_manifest(tmp_path, [result], "2026-09-13T05:00:00Z")
    manifest = read_manifest(tmp_path)
    entry = manifest[("46222", 2021)]
    assert entry["retrieved_at_utc"] == "2026-09-13T05:00:00Z"
    assert "46222h2021.txt.gz" in entry["url"]
    assert entry["rows_kept"] == "2"


def test_manifest_survives_a_later_station_year(tmp_path):
    first = backfill_year(tmp_path, STATION, 2021, fetch=lambda *a, **k: HALF_HOURLY)
    append_manifest(tmp_path, [first], "2026-09-13T05:00:00Z")
    second = backfill_year(tmp_path, STATION, 2022, fetch=lambda *a, **k: year_file([
        "2022 06 01 12 21 180  4.0  5.0  0.90 10.00  5.00 200 1013.0  18.0  19.4  12.0 99.0 99.00",
    ]))
    append_manifest(tmp_path, [second], "2026-09-13T06:00:00Z")
    manifest = read_manifest(tmp_path)
    assert ("46222", 2021) in manifest
    assert ("46222", 2022) in manifest


# --- the moored-buoy pattern ------------------------------------------------
# NDBC moored buoys report meteorology every 10 minutes but waves only once an
# hour, at :30/:40/:50 and never :00. Keeping "the first record in the hour"
# therefore kept the wind and discarded the waves on every single hour: 46001
# came back with 7 wave heights out of 22,467 rows from a file full of them.

MOORED = year_file([
    "2024 03 14 04 00 329  7.0  9.0 99.00 99.00 99.00 999 1002.5   2.0   4.2   1.4 99.0 99.00",
    "2024 03 14 04 10 330  7.1  9.1 99.00 99.00 99.00 999 1002.4   2.0   4.2   1.4 99.0 99.00",
    "2024 03 14 04 50 331  7.2  9.2  1.98 19.05  7.49 227 1002.3   2.1   4.2   1.4 99.0 99.00",
])


def test_an_hour_is_merged_not_sampled():
    hourly = downsample_hourly(parse_realtime2(MOORED))
    assert len(hourly) == 1
    row = hourly[0]
    assert row.get("WSPD") == "7.0"     # from :00
    assert row.get("WVHT") == "1.98"    # from :50 — the bug dropped this
    assert row.get("DPD") == "19.05"


def test_the_merged_row_carries_the_hours_first_timestamp():
    hourly = downsample_hourly(parse_realtime2(MOORED))
    assert hourly[0].timestamp.minute == 0


def test_waves_reaching_the_archive_from_a_late_sub_hourly_record(tmp_path):
    # End to end: the value has to survive downsampling AND the column filter.
    backfill_year(tmp_path, STATION, 2024, columns=("wvht", "wspd"),
                  fetch=lambda *a, **k: MOORED)
    rows = read_rows(historical_path(tmp_path, "46222"))
    assert len(rows) == 1
    assert rows[0]["wvht"] == "1.98"
    assert rows[0]["wspd"] == "7.0"
