"""The model-bias report: pairs, never fills, and reports rather than edits."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from forecast import forecastlog, modelbias

ISO = "%Y-%m-%dT%H:%M:%SZ"
T0 = datetime(2026, 9, 20, 0, tzinfo=timezone.utc)


def row(valid: datetime, lead: int, site: str, hs: float, *, hs5=None, basis="breaking"):
    return {"generated_utc": (valid - timedelta(hours=lead)).strftime(ISO),
            "cycle_utc": "", "valid_utc": valid.strftime(ISO), "lead_h": str(lead),
            "site": site, "hs_m": str(hs), "hs_basis": basis if site != "buoy" else "buoy",
            "hs_5m_m": "" if hs5 is None else str(hs5)}


def measured(valid: datetime, *, south=True, gap=False, pending=False):
    if gap:
        return {"valid_utc": valid.strftime(ISO), "gap": True}
    if pending:
        return {"valid_utc": valid.strftime(ISO), "gap": False, "pending": True}
    return {"valid_utc": valid.strftime(ISO), "gap": False,
            "buoy": {"hs_m": 1.3, "period_s": 15.0 if south else 7.0, "from_deg": 200},
            "breaks": {"coronado_north": {"hs_m": 0.9, "hs_basis": "breaking", "hs_5m_m": 0.8}}}


class TestPairs:
    def test_buoy_5m_and_breaking_each_pair_like_with_like(self):
        rows = [row(T0, 24, "buoy", 1.0), row(T0, 24, "coronado_north", 0.7, hs5=0.6)]
        got = modelbias.samples(rows, lambda t: measured(t))
        assert sorted((s["quantity"], s["forecast"], s["observed"]) for s in got) == [
            ("5 m", 0.6, 0.8), ("breaking", 0.7, 0.9), ("buoy", 1.0, 1.3)]

    def test_breaking_is_only_compared_where_both_sides_broke(self):
        rows = [row(T0, 24, "coronado_north", 0.7, hs5=0.6, basis="5m")]
        got = modelbias.samples(rows, lambda t: measured(t))
        assert [s["quantity"] for s in got] == ["5 m"]

    def test_gaps_and_pending_hours_are_dropped_never_filled(self):
        rows = [row(T0, 0, "buoy", 1.0), row(T0 + timedelta(hours=3), 3, "buoy", 1.0)]
        assert modelbias.samples(rows, lambda t: measured(t, gap=True)) == []
        assert modelbias.samples(rows, lambda t: measured(t, pending=True)) == []

    def test_the_regime_is_read_off_the_measured_buoy(self):
        rows = [row(T0, 0, "buoy", 1.0)]
        assert modelbias.samples(rows, lambda t: measured(t))[0]["regime"] == "south"
        assert modelbias.samples(rows, lambda t: measured(t, south=False))[0]["regime"] == "other"


class TestSummary:
    def found(self, n=40):
        rows = [row(T0 + timedelta(hours=3 * k), 3 * k % 168, "buoy", 1.0 + 0.01 * k)
                for k in range(n)]
        return modelbias.samples(rows, lambda t: measured(t))

    def test_a_low_model_reads_as_a_negative_bias(self):
        table = modelbias.summarise(self.found())
        pooled = next(e for e in table if e["lead"] == "all" and e["regime"] == "all")
        assert pooled["bias_m"] < 0 and pooled["bias_pct"] < 0
        assert "fit_a" in pooled

    def test_no_fit_on_a_thin_sample(self):
        table = modelbias.summarise(self.found(n=10))
        assert all("fit_a" not in e for e in table)

    def test_every_lead_lands_in_a_bucket(self):
        assert [modelbias.lead_bucket(h) for h in (0, 11, 12, 168)] == [
            "0-11 h", "0-11 h", "12-35 h", "144-168 h"]

    def test_the_report_says_it_changes_nothing(self):
        text = modelbias.format_report("t", [], [])
        assert "No pairs yet" in text
        assert "reports and never edits" in modelbias.__doc__.replace("\n", " ").lower().replace("**", "")


class TestTheTwoLogsAreKeptApart:
    def test_the_recomputed_log_is_not_the_shown_log(self, tmp_path):
        assert modelbias.recomputed_dir(tmp_path) != forecastlog.log_dir(tmp_path)
        assert modelbias.recomputed_dir(tmp_path).parent == forecastlog.log_dir(tmp_path).parent
