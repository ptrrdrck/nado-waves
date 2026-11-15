_Read before touching beach geometry, spots.json, blockers, windows, shore normals or buoy siting._

# Beach geometry: windows, blockers, normals, siting

Moved verbatim from CLAUDE.md on 2026-11-14 (the context-reduction
restructure); CLAUDE.md keeps the one-line rule and points here.

## Build order 1: beach geometry

1. **Beach geometry** — done, `forecast/geometry.py`. Which bearings reach each
   beach at all, from coordinates alone. Coronado's three breaks digitised
   2026-09-14; the Coronado Islands and the Baja coast charted from NOAA's ENC
   2026-09-20, which split the islands in two and closed the southern arc on
   land; the Point Loma tip charted 2026-09-22, per break; and the same day
   the three break chords themselves, each endpoint the harbour-band vertex
   nearest the hand trace (BRIEFING §27). **Every coordinate the Coronado
   aperture uses now comes from NOAA's ENC** — except WHERE along the coast
   each break sits, which is a surfer's choice and no chart can make, and,
   since 2026-11-15, South Coronado's south-east tip, which the chart rounds
   off, and both of the Baja coast's points, which it puts out to sea
   (below). If a
   break is ever traced from imagery again, `breaks_from_imagery` names it on
   the surface.

## The three beaches are not one beach

