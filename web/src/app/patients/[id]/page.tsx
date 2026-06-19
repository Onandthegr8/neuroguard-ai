'use client';

import { useState } from 'react';
import useSWR from 'swr';
import { api } from '@/lib/api/client';
import { RISK_TIER_LABEL, RISK_TIER_COLORS, formatScore } from '@/lib/utils/risk';
import type { PatientTimeline, RiskTier } from '@/types';
import { RiskTrendChart } from '@/components/charts/RiskTrendChart';
import { SHAPExplainer } from '@/components/charts/SHAPExplainer';
import { NarrativeExplanation } from '@/components/charts/NarrativeExplanation';
import { AlertFeed } from '@/components/alerts/AlertFeed';
import { BiomarkerCard } from '@/components/charts/BiomarkerCard';
import { FileText, Bell, ArrowLeft } from 'lucide-react';
import Link from 'next/link';

export default function PatientDetailPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const [days, setDays] = useState(90);

  const { data: timeline, isLoading } = useSWR<PatientTimeline>(
    `timeline-${id}-${days}`,
    () => api.patients.timeline(id, days).then(r => r.data)
  );

  const { data: riskData } = useSWR(
    `risk-${id}`,
    () => api.risk.score(id).then(r => r.data)
  );

  const { data: narrative, isLoading: narrativeLoading } = useSWR(
    `narrative-${id}`,
    () => api.risk.narrative().then(r => r.data),
  );

  const latestRisk = riskData?.risk_score;
  const latestTier = riskData?.risk_tier as RiskTier | undefined;

  const handleGenerateReport = async () => {
    const end   = new Date().toISOString().slice(0, 10);
    const start = new Date(Date.now() - days * 86400000).toISOString().slice(0, 10);
    const { data } = await api.reports.generate(id, start, end);
    window.open(data.download_url, '_blank');
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/patients" className="p-2 rounded-xl hover:bg-gray-100 transition-colors">
            <ArrowLeft className="w-4 h-4 text-gray-500" />
          </Link>
          <div>
            <h1 className="text-xl font-bold text-gray-900">Patient {id.slice(0, 8)}…</h1>
            {latestTier && (
              <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border badge-${latestTier}`}>
                {RISK_TIER_LABEL[latestTier]}
                {latestRisk != null && ` · ${formatScore(latestRisk)}`}
              </span>
            )}
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={handleGenerateReport} className="flex items-center gap-2 px-4 py-2 bg-blue-800 text-white rounded-xl text-sm font-medium hover:bg-blue-700 transition-colors">
            <FileText className="w-4 h-4" /> Generate Report
          </button>
        </div>
      </div>

      {/* Days selector */}
      <div className="flex gap-2">
        {[30, 60, 90, 180].map(d => (
          <button key={d} onClick={() => setDays(d)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${days === d ? 'bg-blue-800 text-white' : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'}`}>
            {d}d
          </button>
        ))}
      </div>

      {/* Risk + SHAP row */}
      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 card p-6">
          <h2 className="font-semibold text-gray-800 mb-4">Risk Score Trend</h2>
          {isLoading
            ? <div className="h-64 bg-gray-100 animate-pulse rounded-xl" />
            : <RiskTrendChart data={timeline?.risk_trend ?? []} />
          }
        </div>
        <div className="card p-6">
          <h2 className="font-semibold text-gray-800 mb-4">AI Explainability</h2>
          {riskData?.top_contributors
            ? <SHAPExplainer contributors={riskData.top_contributors} keystrokeContrib={riskData.keystroke_contribution} sleepContrib={riskData.sleep_contribution} />
            : <div className="h-64 bg-gray-100 animate-pulse rounded-xl" />
          }
        </div>
      </div>

      {/* AI Narrative Explanation */}
      <div className="card p-6">
        <h2 className="font-semibold text-gray-800 mb-4">AI Narrative Explanation</h2>
        <NarrativeExplanation data={narrative} loading={narrativeLoading} />
      </div>

      {/* Biomarker cards */}
      <div className="grid lg:grid-cols-2 gap-6">
        <div className="card p-6">
          <h2 className="font-semibold text-gray-800 mb-4">Sleep Biomarkers</h2>
          {timeline?.sleep_trend?.length
            ? <BiomarkerCard data={timeline.sleep_trend.map(s => ({ date: s.date, value: s.rem_fragmentation ?? 0 }))} label="REM Fragmentation Index" color="#6366f1" />
            : <p className="text-sm text-gray-400">No sleep data available</p>
          }
        </div>
        <div className="card p-6">
          <h2 className="font-semibold text-gray-800 mb-4">Keystroke Stability</h2>
          {timeline?.keystroke_trend?.length
            ? <BiomarkerCard data={timeline.keystroke_trend.map(k => ({ date: k.date, value: k.entropy ?? 0 }))} label="Typing Entropy" color="#0d9488" />
            : <p className="text-sm text-gray-400">No keystroke data available</p>
          }
        </div>
      </div>

      {/* Alerts */}
      <div className="card p-6">
        <h2 className="font-semibold text-gray-800 mb-4">Recent Alerts</h2>
        <AlertFeed alerts={timeline?.alerts ?? []} patientId={id} />
      </div>
    </div>
  );
}
