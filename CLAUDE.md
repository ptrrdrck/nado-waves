# CLAUDE.md

Read `BRIEFING.md` before proposing or writing anything. It is three years of
measured findings, four falsified hypotheses and several expensive mistakes,
carried over from the project this one grew out of. Most questions worth asking
here have already been answered there, some of them the hard way.

**It is not in this repository.** This repo is public; the briefing lives in
the private sibling `ptrrdrck/nado-waves-notes`, and the `BRIEFING §n`
citations throughout this codebase point into it. If you are a Claude session
and cannot see it, say so and work with reduced confidence — do not re-derive
a finding it already records, and do not assume a rule here is arbitrary
because its reasoning is not in front of you. Attaching that repository to the
session is the fix, not guessing.

## Working with the owner

- **Ask before the scope changes.** Do what was asked, where it was asked.
  When doing it well would mean touching anything beyond that — another
  card, another tab, the docs page, a page-wide helper, a format used
  elsewhere — stop and ask first, saying what else would change and why.
  A word like "everywhere" in a request about one feature means everywhere
  in that feature until the owner says otherwise (owner's rule, 2026-10-18,
  after "use 15 Oct format everywhere" in a Briefing request was taken
  page-wide).

## What this is

**An expert surf forecaster for three beaches on the Coronado peninsula:**
Coronado Central Beach, Breakers Beach (NASNI), and Gator Beach (NAB Coronado).

One offshore buoy, one blocking geometry, **three different answers**. The
premise is that published forecasts are unreliable at exactly these beaches for
a specific, measurable, geometric reason, and that a local model that respects
the geometry can do better.

It is not a game. A gamified feature may be added later for fun; it is not the
product and nothing is designed around it.

## The rule that governs everything

**There is no wave observation at Coronado Central, Breakers, or Gator.**
Nothing measures the thing this project forecasts. That makes every accuracy
claim unfalsifiable until a verification series exists, and pretending otherwise
is the single easiest way to ruin the project.

- **Never state an accuracy figure for a beach without naming the verification
  series it was measured against.** No RMSE, no "within a foot", no confidence
  band, unless something observed it.
- Until a verification series exists, the output is **"physically derived"**,
  never "accurate". That distinction belongs in the UI, not only the README.
- **Verification must be an observation, not another model.** CDIP MOP is a
  model. It is a valuable cross-check and it is not truth.
- A band fitted on history is not automatically honest: the predecessor project
  measured one that under-covered by fifteen points at long lead, and making it
  proportional to forecast size did not fix it. Bands are earned. See
  BRIEFING §5.

**Logged human observation at the beach is the intended primary verification** —
observer, time and method recorded, stored as its own series, never silently
blended into the forecast it judges. It is what every operational surf
forecaster actually verifies against, Surfline included.

- **The log never shows a forecast, and never will.** An observer who has seen
  one is not an independent witness, and a series contaminated that way cannot
  judge the forecast that shaped it. That is structural, not a matter of
  discipline. `forecast_seen` flags the rows where it happened anyway.
- **The unit is the session, not the day.** One observer, one tide, two or three
  breaks, half an hour apart: the comparison cancels nearly everything that
  makes absolute height unreliable, and the differential is what this project
  actually claims.

## Non-negotiables

- **Never infer, interpolate, or substitute a missing observation.** A gap is a
  gap, in the archive and in verification alike. A rehearsal entry carries an
  explicit `is_test` flag decided at entry; nothing re-derives it from the note,
  because "contest" contains "test" and BRIEFING §8 lists that class of fault
  first. Historical NDBC files use
  numeric sentinels (`999.0`, `99.0`, `9999.0`), not `MM` — never backfill
  without `collector.ndbc.is_missing` or you will store 999.0 as a wave height.
  NDBC's real-time SPECTRAL files do the same in their direction and moment
  bins (46047 and 46086, every row): `probe_spectra.mask_sentinels` stores
  those as empty cells, and `transform.load_spectra` reads a 999 there as
  missing too. **A record whose energetic bin has no direction is dropped
  whole** (`transform.unplaceable_bin`): read as 999 it multiplied that bin's
  energy ~636× — 46232 read 21.9 m at 2026-08-26T00Z — and read as NaN it
  would silently vanish. A bin with no energy and no direction is harmless
  (BRIEFING §33–§34).
