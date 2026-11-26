// The Observe service: checks observer codes and takes ratings
// (docs/design/observe.md, "The service"). Everything here is pure, given a
// D1-shaped database, so tests/ runs it against node:sqlite unchanged.
//
// It holds the codes and the ratings and nothing else. It never holds write
// access to GitHub: an Actions job pulls (collector/observepull.py).

import VOCAB from "./vocab.js";

// The page that may read our answers. CORS stops other pages READING a reply;
// it does not stop anyone sending, which is what the codes are for.
export const PAGE_ORIGIN = "https://ptrrdrck.github.io";

// A limit on wrong guesses, and why it has two halves. Per client: ten wrong
// tries in fifteen minutes, then 429. Across every client together: two
// hundred in an hour, then 429 for everyone, so many addresses cannot add up
// to a fast guess. The limit is checked before the code is looked at, so a
// 429 says nothing about whether a code is live. Under a global lockout a
// stored code waits too; the page keeps its ratings queued and sends later.
export const LIMITS = {
  client: {tries: 10, seconds: 15 * 60},
  global: {tries: 200, seconds: 60 * 60},
};

export const MAX_ROWS = 50;            // per /ratings call; the page sends 50 at most
export const MAX_BODY = 64 * 1024;     // 50 rows are under 15 KB
export const CLOCK_GRACE_S = 10 * 60;  // as collector.beachratings.validate

// What an observer types, as the page compares it (app/forecast.html codeOf):
// case, spaces, underscores, dots and dashes are the phone's, never the
// code's. "Heron Jetty 27" is heron-jetty-27. A test runs both on one list.
export const codeOf = (typed) => String(typed || "").trim().toLowerCase()
  .split(/[\s_.‐-―-]+/).filter(Boolean).join("-");

const OBSERVER_ID = /^[a-z0-9][a-z0-9_-]{0,23}$/;
const ENTRY_ID = /^[A-Za-z0-9_-]{1,64}$/;
const ISO = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})Z$/;

export class ConfigError extends Error {}

// CODES is a Worker secret: a JSON object of code to observer id, e.g.
// {"heron-jetty-27": "o01"}. Keys are normalised as typed codes are, so a
// key written with capitals or spaces still matches. Anything malformed fails
// closed: every check answers 500 until the secret is fixed.
let parsed = {raw: null, map: null};
export function codes(env) {
  const raw = env.CODES;
  if (parsed.raw === raw && parsed.map) return parsed.map;
  if (typeof raw !== "string" || !raw.trim()) throw new ConfigError("CODES is not set");
  let obj;
  try { obj = JSON.parse(raw); } catch (e) { throw new ConfigError("CODES is not JSON"); }
  if (!obj || typeof obj !== "object" || Array.isArray(obj)) throw new ConfigError("CODES is not an object");
  const map = new Map();
  for (const [key, id] of Object.entries(obj)) {
    const code = codeOf(key);
    if (!code) throw new ConfigError("CODES has an empty code");
    if (typeof id !== "string" || !OBSERVER_ID.test(id)) {
      throw new ConfigError("CODES has an observer id that is not a short lowercase id");
    }
    if (map.has(code)) throw new ConfigError("CODES has two keys that normalise to one code");
    map.set(code, id);
  }
  parsed = {raw, map};
  return map;
}

export const isoSec = (ms) => new Date(ms).toISOString().slice(0, 19) + "Z";

// The stamp collector.common.ISO writes, and nothing looser: a date that does
// not exist (02-30) is refused, not rolled over.
export function parseIso(value) {
  if (typeof value !== "string") return null;
  const m = ISO.exec(value);
  if (!m) return null;
  const [y, mo, d, h, mi, s] = m.slice(1).map(Number);
  const ms = Date.UTC(y, mo - 1, d, h, mi, s);
  return isoSec(ms) === value ? ms : null;
}

function word(row, name, allowed) {
  const value = row[name];
  if (typeof value !== "string") return [null, `${name}: missing`];
  const v = value.trim().toLowerCase();
  if (!allowed.includes(v)) return [null, `${name}: "${value.slice(0, 20)}" is not one of ${allowed.join(", ")}`];
  return [v, null];
}

