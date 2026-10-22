"""Which way a swell arrives in 5 m of water, by the heading it left deep water on.

    python -m forecast.bending            # the table, as text
    python -m forecast.bending --write    # ... into app/docs.html

The owner's request (2026-10-22): help people see how swell directions
translate inwards. Each break's transfer table (`forecast.raytrace` →
`data/nearshore/<break>.csv`) already says, ray by ray, which offshore heading
reaches the 5 m start point and from which heading it arrives there. This
reads it the way `nearshore.carry` does, for one narrow swell at a time:
a swell spread `SPREAD_DEG` (one standard deviation) about each offshore
heading, at one period, its energy taken ray by ray through the diffracting
edges and bottom friction, and the arriving energy's mean heading. A break
card's train gets its own 5 m heading the same way, from the real spectrum
(`nearshore._arrive`), and a test holds the two to each other.

Where less than `MIN_REACH` of a heading's energy reaches 5 m (shoaling
divided out, as `hs_equivalent` divides it), the table gives no heading: what
arrives is a sliver, and its direction says nothing a reader can use.

Physics on surveyed inputs, fitted to nothing and observed by nothing. Reports,
never edits the chain. Pure Python.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

from .geometry import load
from .nearshore import BREAKS, TABLE_DIR, Table, at, shoaling_squared

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "app" / "docs.html"

#: The offshore headings the docs table lists, FROM, every 10°: the arc any
#: break's windows open on, with a little either side.
HEADINGS = tuple(range(180, 330, 10))

#: The table's period, as the transfer tables hold it (0.07 Hz, 14.3 s); and
#: the two the docs compare it with, for how much the period moves a heading.
PERIOD_HZ = 0.07
COMPARE_HZ = (0.10, 0.055)

#: A narrow swell's spread about its heading, degrees (one standard deviation).
SPREAD_DEG = 10.0

#: Below this share of a heading's energy at 5 m (shoaling divided out), no
#: heading is given.
MIN_REACH = 0.10

BEGIN = "<!-- bending:begin -->"
END = "<!-- bending:end -->"


def swell_grid(from_deg: float, spread_deg: float = SPREAD_DEG) -> list[float]:
    """One narrow swell's direction distribution on carry's 1° grid, per
    radian, integrating to one."""

    raw = [math.exp(-0.5 * (((n + 0.5 - from_deg + 180.0) % 360.0 - 180.0) / spread_deg) ** 2)
           for n in range(360)]
    total = sum(raw) * math.radians(1.0)
    return [v / total for v in raw]


def arriving(table: Table, freq_hz: float, from_deg: float,
             spread_deg: float = SPREAD_DEG) -> tuple[float, float]:
    """(heading FROM at the start depth, share of the swell's energy that
    reaches it with shoaling divided out) for a swell from `from_deg` at the
    table frequency nearest `freq_hz`. The heading is NaN when nothing does.

    Ray by ray as `nearshore.carry` takes energy: density at the ray's
    diffracting offshore heading, times its width and diffracting gain,
    times bottom friction."""

    near = min(table.by_freq, key=lambda f: abs(f - freq_hz))
    grid = swell_grid(from_deg, spread_deg)
    ks2 = shoaling_squared(near, table.start_depth_m)
    e = s = c = 0.0
    for ray in table.by_freq[near]:
        if ray.diff_gain <= 0:
            continue
        got = at(grid, ray.diff_off_from) * ray.width_rad * ray.diff_gain * ray.diff_friction
        t = math.radians(ray.near_from)
        e += got; s += got * math.sin(t); c += got * math.cos(t)
    heading = math.degrees(math.atan2(s, c)) % 360.0 if e > 0 else math.nan
    return heading, e / ks2


def crossing_share(table: Table, freq_hz: float = PERIOD_HZ) -> float:
    """Of neighbouring rays (0.5° apart at 5 m) that both clear every edge,
    the share whose offshore headings come in the opposite order: rays that
    cross on the way in. A one-to-one bending gives 0; a shuffle about a half.
    Measured with the seabed blurred ±150 m it barely moves, so it is the
    shelf's own features, not the survey grid's noise (BRIEFING §45)."""

    near = min(table.by_freq, key=lambda f: abs(f - freq_hz))
    rays = sorted((r for r in table.by_freq[near] if r.gain > 0), key=lambda r: r.near_from)
    pairs = [(a, b) for a, b in zip(rays, rays[1:]) if abs(b.near_from - a.near_from - 0.5) < 0.01]
    crossed = sum(1 for a, b in pairs if (b.off_from - a.off_from + 180.0) % 360.0 - 180.0 < 0)
    return crossed / len(pairs) if pairs else math.nan


def table(directory: Path = TABLE_DIR) -> dict:
    """Every break's 5 m heading for each of `HEADINGS` at `PERIOD_HZ`, None
    where too little arrives; and at `COMPARE_HZ` too, for the period note."""

    spots = {s.id: s for s in load()[0]}
    out = {"period_s": round(1.0 / PERIOD_HZ, 1), "headings": list(HEADINGS),
           "spread_deg": SPREAD_DEG, "min_reach": MIN_REACH, "breaks": []}
    moved = []
    for break_id in BREAKS:
        t = Table.load(break_id, directory)
        cells = []
        for h in HEADINGS:
            deg, reach = arriving(t, PERIOD_HZ, h)
            shown = reach >= MIN_REACH and deg == deg
            cells.append(round(deg) % 360 if shown else None)
            if shown:
                others = [arriving(t, f, h) for f in COMPARE_HZ]
                if all(r >= MIN_REACH and d == d for d, r in others):
                    moved.append(max(abs((d - deg + 180.0) % 360.0 - 180.0) for d, _ in others))
        out["breaks"].append({"id": break_id, "normal_deg": round(spots[break_id].normal) % 360,
                              "cells": cells})
    moved.sort()
    out["compare_s"] = [round(1.0 / f, 1) for f in COMPARE_HZ]
    out["period_moves_deg"] = {"median": round(moved[len(moved) // 2]), "max": round(moved[-1]),
                               "n": len(moved)} if moved else None
    return out


POINTS = ("N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
          "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW")


def _point(deg: float) -> str:
    return POINTS[round(deg / 22.5) % 16]


def render(data: dict) -> str:
    """The docs block: a table of headings and the period sentence under it."""

    names = [b["id"].replace("coronado_", "").capitalize() for b in data["breaks"]]
    head = "".join(f"<th>{n}</th>" for n in names)
    rows = ['<tr><th scope="row">Shore normal</th>'
            + "".join(f'<td class="num">{b["normal_deg"]}&deg;</td>' for b in data["breaks"]) + "</tr>"]
    for k, h in enumerate(data["headings"]):
        cells = "".join(
            f'<td class="num">{c}&deg;</td>' if c is not None else '<td class="num">&mdash;</td>'
            for c in (b["cells"][k] for b in data["breaks"]))
        rows.append(f'<tr><th scope="row">{_point(h)} {h}&deg;</th>{cells}</tr>')
    moves = data["period_moves_deg"]
    lo, hi = data["compare_s"][0], data["compare_s"][1]
    note = (f"At {lo:g} s and {hi:g} s instead of {data['period_s']:g} s, the heading in 5 m moves "
            f"by {moves['median']}&deg; at the median and {moves['max']}&deg; at most, over the "
            f"{moves['n']} cells all three periods give.") if moves else ""
    return "\n".join([
        BEGIN,
        '      <div class="tablebox"><table id="bendtable">',
        f"        <thead><tr><th>From, offshore</th>{head}</tr></thead>",
        "        <tbody>",
        *(f"          {r}" for r in rows),
        "        </tbody></table></div>",
        f'      <p class="foot">{note}</p>',
        f"      {END}",
    ])


def write(page: Path = DOCS, data: dict | None = None) -> bool:
    """Replace the block between the markers in `page`; True if it changed."""

    text = page.read_text(encoding="utf-8")
    if BEGIN not in text or END not in text:
        raise ValueError(f"{page} has no {BEGIN} ... {END} block")
    block = render(data or table())
    new = re.sub(re.escape(BEGIN) + ".*?" + re.escape(END), lambda _: block, text, count=1, flags=re.S)
    if new != text:
        page.write_text(new, encoding="utf-8")
    return new != text


def format_text(data: dict) -> str:
    names = [b["id"].replace("coronado_", "") for b in data["breaks"]]
    lines = [f"Heading in 5 m of water, {data['period_s']:g} s, a swell spread "
             f"±{data['spread_deg']:g}° about each offshore heading; '-' where under "
             f"{data['min_reach']:.0%} of it arrives.",
             "offshore  " + "  ".join(f"{n:>7}" for n in names),
             "normal    " + "  ".join(f"{b['normal_deg']:>6}°" for b in data["breaks"])]
    for k, h in enumerate(data["headings"]):
        lines.append(f"{h:>6}°   " + "  ".join(
            f"{b['cells'][k]:>6}°" if b["cells"][k] is not None else f"{'-':>7}" for b in data["breaks"]))
    if data["period_moves_deg"]:
        m = data["period_moves_deg"]
        lines.append(f"\nAt {data['compare_s'][0]:g} and {data['compare_s'][1]:g} s: moves "
                     f"{m['median']}° median, {m['max']}° at most, over {m['n']} cells.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="fill the block in app/docs.html")
    args = parser.parse_args(argv)
    data = table()
    print(format_text(data))
    if args.write:
        print(f"\n{'updated' if write(DOCS, data) else 'unchanged'}: {DOCS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
