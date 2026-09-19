# BRIEFING — what is already known, and what is already ruled out

Carried over from *beat-the-buoy*, a daily prediction game on SoCal buoy data
that failed its own go/no-go test. The game is dead; the data, the pipeline and
the findings are not, and they are why this project starts several months ahead
of where it looks.

Read this before proposing anything. **Four plausible ideas in here were killed
by their own tests, and three confident conclusions turned out to be wrong.**
Both lists are more useful than the successes.

---

## 1. What data exists, and what it costs to lose

| archive | what | why it matters |
|---|---|---|
| `data/historical/` | 3 years hourly, 15 stations, 2023-01-01 → 2025-12-31 | NDBC's real-time feed retains **45 days**. This is quality-controlled history that took a day to assemble and cannot be reconstructed from the live feed. |
| `data/wave_forecasts/` | 1,095 archived GFS-Wave 00Z cycles per station, 3 SoCal stations, with **swell partitions** | Each partition has its own height, period and direction. A directional window is the whole problem here, so a partitioned forecast is the right input and a total-Hs one is nearly useless. |
| `data/observations/` | rolling 45-day live archive, `first_seen_utc` on every row | Records what was *known at the time*, as distinct from what was later corrected. |
| `data/revisions/` | append-only log of values NDBC changed after publishing | NDBC revises. A published value is never overwritten by a later blank. |

Station set: SoCal nearshore (46222 San Pedro, 46221 Santa Monica, 46253,
46224 Oceanside, 46225 Torrey Pines, 46258 Mission Bay, **46232 Point Loma
South** — the Coronado buoy), offshore reference (46219 San Nicolas Island,
46086 San Clemente Basin, **46047 Tanner Banks** — the least shadowed), and
North Pacific sentinels (46001, 46005, 46006, 46059, 51101, 51002). **46235 was
added 2026-09-14 and is unplaced** — no coordinates, so no claim; see §3a and
§9. Every station is archived; which of them *constrain Coronado* is a separate
and much shorter list (§3a).

### Data traps that have already bitten

- **Historical files use numeric missing sentinels** (`999.0`, `99.0`,
  `9999.0`), not `MM`. Backfilling without `collector.ndbc.is_missing` stores
  999.0 as a wave height. The check is deliberately per-column: 999.0 hPa is a
  real pressure.
- **Moored buoys report waves only at :30/:40/:50.** An hourly downsample that
  keeps the *first* record per hour destroys the wave data — station 46001 came
  out with 7 wave observations out of 22,467 before this was caught. The fix is
  to **merge** values within the hour, not pick one.
- **CDIP buoys report at :26, NDBC moored buoys at :40/:50.** Any cross-station
  join on exact timestamps silently drops every cross-type pair and looks like
  missing data. Bucket to the clock hour.
- **Column mapping must be header-driven, not positional.** NDBC has changed
  column order.

---

## 2. The geometry — the core insight this project is built on

From `python -m forecast.geometry`. Computed from coordinates alone; no waves,
no model, no fitting.

| beach | faces | Point Loma blocks | open swell window | shadow edge from normal |
|---|---|---|---|---|
| Breakers (NASNI) | 223° | 222–313° (4.0 km) | **196–222°, just 26°** | 1° |
| Coronado Central | 251° | 249–341° (5.5 km) | **201–249°, 48°** | 1° |
| Gator (NAB) | 240° | 270–330° (7.2 km) | **206–270°, 65°** | 30° |

Distance from Point Loma orders the shadows. **Gator holds west swell to 270°
where Coronado cuts off at 249° and Breakers at 222°** — on a W/WNW swell Gator
works and Breakers is dead.

**Why published forecasts are unreliable at exactly these beaches:** at Coronado
and Breakers the shadow edge sits about **one degree** from the shore normal, so
dH/dθ there is enormous. A few degrees of incident-direction error moves the
beach across the boundary between "in the window" and "behind the peninsula".
A few miles north the same error costs a few percent.

**And the buoy makes it easy to get wrong.** From 46232 — the nearest buoy and
the natural anchor for any San Diego forecast — Point Loma bears **35–46°,
behind it to the north-east**. The buoy sits entirely outside the shadow that
defines the beaches. In the archive, 3,257 hours of W–WNW and 3,771 hours of NW
swell fall in the blocked sector, against 1,247 hours of S–SW in the open one:
**the dominant swell regime in San Diego is, for Coronado, geometrically
blocked.** Most days the forecast is a transform artifact, not a propagated wave.

Each beach also has a second open arc to the south-east (Coronado 161–190°). It
is geometrically real and practically near-useless — Southern Hemisphere swell
arrives from roughly 180–220° — so the "total open arc" figure overstates. Read
the swell-side window.

**Deliberately omitted rather than guessed:** Zuniga Jetty and the
harbour-entrance shoal (both bear on Breakers), and refraction and shoaling over
the shelf. The model says what is *blocked*, not what happens to what gets
through.

### 2a. Amendment, 2026-09-14 — two claims in §2 were wrong

The table above and the paragraph that used to close this section have been
superseded by measurement. Both errors pointed effort at the wrong input, so
they are recorded rather than quietly edited.

**Wrong: "the shoreline chord matters most."** `spots.json` asserted that five
degrees of chord error moved the open window five degrees at the shadow edge.
It moves it by **zero**. Both edges of the swell-side window are
blocker-derived — Point Loma west, the Coronado Islands east — so the seaward
half-plane clip never binds there and the normal is irrelevant to which swell
arrives. Rotating a chord ±10° at all three beaches changes nothing; moving a
break 500 m costs Coronado ~4.4°. **Position sets the window; facing does not.**
The chord still sets the normal, which is what this section's own "shadow edge
one degree from the normal" figure is computed from, and what wind fetch and
refraction will need — it is simply not the aperture. Pinned by
`test_the_shoreline_chord_does_not_move_the_swell_window` and its control.

