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

### Group 4: Wind and Tide cards -- done (branch claude/affectionate-keller-e0tse2)

Mocked in "Wind Card Rose" (two rounds) and picked by the owner on
2026-11-17; tide_wind_sun.md "The Wind card's rose" and "The LIVE tide's
measured rate".

7. **Space between the tide height and its rate** -- done: 22 px (from 10),
   a flex column gap, so a reading too wide for one line (a low below zero
   in "Both" at 320 px) wraps the rate flush left, not indented.
8. **Wind symbol** -- done: a rose whose top is the break's facing heading,
   its four 90° headings by compass point (all ink, ticks grey), a
   fixed-length arrow pointing where the wind blows TO. One rose, the picked
   break's, on a phone or tablet, none on the buoy's tab; three in a row
   wide. Sized so WNW stays inside the card; the headline sits at the same
   height on every tab (measured). On Forecast it draws the NWS wind.

Not done, asked: a sentence on the rose in docs.html's Wind card section
("Offshore, cross-shore, onshore or light") -- docs.html is out of the
group's area, so it waits for the owner's yes.

### Group 5: Buoys tab -- done (branch claude/peaceful-lamport-8a5hfz)

Mocked in "Buoy Rose Seabed" (four rounds) and picked by the owner on
2026-11-17; buoys.md "The seabed behind the rose, and the bar", map.md "The
roses' seabed"; docs.html's roses section updated (owner's yes).

9. **Map imagery behind the buoy rose, centred on the buoy** -- done: the
   seabed vectors (not satellite) in the colour theme, north up, 40 km at
   the rose's edge for every buoy, the whole plate, no marks; a still image
   from one offscreen map, let go. The rose in the dark theme's colours on
   both themes; the line under it says the map's reach and drops the time;
   the bar redrawn as the break map's fill bar, ft / s back in the
   bottom-right corner. Without WebGL the rose stays on the card as before.

### Group 6: the height overstated on big westerly days (branches claude/sharp-turing-3iyub6, claude/madsen-friction, claude/surfzone-breaking-depth-71qxse)

The owner's report, 2026-11-17, with no logged observation: the LIVE
headline reads high across the beach, more so as a share on big days.
Diagnosed and measured, nothing fitted (BRIEFING §56; scripts in the notes
repository, `evidence/2026-11-17-overstatement/`; chain.md's last three
sections).

21. **The "already breaking" flag** -- done. `surfzone.START_GAIN`; heights
    unchanged, the card's upper-bound note now on the hours it belongs to.
22. **Shelf losses on big days, measured** -- done, report only
    (`python -m forecast.shelfloss --cache <pkl> --every 8`, ~1.5 h; the
    paths take ~10 min to re-trace from the table's own headings and the
    pickle keeps them). Since §57 it is the Madsen runtime's reference.
23. **The MOP cross-check** -- run 2026-11-18 (`mop-check.yml` run 1;
    `docs/mop_check.md`, `data/mop/`, BRIEFING §56a). Chain over MOP,
    deep-water-equivalent before friction: Center 1.17-1.22 on S-W, 1.34 on
    W-WNW; South 1.29-1.39 and 1.43. Re-dispatch to extend the series.
24. **The chain's own rays from MOP's points** -- done, report only
    (`python -m forecast.mopdepth --out docs/mop_depth.md`; ~25 min to build
    the 12 tables into `data/live/mopdepth/`, ~4 min once cached; BRIEFING
    §56b). Not the place: over the same water the chain is 1.19-1.41 x MOP
    at all three points, not diffraction, fills or direction. Open, in
    order:
    a. **MOP's own spectrum and metadata, on Actions** -- done (branch
       claude/loving-cerf-1cllei, BRIEFING §56c, chain.md's MOP section).
       `collector.mop` saves the spectrum, moments, inputs and every
       attribute; `mop-check.yml` runs on a branch (no merge needed). The
       datum is not in the file (inference stands); the file says nothing
       about diffraction; the inputs are CDIP 191 (46232) with 067, 071,
       220, 100, 045. De-shoaled band by band, chain-at-MOP / MOP is
       1.11-1.30 by sector (not 1.19-1.41): broad in frequency, ~1.1-1.25
       from 27 s to 5 s, plus W-WNW 13-16.7 s at 1.37-1.39 at all three
       points, arriving 3-10° further west than MOP. Left open: the CDIP ids
       named (CDIP's station list, from Actions), what the colon in the
       input string separates, whether MOP diffracts (its v1.1 page, from
       Actions), and `mopcheck` still de-shoals at Tp (§56a's figures are
       ~0.1 high for that reason).
    b. **An exposed MOP point** -- done, report only (branch
       claude/mop-imperial-beach-comparison-twsnli, BRIEFING §56d, chain.md's
       MOP section; `collector.mop --points extra` on Actions, run 6, then
       `python -m forecast.mopdepth --out docs/mop_depth.md`, ~4 min once
       the 12 break tables are cached, ~30 min cold). Imperial Beach, D0052,
       Point Loma edge 315.6°. Neither expectation held: below 8 s the
       ratio is much the same at all four points (5-8 s 1.02-1.28),
       common and placeless; above 8 s IB is 1.2-1.9, higher than any Coronado
       point, and W-WNW 13-16.7 s is 1.75 there (Coronado 1.36-1.39), so
       the long-period excess is not the shadow and not (only) the wrap.
       Grid control: Center on the 32 m grid alone moves 0.00-0.08. On S-SW
       swell the chain's long-period energy at IB arrives 13-25° south of
       MOP's, where straight contours put it; MOP's sits near the normal.
       The chain's 14.3 s acceptance at IB is lumpy (to 2.5 per degree,
       143° in all against straight contours' 113°), and 10% of its S-swell
       energy comes from past the seaward limit (the Baja tangent). Next,
       for the owner to choose: whether the long-period excess is the ray
       comb's focusing (the comb smoothed in offshore heading, or traced at
       finer headings, against MOP), and what IB's Baja-side rays stand on.
    c. **The buoy's directional reading**: MEM against Fourier moves the
       ratio 0.1-0.3. MOP blends six buoys (a), so "the same input" is
       not; how MOP combines them is part of this. Not pursued: the
       owner's question is which model is right, and only (d) answers it.
    d. **Both models against an observation** -- done, report only
       (branch claude/youthful-fermi-q19fhe, PR #245; `docs/nearshore_test.md`,
       `docs/nearshore_census.md`). The owner asked whether to give up the
       chain's deep-water-to-10 m leg for MOP's; model against model cannot
       say. `collector.nearshore_census` (mop-check.yml `points=census`, run
       8) found Imperial Beach Nearshore, CDIP 155 / NDBC 46235, 21 m, inside
       the 32 m grid; NDBC holds no historical spectra for it or 46232, CDIP
       does. MOP publishes `forecast` and `ecmwf_fc` for all 1,210 San Diego
       points. `collector.nearshore_test` (`points=nearshore_test`, run 9)
       fetched 2024 (its fixed rule's year): 155, 191 (46232) and MOP D0043
       (hindcast; 155 never among its inputs). `python -m
       forecast.nearshoretest` (~8 min, tables cached in
       `data/live/nearshoretest/`, ~15 min cold) scores them.
       **Verification series CDIP 155, 2024, 8,782 hours**: the chain at the
       buoy, exactly, Hs 1.09x observed [0.95, 1.27], +0.10 m, RMS 0.17 m
       before friction; 1.07x, +0.08 m, RMS 0.15 m with the table's JONSWAP
       friction (Madsen not tabulated there). The excess is long-period:
       > 13 s 1.19 (south swell 1.23-1.33, W-WNW 1.09-1.14), under 13 s
       1.04-1.08; it does not grow with size (>= 2 m: 1.06). Direction at the
       buoy within 2-4 degrees in every band. MOP, at D0043 (10 m, 1.9 km
       inshore) and de-shoaled, so approximate: 0.99x [0.85, 1.14]; low on
       long-period south swell (0.70-0.80), 1.01-1.12 on W-WNW; the chain's
       own two tables put D0043 6% above the buoy's spot. The observation
       sits between the models, nearer MOP in total. One exposed site, one
       year, not Coronado's shadow.
       **The shipped chain** (owner's step 1, 2026-11-21; Madsen tabulated
       at the buoy's own start -- `raytrace.madsen_losses` now takes `h_ref`,
       default unchanged -- carried by `nearshore.carry` itself, MSL):
       1.06x observed [0.92, 1.23], +0.06 m, RMS 0.14 m; >= 2 m 1.02 (W-WNW
       1.03); > 13 s 1.11 (south swell 1.15-1.23, W-WNW 1.01-1.06), under
       13 s 1.01-1.07. Fed NDBC's rounded feed instead of CDIP's (August
       2026, a ratio of two carries): 0.965 whole, 0.991 at >= 8 s, 0.943
       below. The owner asked whether to adjust the height; on this the
       case is weak (smaller than the scatter, one exposed site, the cause
       in long-period south swell not located). Not adjusted. Controls: CDIP's 191 against this
       repository's NDBC archive, same hours, +0.9% Hs at >= 8 s (+6.6%
       below 8 s: NDBC's feed is quantised and its small bins read low --
       the shipped chain's input is low there); read-backs 1.000; a second
       buoy position 1.00. The series (~90 MB) were dropped from the tree
       (owner, 2026-11-21); restore with `git checkout 38e295e --
       data/nearshore_test` before re-running. A new fetch keeps them as
       the run's artifact and commits only its record.
25. **Madsen's friction ships** -- done (branch claude/madsen-friction,
    BRIEFING §57, chain.md "Bottom friction is Madsen's"). Both chains;
    `<break>_madsen.json` beside unchanged tables; the docs page's friction
    section, worked hour and direction table redone (owner's yes,
    2026-11-18). Archive-wide before/after: `docs/friction_shift.md`
    (`python -m forecast.frictionshift --write`, ~10 min). Rebuild the
    Madsen tables with `python -m forecast.raytrace --madsen-only` (~12 min
    a break) whenever the tables are rebuilt; a full build writes them too.
26. **Let waves break before 5 m, in the surf zone** -- done (branch
    claude/surfzone-breaking-depth-71qxse, BRIEFING §58, chain.md "The surf
    zone starts seaward of the tables"). The profiles start at
    `raytrace.SURF_START_M` (North 7 m, Center and South 10 m), measured so
    that no archived hour is breaking there yet; the tables and `H_REF` do
    not move. No archived hour is flagged `outside_start` now (Center was 11
    and South 32 of 68 at 46232 ≥ 2.5 m). Formerly flagged hours fall a
    median 2–3%, at most 6% (Center) and 10% (South): the ceiling was close
    to the real break. Archive-wide: `docs/break_shift.md`
    (`python -m forecast.breakshift --write`, ~3 min). Rebuild the profiles
    with `python -m forecast.raytrace --profile-only`, which refuses unless
    the rows from 5 m in come back as committed; the docs page's step 8 and
    the hand-over box were updated (owner's yes, 2026-11-18).

27. **Big westerly days at Coronado: what the chain over-applies or leaves
    out** -- open, the owner's plan of 2026-11-21. The owner saw the headline
    high on 17 Nov (BRIEFING §56: 46232 3.1-3.7 m from 280-296°), before
    Madsen (§57) and the earlier surf zone (§58) shipped; there has been no
    big westerly day since, so neither is yet seen against one. Item 24d
    clears deep water to 21 m on the open shelf (Imperial Beach, shipped
    chain 1.03x on W-WNW >= 2 m), so the gap lives in what Coronado has and
    Imperial Beach does not. The stages, and whether anything observed has
    checked them:

    | stage | observed? | could over-apply or leave out |
    |---|---|---|
    | 46232's directional reading (NDBC feed, MEM) | partly | one MEM spike on one ray carried 13-17% (§56) |
    | refraction over open shelf to ~21 m | yes (24d) | -- |
    | the wrap round Point Loma (53% of Center's energy on 17 Nov) | never | caustic over-focusing; refraction and diffraction computed apart |
    | Point Loma's kelp bed and reef | not modelled | across the wrap's path |
    | Madsen in the shadow (6-12 m for km) | open sandy shelf only | k_N default may be smooth for rock/kelp |
    | 21 m -> 5 m, the surf zone, breaking | never | gamma, profile, start gain |
    | local chop added on LIVE | never | double-counting 46232's wind sea |
    | headline against what is seen | definition | sets 1-1.3 Hs (§56) |

    In order, each report only, nothing shipped until an observation names a
    stage:
    a. **The gap as shipped** -- done, report only (BRIEFING §59,
       `docs/westerly_gap.md`, `python -m forecast.westerlygap --write`,
       ~10 min). Every archived hour with 46232 >= 2 m and swell (>= 8 s)
       from 270-295° (108 hours, 12 days, 8-21 Nov) plus all of 17 Nov,
       through `now.build(as_of=True)` as LIVE ran it on 17 Nov ("then",
       rebuilt in today's code; gives §56's 22Z table back, and the code of
       67f9fe61 to the digit on all 72 break-hours of 17 Nov) and as it ships.
       **Madsen and the deeper surf-zone start took 14-15% off the headline at
       Center and South (16-18% with 46232 >= 3 m), 11% at North**, nearly
       all of it Madsen's; the surf-zone start <= 2 points. 17 Nov 22Z: Center
       2.09 -> 1.76 m, South 2.34 -> 1.96. Local chop adds nothing on these
       hours (1.00). The chain still gives about twice the straight-line
       window at Center and South (1.8-2.0x, was 2.2-2.5x): the wrap is
       untouched. Hour to hour at a steady buoy the headline still jumps by
       up to a third (South 17 Nov 17Z-19Z 1.84 -> 2.53 m with 46232 at
       3.3-3.6 m; Center 01Z-02Z 1.57 -> 2.09 m at 2.6-2.7 m): the few-ray
       signature (b) tests. 18 and 20 Nov were big westerly days by
       this definition (46232 to 2.82 and 2.39 m); 20 Nov's 20 hours came
       after both changes shipped.
    b. **Stage budget on every big westerly hour** -- done, report only
       (BRIEFING §60, `docs/wrap_budget.md`, `python -m forecast.wrapbudget
       --write`, ~25 min with the finer tables cached in
       `data/live/wrapbudget/`, ~30 min more cold). `raytrace.table` gained
       `dir_step` (default 0.5°; at 0.5 every committed row comes back, all
       three breaks). **The wrap carries 70-71% of Center's and South's 5 m
       energy** on these hours (direct 13-19%, Point Loma fill 7-14%, North
       wrap 30%); without it the headline would be ~0.6x. **It is not the
       comb's focusing**: at 0.25° and 0.125° headings Center and South are
       0.96-1.00 of the shipped 5 m height, a ±5-10° smoothed input 1.01-1.04
       (up, not down); the top 3 rays carry 12-13% (5-6% at 0.125°) and the
       wrap's share holds (0.74-0.79). Linear ray refraction round the tip is
       what makes it, at any resolution. **The hour-to-hour jumps are input
       sampling**: σ 5° removes nearly all (Center 7 -> 1, South 6 -> 0). At
       South they are the Point Loma diffraction fill: 55-70 rays per
       frequency read 46232 at the ONE offshore heading of the nearest clear
       ray, and that heading wanders from frequency to frequency (South
       235-349°, Center 218° to 2°); at 17 Nov 19Z the fill was 59% of
       South's energy. A fault in how the fill picks its heading, worth a few
       % in the median, not the gap; a fix is the owner's call.
    c. **An observation in the shadow** -- skipped (owner, 2026-11-21:
       there is no other CDIP sensor in the shadow).
       Was: CDIP's whole archive (the census
       saw only NDBC's stations) for any buoy or pressure sensor ever off
       Coronado, Silver Strand or Zuniga; if one exists, the 24d test there.
    d. **Kelp and reef** -- parked (owner, 2026-11-22; BRIEFING §62).
       NOAA's ENC answered on run 17: Point Loma's kelp is charted as 45
       POINT symbols only (`Weed_Kelp_point`: harbour 23, coastal 14,
       approach 8; surveys 1998-2005), no WEDKLP area at any scale, so there
       is no outline to measure a path through. The owner stopped the work:
       it is pursued only if it can give an attenuation the chain could
       apply, and neither the chart nor the literature (from search
       summaries: Elwany et al. 1995 and Rosman et al. 2007 no significant
       loss at swell periods; Elsmore et al. 2024 ~1e-3 /m for 1-3 s only)
       offers one. No other outline source is to be sought. Kept for a later
       look: `collector.kelp` (fixed on run 17's finding: points kept with
       positions in `data/kelp/enc_wedklp_points.csv`, no empty file,
       points-only is exit 4; run 18 stored the 45), `forecast.kelpcross`
       (never run; refuses without an area). Reopens on a measured
       swell-band attenuation from a paper read, or a beach-log observation
       naming the wrap. Reef (Madsen at a rock roughness) was not asked for.
       **Found on the way and fixed (owner's choice of design, 2026-11-21):
       the Point Loma / Baja diffraction fill** -- BRIEFING §61, chain.md "A
       headland's fill is read across the Fresnel zone", `docs/fill_shift.md`.
       It moved four of the owner's pinned train-row cases (§49), no height;
       re-pinned on the owner's yes (chain.md has the list).
       Docs page: the worked hour and direction table redone; the method
       sentence on diffraction now in the owner's wording (2026-11-22):
       islands by the nearest clear ray, headlands across the strip beside
       the edge, weighted evenly.
    e. **The beach log**: the owner's big-westerly sessions across breaks,
       the long-run judge (`docs/observation_log.md`).

Open, the owner's calls:

- How the HEADLINE reads when `outside_start` is true: moot on the archive
  since item 26 (no hour flagged); it would take a sea above 46232 ≈ 5.8 m
  at South. Still the number, with the note under the calculation table.
- The westerly half of the excess (the wrap round Point Loma): item 24
  first, so a table fault is not credited to the friction or the reverse.
- Item 24d: whether to switch any leg to MOP, or adjust the height. At the
  one observed site the shipped chain is 1.06x (1.02x on days >= 2 m), MOP
  about right in total but ~25% low on long-period south swell; neither
  wins outright, and nothing is fitted or shipped.

### Group 7: the Swell card's tabs box and tray -- done (PR #252; item 28, branch claude/forecast-swell-card-alignment-bi2xbu; the caret at the box's foot, 2026-11-28; item 29, branch claude/swell-card-wide-layout-sss0yb)

The LIVE phone card shipped (app_surface.md "The Swell card's tabs box and
tray", every measurement and owner's call there): the Briefing's swell
block as its headline with a 112 x 28 sparkline, each tab's height under
its name, the panes in a tray under the tabs, the Buoys tab's plates and
rhythm, the picked tab dropping its height while the tray is open, the
tab names' O / U and pair spacing (`tabLetters`, `TAB_KERN`), and no tap
flash page-wide. The same PR fixed test_mopdepth's known-answer test,
which read a band with no energy (NaN direction, a gap) as a failure on
the newest spectra.

On 2026-11-28 (branch claude/swell-card-redesign-acrmw7, merged without a
PR at the owner's word) the tray moved ABOVE its caret, the caret became a
ruled strip open or shut, every fold's caret on the page turned (down
shut, up open), shutting from the caret keeps it under the finger, buoy
folds stopped jumping as they finish shutting, and Forecast's 46232 became
the Buoys tab's foot (app_surface.md "The page's carets" and the tray
section's 2026-11-28 block). Later that day Tanner Bank's swells on their way
left the LIVE headline for an Offshore box under the tabs box (app_surface.md
"The Offshore box"). Item 29's wide layouts have no tray or caret.

`swellCard`'s `tray` and `headline` options are what the LIVE call passes;
the Forecast call passes neither, so item 28 is mostly a headline to build
and the two options to pass. Spacing on this card is measured in PAINTED
pixels (ink to ink, ink to hairline), not boxes: the owner judges it that
way, and box arithmetic was off by 2-6 px every time.

Mocking with live data, as PR #252's mock was built: clone the public
`ptrrdrck/nado-waves-forecast` bundle (the git proxy serves it), write its
`index.html` from `forecast.publish.wrap(repoint(app/forecast.html))`,
serve it with `python3 -m http.server`, and measure with Playwright. As an
artifact: the page as the main file, the bundle's JSON, seabed and
nearshore files beside it; MapLibre's script from jsDelivr
(`maplibre-gl@4.7.1/dist`) and its CSS inlined (the artifact's CSP admits
neither the vendored script nor a stylesheet), `kept()` bypassed to plain
fetches, and `Date` pinned to the snapshot's collection so the countdowns
and greying read as they did. Mock only, never committed.

28. **The Forecast tab's Swell card, aligned** -- done (app_surface.md
    "The Forecast tab's Swell card"): LIVE's tab heights and tray, and its
    own headline from forecast.json at the picked hour (`fcSwellBrief`):
    the range, a sparkline of the 24 h FROM the hour, a line a train by the
    Briefing's rule, lines whose words match merged, no trend word (the
    owner's picks from the mock).
29. **The wide layouts** -- done (2026-11-28; app_surface.md "The swell
    headline and Offshore box on a wide screen"): the headline above the
    break columns on both tabs (Forecast's new there), the Offshore box
    under them, each one column wide (owner's picks from the mock), the
    Briefing from the alerts to the tides on every layout. docs.html's
    Briefing paragraphs reworded in place (owner's option 1 of three): the
    swell's read heads the Swell card, the Briefing three blocks, Tanner
    Bank's swells the Offshore box under the breaks.
30. **One line a swell in the swell headline, both tabs** -- done
    (2026-11-28; `briefing.same_swell` and `fcSwellTrains`, measured by
    `python -m forecast.trainmatch --lines`, briefing.md's Swell block).
    docs.html's swell paragraph reworded to one line a swell on 2026-11-28
    (owner's call, with item 29's pass).
31. **Origin on the trains** -- done (branch
    claude/origin-display-trains-mb8vty; origin.md "Origin on the trains",
    docs/origin_wording.md's 2026-11-28 pass): the fold is gone; a marked,
    dotted period, and a tap opens the origin's line under its row. Open:
    the owner's iPhone (no WebKit in a session: the marks' centring and the
    line's slide are checked in Chromium only); and a READING on a period
    two rows share takes the first row, since `origin.match` matches by
    period alone: 6.5% of reading hours over the archive, 3.6-9.9% by site
    (origin.md). A fix would match a row, not a period, in `origin.match`;
    the owner has the numbers, no decision yet.

### Carryover prompts

Each assumes a fresh session; add "Confirm each item before building. PR,
wait for Tests, don't merge." to each.

- Item 27, first (diagnosis; the strongest model, high effort, because
  the stage responsible is unknown and each next test has to be chosen
  from the last one's result, not just run): "Repo ptrrdrck/nado-waves;
  attach ptrrdrck/nado-waves-notes and read BRIEFING §56, §57 and §58,
  chain.md from 'The transfer tables stop at 5 m' to 'Bottom friction is
  Madsen's', docs/nearshore_test.md's first two tables, and
  docs/handoff.md items 24d and 27. Task: item 27 a-d in order, report
  only. The owner saw the headline high on big westerly days (17 Nov);
  Imperial Beach clears deep water to 21 m on open shelf, so find which
  Coronado-only stage makes the excess. Propose each step's measurement
  before running it."
- Group 2: "Repo ptrrdrck/nado-waves; attach ptrrdrck/nado-waves-notes.
  Group 2 of docs/handoff.md (items 4 and 3), geometry and ray diagnosis.
  Read the design docs and BRIEFING sections it names first. Report the
  cause and the truth before changing anything."

### Working efficiently

- Read only the design doc and BRIEFING sections a group names.
- Mock design calls (9) before building.
- iPhone-only bugs get a diagnostic page before any code changes.
- Measure rendering; one screenshot at the end. `app/forecast.html` is
  ~10,500 lines: grep it, never read it whole.
