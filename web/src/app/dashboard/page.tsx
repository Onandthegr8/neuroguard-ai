'use client';

import { useState } from 'react';
import useSWR from 'swr';
import { api } from '@/lib/api/client';
import { RISK_TIER_LABEL, RISK_TIER_BG, formatScore } from '@/lib/utils/risk';
import type { Patient, RiskTier } from '@/types';
import Link from 'next/link';
import { Users, AlertTriangle, TrendingUp, Activity, ClipboardCheck, UserPlus, X } from 'lucide-react';
import { NarrativeExplanation } from '@/components/charts/NarrativeExplanation';

const fetcher = (key: string) => {
  if (key === 'patients') return api.patients.list({ limit: 100 }).then(r => r.data);
  return null;
};

const EMPTY_FORM = { email: '', password: '', age: '', gender: 'prefer_not_to_say', family_history: false };

export default function DashboardPage() {
  const { data, isLoading, mutate } = useSWR('patients', fetcher);

  const [showModal, setShowModal] = useState(false);
  const [form, setForm]           = useState({ ...EMPTY_FORM });
  const [saving, setSaving]       = useState(false);
  const [error, setError]         = useState<string | null>(null);
  const [success, setSuccess]     = useState(false);
  const patients: Patient[] = data?.patients ?? [];

  const { data: narrative, isLoading: narrativeLoading } = useSWR(
    'narrative-self',
    () => api.risk.narrative().then(r => r.data),
  );

  async function handleAddPatient(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.auth.register({
        email:          form.email,
        password:       form.password,
        age:            parseInt(form.age, 10) || 0,
        gender:         form.gender,
        family_history: form.family_history,
        risk_group:     'user',
      });
      setSuccess(true);
      mutate();
      setTimeout(() => {
        setShowModal(false);
        setSuccess(false);
        setForm({ ...EMPTY_FORM });
      }, 1800);
    } catch (err: any) {
      const msg = err?.response?.data?.detail ?? 'Registration failed. Please try again.';
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setSaving(false);
    }
  }

  const highRisk    = patients.filter(p => p.latest_risk_tier === 'high' || p.latest_risk_tier === 'very_high').length;
  const moderate    = patients.filter(p => p.latest_risk_tier === 'moderate').length;
  const avgScore    = patients.length
    ? patients.reduce((s, p) => s + (p.latest_risk_score ?? 0), 0) / patients.length
    : 0;

  const stats = [
    { label: 'Total Patients',     value: patients.length, icon: Users,          color: 'text-blue-600',   bg: 'bg-blue-50'   },
    { label: 'High / Very High',   value: highRisk,        icon: AlertTriangle,  color: 'text-red-600',    bg: 'bg-red-50'    },
    { label: 'Moderate Risk',      value: moderate,        icon: TrendingUp,     color: 'text-amber-600',  bg: 'bg-amber-50'  },
    { label: 'Avg Risk Score',     value: `${(avgScore*100).toFixed(1)}%`, icon: Activity, color: 'text-teal-600', bg: 'bg-teal-50' },
  ];

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-500 text-sm mt-1">Patient monitoring overview</p>
        </div>
        <button
          onClick={() => { setShowModal(true); setError(null); setSuccess(false); setForm({ ...EMPTY_FORM }); }}
          className="flex items-center gap-2 bg-blue-800 hover:bg-blue-700 text-white text-sm font-semibold px-4 py-2.5 rounded-xl transition-colors"
        >
          <UserPlus className="w-4 h-4" />
          Add New Patient
        </button>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map(s => (
          <div key={s.label} className="card p-5 flex items-center gap-4">
            <div className={`${s.bg} p-3 rounded-xl`}>
              <s.icon className={`w-5 h-5 ${s.color}`} />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{isLoading ? '—' : s.value}</p>
              <p className="text-xs text-gray-500">{s.label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* AI narrative explanation */}
      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 card p-6">
          <h2 className="font-semibold text-gray-800 mb-4">Your Risk Explanation</h2>
          <NarrativeExplanation data={narrative} loading={narrativeLoading} />
        </div>
        <div className="card p-6 flex flex-col">
          <h2 className="font-semibold text-gray-800 mb-2">Active Screening</h2>
          <p className="text-xs text-gray-500 mb-4">
            Take a 1-minute test to add specificity to your risk profile.
          </p>
          <div className="flex-1" />
          <Link href="/assessment" className="flex items-center justify-center gap-2 bg-blue-800 hover:bg-blue-700 text-white text-sm font-semibold py-2.5 rounded-xl">
            <ClipboardCheck className="w-4 h-4" />
            Start a test
          </Link>
        </div>
      </div>

      {/* High-risk patient list */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-gray-800">High-Risk Patients</h2>
          <Link href="/patients" className="text-sm text-blue-600 hover:underline">View all →</Link>
        </div>
        {isLoading ? (
          <div className="space-y-3">{Array.from({length:4}).map((_,i)=>(
            <div key={i} className="h-12 bg-gray-100 animate-pulse rounded-xl" />
          ))}</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-400 border-b border-gray-100">
                <th className="pb-3 font-medium">Patient</th>
                <th className="pb-3 font-medium">Risk Score</th>
                <th className="pb-3 font-medium">Tier</th>
                <th className="pb-3 font-medium">Last Prediction</th>
                <th className="pb-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {patients
                .filter(p => p.latest_risk_tier === 'high' || p.latest_risk_tier === 'very_high')
                .slice(0, 8)
                .map(p => (
                  <PatientRow key={p.id} patient={p} />
                ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Add New Patient Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 p-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-bold text-gray-900">Add New Patient</h2>
              <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600 transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>

            {success ? (
              <div className="flex flex-col items-center gap-3 py-8 text-green-700">
                <div className="w-14 h-14 rounded-full bg-green-100 flex items-center justify-center">
                  <UserPlus className="w-7 h-7" />
                </div>
                <p className="font-semibold text-lg">Patient registered!</p>
                <p className="text-sm text-gray-500">The patient can now log in with their credentials.</p>
              </div>
            ) : (
              <form onSubmit={handleAddPatient} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Email <span className="text-red-500">*</span></label>
                  <input
                    type="email" required
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="patient@example.com"
                    value={form.email}
                    onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Temporary Password <span className="text-red-500">*</span></label>
                  <input
                    type="password" required minLength={8}
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Min. 8 characters"
                    value={form.password}
                    onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Age</label>
                    <input
                      type="number" min={1} max={120}
                      className="w-full px-3 py-2 text-sm border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="e.g. 65"
                      value={form.age}
                      onChange={e => setForm(f => ({ ...f, age: e.target.value }))}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Gender</label>
                    <select
                      className="w-full px-3 py-2 text-sm border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                      value={form.gender}
                      onChange={e => setForm(f => ({ ...f, gender: e.target.value }))}
                    >
                      <option value="prefer_not_to_say">Prefer not to say</option>
                      <option value="male">Male</option>
                      <option value="female">Female</option>
                      <option value="other">Other</option>
                    </select>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    id="family_history" type="checkbox"
                    className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    checked={form.family_history}
                    onChange={e => setForm(f => ({ ...f, family_history: e.target.checked }))}
                  />
                  <label htmlFor="family_history" className="text-sm text-gray-700">Family history of Parkinson&apos;s disease</label>
                </div>

                {error && (
                  <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-xl px-3 py-2">{error}</p>
                )}

                <div className="flex gap-3 pt-1">
                  <button
                    type="button"
                    onClick={() => setShowModal(false)}
                    className="flex-1 px-4 py-2.5 text-sm font-semibold text-gray-700 border border-gray-200 rounded-xl hover:bg-gray-50 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit" disabled={saving}
                    className="flex-1 px-4 py-2.5 text-sm font-semibold text-white bg-blue-800 hover:bg-blue-700 rounded-xl transition-colors disabled:opacity-60 flex items-center justify-center gap-2"
                  >
                    {saving ? (
                      <><span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />Registering…</>
                    ) : (
                      <><UserPlus className="w-4 h-4" />Register Patient</>
                    )}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function PatientRow({ patient }: { patient: Patient }) {
  const tier = patient.latest_risk_tier ?? 'very_low';
  return (
    <tr className="hover:bg-gray-50 transition-colors">
      <td className="py-3 font-medium text-gray-800">{patient.email}</td>
      <td className="py-3">{patient.latest_risk_score != null ? formatScore(patient.latest_risk_score) : '—'}</td>
      <td className="py-3">
        <span className={`text-xs font-semibold px-2 py-1 rounded-full border badge-${tier}`}>
          {RISK_TIER_LABEL[tier as RiskTier] ?? tier}
        </span>
      </td>
      <td className="py-3 text-gray-400 text-xs">{patient.latest_prediction_at?.slice(0,10) ?? '—'}</td>
      <td className="py-3 text-right">
        <Link href={`/patients/${patient.id}`} className="text-blue-600 hover:underline text-xs font-medium">View</Link>
      </td>
    </tr>
  );
}
