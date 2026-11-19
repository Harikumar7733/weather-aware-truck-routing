import { formatTime } from '../lib/format';
import { riskColor, riskLabel } from '../lib/risk';
import type { Checkpoint, RouteOption } from '../types';

interface Props {
  route: RouteOption;
  onFocus: (cp: Checkpoint) => void;
}

export function CheckpointTable({ route, onFocus }: Props) {
  return (
    <div className="checkpoints">
      <h3>
        {route.name} checkpoints <span className="muted">({route.checkpoints.length})</span>
      </h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Mile</th>
              <th>ETA</th>
              <th title="Sustained wind (gust)">Wind</th>
              <th title="Rain, in/hr">Rain</th>
              <th title="Snow, in/hr">Snow</th>
              <th>Risk</th>
            </tr>
          </thead>
          <tbody>
            {route.checkpoints.map((cp) => {
              const w = cp.weather;
              return (
                <tr key={cp.index} onClick={() => onFocus(cp)} title={cp.risk?.factors.join(' · ') || undefined}>
                  <td>{Math.round(cp.mile)}</td>
                  <td>{formatTime(cp.eta)}</td>
                  <td>
                    {w ? Math.round(w.wind_mph) : '—'}
                    {w?.gust_mph != null && <span className="muted"> ({Math.round(w.gust_mph)})</span>}
                  </td>
                  <td>{w ? w.rain_in.toFixed(2) : '—'}</td>
                  <td>{w ? w.snow_in.toFixed(2) : '—'}</td>
                  <td>
                    <span className="pill" style={{ background: riskColor(cp.risk?.level) }}>
                      {riskLabel(cp.risk?.level)}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
