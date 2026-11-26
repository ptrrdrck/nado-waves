// The Observe service against the contract in docs/design/observe.md, run on
// node:sqlite through a D1-shaped adapter: `node --test service/observe/test/`.
// The refusals matter most: a wrong code, a guess past the limit, a row that
// names its own observer, a word the series does not hold.
import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";

import {handle, codeOf, LIMITS, MAX_ROWS, isoSec} from "../src/observe.js";
import worker from "../src/worker.js";
import VOCAB from "../src/vocab.js";
import {fakeD1} from "./d1.js";

const NOW = Date.UTC(2026, 10, 26, 18, 0, 0);
const TOKEN = "t".repeat(40);
const CODES = JSON.stringify({"Heron Jetty 27": "o01", "orange-glorietta-1121": "o02"});

function env(extra = {}) {
  return {DB: fakeD1(), CODES, PULL_TOKEN: TOKEN, ...extra};
}

function post(path, body, ip = "198.51.100.7") {
  return new Request(`https://svc.example${path}`, {
    method: "POST",
    headers: {"Content-Type": "text/plain;charset=UTF-8", "CF-Connecting-IP": ip},
    body: typeof body === "string" ? body : JSON.stringify(body),
  });
}

function pull(since, token = TOKEN, ip = "203.0.113.9") {
  const q = since ? `?since=${encodeURIComponent(since)}` : "";
  return new Request(`https://svc.example/pull${q}`, {
    headers: {...(token == null ? {} : {Authorization: `Bearer ${token}`}), "CF-Connecting-IP": ip},
  });
}

function row(over = {}) {
  return {
    entry_id: "3f2b6c1e-0b7a-4d4e-9a35-1c2d3e4f5a6b",
    observed_utc: isoSec(NOW - 30 * 60e3),
    logged_utc: isoSec(NOW - 25 * 60e3),
    break_id: "coronado_center",
    shape: "sections",
    surface: "glassy",
    power: "punchy",
    entered_on: "forecast_page",
    is_test: "true",
    ...over,
  };
}

async function call(e, req, now = NOW) {
  const res = await handle(req, e, now);
  const text = await res.text();
  return {status: res.status, headers: res.headers, json: text ? JSON.parse(text) : null};
}

// ---- the code -------------------------------------------------------------

test("codeOf is the page's codeOf, on every input the phone can produce", () => {
  const page = readFileSync(new URL("../../../app/forecast.html", import.meta.url), "utf8");
  const m = /const codeOf = (\(typed\) =>[\s\S]*?join\("-"\));/.exec(page);
  assert.ok(m, "codeOf not found in app/forecast.html");
  const pageCodeOf = (0, eval)(m[1]);
  const inputs = ["Heron Jetty 27", "  heron-jetty-27 ", "HERON_JETTY.27", "heron–jetty—27",
    "heron‐jetty― 27", "heron  --  jetty 27", "", null, undefined, "héron jetty 27",
    "heron\tjetty\n27", "a.b_c-d e"];
  for (const s of inputs) assert.equal(codeOf(s), pageCodeOf(s), JSON.stringify(s));
  assert.equal(codeOf("Heron Jetty 27"), "heron-jetty-27");
});

test("/code: a live code is taken whatever the typing; a wrong one is not", async () => {
  const e = env();
  assert.deepEqual((await call(e, post("/code", {code: "heron-jetty-27"}))).json, {ok: true});
  assert.deepEqual((await call(e, post("/code", {code: "HERON jetty_27"}))).json, {ok: true});
  // The secret's own key is normalised too: "Heron Jetty 27" was written with capitals.
  assert.deepEqual((await call(e, post("/code", {code: "heron-jetty-28"}))).json, {ok: false});
  assert.deepEqual((await call(e, post("/code", {}))).json, {ok: false});
});

test("/code: past the limit every answer is 429, the live code's too, so 429 leaks nothing", async () => {
  const e = env();
  for (let i = 0; i < LIMITS.client.tries; i++) {
    const got = await call(e, post("/code", {code: `wrong-${i}`}));
    assert.equal(got.status, 200);
    assert.equal(got.json.ok, false);
  }
  assert.equal((await call(e, post("/code", {code: "heron-jetty-27"}))).status, 429);
  // Another client is not held up by this one.
  assert.deepEqual((await call(e, post("/code", {code: "heron-jetty-27"}, "192.0.2.1"))).json, {ok: true});
  // The window passes.
  const later = NOW + (LIMITS.client.seconds + 1) * 1000;
  assert.deepEqual((await call(e, post("/code", {code: "heron-jetty-27"}), later)).json, {ok: true});
});

