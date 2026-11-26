-- The Observe service's database (Cloudflare D1, SQLite). Applied once by
-- hand: npx wrangler d1 execute nado-observe --remote --file=schema.sql
-- Columns are collector.beachratings.COLUMNS, in its order; a test pins it.

CREATE TABLE IF NOT EXISTS ratings (
  entry_id     TEXT PRIMARY KEY,
  observed_utc TEXT NOT NULL,
  logged_utc   TEXT NOT NULL,
  received_utc TEXT NOT NULL,
  break_id     TEXT NOT NULL,
  observer_id  TEXT NOT NULL,
  shape        TEXT NOT NULL,
  surface      TEXT NOT NULL,
  power        TEXT NOT NULL,
  entered_on   TEXT NOT NULL,
  is_test      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ratings_received ON ratings (received_utc);

-- Wrong codes and wrong pull tokens, for the limit on tries. Pruned past the
-- longest window on every wrong try, so it never holds more than an hour.
CREATE TABLE IF NOT EXISTS tries (
  client TEXT NOT NULL,
  at     INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS tries_client_at ON tries (client, at);
CREATE INDEX IF NOT EXISTS tries_at ON tries (at);
