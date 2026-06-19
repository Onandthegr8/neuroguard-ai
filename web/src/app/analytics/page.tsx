'use client';

import useSWR from 'swr';
import { useEffect, useState } from 'react';
import { getSession } from 'next-auth/react';
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell, PieChart, Pie,
} from 'recharts';
import { api, apiClient } from '@/lib/api/client';
import { RISK_TIER_COLORS, RISK_TIER_LABEL } from '@/lib/utils/risk';
import { Users, AlertTriangle, TrendingUp, Activity } from 'lucide-react';
import type { Patient, RiskTier } from '@/types';

const TIERS: RiskTier[] = ['very_low', 'low', 'moderate', 'high', 'very_high'];

interface Overview {
  total_patients:     number;
  total_alerts_30d:   number;
  avg_risk_score:     number;
  high_risk_count:    number;
  risk_distribution:  { tier: string; count: number }[];
  alerts_per_day:     { date: string; count: number }[];
  model_performance:  { model_version: string; avg_risk_score: number; n_predictions: number }[];
}

async function fetchOverview(): Promise<Overview | null> {
  const session = await getSession();
  const token = (session as any)?.accessToken;
  if (!token || token === 'demo-access-token') return null;
  try {
    const resp = await apiClient.get('/analytics/overview');
    return resp.data;
  } catch {
    return null;
  }
}

export default function AnalyticsPage() {
  // Try real backend first
  const [realData, setRealData] = useState<Overview | null>(null);
  useEffect(() => { fetchOverview().then(setRealData); }, []);

  // Mock fallback (demo mode)
  const { data: mock } = useSWR('analytics-patients', () => api.patients.list({ limit: 500 }).then(r => r.data));
  const patients: Patient[] = mock?.patients ?? [];

  // Build the same shape regardless of source
  const overview: Overview = realData ?? {
    total_patients:     patients.length,
    total_alerts_30d:   18,
    avg_risk_score:     patients.length ? patients.reduce((s, p) => s + (p.latest_risk_score ?? 0), 0) / patients.length : 0,
    high_risk_count:    patients.filter(p => ['high', 'very_high'].includes(p.latest_risk_tier ?? '')).length,
    risk_distribution:  TIERS.map(t => ({ tier: t, count: patients.filter(p => p.latest_risk_tier === t).length })),
    alerts_per_day:     Array.from({ length: 30 }, (_, i) => ({
      date:  new Date(Date.now() - (29 - i) * 86400000).toISOString().slice(0, 10),
      count: Math.floor(Math.random() * 6),
    })),
    model_performance:  [
      { model_version: 'v1.0.0',      avg_risk_score: 0.42, n_predictions: 1240 },
      { model_version: 'v1.0.0-rc1',  avg_risk_score: 0.39, n_predictions: 380  },
    ],
  };

  const distribution = TIERS.map((t, i) => ({
    tier:   RISK_TIER_LABEL[t],
    count:  overview.risk_distribution[i]?.count ?? 0,
    color:  RISK_TIER_COLORS[t],
  }));

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Population Analytics</h1>
          <p className="text-sm text-gray-500 mt-1">De-identified aggregate statistics across your patient cohort.</p>
        </div>
        {realData && (
          <span className="text-xs px-2 py-1 bg-green-50 text-green-700 rounded-lg font-medium border border-green-200">
            Live backend data
          </span>
        )}
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Kpi icon={<Users className="w-5 h-5 text-blue-600" />}
             label="Total Patients"
             value={overview.total_patients}
             color="bg-blue-50" />
        <Kpi icon={<AlertTriangle className="w-5 h-5 text-amber-600" />}
             label="Alerts (30d)"
             value={overview.total_alerts_30d}
             color="bg-amber-50" />
        <Kpi icon={<TrendingUp className="w-5 h-5 text-rose-600" />}
             label="High-Risk Patients"
             value={overview.high_risk_count}
             color="bg-rose-50" />
        <Kpi icon={<Activity className="w-5 h-5 text-emerald-600" />}
             label="Avg Population Risk"
             value={`${(overview.avg_risk_score * 100).toFixed(1)}%`}
             color="bg-emerald-50" />
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Risk distribution */}
        <div className="card p-6">
          <h2 className="font-semibold text-gray-800 mb-4">Risk Tier Distribution</h2>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={distribution} margin={{ left: -10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="tier" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                {distribution.map((d, i) => <Cell key={i} fill={d.color} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Alerts per day */}
        <div className="card p-6">
          <h2 className="font-semibold text-gray-800 mb-4">Alert Volume — Last 30 Days</h2>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={overview.alerts_per_day}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 10 }}
                tickFormatter={(d) => d.slice(5)}
              />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Line type="monotone" dataKey="count" stroke="#1E3A5F" strokeWidth={2} dot={{ r: 2 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Model performance */}
      <div className="card p-6">
        <h2 className="font-semibold text-gray-800 mb-4">Model Performance by Version</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left border-b border-gray-200 text-gray-500">
              <th className="py-2">Model Version</th>
              <th className="py-2 text-right">Avg Risk Score</th>
              <th className="py-2 text-right">Predictions</th>
              <th className="py-2 text-right">Distribution</th>
            </tr>
          </thead>
          <tbody>
            {overview.model_performance.map((m) => (
              <tr key={m.model_version} className="border-b border-gray-50 last:border-0">
                <td className="py-3 font-medium text-gray-800">{m.model_version}</td>
                <td className="py-3 text-right">{(m.avg_risk_score * 100).toFixed(1)}%</td>
                <td className="py-3 text-right text-gray-600">{m.n_predictions.toLocaleString()}</td>
                <td className="py-3">
                  <div className="w-full bg-gray-100 rounded-full h-2 ml-auto max-w-[120px]">
                    <div
                      className="bg-blue-600 h-2 rounded-full"
                      style={{ width: `${Math.min(m.avg_risk_score * 100, 100)}%` }}
                    />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-gray-400">
        Analytics are de-identified and aggregated. No individual patient data is shown here.
        Source: <code className="text-gray-500">{realData ? 'live backend (/analytics/overview)' : 'demo mock data'}</code>
      </p>
    </div>
  );
}

function Kpi({ icon, label, value, color }: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  color: string;
}) {
  return (
    <div className="card p-5 flex items-center gap-4">
      <div className={`w-11 h-11 ${color} rounded-xl flex items-center justify-center`}>{icon}</div>
      <div>
        <div className="text-xs uppercase tracking-wider text-gray-500">{label}</div>
        <div className="text-2xl font-bold text-gray-900">{value}</div>
      </div>
    </div>
  );
}
