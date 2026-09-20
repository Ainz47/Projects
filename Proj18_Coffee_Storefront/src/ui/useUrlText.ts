import { useEffect, useRef, useState } from 'react';

// A text field whose value also lives in the URL. It keeps its own text so typing never fights the
// URL round trip (which would drop characters or jump the caret), and only takes the URL's value
// when the URL changed from outside, for example the back button.
export function useUrlText(value: string, commit: (next: string) => void): [string, (next: string) => void] {
  const [text, setText] = useState(value);
  const synced = useRef(value);
  useEffect(() => {
    if (value !== synced.current) {
      synced.current = value;
      setText(value);
    }
  }, [value]);
  return [
    text,
    (next) => {
      setText(next);
      synced.current = next;
      commit(next);
    },
  ];
}
