# SCEP Web Dashboard

The frontend is a small React and TypeScript demonstration client for the public SCEP Backend API.
It provides four authenticated, read-oriented views:

- Overview: Backend health, infrastructure summary and selected Analytics KPIs;
- Infrastructure: visible Facilities, Charging Stations and Connectors;
- Analytics: SPEC-010 KPIs and a daily occupancy series;
- Predictions: current SPEC-012 profile, 7 × 24 heatmap and recurring point lookup.

The browser does not reproduce Backend authorization or domain calculations. Analytics metrics and
prediction values are rendered from API responses. The access token is kept in `sessionStorage` and
is removed on sign-out or an authenticated `401` response. Passwords are never persisted.

## Run locally

From the repository root, start the complete environment:

```bash
cp .env.example .env
make up
```

Open `http://localhost:5173` and sign in with an account configured in the local Backend. No
credentials or infrastructure identifiers are bundled into the frontend.

For standalone frontend development:

```bash
cd frontend
npm ci
npm run dev
```

`VITE_API_BASE_URL` configures the public Backend origin and defaults to
`http://localhost:8000`. Because Vite variables are compiled into the static bundle, Docker Compose
passes this value as a frontend image build argument.

## Validate

```bash
npm test
npm run typecheck
npm run build
npm audit --audit-level=high
```

Tests use mocked API responses and do not require a live Backend.
