import type { AnalyticsOverview, OccupancySeries } from '../services/analytics';
import type { ChargingStation, Facility } from '../services/infrastructure';
import { WEEKDAYS, type CurrentPublication, type PredictionBucket } from '../services/predictions';

export const user = {
  id: '00000000-0000-4000-8000-000000000010',
  email: 'admin@example.com',
  display_name: 'Demo Administrator',
  account_type: 'Human',
  status: 'Active',
  roles: ['PlatformAdministrator'],
  facility_ids: [],
  technical_profile: null,
};

export const facility: Facility = {
  id: '00000000-0000-4000-8000-000000000001',
  name: 'Research Campus',
  facility_type: 'University',
  timezone: 'UTC',
  country: 'Brazil',
  city: 'Juiz de Fora',
  address: 'Campus road',
  latitude: null,
  longitude: null,
  operating_hours: null,
  status: 'Active',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

export const station: ChargingStation = {
  id: '00000000-0000-4000-8000-000000000002',
  facility_id: facility.id,
  name: 'North Station',
  description: 'Research charger',
  serial_number: 'SCEP-001',
  manufacturer: 'SCEP',
  model: 'AC-22',
  maximum_power_kw: 22,
  status: 'Active',
  connectors: [{
    id: '00000000-0000-4000-8000-000000000003',
    charging_station_id: '00000000-0000-4000-8000-000000000002',
    connector_type: 'Type2',
    maximum_power_kw: 22,
    status: 'Available',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  }],
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const occupancy = {
  available_duration_minutes: 43_200,
  reserved_duration_minutes: 4_320,
  charging_duration_minutes: 3_456,
  effective_reserved_charging_duration_minutes: 3_000,
  unused_reserved_duration_minutes: 1_320,
  reserved_occupancy_rate: 0.1,
  effective_occupancy_rate: 0.08,
  reserved_time_utilization_rate: 0.69,
};

export const analytics: AnalyticsOverview = {
  window: { from: '2026-01-01T00:00:00Z', to: '2026-02-01T00:00:00Z', timezone: 'UTC' },
  scope: { facility_id: facility.id, station_id: null, connector_id: null },
  reservations: {
    total_reservations: 24,
    fulfilled_reservations: 20,
    cancelled_reservations: 1,
    late_cancelled_reservations: 1,
    no_show_reservations: 2,
    pending_reservations: 0,
    reservation_fulfillment_rate: 0.8333,
    cancellation_rate: 0.0417,
    late_cancellation_rate: 0.0417,
    no_show_rate: 0.0833,
  },
  capacity: occupancy,
  charging_sessions: {
    total_charging_sessions: 20,
    active_charging_sessions: 0,
    completed_charging_sessions: 20,
    average_session_duration_minutes: 72,
    average_session_start_delay_minutes: 2,
    on_time_start_rate: 0.9,
  },
  energy: {
    total_delivered_energy_kwh: 320.5,
    sessions_with_energy_data: 18,
    sessions_without_energy_data: 2,
    average_energy_per_session_kwh: 17.8,
  },
};

export const occupancySeries: OccupancySeries = {
  window: analytics.window,
  scope: analytics.scope,
  metrics: occupancy,
  series: [
    { from: '2026-01-01T00:00:00Z', to: '2026-01-02T00:00:00Z', metrics: occupancy },
    { from: '2026-01-02T00:00:00Z', to: '2026-01-03T00:00:00Z', metrics: { ...occupancy, effective_occupancy_rate: 0.12 } },
  ],
};

export const buckets: PredictionBucket[] = WEEKDAYS.flatMap((day, dayIndex) =>
  Array.from({ length: 24 }, (_, hour) => {
    const expected_occupancy_rate = (dayIndex + hour) / 100;
    return {
      day_of_week: day,
      hour_of_day: hour,
      expected_occupancy_rate,
      expected_availability_rate: 1 - expected_occupancy_rate,
    };
  }),
);

export const publication: CurrentPublication = {
  id: '00000000-0000-4000-8000-000000000004',
  prediction_type: 'WEEKLY_OCCUPANCY',
  cycle: 'WEEKLY',
  granularity: 'HOUR',
  scope: { scope_type: 'FACILITY', facility_id: facility.id },
  timezone: 'UTC',
  contract_version: '1.0',
  model_name: 'weekday-hour-mean',
  model_version: '1.0.0',
  generated_at: '2026-02-01T00:00:00Z',
  accepted_at: '2026-02-01T00:01:00Z',
  bucket_count: 168,
  is_current: true,
  buckets,
};
