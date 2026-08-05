import { apiRequest } from './api';

export type HealthResponse = {
  status: 'ok';
  service: string;
  version: string;
  environment: string;
};

export function fetchHealth(): Promise<HealthResponse> {
  return apiRequest<HealthResponse>('/health');
}
