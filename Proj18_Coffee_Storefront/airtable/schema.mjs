// The two Airtable tables the storefront reads, in one place. The seed creates them from these specs and the
// mapper reads records by these names, so renaming a column in Airtable breaks the export on purpose.
export const PRODUCTS = 'Products';
export const VARIANTS = 'Variants';

// Products columns.
export const P = {
  title: 'Title',
  handle: 'Handle',
  description: 'Description',
  vendor: 'Vendor',
  type: 'Type',
  tags: 'Tags',
  origin: 'Origin',
  roast: 'Roast',
  option1Name: 'Option 1 Name',
  option2Name: 'Option 2 Name',
  position: 'Position',
};

// Variants columns. Each variant row links to exactly one product.
export const V = {
  sku: 'SKU',
  product: 'Product',
  option1: 'Option 1',
  option2: 'Option 2',
  price: 'Price',
  stock: 'Stock',
  position: 'Position',
};

const text = (name) => ({ name, type: 'singleLineText' });
const whole = (name) => ({ name, type: 'number', options: { precision: 0 } });

export function productsTableSpec() {
  return {
    name: PRODUCTS,
    description: 'Storefront products. One row per product; its variants live in the Variants table.',
    fields: [
      text(P.title), // the first field becomes the table's primary field
      text(P.handle),
      { name: P.description, type: 'multilineText' },
      text(P.vendor),
      text(P.type),
      text(P.tags),
      text(P.origin),
      text(P.roast),
      text(P.option1Name),
      text(P.option2Name),
      whole(P.position),
    ],
  };
}

export function variantsTableSpec(productsTableId) {
  return {
    name: VARIANTS,
    description: 'One row per purchasable combination of a product. Price and Stock are per variant.',
    fields: [
      text(V.sku), // primary field
      { name: V.product, type: 'multipleRecordLinks', options: { linkedTableId: productsTableId } },
      text(V.option1),
      text(V.option2),
      { name: V.price, type: 'number', options: { precision: 2 } },
      whole(V.stock),
      whole(V.position),
    ],
  };
}
