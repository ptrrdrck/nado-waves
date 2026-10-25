"""The context buoys on the LIVE tab's Buoys tab (`forecast.buoys`).

Two things can go wrong here and both are BRIEFING §3a's: 46047 leaking into
the chain that makes a break's number, and 46047's reading being dressed in
46232's clock. The first is guarded by name in test_spectra_collector and by
what this module calls, here; the second by its own measured countdown.
"""

from __future__ import annotations

import ast
import csv
import json
import math
import re
import shutil
import subprocess
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from forecast import buoys
from forecast.transform import Spectrum, at_buoy, load_spectra

from test_now import spectrum

ROOT = Path(__file__).resolve().parent.parent
MOMENT = datetime(2026, 10, 6, 0, 30, tzinfo=timezone.utc)
PAGE = (ROOT / "app" / "forecast.html").read_text(encoding="utf-8")


def write_spectrum(data_dir: Path, station: str, sp: Spectrum) -> None:
    folder = data_dir / "spectra" / station
    folder.mkdir(parents=True, exist_ok=True)
    stamp = sp.time.strftime("%Y-%m-%dT%H:%M:%SZ")
    for kind in ("c11", "a1", "a2", "r1", "r2"):
        with (folder / f"{kind}.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["time_utc", *[f"{f:.4f}" for f in sp.frequencies]])
            w.writerow([stamp, *getattr(sp, kind)])


def block(payload: dict, station: str) -> dict:
    """One buoy's block, by station rather than by its place on the tab."""

    return next(b for b in payload["buoys"] if b["station"] == station)


class TestTheReading:
    def test_it_is_the_buoy_with_nothing_in_the_way(self, tmp_path):
        sp = spectrum(MOMENT - timedelta(minutes=40), peak_dir=300.0)
        write_spectrum(tmp_path, "46047", sp)
        got = block(buoys.build(data_dir=tmp_path, now=MOMENT), "46047")
        want = at_buoy(load_spectra(tmp_path / "spectra" / "46047")[0].with_spread("mem"))
        assert got["station"] == "46047"
        assert got["hs_m"] == pytest.approx(want.hs_m, abs=1e-3)
        assert got["trains"] and got["trains"][0]["from_deg"] == pytest.approx(300, abs=3)

    def test_the_trains_sum_to_the_headline(self, tmp_path):
        write_spectrum(tmp_path, "46047", spectrum(MOMENT - timedelta(minutes=40)))
        got = block(buoys.build(data_dir=tmp_path, now=MOMENT), "46047")
        from_trains = math.sqrt(sum((t["hs_m"] / 4.0) ** 2 for t in got["trains"]))
        assert 4.0 * from_trains == pytest.approx(got["hs_m"], rel=0.08)

    def test_it_is_built_as_46232s_own_block_is(self, tmp_path):
        """The same construction `forecast.now` gives 46232 at the buoy:
        maximum entropy, `at_buoy`, the same train payload."""

        from forecast import now as now_mod

        sp = spectrum(MOMENT - timedelta(minutes=30), peak_dir=250.0)
        write_spectrum(tmp_path, "46232", sp)
        mine = buoys.reading("46232", tmp_path, MOMENT)
        theirs = now_mod.build(data_dir=tmp_path, now=MOMENT).buoy
        for key in ("hs_m", "peak_period_s", "peak_direction_deg", "trains"):
            assert mine[key] == theirs[key], key

    def test_no_spectrum_is_said_not_borrowed(self, tmp_path):
        """A missing 46047 is a gap. Nothing falls back to 46232's reading."""

        write_spectrum(tmp_path, "46232", spectrum(MOMENT))
        got = block(buoys.build(data_dir=tmp_path, now=MOMENT), "46047")
        assert got["observed_utc"] is None and "hs_m" not in got
        assert got["stale"] and got["warnings"]

    def test_an_old_spectrum_is_marked_stale(self, tmp_path):
        write_spectrum(tmp_path, "46047", spectrum(MOMENT - timedelta(hours=5)))
        got = block(buoys.build(data_dir=tmp_path, now=MOMENT), "46047")
        assert got["stale"] and got["hs_m"] > 0
        write_spectrum(tmp_path, "46047", spectrum(MOMENT - timedelta(hours=1)))
        assert not block(buoys.build(data_dir=tmp_path, now=MOMENT), "46047")["stale"]

    def test_it_says_what_it_is_standing_on(self, tmp_path):
        write_spectrum(tmp_path, "46047", spectrum(MOMENT - timedelta(minutes=40)))
        standing = buoys.build(data_dir=tmp_path, now=MOMENT)["standing_on"]
        assert list(standing) == ["context buoys"]
        line = standing["context buoys"]
        assert line.startswith("OBSERVED — NDBC directional spectrum at 46086")
        assert "not carried to any break" in line
        # Each buoy with its own window claim: 46086 is not outside them all.
        assert "at 46047 (outside every break's windows)" in line
        assert "at 46086 (inside South's window alone)" in line

    def test_each_buoy_carries_its_own_words(self, tmp_path):
        for station in buoys.STATIONS:
            write_spectrum(tmp_path, station, spectrum(MOMENT - timedelta(minutes=40)))
        shown = buoys.build(data_dir=tmp_path, now=MOMENT)["buoys"]
        # Owner's call, 2026-10-12: 46086 first, then 46047.
        assert [b["station"] for b in shown] == ["46086", "46047"]
        # Each buoy's own sentence, 46232's included (owner's wording,
        # 2026-10-12), and still there when its spectrum is missing.
        (tmp_path / "spectra" / "46086" / "c11.csv").unlink()
        payload = buoys.build(data_dir=tmp_path, now=MOMENT)
        assert "hs_m" not in block(payload, "46086")
        assert list(payload["about"]) == ["46232", "46086", "46047"]
        assert {s: a["says"] for s, a in payload["about"].items()} == buoys.ABOUT
        # No metadata in this archive: no place, so no distance -- never a guess.
        assert payload["about"]["46086"]["range_km"] is None
        assert payload["about"]["46086"]["place"] == "46086"

    def test_json_round_trips(self, tmp_path):
        write_spectrum(tmp_path, "46047", spectrum(MOMENT - timedelta(minutes=40)))
        assert buoys.main(["--data-dir", str(tmp_path)]) == 0
        got = json.loads((tmp_path / "live" / "buoys.json").read_text())
        assert got["spread"] == "mem" and block(got, "46047")


class TestItFeedsNoBreak:
    """BRIEFING §3a: 46047 is outside every break's windows and no stand-in
    for 46232. Shown at the buoy; never carried."""

    def test_it_calls_nothing_that_carries_a_spectrum_to_a_break(self):
        tree = ast.parse((ROOT / "forecast" / "buoys.py").read_text())
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        names |= {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
                  for a in n.names}
        modules = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        for carrier in ("through", "carry", "summarise", "local_sea", "density_grids",
                        "through_partitions", "load_tables", "load_profiles"):
            assert carrier not in names, carrier
        assert not modules & {"nearshore", "surfzone", "raytrace"}

    def test_what_each_says_about_the_windows_is_sitings(self):
        """BRIEFING §3a: which windows a buoy sits in is DERIVED, never
        stored. The words are typed, so they are held to the derivation: a
        buoy said to be outside every window is in none, and one said to be
        inside South's alone is in exactly that one."""

        from forecast import siting
        from collector.stations import load_stations

        by_id = {s.station.id: s for s in siting.survey(load_stations())}
        words = {(): "outside every break's windows",
                 ("coronado_south",): "inside South's window alone"}
        for station in buoys.STATIONS:
            got = by_id[station].in_window_of
            assert got in words, (station, got)
            assert buoys.WITNESS[station]["windows"] == words[got], station
            says = buoys.ABOUT[station]
            assert says.endswith("not carried to any break.")
            assert ("window" in says) == bool(got), station
        # The anchor's sentence claims all three windows: siting must agree.
        assert len(by_id[buoys.ANCHOR].in_window_of) == 3
        assert "all three breaks' windows" in buoys.ABOUT[buoys.ANCHOR]

    def test_the_only_buoy_shown_is_a_context_buoy(self):
        from collector.spectra import CONTEXT_STATIONS, DEFAULT_STATION

        assert set(buoys.STATIONS) <= set(CONTEXT_STATIONS)
        assert DEFAULT_STATION not in buoys.STATIONS

    def test_every_buoy_shown_is_collected_hourly(self):
        """A countdown that promises a reading every half hour needs a
        collection that fetches it every ten minutes."""

        from collector.spectra import HOURLY_STATIONS

        assert set(buoys.STATIONS) <= set(HOURLY_STATIONS)

    def test_its_own_file_not_a_key_in_now_json(self):
        now_source = (ROOT / "forecast" / "now.py").read_text()
        assert "buoys.json" not in now_source and "forecast.buoys" not in now_source


class TestItsOwnCountdown:
    """46047 and 46086 stamp at :20 and :50 and land on their own lags,
    bracketed 2026-10-06 and 2026-10-12 against the collection log (module
    docstring)."""

    def test_every_buoy_shown_has_measured_lags(self):
        for station in buoys.STATIONS:
            assert buoys.PUBLISH_MINUTES[station]
            assert buoys.PUBLISH_LAG_LATE_MIN[station] >= buoys.PUBLISH_LAG_MIN[station] > 0

    @pytest.mark.parametrize("station", buoys.STATIONS)
    def test_the_archive_stamps_where_it_is_modelled_to(self, station):
        """At least 98% of archived stamps on the modelled minutes: 46047's
        newest 200 had 3 on :40, 46086's 4 on :40 and 2 on :10, and a
        countdown on the wrong minutes would run to a stamp that never
        comes."""

        stamps = [s.time.minute for s in load_spectra(ROOT / "data" / "spectra" / station)]
        on = sum(Counter(stamps)[m] for m in buoys.PUBLISH_MINUTES[station])
        assert on / len(stamps) >= 0.98

    @pytest.mark.parametrize("observed, expected, late", [
        # :50 -> next stamp :20, +25 = :45, the :45 collection; +85 = 01:45.
        ("2026-10-05T23:50:00Z", "2026-10-06T00:45:00Z", "2026-10-06T01:45:00Z"),
        # :20 -> next stamp :50, +25 = 01:15, the :15 collection; +85 = 02:15.
        ("2026-10-06T00:20:00Z", "2026-10-06T01:15:00Z", "2026-10-06T02:15:00Z"),
    ])
    def test_it_lands_on_the_collection_that_typically_has_it(self, tmp_path, observed,
                                                               expected, late):
        at = datetime.strptime(observed, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        write_spectrum(tmp_path, "46047", spectrum(at))
        got = block(buoys.build(data_dir=tmp_path, now=at + timedelta(minutes=30)), "46047")
        assert (got["next_expected"], got["overdue_after"]) == (expected, late)

    def test_46086_lands_on_its_own_worst(self, tmp_path):
        """Bracketed on its own 188 stamps: 25 typical, as 46047's, but 115
        worst, not 46047's 85 -- measured, not borrowed."""

        assert (buoys.PUBLISH_LAG_MIN["46086"], buoys.PUBLISH_LAG_LATE_MIN["46086"]) == (25, 115)
        at = datetime(2026, 10, 6, 0, 20, tzinfo=timezone.utc)
        write_spectrum(tmp_path, "46086", spectrum(at))
        got = block(buoys.build(data_dir=tmp_path, now=at + timedelta(minutes=30)), "46086")
        # :20 -> next stamp :50, +25 = 01:15; +115 = 02:45, the :45 collection.
        assert got["station"] == "46086"
        assert (got["next_expected"], got["overdue_after"]) == (
            "2026-10-06T01:15:00Z", "2026-10-06T02:45:00Z")

    def test_it_is_not_46232s_countdown(self):
        from forecast import now as now_mod

        for station in buoys.STATIONS:
            assert buoys.PUBLISH_MINUTES[station] != now_mod.PUBLISH_MINUTES["swell"]

    def test_the_arithmetic_is_shared_not_copied(self):
        source = (ROOT / "forecast" / "buoys.py").read_text()
        assert "from .now import" in source and "deadline(" in source
        assert "_mark_at_or_after" not in source and "_next_mark" not in source


class TestOnThePage:
    def test_the_tab_is_buoys_on_both_chains(self):
        assert 'title: "Buoys"' in PAGE
        assert "`Buoy ${station}`" not in PAGE.split("function swellCard")[1][:2000]
        assert 'const BUOY_TAB = "buoy";' in PAGE

    def test_the_page_fetches_its_own_file(self):
        assert 'const BUOYS_SOURCE = PARAM.get("buoys") || "../data/live/buoys.json";' in PAGE
        assert "fetch(fresh(BUOYS_SOURCE), {cache: \"no-store\"})" in PAGE
        assert "setInterval(refreshBuoys, NOW_REFRESH_MS)" in PAGE

    def test_only_the_live_chain_carries_it(self):
        """GFS-Wave's run is at 46232 alone: the Forecast tab's Buoys pane
        has no second block."""

        calls = PAGE.split("rows.push(swellCard(")
        assert len(calls) == 3
        live, forecast = calls[1], calls[2]
        assert "others: (BUOYS && BUOYS.buoys) || []" in live.split("}));")[0]
        assert "others" not in forecast.split("}));")[0]

    def test_its_block_says_it_feeds_no_break_and_has_its_own_clock(self):
        block = PAGE[PAGE.index("function contextBuoy("):]
        block = block[:block.index("\n}\n")]
        # Each buoy's own sentence, from buoys.json: never one typed for all.
        assert "const note = buoyAbout(b.station);" in block
        assert "Open ocean witness" not in block
        assert "placeWhen(buoyPlace(b.station_name, b.station), b.observed_utc)" in block
        assert "feedPills(`NDBC ${b.station}`, b.observed_utc, b.observed_utc ? b.next_expected : null," in block
        assert "NOW." not in block

    def test_each_buoys_provenance_follows_its_own_measurements(self):
        """46232's reading, then the card's provenance (46232's), then each
        context buoy with its own provenance under it (owner's call,
        2026-10-06) -- shown and hidden with the Buoys tab."""

        card = PAGE[PAGE.index("function swellCard("):]
        card = card[:card.index("\n}\n")]
        assert (card.index("${tab.body}</div>") < card.index("${srcLines(source, due)}")
                < card.index('data-after-tab="${tab.id}"'))
        assert "contextBuoy" not in PAGE[PAGE.index("function buoyPanel("):
                                         PAGE.index("function buoyReading(")]
        select = PAGE[PAGE.index("function selectSwellTab("):]
        assert '"[data-after-tab]"' in select[:select.index("\n}\n")]


def _fn(name: str) -> str:
    body = PAGE[PAGE.index(f"function {name}("):]
    return body[:body.index("\n}\n")]


class TestTheSentenceUnderEachRose:
    """Owner's wording, 2026-10-12: one sentence under each buoy's rose --
    the station linked to its public page, its distance offshore and bearing
    from Center break, what is read from it and its role here."""

    def _render(self, about):
        node = shutil.which("node")
        if node is None:
            pytest.skip("node is not available")
        script = (
            "const MI_PER_KM = 0.621371;\n"
            + _fn("point") + "\n}\n" + _fn("buoyAbout") + "\n}\n"
            + f"const BUOYS = {{about: {json.dumps(about)}}};\n"
            + "for (const s of ['46232', '46086', '46047']) console.log(buoyAbout(s));\n"
        )
        out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
        return out.stdout.strip().split("\n")

    def test_the_approved_sentences(self):
        got = self._render(buoys.about(ROOT / "data"))
        plain = [re.sub(r"<[^>]+>", "", line).replace("&deg;", "°") for line in got]
        assert plain == [
            "Point Loma South (CDIP 191), 18 mi (29 km) offshore at 231° SW from Center "
            "break: its hourly directional spectrum is what every break's numbers are "
            "carried from, as the only buoy inside all three breaks' windows.",
            "San Clemente Basin (NDBC 46086), 51 mi (81 km) offshore at 256° WSW from "
            "Center break: its half-hourly directional spectrum is shown here and checked "
            "against hurricane tracks, and though it sits inside South's window it is not "
            "carried to any break.",
            "Tanner Banks (NDBC 46047), 138 mi (222 km) offshore at 263° W from Center "
            "break: its half-hourly directional spectrum reads the open ocean before the "
            "Channel Islands, gives Origin its storm bearings and is checked against "
            "hurricane tracks, but is not carried to any break.",
        ]
        assert '<a href="https://cdip.ucsd.edu/m/products/?stn=191p1" rel="noopener">' in got[0]
        assert '<a href="https://www.ndbc.noaa.gov/station_page.php?station=46086"' in got[1]
        assert '<a href="https://www.ndbc.noaa.gov/station_page.php?station=46047"' in got[2]

    def test_measured_from_center_and_never_typed(self):
        from forecast import siting

        assert siting.REFERENCE_BREAK == "coronado_center"
        source = (ROOT / "forecast" / "buoys.py").read_text()
        for figure in ("29.0", "81.5", "222.2", "230.8", "256.2", "263.0"):
            assert figure not in source, figure

    def test_live_only_as_the_rose_is(self):
        assert 'const note = rose ? buoyAbout(id) : "";' in _fn("buoyPanel")


class TestThePills:
    """Owner's requests, 2026-10-09 and -11: each buoy's feed is a pill at
    the start of its countdown line -- "CDIP 191 via NDBC •" and "NDBC
    46047 •" -- the dot green, green fading while an update is due, and red
    once overdue, on that buoy's own countdown; the headline is the height
    alone."""

    def test_the_number_is_the_registrys_not_the_pages(self):
        from collector.stations import load_stations
        from forecast.live import cdip_id
        from forecast.now import Now

        by_id = {s.id: s for s in load_stations()}
        assert by_id["46232"].cdip == "191"
        assert cdip_id("46232") == "191" and cdip_id("46047") == ""
        assert "station_cdip" in Now.__dataclass_fields__
        assert "CDIP 191" not in PAGE and "CDIP ${now.station_cdip}" in PAGE

    def test_the_dot_runs_on_the_swell_countdowns_instants(self):
        assert "due: anchorFeed(NOW, due.swell, late.swell)," in PAGE
        # The dot and the countdown pill read the same instants and force.
        feed = _fn("feedPills")
        assert "statusDot(iso, lateIso, {forceOver})" in feed
        assert "dueSpan(iso, lateIso, {forceOver, bare: true})" in feed
        assert "{forceOver: nowIsStale()}" in PAGE[PAGE.index("const anchorFeed"):][:300]
        # The swell card's countdown is the feed's second pill, forced as its dot is.
        assert "dueSpan(due.swell" not in PAGE
        # One computation of the two instants for the countdown and the dot.
        assert "dueInstants(iso, lateIso)" in _fn("dueSpan")
        assert "dueInstants(iso, lateIso)" in _fn("statusDot")
        tick = _fn("tickDue")
        assert "[data-status-due]" in tick
        assert '"Receiving normally"' in tick and '"Update due"' in tick and '"Overdue"' in tick
        for rule in (".status{", "background:var(--dot-ok)",
                     ".status.due{animation:status-due 2s ease-in-out infinite}",
                     ".status.over{background:var(--dot-over)}",
                     "@keyframes status-due{0%,100%{opacity:1}50%{opacity:.2}}",
                     "@media (prefers-reduced-motion: reduce){ .status.due{animation:none;opacity:.45} }"):
            assert rule in PAGE, rule

    def test_the_dot_is_dark_modes_green_and_red_on_both_themes(self):
        root = PAGE[PAGE.index(":root{"):PAGE.index("}", PAGE.index(":root{"))]
        assert "--dot-ok:#5FBF86; --dot-over:#FF6B6B;" in root
        assert PAGE.count("--dot-ok:") == 1 and PAGE.count("--dot-over:") == 1
        assert "--due:" not in PAGE

    def test_46047_wears_one_on_its_own_countdown(self):
        block = _fn("contextBuoy")
        assert 'feedPills(`NDBC ${b.station}`' in block
        assert "b.next_expected" in block and "b.overdue_after" in block
        assert "sublbl" not in block

    def test_the_pill_starts_the_countdown_line_and_the_headline_is_bare(self):
        assert "sublbl" not in _fn("buoyPanel") and "pill" not in _fn("buoyReading")
        assert "buoyLabel" not in PAGE
        # It replaces the "(NDBC <id>)" the name line carried, on both buoys.
        assert "placeWhen(buoyPlace(NOW.station_name, NOW.station), NOW.observed_utc)" in PAGE
        block = _fn("contextBuoy")
        assert "(NDBC ${b.station})" not in block
        assert "srcLines([placeWhen(buoyPlace(b.station_name, b.station), b.observed_utc)], feed);" in block
        # "CDIP <n>" alone since 2026-10-12, never "via NDBC".
        assert "`CDIP ${now.station_cdip}` : `NDBC ${now.station}`" in PAGE
        assert "via NDBC`" not in PAGE

    def test_the_combined_height_sits_in_a_break_headlines_row(self):
        """Owner's request, 2026-10-09: the buoys' combined height sat about
        1 px above a break's breaking height. Both now sit in one row rule,
        centred in at least the caret's 24 px footprint, so they land alike
        in any engine -- and the buoys' row is never `.val-row`, whose tap
        folds a break's calculation."""

        css = PAGE[:PAGE.index("</style>")]
        rule = css[css.index(".val-row,.val-line{"):]
        rule = rule[:rule.index("}")]
        assert "display:flex;align-items:center" in rule and "min-height:24px" in rule
        assert "width:32px;height:32px;margin:-4px -6px -4px 0;" in css   # 32 - 4 - 4 = 24
        assert 'const valLine = (val) => `<div class="val-line">${val}</div>`;' in PAGE
        for name in ("buoyReading", "buoyPanel", "contextBuoy"):
            assert 'class="val-row"' not in _fn(name)
        # The Forecast chain's buoy is a model at 46232: no feed, no dot.
        assert PAGE.count("anchorFeed(NOW") == 1

    def test_the_pill_is_ink_at_the_provenances_size_on_the_picked_rows_background(self):
        css = PAGE[PAGE.index(".pill,.pill-tail{"):PAGE.index(".status{")]
        assert "background:var(--paper)" in css and "color:var(--ink)" in css
        assert "font-size:12px" in css and ".cond .src{font-size:12px" in PAGE
        assert "height:18px" in css

    def test_the_second_pill_grows_out_of_the_first(self):
        """Owner's design, 2026-10-11: the second pill's left edge is cut
        around the first pill's right end, grown by a 2 px seam, and its
        right end is the first pill's. Since the same day the corners are
        4 px (owner's call), so the 18 px pill keeps 10 px of straight edge:
        the cut is the whole pill less a 6 x 10 px block and two circles of
        6 px, 5 px either side of the middle, centred where the second pill
        starts, 4 px under the first."""

        css = PAGE[PAGE.index(".pill,.pill-tail{"):PAGE.index(".status{")]
        assert ".pill{gap:5px;padding:0 7px;border-radius:4px}" in css
        assert "margin-left:-4px" in css and "border-radius:0 4px 4px 0" in css
        for cut in ("radial-gradient(circle at 0 calc(50% - 5px),#000 6px,transparent 6.5px)",
                    "radial-gradient(circle at 0 calc(50% + 5px),#000 6px,transparent 6.5px)",
                    "linear-gradient(#000 0 0) 0 50%/6px 10px no-repeat"):
            assert css.count(cut) == 2, cut       # -webkit- and standard
        assert "-webkit-mask-composite:source-out,source-over,source-over" in css
        assert "mask-composite:subtract,add,add" in css
        # An empty part is left out: never an empty pill.
        fn = _fn("pills")
        assert "parts.filter(Boolean)" in fn
        assert 'tails.map((tail) => `<span class="pill-tail">${tail}</span>`)' in fn

    def test_a_line_that_does_not_fit_wraps_rather_than_overflows(self):
        """At 320 px a line's pills do not all fit: a pill that wraps to start
        a row stands on its own, in the joined pill's footprint (-4 + 13 + 7
        = 8 + 8), so marking it never moves the next and nothing oscillates."""

        css = PAGE[PAGE.index(".pill,.pill-tail{"):PAGE.index(".status{")]
        assert "flex-wrap:wrap" in css[css.index(".pills{"):]
        assert "margin-left:-4px;padding:0 7px 0 13px" in css
        assert ".pill-tail.wrapped{margin-left:0;padding:0 8px;border-radius:4px;-webkit-mask:none;mask:none}" in css
        fit = _fn("fitPill")
        assert fit.index('classList.remove("wrapped")') < fit.index("offsetTop") < fit.index('classList.toggle("wrapped"')
        assert "fitPills($(\"conditions\"))" in PAGE


class TestTheProvenancePills:
    """Owner's requests, 2026-10-11 and -12: each LIVE card's provenance is
    "CDIP 191 • | <age> | <countdown>", with "Point Loma South, CA | <when>"
    above it built but switched off (`SHOW_PLACE_WHEN`)."""

    def test_46232s_lines_in_order(self):
        live = PAGE.split("rows.push(swellCard(")[1].split("}));")[0]
        assert (live.index("placeWhen(buoyPlace(NOW.station_name, NOW.station), NOW.observed_utc)")
                < live.index("due: anchorFeed(NOW, due.swell, late.swell),"))

    def test_the_second_line_is_station_age_countdown(self):
        feed = _fn("feedPills")
        assert ("pills(label + statusDot(iso, lateIso, {forceOver}), ageSpan(observedIso),\n"
                "               dueSpan(iso, lateIso, {forceOver, bare: true}))") in feed
        assert "now.observed_utc,\n             due, late, {forceOver: nowIsStale()}" in PAGE

    def test_the_first_line_is_place_and_time_with_no_verb(self):
        """Owner's call, 2026-10-12: the time alone, no "Observed" or
        "Measured"."""
        assert 'pillLine(place || "", iso ? when(iso) : "")' in PAGE
        assert "`Observed ${when(" not in PAGE and "`Measured ${when(" not in PAGE

    def test_the_first_line_is_kept_but_not_shown(self):
        """Owner's call, later on 2026-10-12: one line, the station's; the
        place-and-time line stays in the code behind one switch, so it can
        come back on every LIVE card at once."""
        assert "const SHOW_PLACE_WHEN = false;" in PAGE
        assert ('const placeWhen = (place, iso) => (SHOW_PLACE_WHEN ? pillLine(place || "", '
                'iso ? when(iso) : "") : "");') in PAGE
        assert PAGE.count("SHOW_PLACE_WHEN") == 3      # its note, the switch, its one reader

    def test_46047s_lines_in_the_same_order_its_words_above_them(self):
        """Owner's call, 2026-10-11: the buoy's words are a description under
        the rose, above the provenance with space between, and no longer one
        of its lines."""

        block = _fn("contextBuoy")
        assert (block.index("const note = buoyAbout(b.station);")
                < block.index("srcLines(")
                < block.index("placeWhen(buoyPlace(b.station_name, b.station), b.observed_utc)"))
        assert ".buoy-fold .rose + .buoy-note{margin-top:3px}" in PAGE

    def test_the_sentence_reads_at_the_size_of_combined(self):
        """Owner's request, 2026-10-14: each buoy's sentence at the size of
        "combined" beside its height, and a buoy with no rose saying so in
        the same size and colour, evenly spaced between the trains above and
        the sentence below (measured in Chromium at 390 px: 22 and 21.5 px)."""

        assert ".cond .val .unit{font-size:15px}" in PAGE
        assert ".cond .buoy-note{font-size:15px}" in PAGE
        assert ".buoy-note .unit{white-space:nowrap}" in PAGE
        assert ".buoy-fold .rose-none{margin:8px 0 4px}" in PAGE
        assert ('return `<p class="quiet buoy-note rose-none">No spectrum from ${buoyFeed(station)}'
                ' in the last six hours.</p>`;') in _fn("roseBlock")


class TestTheBuoyHeadlineFolds:
    """Owner's request, 2026-10-11: a buoy's headline folds out like a
    break's, but what it folds is everything between it and the
    provenance -- trains, rose and words."""

    def test_the_fold_holds_trains_rose_and_words(self):
        read = _fn("buoyReading")
        assert "const body = trains + rose + note;" in read
        assert 'data-buoy-head="${id}">${value}${buoyToggle(id, open)}</div>' in read
        assert '<div class="buoy-fold" id="buoy-fold-${id}"${open ? "" : " hidden"}>${body}</div>' in read
        # Nothing to fold, no caret.
        assert "if (!id || !body) return valLine(value) + body;" in read
        # The rose is in the fold on both buoys, and the provenance is not.
        assert "buoyReading(buoy, id, {roseFor: rose ? id : null, rose, note, aged}) + line" in _fn("buoyPanel")
        block = _fn("contextBuoy")
        assert "buoyReading(b, b.station, {roseFor: b.station, rose: roseBlock(b.station), note," in block

    def test_each_buoy_its_own_state_kept_across_a_refresh(self):
        assert 'buoyOpen: "nado-waves.buoy-open"' in PAGE
        assert "BUOY_OPEN = Object.fromEntries((recall(KEEP.buoyOpen)" in PAGE
        setter = _fn("setBuoyOpen")
        assert "BUOY_OPEN[id] = open;" in setter and "remember(KEEP.buoyOpen" in setter
        assert "setBuoyOpen(id, !BUOY_OPEN[id]);" in PAGE

    def test_selecting_the_buoys_tab_opens_46232(self):
        """Owner's request, 2026-10-13: the anchor buoy's headline opens when
        the Buoys tab is selected, on either chain; the others are left as
        the reader left them."""

        select = _fn("selectSwellTab")
        assert 'const anchor = CHAIN === "fc" ? DATA && DATA.station : NOW && NOW.station;' in select
        assert "if (anchor && !BUOY_OPEN[anchor]) setBuoyOpen(anchor, true);" in select
        assert select.count("setBuoyOpen(") == 1

    def test_the_caret_is_a_breaks(self):
        toggle = _fn("buoyToggle")
        assert 'class="calc-toggle" data-buoy-toggle="${id}"' in toggle
        assert 'aria-controls="buoy-fold-${id}" aria-expanded="${open}"' in toggle
        assert '<path d="M3.5 10 8 5.5 12.5 10"/>' in toggle
        # Its row never folds a break's calculation.
        assert 'class="val-row"' not in _fn("buoyReading")

    def test_the_place_alone(self):
        """Owner's call, 2026-10-11: "Spectral wave data" came off the first
        line; the place alone, never the id the station pill carries."""
        assert 'const buoyPlace = (name, station) => (name && name !== station ? name : "");' in PAGE
        assert "Spectral wave data" not in PAGE[PAGE.index("const buoyPlace"):][:300]

    def test_the_age_stays_volatile(self):
        """The age is the reader's clock, so `cardText` must still strip it."""
        assert "ageSpan(observedIso)" in _fn("feedPills")
        assert '<span class="age">${age}</span>' in _fn("ageSpan")

    def test_a_pill_line_takes_no_full_stop(self):
        assert '${line.html || period(line)}' in _fn("srcLines")


class TestTheSpacing:
    def test_the_rose_is_spaced_as_a_break_tabs_drawing(self):
        """Owner's request, 2026-10-09: 31 px of card above the first ink and
        28 px under the timeline to the provenance on Height, a break tab's
        drawing's own, in painted pixels at 360 px (within 3 px at 320 and
        390, where the drawing scales and the rose does not); the Period
        legend inside the lower space, so the switch never moves the page."""

        assert (".rose{display:flex;flex-direction:column;gap:6px;margin-top:20px;margin-bottom:-11px}"
                in PAGE)
        assert ".pane .rose + .srcs{margin-top:3px}" in PAGE
        # The legend's row is still laid out on Height.
        assert ".rose .legend.off{visibility:hidden}" in PAGE


class TestBreakRowsLightToo:
    def test_a_picked_break_train_reads_as_pressed(self):
        """Owner's request, 2026-10-09: a break tab's train row lights like a
        Buoys tab row, picked from the list or by its arrow."""

        assert 'data-train="${i}" tabindex="0" role="button" aria-pressed="false"' in PAGE
        show = _fn("showPick")
        assert '.train[data-train]' in show and 'setAttribute("aria-pressed"' in show
        assert "key === `T${n}` || key === `t${n}` || key.startsWith(`t${n}-`)" in show
        assert ('.train[data-rose-train][aria-pressed="true"],.train[data-train][aria-pressed="true"]'
                '{background:var(--paper);opacity:1}') in PAGE


class TestTheHeightChart:
    """Owner's request, 2026-10-09: 46047 on the LIVE Buoys tab's Height
    chart, beside 46232, at its own stamps."""

    def test_the_fast_height_is_at_buoys_to_rounding(self):
        """`combined_hs` skips the train split and MEM's per-bin solve; it must
        still be the reading's own number, maximum entropy and Fourier alike,
        over real spectra (fallback bins included)."""

        from forecast.transform import combined_hs

        spectra = load_spectra(ROOT / "data" / "spectra" / "46047")[::97]
        assert len(spectra) > 20
        for sp in spectra:
            mem = sp.with_spread("mem")
            assert abs(combined_hs(mem) - at_buoy(mem).hs_m) < 1e-9
            assert abs(combined_hs(sp) - at_buoy(sp).hs_m) < 1e-9

    def test_realisable_is_whether_mem_succeeds(self):
        from forecast.spreadmethod import Unrealisable, mem, realisable

        for moments in [(0.6, 0.3, 270.0, 268.0), (0.2, 0.9, 10.0, 200.0),
                        (0.95, 0.1, 90.0, 0.0), (0.5, 0.5, 180.0, 180.0)]:
            try:
                mem(*moments)
                ok = True
            except (Unrealisable, ZeroDivisionError, ValueError):
                ok = False
            assert realisable(*moments) == ok

    def test_heights_keep_each_stamp_where_it_was_measured(self):
        t0 = datetime(2026, 10, 1, 0, 20, tzinfo=timezone.utc)
        spectra = [spectrum(t0 + timedelta(minutes=m)) for m in (0, 30, 60, 120)]
        got = buoys.heights(spectra)
        assert got["start_utc"] == "2026-10-01T00:20:00Z"
        assert got["t_min"] == [0, 30, 60, 120]                # the 90 is a gap, not filled
        assert len(got["hs_m"]) == 4
        assert buoys.heights(spectra, since=t0 + timedelta(minutes=45))["t_min"] == [0, 60]
        assert buoys.heights([]) == {"start_utc": None, "t_min": [], "hs_m": []}

    def test_the_week_rides_in_buoys_json_and_the_rest_in_its_own_file(self):
        assert buoys.HEIGHT_DAYS >= 7
        build = (ROOT / "forecast" / "buoys.py").read_text()
        assert '"heights": {station: heights(_spectra(data_dir, station),' in build
        assert 'out.with_name("buoys_all.json")' in build
        from forecast import publish
        assert publish.BUNDLE_BUOYS_ALL_PATH == "buoys_all.json"

    def test_the_page_draws_it_at_its_own_stamps_and_reads_its_own_time(self):
        tracks = _fn("contextTracks")
        assert "(ms - t0) / HOUR_MS" in tracks                # fractional, never snapped
        assert "join: 0.75" in tracks                          # > 45 min apart is a gap
        spec = _fn("buildSpec")
        assert "`${tr.label} ${height(p.v)} at ${clock(p.t)}`" in spec
        assert "Math.abs(p.i - i) <= 0.5" in spec
        assert "(spec.tracks || []).map((tr) => trackPath(tr, a, z, X, Y, plotW))" in PAGE
        assert ".series .ln.other{stroke:var(--faint)" in PAGE
