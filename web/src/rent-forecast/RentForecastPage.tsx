import { Disclaimer } from "../components/Disclaimer";
import { Layout } from "../components/Layout";
import { Methodology } from "../components/Methodology";
import { PropertyEstimator } from "../components/PropertyEstimator";
import { SuburbForecastSection } from "../components/SuburbForecastSection";

export function RentForecastPage() {
  return (
    <Layout current="rent-forecast">
      <h1>Rent forecast</h1>
      <p className="lede">
        Explore a suburb's median rent history and forecast to 2031, or describe a property for an estimated weekly rent with
        a range. Both are statistical estimates with real uncertainty, explained below.
      </p>
      <Disclaimer />
      <div style={{ height: 24 }} />
      <SuburbForecastSection />
      <PropertyEstimator />
      <Methodology />
    </Layout>
  );
}
