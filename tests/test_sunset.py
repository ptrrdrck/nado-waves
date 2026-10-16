"""forecast.sunset and forecast.skyline: the Sun card's sunset, behind Point
Loma or in the sea, per break (owner's request, 2026-10-16; BRIEFING §42).

The Sun's positions are PyEphem 4.2's for the center break (pressure 0, so
geometric altitude, as `sun_position` returns), run 2026-10-16; the sea-level
rise and set times are astral's, the same references `test_daylight` pins.
The seasons are the measurement §42 records, re-run each time.
"""

from __future__ import annotations

import ast
import csv
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from forecast import sunset
from forecast.geometry import load
from forecast.swell import initial_bearing

SPOTS, BLOCKERS = load()
POS = {s.id: s.position for s in SPOTS}
SKIES = {b: sunset.Skyline.load(b) for b in sunset.BREAKS}


@pytest.mark.parametrize("when,alt,az", [
    ("2026-06-21T02:50:00Z", 0.940, 297.521),
    ("2026-10-17T01:10:00Z", 0.070, 259.008),
    ("2026-12-21T00:40:00Z", 0.366, 241.533),
    ("2027-03-20T14:00:00Z", 0.731, 90.596),
])
def test_the_sun_is_where_pyephem_puts_it(when, alt, az):
    """0.03° is about seven seconds of sunset."""

    t = datetime.strptime(when, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    got_alt, got_az, sd = sunset.sun_position(t, *POS["coronado_center"])
    assert abs(got_alt - alt) < 0.03 and abs(got_az - az) < 0.03
    assert 0.262 < sd < 0.273


@pytest.mark.parametrize("day,rise,sets", [
    (date(2026, 6, 21), (12, 42), (2, 59)),
    (date(2026, 10, 1), (13, 43), (1, 34)),
    (date(2026, 12, 21), (14, 47), (0, 46)),
])
def test_sea_horizon_times_match_the_published_ones(day, rise, sets):
    up, down = sunset.sea_times(day, POS["coronado_center"])

    def minutes(t):
        return t.hour * 60 + t.minute + t.second / 60

    assert abs(minutes(up) - (rise[0] * 60 + rise[1])) <= 1.5
    assert abs(minutes(down) - (sets[0] * 60 + sets[1])) <= 1.5


@pytest.mark.parametrize("break_id", sunset.BREAKS)
def test_the_survey_finds_the_point_where_the_chart_does(break_id):
    """Two independent sources for one edge: CoNED's bare-earth lidar above
    MSL, and NOAA's ENC coastline tangent that carries the swell window's west
    edge (BRIEFING §26). Measured within 0.1°; 0.3° is pinned."""

    tip = next(b for b in BLOCKERS if b.name.startswith("Point Loma"))
    charted = initial_bearing(POS[break_id], tip.a_seen_from(POS[break_id]))
    assert abs(SKIES[break_id].first_land() - charted) < 0.3


def test_the_skyline_is_point_loma_and_nothing_nearer():
    """Every sunset azimuth's skyline is the ridge, 4.5-8 km out and 90-130 m
    up -- never the observer's own beach."""

    for b in sunset.BREAKS:
        with (sunset.TABLES / f"{b}_skyline.csv").open() as f:
            rows = [r for r in csv.DictReader(f) if r["elevation_deg"]
                    and 245 <= float(r["azimuth_deg"]) <= 299 and float(r["elevation_deg"]) > 0.5]
        assert rows
        assert all(4000 <= int(r["distance_m"]) <= 9000 for r in rows), b
        assert max(float(r["elevation_deg"]) for r in rows) < 1.6


@pytest.mark.parametrize("break_id", sunset.BREAKS)
def test_point_loma_takes_minutes_off_a_summer_sunset(break_id):
    s = sunset.sunset(date(2027, 6, 21), POS[break_id], SKIES[break_id])
    assert s["kind"] == "point_loma"
    assert 4.5 < s["early_min"] < 8.5
    assert s["seen_utc"] < s["_sea"].strftime("%Y-%m-%dT%H:%M:%SZ")


def test_a_sea_sunset_is_the_sea_horizon_time():
    s = sunset.sunset(date(2026, 12, 21), POS["coronado_south"], SKIES["coronado_south"])
    assert s["kind"] == "sea" and s["early_min"] == 0.0
    assert s["seen_utc"] == sunset._round(s["_sea"])


def near(got: str, want: date, days: int = 1) -> bool:
    return abs((date.fromisoformat(got) - want).days) <= days


def test_each_break_has_its_own_winter():
    """The measurement in BRIEFING §42: the tip's bearing sweeps 18° along
    the sand, so the season of sea sunsets differs by break."""

    start = date(2026, 10, 16)
    north = sunset.season(start, POS["coronado_north"], SKIES["coronado_north"])
    assert [r["kind"] for r in north["runs"]] == ["point_loma"]
    assert near(north["closest"]["day"], date(2026, 12, 21), 4)
    assert 0.5 < north["closest"]["early_min"] < 1.5

    center = sunset.season(start, POS["coronado_center"], SKIES["coronado_center"])
    sea = [r for r in center["runs"] if r["kind"] == "sea"]
    assert len(sea) == 1 and "closest" not in center
    assert near(sea[0]["from"], date(2026, 11, 9)) and near(sea[0]["to"], date(2027, 2, 1))

    south = sunset.season(start, POS["coronado_south"], SKIES["coronado_south"])
    assert south["runs"][0]["kind"] == "sea"
    assert near(south["runs"][0]["to"], date(2027, 2, 25))
    assert near(south["runs"][-1]["from"], date(2027, 10, 15))


def test_the_block_carries_every_day_and_break():
    days = [date(2026, 10, 16), date(2026, 10, 17)]
    got = sunset.block(days)
    assert list(got["days"]) == ["2026-10-16", "2026-10-17"]
    for entry in got["days"].values():
        assert set(entry["breaks"]) == set(sunset.BREAKS)
        assert entry["sunrise_utc"] < entry["sunset_utc"]
        for s in entry["breaks"].values():
            assert "_sea" not in s and s["seen_utc"] <= entry["sunset_utc"]
    assert set(got["seasons"]) == set(sunset.BREAKS)


def test_the_forecast_path_never_needs_numpy():
    """`forecast.skyline` is the precompute; `forecast.sunset` runs every
    collection and is pure Python, as `nearshore` is."""

    tree = ast.parse(Path(sunset.__file__).read_text())
    names = {a.name for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
             for a in n.names} | {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert "numpy" not in names and "skyline" not in names and ".skyline" not in names
