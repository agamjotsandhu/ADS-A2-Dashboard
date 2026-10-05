# Export suburb ARIMA forecasts to JSON for the website.
#
# Reuses the model-selection logic of `Modelling/Modelling_rent (1).qmd` verbatim
# (trend break by RSS, simulated ADF test for d, ARIMA(p,d,q) p,q <= 9 chosen by
# AICc among models passing Ljung-Box) for:
#   Part B: train 2000Q1-2019Q3, test 2019Q4-2025Q3  -> backtest MAPE / RMSE
#   Part C: full data to 2025Q3, forecast 24 quarters -> 2025Q4..2031Q3 with 95% PI
#
# Usage (from repo root):
#   Rscript ml/arima/export_forecasts.R <path/to/rent_by_qtr_suburb_refactored.csv> [out_dir]
# out_dir defaults to web/public/data.
#
# Env overrides (for smoke tests only; defaults match the qmd):
#   ARIMA_PMAX, ARIMA_QMAX (9), ADF_REPS (20000), ARIMA_CORES (detectCores()-1),
#   ARIMA_SUBURBS (comma-separated subset)
#
# Tested with: R 4.4.3, forecast 9.0.2, urca 1.3.4, jsonlite 2.0.0, parallel (base).
# Reproducibility: RNGkind("L'Ecuyer-CMRG"); set.seed(123) as in the qmd. The ADF
# p-values are simulated, so results are reproducible for a fixed core count.

suppressPackageStartupMessages({
  library(forecast)
  library(parallel)
  library(jsonlite)
})

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) stop("usage: Rscript export_forecasts.R <csv> [out_dir]")
csv_path <- args[1]
out_dir  <- if (length(args) >= 2) args[2] else "web/public/data"
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

env_int <- function(name, default) {
  v <- Sys.getenv(name, "")
  if (nzchar(v)) as.integer(v) else default
}
PMAX  <- env_int("ARIMA_PMAX", 9)
QMAX  <- env_int("ARIMA_QMAX", 9)
REPS  <- env_int("ADF_REPS", 20000)
CORES <- env_int("ARIMA_CORES", max(1, detectCores() - 1))

dt <- read.csv(csv_path, check.names = FALSE)
names(dt)[1] <- "Suburb"
subset_env <- Sys.getenv("ARIMA_SUBURBS", "")
if (nzchar(subset_env)) dt <- dt[dt$Suburb %in% trimws(strsplit(subset_env, ",")[[1]]), ]
stopifnot(ncol(dt) - 1 == 103)   # 2000Q1 .. 2025Q3

# ---------------------------------------------------------------- qmd helpers
get_suburb <- function(name) {
  y <- as.numeric(unlist(dt[dt$Suburb == name, -1]))
  Y <- ts(y, start = c(2000, 1), frequency = 4)
  # Docklands has no data before Mar 2002, so start it there
  if (name == "Docklands") {
    Y <- window(Y, start = c(2002, 1))
  }
  return(Y)
}

trend_break <- function(b, time) {
  return ((time > b) * (time - b))
}

simulate_adf_cv <- function(n, X_det, t_stat, reps = 20000) {
  t <- 2:n
  X <- X_det[t, , drop = FALSE]
  tADF <- matrix(nrow = reps, ncol = 1)
  for (r in 1:reps) {
    Y_simulated <- arima.sim(n = n, model = list(order = c(0, 1, 0)))[-1]
    DY <- Y_simulated[t] - Y_simulated[t - 1]
    Y1 <- Y_simulated[t - 1]
    tADF[r] <- summary(lm(DY ~ X + Y1))$coefficients["Y1", "t value"]
  }
  p_val <- mean(tADF < t_stat)
  return(list(p_val = p_val, tADF = tADF))
}

adf_test <- function(Y, X_det, reps = REPS) {
  n <- length(Y)
  t <- 2:n
  Y_1 <- Y[t - 1]
  DY  <- Y[t] - Y[t - 1]
  X   <- X_det[t, , drop = FALSE]
  t_stat <- summary(lm(DY ~ X + Y_1))$coefficients["Y_1", "t value"]
  p_val <- simulate_adf_cv(n, X_det, t_stat, reps)$p_val
  return(1 * (p_val > 0.05))
}

fit_arima <- function(y, order, xreg, drift) {
  tryCatch(
    Arima(y, order = order, xreg = xreg, include.drift = drift),
    error = function(e) tryCatch(
      Arima(y, order = order, xreg = xreg, include.drift = drift, method = "ML"),
      error = function(e2) NULL
    )
  )
}

find_break <- function(s, first_forecast, lo, hi) {
  Y <- log(get_suburb(s))
  Time <- time(Y)
  t_est <- which(Time < first_forecast)
  Break_range <- Time[which(Time >= lo & Time < hi)]
  rss <- sapply(Break_range, function(b) {
    X <- cbind(Time[t_est], trend_break(b, Time[t_est]))
    sum(Arima(Y[t_est], order = c(0, 0, 0), xreg = X)$residuals^2)
  })
  Break_range[which.min(rss)]
}

