import { normalizeDomain, normalizeSelector } from "./domain.js";
import { result } from "./result.js";
import { checkSpf } from "./spf.js";
import { checkDkim } from "./dkim.js";
import { checkDmarc } from "./dmarc.js";
import { checkMx } from "./mx.js";

export const VERDICT_LABELS = { ready: "Ready", review: "Review", fix: "Fix first", incomplete: "Couldn't finish" };

// A failure always wins. An error (a lookup that could not finish) comes next, so a network
// problem can never read as "Ready".
export function verdictFor(checks) {
  const has = (status) => checks.some((c) => c.status === status);
  if (has("fail")) return "fix";
  if (has("error")) return "incomplete";
  if (has("warn")) return "review";
  return "ready";
}

export async function analyze(rawDomain, rawSelector, resolve) {
  const d = normalizeDomain(rawDomain);
  if (!d.ok) return { ok: false, reason: d.reason };
  const s = normalizeSelector(rawSelector);
  if (!s.ok) return { ok: false, reason: s.reason };

  const runs = [
    ["spf", () => checkSpf(d.domain, resolve)],
    ["dkim", () => checkDkim(d.domain, resolve, s.selector)],
    ["dmarc", () => checkDmarc(d.domain, resolve)],
    ["mx", () => checkMx(d.domain, resolve)],
  ];
  const checks = await Promise.all(
    runs.map(async ([id, run]) => {
      try {
        return await run();
      } catch (e) {
        return result(id, "error", `This check stopped unexpectedly (${e.message}).`, "Try again in a moment.");
      }
    })
  );
  return { ok: true, domain: d.domain, verdict: verdictFor(checks), checks };
}
