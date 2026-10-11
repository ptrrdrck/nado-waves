# Tide phase wording: the formula, and the cases

The Tide card's phase fold, on both tabs since 2026-10-11 (owner's request).
The formula is set out here. The cases at the end are not typed:
`python -m forecast.tidephasewording` runs the page's own phase functions in
Node, on summaries built by `forecast.tidephase`. Four of those summaries come
from the archive as it stood on their dates; the rest are made up to reach
every other branch. `tests/test_tidephasewording.py` fails if this file and
the page disagree. Edit the wording above the generated section. Dates are
Coronado's own days, in Pacific time.

## Where it sits

The fold sits on the Tide card, under the provenance and right above
"Charts", under a rule of its own, like Origin's. It has its own caret,
closed until opened, with one open state for both tabs that is kept across
a refresh.

**Its line is the phase:** `Spring tides`, `Neap tides`, `Building toward
springs` or `Easing toward neaps`. On LIVE the line carries the `predicted`
tag, as the turn line does. On Forecast it carries no tag, because the whole
card is a model there.

The fold body has a title and up to three paragraphs, **never bullets**
(owner's request, 2026-10-11), then one provenance line per claim.

- **On LIVE** the fold is for the reader's day at Coronado.
- **On Forecast** it is for the picked hour's day. Each of the run's own days
  has one. A past hour shows no fold, because the build that showed that hour
  had none.

## The formula

Each paragraph is a fixed run of slots. A slot with no value is dropped
together with its joining words. **Every claim read off NOAA's constants says
so where it is made** (owner's request, 2026-10-11): the phase, the 14 h lag,
the next spring or neap, the one after, and the size comparison.

| Para | Slot | Text |
|---|---|---|
| title | | `Where Coronado is now ({d Mon})`. On a day other than the reader's: `Where Coronado is on {d Mon}` |
| **1** | phase | `Today:` (or `{d Mon}:`) ` {phase, lower case} by NOAA's harmonic constants for San Diego ({analysis years}).` |
| | moon | ` {New moon \| Full moon \| First quarter moon \| Last quarter moon} {is \| was} {d Mon} and the Moon` (on spring or neap days only). Without it: ` The Moon` |
| | lag | `, as the tide feels it {14} h late by the same constants,` |
| | where | ` is {near the equator \| far north \| far south \| heading north \| heading south \| heading for the equator}` |
| | so | `, so {the day's two tides are alike \| one tide of the day is much bigger than the other \| the day's two tides are growing unequal \| the day's two tides are evening out}` |
| | pair | `: {highs \| lows} of {h} and {h} today` (or `that day`): whichever pair differs more |
| | end | `.` |
| **2** | when | `Around {d Mon}: ` for the next spring or neap more than 72 h away |
| | what | `{spring \| neap} tide by the same constants` |
| | coincide | `, coinciding with {e}` / `{e1} and {e2}`, from `perigee`, `apogee`, `maximum declination`, `the Moon over the equator` |
| | so | `, so {consequence}.` (table below) |
| | evidence | ` The CO-OPS turns already show it: {item}; {item}.` when there is any |
| **3** | when | `{Early \| Mid \| Late} {Month}: ` for the one after (owner's "Late October") |
| | what | `{springs \| neaps} by the same constants, ` |
| | moon | `at {new moon \| full moon \| first quarter \| last quarter} ({d Mon})` |
| | distance | `near {perigee \| apogee} ({d Mon})` |
| | declination | `with declination {growing \| falling}` |
| | so | `, so {larger \| smaller} extremes than this week.` / `, so extremes similar to this week.` (`that week` on another day) |

Paragraph 3's three middle slots are joined `a, b and c`.

Consequences in paragraph 2, by kind and by where the Moon is:

| | far north or south | near the equator | between |
|---|---|---|---|
| neap | the twice-daily pattern nearly vanishes | small swings, the day's two tides alike | small swings |
| spring | the biggest swings, one tide of the day much bigger than the other | big swings, the day's two tides alike | big swings |

Evidence items come from the card's own turns. These are CO-OPS's high and
low water, carried to the open coast with the measured departure, and they
are looked for within 2 days of paragraph 2's date:

| Kind | Item | When |
|---|---|---|
| neap | `{d Mon} has a high and low only {h} apart` | two consecutive turns under 0.20 m (0.7 ft) apart |
| neap | `{d Mon} has a single high and low` / `{d}–{d Mon} have a single high and low each day` | exactly two turns on a day the turns cover whole (never the first or last day they reach) |
| spring | `{d Mon} has a {h} swing from {high to low \| low to high}, the largest the turns hold` | the biggest consecutive swing |

Provenance, one line per claim:

- `Spring and neap, the 14 h lag and the size against this week: NOAA's
  harmonic constants for San Diego, CA (9410170), 2017–2021 analysis.`
- `Moon's phase, distance and declination: computed.`
- `Highs and lows: CO-OPS high and low water, {site}, carried from {gauge}.`

## What decides each slot

Every threshold was measured over 19 years of the station's tide, from 2017
to 2035 (a whole nodal cycle), reconstructed from the constants. The
measurement is `python -m forecast.tidephasereport`, recorded in BRIEFING
§41. The rule is the owner's request to measure the thresholds, applied
throughout: **a slot is said only where it is right on at least 85% of the
occasions it fires.** The test re-runs every sweep.

| Slot | Threshold | Measured |
|---|---|---|
| phase | within 72 h of the twice-daily envelope's peak or trough | agrees with the top and bottom third of each 15 days on 69.5% of days. This is the best window: no window reaches 85% on both labels, so this one always says something |
| moon | the phase within 66 h | the farthest apart in 19 years was 64 h, so the slot is always filled |
| where: near the equator | felt \|δ\| ≤ 4° | 88.1% of those days have the day's two tides in the bottom quartile of their difference (5°: 84.8%) |
| where: far | felt \|δ\| ≥ 26° | 86.1% in the top quartile (24°: 80.9%). This happens only near a major lunar standstill, as now |
| where: heading | the sign of \|δ\|'s change | tomorrow's difference moves that way on 93.0% of days |
| lag | `diurnal_age_h`, from K1–O1 | 14.4 h |
| distance | within 72 h | springs near perigee are bigger than the median spring on 85.7% of occasions, and the other pairings 94–100% (96 h: 84.2%) |
| small swing | under 0.20 m | 89.9% fall within 2 days of a neap (0.25 m: 84.7%) |
| larger or smaller | past ±10% of the combined envelope | right on 86.1% (with no margin, 80.6%) |

Two findings changed the words:

- **"The two highs" became "the two tides".** The Moon's declination shows
  in the day's lows (r = 0.82) more than in its highs (r = 0.66). The pair
  shown is whichever differs more.
- **A spring with the Moon over the equator is the smallest spring**, a
  median of 1.94 m against 2.26–2.46 m. So it reads "big swings, the day's
  two tides alike", never the biggest. A neap there is no smaller than other
  neaps, so it reads "small swings", never "every tide small".

## What it does not say

Nothing about waves. On the 2016 profile the whole tide range moves the
break point 34–53 m and the breaking height under 2% (BRIEFING §32).

## Cases

<!-- Generated by python -m forecast.tidephasewording. Edit above this line. -->

### As of 24 Sep, noon: building toward springs

From the archive as it stood then.

> Today: spring tides by NOAA's harmonic constants for San Diego (2017–2021). Full moon is 26 Sep and the Moon, as the tide feels it 14 h late by the same constants, is heading for the equator, so the day's two tides are evening out: lows of 0.9 ft (0.26 m) and 2.0 ft (0.60 m) today.
>
> Around 2 Oct: neap tide by the same constants, coinciding with perigee and maximum declination, so the twice-daily pattern nearly vanishes. The CO-OPS turns already show it: 2 Oct has a high and low only 0.1 ft (0.04 m) apart.
>
> Early October: springs by the same constants, at new moon (10 Oct) and with declination growing, so extremes similar to this week.

### As of 3 Oct, noon: neap tides, the Moon far north

From the archive as it stood then.

> Today: neap tides by NOAA's harmonic constants for San Diego (2017–2021). Last quarter moon is 3 Oct and the Moon, as the tide feels it 14 h late by the same constants, is far north, so one tide of the day is much bigger than the other: lows of 4.5 ft (1.36 m) and 1.4 ft (0.42 m) today.
>
> Around 9 Oct: spring tide by the same constants, coinciding with the Moon over the equator, so big swings, the day's two tides alike. The CO-OPS turns already show it: 10 Oct has a 6.1 ft (1.85 m) swing from high to low, the largest the turns hold.
>
> Mid October: neaps by the same constants, at first quarter (18 Oct), near apogee (16 Oct) and with declination falling, so smaller extremes than this week.

### As of 7 Oct, noon: spring tides, the turns reaching only to 15 Oct

From the archive as it stood then.

> Today: spring tides by NOAA's harmonic constants for San Diego (2017–2021). New moon is 10 Oct and the Moon, as the tide feels it 14 h late by the same constants, is heading for the equator, so the day's two tides are evening out: lows of 1.1 ft (0.32 m) and 2.3 ft (0.71 m) today.
>
> Around 17 Oct: neap tide by the same constants, coinciding with apogee and maximum declination, so the twice-daily pattern nearly vanishes. The CO-OPS turns already show it: 15 Oct has a high and low only 0.5 ft (0.15 m) apart.
>
> Late October: springs by the same constants, at full moon (25 Oct), near perigee (28 Oct) and with declination growing, so larger extremes than this week.

### As of 10 Oct, noon: spring tides, the neap a week out

From the archive as it stood then.

> Today: spring tides by NOAA's harmonic constants for San Diego (2017–2021). New moon is 10 Oct and the Moon, as the tide feels it 14 h late by the same constants, is heading south, so the day's two tides are growing unequal: highs of 7.5 ft (2.28 m) and 6.3 ft (1.91 m) today.
>
> Around 17 Oct: neap tide by the same constants, coinciding with apogee and maximum declination, so the twice-daily pattern nearly vanishes. The CO-OPS turns already show it: 15 Oct has a high and low only 0.5 ft (0.15 m) apart; 16–17 Oct have a single high and low each day; 18 Oct has a high and low only 0.1 ft (0.02 m) apart.
>
> Late October: springs by the same constants, at full moon (25 Oct), near perigee (28 Oct) and with declination growing, so larger extremes than this week.

### easing: easing toward neaps, the Moon heading for the equator, a neap at the equator, an After with no moon or distance slot and similar extremes

Made up, to reach this branch.

> Today: easing toward neaps by NOAA's harmonic constants for San Diego (2017–2021). The Moon, as the tide feels it 14 h late by the same constants, is heading for the equator, so the day's two tides are evening out.
>
> Around 23 Nov: neap tide by the same constants, coinciding with the Moon over the equator, so small swings, the day's two tides alike.
>
> Late November: springs by the same constants, with declination falling, so extremes similar to this week.

### equator-today: spring tides with the Moon near the equator, lows the more unequal pair, a spring next with the largest swing as evidence

Made up, to reach this branch.

> Today: spring tides by NOAA's harmonic constants for San Diego (2017–2021). Full moon is 24 Nov and the Moon, as the tide feels it 14 h late by the same constants, is near the equator, so the day's two tides are alike: lows of 0.7 ft (0.21 m) and 1.1 ft (0.35 m) today.
>
> Around 8 Dec: spring tide by the same constants, coinciding with perigee and maximum declination, so the biggest swings, one tide of the day much bigger than the other. The CO-OPS turns already show it: 8 Dec has a 7.9 ft (2.41 m) swing from high to low, the largest the turns hold.
>
> Mid December: neaps by the same constants, at first quarter (16 Dec), near apogee (13 Dec) and with declination growing, so smaller extremes than this week.

### far-today: neap tides with the Moon far south and a single day of one high and one low next, a spring between the thresholds

Made up, to reach this branch.

> Today: neap tides by NOAA's harmonic constants for San Diego (2017–2021). Last quarter moon was 19 Nov and the Moon, as the tide feels it 14 h late by the same constants, is far south, so one tide of the day is much bigger than the other: highs of 5.0 ft (1.52 m) and 6.4 ft (1.95 m) today.
>
> Around 27 Nov: spring tide by the same constants, so big swings.
>
> Early December: neaps by the same constants, at last quarter (2 Dec) and with declination falling, so smaller extremes than this week.

### single-day: a neap next whose turns show one day of a single high and low

Made up, to reach this branch.

> Today: easing toward neaps by NOAA's harmonic constants for San Diego (2017–2021). The Moon, as the tide feels it 14 h late by the same constants, is heading for the equator, so the day's two tides are evening out.
>
> Around 23 Nov: neap tide by the same constants, coinciding with maximum declination, so the twice-daily pattern nearly vanishes. The CO-OPS turns already show it: 23 Nov has a single high and low; 30 Nov–1 Dec have a single high and low each day.
>
> Late November: springs by the same constants, with declination falling, so extremes similar to this week.
