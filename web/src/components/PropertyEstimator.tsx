import { useEffect, useId, useMemo, useRef, useState, type FormEvent } from "react";
import {
  fetchSuburbs as defaultFetchSuburbs, predict as defaultPredict, type PredictRequest, type PredictResponse,
  type SuburbsResponse,
} from "../lib/api";
import { fmtDollars, fmtWeekly } from "../lib/format";
import { quarterLabel, quartersBetween } from "../lib/quarters";
import { ProjectionChart } from "./ProjectionChart";
import { SuburbPicker } from "./SuburbPicker";

interface Props {
  fetchSuburbs?: typeof defaultFetchSuburbs;
  predict?: typeof defaultPredict;
}

const NOW = "now";
const COUNTS = Array.from({ length: 11 }, (_, i) => i);

export function PropertyEstimator({ fetchSuburbs = defaultFetchSuburbs, predict = defaultPredict }: Props) {
  const [meta, setMeta] = useState<SuburbsResponse | null>(null);
  const [metaError, setMetaError] = useState<string | null>(null);
  const [form, setForm] = useState<Omit<PredictRequest, "target_date"> & { target: string }>({
    suburb: "", property_type: "", bedrooms: 2, bathrooms: 1, carspaces: 1, amenities: [], target: NOW,
  });
  const [result, setResult] = useState<PredictResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const ids = { type: useId(), beds: useId(), baths: useId(), cars: useId(), date: useId() };

  useEffect(() => {
    const ctl = new AbortController();
    fetchSuburbs(ctl.signal)
      .then((m) => {
        setMeta(m);
        setForm((f) => ({ ...f, property_type: f.property_type || m.property_types.find((t) => t === "House") || m.property_types[0] }));
      })
      .catch((e: Error) => {
        if (e.name !== "AbortError") setMetaError(e.message);
      });
    return () => ctl.abort();
  }, [fetchSuburbs]);

  const suburbOptions = useMemo(
    () => (meta?.suburbs ?? []).map((s) => ({ value: s.name, label: s.display })).sort((a, b) => a.label.localeCompare(b.label)),
    [meta],
  );
  const quarterOptions = useMemo(() => (meta ? quartersBetween(meta.quarters.first, meta.quarters.last) : []), [meta]);
  const selected = meta?.suburbs.find((s) => s.name === form.suburb);

  const pickSuburb = (name: string) => {
    const s = meta?.suburbs.find((x) => x.name === name);
    setForm((f) => (s ? { ...f, suburb: name, ...s.defaults } : { ...f, suburb: name }));
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!form.suburb) {
      setError("Choose a suburb first.");
      return;
    }
    abort.current?.abort();
    const ctl = new AbortController();
    abort.current = ctl;
    setLoading(true);
    setError(null);
    try {
      const { target, ...rest } = form;
      const res = await predict({ ...rest, ...(target !== NOW ? { target_date: target } : {}) }, ctl.signal);
      setResult(res);
    } catch (err) {
      if ((err as Error).name !== "AbortError") setError((err as Error).message);
    } finally {
      if (abort.current === ctl) setLoading(false);
    }
  };

  const num = (key: "bedrooms" | "bathrooms" | "carspaces", id: string, label: string) => (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <select id={id} value={form[key]} onChange={(e) => setForm({ ...form, [key]: Number(e.target.value) })}>
        {COUNTS.map((n) => <option key={n} value={n}>{n}</option>)}
      </select>
    </div>
  );

  return (
    <section className="card" aria-labelledby="estimator-h">
      <div className="section-head">
        <h2 id="estimator-h">Property rent estimator</h2>
        <p className="subtle">
          Describe a property to get a weekly rent estimate with a 90% prediction interval at the Sep 2025 rent level,
          optionally projected forward with the suburb forecast.
        </p>
      </div>

      {metaError && (
        <div className="notice error" role="alert">
          <strong>The estimator is unavailable right now.</strong>{metaError}
        </div>
      )}
      {!meta && !metaError && <p className="empty" role="status">Loading estimator…</p>}

      {meta && (
        <form onSubmit={submit} noValidate>
          <div className="form-grid">
            <div className="wide" style={{ maxWidth: 420 }}>
              <SuburbPicker label="Suburb" options={suburbOptions} value={form.suburb} onChange={pickSuburb} required
                hint={selected
                  ? `${selected.n_listings} training listings. ${selected.has_forecast ? "Suburb forecast available." : "No suburb forecast: estimate at Sep 2025 level only."}`
                  : "Suburbs seen in the listings data."} />
            </div>
            <div className="field">
              <label htmlFor={ids.type}>Property type</label>
              <select id={ids.type} value={form.property_type} onChange={(e) => setForm({ ...form, property_type: e.target.value })}>
                {meta.property_types.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            {num("bedrooms", ids.beds, "Bedrooms")}
            {num("bathrooms", ids.baths, "Bathrooms")}
            {num("carspaces", ids.cars, "Car spaces")}
            <div className="field">
              <label htmlFor={ids.date}>Forecast date</label>
              <select id={ids.date} value={form.target} onChange={(e) => setForm({ ...form, target: e.target.value })}>
                <option value={NOW}>Now (Sep 2025)</option>
                {quarterOptions.map((q) => <option key={q} value={q}>{quarterLabel(q)}</option>)}
              </select>
            </div>
            <fieldset className="wide">
              <legend className="label">Features</legend>
              <div className="checks">
                {meta.amenities.map((a) => (
                  <label key={a.key}>
                    <input type="checkbox" checked={form.amenities.includes(a.key)}
                      onChange={(e) => setForm({
                        ...form,
                        amenities: e.target.checked ? [...form.amenities, a.key] : form.amenities.filter((x) => x !== a.key),
                      })} />
                    {a.label}
                  </label>
                ))}
              </div>
            </fieldset>
            <div className="wide">
              <button className="btn" type="submit" disabled={loading}>{loading ? "Estimating…" : "Estimate rent"}</button>
            </div>
          </div>
        </form>
      )}

      <div aria-live="polite">
        {error && <div className="notice error" role="alert" style={{ marginTop: 16 }}><strong>Couldn't get an estimate.</strong>{error}</div>}
        {result && <Result result={result} loading={loading} />}
      </div>
    </section>
  );
}

function Result({ result, loading }: { result: PredictResponse; loading: boolean }) {
  const t = result.at_target;
  const head = t ?? { point: result.point, lower: result.lower, upper: result.upper, quarter: "2025Q3" };
  const pct = Math.round(result.interval_level * 100);
  return (
    <div className={loading ? "is-loading" : undefined} style={{ marginTop: 24 }}>
      <p className="label" style={{ margin: 0 }}>
        Estimated rent, {t ? `projected to ${quarterLabel(t.quarter)}` : "Sep 2025 level"}
      </p>
      <div className="result-hero">{fmtWeekly(head.point)}</div>
      <p className="result-range">
        {t ? "Combined range" : `${pct}% prediction interval`}: {fmtDollars(head.lower)} to {fmtDollars(head.upper)} per week
        {t && <> · Sep 2025 level {fmtWeekly(result.point)} ({fmtDollars(result.lower)} to {fmtDollars(result.upper)})</>}
      </p>
      {result.warnings.map((w) => (
        <div key={w.code} className={`notice${w.code === "combined_band" ? " info" : ""}`} role="note">
          <strong>{w.code === "combined_band" ? "About this range:" : "Note:"}</strong>{w.message}
        </div>
      ))}
      {result.projection && result.projection.length > 1 && (
        <div style={{ marginTop: 16 }}>
          <h3>Projection over time</h3>
          <ProjectionChart points={result.projection} />
        </div>
      )}
    </div>
  );
}
