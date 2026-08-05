import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from './App';
import { AuthProvider } from './auth/AuthContext';
import { InfrastructurePage } from './pages/InfrastructurePage';
import { PredictionsPage } from './pages/PredictionsPage';
import { analytics, facility, occupancySeries, publication, station, user } from './test/fixtures';

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((fulfill) => { resolve = fulfill; });
  return { promise, resolve };
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

  it('transitions prediction hierarchy atomically and ignores a delayed previous response', async () => {
    const facilityB = { ...facility, id: '00000000-0000-4000-8000-000000000011', name: 'South Campus' };
    const stationB = {
      ...station,
      id: '00000000-0000-4000-8000-000000000012',
      facility_id: facilityB.id,
      name: 'South Station',
      connectors: [{
        ...station.connectors[0],
        id: '00000000-0000-4000-8000-000000000013',
        charging_station_id: '00000000-0000-4000-8000-000000000012',
      }],
    };
    const stationsB = deferred<Response>();
    const stalePublication = deferred<Response>();
    const predictionRequests: URL[] = [];

    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(typeof input === 'string' ? input : input.toString());
      if (url.pathname === '/facilities') return response([facility, facilityB]);
      if (url.pathname === `/facilities/${facility.id}/stations`) return response([station]);
      if (url.pathname === `/facilities/${facilityB.id}/stations`) return stationsB.promise;
      if (url.pathname === '/predictions/weekly-occupancy-publications/current') {
        predictionRequests.push(url);
        if (url.searchParams.get('scope_type') === 'CONNECTOR'
          && url.searchParams.get('facility_id') === facility.id) {
          return stalePublication.promise;
        }
        if (url.searchParams.get('facility_id') === facilityB.id) {
          return response({
            ...publication,
            id: '00000000-0000-4000-8000-000000000014',
            model_name: 'facility-b-model',
            scope: {
              scope_type: 'CONNECTOR',
              facility_id: facilityB.id,
              station_id: stationB.id,
              connector_id: stationB.connectors[0].id,
            },
          });
        }
        return response(publication);
      }
      throw new Error(`Unhandled API request: ${url.pathname}`);
    }));

    render(<PredictionsPage token="demo-token" />);
    await screen.findByText('Recurring weekly profile');
    fireEvent.change(screen.getByLabelText('Scope'), { target: { value: 'CONNECTOR' } });
    await waitFor(() => expect(predictionRequests.some((url) =>
      url.searchParams.get('connector_id') === station.connectors[0].id,
    )).toBe(true));

    fireEvent.change(screen.getByLabelText('Facility'), { target: { value: facilityB.id } });
    expect((screen.getByLabelText('Station') as HTMLSelectElement).value).toBe('');
    expect((screen.getByLabelText('Connector') as HTMLSelectElement).value).toBe('');
    expect(predictionRequests.some((url) =>
      url.searchParams.get('facility_id') === facilityB.id
      && url.searchParams.get('station_id') === station.id,
    )).toBe(false);

    await act(async () => stationsB.resolve(response([stationB])));
    await screen.findByText('facility-b-model 1.0.0');
    expect(predictionRequests.some((url) =>
      url.searchParams.get('facility_id') === facilityB.id
      && url.searchParams.get('station_id') === stationB.id
      && url.searchParams.get('connector_id') === stationB.connectors[0].id,
    )).toBe(true);

    await act(async () => stalePublication.resolve(response({
      detail: 'charging station does not belong to facility',
    }, 400)));
    await waitFor(() => expect(screen.queryByText('charging station does not belong to facility')).not.toBeInTheDocument());
    expect(screen.getByText('facility-b-model 1.0.0')).toBeInTheDocument();
  });

  it('ignores delayed Stations responses after changing Facility in Infrastructure', async () => {
    const facilityB = { ...facility, id: '00000000-0000-4000-8000-000000000021', name: 'South Campus' };
    const stationB = {
      ...station,
      id: '00000000-0000-4000-8000-000000000022',
      facility_id: facilityB.id,
      name: 'South Station',
    };
    const staleStations = deferred<Response>();

    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(typeof input === 'string' ? input : input.toString());
      if (url.pathname === '/facilities') return response([facility, facilityB]);
      if (url.pathname === `/facilities/${facility.id}/stations`) return staleStations.promise;
      if (url.pathname === `/facilities/${facilityB.id}/stations`) return response([stationB]);
      throw new Error(`Unhandled API request: ${url.pathname}`);
    }));

    render(<InfrastructurePage token="demo-token" />);
    await screen.findAllByText('Research Campus');
    fireEvent.change(screen.getByLabelText('Facility'), { target: { value: facilityB.id } });
    expect(screen.queryByText('North Station')).not.toBeInTheDocument();
    expect(await screen.findAllByText('South Station')).toHaveLength(2);

    await act(async () => staleStations.resolve(response([station])));
    await waitFor(() => expect(screen.queryByText('North Station')).not.toBeInTheDocument());
    expect(screen.getAllByText('South Station')).toHaveLength(2);
  });
});
