'use client';

import { useState } from 'react';
import useSWR from 'swr';
import Link from 'next/link';
import { Search } from 'lucide-react';
import { api } from '@/lib/api/client';
import { RISK_TIER_LABEL, RISK_TIER_BG, formatScore } from '@/lib/utils/risk';
import type { Patient, RiskTier } from '@/types';

export default function PatientsPage() {
  const [search, setSearch]   = useState('');
  const [tierFilter, setTier] = useState('');
  const [page, setPage]       = useState(1);

  const { data, isLoading } = useSWR(
    `patients-${search}-${tierFilter}-${page}`,
    () => api.patients.list({ search, risk_tier: tierFilter || undefined, page, limit: 20 }).then(r => r.data)
  );

  const patients: Patient[] = data?.patients ?? [];
  const total: number = data?.total ?? 0;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Patients</h1>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            className="pl-9 pr-4 py-2 text-sm border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white w-64"
            placeholder="Search by email…"
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1); }}
          />
        </div>
        <select
          className="px-3 py-2 text-sm border border-gray-200 rounded-xl focus:outline-none bg-white"
          value={tierFilter}
          onChange={e => { setTier(e.target.value); setPage(1); }}
        >
          <option value="">All Risk Tiers</option>
          {(['very_low','low','moderate','high','very_high'] as RiskTier[]).map(t => (
            <option key={t} value={t}>{RISK_TIER_LABEL[t]}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr className="text-left text-gray-500">
              <th className="px-6 py-3 font-medium">Email</th>
              <th className="px-6 py-3 font-medium">Age</th>
              <th className="px-6 py-3 font-medium">Risk Score</th>
              <th className="px-6 py-3 font-medium">Tier</th>
              <th className="px-6 py-3 font-medium">Last Updated</th>
              <th className="px-6 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {isLoading
              ? Array.from({length: 8}).map((_, i) => (
                  <tr key={i}><td colSpan={6} className="px-6 py-4"><div className="h-4 bg-gray-100 animate-pulse rounded" /></td></tr>
                ))
              : patients.map(p => {
                  const tier = p.latest_risk_tier ?? 'very_low';
                  return (
                    <tr key={p.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-6 py-4 font-medium text-gray-800">{p.email}</td>
                      <td className="px-6 py-4 text-gray-500">{p.age ?? '—'}</td>
                      <td className="px-6 py-4">{p.latest_risk_score != null ? formatScore(p.latest_risk_score) : '—'}</td>
                      <td className="px-6 py-4">
                        <span className={`text-xs font-semibold px-2 py-1 rounded-full border badge-${tier}`}>
                          {RISK_TIER_LABEL[tier as RiskTier] ?? tier}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-gray-400 text-xs">{p.latest_prediction_at?.slice(0,10) ?? '—'}</td>
                      <td className="px-6 py-4 text-right">
                        <Link href={`/patients/${p.id}`} className="text-blue-600 hover:underline text-xs font-medium">View →</Link>
                      </td>
                    </tr>
                  );
                })
            }
          </tbody>
        </table>
        <div className="px-6 py-3 border-t border-gray-100 flex items-center justify-between text-sm text-gray-500">
          <span>{total} total patients</span>
          <div className="flex gap-2">
            <button onClick={() => setPage(p => Math.max(1, p-1))} disabled={page === 1} className="px-3 py-1 rounded-lg border disabled:opacity-40 hover:bg-gray-50">←</button>
            <span className="px-3 py-1">Page {page}</span>
            <button onClick={() => setPage(p => p+1)} disabled={patients.length < 20} className="px-3 py-1 rounded-lg border disabled:opacity-40 hover:bg-gray-50">→</button>
          </div>
        </div>
      </div>
    </div>
  );
}
