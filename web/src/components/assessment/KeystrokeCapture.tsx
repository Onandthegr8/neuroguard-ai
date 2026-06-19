'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { ResultsPanel } from './ResultsPanel';
import { analyzeKeystrokes, type KeyEvent, type KeystrokeFeatures } from '@/lib/keystroke/analyzer';
import { Keyboard, CheckCircle, RotateCcw } from 'lucide-react';

// ── Target passages ───────────────────────────────────────────────────────────
const PASSAGES = [
  {
    id: 'standard',
    label: 'Standard passage',
    text: 'The early detection of changes in movement can make a meaningful difference in health outcomes. Please type this passage at your normal, comfortable speed without rushing. Accuracy matters more than pace.',
  },
  {
    id: 'sentences',
    label: 'Short sentences',
    text: 'Good morning. Today I will type a few sentences at my usual speed. I enjoy reading books and taking walks in the park. The weather outside is calm and pleasant.',
  },
  {
    id: 'pangram',
    label: 'Pangram challenge',
    text: 'The quick brown fox jumps over the lazy dog. Pack my box with five dozen liquor jugs. How vexingly quick daft zebras jump over the sleeping fox near the river bank.',
  },
];

type Phase = 'intro' | 'typing' | 'done';

// ── Live stats bar ─────────────────────────────────────────────────────────────
function LiveStats({ wpm, keystrokes, corrections }: {
  wpm: number; keystrokes: number; corrections: number;
}) {
  return (
    <div className="flex gap-6 text-sm">
      <div className="text-center">
        <p className="text-xl font-bold text-blue-800">{wpm}</p>
        <p className="text-xs text-gray-500">WPM</p>
      </div>
      <div className="text-center">
        <p className="text-xl font-bold text-gray-700">{keystrokes}</p>
        <p className="text-xs text-gray-500">Keystrokes</p>
      </div>
      <div className="text-center">
        <p className="text-xl font-bold text-amber-600">{corrections}</p>
        <p className="text-xs text-gray-500">Corrections</p>
      </div>
    </div>
  );
}

