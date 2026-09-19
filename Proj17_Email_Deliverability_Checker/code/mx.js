import { result } from "./result.js";

export async function checkMx(domain, resolve) {
  const r = await resolve(domain, "MX");
  if (!r.ok) return result("mx", "error", `Could not look up the MX records (${r.error}).`, "Try again in a moment.");

  const servers = [...r.answers].sort((a, b) => a.priority - b.priority);
  if (!servers.length) {
    return result("mx", "warn", "No MX records found, so this domain cannot receive replies.", "Add MX records that point at your mail provider so replies and bounces reach you.");
  }
  const records = servers.map((s) => `${s.priority} ${s.host || "."}`);
  if (servers.length === 1 && servers[0].host === "") {
    return result("mx", "pass", "This domain publishes a null MX, so it says it does not receive email.", "", records);
  }
  return result("mx", "pass", `${servers.length} mail ${servers.length === 1 ? "server" : "servers"} found.`, "", records);
}
