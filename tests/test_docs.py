"""The documentation page keeps the app surface's rules, and its numbers.

`app/docs.html` replaced `app/info.html` and `app/geometry.html` (owner's
decision, 2026-10-02), so the rules that governed those two are pinned here. And it
quotes one worked hour through the whole chain, so that hour is rebuilt from
the archive here: if the chain moves, the page has to move with it.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCS = (ROOT / "app" / "docs.html").read_text(encoding="utf-8")
TEXT = re.sub(r"\s+", " ", DOCS)
PAGE = (ROOT / "app" / "forecast.html").read_text(encoding="utf-8")
WORKED = json.loads(DOCS[DOCS.index('id="worked-hour">') + len('id="worked-hour">'):
                         DOCS.index("</script>", DOCS.index('id="worked-hour">'))])


class TestTheVocabulary:
    def test_it_refuses_the_words_a_verified_forecast_would_use(self):
        lowered = TEXT.lower()
        for word in ("rmse", "accuracy", "within a foot", "confidence interval",
                     "error bar of", "% accurate"):
            assert word not in lowered, word

    def test_it_never_calls_the_measurement_what_happened(self):
        lowered = TEXT.lower()
        assert "actual" not in lowered and "what happened" not in lowered

    def test_it_states_the_caveat(self):
        assert "Nothing has ever measured a wave at these three breaks" in TEXT
        assert "physically derived" in TEXT and "not an accurate forecast" in TEXT
        assert "not a wave height at the beach" in TEXT
        assert "not a face height" in TEXT and "has not been fitted" in TEXT
        assert "2016 survey" in TEXT and "nothing has checked it" in TEXT

    def test_the_tab_and_the_breaks_are_named_as_on_the_page(self):
        assert "NOW(ISH)" not in DOCS
        for lower in ("North less south", "less south's", "north less south"):
            assert lower not in DOCS, lower


class TestTheObservationLogIsDescribedNotLinked:
    """An observer who has seen a forecast is not an independent witness, and
    this page ships in the forecast's bundle."""

    def test_no_link_reaches_the_log(self):
        hrefs = re.findall(r'href="([^"]*)"', DOCS)
        for href in hrefs:
            assert "beachlog" not in href and "nado-waves-log" not in href, href

    def test_it_says_why(self):
        assert "never shows a forecast" in TEXT
        assert "does not link to it" in TEXT


class TestItIsReachable:
    def test_the_main_page_links_to_it_below_the_cards(self):
        links = PAGE[PAGE.index('<nav class="links"'):]
        links = links[:links.index("</nav>")]
        assert '<a href="docs.html">Documentation</a>' in links
        assert PAGE.index('id="conditions"') < PAGE.index('<nav class="links"')

    def test_it_links_back(self):
        assert 'href="./"' in DOCS


class TestTheMenu:
    """Built from the article's own headings, so every group is a section with
    an h2 (the first, an h1) and every entry a section with an h3."""

    def test_the_menu_is_built_from_the_headings(self):
        assert 'document.querySelectorAll("#doc > section")' in DOCS
        assert 'sec.querySelectorAll(":scope > section[id]")' in DOCS

    def test_every_id_is_unique(self):
        ids = re.findall(r'\bid="([^"]+)"', DOCS)
        assert len(ids) == len(set(ids)), [i for i in ids if ids.count(i) > 1]

    def test_every_in_page_link_lands(self):
        ids = set(re.findall(r'\bid="([^"]+)"', DOCS))
        markup = DOCS[:DOCS.index("<script")]
        for target in re.findall(r'href="#([^"]+)"', markup):
            assert target in ids, target

    def test_every_subsection_has_an_h3(self):
        body = DOCS[DOCS.index('<article id="doc">'):DOCS.index("</article>")]
        for m in re.finditer(r'<section id="([^"]+)"[^>]*>\s*<(h\d)', body):
            assert m.group(2) in ("h1", "h2", "h3"), m.group(1)
        sections = re.findall(r'<section id="([^"]+)"', body)
        headed = re.findall(r'<section id="([^"]+)"[^>]*>\s*(?:<span class="lbl">[^<]*</span>\s*)?<h[123]', body)
        assert set(sections) == set(headed), set(sections) - set(headed)

    def test_it_collapses_into_a_drawer_on_a_phone(self):
        assert "@media (max-width: 900px)" in DOCS
        assert 'aria-controls="side"' in DOCS and 'aria-expanded="false"' in DOCS


