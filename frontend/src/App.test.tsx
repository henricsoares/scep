import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from './App';
import { AuthProvider } from './auth/AuthContext';
import { analytics, facility, occupancySeries, publication, station, user } from './test/fixtures';

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function backend(options: { analyticsForbidden?: boolean; noFacilities?: boolean } = {}) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(typeof input === 'string' ? input : input.toString());
    if (url.pathname === '/auth/login') {
      expect(init?.method).toBe('POST');
      return response({ access_token: 'demo-token', token_type: 'bearer', expires_in: 1800 });
    }
    if (url.pathname === '/auth/me') return response(user);
    if (url.pathname === '/health') return response({ status: 'ok', service: 'SCEP Backend API', version: '1.12.0', environment: 'test' });
    if (url.pathname === '/facilities') return response(options.noFacilities ? [] : [facility]);
    if (url.pathname === `/facilities/${facility.id}/stations`) return response([station]);
    if (url.pathname === '/analytics/overview') {
      if (options.analyticsForbidden) return response({ detail: 'analytical scope forbidden' }, 403);
      return response(analytics);
    }
    if (url.pathname === '/analytics/occupancy') {
      if (options.analyticsForbidden) return response({ detail: 'analytical scope forbidden' }, 403);
      return response(occupancySeries);
    }
    if (url.pathname === '/predictions/weekly-occupancy-publications/current') {
      expect(url.searchParams.get('include_profile')).toBe('true');
      return response(publication);
    }
    if (url.pathname === '/predictions/weekly-occupancy/point') {
      return response({
        scope: publication.scope,
        day_of_week: url.searchParams.get('day_of_week'),
        hour_of_day: Number(url.searchParams.get('hour_of_day')),
        timezone: 'UTC',
        expected_occupancy_rate: 0.25,
        expected_availability_rate: 0.75,
        basis: 'RECURRING_WEEKLY_PATTERN',
        availability_guaranteed: false,
      });
    }
    throw new Error(`Unhandled API request: ${url.pathname}`);
  });
}

function renderApp() {
  return render(<AuthProvider><App /></AuthProvider>);
}

function openPage(name: string) {
  fireEvent.click(screen.getAllByRole('button', { name })[0]);
}

describe('SCEP dashboard', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', backend());
  });

  it('authenticates through the Backend and keeps the token for the browser session', async () => {
    renderApp();
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'admin@example.com' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'local-password' } });
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(await screen.findByText('Smart charging, from operations to predictions.')).toBeInTheDocument();
    expect(sessionStorage.getItem('scep.accessToken')).toBe('demo-token');
    expect(screen.queryByDisplayValue('local-password')).not.toBeInTheDocument();
  });

  it('renders Infrastructure and Analytics data returned by public APIs', async () => {
    sessionStorage.setItem('scep.accessToken', 'demo-token');
    renderApp();
    await screen.findByText('Smart charging, from operations to predictions.');

    openPage('Infrastructure');
    expect(await screen.findAllByText('North Station')).toHaveLength(2);
    expect(screen.getByText('Type2')).toBeInTheDocument();
    expect(screen.getByText('22 kW maximum')).toBeInTheDocument();

    openPage('Analytics');
    expect(await screen.findByText('Operational KPIs')).toBeInTheDocument();
    expect(screen.getByText('Reservations').closest('article')).toHaveTextContent('24');
    expect(screen.getByText('Effective occupancy').closest('article')).toHaveTextContent('8.0%');
    expect(screen.getByLabelText('Daily reserved and effective occupancy series')).toBeInTheDocument();
  });

  it('renders exactly 168 prediction buckets and performs point lookup', async () => {
    sessionStorage.setItem('scep.accessToken', 'demo-token');
    renderApp();
    await screen.findByText('Smart charging, from operations to predictions.');
    openPage('Predictions');

    expect(await screen.findByTestId('prediction-heatmap')).toBeInTheDocument();
    expect(screen.getAllByTestId('prediction-bucket')).toHaveLength(168);
    expect(screen.getByLabelText('MONDAY 0:00 — occupancy 0.0%, availability 100.0%')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Look up' }));
    const result = await screen.findByRole('status');
    expect(result).toHaveTextContent('25.0%');
    expect(result).toHaveTextContent('75.0%');
    expect(result).toHaveTextContent('recurring pattern, not guaranteed');
  });

  it('shows a loading state while restoring an existing session', () => {
    sessionStorage.setItem('scep.accessToken', 'demo-token');
    vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(() => undefined)));
    renderApp();
    expect(screen.getByRole('status')).toHaveTextContent('Restoring SCEP session');
  });

  it('shows an explicit empty state when no infrastructure is visible', async () => {
    sessionStorage.setItem('scep.accessToken', 'demo-token');
    vi.stubGlobal('fetch', backend({ noFacilities: true }));
    renderApp();
    await screen.findByText('Smart charging, from operations to predictions.');
    openPage('Infrastructure');
    expect(await screen.findByText('No Facilities are visible to this account.')).toBeInTheDocument();
  });

  it('clears an invalid session after a 401 response', async () => {
    sessionStorage.setItem('scep.accessToken', 'expired-token');
    vi.stubGlobal('fetch', vi.fn(async () => response({ detail: 'invalid token' }, 401)));
    renderApp();

    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeInTheDocument();
    expect(screen.getByText('Your session expired. Sign in again to continue.')).toBeInTheDocument();
    expect(sessionStorage.getItem('scep.accessToken')).toBeNull();
  });

  it('shows forbidden Analytics feedback without exposing data or ending the session', async () => {
    sessionStorage.setItem('scep.accessToken', 'demo-token');
    vi.stubGlobal('fetch', backend({ analyticsForbidden: true }));
    renderApp();
    await screen.findByText('Smart charging, from operations to predictions.');
    openPage('Analytics');

    expect(await screen.findByRole('alert')).toHaveTextContent('not authorized');
    expect(screen.queryByText('Operational KPIs')).not.toBeInTheDocument();
    expect(sessionStorage.getItem('scep.accessToken')).toBe('demo-token');
    await waitFor(() => expect(screen.getByText('Demo Administrator')).toBeInTheDocument());
  });
});