- **The three beaches are not one beach — and Coronado is not one beach.**
  Breakers keeps 23° of west window and Gator 62°, and Gator alone holds west
  swell. But the same mechanism runs along Coronado's own sand: the west edge
  IS the bearing to the Point Loma tip, which sweeps as you walk, giving
  **41.3° / 47.6° / 54.9°** at the north, center and south breaks across 2.8 km.
  That 13.6° spread is a third of the entire Breakers-to-Gator range. Any
  surface showing one number for "Coronado" is averaging across it. (Those were
  42.8 / 49.1 / 56.3 until 2026-09-20, when charting the Coronado Islands moved
  the LOW edge 1.2–1.9°; 41.6 / 47.7 / 54.7 until 2026-09-22, when charting
  the Point Loma tip moved the HIGH edge −0.53 / +0.01 / +0.17; and 41.1 /
  47.7 / 54.9 for the rest of that day, until the break chords were charted
  and north's position moved 30 m.)

## The Point Loma tip

- **The Point Loma tip carries every west edge, and it is not one point.** 100 m
  of error there moves an edge ~1°; it is the highest-leverage geometry in the
  repository. Measured 2026-09-18: 250 m of tip error moves a Coronado edge
  2.2–2.8°, against 0.46° for the same error on the Coronado Islands.
  **Charted 2026-09-22 from NOAA's ENC** (BRIEFING §26): the tip is a rounded
  headland, each break's tangent lands on a different charted vertex up to
  330 m apart, and any single point is wrong by up to 0.67° somewhere. So the
  blocker carries an `outline` (the convex hull of the charted tip — only a
  hull vertex can be a tangent) and `Blocker.a_seen_from` takes the edge per
  break. **Never collapse it back to one point.** The approach band is used,
  not the finer harbour band: the harbour coastline has a 336 m hole across
  the tip, and a tangent on a line end is missing data, not coast.
- **Checked against imagery and lidar, 2026-11-15** (BRIEFING §53): Esri
  World Imagery puts each break's tangent +0.08 / +0.01–0.04 / −0.13–0.15°
  from the charted one (N / C / S; 2–16 m across the line of sight), and
  CoNED's 1 m lidar, read at 2 m and contoured at mean high water, within
  ±12 m of each vertex. The chart stands; the map's 32 m grid was what sat
  off it (map.md, "The coast is the chart's").

## The Coronado Islands

- **The Coronado Islands are not a switch, and they are not one island.**
  Charted 2026-09-20 from NOAA's ENC: **two** islands with **6.1° of open
  channel** between them, stable from a 0.3 km to a 3 km clustering distance
  on two chart bands. The estimate they replaced was one blocker spanning the
  whole group, which claimed that channel was land and put the group's Fresnel
  number at ~7 where the islands' own are **1.6 and 0.2** — silencing the
  diffraction flag that §10 exists to raise. They remove **under 5%** of a
  30°-spread swell's energy where Point Loma removes ~50%. The locals who say
  the islands barely shadow are right, and the finer the geometry gets the
  more right they are. **Never restore a binary open/shut test for them**, and
  **never merge them back into one blocker** — both are the same error, one
  scale apart.
- **South Coronado's south-east tip is read off imagery, not the chart**
  (owner's report and decision, 2026-11-15; BRIEFING §52). The owner saw the
  south group's southern edge cross land on the map and on satellite. The
  ENC approach band rounds the island's south-east lobe off: its vertex sat
  48 / 58 / 71 m (north / center / south, across each line of sight at
  32 km) inside solid land on Esri World Imagery, so the edge read 0.08 /
  0.10 / 0.13° high; the coastal band is half way. Control: the imagery and
  the chart agree within 7 m on both islands' west coasts and within
  0.01–0.04° at the group's other edge, so this is generalisation of one
  lobe, not misregistration. Not the cause: the blocker's shape (one vertex
  is every Coronado break's tangent, in chart and imagery alike), the map's
  drawing (the edge line ends on the vertex; the shaded wedge's 0.1°
  rounding is ≤ 32 m there), or the map's seabed (GMRT's land at the tip
  agrees with the imagery). The owner's Google Earth points were not in use:
  §24 replaced them on 2026-09-20. `spots.json` carries the imagery vertex
  with an `imagery` block naming the ENC vertex it replaced, and the
  "standing on" line names "Esri World Imagery for South Coronado's
  south-east tip" beside the chart cells. Published windows: 187.4 → 187.3,
  189.1 → 189.0, 191.2 → 191.0; window energy 0.00% (no bin centre crossed,
  §26).
- **The islands are land in the seabed, from imagery** (owner's decision,
  2026-11-15, group 2d, item 13; BRIEFING §52, §55). GMRT does not carry
  them: in its 90 m `outer` grid only South Coronado was land (Middle
  Coronado a shoal, its shallowest stored cell 5.2 m deep and the cells
  now burned 10-14 m; North Coronado 22 m and more), in the 400 m
  `context` grid none. The rays refracted over a 22 m shoal where North
  Coronado stands: 20 rows of North's table, 15-40 s, crossed it, carrying a
  median 0.85% of North's 5 m energy and up to 18% on some hours (two single
  rays 11% and 13%); 163-216 short straight legs a break crossed Middle or
  North, and still do (the islands are diffracted on the straight leg, never
  blocked). `data/bathymetry/islands.json` holds the three islands' outlines
  from Esri World Imagery (colour, a 12 m opening, zoom 17, simplified to
  2 m; South Coronado's imaged tip 3 m inside it, North Coronado's ends
  within 2 m) with a height each from Copernicus GLO-30 (median, 5 m
  floor: GLO-30 does not resolve Middle Coronado). `raytrace.with_islands`
  burns them in when a grid is LOADED, into `outer` and `context` only, a
  cell becoming land where a quarter of it is island (153 and 15 cells);
  the stored GMRT grids are never edited, so a fetch keeps them. The map
  draws them too (`seabedvector.load_grid`, the outlines' fingerprint in
  its manifest): all three from zoom 8, South and North below it (Middle
  is under a quarter of a 400 m cell). North Coronado's south-east islet
  (2,565 m2) is under a quarter of a 90 m cell: its shadow comes in through
  `a`, the Babinet edge. Rejected: a map-only overlay, which would draw land
  the rays refracted over as a shoal. What the islands' being land did to
  the tables, with item 14's method: North's 5 m height a median +0.10%,
  worst hours -8.6 / +7.0% (15 over 5%), Center and South within 0.9%; four
  or five wind directions a break (189-204 degrees) now close their fetch
  on Middle or North Coronado at about 30 km instead of running 50 km open.
