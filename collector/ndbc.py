"""Fetching and parsing NDBC real-time standard meteorological files.

Source format (https://www.ndbc.noaa.gov/data/realtime2/{STATION}.txt):

    #YY  MM DD hh mm WDIR WSPD GST  WVHT   DPD   APD MWD   PRES  ATMP  WTMP ...
    #yr  mo dy hr mn degT m/s  m/s     m   sec   sec degT   hPa  degC  degC ...
    2026 09 12 20 50  270   5.0  6.0    MM    MM    MM  MM 1012.5  19.3  20.1 ...

Three facts drive the design of this module:

1. Each file holds a *rolling window* of recent history (NDBC retains 45 days),
   newest row first — not just the latest reading. So polling four times a day
   still captures every hourly observation. Polling frequency and data
   resolution are independent. Never read only the top row.
2. Timestamps are UTC.
3. Missing values are the literal string ``MM``. They are recorded as empty,
   never filled in (SPEC section 4, "Failure handling").
"""

from __future__ import annotations

import gzip
import io
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone

DEFAULT_BASE_URL = "https://www.ndbc.noaa.gov/data/realtime2"

USER_AGENT = (
    "beat-the-buoy-collector/1.0 "
    "(+https://github.com/ptrrdrck/beat-the-buoy; NDBC archiving job)"
)

MISSING = "MM"

#: Historical archive files (`data/historical/stdmet/{STATION}h{YEAR}.txt.gz`)
#: do NOT use `MM`. They use per-column numeric sentinels, and the values are
#: plausible-looking numbers — 999.0 read as an air temperature, 99.0 as a wind
#: speed. Storing those would be inventing data, which is the one thing this
#: project does not do, and it would look like a successful parse while doing it.
#:
#: Matched by float value rather than by string so "99.0" and "99.00" both hit.
#: Deliberately per-column, not a blanket "all nines" rule: 999.0 hPa is a
#: perfectly real sea-level pressure, and PRES's actual sentinel is 9999.0.
NUMERIC_SENTINELS = {
    "wdir": 999.0,
    "wspd": 99.0,
    "gst": 99.0,
    "wvht": 99.0,
    "dpd": 99.0,
    "apd": 99.0,
    "mwd": 999.0,
    "pres": 9999.0,
    "atmp": 999.0,
    "wtmp": 999.0,
    "dewp": 999.0,
    "vis": 99.0,
    "ptdy": 99.0,
    "tide": 99.0,
}


def is_missing(column: str, token: str) -> bool:
    """Is this token NDBC's way of saying "no value"?

    Handles both conventions: `MM` in the real-time feed, and the numeric
    sentinels used by the historical archive.
    """

    if token == MISSING:
        return True
    sentinel = NUMERIC_SENTINELS.get(column.lower())
    if sentinel is None:
        return False
    try:
        return float(token) == sentinel
    except ValueError:
        return False

#: Time columns, in the order NDBC writes them.
TIME_COLUMNS = ("YY", "MM", "DD", "hh", "mm")

#: Measurement columns of the standard meteorological file, in NDBC's order.
#: The parser maps by header name rather than position, so a station that omits
#: trailing columns (TIDE is frequently absent) still parses correctly.
DATA_COLUMNS = (
    "WDIR",
    "WSPD",
    "GST",
    "WVHT",
    "DPD",
    "APD",
    "MWD",
    "PRES",
    "ATMP",
    "WTMP",
    "DEWP",
    "VIS",
    "PTDY",
    "TIDE",
)

#: The quantity v1 predicts (SPEC section 2): sea surface water temperature.
PRIMARY_COLUMN = "WTMP"


class NdbcError(RuntimeError):
    """Raised when a station file cannot be fetched or makes no sense."""


@dataclass(frozen=True)
class Observation:
    """One timestamped row of a station file.

    ``values`` maps lowercased NDBC column names to their published strings.
    A missing value (``MM``) is stored as ``""`` — never guessed, never
    interpolated.
    """

    timestamp: datetime
    values: dict[str, str] = field(default_factory=dict)

    @property
    def timestamp_utc(self) -> str:
        return self.timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")

    def get(self, column: str) -> str:
        return self.values.get(column.lower(), "")


def _split_header(line: str) -> list[str]:
    return line.lstrip("#").split()


def _parse_timestamp(parts: list[str]) -> datetime:
    year, month, day, hour, minute = (int(p) for p in parts[:5])
    if year < 100:  # pre-2007 files used a 2-digit year; be tolerant anyway
        year += 2000
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def parse_realtime2(text: str) -> list[Observation]:
    """Parse a full ``realtime2`` standard meteorological file.

    Returns every observation in the file, oldest first. Rows that cannot be
    parsed are skipped rather than failing the run — a single malformed line
    must not cost us the other 45 days in the same response.
    """

    columns: list[str] | None = None
    observations: dict[str, Observation] = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("#"):
            header = _split_header(line)
            # The first header row names the columns; the second gives units
            # ("#yr mo dy hr mn ...") and is ignored.
            if columns is None and header[:5] == list(TIME_COLUMNS):
                columns = header
            continue

        parts = line.split()
        if len(parts) < 5:
            continue

        names = columns if columns is not None else list(TIME_COLUMNS + DATA_COLUMNS)

        try:
            timestamp = _parse_timestamp(parts)
        except (ValueError, IndexError):
            continue

        values: dict[str, str] = {}
        for index, name in enumerate(names[5:], start=5):
            if index >= len(parts):
                break
            token = parts[index]
            column = name.lower()
            values[column] = "" if is_missing(column, token) else token

        observation = Observation(timestamp=timestamp, values=values)
        observations[observation.timestamp_utc] = observation

    return sorted(observations.values(), key=lambda o: o.timestamp)


def base_url() -> str:
    """The realtime2 directory. Overridable for local testing against a mirror."""

    return os.environ.get("NDBC_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def station_url(station_id: str) -> str:
    return f"{base_url()}/{station_id.upper()}.txt"


def fetch_station(
    station_id: str,
    *,
    timeout: float = 30.0,
    retries: int = 3,
    backoff: float = 2.0,
    sleep=time.sleep,
    opener=urllib.request.urlopen,
) -> str:
    """Fetch one station's rolling history file, with backoff on transient errors.

    A 404 is permanent (wrong or retired station id) and is not retried.
    """

    url = station_url(station_id)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"},
    )

    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with opener(request, timeout=timeout) as response:
                payload = response.read()
                if response.headers.get("Content-Encoding") == "gzip":
                    payload = gzip.GzipFile(fileobj=io.BytesIO(payload)).read()
                return payload.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise NdbcError(f"{station_id}: no such station file ({url})") from exc
            last_error = exc
        except Exception as exc:  # noqa: BLE001 - network layer, retry anything else
            last_error = exc

        if attempt < retries - 1:
            sleep(backoff * (2**attempt))

    raise NdbcError(f"{station_id}: fetch failed after {retries} attempts: {last_error}")
