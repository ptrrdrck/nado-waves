"""The directional-spectra probe, tested offline.

The suite makes no network calls; the two NDBC layouts are fixtures. The cases
that matter here are the ones BRIEFING section 8 says produce confident wrong
answers: a layout parsed by assumption rather than detection, a denial read as
an absence, and an integral whose result nobody checked against a case where
the answer is known.
"""

from __future__ import annotations

import math
import urllib.error
from datetime import datetime, timedelta, timezone

import pytest

from collector.probe_spectra import (
    SPECTRAL_FILES,
    FileProbe,
    _demonstrate,
    directional_spread,
    parse_spectral,
    probe_file,
    report,
    window_fraction,
)

# Real-time layout: `value (frequency)` pairs, frequencies on every row.
REALTIME = """\
#YY  MM DD hh mm  Sep_Freq    spec (freq)
2026 09 14 06 40     9.999 0.0100 (0.0325) 0.2500 (0.0375) 0.1000 (0.0425)
2026 09 14 05 40     9.999 0.0200 (0.0325) 0.3000 (0.0375) 0.1200 (0.0425)
"""

# Historical layout: frequencies once, in the header.
HISTORICAL = """\
#YY  MM DD hh mm .0325 .0375 .0425
2024 01 01 00 40 0.0100 0.2500 0.1000
2024 01 01 01 40 0.0200 0.3000 0.1200
"""


def test_the_realtime_layout_is_detected_not_assumed():
    freqs, rows, header, first = parse_spectral(REALTIME)
    assert freqs == [0.0325, 0.0375, 0.0425]
    assert len(rows) == 2
    # Sorted oldest-first, so the newest record is last.
    assert rows[-1][0].hour == 6
    assert rows[-1][1] == [0.01, 0.25, 0.1]
    # The raw lines come back for printing beside the parse.
    assert header.startswith("#YY")
    assert "(0.0325)" in first


def test_the_historical_layout_is_detected_not_assumed():
    freqs, rows, _, _ = parse_spectral(HISTORICAL)
    assert freqs == [0.0325, 0.0375, 0.0425]
    assert len(rows) == 2
    assert rows[-1][1] == [0.02, 0.3, 0.12]


def test_the_two_layouts_agree_on_the_same_numbers():
    """The point of detecting rather than assuming: one answer, two files."""

    freqs_a, rows_a, _, _ = parse_spectral(REALTIME)
    freqs_b, rows_b, _, _ = parse_spectral(HISTORICAL)
    assert freqs_a == freqs_b
    assert sorted(v for _, row in rows_a for v in row) == sorted(
        v for _, row in rows_b for v in row
    )


def test_the_directional_distribution_integrates_to_one():
    """A property with a known answer, which is why it is worth testing.

    Integrating D(f, theta) over the full circle must give exactly 1 for any
    r1, r2, a1, a2: the two cosine terms vanish and only the 0.5 survives. If a
    sign or a factor of pi is wrong in the reconstruction this fails, and an
    error there would otherwise show up as a plausible-looking directional
    distribution that is quietly wrong.
    """

    for a1, r1, a2, r2 in ((210.0, 0.8, 215.0, 0.4), (30.0, 0.1, 300.0, 0.9)):
        step = 0.25
        total = sum(
            directional_spread(r1, a1, r2, a2, (n + 0.5) * step) * math.radians(step)
            for n in range(int(360.0 / step))
        )
        assert total == pytest.approx(1.0, abs=1e-6)


def test_a_narrow_swell_lands_in_the_window_that_contains_it():
    """The control for the integral: a known direction, two windows.

    A tightly focused spectrum pointed at 220° must put most of its energy in
    a window around 220° and very little in one around 300°. Without this the
    integral could be returning a confident number for the wrong sector — and
    at Coronado, where the shadow edge sits within a couple of degrees of the
    normal, the wrong sector is the whole failure mode.
    """

    freqs = [0.05, 0.06, 0.07]
    c11 = [1.0, 2.0, 1.0]
    a1 = [220.0] * 3
    a2 = [220.0] * 3
    r1 = [0.95] * 3
    r2 = [0.95] * 3

    _, on_beam = window_fraction(c11, a1, a2, r1, r2, freqs, (200.0, 240.0))
    _, off_beam = window_fraction(c11, a1, a2, r1, r2, freqs, (280.0, 320.0))

    assert on_beam > 0.5, f"only {on_beam:.1%} of a 220° swell fell in a 200–240° window"
    assert off_beam < 0.05, f"{off_beam:.1%} of a 220° swell leaked into 280–320°"
    assert on_beam > off_beam * 10


def test_a_wider_window_cannot_capture_less_energy():
    """Monotonicity — cheap, and it catches wrap-around arithmetic."""

    freqs = [0.05, 0.06]
    c11 = [1.0, 1.0]
    args = (c11, [215.0] * 2, [215.0] * 2, [0.5] * 2, [0.2] * 2, freqs)
    _, narrow = window_fraction(*args, (205.0, 225.0))
    _, wide = window_fraction(*args, (185.0, 245.0))
    assert wide >= narrow


class _Denied(urllib.error.URLError):
    def __init__(self):
        super().__init__("CONNECT tunnel failed, response 403")


