import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import fixture from "../test/fixtures/synthetic_suburb_forecasts.json";
import type { ForecastFile } from "../lib/forecasts";
import { SuburbForecastSection } from "./SuburbForecastSection";

const file = fixture as unknown as ForecastFile;
const load = () => Promise.resolve(file);

it("renders stats, chart, table and growth rankings from fixture data", async () => {
  const { container } = render(<SuburbForecastSection loader={load} />);
  expect(await screen.findByText("Median now (Sep 2025)")).toBeInTheDocument();
  expect(screen.getByRole("alert")).toHaveTextContent(/Demo data/);
  expect(screen.getByText("Forecast Sep 2031")).toBeInTheDocument();
  expect(container.querySelector(".recharts-surface")).not.toBeNull();
  expect(screen.getByText(/off by about/)).toBeInTheDocument();
  const top = screen.getByText("Top 10").closest("table")!;
  expect(within(top).getAllByRole("row")).toHaveLength(11);
});

it("switches suburb via the searchable picker", async () => {
  render(<SuburbForecastSection loader={load} />);
  const input = await screen.findByLabelText("Suburb");
  await userEvent.clear(input);
  await userEvent.type(input, "Docklands");
  expect(await screen.findByText(/trend break at/)).toBeInTheDocument();
  const s = file.suburbs["Docklands"];
  expect(screen.getByText(new RegExp(s.model.replace(/[()]/g, "\\$&")))).toBeInTheDocument();
});

it("shows an empty state when forecasts are not published", async () => {
  render(<SuburbForecastSection loader={() => Promise.resolve(null)} />);
  expect(await screen.findByText(/aren't published yet/)).toBeInTheDocument();
});

it("shows an error state", async () => {
  render(<SuburbForecastSection loader={() => Promise.reject(new Error("boom"))} />);
  expect(await screen.findByRole("alert")).toHaveTextContent("boom");
});
