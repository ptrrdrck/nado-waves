"""Surf ratings: what the series refuses, and that the page and it agree.

Like the beach log, the tests that matter are the refusals: a coerced word, a
partial row, a row that names its own observer, a rehearsal decided anywhere
but at entry.
"""

from __future__ import annotations

import csv
import json
import re
from datetime import timedelta
from pathlib import Path

import pytest

from collector.beachratings import (
    COLUMNS,
    POWER,
    RATINGS,
    SHAPE,
    SURFACE,
    RatingError,
    from_row,
    import_rows,
    load,
    validate,
)
from collector.common import to_iso, utcnow

BREAKS = ["coronado_north", "coronado_center", "coronado_south"]
PAGE = Path("app/forecast.html").read_text(encoding="utf-8")


def row(**kwargs) -> dict:
    now = utcnow()
    base = {
        "entry_id": "r-1",
        "observed_utc": to_iso(now - timedelta(hours=2)),
        "logged_utc": to_iso(now - timedelta(minutes=1)),
        "received_utc": to_iso(now),
        "break_id": "coronado_center",
        "observer_id": "pete",
        "shape": "corners",
        "surface": "glassy",
        "power": "punchy",
        "entered_on": "forecast_page",
        "is_test": "false",
    }
    base.update(kwargs)
    return base


def test_the_words_are_the_owners():
    """Owner's words, 2026-11-26: Walled / Sections / Corners for shape, and
    three each for surface and power, mushy to hollow."""

    assert SHAPE == ("walled", "sections", "corners")
    assert SURFACE == ("choppy", "textured", "glassy")
    assert POWER == ("mushy", "punchy", "hollow")


def test_a_full_row_is_kept():
    validate(from_row(row()), breaks=BREAKS)


@pytest.mark.parametrize("field", ["shape", "surface", "power"])
def test_all_three_or_no_row(field):
    with pytest.raises(RatingError):
        validate(from_row(row(**{field: ""})), breaks=BREAKS)


@pytest.mark.parametrize("field,word", [("shape", "closeout"), ("surface", "blown_out"),
                                        ("power", "dumpy"), ("shape", "flat")])
def test_a_word_outside_the_scale_is_refused_not_mapped(field, word):
    """No synonym table: "closeout" is not quietly stored as "walled"."""

    with pytest.raises(RatingError):
        validate(from_row(row(**{field: word})), breaks=BREAKS)


def test_case_is_the_only_thing_forgiven():
    r = validate(from_row(row(shape="Corners", surface="GLASSY")), breaks=BREAKS)
    assert (r.shape, r.surface) == ("corners", "glassy")


def test_the_observer_comes_from_the_service():
    """The page never sends `observer_id`; a row that arrives without one did
    not come through the code check."""

    with pytest.raises(RatingError):
        validate(from_row(row(observer_id="")), breaks=BREAKS)
    assert "observer_id" not in PAGE, "the page must not name its own observer"


def test_a_rehearsal_is_decided_at_entry():
    """Blank is refused: the page always asks, so a row without the answer
    came from something that never did."""

    with pytest.raises(RatingError):
        validate(from_row(row(is_test="")), breaks=BREAKS)
    assert validate(from_row(row(is_test="true")), breaks=BREAKS).is_rehearsal


def test_rated_before_it_was_seen_is_refused():
    now = utcnow()
    with pytest.raises(RatingError):
        validate(from_row(row(observed_utc=to_iso(now), logged_utc=to_iso(now - timedelta(hours=1)))),
                 breaks=BREAKS)


def test_a_future_observation_is_refused_but_a_fast_clock_is_not():
    now = utcnow()
    ahead = to_iso(now + timedelta(minutes=5))
    validate(from_row(row(observed_utc=ahead, logged_utc=ahead)), breaks=BREAKS, now=now)
    later = to_iso(now + timedelta(hours=3))
    with pytest.raises(RatingError):
        validate(from_row(row(observed_utc=later, logged_utc=later)), breaks=BREAKS, now=now)


def test_an_unknown_break_is_refused():
    with pytest.raises(RatingError):
        validate(from_row(row(break_id="coronado")), breaks=BREAKS)


def test_import_is_idempotent_and_append_only(tmp_path):
    path = tmp_path / "ratings.csv"
    first = import_rows([row(), row(entry_id="r-2", shape="walled")], path=path, breaks=BREAKS)
    assert first == {"added": 2, "skipped": 0, "refused": []}
    again = import_rows([row(shape="walled"), row(entry_id="r-3")], path=path, breaks=BREAKS)
    assert again["added"] == 1 and again["skipped"] == 1
    held = {r.entry_id: r for r in load(path=path)}
    assert held["r-1"].shape == "corners", "a re-sent row never rewrites the one held"
    with path.open(encoding="utf-8", newline="") as handle:
        assert tuple(next(csv.reader(handle))) == COLUMNS


def test_a_refused_row_is_reported_and_not_stored(tmp_path):
    path = tmp_path / "ratings.csv"
    got = import_rows([row(power="dumpy")], path=path, breaks=BREAKS)
    assert got["added"] == 0 and got["refused"][0][0] == "r-1"
    assert not path.exists()


def test_the_series_file_is_tracked_and_starts_empty_of_rows():
    with RATINGS.open(encoding="utf-8", newline="") as handle:
        assert tuple(next(csv.reader(handle))) == COLUMNS


def test_the_page_offers_exactly_these_words():
    """One vocabulary in two files: the page's chips and the validator."""

    block = PAGE[PAGE.index("const RATE_ROWS = ["):]
    block = block[:block.index("];") + 2]
    keys = {name: tuple(re.findall(r'\["(\w+)", "[^"]+"\]', body))
            for name, body in re.findall(r'\{key: "(\w+)",[^\[]*\[(.*?)\]\}', block, re.S)}
    assert keys == {"shape": SHAPE, "surface": SURFACE, "power": POWER}


def test_the_page_sends_what_the_series_reads():
    """Every key the page puts on a row is a column, so nothing it records is
    dropped on the way in, and it records where the rating was made."""

    body = PAGE[PAGE.index("function rateRow("):]
    body = body[:body.index("\n}\n")]
    sent = set(re.findall(r"^\s+(\w+):", body, re.M))
    assert sent and sent <= set(COLUMNS)
    assert 'entered_on: "forecast_page"' in body
    assert {"received_utc", "observer_id"}.isdisjoint(sent), "the service's to stamp"


def test_the_series_is_never_in_the_log():
    """Its own series: the log is blind and these rows are not."""

    log = json.dumps(list(Path("collector/beachlog.py").read_text(encoding="utf-8").splitlines()))
    for word in ("sections", "corners", "textured", "punchy"):
        assert word not in log
