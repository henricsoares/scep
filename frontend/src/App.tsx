import { useState } from 'react';
import { useAuth } from './auth/AuthContext';
import { AnalyticsPage } from './pages/AnalyticsPage';
import { InfrastructurePage } from './pages/InfrastructurePage';
import { LoginPage } from './pages/LoginPage';
import { OverviewPage } from './pages/OverviewPage';
import { PredictionsPage } from './pages/PredictionsPage';

const NAVIGATION = [
  { id: 'overview', label: 'Overview', icon: '◫' },
  { id: 'infrastructure', label: 'Infrastructure', icon: '⌘' },
  { id: 'analytics', label: 'Analytics', icon: '⌁' },
  { id: 'predictions', label: 'Predictions', icon: '▦' },
] as const;

type Page = (typeof NAVIGATION)[number]['id'];

export function App() {
  const { session, checking, logout } = useAuth();
  const [page, setPage] = useState<Page>('overview');

  if (checking) return <main className="boot-screen" role="status">Restoring SCEP session…</main>;
  if (!session) return <LoginPage />;

  return <div className="app-shell">
    <aside className="sidebar">
      <button className="brand" onClick={() => setPage('overview')} aria-label="Open SCEP overview"><span>S</span><div><strong>SCEP</strong><small>Research platform</small></div></button>
      <nav aria-label="Main navigation">{NAVIGATION.map((item) => <button key={item.id} className={page === item.id ? 'active' : ''} onClick={() => setPage(item.id)}><i>{item.icon}</i>{item.label}</button>)}</nav>
      <div className="session-card"><span>{session.user.display_name.slice(0, 1).toUpperCase()}</span><div><strong>{session.user.display_name}</strong><small>{session.user.roles.join(', ') || session.user.technical_profile || session.user.account_type}</small></div><button onClick={logout} title="Sign out" aria-label="Sign out">↗</button></div>
    </aside>
    <main className="main-content">
      <div className="mobile-header"><button className="brand" onClick={() => setPage('overview')}><span>S</span><strong>SCEP</strong></button><button className="text-button" onClick={logout}>Sign out</button></div>
      <nav className="mobile-nav" aria-label="Mobile navigation">{NAVIGATION.map((item) => <button key={item.id} className={page === item.id ? 'active' : ''} onClick={() => setPage(item.id)}>{item.label}</button>)}</nav>
      {page === 'overview' && <OverviewPage token={session.token} navigate={(target) => setPage(target as Page)} />}
      {page === 'infrastructure' && <InfrastructurePage token={session.token} />}
      {page === 'analytics' && <AnalyticsPage token={session.token} />}
      {page === 'predictions' && <PredictionsPage token={session.token} />}
    </main>
  </div>;
}
