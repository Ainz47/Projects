import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// sw.js hand-maintains SHELL_FILES as a plain array (it runs in a service
// worker, not under Node, so it cannot import the deploy manifest). Nothing
// else keeps that list honest, and it has already gone stale once - missing
// a whole shipped feature (block-edit.js, ui/blocks.js) because the array
// was never updated when those files were added. This test catches the next
// drift: every file deploy.py would actually upload from src/ or vendor/
// must appear in SHELL_FILES, or offline use breaks on that file's import.

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const DEPLOYED_EXTENSIONS = new Set(['.html', '.js', '.css', '.json', '.svg']);
const SKIP_DIRS = new Set(['__pycache__']);

function collectDeployedNames() {
  const names = [];
  for (const [folder, prefix] of [['src', ''], ['vendor', 'vendor/']]) {
    const base = path.join(ROOT, folder);
    if (!fs.existsSync(base)) continue;
    walk(base, base, prefix, names);
  }
  return names;
}

function walk(dir, base, prefix, names) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (SKIP_DIRS.has(entry.name)) continue;
    if (entry.isDirectory()) {
      walk(full, base, prefix, names);
      continue;
    }
    if (!DEPLOYED_EXTENSIONS.has(path.extname(entry.name).toLowerCase())) continue;
    const rel = path.relative(base, full).split(path.sep).join('/');
    names.push(prefix + rel);
  }
}

function parseShellFiles() {
  const text = fs.readFileSync(path.join(ROOT, 'src', 'sw.js'), 'utf8');
  const match = text.match(/const SHELL_FILES = \[([\s\S]*?)\];/);
  assert.ok(match, 'SHELL_FILES array not found in sw.js');
  return [...match[1].matchAll(/'([^']+)'/g)].map(m => m[1]);
}

test('every deployed src/vendor file is offline-cached by sw.js', () => {
  // data/ is deploy.py tooling fodder (seed data, read by scripts/seed.py via
  // node:fs) - no browser code path ever fetches it, so it has no business
  // in the offline shell cache and isn't expected to appear in SHELL_FILES.
  const deployed = collectDeployedNames()
    .filter(n => n !== 'sw.js' && !n.startsWith('data/'));
  const cached = new Set(parseShellFiles());
  const missing = deployed.filter(n => !cached.has(n));
  assert.deepEqual(missing, []);
});

test('sw.js does not cache a file that no longer exists', () => {
  const deployed = new Set(collectDeployedNames());
  const cached = parseShellFiles();
  const stale = cached.filter(n => n !== 'sw.js' && !deployed.has(n));
  assert.deepEqual(stale, []);
});
