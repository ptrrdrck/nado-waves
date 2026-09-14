# The beach observation log

**This is the verification series. Everything in `CLAUDE.md`'s build order below
step 2 is unfalsifiable without it, and it is the only part of this project that
cannot be caught up later.**

Nothing measures waves at Coronado. Not the buoy — 46232 sits outside the
shadow that defines these breaks. Not CDIP MOP, which is a model. This file is
the only thing that will ever have observed the thing the project forecasts.

**The phone form is the normal way in.** Nobody carries a laptop to the
waterline. There are two builds of it, from one source file, because helpers are
not signing in to anything:

| build | file | who | where entries go |
| --- | --- | --- | --- |
| owner | `app/beachlog.html` | Pete | straight into the artifact's shared store |
| observer | `app/beachlog-observer.html` | everyone else | this phone, handed back as text |

They are the same file apart from the `<title>`, and a test enforces that — two
hand-maintained copies would drift the moment one gained a field. **The role is
not a setting.** The page starts as an observer and is promoted only when a
shared store actually resolves, which happens on Pete's build and nowhere else.
Starting closed means the roster controls are never on screen for someone who
should not have them.

The CLI below is the same schema for when you are at a desk.

    python -m collector.beachlog log -b coronado_center -o <you>
    python -m collector.beachlog sweep -o <you>      # all three, one trip
    python -m collector.beachlog show --days 30
    python -m collector.beachlog_import rows.json    # bring the phone rows in
    python -m forecast.beachverify                   # does it match the geometry?

## The round trip

The form captures; this file is the system of record. They are different
places on purpose — a file in this repository is the only copy that cannot
quietly disappear, and the artifact's store is capped at 5,000 documents,
which is about four and a half years of a three-break daily sweep.

1. The form writes to **this phone first**, then flushes to the artifact's
   store. Signal at the waterline is not something to bet a day's observation
   on, and an entry made in a dead spot is still an entry.
2. Get the rows:
   - **owner build** — read them out with the Artifact tool's `read_db` on the
     `observations` collection and save as JSON;
   - **observer build** — they tap *Send your entries*, which copies a JSON
     block to paste into a text or email. Copying does not clear it, and
     clearing is a separate deliberate act behind a confirm, because until it
     reaches the repository that phone holds the only copy.
3. `python -m collector.beachlog_import rows.json` — validating, idempotent by
   `entry_id`, append-only. Re-importing the same export is a no-op rather than
   a double count, which matters because a duplicated break inside one session
   would read as a genuine second look.

## Before the first entry

Add yourself to `observers.csv` with your standing height in centimetres. The
heights in this log are body-referenced — waist, chest, head — because a body is
a stable ruler and "feet" is a local convention that drifts. Without your height
the categories still work for every comparison the log actually makes; they just
cannot be turned into an approximate length.

## Layout

    observations.csv   one row per break per look, append-only
    observers.csv      observer -> standing height, the body-scale calibration

## observations.csv

| column | meaning |
| --- | --- |
| `session_id` | One trip. Entries sharing it were seen by one person, close in time, at one tide — which is what makes them comparable to each other. |
| `observed_utc` | When the waves were seen, **per break**. In a sweep each break is stamped by the first tap on its TYPICAL WAVE. That is the observation — wind, rideability and the rest describe it — so the moment the observer commits to a height is the moment being recorded, and it does not drift if they open a break's card early, walk, and fill in the conditions afterwards. Changing your mind about the height later does not move the stamp. An earlier version stamped all three identically and called the loss nothing; that was wrong — the breaks are a walk apart and one timestamp asserts a simultaneity that did not happen. The buoy being hourly makes that error survivable, not honest. The exception is a session logged under *Previously*, where one supplied time is the whole of what the observer actually knows. |
| `logged_utc` | When the row was written. The gap is a quality signal: an entry written six hours later is weaker evidence than one written on the sand. |
| `break_id` | Must exist in `forecast/spots.json`. An observation against an unknown break cannot be compared to anything and is refused. |
| `entry_id` | Minted where the entry is made. The idempotency key that makes importing the same export twice a no-op. |
| `observer` | Display name at the time of logging. Required — an anonymous observation cannot be weighted. |
| `observer_id` | The durable key. Names start generic and get edited once it is known who was helping; a series keyed on the name would orphan every earlier row the moment that happened. |
| `observer_height_cm` | The observer's standing height at the time of logging, carried on the row itself. Observers set their own on their own phone and it lives nowhere else, so a lookup table here would be permanently empty for everyone but Pete. Riding along also means a later re-measurement never silently rewrites what an old observation was judged against. Blank is allowed and costs only the approximate metres — every comparison this log makes is ordinal — but the form refuses to save without one. |
| `method` | `from_water`, `from_sand`, `from_window`, `from_camera`. The phone form always records `from_sand` and asks no question, because that is what it instructs — a field with one possible answer is a tap that buys nothing. The CLI can still record the others. |
| `minutes_watched` | A two-minute look from a car misses set waves and biases low. Recorded because that bias is correctable and otherwise invisible. |
| `saw_sets` | Whether a set actually came through while watching. |
| `typical` `sets` | Body scale, `flat` → `double_overhead`. `sets` may be blank; on a flat day there are none, and inventing one would substitute a value for a missing observation. |
| `typical_ft` `sets_ft` | Optional. The observer's own number, kept beside the category, never instead of it. |
| `confidence` | `high`, `medium`, `low` |
| `wind` | `glassy`, `offshore`, `cross`, `light_onshore`, `onshore`, `storm`. Cross-checks KNZY against the beach. |
| `rideable` | `yes`, `marginal`, `no`. Two feet and perfect is not two feet and closing out. |
| `forecast_seen` | Whether the observer had already seen a forecast. Flags the entry rather than rejecting it — knowing which rows are contaminated is worth more than pretending none are. |
| `note` | Free text. |

## Rules this file lives by

- **No tide column.** Tide is deterministic from `observed_utc` and NOAA
  9410170. Asking a person for it adds a field that gets guessed, and buys
  nothing the clock does not already give.
- **There is no "did not look" value.** `flat` means the ocean was flat and
  somebody checked. Not looking is a gap, and a gap stays a gap — in
  verification exactly as in the archive.
- **Nothing is coerced.** A bad entry is refused with a reason. A verification
  log that tidies up its own inputs is not a record of what was seen.
- **This series is never blended into the forecast it judges.** It lives in its
  own directory for that reason.
- **Heights are derived on read, never stored.** The category is the
  observation. The metres are a convenience computed through conventional
  anthropometry that was never measured for any particular observer.
