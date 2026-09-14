from datetime import datetime, timezone
from pathlib import Path

import pytest

from collector.ndbc import NdbcError, fetch_station, parse_realtime2, station_url

FIXTURES = Path(__file__).parent / "fixtures"


def sample(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parses_every_row_not_just_the_latest():
    # The whole point of the four-times-a-day cadence: each file is a rolling
    # window of many hours, so one fetch must yield every row in it.
    observations = parse_realtime2(sample("46222_sample.txt"))
    assert len(observations) == 4


def test_rows_are_returned_oldest_first_though_ndbc_writes_newest_first():
    observations = parse_realtime2(sample("46222_sample.txt"))
    timestamps = [o.timestamp for o in observations]
    assert timestamps == sorted(timestamps)
    assert observations[0].timestamp == datetime(2026, 9, 12, 17, 26, tzinfo=timezone.utc)
    assert observations[-1].timestamp == datetime(2026, 9, 12, 20, 26, tzinfo=timezone.utc)


def test_timestamps_are_utc_and_iso_formatted():
    observations = parse_realtime2(sample("46222_sample.txt"))
    assert observations[-1].timestamp_utc == "2026-09-12T20:26:00Z"


def test_values_are_read_by_header_name():
    observations = parse_realtime2(sample("46222_sample.txt"))
    latest = observations[-1]
    assert latest.get("WTMP") == "20.1"
    assert latest.get("DPD") == "13.8"
    assert latest.get("MWD") == "203"


def test_missing_values_become_empty_never_guessed():
    observations = parse_realtime2(sample("46222_sample.txt"))
    gap = next(o for o in observations if o.timestamp.hour == 18)
    assert gap.get("WTMP") == ""
    assert gap.get("WVHT") == "0.8"


def test_station_with_fewer_columns_still_parses():
    # 46086's file has no PTDY column. Positional parsing would silently shift
    # every value right of it.
    observations = parse_realtime2(sample("46086_sample.txt"))
    latest = observations[-1]
    assert latest.get("WTMP") == "18.9"
    assert latest.get("ATMP") == "18.4"
    assert latest.get("PRES") == "1012.8"
    assert latest.get("TIDE") == ""


def test_malformed_rows_are_skipped_not_fatal():
    text = sample("46222_sample.txt") + "\nthis is not a data row\n2026 99 99 99 99\n"
    assert len(parse_realtime2(text)) == 4


def test_duplicate_timestamps_collapse():
    text = sample("46222_sample.txt")
    assert len(parse_realtime2(text + text)) == 4


def test_empty_file_yields_nothing():
    assert parse_realtime2("") == []
    assert parse_realtime2("#YY  MM DD hh mm WDIR\n#yr  mo dy hr mn degT\n") == []


def test_station_url_is_uppercased():
    assert station_url("46222").endswith("/46222.txt")
    assert station_url("bdsp1") == station_url("BDSP1")


class _FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload
        self.headers = {}

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_fetch_retries_transient_failures_then_succeeds():
    attempts = {"count": 0}
    slept: list[float] = []

    def opener(request, timeout=None):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise OSError("connection reset")
        return _FakeResponse(b"payload")

    text = fetch_station(
        "46222", retries=3, sleep=slept.append, opener=opener
    )
    assert text == "payload"
    assert attempts["count"] == 3
    assert slept == [2.0, 4.0]


def test_fetch_gives_up_with_a_clear_error():
    def opener(request, timeout=None):
        raise OSError("connection reset")

    with pytest.raises(NdbcError, match="fetch failed after 2 attempts"):
        fetch_station("46222", retries=2, sleep=lambda _: None, opener=opener)


def test_404_is_not_retried():
    import urllib.error

    attempts = {"count": 0}

    def opener(request, timeout=None):
        attempts["count"] += 1
        raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)

    with pytest.raises(NdbcError, match="no such station"):
        fetch_station("99999", retries=3, sleep=lambda _: None, opener=opener)
    assert attempts["count"] == 1


def test_base_url_can_be_overridden_for_local_testing(monkeypatch):
    monkeypatch.setenv("NDBC_BASE_URL", "http://localhost:8000/fixtures/")
    assert station_url("46222") == "http://localhost:8000/fixtures/46222.txt"


# --- historical archive sentinels ------------------------------------------
# The historical files use numeric sentinels instead of MM. These rows are
# verbatim from 46222h2021.txt.gz and 46086h2025.txt.gz.

def test_historical_numeric_sentinels_are_read_as_missing():
    observations = parse_realtime2(sample("46222h2021_excerpt.txt"))
    first = observations[0]
    assert first.get("WTMP") == "15.1"      # a real value survives
    assert first.get("WDIR") == ""          # 999
    assert first.get("WSPD") == ""          # 99.0
    assert first.get("PRES") == ""          # 9999.0
    assert first.get("ATMP") == ""          # 999.0
    assert first.get("DEWP") == ""          # 999.0
    assert first.get("TIDE") == ""          # 99.00


def test_two_decimal_sentinels_are_matched_by_value_not_by_string():
    observations = parse_realtime2(sample("46086h2025_excerpt.txt"))
    first = observations[0]
    assert first.get("WVHT") == ""          # 99.00, sentinel written as 99.0
    assert first.get("DPD") == ""
    assert first.get("MWD") == ""           # 999


def test_real_values_in_historical_files_are_preserved():
    observations = parse_realtime2(sample("46086h2025_excerpt.txt"))
    first = observations[0]
    assert first.get("PRES") == "1016.1"
    assert first.get("ATMP") == "13.1"
    assert first.get("WTMP") == "15.3"
    assert first.get("WDIR") == "190"


def test_a_real_pressure_of_999_is_not_mistaken_for_a_sentinel():
    # PRES's sentinel is 9999.0. 999.0 hPa is a real, low, sea-level pressure,
    # so a blanket "all nines means missing" rule would delete real weather.
    from collector.ndbc import is_missing

    assert not is_missing("pres", "999.0")
    assert is_missing("pres", "9999.0")
    assert is_missing("atmp", "999.0")


def test_mm_still_works_for_the_realtime_feed():
    from collector.ndbc import is_missing

    assert is_missing("wtmp", "MM")
    assert not is_missing("wtmp", "20.1")
