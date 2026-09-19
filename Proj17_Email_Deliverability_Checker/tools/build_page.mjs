// Builds docs/deliverability/index.html from the tested modules in code/.
// The modules are ordinary ES modules so node can test them; the page needs one inline script, so
// this merges them in dependency order. It accepts only the simple import/export forms the modules
// use and fails loudly on anything else, rather than guessing.
//
//   node tools/build_page.mjs        write the page
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..");
export const PAGE_PATH = join(ROOT, "..", "docs", "deliverability", "index.html");
const TEMPLATE_PATH = join(HERE, "page.template.html");
const MARKER = "/*__LOGIC__*/";

// Dependency order: a module may only import ones listed before it.
export const ORDER = ["domain", "result", "tags", "dns", "spf", "dkim", "dmarc", "mx", "report"];

// Read as LF so the output is the same on Windows (CRLF checkouts) and elsewhere.
const read = (path) => readFileSync(path, "utf8").replace(/\r\n/g, "\n");

export function loadModules() {
  return ORDER.map((name) => ({ name, source: read(join(ROOT, "code", `${name}.js`)) }));
}

export function buildLogic(modules = loadModules()) {
  const names = modules.map((m) => m.name);
  const declaredIn = new Map();
  const chunks = [];

  modules.forEach(({ name, source }, index) => {
    const file = `${name}.js`;
    const out = [];
    for (const line of source.split("\n")) {
      if (/^\s*import\b/.test(line)) {
        const m = /^import \{[^}]*\} from "\.\/([a-z]+)\.js";$/.exec(line);
        if (!m) throw new Error(`${file}: unsupported import line: ${line}`);
        if (!names.slice(0, index).includes(m[1])) throw new Error(`${file}: imports ${m[1]}, which is not built earlier`);
        continue;
      }
      let kept = line;
      if (/^export\b/.test(line)) {
        if (!/^export (async function|function|const) /.test(line)) throw new Error(`${file}: unsupported export line: ${line}`);
        kept = line.replace(/^export /, "");
      }
      const decl = /^(?:async function|function|const|let|class) ([A-Za-z_$][\w$]*)/.exec(kept);
      if (decl) {
        if (declaredIn.has(decl[1])) throw new Error(`${file}: ${decl[1]} is already declared in ${declaredIn.get(decl[1])}`);
        declaredIn.set(decl[1], file);
      }
      out.push(kept);
    }
    chunks.push(`// ---- ${file} ----\n${out.join("\n").trim()}\n`);
  });

  const logic = chunks.join("\n");
  if (logic.includes("</script")) throw new Error("the merged logic contains </script, which would end the inline script");
  return logic;
}

export function buildPage() {
  const template = read(TEMPLATE_PATH);
  if (template.split(MARKER).length !== 2) throw new Error(`the template must contain ${MARKER} exactly once`);
  return template.replace(MARKER, () => buildLogic());
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  mkdirSync(dirname(PAGE_PATH), { recursive: true });
  writeFileSync(PAGE_PATH, buildPage());
  console.log(`wrote ${PAGE_PATH}`);
}
