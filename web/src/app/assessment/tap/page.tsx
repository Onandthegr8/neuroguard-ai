'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, Hand, CheckCircle2 } from 'lucide-react';
import { submitAssessment } from '@/lib/api/assessments';

type Phase = 'intro' | 'running' | 'done';
type Hand  = 'left' | 'right';

const DURATION_MS = 15_000;

interface TapResult {
  tap_count:      number;
  mean_iti_ms:    number;
  iti_cv:         number;
  fatigue_index:  number;
  hand:           Hand;
  overall_score:  number;
}

export default function FingerTapPage() {
  const [phase,  setPhase]  = useState<Phase>('intro');
  const [hand,   setHand]   = useState<Hand>('right');
  const [tapCount, setTapCount] = useState(0);
  const [elapsed,  setElapsed]  = useState(0);
  const [result,   setResult]   = useState<TapResult | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const tapTimesRef = useRef<number[]>([]);
  const startRef    = useRef<number>(0);
  const rafRef      = useRef<number | null>(null);

  // Animation loop for the elapsed-time bar
  useEffect(() => {
    if (phase !== 'running') return;

    function tick() {
      const e = performance.now() - startRef.current;
      setElapsed(Math.min(e, DURATION_MS));
      if (e < DURATION_MS) rafRef.current = requestAnimationFrame(tick);
      else finish();
    }
    rafRef.current = requestAnimationFrame(tick);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);

  function start() {
    tapTimesRef.current = [];
    startRef.current = performance.now();
    setTapCount(0);
    setElapsed(0);
    setResult(null);
    setPhase('running');
  }

  function handleTap() {
    if (phase !== 'running') return;
    const now = performance.now();
    tapTimesRef.current.push(now);
    setTapCount(tapTimesRef.current.length);
  }

  async function finish() {
    const taps = tapTimesRef.current;
    if (taps.length < 5) { setPhase('intro'); return; }

    // Inter-tap intervals in ms
    const itis: number[] = [];
    for (let i = 1; i < taps.length; i++) itis.push(taps[i] - taps[i - 1]);

    const meanITI = itis.reduce((a,b)=>a+b,0)/itis.length;
    const varITI  = itis.reduce((s,x)=>s+(x-meanITI)**2,0)/itis.length;
    const stdITI  = Math.sqrt(varITI);
    const cvITI   = stdITI / (meanITI + 1e-9);

    // Fatigue index: ratio of mean ITI in 2nd half vs 1st half
    const mid       = Math.floor(itis.length / 2);
    const firstMean = mean(itis.slice(0, mid));
    const secondMean = mean(itis.slice(mid));
    const fatigueIdx = firstMean > 0 ? (secondMean - firstMean) / firstMean : 0;

    // Composite score:
    //   tap rate (faster = better) — healthy adults: 60+ taps in 15s
    //   rhythm consistency (lower CV = better) — healthy CV < 0.20
    //   minimal fatigue                          — healthy |fatigue| < 0.10
    const rateScore   = Math.min(100, (taps.length / 60) * 100);
    const rhythmScore = Math.max(0, 100 - cvITI * 200);
    const fatigueScore = Math.max(0, 100 - Math.abs(fatigueIdx) * 200);
    const overall = round1(0.50 * rateScore + 0.30 * rhythmScore + 0.20 * fatigueScore);

    const r: TapResult = {
      tap_count:     taps.length,
      mean_iti_ms:   round1(meanITI),
      iti_cv:        round3(cvITI),
      fatigue_index: round3(fatigueIdx),
      hand,
      overall_score: overall,
    };
    setResult(r);

    setSubmitting(true);
    try {
      await submitAssessment({
        assessment_type: 'finger_tap',
        overall_score:   r.overall_score,
        metrics: { ...r },
      });
    } catch {}
    setSubmitting(false);
    setPhase('done');
  }

  function reset() {
    setPhase('intro');
    setTapCount(0); setElapsed(0); setResult(null);
  }

  // ── UI ────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-white p-6">
      <div className="max-w-2xl mx-auto">
        <Link href="/assessment" className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-blue-700 mb-4">
          <ArrowLeft className="w-4 h-4" /> Back to assessments
        </Link>

        <div className="bg-white rounded-2xl shadow-md p-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 bg-emerald-100 rounded-xl flex items-center justify-center">
              <Hand className="w-5 h-5 text-emerald-700" />
            </div>
            <h1 className="text-2xl font-bold text-gray-900">Finger Tap Test</h1>
          </div>
          <p className="text-sm text-gray-500 mb-6">
            UPDRS-style finger-tap test: tap as fast and rhythmically as you can for 15 seconds.
          </p>

          {phase === 'intro' && (
            <div className="space-y-5">
              <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-sm text-blue-900">
                <strong>What you&apos;ll do:</strong> Tap the large blue circle as fast as possible — but try to keep an
                even rhythm. The test runs for 15 seconds. Use one finger only.
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Which hand are you using?</label>
                <div className="flex gap-2">
                  {(['left','right'] as Hand[]).map(h => (
                    <button key={h} onClick={() => setHand(h)}
                      className={`flex-1 py-3 rounded-xl text-sm font-medium border-2 transition-colors
                        ${hand === h ? 'border-blue-700 bg-blue-50 text-blue-900' : 'border-gray-200 text-gray-700'}`}>
                      {h === 'left' ? 'Left hand' : 'Right hand'}
                    </button>
                  ))}
                </div>
              </div>
              <button onClick={start}
                className="w-full bg-blue-800 hover:bg-blue-700 text-white font-semibold py-3.5 rounded-xl">
                Start Tapping
              </button>
            </div>
          )}

          {phase === 'running' && (
            <div className="space-y-6 text-center">
              <div className="flex justify-between items-baseline">
                <span className="text-3xl font-bold text-gray-900">{tapCount}</span>
                <span className="text-sm text-gray-500">{Math.max(0, (DURATION_MS - elapsed) / 1000).toFixed(1)}s left</span>
              </div>
              <button
                onClick={handleTap}
                onTouchStart={(e) => { e.preventDefault(); handleTap(); }}
                className="w-64 h-64 mx-auto bg-blue-700 hover:bg-blue-600 active:bg-blue-800 active:scale-95 transition-transform rounded-full flex items-center justify-center text-white font-bold text-3xl select-none"
                style={{ touchAction: 'manipulation' }}
              >
                TAP
              </button>
            </div>
          )}

          {phase === 'done' && result && (
            <div className="space-y-5">
              <TapResultsView result={result} />
              {submitting && <p className="text-xs text-center text-gray-500">Saving to your medical record…</p>}
              <button onClick={reset} className="w-full bg-gray-100 hover:bg-gray-200 text-gray-800 py-3 rounded-xl">
                Run another test
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function TapResultsView({ result }: { result: TapResult }) {
  const tone = result.overall_score >= 70 ? 'green'
             : result.overall_score >= 50 ? 'amber' : 'red';
  const colors = {
    green: 'bg-green-50  border-green-200  text-green-800',
    amber: 'bg-amber-50  border-amber-200  text-amber-800',
    red:   'bg-red-50    border-red-200    text-red-800',
  }[tone];

  return (
    <>
      <div className={`rounded-xl p-5 border ${colors}`}>
        <div className="flex items-center justify-between mb-1">
          <span className="text-sm font-medium">Finger tap composite</span>
          <CheckCircle2 className="w-5 h-5" />
        </div>
        <div className="text-4xl font-bold">{result.overall_score}<span className="text-base font-medium opacity-60"> / 100</span></div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Metric label="Total taps"      value={result.tap_count.toString()}        healthy="≥ 60 in 15 s" />
        <Metric label="Mean interval"   value={`${result.mean_iti_ms} ms`}          healthy="200–300 ms" />
        <Metric label="Rhythm CV"       value={result.iti_cv.toFixed(3)}            healthy="< 0.20" />
        <Metric label="Fatigue"         value={`${(result.fatigue_index * 100).toFixed(1)}%`} healthy="|fat| < 10%" />
      </div>

      <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg p-3">
        Screening test only. A physical button + accelerometer offers more sensitive data; the touch-screen
        version is suitable for trend tracking but not for diagnosis.
      </p>
    </>
  );
}

function Metric({ label, value, healthy }: { label: string; value: string; healthy: string }) {
  return (
    <div className="bg-gray-50 rounded-xl p-3">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="text-lg font-semibold text-gray-900">{value}</div>
      <div className="text-[10px] text-gray-400">healthy: {healthy}</div>
    </div>
  );
}

function mean(arr: number[]) { return arr.length ? arr.reduce((a,b)=>a+b,0)/arr.length : 0; }
function round1(x: number) { return Math.round(x * 10) / 10; }
function round3(x: number) { return Math.round(x * 1000) / 1000; }
