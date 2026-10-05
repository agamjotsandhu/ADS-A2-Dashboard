// End-to-end smoke test against a running API (default http://localhost:8000).
// Usage: API_URL=http://localhost:8000 ORIGIN=http://localhost:5173 npm run smoke
const API = (process.env.API_URL ?? "http://localhost:8000").replace(/\/$/, "");
const ORIGIN = process.env.ORIGIN ?? "http://localhost:5173";
let failed = 0;

async function check(name, fn) {
  try {
    await fn();
    console.log(`  ok   ${name}`);
  } catch (e) {
    failed++;
    console.log(`  FAIL ${name}: ${e.message}`);
  }
}
const assert = (cond, msg) => {
  if (!cond) throw new Error(msg);
};
const post = (body) =>
  fetch(`${API}/predict`, { method: "POST", headers: { "Content-Type": "application/json", Origin: ORIGIN }, body: JSON.stringify(body) });

console.log(`Smoke testing ${API}`);
let meta;
await check("GET /health", async () => {
  const r = await fetch(`${API}/health`);
  const b = await r.json();
  assert(r.ok && b.status === "ok", JSON.stringify(b));
});
await check("GET /suburbs", async () => {
  const r = await fetch(`${API}/suburbs`, { headers: { Origin: ORIGIN } });
  meta = await r.json();
  assert(r.ok && meta.suburbs.length > 100, "too few suburbs");
  assert(r.headers.get("access-control-allow-origin") === ORIGIN, "CORS header missing for site origin");
});
await check("POST /predict (current level)", async () => {
  const s = meta.suburbs.find((x) => x.name === "TARNEIT") ?? meta.suburbs[0];
  const r = await post({ suburb: s.name, ...s.defaults, amenities: [meta.amenities[0].key] });
  const b = await r.json();
  assert(r.ok, JSON.stringify(b));
  assert(b.lower < b.point && b.point < b.upper, "interval ordering");
  console.log(`       ${s.display}: $${b.point.toFixed(0)}/wk ($${b.lower.toFixed(0)} to $${b.upper.toFixed(0)})`);
});
await check("POST /predict with target_date", async () => {
  const r = await post({ suburb: "TARNEIT", property_type: "House", bedrooms: 4, bathrooms: 2, carspaces: 2, amenities: [], target_date: "2028Q3" });
  const b = await r.json();
  assert(r.ok, JSON.stringify(b));
  const codes = b.warnings.map((w) => w.code);
  assert(b.projection ? b.projection.at(-1).quarter === "2028Q3" : codes.includes("no_forecast"), "projection or no_forecast warning expected");
});
await check("POST /predict rejects bedrooms=11", async () => {
  const r = await post({ suburb: "TARNEIT", property_type: "House", bedrooms: 11, bathrooms: 2, carspaces: 2, amenities: [] });
  assert(r.status === 422, `status ${r.status}`);
});

console.log(failed ? `${failed} check(s) failed` : "All smoke checks passed");
process.exit(failed ? 1 : 0);
