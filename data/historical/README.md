# Backfilled history — CALIBRATION ONLY

**Never merge this into `data/observations/`, and never resolve a round from it.**

## Why it is separate

| | `data/observations/` | `data/historical/` |
| --- | --- | --- |
| What it is | values **as first published** | values **quality-controlled after the fact** |
| Provenance | `first_seen_utc` per row | `_manifest.csv` per station-year |
| Can resolve a round | **yes** — it is what was known at round open | **no** |
| Missing values in source | `MM` | numeric sentinels (`999.0`, `99.0`, `9999.0`) |
| If lost | **unrecoverable** — 45-day window | re-fetchable from NDBC indefinitely |
| Completeness | every reported observation | downsampled to hourly, narrowed columns |

A round is scored against the baseline frozen when it opened and the observation
published when it resolved (SPEC section 3). NDBC revises values afterwards.
Resolving from the revised record would score players against a number that did
not exist when they called — the exact failure the live archive's
`first_seen_utc` exists to prevent.

## Why it is allowed to be lossy

Because it can afford to be. The 45-day urgency does not apply here: NDBC keeps
this archive indefinitely, so anything dropped is one request away. Storing every
column of every 10-minute reading for ten stations over five years would add tens
of megabytes to the repository to answer questions nobody has asked.

Kept: `timestamp_utc`, `wtmp`, `wvht`, `atmp`, `wspd`, `wdir`, one row per hour.

## What it is for

Calibrating the scoring function across **seasons**. Every number in SPEC
section 3 came from 46 late-summer days — the stratified, post-upwelling part of
the year, and plausibly the quietest window there is. Whether the point scale and
the tail behaviour survive a spring upwelling season is what this answers:

    python -m game.backtest --source historical

## Provenance

`_manifest.csv` records, per station-year: the URL fetched, when, how many rows
the file held, and how many survived downsampling. A station-year that failed is
recorded with its reason rather than silently omitted.
