# Swell card's map: a picked train filling in along its rays (MOCK)

Owner's request (2026-11-10): animate how a swell fills in through the
windows from its direction and period. Owner's choices the same day: a picked
train, LIVE only. A first version on the window drawing (option A) was
confusing: the drawing is a view from the break, so swell that bends round
Point Loma's tip could only be drawn crossing its shadow. The owner moved it
to the map, at true scale, with the real ray paths (option B), and then made
the seabed the map's base in place of the satellite imagery (a satellite
option may come back). **Nothing in this folder is published**:
`forecast.publish` ships `app/` only. The one change this work makes to the
live page is separate (owner's call, 2026-11-10): the window drawing no
longer shows the 5 m heading, its arrowhead and caption line; each train's
`near_from_deg` stays in the payload, and docs.html's swell-bend table stays.

Build, from checkouts of the delivery repository and Leaflet:

    npm install leaflet@1.9.4 leaflet-rotate@0.2.8
    python -m mocks.swell_fill.rays ../nado-waves-forecast/now.json --json > rays.json   # ~4 min
    python -m mocks.swell_fill.build ../nado-waves-forecast node_modules/leaflet/dist \
        node_modules/leaflet-rotate/dist mocks/swell_fill/swell_fill_mock.html --rays rays.json

`python -m mocks.swell_fill.rays NOW.json` alone runs every check and prints
what it built. The page is this branch's `app/forecast.html`, wrapped as
`forecast.publish` wraps it, with the delivery repository's data of the build
time built in, so its cards age from then. It opens on the map on a device that has
never chosen between map and drawing.

## What it does

- **The map is the seabed**: near the breaks, the grids the rays are traced
  over (USGS CoNED 2016 and GMRT, depth below mean sea level), a finer picture
  over the breaks and the Point Loma tip; past them, for context only,
  `collector.bathymetry`'s new `context` grid (GMRT, 400 m, round the breaks
  and the three buoys with 160 km to spare), shaded the same way. Greys,
  lighter for shallower, contours at 5, 10, 20, 50, 100, 200, 500, 1,000 and
  2,000 m, land lighter still; each inner picture fades out at its edges.
- **The context grid is not fetched yet.** gmrt.org is denied from a session,
  so `.github/workflows/bathymetry-context.yml` fetches it on Actions when
  this work is merged (it runs on a push to master that changes the collector
  or itself), into `data/bathymetry/context.{npz,json}`. No chain reads it:
  `raytrace` loads its three grids by name, and a test pins it. Until it
  lands, the inner pictures fade to the map's deep grey; rebuild the mock
  afterwards and `context.py` picks it up.
- **NDBC 46086 and 46047 are marked as 46232 is**, at NDBC's fetched
  coordinates (`forecast.siting.load_coordinates`).
- **It zooms out to just past Tanner Bank and no further**: at the widest, a
  point 25 km past NDBC 46047 is in view with the break where the map keeps
  it, and the view's middle cannot be panned further than that from the
  break. The + and - buttons stop at the limits (they used to walk the centre
  off the map past them).
- **The view is kept across the page's redraws.** The page rebuilds its cards
  every minute on LIVE, and the map was rebuilt with them, back at its
  opening view: that was the jump after a fill. The view and the fill are now
  kept by break.
- On LIVE, on the map, pick a train (its row, or its arrow): the play button
  and the timeline appear along the map's foot, left of return, + and -, the
  timeline at its start. A pick on the Forecast tab, a window, a shadow or
  nothing shows neither. A swell shown as two rows (`G…`) fills as one.
- Play (or drag the timeline): the map frames every ray the train comes in on,
  the train's arrows give way to the rays, and the timeline is a clock,
  **minutes after the same wave group passed NDBC 46232**. The replay symbol
  is the week card's "back to" clock without its arms, at the map buttons'
  line (16 px at 1.5). The caption under the map reads the periods more than half in and
  the height so far, "+38 min · 16.7–14.3 s in · 5.1 ft (1.55 m)"; at the end,
  the minute by which 98% of the train's energy is in and the row's own
  height. The button pauses, and at the end replays. Any other pick ends it.
