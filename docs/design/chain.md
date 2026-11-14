_Read before touching the physics chain: verification log, transform, nearshore rays, surf zone, live forecast, bias/ensemble reports, trains, wind sea._

# The chain: verification, transform, nearshore, surf zone, forecast, bias, trains

Moved verbatim from CLAUDE.md on 2026-11-14 (the context-reduction
restructure); CLAUDE.md keeps the one-line rule and points here.

## Build order 2: the verification series

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

## Build order 3: the transform

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

## Build order 3a: the nearshore transform and the surf zone

3a. **The nearshore transform — built and SHIPPED 2026-09-25, by the owner's
   decision.** `forecast/raytrace.py` (precompute, numpy) traces rays backward
   from the 5 m contour off each break over the USGS CoNED + GMRT seabed
   (`collector/bathymetry.py`) — refraction and shoaling over the whole
   seabed, the Coronado Islands' own shelves included; Point Loma, Baja and
   the islands as land; and diffraction at every window edge (the islands by
   the two-edge Babinet factor, the Point Loma tip and the Baja tangent by the
   straight-edge one), each ray carrying a hard-edged and a diffracting
   answer, and bottom friction along each ray's path (JONSWAP, C_b = 0.038,
   from the literature and never tuned; its own factor per ray) — into
   `data/nearshore/` tables; `forecast/nearshore.py` (pure Python) carries a
   spectrum through them and adds fetch-limited local chop: fresh over
   fetches closed by land, and — since 2026-09-30 (owner's point, BRIEFING
   §36) — grown on by equivalent fetch over the OPEN water between the buoy
   and the break, which the buoy's spectrum never saw. Its wind is the local
   one on both chains: KNZY on Now, the NWS grid on Forecast, and an hour
   the grid lacks has NO local chop (owner's call, 2026-10-15: GFS-Wave's
   wind at the buoy, 29 km out, overstated Point Loma's lee and could not see
   the near-shore wind the open growth is for). The calculation's Local chop
   row reads "<period> s, <fetch> of fetch" (owner's call, 2026-10-15): its
   kind and whose wind are on docs.html, not in the row.
   **Then the surf zone, SHIPPED 2026-09-26** (BRIEFING §32):
   `forecast/surfzone.py` carries that sea from 5 m in over each break's
   surveyed profile (`<break>_profile.csv`, the 2016 CoNED beach, not this
   season's bars) at the tide of the moment, Battjes–Janssen breaking with
   Battjes–Stive's γ, and reports the largest Hs and the depth it breaks in.
   **The number on every break card is that breaking height**, labelled
   "breaking height" on both chains, the depth it breaks in under the
   calculation's Wave break row (owner's call, 2026-10-09) — a significant
   height, never a face height; the
   5 m figure stands in only when there is no tide, never a breaking height at
   an assumed one. The straight-line window figure survives only in
   the card's calculation table, which folds out under the headline from a
   caret at its end (up closed, down open; owner's design 2026-09-26) and
   gives each effect one row — buoy, windows, refraction, diffraction, bottom
   friction, shoaling, local chop, wave break — as Step / Change / % / Hs, the
   percentage against the row before. Refraction is measured with every edge still a hard
   shadow, as the window treats them, and diffraction is only what softening
   the edges changes (`nearshore.summarise`). **Diffraction is computed on the
   bent rays, not straight lines**: the ray that grazes an edge is itself
   refracted between the edge and the beach, and that is where the shadow
   boundary sits as seen from the break (BRIEFING §31). Buoy spectra are read by **maximum entropy**
   (`Spectrum.spread = "mem"`), which also stops the buoy's own Hs reading ~5%
   high. Measured in BRIEFING §28–§29: it REVERSES the south/north ordering in
   south-swell season. It is physics, not calibration, and it is unverified —
   the observation log decides between it and the aperture, not this file.

## Build order 4: the forecast

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

## Build order 5: calibration, bias, ensemble

5. **Calibration and honest bands**, reusing `forecast/verify.py` and
   `forecast/residual.py` against the verification series.
   **Measured first, at the model level: `forecast/modelbias.py`** (owner's
   decision, 2026-09-26). It asks whether BRIEFING §5's 0.26–0.31 m LOW bias
   at 46232 survives each break's windows, by pairing
   `data/forecast_log/` with the measured chain rebuilt for the same hours.
   It reports and never edits. §4 already rules out a correction that keeps
   adapting, so the form to test is a fixed one. Applying anything waits on
   its numbers AND on what `docs.html` calls it, because "calibration" is
   reserved for the beach log. `model-bias.yml` rebuilds past cycles with
   today's chain into `46232_recomputed/`, because GFS-Wave's spectrum is
   recoverable to 2021 and the buoy's is archived from 2026-08-04, so the
   report need not wait for the as-shown log to fill. The two logs are never
   mixed.
   **Where the bias comes from: `forecast/exposurebias.py`** (BRIEFING §33).
   Measured against a buoy the islands do NOT shadow, it is not the "smooth
   ocean" §5 assumed: GFS-Wave reads 8% low at 46047 and 23–32% low at the
   five shadowed buoys, because it shadows them **more** than the islands do —
   its shadow ratio is 0.69–0.79 of the measured one over swell hours, and at
   46232 moves only 0.73–0.80 across direction sectors. Also a report that
   never edits.
   **GEFS-Wave's ensemble: `collector/gefswave.py` → `data/ensemble_forecasts/`,
   measured by `forecast/ensemble.py`** (owner's request, 2026-09-29;
   BRIEFING §35). The 31-member station bulletin at 46232: Hs mean and spread,
   total height only, **no direction** — so it is drawn at the buoy and never
   carried to a break. Archived each forecast run (`forecast.yml`) and back to
   2023. Three things measured before anything was drawn: **the spread only
   exists from 2026-02-25 12Z** (earlier rows are means only, under the same
   header); **the P(Hs >) columns are shifted from their labels** — "2.00m"
   holds P(> 1 m), "3.00m" P(> 2 m) — so they are archived by position and
   only those two are read; and **the band held the buoy on 7–35% of hours**
   by lead (18 Jul – 29 Sep 2026) against the ~68% it implies, because the
   mean runs ~0.2 m HIGH (the single run reads 0.3 m low) and the spread is
   0.03–0.19 m. The page draws the band only beside those figures, which it
   states with n and dates. **Owner's decision 2026-09-30: no correction
   yet — wait for winter.** Tested out of sample the same day (§35): a fixed
   shift plus a per-lead widening held 62–68% on 17–29 Sep, but it was fitted
   on one summer, winter's offset is half the size with more scatter, and a
   summer-fitted band is exactly how §5's under-covered. **And never correct
   GFS-Wave at the buoy and carry it to the breaks**: the buoy reads −22% but
   the breaks −28% to +3% (`docs/model_bias.md`), because most of the buoy's
   deficit is swell the breaks never receive; the chain is linear to 5 m, so a
   buoy fix moves every break by the same factor and puts North ~+33%.

## Bulletin direction (TOWARD) vs MWD (FROM)

- **Bulletin direction is the direction waves travel TOWARD; NDBC `MWD` is where
  they come FROM.** `collector.gfswave` flips it once, on the way in. Do not
  flip it again. Measured: 29° mean error with the flip, 151° without.

## 46232 is the sea after the Channel Islands

- **46232 is the sea after the Channel Islands, and that sea is not
  uniform.** On north-west swell its westerly lobe pins near 270° whatever
  46047 reads, 46258's at 286° and 46086's at 279° — each at its own bearing,
  none at a charted island edge (BRIEFING §38). That lobe carries ~24% of
  Center's and ~36% of South's 5 m energy on those hours, and the breaks'
  rays leave deep water 25 km from both 46232 and 46258. Never "fix" 46232's
  direction toward 46047's: the beach needs the sea where it is, not the
  open ocean's, and §3a still forbids a substitute anchor.

## "At the buoy" means no aperture

- **"At the buoy" means no aperture at all — `transform.at_buoy`, not
  `through(spectrum, spot, [])`.** The latter still applies that spot's seaward
  half-plane, which excludes 304–124° and dropped **12–26% of the energy** out
  of the buoy's train list while leaving its headline Hs whole. The symptom was
  trains that did not sum to the number above them; the cause is that a buoy
  29 km offshore has no landward half.

## The leading wave train; splitting and dividing trains; brackets; row fitting

- **The leading wave train is not the same at the buoy and the beach.** The
  aperture takes whichever trains point at the blocked sector, so a spectrum's
  biggest swell offshore need not be the one running a break — measured, that
  re-ordering happens on 23% of archived spectra, and on 2026-09-19T04:00Z the
  leader differed *between the three breaks* on one reading. Surfaces list the
  trains rather than collapsing them to one "dominant"
  (`transform.split_trains`, BRIEFING §16). **Split by period, then by
  direction** (owner's decision 2026-10-08, BRIEFING §40): period bands are
  cut at dips in the energy smoothed [1, 2, 1], and a dip must clear the
  buoy's own sampling noise — `PROMINENCE` is DERIVED, 1.5σ at
  `BUOY_DOF` = 32 (matched to the archive's band-to-band jitter), 0.63;
  the old raw 0.6 was a one-sigma dip and split a single clean swell in half
  the synthetic trials. Then a band whose energy comes from two directions
  of ≥ 20% each (`split_lobes`) is divided heading by heading, and each
  direction is its own train with its own height and its own PEAK PERIOD:
  until then it was one "A & B" row at one period, and the directions' own
  peaks sat ≥ 1 s apart on 61% of those at 46232. **Except maximum
  entropy's twin** (`mem_twin`): one swell 20–35° wide reads as two EQUAL
  lobes 32–60° apart, which four moments cannot tell from two swells, so an
  even pair (> 0.8) under 60° stays one train. It is NOT a full 2-D
  watershed, and that was measured, not assumed: a fixed 10° watershed split
  a single clean swell in 96% of synthetic trials. Nothing here can part
  two swells of one period less than ~90° apart, or two from one direction
  a few seconds apart when the smaller rides the bigger's tail. A train
  that still holds two directions (0.3% of the buoy's) is labelled with
  both (§38a), "WSW 258° & S 180°" where the row has room and "WSW & S"
  where it does not (below), an arrow from each. `from_deg` is the mean of
  the train's own energy; no height reads a direction.
  **At a break, then, a row two of the buoy's trains carried is divided
  into them** (owner's decision, 2026-11-03; BRIEFING §49;
  `nearshore._divide_by_buoy`, on both chains): the windows trim each buoy
  train differently, and what is left of two can sit side by side with no
  dip and no second lobe for the break's own split to find — North on
  3 Nov read one row, 16.7 s from 228°, that was the buoy's SSW 14.3 s and
  30% of its W 18.2 s, neither swell's period or heading. Every ray's
  energy at 5 m is credited to the buoy train holding its (bin, offshore
  heading) in the buoy's own split with NO floor (`nearshore.buoy_split`,
  from the same 1° grid; floored, it is `at_buoy`'s list, a test pins
  it), which is exact because the chain is linear to 5 m; a row whose
  second buoy train carries ≥ `BUOY_DIVIDE_SHARE` of it becomes one row
  per buoy train, each its own height, peak period, heading, lobes, 5 m
  heading and held arc, under the same floors. **Since 2026-11-04 the bar
  is 5% with a back-check** (owner's decision, BRIEFING §49a, after North's
  W at 10% of its energy — a third of its height — had no row at 20%): a
  division needs two pieces that would each be listed
  (`BUOY_DIVIDE_NEEDS_TWO`), and a second piece is that swell only when
  its own heading sits nearer that swell's heading at the buoy than the
  row's lead swell's (`BUOY_DIVIDE_CHECKS_HEADING`); otherwise it is the
  lead's spread across the buoy's dividing line and goes back to the lead,
  the row naming every buoy swell it holds in `Train.buoys`. Measured
  (`forecast.trainmerge`), control, buoy parted, ≥ 3 s and ≥ 60° apart:
  a swell ≥ 10% of a break's energy with no row 22.1% at 20% → 9.2%,
  phantom rows (a row mostly the swell it is not named for) 10.0% →
  8.0%; 5% without the check 8.8% and 13.0%. The archive's "hidden"
  figures rise under the check (N / C / S ≥ 10%: 4.9 / 4.2 / 6.6% of
  hours against 0.6 / 1.4 / 4.8% at 5% alone) because the check overrules
  the buoy's dividing line that the archive is scored against; only the
  control can judge it. Nothing tells two swells apart that the buoy read
  as one, and the beach log is what would say whether any of this is seen.
  The 20% figures below are the first rule's.
  **Heights never change; only rows.** MEASURED first
  (`python -m forecast.trainmerge`, ~4 min): with the buoy's split as
  reference, a swell carrying ≥ 20% of a break's energy had no row of its
  own on 11–24% of hours, 0.3–0.8% after (a third instead: 7–8%); the
  Briefing missed a swell ≥ half the biggest on 123 of 1,812 hours, 45
  after, and 344 of its 2,699 lines were two buoy trains, 7 after. In the
  known-answer control, where the buoy parted two swells ≥ 60° and ≥ 3 s
  apart, 21% → 3.7%; where it did not part them NOTHING changes, and
  nothing at a break can. Inheriting the buoy's split outright was
  measured and rejected: it merges a swell that came through two windows
  into one row headed between them, North's fault reversed. **That
  reverse is kept on purpose** (owner's call, same day): one buoy swell
  that a break's own split makes two rows stays two rows — 52% of hours
  at South, 30% at Center, 17% at North, and 53% of single narrow
  synthetic swells at some break. **What made the two rows is NOT
  measured, so nothing says it** (owner's call, 2026-11-03): two windows
  (South 12 Oct 06Z: 190° through the Baja–islands gap, 259° through the
  main window), one window and the energy bent or diffracted past its
  edge (Center 3 Nov 15Z: 243° inside the main window, 277° past Point
  Loma's 250° edge), or a dip the aperture and seabed left in its periods.
  The caption reads "reaching this break as two trains", never the
  mock's "through two windows". **On the page, one swell's rows sit
  together under a bracket, and a tap on either picks them all** (owner's
  choice, 2026-11-03: A1 with E of a mock of five): each row carries
  `swell`, the buoy train that carried most of it, and rows that are one
  swell carry `group` and `swell_at_buoy` (`nearshore.train_dicts`, both
  chains). **One buoy train is one swell only from one direction AT THE
  BUOY** (owner's decision, 2026-11-08, BRIEFING §49b; `BRACKET_DEG`,
  `bracket_groups`): each row's `buoy_from_deg` -- its rays given the
  nearest direction lobe of its buoy train in their own bin, an even
  maximum-entropy twin read as one -- and ALL of a buoy train's shown rows
  within 20° of each other, or none bracketed (a subset added as many wrong
  brackets as right). North 5 Nov 17Z read "one swell at the buoy" over a
  SW 16.7 s, a W 10.5 s and a 6.7 s row, the buoy's one train being its
  whole spectrum; at the buoy they came from 247°, 281° and 272°. Measured
  (`python -m forecast.trainmerge --brackets`, ~1 min, the control):
  single swells keep 107 of 111 brackets; in five 5 Nov-like cases wrong
  brackets 79 → 5; two swells ≥ 60° apart the buoy merged 61 → 21, 50°
  40 → 26, ≤ 30° 70 → 70 (one swell's shape at the buoy, at any bar).
  The archive's hours with a bracket: N / C / S 19 / 31 / 51% → 10 / 15 /
  18%. Center 3 Nov 15Z, the case the bracket was built on, sits 23° apart
  and lost it; what the buoy held there is settled by nothing. A dip test
  on the buoy's own energy density was measured and does not help: a weak
  swell on a big one's flank is a shoulder there, not a hill. The three
  rows are chosen by height, then each swell's rows put together, the
  swells in order of their biggest row (`swellGroups`), so the lead row is
  still first and a smaller piece can sit above another swell — the A·B·A
  case, 13–19% of a break's split hours over the archive. Each row keeps
  its index for its arrows; a grouped row's key `G0.2` lights every row
  and arrow of its swell, under one caption, "One swell at the buoy, W at
  18.2 s, / reaching this break as two trains" (`swellCaption`); an arrow
  tap is still its own train. Every Swell-card train list, the Buoys tab's
  too, has the bracket's 9 px lane, and every row 5 px either side, so a
  picked row's background stands as far past its text as above and below
  it (measured at 4x in Archivo: the digits 5.0 px under its top, the
  baseline 6.25 px over its foot); the height column went 112 → 96 px to
  pay for it (heights are 87.4 px wide, 95.5 from 10 ft), so a heading lost
  3 px net.
  **A train is one line at every phone width, and keeps its degrees
  wherever they fit** (owner's calls, 2026-10-06 and -07): never a second
  line, never past the card, never shorter than the row needs. Each row
  carries its heading's forms longest first (`trainForms`) and `fitRow`
  shows the first that FITS, measured on the laid-out row — re-fitted on
  every render and by a ResizeObserver on width change and when a hidden
  tab opens. Degrees on an untagged row and on a tagged one with one
  direction; a tagged row with two names them by point at most beside its
  tag; then one point, the larger lobe's. Only when that cannot sit beside
  its tag (a 320 px phone) does the tag wrap. Worst-case width thresholds
  (the 2026-10-06 container queries) dropped degrees on rows that had room
  for them; measuring each row is what stops that.

## Wind sea is the wind's call

- **Wind sea is the wind's call, never the period's** (owner's decision,
  2026-11-08; BRIEFING §51; `forecast/windsea.py`). A train is tagged wind
  sea only when the wind along it outruns it -- wave age, β·U·cos θ > gT/2π.
  On LIVE BOTH KNZY's and NDBC 46086's MEASURED winds must say so at β 1.5
  (Hanson & Phillips), each as of the spectrum (KNZY's METAR from 70 min
  before; 46086's standard met within 30 min, carried to 10 m ×1.09 from a
  4.1 m anemometer, an assumption); either missing, no tag. On Forecast
  GFS-Wave decides: its own 10 m wind at the buoy at WAVEWATCH III's own
  multiplier (1.7), or on the partition fallback its bulletin's flags.
  **Every other train has NO tag** (owner's call): its period already says
  it is short; "short period" was offered and declined. The 46047 / 46086
  Buoys-tab cards carry no tag (nothing validated there). Measured
  (`python -m forecast.windsea`, ~15 s, 4 Aug - 8 Nov): the old < 8 s rule
  named 32% of 46232's trains; by wave age 13% of those were driven with
  KNZY's wind, 33% 46086's, 55% 46047's; the two winds agree on under a
  third of each other's firings; both together name 94 of 2,884 trains,
  and a third wind that played no part agreed on 87% (46047) and 89%
  (GFS-Wave) of them. GFS-Wave's own flags call 9% of its < 8 s partitions
  at 46232 wind sea. It is a test of the wind: nothing observes the sea
  being driven. `Train.wind_sea` is the tag, set by the chain;
  `Train.is_short` is the period test reports and filters keep. 46086's
  wind is a wind, never its spectrum: §3a's guard still keeps the station
  out of now.py by name, and a test pins that the label reads only its
  standard met. Its standard met is collect-beach-inputs.yml's since the
  same day (beside 46232's; collect.yml excludes both), because on
  collect.yml's schedule it landed a median 5 h apart.

## The seabed transform is physics, never calibration

- **The seabed transform is physics, never "calibration".** Calibration is the
  level reserved for fitting to the observation log (build order 5), and
  `docs.html` names it as its own confidence level. Refraction, shoaling and
  diffraction are modelled from surveyed inputs and fitted to nothing; calling
  them calibration would claim a level the project has not reached.
  `tests/test_app_surface.py` keeps the word out of the card's paragraph.

## The transfer tables stop at 5 m

- **The transfer tables stop at 5 m of water; the surf zone takes it from
  there.** The 10 m contour MOP uses lay 2.2 km off the north break, outside
  Point Loma's shadow, and described a different place (BRIEFING §29). Moving
  `raytrace.H_REF` moves where the tables hand over to `surfzone`; rebuild
  the tables AND the profiles and re-read §29 and §32 before doing it.

## The breaking height is a significant height

- **The breaking height is a significant height, not a face height**, and the
  profile is a 2016 survey. Measured over the archive (BRIEFING §32): breaking
  lifts the 5 m figure ~20–23% into ~1.7–1.9 m of water, and the whole tide
  range moves the break point 34–53 m while changing the height under 2% —
  on a barless profile the tide decides WHERE it breaks, not how big. A
  season's sandbar would change that, and nothing here knows where it is.
