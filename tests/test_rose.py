"""The Buoys tab's roses (`forecast.rose`, built into buoys.json by
`forecast.buoys`): one spectrum's energy by compass sector and period band,
for every spectrum in the last six hours, at the buoy only."""

from __future__ import annotations

import ast
import json
import re
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
        assert {k: v for k, v in frame.items() if k != "train_share"} == rose.frame(sp.with_spread("mem"))

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

    def test_each_buoys_scale_is_its_own_largest_petal_rounded_up(self):
        """Each buoy's own loop sets its scale (shared across both, 46232's
        largest petal filled 22% of its rose); the outermost ring is that
        petal rounded UP to the next ring, always drawn (an edge at the petal
        exactly left petals past the last ring); and the rings are EVEN, at
        most five (2, 4 and 5 ft read as uneven; owner's reports, 2026-10-06
        and -07). Run in node against the page's own function."""

        import subprocess

        scale = PAGE[PAGE.index("function roseScale("):]
        scale = scale[:scale.index("\n}\n") + 3]
        assert "roseOf(station)" in scale and "BUOYS.roses" not in scale
        assert "rosePlot(v.state, ROSE_MODE, station)" in PAGE
        script = (
            "const FT_PER_M = 3.28084; let FRAMES;\n"
            "const roseOf = () => ({frames: FRAMES});\n" + scale +
            "const out = [];\n"
            "for (const [h, s] of [[0.41, 0.26], [1.2526, 0.431], [0.05, 0.02], [1.8288, 0.10],"
            " [0.5517, 0.24]]) {\n"
            "  FRAMES = [{sector_hs_m: [h, 0.1], period_share: [[s, 0, 0, 0, 0], [0.01, 0, 0, 0, 0]]}];\n"
            "  out.push([roseScale('height', 'x'), roseScale('period', 'x')]);\n"
            "}\nconsole.log(JSON.stringify(out));\n")
        got = json.loads(subprocess.run(["node", "-e", script], capture_output=True,
                                        text=True, check=True).stdout)
        # 1.35 ft -> 2; 4.11 -> 5; a near-empty loop still draws 1 ft; exactly
        # 6.0 ft stays on 6 (in 2 ft rings); 1.81 ft (46232, 7 Oct) -> 2.
        assert [g[0]["max"] for g in got] == [2, 5, 1, 6, 2]
        assert [g[0]["step"] for g in got] == [1, 1, 1, 2, 1]
        assert [round(g[1]["max"], 2) for g in got] == [0.3, 0.5, 0.05, 0.1, 0.25]
        for height, period in got:
            for sc in (height, period):
                assert sc["rings"][-1] == sc["max"] and len(sc["rings"]) <= 5
                assert sc["rings"] == pytest.approx(
                    [sc["step"] * (k + 1) for k in range(len(sc["rings"]))])

    def test_the_scale_is_a_line_under_the_rose_and_play_sits_by_the_time(self):
        """Owner's request, 2026-10-07: no figure on the plot, where every
        spot is a bearing; the scale in one line under it; play / pause as
        symbols, left of the six hours."""

        block = PAGE[PAGE.index("function roseBlock("):]
        block = block[:block.index("\n}\n")]
        assert (block.index('class="rose-plot"') < block.index('class="rose-scale"')
                < block.index('class="rose-time">${rosePlayButton()}')
                < block.index('class="rose-line"'))
        assert "rose-head" in block and "rosePlayButton" not in block[:block.index('class="readout"')]
        plot = PAGE[PAGE.index("function rosePlot("):]
        assert 'class="rl"' not in plot[:plot.index("\n}\n")]
        assert 'aria-label="${ROSE_PLAYING ? "Pause" : "Play"}"' in PAGE


