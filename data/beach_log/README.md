# The beach observation log

**This is the verification series. Everything in `CLAUDE.md`'s build order below
step 2 is unfalsifiable without it, and it is the only part of this project that
cannot be caught up later.**

Nothing measures waves at Coronado. Not the buoy — 46232 sits outside the
shadow that defines these breaks. Not CDIP MOP, which is a model. This file is
the only thing that will ever have observed the thing the project forecasts.

**The phone form is the normal way in.** `app/beachlog.html`, published as an
Artifact — nobody carries a laptop to the waterline. The CLI below is the same
schema for when you are at a desk.

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
2. Read the rows out with the Artifact tool's `read_db` on the `observations`
   collection, save them as JSON.
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
| `observed_utc` | When the waves were seen. |
| `logged_utc` | When the row was written. The gap is a quality signal: an entry written six hours later is weaker evidence than one written on the sand. |
| `break_id` | Must exist in `forecast/spots.json`. An observation against an unknown break cannot be compared to anything and is refused. |
| `entry_id` | Minted where the entry is made. The idempotency key that makes importing the same export twice a no-op. |
| `observer` | Display name at the time of logging. Required — an anonymous observation cannot be weighted. |
| `observer_id` | The durable key. Names start generic and get edited once it is known who was helping; a series keyed on the name would orphan every earlier row the moment that happened. |
| `method` | `from_water`, `from_sand`, `from_window`, `from_camera` |
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
