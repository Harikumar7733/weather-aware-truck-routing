import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { planTrip } from './api';
import { CheckpointTable } from './components/CheckpointTable';
import { HeatmapControls } from './components/HeatmapControls';
import { MapView } from './components/MapView';
import { RouteCards } from './components/RouteCards';
import { TripForm } from './components/TripForm';
import { RISK_LEVELS } from './lib/risk';
import { useHeatmap } from './lib/useHeatmap';
import type { Checkpoint, HeatField, PlanRequest, PlanResponse } from './types';

const HOUR_MS = 3600_000;
const PLAY_STEP_MS = 350;

export default function App() {
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState('');
  const [focus, setFocus] = useState<Checkpoint | null>(null);
  const planAbort = useRef<AbortController | null>(null);
  const lastDeparture = useRef<string | null>(null);

  const [field, setField] = useState<HeatField>('risk');
  const [hour, setHour] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [showHeat, setShowHeat] = useState(true);
  const heat = useHeatmap(plan, field);

  const submit = useCallback(async (req: PlanRequest) => {
    planAbort.current?.abort();
    const controller = new AbortController();
    planAbort.current = controller;
    setLoading(true);
    setError(null);
    try {
      const result = await planTrip(req, controller.signal);
      // Keep the slider position when only the checkpoint interval changed.
      if (lastDeparture.current !== result.departure) setHour(0);
      lastDeparture.current = result.departure;
      setPlan(result);
      setSelectedId((prev) => (result.routes.some((r) => r.id === prev) && prev ? prev : result.recommendation.route_id));
      setFocus(null);
      if (window.matchMedia('(max-width: 900px)').matches) window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (err) {
      if ((err as Error).name !== 'AbortError') setError((err as Error).message);
    } finally {
      if (planAbort.current === controller) setLoading(false);
    }
  }, []);

  const hours = heat.raster?.hours ?? 48;
  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => setHour((h) => (h >= hours ? 0 : h + 1)), PLAY_STEP_MS);
    return () => clearInterval(timer);
  }, [playing, hours]);

  const heatUrl = useMemo(() => (showHeat && heat.raster ? heat.raster.frame(field, hour) : null), [showHeat, heat.raster, field, hour]);
  const heatStart = useMemo(() => (plan ? new Date(Math.floor(Date.parse(plan.departure) / HOUR_MS) * HOUR_MS) : null), [plan]);
  const truckTime = heatStart ? new Date(heatStart.getTime() + hour * HOUR_MS) : null;
  const selected = plan?.routes.find((r) => r.id === selectedId);

  return (
    <div className="app">
      <aside className="sidebar">
        <header className="brand">
          <h1>Weather-Aware Truck Routing</h1>
          <p>Compare three routes by forecast weather at the truck's ETA, load-adjusted risk and travel time.</p>
        </header>

        <TripForm loading={loading} hasPlan={!!plan} onSubmit={submit} />

        {error && <div className="alert error">{error}</div>}

        {plan && (
          <section className="results">
            <div className="recommendation">
              <div className="rec-title">
                Recommended: <b>{plan.routes.find((r) => r.id === plan.recommendation.route_id)?.name}</b>
              </div>
              <p>{plan.recommendation.reason}</p>
              {plan.recommendation.warnings.map((w) => (
                <div key={w} className="alert warn">
                  {w}
                </div>
              ))}
            </div>
            <RouteCards plan={plan} selectedId={selectedId} onSelect={setSelectedId} />
            {selected && <CheckpointTable route={selected} onFocus={setFocus} />}
          </section>
        )}

        <footer className="credits">
          Routing: OSRM · Weather: Open-Meteo · Geocoding: Photon/OSM. Ranking: fewest No Travel → Severe → High miles → lowest average risk →
          shortest time.
        </footer>
      </aside>

      <main className="map-area">
        <MapView
          plan={plan}
          selectedId={selectedId}
          onSelect={setSelectedId}
          heatUrl={heatUrl}
          heatBounds={heat.raster?.bounds ?? null}
          truckTime={plan ? truckTime : null}
          focus={focus}
        />
        <div className="map-legend" aria-label="Route risk legend">
          {RISK_LEVELS.map((l) => (
            <span key={l.key}>
              <i style={{ background: l.color }} />
              {l.label}
            </span>
          ))}
        </div>
        {plan && heatStart && (
          <HeatmapControls
            field={field}
            onField={setField}
            hour={hour}
            hours={hours}
            onHour={(h) => {
              setPlaying(false);
              setHour(h);
            }}
            start={heatStart}
            playing={playing}
            onTogglePlay={() => setPlaying((p) => !p)}
            status={heat.status}
            error={heat.error}
            showHeat={showHeat}
            onToggleHeat={() => setShowHeat((s) => !s)}
          />
        )}
        {loading && (
          <div className="map-loading">
            <span className="spinner" /> Fetching routes and forecasts along each route…
          </div>
        )}
        {!plan && !loading && <div className="map-empty">Enter a trip and press “Plan routes”.</div>}
      </main>
    </div>
  );
}
