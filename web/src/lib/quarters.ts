const MONTH = ["Mar", "Jun", "Sep", "Dec"];

export function quarterIndex(q: string): number {
  const m = /^(\d{4})Q([1-4])$/.exec(q);
  if (!m) throw new Error(`bad quarter ${q}`);
  return Number(m[1]) * 4 + Number(m[2]) - 1;
}

export function quarterFromIndex(i: number): string {
  return `${Math.floor(i / 4)}Q${(i % 4) + 1}`;
}

export function addQuarters(q: string, n: number): string {
  return quarterFromIndex(quarterIndex(q) + n);
}

export function quartersBetween(start: string, end: string): string[] {
  const out: string[] = [];
  for (let i = quarterIndex(start); i <= quarterIndex(end); i++) out.push(quarterFromIndex(i));
  return out;
}

/** "2026Q3" -> "Sep 2026" (quarter-end month, as in the source analysis). */
export function quarterLabel(q: string): string {
  const i = quarterIndex(q);
  return `${MONTH[i % 4]} ${Math.floor(i / 4)}`;
}
