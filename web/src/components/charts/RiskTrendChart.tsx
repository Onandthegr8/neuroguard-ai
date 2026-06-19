'use client';

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { RISK_TIER_COLORS } from '@/lib/utils/risk';
import type { RiskHistoryPoint } from '@/types';

interface Props { data: RiskHistoryPoint[]; }

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const score = payload[0].value as number;
  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-lg p-3 text-sm">
      <p className="text-gray-500 mb-1">{label}</p>
      <p className="font-bold text-gray-900">Risk: {(score * 100).toFixed(1)}%</p>
    </div>
  );
}

export function RiskTrendChart({ data }: Props) {
  if (!data.length) return <div className="h-64 flex items-center justify-center text-gray-400 text-sm">No data yet</div>;

  const chartData = data.map(d => ({
    date: d.date.slice(5),   // MM-DD
    score: d.risk_score,
    tier: d.risk_tier,
  }));

  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={chartData} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
        <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
        <YAxis domain={[0, 1]} tickFormatter={v => `${(v*100).toFixed(0)}%`} tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine y={0.55} stroke="#EF4444" strokeDasharray="4 4" strokeWidth={1.5} label={{ value: 'Alert threshold', position: 'insideTopRight', fontSize: 10, fill: '#EF4444' }} />
        <Line type="monotone" dataKey="score" stroke="#1e40af" strokeWidth={2.5} dot={false} activeDot={{ r: 4, fill: '#1e40af' }} />
      </LineChart>
    </ResponsiveContainer>
  );
}
