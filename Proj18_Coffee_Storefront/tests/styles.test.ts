import { readdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

// Resolved from the project root: under jsdom the global URL is not the one node's fs accepts.
const dir = resolve(process.cwd(), 'src/styles');
const files = readdirSync(dir).filter((f) => f.endsWith('.css')).sort();
const all = files.map((f) => readFileSync(resolve(dir, f), 'utf8')).join('\n');

function keyframeBodies(css: string): string[] {
  const bodies: string[] = [];
  const start = /@keyframes\s+[\w-]+\s*\{/g;
  let m: RegExpExecArray | null;
  while ((m = start.exec(css))) {
    let depth = 1;
    let i = start.lastIndex;
    while (i < css.length && depth > 0) {
      if (css[i] === '{') depth += 1;
      else if (css[i] === '}') depth -= 1;
      i += 1;
    }
    bodies.push(css.slice(start.lastIndex, i - 1));
  }
  return bodies;
}

test('all the stylesheets are present', () => {
  expect(files).toEqual(['base.css', 'components.css', 'index.css', 'layout.css', 'motion.css', 'tokens.css']);
});

test('keyframes animate only transform and opacity', () => {
  const bodies = keyframeBodies(all);
  expect(bodies.length).toBeGreaterThan(0);
  for (const body of bodies) {
    const props = [...body.matchAll(/([a-z-]+)\s*:/g)].map((m) => m[1]);
    expect(props.length).toBeGreaterThan(0);
    for (const prop of props) expect(['transform', 'opacity']).toContain(prop);
  }
});

test('transitions name only transform or opacity, never all', () => {
  const values = [...all.matchAll(/\btransition(?:-property)?\s*:\s*([^;}]+)/g)].map((m) => m[1]!);
  expect(values.length).toBeGreaterThan(0);
  for (const value of values) {
    for (const part of value.split(',')) {
      expect(['transform', 'opacity', 'none']).toContain(part.trim().split(/\s+/)[0]);
    }
  }
});

test('no animation or transition is longer than 300ms', () => {
  const values = [...all.matchAll(/\b(?:transition|animation)(?:-duration)?\s*:\s*([^;}]+)/g)].map((m) => m[1]!);
  for (const value of values) {
    for (const [, n, unit] of value.matchAll(/(\d*\.?\d+)(ms|s)\b/g)) {
      const ms = unit === 's' ? Number(n) * 1000 : Number(n);
      expect(ms).toBeLessThanOrEqual(300);
    }
  }
});

test('reduced motion is honoured', () => {
  expect(all).toMatch(/@media\s*\(prefers-reduced-motion:\s*reduce\)/);
});

test('the styles load nothing from the network', () => {
  expect(all).not.toMatch(/url\(\s*["']?(?:https?:)?\/\//i);
  expect(all).not.toMatch(/@import\s+url|@font-face/i);
});
