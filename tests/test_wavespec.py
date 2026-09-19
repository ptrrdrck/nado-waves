"""Tests for the WAVEWATCH III spectral station product.

Two direction conventions live in one file and they disagree: the grid is
TOWARD and the header's wind is FROM. Both were settled by measurement against
the same cycle's bulletin and against KNZY, and both are pinned here, because
getting either backwards is the fault CLAUDE.md measures at 151 degrees.

The grid's ordering is pinned for a subtler reason. A wrong direction mapping
still integrates to the right TOTAL energy, so Hs looks correct while the
energy sits at the wrong headings — the real bug was caught by the peak
landing on a 3.1 s wind sea where the bulletin said a 15.3 s swell, not by any
total.
"""

from __future__ import annotations

import io
import math
from datetime import datetime, timezone

import pytest

from collector import wavespec
from forecast.transform import GridSpectrum

N_FREQ, N_DIR = 4, 36
FREQS = [0.04, 0.08, 0.16, 0.32]
#: Descending, as WAVEWATCH III writes it — the ordering that broke the
#: interpolation when it was assumed to ascend.
DIRS_RAD = [math.radians((84.8 - 10.0 * i) % 360.0) for i in range(N_DIR)]


def spec_text(*, peak_dir_toward: float = 16.0, u10: float = 4.71,
              udir: float = 284.6, times: int = 2) -> str:
    """A minimal but structurally real WW3 spectral file."""

    lines = [f"'WAVEWATCH III SPECTRA'     {N_FREQ}    {N_DIR}     1 'test'"]
    axis = FREQS + DIRS_RAD
    for i in range(0, len(axis), 8):
        # Full precision: the real files carry enough digits that the
        # radian -> degree round trip is exact to well under a degree, and a
        # lossy fixture would make the convention test look wrong.
        lines.append(" " + " ".join(f"{v:.9E}" for v in axis[i:i + 8]))

    # All the energy in one direction bin and one frequency bin.
    target = min(range(N_DIR),
                 key=lambda d: abs(((math.degrees(DIRS_RAD[d]) - peak_dir_toward + 180) % 360) - 180))
    for t in range(times):
        lines.append(f"2026091{8+t} 000000")
        lines.append(f"'46232     '  32.52-117.43     765.4   {u10} {udir}   0.08 255.0")
        flat = []
        for d in range(N_DIR):
            for f in range(N_FREQ):
                flat.append(10.0 if (d == target and f == 1) else 0.0)
        for i in range(0, len(flat), 7):
            lines.append(" " + " ".join(f"{v:.3E}" for v in flat[i:i + 7]))
    return "\n".join(lines) + "\n"


class TestParsing:
    def test_axes_and_record_count(self):
        records = wavespec.parse_spec(spec_text())
        assert len(records) == 2
        assert records[0].frequencies == FREQS
        assert len(records[0].directions) == N_DIR

    def test_the_grid_is_direction_major(self):
        """Settled by measurement: direction-major reproduces the bulletin's
        Hst to 0.800 m against 0.80, where frequency-major gives 0.876."""

        record = wavespec.parse_spec(spec_text())[0]
        assert len(record.energy) == N_DIR
        assert all(len(row) == N_FREQ for row in record.energy)

    def test_lat_and_lon_running_together_do_not_shift_the_fields(self):
        """'32.52-117.43' has no separating space, so the trailing values are
        counted from the right. Counting from the left reads the current speed
        as a wind direction."""

        record = wavespec.parse_spec(spec_text(u10=7.5, udir=310.0))[0]
        assert record.wind_speed_ms == pytest.approx(7.5)
        assert record.wind_from_deg == pytest.approx(310.0)
        assert record.depth_m == pytest.approx(765.4)
        assert record.current_ms == pytest.approx(0.08)

    def test_limit_hours_stops_early(self):
        assert len(wavespec.parse_spec(spec_text(times=3), limit_hours=0)) == 1

    def test_a_short_grid_is_an_error_not_a_partial_spectrum(self):
        text = spec_text().splitlines()
        with pytest.raises(wavespec.WaveSpecError, match="short"):
            wavespec.parse_spec("\n".join(text[:-2]))

    def test_a_file_that_is_not_a_spectrum_is_refused(self):
        with pytest.raises(wavespec.WaveSpecError, match="not a WAVEWATCH"):
            wavespec.parse_spec("<html>404</html>")


