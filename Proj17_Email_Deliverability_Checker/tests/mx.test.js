import test from "node:test";
import assert from "node:assert/strict";
import { checkMx } from "../code/mx.js";
import { fakeDns } from "./helpers.js";

test("no MX records warns that replies cannot arrive", async () => {
  const r = await checkMx("a.com", fakeDns({}));
  assert.equal(r.id, "mx");
  assert.equal(r.status, "warn");
  assert.match(r.summary, /no mx records/i);
  assert.match(r.fix, /mx/i);
});

test("MX records pass and are listed lowest priority first", async () => {
  const dns = fakeDns({ "MX:a.com": [{ priority: 20, host: "mx2.a.com" }, { priority: 10, host: "mx1.a.com" }] });
  const r = await checkMx("a.com", dns);
  assert.equal(r.status, "pass");
  assert.match(r.summary, /2 mail servers/);
  assert.deepEqual(r.records, ["10 mx1.a.com", "20 mx2.a.com"]);
});

test("a single MX record is described in the singular", async () => {
  const r = await checkMx("a.com", fakeDns({ "MX:a.com": [{ priority: 10, host: "mx.a.com" }] }));
  assert.match(r.summary, /1 mail server\b/);
});

test("a null MX passes and says the domain does not receive mail", async () => {
  const r = await checkMx("a.com", fakeDns({ "MX:a.com": [{ priority: 0, host: "" }] }));
  assert.equal(r.status, "pass");
  assert.match(r.summary, /does not receive/i);
});

test("a failed lookup is an error, not a missing record", async () => {
  const r = await checkMx("a.com", fakeDns({ "MX:a.com": new Error("timeout") }));
  assert.equal(r.status, "error");
  assert.match(r.summary, /timeout/);
});
