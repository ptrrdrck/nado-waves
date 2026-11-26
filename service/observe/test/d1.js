// A D1-shaped database over node:sqlite, enough of D1's API for observe.js:
// prepare().bind().first()/all()/run() and batch(), batch as one transaction.
import {DatabaseSync} from "node:sqlite";
import {readFileSync} from "node:fs";

class Stmt {
  constructor(db, sql, args = []) { this.db = db; this.sql = sql; this.args = args; }
  bind(...args) { return new Stmt(this.db, this.sql, args); }
  async first() { return this.db.prepare(this.sql).get(...this.args) ?? null; }
  async all() { return {results: this.db.prepare(this.sql).all(...this.args), success: true}; }
  async run() { this.db.prepare(this.sql).run(...this.args); return {success: true}; }
}

export function fakeD1() {
  const db = new DatabaseSync(":memory:");
  db.exec(readFileSync(new URL("../schema.sql", import.meta.url), "utf8"));
  return {
    raw: db,
    prepare: (sql) => new Stmt(db, sql),
    async batch(stmts) {
      db.exec("BEGIN");
      try {
        const out = stmts.map((s) => { db.prepare(s.sql).run(...s.args); return {success: true}; });
        db.exec("COMMIT");
        return out;
      } catch (e) { db.exec("ROLLBACK"); throw e; }
    },
  };
}