**Wrong: "Coronado" is one beach.** The west edge of the window *is* the bearing
to the Point Loma tip, and that bearing sweeps as you walk the sand — pure
parallax, a 2.5 km baseline at 6 km range. Digitised, Coronado's three breaks
run:

| break | open window | cuts off at |
|---|---|---|
| north | **42.8°** | 242.2° |
| center (Hotel del) | **49.1°** | 250.3° |
| south | **56.3°** | 259.9° |

A **13.5° spread inside one named beach**, against 38.5° for the entire
Breakers-to-Gator range. Coronado's north break is geometrically closer to
Breakers than to Coronado's own south break. §2's single 48° row for "Coronado
Central" averaged across this.

**Also measured:** the old `coronado_central` carried a stored `position` 698 m
off the perpendicular from its own shoreline chord — two independent guesses at
one place, disagreeing, with the position silently winning every blocked sector.
Digitised spots now derive position from the chord midpoint and a test enforces
it.

**Still estimated:** Breakers and Gator, scoped out by decision, not because
their coordinates are good. The Point Loma tip is now digitised and moved only
136 m, changing every west edge by 0.2–0.5° — the old guess was good, but it is
one point carrying every west edge in the file, at ~1° per 100 m.

---

## 3. Measured: how the islands shadow the whole array

Median ratio of each buoy's Hs to Tanner Banks (46047, outside the islands),
swell hours only (DPD ≥ 12 s, Hs ≥ 0.5 m), 2023–2025.

| buoy | S | SW | W | WNW | NW | swing |
|---|---|---|---|---|---|---|
| 46219 San Nicolas I. | 1.06 | 1.05 | 1.02 | 0.98 | 0.97 | 1.08× |
| 46086 San Clemente Bsn | 0.84 | 0.82 | 0.79 | 0.75 | 0.69 | 1.22× |
| 46221 Santa Monica | 0.65 | 0.63 | 0.58 | 0.49 | 0.41 | 1.58× |
| 46222 San Pedro | 0.54 | 0.50 | 0.51 | 0.48 | 0.41 | 1.30× |
| 46224 Oceanside | 0.65 | 0.64 | 0.55 | 0.41 | 0.36 | 1.80× |
| 46225 Torrey Pines | 0.67 | 0.66 | 0.60 | 0.51 | 0.47 | 1.43× |
| 46258 Mission Bay | 0.74 | 0.72 | 0.65 | 0.57 | 0.52 | 1.42× |
| **46232 Point Loma S** | **0.77** | **0.75** | **0.69** | **0.62** | **0.55** | **1.39×** |

San Nicolas reading ~1.0 in every direction is the control — it is outside the
islands and *should* be flat, and is. That is what says the method is not
manufacturing structure.

---

## 3a. Measured, 2026-09-14 — which buoys observe Coronado's swell at all

§3 asks how much energy each buoy *loses*. This asks a prior question the
station list had never been held to: **does the swell that reaches Coronado
pass over this buoy in the first place?**

The test is one line of geometry, and it is exact rather than fitted. Swell
arriving at a break from bearing θ travelled the ray leaving that break at
bearing θ, so a buoy lies on some ray into the window exactly when its own
bearing *from the break* falls inside that break's swell-side window. Run it
with `python -m forecast.siting`.

| buoy | km | bearing | ° outside the window (N / C / S) | verdict |
|---|---|---|---|---|
| **46232** Point Loma S | 29.0 | 230.8° | **0.0 / 0.0 / 0.0** | in all three |
| **46086** San Clemente Bsn | 81.5 | 256.2° | 13.5 / 5.9 / **0.0** | in the south break's |
| 46047 Tanner Banks | 222.2 | 263.0° | 20.7 / 12.8 / 3.4 | edge |
| 46258 Mission Bay W | 30.5 | 284.2° | 41.5 / 33.9 / 25.2 | **behind Point Loma** |
| 46219 San Nicolas I. | 259.6 | 284.2° | 41.9 / 33.9 / 24.5 | behind Point Loma |
| 46225 Torrey Pines | 33.9 | 325.5° | 84.1 / 75.2 / 64.9 | off axis |
| 46224 Oceanside | 61.3 | 334.2° | 92.5 / 83.9 / 73.8 | off axis |
| 46253 San Pedro S | 136.0 | 317.2° | 75.1 / 67.0 / 57.3 | off axis |
| 46222 San Pedro | 147.6 | 314.9° | 72.8 / 64.7 / 55.0 | off axis |
| 46221 Santa Monica | 188.3 | 314.5° | 72.3 / 64.2 / 54.5 | off axis |

**46232 is the only buoy in the array inside Coronado's window, and there is no
substitute.** That reframes its outage (§8): the anchor going dark is not an
inconvenience in the data, it is the removal of the only station that observes
the swell this project forecasts. 46086 covers the south break alone and is
5.9° outside the centre's — the nearest thing to a stand-in, and partial.

**The station list was selecting on the wrong thing entirely.** It filtered on
`launch_candidate`, which marked beat-the-buoy's per-buoy *leagues* — a product
decision about where players lived. Four of its six candidates (46221, 46222,
46224, 46225) sit **55–92° off** Coronado's window: no swell that reaches these
beaches has ever crossed them. Meanwhile 46086, the second-best station in the
array by this criterion, was flagged off. The flag is now deleted rather than
repurposed, and the verdict is derived by `forecast/siting.py` rather than
stored, because §2a already paid for duplicating a derivable coordinate.

