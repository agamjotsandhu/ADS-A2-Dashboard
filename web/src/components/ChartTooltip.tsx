import { fmtDollars } from "../lib/format";
import { quarterLabel } from "../lib/quarters";

export interface TooltipRow {
  key: string;
  label: string;
  color: string;
  value: string;
}

interface Props {
  active?: boolean;
  label?: string;
  payload?: { dataKey?: unknown; value?: unknown }[];
  rows: (payload: Record<string, unknown>) => TooltipRow[];
}

/** One tooltip listing every series at the hovered quarter; values lead, labels follow. */
export function ChartTooltip({ active, label, payload, rows }: Props) {
  if (!active || !payload?.length || !label) return null;
  const datum = (payload[0] as { payload?: Record<string, unknown> }).payload ?? {};
  const items = rows(datum);
  if (!items.length) return null;
  return (
    <div className="tooltip" role="status">
      <div className="t-title">{quarterLabel(label)}</div>
      {items.map((r) => (
        <div className="t-row" key={r.key}>
          <span className="key-line" style={{ background: r.color }} aria-hidden="true" />
          <strong>{r.value}</strong>
          <span className="subtle">{r.label}</span>
        </div>
      ))}
    </div>
  );
}

export const range = (b: unknown): string | null =>
  Array.isArray(b) && b.length === 2 ? `${fmtDollars(b[0] as number)} to ${fmtDollars(b[1] as number)}` : null;
