"""Archive NHC's best tracks (ATCF b-decks), eastern and central Pacific.

Run: ``python -m collector.besttracks`` — on Actions (origin-tracks.yml);
ftp.nhc.noaa.gov is denied at CONNECT from a Claude session (2026-10-02).

Why archive what NHC keeps: during the season a b-deck is the WORKING best
track, rewritten every six hours, and after it the storm is reanalysed and
the file revised. A check run against "the best track" is only reproducible
against the file it actually read, so each file is stored as fetched, raw,
and git's history keeps every revision.

Storage: ``data/besttracks/{YEAR}/b{basin}{nn}{YEAR}.dat``, byte for byte.
Nothing is parsed or filtered here: invests and pre-genesis disturbances are
kept, and the reader (`forecast.origintracks.parse_bdeck`) decides what counts.

Exit 2 on a CONNECT denial, 1 on an empty listing or a failed file, 0 else.
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

from .common import DEFAULT_DATA_DIR, utcnow, write_step_summary

BTK = "https://ftp.nhc.noaa.gov/atcf/btk/"
#: Eastern and central Pacific: everything a ~3,000 km origin south and west
#: of 46232 could be. The western Pacific is JTWC's and 8,000 km off.
BASINS = ("ep", "cp")
USER_AGENT = "nado-waves best-track archive (+https://github.com/ptrrdrck/nado-waves)"


def _get(url: str, timeout: float = 60.0) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", "replace")


def listed(listing: str, year: int) -> list[str]:
    """The b-deck file names in a directory listing, for these basins and year."""

    pattern = rf'href="(b(?:{"|".join(BASINS)})\d{{2}}{year}\.dat)"'
    return sorted(set(re.findall(pattern, listing)))


def directory(data_dir: Path, year: int) -> Path:
    return Path(data_dir) / "besttracks" / str(year)


def archive(data_dir: Path, year: int, fetch=_get) -> tuple[int, int, list[str]]:
    """(files written, files unchanged, failures)."""

    names = listed(fetch(BTK), year)
    out = directory(data_dir, year)
    out.mkdir(parents=True, exist_ok=True)
    written = unchanged = 0
    failed: list[str] = []
    for name in names:
        try:
            text = fetch(BTK + name)
        except urllib.error.URLError as exc:
            failed.append(f"{name}: {exc}")
            continue
        path = out / name
        if path.exists() and path.read_text(encoding="utf-8") == text:
            unchanged += 1
            continue
        path.write_text(text, encoding="utf-8")
        written += 1
    if not names:
        failed.append(f"no {year} b-decks for {', '.join(BASINS)} listed at {BTK}")
    return written, unchanged, failed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--year", type=int, default=utcnow().year)
    args = parser.parse_args(argv)
    try:
        written, unchanged, failed = archive(args.data_dir, args.year)
    except urllib.error.URLError as exc:
        reason = str(getattr(exc, "reason", exc))
        print(f"best tracks not reachable: {reason}")
        write_step_summary(f"**Best tracks not reachable:** {reason}")
        return 2 if "403" in reason or "Tunnel" in reason else 1
    summary = (f"NHC b-decks {args.year}: {written} written, {unchanged} unchanged"
               + (f", {len(failed)} failed: {'; '.join(failed)}" if failed else ""))
    print(summary)
    write_step_summary(summary)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
