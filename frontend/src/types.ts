/** Shapes returned by the Django API (see backend/planner/services). */

export type RiskLevel = 0 | 1 | 2 | 3 | 4;
export type LatLng = [number, number];
export type CheckpointInterval = 10 | 25 | 50;

export interface Place {
  label: string;
  lat: number;
  lon: number;
}

export interface WeatherSample {
  time: string;
  wind_mph: number;
  gust_mph: number | null;
  rain_in: number;
  snow_in: number;
  temp_f: number | null;
  code: number | null;
}

export interface CheckpointRisk {
  level: RiskLevel;
  label: string;
  wind: RiskLevel;
  rain: RiskLevel;
  snow: RiskLevel;
  factors: string[];
}

export interface Checkpoint {
  index: number;
  mile: number;
  lat: number;
  lon: number;
  eta: string;
  covers_miles: number;
  weather: WeatherSample | null;
  risk: CheckpointRisk | null;
}

export type LevelKey = 'low' | 'moderate' | 'high' | 'severe' | 'no_travel';

export interface RiskSummary {
  miles_by_level: Record<LevelKey, number>;
  unknown_miles: number;
  avg_risk: number | null;
  max_level: RiskLevel | null;
}

export interface RiskSegment {
  level: RiskLevel | null;
  coords: LatLng[];
}

export interface RouteOption {
  id: string;
  name: string;
  via: string;
  distance_mi: number;
  drive_duration_s: number;
  trip_duration_s: number;
  arrival: string;
  geometry: LatLng[];
  segments: RiskSegment[];
  checkpoints: Checkpoint[];
  risk: RiskSummary;
  rank: number;
  recommended: boolean;
}

export interface PlanResponse {
  origin: Place;
  destination: Place;
  departure: string;
  load_lbs: number;
  interval_mi: CheckpointInterval;
  hours_of_service: boolean;
  routes: RouteOption[];
  recommendation: { route_id: string; reason: string; warnings: string[] };
}

export interface PlanRequest {
  origin: Place | string;
  destination: Place | string;
  departure: string;
  load_lbs: number;
  interval_mi: CheckpointInterval;
  hours_of_service: boolean;
}

export type HeatField = 'risk' | 'wind' | 'rain' | 'snow';

export interface HeatmapGrid {
  lat0: number;
  lon0: number;
  dlat: number;
  dlon: number;
  rows: number;
  cols: number;
}

export interface HeatmapResponse {
  grid: HeatmapGrid;
  nodes: [number, number][];
  start: string;
  hours: number;
  /** fields[field][nodeIndex][hour] */
  fields: Record<HeatField, (number | null)[][]>;
}
