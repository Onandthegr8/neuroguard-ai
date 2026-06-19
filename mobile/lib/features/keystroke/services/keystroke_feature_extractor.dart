/// KeystrokeFeatureExtractor
/// Captures ONLY timing metadata from the keyboard service — NEVER message content.
/// Computes statistical features from raw key-press and inter-key-interval arrays.

class KeystrokeSession {
  final DateTime sessionStart;
  final List<double> keyPressDurations;   // dwell times in ms
  final List<double> interKeyIntervals;   // IKI sequence in ms
  int backspaceCount = 0;
  int totalKeystrokes = 0;
  int autocorrectCount = 0;
  int diurnalHour;
  String appContext;

  KeystrokeSession({
    required this.sessionStart,
    required this.diurnalHour,
    this.appContext = 'other',
  })  : keyPressDurations = [],
        interKeyIntervals = [];
}

class ExtractedFeatures {
  final double meanDwellMs;
  final double stdDwellMs;
  final double meanIkiMs;
  final double stdIkiMs;
  final double p25Iki;
  final double p75Iki;
  final double ikEntropy;
  final double typingSpeedWpm;
  final double correctionFrequency;
  final double autocorrectRate;
  final double rhythmScore;
  final double qualityScore;

  const ExtractedFeatures({
    required this.meanDwellMs,
    required this.stdDwellMs,
    required this.meanIkiMs,
    required this.stdIkiMs,
    required this.p25Iki,
    required this.p75Iki,
    required this.ikEntropy,
    required this.typingSpeedWpm,
    required this.correctionFrequency,
    required this.autocorrectRate,
    required this.rhythmScore,
    required this.qualityScore,
  });

  Map<String, dynamic> toJson() => {
        'mean_dwell_ms': meanDwellMs,
        'std_dwell_ms': stdDwellMs,
        'mean_iki_ms': meanIkiMs,
        'std_iki_ms': stdIkiMs,
        'p25_iki': p25Iki,
        'p75_iki': p75Iki,
        'iki_entropy': ikEntropy,
        'typing_speed_wpm': typingSpeedWpm,
        'correction_freq': correctionFrequency,
        'autocorrect_rate': autocorrectRate,
        'rhythm_score': rhythmScore,
      };
}

class KeystrokeFeatureExtractor {
  ExtractedFeatures? extract(KeystrokeSession session) {
    final iki = session.interKeyIntervals;
    final dwell = session.keyPressDurations;
    if (iki.length < 30) return null;   // insufficient data

    final meanIki   = _mean(iki);
    final stdIki    = _std(iki, meanIki);
    final meanDwell = _mean(dwell);
    final stdDwell  = dwell.length > 1 ? _std(dwell, meanDwell) : 0.0;
    final p25       = _percentile(iki, 25);
    final p75       = _percentile(iki, 75);
    final entropy   = stdIki / (meanIki + 1e-9);

    final durationSec = session.interKeyIntervals.fold<double>(0, (a, b) => a + b) / 1000;
    final wpm = durationSec > 0 ? (session.totalKeystrokes / 5.0) / (durationSec / 60) : 0.0;

    final corrFreq     = session.totalKeystrokes > 0 ? session.backspaceCount / session.totalKeystrokes : 0.0;
    final autocorrRate = session.totalKeystrokes > 0 ? session.autocorrectCount / session.totalKeystrokes : 0.0;
    final rhythmScore  = 1.0 - (entropy / (entropy + 1.0));
    final quality      = _computeQuality(iki, durationSec);

    return ExtractedFeatures(
      meanDwellMs: meanDwell, stdDwellMs: stdDwell,
      meanIkiMs: meanIki, stdIkiMs: stdIki,
      p25Iki: p25, p75Iki: p75, ikEntropy: entropy,
      typingSpeedWpm: wpm, correctionFrequency: corrFreq,
      autocorrectRate: autocorrRate, rhythmScore: rhythmScore,
      qualityScore: quality,
    );
  }

  double _mean(List<double> v) => v.isEmpty ? 0 : v.reduce((a, b) => a + b) / v.length;

  double _std(List<double> v, double mean) {
    if (v.length < 2) return 0;
    final variance = v.map((x) => (x - mean) * (x - mean)).reduce((a, b) => a + b) / v.length;
    return variance <= 0 ? 0 : variance < double.infinity ? _sqrt(variance) : 0;
  }

  double _sqrt(double x) {
    if (x <= 0) return 0;
    double r = x;
    for (int i = 0; i < 50; i++) { r = (r + x / r) / 2; }
    return r;
  }

  double _percentile(List<double> sorted, int p) {
    final s = List<double>.from(sorted)..sort();
    final idx = (p / 100.0 * (s.length - 1)).round();
    return s[idx.clamp(0, s.length - 1)];
  }

  double _computeQuality(List<double> iki, double durationSec) {
    final completeness  = (iki.length / 200.0).clamp(0.0, 1.0);
    final durationScore = (durationSec / 60.0).clamp(0.0, 1.0);
    final outlierRatio  = iki.where((v) => v > 5000).length / iki.length;
    return completeness * 0.5 + durationScore * 0.3 + (1 - outlierRatio) * 0.2;
  }
}
