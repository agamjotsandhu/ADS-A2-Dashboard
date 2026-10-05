import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { createElement, type ReactElement } from "react";
import { afterEach, vi } from "vitest";

afterEach(() => cleanup());

class RO {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = RO as unknown as typeof ResizeObserver;

// jsdom has no layout, so give Recharts' responsive wrapper a fixed size.
vi.mock("recharts", async (orig) => {
  const mod = await orig<typeof import("recharts")>();
  return {
    ...mod,
    ResponsiveContainer: ({ children }: { children: ReactElement }) =>
      createElement("div", { style: { width: 800, height: 300 } },
        createElement(mod.ResponsiveContainer, { width: 800, height: 300, children })),
  };
});
