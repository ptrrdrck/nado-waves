"""Wind sea is the wind still driving a train, never its period alone
(owner's decision, 2026-11-08, BRIEFING §51; forecast.windsea)."""

from __future__ import annotations

import math
from datetime import datetime, timezone

from forecast import windsea as W
from forecast.transform import Train


def test_the_shipped_rule():
    assert (W.LIVE_BETA, W.MODEL_BETA, W.OFFSHORE_STATION) == (1.5, 1.7, "46086")
    assert W.STDMET_U10 == math.log(10 / 2e-4) / math.log(4.1 / 2e-4)


def test_a_light_wind_cannot_drive_a_6_7_s_train():
    """The owner's case, North 5 Nov 17Z: a 6.7 s train needs ~14 kt along
    it at beta 1.5; KNZY read 3 kt."""

    knzy = W.Wind(3 * W.KT_TO_MS, 160.0, "KNZY")
    assert W.driven(6.7, 239.0, knzy, W.LIVE_BETA) is False
    strong = W.Wind(15 * W.KT_TO_MS, 239.0, "KNZY")
    assert W.driven(6.7, 239.0, strong, W.LIVE_BETA) is True
    # Beside it, not along it: no.
    assert W.driven(6.7, 239.0, W.Wind(15 * W.KT_TO_MS, 329.0, "KNZY"), W.LIVE_BETA) is False
    # A 16 s swell needs ~65 kt.
    assert W.driven(16.0, 239.0, strong, W.LIVE_BETA) is False


def test_both_winds_or_no_label():
    a, b = Train(0.5, 4.5, 300.0, 0.1), Train(0.5, 4.5, 300.0, 0.1)
    on = W.Wind(13 * W.KT_TO_MS, 310.0, "x")
    W.label_live([a], (on, on))
    W.label_live([b], (on, None))
    assert a.wind_sea and not b.wind_sea
    calm = W.Wind(0.0, None, "KNZY")
    c = Train(0.5, 4.5, 300.0, 0.1)
    W.label_live([c], (calm, on))
    assert not c.wind_sea
    vrb = W.Wind(5 * W.KT_TO_MS, None, "KNZY")   # VRB: no direction, no age
    assert W.driven(4.5, 300.0, vrb, 1.5) is None


def test_gfs_wave_decides_the_forecast():
    t, u = Train(0.6, 4.0, 300.0, 0.2), Train(0.6, 9.0, 300.0, 0.2)
    W.label_model([t, u], 14.0, 305.0)
    assert t.wind_sea and not u.wind_sea
    W.label_model([t], None, None)
    assert not t.wind_sea
    p = Train(0.6, 5.0, 290.0, 0.2)
    W.label_partitions([p], [(0.6, 5.5, 300.0, True), (1.0, 14.0, 200.0, False)])
    assert p.wind_sea
    W.label_partitions([p], [(0.6, 5.5, 300.0, False)])
    assert not p.wind_sea


def test_the_winds_are_read_as_of_the_spectrum():
    """KNZY's :52 report counts for the next :00 spectrum; a reading from
    another hour does not."""

    t = datetime(2026, 11, 5, 17, tzinfo=timezone.utc)
    knzy = W.knzy_at(t)
    assert knzy is not None and round(knzy.speed_ms / W.KT_TO_MS) == 3 and knzy.from_deg == 160.0
    assert W.knzy_at(datetime(1990, 1, 1, tzinfo=timezone.utc)) is None


def test_the_offshore_wind_is_a_wind_never_a_spectrum():
    """§3a forbids a context buoy's spectrum on the chain. The label reads
    46086's standard met wind alone, and labels; it moves no height."""

    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "forecast" / "windsea.py").read_text()
    live = src[:src.index("# ------------------------------------------------------------------ the report")]
    assert '"observations"' in live and "spectra" not in live
    assert "hs_m" not in live
