from datetime import datetime, timedelta, timezone
from pathlib import Path

from collector import health as health_module
from collector import run as run_module
from collector import staleness as staleness_module
from collector.archive import merge_station
from collector.ndbc import NdbcError, parse_realtime2
from collector.stations import Station, load_stations, select

FIXTURES = Path(__file__).parent / "fixtures"


def sample(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


STATION = Station(id="46222", name="San Pedro, CA", region="socal")


def test_registry_loads_and_carries_only_what_cannot_be_derived():
    """The registry is a collection list; `forecast.siting` does the ranking.

    `launch_candidate` used to live here and marked the predecessor game's
    leagues. Nothing replaces it in this file on purpose — a station's value to
    this project is computed from coordinates, so storing it would be the
    duplicated-derivable-value bug spots.json already paid for once.
    """

    stations = load_stations()
    assert stations
    assert all(station.id == station.id.upper() for station in stations)
    assert not any(hasattr(station, "launch_candidate") for station in stations)


def test_select_filters_and_rejects_unknown_ids():
    stations = load_stations()
    assert [s.id for s in select(stations, ["46222"])] == ["46222"]
    try:
        select(stations, ["00000"])
    except ValueError as exc:
        assert "00000" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("unknown station id should raise")


def test_collect_station_archives_the_whole_window(tmp_path):
    outcome = run_module.collect_station(
        STATION,
        tmp_path,
        timeout=1,
        retries=1,
        dry_run=False,
        now="2026-09-12T21:00:00Z",
        fetch=lambda station_id, timeout, retries: sample("46222_sample.txt"),
    )
    assert outcome.ok
    assert outcome.fetched_rows == 4
    assert outcome.result.added == 4


def test_one_failing_station_is_reported_not_raised(tmp_path):
    def fetch(station_id, timeout, retries):
        raise NdbcError("46222: fetch failed")

    outcome = run_module.collect_station(
        STATION, tmp_path, timeout=1, retries=1, dry_run=False,
        now="2026-09-12T21:00:00Z", fetch=fetch,
    )
    assert not outcome.ok
    assert "fetch failed" in outcome.error


def test_an_empty_file_counts_as_a_failure(tmp_path):
    outcome = run_module.collect_station(
        STATION, tmp_path, timeout=1, retries=1, dry_run=False,
        now="2026-09-12T21:00:00Z", fetch=lambda *a, **k: "#YY MM DD hh mm WDIR\n",
    )
    assert not outcome.ok
    assert "no data rows" in outcome.error


def test_summary_names_failed_stations(tmp_path):
    good = run_module.collect_station(
        STATION, tmp_path, timeout=1, retries=1, dry_run=False,
        now="2026-09-12T21:00:00Z",
        fetch=lambda *a, **k: sample("46222_sample.txt"),
    )
    bad_station = Station(id="46086", name="San Clemente Basin, CA")
    bad = run_module.collect_station(
        bad_station, tmp_path, timeout=1, retries=1, dry_run=False,
        now="2026-09-12T21:00:00Z",
        fetch=lambda *a, **k: (_ for _ in ()).throw(NdbcError("46086: offline")),
    )
    summary = run_module.format_summary([good, bad], "2026-09-12T21:00:00Z")
    assert "46086" in summary and "offline" in summary
    assert "1/2 stations collected" in summary


def _archive_with_age(tmp_path, hours_old: float) -> None:
    newest = datetime.now(timezone.utc) - timedelta(hours=hours_old)
    text = "\n".join(
        [
            "#YY  MM DD hh mm WDIR WSPD GST  WVHT   DPD   APD MWD   PRES  ATMP  WTMP  DEWP  VIS PTDY  TIDE",
            "#yr  mo dy hr mn degT m/s  m/s     m   sec   sec degT   hPa  degC  degC  degC  nmi  hPa    ft",
            newest.strftime("%Y %m %d %H %M")
            + "  MM   MM   MM   0.7  13.8   6.7 203     MM    MM  20.1    MM   MM   MM    MM",
        ]
    )
    merge_station(tmp_path, "46222", parse_realtime2(text))


def test_fresh_archive_passes_the_dead_mans_check(tmp_path):
    _archive_with_age(tmp_path, hours_old=2)
    health = health_module.inspect_station(tmp_path, STATION)
    assert not health.is_stale(datetime.now(timezone.utc), 48.0)


def test_archive_older_than_the_threshold_is_stale(tmp_path):
    _archive_with_age(tmp_path, hours_old=72)
    health = health_module.inspect_station(tmp_path, STATION)
    assert health.is_stale(datetime.now(timezone.utc), 48.0)


def test_a_missing_data_file_is_stale_not_healthy(tmp_path):
    health = health_module.inspect_station(tmp_path, STATION)
    assert health.missing_file
    assert health.is_stale(datetime.now(timezone.utc), 48.0)


def test_staleness_exit_code_and_report(tmp_path):
    _archive_with_age(tmp_path, hours_old=72)
    output = tmp_path / "report.md"
    code = staleness_module.main(
        ["--data-dir", str(tmp_path), "--stations", "46222", "--output", str(output)]
    )
    assert code == 1
    assert "DARK" in output.read_text()


def test_staleness_report_distinguishes_dead_collector_from_dead_buoy(tmp_path):
    now = datetime.now(timezone.utc)
    stale = health_module.StationHealth(
        station=STATION, rows=1, newest_observation=now - timedelta(hours=100)
    )
    fresh = health_module.StationHealth(
        station=Station(id="46221", name="Santa Monica Bay, CA"),
        rows=1,
        newest_observation=now - timedelta(hours=1),
    )
    all_stale, _ = staleness_module.format_report([stale], now, 48.0)
    assert "dead collector" in all_stale

    one_stale, _ = staleness_module.format_report([stale, fresh], now, 48.0)
    assert "1 of 2 stations are dark" in one_stale


def _spectrum_with_age(data_dir: Path, station: str, hours_old: float) -> None:
    stamp = datetime.now(timezone.utc) - timedelta(hours=hours_old)
    path = data_dir / "spectra" / station / "c11.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("time_utc,0.0330,0.0380\n"
                    f"{(stamp - timedelta(hours=1)):%Y-%m-%dT%H:%M:%SZ},0,0.1\n"
                    f"{stamp:%Y-%m-%dT%H:%M:%SZ},0,0.2\n", encoding="utf-8")


