_Read before working on Observe: the footer's switch, observer codes, the rating rows on LIVE, the Observe service, or `data/beach_ratings/`._

# Observe

Observe is the forecast page gathering observations itself: an observer with a
code switches it on in the footer, and each LIVE break gains three rows of
chips that rate how the surf is breaking, whatever its size. It is meant to
grow, incrementally, into the way the log is gathered too, so the separate log
page is needed less and less (owner's direction, 2026-11-26).

## Decisions (owner's, 2026-11-26)

- **On the forecast page, not the log.** The owner's reasoning: judging how a
  wave breaks after seeing the forecast does not contaminate the judgement the
  way it would a height. The page forecasts neither shape nor power.
- **Three rows, three words each**, left to right as the series orders them:

  | row | words | order |
  |---|---|---|
  | Shape | Walled · Sections · Corners | worse to better (owner's words) |
  | Surface | Choppy · Textured · Glassy | worse to better ("choppy" includes blown out) |
  | Power | Mushy · Punchy · Hollow | soft to steep, **not** worse to better |

  Power is not a third score: a hollow close-out is the worst day there is.
  Any rating worked out from these later has to treat it on its own terms.
- **Access by code, no accounts.** One code per person, two words and a
  number, given out by the owner. Kept in the browser; easy to remember
  because it will sometimes need typing again (below).
- **The service checks codes (option B of two put to the owner).** The other
  option, the page checking codes itself and ratings handed back as text,
  could neither keep anyone out nor be quick.
- **The log-first gate is kept, switched off** (`GATE_ON = false`). It keeps
  the height log blind, and Observe does not gather heights yet. The gate it
  is meant to become: LIVE's numbers blurred until the observer logs or
  declines, inside the page rather than a link to the separate log.
- **The log form is left alone for now.**

## What the series is, and why it is not the log

`data/beach_ratings/ratings.csv`, written by `collector/beachratings.py`.

- **Its own series.** The log never shows a forecast; this page is one. The
  owner's call is recorded on every row as `entered_on = forecast_page`, not
  trusted silently: surface is the one quality the page does hint at, since
  each break's tab shows its offshore/onshore wind, and only the column lets
  that be asked of the series later.
- **All three words or no row**, and no flat (the log records flat).
- **The observer is the code's.** The page never names one; the service
  attaches `observer_id` from the code. Only the id is stored: this
  repository is public, and the names stay with the codes, in the service.
- **`is_test` is decided at entry** by the observer ("Test entry"), never
  read out of anything else.
- `observed_utc` (Now, or a time today on Coronado's clock), `logged_utc`
  (the phone at Save), `received_utc` (the service, on arrival). A large gap
  between the last two is a rating queued without signal, not a fault.
- Refused, never coerced; import idempotent on `entry_id` and append-only.

## The page

- **The switch** is the footer's old "Observer", now "Observe". It stays off
  the page until `OBSERVE_SERVICE` is set, so no switch leads to a code nobody
  can check. Tapped with no code on the device, it opens a field under the
  foot's line (no dialog; 16 px text, or iPhone zooms). The switch moves only
  when the service has said yes; after that a tap turns the UI on and off and
  the code is not asked for again.
- **Codes are never checked or listed by the page.** It is public; a list,
  even hashed, is readable, and two words and a number fall to a guess in
  seconds without the service's limit on tries. Typing is forgiven, the
  code is not: case, spaces, underscores, dots and dashes are normalised
  (`codeOf`: "Heron Jetty 27" is `heron-jetty-27`). **The service must
  normalise the same way.**
- **`?observe=`** points the page at another service only when it is served
  from this machine (localhost, 127.0.0.1, a file). On the public page a
  crafted link could otherwise send an observer's stored code anywhere.
- **Why the code needs remembering:** Safari on iPhone can clear a site's
  stored data after about a week of use without a visit, so the code will
  occasionally need typing again.
- **The rows** sit in each break's LIVE pane under its numbers, above the
  map (`breakPanel`), on the phone's tabs and in the wide layouts' columns
  alike. When: Now, or Earlier with a time today on Coronado's clock. Save
  is enabled once all three rows are chosen. A second tap takes a word back.
- **The minute's redraw** rebuilds the panel from a draft held in memory per
  break, so a half-made rating survives it, and it does not run while the
  time field has focus (`rateTyping`), which would take the field and
  iPhone's wheel with it. A tap repaints the panel in place, not the page.
- **The phone's queue.** A rating is written to localStorage first, always,
  and leaves only on the service's answer, row by row by `entry_id`; a row
  the service refuses leaves with its reason shown, since resending cannot
  change the answer. A refused code switches Observe off and asks again,
  keeping the queue. Sends on Save, on load, on coming back online and on
  the page becoming visible.

Measured, 2026-11-26 (Chromium, against a stub service): a wrong code
refused, a right one taken with other case and spacing, three panels shown,
a draft kept across `show()`, a test row sent with `is_test = true`, an
Earlier row offline queued then sent, the rows passing
`collector.beachratings.validate`; at 320, 390, 768, 1024 and 1440 px no
page overflow, no clipped chip, the footer on one line, the code field
directly under the footer (in the rail on the console layout).

## The service (built 2026-11-26, handoff item 28)

`service/observe/`: a Cloudflare Worker with a D1 (SQLite) database, on the
free plan (owner's choice of host, 2026-11-26: no cold start on a beach's
signal, secrets kept encrypted, storage included). The owner deploys it by
hand with `wrangler`; no Cloudflare token sits in GitHub, because whoever
holds one could deploy a worker that reads the codes. The service holds the
codes and takes the ratings; it never holds write access to GitHub. An
Actions job pulls the ratings into this repository.

The contract the page was built against:

Every page request is a POST with `Content-Type: text/plain` and a JSON body.
A text/plain request needs no CORS preflight, which saves a round trip on a
weak signal. The service sets
`Access-Control-Allow-Origin: https://ptrrdrck.github.io` and must not
require a preflight.

- `POST /code` `{code}` → `200 {"ok": true}` if the code is live, `200
  {"ok": false}` if not; `429` when tries from that client are over the
  limit. The page stores the code only on `ok: true`.
- `POST /ratings` `{code, rows: [...]}` (at most 50 rows) → `200 {"accepted":
  [entry_id, ...], "refused": [{"entry_id", "reason"}, ...]}`; `401`/`403`
  when the code is not live. Idempotent on `entry_id`: a row already held is
  reported accepted. The service stamps `observer_id` (from the code) and
  `received_utc`, and should apply `collector.beachratings`' vocabulary so a
  bad row is refused at the door, not at the pull.
- **The pull** (Actions, a read secret, never the page): returns rows not yet
  pulled; the job hands them to `collector.beachratings.import_rows`, which
  skips what it holds and refuses what does not validate. One job writes the
  file (single writer, append-only; a rejected push re-appends, never
  rebases).
- **Codes** live in the service's secrets as a map of code to `observer_id`.
  Revoking one person is deleting one entry. Codes are generated and given
  out by the owner; they go in no file in either repository.

How it is built, and why:

- **`src/observe.js`** holds all of it; `src/worker.js` only hands it the
  request, so `test/` runs the same code on `node:sqlite` through a D1-shaped
  adapter (`node --test service/observe/test/*.test.js`, a step of the Tests
  workflow). Checked 2026-11-26 in `wrangler dev` (workerd, local D1) too: a
  code taken with other typing, a wrong one not, a row refused with its
  reason, the eleventh wrong try a 429, and the pull's rows through
  `import_rows` added once and skipped the second time.
- **The vocabulary is generated** (`src/vocab.js`, `python -m
  collector.beachratings vocab`): words, breaks and columns from
  `beachratings.py` and `spots.json`, and `tests/test_observe_service.py`
  fails when it drifts. The service is stricter only where the page never
  differs (an `entry_id` of letters, digits, `-` and `_`; the stamp's exact
  form, and no 30 February); anything it takes, `validate` takes.
  `import_rows` checks every row again at the pull: the service is not the
  series' authority.
- **`codeOf` is the page's**, and a node test runs the page's own function
  (read out of `app/forecast.html`) and the worker's on one list of inputs.
  The keys of `CODES` are normalised the same way, so a key written "Heron
  Jetty 27" still matches.
- **The limit on tries has two halves** (`LIMITS`): ten wrong tries in
  fifteen minutes from one client, then 429; two hundred in an hour across
  every client, then 429 for everyone. It is checked before the code is
  looked at, so a 429 says nothing about a code. A wrong code on `/ratings`
  and a wrong token on `/pull` count too: otherwise each would be a way round
  `/code`'s limit. Under the global lockout a stored code waits as well; the
  phone keeps its queue and sends later, so nothing is lost. The table of
  tries holds client addresses for an hour at most, pruned on every wrong try.
- **Fails closed.** A `CODES` that is not a JSON object of code to short
  lowercase id (`o01`; a name is refused, since the id lands in this public
  repository), two keys that normalise to one code, or a `PULL_TOKEN` under
  32 characters: every request answers 500, never `ok`, and the error never
  echoes the secret.
- **The pull never consumes.** `GET /pull?since=` with `Authorization:
  Bearer` returns every row received at or after `since`, oldest first;
  nothing is marked or deleted. `collector/observepull.py` asks from the
  newest `received_utc` the file holds less two days, and `import_rows` skips
  the overlap by `entry_id`, so a run that fails after its pull loses nothing.
- **The pull's address is the page's.** `observepull` reads
  `OBSERVE_SERVICE` out of `app/forecast.html`, so the page and the pull
  cannot point at two services, and there is no second place to set it.
  While it is empty the pull has nothing to do and exits green.
- **`observe-pull.yml`** is the file's one writer: hourly as a backstop
  (about one run in five hours is delivered, and nothing reads the ratings
  yet), and by hand. A rejected push resets to the new tip and pulls again;
  it never rebases. A row refused at import turns the run red after the rows
  taken are committed: the service and the validator disagreeing must be
  seen.

### Codes

`python3 service/observe/newcode.py o01 o02 …` prints a fresh code for each
observer id and the whole `CODES` secret as JSON, to the terminal only; it
writes no file. A code is two different Coronado streets and a house number,
e.g. `glorietta-adella-1121` (owner's idea, 2026-11-26), all chosen by
Python's `secrets`. The street list, `streets.txt`, is public, and that is
fine: the strength is the random choice, not the list. The number has four
digits while that gives at least 2^24 codes and five when the list is too
short; below that even with five, the script refuses. With 56 streets it is
27.7 million codes (24.7 bits): at the global limit of 200 wrong tries an
hour, about sixteen years to try them all. **The list was written from memory and is
unchecked**: the owner prunes it, and the script says how strong a code from
what is left is.

### Setting it up (the owner, once)

On a computer with Node 20 or later, from a checkout of this repository:

1. Create a Cloudflare account (free plan) and choose its `workers.dev`
   subdomain when asked.
2. `cd service/observe`, then `npx wrangler@4.160.1 login`.
3. `npx wrangler@4.160.1 d1 create nado-observe`. Copy the `database_id` it
   prints into `wrangler.toml` in place of `PASTE-THE-ID-FROM-d1-create` (an
   identifier, not a credential; it can be committed).
4. `npx wrangler@4.160.1 d1 execute nado-observe --remote --file=schema.sql`
5. Codes: `python3 newcode.py o01 o02 …` (one id per person). Keep the
   printed JSON and who has which code in a password manager, which is the
   only copy outside the service. Then `npx wrangler@4.160.1 secret put
   CODES` and paste the JSON at its prompt. The prompt keeps it out of the
   shell's history; never pass it as an argument.
6. The pull token: `python3 -c "import secrets; print(secrets.token_hex(32))"`.
   Paste it at `npx wrangler@4.160.1 secret put PULL_TOKEN`, and the same
   value into GitHub: this repository → Settings → Secrets and variables →
   Actions → New repository secret, named `OBSERVE_PULL_TOKEN`. Keep it in
   no file.
7. `npx wrangler@4.160.1 deploy`. It prints the address,
   `https://nado-observe.<subdomain>.workers.dev`.
8. Check: `curl -X POST https://…/code -d '{"code":"nope-nope-1"}'` answers
   `{"ok":false}`, and the same with a real code answers `{"ok":true}`.
9. That address goes into `OBSERVE_SERVICE` in `app/forecast.html` (a
   commit). It is not secret: the page is public and shows it.

Adding a person: run `newcode.py` with just the new id, add the pair to the
map in the password manager, and `secret put CODES` the whole map again.
Revoking: delete their entry and put the map again. Their ratings stay in the
series, under their id. A new token: put it in both places.

## Not yet

- One rehearsal row end to end, once the service is deployed and
  `OBSERVE_SERVICE` is set (handoff item 28's last step).
- Showing a rating once there is enough logged (session 3, after data): the
  owner's goal. The plan put to the owner on 2026-11-26: nothing until there
  is data, a count beside anything shown, first each break's record across
  sessions, then shape conditioned on ONE measured variable (46232's
  direction, the tide or KNZY's wind, attached after the fact) at the beach
  log's floor of 20 per bin, shown only if it beats the unconditioned rate.
  A fourth level of evidence on the page, needing its own label.
- Heights through Observe, and the gate as blurred numbers.
