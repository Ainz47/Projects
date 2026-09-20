import { readFileSync } from 'node:fs';
import { join } from 'node:path';

// The workflow sits at the repo root, one level above the project. It is read as text: these tests pin the
// properties that keep a token safe in a public repo, so an edit that breaks one fails here first.
const workflow = readFileSync(join(process.cwd(), '..', '.github', 'workflows', 'refresh-catalog.yml'), 'utf8').replace(/\r\n/g, '\n');
const lines = workflow.split('\n');
const at = (s: string) => workflow.indexOf(s);

test('only someone with write access to the repo can start it', () => {
  expect(workflow).toMatch(/^ {2}workflow_dispatch:/m);
  expect(workflow).toMatch(/^ {2}repository_dispatch:\n {4}types: \[catalog-refresh\]/m);
  // Nothing a fork's pull request, an outside push or a comment could use to reach the secrets.
  expect(workflow).not.toMatch(/pull_request|^ {2}push:|issue_comment|workflow_run/m);
});

test('the Airtable secrets appear once each, as environment variables', () => {
  // A real reference is a ${{ secrets.NAME }} expression; a comment may still say the word "secrets".
  const uses = lines.filter((l) => /\$\{\{\s*secrets\./.test(l)).map((l) => l.trim()).sort();
  expect(uses).toEqual([
    'AIRTABLE_BASE_ID: ${{ secrets.AIRTABLE_BASE_ID }}',
    'AIRTABLE_TOKEN: ${{ secrets.AIRTABLE_TOKEN }}',
  ]);
  const mentions = lines.filter((l) => l.includes('AIRTABLE_')).map((l) => l.trim()).sort();
  expect(mentions).toEqual(uses);
});

test('nothing prints or dumps the environment', () => {
  expect(workflow).not.toMatch(/printenv|Write-Host|Write-Output|set -x|ACTIONS_(STEP|RUNNER)_DEBUG/);
});

test('the job can write repository contents and nothing else', () => {
  expect(workflow).toMatch(/^permissions:\n {2}contents: write\n/m);
  expect(workflow).not.toMatch(/write-all/);
});

test('refreshes queue up instead of cancelling each other', () => {
  expect(workflow).toMatch(/^concurrency:\n {2}group: refresh-catalog\n {2}cancel-in-progress: false\n/m);
});

test('only the snapshot and the built page are ever committed', () => {
  const adds = lines.filter((l) => /git add/.test(l)).map((l) => l.trim());
  expect(adds).toEqual(['git add data/catalog.export.json ../docs/coffee-store']);
});

test('it exports first, checks next, and commits last', () => {
  expect(at('node airtable/cli.mjs')).toBeGreaterThan(-1);
  expect(at('node airtable/cli.mjs')).toBeLessThan(at('npm run typecheck'));
  expect(at('npm run typecheck')).toBeLessThan(at('npm test'));
  expect(at('npm test')).toBeLessThan(at('npm run build'));
  expect(at('npm run build')).toBeLessThan(at('git commit'));
});

test('it runs on the same OS as the CI check the committed page must pass', () => {
  expect(workflow).toMatch(/runs-on: windows-latest/);
});

test('no em dash and no token-shaped text', () => {
  expect(workflow.includes(String.fromCharCode(0x2014))).toBe(false);
  expect(workflow).not.toMatch(/pat[A-Za-z0-9]{14}\.[0-9a-f]{64}/);
});
