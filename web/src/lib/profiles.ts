import { fiveYearGrowth, type ForecastFile } from "./forecasts";

export interface SuburbProfile {
  name: string;
  display: string;
  n_listings: number;
  median_rent: number;
  median_weekly_income: number;
  population: number;
  dist_to_cbd_km: number;
  affordability: { rent_to_income_pct: number; rank: number | null };
  livability: { score: number; rank: number; domains: Record<string, number> };
  property_profile: {
    dwelling: Record<string, number>;
    property_type: Record<string, number>;
    bedrooms: Record<string, number>;
    median_rent_by_bedrooms: Record<string, number>;
  };
  arima_suburb: string | null;
  /** True when the forecast area is a neighbouring area, not this suburb's own. */
  arima_approximate?: boolean;
}

export interface ProfilesFile {
  meta: {
    generated_at: string;
    n_listings: number;
    listing_dates: [string, string];
    n_suburbs: number;
    n_affordability_ranked: number;
    min_listings_affordability: number;
    dwelling_groups: Record<string, string[]>;
  };
  suburbs: Record<string, SuburbProfile>;
}

export async function loadProfiles(): Promise<ProfilesFile | null> {
  const r = await fetch(`${import.meta.env.BASE_URL}data/suburb_profiles.json`);
  if (r.status === 404 || (r.headers.get("content-type") ?? "").includes("text/html")) return null;
  if (!r.ok) throw new Error(`Could not load suburb profiles (${r.status})`);
  return (await r.json()) as ProfilesFile;
}

/** Rank of an ARIMA area's 5-year forecast growth (1 = highest), out of all forecast areas. */
export function growthRank(file: ForecastFile, arimaName: string): { rank: number; of: number; growth: number } | null {
  const target = file.suburbs[arimaName];
  if (!target) return null;
  const growth = fiveYearGrowth(target);
  const all = Object.values(file.suburbs).map(fiveYearGrowth);
  return { rank: 1 + all.filter((g) => g > growth).length, of: all.length, growth };
}

/** JS objects list number-like keys ("1", "2") first, so bedroom order must be explicit. */
export const BEDROOM_ORDER = ["Studio", "1", "2", "3", "4", "5+"];

/** Counts -> rows with share %, in ``order`` when given (otherwise insertion order). */
export function shares(counts: Record<string, number>, order?: string[]): { label: string; count: number; pct: number }[] {
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  const keys = order ? order.filter((k) => k in counts) : Object.keys(counts);
  return keys.map((label) => ({ label, count: counts[label], pct: total ? (counts[label] / total) * 100 : 0 }));
}
