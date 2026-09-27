"""The observed chain, hour by hour, for the chart under each Now card.

Written by ``python -m forecast.measured`` beside ``measured.json``, as
``data/live/series.json``: the last 168 hours (owner's choice, 2026-09-27),
every hour rather than every third, because the chart is about how the buoy
and the breaks move against each other and a 3-hourly line would skip most of
a swell's arrival.

**Rebuilt, not saved.** Nothing hourly was ever kept: `now.json` is the latest
hour and `measured.json` every third. Every INPUT is committed — 46232's
spectra, KNZY, the gauge — so each hour is rebuilt from scratch through
`measured.Rebuilder`, with TODAY's chain. A past point is therefore what the
current windows, seabed and surf zone make of that hour's spectrum, not what
the page showed at the time; the chart says so. Measured 2026-09-27 on a
4-core session: 0.18 s an hour, 31 s for 168, on top of a 1.1 s load.

**A missing observation is a gap.** An hour with no spectrum stamped at it is
`{"gap": true}` and the page breaks the line there — never joined across,
never filled from a neighbour. The same holds per line: a break whose headline
is not a breaking height at that hour (no tide) has no height on the chart,
because a line that switched quantity mid-way would draw a step nothing
caused.

What each hour carries, beyond the heights:

- ``south_minus_north_m``: south's breaking height less north's. Its sign is
  the ordering the observation log verifies (`forecast.beachverify`), and a
  zero crossing is the ordering flipping.
- ``transmission``: a break's height in its windows over the buoy's — the
  straight-line window figure, not breaking, which lifts ~20% (BRIEFING §32)
  and would hide the windows opening and closing.
- ``pct_k`` / ``pct_d``: a stochastic oscillator. Where a height sits in its
  own trailing 24-hour range, 0 at the bottom and 100 at the top, and the
  three-hour mean of that. Taken only over readings that exist, only when
  the hour itself is present and at least 20 of the 24 are, and never over a
  range under 2 cm, where it is undefined rather than zero. It is a position
  in a range, not a height, and says nothing the heights do not; the page
  plots the buoy's minus the break's, which is positive when the buoy sits
  higher in its own range than the break does in its.

Derived and gitignored like `measured.json`. Nothing here is a comparison with
a forecast, and nothing here checks the beach.

**The archive: every hour since the spectra begin** (owner's request,
2026-09-27: "see how the chart plots over months/years"). Rebuilding it on
every collection does not scale — 0.18 s an hour, so a year is 26 minutes on
one core — so it is kept, not remembered:

- ``python -m forecast.series --archive`` rebuilds EVERY archived hour from
  scratch with today's chain and writes ``data/series/46232/YYYY-MM.csv``.
  Measured 2026-09-27: 1,309 hours (919 spectra, 390 gaps) in 35 s on four
  workers; a year of spectra is about five minutes. Only `series-archive.yml`
  runs it, so the store has one writer. It is deterministic, so a run whose
  chain did not change commits nothing.
- It is DERIVED and tracked anyway, for a different reason from
  `data/historical/`: not because it is irreplaceable — every input is
  committed and a rebuild recreates it exactly — but because rebuilding it on
  every collection is not affordable. It grows ~0.9 MB a year.
- **It is never mixed with a different chain.** Every collection compares the
  store against the hours it has just rebuilt (and a few older ones rebuilt
  for the purpose). If they disagree, the chain changed since the archive was
  written: ``series_all.json`` then says so and carries no hours, the long
  view is withheld rather than drawn across two chains, and the collection
  asks for a rebuild. An hour the store holds as a gap that has since
  landed is the archive being behind, not the chain changing, and is not
  counted against it.
- ``series_all.json`` is the store for the page's zoomed-out views: columnar,
  integers (mm, per mille, whole %K), and a function of the store alone, so
  it is byte-identical until the archive changes and republishing it every
  collection costs git nothing.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR, ISO

from .measured import STATION, Rebuilder, _r

#: How far back the chart reaches (owner's choice, 2026-09-27).
SERIES_HOURS = 168
#: The oscillator's trailing window, and how much of it must be present.
K_LOOKBACK_H = 24
K_MIN_HOURS = 20
#: Below this the range is flat and %K is undefined, not zero.
K_MIN_RANGE_M = 0.02
#: %D is the mean of this many consecutive %K.
D_HOURS = 3

#: Hours rebuilt before the first one shown, so the oscillator is defined from
#: the first hour on screen rather than a day and a bit in.
WARMUP_HOURS = K_LOOKBACK_H - 1 + D_HOURS - 1

SOUTH, NORTH = "coronado_south", "coronado_north"


def hours_until(until: datetime, hours: int) -> list[datetime]:
    """`hours` consecutive UTC hours ending at the one `until` falls in."""

    last = until.replace(minute=0, second=0, microsecond=0)
    return [last - timedelta(hours=n) for n in range(hours - 1, -1, -1)]


def hourly(rebuild: Rebuilder, until: datetime, hours: int = SERIES_HOURS) -> dict[datetime, dict]:
    """One `measured` entry per hour, warm-up hours included, oldest first."""

    return {t: rebuild.at(t) for t in hours_until(until, hours + WARMUP_HOURS)}


def slim(entry: dict) -> dict:
    """The fields the chart draws, from one `measured.entry`."""

    if entry.get("gap"):
        return {"valid_utc": entry["valid_utc"], "gap": True}
    if entry.get("pending"):
        return {"valid_utc": entry["valid_utc"], "gap": False, "pending": True}
    buoy_hs = (entry.get("buoy") or {}).get("hs_m")
    breaks = {}
    for bid, b in (entry.get("breaks") or {}).items():
        window = b.get("hs_window_m")
        # The window height itself is not kept: the chart draws only its ratio
        # to the buoy, and the payload ships every collection.
        breaks[bid] = {
            "hs_m": b.get("hs_m") if b.get("hs_basis") == "breaking" else None,
            "transmission": _r(window / buoy_hs) if window is not None and buoy_hs else None,
        }
    south, north = (breaks.get(SOUTH) or {}).get("hs_m"), (breaks.get(NORTH) or {}).get("hs_m")
    return {
        "valid_utc": entry["valid_utc"],
        "gap": False,
        "buoy": {"hs_m": buoy_hs, "from_deg": (entry.get("buoy") or {}).get("from_deg")},
        "breaks": breaks,
        "south_minus_north_m": _r(south - north) if south is not None and north is not None else None,
    }


def _heights(steps: list[dict], pick) -> list[float | None]:
    out = []
    for step in steps:
        v = None
        if not step.get("gap") and not step.get("pending"):
            v = pick(step)
        out.append(v)
    return out


def pct_k(values: list[float | None], *, lookback: int = K_LOOKBACK_H,
          min_hours: int = K_MIN_HOURS, min_range: float = K_MIN_RANGE_M) -> list[float | None]:
    """%K per hour over the trailing `lookback` hours, current hour included.

    `values` is one entry per consecutive hour, None where there is no reading.
    Nothing is filled: the range is the readings that exist, and a window with
    too few of them has no %K at all.
    """

    out: list[float | None] = []
    for i, v in enumerate(values):
        if v is None or i + 1 < lookback:
            out.append(None)
            continue
        present = [x for x in values[i + 1 - lookback:i + 1] if x is not None]
        lo, hi = min(present), max(present)
        if len(present) < min_hours or hi - lo < min_range:
            out.append(None)
            continue
        out.append(round(100 * (v - lo) / (hi - lo), 1))
    return out


def pct_d(k: list[float | None], *, hours: int = D_HOURS) -> list[float | None]:
    """The mean of the last `hours` %K, only when every one of them exists."""

    out: list[float | None] = []
    for i in range(len(k)):
        window = k[max(0, i + 1 - hours):i + 1]
        ok = len(window) == hours and all(x is not None for x in window)
        out.append(round(sum(window) / hours, 1) if ok else None)
    return out


def oscillate(steps: list[dict]) -> None:
    """Add `pct_k` and `pct_d` to the buoy and every break, in place."""

    ids = sorted({bid for s in steps for bid in (s.get("breaks") or {})})
    lines = [("buoy", lambda s: (s.get("buoy") or {}).get("hs_m"))]
    lines += [(bid, lambda s, bid=bid: ((s.get("breaks") or {}).get(bid) or {}).get("hs_m"))
              for bid in ids]
    for key, pick in lines:
        k = pct_k(_heights(steps, pick))
        d = pct_d(k)
        for step, kv, dv in zip(steps, k, d):
            if step.get("gap") or step.get("pending"):
                continue
            target = step["buoy"] if key == "buoy" else (step.get("breaks") or {}).get(key)
            if target is not None:
                target["pct_k"], target["pct_d"] = kv, dv


def build(entries: dict[datetime, dict], *, now: datetime,
          hours: int = SERIES_HOURS) -> dict:
    """`series.json` from the entries `hourly` rebuilt, warm-up dropped."""

    ordered = [slim(entries[t]) for t in sorted(entries)]
    oscillate(ordered)
    return {
        "generated_utc": now.strftime(ISO),
        "station": STATION,
        "hours": hours,
        "k_lookback_h": K_LOOKBACK_H,
        "k_min_hours": K_MIN_HOURS,
        "d_hours": D_HOURS,
        "rebuilt_with": "the current chain",
        "standing_on": {
            "waves": f"OBSERVED — the NDBC directional spectrum at {STATION} stamped at "
                     f"each hour; an hour without one is a gap, never filled",
            "chain": "today's windows, seabed and surf zone, applied to every past hour",
            "claim": "how the buoy and the breaks moved against each other; it checks "
                     "nothing at the beach",
        },
        "steps": ordered[-hours:],
    }


# --- The archive ---------------------------------------------------------------

#: Where the store lives, under the data directory.
STORE = Path("series") / STATION
#: The page draws the breaks north to south; the store keeps them in that order.
BREAKS = ("coronado_north", "coronado_center", "coronado_south")
#: Older hours rebuilt at each collection to check the store against today's
#: chain, beyond the week that is rebuilt anyway.
CHECK_SAMPLE = 8
#: The store keeps three decimals, so two values from one chain differ by
#: rounding at most; anything past this is a different chain.
CHECK_TOLERANCE = 0.0015


def _utc(stamp: str) -> datetime:
    return datetime.strptime(stamp, ISO).replace(tzinfo=timezone.utc)


def archive_hours(rebuild: Rebuilder) -> list[datetime]:
    """Every hour from the first archived spectrum to the last. The last is
    the newest hour that is final: anything later is still pending."""

    if not rebuild.by_time:
        return []
    first, last = min(rebuild.by_time), max(rebuild.by_time)
    return [first + timedelta(hours=n)
            for n in range(int((last - first).total_seconds() // 3600) + 1)]


_WORKER: Rebuilder | None = None


def _start_worker(data_dir: str) -> None:
    global _WORKER
    _WORKER = Rebuilder(Path(data_dir))


def _rebuild_one(valid: datetime) -> dict:
    return slim(_WORKER.at(valid))


def rebuild_archive(data_dir: Path = DEFAULT_DATA_DIR, *, workers: int = 1) -> list[dict]:
    """Every archived hour through today's chain, slimmed, oldest first."""

    rebuild = Rebuilder(data_dir)
    hours = archive_hours(rebuild)
    if workers <= 1:
        return [slim(rebuild.at(t)) for t in hours]
    from multiprocessing import Pool

    with Pool(workers, initializer=_start_worker, initargs=(str(data_dir),)) as pool:
        return pool.map(_rebuild_one, hours, chunksize=24)


