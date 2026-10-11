"""Fetch NOAA's harmonic constants for 9410170, the tide station for these beaches.

Run: ``python -m collector.harcon`` — on Actions; api.tidesandcurrents.noaa.gov
is denied at CONNECT from a Claude session (BRIEFING §8).

The Tide card's phase line (`forecast.tidephase`) reads spring and neap,
the station's lag behind the Moon, and how big a coming spring will be from
these constants. They are fetched, never typed, for the same reason a buoy
coordinate is: a typed copy drifts from its source without anyone noticing.

Stored as CO-OPS serves it, with when and where it came from:

    data/tide/9410170_harcon.json

`phase_GMT` is what the tide model reads. `phase_local` is the same lag
moved by speed × 8 h to Pacific standard time, and is NOT comparable across
constituents of different speeds: read naively, it puts San Diego's spring
tides 11 h before new or full moon, where `phase_GMT` puts them 3 h before
(BRIEFING §41).

The constants change only when NOAA re-analyses the station, so the
collection runs this with `--max-age-days` and re-fetches only an old file.
A fetch that fails leaves the stored file as it was.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path

from .common import DEFAULT_DATA_DIR, ISO, parse_iso, utcnow, write_step_summary
from .tide import STATION, fetch

MDAPI = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi"

#: The fields the tide model needs from every constituent.
REQUIRED = ("name", "amplitude", "phase_GMT", "speed")


class HarconError(RuntimeError):
    pass


def harcon_path(data_dir: Path = DEFAULT_DATA_DIR, station: str = STATION) -> Path:
    return Path(data_dir) / "tide" / f"{station}_harcon.json"


def url(station: str = STATION) -> str:
    return f"{MDAPI}/stations/{station}/harcon.json?units=metric"


def parse(payload: bytes) -> dict:
    """The response, checked: CO-OPS reports some failures as a 200 with an
    `error` body, and a list missing a phase would be read as a zero lag."""

    try:
        body = json.loads(payload.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise HarconError(f"response was not JSON: {exc}") from None
    if not isinstance(body, dict) or body.get("error"):
        raise HarconError(f"CO-OPS error in a 200 body: {str(body)[:200]}")
    rows = body.get("HarmonicConstituents")
    if not rows:
        raise HarconError("no HarmonicConstituents in the response")
    for row in rows:
        missing = [k for k in REQUIRED if row.get(k) is None]
        if missing:
            raise HarconError(f"constituent {row.get('name')!r} lacks {missing}")
    names = {row["name"] for row in rows}
    for need in ("M2", "S2", "N2", "K1", "O1"):
        if need not in names:
            raise HarconError(f"{need} missing from the constituents")
    return body


def age_days(path: Path) -> float | None:
    try:
        stored = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    fetched = parse_iso(stored.get("fetched_utc"))
    return None if fetched is None else (utcnow() - fetched) / timedelta(days=1)


def collect(station: str = STATION, data_dir: Path = DEFAULT_DATA_DIR) -> dict:
    source = url(station)
    body = parse(fetch(source))
    record = {"station": station, "fetched_utc": utcnow().strftime(ISO),
              "source": source, "response": body}
    path = harcon_path(data_dir, station)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=1) + "\n")
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--station", default=STATION)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--max-age-days", type=float, default=None,
                        help="skip the fetch when the stored file is younger than this")
    args = parser.parse_args(argv)

    path = harcon_path(args.data_dir, args.station)
    age = age_days(path)
    if args.max_age_days is not None and age is not None and age < args.max_age_days:
        print(f"{path.name} is {age:.1f} days old; not re-fetched.")
        return 0
    try:
        record = collect(args.station, args.data_dir)
    except Exception as exc:  # noqa: BLE001 -- reported, and the stored file stands
        message = f"Harmonic constants not fetched: {exc}"
        print(message)
        write_step_summary(f"### Harmonic constants\n\n{message}")
        return 1
    rows = record["response"]["HarmonicConstituents"]
    summary = (f"### Harmonic constants — {args.station}\n\n"
               f"{len(rows)} constituents, units {record['response'].get('units')}, "
               f"stored in {path.name}.")
    print(summary)
    write_step_summary(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
