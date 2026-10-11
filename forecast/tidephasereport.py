"""Measure the Tide card's phase-line thresholds; reports, never edits.

Run: ``python -m forecast.tidephasereport`` (about two minutes).

Every threshold `forecast.tidephase` uses is read here off 19 years of the
station's own tide (2017-2035, one whole nodal cycle), reconstructed hourly
from NOAA's constants and turned into highs and lows. That is a prediction,
and every claim the phase line makes is about the prediction too: whether
the days it calls spring are the days whose predicted swings are biggest.
Before anything is read, the reconstruction is checked against what CO-OPS
itself predicts for this station (the hourly heights and the hilo turns in
data/tide/).

BRIEFING §41 records the results and why each threshold sits where it does.
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
import sys
from bisect import bisect_left
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import moon
from . import tidephase as tp

START = datetime(2017, 1, 1, tzinfo=timezone.utc)
END = datetime(2036, 1, 1, tzinfo=timezone.utc)


def series(c, start: datetime, end: datetime):
    """Hourly height, twice-daily and once-daily envelopes."""

    times, h, semi, diu = [], [], [], []
    t = start
    while t < end:
        x, s, d = tp.species(c, t)
        times.append(t)
        h.append(x)
        semi.append(s)
        diu.append(d)
        t += timedelta(hours=1)
    return times, h, semi, diu


def turns_from(times, h):
    """Highs and lows: each hourly extreme refined by the parabola through
    it and its neighbours."""

    out = []
    for i in range(1, len(h) - 1):
        a, b, d = h[i - 1], h[i], h[i + 1]
        if (b > a and b >= d) or (b < a and b <= d):
            den = a - 2 * b + d
            x = 0.5 * (a - d) / den if den else 0.0
            out.append((times[i] + timedelta(hours=x), b - 0.25 * (a - d) * x,
                        "high" if b > a else "low"))
    return out


def check_against_coops(c, data_dir: Path) -> dict:
    tide = Path(data_dir) / "tide"
    pred = {r["time_utc"]: float(r["height_m"]) for r in csv.DictReader(open(tide / f"{tp.STATION}_predicted.csv"))}
    diffs = [v - tp.height(c, tp._parse(k)) for k, v in pred.items()]
    msl = statistics.fmean(diffs)
    rms = statistics.pstdev(diffs)
    real = {}
    for r in csv.DictReader(open(tide / f"{tp.STATION}_turns.csv")):
        real[r["time_utc"]] = (float(r["height_m"]), r["event"])
    times = sorted(real)
    lo, hi = tp._parse(times[0]) - timedelta(hours=6), tp._parse(times[-1]) + timedelta(hours=6)
    t, hh = [], []
    x = lo
    while x <= hi:
        t.append(x)
        hh.append(tp.height(c, x))
        x += timedelta(hours=1)
    mine = turns_from(t, hh)
    dt, dh = [], []
    for k in times:
        when = tp._parse(k)
        best = min(mine, key=lambda m: abs(m[0] - when))
        if best[2] == real[k][1] and abs(best[0] - when) < timedelta(hours=3):
            dt.append(abs(best[0] - when) / timedelta(minutes=1))
            dh.append(abs(best[1] + msl - real[k][0]))
    return {"hours": len(diffs), "rms_cm": 100 * rms, "turns": len(dt), "of": len(times),
            "turn_min_mean": statistics.fmean(dt), "turn_min_max": max(dt),
            "turn_cm_mean": 100 * statistics.fmean(dh), "turn_cm_max": 100 * max(dh)}


def by_day(turns):
    """Per local day: the biggest swing starting in it, its highs, its lows."""

    days = defaultdict(lambda: {"swings": [], "highs": [], "lows": []})
    for a, b in zip(turns, turns[1:]):
        if a[2] != b[2]:
            days[tp._local_day(a[0])]["swings"].append(abs(a[1] - b[1]))
    for t, v, ev in turns:
        days[tp._local_day(t)]["highs" if ev == "high" else "lows"].append(v)
    return days


def noon(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 12, tzinfo=tp.LOCAL_TZ).astimezone(timezone.utc)


def nearest_gap_h(sorted_times, when: datetime) -> float:
    i = bisect_left(sorted_times, when)
    best = math.inf
    for j in (i - 1, i):
        if 0 <= j < len(sorted_times):
            best = min(best, abs(sorted_times[j] - when) / timedelta(hours=1))
    return best


def quantile(values, q):
    v = sorted(values)
    return v[min(len(v) - 1, max(0, int(round(q * (len(v) - 1)))))]


def measure(c, start: datetime = START, end: datetime = END) -> tuple[list[str], dict]:
    """Every sweep below, as printed lines and as the figures the test
    re-checks the thresholds against."""

    lines: list[str] = []
    fig: dict = {}

    def say(*parts):
        lines.append(" ".join(str(p) for p in parts))

    years = (end - start) / timedelta(days=365.2425)
    times, h, semi, diu = series(c, start, end)
    turns = turns_from(times, h)
    days = by_day(turns)
    keys = sorted(d for d in days if days[d]["swings"])[1:-1]
    biggest = {d: max(days[d]["swings"]) for d in keys}
    say(f"\n{years:.0f} years from {start:%Y-%m-%d}: {len(turns)} turns, {len(keys)} days")

    # Spring and neap extremes of the twice-daily envelope.
    springs, neaps = [], []
    for i in range(1, len(semi) - 1):
        if semi[i] > semi[i - 1] and semi[i] >= semi[i + 1]:
            springs.append(times[i])
        elif semi[i] < semi[i - 1] and semi[i] <= semi[i + 1]:
            neaps.append(times[i])
    say(f"{len(springs)} springs, {len(neaps)} neaps")

    # ---- PHASE_WINDOW_H: does the label pick the fortnight's biggest swings?
    # Truth: a day is a spring day when its biggest swing is in the top third
    # of the 15 days centred on it, a neap day in the bottom third.
    index = {d: i for i, d in enumerate(keys)}
    truth = {}
    for d in keys:
        i = index[d]
        if i < 7 or i >= len(keys) - 7:
            continue
        window = sorted(biggest[keys[j]] for j in range(i - 7, i + 8))
        rank = window.index(biggest[d])
        truth[d] = "spring" if rank >= 10 else "neap" if rank < 5 else "mid"
    say("\nPHASE_WINDOW_H: agreement with the top / bottom third of each 15 days")
    say("  W h   agree   spring days right   neap days right")
    best_w = None
    for w in sorted(set(range(24, 109, 12)) | {tp.PHASE_WINDOW_H}):
        right = n = sr = sn = ss = nn = 0
        for d, want in truth.items():
            t = noon(d)
            gs, gn = nearest_gap_h(springs, t), nearest_gap_h(neaps, t)
            got = "spring" if gs <= w and gs <= gn else "neap" if gn <= w else "mid"
            n += 1
            right += got == want
            if got == "spring":
                ss += 1
                sr += want == "spring"
            if got == "neap":
                nn += 1
                sn += want == "neap"
        rate = right / n
        fig.setdefault("phase_agree", {})[w] = rate
        say(f"  {w:3d}   {100 * rate:5.1f}%   {100 * sr / max(ss, 1):5.1f}% of {ss:5d}       {100 * sn / max(nn, 1):5.1f}% of {nn:5d}")
        if best_w is None or rate > best_w[1]:
            best_w = (w, rate)
    say(f"  best: {best_w[0]} h ({100 * best_w[1]:.1f}%)")
    fig["phase_best_h"] = best_w[0]

    # ---- Moon phase to spring / neap: how far apart can they be?
    events = moon.events(start - timedelta(days=20), end + timedelta(days=20))
    syz = sorted(t for n, t in events if n in ("new moon", "full moon"))
    qtr = sorted(t for n, t in events if n in ("first quarter", "last quarter"))
    gs = [nearest_gap_h(syz, t) for t in springs]
    gq = [nearest_gap_h(qtr, t) for t in neaps]
    fig["moon_gap_max_h"] = max(max(gs), max(gq))
    say(f"\nMoon phase to spring: median {statistics.median(gs):.0f} h, max {max(gs):.0f} h; "
          f"quarter to neap: median {statistics.median(gq):.0f} h, max {max(gq):.0f} h")

    # ---- Declination: which days have a much bigger and a nearly even pair?
    two_highs = {d: abs(days[d]["highs"][0] - days[d]["highs"][1]) for d in keys if len(days[d]["highs"]) == 2}
    two_lows = {d: abs(days[d]["lows"][0] - days[d]["lows"][1]) for d in keys if len(days[d]["lows"]) == 2}
    both = [d for d in two_highs if d in two_lows]
    ineq = {d: max(two_highs[d], two_lows[d]) for d in both}
    felt = {d: tp.felt_declination(c, noon(d)) for d in both}
    q25, q75 = quantile(list(ineq.values()), 0.25), quantile(list(ineq.values()), 0.75)
    hq25 = quantile(list(two_highs.values()), 0.25)
    say(f"\nDeclination: {len(both)} days with two highs and two lows. Larger of the two "
          f"inequalities: quartiles {q25:.2f} / {q75:.2f} m; the highs' alone, lower quartile {hq25:.2f} m")
    for name, series_ in (("highs", two_highs), ("lows", two_lows), ("larger", ineq)):
        xs = [abs(felt[d]) for d in both]
        ys = [series_[d] for d in both]
        say(f"  |declination| against the {name}' inequality: r = {statistics.correlation(xs, ys):+.2f}")
    say("  equator threshold: share of days within it whose larger inequality is in the bottom quartile")
    for deg in sorted({3, 4, 5, 6, 7, 8, 10, 12, tp.DEC_EQUATOR_DEG}):
        sel = [d for d in both if abs(felt[d]) <= deg]
        hit = sum(ineq[d] <= q25 for d in sel)
        fig.setdefault("equator_by_deg", {})[deg] = hit / max(len(sel), 1)
        say(f"    |dec| <= {deg:2d}: {100 * hit / max(len(sel), 1):5.1f}% of {len(sel)}")
    say("  far threshold: share of days past it whose larger inequality is in the top quartile")
    for deg in sorted({16, 18, 20, 22, 24, 26, tp.DEC_FAR_DEG}):
        sel = [d for d in both if abs(felt[d]) >= deg]
        hit = sum(ineq[d] >= q75 for d in sel)
        fig.setdefault("far_by_deg", {})[deg] = hit / max(len(sel), 1)
        say(f"    |dec| >= {deg:2d}: {100 * hit / max(len(sel), 1):5.1f}% of {len(sel)}")

    # Growing unequal / evening out: does tomorrow's inequality move the way
    # the felt declination says?
    right = n = 0
    for d in both:
        nxt = d + timedelta(days=1)
        a = abs(felt[d])
        if nxt not in ineq:
            continue
        if a <= tp.DEC_EQUATOR_DEG or a >= tp.DEC_FAR_DEG:
            continue
        away = abs(tp.felt_declination(c, noon(d) + timedelta(hours=6))) > a
        n += 1
        right += (ineq[nxt] > ineq[d]) == away
    fig["heading_right"] = right / max(n, 1)
    fig["highs_r"], fig["lows_r"] = (statistics.correlation([abs(felt[d]) for d in both], [x[d] for d in both])
                                     for x in (two_highs, two_lows))
    say(f"  heading away / toward the equator: tomorrow's inequality moves that way on "
          f"{100 * right / max(n, 1):.1f}% of {n} days between the thresholds")

    # ---- DISTANCE_WINDOW_H: is a spring near perigee bigger, a neap near apogee smaller?
    peri = sorted(t for n, t in events if n == "perigee")
    apo = sorted(t for n, t in events if n == "apogee")

    def size_at(t):
        d = tp._local_day(t)
        near = [biggest[d + timedelta(days=k)] for k in (-1, 0, 1) if d + timedelta(days=k) in biggest]
        return max(near) if near else None

    def smallest_at(t):
        d = tp._local_day(t)
        near = [biggest[d + timedelta(days=k)] for k in (-1, 0, 1) if d + timedelta(days=k) in biggest]
        return min(near) if near else None

    sp = [(t, size_at(t)) for t in springs if size_at(t) is not None]
    ne = [(t, smallest_at(t)) for t in neaps if smallest_at(t) is not None]
    sp_med = statistics.median(v for _, v in sp)
    ne_med = statistics.median(v for _, v in ne)
    say(f"\nDistance: {len(sp)} springs (median biggest swing {sp_med:.2f} m), {len(ne)} neaps "
          f"(median {ne_med:.2f} m). Share above / below the median by hours from the event:")
    say("  within h   springs near perigee bigger   springs near apogee smaller   neaps near apogee smaller   neaps near perigee bigger")
    for w in sorted({24, 48, 72, 96, 120, 144, tp.DISTANCE_WINDOW_H}):
        rates = []

        def share(pairs, evs, above, med):
            sel = [v for t, v in pairs if nearest_gap_h(evs, t) <= w]
            ok = sum((v > med) if above else (v < med) for v in sel)
            rates.append(ok / max(len(sel), 1))
            return f"{100 * ok / max(len(sel), 1):5.1f}% of {len(sel):3d}"
        say(f"  {w:5d}      {share(sp, peri, True, sp_med)}                {share(sp, apo, False, sp_med)}"
              f"                {share(ne, apo, False, ne_med)}              {share(ne, peri, True, ne_med)}")
        fig.setdefault("distance_by_h", {})[w] = min(rates)

    # ---- What the Next entry says at a spring or neap, by where the Moon is.
    singles = {d for d in keys if len(days[d]["highs"]) == 1 and len(days[d]["lows"]) == 1}
    say("\nAt each spring / neap, by the felt declination there (tidephase thresholds):")
    say("  kind    Moon       n    median biggest swing (±1 d)   larger inequality (±1 d)   a single-pair day or a swing under SMALL_SWING_M (±2 d)")
    for kind, evs in (("spring", springs), ("neap", neaps)):
        groups = defaultdict(list)
        for t in evs:
            groups[tp.declination_state(c, t)["state"]].append(t)
        for state in ("equator", "toward", "away", "far"):
            sel = groups.get(state, [])
            if not sel:
                continue
            sizes, ineqs, vanish = [], [], 0
            for t in sel:
                d0 = tp._local_day(t)
                near1 = [d0 + timedelta(days=k) for k in (-1, 0, 1)]
                near2 = [d0 + timedelta(days=k) for k in range(-tp.EVIDENCE_DAYS, tp.EVIDENCE_DAYS + 1)]
                b = [biggest[x] for x in near1 if x in biggest]
                q = [ineq[x] for x in near1 if x in ineq]
                if b:
                    sizes.append(max(b) if kind == "spring" else min(b))
                if q:
                    ineqs.append(max(q) if state == "far" else min(q))
                small = any(x in singles or (x in days and any(v < tp.SMALL_SWING_M for v in days[x]["swings"]))
                            for x in near2)
                vanish += small
            fig.setdefault("vanish", {})[(kind, state)] = vanish / len(sel)
            fig.setdefault("sizes", {})[(kind, state)] = statistics.median(sizes)
            say(f"  {kind:7s} {state:8s} {len(sel):4d}    {statistics.median(sizes):.2f} m"
                  f"                       {statistics.median(ineqs):.2f} m"
                  f"                     {100 * vanish / len(sel):5.1f}%")

    # ---- SMALL_SWING_M: small swings belong to neaps.
    swings = [(a[0], abs(a[1] - b[1])) for a, b in zip(turns, turns[1:]) if a[2] != b[2]]
    say(f"\nSmall swings: {len(swings)} swings, median {statistics.median(v for _, v in swings):.2f} m. "
          f"Share within {tp.EVIDENCE_DAYS} days of a neap:")
    for x in sorted({0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, tp.SMALL_SWING_M}):
        sel = [t for t, v in swings if v < x]
        near = sum(nearest_gap_h(neaps, t) <= 24 * tp.EVIDENCE_DAYS for t in sel)
        fig.setdefault("small_by_m", {})[x] = near / max(len(sel), 1)
        say(f"  under {x:.2f} m ({x / 0.3048:.1f} ft): {len(sel):5d} swings "
              f"({len(sel) / years:5.1f} a year), {100 * near / max(len(sel), 1):5.1f}% near a neap")

    # ---- SIMILAR_SHARE: does the envelope say which week's extremes are bigger?
    stamps = times

    def env_at(t):
        i = bisect_left(stamps, t)
        i = min(max(i, 0), len(stamps) - 1)
        return semi[i] + diu[i]

    cycles = sorted([(t, "spring") for t in springs] + [(t, "neap") for t in neaps])
    ctimes = [t for t, _ in cycles]
    pairs = []
    for d in keys[10:-30:3]:
        at = noon(d)
        i = bisect_left(ctimes, at + timedelta(hours=tp.PHASE_WINDOW_H))
        if i + 1 >= len(cycles):
            continue
        t_after = cycles[i + 1][0]
        week = [biggest[x] for x in (d + timedelta(days=k) for k in range(-3, 4)) if x in biggest]
        then = [biggest[x] for x in (tp._local_day(t_after) + timedelta(days=k) for k in (-1, 0, 1)) if x in biggest]
        if not week or not then:
            continue
        pairs.append((env_at(t_after) / env_at(at) - 1, max(then) - max(week)))
    say(f"\nLarger / smaller extremes: {len(pairs)} days, the envelope's share against the biggest "
          "swing within a day of the After date less this week's (±3 days)")
    for s in sorted({0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, tp.SIMILAR_SHARE}):
        sel = [(a, b) for a, b in pairs if abs(a) > s]
        ok = sum((a > 0) == (b > 0) for a, b in sel)
        fig.setdefault("similar_by_share", {})[s] = ok / max(len(sel), 1)
        say(f"  |share| > {s:.2f}: says larger or smaller on {100 * len(sel) / len(pairs):5.1f}% of days, "
              f"right on {100 * ok / max(len(sel), 1):5.1f}%")
    return lines, fig


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=tp.DEFAULT_DATA_DIR)
    parser.add_argument("--years", type=int, default=19)
    args = parser.parse_args(argv)

    c = tp.load(args.data_dir)
    if c is None:
        print("No harmonic constants stored; run collector.harcon on Actions.")
        return 1
    end = START + timedelta(days=round(365.2425 * args.years))

    print(f"Constants: {len(c.constituents)} constituents, analysis {c.analysis}, fetched {c.fetched_utc}")
    print(f"Form factor {tp.form_factor(c):.3f}; phase age {tp.phase_age_h(c):+.1f} h, "
          f"diurnal age {tp.diurnal_age_h(c):+.1f} h, parallax age {tp.parallax_age_h(c):+.1f} h")
    chk = check_against_coops(c, args.data_dir)
    print(f"Against CO-OPS: {chk['hours']} hourly heights, {chk['rms_cm']:.2f} cm RMS; "
          f"{chk['turns']} of {chk['of']} turns matched, time {chk['turn_min_mean']:.1f} min mean / "
          f"{chk['turn_min_max']:.1f} max, height {chk['turn_cm_mean']:.1f} cm mean / {chk['turn_cm_max']:.1f} max")

    lines, _ = measure(c, START, end)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
