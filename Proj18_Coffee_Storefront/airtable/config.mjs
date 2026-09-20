// Reads the two settings the Airtable scripts need. Error text is fixed wording, never the value that was read.
export function readConfig(env = process.env) {
  const token = (env.AIRTABLE_TOKEN ?? '').trim();
  const baseId = (env.AIRTABLE_BASE_ID ?? '').trim();
  if (!token) {
    throw new Error('AIRTABLE_TOKEN is not set. Put it in Proj18_Coffee_Storefront/.env.local (see the README).');
  }
  if (!/^app[A-Za-z0-9]{14}$/.test(baseId)) {
    throw new Error('AIRTABLE_BASE_ID is missing or is not a base id (it is "app" followed by 14 letters and digits).');
  }
  return { token, baseId };
}
