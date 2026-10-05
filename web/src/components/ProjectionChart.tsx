import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ProjectionPoint } from "../lib/api";
import { fmtDollars } from "../lib/format";
import { quarterLabel } from "../lib/quarters";
import { ChartTooltip, range } from "./ChartTooltip";

const AXIS_TICK = { fill: "var(--muted)", fontSize: 12 };

export function ProjectionChart({ points }: { points: ProjectionPoint[] }) {
  const rows = points.map((p) => ({ quarter: p.quarter, point: p.point, band: [p.lower, p.upper] as [number, number] }));
  return (
    <figure style={{ margin: 0 }}>
      <figcaption className="visually-hidden">
        Projected weekly rent from {quarterLabel(points[0].quarter)} to {quarterLabel(points[points.length - 1].quarter)} with a combined range.
      </figcaption>
      <div className="legend" aria-hidden="true">
        <span><i className="key-line" style={{ background: "var(--series-1)" }} />Projected estimate</span>
        <span><i className="key-band" style={{ background: "var(--band-2)" }} />Combined range</span>
      </div>
      <div className="chart-wrap small">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
            <CartesianGrid stroke="var(--grid)" vertical={false} />
            <XAxis dataKey="quarter" tickFormatter={quarterLabel} tick={AXIS_TICK} stroke="var(--axis)" tickLine={false}
              interval="preserveStartEnd" minTickGap={24} />
            <YAxis tickFormatter={(v: number) => fmtDollars(v)} tick={AXIS_TICK} stroke="var(--axis)" width={64}
              tickLine={false} axisLine={false} domain={["auto", "auto"]} />
            <Tooltip cursor={{ stroke: "var(--muted)", strokeWidth: 1 }}
              content={<ChartTooltip rows={(d) => [
                { key: "p", label: "estimate", color: "var(--series-1)", value: fmtDollars(d.point as number) },
                { key: "b", label: "range", color: "var(--band-2)", value: range(d.band) as string },
              ]} />} />
            <Area dataKey="band" stroke="none" fill="var(--band-2)" fillOpacity={1} isAnimationActive={false} activeDot={false} />
            <Line dataKey="point" stroke="var(--series-1)" strokeWidth={2} isAnimationActive={false}
              dot={rows.length <= 2 ? { r: 4, fill: "var(--series-1)", stroke: "var(--surface)", strokeWidth: 2 } : false}
              activeDot={{ r: 4, stroke: "var(--surface)", strokeWidth: 2 }} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <details>
        <summary>Show projection as a table</summary>
        <div className="table-scroll">
          <table>
            <thead><tr><th>Quarter</th><th className="num">Estimate</th><th className="num">Low</th><th className="num">High</th></tr></thead>
            <tbody>
              {points.map((p) => (
                <tr key={p.quarter}>
                  <td>{quarterLabel(p.quarter)}</td>
                  <td className="num">{fmtDollars(p.point)}</td>
                  <td className="num">{fmtDollars(p.lower)}</td>
                  <td className="num">{fmtDollars(p.upper)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}
