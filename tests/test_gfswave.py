"""GFS-Wave bulletins: the two conventions that silently produce wrong answers."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

import pytest

from collector.gfswave import (
    BulletinError,
    Partition,
    bulletin_url,
    from_direction,
    parse_bulletin,
)
from collector.gfswave_backfill import DEFAULT_MIN_HS, rows_for

FIXTURES = Path(__file__).parent / "fixtures"
ROLLOVER = (FIXTURES / "gfswave_46232_rollover.bull").read_text()


def parsed():
    return parse_bulletin(ROLLOVER)


def test_header_gives_station_and_cycle():
    bulletin = parsed()
    assert bulletin.station_id == "46232"
    assert bulletin.latitude == pytest.approx(32.52)
    # West longitude is negative. A bulletin that said 117.42 would put this
    # buoy in the Yellow Sea.
    assert bulletin.longitude == pytest.approx(-117.42)
    assert bulletin.cycle_utc == datetime(2025, 12, 30, tzinfo=timezone.utc)


def test_valid_times_roll_over_the_year():
    """The bulletin never states the month, and this one crosses 31 Dec."""

    bulletin = parsed()
    assert bulletin.rows[0].valid_utc == datetime(2025, 12, 31, 18, tzinfo=timezone.utc)
    assert bulletin.rows[-1].valid_utc == datetime(2026, 1, 1, 1, tzinfo=timezone.utc)
    assert [row.lead_hours for row in bulletin.rows] == list(range(42, 50))


def test_direction_is_flipped_into_the_ndbc_convention():
    """The bulletin gives travel direction; NDBC MWD gives the opposite.

    Verified against three years of observations before anything was built on
    it: matching the largest partition to the buoy at lead zero gives a mean
    angular error of 29 degrees with the flip and 151 degrees without it.
    """

    swell = parsed().rows[0].partitions[1]
    assert swell.toward_deg == 108
    assert swell.from_deg == 288  # WNW, which is where December swell comes from
    assert from_direction(0) == 180
    assert from_direction(359) == 179


def minimal(*data_rows: str) -> str:
    """A bulletin with a real header and whatever rows a test needs."""

    return "\n".join(list(ROLLOVER.splitlines()[:7]) + list(data_rows))


def test_wind_sea_marker_and_blank_columns():
    row = parse_bulletin(
        minimal(
            " | 30  2 | 0.48  2   | * 0.30  2.6 286 |   0.29  7.7  99 |"
            "                 |                 |                 |                 |"
        )
    ).rows[0]
    assert [p.wind_sea for p in row.partitions] == [True, False]
    assert len(row.partitions) == 2  # the four blank columns are not partitions


def test_overflow_count_is_kept():
    """`x` counts real wave trains the six columns could not fit."""

    row = parsed().rows[0]
    assert row.fields_found == 3
    assert row.fields_omitted == 0


def test_non_monotonic_rows_raise_rather_than_shifting_a_month():
    lines = ROLLOVER.splitlines()
    lines[8] = lines[8].replace(" | 31 19 |", " | 15 19 |")
    with pytest.raises(BulletinError, match="monotonic"):
        parse_bulletin("\n".join(lines))


def test_garbage_is_rejected_not_silently_empty():
    with pytest.raises(BulletinError, match="Location"):
        parse_bulletin("<html>404 Not Found</html>")


def test_bulletin_url_uses_the_cycle_hour_twice():
    url = bulletin_url("46232", datetime(2025, 7, 1, 12, tzinfo=timezone.utc))
    assert url.endswith("gfs.20250701/12/wave/station/bulls.t12z/gfswave.46232.bull")


def test_archive_rows_store_the_flipped_direction_once():
    rows = rows_for(parsed(), leads=(42,), min_hs=DEFAULT_MIN_HS)
    assert [row["part_from_deg"] for row in rows] == [196, 288, 204]
    assert {row["valid_utc"] for row in rows} == {"2025-12-31T18:00:00Z"}


def test_a_flat_hour_still_produces_a_row():
    """An hour with nothing above threshold is a forecast, not a gap.

    Dropping it would quietly restrict every later statistic to the days with
    waves, which is the subset where the model looks best.
    """

    rows = rows_for(parsed(), leads=(42,), min_hs=5.0)
    assert len(rows) == 1
    assert rows[0]["part_hs_m"] == ""
    assert rows[0]["hs_total_m"] == "0.44"


class TestTheTarFallback:
    """NCEP dropped the per-station bulletin files between 2026-09-15 and
    2026-09-16. The data still ships in `gfswave.tHHz.bull_tar`, so a 404 on
    the per-station path is no longer an answer — it has to be checked against
    the tar before the cycle is called missing. Three days of archiving went
    quietly to zero rows before this was caught."""

    import io
    import tarfile
    import urllib.error
    from datetime import datetime, timezone

    CYCLE = datetime(2026, 9, 18, 0, tzinfo=timezone.utc)

    BULLETIN = (
        "  Location : 46232       (32.52N 117.42W)\n"
        "  Cycle    : 20260918 00 UTC\n"
        "+------+-----------+-----------------+\n"
        "|  day |  hour     | Hst |  1        |\n"
        "+------+-----------+-----------------+\n"
        "| 18 00 |  0 |  0.80 | 0.50 15.3 16 |\n"
    )

    def _tar_bytes(self, members: dict[str, str]) -> bytes:
        import io
        import tarfile

        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as archive:
            for name, text in members.items():
                data = text.encode()
                info = tarfile.TarInfo(f"./{name}")
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
        return buffer.getvalue()

    def _opener(self, payload: bytes):
        import io

        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                self.close()
                return False

        def opener(request, timeout=None):
            return Response(payload)

        return opener

    def test_the_tar_url_is_the_documented_one(self):
        from collector.gfswave import bulletin_tar_url

        url = bulletin_tar_url(self.CYCLE)
        assert url.endswith("gfs.20260918/00/wave/station/gfswave.t00z.bull_tar")

    def test_several_stations_come_out_of_one_download(self):
        from collector.gfswave import fetch_bulletins_from_tar

        payload = self._tar_bytes({
            "gfswave.46232.bull": self.BULLETIN,
            "gfswave.46224.bull": self.BULLETIN.replace("46232", "46224"),
            "gfswave.99999.bull": self.BULLETIN.replace("46232", "99999"),
        })
        found = fetch_bulletins_from_tar(
            ["46232", "46224"], self.CYCLE, opener=self._opener(payload)
        )
        assert sorted(found) == ["46224", "46232"]

    def test_a_station_absent_from_the_tar_is_absent_not_an_error(self):
        from collector.gfswave import fetch_bulletins_from_tar

        payload = self._tar_bytes({"gfswave.46232.bull": self.BULLETIN})
        found = fetch_bulletins_from_tar(
            ["46232", "46224"], self.CYCLE, opener=self._opener(payload)
        )
        assert list(found) == ["46232"]

    def test_a_404_on_the_per_station_path_falls_back_to_the_tar(self, monkeypatch):
        import urllib.error

        from collector import gfswave

        payload = self._tar_bytes({"gfswave.46232.bull": self.BULLETIN})
        tar_opener = self._opener(payload)

        def opener(request, timeout=None):
            if request.full_url.endswith(".bull"):
                raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)
            return tar_opener(request, timeout)

        bulletin = gfswave.fetch_bulletin("46232", self.CYCLE, opener=opener, attempts=1)
        assert bulletin.station_id == "46232"

    def test_a_404_with_the_station_missing_from_the_tar_still_raises(self, monkeypatch):
        import urllib.error

        from collector import gfswave

        payload = self._tar_bytes({"gfswave.46224.bull": self.BULLETIN.replace("46232", "46224")})
        tar_opener = self._opener(payload)

        def opener(request, timeout=None):
            if request.full_url.endswith(".bull"):
                raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)
            return tar_opener(request, timeout)

        with pytest.raises(gfswave.BulletinError):
            gfswave.fetch_bulletin("46232", self.CYCLE, opener=opener, attempts=1)
