import { result, fromProblems, lookupFailed } from "./result.js";
import { parseTags } from "./tags.js";

const isDmarc = (txt) => /^v=DMARC1\s*(;|$)/i.test(txt);
const POLICIES = ["none", "quarantine", "reject"];

// example.com -> [example.com]; a.b.example.com -> [a.b.example.com, b.example.com, example.com].
// There is no public-suffix list here, so the search simply stops at two labels.
function candidates(domain) {
  const labels = domain.split(".");
  const out = [];
  for (let i = 0; i <= labels.length - 2; i++) out.push(labels.slice(i).join("."));
  return out;
}

export async function checkDmarc(domain, resolve) {
  let foundAt = "";
  let records = [];
  for (const candidate of candidates(domain)) {
    const r = await resolve(`_dmarc.${candidate}`, "TXT");
    if (!r.ok) return lookupFailed("dmarc", "the DMARC record", r.error);
    records = r.answers.filter(isDmarc);
    if (records.length) {
      foundAt = candidate;
      break;
    }
  }

  if (!records.length) {
    return result(
      "dmarc",
      "fail",
      "No DMARC record found for this domain.",
      `Add a TXT record at _dmarc.${domain} such as v=DMARC1; p=none; rua=mailto:you@${domain}, then move the policy to quarantine or reject once the reports look clean.`
    );
  }
  if (records.length > 1) {
    return result("dmarc", "fail", `Found ${records.length} DMARC records. Receivers ignore DMARC when there is more than one.`, "Keep a single v=DMARC1 record.", records);
  }

  const tags = parseTags(records[0]);
  const inherited = foundAt !== domain;
  const policy = ((inherited && tags.sp) || tags.p || "").toLowerCase();
  const problems = [];

  if (!policy) {
    problems.push({ level: "fail", text: "The DMARC record has no policy (p=).", fix: "Add p=none, p=quarantine or p=reject to the record." });
  } else if (!POLICIES.includes(policy)) {
    problems.push({ level: "fail", text: `The DMARC policy "${policy}" is not valid.`, fix: "Use p=none, p=quarantine or p=reject." });
  } else if (policy === "none") {
    problems.push({ level: "warn", text: "The policy is none, so DMARC is monitoring only and mail that fails the checks is still delivered.", fix: "Read the reports for a few weeks, then move to p=quarantine and later p=reject." });
  } else if (tags.pct && Number(tags.pct) < 100) {
    problems.push({ level: "warn", text: `The policy only applies to ${tags.pct}% of mail (pct=${tags.pct}).`, fix: "Raise pct to 100 once you are confident nothing legitimate fails." });
  }
  if (!tags.rua) {
    problems.push({ level: "warn", text: "No report address (rua), so you will not receive DMARC reports.", fix: "Add rua=mailto:you@yourdomain so you can see who sends as your domain." });
  }

  const where = inherited ? ` (inherited from ${foundAt})` : "";
  return fromProblems("dmarc", problems, `DMARC found. The policy is ${policy}${where} and reports are turned on.`, records);
}
