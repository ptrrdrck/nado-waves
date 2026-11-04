"""How fast the tide is moving, MEASURED: the Tide card's rate on "LIVE".

    python -m forecast.tiderate          # the measurements behind it (~10 s)

The card's height is the gauge's newest sample. Beside it (owner's request,
2026-11-04) is how fast the level moved over the gauge's last 30 minutes:
the least-squares slope through its six samples, carried to the open coast
by the same transfer as the height (`tidesite.RATIO`), in metres an hour.
The page shows it as an arrowhead and a speed, or "slack" with a dash.

**It is the last 30 minutes, never "now".** A slope fitted over a trailing
window describes the window's middle. Read as the rate at its newest sample,
it lags every turn by about half the window, and its sign disagrees with the
prediction's rate at that instant on 7-9% of readings (30-60 min windows,
BRIEFING §50). Read as what the window says -- the level over the last 30
minutes -- it agrees with the prediction's own change over the same 30
minutes to 2.2 cm rms.

**Slack, two ways.** The level moved less than `SLACK_M_H` (0.10 m/h, 5 cm in
the window: about 2.3x that 2.2 cm scatter, so below it the gauge cannot
reliably tell which way the water is going); or a predicted turn falls inside
the window, so the line was fitted across a high or a low. A straight line
through a turn measures no direction, and it is where the slope had run
against the turn the card names next: 31 of 35 such readings in 47 days lay
within 24 minutes after a predicted turn. With both rules 4 remain, every one
a seiche 1-10 hours from any turn, and they are shown as measured.

**A gap is a gap.** Six samples, six minutes apart, ending at the newest:
any one missing and there is no rate, never one fitted through fewer.

The rate itself is kept in the payload even when the card says slack, so the
number on the card can always be traced to the one measured.
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from bisect import bisect_left, bisect_right
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collector.common import ISO

from .tidesite import LEAD_MIN, RATIO

#: The window, and the gauge's own spacing inside it.
WINDOW_MIN = 30
STEP_MIN = 6
SAMPLES = WINDOW_MIN // STEP_MIN + 1        # 0, 6, ... 30: six samples

#: Below this the card says slack (5 cm over the window). BRIEFING §50.
SLACK_M_H = 0.10

UP, DOWN, SLACK = "up", "down", "slack"
#: Why a reading is slack: the level hardly moved, or a turn is inside it.
BY_RATE, BY_TURN = "rate", "turn"

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
STATION = "9410170"


def window(series: dict[datetime, float], newest: datetime) -> list[tuple[datetime, float]] | None:
    """The six samples ending at `newest`, or None if any is missing."""

    out = []
    for k in range(SAMPLES - 1, -1, -1):
        when = newest - timedelta(minutes=k * STEP_MIN)
        if when not in series:
            return None
        out.append((when, series[when]))
    return out


def slope_m_h(samples: list[tuple[datetime, float]]) -> float:
    """Least-squares slope through the samples, metres an hour."""

    xs = [(t - samples[-1][0]).total_seconds() / 3600 for t, _ in samples]
    ys = [v for _, v in samples]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    return (sum((x - mx) * (y - my) for x, y in zip(xs, ys))
            / sum((x - mx) ** 2 for x in xs))


def motion(rate_m_h: float, start: datetime, newest: datetime,
           turn_times: list[datetime]) -> tuple[str, str | None]:
    """Up, down or slack, and why slack. `turn_times` are the predicted turns
    on the open coast, sorted; any one within [start, newest] makes it slack."""

    i = bisect_left(turn_times, start)
    if i < len(turn_times) and turn_times[i] <= newest:
        return SLACK, BY_TURN
    if abs(rate_m_h) < SLACK_M_H:
        return SLACK, BY_RATE
    return (UP if rate_m_h > 0 else DOWN), None


def reading(series: dict[datetime, float], newest: datetime,
            turn_times: list[datetime]) -> dict:
    """The card's rate at the open coast for the gauge's sample at `newest`.
    `series` is the gauge's own level (its MLLW), keyed by sample time."""

    samples = window(series, newest)
    if samples is None:
        return {"rate_m_h": None, "motion": None, "motion_why": None,
                "rate_note": f"a {STEP_MIN}-minute sample is missing in the last {WINDOW_MIN} minutes"}
    rate = RATIO * slope_m_h(samples)
    state, why = motion(rate, samples[0][0], newest, turn_times)
    return {"rate_m_h": round(rate, 3), "motion": state, "motion_why": why, "rate_note": ""}


