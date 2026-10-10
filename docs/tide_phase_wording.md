# Tide phase wording: DRAFT for the Tide card

**This is a draft, not on the page yet.** Nothing in `app/forecast.html`
reads it. It is for the owner to edit on this branch, the same way
`docs/origin_wording.md` was settled before Origin's code changed. The cases
at the end were rendered by a scratch prototype from the archive as it stood
at each date. They are not typed. Dates and days are Pacific, as on the
card.

## Where it sits

The fold goes on the Tide card, under the turn line ("rising to … at …") and
above Charts. It has its own caret, closed until opened, as Origin's does.
**Its title line is the label**: the phase, followed by the `predicted` tag.

    Spring tides  predicted  ▾

Open, the fold shows the summary: a title, then three entries and their
evidence bullets.

## The formula

Each entry is a fixed run of slots. A slot with no value is dropped together
with its joining words. Nothing is reworded per case.

| Line | Slot | Text |
|---|---|---|
| fold title | phase | `Spring tides` · `Neap tides` · `Building toward springs` · `Easing toward neaps` |
| | tag | `predicted` |
| title | | `Where Coronado is now ({d Mon})` |
| **Today** | phase | `Today: {phase, lower case}.` |
| | moon | ` {New moon \| Full moon \| First quarter moon \| Last quarter moon} is {d Mon} and` (only when the phase is springs or neaps) |
| | declination | ` the Moon is {near the equator \| far north \| far south \| heading north \| heading south \| heading for the equator}` (capitalised `The Moon …` when the moon slot is empty) |
| | so | `, so {the day's two highs are nearly even \| one high of the day is much bigger than the other \| the day's two tides are growing unequal \| the day's two tides are evening out}` |
| | evidence | `: highs of {h} and {h} today` · `: a single high today, {h}` |
| | end | `.` |
| **Next** | when | `Around {d Mon}: ` (the next spring or neap tide more than 2 days away) |
| | what | `{spring \| neap} tide` |
| | coincide | ` and {e} coincide` · `, {e1} and {e2} all coincide`, from: `perigee`, `apogee`, `maximum declination`, `the Moon over the equator` |
| | so | `, so {consequence}.` (table below) |
| | evidence | ` The CO-OPS turns already show it:` and then the bullets, only when there is at least one bullet |
| **After** | when | `{Early \| Mid \| Late} {Month}: ` (the one after Next) |
| | what | `springs` · `neaps` |
| | moon | ` at {new moon \| full moon \| first quarter \| last quarter} ({d Mon})` |
| | distance | `, near {perigee \| apogee} ({d Mon})` |
| | declination | ` and with declination {growing \| falling}` |
| | so | `, so {larger \| smaller \| similar} extremes than this week.` |

Consequences for **Next**, by the kind of tide and where the Moon is:

| | Moon far north or south | Moon near the equator | Moon between the two |
|---|---|---|---|
| neap | the twice-daily pattern nearly vanishes | every tide of the day is small | the swings are small |
| spring | the biggest swings, one high of the day much bigger than the other | big swings, the day's two highs nearly even | big swings |

Evidence bullets come from the card's own turns only: CO-OPS's high and low
water, carried to the open coast with the measured departure, exactly as the
turn line shows them. Within 2 days of the Next date:

| Kind | Bullet | Shown when |
|---|---|---|
| neap | `{d Mon} has a high and low only {h} apart.` | two consecutive turns under 1 ft (0.30 m) apart |
| neap | `{d Mon} has a single high and low.` / `{d}–{d Mon} have a single high and low each day.` | a day with exactly two turns, **counted only on a complete day inside the turns' horizon** (the last day the turns reach is partial, and two turns there are not a fact about that day) |
| spring | `{d Mon} has a {h} swing from {high to low \| low to high}, the largest the turns hold.` | the biggest consecutive swing |

Every height is written as `height()` writes it: feet first, metres in
parentheses.

## What decides each slot

- **Springs and neaps** come from the station's own constituents (M2, S2,
  N2, K2 and the smaller twice-daily terms), not from the Moon's phase. The
  constituents carry San Diego's own lag: springs run about 3 h before new or
  full moon. The phase reads `Spring tides` or `Neap tides` within 48 h of a
  peak or trough of that envelope, and otherwise `Building toward springs` or
  `Easing toward neaps`.
- **Where the Moon is** is read 14 h earlier than the moment being described.
  14 h is the station's diurnal age, from the K1–O1 phases: the tide answers
  the Moon's declination about 14 h late. The states are:
  - near the equator: |δ| ≤ 5°
  - far north or far south: |δ| ≥ 20°
  - otherwise heading north, heading south, or heading for the equator

  In 2026 the Moon reaches 28°, close to the major lunar standstill.
- **Moon phases, perigee, apogee and declination** come from a computed lunar
  ephemeris. A moon phase is named when it falls within 72 h of the spring or
  neap it explains, and perigee or apogee likewise. Mean orbital elements are
  not good enough for this: they put this week's new moon on 11 Oct (it is
  10 Oct) and the next perigee on 30 Oct (it is 28 Oct).
- **Larger, smaller or similar extremes** compares the combined envelope
  (twice-daily plus once-daily) at the After date with the envelope now.
  "Similar" means within ±5%.

## Cases, each as of 12:00 PM Pacific on its date, against that date's archive

As of 24 Sep:

