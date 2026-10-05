import { useEffect, useState } from "react";
import { loadModelSummary, type ModelSummary } from "../lib/forecasts";
import { fmtDollars } from "../lib/format";

export function Methodology({ loader = loadModelSummary }: { loader?: () => Promise<ModelSummary | null> }) {
  const [m, setM] = useState<ModelSummary | null>(null);
  useEffect(() => {
    loader().then(setM).catch(() => setM(null));
  }, [loader]);

  return (
    <section className="card" aria-labelledby="method-h">
      <h2 id="method-h">How these numbers are made</h2>
      <div className="two-col" style={{ marginTop: 12 }}>
        <div>
          <h3>Suburb forecasts (ARIMA)</h3>
          <p className="small">
            For each suburb or suburb group, a time-series model of log median weekly rent by quarter (2000 to Sep 2025,
            Docklands from 2002) with a linear trend and one trend break. The ARIMA order is chosen by AICc among models whose
            residuals pass a Ljung-Box test. Forecasts run Dec 2025 to Sep 2031 with 95% intervals. Accuracy was checked by
            training to Sep 2019 and forecasting the following six years, which included COVID-era disruption.
          </p>
        </div>
        <div>
          <h3>Property estimates (XGBoost)</h3>
          <p className="small">
            A gradient-boosted tree model trained on
            {m ? ` ${m.n_train.toLocaleString()} rental listings (${m.train_date_range[0]} to ${m.train_date_range[1]}, mostly Jul to Sep 2025)` : " Victorian rental listings, mostly from Jul to Sep 2025"},
            using property type, rooms, car spaces, a few features and suburb-level context (distance to the CBD, income,
            crime, population, location). It estimates rent at the Sep 2025 level.
          </p>
          {m && (
            <p className="small">
              On {m.n_test.toLocaleString()} held-out listings from {m.test_date_range[0]} to {m.test_date_range[1]}, the typical
              error was {fmtDollars(m.reduced_test.mae)}/week (MAE), {m.reduced_test.mape.toFixed(1)}% on average (MAPE), RMSE{" "}
              {fmtDollars(m.reduced_test.rmse)}. The {Math.round(m.interval_level * 100)}% intervals contained the actual rent for{" "}
              {(m.test_coverage * 100).toFixed(1)}% of those listings, but for listings above $1,500/week only{" "}
              {m.test_coverage_actual_above_1500.coverage != null ? `${Math.round(m.test_coverage_actual_above_1500.coverage * 100)}%` : "a minority"}{" "}
              (n = {m.test_coverage_actual_above_1500.n}).
            </p>
          )}
          <h3>Projecting a property forward</h3>
          <p className="small">
            The Sep 2025 estimate is scaled by the suburb's forecast growth relative to its Sep 2025 median. The range
            multiplies the property interval by the suburb forecast's interval. That is a rough guide, not a formal statistical
            interval, and it assumes the property's rent moves with its suburb median.
          </p>
        </div>
      </div>
    </section>
  );
}
