"""Archive NWS alerts for Coronado's coast and its coastal waters.

Run: ``python -m collector.nwsalerts`` -- on Actions (collect-beach-inputs.yml,
its one writer); api.weather.gov is denied at CONNECT from a Claude session
(checked 2026-10-24).

Owner's request, 2026-10-24: NWS's coast and ocean warnings in the LIVE
Briefing while they are in force, and on the Forecast tab over the hours they
cover. This only archives; `forecast.alerts` decides which are coast and ocean,
which are in force, and what the page shows.

Two zones are asked for: the land zone the owner's link names (CAZ043, San
Diego County Coastal Areas, county CAC073) and the coastal waters off it
(PZZ750, San Mateo Point to the Mexican border, out to 30 nm). Every alert the
active listing returns for them is kept -- a heat advisory too -- because what
counts is the reader's decision, as with the b-decks (`collector.besttracks`).

Storage: ``data/alerts/{YEAR}/{oid}.json``, the alert's own document
(``/alerts/{id}``) byte for byte, written once: an NWS alert id is never
reissued, and a change is a NEW alert that references the old one. The year
is the alert's ``sent``. An alert issued and ended between two collections is
never seen; that is a gap, never filled.

Exit 2 on a CONNECT denial, 1 on a failed listing or a failed alert, 0 else.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

from .common import DEFAULT_DATA_DIR, write_step_summary
from .wind import USER_AGENT

BASE_URL = "https://api.weather.gov"
#: The owner's link (2026-10-24): showsigwx.php?warnzone=CAZ043&warncounty=CAC073.
LAND_ZONE = "CAZ043"
COUNTY = "CAC073"
#: The coastal waters off Coronado, San Mateo Point to the Mexican border.
MARINE_ZONE = "PZZ750"
ZONES = (LAND_ZONE, MARINE_ZONE)
ARCHIVE_DIR = "alerts"


def _get(url: str, timeout: float = 30.0) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                                   "Accept": "application/geo+json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def listing_url(zones=ZONES) -> str:
    return f"{BASE_URL}/alerts/active?zone={','.join(zones)}"


def oid(alert_id: str) -> str:
    """The file name an alert is kept under: its id without the URN prefix
    ("urn:oid:2.49.0.1.840.0.abc.001.1" -> "2.49.0.1.840.0.abc.001.1")."""

    name = alert_id[len("urn:oid:"):] if alert_id.startswith("urn:oid:") else alert_id
    if not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9._-]*", name) or ".." in name:
        raise ValueError(f"unusable alert id {alert_id!r}")
    return name


def path_for(data_dir: Path, alert_id: str, sent: str) -> Path:
    return Path(data_dir) / ARCHIVE_DIR / sent[:4] / f"{oid(alert_id)}.json"


def archive(data_dir: Path, fetch=_get) -> tuple[int, int, list[str]]:
    """(alerts written, alerts already kept, failures)."""

    listing = json.loads(fetch(listing_url()).decode("utf-8"))
    written = known = 0
    failed: list[str] = []
    for feature in listing.get("features") or []:
        props = feature.get("properties") or {}
        alert_id, sent = props.get("id"), props.get("sent") or ""
        if not alert_id or len(sent) < 4:
            failed.append(f"an alert without an id or a sent time: {feature.get('id')!r}")
            continue
        try:
            path = path_for(data_dir, alert_id, sent)
        except ValueError as exc:
            failed.append(str(exc))
            continue
        if path.exists():
            known += 1
            continue
        try:
            raw = fetch(f"{BASE_URL}/alerts/{alert_id}")
            got = (json.loads(raw.decode("utf-8")).get("properties") or {}).get("id")
        except (urllib.error.URLError, ValueError) as exc:
            failed.append(f"{alert_id}: {exc}")
            continue
        if got != alert_id:
            failed.append(f"{alert_id}: the document says it is {got!r}")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        written += 1
    return written, known, failed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = parser.parse_args(argv)
    try:
        written, known, failed = archive(args.data_dir)
    except (urllib.error.URLError, ValueError) as exc:
        reason = str(getattr(exc, "reason", exc))
        print(f"NWS alerts not reachable: {reason}")
        write_step_summary(f"**NWS alerts not reachable:** {reason}")
        return 2 if "403" in reason or "Tunnel" in reason else 1
    summary = (f"NWS alerts for {', '.join(ZONES)}: {written} new, {known} already kept"
               + (f", {len(failed)} failed: {'; '.join(failed)}" if failed else ""))
    print(summary)
    write_step_summary(summary)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
