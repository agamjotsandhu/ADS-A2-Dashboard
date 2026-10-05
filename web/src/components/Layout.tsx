import type { ReactNode } from "react";

export function Layout({ current, children }: { current: "home" | "rent-forecast"; children: ReactNode }) {
  return (
    <>
      <a className="skip-link" href="#main">Skip to content</a>
      <header className="site-header">
        <div className="inner">
          <a className="brand" href="/">Melbourne Rent Insights</a>
          <nav aria-label="Main">
            <a href="/" aria-current={current === "home" ? "page" : undefined}>Home</a>
            <a href="/rent-forecast/" aria-current={current === "rent-forecast" ? "page" : undefined}>Rent forecast</a>
          </nav>
        </div>
      </header>
      <main id="main">{children}</main>
      <footer className="site-footer">
        <div className="inner">Statistical estimates for information only. Not financial or property advice.</div>
      </footer>
    </>
  );
}
