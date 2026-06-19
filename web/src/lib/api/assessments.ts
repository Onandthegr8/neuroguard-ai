/**
 * Helper to submit an assessment result to the backend.
 * Falls back gracefully when running as a demo user — logs to console instead.
 */

import { getSession } from 'next-auth/react';
import { apiClient } from './client';

export type AssessmentType =
  | 'voice_tremor'
  | 'finger_tap'
  | 'spiral_drawing'
  | 'reaction_time'
  | 'typing';

export interface AssessmentResult {
  assessment_type: AssessmentType;
  overall_score:   number;
  metrics:         Record<string, number | string>;
  notes?:          string;
}

export interface AssessmentResponse extends AssessmentResult {
  id:             string;
  interpretation: string;
  created_at:     string;
}

export async function submitAssessment(
  result: AssessmentResult,
): Promise<AssessmentResponse> {
  const session = await getSession();
  const token   = (session as any)?.accessToken;

  // Demo session — return a fake response so the results screen still renders.
  if (!token || token === 'demo-access-token') {
    return {
      id:             `demo-${Date.now()}`,
      ...result,
      interpretation: _localInterpret(result.assessment_type, result.overall_score),
      created_at:     new Date().toISOString(),
    };
  }

  const resp = await apiClient.post<AssessmentResponse>('/assessments', result);
  return resp.data;
}

function _localInterpret(type: AssessmentType, score: number): string {
  if (score >= 70) return `Within healthy range (${score.toFixed(1)}/100).`;
  if (score >= 50) return `Mildly impaired (${score.toFixed(1)}/100) — consider re-testing in 7 days.`;
  return `Below normal range (${score.toFixed(1)}/100) — clinical follow-up recommended.`;
}
