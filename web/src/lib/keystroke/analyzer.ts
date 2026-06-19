/**
 * Keystroke dynamics analyzer.
 * Extracts timing features from raw key events captured in the browser.
 * Only metadata is processed — no actual key characters are retained.
 */

export interface KeyEvent {
  code: string;       // physical key code e.g. "KeyA"
  downAt: number;     // performance.now() at keydown
  upAt: number;       // performance.now() at keyup
}

export interface KeystrokeFeatures {
  /* Raw arrays (for charts) */
  dwell_times_ms:  number[];   // time key was held per keystroke
  iki_times_ms:    number[];   // time between consecutive keydowns

  /* Aggregate stats */
  mean_dwell_ms:        number;
  std_dwell_ms:         number;
  mean_iki_ms:          number;
  std_iki_ms:           number;
  p25_iki_ms:           number;
  p75_iki_ms:           number;

  /* Derived metrics */
  typing_speed_wpm:     number;
  correction_frequency: number;  // backspaces / total keystrokes
  typing_entropy:       number;  // coefficient of variation of IKIs (0–1)
  pause_frequency:      number;  // fraction of IKIs > 500 ms
  rhythm_score:         number;  // 0–100, higher = more rhythmic/consistent
  consistency_score:    number;  // 0–100 overall health-relevant score

  /* Session info */
  total_keystrokes:     number;
  backspace_count:      number;
  session_duration_ms:  number;
}

// ── Math helpers ─────────────────────────────────────────────────────────────

function mean(arr: number[]): number {
  if (!arr.length) return 0;
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}

function std(arr: number[], mu?: number): number {
  if (arr.length < 2) return 0;
  const m = mu ?? mean(arr);
  return Math.sqrt(arr.reduce((s, v) => s + (v - m) ** 2, 0) / (arr.length - 1));
}

function percentile(sorted: number[], p: number): number {
  if (!sorted.length) return 0;
  const idx = (p / 100) * (sorted.length - 1);
  const lo  = Math.floor(idx);
  const hi  = Math.ceil(idx);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo);
}

function entropy(arr: number[], bins = 10): number {
  if (arr.length < 2) return 0;
  const min = Math.min(...arr);
  const max = Math.max(...arr);
  if (max === min) return 0;
  const counts = new Array(bins).fill(0);
  arr.forEach(v => {
    const b = Math.min(bins - 1, Math.floor(((v - min) / (max - min)) * bins));
    counts[b]++;
  });
  const total = arr.length;
  return -counts
    .filter(c => c > 0)
    .reduce((s, c) => s + (c / total) * Math.log2(c / total), 0);
}

// ── Main export ───────────────────────────────────────────────────────────────

export function analyzeKeystrokes(
  events: KeyEvent[],
  backspaceCount: number,
  sessionDurationMs: number,
  wordsTyped: number
): KeystrokeFeatures {
  const dwell = events.map(e => Math.max(0, e.upAt - e.downAt));
  const iki: number[] = [];
  for (let i = 1; i < events.length; i++) {
    iki.push(Math.max(0, events[i].downAt - events[i - 1].downAt));
  }

  const sortedIki  = [...iki].sort((a, b) => a - b);
  const muDwell    = mean(dwell);
  const muIki      = mean(iki);
  const sdIki      = std(iki, muIki);
  const cv         = muIki > 0 ? sdIki / muIki : 0;   // coefficient of variation
  const pauseFreq  = iki.length ? iki.filter(v => v > 500).length / iki.length : 0;
  const rawEntropy = entropy(iki);
  const maxEntropy = Math.log2(10);  // max entropy for 10 bins

  // Rhythm score: low CV = high rhythm. Map CV 0→100, 1+→0
  const rhythmScore = Math.round(Math.max(0, Math.min(100, (1 - Math.min(cv, 1)) * 100)));

  // Consistency score: blend of rhythm, pause frequency, and correction rate
  const correctionRate = events.length > 0 ? backspaceCount / (events.length + backspaceCount) : 0;
  const consistencyScore = Math.round(
    rhythmScore * 0.50 +
    (1 - pauseFreq)   * 100 * 0.25 +
    (1 - Math.min(correctionRate, 0.4) / 0.4) * 100 * 0.25
  );

  return {
    dwell_times_ms:       dwell,
    iki_times_ms:         iki,
    mean_dwell_ms:        Math.round(muDwell),
    std_dwell_ms:         Math.round(std(dwell, muDwell)),
    mean_iki_ms:          Math.round(muIki),
    std_iki_ms:           Math.round(sdIki),
    p25_iki_ms:           Math.round(percentile(sortedIki, 25)),
    p75_iki_ms:           Math.round(percentile(sortedIki, 75)),
    typing_speed_wpm:     parseFloat(
      (wordsTyped / Math.max(1, sessionDurationMs / 60000)).toFixed(1)
    ),
    correction_frequency: parseFloat(correctionRate.toFixed(3)),
    typing_entropy:       parseFloat((rawEntropy / maxEntropy).toFixed(3)),
    pause_frequency:      parseFloat(pauseFreq.toFixed(3)),
    rhythm_score:         rhythmScore,
    consistency_score:    Math.min(100, Math.max(0, consistencyScore)),
    total_keystrokes:     events.length,
    backspace_count:      backspaceCount,
    session_duration_ms:  Math.round(sessionDurationMs),
  };
}
