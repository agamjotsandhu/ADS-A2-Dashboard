import fixture from "../test/fixtures/synthetic_suburb_forecasts.json";
import { chartRows, currentMedian, fiveYearGrowth, forecastAt, lastHistoryQuarter, rankByGrowth, type ForecastFile } from "./forecasts";
import { addQuarters, quarterLabel, quartersBetween } from "./quarters";

const file = fixture as unknown as ForecastFile;

describe("quarters", () => {
  it("labels and steps quarters", () => {
    expect(quarterLabel("2025Q3")).toBe("Sep 2025");
    expect(quarterLabel("2031Q3")).toBe("Sep 2031");
    expect(addQuarters("2025Q4", 4)).toBe("2026Q4");
    expect(quartersBetween("2025Q4", "2031Q3")).toHaveLength(24);
  });
});

describe("forecast helpers", () => {
  const s = file.suburbs["Docklands"];
  it("handles Docklands starting 2002Q1 and ending 2025Q3", () => {
    expect(s.history.start).toBe("2002Q1");
    expect(lastHistoryQuarter(s)).toBe("2025Q3");
  });
  it("uses the qmd growth formula (Sep 2031 / Sep 2026 - 1)", () => {
    expect(fiveYearGrowth(s)).toBeCloseTo((s.forecast.mean[23] / s.forecast.mean[3] - 1) * 100, 10);
    expect(forecastAt(s, 4)).toBe(s.forecast.mean[3]);
    expect(currentMedian(s)).toBe(s.history.values.at(-1));
  });
  it("joins the forecast line to the last actual", () => {
    const rows = chartRows(s);
    expect(rows).toHaveLength(s.history.values.length + 24);
    const join = rows[s.history.values.length - 1];
    expect(join.quarter).toBe("2025Q3");
    expect(join.forecast).toBe(join.history);
    expect(rows.at(-1)?.quarter).toBe("2031Q3");
  });
  it("ranks top and bottom growth", () => {
    const { top, bottom } = rankByGrowth(file, 3);
    expect(fiveYearGrowth(top[0])).toBeGreaterThanOrEqual(fiveYearGrowth(top[1]));
    expect(fiveYearGrowth(bottom[0])).toBeLessThanOrEqual(fiveYearGrowth(bottom[1]));
  });
});
