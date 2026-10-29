"""collector.sharklab: the Coronado hubs' receiver temperatures, archived
once each, gaps left gaps, each hub's break from its own position."""

from __future__ import annotations

import csv
import json

from collector import probe_sharklab as lab
from collector import sharklab as sl


def _fetched(text):
    f = lab.Fetched(url="x", ok=True)
    f.header, f.units, f.rows = lab.parse_erddap_csv(text)
    return f


STATUS = """device_time_utc,serial_number,ambient_temperature,tilt
,,,
1793231909251,667382,22.7,4.9
1793231909251,667382,22.7,4.9
1793231789251,667382,22.6,5.1
1793231900602,667381,22.7,6.0
"""


def test_the_labs_doubled_rows_are_read_once():
    got = sl.readings(_fetched(STATUS))
    assert sorted(len(v) for v in got.values()) == [1, 2]
    assert {r["timestamp_utc"] for r in got["667382"]} == {"2026-10-28T23:58:29Z", "2026-10-28T23:56:29Z"}


def test_store_appends_once_and_keeps_the_first_of_a_changed_value(tmp_path):
    rows = sl.readings(_fetched(STATUS))["667382"]
    assert sl.store(tmp_path, "667382", rows, "2026-10-29T19:00:00Z") == (2, 0)
    assert sl.store(tmp_path, "667382", rows, "2026-10-29T20:00:00Z") == (0, 0)
    changed = [dict(rows[0], ambient_temperature="23.9")]
    assert sl.store(tmp_path, "667382", changed, "2026-10-29T21:00:00Z") == (0, 1)
    with sl.archive_path(tmp_path, "667382", "2026-10").open() as fh:
        kept = list(csv.DictReader(fh))
    assert len(kept) == 2 and {r["first_seen_utc"] for r in kept} == {"2026-10-29T19:00:00Z"}
    assert "23.9" not in {r["ambient_temperature"] for r in kept}


def test_a_hubs_break_is_its_newest_fix_in_the_water():
    """On land both hubs sit together by the lifeguard station (~190 m
    inland of Center): those fixes never place a hub."""
    fixes = _fetched("""device_time_utc,serial_number,latitude,longitude
,,degrees_north,degrees_east
1793200000000,660495,32.6781062,-117.1872756
1793231905003,660495,32.6838331,-117.1845298
1793231894541,660494,32.6749079,-117.1813938
""")
    got = sl.hub_breaks(fixes, lab.breaks(), {})
    assert got["660495"]["break"] == "coronado_center"
    assert got["660495"]["fix_utc"] == "2026-10-28T15:06:40Z"      # the fix in the water, not the newest
    assert got["660494"]["break"] == "coronado_south"
    kept = sl.hub_breaks(_fetched("device_time_utc,serial_number,latitude,longitude\n"), lab.breaks(),
                         {"660495": {"break": "coronado_center"}})
    assert kept == {"660495": {"break": "coronado_center"}}


def test_a_swapped_receiver_warns():
    hubs = sl.registry()["hubs"]
    det = _fetched("hub_serial,serial_number\n,\n660494,667381\n660495,999999\n")
    assert sl.receiver_swaps(det, hubs) == ["hub 660495: registry says 667382, detections name 999999"]


def test_the_registry_holds_ids_never_a_coordinate():
    reg = json.loads(sl.REGISTRY.read_text())
    assert reg["base"].startswith("http://erddap-public.csulbsharklab.org/")
    for hub, v in reg["hubs"].items():
        assert set(v) == {"receiver"} and hub.isdigit() and v["receiver"].isdigit()


def test_a_collection_fetches_at_most_hourly(tmp_path):
    from datetime import datetime, timedelta, timezone

    now = datetime(2026, 10, 29, 21, 0, tzinfo=timezone.utc)
    assert sl.due({}, now, sl.MIN_INTERVAL_MIN)
    assert not sl.due({"last_fetch_utc": "2026-10-29T20:15:00Z"}, now, sl.MIN_INTERVAL_MIN)
    assert sl.due({"last_fetch_utc": "2026-10-29T20:00:00Z"}, now, sl.MIN_INTERVAL_MIN)
    # A skipped collection touches nothing and fetches nothing.
    sl.write_state(tmp_path, {"last_fetch_utc": (datetime.now(timezone.utc) - timedelta(minutes=5))
                              .strftime("%Y-%m-%dT%H:%M:%SZ")})
    lines, code = sl.collect(tmp_path, None, sl.MIN_INTERVAL_MIN)
    assert code == 0 and "not fetched" in lines[0]
    assert sorted(p.name for p in (tmp_path / "sharklab").iterdir()) == ["state.json"]


def test_the_workflow_keeps_the_collectors_interval():
    from pathlib import Path

    flow = Path(".github/workflows/collect-beach-inputs.yml").read_text()
    assert f"python -m collector.sharklab --min-interval-min {sl.MIN_INTERVAL_MIN}" in flow
    assert 'python -m collector.sharklab --backfill-from "${BACKFILL_FROM}"' in flow
