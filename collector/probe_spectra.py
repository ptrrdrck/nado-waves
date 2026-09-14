"""Are NDBC directional wave spectra reachable and usable for 46232?

    python -m collector.probe_spectra --station 46232

BRIEFING section 7 lists five files — `swden`, `swdir`, `swdir2`, `swr1`,
`swr2` — as verification candidate 4. They are not an observation at the beach,
so they do not unblock the verification series. What they do is convert the
transform from an assumption into an integral: instead of carrying one dominant
direction through the beach's aperture, you integrate measured energy per
frequency over the open window.

They were never confirmed reachable. The host was denied before it could be
tested, and an untested assumption about the input to the whole transform is
exactly the kind of thing this project keeps paying for.

BRIEFING section 8 is blunt about probes: four distinct faults produced
confident wrong answers in the predecessor — stale content behind HTTP 200,
substring matches against page furniture, a truncated read, and `"NOAA" in
"...not NOAA"`. So this probe:

- reads every response in full, and reports the byte count it actually read;
- sniffs FRESHNESS from the newest parsed timestamp, never from HTTP 200;
- prints the raw header and first data line verbatim next to the parse, the
  way `probe_raw.py` does, so a format surprise is visible rather than
  swallowed;
- returns typed flags, so a caller can tell "denied" from "absent" from
  "present but stale" instead of reading prose;
- distinguishes a proxy CONNECT denial from throttling from a real 404. A 403
  at CONNECT is a policy denial: the tunnel is refused before any HTTP request
  is sent, so it surfaces as a connection error and the host looks dead rather
  than forbidden. Backing off does not help. Report the host.

The last check is the one that matters: five files can all be present and still
not support a directional integral if their frequency bins disagree or the
directional moments are out of range. So the probe reconstructs D(f, theta) on
the newest record and integrates it over a real beach window. That is a
reachability demonstration, not a forecast, and it is labelled as one.
"""

from __future__ import annotations

import argparse
import gzip
import io
import math
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .common import utcnow, write_step_summary
from .ndbc import USER_AGENT
from .probe_mop import DENIAL_NOTE

REALTIME = "https://www.ndbc.noaa.gov/data/realtime2/{station}{suffix}"
HISTORICAL = "https://www.ndbc.noaa.gov/data/historical/{kind}/{station}{letter}{year}.txt.gz"

#: The five files, and what each contributes to D(f, theta).
#:
#: The reconstruction NDBC documents is
#:
#:     D(f, t) = (1/pi) * [0.5 + r1*cos(t - a1) + r2*cos(2*(t - a2))]
#:     E(f, t) = C11(f) * D(f, t)
#:
#: so all five are required and none is optional: C11 alone is a non-directional
#: spectrum and cannot be windowed, which is the entire point of wanting it.
SPECTRAL_FILES = {
    "swden": {"suffix": ".data_spec", "letter": "w", "role": "C11(f), energy density"},
    "swdir": {"suffix": ".swdir", "letter": "d", "role": "alpha1, mean direction"},
    "swdir2": {"suffix": ".swdir2", "letter": "i", "role": "alpha2, principal direction"},
    "swr1": {"suffix": ".swr1", "letter": "j", "role": "r1, first moment"},
    "swr2": {"suffix": ".swr2", "letter": "k", "role": "r2, second moment"},
}

#: Older than this and the file is present but not usable as a live input.
STALE_HOURS = 12.0


@dataclass
class FileProbe:
    """One file's verdict, as flags rather than prose."""

    kind: str
    url: str
    reachable: bool = False
    denied: bool = False
    throttled: bool = False
    absent: bool = False
    parsed: bool = False
    bytes_read: int = 0
    rows: int = 0
    frequencies: list[float] = field(default_factory=list)
    newest: datetime | None = None
    value_range: tuple[float, float] | None = None
    header_line: str = ""
    first_data_line: str = ""
    error: str = ""
    #: Kept from the single fetch so the demonstration integral does not pull
    #: all five files down again. BRIEFING section 8: re-reading inside a loop
    #: turned a 12-second job into minutes, in two separate modules.
    newest_row: list[float] = field(default_factory=list)

    @property
    def age_hours(self) -> float | None:
        if self.newest is None:
            return None
        return (utcnow() - self.newest).total_seconds() / 3600.0

    @property
    def stale(self) -> bool:
        age = self.age_hours
        return age is not None and age > STALE_HOURS

    @property
    def usable(self) -> bool:
        return self.reachable and self.parsed and self.rows > 0


