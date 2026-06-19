import 'package:flutter_test/flutter_test.dart';
import 'package:neuroguard/features/keystroke/services/keystroke_feature_extractor.dart';

void main() {
  group('KeystrokeFeatureExtractor', () {
    late KeystrokeFeatureExtractor extractor;

    setUp(() {
      extractor = KeystrokeFeatureExtractor();
    });

    test('computes quality score >= 0.3 with sufficient keystrokes', () {
      // Add 50 keystroke events
      final now = DateTime.now();
      for (int i = 0; i < 50; i++) {
        extractor.recordKeyDown(now.add(Duration(milliseconds: i * 150)));
        extractor.recordKeyUp(now.add(Duration(milliseconds: i * 150 + 85)));
      }

      final features = extractor.extractFeatures(
        sessionStart: now,
        sessionEnd: now.add(const Duration(seconds: 30)),
        appContext: 'messaging',
      );

      expect(features.qualityScore, greaterThanOrEqualTo(0.3));
    });

    test('quality score < 0.3 with fewer than 30 keystrokes', () {
      final now = DateTime.now();
      // Only 10 keystrokes
      for (int i = 0; i < 10; i++) {
        extractor.recordKeyDown(now.add(Duration(milliseconds: i * 200)));
        extractor.recordKeyUp(now.add(Duration(milliseconds: i * 200 + 90)));
      }

      final features = extractor.extractFeatures(
        sessionStart: now,
        sessionEnd: now.add(const Duration(seconds: 10)),
        appContext: 'messaging',
      );

      expect(features.qualityScore, lessThan(0.3));
    });

    test('entropy is positive for varied inter-key intervals', () {
      final now = DateTime.now();
      final intervals = [120, 85, 200, 140, 95, 175, 110, 160, 130, 90];
      for (int i = 0; i < 50; i++) {
        final ms = intervals[i % intervals.length];
        extractor.recordKeyDown(now.add(Duration(milliseconds: i * ms)));
        extractor.recordKeyUp(now.add(Duration(milliseconds: i * ms + 80)));
      }

      final features = extractor.extractFeatures(
        sessionStart: now,
        sessionEnd: now.add(const Duration(seconds: 60)),
        appContext: 'email',
      );

      expect(features.typingEntropy, greaterThan(0.0));
    });

    test('toJson contains all required fields', () {
      final now = DateTime.now();
      for (int i = 0; i < 40; i++) {
        extractor.recordKeyDown(now.add(Duration(milliseconds: i * 130)));
        extractor.recordKeyUp(now.add(Duration(milliseconds: i * 130 + 88)));
      }

      final features = extractor.extractFeatures(
        sessionStart: now,
        sessionEnd: now.add(const Duration(seconds: 25)),
        appContext: 'messaging',
      );

      final json = features.toJson();
      expect(json['key_press_duration_ms'], isNotNull);
      expect(json['inter_key_interval_ms'], isNotNull);
      expect(json['typing_speed_wpm'], isNotNull);
      expect(json['typing_entropy'], isNotNull);
      expect(json['correction_frequency'], isNotNull);
      expect(json['diurnal_hour'], isNotNull);
      expect(json['app_context'], equals('messaging'));
    });

    test('reset clears all recorded data', () {
      final now = DateTime.now();
      for (int i = 0; i < 30; i++) {
        extractor.recordKeyDown(now.add(Duration(milliseconds: i * 100)));
        extractor.recordKeyUp(now.add(Duration(milliseconds: i * 100 + 80)));
      }

      extractor.reset();

      final features = extractor.extractFeatures(
        sessionStart: now,
        sessionEnd: now.add(const Duration(seconds: 10)),
        appContext: 'messaging',
      );

      // After reset, should have no data
      expect(features.keyPressDurationMs, isEmpty);
      expect(features.interKeyIntervalMs, isEmpty);
    });
  });
}
