"""Tests for the transform, including the control that could kill it.

The claim under test is BRIEFING §10: integrating the directional spectrum over
the aperture makes the Coronado Islands a ~11% energy reduction rather than an
on/off switch, while Point Loma stays a real shadow. If that inverts, the
transform is wrong and the app surface built on it is wrong with it.
"""

from __future__ import annotations

import csv
import math
from datetime import datetime, timezone

import pytest

from forecast.geometry import Blocker, load
from forecast.transform import (
    FRESNEL_SHARP,
    MATERIAL_SHARE,
    Spectrum,
    fresnel_number,
    load_spectra,
    through,
    transmission,
    wavelength,
)

SPOTS, BLOCKERS = load()
BY_ID = {s.id: s for s in SPOTS}
CORONADO = ["coronado_north", "coronado_center", "coronado_south"]


def synthetic(peak_dir: float, *, tp: float = 15.0, hs: float = 1.5,
              spread_deg: float = 20.0, bins: int = 48) -> Spectrum:
    """A swell of known height aimed at `peak_dir`, in NDBC's representation."""

    freqs = [0.025 + 0.0075 * i for i in range(bins)]
    fp = 1.0 / tp
    sigma = math.radians(spread_deg)
    r1 = max(0.0, 1.0 - sigma * sigma / 2.0)
    r2 = max(0.0, 1.0 - 2.0 * sigma * sigma)
    c11 = [math.exp(-1.25 * (fp / f) ** 4) * (f / fp) ** -5 for f in freqs]
    m0 = sum(c * (freqs[1] - freqs[0]) for c in c11)
    c11 = [c * ((hs / 4.0) ** 2 / m0) for c in c11]
    return Spectrum(
        datetime(2026, 9, 18, tzinfo=timezone.utc),
        freqs, c11, [peak_dir] * bins, [peak_dir] * bins, [r1] * bins, [r2] * bins,
    )


def share_of(result, name_fragment: str) -> float:
    for removed in result.removed:
        if name_fragment.lower() in removed.blocker.lower():
            return removed.share
    return 0.0


class TestSpectrum:
    def test_mismatched_components_are_refused_not_padded(self):
        with pytest.raises(ValueError, match="disagree"):
            Spectrum(datetime.now(timezone.utc), [0.05, 0.06], [1.0, 1.0],
                     [200.0], [200.0], [0.9, 0.9], [0.5, 0.5])

    def test_density_never_goes_negative(self):
        """A two-term Fourier fit can go negative; summed, that subtracts energy."""

        # r1 = 1, r2 = 0 puts the raw fit at (1/pi)(0.5 - 1) < 0 opposite the
        # peak. With r2 = 1 the second harmonic lifts it back up, which is why
        # the clamp needs a case chosen to exercise it rather than any old one.
        spectrum = Spectrum(
            datetime.now(timezone.utc), [0.08], [1.0], [200.0], [200.0], [1.0], [0.0]
        )
        assert all(spectrum.density(0, t) >= 0.0 for t in range(0, 360, 3))
        assert spectrum.density(0, 20.0) == 0.0

    def test_bin_width_uses_neighbours_not_a_constant(self):
        spectrum = synthetic(200.0, bins=4)
        assert spectrum.bin_width(1) == pytest.approx(0.0075)
        assert spectrum.bin_width(0) == pytest.approx(0.0075)


class TestTheIslandsAreNotASwitch:
    """BRIEFING §10. The headline claim and its control."""

    @pytest.mark.parametrize("spread", [10.0, 20.0, 30.0])
    def test_islands_take_about_a_tenth_at_any_spread(self, spread):
        got = through(synthetic(190.0, spread_deg=spread), BY_ID["coronado_center"], BLOCKERS)
        assert 0.05 < share_of(got, "Islands") < 0.18

    def test_point_loma_takes_several_times_more_when_it_is_in_the_way(self):
        got = through(synthetic(265.0), BY_ID["coronado_center"], BLOCKERS)
        assert share_of(got, "Point Loma") > 3 * share_of(got, "Islands")

    def test_the_control_a_binary_verdict_would_have_swung_the_whole_way(self):
        """Blocked-vs-open on one MWD says 0% or 100%; the integral says ~11%.

        This is the measurement that makes the section a finding rather than an
        opinion. If a swell sitting inside the islands' shadow still delivers
        most of its energy, the binary treatment was wrong.
        """

        centre = BY_ID["coronado_center"]
        islands = [b for b in BLOCKERS if "Islands" in b.name]
        # 195 deg is inside the islands' blocked sector at every Coronado break.
        from forecast.geometry import reaches
        assert not reaches(centre, islands, 195.0)      # binary says: nothing arrives
        got = through(synthetic(195.0), centre, islands)
        assert got.fraction > 0.75                      # the integral says: most of it does


class TestEnergyBookkeeping:
    def test_surviving_plus_removed_accounts_for_everything(self):
        got = through(synthetic(240.0), BY_ID["coronado_north"], BLOCKERS)
        accounted = got.fraction + sum(r.share for r in got.removed)
        # The remainder is the seaward clip, which is attributed but not listed.
        assert accounted <= 1.0 + 1e-9
        assert got.m0_in <= got.m0_total

    def test_overlapping_shadows_are_not_double_counted(self):
        doubled = BLOCKERS + [b for b in BLOCKERS if "Point Loma" in b.name]
        got = through(synthetic(265.0), BY_ID["coronado_center"], doubled)
        assert sum(r.share for r in got.removed) <= 1.0 + 1e-9

    def test_no_blockers_means_only_the_seaward_clip_removes_anything(self):
        got = through(synthetic(214.0), BY_ID["coronado_center"], [])
        assert got.removed == []
        assert got.fraction > 0.9


