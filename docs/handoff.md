_Read at the start of a session that picks up open work, and update it before stopping._

# Handoff

## Where things are

- CLAUDE.md holds the lasting rules; `docs/design/*.md` holds each area's full
  design history, moved there verbatim on 2026-11-14.
- BRIEFING.md is in the private `ptrrdrck/nado-waves-notes`: attach it to the
  session (it is 4,498 lines; read only the sections an item names).

## Backlog

Re-worded and confirmed by the owner on 2026-11-15, grouped by area into one
session per group. Numbers are the items' own and do not change as they close.

### Group 1: map behaviour -- done (PR #223)

Items 1, 5, 6 and 10 shipped; see map.md's last sections and app_surface.md's
"Refresh and redraw". The owner checked the jump fixes on an iPhone.

### Group 2: geometry and ray diagnosis -- done (branch claude/geometry-ray-diagnosis-2bmzpe)

Items 4 and 3 shipped with the `trace` fix that lets the full table build
run again; BRIEFING §52, geometry.md's islands section, chain.md's island
sensitivity, map.md's fill. South Coronado's south-east tip is now Esri
imagery (the ENC rounds it off), and the fill's rays start where the traced
seabed ends. Its two islands items, 13 and 14, are now in group 2d.

### Group 2b: the map's coastline against the geometry's -- built (PR #226)

Owner's report, 2026-11-15: on the LIVE map the edge vertices sat off the
drawn coast. Measured per point and per grid, each vertex checked against
Esri imagery with CoNED lidar at 2 m, Copernicus GLO-30 and GMRT as
controls (BRIEFING §53; evidence images in the notes repository,
`evidence/2026-11-15-group-2b/`). Three causes: the datum (breaks), the
smoothing (Point Loma), the chart (Baja). Items 15 and 16 shipped; map.md
"The coast is the chart's", geometry.md's Point Loma, south window and
islands sections.

15. **The map's coast at the chart's datum, mean high water** -- done.
    NOAA's datums fetched by `collector.datums` (0.623 m above MSL); breaks
    -13/-22/-34 -> +22/+7/-5 m on 8 m cells.
16. **The coast contoured unsmoothed, the sea's water only** -- done.
    Point Loma -57/-58/-67 -> -25/-25/-18 m on 32 m cells; low ground
    inland (and the Salton Sea, Laguna Salada, Death Valley) no longer sea.
    Open: `app/docs.html`'s map paragraph still says every line is drawn
    from depths smoothed over a cell; the owner was asked for the wording.

### Group 2c: the Baja tangent -- built (PR on branch claude/jolly-curie-t44nks)

