import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import { EmptyState, ErrorState, LoadingState } from '../components/AsyncState';
import { PredictionHeatmap } from '../components/PredictionHeatmap';
import { ApiError, readableError } from '../services/api';
import {
  fetchFacilities,
  fetchStations,
  type ChargingStation,
  type Facility,
} from '../services/infrastructure';
import {
  fetchCurrentPublication,
  fetchPointPrediction,
  WEEKDAYS,
  type CurrentPublication,
  type PointPrediction,
  type PredictionScope,
  type PredictionScopeType,
  type Weekday,
} from '../services/predictions';

function percent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function PredictionsPage({ token }: { token: string }) {
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [stations, setStations] = useState<ChargingStation[]>([]);
  const [facilityId, setFacilityId] = useState('');
  const [stationId, setStationId] = useState('');
  const [connectorId, setConnectorId] = useState('');
  const [scopeType, setScopeType] = useState<PredictionScopeType>('FACILITY');
  const [publication, setPublication] = useState<CurrentPublication | null>(null);
  const [point, setPoint] = useState<PointPrediction | null>(null);
  const [day, setDay] = useState<Weekday>('MONDAY');
  const [hour, setHour] = useState(8);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [empty, setEmpty] = useState(false);
  const stationsRequestVersion = useRef(0);
  const publicationRequestVersion = useRef(0);
  const pointRequestVersion = useRef(0);

  function clearPredictionState() {
    publicationRequestVersion.current += 1;
    pointRequestVersion.current += 1;
    setPublication(null);
    setPoint(null);
    setError(null);
    setEmpty(false);
    setLoading(false);
  }

  function selectFacility(nextFacilityId: string) {
    stationsRequestVersion.current += 1;
    setFacilityId(nextFacilityId);
    setStations([]);
    setStationId('');
    setConnectorId('');
    clearPredictionState();
  }

  function selectStation(nextStationId: string) {
    setStationId(nextStationId);
    setConnectorId('');
    clearPredictionState();
  }

  function selectScopeType(nextScopeType: PredictionScopeType) {
    setScopeType(nextScopeType);
    clearPredictionState();
  }

  useEffect(() => {
    fetchFacilities(token)
      .then((items) => { setFacilities(items); setFacilityId(items[0]?.id || ''); if (!items.length) setLoading(false); })
      .catch((reason) => { setError(readableError(reason)); setLoading(false); });
  }, [token]);

  useEffect(() => {
    const requestVersion = ++stationsRequestVersion.current;
    if (!facilityId) { setStations([]); return; }
    const controller = new AbortController();
    fetchStations(token, facilityId, controller.signal)
      .then((items) => {
        if (requestVersion !== stationsRequestVersion.current) return;
        const firstStation = items.find((item) => item.facility_id === facilityId);
        setStations(items);
        setStationId(firstStation?.id || '');
        setConnectorId(firstStation?.connectors[0]?.id || '');
      })
      .catch((reason) => {
        if (requestVersion !== stationsRequestVersion.current || controller.signal.aborted) return;
        setError(readableError(reason));
      });
    return () => controller.abort();
  }, [token, facilityId]);

  const selectedStation = stations.find(
    (station) => station.id === stationId && station.facility_id === facilityId,
  );
  const selectedConnector = selectedStation?.connectors.find(
    (connector) => connector.id === connectorId
      && connector.charging_station_id === selectedStation.id,
  );
  useEffect(() => {
    setConnectorId(selectedStation?.connectors[0]?.id || '');
  }, [selectedStation]);

  const scope = useMemo<PredictionScope | null>(() => {
    if (!facilityId) return null;
    if (scopeType === 'FACILITY') return { scope_type: scopeType, facility_id: facilityId };
    if (!selectedStation) return null;
    if (scopeType === 'STATION') return { scope_type: scopeType, facility_id: facilityId, station_id: selectedStation.id };
    if (!selectedConnector) return null;
    return { scope_type: scopeType, facility_id: facilityId, station_id: selectedStation.id, connector_id: selectedConnector.id };
  }, [scopeType, facilityId, selectedStation, selectedConnector]);

  useEffect(() => {
    const requestVersion = ++publicationRequestVersion.current;
    setPublication(null);
    setPoint(null);
    setError(null);
    setEmpty(false);
    if (!scope) { setLoading(false); return; }
    const controller = new AbortController();
    setLoading(true);
    fetchCurrentPublication(token, scope, controller.signal)
      .then((result) => {
        if (requestVersion === publicationRequestVersion.current) setPublication(result);
      })
      .catch((reason) => {
        if (requestVersion !== publicationRequestVersion.current || controller.signal.aborted) return;
        setPublication(null);
        if (reason instanceof ApiError && reason.status === 404) setEmpty(true);
        else setError(readableError(reason));
      })
      .finally(() => {
        if (requestVersion === publicationRequestVersion.current) setLoading(false);
      });
    return () => controller.abort();
  }, [token, scope]);

  async function lookup(event: FormEvent) {
    event.preventDefault();
    if (!scope) return;
    const requestVersion = ++pointRequestVersion.current;
    const controller = new AbortController();
    setError(null);
    try {
      const result = await fetchPointPrediction(token, scope, day, hour, controller.signal);
      if (requestVersion === pointRequestVersion.current) setPoint(result);
    } catch (reason) {
      if (requestVersion !== pointRequestVersion.current || controller.signal.aborted) return;
      setPoint(null);
      setError(readableError(reason));
    }
  }

  return <div className="page-stack">
    <header className="page-header"><div><p className="eyebrow">SPEC-012</p><h1>Weekly Occupancy Predictions</h1><p>Inspect one externally generated recurring profile. The Backend stores and serves predictions; it does not train or run the model.</p></div></header>
    <section className="control-panel prediction-controls">
      <label>Scope<select value={scopeType} onChange={(event) => selectScopeType(event.target.value as PredictionScopeType)}><option value="FACILITY">Facility</option><option value="STATION">Station</option><option value="CONNECTOR">Connector</option></select></label>
      <label>Facility<select value={facilityId} onChange={(event) => selectFacility(event.target.value)}>{facilities.map((facility) => <option key={facility.id} value={facility.id}>{facility.name}</option>)}</select></label>
      {scopeType !== 'FACILITY' && <label>Station<select value={stationId} onChange={(event) => selectStation(event.target.value)}>{stations.map((station) => <option key={station.id} value={station.id}>{station.name}</option>)}</select></label>}
      {scopeType === 'CONNECTOR' && <label>Connector<select value={connectorId} onChange={(event) => setConnectorId(event.target.value)}>{selectedStation?.connectors.map((connector) => <option key={connector.id} value={connector.id}>{connector.connector_type} · {connector.maximum_power_kw} kW</option>)}</select></label>}
    </section>
    {loading && <LoadingState label="Loading current weekly profile…" />}
    {error && <ErrorState message={error} />}
    {empty && !loading && <EmptyState message={`No current ${scopeType.toLowerCase()} publication exists for the selected scope.`} />}
    {publication && !loading && <>
      <section className="publication-card">
        <div className="section-heading"><div><p className="eyebrow">Current publication</p><h2>Recurring weekly profile</h2></div><span className="current-pill">Current</span></div>
        <dl className="publication-meta"><div><dt>Generated</dt><dd>{new Date(publication.generated_at).toLocaleString()}</dd></div><div><dt>Timezone</dt><dd>{publication.timezone}</dd></div><div><dt>Contract</dt><dd>{publication.contract_version}</dd></div><div><dt>Buckets</dt><dd>{publication.bucket_count}</dd></div>{publication.model_name && <div><dt>Model</dt><dd>{publication.model_name} {publication.model_version}</dd></div>}<div><dt>Basis</dt><dd>Recurring weekly pattern</dd></div></dl>
        {publication.buckets?.length === 168 ? <PredictionHeatmap buckets={publication.buckets} /> : <ErrorState message={`The Backend returned ${publication.buckets?.length ?? 0} buckets; a complete profile requires 168.`} />}
        <div className="heatmap-legend"><span>Lower occupancy</span><i /><span>Higher occupancy</span><small>Cell labels show occupancy %. Hover or focus for occupancy and availability.</small></div>
      </section>
      <section className="point-card">
        <div><p className="eyebrow">Point lookup</p><h2>Inspect one recurring bucket</h2><p>This is not a prediction for a specific calendar date and does not guarantee availability.</p></div>
        <form onSubmit={lookup}><label>Local weekday<select value={day} onChange={(event) => setDay(event.target.value as Weekday)}>{WEEKDAYS.map((weekday) => <option key={weekday}>{weekday}</option>)}</select></label><label>Local hour<select value={hour} onChange={(event) => setHour(Number(event.target.value))}>{Array.from({ length: 24 }, (_, item) => <option key={item} value={item}>{String(item).padStart(2, '0')}:00</option>)}</select></label><button className="primary-button">Look up</button></form>
        {point && <div className="point-result" role="status"><div><span>Expected occupancy</span><strong>{percent(point.expected_occupancy_rate)}</strong></div><div><span>Expected availability</span><strong>{percent(point.expected_availability_rate)}</strong></div><small>{point.day_of_week} {String(point.hour_of_day).padStart(2, '0')}:00 · {point.timezone} · recurring pattern, not guaranteed</small></div>}
      </section>
    </>}
  </div>;
}
