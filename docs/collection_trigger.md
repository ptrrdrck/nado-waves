# Driving the collector from outside GitHub

`collect-beach-inputs` is what makes the Now tab current. It fetches the
directional spectra at 46232, the METAR at KNZY and the water level at 9410170,
rebuilds `now.json`, and publishes it with the page.

Its cron is a floor, not a plan. This file is the plan.

## The measurement that forced this

GitHub delays and drops scheduled workflow runs. That is documented. What is
not documented is how hard, so it was measured on this repository across four
schedules:

| cron asks | delivered | rate |
|---|---|---|
| 0.21/h — `35 1,7,19` + `35 13,14` | 0.18/h | **84%** |
| 1.00/h — `45 * * * *` | 0.26/h | **26%** |
| 2.00/h — `5,35 * * * *` | 0.22/h | **11%** |
| 6.00/h — `*/10 * * * *` | 0.12/h | **2%** |

The delivered rate barely moves across a **29× range** in what is requested,
and `*/10` came out *lower per hour* than hourly did. The ceiling is roughly
**one run every four hours**, and asking harder is throttled harder.

Two consequences:

- **Frequency is not a lever.** An earlier change raised the cron to `*/10` on
  the theory that more scheduled slots would mean more landed runs. It produced
  one scheduled run in the five hours after it merged.
- The cron is kept at hourly because it delivered marginally the best absolute
  rate of the four, and because `COLLECT_INTERVAL_MIN` in `forecast/now.py`
  must match whatever it says. A test enforces that.

## Why not keep it inside Actions

Two in-GitHub designs were considered and rejected on cost.

**A long-running job that loops**, and **a chain where each run dispatches the
next**, both need spacing between fetches. Actions has no "run again in N
minutes" primitive, so the only way to wait is a job that sleeps — and a
sleeping job holds a runner for the whole gap.

The arithmetic is the same either way:

| spacing | runs/day | runner held each | total |
|---|---|---|---|
| 10 min | 144 | ~10 min | **~24 h/day** |
| 60 min | 24 | ~60 min | **~24 h/day** |

That is an always-on server wearing a workflow's clothes, on free public-repo
runners, forever. Driven from outside, each run is the ~25 seconds it already
takes: about **ten runner-minutes a day** for hourly collection, roughly 140×
less.

A `repository_dispatch` is an API call rather than a scheduled event, so it is
not subject to the throttle in the table above.

## The request

```
POST https://api.github.com/repos/ptrrdrck/nado-waves/dispatches

Accept:        application/vnd.github+json
Authorization: Bearer <TOKEN>
Content-Type:  application/json

{"event_type": "collect"}
```

A success is **HTTP 204** with an empty body. Anything else is a failure, and
the code says which kind:

| code | means | fix |
|---|---|---|
| **204** | fired | — |
| **401** | GitHub got **no usable credentials**. The `Authorization` header did not arrive, or the token is expired or malformed. | Check the header is actually being sent, as one header named `Authorization` with the value `Bearer <token>` |
| **404** | credentials were fine, but that token **cannot see this repository**. GitHub hides repositories a token cannot reach rather than admitting they exist. | Widen the token's repository access, or add Contents: write |
| **415** | the body was sent without `Content-Type: application/json` | Add that header |
| **422** | the JSON parsed but `event_type` is missing or wrong | It must be exactly `collect` |

The 401/404 split is the one worth internalising: **401 is "who are you",
404 is "you may not know".** A scheduler that only checks for 2xx reports
either as healthy while collection silently falls back to the throttled cron.

All three headers are required. `Content-Type` in particular is easy to leave
off, because many HTTP clients default a request body to
`application/x-www-form-urlencoded` and the call fails with 415 rather than
anything mentioning authentication.

As curl:

```sh
curl -sS -o /dev/null -w '%{http_code}\n' \
  -X POST https://api.github.com/repos/ptrrdrck/nado-waves/dispatches \
  -H 'Accept: application/vnd.github+json' \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{"event_type":"collect"}'
```

