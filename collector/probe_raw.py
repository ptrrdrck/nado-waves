"""Dump a raw NDBC file next to how we parse it.

    python -m collector.probe_raw --station 46001 --year 2024

Exists because of a specific confusion: after backfilling six North Pacific
sentinel buoys, every one came back with full wind and temperature and
essentially no wave height — while the nearshore CDIP buoys have full wave
height and no wind. "Stations with wind have no waves, stations with waves have
no wind" is the shape of a column-alignment bug, not of an ocean.

It might still be real: a deep-ocean buoy can lose its wave payload while its
anemometer keeps reporting. The only way to know is to put the source bytes and
our interpretation side by side, which is what this does.
"""

from __future__ import annotations

import argparse
import gzip
import io
import sys
import urllib.request

from .common import write_step_summary
from .ndbc import USER_AGENT, is_missing, parse_realtime2

URL = "https://www.ndbc.noaa.gov/data/historical/stdmet/{station}h{year}.txt.gz"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dump a raw NDBC file and our parse.")
    parser.add_argument("--station", default="46001")
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--rows", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args(argv)

    url = URL.format(station=args.station.lower(), year=args.year)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=args.timeout) as response:
        raw = gzip.GzipFile(fileobj=io.BytesIO(response.read())).read()
    text = raw.decode("utf-8", errors="replace")

    lines = [ln for ln in text.splitlines() if ln.strip()]
    headers = [ln for ln in lines if ln.startswith("#")]
    data = [ln for ln in lines if not ln.startswith("#")]

    out = [
        f"## Raw dump — {args.station} {args.year}",
        "",
        f"`{url}`  ",
        f"{len(data)} data rows",
        "",
        "### Header lines",
        "```",
        *headers[:3],
        "```",
        "",
        "### Sample rows, evenly spaced through the year",
        "```",
    ]
    step = max(1, len(data) // (args.rows + 1))
    samples = [data[i * step] for i in range(1, args.rows + 1) if i * step < len(data)]
    out += samples
    out += ["```", "", "### How we parse them", ""]

    columns = headers[0].lstrip("#").split() if headers else []
    out.append("Header columns: `" + " ".join(columns) + "`")
    out.append("")
    for sample in samples[:2]:
        parsed = parse_realtime2("\n".join(headers[:2] + [sample]))
        if not parsed:
            out.append(f"- `{sample[:60]}...` -> **parsed to nothing**")
            continue
        obs = parsed[0]
        shown = {k: v for k, v in obs.values.items() if v}
        blanked = [k for k, v in obs.values.items() if not v]
        out.append(f"- `{obs.timestamp_utc}` kept: `{shown}`")
        out.append(f"  blanked: `{', '.join(blanked)}`")
    out.append("")

    # The decisive question: what literal token sits in the WVHT column?
    if columns and "WVHT" in columns:
        index = columns.index("WVHT")
        tokens = [row.split()[index] for row in samples if len(row.split()) > index]
        out += [
            "### The WVHT column, literally",
            "",
            f"WVHT is column {index}. Raw tokens in the samples above: "
            f"`{', '.join(tokens)}`",
            "",
        ]
        verdict = [
            f"`{t}` -> " + ("MISSING" if is_missing("wvht", t) else "a real value")
            for t in tokens
        ]
        out.append("Our reading: " + "; ".join(verdict))
        out.append("")
        if all(is_missing("wvht", t) for t in tokens):
            out.append(
                "**The source really does say missing in these samples.** If "
                "that holds across the file, this buoy is not reporting wave "
                "height in the standard meteorological file and the gap is not "
                "ours."
            )
        else:
            out.append(
                "**The source carries real wave heights and we parse them "
                "correctly.** If the archive is missing them, the fault is "
                "downstream of parsing — check the downsampling, which sees "
                "every sub-hourly record and keeps only some."
            )
        out.append("")
        out.append(
            "Minutes in the samples: `"
            + ", ".join(row.split()[4] for row in samples if len(row.split()) > 4)
            + "`. A buoy that reports meteorology every 10 minutes but waves "
            "once an hour will lose all its waves to any rule that keeps a "
            "fixed sub-hourly record."
        )
    else:
        out.append("**No WVHT column in the header at all** — this file does not "
                   "carry wave height for this station.")

    report = "\n".join(out)
    print(report)
    write_step_summary(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
