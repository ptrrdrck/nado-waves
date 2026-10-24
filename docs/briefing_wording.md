# Briefing wording: the formula, and every permutation

The LIVE tab's Briefing (owner's requests, 2026-10-16, -17 and -22). It sits
above the LIVE cards in a fold of its own on the page's backdrop, not a card.
It is built every collection and UPDATES only when what it says about the
swell or the tides changes; the conditions refresh without an update. Its
line reads "Briefing updated {time}" (the day too when the update is not
today's) and nothing else, with the provenance pills' green dot while that
update is unopened on this device. Opening the fold removes the dot.

The section at the end lists every permutation, and
`docs/briefing_sentences.md` every distinct line once, for editing. Neither
is typed: `python -m forecast.briefingwording` lifts the Briefing code out of
`app/forecast.html`, runs it in Node on one made-up briefing per branch, and
writes what the page prints. `tests/test_briefingwording.py` fails if the
page and these files disagree. Edit the wording above the generated section;
the numbers in the cases are made up, and times are Pacific.

## The formula

Three blocks, always in this order (the tide above the conditions, owner's
call, 2026-10-23), set apart by the cards' fold rule. Each
is a fixed run of slots: a slot with no value is dropped with its joining
words, and a block with nothing to say drops whole. Never the model: GFS-Wave
and its ensemble are the Forecast tab's.

| Block | Slots, in order |
|---|---|
| **Swell** | Two sources, never matched to each other, each sentence a line of its own, the compass points in ink like the numbers. The beach: `{lo}–{hi} ft ({m}).` — the three breaks' breaking heights (the cards' numbers), lowest rounded down and highest rounded up to whole feet, at least one foot apart — set as a headline, the biggest breaking height each hour over 24 h a sparkline beside it. Under it, a line a train: `{point} at {T} s, {status}.` (shown `{point} at {T} s · {status}`, no trend mark), for every swell train at any of the three breaks at ≥ 50% of the height of the biggest one anywhere, biggest first, and only the biggest from each compass point, so one sea read at two breaks is one line (never wind sea or local chop; with no swell train at all, the biggest break's lead), each status read in its own break's band: the compass point it comes from OFFSHORE (its row's heading, the larger direction for a train of two; never its 5 m heading), its period, and its status — its band at CDIP 191 (the periods it holds and the offshore headings holding 90% of what it carries to the break) as energy averaged over 3 h: building (up ≥ 25% on 3 h before), fading (down ≥ 25%), peaking (the day's highest within 3 h), else holding. Then, a line each, in plain words (no ink), opening on its point, with a small grey signal mark in the margin (a dot, the origin, sending two arcs) turned the way the swell travels (its sector's middle plus 180°), for each west (250–280°) or north-west (280–330°) swell Tanner Banks holds — found by a threefold rise in an 8–10, 10–12, 12–14 or 14–17 s band in the last 72 h, its bands the newest rise and each longer band that rose before it within 24 h — while a band of it is still to reach the breaks: `{W / NW} {band} s, {trend} offshore; due at Point Loma South around {time}, and at the breaks {lo}–{hi} min later.`, naming the band due next (deep-water speed, then the rays' leg; BRIEFING §43), the next once that band's window at the breaks (its due time plus the slowest leg) has passed, and nothing once the last has: the swell is then the headline's to show. It also goes once Tanner Banks no longer holds it (its energy there under a third of its peak). The trend is Tanner Banks' now: building (up ≥ 25% over 3 h), fading (under half its peak), else peaking. A slot with no value drops with its words. If 46232 is dark: `No spectrum from CDIP 191 since {time}.` and nothing else |
| **Tides** | each of the Pacific day's predicted turns, `{AM / PM} {high / low} {height} at {time}`, with the gauge's departure as the card's turns carry it — drawn as the day's curve: the same prediction at the open coast with the departure, every 30 min from Coronado's midnight to the next and strictly that day, each turn's height by its dot (above a high, below a low; feet in ink, metric grey) and its time on the axis under it; the hours gone and their turns grey, the rest ink; a dashed `NOW` line with an open dot where the tide is now; nights faintly shaded, as the Tide card's charts are. Tapped, it says `Predicted · NOAA 9410170 · departure {±height}`. Below, each turn's words are the line it was before the curve, so the curve was no update |
| **Conditions** | A ledger, a row each: the name in small caps, an ink arrowhead (up, down, or a dash for no change) against an earlier reading — water and air 3 h back, humidity and pressure the report before, none when there is no earlier reading — then the value, and a sparkline of its recent readings with its window. `Water {°F} ({°C})` (46232's newest, within 6 h; 14 d); `Air {°F} ({°C})` and `Humidity {n}%` (KNZY's newest, within 90 min; 24 h); `Pressure {inHg} ({hPa})` (KNZY's altimeter; 3 d); `Rain {in} ({mm}) in the last hour ({kinds}), {in} ({mm}) in 24 h`, only when either amount is above zero, and then both (a bar a day for 7 d). A tapped row says when it was read, by what, and against when. Below, each row's words are its name, value and arrow |

**An update** is a change in the swell or tide words, as printed: a change
below the page's precision is none. Each update is kept in
`data/briefings/`, with the conditions of that moment.

<!-- Generated by python -m forecast.briefingwording. Edit above this line. -->

### Q1: a quiet morning: one range, nothing coming, no rain

```text
[Briefing updated 7:16 AM]

3–4 ft (0.9–1.2 m). SSW at 13.3 s, holding.

AM low 0.7 ft (0.21 m) at 3:15 AM
AM high 5.3 ft (1.62 m) at 9:32 AM
PM low 1.8 ft (0.55 m) at 3:48 PM
PM high 6.3 ft (1.92 m) at 10:05 PM

Water 67 °F (19.4 °C), up
Air 61 °F (16 °C), down
Humidity 88%, steady
Pressure 30.05 inHg (1018 hPa)
```

### B1: west swell rising at Tanner Banks, waves spread over three feet, rain in the last hour

```text
[Briefing updated 7:16 AM]

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
```

### C1: two sectors offshore, each still to reach the breaks; rain earlier in the day only

```text
[Briefing updated 7:16 AM]

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
```

### M1: a mix: every swell train at the breaks at half the biggest's height or more, a line each, one a compass point

```text
[Briefing updated 7:16 AM]

3–4 ft (0.9–1.2 m). SSW at 15.4 s, fading. SSW at 14.3 s, holding. W at 10.0 s, building.

AM low 0.7 ft (0.21 m) at 3:15 AM
AM high 5.3 ft (1.62 m) at 9:32 AM
PM low 1.8 ft (0.55 m) at 3:48 PM
PM high 6.3 ft (1.92 m) at 10:05 PM

Water 67 °F (19.4 °C), up
Air 61 °F (16 °C), down
Humidity 88%, steady
Pressure 30.05 inHg (1018 hPa)
```

### H1: the lead train has no heading, and no status yet: their slots drop with their words

```text
[Briefing updated 7:16 AM]

3–4 ft (0.9–1.2 m). At 13.3 s.

AM low 0.7 ft (0.21 m) at 3:15 AM
AM high 5.3 ft (1.62 m) at 9:32 AM
PM low 1.8 ft (0.55 m) at 3:48 PM
PM high 6.3 ft (1.92 m) at 10:05 PM

Water 67 °F (19.4 °C), up
Air 61 °F (16 °C), down
Humidity 88%, steady
Pressure 30.05 inHg (1018 hPa)
```

### D1: 46232 dark: the swell says so and nothing else

```text
[Briefing updated 7:16 AM]

No spectrum from CDIP 191 since Oct 21, 3:00 PM.

AM low 0.7 ft (0.21 m) at 3:15 AM
AM high 5.3 ft (1.62 m) at 9:32 AM
PM low 1.8 ft (0.55 m) at 3:48 PM
PM high 6.3 ft (1.92 m) at 10:05 PM

Water 67 °F (19.4 °C), up
Air 61 °F (16 °C), down
Humidity 88%, steady
Pressure 30.05 inHg (1018 hPa)
```

### K1: no water temperature, no KNZY report, a minus tide

```text
[Briefing updated 7:16 AM]

3–4 ft (0.9–1.2 m). SSW at 13.3 s, holding.

AM low −0.7 ft (−0.21 m) at 6:40 AM
PM high 5.6 ft (1.71 m) at 1:05 PM
```

### Y1: yesterday's update, read this morning

```text
[Briefing updated Oct 21, 12:06 PM]

3–4 ft (0.9–1.2 m). SSW at 13.3 s, holding.

AM low 0.7 ft (0.21 m) at 3:15 AM
AM high 5.3 ft (1.62 m) at 9:32 AM
PM low 1.8 ft (0.55 m) at 3:48 PM
PM high 6.3 ft (1.92 m) at 10:05 PM

Water 67 °F (19.4 °C), up
Air 61 °F (16 °C), down
Humidity 88%, steady
Pressure 30.05 inHg (1018 hPa)
```

### X1: nothing built yet

```text
(no Briefing: the fold is not drawn)
```