`event_type` must be `collect`. The workflow listens for that one name and
ignores every other dispatch, so other automation can share the endpoint
without starting a collection.

## Setting it up on cron-job.org

The failure you will hit first is **401**, and it is almost always the header
not arriving rather than the token being wrong. Things to check, in order:

1. **Request method is POST.** A GET to this endpoint cannot work.
2. **The header is in the headers list, split correctly.** cron-job.org takes a
   key and a value as separate fields. The key is `Authorization` with no
   colon; the value is `Bearer ghp_...` including the word `Bearer` and the
   space. Pasting the whole line into the key field is the usual mistake and
   produces exactly this 401.
3. **`Content-Type: application/json` is present** as a second header.
4. **`Accept: application/vnd.github+json`** as a third. Optional in practice,
   but it pins the API version.
5. **The body is `{"event_type":"collect"}`** in the request-body field, not in
   the URL.
6. **Save the job before using Test run.** A test run executes the saved
   configuration, so headers typed but not saved are not sent — which looks
   identical to headers configured wrongly.

A green test run shows **204** and an empty response body. If it shows 200 with
HTML, the URL is wrong.

## The token

A **fine-grained** personal access token:

| field | value |
|---|---|
| Resource owner | `ptrrdrck` |
| Repository access | **Only select repositories** → `nado-waves` |
| Permissions → Repository → **Contents** | **Read and write** |

Contents write is what `repository_dispatch` requires. Nothing else needs
granting — not Actions, not Workflows.

**This token lives outside GitHub**, on whichever scheduler runs it. Scoped to
one repository with one permission, the blast radius is writing to this
repository, which is recoverable from history. It is still a real key in a
third party's hands, so:

- set an expiry and put the date somewhere you will see it;
- when it expires the dispatch starts returning **401** and collection silently
  falls back to the throttled cron — the Now cards will go red, which is the
  point of them, but nothing will say why.

## Choosing a cadence

**Every ten minutes, at `5,15,25,35,45,55`.**

The offset is the interesting half, and it is not chosen for the swell.

### When the spectra actually appear

The timestamp a spectrum carries is its hour. When it becomes *fetchable* is a
different number, and it was measured on 2026-09-25 by bracketing each hour
between the last collection that did not have it and the first that did:

| spectrum hour | not there at | there at |
|---|---|---|
| 09-25 01Z | H+0.5 | H+15.0 |
| 09-24 23Z | H+16.7 | H+27.0 |
| 09-24 22Z | H+7.0 | H+76.7 |

23Z was **still absent at H+16.7** while 01Z had **already landed by H+15.0**.
Those two cannot both be true of a fixed publication minute, so there is not
one: it jitters across roughly **H+7 to H+27**.

### Which is why the phase is spent elsewhere

Aligning the trigger to a single minute would be early on some hours and twenty
minutes late on others. Against a jittering source, **only the interval bounds
staleness** — a ten-minute cadence catches the spectrum within ten minutes
wherever in its window it lands, whatever the offset.

So the offset goes to the one source that *is* pinned. KNZY publishes its
routine METAR at **:52** — 81 of 95 archived observations sit on that minute —
and the `:55` run catches it three minutes later. That is against a measured
median wind latency of **110 minutes** before any of this.

| source | stamps | fetchable, typical | fetchable, worst seen | wait for a collection |
|---|---|---|---|---|
| wind | `:52`, pinned | H+3 | H+3.2 | **3 min** |
| swell | `:00` | H+15 | H+35.3 | **10 min** |
| tide | every 6 min | H+5 | H+13.4 | **10 min** |

The middle columns are the ones that are easy to skip, and skipping them is what
made the tide card read overdue on a reading eight minutes old. **A stamp minute
is not a publication minute.** Every row was bracketed the same way — between
the last collection that did not have a sample and the first that did — and no
source in this table has ever been fetchable at its own stamp.

There are two columns rather than one because **the lag is a distribution, and a
single number cannot both promise and accuse.** The swell is the case that
proves it. Bracketed against the collection log on 2026-09-25:

