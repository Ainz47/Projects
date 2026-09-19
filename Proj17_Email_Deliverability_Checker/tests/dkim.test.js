import test from "node:test";
import assert from "node:assert/strict";
import { checkDkim, COMMON_SELECTORS } from "../code/dkim.js";
import { fakeDns } from "./helpers.js";

// A key of the given DER length, base64-encoded. Real RSA-2048 public keys are about 294 bytes,
// RSA-1024 about 162.
const key = (bytes) => Buffer.alloc(bytes, 1).toString("base64");
const rec = (bytes, extra = "") => `v=DKIM1; k=rsa; ${extra}p=${key(bytes)}`;
const at = (selector, ...records) => ({ [`TXT:${selector}._domainkey.a.com`]: records });

test("the common-selector list covers the big providers", () => {
  for (const s of ["google", "selector1", "selector2", "default", "k1", "s1"]) assert.ok(COMMON_SELECTORS.includes(s), s);
});

test("a typed selector with a 2048-bit key passes and is queried first", async () => {
  const dns = fakeDns(at("mycorp", rec(294)));
  const r = await checkDkim("a.com", dns, "mycorp");
  assert.equal(r.id, "dkim");
  assert.equal(r.status, "pass");
  assert.match(r.summary, /mycorp/);
  assert.equal(dns.calls[0], "TXT:mycorp._domainkey.a.com");
});

test("a common selector is found without the user typing anything", async () => {
  const dns = fakeDns(at("google", rec(294)));
  const r = await checkDkim("a.com", dns);
  assert.equal(r.status, "pass");
  assert.match(r.summary, /google/);
  assert.ok(dns.calls.includes("TXT:google._domainkey.a.com"));
});

test("several selectors found are all named", async () => {
  const dns = fakeDns({ ...at("google", rec(294)), ...at("selector1", rec(294)) });
  const r = await checkDkim("a.com", dns);
  assert.match(r.summary, /google/);
  assert.match(r.summary, /selector1/);
});

test("a selector that is also in the common list is only queried once", async () => {
  const dns = fakeDns(at("google", rec(294)));
  await checkDkim("a.com", dns, "google");
  assert.equal(dns.calls.filter((c) => c === "TXT:google._domainkey.a.com").length, 1);
});

test("nothing found among the common selectors is a warning, never a failure", async () => {
  const r = await checkDkim("a.com", fakeDns({}));
  assert.equal(r.status, "warn");
  assert.match(r.summary, /common selectors/i);
  assert.match(r.summary, /does not prove/i);
  assert.match(r.fix, /selector/i);
});

test("a typed selector that has no record fails and names the selector", async () => {
  const r = await checkDkim("a.com", fakeDns({}), "mycorp");
  assert.equal(r.status, "fail");
  assert.match(r.summary, /mycorp/);
});

test("other TXT text at a selector name is not a DKIM key", async () => {
  const r = await checkDkim("a.com", fakeDns(at("google", "hello world")));
  assert.equal(r.status, "warn");
});

test("an empty p= means the key was revoked and fails", async () => {
  const r = await checkDkim("a.com", fakeDns(at("google", "v=DKIM1; k=rsa; p=")));
  assert.equal(r.status, "fail");
  assert.match(r.summary, /revoked/i);
});

test("a 1024-bit key warns and suggests 2048", async () => {
  const r = await checkDkim("a.com", fakeDns(at("google", rec(162))));
  assert.equal(r.status, "warn");
  assert.match(r.summary, /1024/);
  assert.match(r.fix, /2048/);
});

test("a very short key fails", async () => {
  const r = await checkDkim("a.com", fakeDns(at("google", rec(60))));
  assert.equal(r.status, "fail");
});

test("an ed25519 key passes", async () => {
  const r = await checkDkim("a.com", fakeDns(at("google", `v=DKIM1; k=ed25519; p=${key(32)}`)));
  assert.equal(r.status, "pass");
});

test("test mode (t=y) warns", async () => {
  const r = await checkDkim("a.com", fakeDns(at("google", rec(294, "t=y; "))));
  assert.equal(r.status, "warn");
  assert.match(r.summary, /test mode/i);
});

test("the raw record is kept for display", async () => {
  const record = rec(294);
  const r = await checkDkim("a.com", fakeDns(at("google", record)));
  assert.deepEqual(r.records, [record]);
});

test("if every lookup fails the result is an error, not a missing record", async () => {
  const table = {};
  for (const s of COMMON_SELECTORS) table[`TXT:${s}._domainkey.a.com`] = new Error("timeout");
  const r = await checkDkim("a.com", fakeDns(table));
  assert.equal(r.status, "error");
});

test("some failed lookups do not hide a key that was found", async () => {
  const table = { ...at("google", rec(294)), "TXT:default._domainkey.a.com": new Error("timeout") };
  const r = await checkDkim("a.com", fakeDns(table));
  assert.equal(r.status, "pass");
});

test("a failed lookup of the typed selector is an error, not a missing key", async () => {
  const r = await checkDkim("a.com", fakeDns({ "TXT:mycorp._domainkey.a.com": new Error("timeout") }), "mycorp");
  assert.equal(r.status, "error");
});
