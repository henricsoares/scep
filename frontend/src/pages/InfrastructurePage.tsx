import { useEffect, useRef, useState } from 'react';
import { EmptyState, ErrorState, LoadingState } from '../components/AsyncState';
import { StatusBadge } from '../components/StatusBadge';
import { readableError } from '../services/api';
import {
  fetchFacilities,
  fetchStations,
  type ChargingStation,
  type Facility,
} from '../services/infrastructure';

export function InfrastructurePage({ token }: { token: string }) {
  const [facilities, setFacilities] = useState<Facility[] | null>(null);
  const [facilityId, setFacilityId] = useState('');
  const [stations, setStations] = useState<ChargingStation[] | null>(null);
  const [stationId, setStationId] = useState('');
  const [error, setError] = useState<string | null>(null);
  const stationsRequestVersion = useRef(0);

  function selectFacility(nextFacilityId: string) {
    stationsRequestVersion.current += 1;
    setFacilityId(nextFacilityId);
    setStations(null);
    setStationId('');
    setError(null);
  }

  useEffect(() => {
    fetchFacilities(token)
      .then((items) => {
        setFacilities(items);
        setFacilityId((current) => current || items[0]?.id || '');
      })
      .catch((reason) => setError(readableError(reason)));
  }, [token]);

  useEffect(() => {
    const requestVersion = ++stationsRequestVersion.current;
    if (!facilityId) { setStations([]); return; }
    const controller = new AbortController();
    setStations(null);
    setStationId('');
    setError(null);
    fetchStations(token, facilityId, controller.signal)
      .then((items) => {
        if (requestVersion !== stationsRequestVersion.current) return;
        const firstStation = items.find((item) => item.facility_id === facilityId);
        setStations(items);
        setStationId(firstStation?.id || '');
      })
      .catch((reason) => {
        if (requestVersion !== stationsRequestVersion.current || controller.signal.aborted) return;
        setError(readableError(reason));
      });
    return () => controller.abort();
  }, [token, facilityId]);

  const facility = facilities?.find((item) => item.id === facilityId);
  const station = stations?.find(
    (item) => item.id === stationId && item.facility_id === facilityId,
  );

  return <div className="page-stack">
    <header className="page-header"><div><p className="eyebrow">Read-only browser</p><h1>Infrastructure</h1><p>Inspect the hierarchy and current operational states owned by Facilities and Charging Stations.</p></div></header>
    {error && <ErrorState message={error} />}
    {!facilities && !error && <LoadingState label="Loading visible Facilities…" />}
    {facilities?.length === 0 && <EmptyState message="No Facilities are visible to this account." />}
    {facilities && facilities.length > 0 && <>
      <section className="control-panel">
        <label>Facility<select value={facilityId} onChange={(event) => selectFacility(event.target.value)}>{facilities.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        {facility && <div className="selection-summary"><div><strong>{facility.name}</strong><span>{facility.facility_type} · {facility.city}, {facility.country}</span></div><div><StatusBadge status={facility.status} /><small>{facility.timezone}</small></div></div>}
      </section>
      {!stations && !error && <LoadingState label="Loading Charging Stations…" />}
      {stations?.length === 0 && <EmptyState message="This Facility has no Charging Stations." />}
      {stations && stations.length > 0 && <div className="infrastructure-grid">
        <section className="list-panel"><p className="eyebrow">Charging Stations</p>{stations.map((item) => <button className={`station-item${item.id === stationId ? ' selected' : ''}`} key={item.id} onClick={() => setStationId(item.id)}><span><strong>{item.name}</strong><small>{item.serial_number}</small></span><StatusBadge status={item.status} /></button>)}</section>
        <section className="detail-panel">
          {station && <><div className="section-heading"><div><p className="eyebrow">Selected Station</p><h2>{station.name}</h2></div><StatusBadge status={station.status} /></div><dl className="detail-list"><div><dt>Manufacturer</dt><dd>{station.manufacturer ?? 'Not specified'}</dd></div><div><dt>Model</dt><dd>{station.model ?? 'Not specified'}</dd></div><div><dt>Maximum power</dt><dd>{station.maximum_power_kw} kW</dd></div><div><dt>Connectors</dt><dd>{station.connectors.length}</dd></div></dl><div className="connector-grid">{station.connectors.map((connector) => <article className="connector-card" key={connector.id}><div><span className="connector-icon">⚡</span><StatusBadge status={connector.status} /></div><h3>{connector.connector_type}</h3><p>{connector.maximum_power_kw} kW maximum</p><small title={connector.id}>ID {connector.id.slice(0, 8)}…</small></article>)}</div></>}
        </section>
      </div>}
    </>}
  </div>;
}
