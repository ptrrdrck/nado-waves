"""The Observe service's Python side: its vocabulary, its codes, and the pull.

The worker itself is tested by node (`service/observe/test/`, in the Tests
workflow). These pin what joins it to this repository: the vocabulary it
refuses rows against is generated from `collector.beachratings`, its table's
columns are the series' columns, a code from `newcode.py` is a fixed point of
the page's normalisation, and the pull loses nothing and invents nothing.
"""

from __future__ import annotations

import csv
import io
import json
import re
import subprocess
import sys
import urllib.error
from datetime import timedelta
from pathlib import Path

import pytest

from collector import observepull
from collector.beachratings import COLUMNS, SERVICE_VOCAB, service_vocab
from collector.common import to_iso, utcnow

ROOT = Path(__file__).resolve().parent.parent
SERVICE = ROOT / "service" / "observe"
sys.path.insert(0, str(SERVICE))
import newcode  # noqa: E402

# ---- the worker's copy of the vocabulary ----------------------------------


def test_the_service_vocabulary_is_generated_from_the_series():
    assert SERVICE_VOCAB.read_text(encoding="utf-8") == service_vocab(), (
        "service/observe/src/vocab.js has drifted: python -m collector.beachratings vocab")


def test_the_service_table_has_the_series_columns_in_order():
    schema = (SERVICE / "schema.sql").read_text(encoding="utf-8")
    body = re.search(r"CREATE TABLE IF NOT EXISTS ratings \((.*?)\n\);", schema, re.S).group(1)
    names = [line.split()[0] for line in body.strip().splitlines()]
    assert names == list(COLUMNS)


def test_no_secret_is_configured_in_a_file():
    """CODES and PULL_TOKEN are Worker secrets: wrangler.toml names neither."""

    toml = (SERVICE / "wrangler.toml").read_text(encoding="utf-8")
    assert "[vars]" not in toml
    for name in ("CODES", "PULL_TOKEN"):
        assert not re.search(rf"^\s*{name}\s*=", toml, re.M)


# ---- codes ----------------------------------------------------------------


def test_the_street_list_is_long_enough_for_the_floor():
    names = newcode.streets()
    assert newcode.space(len(names)) >= newcode.FLOOR


def test_a_code_is_two_different_streets_and_a_house_number():
    names = set(newcode.streets())
    digits = newcode.digits_for(len(names))
    for _ in range(200):
        code = newcode.new_code(sorted(names))
        first, second, number = code.split("-")
        assert first in names and second in names and first != second
        assert len(number) == digits and not number.startswith("0")
        # A fixed point of the page's codeOf: lowercase words and digits
        # joined by single dashes, nothing it would change.
        assert re.fullmatch(r"[a-z]+-[a-z]+-\d+", code)


def test_a_short_list_buys_a_longer_number_and_then_refuses():
    assert newcode.digits_for(60) == 4
    assert newcode.digits_for(30) == 5
    with pytest.raises(newcode.CodeError):
        newcode.digits_for(10)


def test_the_list_refuses_what_a_phone_could_not_type_back(tmp_path):
    bad = tmp_path / "streets.txt"
    bad.write_text("orange\nstar park\n", encoding="utf-8")
    with pytest.raises(newcode.CodeError, match="line 2"):
        newcode.streets(bad)
    bad.write_text("orange\norange\n", encoding="utf-8")
    with pytest.raises(newcode.CodeError, match="twice"):
        newcode.streets(bad)


def test_newcode_prints_the_secret_and_writes_nothing(tmp_path):
    before = sorted(p.name for p in SERVICE.rglob("*"))
    out = subprocess.run([sys.executable, str(SERVICE / "newcode.py"), "o01", "o02"],
                         cwd=tmp_path, capture_output=True, text=True, check=True)
    pairs = json.loads(out.stdout)
    assert sorted(pairs.values()) == ["o01", "o02"]
    assert len(set(pairs)) == 2
    assert list(tmp_path.iterdir()) == []
    assert sorted(p.name for p in SERVICE.rglob("*")) == before


def test_newcode_refuses_a_name_for_an_id(tmp_path):
    out = subprocess.run([sys.executable, str(SERVICE / "newcode.py"), "Pete Smith"],
                         cwd=tmp_path, capture_output=True, text=True)
    assert out.returncode == 2
    assert out.stdout == ""


# ---- the pull -------------------------------------------------------------


