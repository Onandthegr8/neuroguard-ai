'use client';

import { BarChart, Bar, XAxis, YAxis, Cell, Tooltip, ResponsiveContainer } from 'recharts';
import type { SHAPContributor } from '@/types';

interface Props {
  contributors: SHAPContributor[];
  keystrokeContrib: number;
  sleepContrib: number;
}

export function SHAPExplainer({ contributors, keystrokeContrib, sleepContrib }: Props) {
  const chartData = contributors.map(c => ({
    name: c.feature.replace(/_/g, ' '),
    value: c.contribution_pct,
    direction: c.direction,
  }));

  const totalContrib = Math.abs(keystrokeContrib) + Math.abs(sleepContrib);

  return (
    <div className="space-y-4">
      {/* Branch contribution bar */}
      <div>
        <p className="text-xs text-gray-500 mb-2 font-medium">Signal Sources</p>
        <div className="flex rounded-lg overflow-hidden h-6 text-xs font-medium">
          {totalContrib > 0 && <>
            <div style={{ width: `${Math.abs(keystrokeContrib) / totalContrib * 100}%` }} className="bg-blue-500 flex items-center justify-center text-white text-[10px]">Keystroke</div>
            <div style={{ width: `${Math.abs(sleepContrib) / totalContrib * 100}%` }} className="bg-indigo-500 flex items-center justify-center text-white text-[10px]">Sleep</div>
          </>}
        </div>
      </div>

      {/* Top feature contributions */}
      <div>
        <p className="text-xs text-gray-500 mb-2 font-medium">Top Risk Contributors</p>
        <ResponsiveContainer width="100%" height={160}>
          <BarChart data={chartData} layout="vertical" margin={{ left: 0, right: 20, top: 0, bottom: 0 }}>
            <XAxis type="number" tick={{ fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={v => `${v}%`} />
            <YAxis type="category" dataKey="name" tick={{ fontSize: 10, fill: '#64748b' }} tickLine={false} axisLine={false} width={130} />
            <Tooltip formatter={(v: number) => [`${v.toFixed(1)}%`, 'Contribution']} />
            <Bar dataKey="value" radius={[0, 4, 4, 0]}>
              {chartData.map((d, i) => (
                <Cell key={i} fill={d.direction === 'increases_risk' ? '#EF4444' : '#10B981'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <p className="text-[10px] text-gray-400">Red = increases risk · Green = decreases risk</p>
    </div>
  );
}
