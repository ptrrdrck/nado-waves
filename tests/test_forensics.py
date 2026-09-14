"""Swell forensics: geometry that is easy to get subtly, confidently wrong."""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from forecast.forensics import (
    BEARING_MIN_HOURS,
    arrival_bearing,
    find_witnesses,
    region_name,
)
from forecast.swell import (
    POSITIONS,
    cross_track_km,
    destination_point,
    great_circle_km,
    initial_bearing,
)

UTC = timezone.utc
SD = POSITIONS["46258"]


def test_destination_point_inverts_distance_and_bearing():
    for bearing, distance in ((201.0, 9856.0), (307.0, 8032.0), (35.0, 500.0)):
        point = destination_point(SD, bearing, distance)
        assert great_circle_km(SD, point) == pytest.approx(distance, rel=1e-6)
        assert initial_bearing(SD, point) == pytest.approx(bearing, abs=1e-6)


def test_a_great_circle_west_does_not_stay_west():
    """The trap that produced a tropical origin for a 20-second winter swell.

    Walking 8,000 km on an initial bearing of 279 degrees from San Diego does
    not end up near Alaska — the great circle tops out barely north of the
    start and then descends, landing in the tropical western Pacific. The fix
    was a better bearing, not a different projection, so this pins the geometry
    so nobody "corrects" it back.
    """

    latitude, longitude = destination_point(SD, 279.0, 8032.0)
    assert latitude < 20.0
    assert longitude > 150.0  # across the dateline, east longitude

    # A genuinely north-west bearing does reach the Kuril storm track.
    latitude, longitude = destination_point(SD, 307.0, 8032.0)
    assert 35.0 < latitude < 45.0
    assert 140.0 < longitude < 160.0


def test_cross_track_is_zero_on_the_path_and_positive_beside_it():
    far = destination_point(SD, 290.0, 6000.0)
    midpoint = destination_point(SD, initial_bearing(SD, far), 3000.0)
    assert cross_track_km(SD, far, midpoint) == pytest.approx(0.0, abs=1.0)
    assert cross_track_km(SD, far, destination_point(midpoint, 20.0, 400.0)) > 300.0


def test_regions_cover_both_sides_of_the_dateline():
    assert region_name(-49.7, -125.2) == "the Southern Ocean"
    assert region_name(40.3, 148.5) == "the Kuril and Japan storm track"
    assert region_name(34.3, -176.4) == "the central North Pacific"
    assert region_name(45.0, -170.0) == "the Aleutian storm track"
    assert region_name(56.0, -145.0) == "the Gulf of Alaska"
    assert region_name(5.0, -30.0) == "open ocean"  # Atlantic: honestly unlabelled


def write_station(path: Path, rows: dict[datetime, tuple[float, float, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp_utc", "wtmp", "wvht", "dpd", "mwd", "atmp", "wspd", "wdir"])
        for stamp, (wvht, dpd, mwd) in sorted(rows.items()):
            writer.writerow([stamp.strftime("%Y-%m-%dT%H:%M:%SZ"), "", wvht, dpd, mwd, "", "", ""])


def test_bearing_ignores_a_buoy_whose_peak_is_a_different_wave(tmp_path):
    """The period gate, which is what stops a confident answer about wind sea."""

    arrival = datetime(2025, 6, 27, tzinfo=UTC)
    hours = [arrival + timedelta(hours=i) for i in range(12)]

    # Most exposed buoy in the list, but its dominant peak is 8 s wind chop.
    write_station(
        tmp_path / "historical" / "46047.csv",
        {h: (1.0, 8.0, 300.0) for h in hours},
    )
    # Next one along genuinely has the 18 s swell.
    write_station(
        tmp_path / "historical" / "46086.csv",
        {h: (1.0, 18.0, 200.0) for h in hours},
    )
    bearing, source = arrival_bearing(tmp_path, "46258", arrival, 18.0)
    assert source == "46086"
    assert bearing == pytest.approx(200.0, abs=0.5)


def test_bearing_needs_enough_matching_hours(tmp_path):
    arrival = datetime(2025, 6, 27, tzinfo=UTC)
    write_station(
        tmp_path / "historical" / "46047.csv",
        {
            arrival + timedelta(hours=i): (1.0, 18.0 if i < BEARING_MIN_HOURS - 1 else 7.0, 200.0)
            for i in range(12)
        },
    )
    assert arrival_bearing(tmp_path, "46258", arrival, 18.0) is None


def test_witness_must_be_upstream_and_near_the_path(tmp_path):
    """A buoy behind the target, or far off the line, is not a witness."""

    origin = destination_point(POSITIONS["46258"], 290.0, 6000.0)
    generated = datetime(2025, 12, 1, tzinfo=UTC)
    for station in ("46059", "51002"):
        write_station(tmp_path / "historical" / f"{station}.csv", {})

    found = find_witnesses(
        tmp_path, "46258", origin, generated, 18.0, ("46059", "51002", "46258")
    )
    names = {w.station for w in found}
    assert "46258" not in names          # the target is never its own witness
    assert "46059" in names              # upstream and close to the line
    # 51002, south of Hawaii, is far off a north-west path.
    assert "51002" not in names or next(
        w for w in found if w.station == "51002"
    ).off_path_km > 1000.0
