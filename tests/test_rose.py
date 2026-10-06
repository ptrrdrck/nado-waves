"""The Buoys tab's roses (`forecast.rose`, built into buoys.json by
`forecast.buoys`): one spectrum's energy by compass sector and period band,
for every spectrum in the last six hours, at the buoy only."""

from __future__ import annotations

import ast
import math
from datetime import timedelta
from pathlib import Path

import pytest

from forecast import buoys, rose
from forecast.transform import at_buoy

from test_buoys import MOMENT, PAGE, write_spectrum
from test_now import spectrum

ROOT = Path(__file__).resolve().parent.parent


def write_many(data_dir: Path, station: str, spectra) -> None:
    """All stamps into one set of five files, as the collector keeps them."""

    import csv

    folder = data_dir / "spectra" / station
    folder.mkdir(parents=True, exist_ok=True)
    for kind in ("c11", "a1", "a2", "r1", "r2"):
        with (folder / f"{kind}.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["time_utc", *[f"{f:.4f}" for f in spectra[0].frequencies]])
            for sp in spectra:
                w.writerow([sp.time.strftime("%Y-%m-%dT%H:%M:%SZ"), *getattr(sp, kind)])


class TestOneFrame:
    @pytest.mark.parametrize("spread", ["mem", "fourier"])
    def test_the_sectors_sum_to_the_blocks_own_height(self, spread):
        """Integrated as `at_buoy` integrates, so the rose and the reading
        above it are one m0."""

        sp = spectrum(MOMENT, peak_dir=250.0).with_spread(spread)
        got = rose.frame(sp)
        assert got["hs_m"] == pytest.approx(at_buoy(sp).hs_m, abs=1e-3)
        from_petals = 4.0 * math.sqrt(sum((h / 4.0) ** 2 for h in got["sector_hs_m"]))
        assert from_petals == pytest.approx(got["hs_m"], rel=1e-3)

    def test_the_shares_are_the_whole_spectrum(self):
        got = rose.frame(spectrum(MOMENT).with_spread("mem"))
        assert sum(map(sum, got["period_share"])) == pytest.approx(1.0, abs=2e-3)
        assert len(got["sector_hs_m"]) == len(got["period_share"]) == 16
        assert all(len(row) == len(rose.PERIOD_EDGES_S) + 1 for row in got["period_share"])

    def test_the_petals_point_where_the_swell_comes_from(self):
        """FROM, as NDBC reports it. The energy-weighted bearing of the
        petals, not the largest one: maximum entropy reads this fixture's
        moments as two lobes either side of 300°."""

        got = rose.frame(spectrum(MOMENT, peak_dir=300.0).with_spread("mem"))
        energy = [h * h for h in got["sector_hs_m"]]
        s = sum(e * math.sin(math.radians(22.5 * i)) for i, e in enumerate(energy))
        c = sum(e * math.cos(math.radians(22.5 * i)) for i, e in enumerate(energy))
        assert math.degrees(math.atan2(s, c)) % 360 == pytest.approx(300, abs=4)
        assert got["sector_hs_m"][rose.POINTS.index("SE")] < 0.02 * got["hs_m"]

    def test_a_long_swell_lands_in_its_own_band(self):
        got = rose.frame(spectrum(MOMENT, tp=15.0).with_spread("mem"))
        by_band = [sum(row[b] for row in got["period_share"]) for b in range(5)]
        assert max(range(5), key=by_band.__getitem__) == rose.band_of(15.0) == 3

    def test_sectors_are_centred_on_their_points(self):
        assert [rose.sector_of(t) for t in (0, 11.2, 11.3, 180, 348.7, 348.8)] == [0, 0, 1, 8, 15, 0]
        assert [rose.band_of(t) for t in (5, 8, 10.9, 11, 16.9, 17, 25)] == [0, 1, 1, 2, 3, 4, 4]


class TestTheLoop:
    def test_only_the_last_six_hours_and_nothing_filled(self, tmp_path):
        """A missing stamp is a missing frame; one past the build is not shown."""

        stamps = [MOMENT - timedelta(minutes=m) for m in (430, 350, 230, 110, 20)]
        write_many(tmp_path, "46047", [spectrum(t) for t in stamps])
        got = buoys.build(data_dir=tmp_path, now=MOMENT)["roses"]["46047"]
        times = [f["time_utc"] for f in got["frames"]]
        assert times == [t.strftime("%Y-%m-%dT%H:%M:%SZ") for t in stamps[1:]]
        assert got["interval_min"] == 30.0

    def test_each_buoy_has_its_own_and_none_is_borrowed(self, tmp_path):
        write_spectrum(tmp_path, "46232", spectrum(MOMENT - timedelta(minutes=30)))
        got = buoys.build(data_dir=tmp_path, now=MOMENT)["roses"]
        assert list(got) == ["46232", "46047"]
        assert len(got["46232"]["frames"]) == 1 and got["46232"]["interval_min"] == 60.0
        assert got["46047"]["frames"] == []

    def test_read_by_maximum_entropy_like_the_reading_above_it(self, tmp_path):
        sp = spectrum(MOMENT - timedelta(minutes=40), peak_dir=290.0)
        write_spectrum(tmp_path, "46047", sp)
        payload = buoys.build(data_dir=tmp_path, now=MOMENT)
        frame = payload["roses"]["46047"]["frames"][-1]
        assert frame["hs_m"] == pytest.approx(payload["buoys"][0]["hs_m"], abs=2e-3)
        assert frame == rose.frame(sp.with_spread("mem"))

    def test_it_carries_nothing_to_a_break(self):
        tree = ast.parse((ROOT / "forecast" / "rose.py").read_text())
        names = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
        names |= {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        for carrier in ("through", "carry", "summarise", "local_sea", "load_tables"):
            assert carrier not in names, carrier


class TestOnThePage:
    def test_live_only_under_each_buoys_own_reading(self):
        """46232's rose in its pane, above the card's provenance; 46047's in
        its block, above its own. Not on the Forecast tab: GFS-Wave's run has
        no spectrum at the buoy to draw."""

        calls = PAGE.split("rows.push(swellCard(")
        assert "buoyRose: roseBlock(" in calls[1].split("}));")[0]
        assert "buoyRose" not in calls[2].split("}));")[0]
        block = PAGE[PAGE.index("function contextBuoy("):]
        block = block[:block.index("\n}\n")]
        assert block.index("roseBlock(b.station)") < block.index("srcLines(")

    def test_one_switch_and_one_clock_for_both(self):
        assert 'const ROSE_MODES = [{id: "height", label: "Height"}, {id: "period", label: "Period"}];' in PAGE
        assert "KEEP.roseMode" in PAGE
        assert "prefers-reduced-motion" in PAGE.split("// THE ROSES")[1]