test("/code: many clients together hit the global limit", async () => {
  const e = env();
  for (let i = 0; i < LIMITS.global.tries; i++) {
    await call(e, post("/code", {code: "wrong"}, `10.0.${Math.floor(i / 200)}.${i % 200}`));
  }
  assert.equal((await call(e, post("/code", {code: "heron-jetty-27"}, "192.0.2.99"))).status, 429);
  const later = NOW + (LIMITS.global.seconds + 1) * 1000;
  assert.deepEqual((await call(e, post("/code", {code: "heron-jetty-27"}, "192.0.2.99"), later)).json, {ok: true});
  // Pruned: nothing older than the longest window is kept.
  await call(e, post("/code", {code: "wrong"}), later);
  assert.equal(e.DB.raw.prepare("SELECT COUNT(*) AS n FROM tries").get().n, 1);
});

test("CORS: the page's origin, no preflight needed, and OPTIONS answered anyway", async () => {
  const e = env();
  const got = await call(e, post("/code", {code: "x"}));
  assert.equal(got.headers.get("Access-Control-Allow-Origin"), "https://ptrrdrck.github.io");
  assert.equal(got.headers.get("Cache-Control"), "no-store");
  const pre = await handle(new Request("https://svc.example/ratings", {method: "OPTIONS"}), e, NOW);
  assert.equal(pre.status, 204);
  assert.equal(pre.headers.get("Access-Control-Allow-Origin"), "https://ptrrdrck.github.io");
});

// ---- ratings --------------------------------------------------------------

test("/ratings: a wrong code is 401 and counts as a try", async () => {
  const e = env();
  for (let i = 0; i < LIMITS.client.tries; i++) {
    assert.equal((await call(e, post("/ratings", {code: `nope-${i}`, rows: [row()]}))).status, 401);
  }
  assert.equal((await call(e, post("/ratings", {code: "heron-jetty-27", rows: [row()]}))).status, 429);
  assert.equal(e.DB.raw.prepare("SELECT COUNT(*) AS n FROM ratings").get().n, 0);
});

test("/ratings: the observer is the code's and the arrival is ours, whatever the row says", async () => {
  const e = env();
  const sent = row({observer_id: "someone-else", received_utc: "2001-01-01T00:00:00Z", extra: "x"});
  const got = await call(e, post("/ratings", {code: "Orange Glorietta 1121", rows: [sent]}));
  assert.equal(got.status, 200);
  assert.deepEqual(got.json, {accepted: [sent.entry_id], refused: []});
  const stored = e.DB.raw.prepare("SELECT * FROM ratings").all();
  assert.equal(stored.length, 1);
  assert.equal(stored[0].observer_id, "o02");
  assert.equal(stored[0].received_utc, isoSec(NOW));
  assert.deepEqual(Object.keys(stored[0]), VOCAB.columns);
});

test("/ratings: a batch sent twice is taken once and reported accepted both times", async () => {
  const e = env();
  const rows = [row(), row({entry_id: "second-1", break_id: "coronado_north"})];
  const a = await call(e, post("/ratings", {code: "heron-jetty-27", rows}));
  const b = await call(e, post("/ratings", {code: "heron-jetty-27", rows}), NOW + 60e3);
  assert.deepEqual(a.json.accepted, b.json.accepted);
  const stored = e.DB.raw.prepare("SELECT entry_id, received_utc FROM ratings ORDER BY entry_id").all();
  assert.equal(stored.length, 2);
  // The first arrival is the one kept.
  assert.ok(stored.every((r) => r.received_utc === isoSec(NOW)));
});

test("/ratings: refused, never coerced, each with its reason, the rest still taken", async () => {
  const e = env();
  const bad = {
    "w-shape": row({entry_id: "w-shape", shape: "clean"}),
    "w-missing": row({entry_id: "w-missing", power: undefined}),
    "w-flat": row({entry_id: "w-flat", surface: "flat"}),
    "w-break": row({entry_id: "w-break", break_id: "ocean_beach"}),
    "w-test": row({entry_id: "w-test", is_test: ""}),
    "w-test2": row({entry_id: "w-test2", is_test: "yes"}),
    "w-order": row({entry_id: "w-order", observed_utc: isoSec(NOW), logged_utc: isoSec(NOW - 60e3)}),
    "w-future": row({entry_id: "w-future", observed_utc: isoSec(NOW + 3600e3), logged_utc: isoSec(NOW + 3600e3)}),
    "w-date": row({entry_id: "w-date", observed_utc: "2026-02-30T10:00:00Z"}),
    "w-form": row({entry_id: "w-form", logged_utc: "2026-11-26 17:35:00"}),
    "w-entry id": row({entry_id: "w-entry id"}),
  };
  const good = row({entry_id: "fine", shape: " Corners ", is_test: false});
  const got = await call(e, post("/ratings", {code: "heron-jetty-27", rows: [...Object.values(bad), good, "nonsense"]}));
  assert.deepEqual(got.json.accepted, ["fine"]);
  const reasons = Object.fromEntries(got.json.refused.map((r) => [r.entry_id, r.reason]));
  for (const id of Object.keys(bad)) assert.ok(reasons[id], `${id} was not refused`);
  assert.match(reasons["w-shape"], /^shape:/);
  assert.match(reasons["w-flat"], /^surface:/);
  assert.match(reasons["w-test"], /^is_test:/);
  assert.match(reasons["w-future"], /future/);
  assert.ok(reasons["?"], "a non-object row is refused as ?");
  const stored = e.DB.raw.prepare("SELECT shape, is_test FROM ratings").all();
  assert.deepEqual(stored.map((r) => ({...r})), [{shape: "corners", is_test: "false"}]);
});

