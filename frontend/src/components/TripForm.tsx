import { useState } from 'react';
import { nextHourLocalInput } from '../lib/format';
import type { CheckpointInterval, Place, PlanRequest } from '../types';
import { PlaceInput } from './PlaceInput';

const INTERVALS: CheckpointInterval[] = [10, 25, 50];

interface Props {
  loading: boolean;
  hasPlan: boolean;
  onSubmit: (req: PlanRequest) => void;
}

export function TripForm({ loading, hasPlan, onSubmit }: Props) {
  const [origin, setOrigin] = useState<Place | string>({ label: 'Chicago, Illinois, United States', lat: 41.8755616, lon: -87.6244212 });
  const [destination, setDestination] = useState<Place | string>({ label: 'Denver, Colorado, United States', lat: 39.7392364, lon: -104.984862 });
  const [departure, setDeparture] = useState(nextHourLocalInput);
  const [load, setLoad] = useState('42000');
  const [interval, setIntervalMi] = useState<CheckpointInterval>(25);
  const [hos, setHos] = useState(true);

  const build = (overrides: Partial<PlanRequest> = {}): PlanRequest => ({
    origin,
    destination,
    departure: new Date(departure).toISOString(),
    load_lbs: Number(load),
    interval_mi: interval,
    hours_of_service: hos,
    ...overrides,
  });

  return (
    <form
      className="trip-form"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(build());
      }}
    >
      <PlaceInput label="Origin" value={origin} onChange={setOrigin} placeholder="City, address or lat,lon" />
      <button
        type="button"
        className="swap"
        title="Swap origin and destination"
        aria-label="Swap origin and destination"
        onClick={() => {
          setOrigin(destination);
          setDestination(origin);
        }}
      >
        ⇅
      </button>
      <PlaceInput label="Destination" value={destination} onChange={setDestination} placeholder="City, address or lat,lon" />

      <div className="field-row">
        <div className="field">
          <label htmlFor="departure">Departure</label>
          <input id="departure" type="datetime-local" value={departure} onChange={(e) => setDeparture(e.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="load">Load weight (lb)</label>
          <input
            id="load"
            type="number"
            min={0}
            max={150000}
            step={500}
            value={load}
            onChange={(e) => setLoad(e.target.value)}
            required
          />
        </div>
      </div>

      <div className="field">
        <span className="label">Weather checkpoint every</span>
        <div className="segmented" role="radiogroup" aria-label="Checkpoint interval">
          {INTERVALS.map((mi) => (
            <button
              key={mi}
              type="button"
              role="radio"
              aria-checked={interval === mi}
              className={interval === mi ? 'on' : ''}
              onClick={() => {
                setIntervalMi(mi);
                if (hasPlan && !loading) onSubmit(build({ interval_mi: mi }));
              }}
            >
              {mi} mi
            </button>
          ))}
        </div>
      </div>

      <label className="checkbox">
        <input type="checkbox" checked={hos} onChange={(e) => setHos(e.target.checked)} />
        Include hours-of-service breaks in ETAs
        <span className="hint">30 min after 8 h driving, 10 h rest after 11 h</span>
      </label>

      <button className="primary" type="submit" disabled={loading}>
        {loading ? 'Planning routes…' : 'Plan routes'}
      </button>
    </form>
  );
}
