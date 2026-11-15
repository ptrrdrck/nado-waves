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
seabed ends. It left two items, both the islands':

13. **The seabed grids are missing islands** (owner: its own session). GMRT's
    90 m `outer` grid has only South Coronado as land (Middle reads 1.4 m
    deep, North Coronado at least 22 m); the 400 m `context` grid, the only
    seabed the map draws below zoom 8, has none. Rays use `outer`. Options
    measured nowhere yet: burn the charted (or imaged) islands into the grids
    for the map and the rays, which moves the tables; or a map-only overlay,
    which would show land the rays do not see.
14. **A ray re-traced through an island is unstable** (chain.md). One ray
    through the see-through disc carries up to 33-63% of a break's 5 m energy
    on some hours, and a 50 m change of the disc's pad moves single hours by
    up to -29% / +34%. Measure what a smoother treatment (no step-edged disc;
    bounded single-ray gains; or the islands as land with diffraction only)
    does before choosing one. Strongest setting.

### Group 3: map layers (mock first)

Area: `docs/design/map.md`, `origin.md`. After group 2: extending shadows to
the map's edge also extends any islands error.

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