class TestTheLoopsStart:
    def test_every_buoy_has_a_frame_where_the_loop_starts(self):
        """46047 stamps :20/:50 and 46232 :00, so the oldest frame overall is
        46047's, ten minutes before 46232's first: the loop opened on "No
        spectrum yet" at 46232 (owner's report, 2026-10-07). Run in node
        against the page's own roseSpan and roseAt."""

        import subprocess

        def fn(name):
            body = PAGE[PAGE.index(f"function {name}("):]
            return body[:body.index("\n}\n") + 3]

        script = (
            "let BUOYS; const clock = (iso) => iso.slice(11, 16);\n"
            "const roseTime = (f) => new Date(f.time_utc).getTime();\n"
            + fn("roseSpan") + fn("roseAt") +
            "const at = (h, m) => `2026-10-07T${h}:${m}:00Z`;\n"
            "BUOYS = {roses: {\n"
            "  '46232': {interval_min: 60, frames: [14, 15, 16, 17, 18, 19].map((h) => ({time_utc: at(h, '00')}))},\n"
            "  '46047': {interval_min: 30, frames: [[13, '50'], [14, '20'], [14, '50'], [19, '20']]"
            ".map(([h, m]) => ({time_utc: at(h, m)}))}}};\n"
            "const span = roseSpan();\n"
            "console.log(JSON.stringify({t0: new Date(span.t0).toISOString(),"
            " a: roseAt(BUOYS.roses['46232'], span.t0), b: roseAt(BUOYS.roses['46047'], span.t0)}));\n")
        got = json.loads(subprocess.run(["node", "-e", script], capture_output=True,
                                        text=True, check=True).stdout)
        assert got["t0"] == "2026-10-07T14:00:00.000Z"
        assert got["a"]["frame"]["time_utc"] == "2026-10-07T14:00:00Z"
        # 46047's 13:50 frame is the one in force at 14:00, not dropped.
        assert got["b"]["frame"]["time_utc"] == "2026-10-07T13:50:00Z"


class TestATrainsPetals:
    """A tapped train lights its period range in every frame (owner's
    request, 2026-10-08): the newest spectrum's trains, their ranges, and
    each frame's share within them. Nothing follows a train between
    spectra."""

    def two_trains(self, at):
        """A 15 s swell from 200° and a 4 s sea from 290°, summed."""

        a = spectrum(at, peak_dir=200.0, tp=15.0, hs=1.2)
        b = spectrum(at, peak_dir=290.0, tp=4.0, hs=0.8)
        import math as m
        c11 = [x + y for x, y in zip(a.c11, b.c11)]
        a1 = [m.degrees(m.atan2(x * m.sin(m.radians(200)) + y * m.sin(m.radians(290)),
                                x * m.cos(m.radians(200)) + y * m.cos(m.radians(290)))) % 360
              for x, y in zip(a.c11, b.c11)]
        from forecast.transform import Spectrum
        return Spectrum(at, a.frequencies, c11, a1, a1, a.r1, a.r2)

    def test_the_trains_are_the_readings_own_in_order(self, tmp_path):
        write_many(tmp_path, "46047", [self.two_trains(MOMENT - timedelta(minutes=m))
                                       for m in (70, 40, 10)])
        payload = buoys.build(data_dir=tmp_path, now=MOMENT)
        reading = payload["buoys"][0]
        r = payload["roses"]["46047"]
        assert r["trains_from_utc"] == reading["observed_utc"]
        assert len(r["trains"]) == len(reading["trains"]) >= 2
        newest = r["frames"][-1]
        for t, share in zip(reading["trains"], newest["train_share"]):
            # The range's energy in the newest frame IS the train.
            assert newest["hs_m"] * math.sqrt(sum(share)) == pytest.approx(t["hs_m"], rel=0.01)
        for t in r["trains"]:
            assert t["period_lo_s"] < t["period_hi_s"]

    def test_every_frame_carries_the_newest_trains_ranges(self, tmp_path):
        write_many(tmp_path, "46047", [spectrum(MOMENT - timedelta(minutes=m)) for m in (130, 70, 10)])
        r = buoys.build(data_dir=tmp_path, now=MOMENT)["roses"]["46047"]
        assert all(len(f["train_share"]) == len(r["trains"]) for f in r["frames"])
        assert all(len(row) == 16 for f in r["frames"] for row in f["train_share"])

    def test_no_frames_no_trains(self, tmp_path):
        write_spectrum(tmp_path, "46232", spectrum(MOMENT - timedelta(minutes=30)))
        r = buoys.build(data_dir=tmp_path, now=MOMENT)["roses"]["46047"]
        assert r["frames"] == [] and "trains" not in r

    def test_a_trains_bins_are_not_its_identity(self):
        from forecast.transform import Train

        assert Train(1.0, 12.0, 200.0, 0.5, bins=(3, 4)) == Train(1.0, 12.0, 200.0, 0.5)

    def test_the_page_names_the_range_not_the_train(self):
        """In an older frame the range may hold another swell: the readout
        says the period range, never "this train"."""

        read = PAGE[PAGE.index("function roseReadout("):]
        read = read[:read.index("\n}\n")]
        assert "roseRange(station, k)" in read
        shown = " ".join(re.findall(r"`[^`]*`", read)).lower()
        assert "train" not in re.sub(r"\$\{[^}]*\}", "", shown)
        assert 'data-rose-train="${i}"' in PAGE
        assert 'aria-label="Show this period range on the rose"' in PAGE


