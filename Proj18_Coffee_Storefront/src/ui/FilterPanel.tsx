import type { Query, facets } from '../lib/catalog';
import { useUrlText } from './useUrlText';

type Facets = ReturnType<typeof facets>;

const toggle = (list: string[], value: string): string[] =>
  list.includes(value) ? list.filter((x) => x !== value) : [...list, value];

function CheckGroup(props: { legend: string; options: string[]; selected: string[]; onToggle: (value: string) => void }) {
  if (props.options.length === 0) return null;
  return (
    <fieldset className="filter-group">
      <legend>{props.legend}</legend>
      {props.options.map((option) => (
        <label key={option} className="check">
          <input type="checkbox" checked={props.selected.includes(option)} onChange={() => props.onToggle(option)} />
          <span>{option}</span>
        </label>
      ))}
    </fieldset>
  );
}

function PriceInput(props: { label: string; placeholder: string; cents: number | null; onCommit: (cents: number | null) => void }) {
  const [text, setText] = useUrlText(props.cents === null ? '' : String(props.cents / 100), (next) => {
    props.onCommit(next === '' ? null : Number(next) * 100);
  });
  return (
    <label className="price-field">
      <span>{props.label}</span>
      <input
        type="text"
        inputMode="numeric"
        value={text}
        placeholder={props.placeholder}
        onChange={(e) => setText(e.target.value.replace(/\D/g, ''))}
      />
    </label>
  );
}

export function FilterPanel({ query, facets: f, onChange }: { query: Query; facets: Facets; onChange: (q: Query) => void }) {
  return (
    <div className="filters-body">
      <CheckGroup legend="Type" options={f.types} selected={query.types} onToggle={(v) => onChange({ ...query, types: toggle(query.types, v) })} />
      <CheckGroup legend="Origin" options={f.origins} selected={query.origins} onToggle={(v) => onChange({ ...query, origins: toggle(query.origins, v) })} />
      <CheckGroup legend="Roast" options={f.roasts} selected={query.roasts} onToggle={(v) => onChange({ ...query, roasts: toggle(query.roasts, v) })} />
      <label className="check">
        <input type="checkbox" checked={query.inStockOnly} onChange={(e) => onChange({ ...query, inStockOnly: e.target.checked })} />
        <span>In stock only</span>
      </label>
      <fieldset className="filter-group">
        <legend>Price (USD)</legend>
        <PriceInput label="Min price" placeholder={String(Math.floor(f.minCents / 100))} cents={query.minCents} onCommit={(c) => onChange({ ...query, minCents: c })} />
        <PriceInput label="Max price" placeholder={String(Math.ceil(f.maxCents / 100))} cents={query.maxCents} onCommit={(c) => onChange({ ...query, maxCents: c })} />
      </fieldset>
    </div>
  );
}
