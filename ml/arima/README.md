# ARIMA export

`export_forecasts.R` reproduces the model selection in `Modelling/Modelling_rent (1).qmd` (Parts B and C) and writes:

- `web/public/data/suburb_forecasts.json`: `{meta, suburbs: {name: {suburb, model, order, trend_break, trend_break_quarter, history{start, values}, forecast{start, mean, lower95, upper95}, backtest_mape, backtest_rmse, backtest_mpe, backtest_model}}}`, all values in dollars/week
- `web/public/data/suburb_index.json`: sorted suburb names

Reproducibility: `RNGkind("L'Ecuyer-CMRG"); set.seed(123)` with `mclapply(mc.set.seed = TRUE)`, as in the qmd. Results depend on the core count (set `ARIMA_CORES` to pin it). Tested with R 4.4.3, forecast 9.0.2, urca 1.3.4 and jsonlite 2.0.0.
