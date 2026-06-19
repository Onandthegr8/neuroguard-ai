'use client';

import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

interface DataPoint { date: string; value: number; }
interface Props { data: DataPoint[]; label: string; color: string; }

export function BiomarkerCard({ data, label, color }: Props) {
  if (!data.length) return <p className="text-sm text-gray-400">No data available</p>;
  const chartData = data.map(d => ({ date: d.date.slice(5), value: Number(d.value.toFixed(3)) }));
  return (
    <div>
      <ResponsiveContainer width="100%" height={160}>
        <AreaChart data={chartData} margin={{ top: 5, right: 5, left: -25, bottom: 0 }}>
          <defs>
            <linearGradient id={`grad-${label}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={color} stopOpacity={0.15} />
              <stop offset="95%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
          <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
          <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
          <Tooltip formatter={(v: number) => [v.toFixed(3), label]} />
          <Area type="monotone" dataKey="value" stroke={color} strokeWidth={2} fill={`url(#grad-${label})`} dot={false} />
        </AreaChart>
      </ResponsiveContainer>
      <p className="text-xs text-gray-400 mt-1">{label} over time</p>
    </div>
  );
}
