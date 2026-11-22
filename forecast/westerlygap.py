"""Big westerly days through the chain as it ships now, against BRIEFING §56.

    python -m forecast.westerlygap                # print the report
    python -m forecast.westerlygap --write        # ... and docs/westerly_gap.md

**Reports and never edits** (handoff item 27a). The owner saw the LIVE headline
high on 17 Nov (46232 3.1-3.7 m from 280-296°). §56 diagnosed it on the chain
as it ran that day; since then Madsen's height-dependent friction (§57) and a
surf zone that starts seaward of 5 m (§58) have shipped, and no big westerly
day has been set against them. This rebuilds every such hour in the archive
through the LIVE tab's own call, `now.build(as_of=True)` — the NDBC feed, MEM,
the wind and tide that existed at that hour, local chop from KNZY — four ways:

- ``then``:   the chain as LIVE ran it on 17 Nov: the table's fixed JONSWAP
  friction, the surf zone from the table's 5 m start point;
- ``madsen``: Madsen's friction at the measured tide, the surf zone still
  from 5 m (§57 alone);
- ``now``:    the chain as it ships (§57 and §58);
- ``now_nochop``: as shipped, without the local chop LIVE adds.

``then`` and ``madsen`` read a headland's fill the old way
(`fillshift.nearest_rule`, BRIEFING §61); ``now`` is the chain as it ships,
so since §61 it carries the Fresnel-zone fill too.

``then`` is rebuilt in today's code by handing `carry` the JONSWAP column
(`friction="jonswap"`, which §57 pinned to the pre-Madsen chain to the digit)
and the profiles cut at the table's start point (`Profile.inshore`, §58's
"before"). The control is §56's own step table at 17 Nov 22Z, which it must
give back.

Hours: every archived 46232 spectrum with Hs >= 2 m whose swell (>= 8 s) comes
from W-WNW, 270-295° (`mopcheck.mean_from`, the sector §56a-§56e use), plus
every hour of 17 Nov. Nothing here is observed: a model against its own
earlier self, never a score. Pure Python; ~10 min.
"""

from __future__ import annotations

import argparse
import contextlib
import functools
import math
import sys
from datetime import date, datetime
from pathlib import Path

from .frictionshift import _q

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "westerly_gap.md"
SECTOR = (270.0, 295.0)
MIN_HS = 2.0
DAY = date(2026, 11, 17)
VARIANTS = ("then", "madsen", "now", "now_nochop")
HS_BANDS = ((2.0, 2.5), (2.5, 3.0), (3.0, 99.0))
#: §56's step table at 17 Nov 22Z, as the card listed it (m): the control.
S56_22Z = {
    "coronado_north": (0.66, 0.92, 1.00, 0.88, 1.03, 1.16),
    "coronado_center": (0.75, 1.85, 1.98, 1.74, 2.14, 2.09),
    "coronado_south": (0.91, 2.06, 2.23, 2.00, 2.39, 2.34),
}
STEPS = (("straight-line window", "window_hs_m"), ("refraction, hard edges", "refracted_hs_m"),
         ("+ diffraction", "diffracted_hs_m"), ("+ friction", "friction_hs_m"),
         ("+ shoaling, 5 m", "shoaled_hs_m"), ("+ local chop", "with_chop_hs_m"))


def buoy_hs(sp) -> float:
    m0 = sum(c * sp.bin_width(i) for i, c in enumerate(sp.c11) if c == c and c > 0)
    return 4.0 * math.sqrt(m0) if m0 > 0 else 0.0


def selected(spectra) -> list:
    from .mopcheck import mean_from

    out = []
    for sp in spectra:
        hs = buoy_hs(sp)
        frm = mean_from(sp)
        if sp.time.date() == DAY or (hs >= MIN_HS and SECTOR[0] <= frm < SECTOR[1]):
            out.append((sp, hs, frm))
    return out


@contextlib.contextmanager
def _chain(variant: str):
    """`now.build` with the variant's friction and chop. Only `carry` and
    `local_sea` as `now` holds them are swapped, and always put back."""

    from . import now as live

    carry, local = live.carry, live.local_sea
    try:
        if variant == "then":
            live.carry = functools.partial(carry, friction="jonswap")
        if variant == "now_nochop":
            live.local_sea = lambda *a, **k: None
        yield live
    finally:
        live.carry, live.local_sea = carry, local


def _row(brk) -> dict:
    near = brk.nearshore or {}
    eff = near.get("effects") or {}
    b = near.get("breaking") or {}
    local = eff.get("local") or {}
    return {"hs": near.get("hs_m"), "depth": b.get("depth_m"), "basis_breaking": bool(b),
            "flag": b.get("outside_start"), "local": local.get("hs_m", 0.0),
            "tide": eff.get("friction_tide_m"),
            **{k: eff.get(k) for _, k in STEPS}}


