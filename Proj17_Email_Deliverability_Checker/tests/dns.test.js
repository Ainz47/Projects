import test from "node:test";
import assert from "node:assert/strict";
import { createResolver } from "../code/dns.js";

const CF = "https://cf.test/dns-query";
const GG = "https://gg.test/resolve";
const ENDPOINTS = [CF, GG];

function reply(body, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

// A fake fetch: routes by URL prefix and records every call it receives.
function fakeFetch(routes) {
  const calls = [];
  const fn = async (url, init) => {
    calls.push({ url, init });
    const base = ENDPOINTS.find((e) => url.startsWith(e));
    const handler = routes[base];
    return handler(url, init);
  };
  fn.calls = calls;
  return fn;
}

const txt = (name, ...data) => ({ Status: 0, Answer: data.map((d) => ({ name, type: 16, data: d })) });

test("a TXT answer is returned as plain strings", async () => {
  const f = fakeFetch({ [CF]: async () => reply(txt("a.com", '"v=spf1 -all"')) });
  const r = await createResolver({ fetchFn: f, endpoints: ENDPOINTS })("a.com", "TXT");
  assert.deepEqual(r, { ok: true, answers: ["v=spf1 -all"] });
});

test("a TXT record split into several quoted strings is joined", async () => {
  const f = fakeFetch({ [CF]: async () => reply(txt("a.com", '"v=DKIM1; k=rsa; p=AAA" "BBB"')) });
  const r = await createResolver({ fetchFn: f, endpoints: ENDPOINTS })("a.com", "TXT");
  assert.deepEqual(r.answers, ["v=DKIM1; k=rsa; p=AAABBB"]);
});

test("CNAME entries in the answer are ignored when asking for TXT", async () => {
  const body = { Status: 0, Answer: [{ name: "s._domainkey.a.com", type: 5, data: "k.b.com." }, { name: "k.b.com", type: 16, data: '"v=DKIM1; p=XYZ"' }] };
  const f = fakeFetch({ [CF]: async () => reply(body) });
  const r = await createResolver({ fetchFn: f, endpoints: ENDPOINTS })("s._domainkey.a.com", "TXT");
  assert.deepEqual(r.answers, ["v=DKIM1; p=XYZ"]);
});

test("MX answers become priority and host, without the trailing dot", async () => {
  const body = { Status: 0, Answer: [{ name: "a.com", type: 15, data: "10 mx1.a.com." }, { name: "a.com", type: 15, data: "20 mx2.a.com." }] };
  const f = fakeFetch({ [CF]: async () => reply(body) });
  const r = await createResolver({ fetchFn: f, endpoints: ENDPOINTS })("a.com", "MX");
  assert.deepEqual(r.answers, [{ priority: 10, host: "mx1.a.com" }, { priority: 20, host: "mx2.a.com" }]);
});

test("a name that does not exist is a successful lookup with no answers", async () => {
  const f = fakeFetch({ [CF]: async () => reply({ Status: 3 }) });
  const r = await createResolver({ fetchFn: f, endpoints: ENDPOINTS })("nope.a.com", "TXT");
  assert.deepEqual(r, { ok: true, answers: [] });
});

test("a name with no records of that type is a successful lookup with no answers", async () => {
  const f = fakeFetch({ [CF]: async () => reply({ Status: 0 }) });
  const r = await createResolver({ fetchFn: f, endpoints: ENDPOINTS })("a.com", "TXT");
  assert.deepEqual(r, { ok: true, answers: [] });
});

test("the request carries the encoded name, the type and the DNS JSON accept header", async () => {
  const f = fakeFetch({ [CF]: async () => reply({ Status: 0 }) });
  await createResolver({ fetchFn: f, endpoints: ENDPOINTS })("_dmarc.a.com", "TXT");
  assert.equal(f.calls[0].url, `${CF}?name=_dmarc.a.com&type=TXT`);
  assert.equal(f.calls[0].init.headers.accept, "application/dns-json");
});

test("an HTTP error from the first resolver falls back to the second", async () => {
  const f = fakeFetch({ [CF]: async () => reply({}, 500), [GG]: async () => reply(txt("a.com", '"ok"')) });
  const r = await createResolver({ fetchFn: f, endpoints: ENDPOINTS })("a.com", "TXT");
  assert.deepEqual(r.answers, ["ok"]);
  assert.equal(f.calls.length, 2);
});

test("SERVFAIL from the first resolver falls back to the second", async () => {
  const f = fakeFetch({ [CF]: async () => reply({ Status: 2 }), [GG]: async () => reply(txt("a.com", '"ok"')) });
  const r = await createResolver({ fetchFn: f, endpoints: ENDPOINTS })("a.com", "TXT");
  assert.equal(r.ok, true);
});

test("a network error falls back to the second resolver", async () => {
  const f = fakeFetch({ [CF]: async () => { throw new TypeError("fetch failed"); }, [GG]: async () => reply(txt("a.com", '"ok"')) });
  const r = await createResolver({ fetchFn: f, endpoints: ENDPOINTS })("a.com", "TXT");
  assert.equal(r.ok, true);
});

test("a resolver that never answers is abandoned after the timeout", async () => {
  const hang = (url, init) => new Promise((_, reject) => init.signal.addEventListener("abort", () => reject(new Error("aborted"))));
  const f = fakeFetch({ [CF]: hang, [GG]: async () => reply(txt("a.com", '"ok"')) });
  const r = await createResolver({ fetchFn: f, endpoints: ENDPOINTS, timeoutMs: 20 })("a.com", "TXT");
  assert.deepEqual(r.answers, ["ok"]);
});

test("when every resolver fails the result is a failed lookup, not an empty one", async () => {
  const f = fakeFetch({ [CF]: async () => reply({}, 500), [GG]: async () => reply({ Status: 2 }) });
  const r = await createResolver({ fetchFn: f, endpoints: ENDPOINTS })("a.com", "TXT");
  assert.equal(r.ok, false);
  assert.match(r.error, /could not reach a DNS resolver/i);
});

test("the same question is answered from the cache the second time", async () => {
  const f = fakeFetch({ [CF]: async () => reply(txt("a.com", '"x"')) });
  const resolve = createResolver({ fetchFn: f, endpoints: ENDPOINTS });
  await resolve("a.com", "TXT");
  await resolve("a.com", "TXT");
  assert.equal(f.calls.length, 1);
});

test("a failed lookup is cached too, so a broken resolver is not hammered", async () => {
  const f = fakeFetch({ [CF]: async () => reply({}, 500), [GG]: async () => reply({}, 500) });
  const resolve = createResolver({ fetchFn: f, endpoints: ENDPOINTS });
  await resolve("a.com", "TXT");
  await resolve("a.com", "TXT");
  assert.equal(f.calls.length, 2);
});

test("after the request cap, new questions fail without touching the network", async () => {
  const f = fakeFetch({ [CF]: async () => reply({ Status: 0 }) });
  const resolve = createResolver({ fetchFn: f, endpoints: ENDPOINTS, maxRequests: 2 });
  await resolve("a.com", "TXT");
  await resolve("b.com", "TXT");
  const r = await resolve("c.com", "TXT");
  assert.equal(f.calls.length, 2);
  assert.equal(r.ok, false);
  assert.match(r.error, /request limit/i);
});
