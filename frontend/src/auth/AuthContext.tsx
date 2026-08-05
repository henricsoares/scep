import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  fetchCurrentUser,
  login as authenticate,
  type CurrentUser,
} from '../services/auth';
import { UNAUTHORIZED_EVENT } from '../services/api';

const TOKEN_KEY = 'scep.accessToken';

type Session = {
  token: string;
  user: CurrentUser;
};

type AuthContextValue = {
  session: Session | null;
  checking: boolean;
  notice: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [checking, setChecking] = useState(() => Boolean(sessionStorage.getItem(TOKEN_KEY)));
  const [notice, setNotice] = useState<string | null>(null);

  const logout = useCallback(() => {
    sessionStorage.removeItem(TOKEN_KEY);
    setSession(null);
    setChecking(false);
    setNotice(null);
  }, []);

  const expireSession = useCallback(() => {
    sessionStorage.removeItem(TOKEN_KEY);
    setSession(null);
    setChecking(false);
    setNotice('Your session expired. Sign in again to continue.');
  }, []);

  useEffect(() => {
    const token = sessionStorage.getItem(TOKEN_KEY);
    if (!token) return;
    fetchCurrentUser(token)
      .then((user) => setSession({ token, user }))
      .catch(() => expireSession())
      .finally(() => setChecking(false));
  }, [expireSession]);

  useEffect(() => {
    window.addEventListener(UNAUTHORIZED_EVENT, expireSession);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, expireSession);
  }, [expireSession]);

  async function login(email: string, password: string) {
    const response = await authenticate(email, password);
    const user = await fetchCurrentUser(response.access_token);
    sessionStorage.setItem(TOKEN_KEY, response.access_token);
    setSession({ token: response.access_token, user });
    setNotice(null);
  }

  const value = useMemo(
    () => ({ session, checking, notice, login, logout }),
    [session, checking, notice, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth must be used within AuthProvider');
  return value;
}
