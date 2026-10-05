import { addQuarters } from "./quarters";

export interface SuburbForecast {
  suburb: string;
  model: string;
  order: { p: number; d: number; q: number };
  trend_break: number;
  trend_break_quarter: string;
  history: { start: string; values: number[] };
  forecast: { start: string; mean: number[]; lower95: number[]; upper95: number[] };
  backtest_mape: number | null;
  backtest_rmse: number | null;
  backtest_mpe?: number | null;
}

export interface ForecastFile {
  meta: Record<string, unknown> & { generated_at?: string; data_end?: string; SYNTHETIC?: string };
  suburbs: Record<string, SuburbForecast>;
}

export interface ModelSummary {
  train_date_range: [string, string];
  test_date_range: [string, string];
  n_train: number;
  n_test: number;
  reduced_test: { rmse: number; mae: number; mape: number };
  full_model_test: { rmse: number; mae: number; mape: number };
  baseline_test: { rmse: number; mae: number; mape: number };
  interval_level: number;
  test_coverage: number;
  test_coverage_actual_above_1500: { coverage: number | null; n: number };
  luxury_threshold: number;
}

const DATA_BASE = `${import.meta.env.BASE_URL}data/`;

async function getJson<T>(name: string): Promise<T | null> {
  const r = await fetch(DATA_BASE + name);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`Could not load ${name} (${r.status})`);
  const type = r.headers.get("content-type") ?? "";
  // Dev servers answer unknown paths with index.html; treat that as "not published".
  if (type.includes("text/html")) return null;
  return (await r.json()) as T;
}

export const loadForecasts = () => getJson<ForecastFile>("suburb_forecasts.json");
export const loadSuburbIndex = () => getJson<string[]>("suburb_index.json");
export const loadModelSummary = () => getJson<ModelSummary>("model_summary.json");

export const lastHistoryQuarter = (s: SuburbForecast): string =>
  addQuarters(s.history.start, s.history.values.length - 1);

/** Current (Sep 2025 actual) median. */
export const currentMedian = (s: SuburbForecast): number => s.history.values[s.history.values.length - 1];

/** Forecast mean at a 1-based horizon (h=4 is Sep 2026, h=24 is Sep 2031). */
export const forecastAt = (s: SuburbForecast, h: number): number => s.forecast.mean[h - 1];

/** 5-year growth exactly as in the qmd: forecast Sep 2031 / forecast Sep 2026 - 1, in %. */
export const fiveYearGrowth = (s: SuburbForecast): number => (forecastAt(s, 24) / forecastAt(s, 4) - 1) * 100;

export function rankByGrowth(file: ForecastFile, n = 10): { top: SuburbForecast[]; bottom: SuburbForecast[] } {
  const all = Object.values(file.suburbs).sort((a, b) => fiveYearGrowth(b) - fiveYearGrowth(a));
  return { top: all.slice(0, n), bottom: all.slice(-n).reverse() };
}

export interface ChartRow {
  quarter: string;
  history?: number;
  forecast?: number;
  band?: [number, number];
}

/** One row per quarter; the forecast line starts at the last actual so the lines join. */
export function chartRows(s: SuburbForecast): ChartRow[] {
  const rows: ChartRow[] = s.history.values.map((v, i) => ({ quarter: addQuarters(s.history.start, i), history: v }));
  const last = rows[rows.length - 1];
  last.forecast = last.history;
  last.band = [last.history as number, last.history as number];
  s.forecast.mean.forEach((m, i) => {
    rows.push({
      quarter: addQuarters(s.forecast.start, i),
      forecast: m,
      band: [s.forecast.lower95[i], s.forecast.upper95[i]],
    });
  });
  return rows;
}
