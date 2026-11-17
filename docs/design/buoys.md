_Read before touching the Buoys tab: 46232 / 46047 / 46086 cards, the station block, the rose, the buoys' Height chart._

# The Buoys tab

Moved verbatim from CLAUDE.md on 2026-11-14 (the context-reduction
restructure); CLAUDE.md keeps the one-line rule and points here.

## The Buoys tab

   **The buoy's tab reads "Buoys"** (owner's request, 2026-10-06; BRIEFING
   §39), on both chains, its id still `buoy`. On LIVE it holds 46232 and under
   it **46047, Tanner Bank**, built the same way — combined height, maximum-
   entropy trains split by period then direction (§40) — with its own name,
   observed time, countdown and words under its rose (since 2026-11-10 the
   station block below) (`forecast/buoys.py` → `buoys.json`, its own step in the
   collection). **Each buoy's provenance follows its own measurements**
   (owner's call, same day): 46232's reading, then the card's provenance
   (46232's), then each context buoy's block with its provenance in the
   same style.

## Context buoys, station block, rose, Height chart

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
   **Under every buoy's rose, 46232's too, a STATION BLOCK** (owner's
   request and picks, 2026-11-10, from a mock; replacing 2026-10-12's one
   sentence; `buoys.about`, in buoys.json as `about`, drawn by the page's
   `buoyAbout`): on a PLATE of the page's paper set into the card (the
   owner's pick of four separations; since 2026-11-11 outlined as the rose's
   and the swell's plates are, with 21 px of card above and below it, box to
   box, each place it sits saying its own margin), no name or station (the card has
   both). Readings two to a row, a label in the fold rows' type (no
   symbol since 2026-11-11, owner's request), the value and its OWN time -- a hidden line since 2026-11-11, as a
   Briefing row's: a tap on any reading shows or hides every reading's time
   on every buoy (`BI_TIMES`, `toggleBiTimes`; owner's request) -- greying
   past 3 h as every LIVE number does: Peak (period and FROM direction, `at_buoy`'s, a test pins it),
   Mean period (Tm02 over the headline's own energies, `bin_energies`; NDBC's
   APD is computed differently), Spread at peak (√(2(1 − r1)), Kuik), all
   from the newest spectrum; Water, Wind (knots from NDBC's m/s, its gust in
   the time line) and Pressure from the standard met, the newest within
   `STDMET_WITHIN_H` (24 h), "none in 24 h" otherwise, and a column the
   archive has never held NOT SHOWN (46232, a Waverider: wind and
   pressure; owner's request, 2026-11-11, where it said "not measured"). Then a hairline and the facts, a symbol each: Location —
   distance and bearing from Center break (`forecast.siting`'s, never
   typed), NDBC's coordinates linked to its station page, and "In … of
   water", the depth `collector/stationdepth.py` reads off that page
   (monthly, collect-beach-inputs.yml its one writer, checked against the
   live pages 2026-11-10: 1049.8 / 1862 / 1390 m); Updates — the countdown's
   own `PUBLISH_MINUTES` and typical lag; and Used for — `buoys.USES`, one
   line each in the same type, none a grey second line (owner's request:
   each use as important as the next). **No window line** (owner's call,
   same day): the standing-on line still names each buoy's windows. Left
   off by the owner's pick: air temperature and dewpoint, hull. Advised
   against and not built: NDBC's own WVHT / DPD / MWD (a second reading of
   the swell by another method; 46232's MWD is §38's mean) and NDBC's
   swell / wind-wave split (by period, against §51). **46047's standard met
   is collect-beach-inputs.yml's since the same day** (owner's call; beside
   46232's and 46086's, collect.yml excluding all three): on collect.yml's
   throttled schedule it ran hours behind its spectrum. Each value still
   shows its own time. LIVE only, as the rose is. At 15 px, the size of
   "combined" beside the height (owner's request, 2026-10-14), and a buoy
   with no rose says "No spectrum from … in the last six hours." at that
   size and grey. Its countdown is its
   own: :20 and :50, 25 typical and **115** worst on 188 stamps since its
   sensor returned 2026-10-08. The three past H+85 were NDBC's, shared with
   46047 (10-10 07:50 reached H+125 there, past 46047's shipped 85; not
   changed, the owner's call). On the Height chart 46086 is the second
   lighter line, dashed, as a break tab's second other break is — whatever
   the tab's order: the page reads `heights` by key, and JavaScript orders
   numeric keys ascending.
   **Under each buoy's reading, a rose** (since 2026-11-11 on a plate with a
   tray, as the swell's drawing and map: white inside, the Height / Period
   toggle at its top-left showing what a tap turns to, play / pause at the
   map's 28 px 4 px from the plate's corner, the scale line and the Period
   legend in the tray in its caption's 14 / 21 px type, the tray a line
   taller when they need one and the legend taking no room on Height; where
   the text below says otherwise, this supersedes it) (owner's request, 2026-10-06;
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
   (owner's request, 2026-10-09). **The drawing shows no heading in 5 m of water**
   (owner's call, 2026-11-10, removing the arrowhead at the break and the
   caption line "from SW 222° in 5 m of water" shown since 2026-10-22): by 5 m
   nearly everything arrives within ~16° of straight in, and the map mock's
   traced rays show the turn. Each train's own rays' 5 m heading,
   energy-weighted, is still computed and kept in the payload
   (`nearshore._arrive`, `near_from_deg` / `near_lobes`), never in a row, in
   case it is useful as a trend. docs.html's `swell-bend` table is the same
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
   and readout, is named as its pill names it — "NDBC 46232", "NDBC 46047",
   "NDBC 46086" (owner's requests, 2026-10-14 and 2026-11-06), never
   "Buoy 46232"; and so is every buoy the page or docs.html names in words
   (`buoyFeed`; the geometry drawing's `buoyLabel`). Its height is
   `transform.combined_hs`: `at_buoy`'s m0 to rounding (a test pins it)
   without the trains, MEM's bins summing to one by its pole test alone
   (`spreadmethod.realisable`) — 0.7 s for two months, where `at_buoy` took
   ~90.

## The seabed behind the rose, and the bar

   **Each rose stands on the seabed round its buoy** (owner's request and
   picks, 2026-11-17, group 5, item 9; mocked in "Buoy Rose Seabed" with
   the shipped seabed vectors, not satellite imagery). The swell map's
   seabed (map.md) in its COLOUR theme, the page's light or dark -- never
   the layer list's Grayscale or Lines only -- centred on the buoy and north
   up as the rose is, the rose's outer ring `ROSE_SEA_KM` (40 km) out for
   every buoy, filling the whole plate, no marks. Picked over 120 km (the
   islands), 250 km (the Bight) and each buoy's own scale to Center break
   (29 / 82 / 222 km, not comparable buoy to buoy); over Faded, Grayscale
   and Lines only; over the map inside the rose's circle only; over dots
   and names for the breaks and the other buoys. At 40 km 46232's plate
   holds Point Loma, the Coronado Islands and the beach; 46047's Tanner and
   Cortes Banks; the plate's corners reach ~57 km. The buoys' coordinates
   are map.json's (NDBC's fetched, `seaWhere`), never typed.

   - **A STILL IMAGE** (owner's call): nothing on it moves and a tap goes to
     the rose, so `roseSea` (in the map's module) draws every shown rose
     with ONE offscreen MapLibre map -- `preserveDrawingBuffer`, the plate's
     size, the device's pixel ratio, the buoy at the rose's centre by the
     map's padding -- reads each into a PNG and removes the map, letting its
     WebGL context go. A new size or theme draws again (keyed by buoy,
     theme, size, centre, ring and pixel ratio); each image is kept for the
     visit, so a refresh, which rewrites the cards every minute, puts the
     same image straight back (`roseSea.src`). Until it lands the plate is
     the seabed's 1,000-2,000 m colour. Measured in Chromium (software GL):
     at 390 px one image, 328 x 310, the offscreen host gone after; at
     1300 px both roses shown drawn by one map, 281 x 310; a theme switch
     redraws both in the new theme.
   - **The rose in the dark theme's colours on both themes** (owner's
     request, same day, "white dominant"): over the seabed `--ink`,
     `--soft`, `--faint`, `--line-strong` and `--card` are the dark theme's
     own inside the rose and the legend's swatches (a test holds them to the
     dark tokens), so petals, points and the Period bands run dark slate to
     white and a stale frame greys in the dark theme's grey; the rings in
     ink at .38 (the grey rule vanished on the sea in the mock). The tray is
     still the page's paper: each swatch gets a hairline in the page's rule
     so the near-white one shows on the light page. The legend now says
     "shortest faintest".
   - **Where no map can be drawn** (no WebGL, or the library, map.json or
     the map failing: `seaFail`), the rose stays on the plain card in the
     page's colours and its line drops the reach, as before this change.
     Measured with Chromium's 3D APIs off: no image, card colours, "Rings
     every 2 ft · 8.9 ft combined".
   - **The line under the rose** (owner's requests, same day): "Rings every
     2 ft (0.61 m) · Map 25 mi (40 km) to the edge · 8.9 ft (2.70 m)
     combined" -- the reach said, through `dualText`, so a ring is not read
     as a distance (first left off, then asked back); the frame's time left
     to the bar, which shows it; the combined height kept, as it changes
     while the loop plays.
   - **"Seabed GMRT"** at the plate's top right, in the swell map's source
     line's type, white with a soft shadow (it can sit over land): GMRT's
     licence asks for the credit, and at the roses' zoom only GMRT's grids
     are drawn.

   **THE BAR, as the break map's fill bar** (owner's request, same day):
   along the plate's foot, play / pause, then the six hours in a
   card-coloured pill -- the shown spectrum's time (or the moment a gap or
   a stamp not in yet is named by), the line filled to the moment and a dot
   on it -- then ft / s in the bottom-right corner, where it was before
   2026-11-11. Each 28 px, 4 px apart and 4 px inside the hairline, 6 px
   under the rose, so the plate keeps its height (311 px at 390, as
   before). The tick for every spectrum stays on the line, so a missing
   spectrum is still a missing tick (the fill bar has none); the shown
   frame's tick in ink. A tap goes to a moment, a drag scrubs (pointer
   capture), the arrow keys still step half an hour. This supersedes the
   2026-11-11 top-left toggle and the SVG timeline above.
