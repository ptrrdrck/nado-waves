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
4. **The forecast — built, `forecast/live.py`.** GFS-Wave at 46232 through the
   transform, with wind and 9410170 tide as context. Writes
   `data/live/forecast.json` (gitignored — derived, see Infrastructure).
   **It uses WAVEWATCH III's own directional spectrum** via
   `collector/wavespec.py`, which also carries the model's 10 m wind, so the
   assumed 20°/35° spread is no longer used on this path and no second wind
   source is needed. Falls back to partitions when the spectral product is
   unavailable, and `wave_source` says which was used. The two agree to within
   5.6% through the aperture (BRIEFING §15), which confirms §11 by a different
   route.
5. **Calibration and honest bands**, reusing `forecast/verify.py` and
   `forecast/residual.py` against the verification series.
6. **App surface — built, `app/forecast.html`, published by
   `forecast/publish.py`.** **Two tabs, and they are two evidence chains
   rather than two views of one.** *Now* is built only from measurements
   (`now.json`: NDBC directional spectrum, KNZY METAR, measured water level);
   *Forecast* only from a model (`forecast.json`: GFS-Wave). Each renders its
   own "standing on" block from whatever keys its file carries, because the
   two name different levels. Opens on Now; a stale or missing observation
   says so and points at Forecast rather than falling back silently. This repository is private, so Pages cannot serve
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
- **`data/live/` is gitignored, and that is not a breach of "data is tracked".**
  That rule guards the irreplaceable NDBC archive and the collected series; a
  forecast rebuilt every cycle from committed inputs is neither, and the public
  delivery repository's history is already the record of what was shown.
  Committing it cost ~460 MB of git objects a year (BRIEFING §15).
