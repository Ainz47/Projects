import { useUrlText } from './useUrlText';

export function SearchBox({ value, onChange }: { value: string; onChange: (q: string) => void }) {
  const [text, setText] = useUrlText(value, onChange);
  return (
    <div className="search">
      <label htmlFor="search-input" className="sr-only">
        Search products
      </label>
      <input
        id="search-input"
        type="search"
        value={text}
        placeholder="Search coffee and gear"
        autoComplete="off"
        onChange={(e) => setText(e.target.value)}
      />
    </div>
  );
}
