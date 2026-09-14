# Archived observations

**These files are tracked in git on purpose. Do not add them to `.gitignore`.**

NDBC's real-time service retains only the last 45 days. Anything not committed
here is gone permanently — it cannot be re-fetched, re-derived, or bought later.
This directory is the project's only durable copy.

## Layout

    observations/{STATION}.csv     one row per observation timestamp, oldest first
    revisions/{STATION}.csv        append-only log of values NDBC changed after publishing
    historical/{STATION}.csv       NDBC quality-controlled archive, for calibration only
    wave_forecasts/{STATION}.csv   archived GFS-Wave bulletins (SPEC section 12)
    station_status.json            per-station liveness, rebuilt every run

## station_status.json

What the app reads to decide which buoys can take a call today. Derived from the
archive on every collection run, never hand-maintained.

| field | meaning |
| --- | --- |
| `state` | `live`, `dark` (no observation within `max_age_hours`), or `never_seen` |
| `state_since_utc` | When the current state began. A buoy went dark at its *last observation*, not when we noticed. |
| `rounds_paused` | True when the buoy cannot host a round today |
| `paused_reason` | Player-facing sentence saying what happened and when |

A paused buoy stays discoverable — it keeps its league page and its history.
Paused is not the same as void: void is a round that opened and lost its
resolving observation; paused means no round opens at all. See SPEC section 4.

## observations/{STATION}.csv

| column | meaning |
| --- | --- |
| `timestamp_utc` | Observation time as published by NDBC, UTC, ISO 8601. Unique per file. |
| `first_seen_utc` | When the collector first archived this row. Never rewritten. |
| `wdir` `wspd` `gst` | Wind direction (degT), speed and gust (m/s) |
| `wvht` `dpd` `apd` `mwd` | Significant wave height (m), dominant and average period (s), mean wave direction (degT) |
| `pres` `atmp` | Sea level pressure (hPa), air temperature (°C) |
| `wtmp` | **Sea surface water temperature (°C) — the quantity v1 predicts** |
| `dewp` `vis` `ptdy` `tide` | Dew point (°C), visibility (nmi), pressure tendency (hPa), tide (ft) |

An empty cell means NDBC published `MM` (missing). It is never filled in,
interpolated, or substituted. A round whose resolving observation is empty is
voided for everyone — see SPEC section 4.

`first_seen_utc` is what makes this archive usable for baseline-relative
scoring: it records what was known at a given moment, which is what freezing a
baseline at round open depends on.

## revisions/{STATION}.csv

NDBC revises values after first publication. When that happens the collector
updates the cell in `observations/` and appends the change here, so the earlier
value is never lost. A value that was published and later blanked is kept in
`observations/` and the blanking is logged here — observed data is never
discarded.

Together with `git log -- data/observations/{STATION}.csv`, this gives a full
account of exactly what each station reported and when.

## wave_forecasts/{STATION}.csv

Archived **GFS-Wave station bulletins** — what NCEP's global wave model
predicted for this buoy, as published at the time. Input for the forecast-error
work in SPEC section 12 and `game/verify.py`.

**Not a game input, ever.** A bulletin is the public forecast, which is exactly
what a scoreable quantity must not be derivable from. Measuring against it is
the point; scoring a round with it is forbidden.

| column | meaning |
| --- | --- |
| `cycle_utc` | Model run the forecast came from (00Z unless stated) |
| `valid_utc` | Moment being forecast |
| `lead_h` | `valid_utc - cycle_utc`, in hours |
| `hs_total_m` | Total significant wave height for the whole sea |
| `n_fields` `n_omitted` | Bulletin `n` and `x`: wave trains found, and real ones the six columns could not fit |
| `part_rank` | Index of this wave train within the hour, largest first. Empty when nothing cleared 0.15 m — a flat hour is a forecast, not a gap. |
| `part_hs_m` `part_tp_s` | That train's significant height (m) and peak period (s) |
| `part_from_deg` | **Direction the train comes FROM**, degT — already flipped out of the bulletin's travel-direction convention to match NDBC `MWD`. Do not flip it again. |
| `wind_sea` | `1` when the bulletin's `*` marks local wind generation as probable |

Unlike `observations/`, this archive is **not irreplaceable**: the NOAA Open
Data bucket retains every cycle back to 2021-03, so a lost file is a re-fetch,
not a permanent loss. Rebuild with `python -m collector.gfswave_backfill`.

A missing cycle (NCEP skipped a run) is reported and left missing. It is never
substituted with a neighbouring run.

## Size

About 73 bytes per row, so roughly 6 MiB per year for ten stations at hourly
resolution. Repository size is a non-issue for years.

`wave_forecasts/` runs about 2.8 MiB per station for three years of daily 00Z
cycles at 24-hour lead steps to ten days. Widening the lead grid or adding
cycle hours multiplies that directly, so both are flags on
`collector.gfswave_backfill` rather than defaults.
