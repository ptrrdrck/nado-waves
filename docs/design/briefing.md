_Read before touching the Briefing: its line, changes, swell / tides / conditions / water quality blocks, its record._

# The Briefing

Moved verbatim from CLAUDE.md on 2026-11-14 (the context-reduction
restructure); CLAUDE.md keeps the one-line rule and points here.

## The Briefing

   **The Briefing** (owner's request, 2026-10-16; reshaped 2026-10-17 and
   again 2026-10-22; `forecast/briefing.py`): a short read in a fold on the
   BACKDROP above the LIVE cards, not a card, closed until opened (open, at
   most half the screen, scrolling inside itself, its scroll carrying on to
   the page at either end — a swipe down at its top reaches the page so
   pull-to-refresh works from inside it, one up at its bottom scrolls on
   down the page; owner's requests, 2026-10-23 and -24; and a redraw keeps
   the reader's place in it, `BRIEF_SCROLL`, owner's request, 2026-10-24).
   Open, it reaches across the 18 px gap above the Swell card to that
   card's top edge, and while more lies below, its last 44 px fade out
   there, a hint that it scrolls (cleared at the end of its scroll,
   `briefEdges`); it takes that gap back, so the cards sit where they did.
   It slides open and shut (`slideBrief`; owner's settings 2026-10-31, from
   a mock): 240 ms, a quick start and a soft stop, its contents fading in
   place (they rose a third of its height as they faded until 2026-11-01,
   the owner's call), growing and shrinking from its bottom
   edge only. Nothing in it is ever drawn nearer the line than its first
   line's ink at rest, sliding OR scrolled (owner's reports, same day): its
   own top edge is a clip `--brief-ink` into its contents, 23 px below the
   line's text with or without an alert, measured in painted pixels frozen
   mid-close and scrolled 0–35 px. No slide under reduced motion or on a
   wide screen.