- **Each ray is one row of the break's transfer table**, drawn where it went:
  straight in from the line through 46232 square to its heading, then bent
  over the seabed to 5 m of water, then on to the break. Brighter for more of
  the train's energy; where rays crowd, the light adds up, as the energy does.
  Each period moves at its own group speed, so long periods come in first.
- Reduced motion: play shows the filled map at once; the timeline still reads
  any minute.

## Where the rays start, and why

A ray is traced BACKWARD from 5 m of water off the break until the water is
one deep-water wavelength deep (L0 = gT²/2π: 370 m at 15.4 s, 100 m at 8 s).
Past that depth the seabed no longer bends it, so the rest of its way in is a
straight line, and that is where the trace stops: on the shelf's edge, 19–26
km out, inside 46232's distance for some rays and outside it for others.

The chain takes the spectrum 46232 measures to hold all along the line
through the buoy square to the swell's travel (BRIEFING §29: "the buoy
spectrum is assumed to hold across the offshore boundary"). So each ray is
drawn from that line, where the clock reads 0, straight to its exit, then
along its traced path. A ray that leaves deep water up-swell of that line
starts at its exit, before 0; the clock opens where 2% of the energy has
started (here −31 min), and a ray starting earlier opens part-way in. The
first version drew 15 km of straight line past each exit instead, which
meant nothing.

## Where every number comes from

| drawn | from |
|---|---|
| a ray's path | `trace_paths`, `raytrace.trace`'s loop recording each step, simplified to 12 m (Douglas-Peucker) |
| from 46232's line to the exit | straight, along the ray's offshore heading: the plane-wave offset `raytrace.leg_table` uses |
| from 5 m to the break | straight along the break's normal, the line `surfzone` carries the sea along, at the shallow-water speed of 2.5 m (drawn: the surf zone has no rays) |
| its brightness | the train's energy at 5 m on that ray, as `carry` credits it: the row's bins, its arc, its buoy swell(s) |
| a ray the land stops | nothing hard; what diffraction gives it is drawn on the clearing ray of the same period nearest the heading the table credits it to (raytrace's own reading of where diffracted energy comes round an edge from) |
| when it arrives | the plane-wave offset from 46232 to the exit, then ∫ ds / cg along the path |
| "in so far" | each row's height scaled by the share of its drawn 5 m energy in, as `summarise` scales every train by one factor to the breaking height |

Checks that stop the build: every traced ray's status and offshore heading
equal `raytrace.trace`'s, every clearing ray's offshore heading equals its
table row's, and each row's rays sum to the chain's own 5 m height to 2 mm.
For 2026-11-10 07Z all pass on all three breaks; 98% of each row's 5 m energy
is on the rays drawn (rays under 0.02% each are left out).

## Not a wave field

The chain traces rays backward from 5 m and applies a diffraction factor to
each; it never computes waves. Nothing here is a crest. Where rays cross
(BRIEFING §45: 37–59% of neighbouring pairs on the shelf) ray theory is at
its limit, and swell wrapping round a headland tip is where refraction and
diffraction, combined here rather than solved together (§31), are weakest.
None of it is observed: the beach log is what would say. The outer seabed is
context only: nothing is traced over it.

## Not done, and open

- Phone and tablet layouts only, as the map is: the stack and console layouts
  draw the breaks as columns.
- `mocks/swell_map` itself still opens on Esri's imagery; only this mock's
  map is the seabed (two hooks in `swellmap.js`: `__SWELLMAP_BASE__` and
  `__SWELLMAP_ATTR__`). A satellite option may come back.
- To ship: the paths belong in `forecast/raytrace.py` (`trace` recording them,
  into `data/nearshore/`), each train's per-ray energy in `now.py`, and the
  seabed pictures in a precompute. The map must ship first.
