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

from test_buoys import MOMENT, PAGE, _fn, write_spectrum
from test_buoys import block as by_station
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
        assert list(got) == ["46232", "46086", "46047"]
        assert len(got["46232"]["frames"]) == 1 and got["46232"]["interval_min"] == 60.0
        assert got["46047"]["frames"] == [] and got["46086"]["frames"] == []
        assert got["46086"]["interval_min"] == 30.0

    def test_read_by_maximum_entropy_like_the_reading_above_it(self, tmp_path):
        sp = spectrum(MOMENT - timedelta(minutes=40), peak_dir=290.0)
        write_spectrum(tmp_path, "46047", sp)
        payload = buoys.build(data_dir=tmp_path, now=MOMENT)
        frame = payload["roses"]["46047"]["frames"][-1]
        assert frame["hs_m"] == pytest.approx(by_station(payload, "46047")["hs_m"], abs=2e-3)
        assert {k: v for k, v in frame.items() if k != "train_share"} == rose.frame(sp.with_spread("mem"))

    def test_it_carries_nothing_to_a_break(self):
        tree = ast.parse((ROOT / "forecast" / "rose.py").read_text())
        names = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
        names |= {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        for carrier in ("through", "carry", "summarise", "local_sea", "load_tables"):
            assert carrier not in names, carrier


class TestOnThePage:
    def test_under_each_buoys_own_reading_on_both_chains(self):
        """46232's rose in its pane, above the card's provenance; 46047's in
        its block, above its own. On the Forecast tab too since 2026-11-23
        (owner's request): GFS-Wave's own grid at 46232, from forecast.json."""

        calls = PAGE.split("rows.push(swellCard(")
        assert "buoyRose: roseBlock(NOW && NOW.station)" in calls[1].split("}));")[0]
        assert "buoyRose: roseBlock(DATA.station)" in calls[2].split("}));")[0]
        block = PAGE[PAGE.index("function contextBuoy("):]
        block = block[:block.index("\n}\n")]
        assert block.index("roseBlock(b.station)") < block.index("srcLines(")

    def test_one_switch_and_one_clock_for_both(self):
        assert ('const ROSE_MODES = [{id: "height", label: "Height", symbol: "ft"},'
                ' {id: "period", label: "Period", symbol: "s"}];') in PAGE
        assert "KEEP.roseMode" in PAGE

    def test_a_rose_comes_into_view_paused_on_the_newest_spectrum(self):
        """Owner's request, 2026-10-11: on load, on the LIVE tab, on the
        Buoys tab and on a buoy's headline unfolding, the roses are paused on
        the newest spectrum -- the one the headline reads -- for every
        reader, not only one who asked for less motion."""

        assert "let ROSE_PLAYING = false;\nlet ROSE_PHASE = ROSE_PLAY_MS;" in PAGE
        assert "ROSE_STILL" not in PAGE
        shown = PAGE[PAGE.index("function roseShown("):]
        shown = shown[:shown.index("\n}\n")]
        assert "ROSE_PHASE = ROSE_PLAY_MS;" in shown and "setRosePlaying(false);" in shown
        assert "ROSE_PHASE >= ROSE_PLAY_MS ? span.t1" in PAGE     # that phase is the newest
        assert 'if (id === BUOY_TAB && SWELL_TAB !== BUOY_TAB) {\n    roseShown();' in PAGE
        assert 'if (mode !== MODE) {\n    ROSE_TRAIN = {};\n    roseShown();' in PAGE
        # On unfolding: run by the fold's slide once it is shown, before it
        # is measured (`slideFolds` calls `before` only when opening).
        assert "slideFolds(folds, open, roseShown);" in PAGE
        assert "if (open && before) before();" in PAGE

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
        units = PAGE[PAGE.index("let UNITS = "):PAGE.index("\nconst dual = ")]
        ht = PAGE[PAGE.index("const roseHt = "):]
        ht = ht[:ht.index(";\n") + 2]
        frames_of = PAGE[PAGE.index("const roseFramesOf = "):]
        frames_of = frames_of[:frames_of.index(";\n") + 2]
        script = (
            "const FT_PER_M = 3.28084; let FRAMES;\n" + units + "\n" + ht + frames_of +
            "const roseOf = () => ({frames: FRAMES});\n" + scale +
            "const out = [];\n"
            "for (const [h, s] of [[0.41, 0.26], [1.2526, 0.431], [0.05, 0.02], [1.8288, 0.10],"
            " [0.5517, 0.24]]) {\n"
            "  FRAMES = [{sector_hs_m: [h, 0.1], period_share: [[s, 0, 0, 0, 0], [0.01, 0, 0, 0, 0]]}];\n"
            "  out.push([roseScale('height', 'x'), roseScale('period', 'x')]);\n"
            "}\nUNITS = 'metric'; const metric = [];\n"
            "for (const h of [0.41, 1.2526, 0.05, 1.8288, 0.5517]) {\n"
            "  FRAMES = [{sector_hs_m: [h, 0.1], period_share: [[0.1, 0, 0, 0, 0]]}];\n"
            "  metric.push(roseScale('height', 'x'));\n"
            "}\nconsole.log(JSON.stringify(out)); console.log(JSON.stringify(metric));\n")
        lines = subprocess.run(["node", "-e", script], capture_output=True,
                               text=True, check=True).stdout.splitlines()
        got, metric = json.loads(lines[0]), json.loads(lines[1])
        # On Metric (owner's call, 2026-10-28) the rings step in metres, the
        # same rule: 0.41 m -> 0.5 in 0.25 m rings; 1.25 -> 1.5 in 0.5; 0.05
        # still draws 0.25; 1.83 -> 2 in 0.5; 0.55 -> 0.75 in 0.25.
        assert [g["max"] for g in metric] == [0.5, 1.5, 0.25, 2, 0.75]
        assert [g["step"] for g in metric] == [0.25, 0.5, 0.25, 0.5, 0.25]
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

    def test_the_rose_sits_on_a_plate_its_readout_in_the_tray(self):
        """Owner's requests, 2026-10-07, 2026-11-11 and 2026-11-17: no
        figure on the plot; along the plate's foot the bar -- play / pause,
        the six hours, then ft / s; the scale line and the Period legend in
        the tray under the plate."""

        block = PAGE[PAGE.index("function roseBlock("):]
        block = block[:block.index("\n}\n")]
        assert (block.index('class="rose-plate">') < block.index('class="rose-plot"')
                < block.index('class="rose-bar">${rosePlayButton()}')
                < block.index('class="rose-track" data-rose-scrub') < block.index('class="rose-when"')
                < block.index('class="rose-rail"') < block.index("${roseSwitch()}</div>")
                < block.index('class="rose-tray"')
                < block.index('class="rose-scale') < block.index("${roseLegend(ROSE_MODE)}"))

    def test_the_bar_is_the_break_maps_fill_bar(self):
        """Owner's request, 2026-11-17: the bar under the rose looks as the
        break tab's ray animation bar does -- play, the six hours in a
        card-coloured pill with the moment shown, then ft / s in the
        bottom-right corner -- each 28 px, 4 px apart and 4 px inside the
        hairline, 6 px under the rose so the plate keeps its height."""

        css = lambda sel: PAGE[PAGE.index(sel + "{") + len(sel) + 1:].split("}", 1)[0]
        bar = css(".rose .rose-bar")
        assert "gap:4px;height:28px;margin:6px 4px 4px" in bar
        both = css(".rose .rose-play,.rose .rose-switch")
        assert "width:28px;height:28px" in both and "border-radius:6px" in both
        assert "box-shadow:0 1px 3px rgba(0,0,0,.35)" in both
        # The pill as the fill bar's .sf-track, its line and dot as .sf-line,
        # .sf-past and .sf-head.
        for rose_sel, fill_sel in ((".rose .rose-track", ".sf-track"), (".rose .rose-rail", ".sf-line"),
                                   (".rose .rose-past", ".sf-past"), (".rose .rose-head", ".sf-head")):
            ours, theirs = css(rose_sel), css(fill_sel)
            for decl in theirs.replace("\n", "").split(";"):
                decl = decl.strip()
                if decl and not decl.startswith(("cursor", "touch-action", "-webkit")):
                    assert decl in ours.replace("\n  ", ""), (rose_sel, decl)
        # The old top-left corner and the SVG timeline are gone.
        assert ".rose-switch{position:absolute" not in PAGE and "rose-line" not in PAGE
        # A tick for every spectrum still: a missing one is a missing tick.
        line = PAGE[PAGE.index("function roseLine("):]
        line = line[:line.index("\n}\n")]
        assert "(rose.frames || []).map(" in line and 'class="rose-tk' in line

    def test_the_six_hours_are_tapped_dragged_or_stepped(self):
        """A tap goes to a moment, a drag scrubs, as the fill bar's does; the
        arrow keys still step half an hour."""

        wire = PAGE[PAGE.index("function wireRoses("):]
        wire = wire[:wire.index("\n}\n")]
        assert 'strip.addEventListener("pointerdown"' in wire and '"pointermove"' in wire
        assert 'querySelector(".rose-rail").getBoundingClientRect()' in wire
        assert '(x - box.left) / box.width * ROSE_PLAY_MS' in wire
        assert 'e.key === "ArrowRight" ? half : e.key === "ArrowLeft" ? -half : null' in wire

    def test_the_switch_is_one_toggle_at_the_bars_end(self):
        """Owner's requests, 2026-11-11 (one toggle showing what a tap turns
        to, named to a screen reader) and 2026-11-17 (back in the bottom-right
        corner, the bar's right end)."""

        sw = PAGE[PAGE.index("function roseSwitch("):]
        sw = sw[:sw.index("\n}\n")]
        assert "ROSE_MODES.find((m) => m.id !== ROSE_MODE)" in sw
        assert 'aria-label="Show the ${next.label} rose"' in sw and "${roseSymbol(next)}</button>" in sw
        # "m | s" on Metric (owner's call, 2026-10-28).
        assert 'const roseSymbol = (m) => (m.id === "height" && UNITS === "metric" ? "m" : m.symbol);' in PAGE
        assert 'const ROSE_BAND_KEYS = ["<8", "8–11", "11–14", "14–17", "17+ s"];' in PAGE

    def test_the_outer_ring_is_the_drawing_edge(self):
        """Owner's choice, 2026-10-08: N, E, S and W just inside the outer
        ring, no empty band around it, the circle 260 px across."""

        assert "const ROSE = {c: 120, r: 119};" in PAGE
        plot = PAGE[PAGE.index("function rosePlot("):]
        plot = plot[:plot.index("\n}\n")]
        assert "rosePt(R - 9, deg)" in plot and "R + 11" not in plot
        assert 'viewBox="0 0 240 240"' in plot
        assert "max-width:260px" in PAGE[PAGE.index(".rose-svg{"):PAGE.index(".rose-svg .ring")]
        assert "paint-order:stroke" in PAGE[PAGE.index(".rose-svg .pt{"):PAGE.index(".rose-svg .rp{")]

    def test_switching_views_never_moves_the_page(self):
        """Owner's request, 2026-10-08, and since 2026-11-11 Height takes no
        legend room: the tray grows with its words, as the drawing's and the
        map's does."""

        legend = PAGE[PAGE.index("function roseLegend("):]
        legend = legend[:legend.index("\n}\n")]
        assert 'if (mode !== "period") return ""' not in legend
        assert '" off"' in legend and 'aria-hidden="true"' in legend
        assert ".rose .legend.off{display:none}" in PAGE

    def test_one_line_under_the_rose_carries_the_scale_the_reach_and_the_height(self):
        """Owner's requests, 2026-10-08 ("Rings every 1 ft (0.30 m) · ...
        combined", no values line above it, no "to 4 ft" ending) and
        2026-11-17: the seabed's reach said after the rings, so a ring is not
        read as a distance; the frame's time left to the bar; the combined
        height kept, as it changes while the loop plays."""

        block = PAGE[PAGE.index("function roseBlock("):]
        block = block[:block.index("\n}\n")]
        assert 'class="readout"' not in block
        assert '<div class="rose-scale${roseAged(rose, v.state) ? " aged" : ""}" data-rose-live aria-live="off">${roseReadout(v.state, station)}</div>' in block
        read = PAGE[PAGE.index("function roseReadout("):]
        read = read[:read.index("\n}\n")]
        assert "clock(" not in read
        assert "roseScaleLine(ROSE_MODE, station))\n    + (roseOnSea() ? sep + seg(roseReach()) : \"\")" in read
        assert read.index("roseReach()") < read.index("combined")
        assert ("const roseReach = () => `Map ${dualText(`${Math.round(ROSE_SEA_KM * MI_PER_KM)} mi`,"
                " `${ROSE_SEA_KM} km`)} to the edge`;") in PAGE
        # The time is the bar's: the frame's own, or the moment a gap is named by.
        assert ("const roseWhen = (state) => (state.last ? roseLastWhen(state.frame)"
                " : state.at ? clock(state.at) : \"\");") in PAGE
        line = PAGE[PAGE.index("function roseScaleLine("):]
        line = line[:line.index("\n}\n")]
        assert " to " not in line and "of the energy" not in line
        plot = PAGE[PAGE.index("function rosePlot("):]
        assert 'class="rl"' not in plot[:plot.index("\n}\n")]
        assert 'aria-label="${ROSE_PLAYING ? "Pause" : "Play"}"' in PAGE


class TestTheSeabedBehindTheRose:
    """Group 5, item 9 (owner's picks, 2026-11-17, from the mock "Buoy Rose
    Seabed"): the swell map's seabed behind each rose, centred on the buoy
    and north up, the rose's edge 40 km out, filling the plate, no marks, as
    a still image."""

    SEA = PAGE[PAGE.index("// THE SEABED BEHIND EACH BUOY'S ROSE"):PAGE.index("window.roseSea = {")]

    def test_one_scale_for_every_buoy_40_km(self):
        assert "const ROSE_SEA_KM = 40;" in PAGE
        assert ("const seaZoom = (at, g) => Math.log2(MPP0 * Math.cos(rad(at[0])) * g.r"
                " / (ROSE_SEA_KM * 1000));") in self.SEA
        # The outer ring's radius on the plate: the drawing's own geometry.
        assert "r: r.width * ROSE.r / 240" in self.SEA

    def test_the_zoom_puts_the_outer_ring_40_km_out(self):
        """Run in node: at the zoom chosen, MapLibre's metres a pixel at the
        buoy's latitude times the ring's radius in pixels is 40 km."""

        import subprocess

        zoom = re.search(r"const seaZoom = [^\n]+", self.SEA).group(0)
        script = ("const MPP0 = 78271.51696, ROSE_SEA_KM = 40, rad = (d) => d * Math.PI / 180;\n" + zoom + "\n"
                  "const out = [[32.517, 128.9], [32.418, 100], [32.504, 64]].map(([lat, r]) => {\n"
                  "  const z = seaZoom([lat, 0], {r});\n"
                  "  return MPP0 * Math.cos(rad(lat)) / 2 ** z * r; });\n"
                  "console.log(JSON.stringify(out));\n")
        got = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True,
                                        check=True).stdout)
        assert got == pytest.approx([40000.0] * 3)
        assert "const MPP0 = 78271.51696;" in PAGE

    def test_centred_on_the_buoy_north_up_never_a_typed_coordinate(self):
        assert "bearing: 0" in self.SEA
        assert "if (b && b.id === station) return b.position || null;" in self.SEA
        assert "return (MAPDATA.buoys || {})[station] || null;" in self.SEA
        assert not re.search(r"-?1\d\d\.\d{2,}|3[23]\.\d{2,}", self.SEA)

    def test_the_colour_theme_never_the_layer_lists_looks_and_no_marks(self):
        assert "const seaTheme = () => MAP_THEMES[shownTheme()] || MAP_THEMES.light;" in self.SEA
        assert "MAP_LOOKS" not in self.SEA and "layers.look" not in self.SEA
        assert "circle" not in self.SEA and "Marker" not in self.SEA

    def test_a_still_image_from_one_map_let_go(self):
        """Owner's call, 2026-11-17: still images, not three live maps."""

        assert "interactive: false" in self.SEA and "preserveDrawingBuffer: true" in self.SEA
        assert 'map.getCanvas().toBlob(ok, "image/png")' in self.SEA
        assert "if (map) map.remove();                     // lets its WebGL context go" in self.SEA
        assert self.SEA.count("new maplibregl.Map(") == 1
        block = PAGE[PAGE.index("function roseBlock("):]
        block = block[:block.index("\n}\n")]
        assert '<img class="rose-sea" alt="" aria-hidden="true" draggable="false"' in block
        assert "window.roseSea.src(station)" in block

    def test_only_where_the_map_can_be_drawn(self):
        """No WebGL, or the map failing: the rose on the card in the page's
        colours, the line without the reach."""

        assert "const seaOk = () => GL && !SEA.failed;" in self.SEA
        fail = self.SEA[self.SEA.index("function seaFail("):]
        fail = fail[:fail.index("\n  }\n")]
        assert 'el.classList.remove("sea")' in fail and 'el.setAttribute("data-k", "")' in fail
        assert "const roseOnSea = () => !!(window.roseSea && window.roseSea.ok());" in PAGE
        assert '<div class="rose${sea ? " sea" : ""}"' in PAGE

    def test_the_dark_themes_rose_on_both_themes(self):
        """Owner's request, 2026-11-17: over the seabed the petals, rings,
        points and Period bands in the dark theme's colours, light page or
        dark ("white dominant") -- the dark theme's own tokens."""

        rule = re.search(r"\.rose\.sea \.rose-svg,\.rose\.sea \.legend \.sw\{([^}]*)\}", PAGE).group(1)
        dark = PAGE[PAGE.index(':root[data-theme="dark"]{'):]
        dark = dark[:dark.index("}")]
        for name in ("ink", "soft", "faint", "line-strong", "card"):
            want = re.search(rf"--{name}:(#[0-9A-Fa-f]{{6}})", dark).group(1)
            assert f"--{name}:{want}" in rule, name
        assert ".rose.sea .rose-svg .ring{stroke:var(--ink);stroke-opacity:.38}" in PAGE
        assert ".rose.sea .legend .sw{box-shadow:0 0 0 1px var(--sw-hair)}" in PAGE


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
            "let BUOYS; const MODE = 'now'; const clock = (iso) => iso.slice(11, 16);\n"
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


