import 'dart:async';
import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../core/network/api_client.dart';
import '../services/keystroke_feature_extractor.dart';
import '../services/offline_keystroke_queue.dart';

// ── Events ─────────────────────────────────────────────────────────────────────
abstract class KeystrokeEvent extends Equatable {
  const KeystrokeEvent();
  @override List<Object?> get props => [];
}

class KeystrokeSessionEnded extends KeystrokeEvent {
  final KeystrokeSession session;
  final String           deviceId;
  const KeystrokeSessionEnded(this.session, this.deviceId);
  @override List<Object?> get props => [session.sessionStart];
}

/// Triggered when connectivity is restored — drains the offline queue.
class KeystrokeQueueDrainRequested extends KeystrokeEvent {}

// ── States ─────────────────────────────────────────────────────────────────────
abstract class KeystrokeState extends Equatable {
  const KeystrokeState();
  @override List<Object?> get props => [];
}

class KeystrokeIdle extends KeystrokeState {}

class KeystrokeUploading extends KeystrokeState {}

class KeystrokeUploadSuccess extends KeystrokeState {
  final double qualityScore;
  const KeystrokeUploadSuccess(this.qualityScore);
  @override List<Object?> get props => [qualityScore];
}

class KeystrokeUploadFailed extends KeystrokeState {
  final String reason;
  const KeystrokeUploadFailed(this.reason);
  @override List<Object?> get props => [reason];
}

class KeystrokeQueuedOffline extends KeystrokeState {
  final int pendingCount;
  const KeystrokeQueuedOffline(this.pendingCount);
  @override List<Object?> get props => [pendingCount];
}

// ── BLoC ───────────────────────────────────────────────────────────────────────
class KeystrokeBloc extends Bloc<KeystrokeEvent, KeystrokeState> {
  final ApiClient                 apiClient;
  final KeystrokeFeatureExtractor extractor;
  final OfflineKeystrokeQueue     offlineQueue;

  KeystrokeBloc({
    required this.apiClient,
    required this.extractor,
    required this.offlineQueue,
  }) : super(KeystrokeIdle()) {
    on<KeystrokeSessionEnded>(_onSessionEnded);
    on<KeystrokeQueueDrainRequested>(_onQueueDrain);
  }

  Future<void> _onSessionEnded(
    KeystrokeSessionEnded event,
    Emitter<KeystrokeState> emit,
  ) async {
    final features = extractor.extract(event.session);
    if (features == null || features.qualityScore < 0.3) {
      emit(const KeystrokeUploadFailed('Insufficient data quality'));
      return;
    }

    emit(KeystrokeUploading());

    final payload = {
      'device_id'             : event.deviceId,
      'session_start'         : event.session.sessionStart.toIso8601String(),
      'session_end'           : DateTime.now().toIso8601String(),
      'key_press_duration_ms' : event.session.keyPressDurations,
      'inter_key_interval_ms' : event.session.interKeyIntervals,
      'typing_speed_wpm'      : features.typingSpeedWpm,
      'correction_frequency'  : features.correctionFrequency,
      'typing_entropy'        : features.ikEntropy,
      'autocorrect_rate'      : features.autocorrectRate,
      'diurnal_hour'          : event.session.diurnalHour,
      'app_context'           : event.session.appContext,
    };

    try {
      await apiClient.post('/keystroke/features', data: payload);
      emit(KeystrokeUploadSuccess(features.qualityScore));
    } catch (_) {
      // Network unavailable — queue locally
      await offlineQueue.enqueue(deviceId: event.deviceId, payload: payload);
      final pending = await offlineQueue.pendingCount();
      emit(KeystrokeQueuedOffline(pending));
    }
  }

  Future<void> _onQueueDrain(
    KeystrokeQueueDrainRequested event,
    Emitter<KeystrokeState> emit,
  ) async {
    final pending = await offlineQueue.pendingCount();
    if (pending == 0) return;

    emit(KeystrokeUploading());
    await offlineQueue.drain(apiClient);
    final remaining = await offlineQueue.pendingCount();
    if (remaining == 0) {
      emit(const KeystrokeUploadSuccess(1.0));
    } else {
      emit(KeystrokeQueuedOffline(remaining));
    }
  }
}
