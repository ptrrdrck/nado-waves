_Read before touching the Swell card map, its seabed vectors, caching, or the fill._

# The Swell card map, seabed and fill

Moved verbatim from CLAUDE.md on 2026-11-14 (the context-reduction
restructure); CLAUDE.md keeps the one-line rule and points here.

## The map

   **The Swell card's MAP** (owner's requests, 2026-11-06 to -10, mocked in
   `mocks/swell_map` and shipped 2026-11-10): a button in each break
   drawing's top-left corner swaps it for the same windows at true scale
   over the SEABED (owner's choice over Esri imagery, 2026-11-10; a
   satellite option may come later), on both tabs, every layout -- phone,
   tablet, stack and console (owner's call, same day) -- and every past
   hour. The choice is this device's (`nado-waves.swell-view`, through
   `stored`/`store`). It READS THE DRAWING, never a payload of its own: the
   sections' angles (`data-geo`), the arrows, the captions and the picks are
   the svg's, and a map tap goes through `togglePick`, so a row, an arrow
   and a map tap are one pick. Turned the drawing's way, the break's shore
   normal up (MapLibre's `bearing`; the reader cannot rotate it), the
   break as far above the map's foot as above the drawing's, opening three
   zoom steps in from the drawing's scale -- ONE scale for the three breaks,
   the farthest edge vertex of any (owner's request, 2026-11-11: each break
   had opened at its own, South ~0.2 steps nearer); square, at most 70vh; the toggle
   and the caption under it as the owner picked them in the mock. **The
   drawing and the map share ONE PLATE** (owner's requests, 2026-11-11;
   `.sm-plate`, `space`, `slide`), WHITE INSIDE as the drawing was before it
   (the card's colour, a hairline round plate and tray; owner's call, same
   day), every corner button 4 px inside the hairline as the map's own
   controls are: the drawing's trimmed to its ink with
   `PLATE_PAD` (12 px) above and below, the map's square; a switch grows or
   shrinks it from its foot with the folds' slide (`FOLD_SLIDE`), the view
   coming in faded over the one going out, the caption under it in a TRAY
   attached to the plate (same day: a hairline over it, the plate's colour,
   the unit's rounded foot), which rides the foot as the plate grows and
   shrinks above it. Both views stand on the plate's foot: the drawing's
   break `foot` (PLATE_PAD below its ink) above it, the map's opening break
   the untrimmed drawing's (vb.height - cy) * s, ~37 px at 390 (owner's call,
   same day: at 15 px the fill's timeline covered the break and the
   shoreline); the map's canvas unseen until its
   seabed is drawn (a new WebGL canvas paints black first). **The plate
   follows its own break's trains** (owner's call, same day, B of three
   mocked, reversing 2026-11-08's one start height across the break tabs,
   `level`): nothing re-lines the tabs up. That re-lining was also what made
   the map jump after a fold: run mid-slide, it measured the open tab part
   way and the hidden ones whole, overshot ~150 px, and snapped back half a
   second later. It zooms out to just past Tanner Bank (46047 and 25 km in view
   with the break kept where it sits) and pans no further from the break;
   the + / - buttons clamp before zooming round the break. ONE MAP PER
   BREAK, carried across the page's redraws (`Face.adopt`; every minute on
   LIVE), never rebuilt: a new map each minute reset the view (the mock's
   "jump") and would leak WebGL contexts. Drawn by **MapLibre GL JS 4.7.1**,
   BUNDLED in `app/vendor/` with its BSD-3 licence (owner's calls,
   2026-11-10: bundled, not a CDN; MapLibre over Leaflet + leaflet-rotate,
   whose GPL-3.0 would arguably have made the page a GPL combined work while
   the repository carries no licence on purpose), loaded only when a map is
   first shown. The seabed is VECTORS (owner's request, 2026-11-11, after
   2x anti-aliased raster tiles still looked "like a retro monitor" on a
   phone; `forecast/seabedvector.py` -> `data/seabed_vector/`, derived but
   tracked, redrawn by both bathymetry workflows after a fetch, a test failing
   when a grid is newer than its drawing): one GeoJSON a grid, the finer drawn
   over the coarser from the zoom its cells are fit for -- `wide` (GMRT 2 km,
   1,200 km round the breaks, read by no chain; owner's report, 2026-11-11:
   the widest view reaches ~850 km from the break on a 390 px phone, ~1,030 km
   on a 260 px map, and ran off the context grid as bare land colour) from 0,
   `context` (GMRT 400 m, 350 km round the breaks and the three buoys, read
   by no chain) from 0 over it, `outer` (90 m) from 8, `regional` (CoNED 32 m) from 9, `nearshore`
   (8 m) from 11 -- each its depth bands as NESTED polygons (land, then
   the coast -- `raytrace.H_LAND` until 2026-11-15, mean high water since
   (below) -- and 5 ... 4,000 m, so simplifying one edge opens no gap),
   ALL cut to one outline two tolerances inside the grid's edge, with a
   vertex every 250 (`seabedvector.edge`; owner's report, 2026-11-11: a
   land-coloured line across open sea along the context grid's edge -- each
   band simplified alone, and a UTM-straight edge curving on the map, a band
   whose edge was one 900 km chord bowed up to ~3 km from its neighbours;
   a test pins one line on a synthetic grid, 0.06 deg apart before),
   and NO fill draws MapLibre's anti-aliased outline, the canvas
   multisampling instead (`antialias: true`; owner's report, 2026-11-12:
   that outline also traces where a polygon is cut at a TILE's edge, and on
   the turned map faint light lines crossed the sea on tile boundaries,
   32.5468 N at zoom 9 -- not a grid's edge; edges measured as smooth),
   and within a strip three CSS pixels wide (at the zoom a grid is first
   drawn) along each grid's edge every band is cut away under the next
   deeper, so only the band shown reaches the edge (`strip_m`; owner's
   report, 2026-11-12, on an iPhone: MapLibre re-simplifies each shape as
   it draws, edges that meet in the file part by up to ~0.2 px, and the
   land colour under them showed as a faint dotted line along the context
   grid's edge; drawn with no smoothing at all, 128 such pixels at zoom 5,
   none after, and the finer grids' edges the same; a test pins one band,
   the right one, just inside the edge),
   and every file the map loads -- the library, the seabed, each break's
   rays -- KEPT on the device (owner's report, 2026-11-12: it downloaded again
   on visits minutes apart; Pages lets a browser hold a file ten minutes and
   redeploys every collection): Cache Storage, under each file's version, the
   library's in its path and the others' 16-hex SHA-256 fingerprints in the
   seabed manifest and map.json's `paths`, fetched at a URL carrying it so no
   cache hands an older file back under a newer one, a changed file a new
   copy and the old deleted (`kept`); measured in Chromium, a reload fetches
   map.json alone,
   its contours at 5 ... 2,000 m and its shoreline (at H_LAND until
   2026-11-15, at mean high water and unsmoothed since: "The coast is the
   chart's", below); the depths smoothed over ~1 cell before contouring and
   simplified to 2 m near the beach and 80 m past Tanner Bank (contourpy,
   shapely); 1.5 MB, ~0.4 MB compressed,
   against the tiles' 2.2 MB. Contours as drawn for now (owner's call,
   2026-11-10: busy at the widest zooms). **Its colours are the owner's two
   themes** (2026-11-11, picked in the mock "Seabed map themes"; `MAP_THEMES`,
   restyled when the page's theme changes): light a pale sea to deep blue over
   sand, dark blue to near-black over warm charcoal, the bands ramped in OKLab
   (`bandColours`); white lines and marks, no halo; the rays and a picked
   train's arrow orange `#e8590c` laid over each other on light, the shipped
   gold `#ffd84d` glowing ("lighter") on dark, its strength the alpha of a ray
   carrying the 90th percentile's energy. `map.json` (`forecast/mapdata.py`): geomviz's model, 46086
   and 46047 at NDBC's fetched coordinates, and the tile manifest; with
   `seabed/` and `vendor/` it ships from BOTH publish jobs, and
   `publish-pages.sh` replaces a directory whole (its old `cp "$BUNDLE"/*`
   skipped directories and, under `set -e`, would have failed the publish).

## The coast is the chart's

   **The map's coast is mean high water, drawn from the grid as stored, and
   only the sea is water** (owner's report and decisions, 2026-11-15, group
   2b, items 15 and 16; BRIEFING §53). The owner saw the geometry's vertices
   off the drawn coast on the LIVE map: Point Loma's tangents over land,
   Baja's in the water, the breaks on land. Measured per point and per grid
   (signed distance, vertex to drawn coast, + water) and each vertex checked
   against Esri World Imagery, with CoNED lidar read at 2 m, Copernicus
   GLO-30 and GMRT as independent controls, the causes were three:

   - **The datum** (the breaks). Every vertex is chart coastline, which is
     mean high water; the map drew `raytrace.H_LAND`, 0.3 m below MSL, 0.92 m
     lower, which on Coronado's beach is ~30 m of sand. The breaks sat 13 /
     22 / 34 m (N / C / S) inside the 8 m grid's land; on imagery each dot is
     at the waterline, and the chart agrees with CoNED's own MHW contour
     within -4 to +20 m. MHW is NOAA's, fetched (`collector.datums`,
     `data/tide/9410170_datums.json`: 0.623 m above MSL, epoch 1983-2001),
     never typed; a test checks it against the station's harmonic constants
     (0.602 m). The rays still stop at `H_LAND`: waterline and depth contour
     are two claims, and the map draws the chart's.
   - **The smoothing** (Point Loma). A cliff whose land stands 15 m over
     water a few metres deep carries a smoothed coast seaward: 21-43 m at
     the tip on 32 m cells, on top of 18-26 m from resampling a cliff into 32
     m cells. The chart is right there: imagery puts each tangent within
     2-16 m of it and 2 m lidar at MHW within 12 m. So the coast and band 0
     are contoured from the grid as stored, and the deeper bands and the
     contour lines, still smoothed, are cut to the sea.
   - **The chart** (Baja) and **missing islands** (GMRT): not the map's to
     fix. The ENC approach band's Mexican coast lies a median 225-466 m
     seaward of imagery, GLO-30 and GMRT from 32.38 to 32.50 N; the map's
     GMRT coast was right and the Baja tangent wrong; the tangent moved to
     imagery on the same day (geometry.md, item 17, BRIEFING §54) and now
     sits 4 m from the drawn 90 m coast. GMRT lacks Middle and North
     Coronado: since 2026-11-15 (group 2d, item 13; BRIEFING §55) the
     map draws them burned in from their imaged outlines
     (`data/bathymetry/islands.json`), as the rays see them,
     `seabedvector.load_grid` reading each grid through
     `raytrace.with_islands`; all three from zoom 8, South and North
     below it (Middle is under a quarter of a 400 m cell). The manifest
     carries the outlines' fingerprint (what is drawn, not the file's
     notes), so a changed outline fails `--check` until the seabed is
     redrawn.

   At MHW the stored grid makes low ground inland water (half a square
   kilometre of Coronado on 8 m cells; on the coarse grids the Salton Sea,
   Laguna Salada, the Sacramento delta and Death Valley, all below sea level,
   had been drawn as sea), so band 0 is the sea's: water that reaches the
   edge of a grid's cover, where the sea runs on past it. San Diego Bay
   leaves the 8 m grid at its edge and the Gulf of California the 400 m
   grid's, so both stay water.

   | vertex, grid | before | after |
   |---|---|---|
   | breaks, 8 m (zoom 11+) | -13 / -22 / -34 m | +22 / +7 / -5 m |
   | breaks, 32 m (zoom 9-10) | +3 / -35 / -43 m | +32 / -7 / -5 m |
   | Point Loma tangents, 32 m (zoom 9+) | -57 / -58 / -67 m | -25 / -25 / -18 m |
   | Baja tangent, 90 m (chart error, item 17) | +301 m | +346 m; imaged tangent +4 m |
   | South Coronado tip, 90 m | +87 m | +122 m |

   At the opening view (~26 m a pixel on a 390 px phone) every break and
   Point Loma vertex is now within a pixel of the coast; at zoom 14, 1-6 px.
   South Coronado's edge line, which cut 0.02-0.05 degrees into GMRT's
   drawn island, now passes 0.03-0.06 degrees outside it, both within GMRT's
   90 m cells. The seabed is 2.22 MB (was 2.21). No forecast number moved:
   the chain reads the grids, never the drawing. `seabedvector.check` fails
   when NOAA's datums change, as when a grid is fetched again.