- **Never commit secrets**, even to a private repo.
- **Data files are tracked, not ignored** — do not add `data/` to `.gitignore`.
  `data/historical/` is three years the 45-day NDBC window can no longer serve.
- **Coordinates are either verified or flagged, and that is two claims.**
  `forecast/spots.json` tracks `position_verified` and `shoreline_verified`
  separately, because measurement says they govern different things: **position
  sets the open window; the shoreline chord does not.** Rotating a chord ±10°
  moves the swell-side window by exactly zero — both its edges are
  blocker-derived, so the seaward half-plane clip never binds — while moving a
  break 500 m costs Coronado ~4.4°. The chord still sets the normal, which is
  what the "shadow edge one degree off the normal" figure and all future wind
  and refraction work are computed from. `tests/test_geometry.py` pins both
  halves, invariance and its control.
- **Coronado's three breaks are digitised; Breakers and Gator are not.**
  Scoped out by decision, not because their estimates are good. Any claim about
  those two is still standing on guessed coordinates.
- **If it is gamified later**, the predecessor's rules return in full: no real
  money, no entry fees, prizes or wagering, no play-money tokens or virtual
  currency, points and streaks only.

## Working efficiently

- **CLAUDE.md holds lasting rules only.** Dated reasons ("owner's call,
  2026-…") and measurements go in the design doc (`docs/design/`) and the
  commit message, never here. Editing this file mid-session re-sends all of it.
- **Read the design doc before working in its area.** Each rule below points
  to one; the doc holds the full history, measurements and owner's calls.
- **Sessions.** When a PR has merged and the next request is unrelated, or the
  conversation has run long, say so and suggest a new session. Give a
  ready-to-paste carryover prompt (task, context, where things are, what's
  open), and update `docs/handoff.md` before stopping.
- **Confirm before building.** For a request with several items, or one open
  to more than one reading, restate each item in a line with how you'll
  approach it, and wait for a yes. Say when items span different areas and
  suggest grouping them by area into separate sessions.
- **Match the model to the task.** Say when a task is routine enough for a
  lighter model or effort, and when it needs the strongest setting
  (diagnosis, design, architecture).
- **Keep tool output small**: narrow queries, small page sizes, grep or tail
  logs. Verify rendering with measurements; look at one screenshot at the
  end, not one per round.
- **Reproduce a bug before fixing it.** When it shows only on a device the
  session can't run (the owner's iPhone / WebKit), build a cheap diagnostic
  first (e.g. a test page that paints the suspected cause red) and confirm
  the cause before changing code.
- **Wait for CI** (the Tests workflow) on a PR before merging it. Tests skips
  pushes that change only `*.md`; dispatch it by hand for those.

## Build order

1. **Beach geometry** — done, `forecast/geometry.py`. Every coordinate the
   Coronado aperture uses comes from NOAA's ENC, except where along the coast
   each break sits, South Coronado's south-east tip, North Coronado and the
   Baja coast (imagery: the chart rounds the tip off, draws North Coronado
   off where it stands and puts that coast out to sea). The islands are land
   in the seabed from their imaged outlines (`data/bathymetry/islands.json`).
   → `docs/design/geometry.md`
2. **A verification series** — built and empty, `collector/beachlog.py` →
   `data/beach_log/`. Blocks every accuracy CLAIM, not construction; it
   verifies ordinal and differential claims, not heights.
   → `docs/observation_log.md`, `docs/design/chain.md`
3. **The transform** — `forecast/transform.py`; spectra archived by
   `collector/spectra.py` from Actions, never a session. Integrate the
   spectrum; never a binary blocker test against one `MWD`. No other station
   can stand in for 46232. → `docs/design/chain.md`
