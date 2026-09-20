import type { Product, Variant } from '../model/types';

export type Selection = Record<string, string>;

export function defaultSelection(p: Product): Selection {
  const v = p.variants.find((x) => x.available) ?? p.variants[0]!;
  return { ...v.options };
}

export function pickVariant(p: Product, sel: Selection): Variant | undefined {
  return p.variants.find((v) => p.optionNames.every((n) => v.options[n] === sel[n]));
}

// Is there an in-stock variant with this option value, given the other current choices?
export function isValueAvailable(p: Product, sel: Selection, optionName: string, value: string): boolean {
  return p.variants.some(
    (v) =>
      v.available &&
      v.options[optionName] === value &&
      p.optionNames.every((n) => n === optionName || v.options[n] === sel[n]),
  );
}