def fetch(url: str, *, timeout: float = 45.0) -> bytes:
    """Fetch one file in full. Raises; the caller classifies the failure.

    Deliberately does NOT retry. If this is a policy denial, retrying burns
    time and teaches nothing, and BRIEFING section 8 records what it cost to
    diagnose a denial as rate-limiting.
    """

    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read()
        if response.headers.get("Content-Encoding") == "gzip" or url.endswith(".gz"):
            payload = gzip.GzipFile(fileobj=io.BytesIO(payload)).read()
    return payload


def parse_spectral(text: str) -> tuple[list[float], list[tuple[datetime, list[float]]], str, str]:
    """Parse an NDBC spectral file into frequencies and timestamped rows.

    Two layouts exist and the probe must not assume which it got. The real-time
    files interleave `value (frequency)` pairs on every data row; the historical
    files carry the frequencies once, in the header. Getting this wrong would
    produce a confident parse of nonsense, which is failure mode number one in
    BRIEFING section 8 — so the layout is DETECTED, and the raw lines are
    returned for printing beside the result.
    """

    lines = [ln for ln in text.splitlines() if ln.strip()]
    headers = [ln for ln in lines if ln.startswith("#")]
    data = [ln for ln in lines if not ln.startswith("#")]
    header_line = headers[0] if headers else ""
    first_data = data[0] if data else ""

    if not data:
        return [], [], header_line, first_data

    inline = "(" in first_data
    frequencies: list[float] = []

    if not inline:
        # Frequencies live in the header, after the five date columns.
        tokens = header_line.lstrip("#").split()
        for token in tokens[5:]:
            try:
                frequencies.append(float(token))
            except ValueError:
                continue

    rows: list[tuple[datetime, list[float]]] = []
    for line in data:
        parts = line.split()
        if len(parts) < 6:
            continue
        try:
            stamp = datetime(
                int(parts[0]), int(parts[1]), int(parts[2]),
                int(parts[3]), int(parts[4]), tzinfo=timezone.utc,
            )
        except ValueError:
            continue

        values: list[float] = []
        if inline:
            row_freqs: list[float] = []
            rest = parts[5:]
            # `value (freq) value (freq) ...`, occasionally with a leading
            # separation-frequency column that has no parenthesised partner.
            index = 0
            while index + 1 < len(rest):
                token, following = rest[index], rest[index + 1]
                if following.startswith("("):
                    try:
                        values.append(float(token))
                        row_freqs.append(float(following.strip("()")))
                    except ValueError:
                        pass
                    index += 2
                else:
                    index += 1
            if row_freqs and not frequencies:
                frequencies = row_freqs
        else:
            for token in parts[5:]:
                try:
                    values.append(float(token))
                except ValueError:
                    values.append(float("nan"))

        if values:
            rows.append((stamp, values))

    rows.sort(key=lambda r: r[0])
    return frequencies, rows, header_line, first_data


