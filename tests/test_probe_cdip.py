"""The CDIP probe, tested offline.

The OPeNDAP responses below are written by hand in the DAP2 text layout
THREDDS serves; they were NOT captured from CDIP (both CDIP hosts are denied
at CONNECT from a session, BRIEFING §8). That is why the parser checks every
array against the shape the server declares and refuses a mismatch: the first
real run is the test of the format, and this suite tests the rules — Grid maps
skipped, shapes enforced, fill values masked, a convention chosen by
agreement and never by assumption.
"""

from __future__ import annotations

import math
import urllib.error
from datetime import datetime, timedelta, timezone

import pytest

from collector import probe_cdip
from collector.probe_cdip import (
    CONVENTIONS,
    CdipRecord,
    NdbcRecord,
    ascii_url,
    bearing,
    bin_map,
    classify,
    offsets_table,
    parse_ascii,
    parse_das,
    parse_dds,
    parse_stations,
    records_from,
    score_pair,
)

DDS = """\
Dataset {
    Int32 waveTime[waveTime = 2];
    Float32 waveFrequency[waveFrequency = 3];
    Grid {
      ARRAY:
        Float32 waveHs[waveTime = 2];
      MAPS:
        Int32 waveTime[waveTime = 2];
    } waveHs;
    Grid {
      ARRAY:
        Float32 waveEnergyDensity[waveTime = 2][waveFrequency = 3];
      MAPS:
        Int32 waveTime[waveTime = 2];
        Float32 waveFrequency[waveFrequency = 3];
    } waveEnergyDensity;
} cdip/realtime/191p1_rt.nc;
"""

ASCII = DDS + """\
---------------------------------------------
waveTime[2]
1759795200, 1759797000

waveHs.waveHs[2]
1.25, -999.99
waveHs.waveTime[2]
1759795200, 1759797000

waveEnergyDensity.waveEnergyDensity[2][3]
[0], 0.5, 1.5, 0.25
[1], 0.75, 2.0, 1.0E-4
waveEnergyDensity.waveTime[2]
1759795200, 1759797000
waveEnergyDensity.waveFrequency[3]
0.025, 0.03, 0.035
"""

DAS = """\
Attributes {
    waveTime {
        String long_name "UTC sample start time";
        String units "seconds since 1970-01-01 00:00:00 UTC";
    }
    waveHs {
        Float32 _FillValue -999.99;
    }
    NC_GLOBAL {
        String wmo_id "46232";
        String title "Directional wave and sea surface temperature measurements";
    }
}
"""


def test_the_dds_declares_every_array_with_its_size():
    dds = parse_dds(DDS)
    assert dds["waveTime"] == [("waveTime", 2)]
    assert dds["waveEnergyDensity"] == [("waveTime", 2), ("waveFrequency", 3)]
    assert dds["waveHs"] == [("waveTime", 2)]


def test_the_das_keeps_values_and_strips_quotes():
    das = parse_das(DAS)
    assert das["NC_GLOBAL"]["wmo_id"] == "46232"
    assert das["waveHs"]["_FillValue"] == "-999.99"
    assert probe_cdip.time_units_are_epoch_seconds(das)
    assert probe_cdip.fill_value(das, "waveHs") == -999.99
    assert probe_cdip.fill_value(das, "waveTime") is None


def test_grid_arrays_are_kept_and_their_maps_skipped():
    arrays = parse_ascii(ASCII)
    assert arrays["waveTime"] == [1759795200, 1759797000]
    assert arrays["waveHs"] == [1.25, -999.99]
    assert arrays["waveEnergyDensity"] == [[0.5, 1.5, 0.25], [0.75, 2.0, 1.0e-4]]
    # A map never overwrites the coordinate it names, nor appears as its own key.
    assert "waveFrequency" not in arrays


def test_a_parse_that_disagrees_with_the_declared_shape_is_refused():
    short = ASCII.replace("[1], 0.75, 2.0, 1.0E-4", "[1], 0.75, 2.0")
    with pytest.raises(ValueError, match="declared"):
        parse_ascii(short)


def test_fill_values_become_gaps_never_values():
    arrays = parse_ascii(ASCII)
    flat = [[0.0] * 3] * 2
    arrays.update({k: flat for k in ("waveMeanDirection", "waveA1Value", "waveB1Value",
                                      "waveA2Value", "waveB2Value")})
    recs = records_from(arrays, {"waveHs": -999.99})
    assert recs[0].hs == 1.25
    assert math.isnan(recs[1].hs)
    assert recs[1].time == datetime(2025, 10, 7, 0, 30, tzinfo=timezone.utc)


