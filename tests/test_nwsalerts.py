"""NWS's coast and ocean alerts: the archive (collector.nwsalerts) and which
are in force (forecast.alerts). api.weather.gov is denied from a session, so
these are built on the API's documented shape, never a live response."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import pytest

from collector import nwsalerts
from forecast import alerts

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "app" / "forecast.html").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "collect-beach-inputs.yml").read_text(encoding="utf-8")


def _t(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(timezone.utc)


def props(n: int, event: str = "Coastal Flood Warning", *, sent: str = "2026-10-24T03:12:00-07:00",
          onset: str | None = "2026-10-24T03:12:00-07:00", ends: str | None = "2026-10-25T14:00:00-07:00",
          expires: str = "2026-10-24T15:00:00-07:00", ugc=("CAZ043", "CAZ552"), vtec: str | None = "NEW",
          message: str = "Alert", status: str = "Actual", refs=()):
    return {
        "@id": f"https://api.weather.gov/alerts/urn:oid:2.49.0.1.840.0.abc{n}.001.1",
        "id": f"urn:oid:2.49.0.1.840.0.abc{n}.001.1",
        "areaDesc": "San Diego County Coastal Areas",
        "geocode": {"SAME": ["006073"], "UGC": list(ugc)},
        "references": [{"@id": f"https://api.weather.gov/alerts/{r}", "identifier": r,
                        "sender": "w-nws.webmaster@noaa.gov", "sent": "2026-10-24T03:12:00-07:00"} for r in refs],
        "sent": sent, "effective": sent, "onset": onset, "expires": expires, "ends": ends,
        "status": status, "messageType": message, "category": "Met", "severity": "Moderate",
        "certainty": "Likely", "urgency": "Expected", "event": event,
        "sender": "w-nws.webmaster@noaa.gov", "senderName": "NWS San Diego CA",
        "headline": f"{event} issued October 24 at 3:12AM PDT until October 25 at 2:00PM PDT by NWS San Diego CA",
        "description": "* WHAT...Flooding caused by high tides.", "instruction": None,
        "parameters": {"NWSheadline": [f"{event.upper()} REMAINS IN EFFECT UNTIL 2 PM PDT SUNDAY"],
                       "VTEC": [f"/O.{vtec}.KSGX.CF.W.0003.261024T1012Z-261025T2100Z/"] if vtec else []},
    }


def feature(p: dict) -> dict:
    return {"id": p["@id"], "type": "Feature", "geometry": None, "properties": p}


def keep(tmp_path: Path, *ps: dict) -> Path:
    for p in ps:
        path = nwsalerts.path_for(tmp_path, p["id"], p["sent"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(feature(p)), encoding="utf-8")
    return tmp_path


class TestTheArchive:
    def test_it_asks_for_the_coast_and_its_waters(self):
        assert nwsalerts.listing_url() == "https://api.weather.gov/alerts/active?zone=CAZ043,PZZ750"

    def test_each_alert_is_kept_byte_for_byte_once(self, tmp_path):
        a, b = props(1), props(2, "Small Craft Advisory", ugc=("PZZ750",))
        raw = {f"https://api.weather.gov/alerts/{p['id']}": json.dumps(feature(p), indent=4).encode()
               for p in (a, b)}
        calls = []

        def fetch(url):
            calls.append(url)
            if url == nwsalerts.listing_url():
                return json.dumps({"features": [feature(a), feature(b)]}).encode()
            return raw[url]

        assert nwsalerts.archive(tmp_path, fetch) == (2, 0, [])
        stored = nwsalerts.path_for(tmp_path, a["id"], a["sent"])
        assert stored == tmp_path / "alerts" / "2026" / "2.49.0.1.840.0.abc1.001.1.json"
        assert stored.read_bytes() == raw[f"https://api.weather.gov/alerts/{a['id']}"]
        # Seen again: never fetched or written twice.
        calls.clear()
        assert nwsalerts.archive(tmp_path, fetch) == (0, 2, [])
        assert calls == [nwsalerts.listing_url()]

    def test_a_document_for_another_alert_is_refused(self, tmp_path):
        a = props(1)

        def fetch(url):
            if url == nwsalerts.listing_url():
                return json.dumps({"features": [feature(a)]}).encode()
            return json.dumps(feature(props(9))).encode()

        written, known, failed = nwsalerts.archive(tmp_path, fetch)
        assert (written, known) == (0, 0) and "says it is" in failed[0]
        assert not (tmp_path / "alerts").exists()

    def test_an_unusable_id_is_never_a_path(self):
        for bad in ("urn:oid:../x", "urn:oid:", "../../etc"):
            with pytest.raises(ValueError):
                nwsalerts.oid(bad)

    def test_a_denial_exits_two(self, monkeypatch, tmp_path):
        def denied(data_dir, fetch=None):
            raise urllib.error.URLError("Tunnel connection failed: 403 Forbidden")

        monkeypatch.setattr(nwsalerts, "archive", denied)
        assert nwsalerts.main(["--data-dir", str(tmp_path)]) == 2

    def test_the_collection_runs_it_and_commits_the_archive(self):
        assert "python -m collector.nwsalerts" in WORKFLOW
        assert "python -m forecast.alerts" in WORKFLOW
        assert "git add data/alerts" in WORKFLOW
        # Its one writer.
        others = [f.name for f in (ROOT / ".github" / "workflows").glob("*.yml")
                  if f.name != "collect-beach-inputs.yml" and "collector.nwsalerts" in f.read_text()]
        assert others == []


class TestWhatIsShown:
    def test_coast_and_ocean_only(self):
        assert alerts.relevant(props(1))
        assert alerts.relevant(props(2, "Rip Current Statement"))
        # Every alert for the coastal waters, whatever its event.
        assert alerts.relevant(props(3, "Dense Fog Advisory", ugc=("PZZ750",)))
        # Never heat, fire weather or wind on land.
        for event in ("Heat Advisory", "Red Flag Warning", "Wind Advisory", "Dense Fog Advisory"):
            assert not alerts.relevant(props(4, event))
        # Never a test or an exercise.
        assert not alerts.relevant(props(5, status="Test"))

    def test_in_force_from_onset_to_ends_and_never_before_sent(self, tmp_path):
        later = props(1, onset="2026-10-25T06:00:00-07:00")
        segs = alerts.segments(alerts.load(keep(tmp_path, later)))
        assert segs[0]["start_utc"] == "2026-10-25T13:00:00Z"
        assert segs[0]["stop_utc"] == segs[0]["ends_utc"] == "2026-10-25T21:00:00Z"
        assert alerts.in_force(segs, _t("2026-10-25T12:59:00Z")) == []
        assert [s["event"] for s in alerts.in_force(segs, _t("2026-10-25T13:00:00Z"))] == ["Coastal Flood Warning"]
        assert alerts.in_force(segs, _t("2026-10-25T21:00:00Z")) == []

    def test_without_ends_it_runs_to_expires_and_says_no_end(self, tmp_path):
        segs = alerts.segments(alerts.load(keep(tmp_path, props(1, ends=None))))
        assert segs[0]["ends_utc"] is None and segs[0]["stop_utc"] == "2026-10-24T22:00:00Z"

    def test_an_update_replaces_it_from_when_it_was_sent(self, tmp_path):
        first = props(1)
        update = props(2, sent="2026-10-24T09:00:00-07:00", ends="2026-10-25T18:00:00-07:00", vtec="EXT",
                       message="Update", refs=(first["id"],))
        segs = alerts.segments(alerts.load(keep(tmp_path, first, update)))
        assert [(s["start_utc"], s["stop_utc"]) for s in segs] == [
            ("2026-10-24T10:12:00Z", "2026-10-24T16:00:00Z"),
            ("2026-10-24T16:00:00Z", "2026-10-26T01:00:00Z")]
        # A past moment reads the version in force then.
        assert alerts.in_force(segs, _t("2026-10-24T12:00:00Z"))[0]["id"] == first["id"]
        assert alerts.in_force(segs, _t("2026-10-24T17:00:00Z"))[0]["id"] == update["id"]

    def test_a_cancel_ends_it_and_is_never_shown(self, tmp_path):
        first = props(1)
        for cancel in (props(2, sent="2026-10-24T09:00:00-07:00", vtec="CAN", message="Update", refs=(first["id"],)),
                       props(3, sent="2026-10-24T09:00:00-07:00", vtec=None, message="Cancel", refs=(first["id"],))):
            segs = alerts.segments(alerts.load(keep(tmp_path / cancel["id"][-8:], first, cancel)))
            assert [s["id"] for s in segs] == [first["id"]]
            assert segs[0]["stop_utc"] == "2026-10-24T16:00:00Z"

    def test_one_line_an_event(self, tmp_path):
        land = props(1, "Hurricane Warning", ugc=("CAZ043",), ends="2026-10-25T12:00:00-07:00")
        sea = props(2, "Hurricane Warning", ugc=("PZZ750",))
        segs = alerts.segments(alerts.load(keep(tmp_path, land, sea)))
        got = alerts.in_force(segs, _t("2026-10-24T12:00:00Z"))
        assert [s["id"] for s in got] == [sea["id"]]

    def test_its_page_is_the_owners_link(self):
        url = alerts.url(props(1))
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        assert url.startswith("https://forecast.weather.gov/showsigwx.php?")
        assert q["warnzone"] == ["CAZ043"] and q["warncounty"] == ["CAC073"]
        assert q["product1"] == ["Coastal Flood Warning"] and q["local_place1"] == ["Coronado CA"]
        marine = urllib.parse.parse_qs(urllib.parse.urlsplit(
            alerts.url(props(2, "Small Craft Advisory", ugc=("PZZ750",)))).query)
        assert marine["warnzone"] == ["PZZ750"] and marine["warncounty"] == ["marine"]

    def test_the_briefing_reads_what_was_sent_by_its_build(self, tmp_path):
        keep(tmp_path, props(1), props(2, "High Surf Advisory", sent="2026-10-24T09:00:00-07:00",
                                       onset="2026-10-24T09:00:00-07:00"))
        got = alerts.briefing(tmp_path, _t("2026-10-24T12:00:00Z"))
        assert [a["event"] for a in got] == ["Coastal Flood Warning"]
        assert set(got[0]) == {"id", "event", "headline", "url", "start_utc", "ends_utc"}

    def test_the_page_file_reaches_48_h_back_as_of_its_build(self, tmp_path):
        old = props(1, sent="2026-10-20T03:00:00-07:00", onset="2026-10-20T03:00:00-07:00",
                    ends="2026-10-20T09:00:00-07:00", expires="2026-10-20T09:00:00-07:00")
        keep(tmp_path, old, props(2))
        got = alerts.build(tmp_path, _t("2026-10-24T12:00:00Z"))
        assert [a["id"] for a in got["alerts"]] == [props(2)["id"]]
        # Not yet sent at the build: not in its file.
        assert alerts.build(tmp_path, _t("2026-10-24T10:00:00Z"))["alerts"] == []


class TestThePage:
    def test_it_fetches_its_own_file(self):
        assert 'const ALERTS_SOURCE = PARAM.get("alerts") || "../data/live/alerts.json";' in PAGE
        assert PAGE.count("fetch(fresh(ALERTS_SOURCE)") == 1

    def test_the_forecast_line_sits_above_the_swell_card(self):
        assert PAGE.index('id="fc-alerts"') < PAGE.index('<section id="panel"')

    def test_nws_words_are_escaped(self):
        row = PAGE[PAGE.index("const alertRow = "):]
        row = row[:row.index("\n};\n")]
        assert "esc(a.event)" in row and "esc(a.headline)" in row and "esc(a.url)" in row

    def test_published_with_the_page(self):
        from forecast import publish

        assert publish.REPO_ALERTS_PATH in PAGE
        assert publish.BUNDLE_ALERTS_PATH in publish.repoint(PAGE)