def _columns(ids) -> list[str]:
    return (["valid_utc", "gap", "buoy_hs_m", "buoy_from_deg"]
            + [f"{b}_hs_m" for b in ids] + [f"{b}_transmission" for b in ids])


def _cell(v) -> str:
    return "" if v is None else repr(v) if isinstance(v, float) else str(v)


def write_store(steps: list[dict], data_dir: Path = DEFAULT_DATA_DIR) -> list[Path]:
    """One CSV per month. A full rebuild owns the directory, so a month it did
    not produce is removed rather than left standing from an older chain."""

    folder = Path(data_dir) / STORE
    folder.mkdir(parents=True, exist_ok=True)
    months: dict[str, list[dict]] = {}
    for step in steps:
        months.setdefault(step["valid_utc"][:7], []).append(step)
    written = []
    for month, rows in sorted(months.items()):
        path = folder / f"{month}.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            out = csv.writer(fh, lineterminator="\n")
            out.writerow(_columns(BREAKS))
            for step in rows:
                if step.get("gap"):
                    out.writerow([step["valid_utc"], 1] + [""] * (2 + 2 * len(BREAKS)))
                    continue
                buoy, brk = step.get("buoy") or {}, step.get("breaks") or {}
                out.writerow([step["valid_utc"], 0, _cell(buoy.get("hs_m")),
                              _cell(buoy.get("from_deg"))]
                             + [_cell((brk.get(b) or {}).get("hs_m")) for b in BREAKS]
                             + [_cell((brk.get(b) or {}).get("transmission")) for b in BREAKS])
        written.append(path)
    for stale in folder.glob("*.csv"):
        if stale not in written:
            stale.unlink()
    return written


