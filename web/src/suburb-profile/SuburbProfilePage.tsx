import { useEffect, useMemo, useState } from "react";
import { BarList } from "../components/BarList";
import { Disclaimer } from "../components/Disclaimer";
import { ForecastChart } from "../components/ForecastChart";
import { Layout } from "../components/Layout";
import { SuburbPicker } from "../components/SuburbPicker";
import { forecastAt, loadForecasts, type ForecastFile } from "../lib/forecasts";
import { fmtDollars, fmtPct } from "../lib/format";
import { BEDROOM_ORDER, growthRank, loadProfiles, shares, type ProfilesFile, type SuburbProfile } from "../lib/profiles";

interface Props {
  profilesLoader?: () => Promise<ProfilesFile | null>;
  forecastsLoader?: () => Promise<ForecastFile | null>;
}

type Load<T> = { status: "loading" } | { status: "error"; message: string } | { status: "ready"; data: T | null };

const DEFAULT_SUBURB = "MELBOURNE";

function readQuery(): string {
  try {
    return new URLSearchParams(window.location.search).get("suburb")?.toUpperCase() ?? "";
  } catch {
    return "";
  }
}

export function SuburbProfilePage({ profilesLoader = loadProfiles, forecastsLoader = loadForecasts }: Props) {
  const [profiles, setProfiles] = useState<Load<ProfilesFile>>({ status: "loading" });
  const [forecasts, setForecasts] = useState<ForecastFile | null>(null);
  const [suburb, setSuburb] = useState(readQuery);

  useEffect(() => {
    let live = true;
    profilesLoader()
      .then((data) => {
        if (!live) return;
        setProfiles({ status: "ready", data });
        if (data) setSuburb((s) => (s && data.suburbs[s] ? s : data.suburbs[DEFAULT_SUBURB] ? DEFAULT_SUBURB : Object.keys(data.suburbs).sort()[0]));
      })
      .catch((e: Error) => live && setProfiles({ status: "error", message: e.message }));
    forecastsLoader().then((f) => live && setForecasts(f)).catch(() => live && setForecasts(null));
    return () => {
      live = false;
    };
  }, [profilesLoader, forecastsLoader]);

  const pick = (s: string) => {
    setSuburb(s);
    try {
      const url = new URL(window.location.href);
      url.searchParams.set("suburb", s);
      window.history.replaceState(null, "", url);
    } catch {
      /* non-browser environments */
    }
  };

  const options = useMemo(
    () =>
      profiles.status === "ready" && profiles.data
        ? Object.values(profiles.data.suburbs).map((s) => ({ value: s.name, label: s.display })).sort((a, b) => a.label.localeCompare(b.label))
        : [],
    [profiles],
  );

  return (
    <Layout current="suburb-profile">
      <h1>Suburb profile</h1>
      <p className="lede">
        Rent forecast to 2031, affordability and livability rankings, and the mix of rental properties for a single suburb.
      </p>

      {profiles.status === "loading" && <p className="empty" role="status">Loading suburb profiles…</p>}
      {profiles.status === "error" && <div className="notice error" role="alert"><strong>Couldn't load suburb profiles.</strong>{profiles.message}</div>}
      {profiles.status === "ready" && !profiles.data && (
        <div className="notice info" role="status"><strong>Suburb profiles aren't published yet.</strong></div>
      )}

      {profiles.status === "ready" && profiles.data && (
        <>
          <div className="card">
            <div style={{ maxWidth: 420 }}>
              <SuburbPicker label="Suburb" options={options} value={suburb} onChange={pick}
                hint={`${options.length} suburbs with rental listings.`} />
            </div>
          </div>
          {profiles.data.suburbs[suburb] && (
            <Profile p={profiles.data.suburbs[suburb]} meta={profiles.data.meta} forecasts={forecasts} />
          )}
          <Method meta={profiles.data.meta} />
        </>
      )}
      <Disclaimer />
    </Layout>
  );
}

function Profile({ p, meta, forecasts }: { p: SuburbProfile; meta: ProfilesFile["meta"]; forecasts: ForecastFile | null }) {
  const fc = p.arima_suburb && forecasts ? forecasts.suburbs[p.arima_suburb] : undefined;
  const gr = fc && forecasts && p.arima_suburb ? growthRank(forecasts, p.arima_suburb) : null;
  const few = p.n_listings < 10;

  const dwelling = shares(p.property_profile.dwelling);
  const beds = shares(p.property_profile.bedrooms, BEDROOM_ORDER);
  const domains = Object.entries(p.livability.domains);

  return (
    <>
      <section className="card" aria-labelledby="profile-h">
        <h2 id="profile-h">{p.display}</h2>
        <p className="subtle">
          {p.n_listings} rental listing{p.n_listings === 1 ? "" : "s"} in our data · median asking rent {fmtDollars(p.median_rent)}/week ·{" "}
          {p.dist_to_cbd_km} km drive to the CBD
        </p>
        {few && (
          <div className="notice" role="note"><strong>Small sample.</strong>Figures based on fewer than 10 listings can change a lot with a few more listings.</div>
        )}
        <div className="stats">
          <div className="stat">
            <span className="label">Affordability rank</span>
            <span className="value">{p.affordability.rank ? `#${p.affordability.rank}` : "Not ranked"}</span>
            <span className="note">
              {p.affordability.rank
                ? `of ${meta.n_affordability_ranked}; rent is ${p.affordability.rent_to_income_pct}% of median weekly income`
                : `needs ${meta.min_listings_affordability}+ listings (rent is ${p.affordability.rent_to_income_pct}% of income)`}
            </span>
          </div>
          <div className="stat">
            <span className="label">Livability rank</span>
            <span className="value">#{p.livability.rank}</span>
            <span className="note">of {meta.n_suburbs}; score {p.livability.score.toFixed(0)}/100</span>
          </div>
          <div className="stat">
            <span className="label">Forecast growth rank</span>
            <span className="value">{gr ? `#${gr.rank}` : "n/a"}</span>
            <span className="note">{gr ? `of ${gr.of} areas; ${fmtPct(gr.growth)} Sep 2026 to Sep 2031` : "No suburb forecast available"}</span>
          </div>
        </div>
        <p className="subtle small">Rank 1 is the most affordable, most livable or fastest forecast growth.</p>
      </section>

      <section className="card" aria-labelledby="fc-h">
        <h2 id="fc-h">Rent forecast, 2026 to 2031</h2>
        {fc ? (
          <>
            <p className="subtle">
              Median weekly rent forecast for the {fc.suburb} area ({fc.model}), with a 95% prediction interval.
              Sep 2026: {fmtDollars(forecastAt(fc, 4))} · Sep 2031: {fmtDollars(forecastAt(fc, 24))}.
            </p>
            {forecasts?.meta.SYNTHETIC && <div className="notice error" role="alert"><strong>Demo data.</strong>{forecasts.meta.SYNTHETIC}</div>}
            <ForecastChart data={fc} forecastOnly />
            {fc.backtest_mape != null && (
              <p className="subtle small">
                On the 2019 to 2025 backtest, this area's forecasts were off by about {fc.backtest_mape.toFixed(1)}% on average.
              </p>
            )}
          </>
        ) : (
          <div className="notice info" role="status">
            <strong>No forecast for this suburb.</strong>
            {forecasts ? "It isn't matched to a suburb area in the rent forecast data." : "Suburb rent forecasts aren't published yet."}
          </div>
        )}
      </section>

      <section className="card" aria-labelledby="pp-h">
        <h2 id="pp-h">Property profile</h2>
        <p className="subtle">Share of the {p.n_listings} rental listings in our data, not of all homes in the suburb.</p>
        <div className="two-col" style={{ marginTop: 12 }}>
          <div>
            <h3>Houses, townhouses and apartments</h3>
            <BarList title={`Property types in ${p.display}`} max={100}
              data={dwelling.map((d) => ({ label: d.label, value: d.pct, display: `${d.pct.toFixed(0)}%`, detail: `${d.count} listings` }))} />
          </div>
          <div>
            <h3>Bedrooms</h3>
            <BarList title={`Bedrooms in ${p.display}`} max={100} labelWidth={70}
              data={beds.map((d) => ({ label: d.label, value: d.pct, display: `${d.pct.toFixed(0)}%`, detail: `${d.count} listings` }))} />
          </div>
        </div>
        {Object.keys(p.property_profile.median_rent_by_bedrooms).length > 0 && (
          <div className="table-scroll" style={{ marginTop: 12 }}>
            <table>
              <caption className="label" style={{ textAlign: "left", paddingBottom: 6 }}>Median asking rent by bedrooms (3+ listings)</caption>
              <thead><tr><th>Bedrooms</th><th className="num">Median rent</th><th className="num">Listings</th></tr></thead>
              <tbody>
                {BEDROOM_ORDER.filter((b) => b in p.property_profile.median_rent_by_bedrooms).map((b) => (
                  <tr key={b}><td>{b}</td><td className="num">{fmtDollars(p.property_profile.median_rent_by_bedrooms[b])}/wk</td><td className="num">{p.property_profile.bedrooms[b]}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="card" aria-labelledby="liv-h">
        <h2 id="liv-h">Livability breakdown</h2>
        <p className="subtle">Each score is 0 to 100 against all {meta.n_suburbs} suburbs (100 = best). The overall score is their average.</p>
        <BarList title={`Livability domain scores for ${p.display}`} max={100} labelWidth={130}
          data={domains.map(([d, v]) => ({ label: d, value: v, display: v.toFixed(0) }))} />
      </section>
    </>
  );
}

function Method({ meta }: { meta: ProfilesFile["meta"] }) {
  return (
    <section className="card" aria-labelledby="pm-h">
      <h2 id="pm-h">How these rankings work</h2>
      <ul className="small" style={{ paddingLeft: 20 }}>
        <li>
          <strong>Affordability</strong> is the median asking rent divided by the median weekly income recorded for the suburb.
          Lower is more affordable. It measures rent relative to local incomes, so a high-income suburb can rank as affordable even
          with high rents. Ranked only for suburbs with {meta.min_listings_affordability}+ listings, and it reflects that suburb's mix of
          property types.
        </li>
        <li>
          <strong>Livability</strong> is the average of seven equally weighted scores: safety (crime rate), public transport (road
          distance to the nearest train station and bus stop), schools (primary and secondary), health care (GP and hospital),
          shopping, parks and CBD access. Each is the suburb's percentile among all suburbs, using the median over its listings. It is a
          simple index built from the data available, not an official measure.
        </li>
        <li>
          <strong>Forecast growth</strong> is the suburb area's ARIMA forecast for Sep 2031 over Sep 2026, ranked against every area
          with a forecast. Listing suburbs are matched to forecast areas by name; some forecast areas group several suburbs.
        </li>
        <li>
          Listings data: {meta.n_listings.toLocaleString()} rental listings from {meta.listing_dates[0]} to {meta.listing_dates[1]}, mostly Jul
          to Sep 2025. Crime, income and population may be backfilled in the source data.
        </li>
      </ul>
    </section>
  );
}
