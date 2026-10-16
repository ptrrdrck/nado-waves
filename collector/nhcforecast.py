"""Archive NHC's official forecast track (the OFCL lines of ATCF a-decks).

Run: ``python -m collector.nhcforecast`` — on Actions (collect-beach-inputs.yml);
ftp.nhc.noaa.gov is denied at CONNECT from a Claude session.

Why (owner's call, 2026-10-16): the LIVE briefing may say how long a
hurricane's swell keeps coming — "until we can't anymore" — and that needs
where NHC expects the storm to go, not only where it has been. The best
track (`collector.besttracks`) is the past; NHC's official forecast, the
track the cone is drawn around, is the future. Archived so the forecast
fixes can be checked against the best-track fixes that later land on them,
which is how the project confirms it on its own end.

What is fetched: for each storm whose archived b-deck has a fix in the last
`ACTIVE_H` hours, its a-deck ``a{basin}{nn}{year}.dat.gz`` from
``atcf/aid_public/``. An a-deck carries every guidance model, several MB for
a long storm, and is cumulative; only NHC's own forecast is kept — the lines
whose technique column is ``OFCL`` — as fetched, in file order, nothing
reformatted. Storage: ``data/nhcforecasts/{YEAR}/a{basin}{nn}{YEAR}_ofcl.dat``,
rewritten only when its OFCL lines change; git's history keeps each revision.

The cone's radii are NOT here: they are a fixed table per season in NHC's
cone documentation, never typed in this repository. The briefing uses the
forecast track and names it as NHC's forecast.

**Unverified against a live file** when written: the host is denied from the
session that wrote it, so the parser is pinned to ATCF's published a-deck
layout by a fixture. The first Actions run is the check; its summary prints
how many OFCL lines each file held.

Exit 2 on a CONNECT denial, 1 on a failed file, 0 else (including no active
storm, the usual case).
"""

from __future__ import annotations

import argparse
import gzip
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .common import DEFAULT_DATA_DIR, utcnow, write_step_summary

AID = "https://ftp.nhc.noaa.gov/atcf/aid_public/"
TECH = "OFCL"
#: A storm is active when its b-deck's newest fix is this recent. NHC writes
#: a fix every six hours and stops when the storm is dead; three days keeps a
#: storm whose b-deck the collector has not refreshed for a while.
ACTIVE_H = 72
USER_AGENT = "nado-waves NHC forecast archive (+https://github.com/ptrrdrck/nado-waves)"


def _get(url: str, timeout: float = 60.0) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def official_lines(text: str) -> list[str]:
    """The a-deck's OFCL lines, as they are: the fifth comma column is the
    technique."""

    out = []
    for line in text.splitlines():
        cols = line.split(",")
        if len(cols) > 5 and cols[4].strip() == TECH:
            out.append(line.rstrip())
    return out


def newest_fix_utc(bdeck: str) -> datetime | None:
    newest = None
    for line in bdeck.splitlines():
        cols = [c.strip() for c in line.split(",")]
        if len(cols) > 4 and cols[4] == "BEST":
            try:
                t = datetime.strptime(cols[2], "%Y%m%d%H").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            newest = t if newest is None or t > newest else newest
    return newest


def active(data_dir: Path, year: int, now: datetime) -> list[str]:
    """The storms (``ep15``) whose archived b-deck is recent."""

    out = []
    for path in sorted((Path(data_dir) / "besttracks" / str(year)).glob("b*.dat")):
        newest = newest_fix_utc(path.read_text(encoding="utf-8"))
        if newest is not None and now - newest <= timedelta(hours=ACTIVE_H):
            out.append(path.stem[1:5])
    return out


def directory(data_dir: Path, year: int) -> Path:
    return Path(data_dir) / "nhcforecasts" / str(year)


def archive(data_dir: Path, year: int, now: datetime, fetch=_get) -> tuple[int, int, list[str], dict[str, int]]:
    """(files written, files unchanged, failures, OFCL lines per storm)."""

    out = directory(data_dir, year)
    written = unchanged = 0
    failed: list[str] = []
    counts: dict[str, int] = {}
    for storm in active(data_dir, year, now):
        name = f"a{storm}{year}.dat.gz"
        try:
            raw = fetch(AID + name)
        except urllib.error.HTTPError as exc:
            failed.append(f"{name}: HTTP {exc.code}")
            continue
        try:
            text = gzip.decompress(raw).decode("utf-8", "replace")
        except OSError as exc:
            failed.append(f"{name}: not gzip ({exc})")
            continue
        lines = official_lines(text)
        counts[storm] = len(lines)
        if not lines:
            continue
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"a{storm}{year}_ofcl.dat"
        body = "\n".join(lines) + "\n"
        if path.exists() and path.read_text(encoding="utf-8") == body:
            unchanged += 1
            continue
        path.write_text(body, encoding="utf-8")
        written += 1
    return written, unchanged, failed, counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--year", type=int, default=utcnow().year)
    args = parser.parse_args(argv)
    try:
        written, unchanged, failed, counts = archive(args.data_dir, args.year, utcnow())
    except urllib.error.URLError as exc:
        reason = str(getattr(exc, "reason", exc))
        print(f"NHC forecasts not reachable: {reason}")
        write_step_summary(f"**NHC forecasts not reachable:** {reason}")
        return 2 if "403" in reason or "Tunnel" in reason else 1
    held = ", ".join(f"{s} {n} OFCL lines" for s, n in counts.items()) or "no active storm"
    summary = (f"NHC official forecasts {args.year}: {written} written, {unchanged} unchanged; {held}"
               + (f"; {len(failed)} failed: {'; '.join(failed)}" if failed else ""))
    print(summary)
    write_step_summary(summary)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
