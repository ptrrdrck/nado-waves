"""NHC's official forecast: the collector keeps OFCL lines only, the reader
takes the newest issue, and the due window runs each fix forward.

The a-deck fixture follows ATCF's published layout (basin, number, issue,
technique number, technique, tau, lat, lon, vmax, mslp, type, radius
threshold, ...); the host is denied from a session, so a live file has not
been read here (collector.nhcforecast says so)."""

from __future__ import annotations

import gzip
import math
from datetime import datetime, timedelta, timezone

import pytest

from collector import nhcforecast
from forecast import stormdue
from forecast.origintracks import Fix

ADECK = """EP, 20, 2026101500, 03, AVNO,   0, 191N, 1083W,  55,  998, XX,
EP, 20, 2026101500, 01, OFCL,   0, 191N, 1083W,  55,  998, TS,  34, NEQ,  60,  50,  40,  50,
EP, 20, 2026101500, 01, OFCL,   0, 191N, 1083W,  55,  998, TS,  50, NEQ,  20,  20,   0,  20,
EP, 20, 2026101500, 01, OFCL,  12, 195N, 1090W,  50,    0, TS,  34, NEQ,  60,  50,  40,  50,
EP, 20, 2026101500, 01, OFCL,  24, 201N, 1101W,  40,    0, TS,  34, NEQ,  50,  40,  30,  40,
EP, 20, 2026101500, 01, OFCL,  36, 207N, 1113W,  30,    0, TD,
EP, 20, 2026101506, 01, OFCL,   0, 193N, 1085W,  50,  999, TS,  34, NEQ,  60,  50,  40,  50,
EP, 20, 2026101506, 01, OFCL,  12, 199N, 1094W,  45,    0, TS,  34, NEQ,  50,  40,  30,  40,
EP, 20, 2026101506, 03, HWRF,  12, 199N, 1094W,  45,    0, XX,
"""

BDECK = "EP, 20, 2026101500,   , BEST,   0, 191N, 1083W,  55,  998, TS,  34, NEQ\n"


def test_only_the_official_forecast_is_kept_as_fetched():
    kept = nhcforecast.official_lines(ADECK)
    assert len(kept) == 7
    assert all(", OFCL," in line for line in kept)
    assert kept[0] == ADECK.splitlines()[1].rstrip()


def test_only_storms_with_a_recent_best_track_are_fetched(tmp_path):
    d = tmp_path / "besttracks" / "2026"
    d.mkdir(parents=True)
    (d / "bep202026.dat").write_text(BDECK)
    (d / "bep052026.dat").write_text(BDECK.replace("2026101500", "2026071200").replace("20,", "05,"))
    now = datetime(2026, 10, 16, 6, tzinfo=timezone.utc)
    assert nhcforecast.active(tmp_path, 2026, now) == ["ep20"]


def test_the_archive_is_rewritten_only_when_its_lines_change(tmp_path):
    d = tmp_path / "besttracks" / "2026"
    d.mkdir(parents=True)
    (d / "bep202026.dat").write_text(BDECK)
    now = datetime(2026, 10, 16, 6, tzinfo=timezone.utc)
    pages = {nhcforecast.AID + "aep202026.dat.gz": gzip.compress(ADECK.encode())}
    assert nhcforecast.archive(tmp_path, 2026, now, fetch=pages.__getitem__)[:3] == (1, 0, [])
    assert nhcforecast.archive(tmp_path, 2026, now, fetch=pages.__getitem__)[:3] == (0, 1, [])
    stored = (tmp_path / "nhcforecasts" / "2026" / "aep202026_ofcl.dat").read_text()
    assert "AVNO" not in stored and "HWRF" not in stored


