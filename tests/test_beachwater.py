"""collector.beachwater: the county's water quality at Coronado's three
stations, read through the site's own screen services, each sample and
event kept once, each status change logged."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone

from collector import beachwater as bw


def _sample(sid, date, result, qualifier="=", station="IB-079", method="ddPCR", units="Copies/100ml"):
    """One row as SampleBlock.GetSamples returns it (probe run 6)."""
    return {"AnalysisMethod": {"Id": 0, "Label": method}, "Site": {"StationID": station},
            "Parameter": {"Id": 0, "Label": "Enterococcus"}, "Units": {"Id": 0, "Label": units},
            "Sample": {"Id": sid, "SampleDate": date, "SampleTime": "07:06:00", "Result": result,
                       "Qualifier": qualifier, "Comments": "", "ParameterOther": "", "AnalysisMethodOther": "",
                       "UnitOther": ""}}


def _event(station, kind, issued, lifted="1900-01-01T00:00:00", group="All County", distance="300 ft"):
    """One row of the posting report (SamplePostingReportBlock.GetSites)."""
    return {"BeachName": "Coronado City Beaches", "Distance": distance, "EventType": kind, "GroupName": group,
            "IndicatorDetails": "", "PublicNotification": "", "Reason": "", "StationID": station,
            "IssueDateTime": issued, "LiftedDateTime": lifted, "CompletedWithin3Hours": True, "District": 3}


def test_the_registry_holds_ids_never_a_coordinate():
    reg = bw.registry()
    assert reg["base"] == "https://cosdapps.sandiegocounty.gov/sdbeachinfo"
    assert set(reg["breaks"]) == {"coronado_north", "coronado_center", "coronado_south"}
    assert {v["station"] for v in reg["breaks"].values()} == {"EH-060", "EH-050", "IB-079"}
    for v in reg["breaks"].values():
        assert set(v) == {"station", "site", "name"} and v["site"].isdigit()


def test_a_scripts_aggregates_are_found_by_name_and_api_version():
    js = ('return controller.callAggregateWithStartIndexAndClientVars("ScreenDataSetGetSamples", '
          '"screenservices/CoSD_Beach_Water_CW/MainFlow/SampleBlock/ScreenDataSetGetSamples", '
          '"L1afk6NDVnwatxTYNUtNLA", maxRecords, startIndex, function (b) {')
    assert bw.CALL.findall(js) == [("ScreenDataSetGetSamples",
                                    "screenservices/CoSD_Beach_Water_CW/MainFlow/SampleBlock/ScreenDataSetGetSamples",
                                    "L1afk6NDVnwatxTYNUtNLA")]


def test_the_sites_times_are_whole_seconds_utc_and_its_null_date_is_empty():
    assert bw.utc_text("2026-08-09T23:23:00.253Z") == "2026-08-09T23:23:00Z"
    assert bw.utc_text("2026-10-26T18:00:00Z") == "2026-10-26T18:00:00Z"
    assert bw.utc_text("1900-01-01T00:00:00") == "" and bw.utc_text(None) == ""


def test_samples_are_kept_once_by_the_countys_id_and_a_changed_one_is_counted(tmp_path):
    got = [bw.sample_row(_sample("7669", "2026-10-27", "195", "<")),
           bw.sample_row(_sample("7785", "2026-10-28", "420"))]
    assert got[0]["qualifier"] == "<" and got[0]["units"] == "Copies/100ml"
    assert bw.store_samples(tmp_path, "IB-079", got, "2026-10-30T01:23:01Z") == (2, 0)
    assert bw.store_samples(tmp_path, "IB-079", got, "2026-10-30T02:00:00Z") == (0, 0)
    changed = [dict(got[1], result="421")]
    assert bw.store_samples(tmp_path, "IB-079", changed, "2026-10-30T03:00:00Z") == (0, 1)
    with (tmp_path / "beach_water" / "samples" / "IB-079.csv").open() as fh:
        kept = list(csv.DictReader(fh))
    assert [r["result"] for r in kept] == ["195", "420"]
    assert {r["first_seen_utc"] for r in kept} == {"2026-10-30T01:23:01Z"}


def test_an_event_listed_in_several_groups_is_kept_once_and_a_moved_lift_is_a_new_row(tmp_path):
    """Probe run 8: one Center closure read "1.5 Miles" in one group and
    "300 ft" in another."""
    rows = [bw.event_row(_event("EH-050", "Closure", "2026-06-02T17:37:00Z", "2026-06-19T00:15:00Z",
                                distance="1.5 Miles")),
            bw.event_row(_event("EH-050", "Closure", "2026-06-02T17:37:00Z", "2026-06-19T00:15:00Z",
                                group="Coronado Shoreline")),
            bw.event_row(_event("IB-068", "Closure", "2026-10-29T23:24:00Z"))]
    stations = {"EH-060", "EH-050", "IB-079"}
    assert bw.store_events(tmp_path, rows, stations, "2026-10-30T01:23:01Z") == 1     # IB-068 is not ours
    assert bw.store_events(tmp_path, rows, stations, "2026-10-30T02:00:00Z") == 0
    rain = bw.event_row(_event("IB-079", "Advisory", "2026-10-23T18:00:00Z", "2026-10-26T18:00:00Z"))
    moved = dict(rain, lifted_utc="2026-10-27T18:00:00Z")
    assert bw.store_events(tmp_path, [rain], stations, "2026-10-23T19:00:00Z") == 1
    assert bw.store_events(tmp_path, [moved], stations, "2026-10-25T19:00:00Z") == 1
    with (tmp_path / "beach_water" / "events.csv").open() as fh:
        kept = list(csv.DictReader(fh))
    assert len(kept) == 3 and kept[0]["distance"] == "1.5 Miles"
    assert [r["lifted_utc"] for r in kept[1:]] == ["2026-10-26T18:00:00Z", "2026-10-27T18:00:00Z"]


def test_a_status_is_logged_when_it_changes_and_only_then(tmp_path):
    seen = "2026-10-30T01:23:01Z"
    assert bw.store_status(tmp_path, {"IB-079": ("", "Open"), "EH-050": ("", "Open")}, seen) == ["EH-050", "IB-079"]
    assert bw.store_status(tmp_path, {"IB-079": ("", "Open"), "EH-050": ("", "Open")}, seen) == []
    assert bw.store_status(tmp_path, {"IB-079": ("4", "Closed"), "EH-050": ("", "Open")}, seen) == ["IB-079"]


def test_a_collection_fetches_at_most_every_half_hour():
    now = datetime(2026, 10, 30, 2, 0, tzinfo=timezone.utc)
    assert bw.due({}, now, bw.MIN_INTERVAL_MIN)
    assert not bw.due({"last_fetch_utc": "2026-10-30T01:45:00Z"}, now, bw.MIN_INTERVAL_MIN)
    assert bw.due({"last_fetch_utc": (now - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")}, now,
                  bw.MIN_INTERVAL_MIN)


class _Fake(bw.Client):
    """A client whose site is a dict: service -> rows, by StationIdFilter."""

    def __init__(self, by_service):
        super().__init__("https://example.invalid/sdbeachinfo")
        self.by_service = by_service
        self.services = {k: ("p", "a") for k in by_service}
        self.module_version = "v"
        self.calls = []

    def start(self):
        return self

    def aggregate(self, service, variables, max_records=1000, start=0):
        self.calls.append((service, variables.get("StationIdFilter") or variables.get("SiteId"), start))
        got = self.by_service[service]
        got = got(variables) if callable(got) else got
        return {"List": {"List": got[start:start + max_records]}}


def test_a_collection_files_only_a_stations_own_samples_and_pages_the_report(tmp_path, monkeypatch):
    sites = {v["site"]: v["station"] for v in bw.registry()["breaks"].values()}
    report = [_event("IB-079", "Closure", f"2026-06-{d:02d}T17:37:00Z", f"2026-06-{d:02d}T23:00:00Z")
              for d in range(1, 29)] * 40                                   # 1,120 rows: two pages
    fake = _Fake({
        "SampleBlock.GetSamples": lambda v: [_sample("1", "2026-10-28", "420", station=sites[v["StationIdFilter"]]),
                                             _sample("2", "2026-10-28", "999", station="IB-050")],
        "SamplePostingReportBlock.GetSites": report,
        "BlockLegend.GetLegends": [{"Legend": {"Id": 2, "Label": "Open"}}, {"Legend": {"Id": 4, "Label": "Closed"}}],
        "BlockMarkup.GetEvents": lambda v: [{"PriorityMax": 4}] if v["SiteId"] == "121" else [],
    })
    monkeypatch.setattr(bw, "Client", lambda base: fake)
    lines, code = bw.collect(tmp_path)
    assert code == 0, lines
    for station in ("EH-060", "EH-050", "IB-079"):
        with (tmp_path / "beach_water" / "samples" / f"{station}.csv").open() as fh:
            assert [r["result"] for r in csv.DictReader(fh)] == ["420"]       # IB-050's row is not filed here
    assert any("rows from other stations: ['IB-050']" in line for line in lines)
    assert [c[2] for c in fake.calls if c[0] == "SamplePostingReportBlock.GetSites"] == [0, 1000]
    with (tmp_path / "beach_water" / "events.csv").open() as fh:
        assert len(list(csv.DictReader(fh))) == 28
    state = json.loads((tmp_path / "beach_water" / "state.json").read_text())
    assert state["current"] == {"EH-050": {"priority": "", "status": "Open"},
                                "EH-060": {"priority": "", "status": "Open"},
                                "IB-079": {"priority": "4", "status": "Closed"}}
    assert state["last_ok_utc"] == state["last_fetch_utc"]


def test_a_refusal_keeps_the_archive_and_says_so(tmp_path, monkeypatch):
    class Refusing(_Fake):
        def aggregate(self, service, variables, max_records=1000, start=0):
            raise bw.Refused(f"{service}: No role validation found")

    monkeypatch.setattr(bw, "Client", lambda base: Refusing({}))
    lines, code = bw.collect(tmp_path)
    assert code == 1 and "No role validation found" in lines[-1]
    state = json.loads((tmp_path / "beach_water" / "state.json").read_text())
    assert "last_ok_utc" not in state and "No role validation found" in state["last_error"]
