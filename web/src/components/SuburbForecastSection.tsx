import { useEffect, useMemo, useState } from "react";
import {
  currentMedian, fiveYearGrowth, forecastAt, loadForecasts, rankByGrowth, type ForecastFile,
} from "../lib/forecasts";
import { fmtDollars, fmtPct } from "../lib/format";
import { ForecastChart } from "./ForecastChart";
import { GrowthTable } from "./GrowthTable";
import { SuburbPicker } from "./SuburbPicker";

type State = { status: "loading" } | { status: "missing" } | { status: "error"; message: string } | { status: "ready"; file: ForecastFile };

export function SuburbForecastSection({ loader = loadForecasts }: { loader?: () => Promise<ForecastFile | null> }) {
  const [state, setState] = useState<State>({ status: "loading" });
  const [suburb, setSuburb] = useState("");

  useEffect(() => {
    let live = true;
    loader()
      .then((file) => {
        if (!live) return;
        if (!file || !Object.keys(file.suburbs).length) return setState({ status: "missing" });
        setState({ status: "ready", file });
        const names = Object.keys(file.suburbs).sort();
        setSuburb((s) => s || (file.suburbs["Melbourne"] ? "Melbourne" : names[0]));
      })
      .catch((e: Error) => live && setState({ status: "error", message: e.message }));
    return () => {
      live = false;
    };
  }, [loader]);

  const options = useMemo(
    () => (state.status === "ready" ? Object.keys(state.file.suburbs).sort().map((s) => ({ value: s, label: s })) : []),
    [state],
  );
  const ranked = useMemo(() => (state.status === "ready" ? rankByGrowth(state.file) : null), [state]);

  return (
    <section className="card" aria-labelledby="suburb-forecast-h">
      <div className="section-head">
        <h2 id="suburb-forecast-h">Suburb median rent forecast</h2>
        <p className="subtle">Quarterly median weekly rent, history and a six-year ARIMA forecast with a 95% interval.</p>
      </div>

      {state.status === "loading" && <p className="empty" role="status">Loading suburb forecasts…</p>}
      {state.status === "error" && <div className="notice error" role="alert"><strong>Couldn't load forecasts.</strong>{state.message}</div>}
      {state.status === "missing" && (
        <div className="notice info" role="status">
          <strong>Suburb forecasts aren't published yet.</strong>
          The quarterly suburb rent data behind this section hasn't been loaded. The property estimator below still works, at
          the Sep 2025 rent level.
        </div>
      )}

      {state.status === "ready" && (
        <>
          {state.file.meta.SYNTHETIC && (
            <div className="notice error" role="alert"><strong>Demo data.</strong>{state.file.meta.SYNTHETIC}</div>
          )}
          <div style={{ maxWidth: 420 }}>
            <SuburbPicker label="Suburb" options={options} value={suburb} onChange={setSuburb}
              hint={`${options.length} suburbs or suburb groups (DFFH rental report areas).`} />
          </div>
          {state.file.suburbs[suburb] && <SuburbDetail file={state.file} name={suburb} />}
          {ranked && <GrowthTable top={ranked.top} bottom={ranked.bottom} onPick={setSuburb} />}
        </>
      )}
    </section>
  );
}

function SuburbDetail({ file, name }: { file: ForecastFile; name: string }) {
  const s = file.suburbs[name];
  const mape = s.backtest_mape;
  return (
    <div>
      <div className="stats">
        <div className="stat"><span className="label">Median now (Sep 2025)</span><span className="value">{fmtDollars(currentMedian(s))}</span><span className="note">per week, actual</span></div>
        <div className="stat"><span className="label">Forecast Sep 2026</span><span className="value">{fmtDollars(forecastAt(s, 4))}</span><span className="note">{fmtDollars(s.forecast.lower95[3])} to {fmtDollars(s.forecast.upper95[3])}</span></div>
        <div className="stat"><span className="label">Forecast Sep 2031</span><span className="value">{fmtDollars(forecastAt(s, 24))}</span><span className="note">{fmtDollars(s.forecast.lower95[23])} to {fmtDollars(s.forecast.upper95[23])}</span></div>
        <div className="stat"><span className="label">5-year growth</span><span className="value">{fmtPct(fiveYearGrowth(s))}</span><span className="note">Sep 2026 to Sep 2031 forecast</span></div>
      </div>
      <ForecastChart data={s} />
      <p className="subtle small" style={{ marginTop: 12 }}>
        Model: <strong>{s.model}</strong> on log rent with a trend break at {s.trend_break_quarter}.{" "}
        {mape != null
          ? <>On the 2019 to 2025 backtest, this suburb's forecasts were off by about <strong>{mape.toFixed(1)}%</strong> on average (MAPE).</>
          : <>No backtest result is available for this suburb.</>}
      </p>
    </div>
  );
}
