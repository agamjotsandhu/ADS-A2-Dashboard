import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import type { PredictResponse, SuburbsResponse } from "../lib/api";
import { PropertyEstimator } from "./PropertyEstimator";

const META: SuburbsResponse = {
  suburbs: [
    { name: "TARNEIT", display: "Tarneit", n_listings: 230, defaults: { property_type: "House", bedrooms: 4, bathrooms: 2, carspaces: 2 }, arima_suburb: "Tarneit", has_forecast: true },
    { name: "TOORAK", display: "Toorak", n_listings: 40, defaults: { property_type: "House", bedrooms: 4, bathrooms: 3, carspaces: 2 }, arima_suburb: null, has_forecast: false },
  ],
  property_types: ["Apartment / Unit / Flat", "House", "Townhouse"],
  amenities: [{ key: "feat_dishwasher", label: "Dishwasher" }, { key: "feat_study", label: "Study" }],
  quarters: { base: "2025Q3", first: "2025Q4", last: "2031Q3" },
  price_level: "Sep 2025",
  forecasts_available: true,
};

const RESULT: PredictResponse = {
  point: 560, lower: 450, upper: 680, interval_level: 0.9, price_level: "Sep 2025",
  suburb: { input: "TARNEIT", listing_suburb: "TARNEIT", seen_in_training: true, arima_suburb: "Tarneit" },
  target_date: "2026Q1",
  projection: [
    { quarter: "2025Q3", point: 560, lower: 450, upper: 680, growth_factor: 1 },
    { quarter: "2025Q4", point: 566, lower: 440, upper: 700, growth_factor: 1.01 },
    { quarter: "2026Q1", point: 572, lower: 430, upper: 720, growth_factor: 1.02 },
  ],
  at_target: { quarter: "2026Q1", point: 572, lower: 430, upper: 720, growth_factor: 1.02 },
  warnings: [{ code: "combined_band", message: "The projected range combines two intervals." }],
};

it("submits the form and shows estimate, projection and warnings", async () => {
  const predict = vi.fn().mockResolvedValue(RESULT);
  const { container } = render(<PropertyEstimator fetchSuburbs={() => Promise.resolve(META)} predict={predict} />);
  await userEvent.type(await screen.findByLabelText("Suburb"), "Tarneit");
  expect(screen.getByLabelText("Bedrooms")).toHaveValue("4"); // suburb defaults applied
  await userEvent.click(screen.getByLabelText("Dishwasher"));
  await userEvent.selectOptions(screen.getByLabelText("Forecast date"), "2026Q1");
  await userEvent.click(screen.getByRole("button", { name: "Estimate rent" }));

  expect(predict).toHaveBeenCalledTimes(1);
  expect(predict.mock.calls[0][0]).toEqual({
    suburb: "TARNEIT", property_type: "House", bedrooms: 4, bathrooms: 2, carspaces: 2,
    amenities: ["feat_dishwasher"], target_date: "2026Q1",
  });
  expect(await screen.findByText("$572/wk")).toBeInTheDocument();
  expect(screen.getByText(/projected to Mar 2026/)).toBeInTheDocument();
  expect(screen.getByText(/combines two intervals/)).toBeInTheDocument();
  expect(container.querySelector(".recharts-surface")).not.toBeNull();
});

it("does not call the API while typing, only on submit", async () => {
  const predict = vi.fn().mockResolvedValue({ ...RESULT, projection: null, at_target: null, target_date: null, warnings: [] });
  render(<PropertyEstimator fetchSuburbs={() => Promise.resolve(META)} predict={predict} />);
  await userEvent.type(await screen.findByLabelText("Suburb"), "Toorak");
  expect(predict).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Estimate rent" }));
  expect(await screen.findByText("$560/wk")).toBeInTheDocument();
  expect(document.querySelector(".result-range")).toHaveTextContent("90% prediction interval: $450 to $680 per week");
  expect(predict.mock.calls[0][0]).not.toHaveProperty("target_date");
});

it("asks for a suburb before submitting", async () => {
  const predict = vi.fn();
  render(<PropertyEstimator fetchSuburbs={() => Promise.resolve(META)} predict={predict} />);
  await userEvent.click(await screen.findByRole("button", { name: "Estimate rent" }));
  expect(screen.getByRole("alert")).toHaveTextContent("Choose a suburb first.");
  expect(predict).not.toHaveBeenCalled();
});

it("shows API errors", async () => {
  const predict = vi.fn().mockRejectedValue(new Error("Too many requests. Please wait a minute and try again."));
  render(<PropertyEstimator fetchSuburbs={() => Promise.resolve(META)} predict={predict} />);
  await userEvent.type(await screen.findByLabelText("Suburb"), "Tarneit");
  await userEvent.click(screen.getByRole("button", { name: "Estimate rent" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(/Too many requests/);
});

it("shows an unavailable state when the API is down", async () => {
  render(<PropertyEstimator fetchSuburbs={() => Promise.reject(new Error("Failed to fetch"))} />);
  expect(await screen.findByRole("alert")).toHaveTextContent(/unavailable right now/);
});
