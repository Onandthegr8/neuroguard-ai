/// KeyboardService
///
/// Bridges the native platform keystroke channel to Dart.
/// Android: receives events from KeystrokeAccessibilityService via MethodChannel.
/// iOS:     receives events from the custom keyboard extension via MethodChannel.
///
/// Privacy guarantee: key *codes* are passed as category labels only
/// ('alpha', 'digit', 'backspace', 'space', 'punct', 'special').
/// The actual characters are never transmitted.

import 'dart:async';
import 'package:flutter/services.dart';

import 'keystroke_feature_extractor.dart';
import 'offline_keystroke_queue.dart';

/// Low-level key event as received from the platform channel.
class RawKeyEvent {
  final String  category;    // 'alpha'|'digit'|'backspace'|'space'|'punct'|'special'
  final int     action;      // 0 = DOWN, 1 = UP
  final int     timestampMs; // ms since epoch (device clock)

  const RawKeyEvent({
    required this.category,
    required this.action,
    required this.timestampMs,
  });

  factory RawKeyEvent.fromMap(Map<dynamic, dynamic> m) => RawKeyEvent(
    category:    m['category']    as String,
    action:      m['action']      as int,
    timestampMs: m['timestamp_ms'] as int,
  );
}

/// Manages the lifecycle of a keystroke capture session.
class KeyboardService {
  static const _channel   = MethodChannel('com.neuroguard/keystroke');
  static const _minEvents = 30;       // minimum IKI events before session is valid
  static const _sessionTimeoutMs = 5 * 60 * 1000; // 5 min inactivity ends session

  final OfflineKeystrokeQueue _queue;
  final KeystrokeFeatureExtractor _extractor;

  KeystrokeSession?     _activeSession;
  final Map<String, int> _pendingDownMs = {}; // category → downTimestampMs (for dwell)
  int _lastDownMs = 0;

  Timer? _idleTimer;

  final StreamController<KeystrokeSession> _sessionEndController =
      StreamController<KeystrokeSession>.broadcast();

  /// Emits completed sessions ready for feature extraction + upload.
  Stream<KeystrokeSession> get onSessionEnded => _sessionEndController.stream;

  KeyboardService({
    required OfflineKeystrokeQueue queue,
    required KeystrokeFeatureExtractor extractor,
  })  : _queue = queue,
        _extractor = extractor {
    _channel.setMethodCallHandler(_onPlatformEvent);
  }

  // ── Platform channel handler ────────────────────────────────────────────────

  Future<dynamic> _onPlatformEvent(MethodCall call) async {
    switch (call.method) {
      case 'onKeyEvent':
        final event = RawKeyEvent.fromMap(call.arguments as Map);
        _handleKeyEvent(event);
        break;
      case 'onAccessibilityEnabled':
        _startSession(appContext: call.arguments['app_context'] as String? ?? 'other');
        break;
      case 'onAccessibilityDisabled':
        _endSession();
        break;
      case 'onAppContextChanged':
        _endSession(); // end current session when user switches apps
        _startSession(appContext: call.arguments['app_context'] as String? ?? 'other');
        break;
    }
  }

  // ── Session management ──────────────────────────────────────────────────────

  void _startSession({String appContext = 'other'}) {
    _endSession(); // close any previous session
    _activeSession = KeystrokeSession(
      sessionStart: DateTime.now(),
      diurnalHour:  DateTime.now().hour,
      appContext:   appContext,
    );
    _pendingDownMs.clear();
    _lastDownMs = 0;
  }

  void _endSession() {
    _idleTimer?.cancel();
    final session = _activeSession;
    if (session == null) return;
    _activeSession = null;

    // Only emit if we have enough IKI data
    if (session.interKeyIntervals.length >= _minEvents) {
      _sessionEndController.add(session);
    }
  }

  void _resetIdleTimer() {
    _idleTimer?.cancel();
    _idleTimer = Timer(
      const Duration(milliseconds: _sessionTimeoutMs),
      _endSession,
    );
  }

  // ── Key event processing ────────────────────────────────────────────────────

  void _handleKeyEvent(RawKeyEvent event) {
    if (_activeSession == null) {
      _startSession();
    }
    final session = _activeSession!;

    if (event.action == 0) {
      // Key DOWN — record timestamp for dwell calculation
      _pendingDownMs[event.category] = event.timestampMs;

      // IKI = time between consecutive key-downs
      if (_lastDownMs > 0) {
        final iki = (event.timestampMs - _lastDownMs).toDouble();
        if (iki > 0 && iki < 5000) { // filter impossible values
          session.interKeyIntervals.add(iki);
        }
      }
      _lastDownMs = event.timestampMs;

      // Count event type
      session.totalKeystrokes++;
      if (event.category == 'backspace') session.backspaceCount++;

      _resetIdleTimer();
    } else {
      // Key UP — compute dwell time
      final downMs = _pendingDownMs.remove(event.category);
      if (downMs != null) {
        final dwell = (event.timestampMs - downMs).toDouble();
        if (dwell > 0 && dwell < 2000) { // filter held-key anomalies
          session.keyPressDurations.add(dwell);
        }
      }
    }
  }

  // ── Platform controls ───────────────────────────────────────────────────────

  /// Request permission to enable AccessibilityService (Android) / activate keyboard (iOS).
  Future<bool> requestPermission() async {
    try {
      final result = await _channel.invokeMethod<bool>('requestPermission');
      return result ?? false;
    } on PlatformException {
      return false;
    }
  }

  /// Check whether the accessibility / custom keyboard is currently active.
  Future<bool> isServiceActive() async {
    try {
      final result = await _channel.invokeMethod<bool>('isServiceActive');
      return result ?? false;
    } on PlatformException {
      return false;
    }
  }

  void dispose() {
    _endSession();
    _idleTimer?.cancel();
    _sessionEndController.close();
  }
}
