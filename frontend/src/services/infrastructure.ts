import { apiRequest } from './api';

export type Facility = {
  id: string;
  name: string;
  facility_type: string;
  timezone: string;
  country: string;
  city: string;
  address: string;
  latitude: number | null;
  longitude: number | null;
  operating_hours: Record<string, unknown> | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export type Connector = {
  id: string;
  charging_station_id: string;
  connector_type: string;
  maximum_power_kw: number;
  status: string;
  created_at: string;
  updated_at: string;
};

export type ChargingStation = {
  id: string;
  facility_id: string;
  name: string;
  description: string | null;
  serial_number: string;
  manufacturer: string | null;
  model: string | null;
  maximum_power_kw: number;
  status: string;
  connectors: Connector[];
  created_at: string;
  updated_at: string;
};

export function fetchFacilities(token: string): Promise<Facility[]> {
  return apiRequest<Facility[]>('/facilities', { token });
}

export function fetchStations(token: string, facilityId: string): Promise<ChargingStation[]> {
  return apiRequest<ChargingStation[]>(`/facilities/${facilityId}/stations`, { token });
}