def rating(entry_id: str, received) -> dict:
    now = utcnow()
    return {
        "entry_id": entry_id,
        "observed_utc": to_iso(now - timedelta(hours=3)),
        "logged_utc": to_iso(now - timedelta(hours=2)),
        "received_utc": to_iso(received),
        "break_id": "coronado_center",
        "observer_id": "o01",
        "shape": "corners",
        "surface": "glassy",
        "power": "punchy",
        "entered_on": "forecast_page",
        "is_test": "true",
    }


class FakeService:
    """Holds rows the way the worker does: every one, never consumed."""

    def __init__(self, rows, token="t" * 40, status=200, body=None):
        self.rows, self.token, self.status, self.body = rows, token, status, body
        self.asked = []

    def __call__(self, request, timeout=None):
        self.asked.append(request.full_url)
        if request.get_header("Authorization") != f"Bearer {self.token}":
            raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, None)
        if self.status != 200:
            raise urllib.error.HTTPError(request.full_url, self.status, "err", {}, None)
        since = re.search(r"since=([^&]+)", request.full_url).group(1).replace("%3A", ":")
        rows = [r for r in self.rows if r["received_utc"] >= since]
        payload = self.body if self.body is not None else json.dumps({"rows": rows})
        return _Response(payload.encode())


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def page(tmp_path, url="https://nado-observe.example.workers.dev"):
    p = tmp_path / "forecast.html"
    p.write_text(f'<script>\nconst OBSERVE_SERVICE = "{url}";\n</script>', encoding="utf-8")
    return p


def test_the_pull_reads_the_pages_own_address():
    # Whatever it is set to, the page constant is where the pull finds it.
    assert observepull.service_url() == observepull._SERVICE.search(
        observepull.PAGE.read_text(encoding="utf-8")).group(1).rstrip("/")


def test_no_service_yet_is_nothing_to_do(tmp_path):
    def never(*a, **k):
        raise AssertionError("no request without a service")
    assert observepull.run(page=page(tmp_path, ""), path=tmp_path / "r.csv", token="", opener=never) == 0
    assert not (tmp_path / "r.csv").exists()


def test_an_http_address_is_refused(tmp_path):
    with pytest.raises(observepull.PullError, match="https"):
        observepull.service_url(page(tmp_path, "http://example.com"))


def test_the_pull_is_idempotent_and_starts_behind_the_newest_arrival(tmp_path):
    now = utcnow().replace(microsecond=0)
    svc = FakeService([rating("a", now - timedelta(days=5)), rating("b", now - timedelta(hours=1))])
    out = tmp_path / "ratings.csv"
    args = dict(page=page(tmp_path), path=out, token="t" * 40, opener=svc)
    assert observepull.run(**args) == 0
    assert "since=1970-01-01" in svc.asked[0]
    assert observepull.run(**args) == 0
    # The second asks from the newest arrival held, less the overlap, and the
    # overlap's rows are skipped, not stored twice.
    expected = to_iso(now - timedelta(hours=1) - observepull.OVERLAP).replace(":", "%3A")
    assert expected in svc.asked[1]
    with out.open(encoding="utf-8", newline="") as handle:
        stored = list(csv.DictReader(handle))
    assert [r["entry_id"] for r in stored] == ["a", "b"]
    assert list(stored[0]) == list(COLUMNS)


def test_a_row_refused_at_import_is_red_and_the_rest_are_kept(tmp_path):
    now = utcnow()
    bad = rating("bad", now) | {"shape": "clean"}
    svc = FakeService([rating("good", now), bad])
    out = tmp_path / "ratings.csv"
    assert observepull.run(page=page(tmp_path), path=out, token="t" * 40, opener=svc) == 3
    assert "good" in out.read_text(encoding="utf-8")
    assert "bad" not in out.read_text(encoding="utf-8")


def test_a_wrong_token_or_a_bad_answer_fails_and_writes_nothing(tmp_path):
    out = tmp_path / "ratings.csv"
    with pytest.raises(urllib.error.HTTPError):
        observepull.run(page=page(tmp_path), path=out, token="wrong", opener=FakeService([]))
    with pytest.raises(observepull.PullError, match="not set"):
        observepull.run(page=page(tmp_path), path=out, token="", opener=FakeService([]))
    with pytest.raises(observepull.PullError, match="rows"):
        observepull.run(page=page(tmp_path), path=out, token="t" * 40,
                        opener=FakeService([], body='{"rows": "x"}'))
    assert not out.exists()


def test_a_transient_failure_is_retried(tmp_path):
    svc = FakeService([], status=503)
    with pytest.raises(urllib.error.HTTPError):
        observepull.run(page=page(tmp_path), path=tmp_path / "r.csv", token="t" * 40,
                        opener=svc, sleep=lambda s: None)
    assert len(svc.asked) == 3
