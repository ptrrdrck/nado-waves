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

## The service (session 2; not built)

The page is built against this. The service holds the codes and takes the
ratings; it never holds write access to GitHub. An Actions job pulls the
ratings into this repository.

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

## Not yet

- The service and the pull (session 2).
- Showing a rating once there is enough logged (session 3, after data): the
  owner's goal. The plan put to the owner on 2026-11-26: nothing until there
  is data, a count beside anything shown, first each break's record across
  sessions, then shape conditioned on ONE measured variable (46232's
  direction, the tide or KNZY's wind, attached after the fact) at the beach
  log's floor of 20 per bin, shown only if it beats the unconditioned rate.
  A fourth level of evidence on the page, needing its own label.
- Heights through Observe, and the gate as blurred numbers.
