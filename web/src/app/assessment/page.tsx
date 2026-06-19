'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Keyboard, Moon, ArrowRight, CheckCircle2 } from 'lucide-react';
import { apiClient } from '@/lib/api/client';
import { getSession } from 'next-auth/react';

interface LatestScores {
  [key: string]: {
    score:          number | null;
    taken_at:       string | null;
    interpretation: string;
  };
}

const TESTS = [
  {
    key:    'typing',
    label:  'Keystroke Test',
    blurb:  'Type a short passage. Measures rhythm, inter-key interval, dwell time, and correction frequency — all passive biomarkers for early motor changes.',
    icon:   Keyboard,
    color:  'blue',
    href:   '/assessment/typing',
    dur:    '~2 min',
  },
] as const;

const COLOR_STYLES: Record<string, { tile: string; icon: string }> = {
  blue:   { tile: 'border-blue-200 hover:border-blue-400',   icon: 'bg-blue-100 text-blue-700'   },
  indigo: { tile: 'border-indigo-200 hover:border-indigo-400', icon: 'bg-indigo-100 text-indigo-700' },
};

export default function AssessmentIndexPage() {
  const [scores,  setScores]  = useState<LatestScores | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const session = await getSession();
        const token   = (session as any)?.accessToken;
        if (!token || token === 'demo-access-token') {
          if (!cancelled) {
            setScores({
              typing: { score: 64, taken_at: '2026-05-15T08:30:00Z', interpretation: 'Mildly impaired — consider re-testing in 7 days.' },
            });
            setLoading(false);
          }
          return;
        }
        const resp = await apiClient.get<LatestScores>('/assessments/latest');
        if (!cancelled) { setScores(resp.data); setLoading(false); }
      } catch {
        if (!cancelled) { setScores({}); setLoading(false); }
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Active Screening</h1>
        <p className="text-gray-500 text-sm mt-1 max-w-2xl">
          Keystroke biometrics capture subtle motor changes passively while you type.
          Take the test weekly for the best longitudinal signal.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Static sleep import card */}
        <Link
          href="/settings/import-sleep"
          className="group bg-white border-2 rounded-2xl p-5 hover:shadow-md transition-all border-indigo-200 hover:border-indigo-400"
        >
          <div className="flex items-start gap-4 mb-3">
            <div className="w-12 h-12 rounded-xl flex items-center justify-center bg-indigo-100 text-indigo-700">
              <Moon className="w-6 h-6" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-gray-900">Import Sleep Data</h3>
                <ArrowRight className="w-4 h-4 text-gray-400 group-hover:translate-x-1 transition-transform" />
              </div>
              <p className="text-xs text-gray-500 mt-0.5">Upload CSV</p>
            </div>
          </div>
          <p className="text-sm text-gray-600 leading-relaxed mb-4">
            Upload a sleep export from Mi Fitness, Fitbit, Samsung Health, or any CSV. Maps directly
            to the 15 sleep features used by the risk model.
          </p>
          <div className="flex items-center border-t border-gray-100 pt-3 -mx-1 px-1">
            <span className="text-xs text-gray-400">Mi Fitness, Zepp, generic CSV supported</span>
          </div>
        </Link>

        {TESTS.map(t => {
          const Icon  = t.icon;
          const sc    = scores?.[t.key];
          const score = sc?.score ?? null;
          const tone  = score == null ? 'gray'
                      : score >= 70   ? 'green'
                      : score >= 50   ? 'amber' : 'red';
          const toneClasses = {
            gray:  'bg-gray-100 text-gray-500',
            green: 'bg-green-100 text-green-800',
            amber: 'bg-amber-100 text-amber-800',
            red:   'bg-red-100 text-red-800',
          }[tone];
          const styles = COLOR_STYLES[t.color];

          return (
            <Link
              key={t.key}
              href={t.href}
              className={`group bg-white border-2 rounded-2xl p-5 hover:shadow-md transition-all ${styles.tile}`}
            >
              <div className="flex items-start gap-4 mb-3">
                <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${styles.icon}`}>
                  <Icon className="w-6 h-6" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold text-gray-900">{t.label}</h3>
                    <ArrowRight className="w-4 h-4 text-gray-400 group-hover:translate-x-1 transition-transform" />
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5">{t.dur}</p>
                </div>
              </div>
              <p className="text-sm text-gray-600 leading-relaxed mb-4">{t.blurb}</p>

              <div className="flex items-center justify-between border-t border-gray-100 pt-3 -mx-1 px-1">
                {loading ? (
                  <span className="text-xs text-gray-400">Loading latest result…</span>
                ) : score !== null ? (
                  <>
                    <span className={`text-xs px-2 py-1 rounded-md font-semibold ${toneClasses}`}>
                      Last score: {score.toFixed(0)}/100
                    </span>
                    <span className="text-xs text-gray-400">
                      {sc?.taken_at ? new Date(sc.taken_at).toLocaleDateString() : ''}
                    </span>
                  </>
                ) : (
                  <span className="text-xs text-gray-400">Not taken yet</span>
                )}
              </div>
            </Link>
          );
        })}
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-sm text-blue-900 max-w-2xl">
        <strong className="block mb-1 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4" /> Why keystroke biometrics?
        </strong>
        Typing rhythm, inter-key interval, and dwell time are non-invasive proxies for fine motor
        control. Changes in these patterns — often unnoticed consciously — can precede clinical
        Parkinson&apos;s symptoms by months to years.
      </div>
    </div>
  );
}
