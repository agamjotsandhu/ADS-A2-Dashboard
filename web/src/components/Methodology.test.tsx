import { render, screen } from "@testing-library/react";
import summary from "../test/fixtures/model_summary.json";
import type { ModelSummary } from "../lib/forecasts";
import { Disclaimer } from "./Disclaimer";
import { Methodology } from "./Methodology";

it("shows measured metrics from model_summary.json", async () => {
  render(<Methodology loader={() => Promise.resolve(summary as unknown as ModelSummary)} />);
  const s = summary as unknown as ModelSummary;
  expect(await screen.findByText(new RegExp(`${s.reduced_test.mape.toFixed(1)}% on average`))).toBeInTheDocument();
});

it("disclaimer covers advice, intervals and luxury bias", () => {
  render(<Disclaimer />);
  expect(screen.getByText(/not financial or property advice/)).toBeInTheDocument();
  expect(screen.getByText(/not guarantees/)).toBeInTheDocument();
  expect(screen.getByText(/Luxury properties/)).toBeInTheDocument();
});