17. **The Baja tangent from imagery** -- done (BRIEFING §54; geometry.md
    "The south window", chain.md "Baja's edge in the rays"). Both ends on
    Esri World Imagery: `a` 32.46914, -117.12028 (the headland; GLO-30 and
    GMRT within 0.01-0.09 degrees), `b` 32.38339, -117.08238 (the coast at
    the old `b`'s latitude, so Breakers keeps its sector). Low edges
    164.6 / 166.4 / 168.5 -> 163.8 / 165.6 / 167.5, Breakers 161.4 -> 160.7,
    Gator 170.1 -> 169.1; window energy +1.07% North, +1.17% Gator, 0 at the
    rest. Tables rebuilt: 1.2-1.5% of rows, 5 m height a median within
    0.03%, worst hour -1.8%; legs and fill paths unchanged. The "standing on"
    line says "Esri World Imagery for the Baja coast"; spots.json's
    UNTESTED note closed.

### Group 2d: the islands, and the straight leg (strongest setting; next)

All three move the islands' see-through disc, item 14's unstable input, so
one session.

18. **North Coronado's outline** sits ~100-200 m north-west of the island
    on imagery (edges -0.22 to -0.38 degrees). GLO-30 agrees at `b`, not at
    `a`, where a rocky spur runs past the chart's end at an imagery seam
    (2023/2021). A §52-style look at both ends before any change; a move
    shifts the main west window's low edge and the channel's high edge.
13. **The seabed grids are missing islands** (owner: its own session). GMRT's
    90 m `outer` grid has only South Coronado as land (Middle reads 1.4 m
    deep, North Coronado at least 22 m); the 400 m `context` grid, the only
    seabed the map draws below zoom 8, has none. Rays use `outer`. Options:
    burn the imaged islands (GLO-30 as the registration control) into the
    grids for the map and the rays, which moves the tables (those rays then
    land and go through the disc); or a map-only overlay, which would show
    land the rays do not see. First measure how many table rays cross
    Middle and North Coronado today.
14. **A ray re-traced through an island is unstable** (chain.md). One ray
    through the see-through disc carries up to 33-63% of a break's 5 m energy
    on some hours, and a 50 m change of the disc's pad moves single hours by
    up to -29% / +34%. Measure what a smoother treatment (no step-edged disc;
    bounded single-ray gains; or the islands as land with diffraction only)
    does before choosing one.

19. **The straight leg ignores `continues`** (found in group 2c; chain.md
    "Baja's edge in the rays"). `raytrace.straight_line_blocker` blocks only
    inside the span of a blocker's `a`, `b` and outline, so a short-period
    ray leaving deep water near the beach heading into the Mexican coast
    south of `b` counts as clear. Upper bound on what it carries: the 5 m
    height a median -0.002%, at worst -3.5% (North, 22 Oct 00Z). It needs
    the table rebuild group 2d makes anyway; measure a fix that honours
    `continues` (the real coast, not a half-plane) before choosing one.

### Group 3: map layers (mock first)

Area: `docs/design/map.md`, `origin.md`. After groups 2c and 2d: extending
shadows to the map's edge also extends any islands or Baja error.

2. **Extend the window edges (dashed lines) to the map's edges when zoomed
   out**; add toggles to the map colours mock ("Seabed Map Themes") for rays /
   windows / shadows extending to the edge, and one to mask the shadow over
   land.
11. **A map layer control**, built from item 2's toggles.
12. **Origins as a map layer.** Storms are 500–10,000 mi out; the map zooms
    only to just past Tanner Bank and the seabed reaches ~1,200 km. Mock a
    bearing mark at the map's edge against a wider zoom. Origins are LIVE
    only; the map is on both tabs.

### Group 4: Wind and Tide cards

Area: `docs/design/tide_wind_sun.md`, `app_surface.md`.

7. **Space between the tide height and its rising/falling rate** (`tideRate`'s
   `.rate`), tide card only. Routine: a lighter model is enough.
8. **Wind symbol**: a rose whose top heading is the break's facing direction,
   its four "cardinals" the 90° headings from it, the centre filled side to
   side with a classic wind arrow pointing where the wind blows TOWARD. Mock
   first; settle per break vs the picked break (wide layouts pick none) and
   whether length shows speed.

### Group 5: Buoys tab (after group 3)

Area: `docs/design/buoys.md`, `map.md`.

9. **Map imagery behind the buoy rose, centred on the buoy.** Mock first:
   seabed vectors or satellite, and the scale.

### Carryover prompts

Each assumes a fresh session; add "Confirm each item before building. PR,
wait for Tests, don't merge." to each.

- Group 2: "Repo ptrrdrck/nado-waves; attach ptrrdrck/nado-waves-notes.
  Group 2 of docs/handoff.md (items 4 and 3), geometry and ray diagnosis.
  Read the design docs and BRIEFING sections it names first. Report the
  cause and the truth before changing anything."
- Group 2d: "Repo ptrrdrck/nado-waves; attach ptrrdrck/nado-waves-notes
  for BRIEFING.md. Group 2d of docs/handoff.md (items 18, 13, 14, 19), the
  islands (strongest setting). Read geometry.md's islands section, chain.md
  ('A ray re-traced through an island...'), map.md, forecast/raytrace.py's
  islands code and BRIEFING §10, §29, §31, §52, §53 first. Look at North
  Coronado's ends as §52 did, count the table rays that cross Middle and
  North Coronado, and measure item 14's smoother treatments and item 19's
  straight-leg fix (chain.md, "Baja's edge in the rays"; BRIEFING §54)
  before choosing; report before changing anything."
- Group 3: "Repo ptrrdrck/nado-waves; attach ptrrdrck/nado-waves-notes.
  Group 3 of docs/handoff.md (items 2, 11, 12), map layers. Read map.md and
  origin.md first; mock before building."
- Group 4: "Repo ptrrdrck/nado-waves; attach ptrrdrck/nado-waves-notes.
  Group 4 of docs/handoff.md (items 7, 8), Wind and Tide cards. Read
  tide_wind_sun.md and app_surface.md first; mock item 8 before building."
- Group 5: "Repo ptrrdrck/nado-waves; attach ptrrdrck/nado-waves-notes.
  Group 5 of docs/handoff.md (item 9), Buoys tab. Read buoys.md and map.md
  first; mock before building."

### Working efficiently

- Read only the design doc and BRIEFING sections a group names.
- Mock design calls (2, 8, 9, 11, 12) before building.
- iPhone-only bugs get a diagnostic page before any code changes.
- Measure rendering; one screenshot at the end. `app/forecast.html` is
  ~10,500 lines: grep it, never read it whole.