def test_a_connect_denial_is_not_recorded_as_an_absent_file(monkeypatch):
    """The distinction that cost hours in the predecessor.

    A proxy refusing the tunnel never reaches the HTTP layer, so the host looks
    dead rather than forbidden. Recording that as a 404 would say NDBC does not
    publish these files for 46232 — a conclusion about the data drawn from a
    fact about the network.
    """

    def refuse(*_args, **_kwargs):
        raise _Denied()

    monkeypatch.setattr("urllib.request.urlopen", refuse)
    result = probe_file("swden", "https://www.ndbc.noaa.gov/data/realtime2/46232.data_spec")

    assert result.denied
    assert not result.absent
    assert not result.reachable
    assert not result.usable


def test_a_real_404_is_recorded_as_absent(monkeypatch):
    def missing(*_args, **_kwargs):
        raise urllib.error.HTTPError("u", 404, "Not Found", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", missing)
    result = probe_file("swr2", "https://www.ndbc.noaa.gov/data/realtime2/46232.swr2")

    assert result.absent
    assert not result.denied


def test_throttling_is_not_confused_with_denial(monkeypatch):
    def busy(*_args, **_kwargs):
        raise urllib.error.HTTPError("u", 503, "Service Unavailable", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", busy)
    result = probe_file("swdir", "https://www.ndbc.noaa.gov/data/realtime2/46232.swdir")

    assert result.throttled
    assert not result.denied
    assert not result.absent


def test_the_report_leads_with_the_blocked_host_when_denied():
    probes = {
        kind: FileProbe(
            kind=kind,
            url=f"https://www.ndbc.noaa.gov/data/realtime2/46232{spec['suffix']}",
            denied=True,
            error="URLError: CONNECT tunnel failed",
        )
        for kind, spec in SPECTRAL_FILES.items()
    }
    text = "\n".join(report("46232", probes))

    assert "BLOCKED" in text
    assert "www.ndbc.noaa.gov" in text
    # And it must not let a denial read as a verdict about NDBC's holdings.
    assert "says nothing about whether the files exist" in text


def test_the_report_refuses_to_call_a_partial_set_usable():
    probes = {kind: FileProbe(kind=kind, url="u") for kind in SPECTRAL_FILES}
    probes["swden"] = FileProbe(
        kind="swden", url="u", reachable=True, parsed=True, rows=10,
        frequencies=[0.03, 0.04],
    )
    text = "\n".join(report("46232", probes))

    assert "Incomplete" in text
    assert "All five are required" in text


def _usable(kind: str, row: list[float], stamp: datetime, freqs: list[float]) -> FileProbe:
    return FileProbe(
        kind=kind, url=f"https://www.ndbc.noaa.gov/data/realtime2/46232.{kind}",
        reachable=True, parsed=True, rows=1, frequencies=freqs,
        newest=stamp, newest_row=row,
        value_range=(min(row), max(row)),
    )


def _synthetic(stamp_offsets=None, r_scale=1.0):
    freqs = [0.05, 0.06, 0.07]
    base = datetime(2026, 9, 14, 6, 40, tzinfo=timezone.utc)
    offsets = stamp_offsets or {k: 0 for k in SPECTRAL_FILES}
    rows = {
        "swden": [1.0, 2.0, 1.0],
        "swdir": [220.0] * 3,
        "swdir2": [220.0] * 3,
        "swr1": [0.9 * r_scale] * 3,
        "swr2": [0.9 * r_scale] * 3,
    }
    return {
        kind: _usable(kind, rows[kind], base + timedelta(hours=offsets[kind]), freqs)
        for kind in SPECTRAL_FILES
    }


def test_the_demonstration_integral_runs_without_refetching():
    """The demo must use the rows already in hand.

    If it went back to the network these probes — which have no URL that
    resolves — would raise. BRIEFING section 8 records re-reading inside a loop
    turning a 12-second job into minutes, in two separate modules.
    """

    text = _demonstrate("46232", _synthetic(), (200.0, 240.0), None)

    assert "demonstration only" in text
    assert "of the buoy's total" in text
    # And it must refuse to be read as a forecast.
    assert "not a forecast and not a beach height" in text
    assert "Nothing measures waves at" in text


def test_the_demonstration_refuses_to_mix_observation_times():
    """Five files, five newest records, and no guarantee they align.

    Combining them by index when the timestamps differ would silently blend
    observation times into one directional distribution — present, parseable,
    and wrong.
    """

    skewed = _synthetic(stamp_offsets={"swden": 0, "swdir": -1, "swdir2": 0, "swr1": 0, "swr2": 0})
    text = _demonstrate("46232", skewed, (200.0, 240.0), None)

    assert "NOT ATTEMPTED" in text
    assert "different timestamps" in text


def test_percent_scaled_moments_are_detected_and_divided_out():
    """r1/r2 ship scaled by 100 in some NDBC products and not others.

    Guessing wrong does not fail — it produces a plausible directional
    distribution that is wrong, which is the worst available outcome. The two
    conventions must give the same answer.
    """

    plain = _demonstrate("46232", _synthetic(), (200.0, 240.0), None)
    percent = _demonstrate("46232", _synthetic(r_scale=100.0), (200.0, 240.0), None)

    def fraction(text: str) -> float:
        line = next(ln for ln in text.splitlines() if "of the buoy's total" in ln)
        return float(line.split("**")[1].rstrip("%"))

    assert fraction(plain) == pytest.approx(fraction(percent), abs=0.05)
    assert "r2 by 1/100" in percent
    assert "r2 by 1/1" in plain
