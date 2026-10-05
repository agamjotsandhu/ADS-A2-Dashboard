import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "../styles.css";
import { RentForecastPage } from "./RentForecastPage";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RentForecastPage />
  </StrictMode>,
);
