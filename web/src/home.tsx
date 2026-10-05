import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Layout } from "./components/Layout";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Layout current="home">
      <h1>Melbourne Rent Insights</h1>
      <p className="lede">Data-driven views of rents across Victoria.</p>
      <div className="card">
        <h2>Rent forecast</h2>
        <p className="subtle">Suburb median rent forecasts to 2031 and a property rent estimator with prediction intervals.</p>
        <a className="btn" href="/rent-forecast/" style={{ display: "inline-block", textDecoration: "none" }}>Open rent forecast</a>
      </div>
    </Layout>
  </StrictMode>,
);
