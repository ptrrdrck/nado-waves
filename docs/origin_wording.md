# Origin wording: the formula, and every permutation

The owner's formula for the Origin fold, decided 2026-10-10 and on the page
since then. The section at the end lists every permutation. It is not typed:
`python -m forecast.originwording` lifts the Origin code out of
`app/forecast.html`, runs it in Node on one made-up Origin block per branch,
and writes what the page prints. `tests/test_originwording.py` fails if the
page and this file disagree. Edit the wording above the generated section;
the numbers in the cases are made up, and dates are Pacific.

## The formula

Every entry is three lines in a fixed order, as in the owner's 2026-10-04
design: **what**, **sent when and from where**, **how it is known**. Each line
is a fixed run of slots. A slot with no value is dropped together with its
joining words. Nothing is reworded per case.

| Line | Slot | Hurricane | Reading, placed | Reading, unplaced: split bearing | Reading, unplaced: not at 46047 |
|---|---|---|---|---|---|
| 1 what | head | `Hurricane {Name}` | `{Sea}` | `Unplaced storm` | `Unplaced storm` |
| 1 | tag (grey) | none | `last readable arrival` if past, else none | same | same |
| 2 sent | train | `The {T} s train` (the card's train) | `The {T} s train` (the card's train now; its peak-hour train if past) | same | same |
| 2 | when | `, sent {date}` (NHC's fix) | `, sent about {date}` (fitted off the swell) | same | same |
| 2 | distance | ` from about {mi} ({km}) away`, to 100 | ` from about {mi} ({km}) away`, to 500 | same | same |
| 2 | direction | `, bearing {deg}° {pt}` | `, bearing {deg}° {pt}` | `, with a split bearing ({d1}° {pt} or {d2}° {pt}[ or …])` | none |
| 2 | strength | ` with winds of {mph} ({kt})` + ` and {mb} mb pressure` if the fix has one | none | none | none |
| 2 | end | `.` | `.` | `.` | `.` |
| 3 known | method | `Timing and direction beat NHC's track moved earlier` | `Read backwards off the swell` | same | same |
| 3 | evidence | ` {b} of {n} times at {buoy}` + ` over {h} h` if known, then `, and {b} of {n} times at {buoy}` + ` over {h} h` per further gate buoy, then `.` | arriving: `, {h} h so far.` past: ` over {h} h. Arrived {date}, no longer arriving.` | same | same |

Source lines, one per claim on screen, each present only when its entry is,
in this order:

| # | Present when | Text |
|---|---|---|
| S1 | always | `Trains read off the spectrum at {46232}` + `, and storms read backwards from them` if any reading is shown + `; direction at {46047}` if any reading has a bearing |
| S2 | a hurricane is shown | `Hurricane position, winds and pressure: National Hurricane Center best track for {Name}, an analysis.` The name links to NHC's best-track file for that storm (`https://ftp.nhc.noaa.gov/atcf/btk/b{basin}{nn}{year}.dat`). Two storms: `best tracks for {Name} and {Name}`, each linked. `position and winds` when no fix shown has a pressure |
| S3 | a reading has a split bearing | `Unplaced storm: {46047} holds that train from multiple directions, so no place is given.` |
| S4 | a reading is not at 46047 | one buoy: `Unplaced storm: {46047} does not have that train.` two: `Unplaced storm: neither {A} nor {B} has that train.` |

Every buoy is named as NDBC names it, from `now.json`'s `station_names`,
which covers the bearing buoys and every gate buoy a shown hurricane was
matched at.

Fold-level rules (unchanged): hurricanes first, then current readings; a
reading of the same train as a shown hurricane is dropped; the last readable
arrival appears only when nothing is arriving; with nothing at all, `No
readable arrival in the last {21} days` and S1 alone.

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
No readable arrival in the last 21 days
Trains read off the spectrum at Point Loma South, CA (NDBC 46232).
```

### L1: last readable arrival, placed

```text
South Pacific  last readable arrival
The 15.4 s train, sent about Oct 1 from about 4,500 mi (7,500 km) away, bearing 212° SSW.
Read backwards off the swell over 18 h. Arrived Oct 6, no longer arriving.
Trains read off the spectrum at Point Loma South, CA (NDBC 46232), and storms read backwards from them; direction at Tanner Banks, CA (NDBC 46047).
```

### L2: last readable arrival, unplaced: split bearing

```text
Unplaced storm  last readable arrival
The 15.4 s train, sent about Oct 1 from about 4,500 mi (7,500 km) away, with a split bearing (205° SSW or 285° WNW).
Read backwards off the swell over 18 h. Arrived Oct 6, no longer arriving.
Trains read off the spectrum at Point Loma South, CA (NDBC 46232), and storms read backwards from them.
Unplaced storm: Tanner Banks, CA (NDBC 46047) holds that train from multiple directions, so no place is given.
```

### L3: last readable arrival, unplaced: 46047 does not have it

```text
Unplaced storm  last readable arrival
The 15.4 s train, sent about Oct 1 from about 4,500 mi (7,500 km) away.
Read backwards off the swell over 18 h. Arrived Oct 6, no longer arriving.
Trains read off the spectrum at Point Loma South, CA (NDBC 46232), and storms read backwards from them.
Unplaced storm: Tanner Banks, CA (NDBC 46047) does not have that train.
```

### C1: arriving, placed

```text
South Pacific
The 15.1 s train, sent about Oct 1 from about 4,500 mi (7,500 km) away, bearing 212° SSW.
Read backwards off the swell, 18 h so far.
Trains read off the spectrum at Point Loma South, CA (NDBC 46232), and storms read backwards from them; direction at Tanner Banks, CA (NDBC 46047).
```

### C2: arriving, unplaced: split three ways

```text
Unplaced storm
The 15.1 s train, sent about Oct 1 from about 4,500 mi (7,500 km) away, with a split bearing (140° SE or 196° SSW or 254° WSW).
Read backwards off the swell, 18 h so far.
Trains read off the spectrum at Point Loma South, CA (NDBC 46232), and storms read backwards from them.
Unplaced storm: Tanner Banks, CA (NDBC 46047) holds that train from multiple directions, so no place is given.
```

### C3: arriving, unplaced: 46047 does not have it

```text
Unplaced storm
The 15.1 s train, sent about Oct 1 from about 4,500 mi (7,500 km) away.
Read backwards off the swell, 18 h so far.
Trains read off the spectrum at Point Loma South, CA (NDBC 46232), and storms read backwards from them.
Unplaced storm: Tanner Banks, CA (NDBC 46047) does not have that train.
```

### C4: arriving, one of each

```text
South Pacific
The 15.1 s train, sent about Oct 1 from about 4,500 mi (7,500 km) away, bearing 212° SSW.
Read backwards off the swell, 18 h so far.
Unplaced storm
The 13.2 s train, sent about Oct 2 from about 3,000 mi (5,000 km) away, with a split bearing (205° SSW or 285° WNW).
Read backwards off the swell, 18 h so far.
Unplaced storm
The 11.8 s train, sent about Oct 4 from about 2,000 mi (3,000 km) away.
Read backwards off the swell, 18 h so far.
Trains read off the spectrum at Point Loma South, CA (NDBC 46232), and storms read backwards from them; direction at Tanner Banks, CA (NDBC 46047).
Unplaced storm: Tanner Banks, CA (NDBC 46047) holds that train from multiple directions, so no place is given.
Unplaced storm: Tanner Banks, CA (NDBC 46047) does not have that train.
```

### H1: hurricane, one gate buoy

```text
Hurricane Rachel
The 14.3 s train, sent Oct 1 from about 1,000 mi (1,700 km) away, bearing 196° SSW with winds of 121 mph (105 kt) and 950 mb pressure.
Timing and direction beat NHC's track moved earlier 46 of 50 times at Tanner Banks, CA (NDBC 46047) over 30 h.
Trains read off the spectrum at Point Loma South, CA (NDBC 46232).
Hurricane position, winds and pressure: National Hurricane Center best track for [Rachel](https://ftp.nhc.noaa.gov/atcf/btk/bep182026.dat), an analysis.
```

### H2: hurricane, two gate buoys

```text
Hurricane Rachel
The 14.3 s train, sent Oct 1 from about 1,000 mi (1,700 km) away, bearing 196° SSW with winds of 121 mph (105 kt) and 950 mb pressure.
Timing and direction beat NHC's track moved earlier 39 of 50 times at Tanner Banks, CA (NDBC 46047) over 30 h, and 28 of 40 times at San Clemente Basin, CA (NDBC 46086) over 26 h.
Trains read off the spectrum at Point Loma South, CA (NDBC 46232).
Hurricane position, winds and pressure: National Hurricane Center best track for [Rachel](https://ftp.nhc.noaa.gov/atcf/btk/bep182026.dat), an analysis.
```

### H3: hurricane, no hours, no pressure

```text
Hurricane Rachel
The 14.3 s train, sent Oct 1 from about 1,000 mi (1,700 km) away, bearing 196° SSW with winds of 121 mph (105 kt).
Timing and direction beat NHC's track moved earlier 11 of 20 times at Tanner Banks, CA (NDBC 46047).
Trains read off the spectrum at Point Loma South, CA (NDBC 46232).
Hurricane position and winds: National Hurricane Center best track for [Rachel](https://ftp.nhc.noaa.gov/atcf/btk/bep182026.dat), an analysis.
```

### H4: two hurricanes

```text
Hurricane Rachel
The 14.3 s train, sent Oct 1 from about 1,000 mi (1,700 km) away, bearing 196° SSW with winds of 121 mph (105 kt) and 950 mb pressure.
Timing and direction beat NHC's track moved earlier 46 of 50 times at Tanner Banks, CA (NDBC 46047) over 30 h.
Hurricane Sergio
The 12.5 s train, sent Oct 8 from about 1,300 mi (2,200 km) away, bearing 178° S with winds of 109 mph (95 kt) and 964 mb pressure.
Timing and direction beat NHC's track moved earlier 37 of 50 times at Tanner Banks, CA (NDBC 46047) over 22 h.
Trains read off the spectrum at Point Loma South, CA (NDBC 46232).
Hurricane position, winds and pressure: National Hurricane Center best tracks for [Rachel](https://ftp.nhc.noaa.gov/atcf/btk/bep182026.dat) and [Sergio](https://ftp.nhc.noaa.gov/atcf/btk/bep202026.dat), an analysis.
```

### M1: hurricane and a placed reading

```text
Hurricane Rachel
The 14.3 s train, sent Oct 1 from about 1,000 mi (1,700 km) away, bearing 196° SSW with winds of 121 mph (105 kt) and 950 mb pressure.
Timing and direction beat NHC's track moved earlier 46 of 50 times at Tanner Banks, CA (NDBC 46047) over 30 h.
South Pacific
The 15.1 s train, sent about Oct 1 from about 4,500 mi (7,500 km) away, bearing 212° SSW.
Read backwards off the swell, 18 h so far.
Trains read off the spectrum at Point Loma South, CA (NDBC 46232), and storms read backwards from them; direction at Tanner Banks, CA (NDBC 46047).
Hurricane position, winds and pressure: National Hurricane Center best track for [Rachel](https://ftp.nhc.noaa.gov/atcf/btk/bep182026.dat), an analysis.
```

### M3: hurricane and a split bearing, as live on 2026-10-10

```text
Hurricane Rachel
The 14.3 s train, sent Oct 1 from about 1,000 mi (1,700 km) away, bearing 196° SSW with winds of 121 mph (105 kt) and 950 mb pressure.
Timing and direction beat NHC's track moved earlier 46 of 50 times at Tanner Banks, CA (NDBC 46047) over 30 h.
Unplaced storm
The 20.0 s train, sent about Oct 1 from about 9,500 mi (15,000 km) away, with a split bearing (140° SE or 196° SSW or 254° WSW).
Read backwards off the swell, 18 h so far.
Trains read off the spectrum at Point Loma South, CA (NDBC 46232), and storms read backwards from them.
Hurricane position, winds and pressure: National Hurricane Center best track for [Rachel](https://ftp.nhc.noaa.gov/atcf/btk/bep182026.dat), an analysis.
Unplaced storm: Tanner Banks, CA (NDBC 46047) holds that train from multiple directions, so no place is given.
```

### M2: hurricane and a last readable arrival (the last is not shown)

```text
Hurricane Rachel
The 14.3 s train, sent Oct 1 from about 1,000 mi (1,700 km) away, bearing 196° SSW with winds of 121 mph (105 kt) and 950 mb pressure.
Timing and direction beat NHC's track moved earlier 46 of 50 times at Tanner Banks, CA (NDBC 46047) over 30 h.
Trains read off the spectrum at Point Loma South, CA (NDBC 46232).
Hurricane position, winds and pressure: National Hurricane Center best track for [Rachel](https://ftp.nhc.noaa.gov/atcf/btk/bep182026.dat), an analysis.
```