class TestTheWordingFile:
    """app/docs_wording.md is the page's prose for editing, keyed by section
    id. It must be the export of the page exactly, or an edit made to it
    could land against wording the page no longer has."""

    def test_it_is_the_export_of_the_page(self):
        from forecast import docswording

        current = (ROOT / "app" / "docs_wording.md").read_text(encoding="utf-8")
        assert current == docswording.export(DOCS), \
            "app/docs_wording.md is stale: run python -m forecast.docswording"

    def test_every_section_has_its_key(self):
        current = (ROOT / "app" / "docs_wording.md").read_text(encoding="utf-8")
        body = DOCS[DOCS.index('<article id="doc">'):DOCS.index("</article>")]
        keys = re.findall(r"^#{2,3} \[([^\]]+)\]", current, flags=re.M)
        assert keys == re.findall(r'<section id="([^"]+)"', body)

    def test_the_math_comes_through_whole(self):
        current = (ROOT / "app" / "docs_wording.md").read_text(encoding="utf-8")
        assert current.count("```") == 2 * DOCS.count('<pre class="math">')
        assert "γ = 0.5 + 0.4·tanh(33·s₀)" in current


class TestSearch:
    """Full text over every section, from the sidebar, with "/" to reach it
    and a Search button on a phone."""

    def test_there_is_a_search_box_and_a_result_list(self):
        assert 'id="search" type="search"' in DOCS and 'role="search"' in DOCS
        assert 'id="results" role="listbox"' in DOCS
        assert 'id="search-open"' in DOCS

    def test_it_indexes_each_section_once(self):
        """A group's own text excludes its subsections, which are entries of
        their own; drawings and scripts are not text."""

        own = DOCS[DOCS.index("function ownText"):DOCS.index("function buildIndex")]
        assert 'closest("section[id]") === sec' in own
        assert "svg, script, style" in DOCS

    def test_every_word_must_match(self):
        fn = DOCS[DOCS.index("function search(q)"):DOCS.index("function snippet")]
        assert "words.every(" in fn

    def test_the_highlight_does_not_share_a_global_regex_for_its_test(self):
        """A /g regex carries lastIndex between test() calls and skips matches."""

        fn = DOCS[DOCS.index("function markIn"):DOCS.index("function go(")]
        assert 'const has = new RegExp(words.map(reEsc).join("|"), "i");' in fn
        assert "has.test(t.nodeValue)" in fn and "re.test(" not in fn


class TestItFoldsInInfo:
    """Every rule info.html was held to, now on the page that replaced it."""

    def test_each_chain_has_its_own_standing_on_block(self):
        assert "Object.keys(standing" in DOCS
        assert 'renderStanding($("standing-now"), NOW.standing_on' in DOCS
        assert 'renderStanding($("standing-forecast"), DATA.standing_on' in DOCS
        assert "What &ldquo;LIVE&rdquo; is standing on" in DOCS
        assert "What Forecast is standing on" in DOCS
        assert '/^none/i.test(value)' in DOCS and ".none{" in DOCS

    def test_the_observed_footer_names_the_buoy_only(self):
        now = DOCS[DOCS.index("function renderNow"):]
        now = now[:now.index("\n}\n")]
        assert "nothing here is measured at the sand" in re.sub(r"\s+", " ", now)
        assert "DATA" not in now and "spread_assumption" not in now

    def test_the_cycle_line_and_the_spread_note(self):
        assert DOCS.index('id="cycle"') > DOCS.index("What Forecast is standing on")
        assert "Latest data from the" in TEXT and "model run of" in TEXT
        assert "spread.swell_deg != null" in DOCS and "no spread is assumed" in TEXT

    def test_past_hours_are_explained(self):
        assert "what this page showed for that hour" in TEXT
        assert "the same chain" in TEXT and "does not check the beach" in TEXT

    def test_the_charts_are_explained(self):
        assert "today's" in TEXT and "rebuilt" in TEXT
        for view in ("Height", "North vs. South", "Window", "Day's Range", "Shore direction",
                     "Departure", "Forecast + Observed", "Swell trains", "Ensemble",
                     "Daily range"):
            assert f"<dt>{view}</dt>" in DOCS, view

    def test_it_reads_the_same_sources_the_publisher_repoints(self):
        from forecast import publish

        assert publish.REPO_DATA_PATH in DOCS and publish.REPO_NOW_PATH in DOCS


