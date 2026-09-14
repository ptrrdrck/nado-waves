# The observation log — why it is shaped this way

BRIEFING §9 asks the question this design answers: *what does a verification log
actually look like, such that a person will fill it in daily for a year?*

The honest answer is that nothing makes a person do anything daily for a year.
So the log is built to survive irregularity rather than to demand consistency.
Every entry is independently useful. A fortnight of silence costs nothing
structurally. There are no streaks to break, and no scoreboard that punishes a
gap — which matters, because the moment a log makes you feel behind, it is dead.

## The one decision that changes everything

**The log's first job is the differential, not the absolute height.**

People are unreliable at *"that is 3.2 feet"* and reliable at *"the south end is
bigger than the north end today."* Absolute surf height is contaminated by local
convention, by mood, by whether the scale is Hawaiian, by who you are standing
next to. A within-session comparison — one observer, one tide, one light, half
an hour apart — cancels nearly all of it.

And the differential is what the project is actually claiming. The geometry says
Coronado's three breaks hold 42.8°, 49.1° and 56.3° of open window. That claim
is testable by comparison alone, with no height calibration whatsoever.

So the unit of the log is the **session**, and the highest-value entry in the
whole design is a sweep of all three breaks in one trip.

## The control, which is the part that makes it a test

Agreement is worthless without the days that could have disagreed.

The geometry's prediction is **conditional on swell direction**, and only some
days discriminate:

| swell from | north (cuts 242.2°) | centre (250.3°) | south (259.9°) | geometry predicts |
|---|---|---|---|---|
| 210° | open | open | open | **nothing** — control |
| 245° | blocked | open | open | south bigger |
| 255° | blocked | blocked | open | south bigger |
| 200° | open | blocked | blocked | **north bigger** |
| 265° | blocked | blocked | blocked | **nothing** — control |

Two things fall out of that table, and the second is the good one.

**Control days.** On a 210° swell the geometry predicts no ordering at all. If
the south end still reads bigger on those days, something other than the
aperture is producing it — a sandbar, where the observer stands, the order they
walk the beach in, the light changing while they walk. Those days are kept and
counted, not discarded.

**The two edges predict opposite orderings.** This is the sharp control, and it
is free. The Point Loma shadow cuts the *north* break off first, so a west swell
says south is bigger. The Coronado Islands shadow cuts the *south* break off
first, so a 200° swell says **north** is bigger.

A fixed bias produces a *consistent* ordering, so it agrees on one edge and
contradicts the other. Only a real aperture effect **flips** with the swell.
Agreement on both edges is worth far more than twice the agreement on either,
and agreement on one edge alone is not evidence at all.

`forecast/beachverify.py` reports agreement separately per edge for exactly this
reason, and says so explicitly while only one edge has been seen. The synthetic
confound is in the test suite:
`test_a_fixed_bias_agrees_on_one_edge_and_disagrees_on_the_other`.

This is the same shape as the expanding-window control in BRIEFING §4, which
turned a promising 2–9% improvement into a sub-inch non-result. That control was
written after the fact. This one exists before the first observation.

## Blind logging is structural, not a discipline

An observer who checks the forecast before logging is no longer an independent
witness, and a series contaminated that way cannot judge the forecast that
shaped it. That is a property of the system, not a matter of willpower, so
`collector/beachlog.py` has no forecast display and never will.

`forecast_seen` records the honest answer when someone saw one anyway on the
drive over. The entry is flagged, not rejected: knowing which rows are
contaminated is worth more than pretending none are, and a sensitivity check
that drops them is cheap once there are enough to spare.

Using the buoy's measured direction to *classify* days afterwards is not
contamination. The observation was already logged blind; sorting days by a
measurement after the fact is what every operational verification does.

## The small decisions, and what each one refuses

| decision | the obvious thing, and why not |
|---|---|
| Body scale, not feet | A body is a stable ruler. Feet drift with convention and company. |
| Store the category, derive metres on read | The category is what was observed. The fractions are conventional anthropometry, never measured for this observer — freezing them into the file would store a guess as data. |
| No tide column | Deterministic from the timestamp and NOAA 9410170. A field that gets guessed is worse than a field that is computed. |
| Keep a coarse wind field | KNZY is minutes away, but one keystroke cross-checks it against the beach. |
| `minutes_watched`, `saw_sets` | A two-minute look misses sets and biases low. Correctable if recorded, invisible if not. |
| `observed_utc` and `logged_utc` apart | An entry written six hours later is weaker evidence, and only the pair can say which this was. |
| No "did not look" value | `flat` is an observation. Absence is a gap, and gaps stay gaps. |
| Refuse, never coerce | A log that tidies up its own inputs is not a record of what was seen. |

## What this log cannot do yet, stated plainly

It cannot verify a forecast height. Face height and significant wave height are
different quantities and the transfer between them is a fitted function nobody
has fitted. Until that exists, this series verifies **ordinal and differential**
claims — which is not a limitation worth apologising for, because the ordinal
claim is the one the project is built on.

`forecast/beachverify.py` reports counts and refuses to produce a rate below 20
discriminating sessions. Per CLAUDE.md: never state an accuracy figure for a
beach without naming the verification series it was measured against, and a
series of eleven observations is not one.

## Where it goes next

- Fill in `observers.csv` — the body scale needs your standing height.
- Wire tide (NOAA 9410170) and wind (KNZY) so each row can be joined after the
  fact rather than asked for.
- ~~A phone-shaped entry form.~~ **Built** — `app/beachlog.html`, published as
  an Artifact. Body scale as a vertical ruler because that is how an observer
  reads a wave; everything else thumb-sized chips; sweep mode walks the three
  breaks in one session. It writes to the phone first and syncs afterwards,
  because an entry made where there is no signal is still an entry. It shows no
  forecast and contains no code that could.
- The face-height transfer function, once the series can support fitting one.
