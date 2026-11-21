"""Fetch one year at Imperial Beach Nearshore: the observation, the input, and MOP.

The owner's question (handoff item 24, 2026-11-20): should the chain's
deep-water-to-10 m leg give way to CDIP MOP's? Two models cannot settle it;
an observation can. `collector.nearshore_census` (run 8) found the site:
Imperial Beach Nearshore, NDBC 46235 / CDIP 155, a Waverider in 21 m inside
the chain's 32 m seabed, archived at CDIP 2006-12-19 to 2026-05-03; 46232's
own record at CDIP (191) from 2007-10-03; MOP's nearest point D0043.
NDBC holds no historical spectra for either buoy, so this reads CDIP.

What it fetches, for ONE year chosen by a rule fixed before any spectrum is
read (`choose_window`): the twelve consecutive calendar months, inside one
MOP product's coverage, with the most clock hours on which both buoys
reported (ties to the latest). Then:

- both buoys' spectra (energy density and a1, b1, a2, b2 on their own
  bands), Hs and the primary QC flag, month by month, with the file's own
  DDS/DAS checked first (`mop.spectral_schema`) and the read-back
  4·sqrt(Σ E·df) / Hs over every record;
- 46232's (191) August 2026 as well: the hours this repository's NDBC archive
  also holds, so the session can check that CDIP's 191 converted to NDBC's
  form gives the archived spectra back (the control that says the input is
  the input);
- MOP at its point nearest the buoy (from the census, not typed), for the
  same year, through `mop.save_extras` itself: the spectrum, moments, the
  small variables (its shore normal) and what drove each hour. If 155 is
  among MOP's inputs that year, MOP is not independent of the observation,
  and the report says so first.

The series (~90 MB) are kept as the run's artifact, not committed; the
commit holds `fetch.json` and the meta and band files (owner's call,
2026-11-21).

Report only, on Actions (`mop-check.yml`, `points=nearshore_test`): CDIP is
refused at CONNECT from a session. Nothing the forecast uses reads it, and
the buoy's record is a verification series for the deep-water-to-21 m leg at
Imperial Beach, never for a break.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

from collector import mop
from collector.common import write_step_summary

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "nearshore_test"
CENSUS = ROOT / "data" / "nearshore_census" / "census.json"

#: The observation and the input, by CDIP station and dataset. Positions,
#: depths and coverage are read from the files, never typed.
BUOYS = {"imperial_beach_nearshore": "155p1", "point_loma_south": "191p1"}
OBSERVED, INPUT = "imperial_beach_nearshore", "point_loma_south"
NDBC_OF = {"imperial_beach_nearshore": "46235", "point_loma_south": "46232"}
FLAG = "waveFlagPrimary"
#: The control month: hours this repository's NDBC archive of 46232 also holds
#: (it starts 2026-08-04; CDIP's 191 archive ends 2026-09-01).
CONTROL = ("2026-08-04", "2026-09-01")
MONTHS = 12
CDIP_REQUESTS = 90
CATALOG_RETRY_S = (30, 90, None)


def archive_path(sid: str) -> str:
    return f"cdip/archive/{sid}/{sid}_historic.nc"


def epoch(day: str) -> float:
    return datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp()


def month_starts(first: float, last: float) -> list[float]:
    """Epoch seconds of each calendar month start from the month after
    `first` (a partial first month never counts as a month) to `last`."""

    d = datetime.fromtimestamp(first, tz=timezone.utc)
    y, m = (d.year, d.month) if (d.day, d.hour, d.minute, d.second) == (1, 0, 0, 0) else \
        ((d.year + (d.month == 12), d.month % 12 + 1))
    out = []
    while True:
        t = datetime(y, m, 1, tzinfo=timezone.utc).timestamp()
        if t > last:
            return out
        out.append(t)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def hours_with(times: list[float]) -> set[int]:
    return {int(t // 3600) for t in times}


def choose_window(a: list[float], b: list[float], products: dict[str, tuple[float, float]],
                  months: int = MONTHS) -> dict | None:
    """The rule, fixed before any spectrum is read: `months` consecutive
    calendar months inside ONE MOP product's coverage with the most clock
    hours on which both buoys have a record; ties go to the latest window.
    Returns {"start", "end", "product", "joint_hours"} or None."""

    joint = hours_with(a) & hours_with(b)
    if not joint:
        return None
    best = None
    for product, (p0, p1) in sorted(products.items()):
        # Through the month start AFTER the last record (but never past the
        # product's end, checked below): a window ending where the data end
        # must be able to close.
        starts = month_starts(max(p0, min(a), min(b)), min(p1, max(a), max(b)) + 32 * 86400.0)
        for i in range(len(starts) - months):
            t0, t1 = starts[i], starts[i + months]
            if t1 > p1:
                continue
            n = sum(1 for h in joint if t0 <= h * 3600 < t1)
            if best is None or (n, t0) > (best["joint_hours"], best["start"]):
                best = {"start": t0, "end": t1, "product": product, "joint_hours": n}
    return best


def uses(source: str, sid: str) -> bool:
    """Whether a `waveModelInputSource` string names CDIP station `sid`
    (`155p1`): its tokens split on `-` and `:`, compared by station number."""

    tokens = [t for t in source.replace(":", "-").split("-") if t]
    return any(t[:3] == sid[:3] for t in tokens)


def iso(t: float) -> str:
    return datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def index_span(times: list[float], t0: float, t1: float) -> tuple[int, int] | None:
    idx = [i for i, t in enumerate(times) if t0 <= t < t1]
    return (idx[0], idx[-1]) if idx else None


class Patient(mop.Budget):
    """mop.Budget that retries a 504 (the catalogue's, runs 5 and 7)."""

    def __init__(self, log: list[str], **kw):
        super().__init__(**kw)
        self.log = log

    def fetch(self, url: str, timeout: float = 120.0) -> str:
        for wait in CATALOG_RETRY_S:
            try:
                return super().fetch(url, timeout)
            except urllib.error.HTTPError as exc:
                if exc.code != 504 or wait is None:
                    raise
                self.log.append(f"{url}: 504, retried after {wait} s")
                time.sleep(wait)
        raise RuntimeError("unreachable")


def open_buoy(budget: mop.Budget, sid: str) -> dict:
    """The file's DDS, DAS, schema, small variables and time axis, checked."""

    path = archive_path(sid)
    dds = budget.fetch(f"{mop.DODS}{path}.dds")
    das = budget.fetch(f"{mop.DODS}{path}.das")
    dims, attrs = mop.parse_dds(dds), mop.parse_das(das)
    units = mop.time_units(das)
    if not units or not units.startswith("seconds since 1970-01-01"):
        raise ValueError(f"{sid}: {mop.TIME} units are {units!r}")
    schema, problems = mop.spectral_schema(dims, attrs)
    if schema is None or not schema["moments"]:
        raise ValueError(f"{sid}: spectrum not readable: {problems or 'no moments'}")
    if dims.get(mop.HS, {}).get("dims") != [(mop.TIME, dims[mop.TIME]["dims"][0][1])]:
        raise ValueError(f"{sid}: {mop.HS} is not on {mop.TIME}: {dims.get(mop.HS)}")
    small = [v for v in mop.small_variables(dims)]
    try:
        body = budget.fetch(f"{mop.DODS}{path}.ascii?{','.join(small)}") if small else ""
    except urllib.error.HTTPError:
        # As collector.mop: one variable THREDDS will not serve as ASCII must
        # not cost the bands.
        small = [v for v in (mop.FREQ, mop.BOUNDS, mop.BANDWIDTH, mop.LAT, mop.LON, mop.DEPTH) if v in dims]
        body = budget.fetch(f"{mop.DODS}{path}.ascii?{','.join(small)}")
    values = mop.parse_ascii(body) if body else {}
    times = mop.parse_ascii(budget.fetch(f"{mop.DODS}{path}.ascii?{mop.TIME}"))[mop.TIME]
    return {"sid": sid, "path": path, "dds": dds, "das": das, "dims": dims, "attrs": attrs,
            "schema": schema, "bands": mop.band_edges(schema, values), "small": body,
            "times": times, "flag": FLAG in dims and dims[FLAG]["dims"] == dims[mop.HS]["dims"]}


def fetch_months(budget: mop.Budget, f: dict, t0: float, t1: float) -> list[dict]:
    """Every record in [t0, t1), a month a request: time, Hs, flag, energy
    and the four moments by band, gaps as None."""

    nf, out = f["schema"]["nf"], []
    starts = [t0] + [s for s in month_starts(t0, t1) if t0 < s < t1]
    for a, b in zip(starts, starts[1:] + [t1]):
        span = index_span(f["times"], a, b)
        if span is None:
            continue
        i0, i1 = span
        sl = f"[{i0}:1:{i1}]"
        hyper = "".join(sl if d == mop.TIME else f"[0:1:{nf - 1}]" for d, _ in f["dims"][mop.ENERGY]["dims"])
        names = [mop.TIME + sl, mop.HS + sl] + ([FLAG + sl] if f["flag"] else []) \
            + [v + hyper for v in (mop.ENERGY, *mop.MOMENTS)]
        got = mop.parse_ascii(budget.fetch(f"{mop.DODS}{f['path']}.ascii?{','.join(names)}", timeout=600.0))
        n = i1 - i0 + 1
        arrays = {}
        for v in (mop.ENERGY, *mop.MOMENTS):
            fills = mop.fill_values(f["attrs"].get(v, {}))
            arrays[v] = [[None if mop.is_gap(x, fills) else x for x in r]
                         for r in mop.unpack(got.get(v, []), n, nf, f["schema"]["time_first"])]
        hs_fill = mop.fill_values(f["attrs"].get(mop.HS, {}))
        for k in range(n):
            h = got[mop.HS][k]
            out.append({"t": got[mop.TIME][k], "hs": None if mop.is_gap(h, hs_fill) else h,
                        "flag": int(got[FLAG][k]) if f["flag"] else None,
                        **{v: arrays[v][k] for v in arrays}})
    return out


def write_buoy(out: Path, name: str, f: dict, recs: list[dict]) -> dict:
    """The same files `collector.mop` writes for a MOP point, so one reader
    serves all three: `_bands.csv`, `_spectrum.csv`, `_moments.csv`, and
    `<name>.csv` (time, Hs, flag)."""

    nf = f["schema"]["nf"]
    cell = lambda x, fmt: "" if x is None else format(x, fmt)
    with (out / f"{name}_bands.csv").open("w", encoding="utf-8") as fh:
        fh.write("band,freq_hz,lower_hz,upper_hz,bandwidth_hz\n")
        for i, (fc, lo, hi, bw) in enumerate(f["bands"]):
            fh.write(f"{i},{fc:.6g},{lo:.6g},{hi:.6g},{'' if bw is None else f'{bw:.6g}'}\n")
    with (out / f"{name}.csv").open("w", encoding="utf-8") as fh:
        fh.write("valid_utc,hs_m,flag_primary\n")
        for r in recs:
            fh.write(f"{iso(r['t'])},{cell(r['hs'], '.3f')},{'' if r['flag'] is None else r['flag']}\n")
    with (out / f"{name}_spectrum.csv").open("w", encoding="utf-8") as fh:
        fh.write("valid_utc," + ",".join(f"e{i:02d}" for i in range(nf)) + "\n")
        for r in recs:
            fh.write(iso(r["t"]) + "," + ",".join(cell(x, ".4g") for x in r[mop.ENERGY]) + "\n")
    with (out / f"{name}_moments.csv").open("w", encoding="utf-8") as fh:
        fh.write("valid_utc," + ",".join(f"{m}_{i:02d}" for m in ("a1", "b1", "a2", "b2") for i in range(nf)) + "\n")
        for r in recs:
            fh.write(iso(r["t"]) + "," + ",".join(cell(x, ".3f") for m in mop.MOMENTS for x in r[m]) + "\n")
    widths = [hi - lo for _, lo, hi, _ in f["bands"]]
    rb = mop.readback([r[mop.ENERGY] for r in recs], widths, [r["hs"] for r in recs])
    flags: dict[str, int] = {}
    for r in recs:
        flags[str(r["flag"])] = flags.get(str(r["flag"]), 0) + 1
    meta = {"cdip": f["sid"], "ndbc": NDBC_OF.get(name.split("_control")[0]), "url_path": f["path"],
            "global": f["attrs"].get("NC_GLOBAL", {}), "small_variables": {"ascii": f["small"]},
            "spectrum": {"schema": f["schema"], "bands": nf, "records": len(recs), "readback": rb},
            "flags": flags, "dds": f["dds"], "das": f["das"]}
    (out / f"{name}_meta.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    return {"records": len(recs), "readback": rb, "flags": flags,
            "first": iso(recs[0]["t"]) if recs else None, "last": iso(recs[-1]["t"]) if recs else None}


def run(out: Path, log: list[str]) -> dict:
    census = json.loads(CENSUS.read_text(encoding="utf-8"))
    site = census["stations"][NDBC_OF[OBSERVED]]["mop"]
    pid = site["point"]
    cov = {p: (epoch(site[p]["time_coverage_start"][:10]), epoch(site[p]["time_coverage_end"][:10]))
           for p in ("hindcast", "nowcast") if site.get(p, {}).get("time_coverage_start")}
    budget = Patient(log, limit=CDIP_REQUESTS)
    files = {name: open_buoy(budget, sid) for name, sid in BUOYS.items()}
    window = choose_window(files[OBSERVED]["times"], files[INPUT]["times"], cov)
    summary: dict = {"rule": "12 consecutive calendar months inside one MOP product's coverage with the "
                             "most clock hours on which both buoys have a record; ties to the latest",
                     "mop_point": pid, "mop_point_from": "data/nearshore_census/census.json (run 8)"}
    if window is None:
        summary["window"] = None
        log.append("no window: the two buoys never reported in the same hour inside MOP's coverage")
        return summary
    summary["window"] = {**window, "start": iso(window["start"]), "end": iso(window["end"])}
    out.mkdir(parents=True, exist_ok=True)
    summary["buoys"] = {}
    for name, f in files.items():
        summary["buoys"][name] = write_buoy(out, name, f, fetch_months(budget, f, window["start"], window["end"]))
    c0, c1 = epoch(CONTROL[0]), epoch(CONTROL[1])
    summary["buoys"][f"{INPUT}_control"] = write_buoy(out, f"{INPUT}_control", files[INPUT],
                                                      fetch_months(budget, files[INPUT], c0, c1))

    # MOP, through collector.mop's own reader.
    catalog = budget.fetch(mop.CATALOG)
    url_path = mop.list_points(catalog, window["product"]).get(pid)
    if url_path is None:
        log.append(f"MOP {pid} {window['product']} not in the catalogue")
        return summary
    dds = budget.fetch(f"{mop.DODS}{url_path}.dds")
    das = budget.fetch(f"{mop.DODS}{url_path}.das")
    t = mop.parse_ascii(budget.fetch(f"{mop.DODS}{url_path}.ascii?{mop.TIME}"))[mop.TIME]
    span = index_span(t, window["start"], window["end"])
    if span is None:
        log.append(f"MOP {pid}: no hours in the window")
        return summary
    i0, i1 = span
    hs_raw = mop.parse_ascii(budget.fetch(f"{mop.DODS}{url_path}.ascii?{mop.HS}[{i0}:1:{i1}]"))[mop.HS]
    hs = [None if mop.is_gap(x, set()) else x for x in hs_raw]
    lines, ok = mop.save_extras(budget, f"mop_{pid}", pid, url_path, dds, das, (i0, i1, t[i0:i1 + 1]), hs, out)
    with (out / f"mop_{pid}.csv").open("w", encoding="utf-8") as fh:
        fh.write("valid_utc,hs_m\n")
        for tt, h in zip(t[i0:i1 + 1], hs):
            fh.write(f"{iso(tt)},{'' if h is None else f'{h:.3f}'}\n")
    meta = json.loads((out / f"mop_{pid}_meta.json").read_text(encoding="utf-8"))
    sources = meta.get("inputs", {}).get("sources", {})
    with_obs = {s: n for s, n in sources.items() if uses(s, BUOYS[OBSERVED])}
    summary["mop"] = {"point": pid, "product": window["product"], "hours": i1 - i0 + 1, "ok": ok,
                      "lines": lines, "inputs": sources, "hours_driven_by_the_observed_buoy": sum(with_obs.values())}
    if with_obs:
        log.append(f"MOP {pid} lists {BUOYS[OBSERVED]} among its inputs on {sum(with_obs.values())} hours: "
                   "on those hours MOP is not independent of the observation")
    if not ok:
        log.append(f"MOP {pid}: spectrum or read-back failed: {lines}")
    summary["cdip_requests"] = CDIP_REQUESTS - budget.left
    return summary


def report(summary: dict, log: list[str]) -> str:
    w = summary.get("window")
    lines = ["## One year at Imperial Beach Nearshore: what was fetched", ""]
    if not w:
        return "\n".join(lines + ["No window. " + "; ".join(log)]) + "\n"
    lines += [f"Window ({summary['rule']}): **{w['start'][:10]} – {w['end'][:10]}**, MOP `{w['product']}`, "
              f"{w['joint_hours']} clock hours with both buoys.", "",
              "| series | records | first | last | read-back median / worst | QC flags |", "|---|---|---|---|---|---|"]
    for name, b in summary.get("buoys", {}).items():
        rb = b["readback"]
        lines.append(f"| {name} | {b['records']} | {b['first']} | {b['last']} | "
                     f"{rb.get('median')} / {rb.get('worst')} | {b['flags']} |")
    m = summary.get("mop")
    if m:
        lines += ["", f"MOP {m['point']} ({m['product']}): {m['hours']} hours; "
                      f"driven by the observed buoy on {m['hours_driven_by_the_observed_buoy']} hours.",
                  "", "MOP's inputs (hours): " + ", ".join(f"`{k}` {v}" for k, v in m["inputs"].items())]
        lines += [x.strip() for x in m["lines"]]
    lines += ["", f"CDIP requests: {summary.get('cdip_requests')} of {CDIP_REQUESTS}.", "", "### What failed", ""]
    lines += [f"- {x}" for x in log] or ["- nothing"]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args(argv)
    log: list[str] = []
    try:
        summary = run(args.out, log)
    except Exception as exc:  # noqa: BLE001 - what was found is still reported
        log.append(f"stopped: {exc.__class__.__name__}: {exc}")
        summary = {}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "fetch.json").write_text(json.dumps({**summary, "failed": log}, indent=1) + "\n", encoding="utf-8")
    text = report(summary, log)
    print(text)
    write_step_summary(text)
    if not summary.get("window"):
        return 2
    return 3 if log else 0


if __name__ == "__main__":
    sys.exit(main())
