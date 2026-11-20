"""collector.nearshore_test, offline: CDIP is refused from a session (BRIEFING
§8), so every response here is a fixture in the form THREDDS serves."""

from __future__ import annotations

import csv
import json
import math
import re

from collector import mop
from collector import nearshore_test as nt

H = 3600.0
T0 = nt.epoch("2024-01-31") + 23.5 * H          # 2024-01-31T23:30Z
TIMES = [T0, T0 + H, T0 + 2 * H]                # straddles the month end

BUOY_DDS = """Dataset {
    Float32 metaDeployLatitude;
    Float32 waveFrequency[waveFrequency = 3];
    Float32 waveBandwidth[waveFrequency = 3];
    Int32 waveTime[waveTime = 3];
    Float32 waveHs[waveTime = 3];
    Byte waveFlagPrimary[waveTime = 3];
    Float32 waveEnergyDensity[waveTime = 3][waveFrequency = 3];
    Float32 waveA1Value[waveTime = 3][waveFrequency = 3];
    Float32 waveB1Value[waveTime = 3][waveFrequency = 3];
    Float32 waveA2Value[waveTime = 3][waveFrequency = 3];
    Float32 waveB2Value[waveTime = 3][waveFrequency = 3];
} cdip/archive/155p1/155p1_historic.nc;"""

BUOY_DAS = """Attributes {
    waveTime {
        String units "seconds since 1970-01-01 00:00:00 UTC";
    }
    waveFrequency {
        String units "Hz";
    }
    waveEnergyDensity {
        Float32 _FillValue -999.99;
    }
    waveHs {
        Float32 _FillValue -999.99;
    }
    NC_GLOBAL {
        String title "Imperial Beach Nearshore";
    }
}"""

ENERGY = [[0.1, 0.2, 0.3], [0.4, -999.99, 0.6], [0.2, 0.2, 0.2]]
WIDTHS = [0.02, 0.05, 0.1]


def hs_of(row):
    return 4 * math.sqrt(sum(e * w for e, w in zip(row, WIDTHS)))


class Fake(mop.Budget):
    def __init__(self):
        super().__init__(limit=50, delay=0.0)
        self.urls = []

    def fetch(self, url, timeout=120.0):
        self.left -= 1
        self.urls.append(url)
        if url.endswith(".dds"):
            return BUOY_DDS
        if url.endswith(".das"):
            return BUOY_DAS
        head = "Dataset { } x;\n---------------------------------------------\n"
        if url.endswith(f"?{mop.TIME}"):
            return head + f"waveTime[3]\n{', '.join(str(int(t)) for t in TIMES)}\n"
        if "waveEnergyDensity[" in url:
            a, b = map(int, re.search(r"waveTime\[(\d+):1:(\d+)\]", url).groups())
            rows = range(a, b + 1)
            out = head + f"waveTime[{len(rows)}]\n" + ", ".join(str(int(TIMES[k])) for k in rows) + "\n"
            hs = [hs_of(ENERGY[k]) if k != 1 else -999.99 for k in rows]
            out += f"waveHs[{len(rows)}]\n" + ", ".join(f"{h:.6f}" for h in hs) + "\n"
            out += f"waveFlagPrimary[{len(rows)}]\n" + ", ".join("1" if k != 2 else "4" for k in rows) + "\n"
            for v in (mop.ENERGY, *mop.MOMENTS):
                out += f"{v}[{len(rows)}][3]\n"
                for j, k in enumerate(rows):
                    vals = ENERGY[k] if v == mop.ENERGY else [0.5, 0.0, -0.25]
                    out += f"[{j}], " + ", ".join(str(x) for x in vals) + "\n"
            return out
        return head + "metaDeployLatitude, 32.57\nwaveFrequency[3]\n0.05, 0.1, 0.2\nwaveBandwidth[3]\n0.02, 0.05, 0.1\n"


