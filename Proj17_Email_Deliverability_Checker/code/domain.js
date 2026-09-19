// Turns whatever the user typed into a domain we are willing to query, or a reason we are not.

const LABEL = /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/;
const SELECTOR = /^[a-z0-9](?:[a-z0-9._-]{0,61}[a-z0-9])?$/;

function reject(reason) {
  return { ok: false, reason };
}

export function normalizeDomain(input) {
  let s = String(input ?? "").trim().toLowerCase();
  if (!s) return reject("Enter a domain, for example example.com.");

  s = s.replace(/^[a-z][a-z0-9+.-]*:\/\//, "").split(/[/?#]/)[0];
  if (s.includes("@")) s = s.slice(s.lastIndexOf("@") + 1);
  s = s.replace(/:\d+$/, "").replace(/\.$/, "");

  if (s.startsWith("[") || s.includes(":") || /^\d+\.\d+\.\d+\.\d+$/.test(s)) {
    return reject("That looks like an IP address. Enter a domain name instead.");
  }

  let host; // mutable: a leading "www." is dropped below
  try {
    host = new URL("http://" + s).hostname;
  } catch {
    return reject("That is not a valid domain name.");
  }

  if (host.startsWith("www.") && host.split(".").length > 2) host = host.slice(4);

  const labels = host.split(".");
  if (host.length > 253 || labels.length < 2 || labels.some((l) => l.length > 63 || !LABEL.test(l))) {
    return reject("That is not a valid domain name.");
  }
  return { ok: true, domain: host };
}

export function normalizeSelector(input) {
  const s = String(input ?? "").trim().toLowerCase();
  if (!s) return { ok: true, selector: "" };
  if (!SELECTOR.test(s)) return reject("A DKIM selector uses letters, digits, dots, hyphens and underscores.");
  return { ok: true, selector: s };
}
