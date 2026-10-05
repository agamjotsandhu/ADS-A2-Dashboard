import { fiveYearGrowth, forecastAt, type SuburbForecast } from "../lib/forecasts";
import { fmtDollars, fmtPct } from "../lib/format";

function Rows({ title, items, onPick }: { title: string; items: SuburbForecast[]; onPick: (s: string) => void }) {
  return (
    <div className="table-scroll">
      <table>
        <caption className="label" style={{ textAlign: "left", paddingBottom: 6 }}>{title}</caption>
        <thead>
          <tr><th>Suburb</th><th className="num">Sep 2026</th><th className="num">Sep 2031</th><th className="num">Growth</th></tr>
        </thead>
        <tbody>
          {items.map((s) => (
            <tr key={s.suburb}>
              <td>
                <button type="button" className="linklike" onClick={() => onPick(s.suburb)}
                  style={{ background: "none", border: 0, padding: 0, color: "var(--accent)", cursor: "pointer", font: "inherit", textAlign: "left" }}>
                  {s.suburb}
                </button>
              </td>
              <td className="num">{fmtDollars(forecastAt(s, 4))}</td>
              <td className="num">{fmtDollars(forecastAt(s, 24))}</td>
              <td className="num">{fmtPct(fiveYearGrowth(s))}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function GrowthTable({ top, bottom, onPick }: { top: SuburbForecast[]; bottom: SuburbForecast[]; onPick: (s: string) => void }) {
  return (
    <div>
      <h3>Highest and lowest forecast growth</h3>
      <p className="subtle small">
        Growth is forecast Sep 2031 over forecast Sep 2026, as in the original analysis. These are point forecasts with wide
        intervals, so treat rankings as indicative.
      </p>
      <div className="two-col">
        <Rows title="Top 10" items={top} onPick={onPick} />
        <Rows title="Bottom 10" items={bottom} onPick={onPick} />
      </div>
    </div>
  );
}
