import { formatDateTime, formatDuration, formatMiles } from '../lib/format';
import { RISK_LEVELS, UNKNOWN_COLOR, riskColor, riskLabel } from '../lib/risk';
import type { PlanResponse, RouteOption } from '../types';

function RiskBar({ route }: { route: RouteOption }) {
  const total = route.distance_mi || 1;
  const parts = [
    ...RISK_LEVELS.map((l) => ({ key: l.key, label: l.label, color: l.color, miles: route.risk.miles_by_level[l.key] })),
    { key: 'unknown', label: 'No data', color: UNKNOWN_COLOR, miles: route.risk.unknown_miles },
  ].filter((p) => p.miles > 0);
  return (
    <div className="risk-bar" role="img" aria-label={parts.map((p) => `${p.label} ${Math.round(p.miles)} mi`).join(', ')}>
      {parts.map((p) => (
        <span key={p.key} style={{ width: `${(p.miles / total) * 100}%`, background: p.color }} title={`${p.label}: ${formatMiles(p.miles)}`} />
      ))}
    </div>
  );
}

interface Props {
  plan: PlanResponse;
  selectedId: string;
  onSelect: (id: string) => void;
}

export function RouteCards({ plan, selectedId, onSelect }: Props) {
  const sorted = [...plan.routes].sort((a, b) => a.rank - b.rank);
  return (
    <div className="route-cards">
      {sorted.map((route) => {
        const m = route.risk.miles_by_level;
        return (
          <button
            key={route.id}
            type="button"
            className={`route-card ${route.id === selectedId ? 'selected' : ''} ${route.recommended ? 'recommended' : ''}`}
            onClick={() => onSelect(route.id)}
          >
            <div className="card-head">
              <span className="route-name">
                <span className="rank">#{route.rank}</span> {route.name}
              </span>
              {route.recommended && <span className="badge">Recommended</span>}
              <span className="max-risk" style={{ background: riskColor(route.risk.max_level) }}>
                Max: {riskLabel(route.risk.max_level)}
              </span>
            </div>
            {route.via && <div className="via">via {route.via}</div>}
            <div className="stats">
              <span>
                <b>{formatMiles(route.distance_mi)}</b>
              </span>
              <span title="Driving time (truck-speed capped)">
                <b>{formatDuration(route.drive_duration_s)}</b> driving
              </span>
              {route.trip_duration_s !== route.drive_duration_s && (
                <span title="Including hours-of-service breaks">{formatDuration(route.trip_duration_s)} total</span>
              )}
            </div>
            <div className="arrival">Arrive {formatDateTime(route.arrival)}</div>
            <RiskBar route={route} />
            <div className="risk-stats">
              <span className={m.no_travel > 0 ? 'bad' : ''}>No Travel {Math.round(m.no_travel)} mi</span>
              <span className={m.severe > 0 ? 'bad' : ''}>Severe {Math.round(m.severe)} mi</span>
              <span>High {Math.round(m.high)} mi</span>
              <span>Avg risk {route.risk.avg_risk?.toFixed(2) ?? '—'}</span>
            </div>
          </button>
        );
      })}
    </div>
  );
}
