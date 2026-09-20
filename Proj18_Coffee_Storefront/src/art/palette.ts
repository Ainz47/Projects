export interface Palette {
  bgTop: string;
  bgBottom: string;
  body: string;
  bodyDark: string;
  gear: string;
  gearDark: string;
  label: string;
  ink: string;
  accent: string;
}

// FNV-1a: tiny, deterministic, plenty good enough to seed decoration.
export function hashString(s: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i += 1) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

// Roast picks the bag colour; origin (or handle, for gear) picks the hue of everything else.
const ROAST_BODY: Record<string, [string, string]> = {
  Light: ['#d9b77e', '#b98f52'],
  Medium: ['#a8703f', '#824f27'],
  Dark: ['#4d3323', '#33200f'],
};
const NEUTRAL_BODY: [string, string] = ['#8d9a94', '#6b7a73'];

export function paletteFor(p: { origin: string | null; roast: string | null; handle: string }): Palette {
  const [body, bodyDark] = ROAST_BODY[p.roast ?? ''] ?? NEUTRAL_BODY;
  const hue = hashString(p.origin ?? p.handle) % 360;
  return {
    bgTop: `hsl(${hue} 38% 90%)`,
    bgBottom: `hsl(${(hue + 24) % 360} 34% 80%)`,
    body,
    bodyDark,
    gear: `hsl(${hue} 30% 34%)`,
    gearDark: `hsl(${hue} 30% 22%)`,
    label: '#f7f1e6',
    ink: '#2a1f17',
    accent: `hsl(${hue} 52% 34%)`,
  };
}