test("/ratings: a phone clock a few minutes fast is kept; the grace is ten minutes", async () => {
  const e = env();
  const at = isoSec(NOW + 5 * 60e3);
  const got = await call(e, post("/ratings", {code: "heron-jetty-27", rows: [row({observed_utc: at, logged_utc: at})]}));
  assert.equal(got.json.accepted.length, 1);
});

test("/ratings: the batch's own shape is checked", async () => {
  const e = env();
  const many = Array.from({length: MAX_ROWS + 1}, (_, i) => row({entry_id: `r${i}`}));
  assert.equal((await call(e, post("/ratings", {code: "heron-jetty-27", rows: many}))).status, 400);
  assert.equal((await call(e, post("/ratings", {code: "heron-jetty-27", rows: []}))).status, 400);
  assert.equal((await call(e, post("/ratings", {code: "heron-jetty-27"}))).status, 400);
  assert.equal((await call(e, post("/ratings", "{not json"))).status, 400);
  assert.equal((await call(e, post("/ratings", "x".repeat(70000)))).status, 413);
});

// ---- the pull -------------------------------------------------------------

test("/pull: only with the token; every row since, oldest first; nothing marked or deleted", async () => {
  const e = env();
  await call(e, post("/ratings", {code: "heron-jetty-27", rows: [row({entry_id: "a",
    observed_utc: isoSec(NOW - 7200e3), logged_utc: isoSec(NOW - 7000e3)})]}), NOW - 3600e3);
  await call(e, post("/ratings", {code: "heron-jetty-27", rows: [row({entry_id: "b"})]}), NOW);
  assert.equal((await call(e, pull(null, null))).status, 401);
  assert.equal((await call(e, pull(null, "wrong"))).status, 401);
  assert.equal((await call(e, pull(null, TOKEN.slice(0, -1) + "u"))).status, 401);
  const all = await call(e, pull(null));
  assert.equal(all.status, 200);
  assert.deepEqual(all.json.rows.map((r) => r.entry_id), ["a", "b"]);
  assert.deepEqual(Object.keys(all.json.rows[0]), VOCAB.columns);
  assert.equal(all.headers.get("Access-Control-Allow-Origin"), null);
  const since = await call(e, pull(isoSec(NOW - 60e3)));
  assert.deepEqual(since.json.rows.map((r) => r.entry_id), ["b"]);
  // Asking again returns the same rows: the pull never consumes.
  assert.deepEqual((await call(e, pull(null))).json.rows.length, 2);
  assert.equal((await call(e, pull("yesterday"))).status, 400);
});

test("/pull: wrong tokens count against the limit", async () => {
  const e = env();
  for (let i = 0; i < LIMITS.client.tries; i++) await call(e, pull(null, `guess-${i}`));
  assert.equal((await call(e, pull(null))).status, 429);
});

// ---- failing closed -------------------------------------------------------

test("a malformed CODES secret fails closed: 500, never ok", async () => {
  for (const bad of [undefined, "", "{", "[]", JSON.stringify({"a b 1": "Pete Smith"}),
    JSON.stringify({"a b 1": "o01", "A B 1": "o02"}), JSON.stringify({"  ": "o01"})]) {
    const e = env({CODES: bad});
    const got = await call(e, post("/code", {code: "a-b-1"}));
    assert.equal(got.status, 500, String(bad));
    assert.equal(got.json.ok, undefined);
    assert.equal(JSON.stringify(got.json).includes("Pete"), false);
  }
});

test("an unset or short PULL_TOKEN fails closed", async () => {
  assert.equal((await call(env({PULL_TOKEN: undefined}), pull(null, ""))).status, 500);
  assert.equal((await call(env({PULL_TOKEN: "short"}), pull(null, "short"))).status, 500);
});

test("methods and paths", async () => {
  const e = env();
  assert.equal((await call(e, new Request("https://svc.example/code"))).status, 405);
  assert.equal((await call(e, post("/pull", {}))).status, 405);
  assert.equal((await call(e, post("/elsewhere", {}))).status, 404);
  assert.equal((await call(e, post("/code/", {code: "heron-jetty-27"}))).json.ok, true);
});

test("the Worker's entry point hands requests to handle", async () => {
  const res = await worker.fetch(post("/code", {code: "heron-jetty-27"}), env());
  assert.deepEqual(await res.json(), {ok: true});
});