def test_the_window_rule_most_joint_hours_inside_one_product_ties_to_the_latest():
    day = 86400.0
    start = nt.epoch("2020-01-01")
    a = [start + k * H for k in range(int(4 * 366 * 24))]                    # 2020-2023 hourly
    # The input has only 2020 (less its last day: 2020 is a leap year) and
    # 2022, so the two calendar years tie on joint hours and every other
    # window has fewer.
    b = [t for t in a if t < nt.epoch("2020-12-31")
         or nt.epoch("2022-01-01") <= t < nt.epoch("2023-01-01")]
    got = nt.choose_window(a, b, {"hindcast": (start, start + 4 * 366 * day)})
    assert nt.iso(got["start"]) == "2022-01-01T00:00:00Z"                  # ties go to the latest
    # A window may not straddle two products.
    got = nt.choose_window(a, a, {"hindcast": (start, nt.epoch("2021-06-15")),
                                  "nowcast": (nt.epoch("2021-06-15"), nt.epoch("2022-07-01"))})
    assert got["product"] == "hindcast" or nt.iso(got["start"]) >= "2021-07-01"
    assert got["end"] <= nt.epoch("2022-07-01")
    assert nt.choose_window(a, [t + 400 * day * 3 for t in a], {"h": (start, start + 10)}) is None


def test_input_sources_name_the_observed_buoy_by_station():
    assert not nt.uses("191p1-067p1-071p1:191p1-220p1-100p1-045p1", "155p1")
    assert nt.uses("191p1-155p1:220p1", "155p1")


def test_month_starts_never_count_a_partial_month():
    got = [nt.iso(t) for t in nt.month_starts(nt.epoch("2024-03-15"), nt.epoch("2024-06-01"))]
    assert got == ["2024-04-01T00:00:00Z", "2024-05-01T00:00:00Z", "2024-06-01T00:00:00Z"]
    assert nt.iso(nt.month_starts(nt.epoch("2024-03-01"), nt.epoch("2024-04-01"))[0]) == "2024-03-01T00:00:00Z"


def test_a_buoy_is_checked_then_fetched_a_month_a_request_and_written_as_mop_is(tmp_path):
    budget = Fake()
    f = nt.open_buoy(budget, "155p1")
    assert f["flag"] and f["schema"]["moments"] and len(f["bands"]) == 3
    recs = nt.fetch_months(budget, f, TIMES[0], TIMES[-1] + 1)
    assert sum("waveEnergyDensity[" in u for u in budget.urls) == 2         # January, then February
    assert [r["flag"] for r in recs] == [1, 1, 4]
    assert recs[1]["hs"] is None and recs[1][mop.ENERGY][1] is None         # a fill is a gap
    out = nt.write_buoy(tmp_path, "imperial_beach_nearshore", f, recs)
    assert out["records"] == 3 and out["readback"]["ok"]
    assert out["flags"] == {"1": 2, "4": 1}
    spec = list(csv.DictReader((tmp_path / "imperial_beach_nearshore_spectrum.csv").open()))
    assert spec[0]["valid_utc"] == "2024-01-31T23:30:00Z" and spec[1]["e01"] == ""
    mom = list(csv.DictReader((tmp_path / "imperial_beach_nearshore_moments.csv").open()))
    assert mom[2]["a2_02"] == "-0.250"
    meta = json.loads((tmp_path / "imperial_beach_nearshore_meta.json").read_text())
    assert meta["ndbc"] == "46235" and meta["global"]["title"] == "Imperial Beach Nearshore"
    # The same reader serves the buoy and MOP: mopdepth reads the files back.
    from forecast import mopdepth
    spec_read, why = mopdepth.read_mop_spectrum(tmp_path, "imperial_beach_nearshore")
    assert spec_read is not None, why


def test_a_renamed_time_unit_stops_the_buoy_before_anything_is_read():
    class Bad(Fake):
        def fetch(self, url, timeout=120.0):
            body = super().fetch(url, timeout)
            return body.replace("seconds since 1970", "days since 1970") if url.endswith(".das") else body

    try:
        nt.open_buoy(Bad(), "155p1")
    except ValueError as exc:
        assert "units" in str(exc)
    else:
        raise AssertionError("a time axis in other units was read")