## The fill

   **The map's FILL, LIVE only** (owner's requests and calls, 2026-11-10,
   mocked in mocks/swell_fill and shipped the same day): pick a train on the
   map and a play button and a timeline appear along its foot, the
   timeline at its start at once; play and the train comes in along its
   rays -- every row of the break's table that clears every edge, drawn
   where it was TRACED (`raytrace.trace(record=True)`, `--paths-only` ->
   `data/nearshore/<break>_paths.json`, each ray checked against its table
   row; 2.9 MB, ~0.8 MB compressed, a break's fetched the first time a train
   is picked there), from as far out as the physics supports it -- where
   the grids the rays are traced over end, or nearer where land or water
   shallower than L0/2 lies across its straight deep-water leg
   (`raytrace.deep_leg`; owner's request, 2026-11-15) -- straight to its
   exit, over the seabed to 5 m, then along the break's normal to the
   break; long periods first, minutes after the swell passed 46232, the
   clock's 0 (`leg_table`'s arithmetic: the plane-wave offset from the
   line through 46232 square to the ray's heading, where the chain takes
   the buoy's spectrum to hold). Until 2026-11-15 a ray started on that
   line, or at its exit where the exit lay up-swell of it: 20 / 21 / 28%
   of rays (N / C / S) started past 46232 and the rest on its line (owner's
   report; south swell 150-195 degrees, periods of 25 s and more, and rays
   bending round Point Loma the former). Measured (BRIEFING §52) with
   `trace(record=True)`: rays stop turning by more than 0.1 degree at about
   L0/2 (14 m at 4 s, 147 m at 13 s), but most rays at 14 s and more at
   North, and from about 10 s at Center and South, are still turning where
   they leave the `outer` grid, so the traced physics ends at that grid's
   edge; the straight leg back from each exit stays over water deeper than
   L0/2 to that edge for 89-95% of rays. Now 93 / 98 / 99% start before 0,
   a median 44-50 km from the break (61 at most), and the fill's view opens
   about a zoom step wider; no arrival moved. Each ray's share of the train
   is `forecast/fill.py`'s
   (`data/live/fill.json`, its own step after `forecast.now`, NEVER a key
   in now.json: owner's question, the per-ray energy would ride every
   refresh): the chain's carry re-run for now.json's own spectrum, credited
   as `carry` credits it -- diffraction on the nearest clearing ray of the
   same period -- and a row whose rays do not rebuild the chain's 5 m height
   to 2 mm is left out with a note, never drawn wrong; the page plays a
   fill only when fill.json and now.json name the same spectrum. Brighter
   for more energy, the light adding where rays crowd; the caption the
   periods and height in so far, then "98% in by +N min" and the row's own
   height. **Not a wave field**: no crest is drawn, nothing observes it,
   and swell wrapping round a headland tip is where the ray method is
   weakest (§31, §45). The first version, on the window DRAWING, was
   dropped by the owner the same day: a view from the break can only draw
   swell bending round Point Loma's tip as energy crossing its shadow.

## The page must not move under the reader

   **The page jumped on a Units change and on a refresh** (owner's report,
   2026-11-15). Measured at 390 x 664 with scroll anchoring off, as WebKit
   has none: the cards are rewritten whole, and the map's plates came back
   only on its MutationObserver, after `restorePicks` and the rest had laid
   the page out without them, 176 px shorter, so a reader near the foot was
   clamped up 176 px (533 -> 357). Chromium's anchoring hid it. Now every
   rewrite calls `replate()` (the face IIFE's `attach`) before anything
   reads the layout. And a face was made as a drawing, so a page opening on
   the map slid its plate from the drawing's height to the map's (230 ->
   328 px) on every load; a face is now made in the view this device keeps.
   A refresh in Chromium still lands at the top: the cards arrive after its
   scroll restoration gives up, which is the page's, not the map's.

   **A pick's headings were cut off, then the drawing dropped** (owner's
   report, 2026-11-15). The plate is trimmed to the drawing's ink with
   getBBox, which skips hidden elements, and a pick's headings (`text.deg`,
   at r + 12) are hidden until picked: tapping North's island groups put
   "187°"-"201°" up to 7 px over the plate's top at 390 (9 px at 430), and
   the next `resize` -- iOS Safari's toolbar on scroll -- re-trimmed round
   them, the plate 171 -> 189 px and the drawing 18 px lower. The trim now
   takes every heading's baseline less its font size, shown or not: no cut
   at 320-430 on any break or pick, the plate one height through pick,
   resize and unpick, taller at rest (North 171 -> 193 px at 390).

   **Another break's dot is its tab** (owner's request, 2026-11-15): a tap
   on another break's dot on the map calls `selectSwellTab`, as the tab
   does, before any other hit; a finger reaches 14 px round the 3.5 px dot,
   a mouse 8 px and gets a pointer over it. The break's own dot does
   nothing new.

   **A switch to another break's map moves as the mock's one map does**
   (owner's pick, 2026-11-15, 400 ms ease in the "Seabed Map Themes" mock's
   Switching break option). The map a tab switch or a dot tap shows is set,
   in the click itself (`preTurn`), to the view the last tab's map was
   showing (that break's opening view if it showed the drawing), sized then
   too -- hidden, it had kept a stale 400 x 300 canvas until a task later --
   and eased over `TURN_MS` to its own opening view (`viewFor`), centre,
   zoom and bearing together. The first build turned the map round its
   break alone, with no pan, and the owner saw it move differently from the
   mock. The clock starts after the shown map's first frame: a hidden
   canvas's first frame is the heavy one (173 ms in headless software GL
   with no ease at all), and an ease started before it skipped its first
   third. Measured against the mock, South to North: the same path, the old
   break sliding off as the new one arrives at its place, ending exactly on
   North's opening view. Never under reduced motion, never on the wide
   layout, where no tab hides a break.