def test_the_constraint_is_percent_encoded_for_tomcat():
    url = ascii_url("https://x/y.nc", "waveTime[0:1:5],waveHs[0:1:5]")
    assert "[" not in url and "]" not in url
    assert url.endswith(".ascii?waveTime%5B0:1:5%5D,waveHs%5B0:1:5%5D")


@pytest.mark.parametrize("convention", list(CONVENTIONS))
def test_each_convention_recovers_its_own_bearing_and_no_other_does(convention):
    """The control for choosing by agreement: only the right one comes back.

    Over SEVERAL bearings. A reflected convention (90 - phi against phi)
    agrees with the right one wherever the bearing sits on its mirror axis —
    at 215° "atan2(b,a)+180" and "270-atan2(b,a)" are both 20° off, and at
    225° they coincide exactly — so one direction cannot choose. The probe
    scores every energetic bin of every record for the same reason.
    """

    s, c = CONVENTIONS[convention]
    truths = [20.0, 95.0, 170.0, 215.0, 260.0, 300.0]
    errors = {other: [] for other in CONVENTIONS}
    for truth in truths:
        phi = math.radians((truth - c) / s)
        a, b = 0.8 * math.cos(phi), 0.8 * math.sin(phi)
        for other in CONVENTIONS:
            errors[other].append(probe_cdip.angdiff(bearing(a, b, other), truth))
        # alpha2 under the same convention, modulo 180.
        phi2 = math.radians(2 * (truth - c) / s)
        a2, b2 = 0.5 * math.cos(phi2), 0.5 * math.sin(phi2)
        assert probe_cdip.angdiff(bearing(a2, b2, convention, second=True), truth % 180, 180) < 1e-6
    assert max(errors[convention]) < 1e-9
    for other in CONVENTIONS:
        if other != convention:
            assert sorted(errors[other])[len(truths) // 2] > 30.0


def test_bins_are_matched_by_frequency_and_ndbc_rounding_is_absorbed():
    cdip = [0.025, 0.03, 0.095, 0.10125, 0.11]
    ndbc = [0.025, 0.03, 0.095, 0.101, 0.11]
    assert bin_map(cdip, ndbc) == {0: 0, 1: 1, 2: 2, 3: 3, 4: 4}
    # A bin with no partner refuses the whole comparison.
    assert bin_map(cdip, [0.025, 0.04]) is None


def _record(t: datetime, energy: list[float], bearing_deg: float) -> CdipRecord:
    phi = math.radians(bearing_deg)
    n = len(energy)
    return CdipRecord(t, energy, [bearing_deg] * n, [0.7 * math.cos(phi)] * n,
                      [0.7 * math.sin(phi)] * n, [0.0] * n, [0.0] * n)


def test_the_pairing_offset_is_found_on_energy_and_stands_out():
    """NDBC's HH:00 is the CDIP record 30 min BEFORE it here; the others differ."""

    base = datetime(2026, 10, 1, tzinfo=timezone.utc)
    cdip, ndbc = [], {}
    for k in range(48):
        t = base + timedelta(minutes=30 * k)
        # Every record a different sea, so only the true pairing matches.
        energy = [1.0 + 0.3 * math.sin(k + j) for j in range(5)]
        cdip.append(_record(t, energy, 210.0))
        if t.minute == 30:
            stamp = t + timedelta(minutes=30)
            ndbc[stamp] = NdbcRecord(stamp, [round(e, 3) for e in energy], [210.0] * 5,
                                     [210.0] * 5, [0.7] * 5, [0.0] * 5)
    bins = {j: j for j in range(5)}
    table = offsets_table(cdip, ndbc, bins, "atan2(b,a)")
    medians = {k: sorted(s.energy_rel for s in v)[len(v) // 2] for k, v in table.items()}
    assert min(medians, key=medians.get) == -30
    assert medians[-30] < 0.01
    assert min(v for k, v in medians.items() if k != -30) > 10 * medians[-30]


def test_score_pair_reads_direction_only_on_energetic_bins():
    t = datetime(2026, 10, 1, tzinfo=timezone.utc)
    cdip = _record(t, [1.0, 0.001], 200.0)
    cdip.a1[1], cdip.b1[1] = 0.7, 0.0          # an empty bin pointing at 0°
    ndbc = NdbcRecord(t, [1.0, 0.001], [200.0, 200.0], [200.0, 200.0], [0.7, 0.7], [0.0, 0.0])
    score = score_pair(cdip, ndbc, {0: 0, 1: 1}, "atan2(b,a)")
    assert score.dir_err == pytest.approx(0.0, abs=1e-9)


def test_stations_parse_into_pairs():
    assert parse_stations("191P1=46232, 220p1=46258") == [("191p1", "46232"), ("220p1", "46258")]


def test_a_refused_tunnel_is_a_denial_and_exits_2(monkeypatch, capsys):
    def refuse(url, *, timeout=0):
        raise urllib.error.URLError("Tunnel connection failed: 403 Forbidden")

    monkeypatch.setattr(probe_cdip, "fetch", refuse)
    text, denied = classify(urllib.error.URLError("Tunnel connection failed: 403"))
    assert denied
    assert probe_cdip.main(["--no-historic", "--no-ndar"]) == 2
    assert "DENIED" in capsys.readouterr().out


def test_a_buoy_that_names_another_wmo_id_is_not_compared(monkeypatch, tmp_path):
    def serve(url, *, timeout=0):
        if url.endswith(".dds"):
            return DDS.encode()
        if url.endswith(".das"):
            return DAS.replace('"46232"', '"46258"').encode()
        raise AssertionError(f"fetched data after an identity mismatch: {url}")

    monkeypatch.setattr(probe_cdip, "fetch", serve)
    assert probe_cdip.main(["--no-historic", "--no-ndar", "--data-dir", str(tmp_path)]) == 1


def test_a_403_from_the_server_is_not_an_egress_denial():
    """BRIEFING §21a, repeated by this probe's first run on 2026-10-07.

    On a runner there is no proxy: an HTTPError is the origin saying no, and
    its words belong in the report rather than a note about session egress.
    """

    import io
    from email.message import Message

    headers = Message()
    headers["Server"] = "Apache"
    exc = urllib.error.HTTPError("https://x", 403, "Forbidden", headers,
                                 io.BytesIO(b"<html><h1>Access denied</h1> by policy</html>"))
    text, denied = classify(exc)
    assert not denied
    assert "from the server" in text and "Server: Apache" in text and "Access denied by policy" in text


def test_a_server_refusal_is_placed_across_every_door(monkeypatch, capsys):
    def refuse(url, *, timeout=0):
        raise urllib.error.HTTPError(url, 403, "Forbidden", None, None)

    monkeypatch.setattr(probe_cdip, "fetch", refuse)
    assert probe_cdip.main(["--no-historic", "--no-ndar", "--station", "191p1=46232"]) == 1
    out = capsys.readouterr().out
    assert "EGRESS" not in out and "egress-policy" not in out
    assert out.count("HTTP 403 Forbidden from the server") == 1 + len(probe_cdip.DOORS)


def test_a_stamping_convention_that_changes_shows_as_two_runs():
    """46258's pooled table said +0 while its newest pair disagreed 2x: if NDBC
    switched which half-hour it relays, each record must say so on its own."""

    base = datetime(2026, 10, 1, tzinfo=timezone.utc)
    cdip, ndbc = [], {}
    for k in range(96):
        t = base + timedelta(minutes=30 * k)
        cdip.append(_record(t, [1.0 + 0.4 * math.sin(1.7 * k + j) for j in range(5)], 210.0))
    by_time = {r.time: r for r in cdip}
    for h in range(1, 47):
        stamp = base + timedelta(hours=h)
        source = by_time[stamp] if h < 24 else by_time[stamp - timedelta(minutes=30)]
        ndbc[stamp] = NdbcRecord(stamp, list(source.c11), [210.0] * 5, [210.0] * 5, [0.7] * 5, [0.0] * 5)
    matches = probe_cdip.best_matches(cdip, ndbc, {j: j for j in range(5)}, [0.01] * 5)
    assert [m.offset_min for m in matches[:23]] == [0] * 23
    assert [m.offset_min for m in matches[23:]] == [-30] * 23
    assert max(m.energy_rel for m in matches) < 1e-9
    text = "\n".join(probe_cdip.match_lines(matches))
    assert "| +0 | 23 |" in text and "| -30 | 23 |" in text
