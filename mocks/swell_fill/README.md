# Swell card's map: a picked train filling in along its rays (MOCK)

Owner's request (2026-11-10): animate how a swell fills in through the
windows from its direction and period. Owner's choices the same day: a picked
train, LIVE only. A first version on the window drawing (option A) was
confusing: the drawing is a view from the break, so swell that bends round
Point Loma's tip could only be drawn crossing its shadow. The owner moved it
to the map, at true scale, with the real ray paths (option B). Option A is
gone from this folder, and from the build. **Nothing here is published**:
`forecast.publish` ships `app/` only, and `app/forecast.html` is unchanged.

Build, from checkouts of the delivery repository and Leaflet (as the
swell-map mock is built):

    npm install leaflet@1.9.4 leaflet-rotate@0.2.8
    python -m mocks.swell_fill.rays ../nado-waves-forecast/now.json --json > rays.json   # ~4 min
    python -m mocks.swell_fill.build ../nado-waves-forecast node_modules/leaflet/dist \
        node_modules/leaflet-rotate/dist mocks/swell_fill/swell_fill_mock.html --rays rays.json

`python -m mocks.swell_fill.rays NOW.json` alone runs every check and prints
what it built. The file is the published page of its build time with its data
built in, so its cards age from then. It opens on the map on a device that has
never chosen between map and drawing.

## What it does

- On LIVE, on the map, pick a train (its row, or its arrow): a play button and
  a timeline appear along the map's foot, left of return, + and -. A pick on
  the Forecast tab, a window, a shadow or nothing shows neither. A swell shown
  as two rows (`G…`) fills as one.
- Play: the map turns to the seabed and frames every ray the train comes in
  on, from where it leaves deep water to the break (shore normal still up).
  The train's arrows give way to its rays. The clock in the timeline is
  **minutes after the same wave group passed NDBC 46232**; the caption under
  the map reads the periods more than half in and the height so far, "+38 min
  · 16.7–14.3 s in · 5.1 ft (1.55 m)". At the end it gives the minute by which
  98% of the train's 5 m energy is in, the row's own height, and the train's
  5 m arrowhead comes back. Drag the timeline, or use the arrow keys; pan and
  zoom as ever (into the tip, where the rays turn most). Any other pick ends it.
- **Each ray is one row of the break's transfer table**, drawn where it really
  went: straight in from 15 km seaward of where it leaves deep water, then
  bent over the seabed to 5 m of water off the break. Brighter for more of the
  train's energy; where rays crowd, the light adds up, as the energy does.
  Each period moves at its own group speed, so long periods come in first.
- The seabed is drawn from the same grids the rays were traced over (USGS
  CoNED 2016 and GMRT, depth below mean sea level): greys, lighter for
  shallower, contours at 5, 10, 20, 50, 100, 200 and 500 m, land lighter
  still. A finer picture covers the breaks and the Point Loma tip. It also
  stands in for the satellite imagery wherever the imagery cannot load (the
  artifact's host blocks tile servers).
- Reduced motion: play shows the filled map at once; the timeline still reads
  any minute.

## Where every number comes from

`rays.py` re-runs the LIVE chain (`nearshore.buoy_split`, `nearshore.carry`) on
the archived 46232 spectrum at that `now.json`'s `observed_utc`, and for each
period bin a listed train holds re-traces all 360 of the break's rays with
`trace_paths`: `raytrace.trace`'s own loop, recording each step.

| drawn | from |
|---|---|
| a ray's path | `trace_paths`, paths simplified to 12 m (Douglas-Peucker) |
| its brightness | the train's energy at 5 m on that ray, as `carry` credits it: the row's bins, its arc, its buoy swell(s) |
| a ray the land stops | nothing hard; what diffraction gives it is drawn on the clearing ray of the same period nearest the heading the table credits it to (raytrace's own reading of where diffracted energy comes round an edge from) |
| when it arrives | the plane-wave offset from 46232 to the ray's exit, then ∫ ds / cg along it: `raytrace.leg_table`'s arithmetic, for every period |
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
None of it is observed: the beach log is what would say.

## What it shows

On 2026-11-10 07Z (a W swell, 15.4 s from 241–276° at the three breaks), most
of what reaches Center and South leaves deep water west and south-west of
Point Loma, 19–26 km out, and bends round the tip over its shelf: rays from
offshore headings the drawing shades as Point Loma's shadow, on the water the
whole way.

## Not done, and open

- Phone and tablet layouts only, as the map is: the stack and console layouts
  draw the breaks as columns.
- To ship: the paths belong in `forecast/raytrace.py` (`trace` recording them,
  into `data/nearshore/`), and each train's per-ray energy in `now.py`; ~5,000
  points a break for one train at this simplification. The map must ship first.
- Esri's terms are still unchecked (see `mocks/swell_map/README.md`).
