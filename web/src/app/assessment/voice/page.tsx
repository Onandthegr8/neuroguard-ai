'use client';

import { useRef, useState } from 'react';
import Link from 'next/link';
import { Mic, MicOff, ArrowLeft, CheckCircle2 } from 'lucide-react';
import { analyzeVoice, VoiceResult } from '@/lib/assessments/voice_analyzer';
import { submitAssessment } from '@/lib/api/assessments';

type Phase = 'intro' | 'recording' | 'analyzing' | 'done' | 'error';

const TARGET_DURATION_S = 6;
const TARGET_VOWEL      = 'ahhhh';

export default function VoiceAssessmentPage() {
  const [phase,    setPhase]    = useState<Phase>('intro');
  const [progress, setProgress] = useState(0);
  const [result,   setResult]   = useState<VoiceResult | null>(null);
  const [error,    setError]    = useState('');
  const [submitting, setSubmitting] = useState(false);

  const streamRef    = useRef<MediaStream | null>(null);
  const audioCtxRef  = useRef<AudioContext | null>(null);
  const samplesRef   = useRef<Float32Array[]>([]);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const timerRef     = useRef<number | null>(null);

  async function startRecording() {
    setError('');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
      });
      streamRef.current = stream;

      const AudioCtx = (window.AudioContext || (window as any).webkitAudioContext);
      const ctx      = new AudioCtx();
      audioCtxRef.current = ctx;

      const source    = ctx.createMediaStreamSource(stream);
      const processor = ctx.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      samplesRef.current = [];
      processor.onaudioprocess = (e) => {
        const data = e.inputBuffer.getChannelData(0);
        samplesRef.current.push(new Float32Array(data));
      };

      source.connect(processor);
      processor.connect(ctx.destination);

      setPhase('recording');
      const startTime = Date.now();
      timerRef.current = window.setInterval(() => {
        const elapsed = (Date.now() - startTime) / 1000;
        setProgress(Math.min(elapsed / TARGET_DURATION_S, 1));
        if (elapsed >= TARGET_DURATION_S) finishRecording();
      }, 100);
    } catch (e: any) {
      setError(e.message ?? 'Microphone permission denied');
      setPhase('error');
    }
  }

  function finishRecording() {
    if (timerRef.current) clearInterval(timerRef.current);
    streamRef.current?.getTracks().forEach(t => t.stop());
    processorRef.current?.disconnect();

    const sampleRate = audioCtxRef.current?.sampleRate ?? 44100;
    const chunks     = samplesRef.current;
    const totalLen   = chunks.reduce((s, c) => s + c.length, 0);
    const merged     = new Float32Array(totalLen);
    let offset = 0;
    for (const c of chunks) { merged.set(c, offset); offset += c.length; }

    audioCtxRef.current?.close();
    setPhase('analyzing');

    setTimeout(async () => {
      const analysis = analyzeVoice(merged, sampleRate);
      setResult(analysis);
      setSubmitting(true);
      try {
        await submitAssessment({
          assessment_type: 'voice_tremor',
          overall_score:   analysis.overall_score,
          metrics: {
            jitter_pct:   analysis.jitter_pct,
            shimmer_pct:  analysis.shimmer_pct,
            f0_mean_hz:   analysis.f0_mean_hz,
            f0_std_hz:    analysis.f0_std_hz,
            voice_breaks: analysis.voice_breaks,
            hnr_db:       analysis.hnr_db,
            duration_s:   analysis.duration_s,
          },
        });
      } catch (_) { /* still show result on failure */ }
      setSubmitting(false);
      setPhase('done');
    }, 300);
  }

  function reset() {
    setPhase('intro');
    setProgress(0);
    setResult(null);
    setError('');
  }

  // ── UI ──────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-white p-6">
      <div className="max-w-2xl mx-auto">
        <Link href="/assessment" className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-blue-700 mb-4">
          <ArrowLeft className="w-4 h-4" /> Back to assessments
        </Link>

        <div className="bg-white rounded-2xl shadow-md p-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 bg-purple-100 rounded-xl flex items-center justify-center">
              <Mic className="w-5 h-5 text-purple-700" />
            </div>
            <h1 className="text-2xl font-bold text-gray-900">Voice Tremor Test</h1>
          </div>
          <p className="text-sm text-gray-500 mb-6">
            Sustained vowel phonation. Measures jitter, shimmer, and harmonic-to-noise ratio.
          </p>

          {phase === 'intro' && (
            <div className="space-y-5">
              <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-sm text-blue-900">
                <strong>What you&apos;ll do:</strong> Take a deep breath and say a steady &ldquo;<em>{TARGET_VOWEL}</em>&rdquo;
                at a comfortable pitch for {TARGET_DURATION_S} seconds. Try to hold the same volume and pitch.
              </div>
              <ul className="text-sm text-gray-700 space-y-1 list-disc list-inside">
                <li>Sit upright in a quiet room</li>
                <li>Hold the microphone about 15 cm from your mouth</li>
                <li>Don&apos;t whisper or shout — speak at conversational volume</li>
              </ul>
              <button
                onClick={startRecording}
                className="w-full bg-blue-800 hover:bg-blue-700 text-white font-semibold py-3.5 rounded-xl flex items-center justify-center gap-2"
              >
                <Mic className="w-5 h-5" /> Start Recording
              </button>
            </div>
          )}

          {phase === 'recording' && (
            <div className="text-center py-10 space-y-6">
              <div className="relative w-40 h-40 mx-auto">
                <svg className="w-40 h-40 -rotate-90">
                  <circle cx="80" cy="80" r="70" stroke="#e5e7eb" strokeWidth="10" fill="none" />
                  <circle
                    cx="80" cy="80" r="70" stroke="#a855f7" strokeWidth="10" fill="none"
                    strokeDasharray={2 * Math.PI * 70}
                    strokeDashoffset={2 * Math.PI * 70 * (1 - progress)}
                    strokeLinecap="round"
                  />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center">
                  <Mic className="w-16 h-16 text-purple-600 animate-pulse" />
                </div>
              </div>
              <p className="text-3xl font-bold text-gray-900">
                {Math.max(0, TARGET_DURATION_S - progress * TARGET_DURATION_S).toFixed(1)}s
              </p>
              <p className="text-sm text-gray-500">Keep saying &ldquo;<em>{TARGET_VOWEL}</em>&rdquo;…</p>
              <button onClick={finishRecording} className="text-sm text-red-600 hover:underline">
                <MicOff className="inline w-4 h-4 mr-1" /> Stop early
              </button>
            </div>
          )}

          {phase === 'analyzing' && (
            <div className="text-center py-12">
              <div className="inline-block w-12 h-12 border-4 border-purple-200 border-t-purple-700 rounded-full animate-spin mb-4" />
              <p className="text-gray-700">Analysing voice samples…</p>
            </div>
          )}

          {phase === 'done' && result && (
            <div className="space-y-5">
              <ResultsView result={result} />
              {submitting && <p className="text-xs text-center text-gray-500">Saving to your medical record…</p>}
              <button onClick={reset} className="w-full bg-gray-100 hover:bg-gray-200 text-gray-800 py-3 rounded-xl">
                Run another test
              </button>
            </div>
          )}

          {phase === 'error' && <ErrorPanel error={error} onRetry={reset} />}
        </div>
      </div>
    </div>
  );
}

