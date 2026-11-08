# Swell card: the model's geometry on satellite imagery (MOCK)

Owner's requests: browse the model map from the Swell card over zoomable
satellite imagery like piermonkey.com's (2026-11-06), then (2026-11-07) turned
to match the window drawing, and living WHERE the drawing is with an easy
toggle between the two instead of on the back of a card that turns over.
Owner's choices: Esri World Imagery, in full colour (an exception to the
drawing's greys-only rule, on the map only). **Nothing here is published**:
`forecast.publish` ships `app/` only, and `app/forecast.html` is unchanged.

On a phone: https://raw.githack.com/ptrrdrck/nado-waves/master/mocks/swell_map/swell_map_mock.html
(tap "Open the page" the first time). Or open `swell_map_mock.html` in any
browser. It is the published page of its build time with that data built in,
so its cards age from then; the map's tiles need the network.

## What it does

- ONE button showing what a tap turns to, at ONE place in both views, 4 px
  in from the map's top-left corner (owner's calls, 2026-11-08): on the
  drawing the map symbol alone; on the map the drawing symbol, a half-circle
  with a line from the break to Baja's edge and Point Loma's as Center sees
  them, as wide as the map symbol. Every map control (that button, return,
  + and -) is the card's colour with a soft shadow and NO outline. + and - are drawn, not typed, so all four sit
  on their box's centre: measured at 4x, 0.00 px across and the same 0.5 px
  low for each (the card starts on a fractional pixel here); the
  half-circle a quarter pixel higher, where a flat-based shape reads as
  centred.
- The caption is OUT of the drawing and the map: one plain line under
  either, in a lead train heading's style (Archivo 14 px, 400, ink), the
  drawing's own words rejoined as its spoken label joins them.
- The drawing keeps its own box, but its lowest ink (the break's dot) sits
  as far above the caption's ink as the map's foot does: 13.5 px against
  13.25 at 4x. The empty card below its chord moved above it, so the page
  keeps its height. Only the MAP's top edge moves against the trains: as far
  under the last train's ink as the first train's ink sits under the
  headline's, 21.0 px at 4x (21.25 as Chromium snaps it here).
- **The drawing or map starts at ONE height on all three break tabs**
  (owner's choice, 2026-11-08, of three put to the owner): the lowest any
  of them would start at this reading or hour, so switching break tabs
  never moves it; it moves only when a new reading or another hour changes
  the lowest. One to four train rows, a headline wrapping on a 320 px
  phone, a past hour's "Observed at" line all vary above it, so the
  difference is made up directly above the drawing. Hidden tabs are
  measured laid out unseen, their rows fitted as the page fits them when
  shown, so nothing flickers. Checked at 320, 360 and 390 px on both tabs,
  drawing and map: one top on every break.
- The map is SQUARE, taller than the drawing so there is room to move about
  in (owner's request, 2026-11-08), and never more than 70% of the screen's
  height; the card grows by the difference while it shows.
- **Turned as the drawing is**: the break's shore normal straight up and
  the break as far above the map's foot as it sits above the drawing's, so
  every window edge is at its drawing angle. It OPENS three zoom steps in
  from the drawing's own scale (where the farthest vertex forming an edge
  sits on its rim): the owner's "+" three times, 2026-11-08.
- **It reads the drawing, not a payload of its own**: the windows' and
  shadows' angles (`data-geo`), each train's arrow, the 5 m arrowheads and
  the captions are the svg's, and a tap on the map goes through the page's
  own `togglePick`. So a row tap, an arrow tap and a map tap are one pick
  with one caption, on LIVE, Forecast and every past hour. Only the edge
  vertices, the land outlines and the buoy come from `forecast.geomviz`.
- Arrows are drawn in screen pixels from the break, as on the drawing, and
  keep their size at every zoom; a picked train lights in yellow with its
  5 m arrowhead at the break. Each edge is a ray to the ONE vertex that
  forms it; tap a vertex for its blocker and distance.
- Along the map's foot, aligned right: the return button, then + and -
  (owner's request, 2026-11-08). + and - zoom around the break; return
  goes back to the opening view.
  On a phone one finger scrolls the page and two move the map, with a hint;
  with a mouse, drag pans and ctrl + wheel zooms, as the charts do.

## Not done, and open

- Phone and tablet layouts only: the stack and console layouts draw the
  breaks as columns (`swellWide`); not tried there.
- The Buoys tab has no drawing, so no map.
- **Esri's terms are unchecked.** The classic tile endpoint needs no key
  today; Esri's current terms may ask for a free ArcGIS key, and attribution
  is required (top right of the map).
- Leaflet 1.9.4 and leaflet-rotate 0.2.8 are built into the file (~190 KB).
  Shipping them would make them the page's first outside scripts.
- docs.html would need a section saying the imagery is a photograph under
  the model and is read by nothing.

## Rebuild

    npm install leaflet@1.9.4 leaflet-rotate@0.2.8
    python -m mocks.swell_map.build ../nado-waves-forecast \
        node_modules/leaflet/dist node_modules/leaflet-rotate/dist \
        mocks/swell_map/swell_map_mock.html
