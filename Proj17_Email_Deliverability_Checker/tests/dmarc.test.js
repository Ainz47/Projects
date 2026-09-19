import test from "node:test";
import assert from "node:assert/strict";
import { checkDmarc } from "../code/dmarc.js";
import { fakeDns } from "./helpers.js";

const at = (domain, ...records) => ({ [`TXT:_dmarc.${domain}`]: records });

test("no DMARC record fails and says how to add one", async () => {
  const r = await checkDmarc("a.com", fakeDns({}));
  assert.equal(r.id, "dmarc");
  assert.equal(r.status, "fail");
  assert.match(r.summary, /no dmarc record/i);
  assert.match(r.fix, /v=DMARC1/);
});

test("other TXT records at _dmarc are ignored", async () => {
  const r = await checkDmarc("a.com", fakeDns(at("a.com", "hello world")));
  assert.equal(r.status, "fail");
});

test("p=none warns because nothing is enforced", async () => {
  const r = await checkDmarc("a.com", fakeDns(at("a.com", "v=DMARC1; p=none; rua=mailto:r@a.com")));
  assert.equal(r.status, "warn");
  assert.match(r.summary, /monitoring/i);
});

test("p=quarantine with a report address passes", async () => {
  const r = await checkDmarc("a.com", fakeDns(at("a.com", "v=DMARC1; p=quarantine; rua=mailto:r@a.com")));
  assert.equal(r.status, "pass");
  assert.match(r.summary, /quarantine/);
});

test("p=reject with a report address passes and shows the record", async () => {
  const rec = "v=DMARC1; p=reject; rua=mailto:r@a.com";
  const r = await checkDmarc("a.com", fakeDns(at("a.com", rec)));
  assert.equal(r.status, "pass");
  assert.deepEqual(r.records, [rec]);
});

test("no rua warns that no reports will arrive", async () => {
  const r = await checkDmarc("a.com", fakeDns(at("a.com", "v=DMARC1; p=reject")));
  assert.equal(r.status, "warn");
  assert.match(r.summary, /report/i);
});

test("pct below 100 warns", async () => {
  const r = await checkDmarc("a.com", fakeDns(at("a.com", "v=DMARC1; p=reject; pct=50; rua=mailto:r@a.com")));
  assert.equal(r.status, "warn");
  assert.match(r.summary, /50/);
});

test("pct=100 is fine", async () => {
  const r = await checkDmarc("a.com", fakeDns(at("a.com", "v=DMARC1; p=reject; pct=100; rua=mailto:r@a.com")));
  assert.equal(r.status, "pass");
});

test("a record with no p tag fails", async () => {
  const r = await checkDmarc("a.com", fakeDns(at("a.com", "v=DMARC1; rua=mailto:r@a.com")));
  assert.equal(r.status, "fail");
  assert.match(r.summary, /policy/i);
});

test("an unknown policy value fails", async () => {
  const r = await checkDmarc("a.com", fakeDns(at("a.com", "v=DMARC1; p=allow; rua=mailto:r@a.com")));
  assert.equal(r.status, "fail");
});

test("two DMARC records fail", async () => {
  const r = await checkDmarc("a.com", fakeDns(at("a.com", "v=DMARC1; p=none", "v=DMARC1; p=reject")));
  assert.equal(r.status, "fail");
  assert.match(r.summary, /2 dmarc records/i);
});

test("tag names and values are read case-insensitively and without spaces", async () => {
  const r = await checkDmarc("a.com", fakeDns(at("a.com", "V=DMARC1;P=Reject;RUA=mailto:r@a.com")));
  assert.equal(r.status, "pass");
});

test("a failed lookup is an error, not a missing record", async () => {
  const r = await checkDmarc("a.com", fakeDns({ "TXT:_dmarc.a.com": new Error("timeout") }));
  assert.equal(r.status, "error");
  assert.match(r.summary, /timeout/);
});

test("a subdomain with no record uses the parent's and says so", async () => {
  const dns = fakeDns(at("a.com", "v=DMARC1; p=reject; rua=mailto:r@a.com"));
  const r = await checkDmarc("mail.a.com", dns);
  assert.equal(r.status, "pass");
  assert.match(r.summary, /inherit/i);
  assert.deepEqual(dns.calls, ["TXT:_dmarc.mail.a.com", "TXT:_dmarc.a.com"]);
});

test("an inherited record's sp tag is the policy that applies to the subdomain", async () => {
  const dns = fakeDns(at("a.com", "v=DMARC1; p=reject; sp=none; rua=mailto:r@a.com"));
  const r = await checkDmarc("mail.a.com", dns);
  assert.equal(r.status, "warn");
  assert.match(r.summary, /monitoring/i);
});

test("the search for a parent record stops at two labels", async () => {
  const dns = fakeDns({});
  const r = await checkDmarc("x.y.a.com", dns);
  assert.equal(r.status, "fail");
  assert.deepEqual(dns.calls, ["TXT:_dmarc.x.y.a.com", "TXT:_dmarc.y.a.com", "TXT:_dmarc.a.com"]);
});

test("a failed lookup while searching parents is an error", async () => {
  const dns = fakeDns({ "TXT:_dmarc.a.com": new Error("timeout") });
  const r = await checkDmarc("mail.a.com", dns);
  assert.equal(r.status, "error");
});
