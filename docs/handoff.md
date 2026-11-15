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

### Group 1: map behaviour (Opus, usual effort) -- built, awaiting the owner

Area: `docs/design/map.md`. Items 1, 5 and 10 are fixed on
`claude/keen-cannon-29iuv0` (see map.md's last sections); item 6 waits on the
owner's pick in the "Seabed Map Themes" mock (Switching break: Ease / Jump).
The iPhone check is the "Swell Map Jump Check" artifact: before / after copies
of the page with a badge that turns red when the page moves on its own. Still
open from item 1: a refresh lands at the top in Chromium because the cards
arrive after its scroll restoration gives up; that is page-wide, not the map's,
and waits on the owner's iPhone result and call.

1. **The page jumps** on refresh while scrolled below the map, and when the
   Units setting changes. Reproduce (scrollY before and after) before fixing;
   an iPhone-only cause gets a diagnostic page first.
5. **The window drawing's top heading numbers are cut off** (e.g. tap the
   islands' north group), then the drawing drops into place after a long
   delay. Measure the clipped text against the trimmed viewBox; time the
   delay.
6. **Map rotation animation.** The owner saw the rotation ease in the
   "Seabed Map Themes" mock (one map; switching break eases the bearing over
   400 ms) and thinks they want it. The app has one map per break, so a tab
   switch never rotates. First an ease / jump option in that mock; the app
   follows the owner's pick.
10. **Tap a break on the map to switch break tabs**, through the same switch
    a tab tap uses.

### Group 2: geometry and ray diagnosis (strongest setting)

Area: `docs/design/geometry.md`, `chain.md`, `map.md` ("The fill"); BRIEFING
§10, §24–§26, §31, §45.

4. **Coronado Islands: the south group's southern edge runs over land** (seen
   on satellite before too). Find the cause and the truth (ENC outline,
   blocker hull, drawing projection, seabed shoreline) and report before
   changing anything: a change moves published windows.
3. **The fill's rays: some start past 46232, some at it.** Explain why, then
   make them consistent, drawn as far out as the physics supports (where they
   leave deep water?), measured before built.

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
