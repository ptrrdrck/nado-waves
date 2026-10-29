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
   observed time, countdown and words under its rose (since 2026-10-12 the
   one sentence below) (`forecast/buoys.py` → `buoys.json`, its own step in the
   collection). **Each buoy's provenance follows its own measurements**
   (owner's call, same day): 46232's reading, then the card's provenance
   (46232's), then each context buoy's block with its provenance in the
   same style.
   Each buoy's feed is a pill at the START of its countdown line (owner's
   requests, 2026-10-09, moved there 2026-10-11 from beside the combined
   height, whose headline is now the height alone, as a break's is): "CDIP
   191 •" for 46232 (owner's call, 2026-10-12, shortened from "CDIP 191 via
   NDBC") — CDIP runs it, NDBC serves its spectra — and "NDBC 46047 •",
   replacing the "(NDBC <id>)" the name line carried. **The whole
   provenance is ONE line of joined pills** (owner's requests, 2026-10-11
   and -12): "CDIP 191 • | <age> | <countdown>" (`feedPills`). A first line
   above it, "Point Loma South, CA | <when>" (the place alone, the time with
   no "Observed" or "Measured"; `placeWhen`), is built but switched off by
   `SHOW_PLACE_WHEN` (owner's call, same day: kept so it can come back).
   Each pill after the first grows out of the one before, corners 4 px; the
   LIVE Wind and Tide cards' too — "METAR KNZY • | <age> | <countdown>" and
   "NOAA 9410170 • | …" (their hidden first lines "NAS North Island" and
   "Coronado, CA", `tidesite.SITE_PLACE`, now.json `tide_place`), the dot
   on each card's own countdown; a line too wide for the card wraps a
   pill to start the next row as a pill of its own, in the joined one's
   footprint (`fitPills`), never past the card. 46047's "Open ocean witness" line is
   no longer provenance: words under its rose, above its pills with space
   between. **Each buoy's headline folds like a break's** (owner's request,
   same day; `buoyReading`): its caret and whole line fold out everything
   between it and the provenance -- trains, rose, those words -- closed
   until opened, each buoy its own state, kept across a refresh; selecting
   the Buoys tab opens 46232's (owner's request, 2026-10-13). 46232's
   number is the registry's (`stations.json` `cdip`, `now.json`
   `station_cdip`, never typed on the page; "NDBC 46232" without it). Ink at
   the provenance's 12 px on the picked row's background; 46232's sits under
   every swell tab, the break tabs too, because every break's numbers are
   that one spectrum. Each pill after the first grows out of the one before
   (owner's design, 2026-10-11; `feedPills`): it starts under that pill's
   right end, its left edge cut 2 px outside it (a CSS mask), and the
   countdown's words without the full stop the card's other
   countdowns keep (`dueSpan`'s `bare`). The dot runs on that
   buoy's own countdown instants (`dueInstants`), so it turns exactly when
   "Update due." and "Overdue …" do: green, green fading in and out
   while due (held at half strength under reduced motion), red overdue --
   dark mode's green and red on both themes (`--dot-ok`, `--dot-over`), and
   every card's "Overdue …" in that same red (owner's call, same day).
   LIVE only: the Forecast chain's buoy is a model.
   **The Forecast tab's provenance is the same joined pills, with no dot and
   no countdown** (owner's request, 2026-10-15): swell and the model's wind
   at the buoy "CDIP 191 | GFS-Wave | Oct 15 at 5:00 AM, 9 h ahead" (the run
   and its lead; one name whatever `wave_source` says), Local "NWS |
   Grid SGX 56,13 | Updated …" (a past hour's from its own build's
   `local_wind_updated_utc` in `46232_shown/`, none where that build kept
   none), Tide "NOAA 9410170 | Harmonic | Departure …" or "No departure"
   ("Gauge departure" measured 358 px against the card's 330 at a 390 px
   phone; "Departure" 321). The hour is the seek bar's, no longer a
   "Forecast for" line. **KNZY never stands in on the Forecast tab** (owner's
   call, same day): it is not a forecast. A missing model wind reads "not
   collected yet" (under a past hour "no model wind for this hour", owner's
   wording), a missing NWS hour "no local forecast" and why.
   **It feeds nothing**: its own module and file, never a key in now.json, so
   the context-station guard still keeps "46047" out of now.py and the chain,
   and `tests/test_buoys.py` keeps `through`/`carry`/the surf zone out of it.
   Its countdown is measured, not borrowed: stamped :20 and :50, 25 min
   typical and 85 worst, bracketed against the collection log on 148 stamps.
   Its opposed lobes (≥ 150° apart, 168 over the archive; 46232 has none) are
   real — 46232 saw the southern one on 163 of 163 — and since §40 each is
   its own train.
   **46086, San Clemente Basin, between 46232 and 46047** (owner's request,
   2026-10-12, first under 46047; the owner swapped the two the same day),
   built and guarded the same way (`buoys.STATIONS`), "NDBC 46086 •" its
   feed pill. **It is not open ocean**: `forecast.siting` puts it inside
   South's window alone (§3a: "the nearest thing to a stand-in, and
   partial"), so the standing-on line names each buoy's windows
   (`buoys.WITNESS`), held to siting's verdict by a test.
   **Under every buoy's rose, 46232's too, ONE sentence** (owner's wording,
   2026-10-12; `buoys.ABOUT`, in buoys.json as `about`, joined by the
   page's `buoyAbout`): the station linked to its public page (CDIP's for
   a buoy with a registry `cdip` number, NDBC's otherwise), its distance
   offshore and bearing from Center break — `forecast.siting`'s, never
   typed, none for a buoy siting cannot place — then what is read from it
   and its role. It replaced the "Open ocean witness" / "Inside South's
   window" notes; its mention of a window is held to siting's verdict too.
   LIVE only, as the rose is. At 15 px, the size of "combined" beside the
   height (owner's request, 2026-10-14), and a buoy with no rose says "No
   spectrum from … in the last six hours." at that size and grey, evenly
   spaced between its trains and its sentence. Its countdown is its
   own: :20 and :50, 25 typical and **115** worst on 188 stamps since its
   sensor returned 2026-10-08. The three past H+85 were NDBC's, shared with
   46047 (10-10 07:50 reached H+125 there, past 46047's shipped 85; not
   changed, the owner's call). On the Height chart 46086 is the second
   lighter line, dashed, as a break tab's second other break is — whatever
   the tab's order: the page reads `heights` by key, and JavaScript orders
   numeric keys ascending.
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
   That ring is the drawing's edge, N / E / S / W just inside it on a
   card-coloured halo, the circle 260 px across (owner's choice, 2026-10-08:
   21% wider than with the points outside, and the block 20 px shorter).
   The scale is one line under the rose, never a figure on the plot, and
   it carries the frame too: "Rings every 1 ft (0.30 m) · 11:00 AM · 4.6 ft
   (1.39 m) combined" (owner's request, 2026-10-08; no values line above
   the rose, and no "to 4 ft" ending), breaking only at a "·"; play /
   pause is a symbol button left of the timeline, and the Height / Period
   switch is "ft | s" at its right (owner's request, 2026-10-08: its own row
   above the rose cost 28 px), the Period legend one row ("<8 … 17+ s"), its row kept, unseen, on
   Height so the switch never moves the page, and play / pause the ft / s
   buttons' 22 px height (owner's requests, same day). **A tapped train row lights
   its PERIOD RANGE on the rose** (owner's request, 2026-10-08): the bins
   that train holds in the newest spectrum (`Train.bins`, ignored by
   equality) — and, for a train divided from a band of two directions
   (§40), the headings it holds (`Train.arc`), since its twin shares the
   range — and each frame's share within them, in ink over the rose
   dimmed; the readout names the range, never "the train", because nothing
   follows a train between spectra (owner's question, same day: Origin's
   ridges are the one tracker, and a later step could follow one). Only
   under the reading split from that same spectrum (`trains_from_utc`); a
   new spectrum clears it. A break tab's train row lights the same way
   when its train is picked, from the list or by its arrow on the drawing
   (owner's request, 2026-10-09). **A picked train also shows its heading in
   5 m of water** (owner's request, 2026-10-22): an arrowhead alone at the
   break, 1.25× its own offshore head (`NEAR_HEAD`; owner's call, same day:
   the dashed leg looked bad), and a second caption line, "from SW 222° in
   5 m of water" — its own rays' 5 m headings, energy-weighted
   (`nearshore._arrive`, `near_from_deg` / `near_lobes`), on the drawing
   only, never in the row. docs.html's `swell-bend` table is the same
   calculation for one narrow swell per heading (`forecast/bending.py
   --write`, pinned to `carry` by a test). **By 5 m the offshore direction
   is mostly erased** (BRIEFING §45): everything the windows let in arrives
   within ~16° of the normal, turned crossing a wide 8–15 m shelf 3–8 km
   out, which scrambles the rays (37–59% of neighbours swap order; real
   shelf features, not grid noise). The seabed within 400 m of each start
   faces its chord normal within 1–4°, so the surf zone's breaking angle
   against the chord normal is consistent. Read a 5 m heading as a few
   degrees either way: where rays cross, ray theory is at its limit. The rose is spaced as a break tab's
   drawing is (owner's request, same day): 31 px of card above its first
   ink, 28 px from its timeline to the provenance on Height, in painted
   pixels at 360 px — the drawing scales with the width and the rose does
   not, so 320 and 390 differ by up to 3 px — with the Period legend inside
   that lower space, closer to the provenance, so the switch never moves the
   page. And the drawing is greys and ink only, as the rose is (same day):
   no site blue on the chord, the break, the swell or a picked window.
   Every rose opens paused on the newest spectrum, the one its headline
   reads, whenever it comes into view (owner's request, 2026-10-11: load,
   LIVE, the Buoys tab, a headline unfolding; `roseShown`). LIVE
   only; not carried to any break. The
   Forecast tab's Buoys tab holds 46232 alone. **46047 is on the LIVE Buoys
   tab's Height chart** (owner's request, 2026-10-09), a lighter line under
   46232's at its OWN :20 / :50 stamps — never moved onto 46232's hour, a
   stamp > 45 min from the last a gap, the readout naming its own time —
   from `buoys.json`'s `heights` (the week) and `buoys_all.json` (every
   archived stamp, fetched with series_all.json). Each line, in its key
   and readout, is named as its pill names it — "CDIP 191", "NDBC 46047",
   "NDBC 46086" (owner's request, 2026-10-14), never "Buoy 46232"; and so
   is every buoy the page or docs.html names in words (`buoyFeed`, the CDIP
   number from now.json or forecast.json; the geometry drawing's from
   `geomviz`'s registry lookup). Its height is
   `transform.combined_hs`: `at_buoy`'s m0 to rounding (a test pins it)
   without the trains, MEM's bins summing to one by its pole test alone
   (`spreadmethod.realisable`) — 0.7 s for two months, where `at_buoy` took
   ~90.
   **The Forecast tab reaches 48 h back** (owner's decision, 2026-09-26). For a
   past hour it shows what the page showed then: the newest run published
   before that hour, from `forecast.json`'s `past`, read back from the
   permanent log — **the full card, drawing and calculation table included**,
   from that build's own hour as it was published (`46232_shown/`). A past
   hour whose build kept only a headline says "The calculation for this hour
   was not kept" rather than borrowing another build's detail. Under it, in
   blue, is the measured chain rebuilt for that hour (`measured.json`). It opens on the first hour not yet passed, never
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
   in beside the passed hours in blue), *Swell trains*
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
   second measurement, and the newest report's slot added as soon as the
   report lands (2026-10-16: the :52 METAR's hour had no slot until the
   clock reached it, and the chart sat a report behind the card) — and the
   gauge's sample AT the hour on the open coast;
   plus the tide's next 24 h of harmonic prediction with the departure,
   dashed, the tab's one modelled line beside its one modelled number. On
   Forecast, `forecast.json`'s `hourly` (the NWS local wind, and the card's
   tide) to the run's end, the measured hours in blue, and GFS-Wave's own
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
   card says Calm rather than "N 0°"; a METAR's `VRB` (a speed, no
   direction) reads "Variable at …", never "not collected" — both
   capitalised in the headline (owner's request, 2026-10-15). Neither has a
   side, so the break's line says why instead of repeating the headline:
   "**no wind**, so no side set" and "**no direction**, so no side set"
   (owner's wording, same day). The Tide view is shaded by night on both tabs
   (`forecast/daylight.py`: NOAA's solar equations at the center break from
   spots.json, within a minute of `astral`; `nights` in both payloads).
   **The Tide card's phase fold** (owner's request, 2026-10-11;
   `forecast/tidephase.py`, BRIEFING §41), on the Forecast tab only since
   2026-10-20 (owner's request: off LIVE "for now", `SHOW_LIVE_PHASE`
   brings it back), right above its
   Charts line under a rule of its own, its caret like Origin's: the line is
   a fixed title, "Phase" (owner's edit, same day, replacing the phase
   itself), tagged `predicted` on LIVE as the turn line is; open, three
   PARAGRAPHS, never bullets (owner's call), each a heading over its
   body — "Today" (the phase: Spring tides / Neap tides / Building toward
   springs / Easing toward neaps, the Moon, the day's pair), "Around 17 Oct"
   (the next spring or neap, what coincides, and "The upcoming turns show
   it: …"), "Late October" (owner's wording kept) — with no title above them.
   NOAA's constants are not named in the paragraphs (owner's edit, same
   day: "by NOAA's harmonic constants" and "by the same constants" came
   out). **Set as Origin's entries are, and no provenance** (owner's
   request, 2026-10-14): each heading at the value size over a grey body at
   15 px, a centred 4 px dot in that body's grey between paragraphs (Origin's
   entries alike; owner's request, same day); the constants and their 2017–2021
   analysis, the computed Moon and CO-OPS's turns are named on docs.html
   instead, the analysis held to the archived constants by a test. Spring and neap come from NOAA's harmonic constants for
   9410170 (`collector/harcon.py`, fetched on Actions, never typed — their
   `phase_local` is NOT comparable across speeds: read naively it puts
   springs 11 h before syzygy, `phase_GMT` 3 h), the Moon from
   `forecast/moon.py` (Meeus ch. 47, pure Python; mean elements had the
   October new moon a day late and perigee two days late). **Every threshold
   is measured** (owner's request) over 19 years of the station's tide
   rebuilt from the constants (`forecast/tidephasereport.py`, ~10 s, re-run
   by a test): a slot is said only where it is right ≥ 85% of the times it
   fires. **"The day's two tides", never "the two highs"**: the declination
   shows in the lows here (r 0.82 against 0.66). The constants reproduce
   CO-OPS's hourly prediction to 1.1 cm, and are read for the CYCLES only —
   the card's turns stay CO-OPS's hilo, with no fallback to a computed one.
   Wording generated from the page's code into `docs/tide_phase_wording.md`
   (`forecast/tidephasewording.py`). LIVE: the reader's day at Coronado;
   Forecast: the picked hour's day, none under a past hour.
   **The Sun card** (owner's request, 2026-10-16; `forecast/sunset.py`,
   BRIEFING §42), after Tide (owner's choice of a card over a Tide fold),
   on the Forecast tab only since 2026-10-20 (owner's request: off LIVE
   "for now", `SHOW_LIVE_SUN` brings it back): the sunset the open break SEES. For most of the year the sun
   goes behind Point Loma's ridge (4.5–8 km out, 90–130 m, ~1° up) 5–8 min
   before the sea-horizon time every table gives; through the winter it sets
   in the sea, LEFT of the point, for a season that differs by break as the
   window does — South ~15 Oct–25 Feb, Center ~9 Nov–1 Feb, North NEVER
   (closest ~19–23 Dec, still 1 min early). Headline the break's sunset,
   then "behind Point Loma, 7 min early" (the minutes the two shown clocks'
   own difference) or "in the sea, left of the point, until …", the season
   line (one line in all while it sets in the sea), and "Sunrise …"; each
   tab's lines follow the swell tab (`data-sun-for`), the Buoys tab reading
   the sea horizon. Tagged `computed` on LIVE, where each time is the NEXT
   one, per tab, saying "tomorrow" when it is (owner's question, 2026-10-16:
   "Sunrise … · sea horizon 6:14 PM" after sunset read as either day's, and
   the sea-horizon clock came off). Refraction is Bennett's standard: KNZY's
   temperature and pressure move it 3–12 s over 28 sunsets, invisible at a
   minute; the air–sea difference (−3.5 to +8.3 °C, KNZY against 46232's
   SST) is the real swing, and nothing here measures what it does. The skyline
   is CoNED's own LAND (it is topobathy) traced from each break by
   `forecast/skyline.py` (precompute, numpy) into
   `data/nearshore/<break>_skyline.csv`; its first land agrees with the
   charted Point Loma tangent within 0.1° (a test pins 0.3°). Bare earth:
   trees and buildings can only make the real sunset EARLIER. Sunrise is
   the sea-level time; nothing east of the breaks is in the grids.
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
   once a ridge passes the reading gate (≥ 12 h, R² ≥ 0.8), "Arriving for
   N h so far." while it runs; otherwise the last readable arrival at that
   break in the last 21 days — whichever ended later of Origin's last reading
   there and the last storm named there (origins.json's named moments, as of
   now.json's spectrum, a reading credited to a storm being that storm's;
   owner's report 2026-10-12, when South read a ridge ended 2 Oct while
   Tropical Storm Rachel was named there to 11 Oct). That last arrival opens
   with "No readable swell arriving here now. The last one was:" (owner's
   rewrite, 2026-10-14; the tab's name dropped) instead of a grey tag, its
   lines at the tag's 15 px (owner's request, 2026-10-12); a storm's has no
   counts, "Arrived" being the first moment the storm was named there with
   the fix that sent the train shown, never its first train there. A named
   storm's head carries the tropical cyclone symbol, eye open for a tropical
   storm and filled for a hurricane, in ink, and its NAME alone links to
   NHC's own page for it (`archive/{year}/{NAME}_graphics.php`, track and
   cone map; owner's calls 2026-10-12 and -14), never the b-deck the card
   reads; the Origins chart's readout names it with neither link nor
   symbol (owner's call, 2026-10-14). now.json names every
   gate buoy so a past storm's line can name its own. **Every origin is a
   head and one paragraph** (owner's design 2026-10-04, one paragraph since
   the owner's rewrite of 2026-10-14), **each a fixed run of slots** (owner's
   formula, 2026-10-10, `docs/origin_wording.md`): a slot with no value drops
   with its joining words, nothing is reworded per case. What it is, the head
   alone ("Hurricane Polo", a sea, or "Unplaced storm" — 46047 holds the
   train from several directions, or does not have it); then, run on, "The
   16.0 s train, sent about Sep 28 from about 700 mi (1,100 km) away" ("about"
   on a reading's fitted day, bare on NHC's; the last arrival's train is its
   peak hour's, `peak_period_s`); where its direction comes from, a sentence
   of its own: a hurricane's "NHC had it at 161° SSE, with winds of
   121 mph (105 kt) and 950 mb pressure at that time.", NHC's fix that SENT the train, so
   a storm that has weakened since still reads as it was then; a reading's
   naming the buoy (`heldAt`): "Tanner Banks (NDBC 46047) holds this train
   from 212° SSW.", "… from 190° S and 276° W, so no place is given." for a
   split, "… does not have this train, so no place is given."; and how long:
   a storm's "Arriving for N h so far." — the longest any gate buoy has had
   its swell by its track, none when no buoy has hours; **the match counts
   are NOT on the card** (owner's call, 2026-10-14: they still decide
   whether a storm is named, and docs.html explains them; never a
   percentage or a strong/partial/weak word on the card either); a
   reading's "Arriving for N h so far." too (owner's call, same day), its
   hours as read off the swell; past, every kind ends "Arrived …, no longer
   arriving." with no hours. **No provenance follows the entries** (owner's call,
   2026-10-14): storm matching is explained on docs.html. Entries are set
   apart by a centred 4 px dot, never a rule: a full-width rule opens a
   section on this card. Each buoy is named as NDBC names it,
   "Tanner Banks (NDBC 46047)" — the state dropped, and a buoy CDIP runs by
   CDIP's number, "Point Loma South (CDIP 191)", here and on docs.html's
   provenance (owner's request, 2026-10-13; the Forecast tab's pill reads
   "CDIP 191" since 2026-10-15) — from
   `origin.station_names` and `station_cdips` in now.json (fetched metadata
   and the registry, never typed). **No upstream sighting is shown, ever**: measured, the predecessor's
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
   sources on one bearing apart) — on 3 Oct; to 10 Oct, 17 of 74, partial 15,
   strong 7, the seven not yet examined. Backtest: Marie strong at both buoys, Polo
   partial (78% at best), Odalys partial (82%). **A hurricane that weakens
   stays named** (owner's request, 2026-10-11, after Rachel dropped off the
   card while her swell still arrived; BRIEFING §37f): a storm's sources
   (`stormtrack.sources`) are its ≥ 64 kt fixes and every fix AFTER its
   first one that NHC classes TS or HU at ≥ 34 kt — never before it, never
   a depression, remnant low or extratropical storm. A train a tropical storm
   fix sent reads "Tropical Storm X" (`strength`, as its winds are the
   fix's). Measured on one archive with and without: the control does not
   loosen (misplaced moments named 3.3% → 2.9%), but real matches soften —
   Marie at 46047 falls from strong to partial (80%) and fails the strict
   gate, because her weakened days' swell does not stand out there. On a break only when one of its
   card trains is the storm's, and a train is only when ALL hold (2026-10-11,
   BRIEFING §37g–i): on the band's schedule; within 45° of the storm's
   bearing at the break, REQUIRED (refraction turns a swell ≤ ~31° toward
   normals of 194–221°, so a train further round is another swell — the old
   "nearest of the rest" fallback named Center's 11.8 s from 260° as
   Rachel's); a gate buoy it is matched at has that train's periods from the
   bearing to the sending fix at ≥ `DIR_RATIO` × either side turned 45°
   (`_gate_has`, the match's own direction count per train; its newest
   spectrum ≤ the card's, ≤ `GATE_STALE_H` old — before it, 79 of 149 named
   trains failed it at 46047); and Origin does not read it from > 3× or < ⅓
   of the sending fix's distance (`SAME_SOURCE_RATIO`, wide by §37b's 0.78×
   and 1.8–2.4×; `now.origin_readings` live, `originhistory.readings_at` in
   the archive, each ridge paired with every site's train at its frequency).
   Of those, the one its track has arriving NEAREST NOW, never card order (the
   biggest-first pick gave Rachel 16.7 s at two breaks and 11.8 s at the
   third). Other passing rows that are ONE band at that gate buoy (no dip
   below `transform.PROMINENCE` in the storm's sector between them; `_one_band`)
   are one swell the break's splitter cut, listed as `also_periods_s` — "The
   10.5 and 11.1 s trains" — and a twin of the same period never twice. TWO
   SEPARATE trains from one storm are never claimed (§37h: unconfirmed in the
   literature found and in the archive). Placed and sized from NHC's fix that sent
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
   its dispersion distance. Its readout names each as the fold does — a
   hurricane by name with no match word or figure, a sea, or "Unplaced storm,
   about … , no bearing" (owner's call, 2026-10-10). Log miles, 500–10,000;
   a bearing strip under it,
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
   **The Briefing** (owner's request, 2026-10-16; reshaped 2026-10-17 and
   again 2026-10-22; `forecast/briefing.py`): a short read in a fold on the
   BACKDROP above the LIVE cards, not a card, closed until opened (open, at
   most half the screen, scrolling inside itself, its scroll carrying on to
   the page at either end — a swipe down at its top reaches the page so
   pull-to-refresh works from inside it, one up at its bottom scrolls on
   down the page; owner's requests, 2026-10-23 and -24; and a redraw keeps
   the reader's place in it, `BRIEF_SCROLL`, owner's request, 2026-10-24).
   Its line
   reads "Briefing updated 7:16 AM" (the day too when not today's) and names
   no condition, with the provenance pills' green `.status` dot while that
   update is unopened on this device (`BRIEF_SEEN` in localStorage, through
   the gate's `stored`/`store`); opening the fold, or an update drawn into
   an open one, removes it. **Built every collection; UPDATED only when its
   alert, swell or tide words change** (owner's call, 2026-10-22, replacing the
   Morning / Midday issues): the build renders the page's own words
   (`briefingwording.render_issue`, Node) and `briefing.settle` compares the
   swell and tide lines with the newest kept line's, so a change below the
   page's precision is no update. **It updates most hours, and that is the
   owner's call** (2026-10-22): over the week to then the swell sentence
   alone changed on 139 of 170 hours (82%) — the floor/ceil range flips when
   any break crosses a whole foot, and the lead period hops between the
   buoy's bins (13.3 → 14.3 s), so whole seconds change nothing. 3-hour
   medians gave 45%, 6-hour 24%; the owner kept every hour's own numbers so
   the words always match the cards. The conditions refresh every build
   without one; the page redraws on a new `built_utc` and moves the time and dot only
   on a new `key`. **NWS's coast and ocean alerts come first** (owner's
   request and calls, 2026-10-24; `forecast.alerts`, archived by
   `collector/nwsalerts.py` → `data/alerts/`): a line each while one is in
   force at the build, "Coastal Flood Warning until 2 PM Sun" (always the
   weekday, so midnight is no update; "in effect" with no NWS end), an ink
   triangle, the event linking to NWS's showsigwx page as the owner's link
   has it, a grey NWS tag, and tapped NWS's own `headline` — NWS's words,
   escaped, and exempt from the page's vocabulary test because "Rip Current
   Statement" is NWS's name. Coast and ocean only (owner's choice): every
   alert for PZZ750, and CAZ043's events in `COASTAL_EVENTS`, never heat,
   fire weather or wind on land, never a Test. In force is NWS's own times:
   onset (never before `sent`) to `ends` (`expires` without one); a later
   alert that references it takes over from its `sent`, and a Cancel or an
   all-CAN/EXP/UPG VTEC alert ends it and is never shown. One line an event.
   An alert that starts, moves its end or ends is an update (its words enter
   `update_words` first). **The Forecast tab shows them too**, above the
   Swell card on the backdrop (`#fc-alerts`, `fcAlerts`), every version in
   force from the hour shown to the next one the picker offers, "from …"
   when it starts after that hour, from `alerts.json` (48 h back, as NWS had
   it by the build, `forecast.alerts`, each collection). The archive is
   every alert the active listing returns for CAZ043 and PZZ750, each its
   own `/alerts/{id}` document byte for byte, written once by its id
   (`data/alerts/YYYY/<oid>.json`); an alert issued and ended between
   collections is a gap. api.weather.gov is denied from a session: built on
   the API's documented shape, unverified against a live alert until the
   first one lands. Three blocks, apart by the cards' fold rule (owner's call,
   2026-10-23, replacing Origin's dot) — Swell, Tides, then Conditions (the
   tide moved above the conditions, owner's call, same day; described below
   in their earlier order), every number that says something in
   ink and heavier, the metric in brackets grey (`briefNum`): **Swell** (owner's
   wording and calls, 2026-10-23), TWO SOURCES never matched to each other.
   Each swell sentence a line of its own, 6 px apart, the beach's compass
   points in ink like the numbers (owner's request, same day). The beach
   (owner's choices, same day) is a HEADLINE: the range at 27 px, "3–4 ft
   (0.9–1.2 m)" (the three cards' breaking heights, lowest floored and
   highest ceiled to whole feet, at least a foot apart), the biggest
   breaking height each hour over 24 h a sparkline beside it (`beach_spark`,
   `swell.spark`, kept out of the record by `unsparked`); then A LINE A
   TRAIN, "SSW at 13.3 s · building" (its words "SSW at 13.3 s, building."),
   no trend mark: every swell train at ANY of the three breaks at ≥ HALF
   the biggest one's height, biggest first (owner's call, same day, after
   the WSW sea leading Center and South went unsaid because North, the
   biggest break, held only an SSW train; `MIX_SHARE` 0.5 of height; never
   wind sea or chop, unless no swell train exists at all), **ONE LINE A
   TRAIN AT 46232** (owner's call, 2026-10-24, replacing one a compass
   point, which listed one W swell twice, W 9.1 s at South and WSW 9.9 s at
   Center, either side of the 258.75° boundary): each carried row's
   `buoy_train` (now.py, `forecast.trainmatch.buoy_train`) is the buoy
   train holding its peak period, and of a band the buoy divided by
   direction the one holding its heading, else the nearest; trains of one
   buoy train are one line, the biggest's words. MEASURED first
   (`python -m forecast.trainmatch`, owner's condition): periods alone
   joined two buoy trains on 24% of its joins over the archive, nearly all
   a band the buoy divides by direction, and was rejected; in a known-answer
   control the shipped rule is wrong on 6.1% of joins of swells ≥ 3 s apart
   (17 of 18 a 15 s SSW + 12 s from 250–270° the buoy itself reads as one
   train, §40) and 25% at 1–2 s, catching 97% of duplicates where the
   compass point was wrong on 34% and caught 46%; pairs with a train no
   swell carries ⅔ of are counted, not scored. each its row's
   OFFSHORE heading (the larger direction of a two-direction train, never
   its 5 m one) and period, and ITS OWN STATUS (owner's call, same day):
   its band at 46232 -- the bins it holds in the newest spectrum and the
   offshore headings holding 90% of what it carries to the break
   (`Train.held`, `nearshore.HELD_SHARE`; now.json trains' `band_hz` /
   `held_deg`) -- as energy over a trailing 3 h (`train_trend`, `trend_word`;
   a bin MEM cannot represent read as the chain reads it, by NDBC's Fourier
   form, `band_energy` / `fourier_sector`, since 2026-10-27: dropping the
   band left 9 of 225 lines with no status, and 16.7% of 46232's spectra
   hold such a bin):
   building ≥ +25% on 3 h before, fading ≤ −25%, peaking when the day's
   highest came within 3 h, else holding. Nothing follows a train between
   spectra, so it is the band's energy at the buoy, not the train's at the
   break; how often each word fires is NOT measured yet (the beach-wide
   trend it replaced was: holding 67%, peaking 16%, building 11%, fading 4%).
   Metric in brackets by the units rule. Offshore, each 46047 west / north-west swell: FOUND by a
   ×3 rise (§43's three bands plus 8–10 s, owner's request, whose lag §43
   did not check) in the last 72 h, its bands the newest rise and each
   LONGER band's newest rise before it within 24 h (`disperse`: long periods
   lead), and SAID only while a band of it is still to reach the breaks
   (owner's calls, 2026-10-24, replacing "arriving since", which read as
   arriving at the beach): the band due next (`next_band`), the next once
   that band's window at the breaks — due at 46232 plus the slowest leg —
   has passed, and nothing after the last, when the swell is the headline's
   to show or not at all; or sooner, once its sector's 8–17 s energy falls
   under a third of its peak since it began. In plain words with no
   ink, each OPENING ON ITS POINT, no "first", and saying "offshore" on its
   trend, which is Tanner Banks' own (owner's calls, same day, replacing an
   "offshore" tag, which had replaced an "Offshore:" line), with a grey
   SIGNAL MARK in the margin — a dot, the origin, sending two arcs — turned
   to the swell's direction of TRAVEL, its sector's middle plus 180°
   (`briefSignal`): "W 10–12 s, building offshore; due at Point Loma South
   around 1:33 PM, and at the breaks 39–53 min later." The due time is
   computed, never a measured arrival (§43), and the trend is Tanner Banks'
   NOW: building ≥ +25% on 3 h before, fading under half its peak, else
   peaking. Hourly over the 60 days to 24 Oct a line showed on 19% of hours
   (the first band's window alone would have given 10%; with "arriving
   since" it was 91%), a swell caught a median 3.1 h before its first
   band's window. SW at Tanner Banks is never said (owner's call): it is not
   upstream of the breaks for a south swell. A dark 46232 says so and nothing
   else.
   **Conditions**, a LEDGER (owner's calls, 2026-10-23; `briefConditions`,
   `briefCondRow`): a row each, its name in small caps, an ink arrowhead —
   up, down, or a dash for no change, none with no earlier reading — the
   value, and a sparkline of its recent readings, broken at a missing hour,
   with its window (`briefing.trends`). Water 46232's (≤ 6 h: its standard
   met reaches the archive on collect.yml's throttled schedule, a median
   2.7 h old; 14 d), KNZY's air temperature and humidity (≤ 90 min; the T
   group's tenths, Magnus; 24 h), its PRESSURE (the body's A group, inHg
   as published, hPa in brackets; 3 d; owner's request, same day), and RAIN
   only when the last hour's (the newest routine report's P group) or the
   rolling 24 h's (every routine report's; a SPECI's repeats its hour) is
   above zero, then both, with a bar a Pacific day for 7 d. **Water and air
   are compared 3 h back** (owner's call, measured: the reading before was
   the same on 64% of 46232's half-hours and 32% of KNZY's hours, 3 h back
   22% and 15%), humidity and pressure with the report before; a change
   under half a source's step is steady, humidity compared in the whole
   percent shown (it is computed). A tapped row says when it was read, by
   what, and against when. The record keeps the arrows, never the
   sparklines (`unsparked`): they are the archives' own readings again. **Tides**: the
   Pacific day's predicted turns, "AM low 0.7 ft (0.21 m) at 3:15 AM", with
   the gauge's departure as the card's carry it — DRAWN AS THE DAY'S CURVE
   (owner's choices, 2026-10-23, replacing that day's ledger;
   `briefTideChart`, `tide_story`'s `curve` and `nights`): the same
   prediction at the open coast with the departure every 30 min
   (`TIDE_CURVE_MIN`), Coronado's midnight to midnight and STRICTLY TODAY —
   no next day's turn at the edge — each turn's height by its dot (above a
   high, below a low) and its time on the axis under it, the hours gone and
   their turns grey, the rest ink, now an open dot on the curve alone (no
   line, no word) with a ring rippling out of it — to 3× over 2.6 s as it
   fades, then 2 s of rest (`BRIEF_RING`), none under reduced motion
   (owner's choices, 2026-10-25). A Web Animation counted from the page's
   timeline (`ringNow`, startTime 0), never a CSS animation: the chart is
   redrawn every minute and on every width change, each time a new ring,
   and a CSS one restarted on each even with a clock-set negative delay
   (measured the same day: phase jumps of 1.5–2.5 s, now 0) — nights shaded as the Tide card's charts are — from under
   a top row with the day's sunrise and sunset, each an icon (horizon, half
   sun, arrow up or down; `BRIEF_SUN`) beside its time, set as the turns'
   times are and grey once passed (the shading's own edges,
   `daylight`'s sea horizon at the center break, packed in order by
   `briefRow`) to just above the times, so every height sits on the
   shading (owner's requests, 2026-10-24); drawn at its own width
   (`fitBriefTide`, a ResizeObserver, as the fold opens); tapped,
   "Predicted · NOAA 9410170 · departure +1.5 ft (0.46 m)". The record
   keeps the turns, never the curve (`unsparked`). Each turn's words
   (`briefTideText`) are the ledger's, so the curve was no update. **Every update is kept**:
   `data/briefings/YYYY-MM.jsonl`, append-only, the build and its words; its
   one writer is collect-beach-inputs.yml's "Record the briefing", in a
   sparse worktree of the branch's NEWEST tip, re-appending on a rejected
   push, never rebasing; `briefing.json` is each build settled against the
   newest kept line. The lines from 18–22 Oct are the Morning / Midday
   design's (`issued_utc`, no `update_words`), never matched. **Never the
   model**: GFS-Wave and its ensemble are the Forecast tab's. Units as each
   source publishes them (°C, METAR's inches), converted only on the page
   (`fahrenheit`, `MM_PER_IN` beside the other unit constants). The 10-17
   design's measured words (filling / fading, leader, a ridge's period
   ahead; `forecast/briefingreport.py`, `docs/briefing_thresholds.md`) are
   no longer said; their constants stay in briefing.py for the report.
   **Long-period energy ahead is NOT said** (measured 2026-10-27 at the
   owner's request, kept in the same report to re-run in winter): 46232's
   energy at 14, 16 or 18 s and longer from the breaks' windows doubling on
   3 h before came before a beach 15% higher within a day LESS often than
   any hour did (25–60% against 69%), and before a bigger day at most one
   firing in five (13% for any hour); a test says when a winter archive
   passes the 85% rule.
   Wording generated from the page into `docs/briefing_wording.md` (the
   formula and each case) and `docs/briefing_sentences.md` (every distinct
   line once, for the owner to edit; edits are carried into the page by
   hand) by `forecast/briefingwording.py`, both pinned by a test.
   **The foot of the page** (owner's design, 2026-10-28): ONE line,
   "Docs | Observer | Units [Both] | ◐", centred on a wide screen and
   spread edge to edge on a phone (≤ 600 px; owner's call, 2026-10-29) — Docs in ink at the line's
   weight, Observer the gate's checkbox drawn as a switch, Units a bordered
   chip that shows its setting and cycles Both → Imperial → Metric on a tap
   (its word centred cap-to-baseline in the chip, measured at 4x; always as
   wide as "Imperial", so a tap never moves the line), and the theme a
   half-lit disc at the right end: a tap gives the other theme, and landing
   on the phone's own forgets the choice. Below 340 px the bars drop and the
   gaps close, keeping one line at 320. The theme is applied before the
   first paint by a script at the top of the page (docs.html too, which
   follows the same saved choice) and sets `color-scheme` with it.
   **The log-first gate** (owner's call, 2026-10-16): "Wave observer", the
   Observer switch, kept in localStorage (with the Briefing's last opened
   update and the Units and theme settings, its only uses, pinned). On such a device the page opens on "Logging the beach today?"
   and nothing else until today's log is done or declined; it returns at
   Coronado's midnight, and ticking it after looking starts it tomorrow.
   That question is the ONE place the page links to the log; docs.html
   still never does.

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
  own refresh interval, because only it knows that, and to the RED instant
  alone `PUBLISH_LEG_MS` (5 min; owner's call, 2026-10-23, BRIEFING §46): the
  run publishes ~2.1 min after its mark and Pages deploys after that, so red
  at mark + refresh caught files still on their way. The countdown is not
  moved; "Update due" covers the publishing.
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
  on the late one. Swell 15/36, tide 5/10 (re-bracketed 2026-10-23 on ~6,800 samples: 8 sat inside the tail, 34 were still absent past it; an outage at CO-OPS is red and rightly, owner's call 2026-10-27, after ten samples of 26 Oct landed 100–154 min late in one batch), wind 3/4. n = 6 for the swell, which
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
- **Past `STALE_HOURS` (3 h) a LIVE card's numbers go grey** (owner's call,
  2026-10-25; `agedAttr`, flipped by `tickDue` on the reader's clock, the
  build's `stale` a floor): every such text one shade, `--faint` — a
  secondary train's heading within a few steps on both themes, so secondary
  rows lose their fade — weights kept, and back to normal when a newer
  reading lands. Each card its own source: break tabs and 46232's reading by
  46232's spectrum, 46047 and 46086 by their own, Wind (value and each
  break's line) by KNZY, Tide's height by the gauge. NOT the calculation
  table or Origin (right for the reading they were made from), the
  provenance, or the tide's predicted turn; on the drawing only the leading
  train's arrow. A rose frame greys only if it was itself the stale
  reading (`roseAged`): more than 3 h from its stamp to the NEXT frame's
  stamp, or to now for the newest — petals and the line under them,
  Period's bands kept in order up to `--faint` — never the rings or
  N / E / S / W. A frame replaced in time stays in ink however old it grows
  in the loop: greying frames by their age today greyed every current
  buoy's 3–6 h frames, and greying the whole rose with its newest frame was
  wrong too (owner's calls, same day). Stamps, not arrival times, by the
  owner's call.
  Red "Overdue" starts long before this, at each source's late instant.
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
  run it is showing, rather than printing the URL. Its spectral tar can land
  after the bulletin (2026-10-22 12Z), and `live.fetch_spectra` says that too;
  no spectrum note carries a URL (it ran past the card on a phone), the build
  log keeps it. The build's notes show on the Forecast tab only, in greys
  under a warning triangle (owner's call, same day): LIVE is measurements.
- **Retry what a build loses for its whole life, not what the next
  collection fetches again.** `common.retrying` (owner's request,
  2026-10-15) tries the NWS grid three times and GFS-Wave's spectral tar
  twice on a 5xx, 408/429, reset or cut stream: a failed fetch cost a whole
  build its local chop (2026-10-12 02Z) or put it on partitions (2 of 158
  builds). Never a 404, never a proxy's refused tunnel (BRIEFING §8,
  `common.is_transient`), and never the tar's timeout, which at 600 s would
  run a second try past forecast.yml's 15 minutes. KNZY, CO-OPS, NDBC's
  spectra and the b-decks are NOT retried: each collection re-reads a
  trailing window (6 h, 24 h, 45 days, the whole file), so a miss is filled
  ten minutes later; NDBC's standard met and the GFS/GEFS bulletins keep
  their own older retries.
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
- **A test that measures the archive grows with it, so it must never be
  quadratic in it.** Measured 2026-10-12: the suite took 347 s, 285 s of it in
  30 tests, and the two worst scanned a whole series once per sample — the
  tide-direction pin (85 s → 0.09 s by bisection) and `tidesite.measure`
  (20 s → 0.5 s, `interpolate` rebuilt its stamps every call). Both gave
  identical results after the fix. `tests/conftest.py` reads the ensemble
  archive once a session rather than once per `live.build`, and `tests.yml`
  runs on every core (`-n auto`): 49 s on four. Check `--durations` before
  adding a test that reads `data/`.
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
                        harcon.py (NOAA's harmonic constants for 9410170,
                        as served, monthly; the phase fold's — §41),
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
                        nwsalerts.py (NWS's alerts for CAZ043 and PZZ750,
                        each one's document byte for byte, once by its id
                        -> data/alerts/; Actions only),
                        nhcforecast.py (NHC's official forecast, the OFCL
                        lines of each live storm's a-deck, Actions only —
                        unverified against a live file until its first run),
                        bathymetry.py (USGS CoNED seabed, regional 32 m and
                        nearshore 8 m, NAVD88; the MSL offset is fetched from
                        CO-OPS on Actions — needs requirements-precompute.txt)
    app/forecast.html   the app surface — Coronado's three breaks       [built]
    app/docs.html       the documentation, the live page's one link: every
                        card, chart and calculation; one contents pill built
                        from its own headings, with full-text search, its
                        panel growing out of it (at the bottom on a phone, at
                        the top on a wide screen; owner's design, 2026-10-29,
                        replacing the sidebar and drawer); the caveat, the cycle line and both chains'
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
      bending.py        which way each offshore heading arrives in 5 m,
                        per break, into docs.html's swell-bend table [built]
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
      tidephase.py      the Tide card's phase fold: spring / neap and the
                        declination from NOAA's constants, the Moon's
                        events, the card's turns as evidence; pure Python;
                        never a turn or a height for the card     [built]
      tidephasereport.py its thresholds measured over 19 years; reports,
                        never edits (BRIEFING §41)                 [built]
      tidephasewording.py its wording, run from the page's own code into
                        docs/tide_phase_wording.md; --check         [built]
      moon.py           the Moon's phases, distance and declination
                        (Meeus ch. 47), pure Python                 [built]
      daylight.py       sunrise and sunset at the center break, for the
                        Tide charts' night shading; computed, not fetched [built]
      skyline.py        PRECOMPUTE (numpy): Point Loma's skyline from each
                        break off CoNED's land, into data/nearshore/ [built]
      sunset.py         the Sun card: sunrise, and each break's sunset
                        behind Point Loma or in the sea, and its season;
                        pure Python (Meeus ch. 25)                [built]
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
      buoys.py          the LIVE tab's Buoys tab below 46232: 46047 and
                        46086 at the buoy, not carried to any break, each its
                        own countdown and words                    [built]
      rose.py           one spectrum's height and period rose by compass
                        sector, for the Buoys tab's six-hour loop   [built]
      alerts.py         NWS's coast and ocean alerts: which are in force,
                        and over which hours; the Briefing's top line and
                        the Forecast tab's, alerts.json             [built]
      briefing.py       the LIVE tab's Briefing: built every collection,
                        updated when its swell or tide words change, each
                        update kept in data/briefings/             [built]
      trainmatch.py     a break's train to the buoy train it is, for the
                        Briefing's one line a swell; and the archive and
                        known-answer control that chose it; reports  [built]
      briefingreport.py its thresholds, measured; reports, never edits
      briefingwording.py its wording, run from the page's own code into
                        docs/briefing_wording.md; --check           [built]
      stormdue.py       when a storm's swell is due at each break, from NHC's
                        best track and official forecast             [built]
      upstreamlag.py    46047 → 46232 → the breaks: deep-water lag, checked
                        against the archive; reports (BRIEFING §43)  [built]
      origin.py         the LIVE tab's Origin: each train's dispersion
                        ridge in 46232's spectrum, bearing at 46047
                        [built]
      originreport.py   the measurements behind it; reports, never edits
      originwording.py  every wording Origin can show, run from the page's own
                        code into docs/origin_wording.md; --check     [built]
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
                        series_all.json, windtide.json, origins.json,
                        buoys.json, briefing.json and alerts.json, what the app surface
                        reads (derived, gitignored)
    data/alerts/        YYYY/<oid>.json: every NWS alert the active listing
                        returned for CAZ043 and PZZ750, as NWS served it,
                        written once (collector.nwsalerts, its one writer)
    data/briefings/     YYYY-MM.jsonl: every Briefing update, as built and as
                        worded (18–22 Oct: the Morning / Midday issues).
                        PERMANENT, append-only, one writer ("Record the
                        briefing"); the page's briefing.json is each build
                        settled against its newest line
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
                        _turns (the harmonic model's own highs and lows),
                        and _harcon.json (NOAA's harmonic constants, as
                        served: the phase fold reads them)
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
                        <break>_skyline.csv (the land's angle above the eye
                        every 0.02° of azimuth, 225–315°; forecast.skyline)
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
  on the sand. Since 2026-09-30 the Wind card carries the local wind,
  and since 2026-10-20 it LEADS (owner's request): the NWS wind first, with
  KNZY's observed wind under it on a past hour, then GFS-Wave's under an
  "At the buoy" heading — "Local" is no longer a heading. The local wind is
  the NWS forecast grid at Coronado's center break
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
- **Imperial leads, metric in parentheses, everywhere a number is shown — by
  default.** "2.3 ft (0.71 m)", "9 mph (8 kt)". Since 2026-10-28 (owner's
  call) the reader's Units setting at the foot of the page can show
  Imperial or Metric alone instead: every number goes through the page's
  one `dual` / `dualText` (beside the constants), a metric value alone is
  the "both" form's bracket and never a second rounding, wind's metric stays
  knots (owner's call, same day), and the chart axes and the rose's rings
  step in metric units on Metric. docs.html keeps both throughout: its
  worked numbers are checked against each other. Python's report strings
  (`forecast/units.py`) are not the page and keep both. **Nothing upstream of a display converts**:
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
  earlier; the source line (on LIVE the countdown pill) names the gauge it
  was carried from, the measured reading keeps the gauge's stamp for its
  countdown, and `gauge_height_m`
  keeps the raw value. Breaking uses the MSL form (`tidesite.coast_level`)
  from the gauge's raw reading — never from the card's, or the transfer runs
  twice. And the harmonic prediction is on the 1983–2001
  epoch: the measured level ran ~0.23 m above it in Sept 2026, so the
  forecast carries the last 3 days' measured departure forward — and computes
  no breaking at all without one.
- **The line under a past forecast hour says when it was observed, never
  "what happened".** Blue, in a 1 px outline at the card's radius, and
  labelled "Observed at 8:00 AM" (the tide's "Measured at 8:00 AM") — owner's
  wording and style, 2026-09-27. Every measured element on the Forecast tab is
  `--measured`: the selected tab's blue, `var(--surf)`, on both themes
  (owner's call, 2026-10-09, after red from 2026-10-02 and sea green before;
  5.4:1 light, 7.0:1 dark), so the Ensemble's mean and band went grey. Under
  a past hour KNZY's observed wind sits under the Local forecast, not under
  GFS-Wave's wind at the buoy (same day): both are the wind on the sand. Where it comes from is said on `docs.html`:
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
