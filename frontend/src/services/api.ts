const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export const API_BASE_URL = configuredBaseUrl.replace(/\/$/, '');
export const UNAUTHORIZED_EVENT = 'scep:unauthorized';

type ErrorDetail = string | { code?: string; message?: string; request_id?: string };

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly code?: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

function errorDetails(payload: unknown, status: number): { message: string; code?: string } {
  if (payload && typeof payload === 'object' && 'detail' in payload) {
    const detail = (payload as { detail: ErrorDetail }).detail;
    if (typeof detail === 'string') return { message: detail };
    if (detail?.message) return { message: detail.message, code: detail.code };
  }
  return { message: `Backend request failed (${status})` };
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit & { token?: string | null } = {},
): Promise<T> {
  const { token, headers: suppliedHeaders, ...requestOptions } = options;
  const headers = new Headers(suppliedHeaders);
  if (requestOptions.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  if (token) headers.set('Authorization', `Bearer ${token}`);

  const response = await fetch(`${API_BASE_URL}${path}`, { ...requestOptions, headers });
  if (!response.ok) {
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    const details = errorDetails(payload, response.status);
    if (response.status === 401 && token) window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    throw new ApiError(response.status, details.message, details.code);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function readableError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Your session is invalid or expired. Sign in again.';
    if (error.status === 403) return 'Your account is not authorized to view this information.';
    return error.message;
  }
  if (error instanceof Error) return error.message;
  return 'An unexpected error occurred.';
}