class TestADividedTrainsPetals:
    """A band from two directions is two trains on one period range
    (BRIEFING §40): each lights its own headings, not its twin's."""

    def two_directions(self, at):
        """A 14 s swell from 190° and another from 290°, both 12° wide:
        moments summed, so maximum entropy reads two lobes in one band."""

        from forecast.transform import Spectrum

        base = spectrum(at, tp=14.0, hs=1.2)
        sig = math.radians(12.0)
        r1, r2 = math.exp(-sig * sig / 2), math.exp(-2 * sig * sig)
        c11, a1, a2, R1, R2 = [], [], [], [], []
        for e in base.c11:
            parts = [(0.6 * e, 190.0), (0.4 * e, 290.0)]
            tot = sum(p for p, _ in parts) or 1.0
            m = [sum(p * r * f(k * math.radians(d)) for p, d in parts) / tot
                 for k, r, f in ((1, r1, math.cos), (1, r1, math.sin), (2, r2, math.cos), (2, r2, math.sin))]
            c11.append(e)
            a1.append(math.degrees(math.atan2(m[1], m[0])) % 360)
            a2.append((math.degrees(math.atan2(m[3], m[2])) / 2) % 360)
            R1.append(math.hypot(m[0], m[1]))
            R2.append(math.hypot(m[2], m[3]))
        return Spectrum(at, base.frequencies, c11, a1, a2, R1, R2)

    def test_each_lights_its_own_side_and_together_the_band(self, tmp_path):
        write_many(tmp_path, "46047", [self.two_directions(MOMENT - timedelta(minutes=m))
                                       for m in (70, 40, 10)])
        payload = buoys.build(data_dir=tmp_path, now=MOMENT)
        reading = payload["buoys"][0]
        r = payload["roses"]["46047"]
        divided = [k for k, t in enumerate(r["trains"]) if "from_lo_deg" in t]
        assert len(divided) == 2, r["trains"]
        a, b = (r["trains"][k] for k in divided)
        assert (a["period_lo_s"], a["period_hi_s"]) == (b["period_lo_s"], b["period_hi_s"])
        newest = r["frames"][-1]
        for k in divided:
            share = newest["train_share"][k]
            # The lit petals ARE that train, and they sit on its own side.
            assert newest["hs_m"] * math.sqrt(sum(share)) == pytest.approx(
                reading["trains"][k]["hs_m"], rel=0.01)
            lit = max(range(16), key=share.__getitem__)
            assert abs((lit * 22.5 - reading["trains"][k]["from_deg"] + 180) % 360 - 180) <= 22.5
        # Between them, nothing lit twice.
        whole = [x + y for x, y in zip(*(newest["train_share"][k] for k in divided))]
        assert sum(whole) <= 1.0 + 1e-3
