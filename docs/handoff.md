_Read at the start of a session that picks up open work, and update it before stopping._

# Handoff

## Where things are

- CLAUDE.md holds the lasting rules; `docs/design/*.md` holds each area's full
  design history, moved there verbatim on 2026-11-14.

## Backlog

**Owner will re-word these before work starts.** Don't begin an item until it
has been re-worded and confirmed.

- Map causes page jumping: on refresh while scrolled below the map, and when
  the Units setting changes.
- Extend the window edges (dashed lines) to the map's edges when zoomed out;
  add it to the map colours mock with toggles for rays / windows / shadows
  extending to the edge, and a toggle to mask the shadow over land.
- The fill's rays: some are drawn starting past 46232, some at it. Explain
  why, then make them consistent, drawn as far out as the physics supports
  (where they leave deep water?).
- Coronado Islands geometry looks wrong: the south group's southern edge runs
  over land (seen on satellite before too). Find the cause and the truth
  before adjusting anything.
- The window drawing's top heading numbers are cut off (e.g. tap the islands'
  north group), then the drawing drops into place after a long delay.
- (Owner has more items to add.)