def probe_file(kind: str, url: str, *, timeout: float = 45.0) -> FileProbe:
    result = FileProbe(kind=kind, url=url)
    try:
        payload = fetch(url, timeout=timeout)
    except urllib.error.HTTPError as exc:
        result.error = f"HTTP {exc.code} {exc.reason}"
        if exc.code == 404:
            result.absent = True
        elif exc.code in (429, 503):
            result.throttled = True
        elif exc.code == 403:
            result.denied = True
        return result
    except urllib.error.URLError as exc:
        # The tunnel was refused before any request was sent. See DENIAL_NOTE.
        result.error = f"{exc.__class__.__name__}: {exc}"
        result.denied = True
        return result
    except Exception as exc:  # noqa: BLE001 - network layer
        result.error = f"{exc.__class__.__name__}: {exc}"
        return result

    result.reachable = True
    result.bytes_read = len(payload)
    text = payload.decode("utf-8", errors="replace")
    frequencies, rows, header_line, first_data = parse_spectral(text)
    result.header_line = header_line
    result.first_data_line = first_data
    result.frequencies = frequencies
    result.rows = len(rows)
    result.parsed = bool(rows and frequencies)
    if rows:
        result.newest = rows[-1][0]
        result.newest_row = rows[-1][1]
        finite = [v for v in rows[-1][1] if not math.isnan(v)]
        if finite:
            result.value_range = (min(finite), max(finite))
    return result


def directional_spread(r1: float, a1: float, r2: float, a2: float, theta: float) -> float:
    """D(f, theta), the NDBC directional distribution, in units of 1/radian.

    `theta`, `a1` and `a2` are degrees. The caller is responsible for having
    them in the same convention — which for NDBC is degrees FROM which the
    waves come, matching `MWD` and NOT the GFS-Wave bulletin convention that
    `collector.gfswave` flips on the way in. CLAUDE.md measured that confusion
    at 29 degrees of error with the flip and 151 without; it is worth restating
    at every boundary.
    """

    t = math.radians(theta)
    return (1.0 / math.pi) * (
        0.5
        + r1 * math.cos(t - math.radians(a1))
        + r2 * math.cos(2.0 * (t - math.radians(a2)))
    )


def window_fraction(
    c11: list[float],
    a1: list[float],
    a2: list[float],
    r1: list[float],
    r2: list[float],
    frequencies: list[float],
    window: tuple[float, float],
    *,
    step: float = 1.0,
) -> tuple[float, float]:
    """Energy inside an angular window, and the fraction of the total it is.

    This is the demonstration that the five files support a directional
    integral at all — the thing the transform will eventually be built on. It
    is NOT the transform: no shoaling, no refraction, no propagation, and it
    reports the buoy's own spectrum resolved into a sector rather than anything
    that has arrived anywhere.
    """

    low, high = window
    span = (high - low) % 360.0
    total = 0.0
    inside = 0.0
    for index, freq in enumerate(frequencies):
        if index >= min(len(c11), len(a1), len(a2), len(r1), len(r2)):
            break
        density = c11[index]
        if math.isnan(density) or density <= 0.0:
            continue
        width = _bin_width(frequencies, index)
        steps = max(int(span / step), 1)
        for n in range(steps):
            theta = (low + (n + 0.5) * span / steps) % 360.0
            energy = density * directional_spread(r1[index], a1[index], r2[index], a2[index], theta)
            inside += energy * math.radians(span / steps) * width
        for n in range(int(360.0 / step)):
            theta = (n + 0.5) * step
            energy = density * directional_spread(r1[index], a1[index], r2[index], a2[index], theta)
            total += energy * math.radians(step) * width
    return inside, (inside / total if total > 0 else float("nan"))


def _bin_width(frequencies: list[float], index: int) -> float:
    if len(frequencies) < 2:
        return 1.0
    if index == 0:
        return frequencies[1] - frequencies[0]
    if index == len(frequencies) - 1:
        return frequencies[-1] - frequencies[-2]
    return (frequencies[index + 1] - frequencies[index - 1]) / 2.0


