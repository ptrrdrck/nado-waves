"""Archive tide at NOAA 9410170 (San Diego), the tide station for these beaches.

Run: ``python -m collector.tide`` — on Actions; api.tidesandcurrents.noaa.gov
is denied at CONNECT from a Claude session (BRIEFING §8, checked 2026-09-18).

CLAUDE.md: "Wind and tide are not optional at these beaches." 9410170 is the
nearest long-record NOAA station; Coronado has no gauge of its own.

Two products, stored separately, because they are two different kinds of thing
and the project's central rule is about not confusing them:

    data/tide/9410170_observed.csv     measured water level  — an OBSERVATION
    data/tide/9410170_predicted.csv    harmonic prediction   — a MODEL

The predictions are what a forecast needs, since they run into the future. They
are also not truth: a harmonic prediction is a model, exactly as CDIP MOP is a
model (CLAUDE.md), and storing them in the same file as the measurements would
make it possible to verify a forecast against a prediction without noticing.
They are kept apart so that any future comparison has to name which it used.

Datum is MLLW throughout, and it is recorded in the file rather than assumed.
Heights are metres.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .common import DEFAULT_DATA_DIR, ISO, utcnow, write_step_summary

STATION = "9410170"

BASE_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"

USER_AGENT = "nado-waves/1.0 (surf forecast research; contact via repository)"

DATUM = "MLLW"
UNITS = "metric"

#: The two products and the file each lands in. `water_level` is measured;
#: `predictions` is computed from harmonic constituents.
PRODUCTS = {
    "water_level": "observed",
    "predictions": "predicted",
}

FIELDS = ["time_utc", "first_seen_utc", "height_m", "kind", "datum"]


class TideError(RuntimeError):
    pass


@dataclass
class TideResult:
    station: str
    product: str
    fetched: int = 0
    added: int = 0
    denied: bool = False
    error: str = ""
    newest: str | None = None
    rows: list[dict[str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.error and not self.denied


def tide_path(data_dir: Path, station: str, product: str) -> Path:
    return Path(data_dir) / "tide" / f"{station}_{PRODUCTS[product]}.csv"


def build_url(
    station: str,
    product: str,
    *,
    begin: datetime,
    end: datetime,
    interval: str | None = None,
) -> str:
    params = [
        f"product={product}",
        f"station={station}",
        f"begin_date={begin:%Y%m%d %H:%M}".replace(" ", "%20"),
        f"end_date={end:%Y%m%d %H:%M}".replace(" ", "%20"),
        f"datum={DATUM}",
        f"units={UNITS}",
        "time_zone=gmt",
        "format=json",
        "application=nado-waves",
    ]
    if interval:
        params.append(f"interval={interval}")
    return f"{BASE_URL}?{'&'.join(params)}"


def fetch(url: str, *, timeout: float = 30.0) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def parse(payload: bytes, product: str) -> list[dict[str, str]]:
    """Parse a CO-OPS response into storable rows.

    CO-OPS reports failure as HTTP 200 with an `error` object in the body —
    exactly the "stale content behind a 200" class of fault BRIEFING §8 lists,
    so the error key is checked before the data key rather than after.
    """

    try:
        data = json.loads(payload.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise TideError(f"response was not JSON: {exc}") from None

    if isinstance(data, dict) and data.get("error"):
        message = data["error"].get("message", "") if isinstance(data["error"], dict) else str(data["error"])
        raise TideError(f"CO-OPS returned an error in a 200 body: {message[:200]}")

    records = data.get("data") if product == "water_level" else data.get("predictions")
    if records is None:
        raise TideError(f"no records for product {product}")

    kind = PRODUCTS[product]
    rows: list[dict[str, str]] = []
    for item in records:
        stamp, value = item.get("t"), item.get("v")
        if not stamp or value in (None, ""):
            # A blank is a gap. It is skipped, never zero-filled.
            continue
        try:
            parsed = datetime.strptime(stamp, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
            height = float(value)
        except ValueError:
            continue
        rows.append({
            "time_utc": parsed.strftime(ISO),
            "first_seen_utc": "",
            "height_m": f"{height:.3f}",
            "kind": kind,
            "datum": DATUM,
        })
    rows.sort(key=lambda r: r["time_utc"])
    return rows


def read_existing(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open(newline="", encoding="utf-8") as fh:
        return {row["time_utc"] for row in csv.DictReader(fh) if row.get("time_utc")}


def append(path: Path, rows: list[dict[str, str]], *, seen_at: str) -> int:
    """Append rows whose timestamp is not already stored.

    Predictions for a future hour are written once and not revisited. A
    prediction that later disagrees with the measurement is the interesting
    case, and overwriting it would destroy exactly that comparison — the same
    reason `collector.archive` logs NDBC's revisions instead of silently
    applying them.
    """

    stored = read_existing(path)
    fresh = [r for r in rows if r["time_utc"] not in stored]
    if not fresh:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        for row in fresh:
            writer.writerow({**row, "first_seen_utc": seen_at})
    return len(fresh)


def collect_product(
    station: str,
    product: str,
    data_dir: Path,
    *,
    back_hours: int = 24,
    ahead_hours: int = 0,
    interval: str | None = None,
) -> TideResult:
    result = TideResult(station=station, product=product)
    now = utcnow()
    url = build_url(
        station, product,
        begin=now - timedelta(hours=back_hours),
        end=now + timedelta(hours=ahead_hours),
        interval=interval,
    )
    try:
        payload = fetch(url)
    except Exception as exc:  # noqa: BLE001 — classified below
        text = f"{exc.__class__.__name__}: {exc}"
        result.error = text
        result.denied = "403" in text or "URLError" in text or "CONNECT" in text
        return result

    try:
        rows = parse(payload, product)
    except TideError as exc:
        result.error = str(exc)
        return result

    result.fetched = len(rows)
    result.rows = rows
    path = tide_path(data_dir, station, product)
    result.added = append(path, rows, seen_at=now.strftime(ISO))
    stored = read_existing(path)
    result.newest = max(stored) if stored else None
    return result


def collect(
    station: str = STATION,
    data_dir: Path = DEFAULT_DATA_DIR,
    *,
    ahead_hours: int = 96,
) -> list[TideResult]:
    """Measured water level for the last day, predictions for the next four."""

    return [
        collect_product(station, "water_level", data_dir, back_hours=24, ahead_hours=0),
        collect_product(
            station, "predictions", data_dir,
            back_hours=0, ahead_hours=ahead_hours, interval="h",
        ),
    ]


def format_summary(results: list[TideResult]) -> str:
    lines = [f"### Tide — {results[0].station if results else STATION}", ""]
    lines += ["| product | stored as | fetched | new | newest |", "|---|---|---|---|---|"]
    for r in results:
        state = "denied" if r.denied else (r.error[:50] if r.error else "")
        lines.append(
            f"| {r.product} | {PRODUCTS[r.product]} | {r.fetched} | {r.added} | "
            f"{r.newest or '—'} {state} |"
        )
    lines.append("")
    if any(r.denied for r in results):
        lines.append("**Denied at CONNECT** — policy, not throttling (BRIEFING §8).")
    else:
        lines.append(
            "Predictions are a harmonic MODEL, stored apart from the measured "
            "water level so the two can never be compared by accident."
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--station", default=STATION)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--ahead-hours", type=int, default=96)
    args = parser.parse_args(argv)

    results = collect(args.station, args.data_dir, ahead_hours=args.ahead_hours)
    summary = format_summary(results)
    print(summary)
    write_step_summary(summary)

    if any(r.denied for r in results):
        return 2
    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
