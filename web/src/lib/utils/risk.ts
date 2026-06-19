import type { RiskTier } from '@/types';

export const RISK_TIER_COLORS: Record<RiskTier, string> = {
  very_low: '#059669',
  low:      '#10B981',
  moderate: '#D97706',
  high:     '#EF4444',
  very_high: '#DC2626',
};

export const RISK_TIER_BG: Record<RiskTier, string> = {
  very_low:  'bg-emerald-50 text-emerald-700 border-emerald-200',
  low:       'bg-green-50 text-green-700 border-green-200',
  moderate:  'bg-amber-50 text-amber-700 border-amber-200',
  high:      'bg-red-50 text-red-700 border-red-200',
  very_high: 'bg-red-100 text-red-800 border-red-300',
};

export const RISK_TIER_LABEL: Record<RiskTier, string> = {
  very_low:  'Very Low',
  low:       'Low',
  moderate:  'Moderate',
  high:      'High',
  very_high: 'Very High',
};

export function scoreToTier(score: number): RiskTier {
  if (score < 0.15) return 'very_low';
  if (score < 0.30) return 'low';
  if (score < 0.55) return 'moderate';
  if (score < 0.75) return 'high';
  return 'very_high';
}

export function formatScore(score: number): string {
  return `${(score * 100).toFixed(1)}%`;
}
