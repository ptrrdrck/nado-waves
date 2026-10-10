# Origin wording: every permutation, and a formula for them

For the owner to edit, 2026-10-10. Nothing on the page has changed yet.

The examples below are not typed by hand. The "Now" text comes from the page's
own `originFor`, `originBody` and helpers, lifted out of `app/forecast.html`
and run in Node on made-up Origin blocks, one for each branch the code can
take. The "Proposed" text comes from a prototype of the formula below, run on
the same inputs. Dates are Pacific. The numbers are made up; only the wording
is under review.

## What the current wording gets wrong

1. **A withheld bearing looks the same as no bearing, and the source line is
   false.** When 46047 has the train but holds it from two directions
   (BRIEFING §38, `bearing_lobes`), the card reads "Unplaced storm" and the
   source says "neither Tanner Banks … has that train". It does have it. The
   directions it held aren't listed either, though CLAUDE.md says a withheld
   arrival "lists the directions it held". Compare L2 and L3, and C2 and C3:
   each pair is identical now.
2. **"neither Tanner Banks, CA (NDBC 46047) has that train"** is a "neither"
   with nothing after it. Since §38a dropped 46086, Origin's direction comes
   from one buoy only.
3. **"on Oct 1" doesn't say what happened on Oct 1.** It is the day the train
   was SENT: NHC's fix for a hurricane, the dispersion fit's start for a
   reading. On a current entry, which has no "Arrived" line beside it, it
   reads like the arrival date.
4. **"N h read so far" means two different things.** On a reading it is hours
   of the ridge read at 46232. On a hurricane it is hours since the storm's
   band began at the GATE buoy (46047 or 46086, whichever matched best), and
   it sits on the line about 46232's train without naming that buoy.
5. **A hurricane's winds are unlabelled.** "winds 121 mph (105 kt)" are from
   the fix that sent the train, not the storm now. That is what made Rachel
   read as a hurricane after NHC had a tropical storm.
6. **"92%" repeats the first count** ("46 of 50") as a bare percentage beside
   the word "match", where it can read as a probability. CLAUDE.md: "A count,
   never a probability or a confidence."
7. **Empty fold:** with nothing found, the source still says "and storms read
   backwards from them".

Not changed, but worth knowing: the same "about X mi … bearing Y°" phrasing
covers two methods. For a hurricane it is NHC's position measured from
46232, rounded to 100. For a reading it is the dispersion distance and
46047's direction, rounded to 500. The proposal leaves the method to line 3
and the source block instead of adding it to line 2.

## The formula

Every entry is three lines in a fixed order, as in the owner's 2026-10-04
design: **what**, **sent when and from where**, **how it is known**. Each line
is a fixed run of slots. A slot with no value is dropped together with its
joining words. Nothing is reworded per case.

