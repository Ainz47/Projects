import { result, fromProblems } from "./result.js";
import { parseTags } from "./tags.js";

// A selector cannot be discovered from the domain, so we probe the names the big providers use.
export const COMMON_SELECTORS = [
  "google", "default", "selector1", "selector2", "k1", "k2", "k3", "s1", "s2",
  "mail", "dkim", "smtp", "zoho", "mandrill", "brevo1", "brevo2",
];

const isDkim = (txt) => /^\s*v=DKIM1/i.test(txt) || /(^|;)\s*p=/i.test(txt);

// Byte length of a base64 string without decoding it (works the same in a browser and in node).
const base64Bytes = (b64) => Math.floor((b64.replace(/=+$/, "").length * 3) / 4);

function evaluate(selector, txt) {
  const tags = parseTags(txt);
  const p = (tags.p || "").replace(/\s+/g, "");
  if (!p) {
    return [{ level: "fail", text: `The key for selector ${selector} has been revoked (empty p=).`, fix: "Publish a current key for this selector, or stop sending with it." }];
  }
  const problems = [];
  if ((tags.k || "rsa").toLowerCase() !== "ed25519") {
    const bytes = base64Bytes(p);
    if (bytes < 100) {
      problems.push({ level: "fail", text: `The key for selector ${selector} is too short to be secure.`, fix: "Publish a 2048-bit key." });
    } else if (bytes < 270) {
      problems.push({ level: "warn", text: `Selector ${selector} uses what looks like a 1024-bit key, which is considered weak.`, fix: "Rotate to a 2048-bit key with your email provider." });
    }
  }
  if ((tags.t || "").toLowerCase().split(":").includes("y")) {
    problems.push({ level: "warn", text: `Selector ${selector} is in test mode (t=y), so receivers may ignore failures.`, fix: "Remove t=y once you have confirmed DKIM works." });
  }
  return problems;
}

export async function checkDkim(domain, resolve, typedSelector = "") {
  const selectors = [...new Set([typedSelector, ...COMMON_SELECTORS].filter(Boolean))];
  const lookups = await Promise.all(
    selectors.map(async (selector) => ({ selector, r: await resolve(`${selector}._domainkey.${domain}`, "TXT") }))
  );

  const typed = typedSelector ? lookups.find((l) => l.selector === typedSelector) : null;
  if (typed && !typed.r.ok) {
    return result("dkim", "error", `Could not look up the DKIM record for ${typedSelector} (${typed.r.error}).`, "Try again in a moment.");
  }

  const found = lookups
    .filter((l) => l.r.ok)
    .map((l) => ({ selector: l.selector, records: l.r.answers.filter(isDkim) }))
    .filter((l) => l.records.length);

  if (!found.length && !typed) {
    if (lookups.every((l) => !l.r.ok)) {
      return result("dkim", "error", `Could not look up any DKIM records (${lookups[0].r.error}).`, "Try again in a moment.");
    }
    return result(
      "dkim",
      "warn",
      "No DKIM record found among the common selectors. This does not prove DKIM is missing, because a selector cannot be discovered from the domain.",
      "Type your selector into the DKIM selector field. Your email provider's DKIM setup page shows it."
    );
  }

  const problems = [];
  if (typed && !found.some((f) => f.selector === typedSelector)) {
    problems.push({
      level: "fail",
      text: `No DKIM record found for the selector ${typedSelector} (${typedSelector}._domainkey.${domain}).`,
      fix: "Check the selector name in your email provider's DKIM settings, or publish the key it gives you.",
    });
  }
  for (const f of found) problems.push(...evaluate(f.selector, f.records[0]));

  const names = found.map((f) => f.selector).join(", ");
  const summary = `DKIM found for ${found.length === 1 ? "selector" : "selectors"} ${names}.`;
  return fromProblems("dkim", problems, summary, found.map((f) => f.records[0]));
}