class TestItFoldsInGeometry:
    def test_it_is_filled_from_the_model_never_typed(self):
        assert "const MODEL = /*__MODEL__*/null;" in DOCS
        assert not re.search(r"32\.\d{4,}", DOCS[:DOCS.index("<script")]), \
            "a coordinate typed into the text"

    def test_all_four_views_and_the_three_tables(self):
        for view in ("whole", "near", "tip", "islands"):
            assert f'id: "{view}"' in DOCS
        for table in ("wtable", "vtable", "dtable", "legend", "geo-status", "geo-foot"):
            assert f'id="{table}"' in DOCS
        assert "NOAA ENC" in DOCS and "traced from imagery" in DOCS

    def test_every_small_drawing_names_a_view_that_exists(self):
        for view in re.findall(r'data-map data-view="([^"]+)"', DOCS):
            assert view in ("whole", "near", "tip", "islands"), view
        assert DOCS.count("data-map ") >= 6

    def test_every_geometry_fact_in_the_prose_has_a_reader(self):
        keys = set(re.findall(r'data-geo="([^":]+)', DOCS))
        block = DOCS[DOCS.index("const GEO = {"):DOCS.index("};", DOCS.index("const GEO = {"))]
        for key in keys:
            assert f'"{key}":' in block, key

    def test_the_filled_page_draws(self):
        from forecast import geomviz

        page = geomviz.render(geomviz.build(), template=ROOT / "app" / "docs.html")
        assert "const MODEL = {" in page and "/*__MODEL__*/" not in page


class TestTheWorkedHour:
    """The page quotes one hour through every step. Rebuild it from the
    archive with today's chain: a failure here means the chain moved and the
    page's worked hour (the JSON block AND the prose math) must be redone."""

    @pytest.fixture(scope="class")
    @classmethod
    def rebuilt(cls):
        from forecast import now as observed
        from forecast.nearshore import load_tables
        from forecast.surfzone import load_profiles
        from forecast.transform import load_spectra

        when = datetime.fromisoformat(WORKED["valid_utc"].replace("Z", "+00:00"))
        spectra = {s.time: s for s in load_spectra(ROOT / "data" / "spectra" / "46232")}
        if when not in spectra:
            pytest.fail(f"the worked hour's spectrum ({when}) is not in the archive")
        return observed.build(now=when, spectrum=spectra[when], as_of=True,
                              tables=load_tables(), profiles=load_profiles())

    def test_the_buoy(self, rebuilt):
        assert rebuilt.buoy["hs_m"] == pytest.approx(WORKED["buoy"]["hs_m"], abs=0.0015)
        assert rebuilt.buoy["peak_direction_deg"] == WORKED["buoy"]["peak_direction_deg"]

    def test_the_wind_and_tide(self, rebuilt):
        assert rebuilt.wind.from_deg == WORKED["wind"]["from_deg"]
        assert rebuilt.wind.speed_kt == WORKED["wind"]["speed_kt"]
        assert rebuilt.tide.gauge_height_m == pytest.approx(WORKED["tide"]["gauge_height_m"], abs=0.0015)

    def test_every_step_at_every_break(self, rebuilt):
        got = {b.id: b.nearshore for b in rebuilt.breaks}
        for bid, want in WORKED["breaks"].items():
            effects = got[bid]["effects"]
            for key, value in want["effects"].items():
                if key == "local":
                    for k in ("hs_m", "tp_s", "fetch_km"):
                        assert effects["local"][k] == pytest.approx(value[k], abs=0.0015), (bid, k)
                    for k in ("fetch", "wind"):
                        assert effects["local"][k] == value[k], (bid, k)
                    continue
                assert effects[key] == pytest.approx(value, abs=0.0015), (bid, key)
            for key, value in want["breaking"].items():
                assert got[bid]["breaking"][key] == pytest.approx(value, abs=0.0015), (bid, key)

    def test_the_prose_quotes_the_same_numbers(self):
        north = WORKED["breaks"]["coronado_north"]
        e, k = north["effects"], north["breaking"]
        for value in (e["window_hs_m"], e["refracted_hs_m"], e["diffracted_hs_m"],
                      e["friction_hs_m"], e["shoaled_hs_m"], e["with_chop_hs_m"],
                      k["hs_m"], k["depth_m"], k["gamma"], k["fraction_breaking"]):
            assert f"{value:.3f}".rstrip("0").rstrip(".") in TEXT, value
        assert f"{WORKED['buoy']['hs_m']:.3f}" in TEXT