function ResultsView({ result }: { result: VoiceResult }) {
  const tone = result.overall_score >= 70 ? 'green'
             : result.overall_score >= 50 ? 'amber' : 'red';
  const colors = {
    green: 'bg-green-50 border-green-200 text-green-800',
    amber: 'bg-amber-50 border-amber-200 text-amber-800',
    red:   'bg-red-50   border-red-200   text-red-800',
  }[tone];

  return (
    <div className="space-y-4">
      <div className={`rounded-xl p-5 border ${colors}`}>
        <div className="flex items-center justify-between mb-1">
          <span className="text-sm font-medium">Voice tremor composite</span>
          <CheckCircle2 className="w-5 h-5" />
        </div>
        <div className="text-4xl font-bold">{result.overall_score.toFixed(1)}<span className="text-base font-medium opacity-60"> / 100</span></div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Metric label="Jitter"       value={`${result.jitter_pct}%`}    healthy="< 1.04%" />
        <Metric label="Shimmer"      value={`${result.shimmer_pct}%`}   healthy="< 3.81%" />
        <Metric label="Mean F0"      value={`${result.f0_mean_hz} Hz`}  healthy="100–250 Hz" />
        <Metric label="F0 std"       value={`${result.f0_std_hz} Hz`}   healthy="< 10 Hz" />
        <Metric label="HNR"          value={`${result.hnr_db} dB`}      healthy="> 20 dB" />
        <Metric label="Voice breaks" value={result.voice_breaks.toString()} healthy="0" />
      </div>

      <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg p-3">
        Screening test only — not a clinical diagnosis. Browser-based voice analysis is approximate;
        clinical-grade systems (e.g. Praat) yield more precise measurements.
      </p>
    </div>
  );
}

function ErrorPanel({ error, onRetry }: { error: string; onRetry: () => void }) {
  const lower = error.toLowerCase();
  const isSystemBlock = lower.includes('system') || lower.includes('not allowed') || lower.includes('not-allowed');
  const isNoDevice    = lower.includes('not found') || lower.includes('notfounderror') || lower.includes('no device');
  const isInUse       = lower.includes('in use') || lower.includes('busy') || lower.includes('notreadable');

  return (
    <div className="bg-red-50 border border-red-200 rounded-xl p-5 text-sm">
      <p className="font-semibold text-red-900 mb-2">Microphone unavailable</p>
      <p className="text-red-800 mb-3">Browser says: <em>{error}</em></p>

      {isSystemBlock && (
        <div className="bg-white border border-red-100 rounded-lg p-3 space-y-2 text-red-900">
          <p className="font-semibold">This is a Windows-level block, not a browser one.</p>
          <ol className="list-decimal list-inside space-y-1 text-xs">
            <li>Press <kbd className="bg-gray-100 px-1.5 py-0.5 rounded">Win + I</kbd> → <strong>Privacy & security → Microphone</strong></li>
            <li>Turn ON <strong>Microphone access</strong> (top toggle)</li>
            <li>Turn ON <strong>Let apps access your microphone</strong></li>
            <li>Turn ON <strong>Let desktop apps access your microphone</strong></li>
            <li>Close Chrome completely, reopen, and retry</li>
          </ol>
        </div>
      )}

      {isInUse && (
        <div className="bg-white border border-red-100 rounded-lg p-3 text-red-900">
          <p className="font-semibold mb-1">Another app is using the microphone.</p>
          <p className="text-xs">Quit Zoom, Teams, Discord, OBS, or any other voice/video app, then retry.</p>
        </div>
      )}

      {isNoDevice && (
        <div className="bg-white border border-red-100 rounded-lg p-3 text-red-900">
          <p className="font-semibold mb-1">No microphone detected.</p>
          <p className="text-xs">Plug in a mic or check Device Manager — your built-in mic may be disabled.</p>
        </div>
      )}

      <button onClick={onRetry} className="mt-3 px-4 py-2 bg-blue-800 hover:bg-blue-700 text-white text-sm font-medium rounded-lg">
        Try again
      </button>
    </div>
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