# Shared selection: returns list(model, nd, p, q, X, drift) or NULL
select_model <- function(Y, Time, t_est, b) {
  TBt <- 1 * (Time > b) * (Time - b)
  AICc <- matrix(nrow = PMAX + 1, ncol = QMAX + 1)
  LBp <- AICc

  nd <- adf_test(Y[t_est], cbind(Time[t_est], TBt[t_est]))
  if (nd == 1) {
    DU <- 1 * (Time[t_est][-1] > b)
    nd <- nd + adf_test(diff(Y[t_est]), cbind(DU))
  }
  if (nd == 0) {
    X <- cbind(Time, TBt); drift <- FALSE
  } else if (nd == 1) {
    X <- cbind(TBt); drift <- TRUE
  } else {
    X <- cbind(TBt); drift <- FALSE
  }

  models <- list()
  for (p in 0:PMAX) for (q in 0:QMAX) {
    eq <- fit_arima(Y[t_est], c(p, nd, q), X[t_est, , drop = FALSE], drift)
    if (is.null(eq)) next
    AICc[p + 1, q + 1] <- eq$aicc
    LBp[p + 1, q + 1] <- Box.test(eq$residuals, lag = max(8, p + q + 4),
                                  type = "Ljung-Box", fitdf = p + q)$p.value
    models[[paste(p, q)]] <- eq
  }
  AICc_ok <- AICc
  AICc_ok[LBp <= 0.05 | is.na(LBp)] <- NA
  if (all(is.na(AICc_ok))) return(NULL)
  best <- which(AICc_ok == min(AICc_ok, na.rm = TRUE), arr.ind = TRUE)
  p_best <- best[1, 1] - 1
  q_best <- best[1, 2] - 1
  list(model = models[[paste(p_best, q_best)]], nd = nd, p = p_best, q = q_best,
       X = X, drift = drift)
}

# ---------------------------------------------------------------- Part B
fit_backtest <- function(s) {
  FirstForecast <- 2019.75
  b <- find_break(s, FirstForecast, 2003, 2016.75)
  Y <- log(get_suburb(s))
  Time <- as.numeric(time(Y))
  t_est <- which(Time < FirstForecast)
  t_test <- which(Time >= FirstForecast)
  sel <- select_model(Y, Time, t_est, b)
  if (is.null(sel)) return(NULL)
  Y_test <- exp(Y[t_test])
  fc <- exp(forecast(sel$model, xreg = sel$X[t_test, , drop = FALSE], h = length(t_test))$mean)
  list(
    rmse = sqrt(mean((Y_test - fc)^2, na.rm = TRUE)),
    mape = 100 * mean(abs(Y_test - fc) / Y_test, na.rm = TRUE),
    mpe  = 100 * mean((Y_test - fc) / Y_test, na.rm = TRUE),
    model = sprintf("ARIMA(%d,%d,%d)", sel$p, sel$nd, sel$q)
  )
}

# ---------------------------------------------------------------- Part C
fit_future <- function(s) {
  FirstForecast <- 2025.75
  hmax <- 24
  b <- find_break(s, FirstForecast, 2004, 2021.75)
  Y <- log(get_suburb(s))
  Time <- as.numeric(time(Y))
  t_est <- which(Time < FirstForecast)
  sel <- select_model(Y, Time, t_est, b)
  if (is.null(sel)) return(NULL)   # qmd used `next` here, which errors inside a function

  Time_future <- max(Time) + (1:hmax) / 4
  TB_future <- 1 * (Time_future > b) * (Time_future - b)
  X_future <- if (sel$nd == 0) cbind(Time = Time_future, TBt = TB_future) else cbind(TBt = TB_future)

  fc <- forecast(sel$model, xreg = X_future, h = hmax, level = 95)
  list(
    model = sprintf("ARIMA(%d,%d,%d)", sel$p, sel$nd, sel$q),
    order = list(p = sel$p, d = sel$nd, q = sel$q),
    trend_break = b,
    history_start = Time[1],
    history = exp(as.numeric(Y)),
    mean = exp(as.numeric(fc$mean)),
    lower95 = exp(as.numeric(fc$lower[, 1])),
    upper95 = exp(as.numeric(fc$upper[, 1]))
  )
}

to_quarter <- function(t) sprintf("%dQ%d", as.integer(floor(t + 1e-9)),
                                  as.integer(round((t - floor(t + 1e-9)) * 4)) + 1L)

# ---------------------------------------------------------------- run
RNGkind("L'Ecuyer-CMRG")
set.seed(123)
suburbs <- dt$Suburb
cat(sprintf("Fitting %d suburbs (p,q <= %d,%d; ADF reps %d; %d cores)\n",
            length(suburbs), PMAX, QMAX, REPS, CORES))