**46258 is a control, not a spare anchor.** It is 30.5 km from the centre break
against 46232's 29.0 — very nearly matched range — but on the far side of the
blocker, 33.9° inside Point Loma's shadow. That pairing is the natural control
for the aperture claim: a model that respects the geometry should track 46232
and *decouple* from 46258 as the swell direction crosses 250°. Substituting it
for 46232 while the anchor is dark would feed the transform W/WNW energy that
cannot physically arrive — the §2 failure, committed deliberately.

### Falsified in the same session

**"Score each buoy by how much of the window it can see past the blockers."**
Strictly stronger-looking than a bearing test, and it carries *no information*.
Point Loma and the Coronado Islands subtend a few degrees from any offshore
buoy and none of it lands in the 201–260° band, so **all ten placed stations
score the full window to within 0.1°** — including the ones 90° off axis. The
blockers shadow the *beaches*, not the buoys. Pinned as a null by
`test_blocker_visibility_at_the_buoy_carries_no_information`.

### New primitive

`geometry.swell_window` now computes the swell-side arc directly, as the arc
with **both edges cut by land**. §2 told the reader to "read the swell-side
window" and left them to find it by eye. It is also the mechanical reason the
chord cannot move the window (§2a): the shore normal controls only the seaward
clip, and at these beaches the clip never binds.

---

## 4. Falsified — do not re-derive these

Four ideas that looked right and were killed by their own tests.

**Shadowing improves with period.** It does not; it worsens slightly. Split by
period band, the ratio never rises and falls most in shadowed directions —
Oceanside W–WNW runs 0.43 (12–15 s), 0.37 (15–18 s), 0.32 (18 s+), a 0.74×
change. Same sign at all four stations tested, n > 3,000 per cell. *Untested
hypothesis for why:* long-period swell is directionally narrow, so a blocked
beam stays blocked, where broad-spread short-period energy leaks in at angles
that miss the blocker. Do not repeat that as established.

**Skill collapses at six hours.** Written into a spec as an argument, then
measured: ratio 0.82–1.31×. False.

**The forecast "fills in late" near the event.** The opposite. Mean signed
revision from +240h to the settled +24h call is **negative at every lead and
every station**, with only 25–42% of revisions upward — GFS-Wave starts below
the buoy and then talks itself further down, by 0.075 m on south swells at
46232. A swell that genuinely arrived bigger than modelled would revise upward.

**The residual after bias correction is recoverable.** Its one-day
autocorrelation is +0.24 to +0.46, which looks exactly like a drifting bias, and
a trailing-window correction beats the static fit by 2–9%. **The control kills
it:** an *expanding* window — every residual knowable at cycle time — captures
nearly all of that (static and expanding differ by 0.002–0.005 m), so the static
fit was never stale. What is left for genuine drift is +0.5% to +6.4% at two
stations and *negative at eight of eleven leads at the third*. The whole win is
0.14–0.69 **inches** of wave height. The autocorrelation is within-episode
persistence, not a bias that moves.

---

## 5. Measured: how wrong the published wave forecast is

1,095 archived GFS-Wave 00Z cycles per station, verified against the buoy
archive. Regenerate with `python -m forecast.verify`.

**The dominant error is a fixed low bias, not a forecasting failure.** All three
SoCal buoys sit **0.26–0.31 m below** the model at *every* lead time including
+0h. A bias present in the analysis is model geometry at an unresolved nearshore
point, not a forecast error.

| 46232 Point Loma | +0h | +24h | +120h | +240h |
|---|---|---|---|---|
| bias (m) | -0.31 | -0.30 | -0.27 | -0.28 |
| RMSE (m) | 0.38 | 0.38 | 0.40 | 0.50 |
| scatter index | 17.1% | 17.8% | 23.4% | 32.5% |

Removing it — two parameters, fit on 2023–24, scored on 2025 — cuts RMSE by
**+50% at +0h, +47% at +24h, still +25% at ten days**.

**South swell is the predictable case, not the wobbly one.** Restricted to hours
the buoy itself calls south-dominated (DPD ≥ 14 s, MWD 160–230°), 46232's RMSE
runs **0.27 m at +0h to 0.29 m at +240h** — essentially flat across ten days,
against 0.38 → 0.50 m for all hours. A swell six days in transit is the *easy*
part of a SoCal forecast; the scatter that grows with lead is local wind sea.

**Bands fitted on history are not automatically honest.** The 70% band held
78–87% for all hours (over-covering) but only **54–56% at +216h and +240h in the
south regime**. Making it proportional to forecast height did not fix it —
coverage moved a point or two, sometimes the wrong way.

**Ceiling on any upstream observation** (`python -m forecast.residual --ceiling`):
the +0h floor is 0.147 m (5.8 in) of representativeness error that no upstream
observation removes, and a swell arriving beyond about +190h has not been
generated yet at cycle time, so nothing can see it. Where an in-transit
observation could act at all, the entire prize is 2.2–6.5 inches.

**GFS-Wave performs no wave data assimilation at all** — WAVEWATCH III forced by
GFS winds and ice, nothing more. ECMWF's wave model does assimilate, and ECMWF
Open Data publishes a 0.25° `wave` stream (`swh`, `mwd`, `mwp`, `mp2`, `pp1d`)
on the same public bucket as the rest of IFS, retained from somewhere in H1 2024
(2024-01-01 is 404, 2024-06-01 is 200; boundary not pinned). Comparing an
assimilating model against an unassimilated one at these buoys costs one GRIB2
decoder and is the cheapest open experiment left. Caveat: the open-data wave
stream is **total Hs only, no partitions**, so the south-regime split cannot be
reproduced on it.

---

## 6. What the published forecasters actually do

