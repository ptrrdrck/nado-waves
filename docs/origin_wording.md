# Origin wording: the formula, and every permutation

The owner's formula for the Origin fold, decided 2026-10-10, rewritten
2026-10-14, and on the page since then. The section at the end lists every permutation. It is not typed:
`python -m forecast.originwording` lifts the Origin code out of
`app/forecast.html`, runs it in Node on one made-up Origin block per branch,
and writes what the page prints. `tests/test_originwording.py` fails if the
page and this file disagree. Edit the wording above the generated section;
the numbers in the cases are made up, and dates are Pacific.

## The formula

Every entry is a head and one paragraph (owner's rewrite, 2026-10-14; three
lines before that, in the owner's 2026-10-04 design): **what**, then **sent
when and from where**, **where the direction comes from** and **how it is
known**, run on. Each part is a fixed run of slots. A slot with no
value is dropped together with its joining words. Nothing is reworded per case.

| Part | Slot | Hurricane | Reading, placed | Reading, unplaced: split bearing | Reading, unplaced: not at 46047 |
|---|---|---|---|---|---|
| 0 past | opening line, if past | `No readable swell arriving here now. The last one was:` | same | same | same |
| 1 what | head | `Hurricane {Name}` or `Tropical Storm {Name}`, the name linked to NHC's page, then its symbol | `{Sea}` | `Unplaced storm` | `Unplaced storm` |
| 2 sent | train | `The {T} s train` (the card's train) | `The {T} s train` (the card's train now; its peak-hour train if past) | same | same |
| 2 | when | `, sent {date}` (NHC's fix) | `, sent about {date}` (fitted off the swell) | same | same |
| 2 | distance | ` from about {mi} ({km}) away`, to 100 | ` from about {mi} ({km}) away`, to 500 | same | same |
| 2 | end | `.` | `.` | `.` | `.` |
| 3 held | source | ` NHC places it at {deg}° {pt}, with winds of {mph} ({kt})` + ` and {mb} mb pressure` if the fix has one, then `.`; past: + ` Arrived {date}, no longer arriving.` | ` {46047} holds this train from {deg}° {pt}.` | ` {46047} holds this train from {d1}° {pt} and {d2}° {pt}, so no place is given.` (three: `{d1}, {d2} and {d3}`) | ` {46047} does not have this train, so no place is given.` |
| 4 known | method | ` Its track beat`; none if past | ` Read over {h} h of swell` | same | same |
| 4 | evidence | ` {b} of {n} earlier copies at {buoy}` + ` over {h} h` if known, then `, and {b} of {n} at {buoy}` + ` over {h} h` per further gate buoy, then `.`; none if past | arriving: ` so far.` past: `. Arrived {date}, no longer arriving.` | same | same |

A past entry's lines are at 15 px, the size its old grey tag was, with a blank
line between its opening line and the head (owner's request, 2026-10-13); the
head stays at the storm name's size. A storm's symbol is the meteorological
tropical cyclone symbol, two arms around the eye as a Northern Hemisphere storm
turns: the eye open for a tropical storm, filled for a hurricane, in ink. A
storm's name links to NHC's page for that storm, with its advisories, track and
cone map (`https://www.nhc.noaa.gov/archive/{year}/{NAME}_graphics.php`), not
the best-track file the card reads; only the name is the link, and the Origins
chart's readout names the storm unlinked. A storm's past `{date}` is the first
moment it was named at the tab with the fix that sent the train shown, so a
train never arrives before it was sent.

**No provenance follows the entries** (owner's call, 2026-10-14): how trains
are read off 46232, how storms are read backwards from them and how a storm is
matched to NHC's track are on `docs.html`. What the provenance said about a
reading's direction is in part 3 now, beside the train, and NHC's link is on
the storm's name.

Every buoy is named as NDBC names it without its state, from `now.json`'s
`station_names`, which covers the bearing buoys and every gate buoy a shown
hurricane was matched at, and by the number of whoever runs it: CDIP's for a
buoy with one (`station_cdips`), so 46232 is "Point Loma South (CDIP 191)",
NDBC's otherwise, "Tanner Banks (NDBC 46047)" (owner's request, 2026-10-13).

Fold-level rules (unchanged): hurricanes first, then current readings; a
reading of the same train as a shown hurricane is dropped; the last readable
arrival appears only when nothing is arriving, and is whichever ended later:
Origin's last reading at the tab, or the last storm named there (from
`origins.json`; owner's report, 2026-10-12), a storm's in the hurricane's
form with its opening line and "Arrived {date}, no longer arriving."; with
nothing at all, `No readable swell in the last {21} days.` alone.

### Decided 2026-10-14

From the owner's rewrite of North's last readable arrival, a split bearing:

- **The opening line is "No readable swell arriving here now. The last one
  was:"**, without the tab's name.
- **One paragraph under the head.** The train's sentence, the buoy's and how
  it is known run on, where each was its own line.
- **A reading's direction is its own sentence, naming the buoy**: "Tanner
  Banks (NDBC 46047) holds this train from 190° S and 276° W, so no place is
  given." It replaces ", with a split bearing (… or …)" and the source line
  saying why. A placed reading says the same without "so no place is given"
  (", bearing …" left line 2); a train 46047 does not have, "Tanner Banks
  (NDBC 46047) does not have this train, so no place is given."
- **No provenance.** Storm matching is explained on `docs.html`. NHC's link
  moved onto the storm's name in the head, the name alone.
- **"No readable swell in the last 21 days."** where nothing was read.

Second pass, the same day, from the owner's answers:

- **A named storm's direction is a sentence of its own too**, naming NHC as
  a reading's names its buoy: "NHC places it at 196° SSW, with winds of
  121 mph (105 kt) and 950 mb pressure." It still follows the day the train
  was sent, so the winds read as the fix's, not the storm's now.
- **The counts, shortened**: "Its track beat 46 of 50 earlier copies at
  Tanner Banks (NDBC 46047) over 30 h", where it read "Timing and direction
  beat NHC's track moved earlier 46 of 50 times at …". "earlier copies" is
  said once; a second gate buoy reads ", and 28 of 40 at …". What the copies
  are, and that they are scored on timing and direction, is on `docs.html`.
- **"Read over {h} h of swell"**, where it read "Read backwards off the
  swell"; "… so far." while it runs.

### Decided 2026-10-12

From the owner's rewrite of South's Tropical Storm Rachel:

- **A named storm carries its symbol** after its name, the tropical storm's
  or the hurricane's.
- **A last readable arrival opens with a line**, "No readable trains arriving
  here now ({tab}). The last one read was:", in place of the grey tag beside
  the head, and its lines are at the tag's size.
- **A storm's last arrival is two lines**: the head, then line 2 ending
  "Arrived {date}, no longer arriving." The counts line goes.
- **"Arrived" is the train's own day.** It was the storm's first moment at the
  tab, which put "Arrived Oct 5" under a train sent Oct 10.
- **`Trains: {46232}`** where nothing is read backwards.

### Decided 2026-10-10

First pass:

- **No percentage.** "92%" repeated the first count as a bare figure beside
  "match", where it read as a probability.
- **"sent about {date}" on a reading.** That date is fitted off the swell and
  is as uncertain as the distance. NHC's fix is a time, so a hurricane's is
  bare.
- **Pressure** from the best track, beside the winds, both from the fix that
  sent the train. A fix with no pressure drops the slot.

Second pass, from the owner's rewrite of two live origins:

- **Line 1 is the head alone.** A hurricane's winds and pressure move to the
  end of line 2, after the day it was sent, so they read as the storm's
  strength when it sent the train, not now.
- **Line 2 is a sentence**: "The … train, sent … from about … away, bearing
  …". Every kind has "away"; a split bearing reads ", with a split bearing
  (… or …)".
- **A split bearing is an unplaced storm** under the same head as a train
  46047 does not have. Line 2 and the source line say which: "holds that
  train from multiple directions" (live, 46047 held one in three), or "does
  not have that train".
- **No match word.** Line 3 is the counts alone, "times" at each buoy. The
  verb stays "beat": the count is how many copies of the same track, moved
  earlier in time, the real timing and direction did better than (not how
  many times anything matched). The words strong / partial / weak stay in
  `forecast.stormtrack` and on `docs.html`, which reads the counts against
  the control.
- **NHC's line names the storm** and links the name to NHC's best-track
  file; it comes before the unplaced lines.

### What it replaced

Before 2026-10-10 the fold read, among other things:

- a split bearing as "Unplaced storm" with no directions, and the source line
  "neither Tanner Banks, CA (NDBC 46047) has that train". That was false for
  a split, and since §38a dropped 46086 it was a "neither" with nothing after
  it;
- "… bearing 196° SSW on Oct 1", which did not say Oct 1 was the day the
  train was sent;
- "30 h read so far" on a hurricane's line 2, about the gate buoy that
  matched best, without naming it, in the same words a reading uses for
  hours read at 46232;
- "winds 121 mph (105 kt)" unlabelled, so a storm that had weakened since
  still read as a hurricane;
- "and storms read backwards from them" when nothing had been read.

## Every permutation

Cases: E is empty, L is the last readable arrival, C is arriving now, H is a
hurricane, M is a mix. Grey tags are set off by two spaces, and a link
is shown as `[text](url)`.

<!-- Generated by python -m forecast.originwording. Edit above this line. -->

### E0: nothing in 21 days

```text
No readable swell in the last 21 days.
```

### L1: last readable arrival, placed

```text
No readable swell arriving here now. The last one was:
South Pacific
The 15.4 s train, sent about Oct 1 from about 4,500 mi (7,500 km) away. Tanner Banks (NDBC 46047) holds this train from 212° SSW. Read over 18 h of swell. Arrived Oct 6, no longer arriving.
```

### L2: last readable arrival, unplaced: split bearing

```text
No readable swell arriving here now. The last one was:
Unplaced storm
The 15.4 s train, sent about Oct 1 from about 4,500 mi (7,500 km) away. Tanner Banks (NDBC 46047) holds this train from 205° SSW and 285° WNW, so no place is given. Read over 18 h of swell. Arrived Oct 6, no longer arriving.
```

### L3: last readable arrival, unplaced: 46047 does not have it

```text
No readable swell arriving here now. The last one was:
Unplaced storm
The 15.4 s train, sent about Oct 1 from about 4,500 mi (7,500 km) away. Tanner Banks (NDBC 46047) does not have this train, so no place is given. Read over 18 h of swell. Arrived Oct 6, no longer arriving.
```

### L4: last readable arrival, a storm named here after Origin's last reading

```text
No readable swell arriving here now. The last one was:
Tropical Storm [Rachel](https://www.nhc.noaa.gov/archive/2026/RACHEL_graphics.php) {tropical storm symbol}
The 10.5 s train, sent Oct 8 from about 800 mi (1,300 km) away. NHC places it at 200° SSW, with winds of 69 mph (60 kt) and 985 mb pressure. Arrived Oct 11, no longer arriving.
```

### L5: last readable arrival, Origin's reading ended after the last storm named here

```text
No readable swell arriving here now. The last one was:
Aleutian storm track
The 15.4 s train, sent about Oct 1 from about 4,500 mi (7,500 km) away. Tanner Banks (NDBC 46047) holds this train from 212° SSW. Read over 18 h of swell. Arrived Sep 30, no longer arriving.
```

### C1: arriving, placed

```text
South Pacific
The 15.1 s train, sent about Oct 1 from about 4,500 mi (7,500 km) away. Tanner Banks (NDBC 46047) holds this train from 212° SSW. Read over 18 h of swell so far.
```

### C2: arriving, unplaced: split three ways

```text
Unplaced storm
The 15.1 s train, sent about Oct 1 from about 4,500 mi (7,500 km) away. Tanner Banks (NDBC 46047) holds this train from 140° SE, 196° SSW and 254° WSW, so no place is given. Read over 18 h of swell so far.
```

### C3: arriving, unplaced: 46047 does not have it

```text
Unplaced storm
The 15.1 s train, sent about Oct 1 from about 4,500 mi (7,500 km) away. Tanner Banks (NDBC 46047) does not have this train, so no place is given. Read over 18 h of swell so far.
```

### C4: arriving, one of each

```text
South Pacific
The 15.1 s train, sent about Oct 1 from about 4,500 mi (7,500 km) away. Tanner Banks (NDBC 46047) holds this train from 212° SSW. Read over 18 h of swell so far.
Unplaced storm
The 13.2 s train, sent about Oct 2 from about 3,000 mi (5,000 km) away. Tanner Banks (NDBC 46047) holds this train from 205° SSW and 285° WNW, so no place is given. Read over 18 h of swell so far.
Unplaced storm
The 11.8 s train, sent about Oct 4 from about 2,000 mi (3,000 km) away. Tanner Banks (NDBC 46047) does not have this train, so no place is given. Read over 18 h of swell so far.
```

### H1: hurricane, one gate buoy

```text
Hurricane [Rachel](https://www.nhc.noaa.gov/archive/2026/RACHEL_graphics.php) {hurricane symbol}
The 14.3 s train, sent Oct 1 from about 1,000 mi (1,700 km) away. NHC places it at 196° SSW, with winds of 121 mph (105 kt) and 950 mb pressure. Its track beat 46 of 50 earlier copies at Tanner Banks (NDBC 46047) over 30 h.
```

### H2: hurricane, two gate buoys

```text
Hurricane [Rachel](https://www.nhc.noaa.gov/archive/2026/RACHEL_graphics.php) {hurricane symbol}
The 14.3 s train, sent Oct 1 from about 1,000 mi (1,700 km) away. NHC places it at 196° SSW, with winds of 121 mph (105 kt) and 950 mb pressure. Its track beat 39 of 50 earlier copies at Tanner Banks (NDBC 46047) over 30 h, and 28 of 40 at San Clemente Basin (NDBC 46086) over 26 h.
```

### H3: hurricane, no hours, no pressure

```text
Hurricane [Rachel](https://www.nhc.noaa.gov/archive/2026/RACHEL_graphics.php) {hurricane symbol}
The 14.3 s train, sent Oct 1 from about 1,000 mi (1,700 km) away. NHC places it at 196° SSW, with winds of 121 mph (105 kt). Its track beat 11 of 20 earlier copies at Tanner Banks (NDBC 46047).
```

### H4: two hurricanes

```text
Hurricane [Rachel](https://www.nhc.noaa.gov/archive/2026/RACHEL_graphics.php) {hurricane symbol}
The 14.3 s train, sent Oct 1 from about 1,000 mi (1,700 km) away. NHC places it at 196° SSW, with winds of 121 mph (105 kt) and 950 mb pressure. Its track beat 46 of 50 earlier copies at Tanner Banks (NDBC 46047) over 30 h.
Hurricane [Sergio](https://www.nhc.noaa.gov/archive/2026/SERGIO_graphics.php) {hurricane symbol}
The 12.5 s train, sent Oct 8 from about 1,300 mi (2,200 km) away. NHC places it at 178° S, with winds of 109 mph (95 kt) and 964 mb pressure. Its track beat 37 of 50 earlier copies at Tanner Banks (NDBC 46047) over 22 h.
```

### T1: a hurricane since weakened: its tropical storm fix sent the train

```text
Tropical Storm [Rachel](https://www.nhc.noaa.gov/archive/2026/RACHEL_graphics.php) {tropical storm symbol}
The 10.5 s train, sent Oct 8 from about 800 mi (1,300 km) away. NHC places it at 200° SSW, with winds of 69 mph (60 kt) and 985 mb pressure. Its track beat 36 of 43 earlier copies at Tanner Banks (NDBC 46047) over 40 h.
```

### T3: one storm's swell cut into two rows at this break

```text
Tropical Storm [Rachel](https://www.nhc.noaa.gov/archive/2026/RACHEL_graphics.php) {tropical storm symbol}
The 10.5 and 11.1 s trains, sent Oct 8 from about 800 mi (1,300 km) away. NHC places it at 200° SSW, with winds of 69 mph (60 kt) and 985 mb pressure. Its track beat 36 of 43 earlier copies at Tanner Banks (NDBC 46047) over 40 h.
```

### T2: a tropical storm and a hurricane

```text
Tropical Storm [Rachel](https://www.nhc.noaa.gov/archive/2026/RACHEL_graphics.php) {tropical storm symbol}
The 10.5 s train, sent Oct 8 from about 800 mi (1,300 km) away. NHC places it at 200° SSW, with winds of 69 mph (60 kt) and 985 mb pressure. Its track beat 36 of 43 earlier copies at Tanner Banks (NDBC 46047) over 40 h.
Hurricane [Sergio](https://www.nhc.noaa.gov/archive/2026/SERGIO_graphics.php) {hurricane symbol}
The 12.5 s train, sent Oct 8 from about 1,300 mi (2,200 km) away. NHC places it at 178° S, with winds of 109 mph (95 kt) and 964 mb pressure. Its track beat 37 of 50 earlier copies at Tanner Banks (NDBC 46047) over 22 h.
```

### M1: hurricane and a placed reading

```text
Hurricane [Rachel](https://www.nhc.noaa.gov/archive/2026/RACHEL_graphics.php) {hurricane symbol}
The 14.3 s train, sent Oct 1 from about 1,000 mi (1,700 km) away. NHC places it at 196° SSW, with winds of 121 mph (105 kt) and 950 mb pressure. Its track beat 46 of 50 earlier copies at Tanner Banks (NDBC 46047) over 30 h.
South Pacific
The 15.1 s train, sent about Oct 1 from about 4,500 mi (7,500 km) away. Tanner Banks (NDBC 46047) holds this train from 212° SSW. Read over 18 h of swell so far.
```

### M3: hurricane and a split bearing, as live on 2026-10-10

```text
Hurricane [Rachel](https://www.nhc.noaa.gov/archive/2026/RACHEL_graphics.php) {hurricane symbol}
The 14.3 s train, sent Oct 1 from about 1,000 mi (1,700 km) away. NHC places it at 196° SSW, with winds of 121 mph (105 kt) and 950 mb pressure. Its track beat 46 of 50 earlier copies at Tanner Banks (NDBC 46047) over 30 h.
Unplaced storm
The 20.0 s train, sent about Oct 1 from about 9,500 mi (15,000 km) away. Tanner Banks (NDBC 46047) holds this train from 140° SE, 196° SSW and 254° WSW, so no place is given. Read over 18 h of swell so far.
```

### M2: hurricane and a last readable arrival (the last is not shown)

```text
Hurricane [Rachel](https://www.nhc.noaa.gov/archive/2026/RACHEL_graphics.php) {hurricane symbol}
The 14.3 s train, sent Oct 1 from about 1,000 mi (1,700 km) away. NHC places it at 196° SSW, with winds of 121 mph (105 kt) and 950 mb pressure. Its track beat 46 of 50 earlier copies at Tanner Banks (NDBC 46047) over 30 h.
```