def read_store(data_dir: Path = DEFAULT_DATA_DIR) -> list[dict]:
    """The store as slim steps, oldest first; empty when there is none."""

    num = lambda v: float(v) if v not in ("", None) else None  # noqa: E731
    steps = []
    for path in sorted((Path(data_dir) / STORE).glob("*.csv")):
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if row["gap"] == "1":
                    steps.append({"valid_utc": row["valid_utc"], "gap": True})
                    continue
                breaks = {b: {"hs_m": num(row.get(f"{b}_hs_m")),
                              "transmission": num(row.get(f"{b}_transmission"))}
                          for b in BREAKS}
                south, north = breaks[SOUTH]["hs_m"], breaks[NORTH]["hs_m"]
                steps.append({
                    "valid_utc": row["valid_utc"], "gap": False,
                    "buoy": {"hs_m": num(row["buoy_hs_m"]), "from_deg": num(row["buoy_from_deg"])},
                    "breaks": breaks,
                    "south_minus_north_m": _r(south - north)
                    if south is not None and north is not None else None,
                })
    return steps


def _same(a: dict, b: dict, tol: float = CHECK_TOLERANCE) -> bool:
    """Two readings of one hour agree to the store's rounding."""

    def close(x, y):
        return (x is None and y is None) or (
            x is not None and y is not None and abs(x - y) <= tol)

    if not close((a.get("buoy") or {}).get("hs_m"), (b.get("buoy") or {}).get("hs_m")):
        return False
    for bid in BREAKS:
        p, q = (a.get("breaks") or {}).get(bid) or {}, (b.get("breaks") or {}).get(bid) or {}
        if not (close(p.get("hs_m"), q.get("hs_m"))
                and close(p.get("transmission"), q.get("transmission"))):
            return False
    return True


