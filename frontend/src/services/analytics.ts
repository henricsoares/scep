import { apiRequest } from './api';

export type AnalyticsWindow = { from: string; to: string; timezone: string };
export type AnalyticsScope = {
  facility_id: string | null;
  station_id: string | null;
  connector_id: string | null;
};

export type ReservationMetrics = {
  total_reservations: number;
  fulfilled_reservations: number;
  cancelled_reservations: number;
  late_cancelled_reservations: number;
  no_show_reservations: number;
  pending_reservations: number;
  reservation_fulfillment_rate: number | null;
  cancellation_rate: number | null;
  late_cancellation_rate: number | null;
  no_show_rate: number | null;
};

export type OccupancyMetrics = {
  available_duration_minutes: number;
  reserved_duration_minutes: number;
  charging_duration_minutes: number;
  effective_reserved_charging_duration_minutes: number;
  unused_reserved_duration_minutes: number;
  reserved_occupancy_rate: number | null;
  effective_occupancy_rate: number | null;
  reserved_time_utilization_rate: number | null;
};

export type ChargingSessionMetrics = {
  total_charging_sessions: number;
  active_charging_sessions: number;
  completed_charging_sessions: number;
  average_session_duration_minutes: number | null;
  average_session_start_delay_minutes: number | null;
  on_time_start_rate: number | null;
};

export type EnergyMetrics = {
  total_delivered_energy_kwh: number;
  sessions_with_energy_data: number;
  sessions_without_energy_data: number;
  average_energy_per_session_kwh: number | null;
};

export type AnalyticsOverview = {
  window: AnalyticsWindow;
  scope: AnalyticsScope;
  reservations: ReservationMetrics;
  capacity: OccupancyMetrics;
  charging_sessions: ChargingSessionMetrics;
  energy: EnergyMetrics;
};

export type OccupancySeriesItem = {
  from: string;
  to: string;
  metrics: OccupancyMetrics;
};

export type OccupancySeries = {
  window: AnalyticsWindow;
  scope: AnalyticsScope;
  metrics: OccupancyMetrics;
  series?: OccupancySeriesItem[];
};

function query(facilityId: string, from: string, to: string, granularity?: string): string {
  const params = new URLSearchParams({ facility_id: facilityId, from, to });
  if (granularity) params.set('granularity', granularity);
  return params.toString();
}

export function fetchAnalyticsOverview(
  token: string,
  facilityId: string,
  from: string,
  to: string,
): Promise<AnalyticsOverview> {
  return apiRequest<AnalyticsOverview>(`/analytics/overview?${query(facilityId, from, to)}`, {
    token,
  });
}

export function fetchOccupancySeries(
  token: string,
  facilityId: string,
  from: string,
  to: string,
): Promise<OccupancySeries> {
  return apiRequest<OccupancySeries>(
    `/analytics/occupancy?${query(facilityId, from, to, 'day')}`,
    { token },
  );
}
