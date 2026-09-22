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

A success is **HTTP 204** with an empty body. Anything else is a failure worth
seeing — in particular `404` means the token cannot reach the repository, which
is what an expired or under-scoped token looks like from here. GitHub does not
return `401` for that case, so a scheduler that only checks for 2xx will report
a dead trigger as healthy.

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
- when it expires the dispatch starts returning `404` and collection silently
  falls back to the throttled cron — the Now cards will go red, which is the
  point of them, but nothing will say why.

## Choosing a cadence

Hourly is enough. The sources are hourly (spectra, METAR) and six-minutely
(tide), and the tide moves a median 1.1 cm per step, so finer collection buys a
sharper number nobody can read at the cost of more commits.

**If you change the cadence, change `COLLECT_INTERVAL_MIN` in
`forecast/now.py` to match.** The countdown on each card is
`observed + source interval + collection interval + one tolerated missed
cycle`, so a page promising a cadence the trigger is not keeping will call
itself late on a schedule nobody asked it to keep. That exact mismatch shipped
once. `tests/test_now.py` reads the cron out of the workflow and fails if the
two disagree — but it cannot see an external scheduler, so this one is on you.

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
