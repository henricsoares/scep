import { useEffect, useState, type FormEvent } from 'react';
import { ErrorState, LoadingState } from '../components/AsyncState';
import { KpiCard } from '../components/KpiCard';
import {
  fetchAnalyticsOverview,
  fetchOccupancySeries,
  type AnalyticsOverview,
  type OccupancySeries,
} from '../services/analytics';
import { readableError } from '../services/api';
import { fetchFacilities, type Facility } from '../services/infrastructure';

function localInput(date: Date): string {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function percent(value: number | null): string {
  return value === null ? 'Not available' : `${(value * 100).toFixed(1)}%`;
}

export function AnalyticsPage({ token }: { token: string }) {
  const now = new Date();
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [facilityId, setFacilityId] = useState('');
  const [from, setFrom] = useState(() => localInput(new Date(now.getTime() - 30 * 86_400_000)));
  const [to, setTo] = useState(() => localInput(now));
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [occupancy, setOccupancy] = useState<OccupancySeries | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchFacilities(token)
      .then((items) => {
        setFacilities(items);
        setFacilityId(items[0]?.id || '');
        if (!items.length) setLoading(false);
      })
      .catch((reason) => { setError(readableError(reason)); setLoading(false); });
  }, [token]);

  async function loadAnalytics(selectedFacility = facilityId) {
    if (!selectedFacility) return;
    setLoading(true);
    setError(null);
    try {
      const fromIso = new Date(from).toISOString();
      const toIso = new Date(to).toISOString();
      const [summary, series] = await Promise.all([
        fetchAnalyticsOverview(token, selectedFacility, fromIso, toIso),
        fetchOccupancySeries(token, selectedFacility, fromIso, toIso),
      ]);
      setOverview(summary);
      setOccupancy(series);
    } catch (reason) {
      setError(readableError(reason));
      setOverview(null);
      setOccupancy(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (facilityId) void loadAnalytics(facilityId);
    // The time window is intentionally applied only by the form.
  }, [facilityId]);

  function submit(event: FormEvent) {
    event.preventDefault();
    void loadAnalytics();
  }

  return <div className="page-stack">
    <header className="page-header"><div><p className="eyebrow">SPEC-010</p><h1>Analytics</h1><p>Backend-calculated operational indicators for one Facility and a half-open analysis window.</p></div></header>
    <form className="control-panel analytics-controls" onSubmit={submit}>
      <label>Facility<select value={facilityId} onChange={(event) => setFacilityId(event.target.value)} disabled={!facilities.length}>{facilities.length ? facilities.map((facility) => <option key={facility.id} value={facility.id}>{facility.name}</option>) : <option>No visible Facilities</option>}</select></label>
      <label>From<input type="datetime-local" value={from} onChange={(event) => setFrom(event.target.value)} required /></label>
      <label>To<input type="datetime-local" value={to} onChange={(event) => setTo(event.target.value)} required /></label>
      <button className="primary-button" disabled={!facilityId || loading}>Apply window</button>
    </form>
    {loading && <LoadingState label="Calculating Analytics in the Backend…" />}
    {error && <ErrorState message={error} />}
    {overview && !loading && <>
      <section><div className="section-heading"><div><p className="eyebrow">Backend response</p><h2>Operational KPIs</h2></div><small>{new Date(overview.window.from).toLocaleDateString()} – {new Date(overview.window.to).toLocaleDateString()} · {overview.window.timezone}</small></div>
        <div className="kpi-grid analytics-kpis">
          <KpiCard label="Reservations" value={String(overview.reservations.total_reservations)} detail={`${overview.reservations.fulfilled_reservations} fulfilled`} />
          <KpiCard label="No-shows" value={String(overview.reservations.no_show_reservations)} detail={percent(overview.reservations.no_show_rate)} />
          <KpiCard label="Fulfillment rate" value={percent(overview.reservations.reservation_fulfillment_rate)} />
          <KpiCard label="Reserved occupancy" value={percent(overview.capacity.reserved_occupancy_rate)} />
          <KpiCard label="Effective occupancy" value={percent(overview.capacity.effective_occupancy_rate)} />
          <KpiCard label="Charging Sessions" value={String(overview.charging_sessions.total_charging_sessions)} detail={`${overview.charging_sessions.completed_charging_sessions} completed`} />
          <KpiCard label="Charging duration" value={`${overview.capacity.charging_duration_minutes.toFixed(0)} min`} />
          <KpiCard label="Delivered energy" value={`${overview.energy.total_delivered_energy_kwh.toFixed(1)} kWh`} detail={`${overview.energy.sessions_with_energy_data} Sessions with data`} />
        </div>
      </section>
      <section className="chart-card">
        <div className="section-heading"><div><p className="eyebrow">Daily series</p><h2>Occupancy over time</h2></div><div className="legend"><span><i className="legend-reserved" />Reserved</span><span><i className="legend-effective" />Effective</span></div></div>
        {occupancy?.series?.length ? <div className="bar-chart" aria-label="Daily reserved and effective occupancy series">{occupancy.series.map((item) => <div className="bar-group" key={item.from} title={`${new Date(item.from).toLocaleDateString()}: reserved ${percent(item.metrics.reserved_occupancy_rate)}, effective ${percent(item.metrics.effective_occupancy_rate)}`}><div className="bar-pair"><i className="bar reserved" style={{ height: `${Math.max((item.metrics.reserved_occupancy_rate ?? 0) * 100, 1)}%` }} /><i className="bar effective" style={{ height: `${Math.max((item.metrics.effective_occupancy_rate ?? 0) * 100, 1)}%` }} /></div><small>{new Date(item.from).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</small></div>)}</div> : <p className="state-message">The Backend returned no daily series for this window.</p>}
        <p className="chart-note">Rates and time buckets come directly from the Analytics API. Bar height is a percentage display only.</p>
      </section>
    </>}
  </div>;
}
