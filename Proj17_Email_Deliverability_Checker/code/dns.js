// The only module that touches the network. Everything else takes the `resolve` function this returns.
//
// resolve(name, type) -> { ok: true, answers } | { ok: false, error }
// "No such name" and "no records" are ok:true with empty answers; only a lookup that could not
// be completed is ok:false, so a network problem can never be read as "the domain has no SPF".

const DEFAULT_ENDPOINTS = ["https://cloudflare-dns.com/dns-query", "https://dns.google/resolve"];
const TYPE_CODES = { TXT: 16, MX: 15 };

function parseTxt(data) {
  const parts = [...data.matchAll(/"((?:[^"\\]|\\.)*)"/g)].map((m) => m[1].replace(/\\(.)/g, "$1"));
  return parts.length ? parts.join("") : data;
}

function parseMx(data) {
  const [priority, ...host] = data.trim().split(/\s+/);
  return { priority: Number(priority), host: host.join(" ").replace(/\.$/, "") };
}

export function createResolver({
  fetchFn = (...args) => globalThis.fetch(...args),
  endpoints = DEFAULT_ENDPOINTS,
  timeoutMs = 5000,
  maxRequests = 60,
} = {}) {
  const cache = new Map();
  let requests = 0;

  async function ask(base, name, type) {
    const controller = new AbortController();
    let timer;
    const timeout = new Promise((_, reject) => {
      timer = setTimeout(() => {
        controller.abort();
        reject(new Error("timed out"));
      }, timeoutMs);
    });
    const work = (async () => {
      const url = `${base}?name=${encodeURIComponent(name)}&type=${type}`;
      const res = await fetchFn(url, { headers: { accept: "application/dns-json" }, signal: controller.signal });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const body = await res.json();
      if (body.Status !== 0 && body.Status !== 3) throw new Error(`DNS status ${body.Status}`);
      const wanted = (body.Answer || []).filter((a) => a.type === TYPE_CODES[type]);
      return { ok: true, answers: wanted.map((a) => (type === "MX" ? parseMx(a.data) : parseTxt(a.data))) };
    })();
    try {
      return await Promise.race([work, timeout]);
    } finally {
      clearTimeout(timer);
    }
  }

  async function lookup(name, type) {
    let lastError = "no resolver configured";
    for (const base of endpoints) {
      if (requests >= maxRequests) return { ok: false, error: "Request limit reached for this check." };
      requests += 1;
      try {
        return await ask(base, name, type);
      } catch (e) {
        lastError = e.message;
      }
    }
    return { ok: false, error: `Could not reach a DNS resolver (${lastError}).` };
  }

  return (name, type) => {
    const key = `${type}:${name}`;
    if (!cache.has(key)) cache.set(key, lookup(name, type));
    return cache.get(key);
  };
}
