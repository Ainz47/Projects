import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

// The project root: `npm test` runs from it, and under jsdom the global URL is not the one node's fs accepts.
const root = process.cwd();
const walk = (dir: string): string[] =>
  readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    return statSync(p).isDirectory() ? walk(p) : [p];
  });
const read = (files: string[]) => files.filter(existsSync).map((f) => ({ f, s: readFileSync(f, 'utf8') }));

const srcFiles = walk(join(root, 'src'));
const written = [...srcFiles, ...walk(join(root, 'exporter')), ...walk(join(root, 'airtable')), ...walk(join(root, 'tools')),
  ...walk(join(root, 'data')), join(root, 'README.md'), join(root, 'AUDIT.md'), join(root, 'index.html')];

test('no em dashes in source, data or docs', () => {
  for (const { f, s } of read(written)) expect(s.includes(String.fromCharCode(0x2014)), f).toBe(false);
});

test('nothing writes HTML from strings', () => {
  for (const { f, s } of read(srcFiles)) {
    expect(s, f).not.toMatch(/dangerouslySetInnerHTML|innerHTML|outerHTML|insertAdjacentHTML|document\.write/);
  }
});

test('the only runtime dependencies are react and react-dom', () => {
  const pkg = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8'));
  expect(Object.keys(pkg.dependencies).sort()).toEqual(['react', 'react-dom']);
});

test('no exporter or seed CLI ever prints or writes the access token', () => {
  for (const file of ['exporter/cli.mjs', 'airtable/cli.mjs', 'airtable/seed-cli.mjs']) {
    const cli = readFileSync(join(root, file), 'utf8');
    for (const line of cli.split('\n').filter((l) => /console\.|writeFileSync/.test(l))) {
      expect(line, file).not.toMatch(/token|secret/i);
    }
  }
});

test('the file that holds the Airtable token is gitignored', () => {
  expect(readFileSync(join(root, '.gitignore'), 'utf8')).toMatch(/^\.env\.local$/m);
});

test('no file in the project holds an Airtable token', () => {
  // A personal access token is "pat", 14 characters, a dot, then 64 hex characters.
  for (const { f, s } of read(written)) expect(s, f).not.toMatch(/pat[A-Za-z0-9]{14}\.[0-9a-f]{64}/);
});
