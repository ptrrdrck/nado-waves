_Read before touching workflows, collection timing, countdowns, staleness, caching, egress, external sources' quirks, retries, or the test suite's cost._

# Infrastructure

Moved verbatim from CLAUDE.md on 2026-11-14 (the context-reduction
restructure); CLAUDE.md keeps the one-line rule and points here.

## Infrastructure

- The collector runs as a **scheduled GitHub Actions workflow**, not a local
  cron and not a VPS. It must run whether or not a dev machine is on, and it is
  unaffected by what an interactive Claude session can reach.
- Observations are **committed back into this repository** as per-station files.
- **Wire in a keepalive action.** GitHub disables scheduled workflows after 60
  days of repository inactivity, and the workflow's own bot commits do not
  reliably reset that timer.
- **GitHub's scheduler is throttled, and frequency is not a lever.** Measured
  2026-09-22 across four schedules on this repository: the rate actually
  DELIVERED sits near 0.2 runs an hour whatever the cron asks. 5/day got 84%,
  hourly 26%, 2/h 11%, `*/10` **2%** — and `*/10` came out lower per hour than
  hourly did. Raising the cron to buy freshness is a falsified idea; it was
  tried and reverted the same day. Reliable collection is driven from outside
  by `repository_dispatch`, and the cron is a backstop — `docs/collection_trigger.md`.
  Keeping it inside Actions was rejected on cost: spacing runs apart needs a
  job that sleeps, and a sleeping job holds a runner for the gap, ~24
  runner-hours a day at any cadence.
