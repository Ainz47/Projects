import test from "node:test";
import assert from "node:assert/strict";
import { analyze, verdictFor, VERDICT_LABELS } from "../code/report.js";
import { fakeDns } from "./helpers.js";

const key = (bytes) => Buffer.alloc(bytes, 1).toString("base64");
const healthy = {
  "TXT:a.com": ["v=spf1 ip4:1.2.3.4 -all"],
  "TXT:_dmarc.a.com": ["v=DMARC1; p=reject; rua=mailto:r@a.com"],
  "TXT:google._domainkey.a.com": [`v=DKIM1; k=rsa; p=${key(294)}`],
  "MX:a.com": [{ priority: 10, host: "mx.a.com" }],
};
const c = (...statuses) => statuses.map((status) => ({ status }));

test("the verdict labels are the four stamp words", () => {
  assert.deepEqual(VERDICT_LABELS, { ready: "Ready", review: "Review", fix: "Fix first", incomplete: "Couldn't finish" });
});

test("all passes is ready", () => assert.equal(verdictFor(c("pass", "pass")), "ready"));
test("a warning is review", () => assert.equal(verdictFor(c("pass", "warn")), "review"));
test("an error with no failure is incomplete", () => assert.equal(verdictFor(c("pass", "error", "warn")), "incomplete"));
test("a failure is fix, even next to an error", () => assert.equal(verdictFor(c("error", "fail", "pass")), "fix"));

test("a healthy domain is ready, with the four checks in a fixed order", async () => {
  const r = await analyze("a.com", "", fakeDns(healthy));
  assert.equal(r.ok, true);
  assert.equal(r.domain, "a.com");
  assert.equal(r.verdict, "ready");
  assert.deepEqual(r.checks.map((x) => x.id), ["spf", "dkim", "dmarc", "mx"]);
});

test("a domain with problems is not ready", async () => {
  const r = await analyze("a.com", "", fakeDns({}));
  assert.equal(r.verdict, "fix");
});

test("the input is cleaned before it is used", async () => {
  const dns = fakeDns(healthy);
  const r = await analyze("https://A.com/page", "", dns);
  assert.equal(r.domain, "a.com");
  assert.ok(dns.calls.includes("TXT:a.com"));
});

test("an invalid domain is refused and nothing is looked up", async () => {
  const dns = fakeDns({});
  const r = await analyze("192.168.0.1", "", dns);
  assert.equal(r.ok, false);
  assert.match(r.reason, /ip address/i);
  assert.equal(dns.calls.length, 0);
});

test("an invalid selector is refused and nothing is looked up", async () => {
  const dns = fakeDns({});
  const r = await analyze("a.com", "bad selector", dns);
  assert.equal(r.ok, false);
  assert.equal(dns.calls.length, 0);
});

test("the typed selector is passed through to the DKIM check", async () => {
  const dns = fakeDns({});
  await analyze("a.com", "MyCorp", dns);
  assert.ok(dns.calls.includes("TXT:mycorp._domainkey.a.com"));
});

test("a check that throws becomes an error row and the others still finish", async () => {
  const base = fakeDns(healthy);
  const resolve = async (name, type) => {
    if (type === "MX") throw new Error("boom");
    return base(name, type);
  };
  const r = await analyze("a.com", "", resolve);
  const mx = r.checks.find((x) => x.id === "mx");
  assert.equal(mx.status, "error");
  assert.match(mx.summary, /boom/);
  assert.equal(r.checks.find((x) => x.id === "spf").status, "pass");
  assert.equal(r.verdict, "incomplete");
});