| spectrum | absent at | present by |
|---|---|---|
| 09-24 23Z | H+16.4 | H+27.0 |
| 09-25 01Z | H+0.2 | **H+15.0** |
| 09-25 02Z | H+25.1 | **H+35.3** |
| 09-25 03Z | H+5.1 | H+15.3 |
| 09-25 04Z | H+10.9 | H+15.3 |
| 09-25 05Z | H+5.1 | H+15.3 |

Four of six land by H+15 — three consecutive hours on the very same collection —
and `02Z` did not appear until H+35.3. A single value had to sit at one end or
the other. It sat at 27: above the typical and below the worst, so it was
twelve minutes pessimistic on the common hour *and* would still have gone red on
`02Z`. On an hourly source that meant promising **100 minutes from stamp to
screen where 80 was honest** — a countdown a reader learns to discount, which is
no better than one that cries wolf.

So `forecast/now.py` carries both: `PUBLISH_LAG_MIN` (typical) is what the
countdown runs to, and `PUBLISH_LAG_LATE_MIN` (worst seen) is the only thing
that turns a card red. Between them the card says the update is due and does not
accuse anyone. A test holds the typical value against `first_seen_utc` in the
archive — a source the data has never seen inside a minute of its stamp may not
be modelled as instant — and another holds `late >= expected` for every stamp
minute, since a card reddening before its own countdown expired would be
accusing a source of missing a deadline it had not reached.

The spectra files carry no `first_seen_utc`, so their bracketing uses git
history instead: each collection commits the file, so the commit time *is* when
that row first existed here.

### What it costs

144 runs a day at roughly 20 seconds each — about **48 minutes of runner time a
day**, against 5,000 API calls an hour of headroom and 144 used. The real cost
is commits: the tide moves every run, so this is ~144 commits a day against 24
at hourly. Worth knowing before going finer still; it is the reason the tide is
not collected at its own six-minute cadence.

## Keeping the two numbers together

`COLLECT_INTERVAL_MIN` in `forecast/now.py` feeds every card's countdown, and it
must equal what this scheduler actually runs. If the page promises a cadence
the trigger is not keeping, the cards report the gap between the request and
reality rather than anything about the data — which is exactly what happened
when a `*/10` cron met GitHub's one-run-every-four-hours.

`forecast/now.py` therefore declares **`EXTERNAL_TRIGGER_CRON`**, and three
tests hold the pieces together:

- `COLLECT_INTERVAL_MIN` must match the spacing `EXTERNAL_TRIGGER_CRON` implies,
  and that schedule must be evenly spaced;
- the GitHub cron must stay an hourly **backstop**, never written to match the
  promised cadence — GitHub cannot keep it;
- the last run of each hour must land after `:52` and within five minutes of it,
  so the wind offset cannot be lost by accident.

**Nothing in this repository can reach cron-job.org.** If you change the
interval there, change `EXTERNAL_TRIGGER_CRON` to match in the same sitting —
the tests will then carry the rest. That one step is a human obligation and the
only part of this with no safety net.

## What stays as it is

- **The cron remains**, at hourly, as a backstop. If the external trigger dies,
  collection degrades to the throttled rate rather than stopping.
- **`workflow_dispatch` remains**, for running it by hand from the Actions tab.
- **`concurrency: beach-inputs`** already serialises runs, so a dispatch that
  arrives mid-run queues rather than racing the git push.
- **Nothing depends on the dispatch.** Until something starts calling, the
  trigger is inert and the repository behaves exactly as it did before.

## Checking it works

After pointing a scheduler at it:

1. The Actions tab should show runs with the event **`repository_dispatch`**
   rather than `schedule`.
2. `data/wind/KNZY.csv` — the newest row's `first_seen_utc` should track the
   trigger's cadence rather than lagging hours behind `observed_utc`.
3. The Now cards should spend most of their time counting down rather than
   showing red.

The third is the one that matters, and it is the only one a reader ever sees.
