import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import forecastsFx from "../test/fixtures/synthetic_suburb_forecasts.json";
import profilesFx from "../test/fixtures/suburb_profiles.json";
import type { ForecastFile } from "../lib/forecasts";
import { growthRank, shares, type ProfilesFile } from "../lib/profiles";
import { SuburbProfilePage } from "./SuburbProfilePage";

const profiles = profilesFx as unknown as ProfilesFile;
const forecasts = forecastsFx as unknown as ForecastFile;
const pl = () => Promise.resolve(profiles);
const fl = () => Promise.resolve(forecasts);

it("growthRank ranks 5-year growth, 1 = highest", () => {
  const ranks = Object.keys(forecasts.suburbs).map((s) => growthRank(forecasts, s)!.rank).sort((a, b) => a - b);
  expect(ranks[0]).toBe(1);
  expect(ranks.at(-1)).toBe(Object.keys(forecasts.suburbs).length);
  expect(growthRank(forecasts, "Nowhere")).toBeNull();
});

it("shares converts counts to percentages", () => {
  const s = shares({ a: 1, b: 3 });
  expect(s.map((x) => x.pct)).toEqual([25, 75]);
  const beds = shares({ "1": 1, "2": 1, Studio: 2 }, ["Studio", "1", "2"]);
  expect(beds.map((x) => x.label)).toEqual(["Studio", "1", "2"]);
});

it("renders ranks, forecast chart and property profile for a matched suburb", async () => {
  const { container } = render(<SuburbProfilePage profilesLoader={pl} forecastsLoader={fl} />);
  const input = await screen.findByLabelText("Suburb");
  await userEvent.clear(input);
  await userEvent.type(input, "Tarneit");
  const p = profiles.suburbs.TARNEIT;
  expect(await screen.findByRole("heading", { name: "Tarneit" })).toBeInTheDocument();
  expect(screen.getByText(`#${p.affordability.rank}`)).toBeInTheDocument();
  expect(screen.getByText(`#${p.livability.rank}`)).toBeInTheDocument();
  const gr = growthRank(forecasts, "Tarneit")!;
  expect(screen.getByText(new RegExp(`of ${gr.of} areas`))).toBeInTheDocument();
  expect(screen.getByText(/Rent forecast, 2026 to 2031/)).toBeInTheDocument();
  expect(screen.getByText(/Demo data/)).toBeInTheDocument();
  expect(container.querySelectorAll(".recharts-surface").length).toBeGreaterThanOrEqual(4);
  expect(screen.getByText(`Property types in ${p.display}`)).toBeInTheDocument();
});

it("explains missing forecast and unranked affordability", async () => {
  render(<SuburbProfilePage profilesLoader={pl} forecastsLoader={() => Promise.resolve(null)} />);
  const small = Object.values(profiles.suburbs).find((s) => s.affordability.rank === null)!;
  const input = await screen.findByLabelText("Suburb");
  await userEvent.clear(input);
  await userEvent.type(input, small.display);
  expect(await screen.findByText("Not ranked")).toBeInTheDocument();
  expect(screen.getByText(/Small sample/)).toBeInTheDocument();
  expect(screen.getByText(/aren't published yet/)).toBeInTheDocument();
  expect(screen.getByText("n/a")).toBeInTheDocument();
});
