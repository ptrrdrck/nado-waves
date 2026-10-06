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


class TestTheReading:
    def test_it_is_the_buoy_with_nothing_in_the_way(self, tmp_path):
        sp = spectrum(MOMENT - timedelta(minutes=40), peak_dir=300.0)
        write_spectrum(tmp_path, "46047", sp)
        got = buoys.build(data_dir=tmp_path, now=MOMENT)["buoys"][0]
        want = at_buoy(load_spectra(tmp_path / "spectra" / "46047")[0].with_spread("mem"))
        assert got["station"] == "46047"
        assert got["hs_m"] == pytest.approx(want.hs_m, abs=1e-3)
        assert got["trains"] and got["trains"][0]["from_deg"] == pytest.approx(300, abs=3)

    def test_the_trains_sum_to_the_headline(self, tmp_path):
        write_spectrum(tmp_path, "46047", spectrum(MOMENT - timedelta(minutes=40)))
        got = buoys.build(data_dir=tmp_path, now=MOMENT)["buoys"][0]
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
        got = buoys.build(data_dir=tmp_path, now=MOMENT)["buoys"][0]
        assert got["observed_utc"] is None and "hs_m" not in got
        assert got["stale"] and got["warnings"]

    def test_an_old_spectrum_is_marked_stale(self, tmp_path):
        write_spectrum(tmp_path, "46047", spectrum(MOMENT - timedelta(hours=5)))
        got = buoys.build(data_dir=tmp_path, now=MOMENT)["buoys"][0]
        assert got["stale"] and got["hs_m"] > 0
        write_spectrum(tmp_path, "46047", spectrum(MOMENT - timedelta(hours=1)))
        assert not buoys.build(data_dir=tmp_path, now=MOMENT)["buoys"][0]["stale"]

    def test_it_says_what_it_is_standing_on(self, tmp_path):
        write_spectrum(tmp_path, "46047", spectrum(MOMENT - timedelta(minutes=40)))
        standing = buoys.build(data_dir=tmp_path, now=MOMENT)["standing_on"]
        assert list(standing) == ["context buoys"]
        assert standing["context buoys"].startswith("OBSERVED — NDBC directional spectrum at 46047")
        assert "carried to no break" in standing["context buoys"]

    def test_json_round_trips(self, tmp_path):
        write_spectrum(tmp_path, "46047", spectrum(MOMENT - timedelta(minutes=40)))
        assert buoys.main(["--data-dir", str(tmp_path)]) == 0
        got = json.loads((tmp_path / "live" / "buoys.json").read_text())
        assert got["spread"] == "mem" and got["buoys"][0]["station"] == "46047"


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
    """46047 stamps at :20 and :50 and lands on its own lag, bracketed
    2026-10-06 against the collection log (module docstring)."""

    def test_every_buoy_shown_has_measured_lags(self):
        for station in buoys.STATIONS:
            assert buoys.PUBLISH_MINUTES[station]
            assert buoys.PUBLISH_LAG_LATE_MIN[station] >= buoys.PUBLISH_LAG_MIN[station] > 0

    def test_the_archive_stamps_where_it_is_modelled_to(self):
        """At least 98% of archived stamps on the modelled minutes: the newest
        200 had 3 on :40, and a countdown on the wrong minutes would run to
        a stamp that never comes."""

        stamps = [s.time.minute for s in load_spectra(ROOT / "data" / "spectra" / "46047")]
        on = sum(Counter(stamps)[m] for m in buoys.PUBLISH_MINUTES["46047"])
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
        got = buoys.build(data_dir=tmp_path, now=at + timedelta(minutes=30))["buoys"][0]
        assert (got["next_expected"], got["overdue_after"]) == (expected, late)

    def test_it_is_not_46232s_countdown(self):
        from forecast import now as now_mod

        assert buoys.PUBLISH_MINUTES["46047"] != now_mod.PUBLISH_MINUTES["swell"]

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
        assert "carried to no break" in block
        assert "observedAt(b.observed_utc)" in block
        assert "dueSpan(b.next_expected, b.overdue_after" in block
        assert "NOW." not in block
