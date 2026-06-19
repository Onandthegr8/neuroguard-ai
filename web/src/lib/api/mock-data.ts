/**
 * Mock data for demo / offline mode.
 * Used as fallback when the backend API is unreachable.
 */

import type { Patient, RiskTier } from '@/types';

const now = new Date();
const daysAgo = (n: number) => new Date(now.getTime() - n * 86400_000).toISOString();

export const MOCK_PATIENTS: Patient[] = [
  { id: 'p-001', email: 'james.harrison@email.com',  age: 68, risk_group: 'high_risk', latest_risk_score: 0.82, latest_risk_tier: 'very_high', latest_prediction_at: daysAgo(1) },
  { id: 'p-002', email: 'margaret.liu@email.com',    age: 72, risk_group: 'high_risk', latest_risk_score: 0.71, latest_risk_tier: 'high',      latest_prediction_at: daysAgo(1) },
  { id: 'p-003', email: 'robert.okafor@email.com',   age: 64, risk_group: 'high_risk', latest_risk_score: 0.67, latest_risk_tier: 'high',      latest_prediction_at: daysAgo(2) },
  { id: 'p-004', email: 'elena.vasquez@email.com',   age: 59, risk_group: 'general',   latest_risk_score: 0.44, latest_risk_tier: 'moderate',  latest_prediction_at: daysAgo(1) },
  { id: 'p-005', email: 'thomas.bergman@email.com',  age: 55, risk_group: 'general',   latest_risk_score: 0.38, latest_risk_tier: 'moderate',  latest_prediction_at: daysAgo(3) },
  { id: 'p-006', email: 'anne.fitzpatrick@email.com',age: 61, risk_group: 'general',   latest_risk_score: 0.41, latest_risk_tier: 'moderate',  latest_prediction_at: daysAgo(1) },
  { id: 'p-007', email: 'david.nakamura@email.com',  age: 48, risk_group: 'general',   latest_risk_score: 0.22, latest_risk_tier: 'low',       latest_prediction_at: daysAgo(2) },
  { id: 'p-008', email: 'sarah.okonkwo@email.com',   age: 51, risk_group: 'general',   latest_risk_score: 0.18, latest_risk_tier: 'low',       latest_prediction_at: daysAgo(1) },
  { id: 'p-009', email: 'william.chen@email.com',    age: 45, risk_group: 'general',   latest_risk_score: 0.09, latest_risk_tier: 'very_low',  latest_prediction_at: daysAgo(4) },
  { id: 'p-010', email: 'priya.sharma@email.com',    age: 53, risk_group: 'general',   latest_risk_score: 0.12, latest_risk_tier: 'very_low',  latest_prediction_at: daysAgo(2) },
];

/** Build 90 days of risk history for a patient, ending at their latest score. */
export function mockRiskHistory(latestScore: number, days = 90) {
  const history = [];
  for (let i = days; i >= 0; i--) {
    const jitter = (Math.random() - 0.5) * 0.08;
    const progression = (days - i) / days; // slight upward trend for high-risk
    const base = latestScore > 0.5
      ? latestScore - (1 - progression) * 0.15
      : latestScore + (1 - progression) * 0.05;
    const score = Math.min(1, Math.max(0, base + jitter));
    const tier: RiskTier = score >= 0.75 ? 'very_high'
      : score >= 0.55 ? 'high'
      : score >= 0.30 ? 'moderate'
      : score >= 0.15 ? 'low'
      : 'very_low';
    history.push({
      date:       daysAgo(i).slice(0, 10),
      risk_score: parseFloat(score.toFixed(3)),
      risk_tier:  tier,
    });
  }
  return history;
}

export function mockPatientTimeline(patient: Patient) {
  const days = 90;
  const riskTrend = mockRiskHistory(patient.latest_risk_score ?? 0.3, days);

  const sleepTrend = riskTrend.map(r => ({
    date:                r.date,
    rem_fragmentation:   parseFloat((0.2 + (r.risk_score * 0.4) + (Math.random() - 0.5) * 0.1).toFixed(3)),
    efficiency:          parseFloat((0.85 - (r.risk_score * 0.2) + (Math.random() - 0.5) * 0.05).toFixed(3)),
  }));

  const keystrokeTrend = riskTrend.map(r => ({
    date:         r.date,
    entropy:      parseFloat((0.3 + r.risk_score * 0.5 + (Math.random() - 0.5) * 0.05).toFixed(3)),
    typing_speed: parseFloat((60 - r.risk_score * 25 + (Math.random() - 0.5) * 5).toFixed(1)),
  }));

  const isHighRisk = (patient.latest_risk_score ?? 0) > 0.55;
  const alerts = isHighRisk ? [
    {
      id:        'a-001',
      type:      'risk_threshold_crossed',
      severity:  'warning' as const,
      title:     'Risk threshold crossed',
      body:      'Patient risk score exceeded 0.55 (moderate → high)',
      created_at: daysAgo(7),
    },
    {
      id:        'a-002',
      type:      'rem_behavior_anomaly',
      severity:  'info' as const,
      title:     'REM fragmentation detected',
      body:      'REM fragmentation index > 0.5 on 3 consecutive nights',
      created_at: daysAgo(14),
    },
  ] : [];

  return { risk_trend: riskTrend, sleep_trend: sleepTrend, keystroke_trend: keystrokeTrend, alerts };
}