## The Briefing, continued (after the fold-slide paragraph, now in app_surface.md)

   A tapped row's detail that folds out below what it shows scrolls into
   view (`briefReveal`; owner's request, same day, after the South water
   row's line opened out of sight): clear of the fade, or to its new end,
   where the fade clears; smoothly, unless reduced motion.
   Its line
   reads "Briefing surf up, new W offshore" with "9:16 PM" (the day too
   when not today's) APART AT ITS RIGHT END, against the caret, the unread
   dot after it, and no comma before it (owner's request and settings,
   2026-11-02, from a mock: the time's box 6 px from the caret's 32 px tap
   target, never in it, at least 12 px after the changes, `--caret-gap` /
   `--when-gap`; once read the dot goes and the time closes up). **The
   Forecast tab's hour line matches**: "Monday Nov 2 ⌄" (no comma, the caret
   by the date), the time in the date's grey at the right, its ink as far
   from ‹ as LIVE's dot from its caret (17.5 px), the select still over the
   whole row; the date as far from the weekday as the changes from
   "Briefing" (4.91 px). The short weekday now runs to 348 px: "Wednesday
   Dec 30 ⌄ 12:00 AM", the year's widest, needs 224.2 px of a row that
   takes 124. The line says WHAT THE UPDATE CHANGED (owner's copy, 2026-11-01;
   `briefing.changes`, kept with each update as `changes` so the record
   can be filtered by kind), in `SHOWN`'s order, as many as fit on one
   line (`fitBriefLine`, measured, through the pure `briefFit` the wording
   docs run with a character budget): one too long for what is left is
   PASSED OVER for later, shorter ones that fit, and when none fits whole
   the first starts on the line and breaks at its last space that fits,
   never after "now", "at", "new" or "&" unless no other break fits ("new…"
   over "…alert", owner's call, same day), on a bare ellipsis, "Briefing SW
   now SSW…" over "…at 15.4 s building" (owner's request, 2026-11-02,
   after "Briefing …" sat over the whole change); too many, it breaks off
   on an ellipsis CLOSED UP to its comma, "Briefing surf up, SW building,…", and
   the open fold's first line carries the rest on, "…tide height, today's
   tides" (owner's design and calls, 2026-11-02, replacing "+N";
   `fillBriefCont`), level with the changes (measured), there only when
   the line broke off and the fold is open (always, wide, while needed),
   outside the scrolling body, whose top-edge clip would cut it, its text
   one line below the line's as a wrapped line's, and the first ink below
   it as far as below the line without it (22.87 px at 390, measured). It
   comes and goes on the fold's own slide (`slideBriefCont`), and a tap
   on it shuts the fold as the line does. CLOSED, the line takes taps from
   around it (owner's request, same day, after missing it below): an
   empty `::after` 8 px up and 14 px down into the 18 px gaps and out to
   the cards' edges, 46 px tall, pixels unchanged (checked at 320 and
   393), off while open — new alert / alert
   extended / shortened / ended, quality status (any break's, said once),
   buoy dark / back, surf up / down, new SW, SW dropped, SW now 14.3 s /
   now WSW / now WSW at 14.3 s, SW building, new W offshore, NW offshore
   passed / now 12–14 s / peaking, today's tides, tide height. **ONE
   PHRASE PER THING THAT CHANGED** (owner's requests and choices,
   2026-11-02; `briefChanges`): the changes grouped by what each is about,
   then each thing's pair said as one — a train's shift and new status,
   "SSW now SW holding" (the status is read on the train's own band, which
   moves with it: together on 70 of 159 shifts, 25 Oct–2 Nov), joined by
   the pair's `train` tag, else on older lines by the status at the
   shift's new point and period; an offshore swell's band and trend, "W
   offshore now 12–14 s peaking"; an alert ending as another of its
   HAZARD starts (the event less its level word), "alert eased" / "alert
   raised" by Warning > Watch, Advisory > Statement, "alert changed"
   between a Watch and an Advisory, every other alert "new alert" / "alert
   ended" since several can be in force. Then alike changes share their
   words by "&", "SW & WSW dropped", "new WSW & SW", "SW & W holding" (a
   comma ran them into the line's own list). Never two things in one
   phrase: "surf up, SW building" stays two (nothing measures that one
   drove the other), and "SW dropped, new SSW" stays two however close
   (`SHIFT_STEPS` decides a shift). Replayed over the record, 16 of 376
   announced lines changed. **Only those
   are an update** (owner's call, same day): any other change to the words
   — an offshore line's due time, a new sample, the range only widening,
   the turns' times, a reordering — is kept in the record with
   `announced` false under the last announced update's key, time and words
   (`said`, what the page's line reads), and the fold shows the new words
   as it shows the conditions. Over the record from 25 Oct to 1 Nov, 10 of
   274 would have been quiet. "updated" is the first, one built without
   its words, or one kept before the line named changes. A train is
   paired across updates on its point, else one point and one 46232 bin
   away (`SHIFT_STEPS`, `SHIFT_HZ`: nothing follows a train between
   spectra, so anything further is one dropped and one new). It names no
   condition, with the
   provenance pills' green `.status` dot while that
   update is unopened on this device (`BRIEF_SEEN` in localStorage, through
   the gate's `stored`/`store`); opening the fold, or an update drawn into
   an open one, removes it. **Built every collection; UPDATED only when its
   alert, swell, tide or water quality words change** (owner's call, 2026-10-22, replacing the
   Morning / Midday issues): the build renders the page's own words
   (`briefingwording.render_issue`, Node) and `briefing.settle` compares the
   swell and tide lines with the newest kept line's, so a change below the
   page's precision is no update. **It updates most hours, and that is the
   owner's call** (2026-10-22): over the week to then the swell sentence
   alone changed on 139 of 170 hours (82%) — the floor/ceil range flips when
   any break crosses a whole foot, and the lead period hops between the
   buoy's bins (13.3 → 14.3 s), so whole seconds change nothing. 3-hour
   medians gave 45%, 6-hour 24%; the owner kept every hour's own numbers so
   the words always match the cards. The conditions refresh every build
   without one; the page redraws on a new `built_utc` and moves the time and dot only
   on a new `key`. **NWS's coast and ocean alerts come first** (owner's
   request and calls, 2026-10-24; `forecast.alerts`, archived by
   `collector/nwsalerts.py` → `data/alerts/`): a line each while one is in
   force at the build, "Coastal Flood Warning until 2 PM Sun" (always the
   weekday, so midnight is no update; "in effect" with no NWS end), an ink
   triangle, the event linking to NWS's showsigwx page as the owner's link
   has it, a grey NWS tag, and tapped NWS's own `headline` — NWS's words,
   escaped, and exempt from the page's vocabulary test because "Rip Current
   Statement" is NWS's name; the fold's first line -- an alert, else the
   swell headline -- as far under the Briefing's line as the Forecast tab's
   under its date, ink to ink, in every layout (owner's requests,
   2026-10-30 and -31: the fold body's own top padding, so it holds
   whatever comes first). Every alert line wraps 6 px short of its box,
   on BOTH tabs (`.alert-line` padding-right; owner's reports, 2026-11-02):
   at 393 px "… until 6 PM Mon NWS" needs ~313 px of a 311 px column, and
   Safari measured it a few px narrower than it drew it, kept it on one
   line and drew the NWS tag ~2 px past the box (unseen on the Forecast
   tab, cut by the open Briefing's clip). The margin made it wrap on the
   iPhone. A width cap (min-width 0, max-width 100%) tried in its place
   changed nothing there — the screenshot that seemed to prove it showed
   the margin, still loaded in an open tab (the page's HTML reloads only
   with the tab; its data refreshes) — and was taken out. No WebKit runs
   in a session: the owner's iPhone is the check, after a reload. Coast and ocean only (owner's choice): every
   alert for PZZ750, and CAZ043's events in `COASTAL_EVENTS`, never heat,
   fire weather or wind on land, never a Test. In force is NWS's own times:
   onset (never before `sent`) to `ends` (`expires` without one); a later
   alert that references it takes over from its `sent`, and a Cancel or an
   all-CAN/EXP/UPG VTEC alert ends it and is never shown. One line an event.
   An alert that starts, moves its end or ends is an update (its words enter
   `update_words` first). **The Forecast tab shows them too**, above the
   Swell card on the backdrop (`#fc-alerts`, `fcAlerts`), every version in
   force from the hour shown to the next one the picker offers, "from …"
   when it starts after that hour, from `alerts.json` (48 h back, as NWS had
   it by the build, `forecast.alerts`, each collection). The archive is
   every alert the active listing returns for CAZ043 and PZZ750, each its
   own `/alerts/{id}` document byte for byte, written once by its id
   (`data/alerts/YYYY/<oid>.json`); an alert issued and ended between
   collections is a gap. api.weather.gov is denied from a session: built on
   the API's documented shape, unverified against a live alert until the
   first one lands. Three blocks, apart by the cards' fold rule (owner's call,
   2026-10-23, replacing Origin's dot) — Swell, Tides, then Conditions (the
   tide moved above the conditions, owner's call, same day; described below
   in their earlier order), every number that says something in
   ink and heavier, the metric in brackets grey (`briefNum`): **Swell** (owner's
   wording and calls, 2026-10-23), TWO SOURCES never matched to each other.
   Each swell sentence a line of its own, 6 px apart, the beach's compass
   points in ink like the numbers (owner's request, same day). The beach
   (owner's choices, same day) is a HEADLINE: the range at 27 px, "3–4 ft
   (0.9–1.2 m)" (the three cards' breaking heights, lowest floored and
   highest ceiled to whole feet, at least a foot apart, FROM EACH HEIGHT AS
   ITS CARD SHOWS IT, to the tenth of a foot — `feetRange`, owner's call,
   2026-11-05, after "3–5 ft" over cards that never passed 4.0 (11:18 PM,
   4 Nov: 2.999 / 3.809 / 4.022 ft, shown 3.0 / 3.8 / 4.0, read "2–5 ft",
   now "3–4"); over the record to 5 Nov it changes 62 of 568
   ranges, each a break within 0.05 ft of a whole foot; the week strip's
   cells the same), the biggest
   breaking height each hour over 24 h a sparkline beside it (`beach_spark`,
   `swell.spark`, kept out of the record by `unsparked`); then A LINE A
   TRAIN, "SSW at 13.3 s · building" (its words "SSW at 13.3 s, building."),
   no trend mark: every swell train at ANY of the three breaks at ≥ HALF
   the biggest one's height, biggest first (owner's call, same day, after
   the WSW sea leading Center and South went unsaid because North, the
   biggest break, held only an SSW train; `MIX_SHARE` 0.5 of height; never
   local chop, unless nothing else exists; WIND SEA since 2026-11-08, said
   "NW wind sea at 4.5 s, building." (owner's call, when the label became
   the wind's: below, and BRIEFING §51), **ONE LINE A
   TRAIN AT 46232** (owner's call, 2026-10-24, replacing one a compass
   point, which listed one W swell twice, W 9.1 s at South and WSW 9.9 s at
   Center, either side of the 258.75° boundary): each carried row's
   `buoy_train` (now.py, `forecast.trainmatch.buoy_train`) is the buoy
   train holding its peak period, and of a band the buoy divided by
   direction the one holding its heading, else the nearest; trains of one
   buoy train are one line, the biggest's words. MEASURED first
   (`python -m forecast.trainmatch`, owner's condition): periods alone
   joined two buoy trains on 24% of its joins over the archive, nearly all
   a band the buoy divides by direction, and was rejected; in a known-answer
   control the shipped rule is wrong on 6.1% of joins of swells ≥ 3 s apart
   (17 of 18 a 15 s SSW + 12 s from 250–270° the buoy itself reads as one
   train, §40) and 25% at 1–2 s, catching 97% of duplicates where the
   compass point was wrong on 34% and caught 46%; pairs with a train no
   swell carries ⅔ of are counted, not scored. **Since 2026-11-03 a row's
   `buoy_train` is the buoy train that CARRIED MOST OF IT** (`Train.buoy`,
   set by `nearshore.carry`; owner's decision, BRIEFING §49), a row two
   buoy trains carried being divided first (below, "The leading wave
   train"); the peak-period rule is the fallback for a row with no such
   credit, and None is a buoy train under the buoy's own floors. each its row's
   OFFSHORE heading (the larger direction of a two-direction train, never
   its 5 m one) and period, and ITS OWN STATUS (owner's call, same day):
   its band at 46232 -- the bins it holds in the newest spectrum and the
   offshore headings holding 90% of what it carries to the break
   (`Train.held`, `nearshore.HELD_SHARE`; now.json trains' `band_hz` /
   `held_deg`) -- as energy over a trailing 3 h (`train_trend`, `trend_word`;
   a bin MEM cannot represent read as the chain reads it, by NDBC's Fourier
   form, `band_energy` / `fourier_sector`, since 2026-10-27: dropping the
   band left 9 of 225 lines with no status, and 16.7% of 46232's spectra
   hold such a bin):
   building ≥ +25% on 3 h before, fading ≤ −25%, peaking when the day's
   highest came within 3 h, else holding. Nothing follows a train between
   spectra, so it is the band's energy at the buoy, not the train's at the
   break; how often each word fires is NOT measured yet (the beach-wide
   trend it replaced was: holding 67%, peaking 16%, building 11%, fading 4%).
   Metric in brackets by the units rule. Offshore, each 46047 west / north-west swell: FOUND by a
   ×3 rise (§43's three bands plus 8–10 s, owner's request, whose lag §43
   did not check) in the last 72 h, its bands the newest rise and each
   LONGER band's newest rise before it within 24 h (`disperse`: long periods
   lead), and SAID only while a band of it is still to reach the breaks
   (owner's calls, 2026-10-24, replacing "arriving since", which read as
   arriving at the beach): the band due next (`next_band`), the next once
   that band's window at the breaks — due at 46232 plus the slowest leg —
   has passed, and nothing after the last, when the swell is the headline's
   to show or not at all; or sooner, once its sector's 8–17 s energy falls
   under a third of its peak since it began. Its energy is
   `briefing.offshore_energy`'s: a bin MEM cannot represent is read by
   Fourier, as the train status reads it (owner's call, 2026-11-10, for
   consistency; `upstreamlag.band_energy` still drops the whole reading,
   for §43's report). Replayed, it changed 8 of 670 builds since 24 Oct,
   each only its trend word. In plain words with no
   ink, each OPENING ON ITS POINT, no "first", and saying "offshore" on its
   trend, which is Tanner Bank's own (owner's calls, same day, replacing an
   "offshore" tag, which had replaced an "Offshore:" line), with a grey
   SIGNAL MARK in the margin — a dot, the origin, sending two arcs — turned
   to the swell's direction of TRAVEL, its sector's middle plus 180°
   (`briefSignal`): "W 10–12 s, building offshore; due at Point Loma South
   around 1:33 PM, and at the breaks 39–53 min later." The due time is
   computed, never a measured arrival (§43), and the trend is Tanner Bank's
   NOW: building ≥ +25% on 3 h before, fading under half its peak, else
   peaking. Hourly over the 60 days to 24 Oct a line showed on 19% of hours
   (the first band's window alone would have given 10%; with "arriving
   since" it was 91%), a swell caught a median 3.1 h before its first
   band's window. SW at Tanner Bank is never said (owner's call): it is not
   upstream of the breaks for a south swell. A dark 46232 says so and nothing
   else.
   **Conditions**, a LEDGER (owner's calls, 2026-10-23; `briefConditions`,
   `briefCondRow`): a row each, its name in small caps, an ink arrowhead —
   up, down, or a dash for no change, none with no earlier reading — the
   value, and a sparkline of its recent readings, broken at a missing hour,
   with its window (`briefing.trends`). WATER a Coronado shark-monitoring
   buoy's receiver (owner's call, 2026-10-29; BRIEFING §47;
   `briefing.hub_water_now`, `collector/sharklab.py`): its
   `ambient_temperature` at ~1–2 m, measured to be the water's (+0.6 °C
   against the lab's AquaMeasure sensors on 19,129 pairs, day and night
   alike; −0.4 °C against 46232 at Coronado, Sept–Oct). ONE hub, Center's
   first, South's next, each hub's break read off its own newest fix in
   the water; upright only (tilt < 30°: on land it lies at 77–94° and reads
   the air); ≤ 48 h (`HUB_WATER_FRESH_H`), because the lab loads each UTC
   day the next night, so it is normally yesterday's, which the TAPPED row
   says ("yesterday, 4:58 PM", `briefAgo`) and the row never does (owner's
   call, same day). Else 46232's (≤ 6 h; its standard met is fetched every
   collection by collect-beach-inputs.yml, its one writer since 2026-10-31,
   collect.yml excluding it: on collect.yml's throttled schedule it lapsed
   past 6 h twice on 30–31 Oct while the hubs' water had lapsed too, and
   the row went empty), the fallback only; never a blend, the row's value,
   arrow and sparkline one source's (14 d). With neither current the row
   says "No current reading", and tapped, when each last read
   (`water_last`, owner's call, 2026-10-31) -- never a lapsed value, KNZY's air temperature and humidity (≤ 90 min; the T
   group's tenths, Magnus; 24 h), its PRESSURE (the body's A group, inHg
   as published, hPa in brackets; 3 d; owner's request, same day), and RAIN
   only when the last hour's (the newest routine report's P group) or the
   rolling 24 h's (every routine report's; a SPECI's repeats its hour) is
   above zero, then both, with a bar a Pacific day for 7 d. **Water and air
   are compared 3 h back** (owner's call, measured: the reading before was
   the same on 64% of 46232's half-hours and 32% of KNZY's hours, 3 h back
   22% and 15%), humidity and pressure with the report before; a change
   under half a source's step is steady, humidity compared in the whole
   percent shown (it is computed). A tapped row says when it was read, by
   what, and against when. The record keeps the arrows, never the
   sparklines (`unsparked`): they are the archives' own readings again. **Tides**: the
   Pacific day's predicted turns, "AM low 0.7 ft (0.21 m) at 3:15 AM", with
   the gauge's departure as the card's carry it — DRAWN AS THE DAY'S CURVE
   (owner's choices, 2026-10-23, replacing that day's ledger;
   `briefTideChart`, `tide_story`'s `curve` and `nights`): the same
   prediction at the open coast with the departure every 30 min
   (`TIDE_CURVE_MIN`), Coronado's midnight to midnight and STRICTLY TODAY —
   no next day's turn at the edge — each turn's height by its dot (above a
   high, below a low) and its time on the axis under it — the times packed
   in order as the sun row's are, `briefRow`, each under a 4 px tick at its
   turn (owner's choice, 2026-11-01: close turns printed over each other on
   15 of 48 days at 320 px) — the hours gone and
   their turns grey, the rest ink, now an open dot on the curve alone (no
   line, no word) with a ring rippling out of it — to 3× over 2.6 s as it
   fades, then 2 s of rest (`BRIEF_RING`), none under reduced motion
   (owner's choices, 2026-10-25). A Web Animation counted from the page's
   timeline (`ringNow`, startTime 0), never a CSS animation: the chart is
   redrawn every minute and on every width change, each time a new ring,
   and a CSS one restarted on each even with a clock-set negative delay
   (measured the same day: phase jumps of 1.5–2.5 s, now 0) — nights shaded as the Tide card's charts are — from under
   a top row with the day's sunrise and sunset, each an icon (horizon, half
   sun, arrow up or down; `BRIEF_SUN`) beside its time, set as the turns'
   times are and grey once passed (the shading's own edges,
   `daylight`'s sea horizon at the center break, packed in order by
   `briefRow`) to just above the times, so every height sits on the
   shading (owner's requests, 2026-10-24); drawn at its own width
   (`fitBriefTide`, a ResizeObserver, as the fold opens); tapped,
   "Predicted · NOAA 9410170 · departure +1.5 ft (0.46 m)". The record
   keeps the turns, never the curve (`unsparked`). Each turn's words
   (`briefTideText`) are the ledger's, so the curve was no update.
   **Water quality** (owner's request, 2026-10-30; since 2026-10-31 under
   the water temperature row as ONE water block, and air, humidity,
   pressure and rain a block of their own below it, owner's request;
   `briefing.water_quality_story`, `briefWater`, BRIEFING §48): the County
   of San Diego's Beach & Bay Water Quality Monitoring Program (DEHQ) at
   each break's own station, North EH-060, Center EH-050, South IB-079
   (`collector/beachwater.json`, the owner's), a ledger row each as the
   conditions' on TWO grid lines (owner's calls, 2026-10-30; `briefWaterRow`):
   the status the county has POSTED, Open / Advisory / Warning / Closed: the
   worst of its events in force in the posting report as just read
   (`beachwater.in_force`, `status_of`), else Open. **The map's PriorityMax
   is NOT the legend's id** (owner's report, 2026-10-31: South showed Open
   for a day under an Advisory issued 30 Oct 22:42Z, its PriorityMax 2 read
   as the legend's 2, Open; Closed is 4 in both, which is why it passed); it
   is a cross-check, `PRIORITY_SEEN` {2: Advisory, 4: Closed}, a worse seen
   value winning and any disagreement a workflow warning and a `note` in
   state.json. "until 11 AM Sat" while
   the county's own lift time lies ahead (a General Rain Advisory is issued
   with its end; never a computed one); then "1,379 copies/100 mL on
   Oct 28", the newest sample's Enterococcus (ddPCR's where the day has both
   methods, `briefing.wq_lead`; named only when not Enterococcus) in ink,
   "<" kept, "=" dropped, its arrowhead in the conditions' arrow column
   against the previous sample of the same parameter and method
   (`briefing.wq_change`): steady within `WQ_STEADY_RATIO` x1.5 either side,
   MEASURED on the archive to 30 Oct (median day-to-day change x1.9 at all
   three; x1.5 calls 30-34% steady, a third each way; the county posts no
   duplicates, so the test's own repeatability is not measured), a "<" a
   change only when its limit is beyond the ratio. **Its samples' sparkline**
   (owner's request, 2026-11-01; `briefing.wq_spark`, `WQ_SPARK_D`): every
   result of the lead's parameter and method over 30 days to the newest
   sample, on a LOG scale (195 to 835,168 copies since May), joined only
   between consecutive days, a sample with a day skipped either side a
   faint dot, a "<" at its limit; on the row's FIRST line, in the
   conditions' sparkline column, with "30 d". Beside the sample it took
   that line's width and put the date on a third line at 390 px; on the
   first line, "Advisory until 6 PM Tue" wraps instead (at 320 and 390),
   which happens only while a lift time is set. 30 days, not 14: the 30 days
   to 31 Oct held 13 samples at North and Center and 23 at South, the 14
   days 9, 9 and 11. Nothing to backfill: the county's site serves samples from 21 May
   2026, when its records begin, and the first collection took them all. A status read more than
   `WQ_FRESH_H` (3 h) ago is not said: "Status not read since …". Tapped:
   "Open since Oct 28, 4:37 PM · Coronado North Beach (EH-060) · sampled
   Oct 28, 6:28 AM: Enterococcus (ddPCR) · County of San Diego DEHQ" (owner's
   wording, same day). Its words are an update. Not measured yet: how soon
   a sample or an advisory reaches the site (each result's `first_seen_utc`
   is in the payload for that).
   **Its spacing** (owner's settings, 2026-10-31, from a mock of options):
   18 px above each section's rule and 16 px below it (the stack layout's
   alerts rule the same), rows 6 px apart at a line height of 1.4, and 4 px
   more between the water breaks' two-line rows.
   **Every name, arrowhead and sparkline of the Briefing's ledgers sits
   beside its value's FIRST line** when the value wraps (owner's request,
   same day: `.brief-row > :not(.brief-val)` one value line tall).
   **Every update is kept**:
   `data/briefings/YYYY-MM.jsonl`, append-only, the build and its words; its
   one writer is collect-beach-inputs.yml's "Record the briefing", in a
   sparse worktree of the branch's NEWEST tip, re-appending on a rejected
   push, never rebasing; `briefing.json` is each build settled against the
   newest kept line. The lines from 18–22 Oct are the Morning / Midday
   design's (`issued_utc`, no `update_words`), never matched. **Never the
   model**: GFS-Wave and its ensemble are the Forecast tab's. Units as each
   source publishes them (°C, METAR's inches), converted only on the page
   (`fahrenheit`, `MM_PER_IN` beside the other unit constants). The 10-17
   design's measured words (filling / fading, leader, a ridge's period
   ahead; `forecast/briefingreport.py`, `docs/briefing_thresholds.md`) are
   no longer said; their constants stay in briefing.py for the report.
   **Long-period energy ahead is NOT said** (measured 2026-10-27 at the
   owner's request, kept in the same report to re-run in winter): 46232's
   energy at 14, 16 or 18 s and longer from the breaks' windows doubling on
   3 h before came before a beach 15% higher within a day LESS often than
   any hour did (25–60% against 69%), and before a bigger day at most one
   firing in five (13% for any hour); a test says when a winter archive
   passes the 85% rule.
   Wording generated from the page into `docs/briefing_wording.md` (the
   formula and each case) and `docs/briefing_sentences.md` (every distinct
   line once, for the owner to edit; edits are carried into the page by
   hand) by `forecast/briefingwording.py`, both pinned by a test.
