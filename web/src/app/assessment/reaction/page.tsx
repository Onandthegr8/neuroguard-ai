'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, Zap, CheckCircle2 } from 'lucide-react';
import { submitAssessment } from '@/lib/api/assessments';

type Phase = 'intro' | 'waiting' | 'go' | 'too_early' | 'between_trials' | 'done';

const TRIALS = 6;                  // 1 practice + 5 scored
const PRACTICE_TRIALS = 1;         // doesn't count toward score
const MIN_WAIT_MS = 1500;
const MAX_WAIT_MS = 4000;

interface ReactionResult {
  mean_rt_ms:    number;   // mean of accepted trials (outliers rejected)
  median_rt_ms:  number;   // median, more robust to one bad trial
  std_rt_ms:     number;
  min_rt_ms:     number;
  max_rt_ms:     number;
  errors:        number;
  trials:        number;   // total scored trials (after practice + outlier rejection)
  outliers:      number;
  trial_rts_ms:  number[]; // ALL scored trial RTs (incl. outliers)
  overall_score: number;
}

export default function ReactionPage() {
  const [phase,  setPhase]  = useState<Phase>('intro');
  const [trial,  setTrial]  = useState(0);          // 0-indexed
  const [errors, setErrors] = useState(0);
  const [rts,    setRts]    = useState<number[]>([]);
  const [lastRT, setLastRT] = useState<number | null>(null);
  const [result, setResult] = useState<ReactionResult | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const goTimeRef = useRef<number>(0);
  const timerRef  = useRef<number | null>(null);

  function startTrial() {
    setLastRT(null);
    setPhase('waiting');
    const wait = MIN_WAIT_MS + Math.random() * (MAX_WAIT_MS - MIN_WAIT_MS);
    timerRef.current = window.setTimeout(() => {
      setPhase('go');
      // Record the *actual* paint time, not the setState time.
      // Two rAFs: the first lands AFTER React commits the new style; the second
      // lands AFTER the browser has rendered & flipped the framebuffer. This is
      // when the user can first see the green colour.
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          goTimeRef.current = performance.now();
        });
      });
    }, wait);
  }

  function handleClick(e?: React.PointerEvent | React.MouseEvent) {
    // Use the actual input event time when available — closer to the user's true
    // click moment than performance.now() at handler-execution time.
    const clickTime = (e && 'timeStamp' in e && typeof e.timeStamp === 'number'
                       && e.timeStamp > 0)
                      ? e.timeStamp
                      : performance.now();

    if (phase === 'waiting') {
      // Pressed too early
      if (timerRef.current) clearTimeout(timerRef.current);
      setErrors(err => err + 1);
      setPhase('too_early');
      return;
    }
    if (phase === 'go') {
      // Guard against the rAF callback not having fired yet (very fast click)
      if (goTimeRef.current === 0) return;
      const rt = clickTime - goTimeRef.current;
      if (rt <= 0 || rt > 5000) return; // sanity bound

      setLastRT(rt);
      const newRTs = [...rts, rt];
      setRts(newRTs);
      const nextTrial = trial + 1;
      setTrial(nextTrial);

      // Reset goTimeRef so the guard catches any double-click during between_trials
      goTimeRef.current = 0;

      if (nextTrial < TRIALS) {
        setPhase('between_trials');
        timerRef.current = window.setTimeout(startTrial, 1200);
      } else {
        finish(newRTs);
      }
      return;
    }
    if (phase === 'too_early') {
      setPhase('between_trials');
      timerRef.current = window.setTimeout(startTrial, 800);
    }
  }

  async function finish(allRTs: number[]) {
    // 1. Drop practice trial(s) from the score
    const scoredRTs = allRTs.slice(PRACTICE_TRIALS);

    // 2. Reject outliers: drop any trial > 2σ from the median.
    //    Robust to a single blink / distraction blip.
    const med  = median(scoredRTs);
    const mad  = median(scoredRTs.map(r => Math.abs(r - med))) || 1; // median abs deviation
    const accepted = scoredRTs.filter(r => Math.abs(r - med) <= 3 * mad);
    const outliers = scoredRTs.length - accepted.length;
    const pool     = accepted.length >= 3 ? accepted : scoredRTs;

    const m  = mean(pool);
    const md = median(pool);
    const s  = std(pool, m);
    const mn = Math.min(...pool);
    const mx = Math.max(...pool);

    // Browser-calibrated scoring (median, not mean — single bad trial shouldn't dominate)
    //   ≤ 300 ms = 100 pts          ≥ 800 ms = 0 pts
    const speedScore = Math.max(0, Math.min(100, 100 - Math.max(0, md - 300) * 0.25));
    const consistencyScore = Math.max(0, 100 - Math.max(0, s - 50) * 1.5);
    const errorPenalty = Math.min(20, errors * 8);
    const overall = round1(Math.max(0, 0.60 * speedScore + 0.40 * consistencyScore - errorPenalty));

    const r: ReactionResult = {
      mean_rt_ms:    round1(m),
      median_rt_ms:  round1(md),
      std_rt_ms:     round1(s),
      min_rt_ms:     round1(mn),
      max_rt_ms:     round1(mx),
      errors,
      trials:        accepted.length,
      outliers,
      trial_rts_ms:  scoredRTs.map(round1),
      overall_score: overall,
    };
    setResult(r);

    setSubmitting(true);
    try {
      await submitAssessment({
        assessment_type: 'reaction_time',
        overall_score:   r.overall_score,
        metrics: { ...r },
      });
    } catch {}
    setSubmitting(false);
    setPhase('done');
  }

  function reset() {
    setPhase('intro'); setTrial(0); setErrors(0);
    setRts([]); setResult(null); setLastRT(null);
  }

  useEffect(() => () => {
    if (timerRef.current) clearTimeout(timerRef.current);
  }, []);

  // ── UI ────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-white p-6">
      <div className="max-w-2xl mx-auto">
        <Link href="/assessment" className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-blue-700 mb-4">
          <ArrowLeft className="w-4 h-4" /> Back to assessments
        </Link>

        <div className="bg-white rounded-2xl shadow-md p-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 bg-yellow-100 rounded-xl flex items-center justify-center">
              <Zap className="w-5 h-5 text-yellow-700" />
            </div>
            <h1 className="text-2xl font-bold text-gray-900">Reaction Time Test</h1>
          </div>
          <p className="text-sm text-gray-500 mb-6">
            Simple visual reaction time. 1 practice trial + {TRIALS - PRACTICE_TRIALS} scored trials.
            Bradykinesia (slow movement) is a core Parkinson&apos;s sign.
          </p>

          {phase === 'intro' && (
            <div className="space-y-5">
              <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-sm text-blue-900 space-y-2">
                <p><strong>What you&apos;ll do:</strong> Watch the red box. When it turns green, click as fast as you can.</p>
                <ul className="list-disc list-inside text-xs space-y-0.5 opacity-90">
                  <li>The first trial is a practice round — it doesn&apos;t count toward your score.</li>
                  <li>Use a mouse or hardware key if you have one — trackpads add 30–80 ms of noise.</li>
                  <li>Pre-clicking before green counts as an error (penalised, but capped).</li>
                </ul>
              </div>
              <button onClick={startTrial}
                className="w-full bg-blue-800 hover:bg-blue-700 text-white font-semibold py-3.5 rounded-xl">
                Start ({TRIALS - PRACTICE_TRIALS} scored trials)
              </button>
            </div>
          )}

          {(phase === 'waiting' || phase === 'go' || phase === 'too_early' || phase === 'between_trials') && (
            <div className="space-y-4">
              <div className="flex justify-between items-baseline text-sm">
                <span className="text-gray-500">
                  {trial < PRACTICE_TRIALS
                    ? <>Practice trial · doesn&apos;t count</>
                    : <>Trial {Math.min(trial + 1 - PRACTICE_TRIALS, TRIALS - PRACTICE_TRIALS)} of {TRIALS - PRACTICE_TRIALS}</>
                  }
                </span>
                {lastRT !== null && <span className="text-gray-700">Last: <strong>{lastRT.toFixed(0)} ms</strong></span>}
              </div>

              <button
                onClick={(e) => handleClick(e)}
                onTouchStart={(e) => { e.preventDefault(); handleClick(); }}
                className={`w-full h-72 rounded-2xl text-white text-2xl font-bold select-none
                  ${phase === 'go'        ? 'bg-emerald-500 cursor-pointer' : ''}
                  ${phase === 'waiting'   ? 'bg-red-500 cursor-pointer' : ''}
                  ${phase === 'too_early' ? 'bg-orange-500 cursor-pointer transition-colors' : ''}
                  ${phase === 'between_trials' ? 'bg-gray-300 cursor-not-allowed transition-colors' : ''}`}
                style={{ touchAction: 'manipulation' }}
              >
                {/* No `transition-colors` on the GO state — the red->green flip MUST be
                    instant, otherwise the 150ms CSS transition inflates measured RT.
                    Also no text inside the GO state — reading "CLICK!" adds ~150ms. */}
                {phase === 'waiting'        && <span>Wait for green…</span>}
                {phase === 'go'             && null}
                {phase === 'too_early'      && <span>Too early — tap to continue</span>}
                {phase === 'between_trials' && <span>…</span>}
              </button>

              <div className="flex gap-1 justify-center pt-1">
                {[...Array(TRIALS)].map((_, i) => (
                  <span key={i} className={`w-2 h-2 rounded-full
                    ${i < trial ? 'bg-emerald-500' : i === trial ? 'bg-blue-300' : 'bg-gray-200'}
                    ${i < PRACTICE_TRIALS ? 'opacity-50' : ''}
                  `} title={i < PRACTICE_TRIALS ? 'Practice trial' : 'Scored trial'} />
                ))}
              </div>
              {errors > 0 && (
                <p className="text-center text-xs text-orange-700">Early presses so far: {errors}</p>
              )}
            </div>
          )}

          {phase === 'done' && result && (
            <div className="space-y-5">
              <ReactionResultsView result={result} />
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

function ReactionResultsView({ result }: { result: ReactionResult }) {
  const tone = result.overall_score >= 70 ? 'green'
             : result.overall_score >= 50 ? 'amber' : 'red';
  const colors = {
    green: 'bg-green-50 border-green-200 text-green-800',
    amber: 'bg-amber-50 border-amber-200 text-amber-800',
    red:   'bg-red-50 border-red-200 text-red-800',
  }[tone];

  return (
    <>
      <div className={`rounded-xl p-5 border ${colors}`}>
        <div className="flex items-center justify-between mb-1">
          <span className="text-sm font-medium">Reaction time composite</span>
          <CheckCircle2 className="w-5 h-5" />
        </div>
        <div className="text-4xl font-bold">{result.overall_score}<span className="text-base font-medium opacity-60"> / 100</span></div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Metric label="Median RT"     value={`${result.median_rt_ms} ms`} healthy="300–450 ms (browser)"
                hint="primary score input" />
        <Metric label="Mean RT"       value={`${result.mean_rt_ms} ms`}    healthy="300–450 ms (browser)" />
        <Metric label="Std RT"        value={`${result.std_rt_ms} ms`}     healthy="< 80 ms" />
        <Metric label="Best RT"       value={`${result.min_rt_ms} ms`}     healthy="280–400 ms (browser)" />
        <Metric label="Early presses" value={result.errors.toString()}      healthy="0–1" />
        <Metric label="Outliers dropped" value={result.outliers.toString()} healthy="0–1" />
      </div>

      <div className="bg-gray-50 rounded-xl p-3">
        <div className="text-xs text-gray-500 mb-2 flex justify-between">
          <span>Scored trial reaction times</span>
          <span className="text-gray-400">practice trial excluded</span>
        </div>
        <div className="flex gap-2">
          {result.trial_rts_ms.map((rt, i) => {
            const med = result.median_rt_ms;
            // visually mark outliers (those > 3·MAD from the median)
            const isOutlier = Math.abs(rt - med) > Math.max(60, med * 0.4);
            return (
              <div key={i} className={`flex-1 text-center ${isOutlier ? 'opacity-50' : ''}`}>
                <div className="text-sm font-semibold text-gray-900">{Math.round(rt)}</div>
                <div className="text-[10px] text-gray-400">#{i + 1}{isOutlier && ' (dropped)'}</div>
              </div>
            );
          })}
        </div>
      </div>

      <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg p-3">
        <strong>Screening test only — not a diagnosis.</strong> The median is used (not the mean) to
        ignore one-off slips. Browser + display + trackpad latency adds <strong>~50–150 ms</strong>;
        the healthy ranges shown are already browser-adjusted. Track trends on the <em>same device</em>
        rather than comparing absolute scores across devices.
      </p>
    </>
  );
}

function Metric({ label, value, healthy, hint }: { label: string; value: string; healthy: string; hint?: string }) {
  return (
    <div className="bg-gray-50 rounded-xl p-3">
      <div className="text-xs text-gray-500 flex items-center justify-between">
        <span>{label}</span>
        {hint && <span className="text-[10px] text-blue-600">★ {hint}</span>}
      </div>
      <div className="text-lg font-semibold text-gray-900">{value}</div>
      <div className="text-[10px] text-gray-400">healthy: {healthy}</div>
    </div>
  );
}

function mean(arr: number[]) { return arr.length ? arr.reduce((a,b)=>a+b,0)/arr.length : 0; }
function median(arr: number[]) {
  if (!arr.length) return 0;
  const s = [...arr].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m-1] + s[m]) / 2;
}
function std(arr: number[], m: number) {
  if (arr.length < 2) return 0;
  return Math.sqrt(arr.reduce((s,x)=>s+(x-m)**2,0)/arr.length);
}
function round1(x: number) { return Math.round(x * 10) / 10; }