class TestADarkBuoysLastSpectrum:
    """Owner's request, 2026-11-23: a buoy with no spectrum in the six hours
    keeps its plate and seabed, its newest spectrum however old drawn greyed
    as a stale frame is, and the tray saying so -- "No spectrum in the last
    six hours" and the last one's day and time."""

    def test_the_newest_rides_as_last_only_when_the_window_is_empty(self, tmp_path):
        old = MOMENT - timedelta(days=8)
        write_many(tmp_path, "46086", [spectrum(old - timedelta(minutes=30)), spectrum(old)])
        write_spectrum(tmp_path, "46047", spectrum(MOMENT - timedelta(minutes=20)))
        got = buoys.build(data_dir=tmp_path, now=MOMENT)["roses"]
        assert got["46086"]["frames"] == [] and "trains" not in got["46086"]
        assert got["46086"]["last"] == rose.frame(spectrum(old).with_spread("mem"))
        assert "last" not in got["46047"]          # a frame in the window: no last
        assert "last" not in got["46232"]          # nothing archived: nothing drawn

    def test_drawn_greyed_and_named_by_its_day(self):
        """Run in node against the page's own roseAt and roseAged."""

        import subprocess

        def fn(name):
            body = PAGE[PAGE.index(f"function {name}("):]
            return body[:body.index("\n}\n") + 3]

        def const(name):
            body = PAGE[PAGE.index(f"const {name} = "):]
            return body[:body.index(";\n") + 2]

        aged = PAGE[PAGE.index("const roseAged = "):]
        aged = aged[:aged.index("\n};\n") + 4]
        script = (
            "const clock = (iso) => iso.slice(11, 16);\n"
            "const staleLimitH = () => 3;\n"
            "const roseTime = (f) => new Date(f.time_utc).getTime();\n"
            + const("roseFramesOf") + fn("roseAt") + aged +
            "const r = {interval_min: 30, frames: [], last: {time_utc: '2026-11-15T23:50:00Z'}};\n"
            "const s = roseAt(r, Date.parse('2026-11-23T04:00:00Z'));\n"
            "console.log(JSON.stringify({s, aged: roseAged(r, s), scale: roseFramesOf(r).length,"
            " empty: roseFramesOf({frames: []}).length}));\n")
        got = json.loads(subprocess.run(["node", "-e", script], capture_output=True,
                                        text=True, check=True).stdout)
        assert got["s"]["last"] and got["s"]["frame"]["time_utc"] == "2026-11-15T23:50:00Z"
        assert got["s"]["note"] == "No spectrum in the last six hours"
        assert got["aged"] is True
        assert got["scale"] == 1 and got["empty"] == 0

    def test_the_tray_says_it_and_the_plate_stays(self):
        read = _fn("roseReadout")
        assert ("if (state.last) return scale + sep + seg(state.note) + sep"
                " + seg(`last ${roseLastWhen(state.frame)}`);") in read
        assert "const roseLastWhen = (f) => `${dayOfUtc(f.time_utc)}, ${clock(f.time_utc)}`;" in PAGE
        assert "if (!v || (!roseFramesOf(rose).length && !rose.none)) {" in _fn("roseBlock")


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
        reading = by_station(payload, "46047")
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
        reading = by_station(payload, "46047")
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


