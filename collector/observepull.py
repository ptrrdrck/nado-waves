"""Pull the Observe service's ratings into data/beach_ratings/.

    OBSERVE_PULL_TOKEN=... python -m collector.observepull

Run by `.github/workflows/observe-pull.yml`, the file's one writer. The
service (`service/observe/`, `docs/design/observe.md`) holds every rating it
has taken and never marks one as pulled, so nothing is lost when a run fails
after the pull: each run asks for everything received since the newest
`received_utc` this file holds, less `OVERLAP`, and `import_rows` skips what
it already holds by `entry_id`.

The service's address is the page's own `OBSERVE_SERVICE`, read out of
`app/forecast.html`, so the page and the pull cannot point at two services.
While it is empty the pull has nothing to do and says so.

Exit 0 when the pull ran (or there is no service yet); 1 when it could not
reach the service or was refused; 3 when a row arrived that `validate`
refused. The service checks rows with the same vocabulary, so a refusal here
means the two disagree, and that must be seen: the rows it did take are still
written before the exit.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import timedelta
from pathlib import Path

from .beachratings import RATINGS, import_rows, load
from .common import parse_iso, retrying, to_iso, write_step_summary

PAGE = Path(__file__).resolve().parent.parent / "app" / "forecast.html"
#: How far behind the newest stored arrival each pull starts. Arrivals are
#: stamped by the service, so a day would do; two cost nothing.
OVERLAP = timedelta(days=2)
EPOCH = "1970-01-01T00:00:00Z"
USER_AGENT = "nado-waves-observe-pull"

_SERVICE = re.compile(r'^const OBSERVE_SERVICE = "([^"]*)";', re.M)


class PullError(RuntimeError):
    pass


def service_url(page: Path = PAGE) -> str:
    """The page's OBSERVE_SERVICE, without a trailing slash ("" if unset)."""

    found = _SERVICE.search(page.read_text(encoding="utf-8"))
    if not found:
        raise PullError(f"no OBSERVE_SERVICE constant in {page.name}")
    url = found.group(1).rstrip("/")
    if url and not url.startswith("https://"):
        raise PullError(f"OBSERVE_SERVICE is not https: {url!r}")
    return url


def since(path: Path = RATINGS) -> str:
    """Where this pull starts: the newest arrival held, less the overlap."""

    stamps = [parse_iso(r.received_utc) for r in load(path=path)]
    stamps = [s for s in stamps if s is not None]
    return to_iso(max(stamps) - OVERLAP) if stamps else EPOCH


def fetch(base: str, token: str, start: str, *, opener=urllib.request.urlopen,
          sleep=None) -> list[dict]:
    url = f"{base}/pull?{urllib.parse.urlencode({'since': start})}"
    request = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}", "User-Agent": USER_AGENT,
        "Accept": "application/json"})

    def once():
        with opener(request, timeout=60) as response:
            return response.read()

    body = retrying(once, attempts=3, backoff=10.0, sleep=sleep)
    try:
        data = json.loads(body)
    except ValueError as exc:
        raise PullError("the service's answer is not JSON") from exc
    rows = data.get("rows") if isinstance(data, dict) else None
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        raise PullError("the service's answer has no list of rows")
    return rows


def run(*, page: Path = PAGE, path: Path = RATINGS, token: str | None = None,
        opener=urllib.request.urlopen, sleep=None) -> int:
    base = service_url(page)
    if not base:
        print("OBSERVE_SERVICE is empty in app/forecast.html: no service to pull from yet.")
        return 0
    token = token if token is not None else os.environ.get("OBSERVE_PULL_TOKEN", "")
    if not token:
        raise PullError("OBSERVE_PULL_TOKEN is not set (an Actions secret)")
    start = since(path)
    rows = fetch(base, token, start, opener=opener, sleep=sleep)
    result = import_rows(rows, path=path)
    line = (f"Observe pull since {start}: {len(rows)} row(s) returned, "
            f"{result['added']} added, {result['skipped']} already held, "
            f"{len(result['refused'])} refused.")
    print(line)
    write_step_summary(line)
    for entry_id, reason in result["refused"]:
        # The reason names a field and a word, never the observer's code.
        print(f"::error title=Rating refused at import::{entry_id}: {reason}")
    return 3 if result["refused"] else 0


def main() -> int:
    try:
        return run()
    except PullError as exc:
        print(f"::error title=Observe pull failed::{exc}")
        return 1
    except OSError as exc:
        # urllib's HTTPError is an OSError; its text is the status, never the token.
        print(f"::error title=Observe pull failed::{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
