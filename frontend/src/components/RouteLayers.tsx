import L from 'leaflet';
import { memo, useMemo } from 'react';
import { CircleMarker, Marker, Polyline, Popup, Tooltip } from 'react-leaflet';
import { formatDateTime, formatDuration, formatMiles, formatTime } from '../lib/format';
import { cumulativeMiles, haversineMi, pointAtFraction } from '../lib/geo';
import { riskColor, riskLabel } from '../lib/risk';
import type { Checkpoint, LatLng, PlanResponse, RouteOption } from '../types';

const OTHER_ROUTE_COLOR = '#475569';
const LABEL_SAMPLES = 80;

/**
 * Place each route's summary label on the part of that route (middle 20–80%) that is
 * farthest from every other route, so labels sit on distinct stretches and don't collide.
 */
function labelAnchors(routes: RouteOption[]): Record<string, LatLng> {
  const samples = routes.map((r) => {
    const cum = cumulativeMiles(r.geometry);
    return Array.from({ length: LABEL_SAMPLES + 1 }, (_, i) => pointAtFraction(r.geometry, cum, i / LABEL_SAMPLES));
  });
  const anchors: Record<string, LatLng> = {};
  routes.forEach((route, idx) => {
    let best = samples[idx][LABEL_SAMPLES / 2];
    let bestScore = 0;
    for (let i = LABEL_SAMPLES * 0.2; i <= LABEL_SAMPLES * 0.8; i++) {
      const p = samples[idx][i];
      let nearest = Infinity;
      samples.forEach((other, j) => {
        if (j !== idx) for (const q of other) nearest = Math.min(nearest, haversineMi(p, q));
      });
      if (nearest !== Infinity && nearest > bestScore) {
        bestScore = nearest;
        best = p;
      }
    }
    anchors[route.id] = best;
  });
  return anchors;
}

function CheckpointPopup({ route, cp }: { route: RouteOption; cp: Checkpoint }) {
  const w = cp.weather;
  return (
    <div className="cp-popup">
      <div className="cp-title">
        {route.name} · mile {Math.round(cp.mile)}
        <span className="pill" style={{ background: riskColor(cp.risk?.level) }}>
          {riskLabel(cp.risk?.level)}
        </span>
      </div>
      <div>ETA {formatDateTime(cp.eta)}</div>
      {w ? (
        <table>
          <tbody>
            <tr>
              <td>Wind</td>
              <td>
                {w.wind_mph.toFixed(0)} mph{w.gust_mph != null && ` (gusts ${w.gust_mph.toFixed(0)})`}
              </td>
              <td>{riskLabel(cp.risk?.wind)}</td>
            </tr>
            <tr>
              <td>Rain</td>
              <td>{w.rain_in.toFixed(2)} in/hr</td>
              <td>{riskLabel(cp.risk?.rain)}</td>
            </tr>
            <tr>
              <td>Snow</td>
              <td>{w.snow_in.toFixed(2)} in/hr</td>
              <td>{riskLabel(cp.risk?.snow)}</td>
            </tr>
            {w.temp_f != null && (
              <tr>
                <td>Temp</td>
                <td colSpan={2}>{w.temp_f.toFixed(0)} °F</td>
              </tr>
            )}
          </tbody>
        </table>
      ) : (
        <div className="muted">No forecast available for this ETA.</div>
      )}
      {cp.risk && cp.risk.factors.length > 0 && <div className="factors">Driven by: {cp.risk.factors.join(', ')}</div>}
      {w && <div className="muted small">Forecast hour {formatTime(w.time)}</div>}
    </div>
  );
}

function routeLabelIcon(route: RouteOption, selected: boolean): L.DivIcon {
  const m = route.risk.miles_by_level;
  const worst = m.no_travel > 0 ? `${Math.round(m.no_travel)} mi No Travel` : m.severe > 0 ? `${Math.round(m.severe)} mi Severe` : m.high > 0 ? `${Math.round(m.high)} mi High` : 'no High+ risk';
  const html = `<div class="route-label ${selected ? 'selected' : ''} ${route.recommended ? 'recommended' : ''}">
      <b>${route.name}</b>${route.recommended ? ' ★' : ''}<br/>
      ${formatMiles(route.distance_mi)} · ${formatDuration(route.trip_duration_s)}<br/>
      <span style="color:${riskColor(route.risk.max_level)}">●</span> ${worst}
    </div>`;
  return L.divIcon({ className: 'route-label-wrap', html, iconSize: [0, 0] });
}

