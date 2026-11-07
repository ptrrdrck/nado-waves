# Swell card, back: the model's geometry on satellite imagery (MOCK)

Owner's request, 2026-11-06: browse the model map on the back of the Swell
card, over zoomable satellite imagery like piermonkey.com's. Owner's choices:
Esri World Imagery, in full colour (an exception to the drawing's greys-only
rule, on this face only), and a standalone mock first. **Nothing here is
published**: `forecast.publish` ships `app/` only, and `app/forecast.html` is
unchanged.

Open `swell_map_mock.html` in a browser. It is the published page of
2026-11-05 19:56Z with its data built in, so every card reads stale and
overdue; that is the snapshot, not the mock. The map needs the network for
its tiles (`server.arcgisonline.com`); everything else is in the file.

## What it does

- **Map** at the Swell card's top right turns the card over (170 ms each way,
  in the front's footprint so nothing below moves; instant under reduced
  motion). **Card** turns it back.
- The back has its own South / Center / North / Buoys tabs. Picking one moves
  the front's tab too, so turning back lands on the same break.
- A break tab draws that break's windows and shadows as fans out to 40 km,
  each edge a ray to the ONE vertex that forms it (`forecast.geomviz`), the
  two outermost edges with their degrees; Point Loma's charted hull and the
  islands' and Baja's edges dashed; the other two breaks; and on LIVE each
  train's offshore heading as an arrow. Tap a shadow, window, vertex or
  arrow for the same caption the front's drawing gives; tap it again or the
  land to clear it. A break tab opens framed on its edge vertices.
- Buoys frames 46232 with the beach, the islands and Baja, its caption the
  distance and point from Center break, computed, never typed.
- On a phone one finger scrolls the page and two move the map, with a hint
  when one finger tries; with a mouse, drag pans and ctrl + wheel zooms, as
  the charts do. The square button returns to the whole geometry.

## Not done, and open

- Phone and tablet layouts only. The stack and console layouts draw the
  breaks as columns (`swellWide`) and have no single card to turn over.
- The Forecast tab turns over too and draws the same geometry, but no trains
  or blocked shares: the mock reads LIVE's numbers from now.json only.
- The 5 m heading (`near_from_deg`) is not drawn, and the arrowhead sits
  1.4 km out at every zoom.
- **Esri's terms are unchecked.** The classic tile endpoint needs no key
  today; Esri's current terms may ask for a free ArcGIS key, and attribution
  is required (shown in the map's corner).
- Leaflet 1.9.4 is built into the file here. Shipping it would make it the
  page's first outside script (only Google Fonts load today), or 150 KB
  inline.
- docs.html would need a section saying the imagery is a photograph under
  the model and is read by nothing.

## Rebuild

    npm install leaflet@1.9.4          # anywhere; npm is reachable from a session
    python -m mocks.swell_map.build ../nado-waves-forecast \
        node_modules/leaflet/dist mocks/swell_map/swell_map_mock.html
