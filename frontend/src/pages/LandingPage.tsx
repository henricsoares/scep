import { useEffect, useState } from 'react';
import { fetchHealth, type HealthResponse } from '../services/health';

export function LandingPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchHealth().then(setHealth).catch((err: Error) => setError(err.message));
  }, []);

  return <main className="shell">
    <p className="eyebrow">Smart Charging Experimentation Platform</p>
    <h1>SCEP project foundation</h1>
    <p>Research-ready platform foundation for smart EV charging experiments.</p>
    <section className="card">
      <h2>Backend health</h2>
      {health && <p>Status: <strong>{health.status}</strong> ({health.service} {health.version}, {health.environment})</p>}
      {error && <p role="alert">Unable to reach backend: {error}</p>}
      {!health && !error && <p>Checking backend health…</p>}
    </section>
  </main>;
}