class TestTheTwoConventions:
    def test_grid_directions_are_flipped_from_toward_into_from(self):
        """Measured: flipped agrees with the bulletin's dominant partition to
        4.5 degrees, as-is is 175.5 out."""

        record = wavespec.parse_spec(spec_text())[0]
        for stored, raw in zip(record.directions, DIRS_RAD):
            assert stored == pytest.approx((math.degrees(raw) + 180.0) % 360.0)

    def test_the_energy_peak_lands_on_the_from_direction(self):
        """A partition travelling TOWARD 16 degrees comes FROM 196."""

        record = wavespec.parse_spec(spec_text(peak_dir_toward=16.0))[0]
        peak = max(range(N_DIR), key=lambda d: record.energy[d][1])
        assert abs(((record.directions[peak] - 196.0 + 180) % 360) - 180) <= 10.0

    def test_the_header_wind_is_not_flipped(self):
        """Measured twice: 29.4 degrees as-is against KNZY versus 150.6
        flipped, and 12.6 against the wind-sea partition versus 167.4."""

        record = wavespec.parse_spec(spec_text(udir=284.6))[0]
        assert record.wind_from_deg == pytest.approx(284.6)

    def test_knots_conversion(self):
        record = wavespec.parse_spec(spec_text(u10=10.0))[0]
        assert record.wind_kt == pytest.approx(19.4384, abs=0.01)


class TestFetch:
    CYCLE = datetime(2026, 9, 18, 0, tzinfo=timezone.utc)

    def test_the_url_is_the_documented_one(self):
        url = wavespec.spec_tar_url(self.CYCLE)
        assert url.endswith("gfs.20260918/00/wave/station/gfswave.t00z.spec_tar.gz")

    def _tar_gz(self, members: dict[str, str]) -> bytes:
        import gzip
        import tarfile

        raw = io.BytesIO()
        with tarfile.open(fileobj=raw, mode="w") as archive:
            for name, text in members.items():
                data = text.encode()
                info = tarfile.TarInfo(f"./{name}")
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
        return gzip.compress(raw.getvalue())

    def _opener(self, payload: bytes):
        class Response(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *exc): self.close(); return False
        return lambda request, timeout=None: Response(payload)

    def test_it_pulls_the_requested_station_out_of_the_tar(self):
        payload = self._tar_gz({"gfswave.46232.spec": spec_text(),
                                "gfswave.99999.spec": "other"})
        text, read = wavespec.fetch_station_spec(
            "46232", self.CYCLE, opener=self._opener(payload))
        assert "WAVEWATCH" in text and read > 0
        assert len(wavespec.parse_spec(text)) == 2

    def test_a_missing_station_is_an_error_naming_the_member(self):
        payload = self._tar_gz({"gfswave.99999.spec": spec_text()})
        with pytest.raises(wavespec.WaveSpecError, match="no member"):
            wavespec.fetch_station_spec("46232", self.CYCLE, opener=self._opener(payload))

    def test_a_transport_failure_is_wrapped_not_raised_raw(self):
        import urllib.error

        def boom(request, timeout=None):
            raise urllib.error.URLError("CONNECT tunnel failed, response 403")

        with pytest.raises(wavespec.WaveSpecError):
            wavespec.fetch_station_spec("46232", self.CYCLE, opener=boom)


class TestGridSpectrum:
    def grid(self) -> GridSpectrum:
        record = wavespec.parse_spec(spec_text())[0]
        return GridSpectrum(record.time, record.frequencies,
                            record.directions, record.energy)

    def test_sampling_density_reproduces_c11(self):
        """The control for the interpolation. A mis-mapped direction axis still
        integrates to the right total, which is exactly why this alone did not
        catch the descending-axis bug — but a broken mapping would show up
        here as a per-bin discrepancy."""

        grid = self.grid()
        direct = grid.c11
        sampled = [
            sum(grid.density(i, n + 0.5) * math.radians(1.0) for n in range(360))
            for i in range(len(grid.frequencies))
        ]
        for a, b in zip(direct, sampled):
            if a > 1e-9:
                assert abs(a - b) / a < 0.10

    def test_a_descending_direction_axis_is_handled(self):
        """WAVEWATCH III's axis descends. Assuming it ascends puts the energy
        at the wrong headings while leaving the total unchanged."""

        grid = self.grid()
        assert ((grid.directions[1] - grid.directions[0]) % 360.0) > 180.0
        peak = max(range(len(grid.directions)), key=lambda d: grid.energy[d][1])
        heading = grid.directions[peak]
        assert grid.density(1, heading) > grid.density(1, (heading + 180.0) % 360.0)

    def test_a1_agrees_with_the_populated_direction(self):
        grid = self.grid()
        peak = max(range(len(grid.directions)), key=lambda d: grid.energy[d][1])
        assert abs(((grid.a1[1] - grid.directions[peak] + 180) % 360) - 180) < 1.0

    def test_a_grid_that_does_not_match_its_axis_is_refused(self):
        grid = self.grid()
        with pytest.raises(ValueError, match="does not match"):
            GridSpectrum(grid.time, grid.frequencies, grid.directions[:-1], grid.energy)

    def test_a_ragged_row_is_refused(self):
        grid = self.grid()
        energy = [list(row) for row in grid.energy]
        energy[0] = energy[0][:-1]
        with pytest.raises(ValueError, match="frequency axis"):
            GridSpectrum(grid.time, grid.frequencies, grid.directions, energy)

    def test_density_never_goes_negative(self):
        grid = self.grid()
        assert all(grid.density(1, t) >= 0.0 for t in range(0, 360, 7))
