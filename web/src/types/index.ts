export type RiskTier = 'very_low' | 'low' | 'moderate' | 'high' | 'very_high';

export interface Patient {
  id: string;
  email: string;
  age: number | null;
  risk_group: string;
  latest_risk_score: number | null;
  latest_risk_tier: RiskTier | null;
  latest_prediction_at: string | null;
}

export interface RiskHistoryPoint {
  date: string;
  risk_score: number;
  risk_tier: RiskTier;
}

export interface SleepTrendPoint {
  date: string;
  rem_fragmentation: number | null;
  efficiency: number | null;
}

export interface KeystrokeTrendPoint {
  date: string;
  entropy: number | null;
  typing_speed: number | null;
}

export interface AlertItem {
  id: string;
  type: string;
  severity: 'info' | 'warning' | 'critical';
  title: string;
  created_at: string;
}

export interface PatientTimeline {
  risk_trend: RiskHistoryPoint[];
  sleep_trend: SleepTrendPoint[];
  keystroke_trend: KeystrokeTrendPoint[];
  alerts: AlertItem[];
}

export interface SHAPContributor {
  feature: string;
  contribution_pct: number;
  direction: 'increases_risk' | 'decreases_risk';
}

export interface RiskScore {
  prediction_id: string;
  risk_score: number;
  risk_tier: RiskTier;
  confidence_interval: [number, number];
  model_version: string;
  shap_explanations: Record<string, number>;
  top_contributors: SHAPContributor[];
  keystroke_contribution: number;
  sleep_contribution: number;
  predicted_at: string;
}