- **North Coronado is read off imagery, both ends** (owner's decision,
  2026-11-15, group 2d, item 18; BRIEFING §53, §55). The ENC approach band
  has the island's shape, displaced 200-260 m north-west: its `b` stood in
  open water 150-200 m past the last rocks. Against Esri World Imagery
  (solid land, zoom 16 and 17, openings of 6, 12 and 20 m) its edges read
  0.21-0.26 degrees high at `a` and 0.34-0.39 at `b`. GLO-30 agrees with the
  imagery on the main island within 0.02 degrees at both ends, so the
  imagery is not misregistered; §53's disagreement at `a` is a dry rock
  islet of 2,565 m2 about 100 m past the island's south-east end, across a
  gap of surf, sharp on WorldView-2 of 2023-01-31 at 0.5 m and about 50 m
  north of its seam with a 2022-01-19 capture (the cloudy 2021 GE01 lies
  further south), under GLO-30's 30 m posting. The classifier's "rock"
  variant reads the cloudy capture's water as rock there and was not used.
  `a` 32.43375, -117.29414 (the islet's tip; 0.15-0.17 degrees lower than
  the main island alone), `b` 32.44453, -117.30044; one point per end is
  every spot's tangent within 0.001 degrees. `spots.json` carries an
  `imagery` block naming the ENC vertices and no cells, as the Baja coast
  does, and the "standing on" line names "Esri World Imagery for North
  Coronado".

  | | north | center | south | Breakers* | Gator* |
  |---|---|---|---|---|---|
  | channel's high edge (`a`) | 198.62 -> 198.39 | 200.53 -> 200.29 | 203.01 -> 202.76 | 195.06 -> 194.85 | 205.52 -> 205.24 |
  | west window's low edge (`b`) | 200.61 -> 200.27 | 202.59 -> 202.24 | 205.18 -> 204.80 | 196.91 -> 196.61 | 207.82 -> 207.41 |
  | window energy, 2,100 hours (max. entropy) | -0.05% | -0.08% | 0 | 0 | -0.07% |

  \* estimated positions. Worst single hours of window energy: North
  -39 / +12%, Center -9 / +28%, Gator -8 / +7%. West window widths 41.7 /
  48.0 / 55.3 degrees. The 5 m height moved a median +0.3 / -0.2 / 0.0%
  (N / C / S), worst -4.2% (South), no hour 5%.

## The swell-side window

- **Publish the swell-side window, never the raw open arcs.** A window edge
  formed by the seaward half-plane clip means the arc ran out of *modelled*
  land, not that it ran into ocean. **As of 2026-09-20 no edge of any spot in
  the file is formed that way**, so `swell_window` and `open_window` now
  return the same thing — because the coast that was missing got charted, not
  because the rule relaxed. Keep the guard: it is what stops the next break
  added to the file publishing open water across a coastline nobody has
  digitised. BRIEFING §12, §24.

## The south window

- **The south window is real and it is where the south swell is.** The Baja
  coast is a **tangent**, not a chord: every charted vertex from the border to
  Rosarito sits inside 147–168° from these breaks, so one vertex at 23 km
  carries the whole southern edge. 100 m of error there costs 0.25°, against
  ~1° for the same error on the Point Loma tip. Measured on the three-year
  46232 archive, **16.7% of rows and 11.6% of energy** arrive from 100–190°,
  and **9.6% of all archive hours** carry Hs ≥ 1.0 m at DPD ≥ 12 s from that
  sector. UNTESTED until 2026-11-15: that no coast south of 32.3834 — where
  NOAA's charts stop — bears higher than the tangent. Landmark estimates said
  152–159°, all below it; that was not a measurement. **Measured** (BRIEFING
  §53): over GMRT at 90 m to 32.25 N and at 400 m to 29.24 N, nothing south
  of 32.3834 bears within 1.0–2.1° of the tangent as imagery places it
  (below).
