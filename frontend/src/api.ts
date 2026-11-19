import type { HeatmapResponse, LatLng, Place, PlanRequest, PlanResponse } from './types';

const API_BASE: string = import.meta.env.VITE_API_BASE ?? '';

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init.headers },
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error(body?.error ?? `Request failed (${res.status})`);
  }
  return body as T;
}

export function geocode(query: string, signal?: AbortSignal): Promise<Place[]> {
  return request<Place[]>(`/api/geocode?q=${encodeURIComponent(query)}`, { signal });
}

export function planTrip(req: PlanRequest, signal?: AbortSignal): Promise<PlanResponse> {
  return request<PlanResponse>('/api/plan', { method: 'POST', body: JSON.stringify(req), signal });
}

export function fetchHeatmap(
  routes: LatLng[][],
  departure: string,
  loadLbs: number,
  signal?: AbortSignal,
): Promise<HeatmapResponse> {
  return request<HeatmapResponse>('/api/heatmap', {
    method: 'POST',
    body: JSON.stringify({ routes, departure, load_lbs: loadLbs }),
    signal,
  });
}
