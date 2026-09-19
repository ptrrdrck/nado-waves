"""The next turn of the tide — when it next stops rising, or stops falling.

CO-OPS publishes the turning points directly (`interval=hilo`), and
`collector.tide` archives them to `data/tide/9410170_turns.csv`. This module
only reads them and answers one question: given a moment, which turn comes
next, and is the tide rising or falling into it.

**The direction is read off the turn, never differenced from the water level.**
Measured on the 6-minute measured series, 2026-09-19: comparing the two most
recent samples reads the direction BACKWARDS on 19.5% of readings, because
near slack water the real change over six minutes is smaller than the gauge's
own wobble (median 6-minute step 1.1 cm). A least-squares slope over a trailing
45 minutes is still wrong 3.3% of the time, and every one of those errors sits
under 5.6 cm/h — a deadband wide enough to suppress them would silence the card
for roughly a quarter of every tide cycle, which is most of the time anyone
would want to look at it.

A harmonic prediction has none of that noise. If the next turn is a high, the
tide is rising into it; if a low, falling. Direction and target then come from
one source and cannot contradict each other on screen, which differencing a
measurement against a predicted target could do at exactly the moment the
reader is most interested.

That does put a MODEL on the observed tab. It is labelled as one, in the card
and in the "standing on" block, because the measured water level and the
predicted turn are two different claims and the page says so rather than
letting the reader assume the whole card was measured.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from collector.common import ISO

#: What CO-OPS calls the turn, and which way the tide runs INTO it.
RISING_INTO = "high"
FALLING_INTO = "low"

DIRECTIONS = {RISING_INTO: "rising", FALLING_INTO: "falling"}


@dataclass(frozen=True)
class Turn:
    """One predicted turning point of the tide."""

    valid_utc: str
    height_m: float
    event: str          # "high" or "low", verbatim from CO-OPS

    @property
    def direction(self) -> str | None:
        """Which way the tide runs INTO this turn.

        None for an event this module does not recognise. CO-OPS emits HH and
        LL at some stations, and a turn whose direction cannot be named is
        better left unnamed than guessed at.
        """

        return DIRECTIONS.get(self.event)

    def as_dict(self) -> dict:
        return {
            "valid_utc": self.valid_utc,
            "height_m": round(self.height_m, 3),
            "event": self.event,
            "direction": self.direction,
        }


def turns_path(data_dir: Path, station: str) -> Path:
    return Path(data_dir) / "tide" / f"{station}_turns.csv"


def read_turns(data_dir: Path, station: str) -> list[Turn]:
    """Every archived turning point, oldest first. Empty when not collected.

    There is no fallback to the hourly prediction file. Deriving a turn from
    an hourly grid puts its time up to 29.4 minutes out (measured, 32 extrema),
    and a surface that silently swapped one for the other would present the
    worse number in the same words as the better one — the shape of fault
    BRIEFING §8 and §17 both turn on.
    """

    path = turns_path(data_dir, station)
    if not path.exists():
        return []

    out: list[Turn] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            stamp, height, event = (
                row.get("time_utc"), row.get("height_m"), row.get("event"),
            )
            if not stamp or not height or not event:
                continue
            try:
                float(height)
                datetime.strptime(stamp, ISO)
            except ValueError:
                continue
            out.append(Turn(valid_utc=stamp, height_m=float(height), event=event))
    out.sort(key=lambda t: t.valid_utc)
    return out


def next_turn(turns: list[Turn], after: datetime) -> Turn | None:
    """The first turn strictly after `after`, or None if the archive ends first.

    None is the honest answer at the tail of the collected window, and the
    surfaces say "not collected" rather than reaching back for the last one.
    """

    stamp = after.astimezone(timezone.utc).strftime(ISO)
    for turn in turns:
        if turn.valid_utc > stamp:
            return turn
    return None


def turns_between(turns: list[Turn], start: datetime, end: datetime) -> list[Turn]:
    """The turns a surface needs to answer `next_turn` across a window.

    One turn past `end`, because the last hour on screen still has a next
    turn and it lies beyond the window by definition.
    """

    first = start.astimezone(timezone.utc).strftime(ISO)
    last = end.astimezone(timezone.utc).strftime(ISO)
    kept = [t for t in turns if first <= t.valid_utc <= last]
    beyond = [t for t in turns if t.valid_utc > last]
    return kept + beyond[:1]