// One row as the page sends it, checked as collector.beachratings.validate
// checks it, and stricter only where the page never differs (entry_id's
// characters, the stamp's exact form). Returns {row} or {reason}; never a
// row that was fixed up. observer_id and received_utc are ours to stamp:
// whatever the client sent for them is ignored.
export function checkRow(raw, observerId, nowMs) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return {reason: "not a row"};
  const entryId = raw.entry_id;
  if (typeof entryId !== "string" || !ENTRY_ID.test(entryId)) return {reason: "entry_id: missing or malformed"};
  if (typeof raw.break_id !== "string" || !VOCAB.breaks.includes(raw.break_id)) {
    return {reason: "break_id: not a known break"};
  }
  const out = {entry_id: entryId, break_id: raw.break_id};
  for (const [name, allowed] of [["shape", VOCAB.shape], ["surface", VOCAB.surface],
    ["power", VOCAB.power], ["entered_on", VOCAB.entered_on]]) {
    const [v, reason] = word(raw, name, allowed);
    if (reason) return {reason};
    out[name] = v;
  }
  // Decided at entry by the observer; a row without the decision is from
  // something that never asked.
  const t = raw.is_test;
  if (t === true || t === false) out.is_test = String(t);
  else if (typeof t === "string" && ["true", "false"].includes(t.trim().toLowerCase())) out.is_test = t.trim().toLowerCase();
  else return {reason: "is_test: must be true or false, decided at entry"};

  const observed = parseIso(raw.observed_utc), logged = parseIso(raw.logged_utc);
  if (observed == null) return {reason: "observed_utc: not YYYY-MM-DDTHH:MM:SSZ"};
  if (logged == null) return {reason: "logged_utc: not YYYY-MM-DDTHH:MM:SSZ"};
  if (observed > logged) return {reason: "observed_utc is after logged_utc"};
  if (observed > nowMs + CLOCK_GRACE_S * 1000) return {reason: "observed_utc is in the future"};
  out.observed_utc = raw.observed_utc;
  out.logged_utc = raw.logged_utc;
  out.observer_id = observerId;
  out.received_utc = isoSec(nowMs);
  return {row: out};
}

// ---- the limit on tries ---------------------------------------------------

async function overLimit(db, client, nowS) {
  const mine = await db.prepare("SELECT COUNT(*) AS n FROM tries WHERE client = ? AND at > ?")
    .bind(client, nowS - LIMITS.client.seconds).first();
  if (mine && mine.n >= LIMITS.client.tries) return true;
  const all = await db.prepare("SELECT COUNT(*) AS n FROM tries WHERE at > ?")
    .bind(nowS - LIMITS.global.seconds).first();
  return !!(all && all.n >= LIMITS.global.tries);
}

async function wrongTry(db, client, nowS) {
  const longest = Math.max(LIMITS.client.seconds, LIMITS.global.seconds);
  await db.batch([
    db.prepare("INSERT INTO tries (client, at) VALUES (?, ?)").bind(client, nowS),
    db.prepare("DELETE FROM tries WHERE at <= ?").bind(nowS - longest),
  ]);
}

// ---- HTTP -----------------------------------------------------------------

const CORS = {
  "Access-Control-Allow-Origin": PAGE_ORIGIN,
  "Access-Control-Allow-Methods": "POST",
  "Access-Control-Allow-Headers": "Content-Type",
  "Access-Control-Max-Age": "86400",
  "Vary": "Origin",
};

function reply(status, body, cors = true) {
  return new Response(body == null ? null : JSON.stringify(body), {
    status,
    headers: {
      ...(body == null ? {} : {"Content-Type": "application/json"}),
      "Cache-Control": "no-store",
      ...(cors ? CORS : {}),
    },
  });
}

async function readJson(request) {
  const text = await request.text();
  if (text.length > MAX_BODY) return {error: reply(413, {error: "body too large"})};
  try { return {body: JSON.parse(text)}; } catch (e) { return {error: reply(400, {error: "body is not JSON"})}; }
}

async function sameSecret(a, b) {
  // Compare digests, so the time taken says nothing about where they differ.
  const enc = new TextEncoder();
  const [x, y] = await Promise.all([a, b].map((s) => crypto.subtle.digest("SHA-256", enc.encode(s))));
  const u = new Uint8Array(x), v = new Uint8Array(y);
  let diff = 0;
  for (let i = 0; i < u.length; i++) diff |= u[i] ^ v[i];
  return diff === 0;
}

// POST /code {code} -> 200 {ok}; 429 over the limit.
async function postCode(request, env, client, nowMs) {
  const {body, error} = await readJson(request);
  if (error) return error;
  const map = codes(env);
  const nowS = Math.floor(nowMs / 1000);
  if (await overLimit(env.DB, client, nowS)) return reply(429, {error: "too many tries"});
  const code = codeOf(body && body.code);
  if (code && map.has(code)) return reply(200, {ok: true});
  await wrongTry(env.DB, client, nowS);
  return reply(200, {ok: false});
}