- **A total is not a validation of a mapping.** The WW3 direction axis descends;
  reading it as ascending scrambled which heading each energy bin sat at and
  still integrated to exactly the right Hs. Only a *located* quantity — the
  spectral peak, against the bulletin's dominant partition — caught it.
  BRIEFING §15.
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
                        wavespec.py (WW3's own spectrum + wind, not archived),
                        tide.py (9410170 — measured, hourly predicted, and
                        CO-OPS's own hilo TURNS in a third file),
                        shoreline.py (NOAA's ENC coastline, to check the
                        hand-traced chords — run on Actions),
                        enc_layers.py (what else the charts carry: the jetty,
                        the soundings, a finer coastline — BRIEFING §22),
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
      now.py            the OBSERVED reading, measurements only    [built]
      publish.py        the public delivery bundle                 [built]
      units.py          ft/mph first, m/kt in parentheses -- display only
      tideturns.py      the next high/low, and why its direction is not
                        differenced from the measured level      [built]
      shorenormal.py    surveyed shore normals vs the digitised chords,
                        swept over scale; reports, never edits    [built]
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
    data/wind/          KNZY       data/tide/  NOAA 9410170, three files:
                        _observed (measured), _predicted (hourly harmonic),
                        _turns (the harmonic model's own highs and lows)
    data/shoreline/     NOAA ENC coastline near Coronado - a CHART product,
                        generalised, not the survey-grade MHW vector  [689 pts]
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
- **One station's reading is not one beach's condition.** Wind and tide are
  hoisted above the break cards because KNZY and 9410170 feed all three and
  repeating them three times is noise. **The offshore/onshore reading is not
  hoisted**, because it is derived from the shore normal and Coronado's three
  normals span 29° (192.8 / 214.2 / 221.5) — measured 2026-09-18, a 290° wind
  reads cross-shore at north and centre and onshore at south, on the same
  reading. Hoist the measurement; keep the interpretation where it is made.
- **"At the buoy" means no aperture at all — `transform.at_buoy`, not
  `through(spectrum, spot, [])`.** The latter still applies that spot's seaward
  half-plane, which excludes 304–124° and dropped **12–26% of the energy** out
  of the buoy's train list while leaving its headline Hs whole. The symptom was
  trains that did not sum to the number above them; the cause is that a buoy
  29 km offshore has no landward half.
- **The leading wave train is not the same at the buoy and the beach.** The
  aperture takes whichever trains point at the blocked sector, so a spectrum's
  biggest swell offshore need not be the one running a break — measured, that
  re-ordering happens on 23% of archived spectra, and on 2026-09-19T04:00Z the
  leader differed *between the three breaks* on one reading. Surfaces list the
  trains rather than collapsing them to one "dominant"
  (`transform.split_trains`, BRIEFING §16). It is a peak split of the 1-D
  spectrum, not a 2-D watershed, and must not be described as partitioning.
- **Imperial leads, metric in parentheses, everywhere a number is shown.**
  "2.3 ft (0.71 m)", "9 mph (8 kt)". **Nothing upstream of a display converts**:
  the JSON, the transform and the collectors stay in metres and knots, because
  that is what NDBC and WAVEWATCH III publish and putting a unit change between
  the source and every cross-check is how a 3.28 ends up somewhere it should
  not be. `forecast/units.py` and the two constants at the top of
  `app/forecast.html` are the only places the conversion happens; a test pins
  that each factor appears exactly once.
- **The tide's direction is read off the next turn, never differenced from the
  water level.** Measured 2026-09-19 on the 6-minute measured series:
  differencing the two newest samples reads the direction **backwards on 19.5%
  of readings**, and a least-squares slope over a trailing 45 minutes is still
  wrong 3.3% — because near slack water the real change is smaller than the
  gauge's own wobble (median 6-minute step 1.1 cm). Every 45-minute error sits
  under 5.6 cm/h, but a deadband that wide would silence the card for roughly a
  quarter of every cycle. If the next turn is a high the tide is rising into it,
  so direction and target come from one source and cannot contradict each other
  on screen — which is what a measured "falling" beside a predicted high water
  would do, at exactly the moment a reader is looking. BRIEFING §19.
- **Fetch the turns; do not find them in the hourly file.** `interval=hilo` is
  CO-OPS computing high and low water from the constituents. Taking the argmax
  of the hourly predictions instead puts the time **15.4 min out on average and
  up to 30.0** — measured against 31 real CO-OPS turns — while the height
  barely moves (2.8 cm worst). An hourly grid can
  say how high the next high water is and not when, and when is the half anyone
  plans around. There is deliberately **no fallback** from one to the other: a
  surface that silently swapped them would present the worse number in the same
  words as the better one.
- **The observed tab now carries exactly one modelled number — the tide's next
  turn — and it is labelled everywhere it appears**: a `predicted` tag on the
  card, and a "standing on" row that names the measured level and the predicted
  turn as two claims. The Now/Forecast split is about the reader always knowing
  which chain they are looking at, not about a tab being chemically pure; an
  unlabelled turn would have broken it, a labelled one demonstrates it.
- **The shore normal is the highest-leverage input to the wind reading, and
  two of three are unchecked.** Measured 2026-09-20 (BRIEFING §20): the verdict
  boundaries sit at fixed angles from the normal, which puts six of the nine
  boundaries for Coronado's breaks inside 265–330°, and **62.6% of a three-year
  wind record sits in 270–330°**. So error lands where the data is: 1° of
  normal error changes the verdict on **4.2%** of readings, 5° on 21%, and
  `coronado_north`'s known ~19° imagery-splice error on about **70%**. That is
  roughly twice what a uniform wind rose would cost. The north card's wind line
  is close to uninformative until the chord is re-digitised.
- **A normal is a property of a chord, not of a point.** The same beach gives
  102.8° over north's 547 m chord, 124.2° over centre's 285 m, 131.5° over
  south's 471 m and 121.3° over the whole 2.8 km — 28.7° of spread, all of it
  real. Any verification that does not state its chord length has verified
  nothing. `forecast/shorenormal.py` therefore reports a SWEEP over scale, and
  `residual_m` says whether the break sits on a straight stretch or a curve.
- **There are two shore normals and they are not the same claim.** The
  waterline normal is what the wind reading needs; the depth-contour normal at
  breaking depth is what refraction will need. `Spot.normal` is currently one
  number doing both jobs, and checking it against a shoreline verifies only the
  first.
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
