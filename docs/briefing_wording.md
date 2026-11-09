# Briefing wording: the formula, and every permutation

The LIVE tab's Briefing (owner's requests, 2026-10-16, -17 and -22). It sits
above the LIVE cards in a fold of its own on the page's backdrop, not a card.
It is built every collection and UPDATES only when what it says about NWS's
alerts, the swell, the tides or the water quality changes in a way its line
names; the conditions refresh without an update. Its line reads "Briefing
{what changed}" with {time} apart at its right end, against the caret, the
unread dot after it (owner's request and settings, 2026-11-02; below, the
time follows a " · "), the day too when the update is not today's: what
the update changed, in the order of the list at the end, as many as fit on
the line (owner's copy, 2026-11-01; `forecast.briefing.changes`, each kept
with the update so the record can be filtered by it). When they do not all
fit, the line breaks off on an ellipsis closed up to its comma, "Briefing
surf up, SW building,… · 6:17 PM", and the open fold's first line carries the
rest on, level with the changes, "…tide height, today's tides" (owner's
design, 2026-11-02, replacing "+N"). A change too long for what is left of
the line is passed over for later, shorter ones that fit; when none fits
whole, the first starts on the line and breaks at its last space that fits,
never after "now", "at", "new" or "&" unless no other break fits ("new…"
over "…alert"), ending the line on a bare ellipsis,
"Briefing SW now SSW… · 7:16 AM" over "…at 15.4 s building" (owner's
request, 2026-11-02). Below, a case's room is in characters; the page
measures the line. Each THING that changed is said
once (owner's requests and choices, 2026-11-02): a train's shift and its
status, "SSW now SW holding"; an offshore swell's band and trend, "W
offshore now 12–14 s peaking"; an alert ending as another of its hazard
starts, "alert eased", "alert raised" or, between a Watch and an Advisory,
"alert changed", every other alert "new alert" or "alert ended". Then
things that changed alike share their words by "&", "SW & WSW dropped",
never two things in one phrase as though they were one. A change
the line names none of (an offshore swell's due time, a new sample, the
range only widening) is kept in the record, not announced, and is no
update: the line and its time stay on the last one, while the fold shows
the new words. "Briefing updated {time}" is the first update, one built
without its words, or one kept before the line named its changes. The provenance pills' green dot sits
beside it while that update is unopened on this device. Opening the fold
removes the dot.

The section at the end lists every permutation, and
`docs/briefing_sentences.md` every distinct line once, for editing. Neither
is typed: `python -m forecast.briefingwording` lifts the Briefing code out of
`app/forecast.html`, runs it in Node on one made-up briefing per branch, and
writes what the page prints. `tests/test_briefingwording.py` fails if the
page and these files disagree. Edit the wording above the generated section;
the numbers in the cases are made up, and times are Pacific.

## The formula

NWS's alerts when there are any, then three blocks, always in this order (the
alerts the top line, owner's call, 2026-10-24; the tide above the conditions,
owner's call, 2026-10-23), set apart by the cards' fold rule. Each
is a fixed run of slots: a slot with no value is dropped with its joining
words, and a block with nothing to say drops whole. Never the model: GFS-Wave
and its ensemble are the Forecast tab's.

| Block | Slots, in order |
|---|---|
| **Alerts** | NWS's coast and ocean alerts in force at the build, a line each, oldest first: `{event} until {time} {weekday}` (`2 PM Sun`, `2:30 PM Sun`: always the weekday, so a day turning over is no update), or `{event} in effect` when NWS gives no end, with a warning triangle in ink, the event linking to NWS's page and a grey `NWS` tag; tapped, NWS's own headline under it in grey. Coast and ocean only (owner's choice): every alert for the coastal waters (PZZ750), and from the land zone (CAZ043) its coastal flood, high surf, rip current, beach hazards, tsunami and storm surge events — never heat, fire weather or wind on land. An alert ended by the reader's clock drops. Two in force for one event (the land's and the waters') are one line, the one ending last. Below, each line's words are the line without its tag |
| **Swell** | Two sources, never matched to each other, each sentence a line of its own, the compass points in ink like the numbers. The beach: `{lo}–{hi} ft ({m}).` — the three breaks' breaking heights (the cards' numbers), lowest rounded down and highest rounded up to whole feet, at least one foot apart — set as a headline, the biggest breaking height each hour over 24 h a sparkline beside it. Under it, a line a train: `{point} at {T} s, {status}.` (shown `{point} at {T} s · {status}`, no trend mark), for every swell train at any of the three breaks at ≥ 50% of the height of the biggest one anywhere, biggest first, and one line a train at CDIP 191: trains at two breaks that are the same train at the buoy — the one holding each's peak period, and of a band the buoy divided by direction, the one holding its heading — are one line, the biggest's, so one swell read through two breaks' windows is never two lines (never local chop, and with no train but chop, the biggest break's lead; a wind sea, the wind still driving it by wave age against KNZY's and NDBC 46086's winds both (forecast.windsea, owner's call 2026-11-08), reads `{point} wind sea at {T} s, {status}.`; a short train the wind is not driving is a train like any other), each status read in its own break's band: the compass point it comes from OFFSHORE (its row's heading, the larger direction for a train of two; never its 5 m heading), its period, and its status — its band at CDIP 191 (the periods it holds and the offshore headings holding 90% of what it carries to the break) as energy averaged over 3 h: building (up ≥ 25% on 3 h before), fading (down ≥ 25%), peaking (the day's highest within 3 h), else holding. Then, a line each, in plain words (no ink), opening on its point, with a small grey signal mark in the margin (a dot, the origin, sending two arcs) turned the way the swell travels (its sector's middle plus 180°), for each west (250–280°) or north-west (280–330°) swell Tanner Bank holds — found by a threefold rise in an 8–10, 10–12, 12–14 or 14–17 s band in the last 72 h, its bands the newest rise and each longer band that rose before it within 24 h — while a band of it is still to reach the breaks: `{W / NW} {band} s, {trend} offshore; due at Point Loma South around {time}, and at the breaks {lo}–{hi} min later.`, naming the band due next (deep-water speed, then the rays' leg; BRIEFING §43), the next once that band's window at the breaks (its due time plus the slowest leg) has passed, and nothing once the last has: the swell is then the headline's to show. It also goes once Tanner Bank no longer holds it (its energy there under a third of its peak). The trend is Tanner Bank's now: building (up ≥ 25% over 3 h), fading (under half its peak), else peaking. A slot with no value drops with its words. If 46232 is dark: `No spectrum from CDIP 191 since {time}.` and nothing else |
| **Tides** | each of the Pacific day's predicted turns, `{AM / PM} {high / low} {height} at {time}`, with the gauge's departure as the card's turns carry it — drawn as the day's curve: the same prediction at the open coast with the departure, every 30 min from Coronado's midnight to the next and strictly that day, each turn's height by its dot (above a high, below a low; feet in ink, metric grey) and its time on the axis under it; the hours gone and their turns grey, the rest ink; an open dot where the tide is now, with no line or word, and a ring rippling out of it (to 3× over 2.6 s as it fades, then 2 s of rest; none under reduced motion) (the curve grey before it and ink after says what it is); nights faintly shaded, as the Tide card's charts are, from under a row with the day's sunrise and sunset, each a horizon-and-half-sun icon (arrow up, arrow down) beside its time, set as the turns' times are and grey once passed (the shading's own edges: the sea horizon at the center break), down to just above the turns' times, so every height sits on the shading. Tapped, it says `Predicted · NOAA 9410170 · departure {±height}`. Below, each turn's words are the line it was before the curve, so the curve was no update |
| **Conditions** | A ledger, a row each: the name in small caps, an ink arrowhead (up, down, or a dash for no change) against an earlier reading — water and air 3 h back, humidity and pressure the report before, none when there is no earlier reading — then the value, and a sparkline of its recent readings with its window. `Water {°F} ({°C})` (a Coronado hub's receiver at ~1–2 m, Center's first, its newest upright reading within 48 h: the lab loads each day the next night, so it is normally yesterday's, which the tapped row says; else 46232's newest, within 6 h; never a blend, the arrow and sparkline the same source's; 14 d); `Air {°F} ({°C})` and `Humidity {n}%` (KNZY's newest, within 90 min; 24 h); `Pressure {inHg} ({hPa})` (KNZY's altimeter; 3 d); `Rain {in} ({mm}) in the last hour ({kinds}), {in} ({mm}) in 24 h`, only when either amount is above zero, and then both (a bar a day for 7 d). A tapped row says when it was read, by what, and against when. Below, each row's words are its name, value and arrow |

**An update** is a change in the alert, swell or tide words, as printed, so
an alert that starts, changes its end or ends is one: a change
below the page's precision is none. Each update is kept in
`data/briefings/`, with the conditions of that moment.

<!-- Generated by python -m forecast.briefingwording. Edit above this line. -->

### Q1: a quiet morning: one range, nothing coming, no rain

```text
[Briefing updated · 7:16 AM]

3–4 ft (0.9–1.2 m). SSW at 13.3 s, holding.

AM low 0.7 ft (0.21 m) at 3:15 AM
AM high 5.3 ft (1.62 m) at 9:32 AM
PM low 1.8 ft (0.55 m) at 3:48 PM
PM high 6.3 ft (1.92 m) at 10:05 PM

Water 67 °F (19.4 °C), up
Air 61 °F (16 °C), down
Humidity 88%, steady
Pressure 30.05 inHg (1018 hPa)

North Open; 1,379 copies/100 mL on Oct 21, steady
Center Open; 793 copies/100 mL on Oct 21, up
South Open; <195 copies/100 mL on Oct 22, down
```

### B1: west swell rising at Tanner Bank, waves spread over three feet, rain in the last hour

```text
[Briefing updated · 7:16 AM]

2–5 ft (0.6–1.5 m). S at 18.2 s, building. W 10–12 s, building offshore; due at Point Loma South around 1:32 PM, and at the breaks 39–53 min later.

AM low 0.7 ft (0.21 m) at 3:15 AM
AM high 5.3 ft (1.62 m) at 9:32 AM
PM low 1.8 ft (0.55 m) at 3:48 PM
PM high 6.3 ft (1.92 m) at 10:05 PM

Water 67 °F (19.4 °C), up
Air 61 °F (16 °C), down
Humidity 88%, steady
Pressure 30.05 inHg (1018 hPa)
Rain 0.03 in (0.8 mm) in the last hour (rain), 0.11 in (2.8 mm) in 24 h

North Open; 1,379 copies/100 mL on Oct 21, steady
Center Open; 793 copies/100 mL on Oct 21, up
South Open; <195 copies/100 mL on Oct 22, down
```

### C1: two sectors offshore, each still to reach the breaks; rain earlier in the day only

```text
[Briefing updated · 7:16 AM]

3–4 ft (0.9–1.2 m). SSW at 13.3 s, peaking. NW 14–17 s, fading offshore; due at Point Loma South around 9:50 AM, and at the breaks 39–53 min later. W 10–12 s, building offshore; due at Point Loma South around 1:32 PM, and at the breaks 39–53 min later.

AM low 0.7 ft (0.21 m) at 3:15 AM
AM high 5.3 ft (1.62 m) at 9:32 AM
PM low 1.8 ft (0.55 m) at 3:48 PM
PM high 6.3 ft (1.92 m) at 10:05 PM

Water 67 °F (19.4 °C), up
Air 61 °F (16 °C), down
Humidity 88%, steady
Pressure 30.05 inHg (1018 hPa)
Rain 0.00 in (0.0 mm) in the last hour, 0.24 in (6.1 mm) in 24 h

North Open; 1,379 copies/100 mL on Oct 21, steady
Center Open; 793 copies/100 mL on Oct 21, up
South Open; <195 copies/100 mL on Oct 22, down
```

### M1: a mix: every swell train at the breaks at half the biggest's height or more, a line each, one a train at the buoy

```text
[Briefing updated · 7:16 AM]

3–4 ft (0.9–1.2 m). SSW at 15.4 s, fading. SSW at 14.3 s, holding. W at 10.0 s, building.

AM low 0.7 ft (0.21 m) at 3:15 AM
AM high 5.3 ft (1.62 m) at 9:32 AM
PM low 1.8 ft (0.55 m) at 3:48 PM
PM high 6.3 ft (1.92 m) at 10:05 PM

Water 67 °F (19.4 °C), up
Air 61 °F (16 °C), down
Humidity 88%, steady
Pressure 30.05 inHg (1018 hPa)

North Open; 1,379 copies/100 mL on Oct 21, steady
Center Open; 793 copies/100 mL on Oct 21, up
South Open; <195 copies/100 mL on Oct 22, down
```

### WS1: a wind sea at half the biggest's height or more: the wind still driving it, said after its point (forecast.windsea, owner's call 2026-11-08); a short train the wind is not driving is a train like any other

```text
[Briefing updated · 7:16 AM]

3–4 ft (0.9–1.2 m). SSW at 14.3 s, holding. NW wind sea at 4.5 s, building. W at 6.7 s, holding.

AM low 0.7 ft (0.21 m) at 3:15 AM
AM high 5.3 ft (1.62 m) at 9:32 AM
PM low 1.8 ft (0.55 m) at 3:48 PM
PM high 6.3 ft (1.92 m) at 10:05 PM

Water 67 °F (19.4 °C), up
Air 61 °F (16 °C), down
Humidity 88%, steady
Pressure 30.05 inHg (1018 hPa)

North Open; 1,379 copies/100 mL on Oct 21, steady
Center Open; 793 copies/100 mL on Oct 21, up
South Open; <195 copies/100 mL on Oct 22, down
```

### H1: the lead train has no heading, and no status yet: their slots drop with their words

```text
[Briefing updated · 7:16 AM]

3–4 ft (0.9–1.2 m). At 13.3 s.

AM low 0.7 ft (0.21 m) at 3:15 AM
AM high 5.3 ft (1.62 m) at 9:32 AM
PM low 1.8 ft (0.55 m) at 3:48 PM
PM high 6.3 ft (1.92 m) at 10:05 PM

Water 67 °F (19.4 °C), up
Air 61 °F (16 °C), down
Humidity 88%, steady
Pressure 30.05 inHg (1018 hPa)

North Open; 1,379 copies/100 mL on Oct 21, steady
Center Open; 793 copies/100 mL on Oct 21, up
South Open; <195 copies/100 mL on Oct 22, down
```

### D1: 46232 dark: the swell says so and nothing else

```text
[Briefing updated · 7:16 AM]

No spectrum from NDBC 46232 since Oct 21, 3:00 PM.

AM low 0.7 ft (0.21 m) at 3:15 AM
AM high 5.3 ft (1.62 m) at 9:32 AM
PM low 1.8 ft (0.55 m) at 3:48 PM
PM high 6.3 ft (1.92 m) at 10:05 PM

Water 67 °F (19.4 °C), up
Air 61 °F (16 °C), down
Humidity 88%, steady
Pressure 30.05 inHg (1018 hPa)

North Open; 1,379 copies/100 mL on Oct 21, steady
Center Open; 793 copies/100 mL on Oct 21, up
South Open; <195 copies/100 mL on Oct 22, down
```

### W1: the water from Center's hub, yesterday's (the lab loads it each night); 46232 only when no hub has a reading

```text
[Briefing updated · 7:16 AM]

3–4 ft (0.9–1.2 m). SSW at 13.3 s, holding.

AM low 0.7 ft (0.21 m) at 3:15 AM
AM high 5.3 ft (1.62 m) at 9:32 AM
PM low 1.8 ft (0.55 m) at 3:48 PM
PM high 6.3 ft (1.92 m) at 10:05 PM

Water 73 °F (22.7 °C), steady
Air 61 °F (16 °C), down
Humidity 88%, steady
Pressure 30.05 inHg (1018 hPa)

North Open; 1,379 copies/100 mL on Oct 21, steady
Center Open; 793 copies/100 mL on Oct 21, up
South Open; <195 copies/100 mL on Oct 22, down
```

### W2: neither source current: the row says so, and tapped, when each last read, never a value

```text
[Briefing updated · 7:16 AM]

3–4 ft (0.9–1.2 m). SSW at 13.3 s, holding.

AM low 0.7 ft (0.21 m) at 3:15 AM
AM high 5.3 ft (1.62 m) at 9:32 AM
PM low 1.8 ft (0.55 m) at 3:48 PM
PM high 6.3 ft (1.92 m) at 10:05 PM

Water No current reading
Air 61 °F (16 °C), down
Humidity 88%, steady
Pressure 30.05 inHg (1018 hPa)

North Open; 1,379 copies/100 mL on Oct 21, steady
Center Open; 793 copies/100 mL on Oct 21, up
South Open; <195 copies/100 mL on Oct 22, down
```

### K1: no water temperature, no KNZY report, a minus tide

```text
[Briefing updated · 7:16 AM]

3–4 ft (0.9–1.2 m). SSW at 13.3 s, holding.

AM low −0.7 ft (−0.21 m) at 6:40 AM
PM high 5.6 ft (1.71 m) at 1:05 PM

North Open; 1,379 copies/100 mL on Oct 21, steady
Center Open; 793 copies/100 mL on Oct 21, up
South Open; <195 copies/100 mL on Oct 22, down
```

### A1: two NWS alerts in force, one with no end, and one that ended after the build, which drops

```text
[Briefing updated · 7:16 AM]

Coastal Flood Warning until 2 PM Sun
Small Craft Advisory in effect

3–4 ft (0.9–1.2 m). SSW at 13.3 s, holding.

AM low 0.7 ft (0.21 m) at 3:15 AM
AM high 5.3 ft (1.62 m) at 9:32 AM
PM low 1.8 ft (0.55 m) at 3:48 PM
PM high 6.3 ft (1.92 m) at 10:05 PM

Water 67 °F (19.4 °C), up
Air 61 °F (16 °C), down
Humidity 88%, steady
Pressure 30.05 inHg (1018 hPa)

North Open; 1,379 copies/100 mL on Oct 21, steady
Center Open; 793 copies/100 mL on Oct 21, up
South Open; <195 copies/100 mL on Oct 22, down
```

### R1: a General Rain Advisory at all three, the county's end ahead: until when, and the samples from before it

```text
[Briefing updated · 7:16 AM]

3–4 ft (0.9–1.2 m). SSW at 13.3 s, holding.

AM low 0.7 ft (0.21 m) at 3:15 AM
AM high 5.3 ft (1.62 m) at 9:32 AM
PM low 1.8 ft (0.55 m) at 3:48 PM
PM high 6.3 ft (1.92 m) at 10:05 PM

Water 67 °F (19.4 °C), up
Air 61 °F (16 °C), down
Humidity 88%, steady
Pressure 30.05 inHg (1018 hPa)

North Advisory until 11 AM Sat; 1,379 copies/100 mL on Oct 21, steady
Center Advisory until 11 AM Sat; 793 copies/100 mL on Oct 21, up
South Advisory until 11 AM Sat; <195 copies/100 mL on Oct 22, down
```

### Z1: South closed with no end set, North's day of four results (the City of Coronado's lab), Center with no sample yet

```text
[Briefing updated · 7:16 AM]

3–4 ft (0.9–1.2 m). SSW at 13.3 s, holding.

AM low 0.7 ft (0.21 m) at 3:15 AM
AM high 5.3 ft (1.62 m) at 9:32 AM
PM low 1.8 ft (0.55 m) at 3:48 PM
PM high 6.3 ft (1.92 m) at 10:05 PM

Water 67 °F (19.4 °C), up
Air 61 °F (16 °C), down
Humidity 88%, steady
Pressure 30.05 inHg (1018 hPa)

North Open; 2,957 copies/100 mL on Oct 20
Center Open; no sample yet
South Closed; <195 copies/100 mL on Oct 22, down
```

### S1: the county's status last read too long ago: no status, when it was read, the samples kept

```text
[Briefing updated · 7:16 AM]

3–4 ft (0.9–1.2 m). SSW at 13.3 s, holding.

AM low 0.7 ft (0.21 m) at 3:15 AM
AM high 5.3 ft (1.62 m) at 9:32 AM
PM low 1.8 ft (0.55 m) at 3:48 PM
PM high 6.3 ft (1.92 m) at 10:05 PM

Water 67 °F (19.4 °C), up
Air 61 °F (16 °C), down
Humidity 88%, steady
Pressure 30.05 inHg (1018 hPa)

North Status not read since 2:35 AM; 1,379 copies/100 mL on Oct 21, steady
Center Status not read since 2:35 AM; 793 copies/100 mL on Oct 21, up
South Status not read since 2:35 AM; <195 copies/100 mL on Oct 22, down
```

### Y1: yesterday's update, read this morning

```text
[Briefing updated · Oct 21, 12:06 PM]

3–4 ft (0.9–1.2 m). SSW at 13.3 s, holding.

AM low 0.7 ft (0.21 m) at 3:15 AM
AM high 5.3 ft (1.62 m) at 9:32 AM
PM low 1.8 ft (0.55 m) at 3:48 PM
PM high 6.3 ft (1.92 m) at 10:05 PM

Water 67 °F (19.4 °C), up
Air 61 °F (16 °C), down
Humidity 88%, steady
Pressure 30.05 inHg (1018 hPa)

North Open; 1,379 copies/100 mL on Oct 21, steady
Center Open; 793 copies/100 mL on Oct 21, up
South Open; <195 copies/100 mL on Oct 22, down
```

### X1: nothing built yet

```text
(no Briefing: the fold is not drawn)
```

### The fold's line, by what the update changed

```text
L1   Briefing surf up · 7:16 AM                               the surf up
L2   Briefing surf down · 7:16 AM                             the surf down
L3   Briefing new SW · 7:16 AM                                a new train
L4   Briefing W dropped · 7:16 AM                             a train dropped
L5   Briefing SW now 14.3 s · 7:16 AM                         a train's period moved
L6   Briefing SW now WSW · 7:16 AM                            a train's point moved
L7   Briefing SW now WSW at 14.3 s · 7:16 AM                  both
L8   Briefing SSW now SW holding · 7:16 AM                    a train's point moved and its status changed: one phrase
L9   Briefing SW building · 7:16 AM                           a train's status
L10  Briefing SSW now SW holding, W holding · 7:16 AM         a train's shift and its status, with another train's status: that one said alone
L11  Briefing SW & W holding · 7:16 AM                        two trains' status alike: their words shared
L12  Briefing new SSW, SW & WSW dropped · 7:16 AM             a new train and two dropped: the two dropped share their words
L13  Briefing new WSW & SW · 7:16 AM                          two new trains: their words shared
L14  Briefing new W offshore · 7:16 AM                        a swell first said offshore
L15  Briefing NW offshore passed · 7:16 AM                    a swell offshore passed
L16  Briefing NW offshore now 12–14 s · 7:16 AM               an offshore swell's next band
L17  Briefing NW offshore peaking · 7:16 AM                   an offshore swell's trend
L18  Briefing W offshore now 12–14 s peaking · 7:16 AM        an offshore swell's next band and its trend: one phrase
L19  Briefing buoy dark · 7:16 AM                             NDBC 46232 dark
L20  Briefing buoy back · 7:16 AM                             NDBC 46232 back
L21  Briefing new alert · 7:16 AM                             an NWS alert starts
L22  Briefing alert extended · 7:16 AM                        an alert's end moved later
L23  Briefing alert shortened · 7:16 AM                       an alert's end moved earlier
L24  Briefing alert ended · 7:16 AM                           an alert ended
L25  Briefing alert eased · 7:16 AM                           an alert ending as a lower one of its hazard starts
L26  Briefing alert raised · 7:16 AM                          an alert ending as a higher one of its hazard starts
L27  Briefing alert changed · 7:16 AM                         a Watch ending as an Advisory of its hazard starts: neither above the other
L28  Briefing alert eased, new alert · 7:16 AM                a hand-over beside another hazard's new alert: that one said as it is
L29  Briefing quality status · 7:16 AM                        two breaks' water quality status changed: said once
L30  Briefing today's tides · 7:16 AM                         midnight's tides
L31  Briefing tide height · 7:16 AM                           a tide height moved with the gauge's departure
L32  Briefing surf up, new SW, new W offshore · 7:16 AM       the surf up, a new train and a new offshore swell, with room for all three
L33  Briefing surf up,… · 7:16 AM                             the same three, with room for 10 characters: the rest carries on under it, open
              …new SW, new W offshore                         (the open fold's first line)
L34  Briefing tide height,… · 7:16 AM                         a first change too long for the line: a shorter one moves ahead of it
              …SW now SSW at 15.4 s building                  (the open fold's first line)
L35  Briefing SW now SSW… · 7:16 AM                           one change too long for the line, and nothing shorter: broken at its last space that fits, never after a joining word
              …at 15.4 s building                             (the open fold's first line)
L36  Briefing new… · 7:16 AM                                  one change whose only break is after a joining word: broken there rather than leaving the line empty
              …alert                                          (the open fold's first line)
L37  Briefing updated · 7:16 AM                               the first update of this design, or one built without its words
L38  Briefing updated · 7:16 AM                               an update kept before the line named its changes
```
