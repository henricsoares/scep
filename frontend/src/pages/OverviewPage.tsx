import { useEffect, useState } from 'react';
import { KpiCard } from '../components/KpiCard';
import { ErrorState, LoadingState } from '../components/AsyncState';
import { fetchAnalyticsOverview, type AnalyticsOverview } from '../services/analytics';
import { readableError } from '../services/api';
import { fetchHealth, type HealthResponse } from '../services/health';
import {
  fetchFacilities,
  fetchStations,
  type ChargingStation,
  type Facility,
} from '../services/infrastructure';

type OverviewData = {
  health: HealthResponse;
  facilities: Facility[];
  stations: ChargingStation[];
  analytics: AnalyticsOverview | null;
};

function percent(value: number | null): string {
  return value === null ? 'Not available' : `${(value * 100).toFixed(1)}%`;
}

function windowForLastDays(days: number): { from: string; to: string } {
  const to = new Date();
  const from = new Date(to.getTime() - days * 24 * 60 * 60 * 1000);
  return { from: from.toISOString(), to: to.toISOString() };
}

export function OverviewPage({ token, navigate }: { token: string; navigate: (page: string) => void }) {
  const [data, setData] = useState<OverviewData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const [health, facilities] = await Promise.all([fetchHealth(), fetchFacilities(token)]);
        const facility = facilities[0];
        const stations = facility ? await fetchStations(token, facility.id) : [];
        let analytics: AnalyticsOverview | null = null;
        if (facility) {
          try {
            const window = windowForLastDays(30);
            analytics = await fetchAnalyticsOverview(token, facility.id, window.from, window.to);
          } catch {
            analytics = null;
          }
        }
        if (active) setData({ health, facilities, stations, analytics });
      } catch (reason) {
        if (active) setError(readableError(reason));
      }
    }
    void load();
    return () => { active = false; };
  }, [token]);

  if (error) return <ErrorState message={error} />;
  if (!data) return <LoadingState label="Loading platform overview…" />;

  const connectorCount = data.stations.reduce((total, station) => total + station.connectors.length, 0);
  return <div className="page-stack">
    <header className="page-header overview-header">
      <div>
        <p className="eyebrow">Platform overview</p>
        <h1>Smart charging, from operations to predictions.</h1>
        <p>SCEP is a research-oriented environment for reproducible EV charging experiments. This dashboard reads the same public APIs used by external clients.</p>
      </div>
      <div className="health-panel">
        <span className="live-dot" />
        <div><strong>Backend {data.health.status}</strong><small>{data.health.service} · {data.health.version} · {data.health.environment}</small></div>
      </div>
    </header>

    <section>
      <div className="section-heading"><div><p className="eyebrow">Current environment</p><h2>Infrastructure at a glance</h2></div><button className="text-button" onClick={() => navigate('infrastructure')}>Explore infrastructure →</button></div>
      <div className="kpi-grid">
        <KpiCard label="Visible Facilities" value={String(data.facilities.length)} />
        <KpiCard label="Stations in first Facility" value={String(data.stations.length)} />
        <KpiCard label="Connectors in first Facility" value={String(connectorCount)} />
        <KpiCard label="Operational data window" value="30 days" detail="Overview default" />
      </div>
    </section>

    <section>
      <div className="section-heading"><div><p className="eyebrow">SPEC-010</p><h2>Selected Analytics KPIs</h2></div><button className="text-button" onClick={() => navigate('analytics')}>Open Analytics →</button></div>
      {data.analytics ? <div className="kpi-grid">
        <KpiCard label="Reservations" value={String(data.analytics.reservations.total_reservations)} />
        <KpiCard label="Fulfillment" value={percent(data.analytics.reservations.reservation_fulfillment_rate)} />
        <KpiCard label="Effective occupancy" value={percent(data.analytics.capacity.effective_occupancy_rate)} />
        <KpiCard label="Delivered energy" value={`${data.analytics.energy.total_delivered_energy_kwh.toFixed(1)} kWh`} />
      </div> : <p className="state-message">Analytics are unavailable for the first visible Facility or current account. Open Analytics to choose another Facility and window.</p>}
    </section>

    <section className="story-card">
      <div><span>01</span><strong>Infrastructure</strong><small>Facilities, Stations and Connectors</small></div>
      <i>→</i><div><span>02</span><strong>Operational history</strong><small>Reservations, Sessions and Telemetry</small></div>
      <i>→</i><div><span>03</span><strong>Research outputs</strong><small>Analytics and recurring Predictions</small></div>
    </section>
  </div>;
}
