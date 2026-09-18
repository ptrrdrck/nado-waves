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
3. **The transform — built, `forecast/transform.py`.** Offshore spectrum at
   46232 → energy that survives the beach's window. Integrates E(f, θ)·T(θ)
   over the circle, and also runs GFS-Wave partitions one train at a time,
   recombining in energy. `collector/spectra.py` archives the five NDBC
   components to `data/spectra/46232/`; run it from Actions, never a session.
   **The finding that shaped it (BRIEFING §10): integrating the spectrum is
   what makes the Coronado Islands an ~11% energy reduction rather than an
   on/off switch.** Do not reintroduce a binary blocker test against a single
   `MWD`.
   **Caveat: 46232 was dark for 16.2 days, 2026-09-01 to 2026-09-17**, and is
   reporting again. Cause unknown, nothing was done to fix it, and the 48-hour
   staleness alert never visibly fired. The anchor buoy for every transform
   here can disappear for a fortnight without notice, and BRIEFING §3a says no
   other station in the array can stand in for it.
4. **The forecast — built, `forecast/live.py`.** GFS-Wave partitions at 46232
   through the transform, with KNZY wind and 9410170 tide as context. Writes
   `data/live/forecast.json`. **GFS-Wave publishes no directional spread, so
   one is assumed** (20° swell, 35° wind sea) — conventional, not fitted, and
   the weakest number in the chain. BRIEFING §11 measures what it costs: across
   a fourfold change the between-break ratio moves 1–4%, so publish the ratio
   loudly and the absolute height quietly.
5. **Calibration and honest bands**, reusing `forecast/verify.py` and
   `forecast/residual.py` against the verification series.
6. **App surface — built, `app/forecast.html`, published by
   `forecast/publish.py`.** This repository is private, so Pages cannot serve
   it and a published page cannot fetch `data/live/forecast.json` across the
   boundary. The forecast workflow builds a flat bundle (`index.html` +
   3-hourly `forecast.json` + `.nojekyll` + README) and pushes it to the
   **public** `nado-waves-forecast`, the same pattern `nado-waves-log` uses for
   the observer form. **This repository stays the system of record; nothing is
   edited on the far side.** Kept separate from the log repository on purpose:
   the log never shows a forecast, and a sibling path on the same Pages site is
   one URL edit away. Note that is a separation of paths, not of origins —
   `*.github.io` project sites share one origin, so it is not a browser
   boundary.
   Publishes the swell-side
   window only (BRIEFING §12), no ratio and no confidence badge — a ratio
   against the smallest of three is circular when all three are on screen.
   States all four levels
   (geometry / model / calibration / observation) on screen, not just in the
   README. **Coronado's three breaks only, by decision (2026-09-18).** Breakers
   and Gator are out of the forecast and the app. They are not equivalent to
   Coronado north and south — measured, they differ on 17.6% and 13.5% of
   archive swell hours — but they are the two spots still standing on estimated
   coordinates, so nothing trustworthy was dropped.
   `tests/test_app_surface.py` enforces the vocabulary: the page may not use
   the words an accuracy claim would need.

## Infrastructure

- The collector runs as a **scheduled GitHub Actions workflow**, not a local
  cron and not a VPS. It must run whether or not a dev machine is on, and it is
  unaffected by what an interactive Claude session can reach.
- Observations are **committed back into this repository** as per-station files.
- **Wire in a keepalive action.** GitHub disables scheduled workflows after 60
  days of repository inactivity, and the workflow's own bot commits do not
  reliably reset that timer.
- **Keep the staleness alert** — no new observation in 48 hours, notify. A
  silently dead collector loses days that cannot be recovered. It did not
  visibly fire for 46232's 16-day outage; **partly explained** (BRIEFING §8):
  `health.newly_dark` deliberately suppresses anything dark longer than
  2 × 48 h, so the alert had 09-01 to 09-05 to be seen and has been silent by
  design since. Whether it was ever *delivered* in that window is still
  unchased. A station that had never reported at all had no date to age from
  and alerted forever; `first_checked_utc` fixes that.
- **Egress from a Claude session is policy-controlled and changes mid-session.**
  A 403 at CONNECT is a denial, not throttling: check
  `$HTTPS_PROXY/__agentproxy/status`, report the blocked host, do not route
  around it. See `collector/probe_mop.py:DENIAL_NOTE` and BRIEFING §8.
- **A 404 that used to mean one thing can start meaning another.** NCEP dropped
  the per-station GFS-Wave bulletin files between 2026-09-15 and 2026-09-16;
  the data moved to `gfswave.tHHz.bull_tar` in the same directory. The archive
  job read the 404 as "NCEP skipped this cycle" and went silently to zero rows
  for three days. `collector.gfswave` now checks the tar before believing a
  404. Same shape as the staleness alert missing 46232's outage: the monitoring
  watched for the failure it expected.
- Before writing an "archive it now, history is unrecoverable" job, **check
  whether the history is actually unrecoverable.** It was for Open-Meteo. It was
  not for GFS-Wave, whose every cycle since 2021-03 sits in the NOAA Open Data
  bucket — which turned a six-month wait into an afternoon.

