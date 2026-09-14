"""The forecast probe's judgement, tested offline.

Every case here is a mistake the first live run of the probe actually made.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from collector.probe_forecast import Candidate, Result, sniff_date

NOW = datetime(2026, 9, 13, 2, 55, tzinfo=timezone.utc)

# Verbatim from the first probe run: HTTP 200, and eighteen months stale.
STALE_NWS = (
    "Expires:202503200815;;810414 FZUS56 KSGX 191952 CWFSGX Coastal Waters "
    "Forecast for California National Weather Service San Diego CA 1252 PM PDT "
    "Wed Mar 19 2025 San Mateo Point to the Mexican border out to 60 nm"
)

CANDIDATE = Candidate(
    name="test", url="https://example.invalid", looking_for=("water temp",),
    operator="NOAA / NWS",
)


def result(**kwargs) -> Result:
    base = dict(candidate=CANDIDATE, status="200", found=("water temp",))
    base.update(kwargs)
    return Result(**base)


def test_finds_the_date_buried_in_a_national_weather_service_product():
    dated, source = sniff_date(STALE_NWS, {}, NOW)
    assert dated == datetime(2025, 3, 19, tzinfo=timezone.utc)
    assert source == "content"


def test_a_reachable_source_serving_old_content_is_not_usable():
    # The trap: HTTP 200, field present, and completely useless as a baseline.
    dated, _ = sniff_date(STALE_NWS, {}, NOW)
    r = result(dated=dated)
    assert r.reachable
    assert r.found
    assert r.is_stale(NOW)
    assert r.verdict(NOW) == "STALE DATA"


def test_content_dates_beat_a_fresh_header_over_stale_bytes():
    headers = {"Last-Modified": "Sun, 13 Sep 2026 02:00:00 GMT"}
    dated, source = sniff_date(STALE_NWS, headers, NOW)
    assert source == "content"
    assert dated.year == 2025


def test_header_is_used_only_when_the_body_has_no_dates():
    headers = {"Last-Modified": "Sun, 13 Sep 2026 02:00:00 GMT"}
    dated, source = sniff_date("no dates here at all", headers, NOW)
    assert source == "Last-Modified header"
    assert dated.day == 13


def test_forecast_valid_times_count_as_fresh():
    # A live forecast body is full of near-future timestamps. That is the
    # product working, not a clock problem.
    body = "2026-09-13T06:00 2026-09-13T12:00 2026-09-14T00:00"
    dated, _ = sniff_date(body, {}, NOW)
    assert dated is not None
    assert not result(dated=dated).is_stale(NOW)


def test_far_future_dates_are_ignored_as_junk():
    dated, _ = sniff_date("valid until 2099-01-01 and issued 2026-09-12", {}, NOW)
    assert dated == datetime(2026, 9, 12, tzinfo=timezone.utc)


def test_compact_yyyymmdd_is_recognised():
    # How NOMADS names its model cycle directories: rtofs.20260913
    dated, _ = sniff_date("rtofs.20260913/", {}, NOW)
    assert dated == datetime(2026, 9, 13, tzinfo=timezone.utc)


def test_a_truncated_body_is_inconclusive_not_a_negative():
    # The first run capped reads at 200KB and called a cut-off gridpoint
    # payload "field not found".
    assert result(found=(), truncated=True).verdict(NOW) == "inconclusive (truncated)"


def test_missing_field_is_reported_plainly():
    assert result(found=()).verdict(NOW) == "no target field"


def test_unreachable_source_is_reported_plainly():
    assert result(error="HTTP 403 Forbidden", status="403").verdict(NOW) == "unreachable"


def test_fresh_source_with_the_field_is_usable():
    r = result(dated=NOW - timedelta(hours=3))
    assert r.verdict(NOW) == "usable"


def test_undated_content_is_not_silently_called_usable():
    assert result(dated=None).verdict(NOW) == "field present, undated"


def test_third_party_sources_are_not_counted_as_noaa():
    # "Open-Meteo (THIRD PARTY, not NOAA)" contains the substring "NOAA", and a
    # substring check on the operator prose reported it as a NOAA source.
    from collector.probe_forecast import CANDIDATES

    by_name = {c.name: c for c in CANDIDATES}
    assert by_name["Open-Meteo Marine"].noaa is False
    assert by_name["NWS gridpoint forecast"].noaa is True
    assert sum(1 for c in CANDIDATES if not c.noaa) == 1
