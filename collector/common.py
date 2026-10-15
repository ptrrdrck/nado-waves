"""Small shared helpers.

Exists so that the collector, the dead-man check and the station status file
can share plumbing without importing each other in a cycle.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

ISO = "%Y-%m-%dT%H:%M:%SZ"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(value: datetime | None) -> str | None:
    return value.strftime(ISO) if value else None


def parse_iso(value: str | None) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, ISO).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def write_step_summary(text: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(text + "\n")


#: HTTP statuses a second try can cure: a timeout, a rate limit, a server
#: error. Every other 4xx is the request, and asking again changes nothing.
TRANSIENT_HTTP = frozenset({408, 429, 500, 502, 503, 504})


def is_transient(error: BaseException) -> bool:
    """Whether one more try could succeed.

    A proxy that refuses the tunnel (a session's egress policy) is a DENIAL,
    not throttling, and is never retried (BRIEFING §8): it arrives as a
    URLError naming the 403, before any HTTP request is sent.
    """

    import http.client
    import urllib.error

    if isinstance(error, urllib.error.HTTPError):
        return error.code in TRANSIENT_HTTP
    text = str(error)
    if "Tunnel connection failed" in text or "403" in text:
        return False
    return isinstance(error, (OSError, http.client.HTTPException))


def retrying(call, *, attempts: int = 3, backoff: float = 5.0, transient=is_transient,
             sleep=None):
    """`call()`, tried up to `attempts` times while it fails transiently,
    waiting backoff, 2 x backoff, ... between tries. The last failure, or the
    first that is not transient, is raised as it came."""

    import time

    sleep = sleep or time.sleep
    for attempt in range(attempts):
        try:
            return call()
        except Exception as error:  # noqa: BLE001 -- classified, re-raised
            if attempt + 1 >= attempts or not transient(error):
                raise
            sleep(backoff * (2 ** attempt))
