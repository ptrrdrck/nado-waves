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

## Build order

1. **Beach geometry** — done, `forecast/geometry.py`. Which bearings reach each
   beach at all, from coordinates alone. Coronado's three breaks digitised
   2026-09-14; the Coronado Islands and the Baja coast charted from NOAA's ENC
   2026-09-20, which split the islands in two and closed the southern arc on
   land; the Point Loma tip charted 2026-09-22, per break; and the same day
   the three break chords themselves, each endpoint the harbour-band vertex
   nearest the hand trace (BRIEFING §27). **Every coordinate the Coronado
   aperture uses now comes from NOAA's ENC** — except WHERE along the coast
   each break sits, which is a surfer's choice and no chart can make. If a
   break is ever traced from imagery again, `breaks_from_imagery` names it on
   the surface.
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
   one on both chains: KNZY on Now, the NWS grid on Forecast (GFS-Wave's
   buoy wind only for an hour the grid lacks, and the calculation row says
   whose).
   **Then the surf zone, SHIPPED 2026-09-26** (BRIEFING §32):
   `forecast/surfzone.py` carries that sea from 5 m in over each break's
   surveyed profile (`<break>_profile.csv`, the 2016 CoNED beach, not this
   season's bars) at the tide of the moment, Battjes–Janssen breaking with
   Battjes–Stive's γ, and reports the largest Hs and the depth it breaks in.
   **The number on every break card is that breaking height**, labelled with
   its depth, on both chains — a significant height, never a face height; the
   5 m figure stands in only when there is no tide, never a breaking height at
   an assumed one. The straight-line window figure survives only in
   the card's calculation table, which folds out under the headline from a
   caret at its end (up closed, down open; owner's design 2026-09-26) and
   gives each effect one row — buoy, windows, refraction, diffraction, bottom
   friction, shoaling, local chop, wave break — as Calc / Change / % / Hs, the
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
6. **App surface — built, `app/forecast.html`, published by
   `forecast/publish.py`.** **Two tabs, and they are two evidence chains
   rather than two views of one.** *Now* is built only from measurements
   (`now.json`: NDBC directional spectrum, KNZY METAR, measured water level);
   *Forecast* only from a model (`forecast.json`: GFS-Wave). The observed
   tab's label reads **“LIVE”**, quotation marks included (owner's call,
   2026-10-01, replacing 2026-09-30's NOW(ISH)): it points at the updating
   feeds, the quotes keep it from claiming the present, and each card's
   countdown is what states how live the reading actually is. Each renders its
   own "standing on" block from whatever keys its file carries, because the
   two name different levels — both on `app/docs.html`, each under its own
   heading and from its own file, beside the "physically derived" caveat and
   the cycle line; it is the live page's one link (it replaced info.html and
   geometry.html, 2026-10-02).
   **The buoy's tab reads "Buoys"** (owner's request, 2026-10-06; BRIEFING
   §39), on both chains, its id still `buoy`. On LIVE it holds 46232 and under
   it **46047, Tanner Banks**, built the same way — combined height, maximum-
   entropy trains split by period then direction (§40) — with its own name,
   observed time, countdown and "Open ocean witness, not carried to any
   break." line (`forecast/buoys.py` → `buoys.json`, its own step in the
   collection). **Each buoy's provenance follows its own measurements**
   (owner's call, same day): 46232's reading, then the card's provenance
   (46232's), then 46047's block with its provenance in the same style.
   **It feeds nothing**: its own module and file, never a key in now.json, so
   the context-station guard still keeps "46047" out of now.py and the chain,
   and `tests/test_buoys.py` keeps `through`/`carry`/the surf zone out of it.
   Its countdown is measured, not borrowed: stamped :20 and :50, 25 min
   typical and 85 worst, bracketed against the collection log on 148 stamps.
   Its opposed lobes (≥ 150° apart, 168 over the archive; 46232 has none) are
   real — 46232 saw the southern one on 163 of 163 — and since §40 each is
   its own train.
   **Under each buoy's reading, a rose** (owner's request, 2026-10-06;
   `forecast/rose.py`, in `buoys.json` as `roses`): one per spectrum, the
   energy in sixteen 22.5° sectors, petals pointing FROM, integrated as
   `at_buoy` integrates it so the sectors are the reading's own m0 (a test
   pins it). A Height / Period switch, one state for both: Height is each
   sector's energy as 4√E — the petals combine in energy and do not add to
   the combined height — and Period each sector's share split into five
   bands (< 8, 8–11, 11–14, 14–17, 17 s +), greys from the faintest rule to
   ink. Every spectrum of the last six hours loops on ONE clock for both
   buoys, so the two show the same moment, then holds on the newest; a frame
   shows until its successor was due (each buoy's own stamp spacing) and a
   gap says so — never the frame beside it — but the newest stays until a
   newer one lands, because a stamp not out yet is not a gap. Each buoy has
   its own scale per view, fixed over its loop (owner's request, same day:
   rounded up to a ring and shared, 46232's largest petal filled 22% of its
   rose). Rings EVEN, at most five, the outermost the edge: the loop's
   largest petal rounded UP to the next ring — the next whole foot, every
   2 ft past 5 ft — so no petal passes it (owner's calls: an edge at the
   petal exactly drew no ring there; 2, 4 and 5 ft read as uneven, 7 Oct).
   The scale is one line under the rose, never a figure on the plot; play /
   pause is a symbol button left of the timeline. **A tapped train row lights
   its PERIOD RANGE on the rose** (owner's request, 2026-10-08): the bins
   that train holds in the newest spectrum (`Train.bins`, ignored by
   equality) — and, for a train divided from a band of two directions
   (§40), the headings it holds (`Train.arc`), since its twin shares the
   range — and each frame's share within them, in ink over the rose
   dimmed; the readout names the range, never "the train", because nothing
   follows a train between spectra (owner's question, same day: Origin's
   ridges are the one tracker, and a later step could follow one). Only
   under the reading split from that same spectrum (`trains_from_utc`); a
   new spectrum clears it. Reduced motion opens paused on the newest. LIVE
   only; carried to no break. The
   Forecast tab's Buoys tab holds 46232 alone. A 46047 line on the Height
   chart is the next step, not built.
   **The Forecast tab reaches 48 h back** (owner's decision, 2026-09-26). For a
   past hour it shows what the page showed then: the newest run published
   before that hour, from `forecast.json`'s `past`, read back from the
   permanent log — **the full card, drawing and calculation table included**,
   from that build's own hour as it was published (`46232_shown/`). A past
   hour whose build kept only a headline says "The calculation for this hour
   was not kept" rather than borrowing another build's detail. Under it, in
   red, is the measured chain rebuilt for that hour (`measured.json`). It opens on the first hour not yet passed, never
   one that has. **Under each Now card are the hourly charts** (owner's
   requests, 2026-09-27; `forecast/series.py`), in the owner's order
   (2026-10-05): Height, Window (ratio), **Origins** (owner's request, 2026-10-03;
   below) and North vs. South (north less south) — the 24 h %K view taken off
   the menu the same day by the owner's call, its spec (`buildSpec`'s
   "range") and `series.py`'s pct_k / pct_d kept so it can return — switched above the plot, folded out from an
   "Charts" line with the calculation's caret (closed until opened) — the
   last line on every card, below the provenance and under the card's one
   rule; the provenance has space above it, no rule (owner's calls,
   2026-10-02). **Each tab plots its own line in ink** — the break
   on a break's tab, the buoy on the buoy's (owner's call, 2026-09-28, after
   a round of per-break colours was rolled back). **Height alone draws the
   other two breaks under it** (owner's request, 2026-10-05), lighter and
   thinner in `--faint`, north to south, the second dashed — greys and a
   dash, never per-break colours — so the three compare at a glance on one
   axis; the readout names all three, the tab's own first. The buoy's tab and
   every other view keep one line. The Window chart carries a
   direction strip under it on the same hours: a dot an hour where the
   buoy's peak came from, never joined (the peak jumps between trains), over
   the break's open windows shaded. It says where the peak sits, never
   "inside" or "outside": the share is the whole spectrum through the
   windows, and a binary test on one bearing is what BRIEFING §10 retired.
   The readout sits against the plot and grows upward as it wraps, in room
   kept for three lines so a reading that wraps while scrubbing never moves
   the plot. The x axis zooms and pans — pinch, drag, ctrl + wheel, and
   1D / 7D / 1M / All — and a sideways swipe reads the hours under the finger
   into a readout ABOVE the plot, keeping the last on release; a vertical
   swipe still scrolls the page. It opens on the last day (owner's choice;
   the chart is picked from a menu, not tabs); the week is `series.json`, rebuilt
   each collection, ~37 s; past it, the committed archive (`series_all.json`
   from `data/series/`, fetched only when asked for). It is the observed
   chain; every past hour is REBUILT with today's chain, not
   remembered, and docs.html says so; a missing hour is a gap in the line at
   every zoom. **The Forecast tab has its own charts in the same place**
   (owner's request, 2026-09-29): the model's 3-hourly hours from 48 h back
   to the run's end, drawn from `forecast.json` (`fcSteps`), never from the
   Now series. Three views (owner's call, 2026-09-30, which folded the old
   "Forecast & observed" into the runs view): *Forecast + Observed* (the
   newest GFS-Wave run over the last eight runs' lines from
   `forecast.json`'s `runs`, `forecastlog.recent_runs`, with 46232 carried
   in beside the passed hours in red), *Swell trains*
   (a dot per train at its period, sized by height, with a direction strip
   over the break's windows) and *North vs. South*; and on the buoy's tab
   only, *Ensemble* (below, build order 5). **Only the Ensemble view carries
   a band, and only beside the measured share of hours 46232 fell inside it;
   none shows a forecast-minus-observed difference**: nothing measures the
   breaks, and a run spread is not a range the swell will fall in — the page
   says so. The two tabs keep their own window, picked hour and
   view (`useChain`). **The Wind and Tide cards have charts too** (owner's
   request, 2026-09-30; `forecast/windtide.py` → `windtide.json`), sharing
   the tab's window and picked hour. On Now, what was MEASURED each hour:
   KNZY's report taken in the hour up to it — never carried into the next,
   unlike `measured`'s two-hour as-of, because a carried reading draws as a
   second measurement — and the gauge's sample AT the hour on the open coast;
   plus the tide's next 24 h of harmonic prediction with the departure,
   dashed, the tab's one modelled line beside its one modelled number. On
   Forecast, `forecast.json`'s `hourly` (the NWS local wind, and the card's
   tide) to the run's end, the measured hours in red, and GFS-Wave's own
   buoy wind in grey (owner's request, same day) — hourly to +120 h and
   3-hourly after, so its line `bridge`s the model's own spacing, never a
   measured gap. Read from the archives, not rebuilt: today's chain cannot
   change a past hour. Each has a second view (owner's request, 2026-10-01):
   *Shore direction* (owner's name) — per hour of the reader's day, over
   every day counted, how often the wind at the open swell tab's break was
   offshore / cross / onshore / calm, by the card's own `sense()` against
   that break's normal over KNZY's hours, in greys only, the readout saying
   "over N days" because a bar is many days' one reading, not one hour's —
   and *Departure* — the gauge's measured-less-predicted each hour and the
   trailing 3-day mean the forecast adds (`windtide`'s `departure_m` /
   `departure_mean_m`, coast-scaled like the card's). **Those two are the
   LIVE tab's only** (owner's call, 2026-10-02): on Forecast a "how often"
   over a week's forecast threw away which day, and a measured departure has
   no future hours. Forecast's second views are *Shore direction* as a week
   grid (a row a day, a square an hour, the NWS verdict at the open break)
   and *Daily range* (each day's biggest swing between CONSECUTIVE predicted
   turns, from `tide_turns` — never the calendar day's highest high less
   lowest low, which dropped a lower low that had crossed midnight and drew
   a false neap). **A wind of 3 kt or less is "light", not offshore** (owner's
   report, 2026-10-02: the NWS grid's 2–5 kt northerly every night painted
   the week grid 100% offshore 11 PM–10 AM, where KNZY over the same hours
   was calm or variable 29% and ≤ 3 kt 44%). `LIGHT_KT`, Beaufort force 1,
   lives in the page's one `sense()`, so the card's line and both Shore
   direction charts change together. **The card still names a light wind's
   side** ("light offshore", "light cross-shore", "light onshore"; owner's
   request, 2026-10-07) while the charts count it as light or variable, and
   **0 kt is "calm"**: KNZY's `00000KT` is archived as 0° at 0 kt, and the
   card says calm rather than "N 0°"; a METAR's `VRB` (a speed, no
   direction) reads "variable at …" and "light and variable" or
   "variable" at the break, never "not collected". The Tide view is shaded by night on both tabs
   (`forecast/daylight.py`: NOAA's solar equations at the center break from
   spots.json, within a minute of `astral`; `nights` in both payloads).
   **Right above each LIVE swell tab's Charts line, an Origin line** (owner's
   request, 2026-10-02; `forecast/origin.py`, BRIEFING §37) that folds out
   like the charts — its own caret, closed until opened, one open state for
   every tab, kept across a refresh — under a rule of its own (owner's call,
   same day, replacing a block under the drawing): where each train now arriving was
   born, read BACKWARDS off 46232's spectrum — every hour's swell-band peaks
   linked into ridges and fitted f = g(t − t₀)/4πR. **An origin belongs to a
   train**: a break shows only arrivals that are one of its own card trains,
   which is the aperture's answer, never a bearing tested against a window.
   **Its direction is never 46232's** (it reads north-west swell 50–74° too far
   south — half of that is its mean averaging two lobes, the rest a westerly
   lobe that pins near 270°, not at any island's edge; BRIEFING §38), but
   46047's only; without it there is no place. **46086 was dropped from
   Origin 2026-10-05** (owner's decision, §38a): its north-west lobe stays
   near 279° whatever 46047 reads, so it holds no reading of where that swell
   came from; it stays in the hurricane gate and on hourly collection. And a
   bearing is **withheld** when 46047's energy at the ridge holds two
   directions of ≥ 15% each (`origin.SPLIT_SHARE`, `transform.lobes`): its
   mean would point between them. A withheld arrival keeps distance and date,
   lists the directions it held, and is a storm's only from within 45° of one
   of them — withholding a place never makes a name easier. Two buoys
   reading one storm differ by ~18–25% at the median, so distances are rounded
   to 500 mi and 500 km and said "about", and the place is a sea. Shown only
   once a ridge passes the reading gate (≥ 12 h, R² ≥ 0.8), "Read off the
   swell, N h so far" while it runs; otherwise the last readable arrival at that
   break in the last 21 days. **Every origin is the same three lines** (owner's
   design and wording, 2026-10-04): what it is ("Hurricane Polo  winds 121 mph
   (105 kt)", a sea, or "Unplaced storm"); "16.0 s train, about 700 mi
   (1,100 km) bearing 161° SSE on Sep 28" (an unplaced storm has no bearing; a
   hurricane adds "N h read so far", the hours its band has arrived at the
   gate buoy; the last arrival's train is its peak hour's, `peak_period_s`);
   and how it is known (the match with its count at each buoy, the hours read,
   or "Arrived …, no longer arriving"). Then ONE provenance block for any mix:
   every train is read off 46232's spectrum, a hurricane's too; "and storms
   read backwards from them" only with a reading; "National Hurricane Center
   best track, an analysis" only with a hurricane — each buoy as NDBC names
   it, "Tanner Banks, CA (NDBC 46047)", from `origin.station_names` in
   now.json (fetched metadata, never typed). **No upstream sighting is shown, ever**: measured, the predecessor's
   "confirmed in transit" check is blind to the distance (scaling every distance
   by 0.7 or 1.3 moved its hit rate by a point). LIVE only: the Forecast tab
   has no Origin. **Checked against NHC's best tracks** (b-decks archived
   byte for byte in `data/besttracks/` by `collector/besttracks.py`, from
   `origin-tracks.yml`; BRIEFING §37a–b). By position (`origintracks`), one of
   seven readings within ~4,000 km "matched" Polo — **run FORWARD it does not**
   (`forecast/stormtrack.py`, `docs/origin_best_tracks.md`): each ≥ 64 kt fix
   sweeps a band in a buoy's time-frequency plane, scored as the rank of the
   maximum-entropy energy from the storm's bearing, against the band shifted
   ±5/10/15 d and the sector turned ±45° (energy, not rank: a spread lifts its
   neighbours' ranks too). Marie is explained at 46047 and 46086
   independently; Polo at no buoy on no day (best 0.65 against a 0.7 gate
   fixed before the run, its peak days behind Baja); and the two ridges that
   agree with a storm in timing AND bearing do so in 28% of bearing shuffles
   (under §38a's bearings, one ridge, Polo's, and 20%: the "possible" Nolo
   ridge's bearing is withheld; `stormtrack --ridges`).
   Timing alone matches almost anything. **What the card shows instead
   (owner's request, 2026-10-03; BRIEFING §37c): "Hurricane X" under Origin**,
   NHC's track run forward with paths across land dropped
   (`forecast/landpath.py`, Natural Earth 1:10m via `collector/coastline.py`),
   **with its MATCH** (owner's request, same day, BRIEFING §37d: where a train
   came from is separate from how big it is, so it may carry a figure): as of
   the newest spectrum at 46047 or 46086, the share of the same track moved
   BACK in time (every 12 h, to 30 days, each as of its own moment and ranked
   against its own preceding 40 days) that the real band beats on timing AND
   direction. Stated only with ≥ 20 trials and the real band livelier than
   typical on both; named from 50% ("weak"), "partial" from 70%, "strong"
   from 90%. A count, never a probability or a confidence — and the words are
   read against the control in `docs/origin_best_tracks.md`: every track moved
   8–24 days LATER was named at some moment 12 of 55 times, partial 9, strong
   2 (both onto another swell from the same bearing: the test cannot tell two
   sources on one bearing apart). Backtest: Marie strong at both buoys, Polo
   partial (78% at best), Odalys partial (82%). On a break only when one of its
   card trains is the one arriving — of two (one band, two directions, §40),
   the one within 45° of the storm's bearing. Placed and sized from NHC's fix that sent
   that train, rounded to 100, never from Origin's distance; it replaces
   Origin's reading of the same train. The b-decks are archived hourly by
   collect-beach-inputs.yml (their one writer). The directional sector is
   integrated in closed form (`spreadmethod.mem_sector`, equal to MEM's 1° bins
   to 1e-15, ~60× faster); the match loads 90 days of the two buoys and costs
   ~5–7 s a collection while a storm's band is open at either, a file read
   when none is.
   GFS-Wave's hindcast (`collector/wavehindcast.py` → `data/wave_hindcast/`,
   origin-tracks.yml its one writer) is a REPORT column, never on the card.
   **The Origins chart** (owner's request, 2026-10-03;
   `forecast/originhistory.py`, BRIEFING §37e), on every LIVE swell tab, the
   buoy's included: over time, a black dot every 6 h for each hurricane the
   card would have named AS OF that moment, at the distance of NHC's fix that
   sent that tab's train, its name by its first dot in view; and a grey bar
   over the hours each Origin arrival no storm is named for was arriving, at
   its dispersion distance. Log miles, 500–10,000; a bearing strip under it,
   never tested against the windows. A mark is on a tab only where it was that
   tab's card train (an arrival at its peak hour). An arrival is the storm's,
   on chart AND card, only when the storm's train there is the ridge's own
   AND, if Origin has a bearing, from within 45° of the storm's
   (`SAME_SOURCE_DEG`): on 29 Sep a 304° ridge shared a period with Polo. A
   moment with no 46232 spectrum places a storm on no tab — Marie arrived
   during the September outage and is on no tab. The archive
   (`data/series/46232_origins.json`, ~75 s) is series-archive.yml's;
   each collection writes `data/live/origins.json` from it plus the last 21
   days' arrivals, the named moments since its end (≤ 7 days), and now.json's
   own hurricanes (~1 s, more while a band is open).
   **No chart carries a description under it** (owner's call, same day):
   what each draws lives on `docs.html` and in the plot's spoken label. The
   one line kept is the Ensemble's measured coverage, because the band is
   drawn only beside it. Opens on Now;
   a refresh keeps the tabs the reader chose (sessionStorage, so a new visit
   still opens on Now); a stale or missing observation
   says so and points at Forecast rather than falling back silently. The
   delivery repository is separate because `data/live/` is gitignored here, so
   there is nothing at `data/live/forecast.json` for a published page to fetch —
   not, as this said until 2026-09-25, because this repository is private. It
   has been public since the Actions-limit switch, and the split survived that
   change for its other reasons. The forecast workflow builds a flat bundle (`index.html` +
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
   (geometry / model / calibration / observation) on screen — on
   `docs.html`, one tap from the live page — not just in the README. **Coronado's three breaks only, by decision (2026-09-18).** Breakers
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
- **GitHub's scheduler is throttled, and frequency is not a lever.** Measured
  2026-09-22 across four schedules on this repository: the rate actually
  DELIVERED sits near 0.2 runs an hour whatever the cron asks. 5/day got 84%,
  hourly 26%, 2/h 11%, `*/10` **2%** — and `*/10` came out lower per hour than
  hourly did. Raising the cron to buy freshness is a falsified idea; it was
  tried and reverted the same day. Reliable collection is driven from outside
  by `repository_dispatch`, and the cron is a backstop — `docs/collection_trigger.md`.
  Keeping it inside Actions was rejected on cost: spacing runs apart needs a
  job that sleeps, and a sleeping job holds a runner for the gap, ~24
  runner-hours a day at any cadence.
- **An update countdown is three real events on the clock, not intervals added
  to the reading on screen.** `forecast/now.py` walks: the next time the source
  PUBLISHES (`PUBLISH_MINUTES` — swell `:00`, wind `:52`, tide every 6 from
  `:00`, all measured), plus how long until that is FETCHABLE
  (**no source is fetchable at its own stamp minute** — modelling the tide as
  though it were promised a sample CO-OPS had not written yet, turning a reading
  eight minutes old into a red card), rounded
  up to the next COLLECTION from `EXTERNAL_TRIGGER_CRON`; the page then adds its
  own refresh interval, because only it knows that.
- **The lag is a distribution, so it takes two numbers, not one.** A single
  deadline has to choose between crying wolf and quoting a figure that almost
  never applies, and both are dishonest on screen. `PUBLISH_LAG_MIN` is the
  measured typical and the countdown runs to it; `PUBLISH_LAG_LATE_MIN` is the
  measured worst and the card only turns red past that, saying "update due" in
  between without claiming anything is wrong. Measured 2026-09-25 by bracketing
  each hour against the collection log: **4 of 6 spectra land by H+15 and one
  took H+35.3**, so the old single value of 27 was above the typical AND below
  the worst — twelve minutes pessimistic on the common hour, promising an hourly
  source **100 minutes from stamp to screen where 80 was honest**, and still red
  on the late one. Swell 15/36, tide 5/8, wind 3/4. n = 6 for the swell, which
  is thin; revisit as the archive fills (re-bracketed 2026-10-06 on 260: 15
  holds, and 36 rounds to the H+45 run, red on 4 of 260 that came later —
  BRIEFING §39, not changed). 46047 on the Buoys tab: 25/85, its own, in
  `forecast/buoys.py`, through `now.deadline`'s same arithmetic. The first version added
  `source interval + 2 × collection interval` to the reading on screen instead,
  which charged a tide sample due in ninety seconds a full six minutes and then
  twenty more as slack — **over twenty minutes of countdown for a source that
  publishes every six.** There is no slack term now: the external trigger lands
  on time to the second, so a missed collection is a real failure and the card
  should say so. **46232's `:26`/`:56` is STANDARD MET**, a different product in
  `data/observations/` that no card reads; the Now tab's swell is the hourly
  directional spectrum.
- **A cadence promised on screen must match the trigger that keeps it.**
  `COLLECT_INTERVAL_MIN` in `forecast/now.py` feeds each Now card's countdown.
  When the cron said `*/10` and GitHub was delivering one run every four hours,
  every card called itself late against a schedule nobody was keeping — the
  countdown reported the gap between the request and reality rather than
  anything about the data. The trigger is now external, so `now.py` declares
  `EXTERNAL_TRIGGER_CRON` and `tests/test_now.py` pins the interval to it, pins
  the GitHub cron to being a slower backstop, and pins the wind offset.
  **No test can reach cron-job.org** — changing the interval there without
  changing `EXTERNAL_TRIGGER_CRON` is the one move nothing catches.
- **46232's spectra do not publish on a fixed minute.** Measured 2026-09-25 by
  bracketing each hour between the last collection without it and the first
  with it: 23Z was still absent at H+16.7 while 01Z had landed by H+15.0, so
  there is no single publication minute — it jitters across roughly **H+7 to
  H+27**. A trigger phase-locked to the swell would therefore be early on some
  hours and twenty minutes late on others; only the INTERVAL bounds staleness
  against a jittering source. The phase is spent instead on KNZY's `:52`,
  which is pinned (81 of 95 archived observations), and the `:55` run catches
  it three minutes later against a measured median of 110.
- **Keep the staleness alert** — no new observation in 48 hours, notify. A
  silently dead collector loses days that cannot be recovered. It did not
  visibly fire for 46232's 16-day outage; **partly explained** (BRIEFING §8):
  `health.newly_dark` deliberately suppresses anything dark longer than
  2 × 48 h, so the alert had 09-01 to 09-05 to be seen and has been silent by
  design since. Whether it was ever *delivered* in that window is still
  unchased. A station that had never reported at all had no date to age from
  and alerted forever; `first_checked_utc` fixes that. **The directional
  spectra are checked too, file by file** (`staleness.spectra_report`, since
  2026-10-05): the standard met keeps a station "live" on any column, and
  46086 reported wind for ten days after its wave sensor stopped on
  2026-09-25 with nothing noticing. A spectrum newly past 48 h alerts once; all
  of them stale is a dead spectra collector.
- **GitHub Pages caches for ten minutes and you cannot change it.** Measured on
  the live bundle 2026-09-25T15:48:58Z: Pages serves through Fastly with
  `Cache-Control: max-age=600`, and Pages exposes no header configuration, so
  this cannot be fixed on the publishing side. Ten minutes of permitted
  staleness against a ten-minute collection cadence means a cache HIT can hand a
  reader a `now.json` one whole collection behind — and its age line would be
  honest about a reading that had already been superseded. So every payload
  fetch carries a `?v=<epoch ms>` (`fresh()` in `app/forecast.html`): a distinct
  URL cannot be answered from any cache by definition, which turns a policy we
  do not control into arithmetic we do. `cache: "no-store"` stays alongside it —
  the parameter defeats shared caches, `no-store` defeats the browser's own, and
  they are different caches. **The sample that confirmed the mechanism was
  itself a MISS** (`Age: 0`, `x-cache: MISS`, `Last-Modified` 3m14s before
  `Date`), so `no-store` was honoured there; the reason to fix it anyway is that
  honouring a client `no-cache` is Fastly CONFIGURATION rather than a guarantee,
  and says nothing about what another edge node holds for the next reader.
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
  watched for the failure it expected. And the reverse (2026-09-30): on the
  NEWEST cycle a 404 almost always means "not out yet" — 46232's bulletin
  lands ~5 h 25 min after the nominal time, the directory filling over an
  hour — so `live.fetch_latest` says the run is not published yet and which
  run it is showing, rather than printing the URL.
- **A rejected push of an append-only log re-appends; it never rebases.**
  Measured 2026-09-26: the forecast build and the shown-hours seed both
  appended to one JSONL, the rebase conflicted, and the old retry loop
  (`git pull --rebase ... || true`) pushed an unchanged HEAD, read
  "Everything up-to-date" as success and lost the build's rows. `forecast.yml`
  and `seed-shown.yml` now reset to the new tip and re-run their idempotent
  append; `model-bias.yml` aborts loudly. The same `|| true` loop is still in
  the collectors' workflows, where each file has a single writer.
- **`data/series/` is derived and tracked, and that is not a breach either.**
  The chart's zoomed-out views need every archived hour through today's chain;
  at 0.18 s an hour a year is ~26 minutes, so a collection cannot rebuild it
  and the page cannot wait for it. `series-archive.yml` rebuilds it whole
  (35 s for 1,309 hours on four workers, measured 2026-09-27; a year is about
  five minutes) daily, on chain changes, and when asked. Deterministic, so an
  unchanged chain commits only new hours: ~0.9 MB a year. It is never mixed
  with another chain: every collection checks it against the week it has just
  rebuilt plus eight older hours, and on disagreement `series_all.json`
  carries no hours, the page says the earlier hours are being rebuilt, and the
  collection dispatches the rebuild. A stored gap that has since landed is the
  archive behind, not the chain moved, and does not count.
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
                        GFS-Wave bulletins, localwind.py (the NWS forecast
                        grid's hourly wind at Coronado, fetched by the
                        forecast build, not archived), gefswave.py (GEFS-Wave's
                        31-member bulletin at 46232: mean and spread, no
                        direction — BRIEFING §35),
                        probe_spectra.py (are directional spectra reachable?),
                        spectra.py (archive them: 46232, 46047 and 46086
                        hourly (`--hourly`; HOURLY_STATIONS, held by a
                        test to the union of Origin's and the hurricane
                        gate's readers, so dropping a reader never drops a
                        collection) —
                        and 46258 from collect.yml; context for checks, read
                        by no height), wind.py (KNZY),
                        wavespec.py (WW3's own spectrum + wind, not archived),
                        tide.py (9410170 — measured, hourly predicted, and
                        CO-OPS's own hilo TURNS in a third file),
                        tidestations.py (every CO-OPS station near the breaks,
                        their offsets and datums, and a 30-day comparison
                        window — run on Actions; BRIEFING §32),
                        shoreline.py (NOAA's ENC coastline, by named REGION —
                        `coronado` carries the break chords, `baja` carries
                        the islands and the Mexican coast, `point_loma` the
                        tip, `channel_islands_south`/`_north` the eight
                        Channel Islands, read by no chain (§38) — run on
                        Actions),
                        enc_layers.py (what else the charts carry: the jetty,
                        the soundings, a finer coastline — BRIEFING §22),
                        beachlog.py + beachlog_import.py (the observation log),
                        bathymetry.py (USGS CoNED seabed, regional 32 m and
                        nearshore 8 m, NAVD88; the MSL offset is fetched from
                        CO-OPS on Actions — needs requirements-precompute.txt)
    app/forecast.html   the app surface — Coronado's three breaks       [built]
    app/docs.html       the documentation, the live page's one link: every
                        card, chart and calculation; a left menu built from
                        its own headings (a drawer on a phone) and full-text
                        search; the caveat, the cycle line and both chains'
                        standing-on blocks; the model-geometry drawing,
                        filled by `forecast.geomviz` from spots.json and never
                        hand-edited with coordinates; and ONE worked hour
                        through the chain that `tests/test_docs.py` rebuilds
                        from the archive. Shipped by `forecast.publish` in
                        BOTH bundles. Never links to the observation log.
                        Replaced info.html and geometry.html 2026-10-02
                        (owner's decision); `publish.RETIRED` deletes them
                        from the public site
    app/docs_wording.md the page's prose by section id, for the owner to edit
                        on a branch: generated by `python -m forecast.docswording`,
                        pinned to the page by a test. Edits are carried INTO
                        docs.html by hand and the file regenerated; `>>`
                        lines are notes to Claude, never page text
    app/beachlog.html   the phone form, owner build (shared store)
    app/beachlog-observer.html  same file, observer build — no sign-in, entries
                        stay on the phone and are handed back as text. The two
                        differ only in <title>; a test enforces it. The repo CSV
                        stays the system of record for both.
    forecast/
      geometry.py       which bearings reach each beach          [built]
      transform.py      spectrum -> energy through the aperture   [built]
      spreadmethod.py   Fourier vs maximum-entropy D(f, θ) from the same
                        four buoy moments, over the archive; reports,
                        never edits (BRIEFING §28)              [built]
      raytrace.py       PRECOMPUTE (numpy): backward rays from the 5 m
                        contour off each break to deep water over the seabed
                        grids — refraction and shoaling (S·c·cg invariant),
                        islands' shelves included; diffraction at the islands,
                        the Point Loma tip and the Baja tangent, hard and soft
                        per ray; bottom friction per ray; plus each break's
                        wind fetch and cross-shore profile.
                        Writes data/nearshore/; never imported by the
                        forecast                                  [built]
      nearshore.py      carries a spectrum through those tables, pure
                        Python; local fetch-limited chop, fresh over
                        closed fetches and grown on over the open water
                        between the buoy and the break; reports
                        against the aperture                        [built]
      surfzone.py       5 m to the break on each profile at the tide,
                        Battjes–Janssen, pure Python                [built]
      tidesite.py       the bay gauge's level carried to the open coast
                        (x0.944, measured against La Jolla), and the
                        measured departure from the epoch prediction [built]
      live.py           the live forecast, Coronado only          [built]
      now.py            the OBSERVED reading, measurements only    [built]
      forecastlog.py    the permanent record of what each build said,
                        the 48 h of it the page reads back, and the
                        last eight runs' lines for the Runs chart  [built]
      measured.py       the observed chain rebuilt for each past hour:
                        exact-stamp spectrum, wind and tide as of then [built]
      series.py         the same, every hour for the last week, with the
                        south-less-north, window ratio and %K the Now
                        tab's chart draws; one rebuild feeds both files;
                        and `--archive`, every archived hour into
                        data/series/ (series-archive.yml only)      [built]
      windtide.py       the measured wind and tide each hour, and the
                        next day's predicted tide, for the Wind and Tide
                        cards' charts; read from the archives   [built]
      daylight.py       sunrise and sunset at the center break, for the
                        Tide charts' night shading; computed, not fetched [built]
      modelbias.py      GFS-Wave's bias at 46232 through each break's
                        windows; reports, never edits              [built]
      ensemble.py       GEFS-Wave's mean and spread against 46232: how
                        often the buoy fell inside the spread, and the
                        page's Ensemble block; reports, never edits  [built]
      exposurebias.py   GFS-Wave's bias from the unshadowed 46047 to the
                        most shadowed buoy, and the model's shadow against
                        the measured one; reports, never edits     [built]
      publish.py        the public delivery bundle                 [built]
      units.py          ft/mph first, m/kt in parentheses -- display only
      tideturns.py      the next high/low, and why its direction is not
                        differenced from the measured level      [built]
      trainsplit.py     how a spectrum is split into trains: a synthetic
                        control with a known answer (buoy noise, maximum
                        entropy, as the chain reads it) and the archive,
                        period-only vs 10° watershed vs shipped; reports,
                        never edits (BRIEFING §40)                [built]
      nwbearing.py      46232's north-west bearing: the mean against its
                        lobes, the hull control, the Channel Islands' edges,
                        what the lobe carries into each break, shown train
                        headings against their own lobes; reports, never
                        edits (BRIEFING §38)                      [built]
      shorenormal.py    surveyed shore normals vs the digitised chords,
                        swept over scale; reports, never edits    [built]
      blockeredge.py    a blocker's edges read off the charted coast, against
                        what spots.json claims; reports, never edits  [built]
      geomviz.py        draws the vertices the model uses, the ray to each
                        edge's vertex, and the distances between them, into
                        docs.html                                  [built]
      docswording.py    docs.html's prose as app/docs_wording.md, by
                        section id, for editing; --check            [built]
      siting.py         which BUOYS observe the swell that reaches it  [built]
      spots.json        breaks and blockers    [Coronado digitised; others not]
      swell.py          great circles, bearings, group velocity
      utm.py            lat/lon <-> UTM 11 metres, pure Python (the grids' CRS)
      stats.py          load_column, least_squares, rmse, circular means
      dispersion.py     the 1/T dispersion fit, and arrivals in a buoy's
                        dominant period (historical files only)
      forensics.py      a past swell's origin off the historical record;
                        "seen upstream" tests no distance (BRIEFING §37)
      buoys.py          the LIVE tab's Buoys tab below 46232: 46047 at the
                        buoy, carried to no break, its own countdown  [built]
      rose.py           one spectrum's height and period rose by compass
                        sector, for the Buoys tab's six-hour loop   [built]
      origin.py         the LIVE tab's Origin: each train's dispersion
                        ridge in 46232's spectrum, bearing at 46047
                        [built]
      originreport.py   the measurements behind it; reports, never edits
      origintracks.py   readings against NHC's best tracks, by position
      originhistory.py  the Origins chart's marks: every arrival and every
                        named moment over the archive, and the page's
                        file from it each collection             [built]
      stormtrack.py     each hurricane run forward to the buoys, with
                        controls, backtest and GFS-Wave cross-check; and
                        `live`, the card's "Hurricane X" gate       [built]
      landpath.py       does a swell's great circle cross land?   [built]
      verify.py         bias, RMSE, scatter index, calibration, band coverage
      residual.py       is the remaining error recoverable? (it was not, before)
      beachverify.py    does the log agree with the geometry, and the control
    data/live/          forecast.json, now.json, measured.json, series.json,
                        series_all.json, windtide.json, origins.json and
                        buoys.json, what the app surface reads (derived,
                        gitignored)
    data/series/        46232/YYYY-MM.csv: the observed chain for every
                        archived hour, and 46232_origins.json, the Origins
                        chart's marks, both rebuilt whole with today's chain
                        by series-archive.yml, its only writer. DERIVED but
                        tracked: rebuilding a year costs minutes a
                        collection cannot spend (see Infrastructure)
    data/forecast_log/  46232/YYYY-MM.csv: what every forecast build said,
                        3-hourly, one row per site (forecast.forecastlog).
                        PERMANENT and never published: the one input to the
                        bias report nothing can rebuild. 46232_shown/ is each
                        build's hours IN FULL for the 48 h after it was
                        published (JSONL, ~85 KB a build): what a past card is
                        drawn from; `seed-shown.yml` fills it for the first
                        builds from the delivery repo's published history,
                        headline-checked. 46232_recomputed/ is past cycles
                        rebuilt later (model-bias.yml), kept apart
    data/spectra/       NDBC directional spectra, five components per station
    data/wind/          KNZY       data/tide/  NOAA 9410170, three files:
                        _observed (measured), _predicted (hourly harmonic),
                        _turns (the harmonic model's own highs and lows)
    data/shoreline/     NOAA ENC coastline, one file per chart band AND
                        region. `_coronado` (harbour 904 pts, approach 689,
                        coastal 312) and `_baja` (harbour 2428, approach 3691,
                        coastal 1431 - the islands and the Mexican coast to
                        32.383, where NOAA's charts stop) and `_point_loma`
                        (harbour 2815, approach 1612, coastal 879 — the
                        harbour band is holed at the tip), and
                        `_channel_islands_south`/`_north` (the eight Channel
                        Islands; context, read by no chain). A CHART product,
                        generalised, not survey-grade MHW. Every file is
                        clipped by its own query envelope on all four edges,
                        which is why the region is in the filename.
    data/bathymetry/    CoNED seabed grids (.npz, decimetres NAVD88) + a JSON
                        sidecar each. Does NOT cover the Coronado Islands or
                        Baja (south of 32.49 N); those stay charted blockers.
    data/nearshore/     per-break transfer tables from forecast.raytrace:
                        <break>.csv (one row per period x 0.5° heading at
                        5 m: hard-edged gain, diffracting gain and the heading
                        each reads, and the friction factor of each),
                        <break>.json (start point, datum, grids),
                        <break>_fetch.csv (open water upwind, per 1° of wind),
                        <break>_profile.csv (depth below MSL every 2 m from the
                        start point to dry sand, along the normal)
    data/beach_log/     the verification series — human observation  [EMPTY]
    data/historical/    3 years hourly, 15 stations — irreplaceable
    data/ensemble_forecasts/ GEFS-Wave's bulletin at 46232, 00Z 2023–2025 (means
                        only) and every cycle from 2026 (with spread), leads
                        to +240 h; exceedance shares by COLUMN, not label
    data/wave_forecasts/ 1,096 archived GFS-Wave 00Z cycles/station, 2023–2025,
                        with partitions: 46047 (unshadowed, the reference)
                        and five shadowed buoys, 46086, 46258, 46232, 46224,
                        46222

`forecast/stats.py` was trimmed to the four helpers this project uses
(`load_column`, `angular_difference`, `least_squares`, `rmse`) when the
repository went public. The predecessor's scoring work — `assess`,
`contested_skill`, the feature-group fits and the CLI — is gone, along with
`collector/forecast.py` and its probes, which archived an Open-Meteo water
temperature forecast as a candidate scoring baseline. `LEAGUE_TZ` is now
`LOCAL_TZ`; it was always just America/Los_Angeles.

## Design rules that are easy to erode

- **The three beaches are not one beach — and Coronado is not one beach.**
  Breakers keeps 23° of west window and Gator 62°, and Gator alone holds west
  swell. But the same mechanism runs along Coronado's own sand: the west edge
  IS the bearing to the Point Loma tip, which sweeps as you walk, giving
  **41.3° / 47.6° / 54.9°** at the north, center and south breaks across 2.8 km.
  That 13.6° spread is a third of the entire Breakers-to-Gator range. Any
  surface showing one number for "Coronado" is averaging across it. (Those were
  42.8 / 49.1 / 56.3 until 2026-09-20, when charting the Coronado Islands moved
  the LOW edge 1.2–1.9°; 41.6 / 47.7 / 54.7 until 2026-09-22, when charting
  the Point Loma tip moved the HIGH edge −0.53 / +0.01 / +0.17; and 41.1 /
  47.7 / 54.9 for the rest of that day, until the break chords were charted
  and north's position moved 30 m.)
- **The Point Loma tip carries every west edge, and it is not one point.** 100 m
  of error there moves an edge ~1°; it is the highest-leverage geometry in the
  repository. Measured 2026-09-18: 250 m of tip error moves a Coronado edge
  2.2–2.8°, against 0.46° for the same error on the Coronado Islands.
  **Charted 2026-09-22 from NOAA's ENC** (BRIEFING §26): the tip is a rounded
  headland, each break's tangent lands on a different charted vertex up to
  330 m apart, and any single point is wrong by up to 0.67° somewhere. So the
  blocker carries an `outline` (the convex hull of the charted tip — only a
  hull vertex can be a tangent) and `Blocker.a_seen_from` takes the edge per
  break. **Never collapse it back to one point.** The approach band is used,
  not the finer harbour band: the harbour coastline has a 336 m hole across
  the tip, and a tangent on a line end is missing data, not coast.
- **The Coronado Islands are not a switch, and they are not one island.**
  Charted 2026-09-20 from NOAA's ENC: **two** islands with **6.1° of open
  channel** between them, stable from a 0.3 km to a 3 km clustering distance
  on two chart bands. The estimate they replaced was one blocker spanning the
  whole group, which claimed that channel was land and put the group's Fresnel
  number at ~7 where the islands' own are **1.6 and 0.2** — silencing the
  diffraction flag that §10 exists to raise. They remove **under 5%** of a
  30°-spread swell's energy where Point Loma removes ~50%. The locals who say
  the islands barely shadow are right, and the finer the geometry gets the
  more right they are. **Never restore a binary open/shut test for them**, and
  **never merge them back into one blocker** — both are the same error, one
  scale apart.
- **Publish the swell-side window, never the raw open arcs.** A window edge
  formed by the seaward half-plane clip means the arc ran out of *modelled*
  land, not that it ran into ocean. **As of 2026-09-20 no edge of any spot in
  the file is formed that way**, so `swell_window` and `open_window` now
  return the same thing — because the coast that was missing got charted, not
  because the rule relaxed. Keep the guard: it is what stops the next break
  added to the file publishing open water across a coastline nobody has
  digitised. BRIEFING §12, §24.
- **The south window is real and it is where the south swell is.** The Baja
  coast is a **tangent**, not a chord: every charted vertex from the border to
  Rosarito sits inside 147–168° from these breaks, so one vertex at 23 km
  carries the whole southern edge. 100 m of error there costs 0.25°, against
  ~1° for the same error on the Point Loma tip. Measured on the three-year
  46232 archive, **16.7% of rows and 11.6% of energy** arrive from 100–190°,
  and **9.6% of all archive hours** carry Hs ≥ 1.0 m at DPD ≥ 12 s from that
  sector. UNTESTED: that no coast south of 32.3834 — where NOAA's charts
  stop — bears higher than the tangent. Landmark estimates say 152–159°, all
  below it; that is not a measurement.
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
  hoisted out of the breaks — their own cards, beside the Swell card whose
  tabs are the three breaks (ranked by window energy, buoy always last) —
  because KNZY and 9410170 feed all three and repeating them three times is
  noise. **The offshore/onshore reading is not hoisted**, because it is derived from the shore normal and Coronado's three
  normals span 27° (194.1 / 213.9 / 220.9, charted 2026-09-22; they were
  192.8 / 214.2 / 221.5 on the traced chords) — a 290° wind reads cross-shore
  at north and centre and onshore at south, on the same reading. Hoist the
  measurement; keep the interpretation where it is made. Since 2026-09-26
  (owner's layout) the verdict sits on the Wind card as one line per break —
  "offshore at this break" — shown only for the break whose swell tab is open
  and hidden on the buoy's, so it is still per break. **On the Forecast tab
  the verdict comes from the LOCAL forecast wind, never the model's**:
  GFS-Wave's wind is at the buoy, 29 km offshore — kept on the card for the
  wind sea it makes — and a verdict against the shore normal needs the wind
  on the sand. Since 2026-09-30 the Wind card carries "Local" under
  it: the NWS forecast grid at Coronado's center break
  (`collector.localwind`, fetched by `forecast.live` on Actions;
  api.weather.gov and aviationweather.gov are both denied at CONNECT from a
  session), hourly, 7 days, per break on each `Hour` as `local_wind_*`.
  Chosen over KNZY's TAF: a TAF runs 24–30 h in coded change groups written
  for the runway.
- **46232 is the sea after the Channel Islands, and that sea is not
  uniform.** On north-west swell its westerly lobe pins near 270° whatever
  46047 reads, 46258's at 286° and 46086's at 279° — each at its own bearing,
  none at a charted island edge (BRIEFING §38). That lobe carries ~24% of
  Center's and ~36% of South's 5 m energy on those hours, and the breaks'
  rays leave deep water 25 km from both 46232 and 46258. Never "fix" 46232's
  direction toward 46047's: the beach needs the sea where it is, not the
  open ocean's, and §3a still forbids a substitute anchor.
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
- **Imperial leads, metric in parentheses, everywhere a number is shown.**
  "2.3 ft (0.71 m)", "9 mph (8 kt)". **Nothing upstream of a display converts**:
  the JSON, the transform and the collectors stay in metres and knots, because
  that is what NDBC and WAVEWATCH III publish and putting a unit change between
  the source and every cross-check is how a 3.28 ends up somewhere it should
  not be. `forecast/units.py` and the three constants at the top of
  `app/forecast.html` (feet, mph, and since 2026-10-02 miles, for Origin) are
  the only places the conversion happens; a test pins that each factor
  appears exactly once.
- **The tide's direction is read off the next turn, never differenced from the
  water level.** Measured 2026-09-19 on the 6-minute measured series:
  differencing the two newest samples reads the direction **backwards on 19.5%
  of readings** — at a neap; re-measured 2026-09-28 over half a spring-neap
  cycle it is **17–25% on neap days and 2.5–6% at springs, 9.9% overall**, so
  the error follows the tidal range and returns every two weeks
  (`tests/test_tideturns.py` pins the neap figure) — and a least-squares slope over a trailing 45 minutes is still
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
  turn as two claims. Since 2026-09-28 (owner's decision) its HEIGHT carries the
  gauge's measured departure from the prediction over the last 3 days, as the
  Forecast tab's turns do: bare, it contradicted the measured level beside it
  on 15.9% of 245 hourly readings ("rising to" a height already passed), and
  4.5% with it. The measured level itself never takes the departure — the
  departure IS measured minus predicted. The Now/Forecast split is about the reader always knowing
  which chain they are looking at, not about a tab being chemically pure; an
  unlabelled turn would have broken it, a labelled one demonstrates it.
- **The shore normal is the highest-leverage input to the wind reading.**
  Measured 2026-09-20 (BRIEFING §20): the verdict
  boundaries sit at fixed angles from the normal, which puts six of the nine
  boundaries for Coronado's breaks inside 265–330°, and **62.6% of a three-year
  wind record sits in 270–330°**. So error lands where the data is: 1° of
  normal error changes the verdict on **4.2%** of readings and 5° on 21% —
  roughly twice what a uniform wind rose would cost. `coronado_north`'s
  imagery-splice caveat claimed ~19° (~70% of verdicts); §23 measured 1.7° and
  charting the chord (BRIEFING §27) moved it 1.3°, and the flag is retired.
  All three normals are now read off the ENC harbour band, and they agree with
  §23's 400 m principal-axis fits — a different method on the same chart —
  within 0.3°.
- **Past a few hundred metres on a curving coast, a circular window is not a
  chord.** Measured 2026-09-20 (BRIEFING §23): two independent chart bands of
  the same coast agree within **0.3° up to 800 m**, and disagree by **18.6° at
  1500 m** at the south break, where the coast bends toward Imperial Beach. The
  principal axis of a circular window there is decided by which vertices each
  chart happened to place. Read the wide columns of `shorenormal`'s sweep as a
  curvature alarm, never as a normal. `REPORT_SCALE_M` at 400 m sits inside the
  agreeing range.
- **A normal is a property of a chord, not of a point.** The same beach gives
  104.1° over north's 530 m chord, 123.9° over centre's 285 m, 130.9° over
  south's 461 m and 120.8° over the whole 2.75 km — 26.8° of spread, all of it
  real (charted chords; the traced ones gave 102.8 / 124.2 / 131.5 / 121.3). Any verification that does not state its chord length has verified
  nothing. `forecast/shorenormal.py` therefore reports a SWEEP over scale, and
  `residual_m` says whether the break sits on a straight stretch or a curve.
- **There are two shore normals and they are not the same claim.** The
  waterline normal is what the wind reading needs; the depth-contour normal at
  breaking depth is what refraction will need. `Spot.normal` is currently one
  number doing both jobs, and checking it against a shoreline verifies only the
  first.
- **The seabed transform is physics, never "calibration".** Calibration is the
  level reserved for fitting to the observation log (build order 5), and
  `docs.html` names it as its own confidence level. Refraction, shoaling and
  diffraction are modelled from surveyed inputs and fitted to nothing; calling
  them calibration would claim a level the project has not reached.
  `tests/test_app_surface.py` keeps the word out of the card's paragraph.
- **The transfer tables stop at 5 m of water; the surf zone takes it from
  there.** The 10 m contour MOP uses lay 2.2 km off the north break, outside
  Point Loma's shadow, and described a different place (BRIEFING §29). Moving
  `raytrace.H_REF` moves where the tables hand over to `surfzone`; rebuild
  the tables AND the profiles and re-read §29 and §32 before doing it.
- **The breaking height is a significant height, not a face height**, and the
  profile is a 2016 survey. Measured over the archive (BRIEFING §32): breaking
  lifts the 5 m figure ~20–23% into ~1.7–1.9 m of water, and the whole tide
  range moves the break point 34–53 m while changing the height under 2% —
  on a barless profile the tide decides WHERE it breaks, not how big. A
  season's sandbar would change that, and nothing here knows where it is.
- **9410170 is inside the bay; the breaks are not.** The open coast swings
  0.944× as far and leads by ~3 min (measured against La Jolla, and CO-OPS's
  Imperial Beach and Point Loma offsets agree). **The Tide card shows the open
  coast** on both tabs (owner's decision, 2026-09-26): heights ×0.944 on MLLW,
  CO-OPS's own subordinate-station convention, and predicted times 3 min
  earlier; the source line names the gauge it was carried from, the measured
  reading keeps the gauge's stamp for its countdown, and `gauge_height_m`
  keeps the raw value. Breaking uses the MSL form (`tidesite.coast_level`)
  from the gauge's raw reading — never from the card's, or the transfer runs
  twice. And the harmonic prediction is on the 1983–2001
  epoch: the measured level ran ~0.23 m above it in Sept 2026, so the
  forecast carries the last 3 days' measured departure forward — and computes
  no breaking at all without one.
- **The line under a past forecast hour says when it was observed, never
  "what happened".** Red, in a 1 px outline at the card's radius, and
  labelled "Observed at 8:00 AM" (the tide's "Measured at 8:00 AM") — owner's
  wording and style, 2026-09-27. Every measured element on the Forecast tab is
  `--measured`: pure red, #E00000 light / #FF4545 dark (owner's call,
  2026-10-02, replacing sea green; #FF0000 itself fails 4.5:1 for text on
  both cards). Where it comes from is said on `docs.html`:
  46232's spectrum at that hour, through identical windows, seabed and surf
  zone, so its difference from the forecast is the MODEL's error at the buoy,
  carried in, with any physics error cancelled out. It checks nothing at the
  beach. No difference or percentage goes on screen: that would be a claim
  about the forecast without a verification series named beside it. A
  missing spectrum is a gap, never the hour beside it, and the newest hour
  reads "not in yet" until a later spectrum has passed it
  (`tests/test_app_surface.py` keeps "actual" off the page).
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
