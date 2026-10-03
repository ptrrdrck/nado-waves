"""The Origins chart's marks: the grid of named moments, linking a named
storm to Origin's reading of the same train, and now.json's last word."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from forecast import originhistory as H

UTC = timezone.utc


def arrival(first, last, distance_km, bearing, sites, generated):
    return {"first_utc": first, "last_utc": last, "distance_km": distance_km,
            "bearing_deg": bearing, "sites": sites, "generated_utc": generated}


def test_named_moments_sit_on_the_six_hourly_grid_after_since():
    got = H.moments(datetime(2026, 9, 1, 4, 30, tzinfo=UTC), datetime(2026, 9, 2, 0, tzinfo=UTC))
    assert [t.hour for t in got] == [6, 12, 18, 0]
    assert H.moments(datetime(2026, 9, 1, 6, tzinfo=UTC), datetime(2026, 9, 1, 6, tzinfo=UTC)) == []


def test_the_ridge_frequency_is_the_dispersion_line():
    a = arrival("2026-09-02T00:00:00Z", "2026-09-03T00:00:00Z", 3000, 200, [], "2026-08-29T00:00:00Z")
    f = H.ridge_freq_hz(a, datetime(2026, 9, 2, tzinfo=UTC))
    # g t / (4 pi R): four days after it blew, 3,000 km off, an 11 s train.
    assert abs(1 / f - 4 * 3.141592653589793 * 3.0e6 / (9.81 * 4 * 86400)) < 1e-9


def _named(at, site, period, bearing, name="Polo"):
    return {"time_utc": at, "name": name, "storm": "EP17",
            "sites": {site: {"train_period_s": period, "bearing_deg": bearing, "distance_km": 1100}}}


def test_a_named_storm_takes_the_arrival_of_its_own_train_from_its_own_direction():
    a = arrival("2026-09-29T00:00:00Z", "2026-09-30T00:00:00Z", 3000, 165, ["buoy", "coronado_south"],
                "2026-09-26T00:00:00Z")
    t = "2026-09-29T12:00:00Z"
    period = 1 / H.ridge_freq_hz(a, datetime(2026, 9, 29, 12, tzinfo=UTC))
    H.link([a], [_named(t, "coronado_south", round(period, 1), 160)])
    assert a["named"] == {"coronado_south": "Polo"}


def test_the_same_period_from_another_direction_stays_unnamed():
    a = arrival("2026-09-29T00:00:00Z", "2026-09-30T00:00:00Z", 3000, 304, ["buoy"],
                "2026-09-26T00:00:00Z")
    period = 1 / H.ridge_freq_hz(a, datetime(2026, 9, 29, 12, tzinfo=UTC))
    H.link([a], [_named("2026-09-29T12:00:00Z", "buoy", round(period, 1), 161)])
    assert a["named"] == {}


def test_another_period_or_another_time_stays_unnamed():
    a = arrival("2026-09-29T00:00:00Z", "2026-09-30T00:00:00Z", 3000, 165, ["buoy"],
                "2026-09-26T00:00:00Z")
    period = 1 / H.ridge_freq_hz(a, datetime(2026, 9, 29, 12, tzinfo=UTC))
    H.link([a], [_named("2026-09-29T12:00:00Z", "buoy", round(period + 3, 1), 165),
                 _named("2026-10-02T12:00:00Z", "buoy", round(period, 1), 165)])
    assert a["named"] == {}


def test_nows_hurricanes_count_only_at_the_newest_spectrum(tmp_path):
    live = tmp_path / "live"
    live.mkdir()
    hurricane = {"storm": "EP17", "name": "Polo", "best": 0.78, "word": "partial",
                 "match": {}, "sites": {}}
    (live / "now.json").write_text(json.dumps({"observed_utc": "2026-09-29T07:00:00Z",
                                               "origin": {"hurricanes": [hurricane]}}))
    newest = datetime(2026, 9, 29, 7, tzinfo=UTC)
    assert [n["name"] for n in H.current_named(tmp_path, newest)] == ["Polo"]
    assert H.current_named(tmp_path, newest + timedelta(hours=5)) == []
    # On the grid the tail already asked the same question: one mark, not two.
    (live / "now.json").write_text(json.dumps({"observed_utc": "2026-09-29T06:00:00Z",
                                               "origin": {"hurricanes": [hurricane]}}))
    assert H.current_named(tmp_path, newest - timedelta(hours=1)) == []


def test_the_archive_is_in_series_and_the_page_file_is_live():
    assert str(H.ARCHIVE).startswith("series/") and str(H.LIVE) == "live/origins.json"
