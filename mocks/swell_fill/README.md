# Swell card: a picked train filling in through the windows (MOCK)

Owner's request (2026-11-10): animate a break tab's window drawing to show how
a swell fills in through the windows from its direction and period. Owner's
choices the same day: **a picked train, LIVE only, the drawing first (option
A); a plan view on the satellite map (option B) once the map ships.**
**Nothing here is published**: `forecast.publish` ships `app/` only, and
`app/forecast.html` is unchanged.

Build (from a checkout of the delivery repository, as the swell-map mock is):

    python -m mocks.swell_fill.build ../nado-waves-forecast mocks/swell_fill/swell_fill_mock.html

`fill.py` alone prints what it rebuilt and checks it:
`python -m mocks.swell_fill.fill ../nado-waves-forecast/now.json`. The file is
the published page of its build time with its data built in, so its cards age
from then.

## What it does

- On LIVE, pick a train (its row, or its arrow on the drawing): a play button
  appears in the drawing's top-right corner. A pick on the Forecast tab, a
  window, a shadow or nothing shows no button. A swell shown as two rows
  (`G…`) fills as one.
- Play: the train's arrows and caption give way to the fill, and the line under
  the drawing is a clock, **minutes after the same wave group passed NDBC
  46232**, with a scrubber (drag it, or arrow keys) and the time the fill ends.
  The button pauses, and at the end replays. Any other pick ends the fill.
- **Each lane is one degree** the train's energy left deep water FROM, darker
  for more energy. A lane whose degree the straight-line windows close stops at
  the rim, in the shadows' grey. A lane that reaches 5 m runs in to the break,
  turning on the way to the heading its rays arrive from in 5 m of water, and
  darkens or fades from the energy the buoy holds there to what reached 5 m.
  The lanes stop short of the break, as the drawing's arrows do; at the end the
  train's 5 m arrowhead shows there.
- **Each period reaches the break at its own minute**, so long periods arrive
  first and the shorter ones fill in behind them. The line reads the periods
  more than half in and the height in so far: "+38 min · 18.2–14.3 s in · 4.1
  ft (1.25 m)". At the end it gives the minute by which 98% of the train's 5 m
  energy is in, and the row's own height: "98% in by +46 min · 5.5 ft (1.67 m)".
- Reduced motion: play shows the filled drawing at once; the scrubber still
  reads any minute.
- Phone, tablet, stack and console layouts; light and dark. Checked in
  Chromium at 360, 390 and 1300 px with no console errors. Not checked in
  WebKit.

## Where every number comes from

`fill.py` re-runs the LIVE chain (`nearshore.buoy_split`, `nearshore.carry`) on
the archived 46232 spectrum at that `now.json`'s `observed_utc`, then reads
back what it did to each listed train, ray by ray, as `carry` credits it:

| drawn | from |
|---|---|
| a lane's energy at the rim | the train's own bins and arc at 46232 (maximum entropy), only the buoy swell(s) the row is (`Train.buoy` / `buoys`) |
| closed at the rim | outside now.json's own `swell_window` (the drawing's straight-line windows) |
| what reaches 5 m, per degree | each ray's `diff_off_from`, diffraction and bottom friction in, shoaling divided out so it compares with the buoy end |
| the turn | the energy-weighted 5 m heading of the rays from that degree |
| the minute a period arrives | `<break>_leg.csv`'s `from_buoy_min` (`raytrace.leg_table`), interpolated over heading within its period; outside 8–22 s, the nearest tabled period scaled by deep-water group speed |

Checks that stop the build: each row's period and heading must equal
now.json's, and its 5 m height rebuilt from the rays must equal the chain's to
2 mm. For 2026-11-10 07Z every break's windows, refraction, diffraction,
friction and shoaled heights equal the calculation table's to the millimetre.

## Drawn, not computed

- **The rim-to-break leg is drawn**, 15 minutes of the clock for every lane.
  The drawing has no distances (Point Loma is 5.7 km out, the islands 31 km),
  so only the minute each period REACHES 5 m is the chain's. Nothing shows
  where along a bearing the land is.
- **The turn's shape is drawn**: the lane leaves straight and bends late,
  ending on its 5 m heading. BRIEFING §45 puts the turning on the shelf 3–8 km
  out and finds neighbouring rays crossing on 37–59% of pairs. A lane is a
  degree's average, which smooths that out.
- **No wave crests, ever.** The chain traces rays backward from 5 m and
  applies a diffraction factor to each; it never computes a wave field
  (BRIEFING §31).
- "In so far" is the row's height scaled by the share of its 5 m energy in, as
  `summarise` scales every train by one factor to the breaking height.

## What it shows that the drawing did not

At North on 2026-11-10 07Z, about a third of what reaches 5 m is credited to
offshore headings past Point Loma's straight-line edge (242°): lanes from
245–285° run in across the Point Loma shadow. This is the chain's own
bookkeeping (the calculation table's refraction row, 0.73 → 1.28 m, is the
same thing). Which part is refraction round the tip and which is diffraction
credited to a scrambled neighbour's heading is not measured here.

## Not done, and open

- Option B, the plan view with real ray paths on the satellite map, waits for
  the map to ship and for `raytrace.py` to save the paths.
- To ship: the read-back belongs in `now.py` (a `fill` key per train in
  now.json, ~90 KB a break at full resolution; coarser lanes would shrink it),
  not a mock's precompute.
