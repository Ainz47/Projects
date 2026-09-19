import { result, fromProblems, lookupFailed, endSentence } from "./result.js";

const LIMIT = 10;
const isSpf = (txt) => /^v=spf1(\s|$)/i.test(txt);

function parseTerms(record) {
  return record
    .trim()
    .split(/\s+/)
    .slice(1)
    .map((term) => {
      const m = /^([+\-~?])?([a-z0-9]+)(.*)$/i.exec(term);
      if (!m) return { name: "", qualifier: "", domain: "" };
      const rest = m[3];
      const domain = /^[:=]/.test(rest) ? rest.slice(1).replace(/\/\d+(\/\d+)?$/, "") : "";
      return { name: m[2].toLowerCase(), qualifier: m[1] || "", domain: domain.toLowerCase() };
    });
}

function count(ctx) {
  ctx.lookups += 1;
  if (ctx.lookups > LIMIT) {
    ctx.over = true;
    ctx.stop = true;
  }
}

// Fetch and walk the SPF record of an include or redirect target. Returns that record's "all"
// qualifier (only meaningful for redirect; an include's own "all" does not apply to the caller).
async function follow(target, ctx, chain) {
  if (ctx.stop) return null;
  if (chain.has(target)) {
    ctx.loop = target;
    ctx.stop = true;
    return null;
  }
  const r = await ctx.resolve(target, "TXT");
  if (!r.ok) {
    ctx.errors.push(r.error);
    return null;
  }
  const records = r.answers.filter(isSpf);
  if (records.length !== 1) {
    ctx.missing.push(target);
    return null;
  }
  return walk(target, records[0], ctx, new Set([...chain, target]));
}

async function walk(domain, record, ctx, chain) {
  let all = null;
  let redirect = "";
  for (const t of parseTerms(record)) {
    if (ctx.stop) return all;
    if (t.name === "all") {
      all = t.qualifier || "+";
      break;
    }
    if (t.name === "redirect") {
      redirect = t.domain;
    } else if (t.name === "include") {
      count(ctx);
      await follow(t.domain, ctx, chain);
    } else if (t.name === "a" || t.name === "mx" || t.name === "exists") {
      count(ctx);
    } else if (t.name === "ptr") {
      count(ctx);
      ctx.ptr = true;
    }
  }
  if (all === null && redirect && !ctx.stop) {
    count(ctx);
    return follow(redirect, ctx, chain);
  }
  return all;
}

export async function checkSpf(domain, resolve) {
  const r = await resolve(domain, "TXT");
  if (!r.ok) {
    return lookupFailed("spf", "the SPF record", r.error);
  }
  const records = r.answers.filter(isSpf);
  if (records.length === 0) {
    return result(
      "spf",
      "fail",
      "No SPF record found for this domain.",
      "Add a TXT record that starts with v=spf1, lists the services allowed to send for you, and ends with -all (or ~all while testing)."
    );
  }
  if (records.length > 1) {
    return result("spf", "fail", `Found ${records.length} SPF records. Receivers treat more than one as an error.`, "Merge them into a single v=spf1 record.", records);
  }

  const ctx = { resolve, lookups: 0, stop: false, over: false, ptr: false, loop: "", missing: [], errors: [] };
  const all = await walk(domain, records[0], ctx, new Set([domain]));

  const problems = [];
  if (ctx.loop) problems.push({ level: "fail", text: `The includes loop back to ${ctx.loop}.`, fix: "Remove the include that points back to a record already in the chain." });
  if (ctx.over) problems.push({ level: "fail", text: `The record needs more than ${LIMIT} DNS lookups, so receivers reject it.`, fix: "Remove includes you do not use, or flatten them into ip4 and ip6 ranges." });
  for (const target of ctx.missing) problems.push({ level: "fail", text: `Includes ${target}, which has no usable SPF record.`, fix: `Remove the include of ${target}, or get the correct include from that provider.` });
  if (ctx.errors.length) problems.push({ level: "error", text: `Could not finish checking the includes: ${endSentence(ctx.errors[0])}`, fix: "Try again in a moment." });
  if (ctx.ptr) problems.push({ level: "warn", text: "Uses the ptr mechanism, which is deprecated and slow.", fix: "Replace ptr with ip4, ip6 or include." });
  if (!ctx.stop) {
    if (all === "+") problems.push({ level: "fail", text: "The record ends with +all, which lets anyone send as this domain.", fix: "Change +all to -all (or ~all while you are still testing)." });
    else if (all === "?") problems.push({ level: "warn", text: "The record ends with ?all, which says nothing about senders you did not list.", fix: "Change ?all to -all (or ~all while you are still testing)." });
    else if (all === null) problems.push({ level: "warn", text: "The record does not end with an all mechanism, so senders you did not list are not covered.", fix: "End the record with -all (or ~all while you are still testing)." });
  }
  if (!ctx.over && ctx.lookups >= LIMIT - 1) {
    problems.push({ level: "warn", text: `Uses ${ctx.lookups} of ${LIMIT} DNS lookups, so one more include could break it.`, fix: "Trim includes you do not need." });
  }

  const ending = all === "~" ? "~all (soft fail)" : `${all}all`;
  return fromProblems("spf", problems, `SPF found. Ends with ${ending}, uses ${ctx.lookups} of ${LIMIT} DNS lookups.`, records);
}
