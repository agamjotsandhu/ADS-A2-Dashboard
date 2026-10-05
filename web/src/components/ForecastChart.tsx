import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { chartRows, lastHistoryQuarter, type SuburbForecast } from "../lib/forecasts";
import { fmtDollars } from "../lib/format";
import { quarterLabel } from "../lib/quarters";
import { ChartTooltip, range } from "./ChartTooltip";

const AXIS_TICK = { fill: "var(--muted)", fontSize: 12 };

export function ForecastChart({ data }: { data: SuburbForecast }) {
  const rows = chartRows(data);
  const base = lastHistoryQuarter(data);
  const ticks = rows.map((r) => r.quarter).filter((q) => q.endsWith("Q1") && Number(q.slice(0, 4)) % 5 === 0);

  return (
    <figure style={{ margin: 0 }}>
      <figcaption className="visually-hidden">
        Median weekly rent for {data.suburb}: history from {quarterLabel(data.history.start)} to {quarterLabel(base)}, and an
        ARIMA forecast to {quarterLabel(rows[rows.length - 1].quarter)} with a 95% interval. A data table follows the chart.
      </figcaption>
      <div className="legend" aria-hidden="true">
        <span><i className="key-line" style={{ background: "var(--series-1)" }} />Actual median</span>
        <span><i className="key-line" style={{ background: "var(--series-2)" }} />Forecast</span>
        <span><i className="key-band" style={{ background: "var(--band)" }} />95% interval</span>
        <span><i className="key-marker" />Forecast start</span>
      </div>
      <div className="chart-wrap">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
            <CartesianGrid stroke="var(--grid)" vertical={false} />
            <XAxis dataKey="quarter" ticks={ticks} tickFormatter={(q: string) => q.slice(0, 4)} tick={AXIS_TICK}
              stroke="var(--axis)" tickLine={false} />
            <YAxis tickFormatter={(v: number) => fmtDollars(v)} tick={AXIS_TICK} stroke="var(--axis)" width={64}
              tickLine={false} axisLine={false} domain={["auto", "auto"]} />
            <Tooltip
              cursor={{ stroke: "var(--muted)", strokeWidth: 1 }}
              content={<ChartTooltip rows={(d) => [
                d.history !== undefined && { key: "h", label: "actual", color: "var(--series-1)", value: fmtDollars(d.history as number) },
                d.forecast !== undefined && d.history === undefined && { key: "f", label: "forecast", color: "var(--series-2)", value: fmtDollars(d.forecast as number) },
                d.history === undefined && range(d.band) && { key: "b", label: "95% interval", color: "var(--band)", value: range(d.band) as string },
              ].filter(Boolean) as never} />}
            />
            <Area dataKey="band" stroke="none" fill="var(--band)" fillOpacity={1} isAnimationActive={false} activeDot={false} />
            <ReferenceLine x={base} stroke="var(--muted)" strokeWidth={1} />
            <Line dataKey="history" stroke="var(--series-1)" strokeWidth={2} dot={false} isAnimationActive={false}
              activeDot={{ r: 4, stroke: "var(--surface)", strokeWidth: 2 }} />
            <Line dataKey="forecast" stroke="var(--series-2)" strokeWidth={2} dot={false} isAnimationActive={false}
              activeDot={{ r: 4, stroke: "var(--surface)", strokeWidth: 2 }} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <details>
        <summary>Show forecast as a table</summary>
        <div className="table-scroll">
          <table>
            <thead>
              <tr><th>Quarter</th><th className="num">Forecast</th><th className="num">Lower 95%</th><th className="num">Upper 95%</th></tr>
            </thead>
            <tbody>
              {data.forecast.mean.map((m, i) => (
                <tr key={i}>
                  <td>{quarterLabel(rows[data.history.values.length + i].quarter)}</td>
                  <td className="num">{fmtDollars(m)}</td>
                  <td className="num">{fmtDollars(data.forecast.lower95[i])}</td>
                  <td className="num">{fmtDollars(data.forecast.upper95[i])}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}
