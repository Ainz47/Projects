import type { Product } from '../model/types';
import { hashString, paletteFor } from './palette';
import { bag, dripper, generic, grinder, kettle } from './shapes';

export type ArtKind = 'bag' | 'dripper' | 'kettle' | 'grinder' | 'generic';

export function kindFor(p: Pick<Product, 'type'>): ArtKind {
  switch (p.type) {
    case 'Coffee':
      return 'bag';
    case 'Dripper':
      return 'dripper';
    case 'Kettle':
      return 'kettle';
    case 'Grinder':
      return 'grinder';
    default:
      return 'generic';
  }
}

export function artFor(p: Pick<Product, 'handle' | 'type' | 'origin' | 'roast'>): string {
  const pal = paletteFor(p);
  const seed = hashString(p.handle);
  const gradient = `bg${seed}`;
  let inner: string;
  switch (kindFor(p)) {
    case 'bag':
      inner = bag(pal, seed, p.origin ?? 'Blend');
      break;
    case 'dripper':
      inner = dripper(pal, seed);
      break;
    case 'kettle':
      inner = kettle(pal, seed);
      break;
    case 'grinder':
      inner = grinder(pal, seed);
      break;
    default:
      inner = generic(pal, seed);
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" width="400" height="400">
<defs><linearGradient id="${gradient}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${pal.bgTop}"/><stop offset="1" stop-color="${pal.bgBottom}"/></linearGradient></defs>
<rect width="400" height="400" fill="url(#${gradient})"/>
<ellipse cx="200" cy="352" rx="112" ry="12" fill="#000" opacity="0.12"/>${inner}
</svg>`;
}

// The UI only ever shows art through <img src>, so it can never run script or load anything.
export const artDataUri = (p: Pick<Product, 'handle' | 'type' | 'origin' | 'roast'>): string =>
  `data:image/svg+xml,${encodeURIComponent(artFor(p))}`;
