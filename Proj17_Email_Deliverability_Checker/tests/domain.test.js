import test from "node:test";
import assert from "node:assert/strict";
import { normalizeDomain, normalizeSelector } from "../code/domain.js";

test("a plain domain is lower-cased and accepted", () => {
  assert.deepEqual(normalizeDomain("Example.COM"), { ok: true, domain: "example.com" });
});

test("a URL is reduced to its hostname", () => {
  assert.equal(normalizeDomain("https://www.Example.com/path?x=1").domain, "www.example.com");
});

test("an email address is reduced to its domain", () => {
  assert.equal(normalizeDomain("Jane.Doe@Example.com").domain, "example.com");
});

test("a trailing dot and surrounding spaces are dropped", () => {
  assert.equal(normalizeDomain("  example.com.  ").domain, "example.com");
});

test("an internationalised name becomes punycode", () => {
  assert.equal(normalizeDomain("bücher.de").domain, "xn--bcher-kva.de");
});

test("empty input is rejected with a reason", () => {
  const r = normalizeDomain("   ");
  assert.equal(r.ok, false);
  assert.match(r.reason, /enter a domain/i);
});

test("a single label is rejected", () => {
  assert.equal(normalizeDomain("localhost").ok, false);
});

test("an IPv4 address is rejected", () => {
  const r = normalizeDomain("192.168.0.1");
  assert.equal(r.ok, false);
  assert.match(r.reason, /ip address/i);
});

test("an IPv6 address is rejected", () => {
  assert.equal(normalizeDomain("[2001:db8::1]").ok, false);
});

test("spaces or odd characters inside the name are rejected", () => {
  assert.equal(normalizeDomain("exa mple.com").ok, false);
  assert.equal(normalizeDomain("exa_mple.com").ok, false);
});

test("a label longer than 63 characters is rejected", () => {
  assert.equal(normalizeDomain("a".repeat(64) + ".com").ok, false);
});

test("a name longer than 253 characters is rejected", () => {
  const long = Array(6).fill("a".repeat(50)).join(".") + ".com";
  assert.equal(normalizeDomain(long).ok, false);
});

test("an empty selector means none was typed", () => {
  assert.deepEqual(normalizeSelector(""), { ok: true, selector: "" });
  assert.deepEqual(normalizeSelector("   "), { ok: true, selector: "" });
});

test("a selector is lower-cased and accepted", () => {
  assert.equal(normalizeSelector("Selector1").selector, "selector1");
  assert.equal(normalizeSelector("s1._x-y").selector, "s1._x-y");
});

test("a selector with a space, a slash or a leading dot is rejected", () => {
  assert.equal(normalizeSelector("a b").ok, false);
  assert.equal(normalizeSelector("a/b").ok, false);
  assert.equal(normalizeSelector(".a").ok, false);
});

test("a selector longer than 63 characters is rejected", () => {
  assert.equal(normalizeSelector("a".repeat(64)).ok, false);
});
