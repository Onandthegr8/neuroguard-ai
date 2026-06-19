/**
 * Real-time voice biomarker extraction in the browser.
 *
 * Captures microphone audio, computes:
 *   - F0 (fundamental frequency) per frame, then F0 std
 *   - Jitter (period-to-period variation)
 *   - Shimmer (amplitude variation)
 *   - HNR (harmonic-to-noise ratio, rough estimate)
 *   - Voice breaks (gaps where pitch detection fails)
 *
 * Composite score is a function of these vs. published healthy ranges:
 *   Jitter < 1.04%, Shimmer < 3.81%, HNR > 20 dB  (Teixeira 2013)
 *
 * The pitch detector is a naïve autocorrelation method — good enough for a
 * screening test, not clinical Praat-grade. The composite score reflects this
 * uncertainty by smoothing aggressively.
 */

interface VoiceFrame {
  f0:   number;  // Hz, 0 means unvoiced
  rms:  number;  // amplitude
}

export interface VoiceResult {
  jitter_pct:    number;
  shimmer_pct:   number;
  f0_mean_hz:    number;
  f0_std_hz:     number;
  voice_breaks:  number;
  hnr_db:        number;
  overall_score: number;
  duration_s:    number;
}

/**
 * Analyse a captured Float32 audio buffer at a given sample rate.
 * Returns a single VoiceResult covering the whole utterance.
 */
export function analyzeVoice(samples: Float32Array, sampleRate: number): VoiceResult {
  const frameSize = Math.floor(sampleRate * 0.040);   // 40 ms frames
  const hopSize   = Math.floor(sampleRate * 0.020);   // 20 ms hop

  const frames: VoiceFrame[] = [];
  for (let start = 0; start + frameSize < samples.length; start += hopSize) {
    const slice = samples.subarray(start, start + frameSize);
    const rms   = computeRMS(slice);
    const f0    = rms < 0.005 ? 0 : detectF0Autocorr(slice, sampleRate);
    frames.push({ f0, rms });
  }

  const voiced   = frames.filter(f => f.f0 > 50 && f.f0 < 600);
  const voicedF0 = voiced.map(f => f.f0);
  const voicedRMS = voiced.map(f => f.rms);

  if (voiced.length < 10) {
    return {
      jitter_pct: 0, shimmer_pct: 0, f0_mean_hz: 0, f0_std_hz: 0,
      voice_breaks: frames.length - voiced.length, hnr_db: 0,
      overall_score: 0, duration_s: samples.length / sampleRate,
    };
  }

  const f0Mean = mean(voicedF0);
  const f0Std  = std(voicedF0, f0Mean);

  // Jitter = mean(|P_i+1 - P_i|) / mean(P_i), where P_i = 1/F0 (period)
  const periods = voicedF0.map(f => 1 / f);
  const jitterAbs = pairwiseAbsDiff(periods);
  const jitter_pct = (jitterAbs / mean(periods)) * 100;

  // Shimmer = pairwise amplitude variation
  const shimmerAbs = pairwiseAbsDiff(voicedRMS);
  const shimmer_pct = (shimmerAbs / (mean(voicedRMS) + 1e-9)) * 100;

  // HNR rough estimate: voiced vs unvoiced energy ratio
  const totalEnergy = sumSquared(samples);
  const voicedEnergy = voiced.reduce((s, f) => s + f.rms * f.rms, 0);
  const noiseEnergy = Math.max(totalEnergy - voicedEnergy, 1e-9);
  const hnr_db = 10 * Math.log10(voicedEnergy / noiseEnergy);

  // Voice breaks: unvoiced frames during what should be a continuous vowel
  const voiceBreaks = countVoiceBreaks(frames);

  // Composite score — penalise abnormal jitter/shimmer, low HNR.
  const jitter_score  = Math.max(0, 100 - Math.max(0, jitter_pct - 0.5) * 60);  // healthy < ~1%
  const shimmer_score = Math.max(0, 100 - Math.max(0, shimmer_pct - 2.0) * 12); // healthy < ~3.8%
  const hnr_score     = Math.min(100, Math.max(0, (hnr_db - 5) * 6));            // healthy > 20 dB
  const breaks_score  = Math.max(0, 100 - voiceBreaks * 8);
  const overall_score = round1(0.35*jitter_score + 0.30*shimmer_score + 0.25*hnr_score + 0.10*breaks_score);

  return {
    jitter_pct:    round2(jitter_pct),
    shimmer_pct:   round2(shimmer_pct),
    f0_mean_hz:    round1(f0Mean),
    f0_std_hz:     round1(f0Std),
    voice_breaks:  voiceBreaks,
    hnr_db:        round1(hnr_db),
    overall_score,
    duration_s:    round1(samples.length / sampleRate),
  };
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function mean(arr: number[]): number {
  return arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;
}

function std(arr: number[], m: number): number {
  if (arr.length < 2) return 0;
  const v = arr.reduce((s, x) => s + (x - m) ** 2, 0) / arr.length;
  return Math.sqrt(v);
}

function computeRMS(buf: Float32Array): number {
  let s = 0;
  for (let i = 0; i < buf.length; i++) s += buf[i] * buf[i];
  return Math.sqrt(s / buf.length);
}

function sumSquared(buf: Float32Array): number {
  let s = 0;
  for (let i = 0; i < buf.length; i++) s += buf[i] * buf[i];
  return s;
}

function pairwiseAbsDiff(arr: number[]): number {
  if (arr.length < 2) return 0;
  let s = 0;
  for (let i = 1; i < arr.length; i++) s += Math.abs(arr[i] - arr[i - 1]);
  return s / (arr.length - 1);
}

function countVoiceBreaks(frames: VoiceFrame[]): number {
  let breaks = 0;
  let inVoice = false;
  for (const f of frames) {
    const voiced = f.f0 > 50 && f.f0 < 600;
    if (inVoice && !voiced) breaks++;
    inVoice = voiced;
  }
  return breaks;
}

/** Simple autocorrelation-based F0 detector. Returns 0 if no clear pitch. */
function detectF0Autocorr(buf: Float32Array, sampleRate: number): number {
  const minLag = Math.floor(sampleRate / 600);   // 600 Hz max
  const maxLag = Math.floor(sampleRate / 50);    // 50 Hz min

  let bestLag = 0;
  let bestCorr = 0;
  for (let lag = minLag; lag <= maxLag; lag++) {
    let corr = 0;
    for (let i = 0; i < buf.length - lag; i++) {
      corr += buf[i] * buf[i + lag];
    }
    if (corr > bestCorr) {
      bestCorr = corr;
      bestLag  = lag;
    }
  }
  if (bestLag === 0 || bestCorr < 0.1) return 0;
  return sampleRate / bestLag;
}

function round1(x: number): number { return Math.round(x * 10) / 10; }
function round2(x: number): number { return Math.round(x * 100) / 100; }
