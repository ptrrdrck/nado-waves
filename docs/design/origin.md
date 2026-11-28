_Read before touching Origin, its marks and lines on the trains, storm matching, NHC tracks, or the Origins chart._

# Origin and the Origins chart

Moved verbatim from CLAUDE.md on 2026-11-14 (the context-reduction
restructure); CLAUDE.md keeps the one-line rule and points here.

## Origin on the trains (since 2026-11-28)

   **Origin is no longer a fold** (owner's request, 2026-11-28, mocked in
   "Origin on the Trains" on that day's LIVE data and on 6 and 11 Oct
   rebuilt from the archive, three rounds). Each origin arriving now is a
   line under the train it is matched to, folded until that row is tapped.
   The Origin line, its count, its rule, its stored open state
   (`nado-waves.origin-open`) and the wide screen's one block for the beach
   (`beachOrigin`) are gone; each wide column's trains and 46232's on the
   buoys card carry their own, as a phone's tabs do. LIVE only, as before.
   Everything in the next section about how an origin is read, matched,
   named and placed stands; what it says about the fold, its count and the
   last readable arrival is history.

   - **The mark** (owner's calls, same day): a matched row's period is
     underlined with dots (1 px, 3 px under), and its kind's mark sits LEFT
     of the period, out of the flow so nothing on the row moves -- the
     tropical cyclone symbol for a named storm (`stormSymbol`, eye open for a
     tropical storm and filled for a hurricane) or a ring for Origin's own
     reading, in the period's grey. Two origins on one row, two marks. The
     first round put it after the period or at the row's end; the owner
     asked for the left, there being room. Measured at 390 px: 64-72 px
     between the height and the period in Imperial, 61 in Metric.
   - **Scale and centring, measured at 4x on real rows**: the row is 21 px,
     the period's digits 10 px tall and centred on it (5.5-15.5). Both
     symbols are drawn on one 20-unit grid in a 13 px box at one stroke (2
     units); the ring is r 6.75 (ink 10.5 px) against the storm's 11-11.5
     px of arms, a closed circle reading as large as the open arms (r 6, ink
     9.5, read small). The marks' ink centres sit within 0.25 px of the
     digits' in every unit setting. A `translateY(-50%)` put them 1 px
     lower in "Both" than in Imperial with identical boxes (a paint offset
     snapped differently as the row's fractional position moved), so the
     box is placed by `top: calc(50% - 6.5px)`; a further 0.25 px moved
     nothing (snapped). 6-7 px from the mark's ink to the period's.
   - **"Both" units** (owner's pick of three, same day): there a height
     fills 87.4-95.5 px of its 96 px column, leaving 16.6 px to the period
     under 10 ft and 8.5 from 10 ft, against the ~22 a mark needs. The
     height column is 110 px in "Both" on every list (`.trains.both`), so
     nothing jumps between tabs: 15-16 px from the height's ink to the mark.
     At 320 px that ran headings 7-20 px past the list (2-6 px before), so
     every row's heading now ends on its point alone (`trainForms`: "SSW"
     after "SSW 204°"), measured fitting 5 px inside the list. Rejected: no
     shorter form (overrun), the mark at the row's end in "Both" only (the
     mark moving with the units).
   - **The tap does both** (owner's pick, same day): a row that picks its
     arrows on the drawing, or its period on the rose, still does, and opens
     its line; a second tap undoes both; a pick moved elsewhere, from the
     list or the drawing, shuts it (`originTap`, `syncOriginLines` from
     `togglePick`). A row that picks nothing opens and shuts its own line
     (`data-origin-row`). Lines slide with the folds (`slideFolds`), are
     shut on every load and kept across a redraw (`ORIGIN_LINES`, by site
     and origin), never stored.
   - **Under the row, or under its bracket** (owner's call, same day): a
     line goes under the block holding its last row -- the row, or the
     bracket of the swell it is in -- and every row of that block opens it,
     a tap on one bracketed row picking the whole swell (Center, 28 Nov:
     the reading is the 14.3 s row's, the 11.8 s row opens it too). A
     storm's band cut into two rows (`also_periods_s`) is one line on both.
   - **Which row** (`rowOrigins`): a named storm's is the row its own test
     passed (`stormtrack._from_storm`): its period, from within
     SAME_SOURCE_DEG of NHC's bearing on either of the row's directions. Two
     rows can share a period: South, 6 Oct 12Z, 14.3 s from 257° and from
     173°, Rachel at 167° -- the fold never had to choose, a row does. A
     reading's is the first row of its period, as `origin.match` takes it
     (by period only, so on a tie the row is the first). Measured over the
     archive (2,398 hours, 4 Aug - 28 Nov 2026; card rows rebuilt as Origin
     rebuilds a past hour, a reading's frequency interpolated linearly
     between its lead and latest periods, as dispersion makes it): two shown
     rows share a period on 9.0-11.7% of hours at the breaks and 5.0% at the
     buoy; a reading sits on such a period on 220 of 3,393 reading-on-a-row
     hours (6.5%: buoy 3.6%, Center 5.7%, North 7.4%, South 9.9%), where its
     row is the first of the two, never chosen. A storm did on 5 named
     moments, 4 settled to one row by its direction test and one (Rachel,
     Center, 9 Oct 00Z, 11.1 s) with two rows passing, the first taken.
     Reported to the owner; not changed (it would be `origin.match`'s). A
     matched row past the list's four is not on the card, nor its origin.
   - **The words** (owner's call, same day): one paragraph in the
     supporting line's 15 px grey, no head at the value size, no storm
     symbol (the row's mark is it) and no "The {T} s train" (the row says
     the period): "Hurricane Rachel. Sent Oct 5 from about 900 mi away. NHC
     had it at 167° SSE, …". The name keeps its NHC link. The formula and
     every permutation: `docs/origin_wording.md`.
   - **Only what is arriving now** (owner's call, same day): a tab's last
     readable arrival has no train to sit under and is not on the card; the
     Origins chart keeps the history.
   - **Its colours under a stale list**: the line keeps them, as the fold
     did (`agedAttr`); the row and its mark grey with the reading.
   - The tabs box still sits 17.5 px painted from the rule below it, now
     Charts', on LIVE and Forecast.

## Origin

   _As it stood until 2026-11-28 (the fold); the section above says what
   changed._

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
   naming the buoy (`heldAt`): "Tanner Bank (NDBC 46047) holds this train
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
   "Tanner Bank (NDBC 46047)" — the state dropped (owner's request,
   2026-10-13) — and 46232 the same way, "Point Loma South (NDBC 46232)",
   here and on docs.html's provenance (owner's request, 2026-11-06,
   replacing CDIP's number) — from `origin.station_names` in now.json
   (fetched metadata, never typed). **No upstream sighting is shown, ever**: measured, the predecessor's
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

## Origins on the map: not built

   **Set aside by the owner, 2026-11-16** (group 3, item 12), to be thought
   through in a session of its own; nothing in the handoff. Mocked in "Seabed
   Map Themes" (its Origins section): for each arrival still arriving on a
   tab's card (never a past one, never an unplaced storm), an arrow on the
   map's rim where the great-circle bearing from the break to the place
   leaves the map, and a two-line label, the card's name and "about N mi";
   crowded labels stacked toward the map's middle, clear of the map's own
   buttons; a dashed bearing line from the break to each mark (the owner's
   pick: on). LIVE only: on Forecast, no marks and no switch. Real archived
   days in the mock: 14 Nov (Center only), 7 Nov (three at once from
   304-313 degrees), 30 Sep (Hurricane Rachel at NHC's fix, 17.8 N 107.5 W,
   with an Aleutian reading), 16 Oct (the Southern Ocean, near the normal).

   **The whole Pacific on the map** (owner's question, same day), so a zoom
   out shows roughly where every origin and storm track lies. What it takes:

   - **The extent.** The 23 archived origins with a place run 67 S to 48 N
     and 173 E across the dateline to 167 W; storms are 500-10,000 mi out,
     the map today reaches just past Tanner Bank and the seabed ~1,200 km.
   - **A Pacific seabed.** Either Natural Earth's 1:10m bathymetry
     (public-domain polygons at 0, 200, 1,000 ... 10,000 m; the project
     already uses its coastline, `collector/coastline.py`; at ocean scale the
     map's 5-4,000 m bands would not show anyway), the cheapest; or a coarse
     GMRT grid (10-20 km cells) fetched from Actions like the others, which
     needs a geographic path in `seabedvector` (every grid is UTM 11N today),
     estimated 1-4 MB, kept on the device after the first load; measure
     before choosing.
   - **The projection.** MapLibre 4.7.1 draws Web Mercator only: Southern
     Ocean storms at 55-67 S drawn 1.7-2.5 times too big, and a straight
     line on the map is not the swell's great-circle path. Either stay on
     Mercator, drawing each path as a densified great circle and carrying
     longitudes past 180 so the dateline does not split anything (the
     recommendation), or move to MapLibre 5's globe, which changes the
     bundled library and its cache keys and means re-checking every map
     behaviour already checked on the owner's iPhone.
   - **Zoom.** `limits` and `pull` hold only until the reader zooms out past
     Tanner Bank; past that the Pacific opens, the shore normal still up.
   - **Honest placement.** A reading's place is "about": distance rounded to
     500 mi, two buoys reading one storm 18-25% apart, the card naming a
     sea. Draw it as an AREA, its bearing and a band of about +/-25% in
     distance, never a dot; a hurricane at NHC's fix, a measured position.
     `forensics.REGIONS` are latitude-longitude boxes for naming, not
     measured storm tracks: at most faint and labelled, only if wanted.
   - **Scope.** The bathymetry workflow, `seabedvector`, its tests and
     manifest, the map's limits and the files kept on the device: more than
     the layer itself.
