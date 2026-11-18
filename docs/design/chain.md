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
   from the literature and never tuned; its own factor per ray — until
   2026-11-18, when Madsen's height-dependent friction replaced it, below
   "Bottom friction is Madsen's") — into
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
   `forecast/surfzone.py` carries that sea in over each break's surveyed
   profile (`<break>_profile.csv`, the 2016 CoNED beach, not this season's
   bars; since 2026-11-18 it starts seaward of 5 m, "The surf zone starts
   seaward of the tables" below) at the tide of the moment, Battjes–Janssen breaking with
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

## A ray that lands on an island: diffraction only

- **Until 2026-11-15 one ray re-traced through an island could carry a
  third of a break's 5 m energy, and its heading was not stable** (measured
  2026-11-15, BRIEFING §52, when moving South Coronado's tip rebuilt the
  tables). A ray that landed on an island was re-traced over a "see-through"
  disc (`transparent`, sized from the blocker's `a`-`b` chord plus
  `ISLAND_PAD_M`), and its heading through that made-up seabed jumped 4-75
  degrees when the disc moved. Moving the tip (the disc's centre ~180 m, its
  radius +151 m) left window energy and every hard-edge gain exactly
  unchanged but moved single hours up to -29% (Center) and +22% (South);
  the old tip with only the pad 400 -> 450 m moved them as far (South +34%).
  The method, not the coast.