def check(store: list[dict], fresh: dict[str, dict], rebuild: Rebuilder | None = None,
          *, sample: int = CHECK_SAMPLE) -> tuple[bool, str]:
    """Does the store still say what today's chain says?

    `fresh` is slim steps just rebuilt, by stamp. Every hour both hold a
    reading for is compared; so are `sample` older stored hours, rebuilt here.
    Only hours with a reading on both sides count: a stored gap that has since
    landed means the archive is behind, not that the chain moved.
    """

    held = [s for s in store if not s.get("gap")]
    both = [s for s in held
            if s["valid_utc"] in fresh and not fresh[s["valid_utc"]].get("gap")
            and not fresh[s["valid_utc"]].get("pending")]
    older = [s for s in held if s["valid_utc"] not in fresh]
    if rebuild is not None and older and sample:
        pick = [older[round(i * (len(older) - 1) / max(1, sample - 1))]
                for i in range(min(sample, len(older)))]
        for s in {p["valid_utc"]: p for p in pick}.values():
            again = slim(rebuild.at(_utc(s["valid_utc"])))
            if not again.get("gap"):
                both.append(s)
                fresh = {**fresh, s["valid_utc"]: again}
    if not both:
        return False, "no hour to check the archive against"
    moved = [s["valid_utc"] for s in both if not _same(s, fresh[s["valid_utc"]])]
    if moved:
        return False, (f"{len(moved)} of {len(both)} checked hours differ from today's chain "
                       f"(first {moved[0]}); the archive needs rebuilding")
    return True, f"{len(both)} checked hours agree with today's chain"