def from_archive(data_dir: Path, observed_utc: str | None, turns) -> dict:
    """`reading` for the gauge sample the card shows, from the archived
    series. `turns` are the card's own predicted turns on the open coast
    (`tideturns.Turn`, already moved by `tidesite.coast_turn`)."""

    if not observed_utc:
        return {"rate_m_h": None, "motion": None, "motion_why": None,
                "rate_note": "no measured level"}
    newest = datetime.strptime(observed_utc, ISO).replace(tzinfo=timezone.utc)
    path = Path(data_dir) / "tide" / f"{STATION}_observed.csv"
    start = newest - timedelta(minutes=WINDOW_MIN)
    series = {t: v for t, v in _read(path).items() if start <= t <= newest} if path.exists() else {}
    times = sorted(datetime.strptime(t.valid_utc, ISO).replace(tzinfo=timezone.utc) for t in turns)
    return reading(series, newest, times)


# ---------------------------------------------------------------------------
# The measurements behind it. Reports, never edits.

def _read(path: Path) -> dict[datetime, float]:
    out = {}
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                when = datetime.strptime(row["time_utc"], ISO).replace(tzinfo=timezone.utc)
                out[when] = float(row["height_m"])
            except (KeyError, ValueError):
                continue
    return out


def measure(data_dir: Path = DEFAULT_DATA_DIR) -> dict:
    """Every gauge sample with a whole window, against the harmonic
    prediction and the predicted turns. Only samples from the first
    predicted turn on: before it, "the next turn" is unknown."""

    from . import tidephase
    from .tideturns import read_turns

    series = _read(data_dir / "tide" / f"{STATION}_observed.csv")
    turns = sorted((datetime.strptime(t.valid_utc, ISO).replace(tzinfo=timezone.utc)
                    - timedelta(minutes=LEAD_MIN), t.event)
                   for t in read_turns(data_dir, STATION))
    times = [t for t, _ in turns]
    c = tidephase.load(data_dir)
    lead = timedelta(minutes=LEAD_MIN)

    def predicted(t):           # the open coast leads the gauge by LEAD_MIN
        return RATIO * tidephase.height(c, t + lead)

    rows = []
    for newest in sorted(series):
        if not times or newest < times[0]:
            continue
        samples = window(series, newest)
        k = bisect_right(times, newest)
        if samples is None or k >= len(turns):
            continue
        rate = RATIO * slope_m_h(samples)
        start = samples[0][0]
        rows.append({
            "rate": rate,
            "pred_change": predicted(newest) - predicted(start),
            "into": 1 if turns[k][1] == "high" else -1,
            "turn_inside": motion(rate, start, newest, times)[1] == BY_TURN,
        })
    if not rows:
        return {"n": 0}
    hours = WINDOW_MIN / 60
    scatter = statistics.pstdev(r["rate"] * hours - r["pred_change"] for r in rows)
    out = {"n": len(rows), "scatter_cm": round(100 * scatter, 2),
           "first": None, "last": None, "by_threshold": {}}
    for cm in (3, 4, 5, 6):
        limit = cm / 100 / hours
        against = [r for r in rows if abs(r["rate"]) >= limit and r["rate"] * r["into"] < 0]
        out["by_threshold"][cm] = {
            "slack_measured": sum(abs(r["rate"]) < limit for r in rows) / len(rows),
            "slack_predicted": sum(abs(r["pred_change"]) < cm / 100 for r in rows) / len(rows),
            "slack_with_turns": sum(abs(r["rate"]) < limit or r["turn_inside"] for r in rows) / len(rows),
            "against_next_turn": len(against),
            "against_after_turn_rule": sum(not r["turn_inside"] for r in against),
        }
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = ap.parse_args(argv)
    got = measure(args.data_dir)
    if not got["n"]:
        print("no gauge samples with a whole window and a predicted turn")
        return 1
    print(f"{got['n']} gauge samples with a whole {WINDOW_MIN}-minute window")
    print(f"scatter of the window's change against the prediction's: {got['scatter_cm']} cm rms")
    print("slack under   measured  predicted  +turn rule   against next turn  after turn rule")
    for cm, row in got["by_threshold"].items():
        mark = "  <- shipped" if abs(cm / 100 / (WINDOW_MIN / 60) - SLACK_M_H) < 1e-9 else ""
        print(f"  {cm} cm      {row['slack_measured']:7.1%}  {row['slack_predicted']:8.1%}"
              f"  {row['slack_with_turns']:9.1%}   {row['against_next_turn']:17d}"
              f"  {row['against_after_turn_rule']:15d}{mark}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
