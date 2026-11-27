_Read before touching app/forecast.html's tabs, card title rows and provenance pills, charts, past forecast hours, folds and their slide, the page foot, wide layouts, the week strip, the log-first gate, units, or the delivery bundle._

# App surface: tabs, title rows, pills, charts, folds, layouts

Moved verbatim from CLAUDE.md on 2026-11-14 (the context-reduction
restructure); CLAUDE.md keeps the one-line rule and points here.

## Build order 6: the two tabs

6. **App surface — built, `app/forecast.html`, published by
   `forecast/publish.py`.** **Two tabs, and they are two evidence chains
   rather than two views of one.** *Now* is built only from measurements
   (`now.json`: NDBC directional spectrum, KNZY METAR, measured water level);
   *Forecast* only from a model (`forecast.json`: GFS-Wave). The observed
   tab's label reads **“LIVE”**, quotation marks included (owner's call,
   2026-10-01, replacing 2026-09-30's NOW(ISH)): it points at the updating
   feeds, the quotes keep it from claiming the present, and each card's
   countdown is what states how live the reading actually is. Each renders its
   own "standing on" block from whatever keys its file carries, because the
   two name different levels — both on `app/docs.html`, each under its own
   heading and from its own file, beside the "physically derived" caveat and
   the cycle line; it is the live page's one link (it replaced info.html and
   geometry.html, 2026-10-02).

