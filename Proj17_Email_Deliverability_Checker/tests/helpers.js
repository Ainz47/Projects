// A fake resolver for the check tests. Keys look like "TXT:example.com".
// An Error value makes that lookup fail; a missing key is a successful lookup with no records.
export function fakeDns(table) {
  const fn = async (name, type) => {
    fn.calls.push(`${type}:${name}`);
    const v = table[`${type}:${name}`];
    if (v instanceof Error) return { ok: false, error: v.message };
    return { ok: true, answers: v || [] };
  };
  fn.calls = [];
  return fn;
}
