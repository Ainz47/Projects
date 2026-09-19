// Parses "k=v; k2=v2" tag lists (DMARC and DKIM records). Keys are lower-cased, values are trimmed.
export function parseTags(record) {
  const tags = {};
  for (const part of record.split(";")) {
    const i = part.indexOf("=");
    if (i > 0) tags[part.slice(0, i).trim().toLowerCase()] = part.slice(i + 1).trim();
  }
  return tags;
}
