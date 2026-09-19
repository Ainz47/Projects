import test from "node:test";
import assert from "node:assert/strict";
import { checkSpf } from "../code/spf.js";
import { fakeDns } from "./helpers.js";

const spf = (...terms) => ["v=spf1 " + terms.join(" ")];

test("no SPF record fails and says how to add one", async () => {
  const r = await checkSpf("a.com", fakeDns({}));
  assert.equal(r.id, "spf");
  assert.equal(r.status, "fail");
  assert.match(r.summary, /no spf record/i);
  assert.match(r.fix, /v=spf1/);
});

test("other TXT records are not mistaken for SPF", async () => {
  const r = await checkSpf("a.com", fakeDns({ "TXT:a.com": ["google-site-verification=abc", "v=spf10 nope"] }));
  assert.equal(r.status, "fail");
});

test("two SPF records fail", async () => {
  const r = await checkSpf("a.com", fakeDns({ "TXT:a.com": [...spf("-all"), ...spf("~all")] }));
  assert.equal(r.status, "fail");
  assert.match(r.summary, /2 spf records/i);
  assert.match(r.fix, /merge/i);
});

test("a strict record with no lookups passes and shows the record", async () => {
  const r = await checkSpf("a.com", fakeDns({ "TXT:a.com": spf("ip4:1.2.3.4", "-all") }));
  assert.equal(r.status, "pass");
  assert.match(r.summary, /-all/);
  assert.match(r.summary, /0 of 10/);
  assert.deepEqual(r.records, ["v=spf1 ip4:1.2.3.4 -all"]);
});

test("soft fail (~all) passes and is named as soft fail", async () => {
  const r = await checkSpf("a.com", fakeDns({ "TXT:a.com": spf("ip4:1.2.3.4", "~all") }));
  assert.equal(r.status, "pass");
  assert.match(r.summary, /~all/);
});

test("?all warns because it says nothing about other senders", async () => {
  const r = await checkSpf("a.com", fakeDns({ "TXT:a.com": spf("ip4:1.2.3.4", "?all") }));
  assert.equal(r.status, "warn");
});

test("+all fails because it lets anyone send as the domain", async () => {
  const r = await checkSpf("a.com", fakeDns({ "TXT:a.com": spf("+all") }));
  assert.equal(r.status, "fail");
  assert.match(r.summary, /anyone/i);
});

test("a record with no all and no redirect warns", async () => {
  const r = await checkSpf("a.com", fakeDns({ "TXT:a.com": spf("ip4:1.2.3.4") }));
  assert.equal(r.status, "warn");
  assert.match(r.summary, /does not end/i);
});

test("the record is read case-insensitively", async () => {
  const r = await checkSpf("a.com", fakeDns({ "TXT:a.com": ["V=SPF1 IP4:1.2.3.4 -ALL"] }));
  assert.equal(r.status, "pass");
});

test("lookups are counted through includes, a and mx", async () => {
  const dns = fakeDns({
    "TXT:a.com": spf("include:x.com", "include:y.com", "-all"),
    "TXT:x.com": spf("a", "mx", "-all"),
    "TXT:y.com": spf("ip4:5.6.7.8", "-all"),
  });
  const r = await checkSpf("a.com", dns);
  assert.equal(r.status, "pass");
  assert.match(r.summary, /4 of 10/);
});

test("terms after all are ignored and not counted", async () => {
  const r = await checkSpf("a.com", fakeDns({ "TXT:a.com": spf("-all", "include:x.com") }));
  assert.match(r.summary, /0 of 10/);
});

test("more than 10 lookups fails", async () => {
  const table = { "TXT:a.com": spf(...Array.from({ length: 11 }, (_, i) => `include:i${i}.com`), "-all") };
  for (let i = 0; i < 11; i++) table[`TXT:i${i}.com`] = spf("ip4:1.1.1.1", "-all");
  const r = await checkSpf("a.com", fakeDns(table));
  assert.equal(r.status, "fail");
  assert.match(r.summary, /more than 10|over 10|exceeds/i);
  assert.match(r.fix, /remove|flatten/i);
});

test("exactly 10 lookups warns that there is no headroom", async () => {
  const table = { "TXT:a.com": spf(...Array.from({ length: 10 }, (_, i) => `include:i${i}.com`), "-all") };
  for (let i = 0; i < 10; i++) table[`TXT:i${i}.com`] = spf("ip4:1.1.1.1", "-all");
  const r = await checkSpf("a.com", fakeDns(table));
  assert.equal(r.status, "warn");
  assert.match(r.summary, /10 of 10/);
});

test("9 lookups also warns", async () => {
  const table = { "TXT:a.com": spf(...Array.from({ length: 9 }, (_, i) => `include:i${i}.com`), "-all") };
  for (let i = 0; i < 9; i++) table[`TXT:i${i}.com`] = spf("ip4:1.1.1.1", "-all");
  const r = await checkSpf("a.com", fakeDns(table));
  assert.equal(r.status, "warn");
});

test("a huge include list stops early instead of querying every one", async () => {
  const table = { "TXT:a.com": spf(...Array.from({ length: 40 }, (_, i) => `include:i${i}.com`), "-all") };
  for (let i = 0; i < 40; i++) table[`TXT:i${i}.com`] = spf("ip4:1.1.1.1", "-all");
  const dns = fakeDns(table);
  const r = await checkSpf("a.com", dns);
  assert.equal(r.status, "fail");
  assert.ok(dns.calls.length <= 13, `made ${dns.calls.length} lookups`);
});

test("an include loop fails", async () => {
  const dns = fakeDns({ "TXT:a.com": spf("include:b.com", "-all"), "TXT:b.com": spf("include:a.com", "-all") });
  const r = await checkSpf("a.com", dns);
  assert.equal(r.status, "fail");
  assert.match(r.summary, /loop/i);
});

test("an include that points at a domain with no SPF record fails", async () => {
  const dns = fakeDns({ "TXT:a.com": spf("include:gone.com", "-all") });
  const r = await checkSpf("a.com", dns);
  assert.equal(r.status, "fail");
  assert.match(r.summary, /gone\.com/);
});

test("redirect= is followed and its ending is used", async () => {
  const dns = fakeDns({ "TXT:a.com": spf("redirect=_spf.x.com"), "TXT:_spf.x.com": spf("ip4:1.2.3.4", "-all") });
  const r = await checkSpf("a.com", dns);
  assert.equal(r.status, "pass");
  assert.match(r.summary, /1 of 10/);
});

test("the deprecated ptr mechanism warns", async () => {
  const r = await checkSpf("a.com", fakeDns({ "TXT:a.com": spf("ptr", "-all") }));
  assert.equal(r.status, "warn");
  assert.match(r.summary, /ptr/i);
});

test("a failed lookup of the domain is an error, not a missing record", async () => {
  const r = await checkSpf("a.com", fakeDns({ "TXT:a.com": new Error("timeout") }));
  assert.equal(r.status, "error");
  assert.match(r.summary, /timeout/);
});

test("a failed lookup inside an include is an error, not a pass", async () => {
  const dns = fakeDns({ "TXT:a.com": spf("include:x.com", "-all"), "TXT:x.com": new Error("timeout") });
  const r = await checkSpf("a.com", dns);
  assert.equal(r.status, "error");
});