- **An update countdown is three real events on the clock, not intervals added
  to the reading on screen.** `forecast/now.py` walks: the next time the source
  PUBLISHES (`PUBLISH_MINUTES` — swell `:00`, wind `:52`, tide every 6 from
  `:00`, all measured), plus how long until that is FETCHABLE
  (**no source is fetchable at its own stamp minute** — modelling the tide as
  though it were promised a sample CO-OPS had not written yet, turning a reading
  eight minutes old into a red card), rounded
  up to the next COLLECTION from `EXTERNAL_TRIGGER_CRON`; the page then adds its
  own refresh interval, because only it knows that, and to the RED instant
  alone `PUBLISH_LEG_MS` (5 min; owner's call, 2026-10-23, BRIEFING §46): the
  run publishes ~2.1 min after its mark and Pages deploys after that, so red
  at mark + refresh caught files still on their way. The countdown is not
  moved; "Update due" covers the publishing.
- **The lag is a distribution, so it takes two numbers, not one.** A single
  deadline has to choose between crying wolf and quoting a figure that almost
  never applies, and both are dishonest on screen. `PUBLISH_LAG_MIN` is the
  measured typical and the countdown runs to it; `PUBLISH_LAG_LATE_MIN` is the
  measured worst and the card only turns red past that, saying "update due" in
  between without claiming anything is wrong. Measured 2026-09-25 by bracketing
  each hour against the collection log: **4 of 6 spectra land by H+15 and one
  took H+35.3**, so the old single value of 27 was above the typical AND below
  the worst — twelve minutes pessimistic on the common hour, promising an hourly
  source **100 minutes from stamp to screen where 80 was honest**, and still red
  on the late one. Swell 15/36, tide 5/10 (re-bracketed 2026-10-23 on ~6,800 samples: 8 sat inside the tail, 34 were still absent past it; an outage at CO-OPS is red and rightly, owner's call 2026-10-27, after ten samples of 26 Oct landed 100–154 min late in one batch), wind 3/4. n = 6 for the swell, which
  is thin; revisit as the archive fills (re-bracketed 2026-10-06 on 260: 15
  holds, and 36 rounds to the H+45 run, red on 4 of 260 that came later —
  BRIEFING §39, not changed). 46047 on the Buoys tab: 25/85, its own, in
  `forecast/buoys.py`, through `now.deadline`'s same arithmetic. The first version added
  `source interval + 2 × collection interval` to the reading on screen instead,
  which charged a tide sample due in ninety seconds a full six minutes and then
  twenty more as slack — **over twenty minutes of countdown for a source that
  publishes every six.** There is no slack term now: the external trigger lands
  on time to the second, so a missed collection is a real failure and the card
  should say so. **46232's `:26`/`:56` is STANDARD MET**, a different product in
  `data/observations/` that no card reads; the Now tab's swell is the hourly
  directional spectrum.
- **Past `STALE_HOURS` (3 h) a LIVE card's numbers go grey** (owner's call,
  2026-10-25; `agedAttr`, flipped by `tickDue` on the reader's clock, the
  build's `stale` a floor): every such text one shade, `--faint` — a
  secondary train's heading within a few steps on both themes, so secondary
  rows lose their fade — weights kept, and back to normal when a newer
  reading lands. Each card its own source: break tabs and 46232's reading by
  46232's spectrum, 46047 and 46086 by their own, Wind (value and each
  break's line) by KNZY, Tide's height by the gauge. NOT the calculation
  table or Origin (right for the reading they were made from), the
  provenance, or the tide's predicted turn; on the drawing only the leading
  train's arrow. A rose frame greys only if it was itself the stale
  reading (`roseAged`): more than 3 h from its stamp to the NEXT frame's
  stamp, or to now for the newest — petals and the line under them,
  Period's bands kept in order up to `--faint` — never the rings or
  N / E / S / W. A frame replaced in time stays in ink however old it grows
  in the loop: greying frames by their age today greyed every current
  buoy's 3–6 h frames, and greying the whole rose with its newest frame was
  wrong too (owner's calls, same day). Stamps, not arrival times, by the
  owner's call.
  Red "Overdue" starts long before this, at each source's late instant.
- **A cadence promised on screen must match the trigger that keeps it.**
  `COLLECT_INTERVAL_MIN` in `forecast/now.py` feeds each Now card's countdown.
  When the cron said `*/10` and GitHub was delivering one run every four hours,
  every card called itself late against a schedule nobody was keeping — the
  countdown reported the gap between the request and reality rather than
  anything about the data. The trigger is now external, so `now.py` declares
  `EXTERNAL_TRIGGER_CRON` and `tests/test_now.py` pins the interval to it, pins
  the GitHub cron to being a slower backstop, and pins the wind offset.
  **No test can reach cron-job.org** — changing the interval there without
  changing `EXTERNAL_TRIGGER_CRON` is the one move nothing catches.
- **46232's spectra do not publish on a fixed minute.** Measured 2026-09-25 by
  bracketing each hour between the last collection without it and the first
  with it: 23Z was still absent at H+16.7 while 01Z had landed by H+15.0, so
  there is no single publication minute — it jitters across roughly **H+7 to
  H+27**. A trigger phase-locked to the swell would therefore be early on some
  hours and twenty minutes late on others; only the INTERVAL bounds staleness
  against a jittering source. The phase is spent instead on KNZY's `:52`,
  which is pinned (81 of 95 archived observations), and the `:55` run catches
  it three minutes later against a measured median of 110.
- **Keep the staleness alert** — no new observation in 48 hours, notify. A
  silently dead collector loses days that cannot be recovered. It did not
  visibly fire for 46232's 16-day outage; **partly explained** (BRIEFING §8):
  `health.newly_dark` deliberately suppresses anything dark longer than
  2 × 48 h, so the alert had 09-01 to 09-05 to be seen and has been silent by
  design since. Whether it was ever *delivered* in that window is still
  unchased. A station that had never reported at all had no date to age from
  and alerted forever; `first_checked_utc` fixes that. **The directional
  spectra are checked too, file by file** (`staleness.spectra_report`, since
  2026-10-05): the standard met keeps a station "live" on any column, and
  46086 reported wind for ten days after its wave sensor stopped on
  2026-09-25 with nothing noticing. A spectrum newly past 48 h alerts once; all
  of them stale is a dead spectra collector.
- **GitHub Pages caches for ten minutes and you cannot change it.** Measured on
  the live bundle 2026-09-25T15:48:58Z: Pages serves through Fastly with
  `Cache-Control: max-age=600`, and Pages exposes no header configuration, so
  this cannot be fixed on the publishing side. Ten minutes of permitted
  staleness against a ten-minute collection cadence means a cache HIT can hand a
  reader a `now.json` one whole collection behind — and its age line would be
  honest about a reading that had already been superseded. So every payload
  fetch carries a `?v=<epoch ms>` (`fresh()` in `app/forecast.html`): a distinct
  URL cannot be answered from any cache by definition, which turns a policy we
  do not control into arithmetic we do. `cache: "no-store"` stays alongside it —
  the parameter defeats shared caches, `no-store` defeats the browser's own, and
  they are different caches. **The sample that confirmed the mechanism was
  itself a MISS** (`Age: 0`, `x-cache: MISS`, `Last-Modified` 3m14s before
  `Date`), so `no-store` was honoured there; the reason to fix it anyway is that
  honouring a client `no-cache` is Fastly CONFIGURATION rather than a guarantee,
  and says nothing about what another edge node holds for the next reader.
- **Egress from a Claude session is policy-controlled and changes mid-session.**
  A 403 at CONNECT is a denial, not throttling: check
  `$HTTPS_PROXY/__agentproxy/status`, report the blocked host, do not route
  around it. See `collector/probe_mop.py:DENIAL_NOTE` and BRIEFING §8.
- **CSULB Shark Lab's ERDDAP is a nightly copy, with gaps and every row
  twice** (measured 2026-10-20 to -29, BRIEFING §47): the lab downloads
  from Innovasea once a night, a whole UTC day the next day; days go
  missing for good (October 2026 at both Coronado hubs: 11 of 28); and
  every status and detection row is stored twice, as exact copies. So
  `collector.sharklab` re-reads a trailing 72 h, keeps each reading once,
  never fills a gap, and counts a stamp that comes back changed rather
  than overwriting it. It is plain http
  (`erddap-public.csulbsharklab.org`), denied from a session, and not in
  the staleness alert: a 48 h alert would fire every night.
- **The county's beach water site is an OutSystems app read through its own
  screen services** (BRIEFING §48, `collector.probe_beachwater` runs 1–8):
  the pages are a 2 KB shell; `collector.beachwater` reads the module's
  scripts from `moduleservices/moduleinfo` EVERY collection for each
  aggregate's API version (they change when the county redeploys), and
  calls each as the SCREEN its block is shown on (`BLOCKS`: a block's own
  name is refused "No role validation found"), the paging as
  `inputParameters`, the anonymous CSRF token; a refusal comes back inside
  an HTTP 200, so the body is read. Samples filter by `StationIdFilter`
  (SiteId is ignored and every station came back), and only a station's
  own rows are filed under it; the posting report pages past 1,000 rows
  and lists an event once per beach group, its free text differing.
  Probe allow-list only: run 3's deny-list let a server action named
  MigrateSample through (refused for want of a role). Denied from a
  session; not in the staleness alert. **Read EVERY collection** (owner's
  request, 2026-10-31, after colleagues saw South's advisory before the
  page did): at the old 30 min floor reads landed 30–40 min apart, and the
  site itself showed the 30 Oct advisory 23–53 min after its own issue
  time (absent at the 23:05Z read, there at 23:35Z; BRIEFING §48b). The
  block scripts are fetched again only when their manifest version changes
  (`Client.start`'s cache, `scripts` in state.json): a read is ~12
  requests and ~3 s.
- **A 404 that used to mean one thing can start meaning another.** NCEP dropped
  the per-station GFS-Wave bulletin files between 2026-09-15 and 2026-09-16;
  the data moved to `gfswave.tHHz.bull_tar` in the same directory. The archive
  job read the 404 as "NCEP skipped this cycle" and went silently to zero rows
  for three days. `collector.gfswave` now checks the tar before believing a
  404. Same shape as the staleness alert missing 46232's outage: the monitoring
  watched for the failure it expected. And the reverse (2026-09-30): on the
  NEWEST cycle a 404 almost always means "not out yet" — 46232's bulletin
  lands ~5 h 25 min after the nominal time, the directory filling over an
  hour — so `live.fetch_latest` says the run is not published yet and which
  run it is showing, rather than printing the URL. Its spectral tar can land
  after the bulletin (2026-10-22 12Z), and `live.fetch_spectra` says that too;
  no spectrum note carries a URL (it ran past the card on a phone), the build
  log keeps it. The build's notes show on the Forecast tab only, in greys
  under a warning triangle (owner's call, same day): LIVE is measurements.
- **Retry what a build loses for its whole life, not what the next
  collection fetches again.** `common.retrying` (owner's request,
  2026-10-15) tries the NWS grid three times and GFS-Wave's spectral tar
  twice on a 5xx, 408/429, reset or cut stream: a failed fetch cost a whole
  build its local chop (2026-10-12 02Z) or put it on partitions (2 of 158
  builds). Never a 404, never a proxy's refused tunnel (BRIEFING §8,
  `common.is_transient`), and never the tar's timeout, which at 600 s would
  run a second try past forecast.yml's 15 minutes. KNZY, CO-OPS, NDBC's
  spectra and the b-decks are NOT retried: each collection re-reads a
  trailing window (6 h, 24 h, 45 days, the whole file), so a miss is filled
  ten minutes later; NDBC's standard met and the GFS/GEFS bulletins keep
  their own older retries.
- **The production workflows run on plain Python, and a test holds them to
  it.** collect-beach-inputs.yml, forecast.yml and every job that installs
  nothing run their `python -m` modules on the runner's bare interpreter;
  numpy, contourpy and shapely exist only in the precompute jobs and the test
  job. On 2026-11-12 (#218) forecast.mapdata imported a helper from
  seabedvector, which loads numpy, from inside a function: the tests passed
  (they have numpy), every publish failed for two hours, and every LIVE card
  went overdue. `tests/test_workflow_runtime.py` walks every import a
  bare-Python workflow module can reach, function-level ones included, and
  fails on any third-party one not in `ALLOWED` (each with its reason), and
  runs the collection's publish under `python -S`, with no site-packages.
  **A run that did not publish is red**: the collection's publish step is not
  continue-on-error, as the forecast job's never was. Every step before it is
  isolated ON PURPOSE (one source's outage must not cost another's data, and
  the archive is committed first), but the publish is the last step and
  nothing expected fails there. That two hours stayed green; the overdue cards
  were the only sign. And `forecast.now`'s exit 1 for a dark 46232 no longer
  skips the rest of its step (the measured hours, the wind and tide charts,
  Origins), which `set -e` did.
- **A queued run of a single-writer job must start from the branch's tip.**
  `actions/checkout` checks out the TRIGGERING commit; series-archive.yml's
  runs queue behind each other, so a queued one rebuilt on a base from before
  the run ahead pushed, and its rebase conflicted on that run's rebuild of the
  same file (3 of 25 runs, 10-12 Nov). It checks out `github.ref_name`.
- **A rejected push of an append-only log re-appends; it never rebases.**
  Measured 2026-09-26: the forecast build and the shown-hours seed both
  appended to one JSONL, the rebase conflicted, and the old retry loop
  (`git pull --rebase ... || true`) pushed an unchanged HEAD, read
  "Everything up-to-date" as success and lost the build's rows. `forecast.yml`
  and `seed-shown.yml` now reset to the new tip and re-run their idempotent
  append; `model-bias.yml` aborts loudly. The same `|| true` loop is still in
  the collectors' workflows, where each file has a single writer.
- **`data/series/` is derived and tracked, and that is not a breach either.**
  The chart's zoomed-out views need every archived hour through today's chain;
  at 0.18 s an hour a year is ~26 minutes, so a collection cannot rebuild it
  and the page cannot wait for it. `series-archive.yml` rebuilds it whole
  (35 s for 1,309 hours on four workers, measured 2026-09-27; a year is about
  five minutes) daily, on chain changes, and when asked. Deterministic, so an
  unchanged chain commits only new hours: ~0.9 MB a year. It is never mixed
  with another chain: every collection checks it against the week it has just
  rebuilt plus eight older hours, and on disagreement `series_all.json`
  carries no hours, the page says the earlier hours are being rebuilt, and the
  collection dispatches the rebuild. A stored gap that has since landed is the
  archive behind, not the chain moved, and does not count.
- **`data/live/` is gitignored, and that is not a breach of "data is tracked".**
  That rule guards the irreplaceable NDBC archive and the collected series; a
  forecast rebuilt every cycle from committed inputs is neither, and the public
  delivery repository's history is already the record of what was shown.
  Committing it cost ~460 MB of git objects a year (BRIEFING §15).
- **A total is not a validation of a mapping.** The WW3 direction axis descends;
  reading it as ascending scrambled which heading each energy bin sat at and
  still integrated to exactly the right Hs. Only a *located* quantity — the
  spectral peak, against the bulletin's dominant partition — caught it.
  BRIEFING §15.
- **A test that measures the archive grows with it, so it must never be
  quadratic in it.** Measured 2026-10-12: the suite took 347 s, 285 s of it in
  30 tests, and the two worst scanned a whole series once per sample — the
  tide-direction pin (85 s → 0.09 s by bisection) and `tidesite.measure`
  (20 s → 0.5 s, `interpolate` rebuilt its stamps every call). Both gave
  identical results after the fix. `tests/conftest.py` reads the ensemble
  archive once a session rather than once per `live.build`, and `tests.yml`
  runs on every core (`-n auto`): 49 s on four. Check `--durations` before
  adding a test that reads `data/`.
- Before writing an "archive it now, history is unrecoverable" job, **check
  whether the history is actually unrecoverable.** It was for Open-Meteo. It was
  not for GFS-Wave, whose every cycle since 2021-03 sits in the NOAA Open Data
  bucket — which turned a six-month wait into an afternoon.
