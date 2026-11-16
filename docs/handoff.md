_Read at the start of a session that picks up open work, and update it before stopping._

# Handoff

## Where things are

- CLAUDE.md holds the lasting rules; `docs/design/*.md` holds each area's full
  design history, moved there verbatim on 2026-11-14.
- BRIEFING.md is in the private `ptrrdrck/nado-waves-notes`: attach it to the
  session (it is 4,982 lines; read only the sections an item names).

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

### Group 2b: the map's coastline against the geometry's -- done (PR #226)

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
    `app/docs.html`'s map paragraph says so in the owner's approved
    wording.

### Group 2c: the Baja tangent -- done (PR #227)

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

### Group 2d: the islands, and the straight leg -- done (branch claude/elegant-thompson-qcbg6w)

All four confirmed by the owner on 2026-11-15 as recommended after the
measurements (BRIEFING §55; evidence and scripts in the notes repository,
`evidence/2026-11-15-group-2d/`). One rebuild: tables, legs, fill paths,
fetch tables, the seabed drawing, docs.html's worked hour.

18. **North Coronado from imagery, both ends** -- done. `a` the tip of a dry
    islet past the south-east end, `b` the north-west rocks; the chart drew
    the island 200-260 m north-west. Channel's high edge -0.23...-0.28,
    west window's low edge -0.30...-0.41. geometry.md "The Coronado
    Islands".
13. **The islands in the seabed** -- done. `data/bathymetry/islands.json`
    (imaged outlines, GLO-30 heights) burned into `outer` and `context` at
    load, for the rays and the map (Middle is too small for `context`).
14. **Islands as land, the shadow by diffraction only** -- done. The
    see-through disc is gone; a shadowed ray takes a clear neighbour's
    heading and the Babinet factor interpolated across the shadow. Tip and
    pad perturbations now move no hour 5% (the disc: up to 95 hours). The
    5 m height moved a median +0.8 / +0.3 / +1.5% once. chain.md "A ray
    that lands on an island".
19. **The straight leg walked over the grids** -- done. Nearly all the rows
    it blocks cross the US shore south of the breaks, not Mexico past `b`;
    worst hour -6.2%. chain.md "Baja's edge in the rays".

Not done, noted: the largest single ray still carries 33-64% of a break's
5 m energy on some narrow-swell hours (a clear ray with the islands'
lit-side ripple), under every island treatment; stable, so not item 14.

### Group 3: map layers -- items 2, 11 and 20 done (branches claude/gracious-rubin-6x5o2g, claude/awesome-rubin-b550ps)

Mocked in "Seabed Map Themes" and picked by the owner on 2026-11-16; map.md
"Map layers".

2. **Window edges to the map's edge** -- done: the dashed lines run 1,500 km,
   past the widest view (1,028 km at most). The tints stay at 1.6 times the
   farthest vertex; masking them over land was mocked and dropped.
11. **A map layer control** -- done: top right, Windows, Shadows, Window
    edges, then Grayscale and Lines only, one look at a time.
12. **Origins as a map layer** -- set aside by the owner for a session of
    their own; the mock keeps it, origin.md's last section the notes (and
    the whole Pacific).
20. **Hide the window drawing** (owner's request, 2026-11-16) -- done: the
    map the only view, its switch gone; the drawing kept, unseen, as the
    map's source and its keyboard way in, shown only where the map cannot be
    drawn (no WebGL, or the library, map.json or the map failing); a working
    drawing on docs.html as the project's history, its code pinned to the
    page's. map.md "The map, the only view".

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
- Group 4: "Repo ptrrdrck/nado-waves; attach ptrrdrck/nado-waves-notes.
  Group 4 of docs/handoff.md (items 7, 8), Wind and Tide cards. Read
  tide_wind_sun.md and app_surface.md first; mock item 8 before building."
- Group 5: "Repo ptrrdrck/nado-waves; attach ptrrdrck/nado-waves-notes.
  Group 5 of docs/handoff.md (item 9), Buoys tab. Read buoys.md and map.md
  first; mock before building."

### Working efficiently

- Read only the design doc and BRIEFING sections a group names.
- Mock design calls (8, 9) before building.
- iPhone-only bugs get a diagnostic page before any code changes.
- Measure rendering; one screenshot at the end. `app/forecast.html` is
  ~10,500 lines: grep it, never read it whole.