def report(
    station: str,
    probes: dict[str, FileProbe],
    *,
    demo: str = "",
) -> list[str]:
    """A verdict a reader can act on, with the raw bytes beside the parse."""

    denied = [p for p in probes.values() if p.denied]
    absent = [p for p in probes.values() if p.absent]
    usable = [p for p in probes.values() if p.usable]
    stale = [p for p in usable if p.stale]

    lines = [f"## NDBC directional spectra — {station}", ""]

    if denied:
        hosts = sorted({p.url.split("/")[2] for p in denied})
        lines += [
            f"**BLOCKED: {len(denied)} of {len(probes)} files denied at CONNECT.**",
            "",
            f"Host: `{', '.join(hosts)}`",
            "",
            DENIAL_NOTE.strip(),
            "",
            "This says nothing about whether the files exist. It says this",
            "runner cannot see them. The scheduled collector runs on GitHub",
            "Actions and is unaffected by session egress policy — run this",
            "probe there before concluding anything about NDBC.",
            "",
        ]
    elif len(usable) == len(SPECTRAL_FILES):
        lines += [f"**All {len(SPECTRAL_FILES)} files reachable and parsed.**", ""]
    else:
        missing = sorted(set(SPECTRAL_FILES) - {p.kind for p in usable})
        lines += [
            f"**Incomplete: {len(usable)} of {len(SPECTRAL_FILES)} usable.**",
            "",
            f"Missing or unparsed: {', '.join(missing)}.",
            "",
            "All five are required. C11 on its own is a non-directional",
            "spectrum and cannot be windowed, which is the whole reason for",
            "wanting it.",
            "",
        ]

    if absent:
        lines += [
            f"{len(absent)} returned 404. For a CDIP-operated buoy like 46232 that",
            "is a real possibility rather than an error: not every station NDBC",
            "redistributes carries the full directional set.",
            "",
        ]
    if stale:
        lines += [
            f"{len(stale)} file(s) parsed but are older than {STALE_HOURS:.0f} h. "
            "Present is not the same as live.",
            "",
        ]

    lines += [
        "| file | role | HTTP | bytes | rows | bins | newest | age | value range |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for kind, spec in SPECTRAL_FILES.items():
        p = probes[kind]
        status = "ok" if p.reachable else (p.error or "failed")
        age = f"{p.age_hours:.1f} h" if p.age_hours is not None else "—"
        newest = p.newest.strftime("%Y-%m-%d %H:%M") if p.newest else "—"
        rng = f"{p.value_range[0]:.3g} … {p.value_range[1]:.3g}" if p.value_range else "—"
        lines.append(
            f"| `{kind}` | {spec['role']} | {status} | {p.bytes_read} | {p.rows} "
            f"| {len(p.frequencies)} | {newest} | {age} | {rng} |"
        )
    lines.append("")

    # Frequency bins must agree across all five or the reconstruction is
    # combining different frequencies at the same index — a silent, confident
    # wrong answer of exactly the kind BRIEFING section 8 warns about.
    binsets = {tuple(p.frequencies) for p in usable if p.frequencies}
    if len(binsets) > 1:
        lines += [
            "**Frequency bins DISAGREE across the five files.** The",
            "reconstruction indexes all five by bin, so this must be resolved",
            "before any integral is trusted.",
            "",
        ]
    elif binsets:
        bins = next(iter(binsets))
        lines += [
            f"Frequency bins agree across all parsed files: {len(bins)} bins, "
            f"{bins[0]:.4f}–{bins[-1]:.4f} Hz "
            f"({1 / bins[-1]:.1f}–{1 / bins[0]:.1f} s).",
            "",
        ]

    # r1 and r2 are published scaled by 100 in some NDBC products and not in
    # others. Report the observed range rather than silently rescaling: a
    # wrong guess here does not fail, it just produces a wrong directional
    # distribution.
    for kind in ("swr1", "swr2"):
        p = probes.get(kind)
        if p and p.value_range:
            top = p.value_range[1]
            convention = (
                "looks like percent (scale by 1/100 before use)"
                if top > 1.5
                else "looks already normalised to [0, 1]"
            )
            lines.append(f"`{kind}` peaks at {top:.3g} — {convention}.")
    lines.append("")

    for kind, p in probes.items():
        if p.header_line or p.first_data_line:
            lines += [
                f"<details><summary>Raw <code>{kind}</code> — source bytes beside the parse</summary>",
                "",
                "```",
                p.header_line[:400],
                p.first_data_line[:400],
                "```",
                f"parsed as {len(p.frequencies)} bins, {p.rows} rows",
                "",
                "</details>",
                "",
            ]

    if demo:
        lines += [demo, ""]

    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe NDBC directional spectra.")
    parser.add_argument("--station", default="46232")
    parser.add_argument(
        "--historical",
        type=int,
        default=None,
        metavar="YEAR",
        help="Probe the historical archive for this year instead of the live feed.",
    )
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument(
        "--window",
        default="201,250",
        help="Demonstration window, 'low,high' in degrees FROM. Default is "
        "Coronado's centre break.",
    )
    args = parser.parse_args(argv)

    station = args.station.upper()
    probes: dict[str, FileProbe] = {}
    for kind, spec in SPECTRAL_FILES.items():
        if args.historical:
            url = HISTORICAL.format(
                kind=kind, station=station.lower(), letter=spec["letter"], year=args.historical
            )
        else:
            url = REALTIME.format(station=station, suffix=spec["suffix"])
        probes[kind] = probe_file(kind, url, timeout=args.timeout)

    demo = ""
    usable = {k: p for k, p in probes.items() if p.usable}
    if len(usable) == len(SPECTRAL_FILES):
        try:
            low, high = (float(x) for x in args.window.split(","))
            demo = _demonstrate(station, probes, (low, high), args.historical)
        except Exception as exc:  # noqa: BLE001 - a failed demo must not fail the probe
            demo = f"Directional integral demonstration failed: {exc.__class__.__name__}: {exc}"

    lines = report(station, probes, demo=demo)
    text = "\n".join(lines)
    print(text)
    write_step_summary(text)

    if any(p.denied for p in probes.values()):
        return 2
    return 0 if len(usable) == len(SPECTRAL_FILES) else 1


def _demonstrate(
    station: str,
    probes: dict[str, FileProbe],
    window: tuple[float, float],
    historical: int | None,
) -> str:
    """Integrate the newest record over a window, as proof the chain works."""

    stamps = {kind: probes[kind].newest for kind in SPECTRAL_FILES}
    values = {kind: probes[kind].newest_row for kind in SPECTRAL_FILES}

    if len({s for s in stamps.values()}) != 1:
        return (
            "### Directional integral — NOT ATTEMPTED\n\n"
            "The five newest records carry different timestamps "
            f"({', '.join(sorted({s.strftime('%Y-%m-%d %H:%M') for s in stamps.values()}))}), "
            "so combining them by index would mix observation times. "
            "A real transform must align on timestamp first."
        )

    freqs = probes["swden"].frequencies
    scale1 = 100.0 if (probes["swr1"].value_range or (0, 0))[1] > 1.5 else 1.0
    scale2 = 100.0 if (probes["swr2"].value_range or (0, 0))[1] > 1.5 else 1.0
    r1 = [v / scale1 for v in values["swr1"]]
    r2 = [v / scale2 for v in values["swr2"]]

    inside, fraction = window_fraction(
        values["swden"], values["swdir"], values["swdir2"], r1, r2, freqs, window
    )
    stamp = next(iter(stamps.values()))
    return "\n".join([
        "### Directional integral — demonstration only",
        "",
        f"Newest aligned record: **{stamp:%Y-%m-%d %H:%M} UTC**, "
        f"window **{window[0]:.0f}–{window[1]:.0f}° FROM**.",
        "",
        f"- energy inside the window: **{fraction * 100:.1f}%** of the buoy's total",
        f"- r1 scaled by 1/{scale1:.0f}, r2 by 1/{scale2:.0f} (from the observed ranges above)",
        "",
        "**This is not a forecast and not a beach height.** It is the buoy's own",
        "spectrum resolved into a sector, computed to prove the five files",
        "support a directional integral. No propagation, no shoaling, no",
        "refraction, and nothing has arrived anywhere. Nothing measures waves at",
        "Coronado; that has not changed.",
    ])


if __name__ == "__main__":
    sys.exit(main())
