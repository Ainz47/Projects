import type { Palette } from './palette';

export const escapeXml = (s: string): string =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&apos;');

// Each function returns the inner markup for a 400 x 400 canvas. `seed` varies small details only.

export function bag(pal: Palette, seed: number, origin: string): string {
  const beans = 3 + (seed % 3);
  const beanRow = Array.from({ length: beans }, (_, i) => {
    const x = 200 + (i - (beans - 1) / 2) * 22;
    return `<ellipse cx="${x}" cy="236" rx="8" ry="5.5" fill="${pal.bodyDark}" transform="rotate(${20 + ((seed + i * 37) % 50)} ${x} 236)"/>`;
  }).join('');
  const name = escapeXml(origin.toUpperCase().slice(0, 14));
  return `
<path d="M108 92 L292 92 L306 322 Q306 336 292 336 L108 336 Q94 336 94 322 Z" fill="${pal.body}"/>
<path d="M108 92 L292 92 L296 128 L104 128 Z" fill="${pal.bodyDark}"/>
<rect x="104" y="72" width="192" height="24" rx="6" fill="${pal.bodyDark}"/>
<rect x="128" y="168" width="144" height="128" rx="10" fill="${pal.label}"/>
<circle cx="200" cy="200" r="13" fill="${pal.accent}"/>
<path d="M200 187 L200 180" stroke="${pal.accent}" stroke-width="4" stroke-linecap="round"/>
${beanRow}
<text x="200" y="272" text-anchor="middle" font-family="Georgia, serif" font-size="15" letter-spacing="1" fill="${pal.ink}">${name}</text>`;
}

export function dripper(pal: Palette, seed: number): string {
  const ridges = 4 + (seed % 3);
  const lines = Array.from({ length: ridges }, (_, i) => {
    const t = i / (ridges - 1);
    return `<line x1="${112 + t * 176}" y1="126" x2="${166 + t * 68}" y2="246" stroke="${pal.gearDark}" stroke-width="3" opacity="0.35"/>`;
  }).join('');
  return `
<path d="M96 120 L304 120 L240 250 L160 250 Z" fill="${pal.gear}"/>
${lines}
<rect x="150" y="250" width="100" height="18" rx="4" fill="${pal.gearDark}"/>
<rect x="120" y="268" width="160" height="10" rx="5" fill="${pal.gearDark}"/>
<path d="M140 292 L260 292 L250 340 Q248 352 236 352 L164 352 Q152 352 150 340 Z" fill="${pal.label}"/>
<rect x="150" y="292" width="100" height="10" fill="${pal.accent}" opacity="0.8"/>`;
}

export function kettle(pal: Palette, seed: number): string {
  const knob = 8 + (seed % 3) * 2;
  return `
<path d="M120 170 Q120 150 140 150 L260 150 Q280 150 280 170 L290 300 Q290 330 260 330 L140 330 Q110 330 110 300 Z" fill="${pal.gear}"/>
<rect x="140" y="132" width="120" height="20" rx="8" fill="${pal.gearDark}"/>
<circle cx="200" cy="124" r="${knob}" fill="${pal.gearDark}"/>
<path d="M280 200 Q340 190 330 120 Q328 100 350 96" fill="none" stroke="${pal.gear}" stroke-width="14" stroke-linecap="round"/>
<path d="M112 190 Q60 200 70 270 Q76 310 112 306" fill="none" stroke="${pal.gearDark}" stroke-width="12" stroke-linecap="round"/>
<rect x="120" y="330" width="160" height="10" rx="5" fill="${pal.gearDark}"/>
<path d="M142 182 L142 300" stroke="${pal.label}" stroke-width="8" stroke-linecap="round" opacity="0.25"/>`;
}

export function grinder(pal: Palette, seed: number): string {
  const dial = (seed % 8) * 40 - 140;
  return `
<path d="M132 96 L268 96 L240 170 L160 170 Z" fill="${pal.gearDark}"/>
<rect x="146" y="80" width="108" height="16" rx="6" fill="${pal.gear}"/>
<rect x="150" y="170" width="100" height="120" rx="12" fill="${pal.gear}"/>
<rect x="128" y="290" width="144" height="34" rx="8" fill="${pal.gearDark}"/>
<path d="M250 200 L318 200" stroke="${pal.gearDark}" stroke-width="10" stroke-linecap="round"/>
<circle cx="330" cy="200" r="12" fill="${pal.gear}"/>
<circle cx="200" cy="232" r="16" fill="${pal.label}"/>
<line x1="200" y1="232" x2="200" y2="219" stroke="${pal.ink}" stroke-width="3" stroke-linecap="round" transform="rotate(${dial} 200 232)"/>`;
}

export function generic(pal: Palette, seed: number): string {
  const r = 38 + (seed % 3) * 4;
  return `
<rect x="110" y="110" width="180" height="180" rx="28" fill="${pal.gear}"/>
<circle cx="200" cy="200" r="${r}" fill="${pal.label}" opacity="0.9"/>
<circle cx="200" cy="200" r="20" fill="${pal.accent}"/>`;
}
