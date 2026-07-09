export type HealthResponse = { status: string; service: string; version: string; environment: string };

export async function fetchHealth(): Promise<HealthResponse> {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
  const response = await fetch(`${apiBaseUrl}/health`);
  if (!response.ok) throw new Error(`Backend health request failed: ${response.status}`);
  return response.json();
}