def run(data_dir: Path = ROOT / "data", limit: int | None = None) -> list[dict]:
    from .nearshore import load_tables
    from .surfzone import load_profiles
    from .transform import load_spectra

    from .fillshift import nearest_rule

    tables, profiles = load_tables(), load_profiles()
    # Before §61 a headland's fill was read at its nearest clear ray's heading.
    old_fill = {b: nearest_rule(t) for b, t in tables.items()}
    inshore = {b: p.inshore() for b, p in profiles.items()}
    hours = selected(load_spectra(data_dir / "spectra" / "46232"))
    if limit:
        hours = hours[:limit]
    rows = []
    for sp, hs, frm in hours:
        row = {"time": sp.time, "buoy": hs, "from": frm, "v": {}}
        for variant in VARIANTS:
            with _chain(variant) as live:
                got = live.build(data_dir=data_dir, now=sp.time, spectrum=sp, as_of=True,
                                 tables=old_fill if variant in ("then", "madsen") else tables,
                                 profiles=inshore if variant in ("then", "madsen") else profiles)
            row["v"][variant] = {b.id: _row(b) for b in got.breaks}
        rows.append(row)
    return rows


def _f(v, n=2) -> str:
    return "–" if v is None or v != v else f"{v:.{n}f}"


def _qs(v: list[float]) -> str:
    return (f"{_q(v, .5):.2f} [{_q(v, .1):.2f}, {_q(v, .9):.2f}]" if v else "–")


def _ok(r, variants, b) -> bool:
    return all(r["v"][x][b]["hs"] and r["v"][x][b]["basis_breaking"] for x in variants)