## Title rows and provenance pills

   **Since 2026-11-08 every card's provenance sits in its TITLE ROW**
   (owner's design: option B of five mocked; `headPills`, `headRow`): the
   station pill pinned at the right edge, ONE pill growing out of its LEFT
   end (`.pill-lead`, the joined cut mirrored), and a tap switching that
   pill's text and nothing else -- no highlight, no pressed state. On LIVE
   the left pill is the age and a tap shows the countdown for 5 s
   (`HEAD_TAP_MS`), overdue too: the red dot says overdue and a tap shows the
   red count (owner's call, 2026-11-12, after "Overdue 2 d 12:35:31" pushed
   46086's pills under its name). A buoy's name gives way instead of the
   pills: it ends on an ellipsis and its row never wraps
   (`.chead:has(> .buoy-name)`).
   The dot keeps its 7 px inside a countdown RING with no track (`statusRing`:
   1.5 px of stroke at r 5.25, a 1 px gap of the pill between it and the
   dot, 12 px across; owner's pick 2026-11-10, C of three mocked, from 11 px
   with a 0.5 px gap), the arc the share of the wait left from the
   reading's stamp to due. On Forecast (`modelPills`) the first part is at
   the right with no dot, the second beside it, and a tap switches to the
   third for the same 5 s as LIVE's (owner's request, 2026-11-22; from
   2026-11-08 it stayed until the next tap), and the card's title -- "At
   the buoy" first -- ends on an ellipsis while it shows, as a buoy's name
   does, so the pills never wrap under it
   (`.chead:has(> button.chead-pills:not([data-head-live]))`). 46047's and
   46086's sit above their own headlines with no title beside them, and in
   the wide layouts each Buoys-card column's too, 46232's included (owner's
   call, same day). The space under a title row is the space above the
   card's Charts rule (10 px, box to box). No countdown shows a leading zero:
   "42 s" under a minute, never "0:42" (`hms`). What follows describes the
   pills' content; where it places them under the reading, this supersedes it.
   **Since 2026-11-09 the title row is BALANCED** (owner's pick of a mock of
   header and tab options: "Balanced", H3 + T2 + three tweaks, the pills in
   H1's style): every card title (`.cond > .lbl`, `.chead > .lbl`/`.sublbl`)
   the same capitals at 14 px, bold, in ink; the pills QUIET TEXT -- no
   fills and no joined cut, the age or model in `--faint`, a hairline, the
   station in ink at 500; the fold rows (Origin, Charts, Phase; never the
   Briefing's) in the old title type, 12.5 px grey capitals, so the reading
   is the card's heaviest line; "predicted" / "computed" set as a word on
   the paper grey, 4 px corners; the "LIVE" / Forecast tabs drawn as the
   break tabs are, the pick raised in the card colour with its words in
   `--surf`; and "Briefing" and the Forecast tab's weekday in the title
   type. A lone train of the headline's height dropped its height from the
   same day **until 2026-11-11, when the owner reversed it**: without the
   height the period and heading jumped sideways between break tabs, so
   every train row keeps its height.
   **Each buoy is named above its headline** (owner's request, 2026-11-09;
   `buoyTitle`): NDBC's name without its state, set as the station is
   (12 px, ink, 500) -- 46232's on a line of its own on a phone, where its
   pills are the Swell card's, and on both tabs; 46047's and 46086's, and
   every wide Buoys-card column's, across from their own pills. **Overdue
   is the red dot alone, no ring** (same day). **46047's bank is Tanner
   Bank, singular** (owner's call, same day): NDBC's metadata says "Tanner
   Banks, CA" and keeps saying it in the fetched files and the archived
   Briefing lines; `live.NAME_FIXES` corrects it where the name is read,
   so every name the page and docs show reads "Tanner Bank".
   Each buoy's feed is a pill at the START of its countdown line (owner's
   requests, 2026-10-09, moved there 2026-10-11 from beside the combined
   height, whose headline is now the height alone, as a break's is): "NDBC
   46232 •" (owner's request, 2026-11-06, back from 2026-10-12's "CDIP
   191 •": CDIP runs it, NDBC serves its spectra) and "NDBC 46047 •",
   replacing the "(NDBC <id>)" the name line carried. **The whole
   provenance is ONE line of joined pills** (owner's requests, 2026-10-11
   and -12): "NDBC 46232 • | <age> | <countdown>" (`feedPills`). A first line
   above it, "Point Loma South, CA | <when>" (the place alone, the time with
   no "Observed" or "Measured"; `placeWhen`), is built but switched off by
   `SHOW_PLACE_WHEN` (owner's call, same day: kept so it can come back).
   Each pill after the first grows out of the one before, corners 4 px; the
   LIVE Wind and Tide cards' too — "METAR KNZY • | <age> | <countdown>" and
   "NOAA 9410170 • | …" (their hidden first lines "NAS North Island" and
   "Coronado, CA", `tidesite.SITE_PLACE`, now.json `tide_place`), the dot
   on each card's own countdown; a line too wide for the card wraps a
   pill to start the next row as a pill of its own, in the joined one's
   footprint (`fitPills`), never past the card. 46047's "Open ocean witness" line is
   no longer provenance: words under its rose, above its pills with space
   between. **Each buoy's headline folds like a break's** (owner's request,
   same day; `buoyReading`): its caret and whole line fold out everything
   between it and the provenance -- trains, rose, those words -- closed
   until opened, each buoy its own state, kept across a refresh; selecting
   the Buoys tab opens 46232's (owner's request, 2026-10-13). Every buoy
   is named by NDBC's number (`feedName`); the registry still records
   46232's CDIP number (`stations.json` `cdip`), and nothing shows it. Ink at
   the provenance's 12 px on the picked row's background; 46232's sits under
   every swell tab, the break tabs too, because every break's numbers are
   that one spectrum. Each pill after the first grows out of the one before
   (owner's design, 2026-10-11; `feedPills`): it starts under that pill's
   right end, its left edge cut 2 px outside it (a CSS mask), and the
   countdown's words without the full stop the card's other
   countdowns keep (`dueSpan`'s `bare`). The dot runs on that
   buoy's own countdown instants (`dueInstants`), so it turns exactly when
   "Update due." and "Overdue …" do: green, green fading in and out
   while due (held at half strength under reduced motion), red overdue --
   dark mode's green and red on both themes (`--dot-ok`, `--dot-over`), and
   every card's "Overdue …" in that same red (owner's call, same day).
   LIVE only: the Forecast chain's buoy is a model.
   **The Forecast tab's provenance is the same joined pills, with no dot and
   no countdown** (owner's request, 2026-10-15): swell and the model's wind
   at the buoy "NDBC 46232 | GFS-Wave | Oct 15 at 5:00 AM, 9 h ahead" (the run
   and its lead; one name whatever `wave_source` says), Local "NWS |
   Grid SGX 56,13 | Updated …" (a past hour's from its own build's
   `local_wind_updated_utc` in `46232_shown/`, none where that build kept
   none), Tide "NOAA 9410170 | Harmonic | Departure …" or "No departure"
   ("Gauge departure" measured 358 px against the card's 330 at a 390 px
   phone; "Departure" 321). The hour is the seek bar's, no longer a
   "Forecast for" line. **KNZY never stands in on the Forecast tab** (owner's
   call, same day): it is not a forecast. A missing model wind reads "not
   collected yet" (under a past hour "no model wind for this hour", owner's
   wording), a missing NWS hour "no local forecast" and why.

## The Forecast tab's past hours, and the charts (Swell, Wind, Tide)

   **The Forecast tab reaches 48 h back** (owner's decision, 2026-09-26). For a
   past hour it shows what the page showed then: the newest run published
   before that hour, from `forecast.json`'s `past`, read back from the
   permanent log — **the full card, drawing and calculation table included**,
   from that build's own hour as it was published (`46232_shown/`). A past
   hour whose build kept only a headline says "The calculation for this hour
   was not kept" rather than borrowing another build's detail. Under it, in
   blue, is the measured chain rebuilt for that hour (`measured.json`). It opens on the first hour not yet passed, never
   one that has. **Under each Now card are the hourly charts** (owner's
   requests, 2026-09-27; `forecast/series.py`), in the owner's order
   (2026-10-05): Height, Window (ratio), **Origins** (owner's request, 2026-10-03;
   below) and North vs. South (north less south) — the 24 h %K view taken off
   the menu the same day by the owner's call, its spec (`buildSpec`'s
   "range") and `series.py`'s pct_k / pct_d kept so it can return — switched above the plot, folded out from an
   "Charts" line with the calculation's caret (closed until opened) — the
   last line on every card, below the provenance and under the card's one
   rule; the provenance has space above it, no rule (owner's calls,
   2026-10-02). **Each tab plots its own line in ink** — the break
   on a break's tab, the buoy on the buoy's (owner's call, 2026-09-28, after
   a round of per-break colours was rolled back). **Height alone draws the
   other two breaks under it** (owner's request, 2026-10-05), lighter and
   thinner in `--faint`, north to south, the second dashed — greys and a
   dash, never per-break colours — so the three compare at a glance on one
   axis; the readout names all three, the tab's own first. The buoy's tab and
   every other view keep one line. The Window chart carries a
   direction strip under it on the same hours: a dot an hour where the
   buoy's peak came from, never joined (the peak jumps between trains), over
   the break's open windows shaded. It says where the peak sits, never
   "inside" or "outside": the share is the whole spectrum through the
   windows, and a binary test on one bearing is what BRIEFING §10 retired.
   The readout sits against the plot and grows upward as it wraps, in room
   kept for three lines so a reading that wraps while scrubbing never moves
   the plot. The x axis zooms and pans — pinch, drag, ctrl + wheel, and
   1D / 7D / 1M / All — and a sideways swipe reads the hours under the finger
   into a readout ABOVE the plot, keeping the last on release; a vertical
   swipe still scrolls the page. It opens on the last day (owner's choice;
   the chart is picked from a menu, not tabs); the week is `series.json`, rebuilt
   each collection, ~37 s; past it, the committed archive (`series_all.json`
   from `data/series/`, fetched only when asked for). It is the observed
   chain; every past hour is REBUILT with today's chain, not
   remembered, and docs.html says so; a missing hour is a gap in the line at
   every zoom. **The Forecast tab has its own charts in the same place**
   (owner's request, 2026-09-29): the model's 3-hourly hours from 48 h back
   to the run's end, drawn from `forecast.json` (`fcSteps`), never from the
   Now series. Three views (owner's call, 2026-09-30, which folded the old
   "Forecast & observed" into the runs view): *Forecast + Observed* (the
   newest GFS-Wave run over the last eight runs' lines from
   `forecast.json`'s `runs`, `forecastlog.recent_runs`, with 46232 carried
   in beside the passed hours in blue), *Swell trains*
   (a dot per train at its period, sized by height, with a direction strip
   over the break's windows) and *North vs. South*; and on the buoy's tab
   only, *Ensemble* (below, build order 5). **Only the Ensemble view carries
   a band, and only beside the measured share of hours 46232 fell inside it;
   none shows a forecast-minus-observed difference**: nothing measures the
   breaks, and a run spread is not a range the swell will fall in — the page
   says so. The two tabs keep their own window, picked hour and
   view (`useChain`). **The Wind and Tide cards have charts too** (owner's
   request, 2026-09-30; `forecast/windtide.py` → `windtide.json`), sharing
   the tab's window and picked hour. On Now, what was MEASURED each hour:
   KNZY's report taken in the hour up to it — never carried into the next,
   unlike `measured`'s two-hour as-of, because a carried reading draws as a
   second measurement, and the newest report's slot added as soon as the
   report lands (2026-10-16: the :52 METAR's hour had no slot until the
   clock reached it, and the chart sat a report behind the card) — and the
   gauge's sample AT the hour on the open coast;
   plus the tide's next 24 h of harmonic prediction with the departure,
   dashed, the tab's one modelled line beside its one modelled number. On
   Forecast, `forecast.json`'s `hourly` (the NWS local wind, and the card's
   tide) to the run's end, the measured hours in blue, and GFS-Wave's own
   buoy wind in grey (owner's request, same day) — hourly to +120 h and
   3-hourly after, so its line `bridge`s the model's own spacing, never a
   measured gap. Read from the archives, not rebuilt: today's chain cannot
   change a past hour. Each has a second view (owner's request, 2026-10-01):
   *Shore direction* (owner's name) — per hour of the reader's day, over
   every day counted, how often the wind at the open swell tab's break was
   offshore / cross / onshore / calm, by the card's own `sense()` against
   that break's normal over KNZY's hours, in greys only, the readout saying
   "over N days" because a bar is many days' one reading, not one hour's —
   and *Departure* — the gauge's measured-less-predicted each hour and the
   trailing 3-day mean the forecast adds (`windtide`'s `departure_m` /
   `departure_mean_m`, coast-scaled like the card's). **Those two are the
   LIVE tab's only** (owner's call, 2026-10-02): on Forecast a "how often"
   over a week's forecast threw away which day, and a measured departure has
   no future hours. Forecast's second views are *Shore direction* as a week
   grid (a row a day, a square an hour, the NWS verdict at the open break)
   and *Daily range* (each day's biggest swing between CONSECUTIVE predicted
   turns, from `tide_turns` — never the calendar day's highest high less
   lowest low, which dropped a lower low that had crossed midnight and drew
   a false neap). **A wind of 3 kt or less is "light", not offshore** (owner's
   report, 2026-10-02: the NWS grid's 2–5 kt northerly every night painted
   the week grid 100% offshore 11 PM–10 AM, where KNZY over the same hours
   was calm or variable 29% and ≤ 3 kt 44%). `LIGHT_KT`, Beaufort force 1,
   lives in the page's one `sense()`, so the card's line and both Shore
   direction charts change together. **The card still names a light wind's
   side** ("light offshore", "light cross-shore", "light onshore"; owner's
   request, 2026-10-07) while the charts count it as light or variable, and
   **0 kt is "calm"**: KNZY's `00000KT` is archived as 0° at 0 kt, and the
   card says Calm rather than "N 0°"; a METAR's `VRB` (a speed, no
   direction) reads "Variable at …", never "not collected" — both
   capitalised in the headline (owner's request, 2026-10-15). Neither has a
   side, so the break's line says why instead of repeating the headline:
   "**no wind**, so no side set" and "**no direction**, so no side set"
   (owner's wording, same day). The Tide view is shaded by night on both tabs
   (`forecast/daylight.py`: NOAA's solar equations at the center break from
   spots.json, within a minute of `astral`; `nights` in both payloads).

## Chart descriptions, refresh, the delivery repository, vocabulary

   **No chart carries a description under it** (owner's call, same day):
   what each draws lives on `docs.html` and in the plot's spoken label. The
   one line kept is the Ensemble's measured coverage, because the band is
   drawn only beside it. Opens on Now;
   a refresh keeps the tabs the reader chose (sessionStorage, so a new visit
   still opens on Now); a stale or missing observation
   says so and points at Forecast rather than falling back silently. The
   delivery repository is separate because `data/live/` is gitignored here, so
   there is nothing at `data/live/forecast.json` for a published page to fetch —
   not, as this said until 2026-09-25, because this repository is private. It
   has been public since the Actions-limit switch, and the split survived that
   change for its other reasons. The forecast workflow builds a flat bundle (`index.html` +
   3-hourly `forecast.json` + `.nojekyll` + README) and pushes it to the
   **public** `nado-waves-forecast`, the same pattern `nado-waves-log` uses for
   the observer form. **This repository stays the system of record; nothing is
   edited on the far side.** Kept separate from the log repository on purpose:
   the log never shows a forecast, and a sibling path on the same Pages site is
   one URL edit away. Note that is a separation of paths, not of origins —
   `*.github.io` project sites share one origin, so it is not a browser
   boundary.
   Publishes the swell-side
   window only (BRIEFING §12), no ratio and no confidence badge — a ratio
   against the smallest of three is circular when all three are on screen.
   States all four levels
   (geometry / model / calibration / observation) on screen — on
   `docs.html`, one tap from the live page — not just in the README. **Coronado's three breaks only, by decision (2026-09-18).** Breakers
   and Gator are out of the forecast and the app. They are not equivalent to
   Coronado north and south — measured, they differ on 17.6% and 13.5% of
   archive swell hours — but they are the two spots still standing on estimated
   coordinates, so nothing trustworthy was dropped.
   `tests/test_app_surface.py` enforces the vocabulary: the page may not use
   the words an accuracy claim would need.

## Every fold slides

   **Every other fold slides the same way** (owner's settings, 2026-11-01,
   from a mock built on the real page's rendered DOM; `slideFolds`,
   `FOLD_SLIDE`): the calculation, the swell's and the Wind and Tide cards'
   Charts, Origin, the tide's Phase, each buoy's headline and an alert's NWS
   headline (the Briefing's and the Forecast tab's) — 240 ms, the same
   easing, NO RISE, and none of the Briefing's fade at its foot or reach
   below (owner's call). One helper, each fold's open state and storage
   untouched: it grows from its bottom edge, its top padding kept, and shut
   a negative bottom margin takes back its gap in the parent, so the last
   frame is the closed page; every length on one easing, so what lies below
   moves one way only. Checked in Chromium by freezing each slide at 21
   points both ways and tracking the next element's top: monotonic, and
   ending exactly on the closed and open page for all nine folds and the
   Briefing at 390 and 800 px (the Briefing's Swell card 126.5 → 482.5 px).
   With no rise nothing passes a fold's line, so it has no ink clip; if a
   rise comes back, so must one — measured at rest at 390 px, the first ink
   sits 8.5 px into the calculation, 5.5 into Origin, 4 into the Phase, 7.5
   into a buoy's fold, 3.5 into the NWS headline and 0 into the Charts, and
   a clip edge between device pixels antialiases a row nearer (snap it to
   the device grid). What a fold draws on opening (`refitCharts` on a
   tablet, `roseShown`) is drawn before it is measured; a tap mid-slide
   turns it back from where it is; a redraw mid-slide rebuilds the fold in
   its open state. On every layout, the stack and console too (owner's call,
   2026-11-01), where one caret opens all three calculations and
   `alignCols` holds their rows level: min-height moves with the height (its
   min-height would hold a closing fold open), the rows are lined up before
   the folds are measured and again as they land, and `alignCols` never
   reads a height mid-slide — the three columns level in every frozen frame
   at 1000 and 1300 px, after turns mid-slide and a redraw. Every fold ends
   exactly on the closed and open page there too. Never under reduced
   motion; a fold in a hidden tab flips at once. The Briefing still does not
   slide wide: it has no caret there. No WebKit in a session: unchecked on the
   owner's iPhone, and it uses only height, padding, margin and opacity
   through the Web Animations API, which the Briefing's slide already runs
   there.

## The foot of the page, wide layouts, the week strip, the log-first gate

   **The foot of the page** (owner's design, 2026-10-28): ONE line,
   "Docs | Observer | Units [Imperial] | ◐" (Observer HIDDEN since 2026-11-11,
   its bar with it, "just for now", owner's call; the gate still reads the
   stored choice), spread over the Briefing line's
   width (at most a phone's 560 px on a tablet or a stack layout, owner's
   call 2026-10-30; the console's sits in its rail), Docs under its words and the glyph's ink under its
   caret's, with no rule above (owner's calls, 2026-10-29) — Docs in ink at the line's
   weight, Observer the gate's checkbox drawn as a switch, Units a bordered
   chip that shows its setting and cycles Imperial → Metric → Both on a tap
   (its word centred cap-to-baseline in the chip, measured at 4x; always as
   wide as "Imperial", so a tap never moves the line), and the theme a
   half-lit disc at the right end: a tap gives the other theme, and landing
   on the phone's own forgets the choice. Below 370 px the bars drop and the
   gaps close, keeping one line at 320. The theme is applied before the
   first paint by a script at the top of the page (docs.html too, which
   follows the same saved choice) and sets `color-scheme` with it.
   **Wider than a phone** (owner's decision, 2026-10-29: option B,
   "Console", of three put to the owner, with the owner's picks on each
   fold): the script sets the root's `data-layout` from `LAYOUTS` and every
   wide rule is keyed to it, never to a width of its own. **The phone page
   (< 700 px) is untouched**, and that was checked, not assumed: a layout
   dump of every element at 320–698 px on both tabs, folds open and closed,
   equal to master's, and pixels equal at 320–414. *tablet* (700–949) keeps
   the tabs, Wind and Tide side by side. *stack* (950–1279) and *console*
   (1280 up) are other markup (`swellWide`), redrawn on crossing a width:
   the three breaks as columns NORTH TO SOUTH, never ranked (a column's
   place is its break's), each column's headline, calculation rows (by
   step name), trains and measured line held level by `alignCols`, one
   caret opening all three calculations; the buoys a card of their own,
   three across; Origin ONE block for the beach (`beachOrigin`): each
   entry exactly as a break's fold words it, once, under the breaks that
   show it, so nothing is reworded and an entry that differs by train or
   period is two; the swell's charts a card of their own with the break
   picked above the plot (`selectSwellTab` picks only that, there), and
   every chart drawn at its own width (`chartDims`: 320 units on a phone,
   its CSS pixels wider, so the text stays the phone's size) with a
   full-screen button (`setChartMax`, Escape closes); the Wind card every
   break's rose and verdict, each naming its break (tide_wind_sun.md, "The
   Wind card's rose"), and the Sun card every break's
   sunset. Console adds a rail: the tabs, the Briefing ALWAYS OPEN with no
   caret, then Wind, Tide and Sun, the main column one grid item spanning
   every row (`grid-template-rows: repeat(14, auto) 1fr`) so the rail
   stacks on its own. On a wide screen the Briefing's dot marks an update
   the reader has not been AT THE PAGE for (owner's call): it goes at their
   next touch, click, key or scroll (`briefTouched`), not when drawn.
   docs.html: its tables and worked math wider than the reading column
   grow to fit, centred, up to 64rem, from 1100 px; the owner's contents
   pill (same day) is the page's navigation, so no second one was added.
   **The week strip** (owner's request, 2026-10-30, version C of three
   mocked; `weekCard`): on the Forecast tab only, above the Swell card (a
   card of its own on a phone or tablet, the main column's first wider), a
   cell a day and a break, the range of breaking heights over the day's
   DAYLIGHT steps -- sunrise to sunset at the center break from
   forecast.json's `sun` (6 AM–6 PM only for a day without it; the mock
   said 6–6, and the 5 PM step is after dark in winter) -- floored and
   ceiled to whole feet as the Briefing's headline range is (`feetRange`,
   from the heights as the cards show them), the cards' own
   heights (`cardsForForecast`), past hours as shown then. A day picks its
   biggest break's biggest daylight hour, a cell its own break's
   (`weekBest`, the earlier on a tie), through the picker's `choose`, and
   the strip follows the picker. On a phone a carousel under ONE fixed
   outline round the three cells, snapping a day at a time
   (`scroll-snap-stop: always`), the days off it smaller and fainter, the
   day that settles there picked -- never under a finger (`WEEK_TOUCH`); a
   tap on a day beside it slides it in, then picks. Wider, every day in a
   row, the outline on the picked one. **Every day the hour picker offers
   has a column, with the range the page showed** (owner's call,
   2026-11-01, after Thursday vanished: the 48 h started at its 8 PM, after
   its daylight): forecast.json's `day_before` is the earliest day's hours
   from its midnight to the window, by `past_hours`' own rule, each break's
   headline only, counted in that day's range and never offered; a day
   with no daylight hour left to offer picks its first offered hour. The phone's Forecast tab was checked
   to change by that card alone: every other element as master's, moved
   down by its height. **Back to the opening hour** (owner's request and
   choice, 2026-10-31: C2 of six mocked versions of a clock turning back,
   drawn at a 1.4 stroke; `weekBack`): a chip in the Week label's row over
   the opening hour's day (`firstUpcoming`), there whenever the cards are
   on any other hour however the reader got there, on every layout; on a
   phone it rides with that day IN THE STRIP'S OWN SCROLL AREA (a row above
   the days, lifted into the label's line by `--wk-lift`), sticky at the
   strip's edges, so the browser moves it with the days in the same frame
   (owner's report, 2026-11-01: placed by script after each scroll it
   trailed them; measured since, 0 px apart on every frame), that row as
   wide as the days by arithmetic (`--wk-n`), never max-content, which
   Safari can size from the days' text alone and so end the row, and the
   button with it, by the third day (owner's report, same day); wider, in
   its day's column. A tap restores the UNPICKED state (`CHOSEN = null`, so
   it moves on as hours pass) and slides the day back under the outline;
   nothing is picked during that slide (`WEEK_SLIDING`: restoring the
   strip's old position fires a scroll end mid-slide). The chip is the map
   buttons' size (owner's request, 2026-11-21; it was 28 × 22): 28 px
   square, its glyph 16 px at a 1.4 stroke as the Layers button's, still
   centred on the label's line, `--wk-lift` raised 28 → 30 px so the
   carousel's scroll area holds its top; the days do not move.
   **Heat** (owner's request, 2026-11-21; the ramp is the owner's own, made
   in the mock's editor, and of the mock's choices the owner took *smooth by
   peak* and *no key*; `weekHeat`): each height box is coloured by its
   break's daylight PEAK as the cards show it, to the tenth of a foot, on a
   FIXED scale, so a height is the same colour every week (a week-relative
   scale was mocked and not taken: it paints a flat week's biggest day the
   hottest colour). Seven stops (`--wk-heat0`–`6` at `WEEK_HEAT_FT`, 1.0 to
   8.0 ft: mint, green, yellow, amber, salmon, magenta, blue), mixed in
   OKLab between the two either side; the first stop's colour below 1 ft,
   the last's above 8. The same colours on both themes, with dark text on
   every one (`--wk-heat-ink`, the light theme's ink and the dark theme's
   paper; 5.0:1 at the least, mixes included, pinned by test). A past
   day's boxes are mixed 35% toward the paper, its words faint as before.
   Size only, never a rating: wind, period and tide stay out of it. What
   was measured and put to the owner before the choice (2026-11-21): the
   ramp runs by hue, not by lightness (1, 3 and 4 ft are about equally
   light), so the order is learnt, and red-green colour-blind readers will
   find the 1–5 ft stops hard to tell apart; the 8 ft stop (hue 261° in
   OKLCH) sits near the measured blue (250–256°), seldom reached (the
   October–November daylight peaks topped out at 5.8 ft); its first stops
   share the status dot's green hue. A key under the strip was mocked and
   left off, so docs.html's week strip section says what the colours mean
   (owner's call, same day).
   **The log-first gate** (owner's call, 2026-10-16): "Wave observer", the
   Observer switch, kept in localStorage (with the Briefing's last opened
   update and the Units and theme settings, its only uses, pinned). On such a device the page opens on "Logging the beach today?"
   and nothing else until today's log is done or declined; it returns at
   Coronado's midnight, and ticking it after looking starts it tomorrow.
   That question is the ONE place the page links to the log; docs.html
   still never does.

## Imperial leads, metric in parentheses

- **Imperial leads, metric in parentheses, everywhere a number is shown
  in "Both".** "2.3 ft (0.71 m)", "9 mph (8 kt)". Since 2026-10-28 (owner's
  call) the reader's Units setting at the foot of the page can show
  Imperial or Metric alone instead, and since 2026-11-11 Imperial alone is
  the DEFAULT, a tap moving Imperial → Metric → Both (owner's call): every number goes through the page's
  one `dual` / `dualText` (beside the constants), a metric value alone is
  the "both" form's bracket and never a second rounding, wind's metric stays
  knots (owner's call, same day), and the chart axes and the rose's rings
  step in metric units on Metric. docs.html keeps both throughout: its
  worked numbers are checked against each other. Python's report strings
  (`forecast/units.py`) are not the page and keep both. **Nothing upstream of a display converts**:
  the JSON, the transform and the collectors stay in metres and knots, because
  that is what NDBC and WAVEWATCH III publish and putting a unit change between
  the source and every cross-check is how a 3.28 ends up somewhere it should
  not be. `forecast/units.py` and the three constants at the top of
  `app/forecast.html` (feet, mph, and since 2026-10-02 miles, for Origin) are
  the only places the conversion happens; a test pins that each factor
  appears exactly once.

## The line under a past forecast hour

- **The line under a past forecast hour says when it was observed, never
  "what happened".** Blue, in a 1 px outline at the card's radius, and
  labelled "Observed at 8:00 AM" (the tide's "Measured at 8:00 AM") — owner's
  wording and style, 2026-09-27. Every measured element on the Forecast tab is
  `--measured`: the selected tab's blue, `var(--surf)`, on both themes
  (owner's call, 2026-10-09, after red from 2026-10-02 and sea green before;
  5.4:1 light, 7.0:1 dark), so the Ensemble's mean and band went grey. Under
  a past hour KNZY's observed wind sits under the Local forecast, not under
  GFS-Wave's wind at the buoy (same day): both are the wind on the sand. Where it comes from is said on `docs.html`:
  46232's spectrum at that hour, through identical windows, seabed and surf
  zone, so its difference from the forecast is the MODEL's error at the buoy,
  carried in, with any physics error cancelled out. It checks nothing at the
  beach. No difference or percentage goes on screen: that would be a claim
  about the forecast without a verification series named beside it. A
  missing spectrum is a gap, never the hour beside it, and the newest hour
  reads "not in yet" until a later spectrum has passed it
  (`tests/test_app_surface.py` keeps "actual" off the page).

## Refresh and redraw

   **A refresh the reader makes opens at the top; the page's own redraws
   are invisible where the reader is** (owner's call, 2026-11-15).
   `history.scrollRestoration = "manual"`: the cards arrive after the
   browser's restoration gives up, which had put the reader somewhere
   between, differently in each browser. And `show()` is `holdPlace` round
   `drawPage`: the element in view that a redraw can find again (an id, or a
   card's data-card) keeps its place on screen, right after the redraw and
   on the next two frames as charts settle, unless the reader scrolls
   meanwhile. iPhone has no scroll anchoring; measured with it off and on,
   120 px added above the reader moved nothing, with no double correction.

## The Swell card's tabs box and tray (LIVE, phone)

   **Since 2026-11-27 the LIVE Swell card on a phone is headline, tabs box,
   tray** (owner's design and calls, same day; branch
   claude/swell-card-redesign-acrmw7, mocked on the branch's own page with
   that day's published data before merging):

   - **The Briefing's swell block is the card's headline** (`swellBrief`),
     under its title row: the range, the 24 h sparkline, a line a train,
     the 46047 offshore lines and the dark-buoy line, the same rows
     `briefSwellRow` draws, from briefing.json, never a second rendering
     (BRIEFING §44; the block is rebuilt every collection, so it matches the
     tabs under it). The Briefing fold on a phone goes from the alerts to the
     tides; its line, changes and record are unchanged. A wide screen still
     shows the block in the Briefing until that layout is redone.
   - **Each tab carries its own height under its name** (`tabHeight`): a
     break's breaking height, `hsWindow`, to the tenth of a foot as its
     headline; the Buoys tab 46232's combined height, the anchor every
     break's numbers come from. In "Both" the metric is a grey line of its
     own under the feet (four tabs share a 330 px box). Greyed with the
     headline by `c.aged` / the buoy's age; a dash with no spectrum.
   - **The tabs box folds out a tray** (`.tabbox`, `#swell-tray`,
     `TRAY_OPEN`): the box's hairline and paper round the tabs and a caret
     under them, the tray on the card's colour beneath, its full width.
     Closed on every load and kept across a redraw. The caret, or the
     picked tab tapped again, opens and shuts it with the folds' slide
     (`slideFolds`); picking another tab leaves it as it was.
   - **The tray holds what the picked tab showed before**: a break's
     headline, whose caret still folds the calculation, its trains and its
     map, all at one level; the map edge to edge across the tray (328 px
     inside the box's hairline at 390, the width it had), its caption the
     box's foot. The Buoys tab's whole pane, every buoy's rose and station
     block the tray's width too (owner's call, same day), and 46086's and
     46047's blocks. Origin and Charts stay below the box.
   - **The box's spacing** (owner's call, same day): as far from the
     headline above it and the Origin rule below it as the range's ink sits
     under the title's, 17.5 px painted at 390 each, measured in pixels with
     the tray shut and open (`.swell-brief` 6 px and `.tabbox` 7.5 px of
     margin on the card's 8 px gap; it was 13.5 above, 10 below).
   - **Each buoy's rose and station block are ONE plate in the tray**
     (owner's calls, same day): no card between them, a hairline across
     them on the words' 11 px, spaced as the rule between Origin and Charts
     paints (17.3 px from the ink above, 16.2 to the ink below, at 390;
     the plate measures 17.2 / 15.8). The last buoy's block, open, is the
     box's foot, as the map's caption is on a break. An open buoy's block
     is the rule above the next buoy (owner's call, same day): pulled down
     by its margin so its foot's hairline lies on that rule (31 and 21 px of
     card sat above it), the next name 11 px under it as under the rule; a
     margin, not a hidden rule, so a fold's slide never jumps.
   - The tray's caret sits 5 px further from the tabs (owner's call, same
     day): its ink 12.5 px under the tab buttons, and above the box's foot
     (or the open tray) a little less than the tab names' ink sits under
     the box's top edge, which reads as equal: 14.4 px against 15.3 painted
     at 390 (owner's calls, same day; it was 8, then 15.4, which read large),
     and 12.7 against 13.3 once the names were centred by their ink (below),
     Both's names 3 px higher and its caret likewise.
   - **Each tab's name and height are centred by their ink** (owner's
     call, same day): the caps' line box carries empty leading under them,
     so they sat 12.3 / 8.9 px of tab above and below their ink (12.3 / 6.2
     in Both, the bracket's line under them); now 10.3 / 10.9 and 9.3 / 9.1,
     pixel-snapped at 2x, the tab's height unchanged. The open tab's lone
     name likewise, by `--tab-shift` measured (9.4 / 17.15 px): 19.8 / 19.9
     and 26.3 / 26.6.
   - **The tray's first ink about 17.5 px under its edge** (owner's call,
     same day; it was 12.6 on a break): 17.3 on a break, 17.4 in Both,
     17.3 on the Buoys tab, the card's rhythm round the box. **The Buoys tab
     keeps it** (owner's call, same day): 17.5 px painted above and below
     each buoy's name and under its height line, to the trains or the next
     rule (it was 14.9-15.4 above a context buoy's name, 18.5 under every
     name, 24.0 to the trains, 27.1 under 46232 shut); 16.9-17.9 measured at
     2x, one 18.5 a device pixel of snapping under an open plate.
   - **A tab name's O and U stand a little apart** (owner's call, same
     day, replacing a 6% scale of the picked name, which answered the wrong
     question): every name is 14 px with 10 px of caps painted, and SOUTH
     read smaller because Barlow Condensed sets O and U as close as its
     straight letters (1.7-2.0 px painted), so the round letters look
     squeezed. Each O and U is a span (`tabLetters`, `.tab-ou`) with 0.05 em
     more before it and 0.04 after (owner's calls, same day: 0.06 each side
     read loose, then UT, OR and OY at 0.05), and 0.04 em between an O and a
     U side by side, not twice the side's (0.03 read tight). Pairs that still
     read uneven are moved by eye in `TAB_KERN`, em before the second letter:
     CENTER's EN and BUOYS' YS +0.01, BUOYS' OY -0.02 (owner's calls, same
     day; -0.01 read a hair wide).
   - A buoy's fold spans the tray with its contents padded back in: the
     folds' slide clips a moving fold (`.fold-moving`), and a rose or plate
     reaching past it showed its sides only once the slide had ended
     (owner's report, same day).
   - **46232's pills move to Point Loma South's line only while the tray
     is open** (owner's calls, same day): on the Buoys tab with the tray
     shut they stay in the title row (they had vanished into the shut
     tray). `data-tray-open` is set and cleared as the tray STARTS to open
     or shut (once the slide ended, the move read as late), and drawn in by
     a redraw while open.
   - **The picked tab drops its height while the tray is open** (owner's
     call, same day: the tray's headline repeats it): the name slides to
     the tab's middle on the fold's ease (`--tab-shift`, by its ink, above),
     and the height slides down WITH it, out of the tab (clipped), fading in
     120 ms; back over the fold's 240. A fade alone left the height under
     the name (owner's report, same day): the ease moves the name 40% of
     its way in 10 ms. Sampled frame by frame, the 1 px between them holds
     opening and shutting. Picking another tab with the tray open swaps
     them the same way.
   - **No grey tap flash anywhere on the page** (owner's call, same day):
     WebKit's default highlight spilled past the tray's caret onto the tabs.
     One `html` rule replaces the sixteen per-element opt-outs; every
     control answers a tap by changing state, keyboard focus keeps its
     outlines. docs.html and the beach log pages are unchanged.
   - **The range's sparkline is 112 x 28** (owner's pick of three options,
     same day; it was the Briefing's 64 x 18): as tall as the range's
     29.7 px line allows, drawn at that size so its line and dot keep their
     weight (`briefSpark`'s `w` / `h`). The 64 x 18 is drawn beside it and
     shown instead under 361 px, or wherever the range would wrap beside
     the big one (`fitSwellSpark`): measured, "10–14 ft (3.0–4.3 m)" in
     Both does at 390 and 375, today's "3–7 ft (0.9–2.1 m)" does not.
   - The Forecast tab's card is the same on a phone since the same day
     (below); the wide layouts are unchanged for now (docs/handoff.md item
     29).

## The Forecast tab's Swell card (phone)

   **Since 2026-11-27 the Forecast tab's Swell card on a phone is LIVE's:
   headline, tabs box, tray** (owner's design and picks, same day, docs/
   handoff.md item 28; mocked as an artifact on that day's published run
   with a switcher for the options, before building):

   - **The same tabs box and tray** (`tray: true` on the Forecast call):
     every rule in the section above holds unchanged. A break tab's height
     is its card's `hsWindow`, the Buoys tab's the model's combined height
     at 46232 (a dash for an hour with no spectral product). The box sits
     17.5 px under the headline's ink and over the Charts rule (there is no
     Origin on this tab), painted at 390 with the tray shut and open and on
     the Buoys tab. Its last line never has a descender -- no trend word, so
     no "g" -- which painted 20.5 px against LIVE's 18.0 on the same day, so
     `.swell-brief.fc` has 2.5 px less margin.
   - **Its headline is its own, from forecast.json alone**
     (`fcSwellBrief`): the Forecast chain never borrows a measurement, so
     it is NOT the Briefing's block and has no 46047 lines and no dark-buoy
     line. At the picked hour: the range over the three cards' breaking
     heights as they show them (`feetRange`, LIVE's rounding); a sparkline
     of the biggest break each step over the **24 h FROM the picked hour**,
     its dot on that hour, "next 24 h" beside it (owner's pick of four: 24 h
     to the hour, 12 h either side, 24 h on, the whole run), the 112 x 28 and
     64 x 18 pair `fitSwellSpark` chooses between; then a line a train by
     the Briefing's rule (`fcSwellTrains`, `briefing.listed_trains` on the
     cards' rows, one line a model buoy train, `swell`). The sparkline's
     steps are the picker's (3 h apart), a gap a missing step; past hours
     are the log's, as the page showed them; near the run's end the line
     stops where the run does.
   - **No trend word** (owner's pick, same day, of none, LIVE's 3 h back,
     and 3 h on). Mocked from the model's rose at 46232 -- the train's buoy
     train's 22.5° sector and period band, LIVE's thresholds -- it moved
     between all four words over most of 28 Nov on one run, and nothing
     follows a train between model hours; how often each would fire was
     never measured.
   - **Two lines whose words match are one** (owner's call, same day): at
     28 Nov 03Z two buoy trains each surfaced as a W 19.0 s row (Center's
     one row, peaking at 19.0 s, was credited to the 12.7 s buoy train), so
     the rule printed "W at 19.0 s" twice and left the 12.7 s swell unsaid.
     On that run identical words came on 1 hour of 57; a row with other
     words went unsaid on 51, mostly the same swell at another break (W /
     WSW 16.6 s), some another swell (SW 12.7 s under "W at 13.6 s", 27 Nov
     15-21Z). What a line stands for, on both tabs, is docs/handoff.md
     item 30. LIVE is unchanged.
   - `briefSpark` takes `start` and `dot` (the window from an hour, the dot
     on a reading) for it; every other sparkline draws as before.
