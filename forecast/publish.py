"""Build the public delivery bundle for the forecast page.

Run: ``python -m forecast.publish --out build/site``

`nado-waves` is private, so the app surface cannot be served from it and a
published page cannot fetch `data/live/forecast.json` across the repository
boundary. This builds a self-contained bundle that a *public* repository serves
through GitHub Pages — the pattern `nado-waves-log` already uses for the
observer form, which is built from `app/beachlog-observer.html` here and pushed
there as `index.html`.

The bundle:

    index.html      app/forecast.html inside a standalone HTML document
    forecast.json   data/live/forecast.json, thinned to what the page shows
    now.json        data/live/now.json — the observed reading, if there is one
    geometry.html   the model's geometry, drawn by forecast.geomviz from
                    spots.json; linked from the foot of index.html
    info.html       app/info.html: the caveat and each chain's standing-on
                    block; linked beneath geometry.html
    .nojekyll       Pages must serve the files as-is, not run Jekyll over them
    README.md       says what the repository is and where to edit it

`now.json` is optional and is published whenever it exists. It is small and
changes hourly where `forecast.json` changes four times a day, which is why it
is a separate file rather than a key inside one: the hourly job rewrites a few
kilobytes instead of seventy.

**This repository stays the system of record.** The bundle is regenerated from
it every cycle and nothing is ever edited on the far side — the same contract
`nado-waves-log/README.md` states, for the same reason: two copies of a page
that can both be edited is one copy too many.

**Thinning is not lossy here, and that is checked rather than assumed.** The
page offers every third hour in its picker, so publishing 3-hourly data drops
only rows the surface never renders: 208 KB minified becomes 72 KB, over a
connection that is often a phone on the sand. `HOUR_STEP` and the page's own
filter have to agree, and `tests/test_publish.py` pins that they do.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from collector.common import DEFAULT_DATA_DIR

REPO_ROOT = Path(__file__).resolve().parent.parent

PAGE_SOURCE = REPO_ROOT / "app" / "forecast.html"
INFO_SOURCE = REPO_ROOT / "app" / "info.html"

#: Publish every Nth forecast hour. Must match the `lead_h % 3` filter in
#: app/forecast.html — the page renders nothing between these, so anything
#: finer is bytes a phone downloads and never sees.
HOUR_STEP = 3

#: The standalone document wrapper. Taken from the bundle already serving at
#: ptrrdrck.github.io/nado-waves-log so both surfaces are built the same way:
#: `app/*.html` in this repository are fragments that start at <title>, because
#: that is the shape the beachlog pair needs for the test that holds them
#: identical apart from their titles.
#: Where the page looks for its data in the repository, and where it looks in
#: the bundle. The repository layout puts the page in `app/` and the forecast in
#: `data/live/`; the bundle is flat, so the path has to be repointed on the way
#: out or the published page fetches a URL that does not exist and renders
#: nothing. Caught by rendering the bundle rather than by reading it.
REPO_DATA_PATH = "../data/live/forecast.json"
BUNDLE_DATA_PATH = "forecast.json"
REPO_NOW_PATH = "../data/live/now.json"
BUNDLE_NOW_PATH = "now.json"

DOCTYPE = "<!doctype html>"
HEAD = """<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="color-scheme" content="light dark">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="{app_title}">
<style>html{{-webkit-text-size-adjust:100%}}body{{margin:0}}[hidden]{{display:none!important}}img{{max-width:100%}}</style>
</head>
<body>"""
TAIL = "\n</body>\n</html>\n"

README = """# Nado Waves — Coronado forecast

A physically derived swell aperture for the three breaks on Coronado Central
Beach, rebuilt after each GFS-Wave cycle.

**Live: https://ptrrdrck.github.io/nado-waves-forecast/**

This repository is a delivery surface and nothing else. `index.html` is built
from `app/forecast.html` in the private `nado-waves` repository, which holds the
geometry, the transform and the tests, and `forecast.json` is written there by
`forecast/live.py`. `geometry.html` is drawn there from the same geometry file
the forecast reads, by `forecast/geomviz.py`, and `info.html` is built from
`app/info.html`. All three are pushed here by a workflow. **Edit them there** —
anything committed directly to this repository is overwritten by the next cycle.

## What the page shows, and what it does not

It shows how much of the offshore swell at buoy 46232 is aimed through each
break's open window — north, centre and south, which are not one beach: the west
edge of the window is the bearing to the Point Loma tip, and that bearing sweeps
as you walk the sand.

**Nothing has ever measured a wave at these three breaks.** The output is
*physically derived*, never accurate, and carries no error bar because there is
nothing to compute one against. `info.html` states what each tab is standing
on — geometry, model, calibration, observation — and two of those read *none*.