Do not repeat the overclaim this project made. **Surf apps are not blind to any
of this.** Surfline's model gives each swell train with period and direction plus
animated storm and propagation maps, and LOTUS is WAVEWATCH III source plus
machine learning trained on years of forecaster and camera observations,
validated against satellites and buoys, claiming 25%+ error reduction, with
patents. A learned correction fitted to observed outcomes **is** bias
correction — they are doing it, at a spot, against human observers.

Their published tolerance is one foot of **face** height. An offshore Hs error of
0.2 m is a fraction of a foot of face — already inside it. Their binding
constraint is the last 50 km, not the swell.

Wave-model verification against buoys is also long established and public: the
WMO Lead Centre for Wave Forecast Verification at ECMWF has collated
buoy-collocated statistics from the operational centers for two decades. The
scatter index above is reported in their units on purpose.

**So the opening this project has is narrow and specific:** not better physics,
but a model that respects *this* geometry at *these three beaches*, where the
shadow edge sits one degree off the shore normal and a general-purpose transform
is at its most fragile. Claim that, and nothing wider.

---

## 7. The blocker: verification candidates

**Nothing measures waves at these three beaches.** In order of value:

1. **Logged human observation.** What operational forecasters verify against.
   Cheapest, and the only one that observes the actual beach. Needs a local
   person. Store observer, time, method; keep it as its own series; never blend
   it into the forecast it judges.
2. **A camera with a known scale** — the same thing, automated.
3. **CDIP MOP.** Resolves this shoreline and is the obvious cross-check, but it
   is a *model*, not truth. Unreachable from a Claude session (§8).
4. **NDBC directional spectra at 46232** (`swden`, `swdir`, `swdir2`, `swr1`,
   `swr2`). Not an observation at the beach, but it converts the transform from
   an assumption into an integral — energy inside the beach's window, measured,
   per frequency, instead of one dominant direction.

   **ANSWERED 2026-09-14: yes, and in better shape than assumed.** Run from
   Actions, all five files reachable and parsed: **64 frequency bins,
   0.0250–0.5800 Hz (1.7–40.0 s), agreeing across all five**, ~1 MB and 1,094
   rows each. `r1`/`r2` arrive **already normalised to [0, 1]** — no percent
   rescaling for the real-time product, so that trap is settled for this source
   and still worth re-checking on the historical files. The D(f,θ)
   reconstruction integrates: 21.7% of the buoy's energy inside Coronado's
   centre-break window on the record tested. **The transform's input exists and
   is measurable.**

   `collector/probe_spectra.py` is what settled it: all five files, freshness sniffed from the newest
   parsed record rather than from HTTP 200, frequency bins checked for agreement
   across the five, and a D(f,θ) reconstruction integrated over a real window as
   proof the chain works. **Run it on Actions, not from a session** — on
   2026-09-14 `www.ndbc.noaa.gov` was again denied at CONNECT from a session
   (§8), and "unreachable from here" is not "not published".

---

## 8. Environment and process lessons

**Egress is policy-controlled and changes mid-session.** On 2026-09-13 both CDIP
hosts, and then `www.ndbc.noaa.gov`, began refusing at CONNECT with a proxy-side
403 — after NDBC had served thousands of files earlier the same day. A 403 there
is a **denial, not throttling**; the tell is that the proxy refuses the tunnel
before any HTTP request is sent, so it surfaces as a connection error and the
host looks dead rather than forbidden. Check
`$HTTPS_PROXY/__agentproxy/status` → `recentRelayFailures`. Report the host; do
not retry or route around it. The scheduled collector runs on GitHub Actions and
is unaffected by any of this.

**An earlier diagnosis of the same symptom was wrong** and stood for hours: four
roots crawled in ten minutes, all began failing, "we are being rate-limited",
2 s delay added as the fix. The delay was good manners; the explanation was not
supported. `collector/probe_mop.py:DENIAL_NOTE` records it.

**Present is not live, and the verdict is where that gets missed.** The first
run of `probe_spectra` found all five files reachable — and 306 hours old. The
freshness sniff caught it and the table reported it; the exit code ignored it,
so the run went green and the workflow announced the transform unblocked on the
strength of a fortnight-old spectrum. Staleness now downgrades the exit code.
The fault is BRIEFING's own §8 list arriving through the *verdict* rather than
the parse, which is the harder place to see it.

**Partly explained, 2026-09-14 — why the staleness alert went quiet.**
`health.newly_dark` suppresses a station dark for longer than
`2 × max_age_hours` (96 h) on purpose, so that a long outage does not re-alert
daily and train the owner to ignore it; after that it moves to a "known-dark,
not re-alerting" list. So for 46232 the alert had roughly 2026-09-01 to 09-05 to
be seen and has been silent by design since. That accounts for the silence but
**not** for whether it was ever delivered, which is still unchased. Separately,
a station that has *never* reported had no date to age from at all and so was
reported newly-dark on every run forever — found when 46235 was registered while
dark; `first_checked_utc` now dates it from when the collector started looking.

**RESOLVED 2026-09-17: 46232 is reporting again.** The gap in the archive runs
`2026-09-01T13:26Z` to `2026-09-17T17:56Z` — **16.2 days**, first seen by the
collector at 22:24:08Z the same day. Nothing was done to fix it, so nothing was
learned about the cause, and the outage is the measured fact worth keeping: the
one buoy §3a shows has no substitute can vanish for a fortnight without notice.
Sixteen days is also a hole in the record that the 45-day window will erase
around 2026-10-16, and it cannot be backfilled — NDBC's historical archive is
annual and does not cover the current year.

**Station 46232 stopped reporting on 2026-09-01T13:00Z** and was still dark
thirteen days later. Not a feed problem: the repository's own stdmet archive for
46232 ends at `2026-09-01T13:26Z`, the same cutoff, with `first_seen_utc` of
2026-09-12 — the collector was still looking and finding nothing newer. **The
48-hour staleness alert did not visibly fire**, which is its own question and
has not been chased. A dead anchor buoy is a live problem for the whole project:
46232 is the station every transform and every forecast here is anchored on.