> **Building toward springs** `predicted`
>
> Where Coronado is now (24 Sep)
>
> * Today: building toward springs. The Moon is heading for the equator, so the day's two tides are evening out: highs of 5.6 ft (1.72 m) and 6.3 ft (1.91 m) today.
> * Around 26 Sep: spring tide and the Moon over the equator coincide, so big swings, the day's two highs nearly even. The CO-OPS turns already show it:
>    * 28 Sep has a 6.0 ft (1.84 m) swing from high to low, the largest the turns hold.
> * Early October: neaps at last quarter (3 Oct), near perigee (1 Oct) and with declination falling, so smaller extremes than this week.

As of 3 Oct:

> **Neap tides** `predicted`
>
> Where Coronado is now (3 Oct)
>
> * Today: neap tides. Last quarter moon is 3 Oct and the Moon is far north, so one high of the day is much bigger than the other: highs of 4.5 ft (1.38 m) and 6.3 ft (1.91 m) today.
> * Around 9 Oct: spring tide and the Moon over the equator coincide, so big swings, the day's two highs nearly even. The CO-OPS turns already show it:
>    * 10 Oct has a 6.1 ft (1.85 m) swing from high to low, the largest the turns hold.
> * Mid October: neaps at first quarter (18 Oct), near apogee (16 Oct) and with declination falling, so smaller extremes than this week.

As of 7 Oct:

> **Spring tides** `predicted`
>
> Where Coronado is now (7 Oct)
>
> * Today: spring tides. New moon is 10 Oct and the Moon is heading for the equator, so the day's two tides are evening out: highs of 6.4 ft (1.95 m) and 6.8 ft (2.07 m) today.
> * Around 17 Oct: neap tide, apogee and maximum declination all coincide, so the twice-daily pattern nearly vanishes. The CO-OPS turns already show it:
>    * 15 Oct has a high and low only 0.5 ft (0.15 m) apart.
> * Late October: springs at full moon (25 Oct), near perigee (28 Oct) and with declination growing, so larger extremes than this week.

As of 10 Oct (today):

> **Spring tides** `predicted`
>
> Where Coronado is now (10 Oct)
>
> * Today: spring tides. New moon is 10 Oct and the Moon is heading south, so the day's two tides are growing unequal: highs of 7.5 ft (2.28 m) and 6.3 ft (1.91 m) today.
> * Around 17 Oct: neap tide, apogee and maximum declination all coincide, so the twice-daily pattern nearly vanishes. The CO-OPS turns already show it:
>    * 15 Oct has a high and low only 0.5 ft (0.15 m) apart.
>    * 16–17 Oct have a single high and low each day.
>    * 18 Oct has a high and low only 0.1 ft (0.02 m) apart.
> * Late October: springs at full moon (25 Oct), near perigee (28 Oct) and with declination growing, so larger extremes than this week.

On 7 Oct the turns reached only to 15 Oct, so the Next entry has one bullet.
The bullets grow as the turns file fills.

### Where the 10 Oct case differs from the chat summary it was drafted from

- **New moon is 10 Oct, not "about 11 Oct"**, and **perigee is 28 Oct, not
  ~30 Oct.** The summary used mean orbital elements. 30 Oct is about when
  the tide feels perigee most (the station's parallax age is ~37 h), but the
  card names the event, not its echo.
- **"The two highs are fairly even" was wrong for today.** At the open coast
  they are 7.5 and 6.3 ft, 1.2 ft apart and drawing further apart (the highs
  were most even on 8 Oct, at 7.0 and 6.9). The Moon crossed the equator on
  8 Oct and is now heading south. The Today slot now says which way the
  inequality is moving, and its evidence is the card's own turns.
- **Heights are the open coast with the departure**, as the turn line shows
  them, not the bay gauge's metres.
- **Full moon is 25 Oct in Pacific time** (04:11 UTC on the 26th).

## Provenance, one line per claim

- `Spring or neap: NOAA's harmonic constants for San Diego (9410170).`
- `Moon's phase, distance and declination: computed.`
- `Highs and lows: CO-OPS high and low water, carried to {site} from {gauge}.`
  This is the line the turn already uses.

On LIVE this is a second modelled item beside the turn, and it is tagged the
same way. Its row in the standing-on block on `docs.html` would name it as
an astronomical prediction.

## What it does not say

Nothing about waves. On the 2016 profile the whole tide range changes the
breaking height by under 2% and moves the break point 34–53 m (BRIEFING
§32). The fold must not imply that springs mean bigger surf.

## For the owner to decide

1. **Which tabs.** Both tabs, with "today" being the reader's day on LIVE
   and the picked hour's day on Forecast? Or LIVE only?
2. **Where the constants come from.** Fetch them from CO-OPS on Actions
   (`mdapi …/harcon.json`), as the turns are, rather than typing the table
   in. Pasted into a prototype, the table reproduces the archived hourly
   predictions to 1.15 cm RMS once phases are moved from local time to
   Greenwich (add speed × 8 h).
3. **The ephemeris.** Either a pure-Python lunar series (Meeus ch. 47,
   about 60 terms, no dependency) or a library. The prototype used `ephem`.
4. **The thresholds** above: 48 h, 5°/20°, 72 h, 1 ft, ±5%. They are
   reasonable first guesses, not measurements.
5. **The After entry's "when"** is `Late October` and the like, as in your
   text. An `Around {d Mon}` form would match Next.