Window energy is the offshore energy aimed at a break. It is **not a wave height
at the beach**: no shoaling, no refraction, no offshore-to-face transfer.

## Why it is separate from the observation log

`nado-waves-log` serves the observer form, and that form never shows a forecast:
an observer who has seen one is not an independent witness, and a series
contaminated that way cannot judge the forecast that shaped it. Keeping the two
on separate sites keeps the forecast off the path an observer walks.

Note that GitHub Pages project sites share one origin, so this is a separation
of paths and of links, not a browser security boundary.
"""


def repoint(fragment: str, *, name: str = PAGE_SOURCE.name) -> str:
    """Point the page at the bundle's flat `forecast.json`."""

    for repo_path in (REPO_DATA_PATH, REPO_NOW_PATH):
        if repo_path not in fragment:
            raise ValueError(
                f"{name} no longer fetches {repo_path!r}. The "
                f"publisher rewrites that path for the flat bundle; if the page "
                f"changed how it loads data, this has to change with it."
            )
    return (fragment
            .replace(REPO_DATA_PATH, BUNDLE_DATA_PATH)
            .replace(REPO_NOW_PATH, BUNDLE_NOW_PATH))


def wrap(fragment: str, *, app_title: str) -> str:
    """Put an `app/` fragment inside a standalone HTML document."""

    return DOCTYPE + "\n" + HEAD.format(app_title=app_title) + "\n" + fragment.rstrip("\n") + TAIL


def thin(forecast: dict, *, step: int = HOUR_STEP) -> dict:
    """Keep every `step`-th forecast hour, by lead time rather than position.

    By `lead_h`, not by index, so a file that is already thinned passes through
    unchanged instead of being thinned again — this runs every cycle and has to
    be idempotent.
    """

    out = dict(forecast)
    out["breaks"] = [
        {**entry, "hours": [h for h in entry["hours"] if h.get("lead_h", 0) % step == 0]}
        for entry in forecast.get("breaks", [])
    ]

    # The tide series is thinned to the hours that survive, by TIMESTAMP rather
    # than by its own position — the two lists are built separately and there is
    # no guarantee they line up. The page looks tide up by timestamp too, so a
    # mismatch here costs bytes rather than correctness; both being keyed the
    # same way is what makes that true.
    kept = {
        h["valid_utc"]
        for entry in out["breaks"]
        for h in entry["hours"]
    }
    out["tide"] = [t for t in forecast.get("tide", []) if t.get("valid_utc") in kept]
    # The buoy series is per hour like the tide, and gets thinned the same way.
    # It was shipping all 169 hours while the page rendered 57, which is the
    # waste this function exists to prevent.
    out["buoy"] = [b for b in forecast.get("buoy", []) if b.get("valid_utc") in kept]
    out["hour_step_h"] = step
    return out


def geometry_page(data_dir: Path = DEFAULT_DATA_DIR) -> str:
    """`app/geometry.html` filled from spots.json, as a standalone document.

    Built every time the bundle is, from the same file the forecast reads, so
    the drawing cannot lag the geometry it draws. It is in BOTH builds for the
    reason the page is (see `build_now_only`): index.html links to it, and a
    link published an hour before its target is a broken link for an hour.
    """

    from . import geomviz

    return wrap(geomviz.render(geomviz.build(data_dir=data_dir)),
                app_title="Coronado aperture")


def info_page(info: Path = INFO_SOURCE) -> str:
    """`app/info.html` as a standalone document, repointed like the page.

    In BOTH builds for the reason `geometry_page` is: index.html links to it,
    and it reads both payloads, so it has to ship wherever either of them does.
    """

    return wrap(repoint(info.read_text(encoding="utf-8"), name=info.name),
                app_title="Nado Waves")


