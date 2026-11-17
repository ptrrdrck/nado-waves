_Read before touching the Wind, Tide or Sun cards, the tide phase fold, tide direction / turns / rate, or the bay-to-coast tide transfer._

# Wind, tide and sun

Moved verbatim from CLAUDE.md on 2026-11-14 (the context-reduction
restructure); CLAUDE.md keeps the one-line rule and points here.

## The Tide card's phase fold

   **The Tide card's phase fold** (owner's request, 2026-10-11;
   `forecast/tidephase.py`, BRIEFING §41), on the Forecast tab only since
   2026-10-20 (owner's request: off LIVE "for now", `SHOW_LIVE_PHASE`
   brings it back), right above its
   Charts line under a rule of its own, its caret like Origin's: the line is
   a fixed title, "Phase" (owner's edit, same day, replacing the phase
   itself), tagged `predicted` on LIVE as the turn line is; open, three
   PARAGRAPHS, never bullets (owner's call), each a heading over its
   body — "Today" (the phase: Spring tides / Neap tides / Building toward
   springs / Easing toward neaps, the Moon, the day's pair), "Around 17 Oct"
   (the next spring or neap, what coincides, and "The upcoming turns show
   it: …"), "Late October" (owner's wording kept) — with no title above them.
   NOAA's constants are not named in the paragraphs (owner's edit, same
   day: "by NOAA's harmonic constants" and "by the same constants" came
   out). **Set as Origin's entries are, and no provenance** (owner's
   request, 2026-10-14): each heading at the value size over a grey body at
   15 px, a centred 4 px dot in that body's grey between paragraphs (Origin's
   entries alike; owner's request, same day); the constants and their 2017–2021
   analysis, the computed Moon and CO-OPS's turns are named on docs.html
   instead, the analysis held to the archived constants by a test. Spring and neap come from NOAA's harmonic constants for
   9410170 (`collector/harcon.py`, fetched on Actions, never typed — their
   `phase_local` is NOT comparable across speeds: read naively it puts
   springs 11 h before syzygy, `phase_GMT` 3 h), the Moon from
   `forecast/moon.py` (Meeus ch. 47, pure Python; mean elements had the
   October new moon a day late and perigee two days late). **Every threshold
   is measured** (owner's request) over 19 years of the station's tide
   rebuilt from the constants (`forecast/tidephasereport.py`, ~10 s, re-run
   by a test): a slot is said only where it is right ≥ 85% of the times it
   fires. **"The day's two tides", never "the two highs"**: the declination
   shows in the lows here (r 0.82 against 0.66). The constants reproduce
   CO-OPS's hourly prediction to 1.1 cm, and are read for the CYCLES only —
   the card's turns stay CO-OPS's hilo, with no fallback to a computed one.
   Wording generated from the page's code into `docs/tide_phase_wording.md`
   (`forecast/tidephasewording.py`). LIVE: the reader's day at Coronado;
   Forecast: the picked hour's day, none under a past hour.

## The Sun card

   **The Sun card** (owner's request, 2026-10-16; `forecast/sunset.py`,
   BRIEFING §42), after Tide (owner's choice of a card over a Tide fold),
   on the Forecast tab only since 2026-10-20 (owner's request: off LIVE
   "for now", `SHOW_LIVE_SUN` brings it back): the sunset the open break SEES. For most of the year the sun
   goes behind Point Loma's ridge (4.5–8 km out, 90–130 m, ~1° up) 5–8 min
   before the sea-horizon time every table gives; through the winter it sets
   in the sea, LEFT of the point, for a season that differs by break as the
   window does — South ~15 Oct–25 Feb, Center ~9 Nov–1 Feb, North NEVER
   (closest ~19–23 Dec, still 1 min early). Headline the break's sunset,
   then "behind Point Loma, 7 min early" (the minutes the two shown clocks'
   own difference) or "in the sea, left of the point, until …", the season
   line (one line in all while it sets in the sea), and "Sunrise …"; each
   tab's lines follow the swell tab (`data-sun-for`), the Buoys tab reading
   the sea horizon. Tagged `computed` on LIVE, where each time is the NEXT
   one, per tab, saying "tomorrow" when it is (owner's question, 2026-10-16:
   "Sunrise … · sea horizon 6:14 PM" after sunset read as either day's, and
   the sea-horizon clock came off). Refraction is Bennett's standard: KNZY's
   temperature and pressure move it 3–12 s over 28 sunsets, invisible at a
   minute; the air–sea difference (−3.5 to +8.3 °C, KNZY against 46232's
   SST) is the real swing, and nothing here measures what it does. The skyline
   is CoNED's own LAND (it is topobathy) traced from each break by
   `forecast/skyline.py` (precompute, numpy) into
   `data/nearshore/<break>_skyline.csv`; its first land agrees with the
   charted Point Loma tangent within 0.1° (a test pins 0.3°). Bare earth:
   trees and buildings can only make the real sunset EARLIER. Sunrise is
   the sea-level time; nothing east of the breaks is in the grids.

## One station's reading is not one beach's condition (Wind card)

- **One station's reading is not one beach's condition.** Wind and tide are
  hoisted out of the breaks — their own cards, beside the Swell card whose
  tabs are the three breaks (ranked by window energy, buoy always last) —
  because KNZY and 9410170 feed all three and repeating them three times is
  noise. **The offshore/onshore reading is not hoisted**, because it is derived from the shore normal and Coronado's three
  normals span 27° (194.1 / 213.9 / 220.9, charted 2026-09-22; they were
  192.8 / 214.2 / 221.5 on the traced chords) — a 290° wind reads cross-shore
  at north and centre and onshore at south, on the same reading. Hoist the
  measurement; keep the interpretation where it is made. Since 2026-09-26
  (owner's layout) the verdict sits on the Wind card as one line per break —
  "offshore at this break" — shown only for the break whose swell tab is open
  and hidden on the buoy's, so it is still per break. **On the Forecast tab
  the verdict comes from the LOCAL forecast wind, never the model's**:
  GFS-Wave's wind is at the buoy, 29 km offshore — kept on the card for the
  wind sea it makes — and a verdict against the shore normal needs the wind
  on the sand. Since 2026-09-30 the Wind card carries the local wind,
  and since 2026-10-20 it LEADS (owner's request): the NWS wind first, with
  KNZY's observed wind under it on a past hour, then GFS-Wave's under an
  "At the buoy" heading — "Local" is no longer a heading. The local wind is
  the NWS forecast grid at Coronado's center break
  (`collector.localwind`, fetched by `forecast.live` on Actions;
  api.weather.gov and aviationweather.gov are both denied at CONNECT from a
  session), hourly, 7 days, per break on each `Hour` as `local_wind_*`.
  Chosen over KNZY's TAF: a TAF runs 24–30 h in coded change groups written
  for the runway.

## The Wind card's rose

- **A rose beside the reading, turned to the break** (owner's design,
  2026-11-17, handoff group 4 item 8; mocked as "Wind Card Rose", two
  rounds; `windRose`, `windRoses`, `windReading`). The ring's top is the
  break's facing heading, its seaward shore normal; its four "cardinals"
  are the headings 90° from it, named by compass point (owner's pick over
  degrees), so North reads SSW / WNW / NNE / ESE clockwise and Center and
  South SW / NW / NE / SE. A classic arrow (filled head, two pairs of tail
  feathers) fills the ring side to side, pointing where the wind blows TO:
  up is offshore, down onshore, sideways cross-shore -- the verdict line's
  picture, made against the same normal, so it is per break as that line
  is, and the measurement is still hoisted. **The arrow's length never
  shows speed** (owner's pick of fixed over speed-scaled: the words give
  it, and a 5 mph arrow was hard to read in a 54 px ring). Every point in
  ink at one weight, every tick grey (owner's call, second round). A light
  wind (`LIGHT_KT` or less) draws the arrow faint; calm draws a small
  circle, the station-plot convention; a wind with no direction (VRB)
  draws none. An old reading greys the arrow with the card, never the
  points: they are the break's headings, not the reading.
- **Which break.** On a phone or tablet ONE rose, the open swell tab's
  break's, beside the reading (owner's choice of A over three in a row),
  following the tab as the verdict line does (`data-wind-for`); the buoy's
  tab shows none. Wide (stack, console), where no tab picks a break, the
  three in a row North to South, each named, between the headline and the
  three verdict lines; at the console rail's 312 px they draw at ~80%, the
  points ~9 px.
- **The headline never moves** (owner's note on the mock, where it shifted
  between a break's tab and the buoy's): the reading and the rose share one
  row on EVERY tab, the rose column empty on the buoy's. Measured at 390
  and 800 px on both tabs, the headline's top is 43 px into the card on
  North, Center, South and the buoy's, as on master. The card grows 42 px
  under a break's tab (145 → 187 on "LIVE"), and is master's on the buoy's.
- **The rose is 122 × 96** with the ring 54 px across. A side point starts
  6 px off the ring; the widest of the sixteen, WNW (North's right point),
  measures 27.6 px in Archivo 500 at 10.5 px (Chromium, 2026-11-17), so it
  ends 0.4 px inside the card's content edge, level with the pills' end
  (owner's report: WNW reached into the margin in the first round), and the
  ring sits in one place for every break. A test pins the fit both sides.
- **On Forecast the rose draws the NWS wind on the sand**, the one the
  verdict reads, never GFS-Wave's at the buoy (owner's confirmation, same
  day); under a past hour KNZY's observed wind stays the blue line only.

## Tide direction from the next turn

- **The tide's direction is read off the next turn, never differenced from the
  water level.** Measured 2026-09-19 on the 6-minute measured series:
  differencing the two newest samples reads the direction **backwards on 19.5%
  of readings** — at a neap; re-measured 2026-09-28 over half a spring-neap
  cycle it is **17–25% on neap days and 2.5–6% at springs, 9.9% overall**, so
  the error follows the tidal range and returns every two weeks
  (`tests/test_tideturns.py` pins the neap figure) — and a least-squares slope over a trailing 45 minutes is still
  wrong 3.3% — because near slack water the real change is smaller than the
  gauge's own wobble (median 6-minute step 1.1 cm). Every 45-minute error sits
  under 5.6 cm/h, but a deadband that wide would silence the card for roughly a
  quarter of every cycle. If the next turn is a high the tide is rising into it,
  so direction and target come from one source and cannot contradict each other
  on screen — which is what a measured "falling" beside a predicted high water
  would do, at exactly the moment a reader is looking. BRIEFING §19.

## Fetch the turns

- **Fetch the turns; do not find them in the hourly file.** `interval=hilo` is
  CO-OPS computing high and low water from the constituents. Taking the argmax
  of the hourly predictions instead puts the time **15.4 min out on average and
  up to 30.0** — measured against 31 real CO-OPS turns — while the height
  barely moves (2.8 cm worst). An hourly grid can
  say how high the next high water is and not when, and when is the half anyone
  plans around. There is deliberately **no fallback** from one to the other: a
  surface that silently swapped them would present the worse number in the same
  words as the better one.

## The observed tab's one modelled number

- **The observed tab now carries exactly one modelled number — the tide's next
  turn — and it is labelled everywhere it appears**: a `predicted` tag on the
  card, and a "standing on" row that names the measured level and the predicted
  turn as two claims. Since 2026-09-28 (owner's decision) its HEIGHT carries the
  gauge's measured departure from the prediction over the last 3 days, as the
  Forecast tab's turns do: bare, it contradicted the measured level beside it
  on 15.9% of 245 hourly readings ("rising to" a height already passed), and
  4.5% with it. The measured level itself never takes the departure — the
  departure IS measured minus predicted. The Now/Forecast split is about the reader always knowing
  which chain they are looking at, not about a tab being chemically pure; an
  unlabelled turn would have broken it, a labelled one demonstrates it.

## The LIVE tide's measured rate

- **Beside the LIVE tide's height, its MEASURED rate** (owner's choice,
  2026-11-04: B of a mock of five; `forecast/tiderate.py`, BRIEFING §50):
  the least-squares slope through the gauge's last six samples (30 min),
  ×0.944 to the coast, as the Briefing's arrowhead and "0.9 ft/h
  (0.27 m/h)", or its dash and "slack". **It is the last 30 minutes, never
  "now"**: a trailing fit describes its window's middle, and read as the
  rate at its newest sample its sign disagreed with the prediction's on
  7–9% of readings. Slack when under `SLACK_M_H` (0.10 m/h, 5 cm in the
  window, ~2.3× the 2.2 cm rms between the window's change and the
  prediction's; 29% of readings, the prediction 30%), OR when a predicted
  turn lies inside the window — a line across a high or a low measures no
  direction, and 31 of the 35 readings that ran against the next turn in
  47 days lay within 24 min after one. The 4 left are bay seiches 1–10 h
  from any turn, shown as measured, never overruled; forcing slack BEFORE a
  turn removes none of them and relabels hundreds of moving readings. A
  missing sample in the window is no rate, never a shorter fit. The page
  only shows `motion` / `rate_m_h`; it still never differences the level.
  **With it, LIVE's turn line NAMES the turn** — "next low 1.8 ft (0.53 m)
  at 7:18 AM", tagged predicted — and never says rising or falling, so the
  card's one direction is the measured one (`turnLine`'s `named`). The
  Forecast tab keeps "falling to": nothing measured sits beside it.
- **22 px between the height and the rate** (owner's pick, 2026-11-17,
  handoff group 4 item 7, from 10 px; mocked at 10 / 14 / 18 / 22). A flex
  column gap on the tide's `.val` (`.tide-val`), not the rate's margin, so
  a reading too wide for one line wraps the rate under the height FLUSH
  LEFT: measured, a low below zero in "Both" at 320 px ("−0.8 ft (−0.25 m)
  ▼ 1.2 ft/h (0.37 m/h)") wraps on master indented 10 px and now starts at
  0; a typical reading in "Both" stays on one line at 320–390 px. The
  height is one flex item with its metric inside, so no gap opens inside
  "3.8 ft (1.16 m)"; `top: -1px` stands in for the `vertical-align: 1px`
  a flex item ignores, and the rate's text and arrowhead sit exactly where
  they did, against the height, in both units. A wrapped reading is 42.5 px
  tall, not 47.5: the second line is the rate's own 15 px line.

## 9410170 is inside the bay

- **9410170 is inside the bay; the breaks are not.** The open coast swings
  0.944× as far and leads by ~3 min (measured against La Jolla, and CO-OPS's
  Imperial Beach and Point Loma offsets agree). **The Tide card shows the open
  coast** on both tabs (owner's decision, 2026-09-26): heights ×0.944 on MLLW,
  CO-OPS's own subordinate-station convention, and predicted times 3 min
  earlier; the source line (on LIVE the countdown pill) names the gauge it
  was carried from, the measured reading keeps the gauge's stamp for its
  countdown, and `gauge_height_m`
  keeps the raw value. Breaking uses the MSL form (`tidesite.coast_level`)
  from the gauge's raw reading — never from the card's, or the transfer runs
  twice. And the harmonic prediction is on the 1983–2001
  epoch: the measured level ran ~0.23 m above it in Sept 2026, so the
  forecast carries the last 3 days' measured departure forward — and computes
  no breaking at all without one.

## Wind and tide are not optional

- Wind and tide are not optional at these beaches. KNZY (North Island) for wind,
  NOAA 9410170 (San Diego) for tide. **Both wired in and flowing** as of
  2026-09-18; the spectra archive is filling too. **Tide predictions must span
  the whole forecast window at both ends** — a GFS-Wave cycle is already hours
  old when it publishes, so the forecast starts in the past, and it runs to
  +168 h. Fetching from *now* to +96 h covered 100 of 169 hours and the rest
  read "not collected" (BRIEFING §13).