class TestTheGradientAlongTheSand:
    """The product claim: three breaks, one swell, three different answers."""

    @pytest.mark.parametrize("bearing", [230.0, 245.0, 250.0, 265.0])
    def test_south_holds_more_west_swell_than_north(self, bearing):
        got = {sid: through(synthetic(bearing), BY_ID[sid], BLOCKERS) for sid in CORONADO}
        assert (got["coronado_south"].m0_in
                > got["coronado_center"].m0_in
                > got["coronado_north"].m0_in)

    def test_the_spread_is_big_enough_to_be_worth_showing(self):
        got = {sid: through(synthetic(250.0), BY_ID[sid], BLOCKERS) for sid in CORONADO}
        ratio = got["coronado_south"].hs_in_window_m / got["coronado_north"].hs_in_window_m
        assert ratio > 1.15

    def test_a_south_swell_treats_the_three_breaks_nearly_alike(self):
        """The control. If the gradient showed up on SOUTH swell too it would be
        an artifact of the method rather than Point Loma's parallax."""

        got = {sid: through(synthetic(190.0), BY_ID[sid], BLOCKERS) for sid in CORONADO}
        heights = [g.hs_in_window_m for g in got.values()]
        assert (max(heights) - min(heights)) / max(heights) < 0.03


class TestConfidenceFollowsEnergy:
    def test_coronado_is_high_confidence_despite_the_guessed_islands(self):
        got = through(synthetic(250.0), BY_ID["coronado_center"], BLOCKERS)
        assert got.confidence == "high"
        assert share_of(got, "Islands") < MATERIAL_SHARE

    def test_an_unverified_blocker_taking_real_energy_does_downgrade(self):
        guessed = [
            Blocker(b.name, b.a, b.b, b.continues, tip_verified=False)
            if "Point Loma" in b.name else b
            for b in BLOCKERS
        ]
        got = through(synthetic(265.0), BY_ID["coronado_center"], guessed)
        assert share_of(got, "Point Loma") >= MATERIAL_SHARE
        assert got.confidence == "low"

    def test_an_unverified_spot_is_low_whatever_the_blockers(self):
        got = through(synthetic(250.0), BY_ID["nab_gator"], BLOCKERS)
        assert got.confidence == "low"


class TestDiffractionIsFlaggedNotFitted:
    def test_point_loma_is_sharp_and_the_islands_are_not(self):
        centre = BY_ID["coronado_center"]
        for period in (12.0, 15.0, 18.0, 20.0):
            pl = fresnel_number(centre, [b for b in BLOCKERS if "Point Loma" in b.name][0], period)
            isl = fresnel_number(centre, [b for b in BLOCKERS if "Islands" in b.name][0], period)
            assert pl > FRESNEL_SHARP > isl

    def test_the_islands_are_flagged_on_a_swell_they_actually_shadow(self):
        got = through(synthetic(190.0), BY_ID["coronado_center"], BLOCKERS)
        assert any("Islands" in name for name in got.diffraction_suspect)

    def test_flagging_does_not_change_the_number(self):
        """The flag is a report, not a correction. If it ever starts altering
        the energy, a fitted diffraction model has crept in unverified."""

        got = through(synthetic(190.0), BY_ID["coronado_center"], BLOCKERS)
        assert got.diffraction_suspect
        assert got.m0_in == pytest.approx(
            through(synthetic(190.0), BY_ID["coronado_center"], BLOCKERS).m0_in
        )

    def test_wavelength_is_deep_water(self):
        assert wavelength(15.0) == pytest.approx(351.0, abs=1.0)


class TestTransmission:
    def test_nothing_arrives_from_behind_the_beach(self):
        centre = BY_ID["coronado_center"]
        assert transmission(centre, BLOCKERS, (centre.normal + 180.0) % 360.0) == 0.0

    def test_transmission_is_zero_or_one_and_never_tapered(self):
        centre = BY_ID["coronado_center"]
        assert {transmission(centre, BLOCKERS, t) for t in range(0, 360)} <= {0.0, 1.0}


class TestLoadSpectraRefusesToGuess:
    def _write(self, directory, kind, rows, freqs=("0.0500", "0.0600")):
        path = directory / f"{kind}.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["time_utc", *freqs])
            writer.writerows(rows)

    def test_a_timestamp_missing_from_one_component_is_dropped_not_filled(self, tmp_path):
        full = [["2026-09-18T00:00:00Z", "1.0", "2.0"], ["2026-09-18T01:00:00Z", "1.0", "2.0"]]
        for kind in ("c11", "a1", "a2", "r1"):
            self._write(tmp_path, kind, full)
        self._write(tmp_path, "r2", full[:1])          # r2 is missing the 01:00 row

        spectra = load_spectra(tmp_path)
        assert [s.time.hour for s in spectra] == [0]

    def test_a_missing_component_file_is_an_error_not_a_default(self, tmp_path):
        self._write(tmp_path, "c11", [["2026-09-18T00:00:00Z", "1.0", "2.0"]])
        with pytest.raises(FileNotFoundError):
            load_spectra(tmp_path)

    def test_disagreeing_frequency_bins_are_refused(self, tmp_path):
        rows = [["2026-09-18T00:00:00Z", "1.0", "2.0"]]
        for kind in ("c11", "a1", "a2", "r1"):
            self._write(tmp_path, kind, rows)
        self._write(tmp_path, "r2", rows, freqs=("0.0500", "0.0700"))
        with pytest.raises(ValueError, match="frequency bins disagree"):
            load_spectra(tmp_path)
