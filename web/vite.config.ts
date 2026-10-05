/// <reference types="vitest/config" />
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      input: {
        home: fileURLToPath(new URL("index.html", import.meta.url)),
        rentForecast: fileURLToPath(new URL("rent-forecast/index.html", import.meta.url)),
        suburbProfile: fileURLToPath(new URL("suburb-profile/index.html", import.meta.url)),
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["src/test/setup.ts"],
  },
});