class TestTheForecastRose:
    """The Forecast tab's Buoys tab, its rose and station block (owner's
    request and calls, 2026-11-23): GFS-Wave's own grid at 46232, on each
    hour the picker offers; it opens on the picked hour and plays forward
    through the next seven, every 3 h, then back. A run built from
    partitions, or an earlier run's hour, keeps the plate and seabed with no
    petals and the tray saying why."""

    @staticmethod
    def grid(spread_deg=20.0, from_deg=250.0, period_s=14.0):
        from datetime import datetime, timezone
        from forecast.transform import GridSpectrum

        freqs = [0.04 + 0.01 * i for i in range(40)]
        dirs = [5.0 + 10.0 * k for k in range(36)]
        fp = 1.0 / period_s

        def e(f, d):
            dd = (d - from_deg + 180.0) % 360.0 - 180.0
            return math.exp(-0.5 * ((f - fp) / 0.01) ** 2) * math.exp(-0.5 * (dd / spread_deg) ** 2)

        energy = [[e(f, d) for f in freqs] for d in dirs]
        return GridSpectrum(datetime(2026, 11, 23, 12, tzinfo=timezone.utc), freqs, dirs, energy)

    def test_the_rose_is_the_hours_own_reading(self):
        """Its height is the hour's `at_buoy` height, from the same grid."""
        g = self.grid()
        view = at_buoy(g)
        got = rose.model_hour(g, view.trains[:3])
        assert got["hs_m"] == pytest.approx(view.hs_m, abs=1e-3)
        assert len(got["sector_hs_m"]) == 16 and len(got["period_share"]) == 16
        assert got["trains"] and len(got["train_share"]) == len(got["trains"])
        # Its energy comes FROM the WSW sector.
        assert max(range(16), key=lambda k: got["sector_hs_m"][k]) == rose.POINTS.index("WSW")

    def test_mean_period_and_spread_off_the_grid(self):
        narrow, wide = rose.model_reading(self.grid(10.0)), rose.model_reading(self.grid(35.0))
        # One narrow-band swell: Tm02 is its period, to the band's width.
        assert narrow["mean_period_s"] == pytest.approx(14.0, abs=0.4)
        # Kuik's spread tracks the grid's own: wider spread, larger figure.
        assert narrow["spread_deg"] == pytest.approx(10, abs=3)
        assert wide["spread_deg"] > narrow["spread_deg"] + 15

    def test_only_on_the_pickers_hours_and_never_in_the_log(self):
        from forecast import forecastlog
        source = (ROOT / "forecast" / "live.py").read_text()
        assert "if row.lead_hours % forecastlog.HOUR_STEP == 0:" in source
        assert 'entry["rose"] = rose.model_hour(grid, view.trains[:3])' in source
        fc = {"generated_utc": "2026-11-23T12:00:00Z", "cycle_utc": "2026-11-23T06:00:00Z",
              "breaks": [{"id": "coronado_center", "hours": [
                  {"valid_utc": "2026-11-23T12:00:00Z", "lead_h": 6}]}],
              "buoy": [{"valid_utc": "2026-11-23T12:00:00Z", "hs_m": 1.0, "rose": {"hs_m": 1.0},
                        "mean_period_s": 9.1}]}
        got = forecastlog.shown_lines(fc)
        assert got and "rose" not in got[0]["buoy"] and got[0]["buoy"]["mean_period_s"] == 9.1

    def _run(self, body):
        import shutil
        import subprocess
        node = shutil.which("node")
        if node is None:
            pytest.skip("node is not available")

        def fn(name):
            text = PAGE[PAGE.index(f"function {name}("):]
            return text[:text.index("\n}\n") + 3]

        consts = PAGE[PAGE.index("const FC_ROSE_HOURS = "):PAGE.index("function fcRose(")]
        script = ("let MODE = 'forecast', DATA, STEPS = [], CURSOR = 0, ROSE_PHASE = 9000;\n"
                  "const ROSE_PLAY_MS = 9000; const clock = (iso) => iso.slice(11, 16);\n"
                  "const roseTime = (f) => new Date(f.time_utc).getTime();\n"
                  "const roseOf = (station) => fcRose(station);\n"
                  + consts + fn("fcRose") + fn("roseSpan") + fn("roseMoment") + fn("roseAt") + body)
        out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
        return json.loads(out.stdout)

    DATA = ("const hr = (h) => new Date(Date.UTC(2026, 10, 23, h)).toISOString().replace('.000', '');\n"
            "const row = (h) => ({valid_utc: hr(h), rose: {time_utc: hr(h), hs_m: 1,"
            " train_share: [[1]], trains: [{period_lo_s: 12, period_hi_s: 16}]}});\n"
            "DATA = {station: '46232', generated_utc: hr(5), wave_source: 'spectrum',\n"
            "  buoy: [6, 9, 12, 15, 18, 21, 24, 27, 30, 33].map(row)"
            ".concat([{valid_utc: hr(7)}])};\n"
            "STEPS = [{valid_utc: hr(3), from: 'past'}, {valid_utc: hr(9), from: 'cycle'}];\n")

    def test_eight_frames_from_the_picked_hour(self):
        got = self._run(self.DATA + (
            "CURSOR = 1; const r = fcRose('46232'); const s = roseSpan();\n"
            "const rest = roseAt(r, roseMoment(s));\n"
            "ROSE_PHASE = 9000 * 7.5 / 8; const late = roseAt(r, roseMoment(s));\n"
            "console.log(JSON.stringify({n: r.frames.length, t0: r.frames[0].time_utc,"
            " last: r.frames[7].time_utc, lit: r.frames.map((f) => !!f.train_share),"
            " from: r.trains_from_utc, span: (s.t1 - s.t0) / 3600000, rest: rest.at, late: late.at}));\n"))
        assert got["n"] == 8 and got["t0"] == "2026-11-23T09:00:00Z" and got["last"] == "2026-11-24T06:00:00Z"
        # A tapped row lights the picked hour's frame alone.
        assert got["lit"] == [True] + [False] * 7 and got["from"] == "2026-11-23T09:00:00Z"
        # Paused, and after a play's hold, on the picked hour; 24 h of line.
        assert got["span"] == 24 and got["rest"] == "2026-11-23T09:00:00Z"
        assert got["late"] == "2026-11-24T06:00:00Z"

    def test_no_petals_without_the_runs_grid(self):
        got = self._run(self.DATA + (
            "CURSOR = 0; const past = roseAt(fcRose('46232'), 0).note;\n"
            "CURSOR = 1; DATA = {...DATA, wave_source: 'partitions', generated_utc: 'x'};\n"
            "const parts = roseAt(fcRose('46232'), 0);\n"
            "console.log(JSON.stringify({past, parts: parts.note, frame: !!parts.frame}));\n"))
        assert got["past"] == "An earlier run's hour keeps no spectrum"
        assert got["parts"] == "No GFS-Wave spectrum this cycle · forecast from its partitions"
        assert got["frame"] is False
