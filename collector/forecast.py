"""Archive published water-temperature forecasts — as an EXPERIMENT.

**This is not the scoring baseline.** SPEC section 3 leaves the baseline choice
open between persistence and a published forecast, and that decision has not
been made. Archiving a forecast is not adopting it.

The reason to archive now anyway is the same reason the observation collector
came first: **forecast history cannot be recovered later.** Nobody serves you
the forecast that was published last March. Without an archive, the question
"did the forecast actually beat persistence at 24 hours?" can never be asked
about any period before we started storing it — and that question is the top
open risk on the project, because if nothing beats persistence there is no skill
to score and section 2's "forecastable but not solved" requirement fails.

Source: Open-Meteo Marine. It is **third party, not NOAA**, which the probe
established is the only convenient option — NWS publishes no water temperature
for these points, and the NOAA routes that do exist (RTOFS, ERDDAP) need a
GRIB/NetCDF dependency the collector does not have. Depending on a third party
on the live scoring path would be a real decision with real consequences.
Archiving its output into our own repository, where it becomes our data, is not.

Every row records what was published and when it was fetched, so the archive can
answer "what did the forecast say at the moment the round would have opened"
rather than "what does the forecast say now".
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .common import DEFAULT_DATA_DIR, ISO, utcnow, write_step_summary
from .metadata import load_metadata
from .ndbc import USER_AGENT
from .stations import Station, load_stations, select

SOURCE = "open-meteo-marine"

BASE_URL = "https://marine-api.open-meteo.com/v1/marine"

#: Two days is enough to evaluate the 24h round horizon with room to spare, and
#: keeps the archive to kilobytes a day.
FORECAST_DAYS = 2

VARIABLE = "sea_surface_temperature"

FORECAST_FIELDS = [
    "fetched_at_utc",
    "valid_time_utc",
    "sea_surface_temperature_c",
    "latitude",
    "longitude",
    "source",
]


class ForecastError(RuntimeError):
    pass


@dataclass
class ForecastResult:
    station_id: str
    added: int = 0
    total_rows: int = 0
    skipped_reason: str = ""
    first_value: str = ""

    @property
    def ok(self) -> bool:
        return not self.skipped_reason


def forecast_path(data_dir: Path, station_id: str) -> Path:
    return Path(data_dir) / "forecasts" / f"{station_id.upper()}.csv"


def build_url(latitude: float, longitude: float) -> str:
    return (
        f"{BASE_URL}?latitude={latitude:.4f}&longitude={longitude:.4f}"
        f"&hourly={VARIABLE}&forecast_days={FORECAST_DAYS}"
    )


def fetch_forecast(
    latitude: float,
    longitude: float,
    *,
    timeout: float = 30.0,
    retries: int = 3,
    sleep=time.sleep,
    opener=urllib.request.urlopen,
) -> dict:
    url = build_url(latitude, longitude)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last: Exception | None = None
    for attempt in range(retries):
        try:
            with opener(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as exc:
            if 400 <= exc.code < 500 and exc.code != 429:
                raise ForecastError(f"HTTP {exc.code} {exc.reason} for {url}") from exc
            last = exc
        except Exception as exc:  # noqa: BLE001
            last = exc
        if attempt < retries - 1:
            sleep(2.0 * (2**attempt))
    raise ForecastError(f"fetch failed after {retries} attempts: {last}")


def parse_forecast(payload: dict) -> list[tuple[str, str]]:
    """Return [(valid_time_utc, value_or_empty)] from an Open-Meteo response.

    A null value is kept as empty, never dropped and never filled in: the same
    rule the observation archive follows. A gap in the forecast is information.
    """

    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    values = hourly.get(VARIABLE) or []
    rows = []
    for index, raw_time in enumerate(times):
        value = values[index] if index < len(values) else None
        # Open-Meteo emits "2026-09-13T06:00"; normalise to the archive's format.
        stamp = str(raw_time)
        if len(stamp) == 16:
            stamp += ":00"
        stamp = stamp.replace("+00:00", "") + ("Z" if not stamp.endswith("Z") else "")
        rows.append((stamp, "" if value is None else str(value)))
    return rows


def read_existing(path: Path) -> set[tuple[str, str]]:
    if not path.exists():
        return set()
    with path.open(newline="", encoding="utf-8") as handle:
        return {
            (row["fetched_at_utc"], row["valid_time_utc"])
            for row in csv.DictReader(handle)
            if row.get("fetched_at_utc")
        }


def append_forecast(
    data_dir: Path,
    station_id: str,
    rows: list[tuple[str, str]],
    *,
    latitude: float,
    longitude: float,
    fetched_at: str,
    dry_run: bool = False,
) -> ForecastResult:
    """Append one forecast issue. Never rewrites an earlier issue.

    The archive is append-only by design: a forecast that was published and
    later revised is two facts, and the round was scored against the first one.
    """

    path = forecast_path(data_dir, station_id)
    seen = read_existing(path)
    fresh = [(t, v) for t, v in rows if (fetched_at, t) not in seen]
    result = ForecastResult(station_id=station_id.upper(), added=len(fresh))
    result.total_rows = len(seen) + len(fresh)
    if rows:
        result.first_value = rows[0][1] or "missing"

    if dry_run or not fresh:
        return result

    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FORECAST_FIELDS, lineterminator="\n")
        if not exists:
            writer.writeheader()
        for valid_time, value in fresh:
            writer.writerow(
                {
                    "fetched_at_utc": fetched_at,
                    "valid_time_utc": valid_time,
                    "sea_surface_temperature_c": value,
                    "latitude": f"{latitude:.4f}",
                    "longitude": f"{longitude:.4f}",
                    "source": SOURCE,
                }
            )
    return result


def collect_station(
    station: Station,
    data_dir: Path,
    metadata: dict,
    *,
    fetched_at: str,
    timeout: float,
    retries: int,
    dry_run: bool,
    fetch=fetch_forecast,
) -> ForecastResult:
    meta = metadata.get(station.id)
    if meta is None or not meta.usable:
        reason = (meta.note if meta else "no metadata") or "no usable coordinates"
        return ForecastResult(station_id=station.id, skipped_reason=reason)

    try:
        payload = fetch(meta.latitude, meta.longitude, timeout=timeout, retries=retries)
        rows = parse_forecast(payload)
        if not rows:
            raise ForecastError("response carried no hourly series")
        return append_forecast(
            data_dir,
            station.id,
            rows,
            latitude=meta.latitude,
            longitude=meta.longitude,
            fetched_at=fetched_at,
            dry_run=dry_run,
        )
    except ForecastError as exc:
        return ForecastResult(station_id=station.id, skipped_reason=str(exc))
    except Exception as exc:  # noqa: BLE001 - one station must not stop the rest
        return ForecastResult(
            station_id=station.id,
            skipped_reason=f"{exc.__class__.__name__}: {exc}",
        )


def format_summary(results: list[ForecastResult], fetched_at: str) -> str:
    lines = [
        f"## Forecast archive (EXPERIMENT) — {fetched_at}",
        "",
        "Source: Open-Meteo Marine — **third party, not NOAA**. Archived to keep "
        "the option open, because forecast history cannot be recovered later. "
        "This is **not** the scoring baseline; SPEC section 3 is still undecided.",
        "",
        "| Station | Rows added | Rows archived | First value | Status |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for r in results:
        lines.append(
            f"| {r.station_id} | {r.added} | {r.total_rows} | "
            f"{r.first_value or '—'} | {'ok' if r.ok else r.skipped_reason} |"
        )
    ok = [r for r in results if r.ok]
    lines += [
        "",
        f"{len(ok)}/{len(results)} stations archived; "
        f"{sum(r.added for r in ok)} forecast rows added.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Archive published forecasts (experiment, not the baseline)."
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--stations", help="Comma-separated station ids.")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    stations = select(
        load_stations(), args.stations.split(",") if args.stations else None
    )
    metadata = load_metadata(args.data_dir)
    if not metadata:
        print(
            "::error title=Forecast archive::"
            "no station_metadata.csv — run `python -m collector.metadata` first"
        )
        return 1

    fetched_at = utcnow().strftime(ISO)
    results = [
        collect_station(
            station,
            args.data_dir,
            metadata,
            fetched_at=fetched_at,
            timeout=args.timeout,
            retries=args.retries,
            dry_run=args.dry_run,
        )
        for station in stations
    ]

    summary = format_summary(results, fetched_at)
    print(summary)
    write_step_summary(summary)

    for r in results:
        if not r.ok:
            print(f"::warning title=Forecast station skipped::{r.station_id}: {r.skipped_reason}")

    failed = [r for r in results if not r.ok]
    if failed and len(failed) == len(results):
        print("::error title=Forecast archive::no station could be archived")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
