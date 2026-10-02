"""The best-track archive: what it lists, and that it stores files byte for byte."""

from __future__ import annotations

from collector import besttracks

LISTING = """<a href="bep172026.dat">bep172026.dat</a> <a href="bcp012026.dat">x</a>
<a href="bal052026.dat">atlantic</a> <a href="bep172025.dat">last year</a>"""


def test_only_this_years_pacific_bdecks_are_listed():
    assert besttracks.listed(LISTING, 2026) == ["bcp012026.dat", "bep172026.dat"]


def test_files_are_stored_as_fetched_and_rewritten_only_when_changed(tmp_path):
    pages = {besttracks.BTK: LISTING,
             besttracks.BTK + "bep172026.dat": "EP, 17, 2026092512,   , BEST, 0, 171N, 1080W, 155\n",
             besttracks.BTK + "bcp012026.dat": "CP, 01, ...\n"}
    assert besttracks.archive(tmp_path, 2026, fetch=pages.__getitem__) == (2, 0, [])
    stored = tmp_path / "besttracks" / "2026" / "bep172026.dat"
    assert stored.read_text() == pages[besttracks.BTK + "bep172026.dat"]
    assert besttracks.archive(tmp_path, 2026, fetch=pages.__getitem__) == (0, 2, [])
