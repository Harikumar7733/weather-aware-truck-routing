import { formatDateTime } from '../lib/format';
import { HEAT_SCALES, legendGradient } from '../lib/heatmapRaster';
import { RISK_LEVELS } from '../lib/risk';
import type { HeatField } from '../types';

const FIELDS: { field: HeatField; label: string }[] = [
  { field: 'risk', label: 'Risk' },
  { field: 'wind', label: 'Wind' },
  { field: 'rain', label: 'Rain' },
  { field: 'snow', label: 'Snow' },
];

interface Props {
  field: HeatField;
  onField: (f: HeatField) => void;
  hour: number;
  hours: number;
  onHour: (h: number) => void;
  start: Date;
  playing: boolean;
  onTogglePlay: () => void;
  status: 'loading' | 'ready' | 'error';
  error?: string | null;
  showHeat: boolean;
  onToggleHeat: () => void;
}

function Legend({ field }: { field: HeatField }) {
  if (field === 'risk') {
    return (
      <div className="legend discrete">
        {RISK_LEVELS.map((l) => (
          <span key={l.key}>
            <i style={{ background: l.color }} />
            {l.label}
          </span>
        ))}
      </div>
    );
  }
  const scale = HEAT_SCALES[field];
  return (
    <div className="legend">
      <div className="gradient" style={{ background: legendGradient(field) }} />
      <div className="ticks">
        <span>0</span>
        <span>
          {scale.max} {scale.unit}
        </span>
      </div>
    </div>
  );
}

export function HeatmapControls(p: Props) {
  const when = new Date(p.start.getTime() + p.hour * 3600_000);
  return (
    <div className="heat-controls">
      <div className="heat-row">
        <label className="checkbox inline">
          <input type="checkbox" checked={p.showHeat} onChange={p.onToggleHeat} /> Weather heatmap
        </label>
        <div className="segmented small" role="radiogroup" aria-label="Heatmap layer">
          {FIELDS.map(({ field, label }) => (
            <button key={field} type="button" role="radio" aria-checked={p.field === field} className={p.field === field ? 'on' : ''} onClick={() => p.onField(field)}>
              {label}
            </button>
          ))}
        </div>
        {p.status === 'loading' && <span className="muted small">Loading corridor forecast…</span>}
        {p.status === 'error' && <span className="error-text small">{p.error}</span>}
      </div>
      <div className="heat-row">
        <button type="button" className="play" onClick={p.onTogglePlay} aria-label={p.playing ? 'Pause' : 'Play'} disabled={p.status !== 'ready'}>
          {p.playing ? '❚❚' : '▶'}
        </button>
        <input
          type="range"
          min={0}
          max={p.hours}
          step={1}
          value={p.hour}
          onChange={(e) => p.onHour(Number(e.target.value))}
          aria-label="Forecast hour"
          className="slider"
        />
        <div className="time-label">
          <b>+{p.hour}h</b>
          <span>{formatDateTime(when)}</span>
        </div>
      </div>
      <Legend field={p.field} />
    </div>
  );
}
