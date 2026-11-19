import type { LevelKey, RiskLevel } from '../types';

export const RISK_LEVELS: { level: RiskLevel; key: LevelKey; label: string; color: string }[] = [
  { level: 0, key: 'low', label: 'Low', color: '#22c55e' },
  { level: 1, key: 'moderate', label: 'Moderate', color: '#eab308' },
  { level: 2, key: 'high', label: 'High', color: '#f97316' },
  { level: 3, key: 'severe', label: 'Severe', color: '#dc2626' },
  { level: 4, key: 'no_travel', label: 'No Travel', color: '#7e22ce' },
];

export const UNKNOWN_COLOR = '#94a3b8';

export function riskColor(level: RiskLevel | null | undefined): string {
  return level == null ? UNKNOWN_COLOR : RISK_LEVELS[level].color;
}

export function riskLabel(level: RiskLevel | null | undefined): string {
  return level == null ? 'No data' : RISK_LEVELS[level].label;
}
