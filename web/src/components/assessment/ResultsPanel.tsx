'use client';

import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import type { KeystrokeFeatures } from '@/lib/keystroke/analyzer';

interface Props {
  features: KeystrokeFeatures;
  onRetry: () => void;
}

function ScoreRing({ score }: { score: number }) {
  const color = score >= 70 ? '#22c55e' : score >= 45 ? '#f59e0b' : '#ef4444';
  const label = score >= 70 ? 'Consistent' : score >= 45 ? 'Moderate' : 'Variable';
  return (
    <div className="flex flex-col items-center gap-2">
      <div
        className="relative w-28 h-28 rounded-full flex items-center justify-center"
        style={{
          background: `conic-gradient(${color} ${score * 3.6}deg, #e5e7eb ${score * 3.6}deg)`,
        }}
      >
        <div className="w-20 h-20 bg-white rounded-full flex flex-col items-center justify-center">
          <span className="text-2xl font-bold text-gray-900">{score}</span>
          <span className="text-xs text-gray-400">/ 100</span>
        </div>
      </div>
      <span className="text-sm font-semibold" style={{ color }}>{label}</span>
    </div>
  );
}

function Metric({ label, value, unit, note }: {
  label: string; value: string | number; unit?: string; note?: string;
}) {
  return (
    <div className="bg-gray-50 rounded-xl p-4">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className="text-xl font-bold text-gray-900">
        {value}<span className="text-sm font-normal text-gray-400 ml-1">{unit}</span>
      </p>
      {note && <p className="text-xs text-gray-400 mt-1">{note}</p>}
    </div>
  );
}

export function ResultsPanel({ features: f, onRetry }: Props) {
  /* IKI over time — plot first 80 intervals for readability */
  const ikiChart = f.iki_times_ms
    .slice(0, 80)
    .map((v, i) => ({ i: i + 1, iki: Math.min(v, 1200) }));

  /* Dwell time histogram (15 buckets, 0–300 ms) */
  const BUCKET_SIZE = 20;
  const BUCKETS = 20;
  const histogram = Array.from({ length: BUCKETS }, (_, i) => ({
    label: `${i * BUCKET_SIZE}`,
    count: 0,
  }));
  f.dwell_times_ms.forEach(d => {
    const b = Math.min(BUCKETS - 1, Math.floor(d / BUCKET_SIZE));
    histogram[b].count++;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-gray-900">Typing Analysis Complete</h2>
          <p className="text-sm text-gray-500">
            {f.total_keystrokes} keystrokes · {(f.session_duration_ms / 1000).toFixed(1)}s session
          </p>
        </div>
        <button
          onClick={onRetry}
          className="px-4 py-2 border border-gray-200 rounded-xl text-sm font-medium text-gray-600 hover:bg-gray-50 transition-colors"
        >
          Try again
        </button>
      </div>

      {/* Score + key metrics */}
      <div className="card p-6">
        <div className="flex flex-col sm:flex-row items-center gap-8">
          <div className="text-center">
            <ScoreRing score={f.consistency_score} />
            <p className="text-xs text-gray-400 mt-2 max-w-[120px] text-center leading-tight">
              Typing Consistency Score
            </p>
          </div>
          <div className="flex-1 grid grid-cols-2 sm:grid-cols-3 gap-3 w-full">
            <Metric label="Typing Speed"       value={f.typing_speed_wpm} unit="WPM" />
            <Metric label="Avg Key Hold Time"  value={f.mean_dwell_ms}    unit="ms"
              note={`±${f.std_dwell_ms} ms`} />
            <Metric label="Avg Key Interval"   value={f.mean_iki_ms}      unit="ms"
              note={`±${f.std_iki_ms} ms`} />
            <Metric label="Rhythm Score"       value={f.rhythm_score}     unit="/ 100"
              note="IKI consistency" />
            <Metric label="Correction Rate"    value={`${(f.correction_frequency * 100).toFixed(1)}`} unit="%"
              note={`${f.backspace_count} backspaces`} />
            <Metric label="Pause Frequency"    value={`${(f.pause_frequency * 100).toFixed(1)}`} unit="%"
              note="Gaps > 500 ms" />
          </div>
        </div>
      </div>

      {/* IKI timeline */}
      <div className="card p-6">
        <h3 className="font-semibold text-gray-800 mb-1">Inter-Key Interval Over Time</h3>
        <p className="text-xs text-gray-400 mb-4">
          Time between consecutive keystrokes (ms) — lower variance indicates more consistent motor control
        </p>
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={ikiChart} margin={{ top: 4, right: 8, left: -20, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="i" tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} axisLine={false} label={{ value: 'Keystroke #', position: 'insideBottomRight', offset: 0, fontSize: 10, fill: '#94a3b8' }} />
            <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} axisLine={false} unit="ms" />
            <Tooltip formatter={(v: number) => [`${v} ms`, 'IKI']} />
            <ReferenceLine y={f.mean_iki_ms} stroke="#6366f1" strokeDasharray="4 4" strokeWidth={1.5}
              label={{ value: `Mean ${f.mean_iki_ms}ms`, position: 'insideTopRight', fontSize: 10, fill: '#6366f1' }} />
            <Line type="monotone" dataKey="iki" stroke="#1e40af" strokeWidth={1.5} dot={false} activeDot={{ r: 3 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Dwell time histogram */}
      <div className="card p-6">
        <h3 className="font-semibold text-gray-800 mb-1">Key Hold Duration Distribution</h3>
        <p className="text-xs text-gray-400 mb-4">
          How long each key was pressed (ms) — a narrow distribution suggests uniform finger control
        </p>
        <ResponsiveContainer width="100%" height={160}>
          <BarChart data={histogram} margin={{ top: 4, right: 8, left: -20, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="label" tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} axisLine={false} unit="ms" />
            <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
            <Tooltip formatter={(v: number) => [v, 'keystrokes']} labelFormatter={l => `${l}–${+l + 20} ms`} />
            <Bar dataKey="count" fill="#6366f1" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Disclaimer */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
        <p className="text-xs text-amber-800 leading-relaxed">
          <span className="font-semibold">ℹ️ Informational only.</span> These metrics capture your
          typing rhythm and consistency during this session. They are <span className="font-semibold">
          not a medical diagnosis</span> and can vary with fatigue, device type, and environment.
          Results are sent to your care team as one data point among many.
        </p>
      </div>
    </div>
  );
}