| Line | Slot | Hurricane | Reading, placed | Reading, direction withheld | Reading, no direction |
|---|---|---|---|---|---|
| 1 what | head | `Hurricane {Name}` | `{Sea}` | `Unplaced storm` | `Unplaced storm` |
| 1 | tag | `winds {mph} ({kt}) when sent` | `last readable arrival` if past, else none | same | same |
| 2 sent | train | `{T} s train` | `{T} s train` (card's train now; peak period if past) | same | same |
| 2 | when | `, sent {date}` (NHC fix) | `, sent {date}` (fit start) | same | same |
| 2 | distance | ` from about {mi} ({km})`, to 100 | ` from about {mi} ({km})`, to 500 | same | same |
| 2 | direction | ` bearing {deg}° {pt}` | ` bearing {deg}° {pt}` | ` bearing {d1}° {pt} or {d2}° {pt}` | none |
| 3 known | method | `{Word} match to NHC's track.` | `Read backwards off the swell` | same | same |
| 3 | evidence | ` Timing and direction beat the same track moved earlier {b} of {n} times at {buoy}[ over {h} h]`, then `, and {b} of {n} at {buoy}[ over {h} h]` per further gate buoy | current: `, {h} h so far.` past: ` over {h} h. Arrived {date}, no longer arriving.` | same | same |

Source lines, one per claim on screen, each present only when its entry is:

| # | Present when | Text |
|---|---|---|
| S1 | always | `Trains read off the spectrum at {46232}` + `, and storms read backwards from them` if any reading is shown + `; direction at {46047}` if any reading is placed |
| S2 | a reading has its direction withheld | `Two directions: {46047} has that train from both, so no place is given.` |
| S3 | a reading has no direction | one buoy: `Unplaced storm: {46047} does not have that train.` two: `Unplaced storm: neither {A} nor {B} has that train.` |
| S4 | a hurricane is shown | `Hurricane position and winds: National Hurricane Center best track, an analysis.` |

Fold-level rules (unchanged): hurricanes first, then current readings; a
reading of the same train as a shown hurricane is dropped; the last readable
arrival appears only when nothing is arriving; with nothing at all, `No
readable arrival in the last {21} days` and S1 alone.

### Choices for the owner

- **The percentage.** The proposal drops it (point 6). Keeping it is one slot:
  `{Word} match to NHC's track, {p}%.`
- **"sent {date}" on a reading is a fitted date**, as uncertain as the
  distance. `sent about {date}` would say so.
- **Head for a withheld direction.** It stays "Unplaced storm", with the two
  directions on line 2 and S2 explaining them. A separate head ("Storm, two
  directions") is the alternative.
- **The hurricane tag.** "when sent" ties the winds to line 2's date. If
  pressure is wanted (the b-deck carries it on every fix), it goes in the
  same slot: `winds {mph} ({kt}), {mb} mb when sent`.

## Every permutation

Cases: E is empty, L is last readable arrival, C is arriving now, H is a
hurricane, M is a mix. Placed, withheld and no-direction readings are
separate cases because that is where the current text goes wrong. A tag such
as "last readable arrival" is drawn in grey on the page; here it is separated
by one space in "Now" and two in "Proposed".

### E0 — nothing in 21 days

Now:

```text
No readable arrival in the last 21 days
Trains read off the spectrum at Point Loma South, CA (NDBC 46232), and storms read backwards from them.
```

Proposed:

```text
No readable arrival in the last 21 days
Trains read off the spectrum at Point Loma South, CA (NDBC 46232).
```

### L1 — last, placed

Now:

```text
South Pacific last readable arrival
15.4 s train, about 4,500 mi (7,500 km) bearing 212° SSW on Oct 1.
Arrived Oct 6, no longer arriving.
Trains read off the spectrum at Point Loma South, CA (NDBC 46232), and storms read backwards from them; direction at Tanner Banks, CA (NDBC 46047).
```

Proposed:

```text
South Pacific  last readable arrival
15.4 s train, sent Oct 1 from about 4,500 mi (7,500 km) bearing 212° SSW.
Read backwards off the swell over 18 h. Arrived Oct 6, no longer arriving.
Trains read off the spectrum at Point Loma South, CA (NDBC 46232), and storms read backwards from them; direction at Tanner Banks, CA (NDBC 46047).
```

### L2 — last, bearing withheld (split)

Now:

```text
Unplaced storm last readable arrival
15.4 s train, about 4,500 mi (7,500 km) on Oct 1.
Arrived Oct 6, no longer arriving.
Trains read off the spectrum at Point Loma South, CA (NDBC 46232), and storms read backwards from them.
Unplaced storm: neither Tanner Banks, CA (NDBC 46047) has that train.
```

Proposed:

```text
Unplaced storm  last readable arrival
15.4 s train, sent Oct 1 from about 4,500 mi (7,500 km) bearing 205° SSW or 285° WNW.
Read backwards off the swell over 18 h. Arrived Oct 6, no longer arriving.
Trains read off the spectrum at Point Loma South, CA (NDBC 46232), and storms read backwards from them.
Two directions: Tanner Banks, CA (NDBC 46047) has that train from both, so no place is given.
```

### L3 — last, no bearing buoy had it

Now:

```text
Unplaced storm last readable arrival
15.4 s train, about 4,500 mi (7,500 km) on Oct 1.
Arrived Oct 6, no longer arriving.
Trains read off the spectrum at Point Loma South, CA (NDBC 46232), and storms read backwards from them.
Unplaced storm: neither Tanner Banks, CA (NDBC 46047) has that train.
```

Proposed:

```text
Unplaced storm  last readable arrival
15.4 s train, sent Oct 1 from about 4,500 mi (7,500 km).
Read backwards off the swell over 18 h. Arrived Oct 6, no longer arriving.
Trains read off the spectrum at Point Loma South, CA (NDBC 46232), and storms read backwards from them.
Unplaced storm: Tanner Banks, CA (NDBC 46047) does not have that train.
```

### C1 — arriving, placed

Now:

```text
South Pacific
15.1 s train, about 4,500 mi (7,500 km) bearing 212° SSW on Oct 1.
Read off the swell, 18 h so far.
Trains read off the spectrum at Point Loma South, CA (NDBC 46232), and storms read backwards from them; direction at Tanner Banks, CA (NDBC 46047).
```

Proposed:

```text
South Pacific
15.1 s train, sent Oct 1 from about 4,500 mi (7,500 km) bearing 212° SSW.
Read backwards off the swell, 18 h so far.
Trains read off the spectrum at Point Loma South, CA (NDBC 46232), and storms read backwards from them; direction at Tanner Banks, CA (NDBC 46047).
```

### C2 — arriving, bearing withheld (split)

Now:

```text
Unplaced storm
15.1 s train, about 4,500 mi (7,500 km) on Oct 1.
Read off the swell, 18 h so far.
Trains read off the spectrum at Point Loma South, CA (NDBC 46232), and storms read backwards from them.
Unplaced storm: neither Tanner Banks, CA (NDBC 46047) has that train.
```

Proposed:

```text
Unplaced storm
15.1 s train, sent Oct 1 from about 4,500 mi (7,500 km) bearing 205° SSW or 285° WNW.
Read backwards off the swell, 18 h so far.
Trains read off the spectrum at Point Loma South, CA (NDBC 46232), and storms read backwards from them.
Two directions: Tanner Banks, CA (NDBC 46047) has that train from both, so no place is given.
```

### C3 — arriving, no bearing buoy had it

Now:

```text
Unplaced storm
15.1 s train, about 4,500 mi (7,500 km) on Oct 1.
Read off the swell, 18 h so far.
Trains read off the spectrum at Point Loma South, CA (NDBC 46232), and storms read backwards from them.
Unplaced storm: neither Tanner Banks, CA (NDBC 46047) has that train.
```

Proposed:

```text
Unplaced storm
15.1 s train, sent Oct 1 from about 4,500 mi (7,500 km).
Read backwards off the swell, 18 h so far.
Trains read off the spectrum at Point Loma South, CA (NDBC 46232), and storms read backwards from them.
Unplaced storm: Tanner Banks, CA (NDBC 46047) does not have that train.
```

### C4 — arriving, one placed + one unplaced

Now:

```text
South Pacific
15.1 s train, about 4,500 mi (7,500 km) bearing 212° SSW on Oct 1.
Read off the swell, 18 h so far.
Unplaced storm
11.8 s train, about 2,000 mi (3,000 km) on Oct 4.
Read off the swell, 18 h so far.
Trains read off the spectrum at Point Loma South, CA (NDBC 46232), and storms read backwards from them; direction at Tanner Banks, CA (NDBC 46047).
Unplaced storm: neither Tanner Banks, CA (NDBC 46047) has that train.
```

Proposed:

```text
South Pacific
15.1 s train, sent Oct 1 from about 4,500 mi (7,500 km) bearing 212° SSW.
Read backwards off the swell, 18 h so far.
Unplaced storm
11.8 s train, sent Oct 4 from about 2,000 mi (3,000 km).
Read backwards off the swell, 18 h so far.
Trains read off the spectrum at Point Loma South, CA (NDBC 46232), and storms read backwards from them; direction at Tanner Banks, CA (NDBC 46047).
Unplaced storm: Tanner Banks, CA (NDBC 46047) does not have that train.
```

### H1 — hurricane, one gate buoy, hours

Now:

```text
Hurricane Rachel winds 121 mph (105 kt)
14.3 s train, about 1,000 mi (1,700 km) bearing 196° SSW on Oct 1, 30 h read so far.
Strong match to NHC's track, 92%. Timing and direction beat the same track moved earlier 46 of 50 times at Tanner Banks, CA (NDBC 46047).
Trains read off the spectrum at Point Loma South, CA (NDBC 46232).
National Hurricane Center best track, an analysis.
```

Proposed:

```text
Hurricane Rachel  winds 121 mph (105 kt) when sent
14.3 s train, sent Oct 1 from about 1,000 mi (1,700 km) bearing 196° SSW.
Strong match to NHC's track. Timing and direction beat the same track moved earlier 46 of 50 times at Tanner Banks, CA (NDBC 46047) over 30 h.
Trains read off the spectrum at Point Loma South, CA (NDBC 46232).
Hurricane position and winds: National Hurricane Center best track, an analysis.
```

### H2 — hurricane, two gate buoys

Now:

```text
Hurricane Rachel winds 121 mph (105 kt)
14.3 s train, about 1,000 mi (1,700 km) bearing 196° SSW on Oct 1, 30 h read so far.
Partial match to NHC's track, 78%. Timing and direction beat the same track moved earlier 39 of 50 times at Tanner Banks, CA (NDBC 46047), and 28 of 40 at San Clemente Basin, CA (NDBC 46086).
Trains read off the spectrum at Point Loma South, CA (NDBC 46232).
National Hurricane Center best track, an analysis.
```

Proposed:

```text
Hurricane Rachel  winds 121 mph (105 kt) when sent
14.3 s train, sent Oct 1 from about 1,000 mi (1,700 km) bearing 196° SSW.
Partial match to NHC's track. Timing and direction beat the same track moved earlier 39 of 50 times at Tanner Banks, CA (NDBC 46047) over 30 h, and 28 of 40 at San Clemente Basin, CA (NDBC 46086) over 26 h.
Trains read off the spectrum at Point Loma South, CA (NDBC 46232).
Hurricane position and winds: National Hurricane Center best track, an analysis.
```

### H3 — hurricane, weak, no hours

Now:

```text
Hurricane Rachel winds 121 mph (105 kt)
14.3 s train, about 1,000 mi (1,700 km) bearing 196° SSW on Oct 1.
Weak match to NHC's track, 55%. Timing and direction beat the same track moved earlier 11 of 20 times at Tanner Banks, CA (NDBC 46047).
Trains read off the spectrum at Point Loma South, CA (NDBC 46232).
National Hurricane Center best track, an analysis.
```

Proposed:

```text
Hurricane Rachel  winds 121 mph (105 kt) when sent
14.3 s train, sent Oct 1 from about 1,000 mi (1,700 km) bearing 196° SSW.
Weak match to NHC's track. Timing and direction beat the same track moved earlier 11 of 20 times at Tanner Banks, CA (NDBC 46047).
Trains read off the spectrum at Point Loma South, CA (NDBC 46232).
Hurricane position and winds: National Hurricane Center best track, an analysis.
```

### M1 — hurricane + placed reading

Now:

```text
Hurricane Rachel winds 121 mph (105 kt)
14.3 s train, about 1,000 mi (1,700 km) bearing 196° SSW on Oct 1, 30 h read so far.
Strong match to NHC's track, 92%. Timing and direction beat the same track moved earlier 46 of 50 times at Tanner Banks, CA (NDBC 46047).
South Pacific
15.1 s train, about 4,500 mi (7,500 km) bearing 212° SSW on Oct 1.
Read off the swell, 18 h so far.
Trains read off the spectrum at Point Loma South, CA (NDBC 46232), and storms read backwards from them; direction at Tanner Banks, CA (NDBC 46047).
National Hurricane Center best track, an analysis.
```

Proposed:

```text
Hurricane Rachel  winds 121 mph (105 kt) when sent
14.3 s train, sent Oct 1 from about 1,000 mi (1,700 km) bearing 196° SSW.
Strong match to NHC's track. Timing and direction beat the same track moved earlier 46 of 50 times at Tanner Banks, CA (NDBC 46047) over 30 h.
South Pacific
15.1 s train, sent Oct 1 from about 4,500 mi (7,500 km) bearing 212° SSW.
Read backwards off the swell, 18 h so far.
Trains read off the spectrum at Point Loma South, CA (NDBC 46232), and storms read backwards from them; direction at Tanner Banks, CA (NDBC 46047).
Hurricane position and winds: National Hurricane Center best track, an analysis.
```

### M2 — hurricane + last arrival (last hidden)

Now:

```text
Hurricane Rachel winds 121 mph (105 kt)
14.3 s train, about 1,000 mi (1,700 km) bearing 196° SSW on Oct 1, 30 h read so far.
Strong match to NHC's track, 92%. Timing and direction beat the same track moved earlier 46 of 50 times at Tanner Banks, CA (NDBC 46047).
Trains read off the spectrum at Point Loma South, CA (NDBC 46232).
National Hurricane Center best track, an analysis.
```

Proposed:

```text
Hurricane Rachel  winds 121 mph (105 kt) when sent
14.3 s train, sent Oct 1 from about 1,000 mi (1,700 km) bearing 196° SSW.
Strong match to NHC's track. Timing and direction beat the same track moved earlier 46 of 50 times at Tanner Banks, CA (NDBC 46047) over 30 h.
Trains read off the spectrum at Point Loma South, CA (NDBC 46232).
Hurricane position and winds: National Hurricane Center best track, an analysis.
```

