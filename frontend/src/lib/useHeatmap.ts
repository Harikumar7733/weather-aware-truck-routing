import { useEffect, useRef, useState } from 'react';
import { fetchHeatmap } from '../api';
import type { HeatField, PlanResponse } from '../types';
import { downsample } from './geo';
import { HeatmapRaster } from './heatmapRaster';

const MAX_POINTS_PER_ROUTE = 400;

interface Loaded {
  key: string;
  raster: HeatmapRaster | null;
  error: string | null;
}

export interface HeatmapState {
  raster: HeatmapRaster | null;
  status: 'loading' | 'ready' | 'error';
  error: string | null;
}

/** Everything the corridor heatmap depends on. The checkpoint interval is deliberately excluded. */
function heatmapKey(plan: PlanResponse | null): string {
  if (!plan) return '';
  return [plan.departure, plan.load_lbs, ...plan.routes.map((r) => `${r.id}:${r.distance_mi}`)].join('|');
}

/**
 * Loads the corridor heatmap for a plan, re-fetching only when the corridor, departure
 * or load change, and pre-renders frames for the active field in the background.
 */
export function useHeatmap(plan: PlanResponse | null, field: HeatField): HeatmapState {
  const [loaded, setLoaded] = useState<Loaded>({ key: '', raster: null, error: null });
  const inflight = useRef<{ key: string; controller: AbortController } | null>(null);
  const key = heatmapKey(plan);

  useEffect(() => {
    if (!plan || inflight.current?.key === key) return;
    inflight.current?.controller.abort();
    const controller = new AbortController();
    inflight.current = { key, controller };
    fetchHeatmap(
      plan.routes.map((r) => downsample(r.geometry, MAX_POINTS_PER_ROUTE)),
      plan.departure,
      plan.load_lbs,
      controller.signal,
    )
      .then((data) => setLoaded({ key, raster: new HeatmapRaster(data), error: null }))
      .catch((err: Error) => {
        if (err.name !== 'AbortError') setLoaded({ key, raster: null, error: err.message });
      });
  }, [plan, key]);

  useEffect(
    () => () => {
      inflight.current?.controller.abort();
      inflight.current = null;
    },
    [],
  );

  const current = loaded.key === key ? loaded : null;
  const raster = current?.raster ?? null;

  useEffect(() => {
    if (!raster) return;
    let cancelled = false;
    raster.prerender(field, () => cancelled);
    return () => {
      cancelled = true;
    };
  }, [raster, field]);

  return {
    raster,
    status: current ? (current.error ? 'error' : 'ready') : 'loading',
    error: current?.error ?? null,
  };
}
