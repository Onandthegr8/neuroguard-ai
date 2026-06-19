'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, Spline, CheckCircle2, RotateCcw } from 'lucide-react';
import { submitAssessment } from '@/lib/api/assessments';

type Phase = 'intro' | 'drawing' | 'done';

interface SpiralResult {
  mean_deviation_px:  number;   // average distance from ideal Archimedean spiral
  peak_deviation_px:  number;
  tremor_freq_hz:     number;   // dominant tremor frequency 4-12Hz band
  drawing_time_ms:    number;
  sample_count:       number;
  overall_score:      number;
}

interface Point { x: number; y: number; t: number; }

// Canvas + ideal spiral parameters
const CANVAS = 360;
const CENTER = CANVAS / 2;
const SPIRAL_TURNS  = 3;
const SPIRAL_MAX_R  = CANVAS / 2 - 30;
const SAMPLE_RATE_HZ = 60;        // points per second (approx)

export default function SpiralPage() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const pointsRef = useRef<Point[]>([]);
  const startTimeRef = useRef<number>(0);

  const [phase,  setPhase]  = useState<Phase>('intro');
  const [drawing, setDrawing] = useState(false);
  const [result, setResult] = useState<SpiralResult | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Draw the guide spiral at mount of drawing phase
  useEffect(() => {
    if (phase !== 'drawing') return;
    const canvas = canvasRef.current; if (!canvas) return;
    const ctx = canvas.getContext('2d')!;
    ctx.clearRect(0, 0, CANVAS, CANVAS);

    // Background grid
    ctx.strokeStyle = '#f3f4f6';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 8; i++) {
      ctx.beginPath();
      ctx.moveTo(i * CANVAS / 8, 0);
      ctx.lineTo(i * CANVAS / 8, CANVAS);
      ctx.moveTo(0, i * CANVAS / 8);
      ctx.lineTo(CANVAS, i * CANVAS / 8);
      ctx.stroke();
    }

    // Reference Archimedean spiral, drawn lightly
    ctx.strokeStyle = '#cbd5e1';
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (let θ = 0; θ <= SPIRAL_TURNS * 2 * Math.PI; θ += 0.05) {
      const r = (SPIRAL_MAX_R * θ) / (SPIRAL_TURNS * 2 * Math.PI);
      const x = CENTER + r * Math.cos(θ);
      const y = CENTER + r * Math.sin(θ);
      θ === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.stroke();
  }, [phase]);

  function start() {
    pointsRef.current = [];
    startTimeRef.current = performance.now();
    setResult(null);
    setPhase('drawing');
  }

  function reset() {
    setPhase('intro');
    setResult(null);
    pointsRef.current = [];
  }

  function getCanvasPos(e: React.PointerEvent): Point {
    const rect = canvasRef.current!.getBoundingClientRect();
    return {
      x: ((e.clientX - rect.left) / rect.width) * CANVAS,
      y: ((e.clientY - rect.top)  / rect.height) * CANVAS,
      t: performance.now() - startTimeRef.current,
    };
  }

  function onPointerDown(e: React.PointerEvent) {
    e.preventDefault();
    setDrawing(true);
    pointsRef.current = [];
    startTimeRef.current = performance.now();
    const p = getCanvasPos(e);
    pointsRef.current.push(p);
  }

  function onPointerMove(e: React.PointerEvent) {
    if (!drawing) return;
    const p = getCanvasPos(e);
    pointsRef.current.push(p);
    const ctx = canvasRef.current!.getContext('2d')!;
    const prev = pointsRef.current[pointsRef.current.length - 2];
    if (prev) {
      ctx.strokeStyle = '#1e40af';
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.moveTo(prev.x, prev.y);
      ctx.lineTo(p.x, p.y);
      ctx.stroke();
    }
  }

  async function onPointerUp() {
    setDrawing(false);
    if (pointsRef.current.length < 50) return;

    const r = analyzeSpiral(pointsRef.current);
    setResult(r);
    setSubmitting(true);
    try {
      await submitAssessment({
        assessment_type: 'spiral_drawing',
        overall_score:   r.overall_score,
        metrics: { ...r },
      });
    } catch {}
    setSubmitting(false);
    setPhase('done');
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
            <div className="w-10 h-10 bg-orange-100 rounded-xl flex items-center justify-center">
              <Spline className="w-5 h-5 text-orange-700" />
            </div>
            <h1 className="text-2xl font-bold text-gray-900">Spiral Drawing Test</h1>
          </div>
          <p className="text-sm text-gray-500 mb-6">
            Trace the spiral as smoothly as you can. Tremor in the 4–12 Hz band is a marker of motor dysfunction.
          </p>

          {phase === 'intro' && (
            <div className="space-y-5">
              <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-sm text-blue-900">
                <strong>What you&apos;ll do:</strong> Trace the grey spiral from the centre outward in one continuous
                stroke. Use a stylus on a tablet for best results — mouse drawing works but is noisier.
              </div>
              <button onClick={start}
                className="w-full bg-blue-800 hover:bg-blue-700 text-white font-semibold py-3.5 rounded-xl">
                Start Drawing
              </button>
            </div>
          )}

          {phase === 'drawing' && (
            <div className="space-y-4">
              <div className="flex justify-center">
                <canvas
                  ref={canvasRef}
                  width={CANVAS} height={CANVAS}
                  onPointerDown={onPointerDown}
                  onPointerMove={onPointerMove}
                  onPointerUp={onPointerUp}
                  onPointerCancel={onPointerUp}
                  className="border-2 border-gray-200 rounded-xl cursor-crosshair touch-none bg-white"
                  style={{ width: CANVAS, height: CANVAS, maxWidth: '100%' }}
                />
              </div>
              <p className="text-xs text-gray-500 text-center">
                Start at the centre. Trace outward following the grey spiral. Release when you reach the edge.
              </p>
              <button onClick={reset}
                className="w-full bg-gray-100 hover:bg-gray-200 text-gray-700 py-2.5 rounded-xl text-sm flex items-center justify-center gap-1">
                <RotateCcw className="w-4 h-4" /> Reset
              </button>
            </div>
          )}

          {phase === 'done' && result && (
            <div className="space-y-5">
              <SpiralResultsView result={result} />
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

function SpiralResultsView({ result }: { result: SpiralResult }) {
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
          <span className="text-sm font-medium">Spiral composite</span>
          <CheckCircle2 className="w-5 h-5" />
        </div>
        <div className="text-4xl font-bold">{result.overall_score}<span className="text-base font-medium opacity-60"> / 100</span></div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Metric label="Mean deviation"  value={`${result.mean_deviation_px.toFixed(1)} px`} healthy="< 8 px" />
        <Metric label="Peak deviation"  value={`${result.peak_deviation_px.toFixed(1)} px`} healthy="< 25 px" />
        <Metric label="Tremor freq"     value={`${result.tremor_freq_hz.toFixed(1)} Hz`}    healthy="< 4 Hz" />
        <Metric label="Drawing time"    value={`${(result.drawing_time_ms / 1000).toFixed(1)} s`} healthy="5–15 s" />
      </div>
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

// ── Analyzer ────────────────────────────────────────────────────────────

function analyzeSpiral(points: Point[]): SpiralResult {
  // 1. Compute deviation from ideal Archimedean spiral
  const deviations: number[] = [];
  for (const p of points) {
    const dx = p.x - CENTER;
    const dy = p.y - CENTER;
    const r  = Math.sqrt(dx*dx + dy*dy);
    const θ  = Math.atan2(dy, dx);

    // Find the closest theoretical r at this angle, considering θ + n*2π
    let bestDev = Infinity;
    for (let n = 0; n <= SPIRAL_TURNS; n++) {
      const totalθ = (θ < 0 ? θ + 2*Math.PI : θ) + n * 2 * Math.PI;
      const idealR = (SPIRAL_MAX_R * totalθ) / (SPIRAL_TURNS * 2 * Math.PI);
      if (idealR > SPIRAL_MAX_R + 10) break;
      bestDev = Math.min(bestDev, Math.abs(r - idealR));
    }
    deviations.push(bestDev);
  }

  const meanDev = deviations.reduce((a,b)=>a+b,0) / deviations.length;
  const peakDev = deviations.reduce((a,b)=>Math.max(a,b), 0);

  // 2. Estimate tremor frequency from radial deviation series
  // Sample points to ~uniform time spacing, take FFT magnitude, find peak in 4-12 Hz
  const tremorFreq = estimateTremorFreq(deviations, SAMPLE_RATE_HZ);

  // 3. Drawing time
  const time = points[points.length - 1].t - points[0].t;

  // 4. Composite score:
  //    - low mean deviation (smooth tracing) — healthy < ~8 px
  //    - low tremor freq                     — healthy < 4 Hz (no PD tremor)
  //    - reasonable drawing time              — healthy 5-15 s
  const devScore   = Math.max(0, 100 - meanDev * 5);
  const tremorScore = tremorFreq < 4 ? 100 : Math.max(0, 100 - (tremorFreq - 4) * 15);
  const timeMs = time;
  const timeScore = (timeMs > 3000 && timeMs < 20000) ? 100
                  : Math.max(0, 100 - Math.abs(timeMs - 10000) / 100);
  const overall = round1(0.55 * devScore + 0.30 * tremorScore + 0.15 * timeScore);

  return {
    mean_deviation_px:  round1(meanDev),
    peak_deviation_px:  round1(peakDev),
    tremor_freq_hz:     round1(tremorFreq),
    drawing_time_ms:    Math.round(timeMs),
    sample_count:       points.length,
    overall_score:      overall,
  };
}

function estimateTremorFreq(series: number[], sampleRate: number): number {
  if (series.length < 32) return 0;
  // Detrend
  const m = series.reduce((a,b)=>a+b,0)/series.length;
  const x = series.map(v => v - m);
  const N = Math.min(x.length, 1024);
  // Naïve DFT magnitude — fine for short series
  let bestFreq = 0;
  let bestMag  = 0;
  for (let k = 1; k < N / 2; k++) {
    const freq = (k * sampleRate) / N;
    if (freq < 1 || freq > 20) continue;
    let re = 0, im = 0;
    for (let n = 0; n < N; n++) {
      const phase = -2 * Math.PI * k * n / N;
      re += x[n] * Math.cos(phase);
      im += x[n] * Math.sin(phase);
    }
    const mag = Math.sqrt(re*re + im*im);
    if (mag > bestMag) { bestMag = mag; bestFreq = freq; }
  }
  return bestFreq;
}

function round1(x: number) { return Math.round(x * 10) / 10; }