def build(
    out_dir: Path,
    *,
    data_dir: Path = DEFAULT_DATA_DIR,
    page: Path = PAGE_SOURCE,
    step: int = HOUR_STEP,
) -> dict[str, int]:
    """Write the bundle. Returns each file's size in bytes."""

    forecast_path = Path(data_dir) / "live" / "forecast.json"
    if not forecast_path.exists():
        raise FileNotFoundError(
            f"{forecast_path} — run `python -m forecast.live` before publishing"
        )

    forecast = json.loads(forecast_path.read_text(encoding="utf-8"))
    if not forecast.get("breaks"):
        raise ValueError(
            "forecast.json carries no breaks — publishing it would put an empty "
            "page in front of readers. Refusing; check the live build first."
        )

    out_dir = Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    written: dict[str, int] = {}

    index = out_dir / "index.html"
    index.write_text(
        wrap(repoint(page.read_text(encoding="utf-8")), app_title="Nado Waves"),
        encoding="utf-8",
    )
    written["index.html"] = index.stat().st_size

    geometry = out_dir / "geometry.html"
    geometry.write_text(geometry_page(data_dir), encoding="utf-8")
    written["geometry.html"] = geometry.stat().st_size

    info = out_dir / "info.html"
    info.write_text(info_page(), encoding="utf-8")
    written["info.html"] = info.stat().st_size

    payload = out_dir / "forecast.json"
    payload.write_text(
        json.dumps(thin(forecast, step=step), separators=(",", ":")), encoding="utf-8"
    )
    written["forecast.json"] = payload.stat().st_size

    # The observed reading, when there is one. Absent is a normal state: the
    # page falls back to the forecast and says the observation is missing,
    # which is better than publishing a stale "now".
    now_path = Path(data_dir) / "live" / "now.json"
    if now_path.exists():
        payload = out_dir / "now.json"
        payload.write_text(
            json.dumps(json.loads(now_path.read_text(encoding="utf-8")),
                       separators=(",", ":")),
            encoding="utf-8",
        )
        written["now.json"] = payload.stat().st_size

    (out_dir / ".nojekyll").write_text("", encoding="utf-8")
    written[".nojekyll"] = 0

    readme = out_dir / "README.md"
    readme.write_text(README, encoding="utf-8")
    written["README.md"] = readme.stat().st_size

    return written


def build_now_only(
    out_dir: Path, *, data_dir: Path = DEFAULT_DATA_DIR, page: Path = PAGE_SOURCE
) -> dict[str, int]:
    """`now.json` AND the page, for the frequent observed-reading job.

    Not the forecast. That is a 70 KB payload rebuilt from a live NOAA fetch
    four times a day, and copying it every ten minutes would leave it
    byte-identical almost every time. `publish-pages.sh` copies only what it is
    given, so the forecast already in the public repository is left exactly as
    the forecast job last wrote it.

    The PAGE is here for a different reason, learned twice. `index.html` and
    `forecast.json` ship together from the forecast job, and `now.json` ships
    from this one, so a change to the page waited for the next forecast cycle
    while the payload it reads went out immediately. BRIEFING §35 is the first
    time that bit: an older-shaped `now.json` met a newer page. On 2026-09-22 it
    bit the other way round, and the countdown code sat unpublished for a
    quarter of an hour while the `next_expected` it needed was already live.

    Publishing the page from both jobs closes it. It is 45 KB of static HTML
    that git sees as unchanged whenever it has not changed, so the cost of
    including it is a hash comparison.
    """

    source = Path(data_dir) / "live" / "now.json"
    if not source.exists():
        raise FileNotFoundError(f"{source} — run `python -m forecast.now` first")

    out_dir = Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    written: dict[str, int] = {}

    index = out_dir / "index.html"
    index.write_text(
        wrap(repoint(page.read_text(encoding="utf-8")), app_title="Nado Waves"),
        encoding="utf-8",
    )
    written["index.html"] = index.stat().st_size

    geometry = out_dir / "geometry.html"
    geometry.write_text(geometry_page(data_dir), encoding="utf-8")
    written["geometry.html"] = geometry.stat().st_size

    info = out_dir / "info.html"
    info.write_text(info_page(), encoding="utf-8")
    written["info.html"] = info.stat().st_size

    target = out_dir / "now.json"
    target.write_text(
        json.dumps(json.loads(source.read_text(encoding="utf-8")), separators=(",", ":")),
        encoding="utf-8",
    )
    written["now.json"] = target.stat().st_size
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "build" / "site")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--step", type=int, default=HOUR_STEP)
    parser.add_argument("--only-now", action="store_true",
                        help="publish just now.json (the hourly job)")
    args = parser.parse_args(argv)

    try:
        if args.only_now:
            written = build_now_only(args.out, data_dir=args.data_dir)
        else:
            written = build(args.out, data_dir=args.data_dir, step=args.step)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Not published: {exc}")
        return 1

    if args.only_now:
        print(f"Observed reading → {args.out}")
        for name, size in written.items():
            print(f"  {name:16s} {size:>9,} B")
        return 0

    forecast = json.loads((Path(args.data_dir) / "live" / "forecast.json").read_text())
    print(f"Bundle for cycle {forecast.get('cycle_utc')} → {args.out}")
    for name, size in written.items():
        print(f"  {name:16s} {size:>9,} B")
    print(f"\nOne row every {args.step} h, which is what the page renders.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