**Probe verdicts are untrustworthy by default.** Four distinct faults produced
confident wrong answers in the predecessor: 543-day-stale content served behind
HTTP 200; substring matches against page furniture; a 200 KB read truncating the
evidence; and `"NOAA" in "...not NOAA"`. Sniff freshness, match specific strings,
read fully, and return typed flags.

**Performance:** re-reading a 26,000-row CSV inside a candidate loop turned a
12-second job into minutes — twice, in two different modules. Memoise the column
reads.

**Method that worked, and is worth keeping:** probe before building; test
in-sample as an upper bound only; validate out-of-sample on a held-out year;
and for anything that looks like a finding, **write the control that would kill
it** — the expanding-window control in §4 is the model.

---

## 9. Open questions

- ~~Digitised shoreline coordinates for the three beaches.~~ **Done for
  Coronado, 2026-09-14** (three breaks, plus the Point Loma tip); see §2a. Still
  open for Breakers and Gator, and for a re-digitised Coronado north-break chord
  once the Google Earth imagery splice there is resolved — that chord sits ~19°
  off the local coast trend, which costs the window nothing and makes the normal
  unusable for wind and refraction.
- Are NDBC directional spectra reachable and complete for 46232?
- **Where is 46235?** Registered 2026-09-14 and archiving, but unplaced:
  `www.ndbc.noaa.gov` was denied at CONNECT from the session that added it, so
  its coordinates are not in `data/station_metadata.csv` and `forecast.siting`
  reports it UNPLACED rather than guessing. Run `python -m collector.metadata`
  **on Actions**, then `python -m forecast.siting`. Recalled but unverified:
  Imperial Beach Nearshore, CDIP 155 — a lead to check, not a fact. If that is
  right it sits *south* of the breaks, which would put it in the near-useless
  south-east arc rather than the swell window; the tool will say.
- Does a nearer south-west station exist that 46086 is standing in for? The
  window's edges (201–215° and 240–250° at the centre break) have **no buoy on
  them at all** — 46232 sits at 230.8°, mid-window — so the two bearings where
  dH/dθ is largest are the two nothing observes.
- Zuniga Jetty and harbour-shoal geometry for Breakers.
- Does refraction/shoaling over the shelf need modelling, or does a measured
  per-direction transfer function absorb it?
- Wind (KNZY) and tide (NOAA 9410170) — neither probed, both essential at these
  beaches.
- Is ECMWF's assimilating wave model measurably better than GFS-Wave at 46232?
- ~~What does a verification log actually look like, such that a person will
  fill it in daily for a year?~~ **Answered, 2026-09-14** —
  `docs/observation_log.md`, built as `collector/beachlog.py`. The short version:
  nothing makes a person do anything daily for a year, so it is built to survive
  irregularity instead of demanding consistency, and it asks for the
  **differential** (is the south end bigger than the north end today?) rather
  than the absolute height — that being both what people report reliably and
  what this project actually claims. Its control is that **Coronado's two window
  edges predict opposite orderings**: Point Loma cuts the north break off first,
  the Coronado Islands cut the south break off first, so a fixed bias agrees on
  one edge and contradicts the other while a real aperture effect flips.
  Still open: whether anyone fills it in. The file is empty.

---

## 10. Measured, 2026-09-18 — the Coronado Islands should never have been a binary blocker

The locals are right, and there is now a mechanism and a number behind it.
This section supersedes any reading of §2 that treats the islands' shadow as
equivalent in kind to Point Loma's.

**The islands subtend 10.9°; Point Loma subtends 54.0°.** Against a swell with
a realistic directional spread, that difference is not a matter of degree:

| directional spread | removed by islands (10.9°) | removed by Point Loma (54.0°) |
|---|---|---|
| 10° | 11.5% | 52.5% |
| 20° | 11.2% | 51.6% |
| 30° | 10.4% | 48.3% |

Worst case — the notch centred exactly on the swell peak. **The islands remove
about 11% of the energy no matter how the swell is spread**, which is ~6% of
height, well under an inch on a waist-high wave. Point Loma removes about half.

**So the binary open/shut verdict for the islands was a modelling error, not a
low-confidence claim.** It only appeared because a single `MWD` value was being
tested against a hard-edged sector. Integrate the directional spectrum over the
aperture instead and the 11° notch correctly costs ~11% of the energy, with no
special-casing: the transform dissolves the problem rather than tiering it.

**Diffraction says the same thing.** Fresnel number `F = W²/(λL)` — sharp
shadow when `F >> 1`, filled in when `F ~ 1`:

| period | λ | F, Point Loma (6.2 km at 5.7 km) | F, islands (6.1 km at 31.1 km) |
|---|---|---|---|
| 12 s | 225 m | 30.1 | 5.4 |
| 15 s | 351 m | 19.3 | 3.5 |
| 18 s | 506 m | 13.4 | 2.4 |
| 20 s | 625 m | 10.8 | 1.9 |

Point Loma casts a genuine geometric shadow at every surf period. The islands
are marginal and get worse with period — at 20 s, `F ≈ 1.9`, so diffraction
fills a good part of even the 11%. **Untested hypothesis, do not repeat as
established:** the islands' true transmission is higher than geometric.

### The correction this forces on §9's "digitise the islands" item

**Digitising the Coronado Islands is low value and can be deprioritised.**
Worst-case edge movement over 24 perturbation directions, per edge:

| edge | 250 m | 500 m | 1 km |
|---|---|---|---|
| Coronado breaks / Point Loma | 2.20–2.82° | 4.40–5.64° | 8.83–11.36° |
| Coronado breaks / islands | 0.46° | 0.92–0.93° | 1.84–1.86° |

The islands are 31 km away, so their angular leverage is **five times lower**
than Point Loma's. A full kilometre of island error costs under 2°. The earlier
finding that "moving the islands 500 m flips 20.6% of live swell hours" was
**high traffic, not high leverage** — south swell sits on that edge in
September, so a small angular move crossed a binary threshold many times. Once
the verdict stops being binary, the same 500 m moves ~11% of energy by a
fraction of itself.

**The high-leverage coordinate is still the Point Loma tip, and it is already
digitised.** CLAUDE.md's "highest-leverage coordinate in the repository" stands.

### What this means for the disagreement headline

The 50.0% of swell hours on which the five breaks disagreed (3-year archive,
Hs ≥ 0.6 m, DPD ≥ 12 s) is **inflated by island-driven binary flips**. Split by
which blocker causes it: **19.4% from Point Loma, 33.7% from the islands**
(they overlap). Only the Point Loma share is a real differential. In the live
45-day window the split is 1.2% against 56.4% — September is south-swell
season, which sits on the island edge — so *today's* between-break differences
are almost entirely an artifact of the binary treatment.

**Quote the Point Loma number, not the total.**

---

## 11. Measured, 2026-09-18 — the differential survives the weakest assumption

GFS-Wave publishes swell partitions with no directional spread, so running them
through an aperture requires assuming one. That assumption (20° for swell, 35°
for wind sea, `forecast.transform.SWELL_SPREAD_DEG`) is **the least defensible
number in the forecast chain**: conventional, not fitted, with nothing to fit it
against. So it was tested rather than trusted.

Window height at each break against assumed spread, 2026-09-18 00Z cycle:

| spread | north | center | south | south/north |
|---|---|---|---|---|
| 10° | 0.604 m | 0.617 m | 0.632 m | 1.046 |
| 20° | 0.609 m | 0.622 m | 0.637 m | 1.046 |
| 30° | 0.614 m | 0.626 m | 0.640 m | 1.043 |
| 40° | 0.614 m | 0.622 m | 0.636 m | 1.035 |

On a synthetic W swell from 255°, where the geometry actually separates the
breaks, the same sweep runs the ratio 1.249 → 1.198.

**Absolute height moves 2–5% across a fourfold change in the assumption; the
ratio between breaks moves 1–4%.** The differential — the only thing this
project claims — is nearly immune to the worst-supported input in the chain.
That is a reason to publish the ratio prominently and the absolute height
quietly, which is what `forecast.live` and the app surface do.

**This is not a claim that the heights are right.** It says the assumption is
not what would make them wrong. The bias, the missing shoaling and refraction,
the absent offshore-to-face transfer and the total absence of any verification
series are all still there, and they are all larger.

Pinned by `tests/test_live.py::TestTheDifferentialIsRobust`.

### Also found, 2026-09-18 — the GFS-Wave collector had been dead for three days

NCEP stopped publishing per-station bulletins
(`gfs.YYYYMMDD/HH/wave/station/bulls.tHHz/gfswave.{id}.bull`) between
2026-09-15 and 2026-09-16. Every station 404s from 2026-09-16 onward. The data
did not go away: it ships in `gfswave.tHHz.bull_tar` in the same directory,
~49 MB and ~918 stations, and has all along.

The failure was silent in the worst way — `fetch_bulletin` treated a 404 as
"NCEP did not run that cycle", which was true for three years and stopped being
true without anything changing in this repository. **A 404 that used to mean one
thing now means another, and nothing alerted.** Same shape as the staleness
alert not firing for 46232's outage (§8): the monitoring watched for the failure
it expected. `fetch_bulletin` now checks the tar before believing a 404.

---

## 12. Missing blocker, 2026-09-18 — the Baja coastline is not modelled

`spots.json` carries two blockers: Point Loma and the Coronado Islands. It does
not carry the coast running south from the beach, and that gap was visible on
the app surface before anyone measured it — the published "open window" for
Coronado's north break read **103–189°**, which is a claim of open water across
a coastline you can see from the sand.

Measured from each break, the south-east arc spans the bearings where:

| landmark | bears (N / centre / S) | distance |
|---|---|---|
| Imperial Beach pier | 154.8° / 157.6° / 161.0° | 11–13 km |
| Tijuana river mouth | 157.7° / 160.1° / 163.0° | 14–16 km |
| Playas de Tijuana | 158.9° / 161.0° / 163.5° | 17–19 km |
| Rosarito | 160.5° / 161.5° / 162.6° | 39–41 km |

§2 already said this arc was "geometrically real and practically near-useless"
and to "read the swell-side window". That was right and it was not enforced
anywhere, so the first surface built on the geometry published it.

**The rule, now enforced:** a genuine swell-side window has **both edges
blocker-derived**. An edge formed by the seaward half-plane clip means the arc
ran out of modelled land, not that it ran into open ocean.
`forecast.geometry.swell_window` applies that test and is what
`forecast.live` and the app publish; `open_window` still returns everything, so
the gap is filtered at the surface rather than hidden in the model.

**Still open:** digitising the Baja coast from Imperial Beach south would close
the arc properly and is worth more than digitising the Coronado Islands (§10) —
it is nearer, longer, and currently carries no blocker at all. It bears on the
south-east arc only, which is not where San Diego's swell comes from, so it is
a correctness fix for the surface rather than a change to any forecast in the
open window.

---

## 13. Measured, 2026-09-18 — the first real Actions run, and what it caught

The three collectors added this day all work from a runner. All three of their
hosts are denied at CONNECT from a Claude session, so this was the first
evidence either way:

| source | result |
|---|---|
| NDBC directional spectra, 46232 | five components archived, ~1 MB |
| KNZY wind | flowing — `290° 10 kt` on the first cycle carrying it |
| NOAA 9410170 tide | predictions stored |

**And the forecast still said "tide not collected" on most of its hours.** 100
of 169. Two gaps, both from fetching predictions relative to *now*:

- **Head.** A GFS-Wave cycle publishes about five hours after its nominal time,
  so the forecast starts in the past. Predictions beginning at fetch time missed
  the first four hours.
- **Tail.** Predictions ran to +96 h; the forecast runs to +168 h. Sixty-nine
  hours uncovered.

Fixed by fetching −24 h to +192 h (`collector.tide.PREDICTION_BACK_HOURS` and
`PREDICTION_AHEAD_HOURS`), which brackets `live.DEFAULT_HOURS` at both ends.
Hourly predictions are one small request either way, so the margin is free.

**The shape of the fault is the interesting part.** Nothing failed. Every
component reported success, the archive filled, the warnings list was empty, and
the surface degraded exactly as designed — it said "not collected", which was
true, and gave no reason to suspect the collector had run perfectly. A field
that is *allowed* to be absent cannot also signal that something is wrong, and
this project has a lot of those. It is the same shape as the staleness alert
suppressing itself after 4 days (§8) and the GFS-Wave 404 that changed meaning
(§11): **the monitoring reported on what it was asked about, and the question
was wrong.**

Worth a rule: when a field may legitimately be missing, something should still
check the rate. "Tide is absent on 41% of forecast hours" is a fact no component
was in a position to notice, because each one only saw its own half.

### Also: the published page fetched a path that does not exist

`forecast/publish.py` builds a flat bundle for the public Pages repository. The
page fetches `../data/live/forecast.json`, which is right in this repository and
404 in a flat bundle, so the first build rendered a correct, complete, empty
shell. Caught by rendering the bundle rather than by reading it, which is the
only way it *could* have been caught — the HTML was valid, the JSON was valid,
and the page's own error handling worked.

---

## 14. Measured, 2026-09-19 — the spectral chain reproduces the buoy's own report

Before building the observed "now" path on it, the chain from archived NDBC
spectral files through `forecast.transform` was checked against the quantities
46232 publishes for itself. If these disagreed, nothing downstream could be
trusted.

| quantity | spectrum vs the buoy's own report | n |
|---|---|---|
| Hs from integrating E(f, θ) vs `WVHT` | −0.7% to +8.4% | 3 |
| α₁ at the peak bin vs `MWD` | mean **8.0°**, median **5.0°** | 37 |
| 1/f at the peak bin vs `DPD` | mean **0.79 s**, median **0.38 s** | 37 |

The residuals are about what the reported precision allows: `MWD` comes in
whole degrees and `DPD` in whole seconds, and the peak is quantised to a
frequency bin.

**The trap this walked into first.** Compared against the *energy-weighted mean*
direction, the same spectra looked 42–50° away from `MWD`, which reads like a
broken convention. It is not: **`MWD` is α₁ at the peak frequency**, and the
mean over a spectrum carrying both a south swell and a west windsea sits
between them. Two different quantities, one of which happens to have a similar
name. `Survives.peak_period_s` had the same fault — it held an energy-weighted
mean — and is now `mean_period_s`, with the true peak added beside it.

### What the observed reading shows that the buoy alone does not

From the spectrum of 2026-09-19T00:00Z:

| | Hs | peak period | peak direction |
|---|---|---|---|
| the buoy itself | 1.34 m | 5.9 s | 292° |
| Coronado north | 0.66 m (24%) | 13.3 s | 192° |
| Coronado centre | 0.69 m (26%) | 14.3 s | 208° |
| Coronado south | 0.76 m (32%) | 14.3 s | 208° |

**The peak changes wave train at the beach.** What dominates offshore is a
5.9 s west windsea, and Point Loma takes it; what is left is a 13–14 s south
swell at roughly a quarter of the energy. A forecast anchored on this buoy that
skips the aperture reports the windsea. §2's "most days the forecast is a
transform artifact, not a propagated wave" is this, on measured data.

Note the peak is taken **after** the aperture, which is why north differs from
centre and south: they do not all keep the same train.

---

## 15. Measured, 2026-09-19 — WAVEWATCH III publishes its own spectrum and wind

`gfswave.tHHz.spec_tar.gz` carries, per cycle and per station, a full 50 × 36
directional energy grid at every forecast hour, with the 10 m wind and surface
current in each record's header. That is two problems solved from one file:
forecast wind with no second source, and a **measured** directional spread in
place of §11's assumed 20°/35°.

### Cost, and why nothing is archived

The tar is 1.73 GB, but 46232 is **member 330 of 918**, so streaming it and
stopping at that member needs **617 MB and about ten seconds** — the remaining
1.1 GB is never pulled. Gzip has no random access, so stopping early is the
only saving available, and it is a large one.

`spec_tar.gz` still returns 200 for **2021-04-01**, so CLAUDE.md's rule applies
directly: do not write an "archive it now" job for history that is not
unrecoverable. Only the derived per-break numbers are stored.

### Two direction conventions in one file, and they disagree

| field | convention | evidence |
|---|---|---|
| spectral grid | **TOWARD** | flipped: 4.5° from the bulletin's dominant partition; as-is: 175.5° |
| header wind | **FROM** | as-is: 29.4° against KNZY vs 150.6° flipped; 12.6° against the wind-sea partition vs 167.4° |

Both were measured, both twice. `collector.wavespec` flips the grid once and
leaves the wind alone.

### The bug that total energy could not catch

