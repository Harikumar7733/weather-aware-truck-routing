import L from 'leaflet';
import { useEffect, useMemo, useRef } from 'react';
import { ImageOverlay, MapContainer, Marker, Pane, TileLayer, Tooltip, useMap } from 'react-leaflet';
import { formatDateTime } from '../lib/format';
import { cumulativeMiles, truckPosition } from '../lib/geo';
import type { Checkpoint, PlanResponse, RouteOption } from '../types';
import { RouteLayers } from './RouteLayers';

const ESRI = 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas';
const ESRI_ATTRIBUTION = 'Tiles &copy; Esri &mdash; Esri, HERE, Garmin, &copy; OpenStreetMap contributors';
const truckIcon =L.divIcon({ className: 'truck-wrap', html: '<div class="truck">🚚</div>', iconSize: [0, 0] });

function FitToPlan({ plan }: { plan: PlanResponse | null }) {
  const map = useMap();
  const fittedTrip = useRef<string | null>(null);
  // Fit only when a new trip is planned, not when e.g. the checkpoint interval changes.
  const trip = plan ? `${plan.origin.lat},${plan.origin.lon}>${plan.destination.lat},${plan.destination.lon}` : null;
  useEffect(() => {
    if (!plan || fittedTrip.current === trip) return;
    fittedTrip.current = trip;
    const bounds = L.latLngBounds(plan.routes.flatMap((r) => r.geometry));
    map.fitBounds(bounds, { paddingTopLeft: [40, 40], paddingBottomRight: [40, 150] });
  }, [map, plan, trip]);
  return null;
}

function FlyToCheckpoint({ focus }: { focus: Checkpoint | null }) {
  const map = useMap();
  useEffect(() => {
    if (focus) map.flyTo([focus.lat, focus.lon], Math.max(map.getZoom(), 9), { duration: 0.6 });
  }, [map, focus]);
  return null;
}

function Truck({ route, when }: { route: RouteOption; when: Date }) {
  const cum = useMemo(() => cumulativeMiles(route.geometry), [route]);
  const position = truckPosition(route, cum, when);
  return (
    <Marker position={position} icon={truckIcon} zIndexOffset={1000} interactive>
      <Tooltip direction="top" offset={[0, -14]}>
        {route.name} truck at {formatDateTime(when)}
      </Tooltip>
    </Marker>
  );
}

interface Props {
  plan: PlanResponse | null;
  selectedId: string;
  onSelect: (id: string) => void;
  heatUrl: string | null;
  heatBounds: L.LatLngBoundsExpression | null;
  truckTime: Date | null;
  focus: Checkpoint | null;
}

export function MapView({ plan, selectedId, onSelect, heatUrl, heatBounds, truckTime, focus }: Props) {
  const selected = plan?.routes.find((r) => r.id === selectedId);
  return (
    <MapContainer center={[39.5, -98.35]} zoom={4} maxZoom={16} preferCanvas className="map" worldCopyJump>
      <TileLayer url={`${ESRI}/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}`} attribution={ESRI_ATTRIBUTION} maxZoom={16} />
      <Pane name="heatmap" style={{ zIndex: 350 }}>
        {heatUrl && heatBounds && <ImageOverlay url={heatUrl} bounds={heatBounds} opacity={0.9} className="heat-overlay" />}
      </Pane>
      {/* Place labels sit above the heatmap but below routes. */}
      <Pane name="labels" style={{ zIndex: 375, pointerEvents: 'none' }}>
        <TileLayer url={`${ESRI}/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}`} maxZoom={16} />
      </Pane>
      {plan && <RouteLayers plan={plan} selectedId={selectedId} onSelect={onSelect} />}
      {selected && truckTime && <Truck route={selected} when={truckTime} />}
      <FitToPlan plan={plan} />
      <FlyToCheckpoint focus={focus} />
    </MapContainer>
  );
}
