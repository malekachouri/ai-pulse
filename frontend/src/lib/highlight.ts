export interface Segment {
  text: string;
  match: boolean;
}

/** Splits an API snippet using [[ ]] highlight markers into plain-text segments (never parsed as HTML). */
export function parseHighlights(snippet: string): Segment[] {
  const out: Segment[] = [];
  const re = /\[\[(.*?)\]\]/g;
  let last = 0;
  for (const m of snippet.matchAll(re)) {
    if (m.index > last) out.push({ text: snippet.slice(last, m.index), match: false });
    if (m[1]) out.push({ text: m[1], match: true });
    last = m.index + m[0].length;
  }
  if (last < snippet.length) out.push({ text: snippet.slice(last), match: false });
  return out;
}
