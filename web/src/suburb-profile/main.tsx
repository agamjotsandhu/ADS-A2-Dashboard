import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "../styles.css";
import { SuburbProfilePage } from "./SuburbProfilePage";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <SuburbProfilePage />
  </StrictMode>,
);