The direction axis **descends** (264.8, 255.1, 245.1, …). The first
interpolation assumed it ascends, which scrambles which heading each energy bin
sits at — **and integrates to exactly the right total**. Hs came out 0.800 m
against the bulletin's 0.80, looking like a clean validation, while the peak
landed on a 3.1 s wind sea where the bulletin said a 15.3 s swell.

**A total is not a validation of a mapping.** Any permutation of the bins
conserves it. What caught this was comparing a *located* quantity — the peak —
against an independent statement of the same thing. Worth remembering wherever
a check is "the numbers add up".

Corrected, the grid gives peak 15.6 s from 192° against the bulletin's 15.3 s
from 196°, and Hs 0.790 m against 0.80 (the 1.3% is 1° sampling of a 10° grid).

### The two paths agree, which is the real control

Same model, same cycle, two independent representations through the same
aperture — the measured-spread grid against the assumed-spread partitions:

| | worst disagreement |
|---|---|
| window Hs, all three breaks, 25 hours | **5.6%** |

The grid runs consistently 3–5% lower. **This confirms §11 by a completely
different route**: if the assumed spread had been doing real damage, replacing
it with a measured one would not land within six percent.

### Growth, fixed in the same change

`data/live/` is now gitignored. It is derived output, rebuilt every cycle from
inputs that are all either committed here or served by NOAA back to 2021, and
the public delivery repository's git history is already the record of what was
shown and when. Committing it cost 315 KB four times a day — about **460 MB of
git objects a year** — to duplicate a record that exists in the right place.

This does not weaken "data files are tracked, not ignored": that rule guards the
irreplaceable NDBC archive and the collected series beside it. A regenerable
forecast is neither.

---

## 16. Measured, 2026-09-19 — the leading wave train is not the same at the buoy and the beach

A spectrum is two or three swells plus a wind sea, and the aperture does not
scale them together: it takes whichever ones point at the blocked sector. So
**which train leads can change between the buoy and the sand, and between the
three breaks on one spectrum.**

`forecast.transform.split_trains` splits the surviving energy at its local
minima, after the aperture, so each break's trains are the ones reaching it.

### How often it happens

Over 400 archived NDBC spectra at 46232, the leading train at Coronado centre
differed from the leading train at the buoy by more than 3 s on **92 of them —
23%.** Not an edge case.

Measured example, 2026-08-17T09:00Z:

| | leading train | second |
|---|---|---|
| at the buoy | 0.79 m, 5.6 s, from 260° | 0.69 m, 15.4 s, from 202° |
| at Coronado centre | **0.62 m, 15.4 s, from 196°** | 0.46 m, 5.6 s, from 231° |

Point Loma takes most of the westerly and the south swell leads at the beach.

### And it differs between the three breaks

2026-09-19T04:00Z, one spectrum:

| | leading train |
|---|---|
| buoy | 0.91 m, 7.1 s, from 268° |
| north | 0.46 m, **14.3 s**, from 183° |
| centre | 0.48 m, **14.3 s**, from 187° |
| south | 0.53 m, **7.1 s**, from 240° |

North and centre are led by the south swell; the south break, whose window
reaches to 259.9°, is still led by the westerly. Same water, three answers —
which is the project's whole premise, now visible in one reading.

### What the splitter is, and is not

**A peak split of the 1-D spectrum, not a spectral partitioning.** WAVEWATCH III
uses a watershed over the full 2-D field and can separate two trains that share
a frequency band while arriving from different headings; this cannot, and
reports them as one train at the energy-weighted mean heading. It is honest for
the common case, where swell and wind sea are well separated in frequency.

**Peaks need prominence.** Without a rule that the trough between two peaks must
fall to 60% of the smaller one, ordinary wiggle in a wind sea split into four
"trains" at 4.2, 5.3, 6.2 and 7.1 s — a description of the noise, not the water.
With it, the median spectrum yields three trains.

### The control

The robust claim is not that the leader flips — that depends on how far ahead
the blocked train started — but that **the ratio always moves in favour of the
open train.** Across a synthetic sweep, south-to-sea height ratio at the buoy
against at the beach: 0.57 → 0.85, 0.62 → 0.92, 0.68 → 1.00, 0.76 → 1.12,
0.87 → 1.30. Every case, same direction. The leader itself flips once the
starting margin is small enough. Both are pinned in
`tests/test_transform.py::TestSplittingIntoTrains`.

---

## 17. Found, 2026-09-19 — "at the buoy" was quietly clipped to a beach's half-plane

The Now surface showed a combined Hs with a list of wave trains under it, both
labelled as the buoy's. The Hs came from `Survives.m0_total`, which integrates
every direction. The trains came from the *transmitted* energy — and
`through(spectrum, spot, [])`, with no blockers at all, still applies that
spot's seaward half-plane. So the trains excluded everything outside
124–304° of the centre break's normal.

Measured across the archive, that is **12–26% of the energy** — worst case
26.4% on 2026-08-30T18:00Z. It is exactly the NW sector §2 counts at 3,771
hours of the record.

**The symptom was a sum that did not match its own headline**, which is the only
reason it was visible at all: the Hs was right, each train was right, and
nothing threw. Had the card shown trains alone, or a headline alone, it would
have read as correct indefinitely.

`transform.at_buoy` integrates the full circle with no spot and no
transmission, and is what both surfaces now use. A buoy 29 km offshore has no
landward half.

### The same shape, twice more in one session

- §15: a scrambled direction axis that still integrated to exactly the right Hs.
- §13: tide absent on 41% of forecast hours, with every collector reporting
  success.
- This: an aperture applied where none was meant, visible only as an
  inconsistency between two numbers that were each individually right.

**A quantity that is correct on its own is not evidence that the thing
producing it is.** Each of these was caught by cross-checking two views of the
same state against each other, and none by a value looking wrong.
