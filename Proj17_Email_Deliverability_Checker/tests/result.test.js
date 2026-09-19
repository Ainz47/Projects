import test from "node:test";
import assert from "node:assert/strict";
import { fromProblems, endSentence } from "../code/result.js";

test("no problems is a pass with the pass summary", () => {
  const r = fromProblems("x", [], "All good.", ["rec"]);
  assert.deepEqual(r, { id: "x", status: "pass", summary: "All good.", fix: "", records: ["rec"] });
});

test("the worst problem sets the status and the summary", () => {
  const r = fromProblems("x", [
    { level: "warn", text: "minor", fix: "a" },
    { level: "fail", text: "major", fix: "b" },
    { level: "error", text: "unknown", fix: "c" },
  ], "ok");
  assert.equal(r.status, "fail");
  assert.equal(r.summary, "major");
});

test("an error outranks a warning", () => {
  const r = fromProblems("x", [{ level: "warn", text: "w", fix: "" }, { level: "error", text: "e", fix: "" }], "ok");
  assert.equal(r.status, "error");
});

test("identical fixes are shown once", () => {
  const r = fromProblems("x", [
    { level: "warn", text: "one", fix: "Do the thing." },
    { level: "warn", text: "two", fix: "Do the thing." },
    { level: "warn", text: "three", fix: "Do another thing." },
  ], "ok");
  assert.equal(r.fix, "Do the thing. Do another thing.");
});

test("endSentence adds a full stop only when there is none", () => {
  assert.equal(endSentence("timeout"), "timeout.");
  assert.equal(endSentence("timeout."), "timeout.");
  assert.equal(endSentence("what?"), "what?");
});