safe <- function(f) function(s) tryCatch(f(s), error = function(e) list(error = conditionMessage(e)))
res_b <- mclapply(suburbs, safe(fit_backtest), mc.cores = CORES, mc.set.seed = TRUE)
res_c <- mclapply(suburbs, safe(fit_future), mc.cores = CORES, mc.set.seed = TRUE)
names(res_b) <- names(res_c) <- suburbs

records <- list()
failed <- character(0)
for (s in suburbs) {
  rc <- res_c[[s]]; rb <- res_b[[s]]
  if (is.null(rc) || !is.null(rc$error)) { failed <- c(failed, s); next }
  ok_b <- !is.null(rb) && is.null(rb$error)
  records[[s]] <- list(
    suburb = s,
    model = rc$model,
    order = rc$order,
    trend_break = rc$trend_break,
    trend_break_quarter = to_quarter(rc$trend_break),
    history = list(start = to_quarter(rc$history_start), values = round(rc$history, 2)),
    forecast = list(start = "2025Q4",
                    mean = round(rc$mean, 2),
                    lower95 = round(rc$lower95, 2),
                    upper95 = round(rc$upper95, 2)),
    backtest_mape = if (ok_b) round(rb$mape, 3) else NULL,
    backtest_rmse = if (ok_b) round(rb$rmse, 3) else NULL,
    backtest_mpe  = if (ok_b) round(rb$mpe, 3) else NULL,
    backtest_model = if (ok_b) rb$model else NULL
  )
}

# ---------------------------------------------------------------- validate
problems <- character(0)
for (r in records) {
  v <- c(r$history$values, r$forecast$mean, r$forecast$lower95, r$forecast$upper95)
  if (any(!is.finite(v))) problems <- c(problems, paste(r$suburb, "non-finite values"))
  if (any(v <= 0)) problems <- c(problems, paste(r$suburb, "non-positive values"))
  if (length(r$forecast$mean) != 24) problems <- c(problems, paste(r$suburb, "forecast length"))
  if (any(!(r$forecast$lower95 < r$forecast$mean & r$forecast$mean < r$forecast$upper95)))
    problems <- c(problems, paste(r$suburb, "interval ordering"))
  n_hist <- length(r$history$values)
  last_q <- to_quarter(as.numeric(sub("Q.*", "", r$history$start)) +
                         (as.numeric(sub(".*Q", "", r$history$start)) - 1) / 4 + (n_hist - 1) / 4)
  if (last_q != "2025Q3") problems <- c(problems, paste(r$suburb, "history ends", last_q))
}
if ("Docklands" %in% names(records) && records[["Docklands"]]$history$start != "2002Q1")
  problems <- c(problems, "Docklands should start 2002Q1")

cat(sprintf("\nSuburbs in CSV: %d | exported: %d | failed: %d\n",
            length(suburbs), length(records), length(failed)))
if (length(failed)) cat("Failed:", paste(failed, collapse = "; "), "\n")

summ <- data.frame(
  Suburb = names(records),
  Model = sapply(records, `[[`, "model"),
  Start = sapply(records, function(r) r$history$start),
  Sep2025 = sapply(records, function(r) tail(r$history$values, 1)),
  Sep2026 = sapply(records, function(r) r$forecast$mean[4]),
  Sep2031 = sapply(records, function(r) r$forecast$mean[24]),
  Growth5y = sapply(records, function(r) round(100 * (r$forecast$mean[24] / r$forecast$mean[4] - 1), 1)),
  MAPE = sapply(records, function(r) if (is.null(r$backtest_mape)) NA else r$backtest_mape),
  row.names = NULL
)
print(head(summ[order(-summ$Growth5y), ], 20), row.names = FALSE)
cat("\nBacktest MAPE across suburbs:\n"); print(summary(summ$MAPE))

if (length(problems)) {
  cat("\nVALIDATION FAILED:\n", paste(problems, collapse = "\n"), "\n")
  quit(status = 1)
}

meta <- list(
  generated_at = format(Sys.time(), "%Y-%m-%dT%H:%M:%S%z"),
  source = basename(csv_path),
  data_end = "2025Q3",
  forecast_start = "2025Q4",
  forecast_end = "2031Q3",
  interval = "95% (normal, log scale, back-transformed with exp)",
  backtest = "train 2000Q1-2019Q3, test 2019Q4-2025Q3 (24 quarters)",
  settings = list(pmax = PMAX, qmax = QMAX, adf_reps = REPS, cores = CORES, seed = 123),
  r_version = R.version.string,
  packages = list(forecast = as.character(packageVersion("forecast")),
                  jsonlite = as.character(packageVersion("jsonlite"))),
  failed_suburbs = failed
)
write_json(list(meta = meta, suburbs = records),
           file.path(out_dir, "suburb_forecasts.json"), auto_unbox = TRUE, digits = NA, null = "null")
write_json(sort(names(records)), file.path(out_dir, "suburb_index.json"))
cat("\nAll checks passed. Wrote", file.path(out_dir, "suburb_forecasts.json"), "and suburb_index.json\n")
