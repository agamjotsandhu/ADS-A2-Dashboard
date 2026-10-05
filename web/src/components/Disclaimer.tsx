export function Disclaimer() {
  return (
    <aside className="disclaimer" aria-labelledby="disclaimer-h">
      <h2 id="disclaimer-h" style={{ fontSize: "1rem" }}>Important</h2>
      <ul style={{ margin: "8px 0 0", paddingLeft: 20 }}>
        <li>These are statistical estimates only. They are not a valuation or appraisal, and not financial or property advice.</li>
        <li>Intervals come from the models and past errors. They are not guarantees, and actual rents can fall outside them.</li>
        <li>Luxury properties (roughly above $2,500/week) are systematically under-estimated.</li>
        <li>Data may be incomplete or revised upstream; suburbs with few listings are less reliable.</li>
      </ul>
    </aside>
  );
}