- **The Baja tangent is read off imagery, both ends** (owner's decision,
  2026-11-15, group 2c, item 17; BRIEFING §53-§54). The ENC approach band's
  Mexican coast lies a median 225–466 m seaward of the real one from 32.38
  to 32.50 N and converges at the border; its tangent vertex (32.47015,
  −117.12459) was ~400 m off the headland it stands for, in open water, so
  every south edge read 0.82 / 0.86 / 0.91° (N / C / S) too high. `a` is now
  that headland's tip on Esri World Imagery, **32.46914, −117.12028**;
  Copernicus GLO-30 and GMRT agree within 0.01–0.09°. One vertex serves all
  five spots: Breakers' own imaged tangent (a headland at 32.4505 N) is
  0.03° lower and Gator's 0.004°, so it carries no outline. A rock platform
  awash west of the tip could pull the edge back by at most ~0.1°.
  **`b` moved with it** (32.38339, −117.08238, the imaged coast at the old
  `b`'s latitude; GLO-30 28 m east, GMRT within a 90 m cell): it stood on
  the same faulty band, 620 m out to sea, and left there it bears above the
  new `a` from Breakers' estimated position, `continues: "b"` flips the
  sector and Baja blocks the whole seaward half-plane (every Breakers window
  vanishes). `tests/test_geometry.py` holds `b` below `a` from every spot.
  The blocker has no cells now; `spots.json`'s `imagery` block names both
  ends and the chart vertices they replaced, and the "standing on" line
  says "Esri World Imagery for the Baja coast".

  | | north | center | south | Breakers* | Gator* |
  |---|---|---|---|---|---|
  | published low edge, chart | 164.63 | 166.42 | 168.45 | 161.41 | 170.08 |
  | imagery | 163.81 | 165.56 | 167.54 | 160.66 | 169.10 |
  | window energy, 2,090 hours (max. entropy) | +1.07% | 0.00% | 0.00% | 0.00% | +1.17% |

  \* estimated positions. Only North (164.5) and Gator (169.5) cross a
  half-degree bin centre (BRIEFING §26); their worst single hours gain +6.9%
  and +27% window Hs. What the move did to the rays is in chain.md.

## The buoy does not share the beach's geometry

- **The buoy does not share the beach's geometry.** 46232 sits south-west of
  Point Loma with the peninsula behind it to the north-east; the beaches sit in
  front of it. A transform that skips the aperture delivers north-west swell
  that cannot physically arrive, on most days of the year.

## A station earns its place by geometry

- **A station earns its place by geometry, not by being nearby.** `stations.json`
  says what is *archived* — collect broadly, the 45-day window is
  unrecoverable — and nothing more. Which buoys constrain the swell reaching
  Coronado is **derived** by `forecast/siting.py` from NDBC coordinates and the
  digitised breaks, never stored, because §2a already paid for duplicating a
  derivable coordinate. Measured (BRIEFING §3a): **46232 is the only buoy in
  the array inside Coronado's window, and there is no substitute.** 46258 is
  33.9° *behind* Point Loma at nearly 46232's range — a control for the
  aperture claim, and never a fallback anchor. The predecessor's
  `launch_candidate` flag marked leagues, not physics; four of its six sat
  55–92° off the window, and it is deleted.

## Never type a buoy coordinate

- **Never type a buoy coordinate.** `collector/metadata.py` fetches them from
  NDBC; a station it cannot place is reported UNPLACED and makes no claim.
  46235 is in that state now. NDBC is frequently denied at CONNECT from a
  session — run the metadata job on Actions.

## The shore normal and the wind reading

- **The shore normal is the highest-leverage input to the wind reading.**
  Measured 2026-09-20 (BRIEFING §20): the verdict
  boundaries sit at fixed angles from the normal, which puts six of the nine
  boundaries for Coronado's breaks inside 265–330°, and **62.6% of a three-year
  wind record sits in 270–330°**. So error lands where the data is: 1° of
  normal error changes the verdict on **4.2%** of readings and 5° on 21% —
  roughly twice what a uniform wind rose would cost. `coronado_north`'s
  imagery-splice caveat claimed ~19° (~70% of verdicts); §23 measured 1.7° and
  charting the chord (BRIEFING §27) moved it 1.3°, and the flag is retired.
  All three normals are now read off the ENC harbour band, and they agree with
  §23's 400 m principal-axis fits — a different method on the same chart —
  within 0.3°.

## Circular windows on a curving coast

- **Past a few hundred metres on a curving coast, a circular window is not a
  chord.** Measured 2026-09-20 (BRIEFING §23): two independent chart bands of
  the same coast agree within **0.3° up to 800 m**, and disagree by **18.6° at
  1500 m** at the south break, where the coast bends toward Imperial Beach. The
  principal axis of a circular window there is decided by which vertices each
  chart happened to place. Read the wide columns of `shorenormal`'s sweep as a
  curvature alarm, never as a normal. `REPORT_SCALE_M` at 400 m sits inside the
  agreeing range.

## A normal belongs to a chord

- **A normal is a property of a chord, not of a point.** The same beach gives
  104.1° over north's 530 m chord, 123.9° over centre's 285 m, 130.9° over
  south's 461 m and 120.8° over the whole 2.75 km — 26.8° of spread, all of it
  real (charted chords; the traced ones gave 102.8 / 124.2 / 131.5 / 121.3). Any verification that does not state its chord length has verified
  nothing. `forecast/shorenormal.py` therefore reports a SWEEP over scale, and
  `residual_m` says whether the break sits on a straight stretch or a curve.

## Two shore normals

- **There are two shore normals and they are not the same claim.** The
  waterline normal is what the wind reading needs; the depth-contour normal at
  breaking depth is what refraction will need. `Spot.normal` is currently one
  number doing both jobs, and checking it against a shoreline verifies only the
  first.