3a. **Nearshore and surf zone** — shipped. `forecast/raytrace.py` (precompute)
   → `data/nearshore/`, carried by `forecast/nearshore.py`, then
   `forecast/surfzone.py`. The number on every break card is the BREAKING
   height, a significant height, labelled so. Physics, unverified.
   → `docs/design/chain.md`
4. **The forecast** — `forecast/live.py`: GFS-Wave's own directional spectrum
   at 46232 (`collector/wavespec.py`), partitions as fallback, `wave_source`
   saying which. → `docs/design/chain.md`
5. **Calibration and honest bands** — `forecast/modelbias.py`,
   `exposurebias.py`, `ensemble.py` report and never edit. Never correct
   GFS-Wave at the buoy and carry it to the breaks. The Ensemble band is drawn
   only beside its measured coverage. "Calibration" is reserved for the beach
   log. → `docs/design/chain.md`
6. **App surface** — `app/forecast.html` + `app/docs.html`, published by
   `forecast/publish.py` to the public `nado-waves-forecast`; this repo is the
   system of record. Two tabs are two evidence chains: "LIVE" only
   measurements (`now.json`), Forecast only a model (`forecast.json`).
   `tests/test_app_surface.py` enforces the vocabulary. Coronado's three
   breaks only. → `docs/design/app_surface.md`, `buoys.md`, `map.md`,
   `briefing.md`, `origin.md`, `tide_wind_sun.md`

## Infrastructure

All in `docs/design/infrastructure.md` unless noted.

- Collection is a scheduled GitHub Actions workflow committing per-station
  files back here, with a keepalive.
- GitHub's cron is throttled; frequency is not a lever. Collection is driven
  from outside by `repository_dispatch`, the cron a backstop
  (`docs/collection_trigger.md`).
- A countdown is three real events (publish, fetchable, next collection),
  never intervals added to the reading (`forecast/now.py`).
- A source's lag takes two numbers: typical (countdown) and worst (red).
- Past `STALE_HOURS` a LIVE card's numbers go grey, each card by its own source.
- The cadence on screen must match the trigger: `EXTERNAL_TRIGGER_CRON` is
  pinned by test; changing cron-job.org without it is uncaught.
- 46232's spectra jitter in publish time; the trigger's phase goes to KNZY.
- Keep the 48 h staleness alert, spectra checked file by file.
- Pages caches 10 min: every payload fetch carries `?v=` and `no-store`.
- Session egress is policy-controlled: a 403 at CONNECT is a denial; report
  the host, never route around it.
- Shark Lab's ERDDAP is a nightly copy with gaps and duplicate rows: re-read a
  trailing window, keep each reading once, never fill a gap.
- The county's water site is OutSystems: read every collection; refusals come
  inside HTTP 200, so read the body.
- A 404 can change meaning; check before believing it.
- Retry what a build loses for its whole life, not what the next collection
  re-fetches; never a 404 or a refused tunnel.
- Production workflows run on bare Python (`tests/test_workflow_runtime.py`);
  a run that did not publish is red.
- A queued single-writer job checks out the branch's tip.
- A rejected push of an append-only log re-appends, never rebases; the
  collectors' rebase loops are safe only because each file has one writer.
- `data/series/` is derived and tracked, rebuilt only by series-archive.yml,
  never mixed with another chain. `data/live/` is gitignored on purpose.
- A total does not validate a mapping; check a located quantity.
- A test reading `data/` must not be quadratic in it; check `--durations`.
- Check whether history is actually unrecoverable before an "archive it now" job.

## Design rules that are easy to erode

Geometry (`docs/design/geometry.md`):
- Three beaches are not one beach, and Coronado is not one beach: never one
  number for "Coronado".
- The Point Loma tip is a charted outline, taken per break; never one point.
- The Coronado Islands are two islands and not a switch: never a binary test,
  never merged into one blocker.
