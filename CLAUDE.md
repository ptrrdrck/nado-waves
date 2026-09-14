# CLAUDE.md

Read `BRIEFING.md` before proposing or writing anything. It is three years of
measured findings, four falsified hypotheses and several expensive mistakes,
carried over from the project this one grew out of. Most questions worth asking
here have already been answered there, some of them the hard way.

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

## Build order

1. **Beach geometry** — done, `forecast/geometry.py`. Which bearings reach each
   beach at all, from coordinates alone. Coronado's three breaks digitised
   2026-09-14.
2. **A verification series. This blocks every accuracy CLAIM; it does not block
   construction.** BRIEFING §7 lists the candidates. It is also the only item
   here whose cost is wall-clock rather than work — a log started today is thin
   for months — so it starts first and runs alongside the rest, rather than
   being finished before anything else begins.
   **Built, and empty: `collector/beachlog.py` → `data/beach_log/`.** Design and
   reasoning in `docs/observation_log.md`. It verifies ordinal and differential
   claims, not heights — face height and Hs are different quantities and the
   transfer between them is unfitted. `forecast/beachverify.py` tests it against
   the geometry and carries the control: **Coronado's two window edges predict
   opposite orderings**, so a fixed bias agrees on one and contradicts the
   other, while a real aperture effect flips. Agreement on one edge alone is
   not evidence.
3. **The transform.** Offshore spectrum at 46232 → energy that survives the
   beach's window. **Unblocked: the directional spectra are reachable and
   complete** — 64 bins, 0.0250–0.5800 Hz, agreeing across all five files,
   `r1`/`r2` already normalised (BRIEFING §7). Re-probe with the
   `Probe NDBC directional spectra` workflow, never from a session — an
   interactive session cannot see the host and a runner can.
   **Caveat: 46232 has been dark since 2026-09-01.** The anchor buoy for every
   transform here is not currently reporting anything to transform.
4. **The forecast.** GFS-Wave partitions at 46232 through the transform.
5. **Calibration and honest bands**, reusing `forecast/verify.py` and
   `forecast/residual.py` against the verification series.
6. **App surface**, which states which of the above it is standing on.

## Infrastructure

- The collector runs as a **scheduled GitHub Actions workflow**, not a local
  cron and not a VPS. It must run whether or not a dev machine is on, and it is
  unaffected by what an interactive Claude session can reach.
- Observations are **committed back into this repository** as per-station files.
- **Wire in a keepalive action.** GitHub disables scheduled workflows after 60
  days of repository inactivity, and the workflow's own bot commits do not
  reliably reset that timer.
- **Keep the staleness alert** — no new observation in 48 hours, notify. A
  silently dead collector loses days that cannot be recovered. **It did not
  visibly fire for 46232's outage from 2026-09-01**, which is unexplained and
  worth chasing before trusting it.
- **Egress from a Claude session is policy-controlled and changes mid-session.**
  A 403 at CONNECT is a denial, not throttling: check
  `$HTTPS_PROXY/__agentproxy/status`, report the blocked host, do not route
  around it. See `collector/probe_mop.py:DENIAL_NOTE` and BRIEFING §8.
- Before writing an "archive it now, history is unrecoverable" job, **check
  whether the history is actually unrecoverable.** It was for Open-Meteo. It was
  not for GFS-Wave, whose every cycle since 2021-03 sits in the NOAA Open Data
  bucket — which turned a six-month wait into an afternoon.

## Layout

    collector/          data pipeline: NDBC archiving, revisions, station
                        status, historical backfill, GFS-Wave bulletins,
                        probe_spectra.py (are directional spectra reachable?),
                        beachlog.py + beachlog_import.py (the observation log)
    app/beachlog.html   the phone form, owner build (shared store)
    app/beachlog-observer.html  same file, observer build — no sign-in, entries
                        stay on the phone and are handed back as text. The two
                        differ only in <title>; a test enforces it. The repo CSV
                        stays the system of record for both.
    forecast/
      geometry.py       which bearings reach each beach          [built]
      spots.json        breaks and blockers    [Coronado digitised; others not]
      swell.py          great circles, bearings, group velocity
      stats.py          load_column, least_squares, rmse, circular means
      dispersion.py     swell-arrival detection and the 1/T fit
      forensics.py      read a swell's origin off the buoy record
      verify.py         bias, RMSE, scatter index, calibration, band coverage
      residual.py       is the remaining error recoverable? (it was not, before)
      beachverify.py    does the log agree with the geometry, and the control
    data/beach_log/     the verification series — human observation  [EMPTY]
    data/historical/    3 years hourly, 15 stations — irreplaceable
    data/wave_forecasts/ 1,095 archived GFS-Wave cycles/station, with partitions

`forecast/stats.py` still carries `assess`, `contested_skill` and a CLI from the
predecessor's scoring work. Only `load_column`, `least_squares`, `rmse` and the
circular helpers are used here. Trimming it is a good first cleanup.

## Design rules that are easy to erode

- **The three beaches are not one beach — and Coronado is not one beach.**
  Breakers keeps 26° of swell window and Gator 65°, and Gator alone holds west
  swell. But the same mechanism runs along Coronado's own sand: the west edge
  IS the bearing to the Point Loma tip, which sweeps as you walk, giving
  **42.8° / 49.1° / 56.3°** at the north, center and south breaks across 2.8 km.
  That 13.5° spread is a third of the entire Breakers-to-Gator range. Any
  surface showing one number for "Coronado" is averaging across it.
- **The Point Loma tip is one point and it carries every west edge.** 100 m of
  error there moves an edge ~1°. It is the highest-leverage coordinate in the
  repository.
- **The buoy does not share the beach's geometry.** 46232 sits south-west of
  Point Loma with the peninsula behind it to the north-east; the beaches sit in
  front of it. A transform that skips the aperture delivers north-west swell
  that cannot physically arrive, on most days of the year.
- **Bulletin direction is the direction waves travel TOWARD; NDBC `MWD` is where
  they come FROM.** `collector.gfswave` flips it once, on the way in. Do not
  flip it again. Measured: 29° mean error with the flip, 151° without.
- **Say what the forecast is standing on.** Geometry, model, calibration and
  observation are four different confidence levels, and the reader is entitled
  to know which one they are looking at.
- Wind and tide are not optional at these beaches. KNZY (North Island) for wind,
  NOAA 9410170 (San Diego) for tide. Neither is wired in yet.
- **Measure before claiming.** Every strong claim in BRIEFING has a number
  behind it, and four plausible ones were killed by their own tests. Write the
  test that could falsify the idea before building on it.

## Success metric

**Beat the published forecasts at these three beaches, measured against a real
verification series, and be honest about the error bars.** Until that series
exists there is no success metric — only a model nobody has checked.