const endpointIcon = (kind: 'start' | 'end') =>
  L.divIcon({ className: 'endpoint-wrap', html: `<div class="endpoint ${kind}"></div>`, iconSize: [0, 0] });

interface Props {
  plan: PlanResponse;
  selectedId: string;
  onSelect: (id: string) => void;
}

/** Routes, risk-coloured segments, checkpoints and labels. Memoised: unaffected by the time slider. */
export const RouteLayers = memo(function RouteLayers({ plan, selectedId, onSelect }: Props) {
  const selected = plan.routes.find((r) => r.id === selectedId);
  const others = plan.routes.filter((r) => r.id !== selectedId);
  const labelPositions = useMemo(() => labelAnchors(plan.routes), [plan]);

  return (
    <>
      {others.map((r) => (
        <Polyline
          key={`route-${r.id}-${selectedId}`}
          positions={r.geometry}
          pathOptions={{ color: OTHER_ROUTE_COLOR, weight: 5, opacity: 0.5 }}
          eventHandlers={{ click: () => onSelect(r.id) }}
        >
          <Tooltip sticky>Click to select {r.name}</Tooltip>
        </Polyline>
      ))}
      {others.flatMap((r) =>
        r.checkpoints.map((cp) => (
          <CircleMarker
            key={`cp-${r.id}-${cp.index}-${selectedId}`}
            center={[cp.lat, cp.lon]}
            radius={3.5}
            pathOptions={{ color: '#fff', weight: 1, fillColor: riskColor(cp.risk?.level), fillOpacity: 0.75 }}
          >
            <Popup>
              <CheckpointPopup route={r} cp={cp} />
            </Popup>
          </CircleMarker>
        )),
      )}

      {selected && (
        <>
          <Polyline key={`casing-${selected.id}`} positions={selected.geometry} pathOptions={{ color: '#0f172a', weight: 10, opacity: 0.8 }} />
          {selected.segments.map((s, i) => (
            <Polyline
              key={`seg-${selected.id}-${i}-${plan.interval_mi}`}
              positions={s.coords}
              pathOptions={{ color: riskColor(s.level), weight: 6, opacity: 1, lineCap: 'butt' }}
            />
          ))}
          {selected.checkpoints.map((cp) => (
            <CircleMarker
              key={`cp-sel-${selected.id}-${cp.index}-${plan.interval_mi}`}
              center={[cp.lat, cp.lon]}
              radius={6}
              pathOptions={{ color: '#0f172a', weight: 2, fillColor: riskColor(cp.risk?.level), fillOpacity: 1 }}
            >
              <Tooltip direction="top" offset={[0, -6]}>
                Mile {Math.round(cp.mile)} · {formatTime(cp.eta)} · {riskLabel(cp.risk?.level)}
              </Tooltip>
              <Popup>
                <CheckpointPopup route={selected} cp={cp} />
              </Popup>
            </CircleMarker>
          ))}
        </>
      )}

      {plan.routes.map((r) => (
        <Marker
          key={`label-${r.id}-${selectedId}`}
          position={labelPositions[r.id]}
          icon={routeLabelIcon(r, r.id === selectedId)}
          zIndexOffset={r.id === selectedId ? 500 : 0}
          eventHandlers={{ click: () => onSelect(r.id) }}
        />
      ))}

      <Marker position={[plan.origin.lat, plan.origin.lon]} icon={endpointIcon('start')}>
        <Tooltip direction="top">Origin: {plan.origin.label}</Tooltip>
      </Marker>
      <Marker position={[plan.destination.lat, plan.destination.lon]} icon={endpointIcon('end')}>
        <Tooltip direction="top">Destination: {plan.destination.label}</Tooltip>
      </Marker>
    </>
  );
});