- Publish the swell-side window, never the raw open arcs; keep the guard.
- The south window is real; the Baja coast is a tangent.
- The buoy does not share the beach's geometry; skipping the aperture
  delivers swell that cannot arrive.
- A station earns its place by geometry (`forecast/siting.py`), never by
  being nearby; `stations.json` is a collection list. 46232 has no substitute.
- Never type a buoy coordinate (`collector/metadata.py`).
- The shore normal is the highest-leverage input to the wind reading; a
  normal belongs to a chord (state its length); past a few hundred metres a
  circular window is not a chord; waterline and depth-contour normals are two
  claims.

Chain (`docs/design/chain.md`):
- Bulletin direction is TOWARD, NDBC `MWD` is FROM; `collector.gfswave` flips
  once. Do not flip again.
- 46232 is the sea after the Channel Islands; never "fix" its direction
  toward 46047's.
- "At the buoy" is `transform.at_buoy`, never `through(spectrum, spot, [])`.
- The leading train differs between buoy and beach: list trains, split by
  period then direction, divide a break's row two buoy trains carried;
  heights never change, only rows.
- Wind sea is the wind's call (wave age), never the period's.
- The seabed transform is physics, never "calibration".
- The transfer tables stop at 5 m; moving `raytrace.H_REF` means rebuilding
  tables and profiles.
- The breaking height is a significant height, not a face height.

Wind, tide and sun (`docs/design/tide_wind_sun.md`):
- Hoist the measurement, keep the interpretation: offshore/onshore is per
  break; on Forecast it comes from the local NWS wind, never the model's.
- The tide's direction is read off the next turn, never differenced.
- Fetch CO-OPS's turns (`hilo`); never find them in the hourly file, no fallback.
- The LIVE tab's one modelled number, the tide's next turn, is labelled
  `predicted` everywhere.
- The LIVE tide rate is the last 30 minutes, never "now".
- 9410170 is inside the bay: the card shows the open coast; breaking uses
  the gauge's raw reading.
- Wind and tide are not optional; tide predictions span the whole forecast
  window at both ends.

App (`docs/design/app_surface.md`):
- Imperial by default, metric in brackets in "Both"; every number through
  `dual` / `dualText`; nothing upstream of a display converts.
- The line under a past forecast hour says when it was observed, never "what
  happened"; no forecast-minus-observed figure on screen.
- **Say what the forecast is standing on.** Geometry, model, calibration and
  observation are four different confidence levels, and the reader is entitled
  to know which one they are looking at.
- **Measure before claiming.** Every strong claim in BRIEFING has a number
  behind it, and four plausible ones were killed by their own tests. Write the
  test that could falsify the idea before building on it.

## Layout

Full map: `docs/design/layout.md`.

    collector/   fetch and archive: NDBC, GFS/GEFS-Wave, KNZY, tide, NHC,
                 NWS alerts, Shark Lab, county water, bathymetry, shoreline,
                 the beach log. Actions only for most network sources.
    forecast/    geometry + siting; transform, raytrace (precompute),
                 nearshore, surfzone; live (Forecast) and now (LIVE) and
                 their payload builders (series, measured, windtide, buoys,
                 rose, origin*, briefing, alerts, fill, mapdata, seabedvector);
                 reports that never edit (modelbias, exposurebias, ensemble,
                 trainsplit, trainmerge, windsea, …); publish.
    app/         forecast.html (the page), docs.html (its one link),
                 beachlog*.html (the log), vendor/ (MapLibre).
    data/        tracked archives (historical, spectra, wind, tide, alerts,
                 briefings, series, forecast_log, beach_log, …); data/live/
                 derived and gitignored.
    docs/        reports and wording; docs/design/ the full design history;
                 docs/handoff.md the open backlog.
    tests/       the suite, run by the Tests workflow (`-n auto`).

## Success metric

**Beat the published forecasts at these three beaches, measured against a real
verification series, and be honest about the error bars.** Until that series
exists there is no success metric — only a model nobody has checked.
