import axios from 'axios';
import { getSession } from 'next-auth/react';
import { MOCK_PATIENTS, mockPatientTimeline } from './mock-data';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1';

/**
 * Per-request demo-mode check.
 *
 * If the current session was issued to a hardcoded demo user
 * (accessToken === 'demo-access-token'), return mock data.
 * Otherwise, the user has a real JWT — hit the backend.
 *
 * This lets demo@neuroguard.ai / admin@neuroguard.ai keep working
 * as a marketing/UX demo while a user registered against the real
 * FastAPI services gets real data flowing.
 */
async function isDemoSession(): Promise<boolean> {
  // SSR / no session yet
  if (typeof window === 'undefined') return true;

  const session = await getSession();
  if (!session) return true;     // logged out — fall back to mock so empty-state still renders
  return (session as any).accessToken === 'demo-access-token';
}

export const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 8_000,
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT from NextAuth session on every request (skipped for demo token)
apiClient.interceptors.request.use(async (config) => {
  const session = await getSession();
  const token   = (session as any)?.accessToken;
  if (token && token !== 'demo-access-token') {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401) {
      if (typeof window !== 'undefined') window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// ── Mock response helper ───────────────────────────────────────────────────
function mockResponse<T>(data: T) {
  return Promise.resolve({ data, status: 200, statusText: 'OK', headers: {}, config: {} as any });
}

// ── Typed API helpers ──────────────────────────────────────────────────────
export const api = {
  patients: {
    list: async (params?: { search?: string; risk_tier?: string; page?: number; limit?: number }) => {
      if (await isDemoSession()) {
        let pts = [...MOCK_PATIENTS];
        if (params?.search) {
          const q = params.search.toLowerCase();
          pts = pts.filter(p => p.email.toLowerCase().includes(q));
        }
        if (params?.risk_tier) {
          pts = pts.filter(p => p.latest_risk_tier === params.risk_tier);
        }
        const page  = params?.page  ?? 1;
        const limit = params?.limit ?? 20;
        const start = (page - 1) * limit;
        return mockResponse({ patients: pts.slice(start, start + limit), total: pts.length, page, limit });
      }
      return apiClient.get('/clinician/patients', { params });
    },

    timeline: async (id: string, days = 90) => {
      if (await isDemoSession()) {
        const patient = MOCK_PATIENTS.find(p => p.id === id) ?? MOCK_PATIENTS[0];
        return mockResponse(mockPatientTimeline(patient));
      }
      return apiClient.get(`/patients/${id}/timeline`, { params: { days } });
    },

    get: async (id: string) => {
      if (await isDemoSession()) {
        const patient = MOCK_PATIENTS.find(p => p.id === id) ?? MOCK_PATIENTS[0];
        return mockResponse(patient);
      }
      return apiClient.get(`/patients/${id}`);
    },
  },

  risk: {
    score: async (patientId?: string) => {
      if (await isDemoSession()) {
        const p = patientId ? MOCK_PATIENTS.find(pt => pt.id === patientId) : MOCK_PATIENTS[0];
        const score = p?.latest_risk_score ?? 0.28;
        return mockResponse({
          risk_score:    score,
          risk_tier:     p?.latest_risk_tier ?? 'low',
          confidence_interval: [+(score - 0.07).toFixed(2), +(score + 0.07).toFixed(2)],
          model_version: 'v1.4.2-demo',
          shap_explanations: {
            rem_fragmentation:    0.038,
            typing_entropy_delta: 0.027,
            hrv_trend:           -0.015,
          },
          top_contributors: [
            { feature: 'REM fragmentation',    contribution_pct: 38, direction: 'increases_risk' },
            { feature: 'Typing entropy delta', contribution_pct: 27, direction: 'increases_risk' },
            { feature: 'HRV trend',            contribution_pct: 15, direction: 'decreases_risk' },
          ],
          predicted_at: new Date().toISOString(),
        });
      }
      return apiClient.get('/risk/score', patientId ? { params: { patient_id: patientId } } : undefined);
    },

    history: async (days = 90) => {
      if (await isDemoSession()) {
        const { risk_trend } = mockPatientTimeline(MOCK_PATIENTS[0]);
        return mockResponse({ history: risk_trend });
      }
      return apiClient.get('/risk/history', { params: { days } });
    },

    compute: async (patientId?: string) => {
      if (await isDemoSession()) {
        return mockResponse({ status: 'queued', patient_id: patientId ?? 'demo' });
      }
      return apiClient.post('/risk/compute', null, patientId ? { params: { patient_id: patientId } } : undefined);
    },

    narrative: async () => {
      if (await isDemoSession()) {
        return mockResponse({
          headline:   'Risk score: 28% (low).',
          drivers:    [
            'typing rhythm variability (↑12% vs. your 30-day baseline)',
            'REM-sleep fragmentation (↑18% vs. your 30-day baseline)',
          ],
          protective: [
            'heart-rate variability (RMSSD) — holding within healthy range',
            'sleep efficiency — holding within healthy range',
          ],
          callouts:   ['This score is driven primarily by typing-pattern changes.'],
          paragraph:  'Your risk score is 28% (low risk band). The main factors raising it are typing rhythm variability (↑12% vs. your 30-day baseline) and REM-sleep fragmentation (↑18% vs. your 30-day baseline). On the positive side, heart-rate variability (RMSSD) — holding within healthy range and sleep efficiency — holding within healthy range. This score is driven primarily by typing-pattern changes.',
        });
      }
      return apiClient.get('/risk/score/narrative');
    },
  },

  alerts: {
    list: async () => {
      if (await isDemoSession()) {
        return mockResponse({ alerts: [
          { id: 'alert-1', type: 'risk_threshold_crossed', severity: 'warning',  title: 'High risk: James Harrison',    body: 'Risk score reached 0.82',                  created_at: new Date(Date.now()-3600000).toISOString()   },
          { id: 'alert-2', type: 'rem_behavior_anomaly',   severity: 'info',     title: 'REM anomaly: Margaret Liu',    body: 'REM fragmentation index > 0.5 (3 nights)', created_at: new Date(Date.now()-86400000).toISOString()  },
          { id: 'alert-3', type: 'rapid_progression',      severity: 'critical', title: 'Rapid progression: R. Okafor', body: '14-day delta exceeded 0.20',               created_at: new Date(Date.now()-172800000).toISOString() },
        ]});
      }
      return apiClient.get('/alerts');
    },

    create: async (data: { patient_id: string; message: string; severity: string; send_to_patient: boolean }) => {
      if (await isDemoSession()) return mockResponse({ alert_id: 'demo-alert-new', created_at: new Date().toISOString() });
      return apiClient.post('/clinician/alerts', data);
    },
  },

  reports: {
    generate: async (patientId: string, start: string, end: string) => {
      if (await isDemoSession()) return mockResponse({ report_id: 'demo-report-001', download_url: '#', expires_at: new Date(Date.now()+3600000).toISOString() });
      return apiClient.get('/reports/pdf', { params: { patient_id: patientId, period_start: start, period_end: end } });
    },
  },

  health: {
    summary: async () => {
      if (await isDemoSession()) return mockResponse({
        wellness_score:           72,
        risk_score:               0.28,
        risk_tier:                'low',
        sleep_quality_last_night: 0.81,
        typing_stability_7d:      0.74,
        wearable_sync_status:     'synced',
        data_completeness:        0.93,
        last_updated:             new Date().toISOString(),
      });
      return apiClient.get('/health/summary');
    },
  },

  auth: {
    register: (body: { email: string; password: string; age: number; gender: string; family_history: boolean; risk_group: string }) =>
      apiClient.post('/user/register', body),
  },
};