def build_all(store: list[dict], *, ok: bool, why: str) -> dict:
    """`series_all.json`: the store for the zoomed-out views, or why not.

    Columnar and in integers so a year is well under a megabyte: heights in
    mm, the window ratio per mille, %K and %D whole. Nothing here depends on
    the clock, so the file only changes when the store does.
    """

    head = {"station": STATION, "k_lookback_h": K_LOOKBACK_H, "d_hours": D_HOURS}
    if not ok or not store:
        return {**head, "available": False, "why": why or "no archive yet"}
    steps = [json.loads(json.dumps(s)) for s in store]
    oscillate(steps)
    mm = lambda v: None if v is None else round(v * 1000)  # noqa: E731
    whole = lambda v: None if v is None else round(v)  # noqa: E731
    live = [not s.get("gap") for s in steps]
    col = lambda f: [f(s) if on else None for s, on in zip(steps, live)]  # noqa: E731
    key = lambda k: lambda s: (s.get("buoy") or {}).get(k)  # noqa: E731
    brk = lambda b, k: lambda s: ((s.get("breaks") or {}).get(b) or {}).get(k)  # noqa: E731
    return {
        **head,
        "available": True,
        "why": why,
        "start_utc": steps[0]["valid_utc"],
        "through_utc": steps[-1]["valid_utc"],
        "hours": len(steps),
        "breaks": list(BREAKS),
        "gaps": [i for i, on in enumerate(live) if not on],
        "from_deg": [whole(v) for v in col(key("from_deg"))],
        "hs_mm": {"buoy": [mm(v) for v in col(key("hs_m"))],
                  **{b: [mm(v) for v in col(brk(b, "hs_m"))] for b in BREAKS}},
        "tr_pm": {b: [mm(v) for v in col(brk(b, "transmission"))] for b in BREAKS},
        "k": {"buoy": [whole(v) for v in col(key("pct_k"))],
              **{b: [whole(v) for v in col(brk(b, "pct_k"))] for b in BREAKS}},
        "d": {"buoy": [whole(v) for v in col(key("pct_d"))],
              **{b: [whole(v) for v in col(brk(b, "pct_d"))] for b in BREAKS}},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rebuild the hourly archive with today's chain.")
    parser.add_argument("--archive", action="store_true", required=True)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args(argv)

    steps = rebuild_archive(args.data_dir, workers=args.workers)
    if not steps:
        print("No archived spectra: nothing to rebuild.")
        return 1
    written = write_store(steps, args.data_dir)
    gaps = sum(1 for s in steps if s.get("gap"))
    print(f"Rebuilt {len(steps)} hour(s) ({gaps} gap(s)) from {steps[0]['valid_utc']} "
          f"to {steps[-1]['valid_utc']} into {len(written)} month file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