def test_the_newest_issue_wins_and_each_hour_appears_once(tmp_path):
    d = tmp_path / "nhcforecasts" / "2026"
    d.mkdir(parents=True)
    (d / "aep202026_ofcl.dat").write_text("\n".join(nhcforecast.official_lines(ADECK)) + "\n")
    newest = stormdue.load_forecast("EP20", 2026, tmp_path)
    assert [f.tau_h for f in newest] == [0, 12]
    assert newest[1].time == datetime(2026, 10, 15, 18, tzinfo=timezone.utc)
    assert newest[1].lat == pytest.approx(19.9) and newest[1].lon == pytest.approx(-109.4)
    earlier = stormdue.load_forecast("EP20", 2026, tmp_path,
                                     as_of=datetime(2026, 10, 15, 3, tzinfo=timezone.utc))
    assert [f.tau_h for f in earlier] == [0, 12, 24, 36]


def _fix(t, lat, lon, kt, status="HU"):
    return Fix("EP99", "TEST", t, lat, lon, kt, None, status)


HOME = (32.517, -117.425)
T0 = datetime(2026, 10, 1, tzinfo=timezone.utc)


def stormdue_leg(minutes):
    from forecast.upstreamlag import Leg
    return Leg("x", 15.0, minutes, minutes)


def test_the_window_runs_from_the_fastest_swell_of_the_first_fix_to_the_slowest_of_the_last():
    fixes = [_fix(T0, 20.0, -118.0, 90), _fix(T0 + timedelta(hours=24), 21.0, -118.0, 80)]
    got = stormdue.due(fixes, [], home=HOME, breaks=["b"], leg=lambda *a: stormdue_leg(0.0),
                       tables={})
    from forecast.swell import great_circle_km
    cg_fast = 9.81 * 20.0 / (4 * math.pi)
    cg_slow = 9.81 * 12.0 / (4 * math.pi)
    first = T0 + timedelta(seconds=great_circle_km(HOME, (20.0, -118.0)) * 1000 / cg_fast)
    last = T0 + timedelta(hours=24, seconds=great_circle_km(HOME, (21.0, -118.0)) * 1000 / cg_slow)
    edge = got.breaks["b"]
    assert abs((edge["first"].utc - first).total_seconds()) < 60
    assert abs((edge["last"].utc - last).total_seconds()) < 60
    assert edge["first"].source == edge["last"].source == "best track"


def test_nhcs_forecast_extends_the_window_and_is_named():
    fixes = [_fix(T0, 20.0, -118.0, 90)]
    forecast = [stormdue.ForecastFix(T0, 0, T0, 20.0, -118.0, 90),
                stormdue.ForecastFix(T0, 48, T0 + timedelta(hours=48), 22.0, -119.0, 50),
                stormdue.ForecastFix(T0, 72, T0 + timedelta(hours=72), 23.0, -119.0, 25)]
    got = stormdue.due(fixes, forecast, home=HOME, breaks=["b"], leg=lambda *a: stormdue_leg(0.0),
                       tables={})
    last = got.breaks["b"]["last"]
    assert last.source == "NHC forecast"
    assert last.fix_utc == T0 + timedelta(hours=48)   # the 25 kt hour sends nothing


def test_a_storm_with_every_fix_behind_land_has_no_window():
    class Everywhere:
        def __contains__(self, point):
            return True
    fixes = [_fix(T0, 20.0, -118.0, 90)]
    got = stormdue.due(fixes, [], home=HOME, breaks=["b"], land=Everywhere(),
                       leg=lambda *a: stormdue_leg(0.0), tables={})
    assert got.open_fixes == 0 and got.blocked_fixes == 1 and got.breaks == {}


def test_a_storm_that_never_reached_hurricane_strength_is_not_a_source():
    fixes = [_fix(T0, 20.0, -118.0, 50, "TS")]
    assert stormdue.due(fixes, [], home=HOME, breaks=["b"], tables={}) is None


def test_south_swell_from_the_south_west_reaches_every_break():
    keeps = stormdue.response(205.0)
    assert set(keeps) == {"coronado_north", "coronado_center", "coronado_south"}
    assert all(0.3 < v < 1.5 for v in keeps.values())
