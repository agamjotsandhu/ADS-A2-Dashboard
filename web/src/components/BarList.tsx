import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export interface BarDatum {
  label: string;
  value: number;
  /** Text shown at the bar tip and in the tooltip. */
  display: string;
  detail?: string;
}

const AXIS_TICK = { fill: "var(--ink-2)", fontSize: 13 };

function Tip({ active, payload }: { active?: boolean; payload?: { payload: BarDatum }[] }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="tooltip" role="status">
      <div className="t-row"><strong>{d.display}</strong><span className="subtle">{d.label}</span></div>
      {d.detail && <div className="subtle">{d.detail}</div>}
    </div>
  );
}

/** Horizontal single-series bar chart with values at the bar tips, plus a hidden table. */
export function BarList({ data, max, title, labelWidth = 130 }: { data: BarDatum[]; max?: number; title: string; labelWidth?: number }) {
  const height = data.length * 36 + 16;
  return (
    <figure style={{ margin: 0 }}>
      <div style={{ width: "100%", height }} aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 4, right: 56, bottom: 4, left: 0 }} barCategoryGap={8}>
            <CartesianGrid stroke="var(--grid)" horizontal={false} />
            <XAxis type="number" domain={[0, max ?? "dataMax"]} hide />
            <YAxis type="category" dataKey="label" width={labelWidth} tick={AXIS_TICK} tickLine={false} axisLine={{ stroke: "var(--axis)" }} />
            <Tooltip cursor={{ fill: "var(--surface-2)" }} content={<Tip />} />
            <Bar dataKey="value" fill="var(--series-1)" barSize={20} radius={[0, 4, 4, 0]} isAnimationActive={false}>
              <LabelList dataKey="display" position="right" style={{ fill: "var(--ink)", fontSize: 13 }} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <table className="visually-hidden">
        <caption>{title}</caption>
        <tbody>
          {data.map((d) => (
            <tr key={d.label}><th scope="row">{d.label}</th><td>{d.display}{d.detail ? ` (${d.detail})` : ""}</td></tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
