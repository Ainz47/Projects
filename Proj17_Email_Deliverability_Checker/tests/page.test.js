import test from "node:test";
import assert from "node:assert/strict";
import vm from "node:vm";
import { readFileSync } from "node:fs";
import { buildLogic, buildPage, PAGE_PATH } from "../tools/build_page.mjs";

const norm = (s) => s.replace(/\r\n/g, "\n");
const mods = (...pairs) => pairs.map(([name, source]) => ({ name, source }));

test("imports are removed and export keywords are dropped", () => {
  const out = buildLogic(mods(["a", "export const A = 1;\n"], ["b", 'import { A } from "./a.js";\nexport function f() { return A; }\n']));
  assert.doesNotMatch(out, /^\s*import\b/m);
  assert.doesNotMatch(out, /^\s*export\b/m);
  assert.match(out, /const A = 1;/);
  assert.match(out, /function f\(\)/);
});

test("export default is refused", () => {
  assert.throws(() => buildLogic(mods(["a", "export default function f() {}\n"])), /unsupported export/);
});

test("export { ... } is refused", () => {
  assert.throws(() => buildLogic(mods(["a", "const A = 1;\nexport { A };\n"])), /unsupported export/);
});

test("a multi-line import is refused", () => {
  assert.throws(() => buildLogic(mods(["a", "export const A = 1;\n"], ["b", 'import {\n  A,\n} from "./a.js";\n'])), /unsupported import/);
});

test("importing a module that is built later is refused", () => {
  assert.throws(() => buildLogic(mods(["a", 'import { B } from "./b.js";\n'], ["b", "export const B = 1;\n"])), /not built earlier/);
});

test("the same top-level name in two modules is refused", () => {
  assert.throws(() => buildLogic(mods(["a", "const LIMIT = 1;\n"], ["b", "const LIMIT = 2;\n"])), /already declared/);
});

test("a script-closing tag inside the logic is refused", () => {
  assert.throws(() => buildLogic(mods(["a", 'export const S = "</script>";\n'])), /<\/script/);
});

test("the page on disk is exactly what the generator produces", () => {
  assert.equal(norm(readFileSync(PAGE_PATH, "utf8")), buildPage());
});

test("the page never writes HTML from strings", () => {
  const page = buildPage();
  for (const banned of ["innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("]) {
    assert.ok(!page.includes(banned), banned);
  }
});

test("the page has exactly one inline script and no external script", () => {
  const page = buildPage();
  assert.equal((page.match(/<script/g) || []).length, 1);
  assert.doesNotMatch(page, /<script[^>]*\ssrc=/);
});

test("the merged logic runs in a bare context and produces a verdict from fake DoH answers", async () => {
  const answers = {
    "a.com|TXT": ['"v=spf1 ip4:1.2.3.4 -all"'],
    "_dmarc.a.com|TXT": ['"v=DMARC1; p=reject; rua=mailto:r@a.com"'],
    "google._domainkey.a.com|TXT": ['"v=DKIM1; k=rsa; p=' + Buffer.alloc(294, 1).toString("base64") + '"'],
    "a.com|MX": ["10 mx.a.com."],
  };
  const fetch = async (url) => {
    const u = new URL(url);
    const type = u.searchParams.get("type");
    const data = answers[`${u.searchParams.get("name")}|${type}`] || [];
    return { ok: true, status: 200, json: async () => ({ Status: 0, Answer: data.map((d) => ({ type: type === "MX" ? 15 : 16, data: d })) }) };
  };
  const sandbox = { fetch, URL, AbortController, setTimeout, clearTimeout, Promise, Map, Set };
  const { analyze, createResolver, VERDICT_LABELS } = vm.runInNewContext(
    `${buildLogic()}\n({ analyze, createResolver, VERDICT_LABELS })`,
    sandbox
  );
  const report = await analyze("a.com", "", createResolver());
  assert.equal(report.ok, true);
  assert.equal(report.verdict, "ready");
  assert.equal(VERDICT_LABELS.ready, "Ready");
});
