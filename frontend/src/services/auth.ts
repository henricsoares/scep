import { apiRequest } from './api';

export type LoginResponse = {
  access_token: string;
  token_type: 'bearer';
  expires_in: number;
};

export type CurrentUser = {
  id: string;
  email: string;
  display_name: string;
  account_type: string;
  status: string;
  roles: string[];
  facility_ids: string[];
  technical_profile: string | null;
};

export function login(email: string, password: string): Promise<LoginResponse> {
  return apiRequest<LoginResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}

export function fetchCurrentUser(token: string): Promise<CurrentUser> {
  return apiRequest<CurrentUser>('/auth/me', { token });
}
