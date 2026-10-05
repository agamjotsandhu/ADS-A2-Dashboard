export const API_URL: string = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "http://localhost:8000";

export interface SuburbOption {
  name: string;
  display: string;
  n_listings: number;
  defaults: { property_type: string; bedrooms: number; bathrooms: number; carspaces: number };
  arima_suburb: string | null;
  arima_approximate?: boolean;
  has_forecast: boolean;
}

export interface SuburbsResponse {
  suburbs: SuburbOption[];
  property_types: string[];
  amenities: { key: string; label: string }[];
  quarters: { base: string; first: string; last: string };
  price_level: string;
  forecasts_available: boolean;
}

export interface PredictRequest {
  suburb: string;
  property_type: string;
  bedrooms: number;
  bathrooms: number;
  carspaces: number;
  amenities: string[];
  target_date?: string;
}

export interface ProjectionPoint {
  quarter: string;
  point: number;
  lower: number;
  upper: number;
  growth_factor: number;
}

export interface PredictResponse {
  point: number;
  lower: number;
  upper: number;
  interval_level: number;
  price_level: string;
  suburb: {
    input: string;
    listing_suburb: string | null;
    seen_in_training: boolean;
    arima_suburb: string | null;
    arima_approximate?: boolean;
  };
  target_date: string | null;
  at_target: ProjectionPoint | null;
  projection: ProjectionPoint[] | null;
  warnings: { code: string; message: string }[];
}

async function handle<T>(r: Response): Promise<T> {
  if (r.ok) return (await r.json()) as T;
  if (r.status === 429) throw new Error("Too many requests. Please wait a minute and try again.");
  let detail = `Request failed (${r.status})`;
  try {
    const body = await r.json();
    if (typeof body.detail === "string") detail = body.detail;
    else if (Array.isArray(body.detail)) detail = body.detail.map((d: { msg: string }) => d.msg).join("; ");
  } catch {
    /* keep default message */
  }
  throw new Error(detail);
}

export async function fetchSuburbs(signal?: AbortSignal): Promise<SuburbsResponse> {
  return handle(await fetch(`${API_URL}/suburbs`, { signal }));
}

export async function predict(body: PredictRequest, signal?: AbortSignal): Promise<PredictResponse> {
  return handle(
    await fetch(`${API_URL}/predict`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    }),
  );
}
