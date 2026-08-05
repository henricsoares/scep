import { apiRequest } from './api';

export const WEEKDAYS = [
  'MONDAY',
  'TUESDAY',
  'WEDNESDAY',
  'THURSDAY',
  'FRIDAY',
  'SATURDAY',
  'SUNDAY',
] as const;

export type Weekday = (typeof WEEKDAYS)[number];
export type PredictionScopeType = 'FACILITY' | 'STATION' | 'CONNECTOR';

export type PredictionScope = {
  scope_type: PredictionScopeType;
  facility_id: string;
  station_id?: string;
  connector_id?: string;
};

export type PredictionBucket = {
  day_of_week: Weekday;
  hour_of_day: number;
  expected_occupancy_rate: number;
  expected_availability_rate: number;
};

export type CurrentPublication = {
  id: string;
  prediction_type: 'WEEKLY_OCCUPANCY';
  cycle: string;
  granularity: string;
  scope: PredictionScope;
  timezone: string;
  contract_version: string;
  model_name?: string;
  model_version?: string;
  external_run_id?: string;
  generated_at: string;
  accepted_at: string;
  dataset_export_id?: string;
  training_data_from?: string;
  training_data_to?: string;
  bucket_count: 168;
  is_current: boolean;
  buckets?: PredictionBucket[];
};

export type PointPrediction = {
  scope: PredictionScope;
  day_of_week: Weekday;
  hour_of_day: number;
  timezone: string;
  expected_occupancy_rate: number;
  expected_availability_rate: number;
  basis: 'RECURRING_WEEKLY_PATTERN';
  availability_guaranteed: false;
};

function scopeQuery(scope: PredictionScope): URLSearchParams {
  const params = new URLSearchParams({
    scope_type: scope.scope_type,
    facility_id: scope.facility_id,
  });
  if (scope.station_id) params.set('station_id', scope.station_id);
  if (scope.connector_id) params.set('connector_id', scope.connector_id);
  return params;
}

export function fetchCurrentPublication(
  token: string,
  scope: PredictionScope,
): Promise<CurrentPublication> {
  const params = scopeQuery(scope);
  params.set('include_profile', 'true');
  return apiRequest<CurrentPublication>(
    `/predictions/weekly-occupancy-publications/current?${params.toString()}`,
    { token },
  );
}

export function fetchPointPrediction(
  token: string,
  scope: PredictionScope,
  dayOfWeek: Weekday,
  hourOfDay: number,
): Promise<PointPrediction> {
  const params = scopeQuery(scope);
  params.set('day_of_week', dayOfWeek);
  params.set('hour_of_day', String(hourOfDay));
  return apiRequest<PointPrediction>(`/predictions/weekly-occupancy/point?${params}`, { token });
}
