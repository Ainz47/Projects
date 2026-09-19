// The shape every check returns, and the rule for turning a list of problems into one status.
// status is one of pass | warn | error | fail; fail outranks error, error outranks warn.

const RANK = { pass: 0, warn: 1, error: 2, fail: 3 };

export function result(id, status, summary, fix = "", records = []) {
  return { id, status, summary, fix, records };
}

export const endSentence = (text) => (/[.!?]$/.test(text) ? text : `${text}.`);

// A lookup that could not be completed, worded the same way for every check.
export function lookupFailed(id, what, error) {
  return result(id, "error", `Could not look up ${what}: ${endSentence(error)}`, "Try again in a moment.");
}

// problems: [{ level: "warn" | "error" | "fail", text, fix }]
export function fromProblems(id, problems, passSummary, records = []) {
  if (!problems.length) return result(id, "pass", passSummary, "", records);
  const worst = problems.reduce((a, b) => (RANK[b.level] > RANK[a.level] ? b : a));
  const fix = [...new Set(problems.map((p) => p.fix).filter(Boolean))].join(" ");
  return result(id, worst.level, worst.text, fix, records);
}