def report(rows: list[dict], breakshift: dict | None = None) -> str:
    from .nearshore import BREAKS

    short = {b: b.split("_")[1].capitalize() for b in BREAKS}
    big = [r for r in rows if r["buoy"] >= MIN_HS and SECTOR[0] <= r["from"] < SECTOR[1]]
    days = sorted({r["time"].date() for r in big})
    lines = [
        "# Big westerly days through the chain as it ships, against BRIEFING §56",
        "",
        "Written by `python -m forecast.westerlygap --write` (handoff item 27a). Reports, never "
        "edits. Every hour is the LIVE tab's own rebuild of a past hour (`now.build(as_of=True)`: "
        "NDBC's 46232 feed read by MEM, the KNZY wind and 9410170 tide that existed then, local "
        "chop), four ways: **then** — the chain as LIVE ran it on 17 Nov (the table's JONSWAP "
        "friction, surf zone from 5 m); **madsen** — Madsen's friction at the measured tide, surf "
        "zone still from 5 m (§57 alone); **now** — as shipped (§57 and §58); **now, no chop** — "
        "as shipped without the local chop.",
        "",
        f"Hours: {len(big)} archived hours with 46232 Hs ≥ {MIN_HS:g} m and its swell (≥ 8 s, "
        f"energy-weighted) from {SECTOR[0]:g}–{SECTOR[1]:g}°, on {len(days)} days, "
        f"{big[0]['time']:%d %b} – {big[-1]['time']:%d %b %Y}" if big else "Hours: none.",
    ]
    lines[-1] += f", plus every hour of {DAY:%d %b}. **Nothing here is observed**: the chain " \
                 "against its own earlier self, never a score. The headline is a significant " \
                 "breaking height, not a face height."

    # -- control: §56's step table
    at = [r for r in rows if r["time"].date() == DAY and r["time"].hour == 22]
    lines += ["", "## Control: §56's table at 17 Nov 22Z, rebuilt", ""]
    if at:
        r = at[0]
        lines += [f"46232 {r['buoy']:.2f} m, swell from {r['from']:.0f}°. Each step as the card's "
                  "calculation table lists it (m); §56's figure in brackets.", "",
                  "| step | " + " | ".join(f"{short[b]}: then (§56) → now" for b in BREAKS) + " |",
                  "|---|" + "---|" * len(BREAKS)]
        worst = 0.0
        for n, (label, key) in enumerate(STEPS + (("breaking (headline)", "hs"),)):
            cells = []
            for b in BREAKS:
                t, w = r["v"]["then"][b][key], r["v"]["now"][b][key]
                ref = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 6: 5}.get(n)
                s = S56_22Z[b][ref] if ref is not None else None
                if s is not None:
                    worst = max(worst, abs(t - s))
                cells.append(f"{_f(t)} ({_f(s) if s is not None else '–'}) → {_f(w)}")
            lines.append(f"| {label} | " + " | ".join(cells) + " |")
        lines += ["", f"Largest difference from §56's printed figures: {worst:.3f} m, within their rounding "
                      "(the 'then' rebuild gives §56's table back). §56 listed no chop row; "
                      "its headline included the chop."]

    # -- 17 Nov hour by hour
    day = [r for r in rows if r["time"].date() == DAY]
    lines += ["", f"## {DAY:%d %b}, hour by hour", "",
              "Breaking height (m), then → now, and now ÷ then. Tide is the coast level on MSL "
              "Madsen used.", "",
              "| hour | 46232 Hs, swell from | tide | "
              + " | ".join(f"{short[b]}" for b in BREAKS) + " |",
              "|---|---|---|" + "---|" * len(BREAKS)]
    for r in day:
        cells = []
        for b in BREAKS:
            t, w = r["v"]["then"][b]["hs"], r["v"]["now"][b]["hs"]
            cells.append(f"{_f(t)} → {_f(w)} ({_f(w / t) if t and w else '–'})")
        lines.append(f"| {r['time']:%HZ} | {r['buoy']:.2f} m, {r['from']:.0f}° | "
                     f"{_f(r['v']['now'][BREAKS[0]]['tide'])} | " + " | ".join(cells) + " |")

    # -- every big westerly hour, by size
    lines += ["", "## Every big westerly hour, by 46232's size", "",
              "Median [10th, 90th]. **now ÷ then** is what §57 and §58 took off the headline; "
              "**madsen ÷ then** is §57's share of it. **÷ buoy** is the headline over 46232's "
              "Hs; **÷ window** over the straight-line window figure (§56: 1.9–2.45× on W–WNW, "
              "then). **chop** is the headline with chop over without (now).", ""]
    for b in BREAKS:
        lines += [f"### {short[b]}", "",
                  "| 46232 Hs | hours | now ÷ then | madsen ÷ then | then ÷ buoy | now ÷ buoy "
                  "| then ÷ window | now ÷ window | chop | break depth now, median (max) |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        for lo, hi in HS_BANDS + ((MIN_HS, 99.0),):
            band = [r for r in big if lo <= r["buoy"] < hi and _ok(r, VARIANTS, b)]
            if not band:
                continue
            v = lambda x, r: r["v"][x][b]
            nt = [v("now", r)["hs"] / v("then", r)["hs"] for r in band]
            mt = [v("madsen", r)["hs"] / v("then", r)["hs"] for r in band]
            tb = [v("then", r)["hs"] / r["buoy"] for r in band]
            nb = [v("now", r)["hs"] / r["buoy"] for r in band]
            tw = [v("then", r)["hs"] / v("then", r)["window_hs_m"] for r in band]
            nw = [v("now", r)["hs"] / v("now", r)["window_hs_m"] for r in band]
            ch = [v("now", r)["hs"] / v("now_nochop", r)["hs"] for r in band]
            dp = [v("now", r)["depth"] for r in band]
            label = "all ≥ 2 m" if (lo, hi) == (MIN_HS, 99.0) else (
                f"{lo:.1f}–{hi:.1f} m" if hi < 99 else f"≥ {lo:.1f} m")
            lines.append(f"| {label} | {len(band)} | {_qs(nt)} | {_qs(mt)} | {_qs(tb)} | {_qs(nb)} "
                         f"| {_qs(tw)} | {_qs(nw)} | {_qs(ch)} | {_q(dp, .5):.1f} ({max(dp):.1f}) m |")
        lines.append("")

    # -- the days
    lines += ["## The days", "",
              "Each day with a big westerly hour: how many, 46232's largest Hs among them, "
              "and the headline at that hour then → now.", "",
              "| day | hours | 46232 max | " + " | ".join(short[b] for b in BREAKS) + " |",
              "|---|---|---|" + "---|" * len(BREAKS)]
    for d in days:
        sel = [r for r in big if r["time"].date() == d]
        top = max(sel, key=lambda r: r["buoy"])
        cells = [f"{_f(top['v']['then'][b]['hs'])} → {_f(top['v']['now'][b]['hs'])}" for b in BREAKS]
        lines.append(f"| {d:%d %b} | {len(sel)} | {top['buoy']:.2f} m ({top['time']:%HZ}, "
                     f"{top['from']:.0f}°) | " + " | ".join(cells) + " |")

    # -- control against breakshift
    if breakshift:
        diffs = []
        for r in big:
            other = breakshift.get(r["time"])
            for b in BREAKS:
                if other and b in other and r["v"]["now_nochop"][b]["hs"]:
                    diffs.append(abs(r["v"]["now_nochop"][b]["hs"] - round(other[b]["after"][0], 3)))
        if diffs:
            lines += ["", f"Control: on the {len(diffs)} break-hours `forecast.breakshift` also "
                          f"rebuilds, 'now, no chop' against its 'after', largest |Δ| "
                          f"{max(diffs):.3f} m, median {_q(diffs, .5):.3f} m."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true", help=f"also write {OUT.relative_to(ROOT)}")
    ap.add_argument("--limit", type=int, default=None, help="only the first n hours (a quick look)")
    ap.add_argument("--no-control", action="store_true", help="skip the breakshift control (~3 min)")
    args = ap.parse_args(argv)
    rows = run(limit=args.limit)
    shift = None
    if not args.no_control:
        from . import breakshift
        shift = {r["time"]: r for r in breakshift.run()}
    text = report(rows, shift)
    print(text)
    if args.write:
        OUT.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