// ── Target text renderer ───────────────────────────────────────────────────────
function TargetText({ target, typed }: { target: string; typed: string }) {
  return (
    <div className="font-mono text-base leading-relaxed select-none whitespace-pre-wrap break-words">
      {target.split('').map((ch, i) => {
        const typedCh = typed[i];
        let cls = 'text-gray-400';
        if (typedCh !== undefined) {
          cls = typedCh === ch ? 'text-gray-900' : 'text-red-600 bg-red-50';
        }
        if (i === typed.length) cls += ' border-b-2 border-blue-600';
        return (
          <span key={i} className={cls}>
            {ch}
          </span>
        );
      })}
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────
export function KeystrokeCapture() {
  const [phase, setPhase]             = useState<Phase>('intro');
  const [passageIdx, setPassageIdx]   = useState(0);
  const [typedText, setTypedText]     = useState('');
  const [features, setFeatures]       = useState<KeystrokeFeatures | null>(null);
  const [liveWpm, setLiveWpm]         = useState(0);

  const keyEventsRef     = useRef<KeyEvent[]>([]);
  const pendingRef       = useRef<Map<string, number>>(new Map());  // code → downAt
  const backspaceRef     = useRef(0);
  const sessionStartRef  = useRef<number>(0);
  const textareaRef      = useRef<HTMLTextAreaElement>(null);
  const wpmTimerRef      = useRef<ReturnType<typeof setInterval> | null>(null);

  const passage = PASSAGES[passageIdx];
  const progress = Math.min(1, typedText.length / passage.text.length);

  // ── Start session ────────────────────────────────────────────────────────────
  const startSession = useCallback(() => {
    keyEventsRef.current    = [];
    pendingRef.current      = new Map();
    backspaceRef.current    = 0;
    setTypedText('');
    setLiveWpm(0);
    sessionStartRef.current = 0;
    setPhase('typing');
  }, []);

  // ── Focus textarea when phase becomes 'typing' ────────────────────────────
  useEffect(() => {
    if (phase === 'typing') {
      setTimeout(() => textareaRef.current?.focus(), 50);
    }
  }, [phase]);

  // ── WPM live update ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (phase !== 'typing') {
      if (wpmTimerRef.current) clearInterval(wpmTimerRef.current);
      return;
    }
    wpmTimerRef.current = setInterval(() => {
      if (!sessionStartRef.current) return;
      const elapsed = (performance.now() - sessionStartRef.current) / 60000;
      const words   = typedText.trim().split(/\s+/).filter(Boolean).length;
      setLiveWpm(Math.round(words / Math.max(0.01, elapsed)));
    }, 500);
    return () => { if (wpmTimerRef.current) clearInterval(wpmTimerRef.current); };
  }, [phase, typedText]);

  // ── Keystroke event handlers ─────────────────────────────────────────────────
  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Record session start on first keypress
    if (!sessionStartRef.current) sessionStartRef.current = performance.now();

    if (e.key === 'Backspace') backspaceRef.current++;

    // Don't record modifier-only or non-character keys (except backspace for stats)
    if (e.ctrlKey || e.altKey || e.metaKey) return;

    pendingRef.current.set(e.code, performance.now());
  }, []);

  const handleKeyUp = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    const downAt = pendingRef.current.get(e.code);
    if (downAt === undefined) return;
    pendingRef.current.delete(e.code);
    keyEventsRef.current.push({ code: e.code, downAt, upAt: performance.now() });
  }, []);

  const handleChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    // Cap at target length to prevent runaway typing
    if (value.length <= passage.text.length + 5) {
      setTypedText(value);
    }
  }, [passage.text.length]);

  // ── Finish & analyze ─────────────────────────────────────────────────────────
  const finishSession = useCallback(() => {
    const duration = sessionStartRef.current
      ? performance.now() - sessionStartRef.current
      : 1000;
    const words = typedText.trim().split(/\s+/).filter(Boolean).length;
    const result = analyzeKeystrokes(
      keyEventsRef.current,
      backspaceRef.current,
      duration,
      words
    );
    setFeatures(result);
    setPhase('done');
  }, [typedText]);

  const handleRetry = useCallback(() => {
    setFeatures(null);
    setPhase('intro');
  }, []);

  // ── Render: Intro ────────────────────────────────────────────────────────────
  if (phase === 'intro') {
    return (
      <div className="space-y-6">
        <div className="card p-8 text-center space-y-4">
          <div className="w-16 h-16 bg-blue-100 rounded-2xl flex items-center justify-center mx-auto">
            <Keyboard className="w-8 h-8 text-blue-800" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-gray-900">Typing Assessment</h2>
            <p className="text-gray-500 text-sm mt-1 max-w-lg mx-auto">
              Type a short passage at your <span className="font-medium">normal, comfortable speed</span>.
              We capture only timing data — not the content you type.
            </p>
          </div>

          {/* Passage selector */}
          <div className="flex flex-wrap justify-center gap-2 pt-2">
            {PASSAGES.map((p, i) => (
              <button
                key={p.id}
                onClick={() => setPassageIdx(i)}
                className={`px-4 py-2 rounded-xl text-sm font-medium border transition-colors ${
                  passageIdx === i
                    ? 'bg-blue-800 text-white border-blue-800'
                    : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>

          {/* Passage preview */}
          <div className="bg-gray-50 rounded-xl p-4 text-left max-w-xl mx-auto">
            <p className="text-sm text-gray-600 leading-relaxed font-mono">{passage.text}</p>
          </div>

          {/* Privacy notice */}
          <div className="bg-blue-50 border border-blue-100 rounded-xl p-3 text-xs text-blue-700 max-w-md mx-auto text-left">
            <span className="font-semibold">🔒 Privacy:</span> Only keystroke timing metadata
            (how long you hold each key, time between keystrokes) is recorded.
            The actual characters you type are not stored.
          </div>

          <button
            onClick={startSession}
            className="px-8 py-3 bg-blue-800 text-white rounded-xl font-semibold hover:bg-blue-700 transition-colors text-sm"
          >
            Start Assessment
          </button>
        </div>
      </div>
    );
  }

  // ── Render: Typing ───────────────────────────────────────────────────────────
  if (phase === 'typing') {
    const isComplete = typedText.length >= passage.text.length;

    return (
      <div className="space-y-4">
        {/* Live stats */}
        <div className="card p-4 flex items-center justify-between flex-wrap gap-4">
          <LiveStats
            wpm={liveWpm}
            keystrokes={keyEventsRef.current.length}
            corrections={backspaceRef.current}
          />
          {/* Progress bar */}
          <div className="flex-1 min-w-[180px]">
            <div className="flex justify-between text-xs text-gray-400 mb-1">
              <span>Progress</span>
              <span>{Math.round(progress * 100)}%</span>
            </div>
            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-600 rounded-full transition-all duration-100"
                style={{ width: `${progress * 100}%` }}
              />
            </div>
          </div>
        </div>

        {/* Target text */}
        <div className="card p-6 space-y-4">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Type the passage below</p>
          <div className="bg-gray-50 rounded-xl p-4">
            <TargetText target={passage.text} typed={typedText} />
          </div>

          {/* Hidden textarea captures actual input */}
          <textarea
            ref={textareaRef}
            value={typedText}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            onKeyUp={handleKeyUp}
            rows={4}
            placeholder="Start typing here…"
            className="w-full px-4 py-3 border-2 border-blue-200 focus:border-blue-600 rounded-xl font-mono text-sm text-gray-800 resize-none focus:outline-none transition-colors"
            autoComplete="off"
            autoCorrect="off"
            autoCapitalize="off"
            spellCheck={false}
          />

          <div className="flex items-center justify-between">
            <button
              onClick={() => { setPhase('intro'); setTypedText(''); }}
              className="flex items-center gap-2 text-sm text-gray-400 hover:text-gray-600 transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" /> Cancel
            </button>

            <button
              onClick={finishSession}
              disabled={keyEventsRef.current.length < 10}
              className={`flex items-center gap-2 px-6 py-2.5 rounded-xl font-semibold text-sm transition-colors ${
                isComplete
                  ? 'bg-green-600 text-white hover:bg-green-500'
                  : keyEventsRef.current.length >= 10
                  ? 'bg-blue-800 text-white hover:bg-blue-700'
                  : 'bg-gray-100 text-gray-400 cursor-not-allowed'
              }`}
            >
              <CheckCircle className="w-4 h-4" />
              {isComplete ? 'View Results' : 'Finish Early'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── Render: Done ─────────────────────────────────────────────────────────────
  return features ? (
    <ResultsPanel features={features} onRetry={handleRetry} />
  ) : null;
}
