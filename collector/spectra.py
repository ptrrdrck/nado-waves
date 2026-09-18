"""Archive NDBC directional spectra for 46232.

Run: ``python -m collector.spectra`` — on Actions, not from a session.

`probe_spectra` answered whether the five files are reachable and complete
(BRIEFING §7: yes — 64 bins, 0.0250–0.5800 Hz, agreeing across all five, with
`r1`/`r2` already normalised). This archives them, because the real-time feed
retains 45 days and `forecast.transform` needs the series, not one record.

Storage, one directory per station, one file per component:

    data/spectra/{STATION}/c11.csv    energy density, m²/Hz
    data/spectra/{STATION}/a1.csv     mean direction, degrees FROM
    data/spectra/{STATION}/a2.csv     principal direction, degrees FROM
    data/spectra/{STATION}/r1.csv     first normalised moment
    data/spectra/{STATION}/r2.csv     second normalised moment

Wide: `time_utc` then one column per frequency bin, the bins in the header.
Five files rather than one because that is how NDBC publishes them and a join
that has to drop a timestamp should drop it from one component's row, visibly,
rather than leave a wide row half-populated.

**Nothing here fills a gap.** A timestamp present in four components and absent
from the fifth is written to the four and left absent from the fifth;
`transform.load_spectra` then drops it from the join. CLAUDE.md: never infer,
interpolate or substitute a missing observation. A silently half-filled
D(f, θ) is the confident-wrong-answer failure BRIEFING §8 lists first.
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .common import DEFAULT_DATA_DIR, ISO, write_step_summary
from .probe_spectra import REALTIME, SPECTRAL_FILES, fetch, parse_spectral

#: NDBC's file name for each component, and the column name we store it under.
#: `swden` carries C11; the other four are named for what they are.
COMPONENTS = {
    "swden": "c11",
    "swdir": "a1",
    "swdir2": "a2",
    "swr1": "r1",
    "swr2": "r2",
}

DEFAULT_STATION = "46232"


class SpectraError(RuntimeError):
    """Raised when a component cannot be stored without guessing."""


@dataclass
class ComponentResult:
    kind: str
    column: str
    fetched_rows: int = 0
    added: int = 0
    existing: int = 0
    denied: bool = False
    error: str = ""
    newest: str | None = None

    @property
    def ok(self) -> bool:
        return not self.error and not self.denied


@dataclass
class CollectResult:
    station: str
    components: list[ComponentResult] = field(default_factory=list)

    @property
    def added(self) -> int:
        return sum(c.added for c in self.components)

    @property
    def denied(self) -> bool:
        return any(c.denied for c in self.components)

    @property
    def complete(self) -> bool:
        return len(self.components) == len(COMPONENTS) and all(c.ok for c in self.components)


def station_dir(data_dir: Path, station: str) -> Path:
    return Path(data_dir) / "spectra" / station.upper()


def component_path(data_dir: Path, station: str, column: str) -> Path:
    return station_dir(data_dir, station) / f"{column}.csv"


def read_existing(path: Path) -> tuple[list[str], set[str]]:
    """Frequency header and the timestamps already stored."""

    if not path.exists():
        return [], set()
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        try:
            header = next(reader)
        except StopIteration:
            return [], set()
        return header[1:], {row[0] for row in reader if row and row[0]}


def format_frequencies(frequencies: list[float]) -> list[str]:
    return [f"{f:.4f}" for f in frequencies]


def append_rows(
    path: Path,
    frequencies: list[float],
    rows: list[tuple[datetime, list[float]]],
) -> tuple[int, str | None]:
    """Append timestamps not already stored. Returns (added, newest stored).

    Refuses to append when the incoming frequency bins differ from the stored
    header. NDBC could re-bin; writing the new values under the old header
    would misalign every column silently, and a wrong spectrum parses perfectly
    (BRIEFING §8, failure mode one). The caller surfaces it as an error rather
    than dropping the file on the floor.
    """

    header = format_frequencies(frequencies)
    stored_header, stored = read_existing(path)

    if stored_header and stored_header != header:
        raise SpectraError(
            f"{path.name}: frequency bins changed "
            f"({len(stored_header)} stored vs {len(header)} incoming). "
            f"Refusing to append under a header the values do not match."
        )

    fresh = [(t, v) for t, v in rows if t.strftime(ISO) not in stored]
    if not fresh:
        newest = max(stored) if stored else None
        return 0, newest

    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not stored_header
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        if new_file:
            writer.writerow(["time_utc", *header])
        for stamp, values in sorted(fresh, key=lambda r: r[0]):
            # A row whose component is short is written short, not padded. The
            # join in transform.load_spectra will refuse a ragged record.
            writer.writerow([stamp.strftime(ISO), *(f"{v:.6g}" for v in values)])

    newest = max(stored | {t.strftime(ISO) for t, _ in fresh})
    return len(fresh), newest


def collect_component(
    station: str,
    kind: str,
    column: str,
    data_dir: Path,
    *,
    timeout: float = 45.0,
) -> ComponentResult:
    result = ComponentResult(kind=kind, column=column)
    url = REALTIME.format(station=station, suffix=SPECTRAL_FILES[kind]["suffix"])
    try:
        payload = fetch(url, timeout=timeout)
    except Exception as exc:  # noqa: BLE001 — classified, not swallowed
        text = f"{exc.__class__.__name__}: {exc}"
        result.error = text
        # A refused tunnel arrives as a URLError with no HTTP status. BRIEFING
        # §8: that is a denial, not throttling, and must not be retried.
        result.denied = "403" in text or "URLError" in text or "CONNECT" in text
        return result

    frequencies, rows, _, _ = parse_spectral(payload.decode("utf-8", errors="replace"))
    result.fetched_rows = len(rows)
    if not frequencies or not rows:
        result.error = "parsed no frequency bins or no rows"
        return result

    path = component_path(data_dir, station, column)
    try:
        added, newest = append_rows(path, frequencies, rows)
    except SpectraError as exc:
        result.error = str(exc)
        return result

    result.added = added
    result.existing = len(rows) - added
    result.newest = newest
    return result


def collect(station: str = DEFAULT_STATION, data_dir: Path = DEFAULT_DATA_DIR) -> CollectResult:
    out = CollectResult(station=station)
    for kind, column in COMPONENTS.items():
        out.components.append(collect_component(station, kind, column, data_dir))
    return out


def format_summary(result: CollectResult) -> str:
    lines = [
        f"### Directional spectra — {result.station}",
        "",
        "| component | file | fetched | new | newest stored |",
        "|---|---|---|---|---|",
    ]
    for c in result.components:
        state = "denied" if c.denied else (c.error or "ok")
        lines.append(
            f"| {c.column} | {c.kind} | {c.fetched_rows} | {c.added} | "
            f"{c.newest or '—'} {'' if state == 'ok' else '(' + state[:60] + ')'} |"
        )
    lines.append("")
    if result.denied:
        lines.append(
            "**Denied at CONNECT.** This is a policy denial, not throttling "
            "(BRIEFING §8). Do not retry or route around it; report the host."
        )
    elif not result.complete:
        lines.append("**Incomplete set.** Timestamps missing from any component are dropped by the join, never filled.")
    else:
        lines.append(f"All five components stored. {result.added} new rows.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--station", default=DEFAULT_STATION)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = parser.parse_args(argv)

    result = collect(args.station, args.data_dir)
    summary = format_summary(result)
    print(summary)
    write_step_summary(summary)

    if result.denied:
        return 2
    if not result.complete:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
