const dollars = new Intl.NumberFormat("en-AU", { style: "currency", currency: "AUD", maximumFractionDigits: 0 });

export const fmtDollars = (v: number): string => dollars.format(v);
export const fmtWeekly = (v: number): string => `${dollars.format(v)}/wk`;
export const fmtPct = (v: number, digits = 1): string => `${v > 0 ? "+" : ""}${v.toFixed(digits)}%`;