class TestSpectraStaleness:
    """BRIEFING §38: 46086's wave sensor stopped on 2026-09-25 while its wind
    kept the standard met "live" for ten days. The spectra are checked on
    their own."""

    def test_every_collected_spectrum_is_checked(self):
        assert set(staleness_module.SPECTRA_STATIONS) == {"46232", "46047", "46086", "46258"}

    def test_a_spectrum_that_just_stopped_alerts_once(self, tmp_path):
        now = datetime.now(timezone.utc)
        _spectrum_with_age(tmp_path, "46232", 1)
        _spectrum_with_age(tmp_path, "46086", 60)
        table, newly, dead = staleness_module.spectra_report(tmp_path, now, 48.0, ("46232", "46086"))
        assert newly == ["46086"] and not dead
        assert "NEWLY STALE" in table

    def test_a_long_dark_spectrum_is_listed_not_alerted(self, tmp_path):
        now = datetime.now(timezone.utc)
        _spectrum_with_age(tmp_path, "46232", 1)
        _spectrum_with_age(tmp_path, "46086", 238)
        table, newly, dead = staleness_module.spectra_report(tmp_path, now, 48.0, ("46232", "46086"))
        assert newly == [] and not dead
        assert "known, not re-alerting" in table

    def test_every_spectrum_stale_is_a_dead_collector(self, tmp_path):
        now = datetime.now(timezone.utc)
        for station in ("46232", "46047"):
            _spectrum_with_age(tmp_path, station, 200)
        _, _, dead = staleness_module.spectra_report(tmp_path, now, 48.0, ("46232", "46047"))
        assert dead

    def test_no_file_is_not_collected_rather_than_dead(self, tmp_path):
        table, newly, dead = staleness_module.spectra_report(
            tmp_path, datetime.now(timezone.utc), 48.0)
        assert not newly and not dead and "NOT COLLECTED" in table

    def test_main_alerts_on_a_newly_stale_spectrum(self, tmp_path):
        _archive_with_age(tmp_path, hours_old=2)
        for station in staleness_module.SPECTRA_STATIONS:
            _spectrum_with_age(tmp_path, station, 1)
        assert staleness_module.main(["--data-dir", str(tmp_path), "--stations", "46222"]) == 0
        _spectrum_with_age(tmp_path, "46047", 50)
        output = tmp_path / "report.md"
        assert staleness_module.main(
            ["--data-dir", str(tmp_path), "--stations", "46222", "--output", str(output)]) == 1
        assert "46047" in output.read_text() and "Directional spectra" in output.read_text()