- **A ray that lands on an island now brings only what diffracts round it**
  (owner's decision, 2026-11-15, group 2d, item 14; BRIEFING §55), as at
  Point Loma and Baja (§31): it takes the heading and friction of the nearer
  of the clear rays either side of the shadow that have the island abeam,
  and the Babinet factor for the slit geometry interpolated between theirs
  (`raytrace.shadow_factor`), so nothing is read off where or how it lands.
  The disc is gone; `ISLAND_PAD_M` only sets the ring the islands'
  wavelength is read in, and how far an island reaches on a straight leg.
  Four smoother treatments were measured before choosing, each rebuilt over
  2,100 hours (maximum entropy), with §52's two perturbations:

  | treatment | against the committed tables: median N / C / S; hours over 5% | South Coronado's tip, chart and imagery: worst hour; hours over 5% | pad 400 -> 450 m: worst hour; hours over 5% |
  |---|---|---|---|
  | the disc (as committed) | | -18 ... +41%; 3 / 30 / 88 | -23 ... +14%; 11 / 0 / 95 |
  | the disc solved from its rim (no step at its edge) | +0.2 / 0.0 / +0.1%; 16 / 6 / 85 | -23 ... +16%; 7 / 4 / 58 | -23 ... +22%; 14 / 1 / 40 |
  | island factors capped at 1 (bounded single-ray gains) | -3.0 / -1.8 / -1.9%, every hour | -19 ... +44%; 4 / 30 / 106 | -24 ... +15%; 11 / 0 / 107 |
  | islands as land, factor where the ray lands | -0.2 / -0.1 / -0.7%; 6 / 3 / 156 | -3.0 ... +2.2%; 0 | under 0.7%; 0 |
  | **islands as land, factor interpolated across the shadow** | +0.4 / +0.4 / +1.5%; 11 / 29 / 249 | -2.9 ... +1.7%; 0 | under 0.7%; 0 |

  A smooth disc does not help: any made-up seabed puts the re-traced ray
  near a caustic. The cap clips the Babinet ripple's peaks and not its
  troughs, so every hour drops. The factor read where a ray lands depends on
  its last heading, which swings as it climbs the island's slope: burning
  the islands in still moved South +-6% that way, against +-0.4%
  interpolated. The two "land" versions differ by 0.6-2.9% in median, about
  how uncertain the islands' shadow is. Not this item: the largest single
  ray, 33-64% of a break's 5 m energy on some hours, is usually a CLEAR ray
  carrying the islands' lit-side ripple (factors 1.2-1.7), under every
  treatment, and stable.
- **With items 13, 18 and 19 in the same rebuild** (BRIEFING §55): the 5 m
  height a median +0.8 / +0.3 / +1.5% (N / C / S), single hours -19 ...
  +28%, 41 / 26 / 266 hours over 5%, a one-off move of the hours one
  re-traced ray had carried; afterwards the tip perturbation moves no hour
  3%. The worked hour on docs.html (28 Sep 19Z), breaking: 1.071 / 0.882 /
  0.882 -> 1.087 / 0.891 / 0.936 m, South's diffraction +3.9% -> +11%.
  The pinned 3 Nov cases moved: North's 16Z rows SSW 1.06 m, W 0.69 ->
  0.72 m; South's 22Z SSW row 1.16 ft at 16.7 s -> 1.36 ft at 13.3 s, the
  island method alone (South's 5 m height 1.047 -> 1.068 m).
- **The full table build ran again only after `trace`'s recorded paths got a
  name of their own** (2026-11-15): from 2026-11-10 they shared `rec` with
  the edge and island bookkeeping, and any call with edges failed. A rebuild
  with the unchanged geometry reproduced every committed table byte for
  byte before the tip moved.

## Baja's edge in the rays: diffraction and the straight leg

- **Moving the Baja tangent to the imaged headland moved the rays very
  little** (measured 2026-11-15, BRIEFING §54, before the owner's decision
  to ship it, group 2c, item 17). The rays already stopped on the right
  coast (GMRT); what reads `spots.json`'s Baja is the straight-edge
  diffraction (`raytrace.edge_points`, the tangent vertex), the straight-leg
  block (`raytrace.straight_line_blocker`, the `a`-`b` span) and the
  landed-ray label (`raytrace.landed_on`, nearest vertex within 3 km).
  Control first: the rebuild with the old geometry reproduced every committed
  file byte for byte. With `a` and `b` on the imaged coast, only the three
  `<break>.csv` tables changed, 336 / 271 / 316 of 23,040 rows (N / C / S);
  the legs, the fill's paths, the profiles, the fetch tables and the
  tables' metadata were byte-identical. Hard shadows changed only for rays of
  3.4 s and under, at the two ends of the straight-leg span; the rest is
  diffraction at the moved vertex (~400 m further east, so a ray that lands
  on Baja runs further into its shadow) and 3-6 rows per break that
  `landed_on` relabels between "Baja peninsula" and the Coronado shore.
  Over 2,090 archived hours (maximum entropy) the 5 m height moved a median
  +0.002 / −0.03 / +0.009%, at worst −1.8% (Center, 8 Aug 10Z) and +0.9%
  (South, 25 Aug 11Z), more than 1% on 0 / 5 / 0 hours, never 5%; hard-edged,
  never 0.06%. No island ray was involved, unlike §52. The worked hour on
  docs.html moved by at most 4 mm (North's window 0.836 → 0.840 m).
- **The straight leg is walked over the grids** (owner's decision,
  2026-11-15, group 2d, item 19; BRIEFING §54, §55). `straight_line_blocker`
  blocks a heading only inside the angular span of a blocker's `a`, `b` and
  outline seen from the ray's exit, so a short ray leaving deep water near
  the beach and heading back across land outside that span counted as
  clear. Measured, the gap was wider than "past `b`": of the rows a walk
  over the grids blocks, 1,841 / 1,351 / 1,180 (N / C / S) cross the US
  shore south of the breaks (the Silver Strand, Imperial Beach), 234 / 153
  / 116 the Mexican coast between the border and the Baja tangent, 20-25
  Point Loma north of its `b`, and ONE the Mexican coast south of `b`; all
  but one are 3.4 s and under. `raytrace.leg_blockers` keeps the chart test
  (it reaches past the grids) and walks each leg over the grids at the
  tracer's own step (`leg_land`), any land not an island's blocking it;
  `table` and `leg_table` use it. The 5 m height moved a median -0.01%,
  worst -6.2% (North, 22 Oct 00Z), one hour over 5%. Rejected: the half
  plane past `b`, which from exits far from the beach blocks long-period
  rays that clear Baja (South median -3.4%, worst -47%).

## The transfer tables stop at 5 m

- **The transfer tables stop at 5 m of water; the surf zone takes it from
  there.** The 10 m contour MOP uses lay 2.2 km off the north break, outside
  Point Loma's shadow, and described a different place (BRIEFING §29). Moving
  `raytrace.H_REF` moves where the tables hand over to `surfzone`; rebuild
  the tables AND the profiles and re-read §29 and §32 before doing it.
- **Where the surf zone STARTS is a different number** (`raytrace.SURF_START_M`,
  2026-11-18, BRIEFING §58): its profiles run seaward of the tables' start
  point, and the 5 m sea is carried back out to there linearly. Moving it
  rebuilds the profiles only (`--profile-only`, which refuses unless the rows
  from the start point in come back as committed); the tables, the Madsen
  tables and `H_REF` do not move.

## The breaking height is a significant height

- **The breaking height is a significant height, not a face height**, and the
  profile is a 2016 survey. Measured over the archive (BRIEFING §32): breaking
  lifts the 5 m figure ~20–23% into ~1.7–1.9 m of water, and the whole tide
  range moves the break point 34–53 m while changing the height under 2% —
  on a barless profile the tide decides WHERE it breaks, not how big. A
  season's sandbar would change that, and nothing here knows where it is.

## "Already breaking at 5 m" is the gain over the start

- **`surfzone.Breaking.outside_start` is true when the profile's largest Hs
  is within `START_GAIN` (0.5%) of the height at its first point**, not only
  when it sits exactly there (BRIEFING §56, 2026-11-17). On big westerly days
  the maximum lands a step or two in — South, 17 Nov 22Z, 1 m in at 5.6 m of
  water, shoaling adding 0.1% before breaking overtook it — and the card
  showed the linear 5 m figure as a break found, with no upper-bound note.
  0.5% is the march's own convergence tolerance
  (`test_the_march_is_converged_at_its_step`), not a fitted number. Heights
  unchanged on all 4,404 archived break-hours; flagged with 46232 at 2.5 m or
  more, Center 39% → 66%, South 66% → 87%, none below 1.5 m. The card's
  calculation table already marks the row and says the figure is an upper
  bound; the HEADLINE still shows the number, and how it should read when
  flagged is the owner's call (asked 2026-11-17).
- **After Madsen's friction (2026-11-18, §57; `docs/friction_shift.md`)**,
  over 1,476 archived hours with a measured tide: flagged with 46232 at
  2.5 m or more, Center 11 of 68 hours (41 before), South 32 (56), North
  none; 2–2.5 m, Center 1 of 56 (13), South 4 (20); none below 1.5 m but
  one at Center. The headline's reading when flagged is unchanged: the next
  session replaces that ceiling with a real break point.
- **Replaced by a break point, 2026-11-18 (BRIEFING §58)**: the profiles now
  start seaward of 5 m (next section) and no archived hour is flagged. The
  flag keeps its definition, at the profile's first point, as the guard for
  a sea bigger than the new starts can hold; the card's "or deeper" then
  quotes the surf zone's own depth (`b.depth_m`), no longer the tables' 5 m.

## The surf zone starts seaward of the tables

- **Each break's surf-zone profile starts seaward of the tables' 5 m start
  point, since 2026-11-18** (owner's yes, BRIEFING §58): North in 7 m of
  water (66 m out), Center 10 m (526 m), South 10 m (378 m),
  `raytrace.SURF_START_M`. The profile's `distance_m` is still measured from
  the table's start point (negative seaward), and its rows from 0 in are
  byte-identical to before. `surfzone.break_on` fixes the flux and Snell's
  invariant by the table's 5 m figure (after the rays' friction) at the
  table's start depth, as before; the march starts where the profile does.
  So the deeper start's sea is the 5 m sea carried back out linearly
  (de-shoaled, de-refracted over straight contours along the normal), and
  it may break on the way in. γ and the dissipation stay Battjes–Janssen /
  Battjes–Stive; nothing fitted.
- **The depths are measured, not chosen** (over 1,484 archived hours): at
  these starts no hour has more than 1.1e-4 of its waves breaking (Qb), and
  a 12 m start changes no breaking height by more than 0.04% (South; Center
  0.01%, North 0.00%). Shallower starts did not converge at South (8 m:
  0.83%, 9 m: 0.19%). They flag again only above 46232 ≈ 8.9 / 6.6 / 5.8 m
  (North / Center / South; archive max 3.64 m). Center's and South's
  contours stay within 1° of the chord normal over the extension (plane fit)
  and the Point Loma edge of the straight-line window moves 3–4° there.
- **North stops at 7 m**: it never breaks deeper than 3.5 m in the archive
  and is converged by 7 m. Its 10 m water is 2.1 km out on the flat 7–10 m
  shelf, where the Point Loma edge has moved 26° and the contours have
  rotated: outside the shadow, the reason the tables stop at 5 m (§29). The
  furthest it could go is the 8 m contour, 248 m out (edge +3°, contours
  ~7°).
- **Friction between the deeper start and 5 m** is in the 5 m figure, so it
  acts before the breaking rather than with it: 1.4–2.8% of height (median)
  over the extensions. Moving it into the march (Madsen, bulk, the start
  raised so the 5 m flux still comes back) changed the breaking height by
  0.00% median, at most +1.0% on one hour.
- **Controls**: with breaking off (`break_on(breaking=False)`) the march
  gives the 5 m figure back at x = 0 to the digit, on every stored profile;
  a sea nothing breaks seaward of 5 m breaks exactly as before; on the
  extended planar beach the tide moves the break point and not the break,
  for a sea that breaks inside 5 m and one that now breaks outside it.
  `raytrace --profile-only` refuses unless the rows from the start point in
  come back as committed.
- **What it did (`docs/break_shift.md`, `python -m forecast.breakshift
  --write`, ~3 min)**: below 1.5 m at 46232 nothing changes; flagged with
  46232 at 2.5 m or more, Center 11 → 0 of 68 hours and South 32 → 0, and
  none anywhere. On the formerly flagged hours the breaking height falls a
  median 2.2% (Center) and 2.9% (South), at most 6.1% and 10.0%, on
  long-period westerly hours (20 s peaks) that now break seaward of 5 m, in
  up to 6.0 m (Center) and 6.7 m (South) of water. On hours not flagged
  before: unchanged where no wave broke at 5 m with the old start; within
  0.1% where under one in a thousand did; up to 1.25% where more did (9–14
  hours a break): the new physics, not an error. **The ceiling was close to
  the real break**: breaking that starts before 5 m on these profiles is
  gentle, and shoaling still nearly balances it to about 5 m. It is not the
  big-day overstatement; that is the westerly wrap (§56a, handoff item 24).
- **Cost**: the longer profiles made `Profile.depth_at`'s scan from the
  first row quadratic in their length; it is a bisection now, identical
  values.

## On big westerly days the 5 m figure carries nothing that grows with height

- **Both terms that would make the excess grow with size are missing
  between deep water and 5 m**: the rays carry no breaking (§29, §31), and
  their friction is JONSWAP's, the same share of energy at every height
  (§32: 0.88–0.91 of Hs at every buoy size). Neither can live in the table,
  which is linear in energy. `forecast/shelfloss.py` measures what breaking
  (the surf zone's own Battjes–Janssen and γ, applied over the shelf) and
  Madsen's height-dependent friction (SWAN's form, k_N = 0.05 m, its
  default) would take, beside the shipped chain, with three controls. It
  reports and never edits. Over 285 archived hours (2026-11-17): Madsen
  takes 4–8% of the breaking height on the smallest days and 13–18% with
  46232 at 2.5 m or more (median, all three breaks), the share growing with
  size; shelf breaking alone takes nothing below 2 m and ~5% above 2.5 m,
  and adds nothing measurable on top of Madsen. **Madsen shipped on
  2026-11-18** (owner's decision, BRIEFING §57; next section). Shelf
  breaking did not: letting waves break before 5 m is the surf zone's job,
  and since §58 it starts seaward of 5 m to do it ("The surf zone starts
  seaward of the tables").
- **The westerly half of the excess is the wrap round Point Loma**: rays
  passing ~1 km south of the tip and bending north-east over the shelf, at
  14.3 s about twice a planar beach's acceptance per offshore degree at
  Center (230–249°: 2.0 against ~0.9; 280–289°: 0.95 against ~0.45). Linear,
  so it depends on direction, not size; big days here are westerly, so the
  two compound. Breaking over the straight-line window figure: 1.1–1.3× on
  south swell, 1.9–2.45× on W–WNW.

## Bottom friction is Madsen's, tabulated

- **Madsen's friction ships, on both chains, since 2026-11-18** (owner's
  decision, BRIEFING §57): SWAN's form with C = f_w·g·U_rms/√2 (Madsen,
  Poon & Graber 1988), k_N = 0.05 m and m_f = −0.08, SWAN's defaults.
  Physics from the literature, never "calibration", nothing fitted. It
  depends on the sea's height, so it cannot be one factor per ray: the
  precompute tabulates it and the runtime interpolates.
- **Precompute** (`raytrace.table(madsen_out=...)`, `--madsen-only`):
  `trace(steps=True)` records each ray's wet steps exactly as the JONSWAP
  integral sums them (the control: JONSWAP marched over those steps gives
  the stored friction to 1e-15). `madsen_losses` marches every carrying
  path deep water inward on those steps for a grid of the break's linear
  5 m Hs (0.25–6 m, 9 nodes), peak frequency (0.04–0.2 Hz, 9) and coast
  tide on MSL (−1.5 to +2.25 m, 6), the local sea shelfloss's mean-field
  estimate (H5 de-shoaled at the peak, reduced by the ray's own losses),
  solved exactly in one forward pass. A diffracted fill takes the path of
  the clear ray whose friction the table already gives it. Each frequency's
  loss table is stored as the fewest singular components that give every
  path back within 0.005 in −ln(energy) at every node after rounding
  (`compress_losses`): `<break>_madsen.json`, 1.7–2.3 MB a break, beside an
  unchanged CSV. `--madsen-only` refuses unless its re-trace gives the
  committed table back row for row (it did, all three breaks).
- **Grid sized by measurement** against the exact march over 290 archived
  hours (BRIEFING §57): worst 0.25% of the 5 m height. Tide is an axis
  (3–4% of the 5 m height per metre of tide, up to 7%); interpolating the
  peak in PERIOD is three times better than in frequency; 3 tide nodes or
  6 period nodes missed.
- **Runtime** (`nearshore.carry`, pure Python): a first pass gives the
  linear 5 m Hs and the linear peak (the bin with most energy before
  friction); the loss is interpolated linearly in Hs (zero at zero,
  extrapolated past 6 m), in period and in tide (both clamped), once per
  frequency per hour, and each ray keeps exp(−loss). `tide_m` is the
  measured coast tide on LIVE (the gauge at that hour for past trains) and
  the forecast coast tide on Forecast, MSL when there is none.
  `carry(friction="jonswap")` is the chain before §57, kept as the
  control: identical to it in every field over all 2,161 archived hours.
  `Table.load` refuses a break without its Madsen table.
- **Controls (2026-11-18, §57)**: the runtime against `shelfloss`'s Madsen
  march, hour by hour over 293 archived hours, worst 0.23% of the 5 m
  height (thinning divided out) and 0.22% of the breaking height, against
  a stated 0.3%. `shelfloss` now re-traces from the table's own headings
  with its islands and edges: from the CSV's headings (rounded to 0.01°)
  2–5 grazing rays per frequency flipped status, which, not the 20 m
  thinning, was §56's 4.1% control; on the table's own paths the march at
  MSL gives carry's 5 m height to 0.08%.
- **Everything that rebuilds carry's energies takes carry's own factors**
  (`Nearshore.ray_friction`), never the table's column: the map fill
  (with the tide `effects.friction_tide_m` records), `trainmerge._rays`.
  `bending`'s docs table states its sea: 1 m at 5 m, its period the peak,
  at MSL.
- **What it does not fix**: the local sea is a mean field from the peak bin;
  when two swells' peaks are close in energy the peak can flip between
  them from one hour to the next, and the friction with it (up to 12% of
  the 5 m height at Center on 3 of 290 hours, §57). SWAN integrates the
  orbital velocity over the whole spectrum; that is a later change.

## The MOP cross-check

- **`collector/mop.py` + `forecast/mopcheck.py`, on Actions only
  (`.github/workflows/mop-check.yml`, on demand)**: CDIP is refused at
  CONNECT from a session. The collector discovers dataset names from the
  THREDDS catalogue and checks every variable and the time units against the
  file's own DDS/DAS, stopping with what it found when they differ — a first
  run that stops is a finding about CDIP's layout. The report compares
  deep-water-equivalent Hs over 46232's, MOP de-shoaled at its own Tp and
  depth against the chain's `hs_equivalent` (before friction, which MOP does
  not apply), by 46232's swell direction. A model against a model: never a
  verification series, never read by anything that ships. North is shown and
  not read (its 10 m water is outside Point Loma's shadow, §29).
- **First run, 2026-11-18** (nowcast, 2,154 matched hours from 4 Aug; points
  D0181 / D0179 / D0168, 10 m, 0.8-1.4 km off): MOP takes W-WNW swell into
  Center and South at 0.53-0.55 of the buoy, as much as SW; the chain takes
  more from every direction, chain / MOP 1.17-1.22 (Center) and 1.29-1.39
  (South) on S-W, 1.34 and 1.43 on W-WNW. The 5 m vs 10 m difference is not
  yet separated from a fault in the tables (BRIEFING §56a).
- **The chain's own rays from MOP's points, 2026-11-18 (`forecast.mopdepth`,
  `docs/mop_depth.md`, BRIEFING §56b).** Report-only and precompute-side
  (numpy; no workflow runs it). `raytrace.table(..., h_ref=)` builds the
  tables at each MOP point (2 m seaward of it, at the seabed's own depth,
  10.77-11.0 m MSL), with the shipped frequencies, headings, islands and
  edges and no Madsen; cached in `data/live/mopdepth/` (~2 min a table).
  Control: each break's own start gives the committed table back row for
  row (0 of 23,040 differ, all three). **It is not the place**: over the
  same water the chain gives 1.24-1.40 x MOP at Center, 1.19-1.41 at South,
  1.24-1.40 at North, as high as or higher than from 5 m; from MOP's point
  to the break adds 0.94-0.95 (Center), 0.98-1.15 (South, the most on
  W-WNW). Not diffraction (hard edges alone 1.14-1.37), not the fill rays
  except South's W-WNW (Point Loma fill 19% of its energy), not direction
  (arrival within ~3 degrees of MOP's Dp at Center). Common to all three
  points, and it moves with the buoy's directional reading (Fourier
  1.27-1.70). The chain's energy up to 0.1 Hz alone is as big as MOP's whole
  Hs (0.86-1.08; Center W-WNW 1.25): which band MOP is short in needs MOP's
  own spectrum.
- **MOP's depth datum** is not in `points.json` (`metaWaterDepth`, 10.0).
  The seabed reads 10.77 / 10.98 / 10.95 m below MSL at D0181 / D0179 /
  D0168: 10 m NAVD88 is 10.77 m MSL, so NAVD88 (or MLLW, ~the same here) and
  not MSL. Inferred, not read: CDIP is unreachable from a session. It moves
  the comparison by 0.01-0.02.