## Map layers

   **A layer button and two other looks** (owner's picks, 2026-11-16, group
   3, items 2 and 11, mocked in "Seabed Map Themes"). A button top right, 4 px
   inside the hairline and dressed as every map control is (the source line
   now stops 40 px from the right, left of it), opens a list: **Windows**,
   **Shadows**, **Window edges**, then **Grayscale** and **Lines only**. One
   choice for every map, this device's (`nado-waves.map-layers`, through
   `stored` / `store`), as the drawing-or-map choice is; a tap anywhere else,
   or Escape, shuts the list, and nothing in the button or the list reaches
   the map.

   - **Windows and Shadows** each switch their tint, separately (owner's
     request). Switched off, a window or shadow is still there to tap and
     still lights when picked: the pick is the reader's own.
   - **Window edges** switch the edge lines, their halo, the dashed lines
     past each vertex and the vertices with them.
   - **The looks, one at a time**: turning one on turns the other off;
     neither is the colour themes (`MAP_THEMES`), the default. GRAYSCALE
     (`MAP_LOOKS.grey`) is the colour themes with their colour taken out,
     every colour at its own OKLab lightness (a = b = 0, the page's own
     conversion; a test recomputes each), but the light page's rays: the
     orange's own lightness is a mid grey lost on the pale sea there, so they
     are near-black, #25292c. On the light page land and shallow water come
     out nearly the same grey (#e1e1e1, #e7e7e7), the shoreline between
     them. LINES ONLY (`MAP_LOOKS.lines`) is the mock's "Lines only" pair as
     the mock drew it (its halo at 0.35, the shipped rays).
   - **The headings carry a black hairline** (owner's request, 2026-11-23,
     after the mock gained text controls): the NDBC tags and the two
     outermost edges' degrees, in every theme and look (`outline`,
     `outlineColor`, the mock's keys), stroked `HEADING_OUTLINE_PX` (1.5 px)
     wide under the fill so about 0.75 px shows round each letter -- CSS
     `paint-order` on the tags, `strokeText` before `fillText` on the
     canvas. The attribution has none, and the halo still glows under both.
   - **The window edges run to the map's edge** (item 2): each dashed line
     runs `EDGE_KM` (1,500 km) from the break along its bearing, a point
     every ~20 km so it stays the great circle it is. Before, it stopped at
     1.6 times the break's farthest edge vertex, ~40-50 km, past the edge at
     the opening view but part way across the map zoomed out. The farthest
     ground any view shows -- the widest zoom `limits` allows, panned as far
     as `pull` lets it -- is 1,028 km (North, a 260 px map), 680-780 km at
     390 px; a test recomputes it. The window and shadow TINTS were mocked
     running to the edge too and stay as they were, at 1.6 times (owner's
     pick).

   **Mocked and dropped** (same day): masking the tints over land. MapLibre
   cannot cut one layer by another, and each grid's land is only its
   outline under its sea (band -1 under band 0), so the mock computed each
   grid's land (shapely, +164 KB on the seabed's 2.22 MB, 4-17% a grid) and
   drew each grid, then the tints, then that grid's land; the owner saw it
   fail in places and at some zooms. Rays to the map's edge were dropped
   before the mock (a ray past `raytrace.deep_leg`'s start is not traced),
   and so were Contours and Origins in the layer list (origins:
   origin.md's last section).

## The map, the only view

   **The drawing left the card for the map** (owner's request and calls,
   2026-11-16, group 3, item 20). The drawing / map switch is gone, and with
   it the choice it kept (`nado-waves.swell-view`, no longer read; left on
   devices that have it, since localStorage is pinned to the page's two
   helpers, `stored` / `store`, and a third to delete it would be a
   page-wide helper for one stale key). What "Map layers" above calls "as
   the drawing-or-map choice is" now means as the choice WAS.

   - **The drawing stays, unseen, as the map's source**: on the plate under
     the map, at opacity 0 with no pointer events -- never `visibility` or
     `display`, which would take it out of the Tab order and the spoken page.
     `readSvg`, `data-geo`, `togglePick`, the row picks and the observer that
     redraws the map all read it as before. It is also the map's keyboard and
     screen-reader way in (owner's call): its windows, shadows and arrows
     keep their place in the Tab order and their labels, Enter picks one
     (`wireDrawings`), and the part in focus lights on the map as a mouse
     over the drawing lit it there (`focusin` / `focusout` in the map's
     module). Checked at 390 and 1300 px: focus on North's first window
     lights `w0` on the map and puts its caption in the tray; Enter keeps it.
   - **Shown only where the map cannot be drawn.** `GL` asks for WebGL as
     MapLibre 4.7.1 does (WebGL 2, else 1; a test reads both in the bundled
     library) and lets the probe's context go. Without it every card opens
     on the drawing at the drawing's size, and no map file is fetched. The
     library or map.json failing to load, or the map failing to start, falls
     back the same way for the rest of the visit (`noMap`), the plate sliding
     from the map's height to the drawing's as a fold does. Before this, a
     browser without WebGL that kept the map got an EMPTY 328 px plate at
     390 px, MapLibre's "Failed to initialize WebGL" uncaught (reproduced in
     Chromium with `--disable-3d-apis`). Now, at 390 px: the map 328 px;
     without WebGL the drawing 188 px with nothing of the map fetched;
     the library blocked, or map.json, the drawing 188 px; no page error.
   - **A stale reading's arrow** (owner's call): the drawing greys its
     leading arrow when 46232's reading is past `STALE_HOURS`; the map's
     arrows never did, and a grey for them would be a new design to mock.
     docs.html's countdown section no longer names the arrow; the heights
     and trains still grey.
   - **docs.html keeps the drawing working, as the project's history**
     ("The window drawing", same id): how the project worked the beach out,
     window, shadow, then the energy and its direction, in the owner's
     approved wording, over a working drawing of the latest "LIVE" reading
     (now.json, a North / Center / South switch, units both). Its code is the
     forecast page's own, 23 pieces copied line for line, and its `.aperture`
     rules likewise; `tests/test_docs.py` pins both, so it is exactly the
     drawing the card's map reads. Its own wiring (tap, hover, Enter) is
     docs.html's, as the card's was the conditions strip's. The page's
     geometry facts are read from `span[data-geo]`, so the drawing's own
     `data-geo` is never overwritten. The other docs.html lines that put the
     drawing on the card now put the map there.

## The roses' seabed

   **The Buoys tab draws this seabed too** (owner's picks, 2026-11-17,
   group 5, item 9): behind each buoy's rose, as a still image from one
   offscreen map in the colour theme (`roseSea`, in this module, reusing
   `ready`, `kept`'s files, `MAP_THEMES` and `bandColours`). It adds a third
   fill layer, multisampled with no outline as the swell map's are (a test
   counts them), and never a live map. buoys.md "The seabed behind the rose,
   and the bar".