## Layout

    collector/          data pipeline: NDBC archiving, revisions, station
                        status (stations.json is a COLLECTION list, not a
                        ranking — see forecast/siting.py), historical backfill,
                        GFS-Wave bulletins,
                        probe_spectra.py (are directional spectra reachable?),
                        spectra.py (archive them), wind.py (KNZY),
                        tide.py (9410170),
                        beachlog.py + beachlog_import.py (the observation log)
    app/forecast.html   the app surface — Coronado's three breaks       [built]
    app/beachlog.html   the phone form, owner build (shared store)
    app/beachlog-observer.html  same file, observer build — no sign-in, entries
                        stay on the phone and are handed back as text. The two
                        differ only in <title>; a test enforces it. The repo CSV
                        stays the system of record for both.
    forecast/
      geometry.py       which bearings reach each beach          [built]
      transform.py      spectrum -> energy through the aperture   [built]
      live.py           the live forecast, Coronado only          [built]
      siting.py         which BUOYS observe the swell that reaches it  [built]
      spots.json        breaks and blockers    [Coronado digitised; others not]
      swell.py          great circles, bearings, group velocity
      stats.py          load_column, least_squares, rmse, circular means
      dispersion.py     swell-arrival detection and the 1/T fit
      forensics.py      read a swell's origin off the buoy record
      verify.py         bias, RMSE, scatter index, calibration, band coverage
      residual.py       is the remaining error recoverable? (it was not, before)
      beachverify.py    does the log agree with the geometry, and the control
    data/live/          forecast.json, what the app surface reads
    data/spectra/       NDBC directional spectra, five components per station
    data/wind/          KNZY                    data/tide/  NOAA 9410170
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
  repository. Measured 2026-09-18: 250 m of tip error moves a Coronado edge
  2.2–2.8°, against 0.46° for the same error on the Coronado Islands.
- **The Coronado Islands are not a switch, and digitising them is low value.**
  They subtend 10.9° at 31 km and remove ~11% of a spread swell's energy where
  Point Loma removes ~50%; their Fresnel number runs 1.9–5.4, so even that 11%
  is partly filled by diffraction. A full kilometre of island coordinate error
  costs under 2°. The locals who say the islands barely shadow are right, and
  BRIEFING §10 has the mechanism. **Never restore a binary open/shut test for
  them** — that was the modelling error, and it inflated the "breaks disagree
  on 50% of swell hours" headline to roughly twice its real, Point-Loma-driven
  value of 19.4%.
- **Publish the swell-side window, never the raw open arcs.** A window edge
  formed by the seaward half-plane clip means the arc ran out of *modelled*
  land, not that it ran into ocean. Coronado's south-east arc spans Imperial
  Beach, the Tijuana river mouth and Rosarito at 11–41 km, none of which are
  blockers in `spots.json`, so the raw arc claims open water across a visible
  coastline. `forecast.geometry.swell_window` keeps only the windows with both
  edges blocker-derived; `open_window` still returns everything. BRIEFING §12.
- **The buoy does not share the beach's geometry.** 46232 sits south-west of
  Point Loma with the peninsula behind it to the north-east; the beaches sit in
  front of it. A transform that skips the aperture delivers north-west swell
  that cannot physically arrive, on most days of the year.
- **A station earns its place by geometry, not by being nearby.** `stations.json`
  says what is *archived* — collect broadly, the 45-day window is
  unrecoverable — and nothing more. Which buoys constrain the swell reaching
  Coronado is **derived** by `forecast/siting.py` from NDBC coordinates and the
  digitised breaks, never stored, because §2a already paid for duplicating a
  derivable coordinate. Measured (BRIEFING §3a): **46232 is the only buoy in
  the array inside Coronado's window, and there is no substitute.** 46258 is
  33.9° *behind* Point Loma at nearly 46232's range — a control for the
  aperture claim, and never a fallback anchor. The predecessor's
  `launch_candidate` flag marked leagues, not physics; four of its six sat
  55–92° off the window, and it is deleted.
- **Never type a buoy coordinate.** `collector/metadata.py` fetches them from
  NDBC; a station it cannot place is reported UNPLACED and makes no claim.
  46235 is in that state now. NDBC is frequently denied at CONNECT from a
  session — run the metadata job on Actions.
- **Bulletin direction is the direction waves travel TOWARD; NDBC `MWD` is where
  they come FROM.** `collector.gfswave` flips it once, on the way in. Do not
  flip it again. Measured: 29° mean error with the flip, 151° without.
- **Say what the forecast is standing on.** Geometry, model, calibration and
  observation are four different confidence levels, and the reader is entitled
  to know which one they are looking at.
- Wind and tide are not optional at these beaches. KNZY (North Island) for wind,
  NOAA 9410170 (San Diego) for tide. **Both wired in and flowing** as of
  2026-09-18; the spectra archive is filling too. **Tide predictions must span
  the whole forecast window at both ends** — a GFS-Wave cycle is already hours
  old when it publishes, so the forecast starts in the past, and it runs to
  +168 h. Fetching from *now* to +96 h covered 100 of 169 hours and the rest
  read "not collected" (BRIEFING §13).
- **Measure before claiming.** Every strong claim in BRIEFING has a number
  behind it, and four plausible ones were killed by their own tests. Write the
  test that could falsify the idea before building on it.

## Success metric

**Beat the published forecasts at these three beaches, measured against a real
verification series, and be honest about the error bars.** Until that series
exists there is no success metric — only a model nobody has checked.