// POST /ratings {code, rows} -> 200 {accepted, refused}; 401 for a code that
// is not live (a wrong code here counts as a try, or /ratings would be a way
// round /code's limit); 429 over the limit.
async function postRatings(request, env, client, nowMs) {
  const {body, error} = await readJson(request);
  if (error) return error;
  const map = codes(env);
  const nowS = Math.floor(nowMs / 1000);
  if (await overLimit(env.DB, client, nowS)) return reply(429, {error: "too many tries"});
  const code = codeOf(body && body.code);
  const observer = code ? map.get(code) : undefined;
  if (!observer) {
    await wrongTry(env.DB, client, nowS);
    return reply(401, {error: "code not live"});
  }
  const rows = body.rows;
  if (!Array.isArray(rows) || rows.length < 1 || rows.length > MAX_ROWS) {
    return reply(400, {error: `rows: 1 to ${MAX_ROWS}`});
  }
  const accepted = [], refused = [], inserts = [];
  const cols = VOCAB.columns;
  const sql = `INSERT OR IGNORE INTO ratings (${cols.join(", ")}) VALUES (${cols.map(() => "?").join(", ")})`;
  for (const raw of rows) {
    const got = checkRow(raw, observer, nowMs);
    if (got.reason) {
      const id = raw && typeof raw.entry_id === "string" ? raw.entry_id.slice(0, 64) : "?";
      refused.push({entry_id: id, reason: got.reason});
      continue;
    }
    // Held already (a batch sent twice): INSERT OR IGNORE keeps the first,
    // and it is reported accepted, as the contract says.
    inserts.push(env.DB.prepare(sql).bind(...cols.map((c) => got.row[c])));
    accepted.push(got.row.entry_id);
  }
  if (inserts.length) await env.DB.batch(inserts);
  return reply(200, {accepted, refused});
}

// GET /pull?since=ISO, Authorization: Bearer <PULL_TOKEN> -> 200 {rows, now}.
// Every row received at or after `since`, oldest first. Nothing is deleted or
// marked as pulled: a job that fails after the pull loses nothing, and asks
// again with an overlap that import_rows skips by entry_id.
async function getPull(request, env, client, nowMs) {
  if (!env.PULL_TOKEN || env.PULL_TOKEN.length < 32) throw new ConfigError("PULL_TOKEN is not set");
  const nowS = Math.floor(nowMs / 1000);
  if (await overLimit(env.DB, client, nowS)) return reply(429, {error: "too many tries"}, false);
  const auth = request.headers.get("Authorization") || "";
  const token = auth.startsWith("Bearer ") ? auth.slice(7) : "";
  if (!(await sameSecret(token, env.PULL_TOKEN))) {
    await wrongTry(env.DB, client, nowS);
    return reply(401, {error: "not authorised"}, false);
  }
  const since = new URL(request.url).searchParams.get("since") || "1970-01-01T00:00:00Z";
  if (parseIso(since) == null) return reply(400, {error: "since: not YYYY-MM-DDTHH:MM:SSZ"}, false);
  const cols = VOCAB.columns;
  const got = await env.DB.prepare(
    `SELECT ${cols.join(", ")} FROM ratings WHERE received_utc >= ? ORDER BY received_utc, entry_id`,
  ).bind(since).all();
  return reply(200, {rows: got.results || [], now: isoSec(nowMs)}, false);
}

export async function handle(request, env, nowMs = Date.now()) {
  const path = new URL(request.url).pathname.replace(/\/+$/, "");
  const client = request.headers.get("CF-Connecting-IP") || "unknown";
  try {
    if (request.method === "OPTIONS") return reply(204, null);
    if (path === "/code" || path === "/ratings") {
      if (request.method !== "POST") return reply(405, {error: "POST only"});
      return path === "/code"
        ? await postCode(request, env, client, nowMs)
        : await postRatings(request, env, client, nowMs);
    }
    if (path === "/pull") {
      if (request.method !== "GET") return reply(405, {error: "GET only"}, false);
      return await getPull(request, env, client, nowMs);
    }
    return reply(404, {error: "not found"});
  } catch (e) {
    // Never echo the secret's content; the log names the kind of fault only.
    console.error(e instanceof ConfigError ? `config: ${e.message}` : `fault: ${e && e.name}`);
    return reply(500, {error: e instanceof ConfigError ? "service misconfigured" : "service fault"});
  }
}
