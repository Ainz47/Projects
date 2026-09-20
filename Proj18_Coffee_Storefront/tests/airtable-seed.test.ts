import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { runSeed } from '../airtable/seed.mjs';

const nodes = JSON.parse(readFileSync(resolve(process.cwd(), 'data/catalog.fixture.json'), 'utf8')).data.products.nodes as any[];

type Existing = Record<string, unknown[]>;

// A stand-in for the Airtable client that records what the seed asks for.
function fakeClient({ tables = [] as any[], existing = {} as Existing, reverse = false } = {}) {
  const calls: string[] = [];
  const specs: any[] = [];
  const created: Record<string, any[]> = {};
  return {
    calls,
    specs,
    created,
    listTables: async () => tables,
    createTable: async (spec: any) => {
      calls.push(`createTable ${spec.name}`);
      specs.push(spec);
      return { id: `tbl_${spec.name}`, name: spec.name };
    },
    listAll: async (name: string) => existing[name] ?? [],
    createRecords: async (name: string, list: any[]) => {
      calls.push(`createRecords ${name} ${list.length}`);
      created[name] = list;
      const recs = list.map((fields, i) => ({ id: `rec_${name}_${i}`, fields }));
      return reverse ? [...recs].reverse() : recs;
    },
  };
}

test('creates Products then Variants, links Variants to the new Products table, and loads every row', async () => {
  const client = fakeClient();
  const result = await runSeed({ client, nodes });
  expect(client.calls.slice(0, 2)).toEqual(['createTable Products', 'createTable Variants']);
  expect(client.calls.slice(2)).toEqual(['createRecords Products 30', 'createRecords Variants 124']);
  const link = client.specs[1].fields.find((f: any) => f.name === 'Product');
  expect(link.options.linkedTableId).toBe('tbl_Products');
  expect(result).toEqual({ products: 30, variants: 124 });
});

test('links each variant to its own product even if Airtable returns the created records in another order', async () => {
  const client = fakeClient({ reverse: true });
  await runSeed({ client, nodes });
  const expected = nodes.flatMap((n, i) => n.variants.nodes.map(() => [`rec_Products_${i}`]));
  expect(client.created.Variants!.map((f) => f.Product)).toEqual(expected);
});

test('leaves tables that already exist alone', async () => {
  const client = fakeClient({ tables: [{ id: 'tblP', name: 'Products' }, { id: 'tblV', name: 'Variants' }] });
  await runSeed({ client, nodes });
  expect(client.calls.some((c) => c.startsWith('createTable'))).toBe(false);
});

test('refuses to write into a table that already holds rows, and writes nothing', async () => {
  const client = fakeClient({
    tables: [{ id: 'tblP', name: 'Products' }],
    existing: { Products: [{ id: 'recX', fields: {} }] },
  });
  await expect(runSeed({ client, nodes })).rejects.toThrow(/Products already has 1 record/);
  expect(client.calls.some((c) => c.startsWith('createRecords'))).toBe(false);
});

test('writes into a non-empty table when told to', async () => {
  const client = fakeClient({
    tables: [{ id: 'tblP', name: 'Products' }],
    existing: { Products: [{ id: 'recX', fields: {} }] },
  });
  const result = await runSeed({ client, nodes, allowExisting: true });
  expect(result.products).toBe(30);
});

test('reports progress through the log callback', async () => {
  const lines: string[] = [];
  await runSeed({ client: fakeClient(), nodes, log: (line: string) => lines.push(line) });
  expect(lines).toContain('Products: table created');
  expect(lines).toContain('Variants: table created');
});
