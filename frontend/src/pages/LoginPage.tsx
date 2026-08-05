import { useState, type FormEvent } from 'react';
import { useAuth } from '../auth/AuthContext';
import { readableError } from '../services/api';

export function LoginPage() {
  const { login, notice } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(email, password);
    } catch (reason) {
      setError(readableError(reason));
    } finally {
      setSubmitting(false);
    }
  }

  return <main className="login-shell">
    <section className="login-intro">
      <p className="eyebrow">Smart Charging Experimentation Platform</p>
      <h1>Operational insight for reproducible charging research.</h1>
      <p>SCEP connects infrastructure, simulated operations, Analytics and externally generated weekly occupancy predictions in one demonstrable platform.</p>
      <div className="research-note">Research platform · Thin API client · Backend-authoritative</div>
    </section>
    <form className="login-card" onSubmit={submit}>
      <div>
        <p className="eyebrow">SCEP dashboard</p>
        <h2>Sign in</h2>
        <p>Use an account configured in your local SCEP environment.</p>
      </div>
      <label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required autoComplete="username" /></label>
      <label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required autoComplete="current-password" /></label>
      {notice && <p className="state-message" role="status">{notice}</p>}
      {error && <p className="state-message state-error" role="alert">{error}</p>}
      <button className="primary-button" disabled={submitting}>{submitting ? 'Signing in…' : 'Sign in'}</button>
      <small>The password is sent only to the configured Backend API and is never stored. The access token remains in this browser tab.</small>
    </form>
  </main>;
}
