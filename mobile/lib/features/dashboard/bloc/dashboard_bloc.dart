import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../core/network/api_client.dart';

// ── Events ────────────────────────────────────────────────────────────────────
abstract class DashboardEvent extends Equatable {
  const DashboardEvent();
  @override List<Object?> get props => [];
}
class DashboardLoadEvent extends DashboardEvent { const DashboardLoadEvent(); }

// ── States ────────────────────────────────────────────────────────────────────
abstract class DashboardState extends Equatable {
  const DashboardState();
  @override List<Object?> get props => [];
}
class DashboardInitial extends DashboardState {}
class DashboardLoading extends DashboardState {}
class DashboardLoaded extends DashboardState {
  final int wellnessScore;
  final double riskScore;
  final String riskTier;
  final double? sleepQuality;
  final double? typingStability;
  final String wearableStatus;
  final double dataCompleteness;
  final String? topInsight;

  const DashboardLoaded({
    required this.wellnessScore,
    required this.riskScore,
    required this.riskTier,
    this.sleepQuality,
    this.typingStability,
    required this.wearableStatus,
    required this.dataCompleteness,
    this.topInsight,
  });
  @override List<Object?> get props => [wellnessScore, riskScore, riskTier];
}
class DashboardError extends DashboardState {
  final String message;
  const DashboardError(this.message);
  @override List<Object?> get props => [message];
}

// ── BLoC ──────────────────────────────────────────────────────────────────────
class DashboardBloc extends Bloc<DashboardEvent, DashboardState> {
  final ApiClient apiClient;

  DashboardBloc({required this.apiClient}) : super(DashboardInitial()) {
    on<DashboardLoadEvent>(_onLoad);
  }

  Future<void> _onLoad(DashboardLoadEvent event, Emitter<DashboardState> emit) async {
    emit(DashboardLoading());
    try {
      final response = await apiClient.get<Map<String, dynamic>>('/health/summary');
      final d = response.data!;
      final typing = d['typing_stability_7d'];
      final sleep  = d['sleep_quality_last_night'];
      emit(DashboardLoaded(
        wellnessScore:   (d['wellness_score']   as num).toInt(),
        riskScore:       (d['risk_score']        as num).toDouble(),
        riskTier:         d['risk_tier']          as String,
        sleepQuality:    sleep  != null ? (sleep  as num).toDouble() : null,
        typingStability: typing != null ? (typing as num).toDouble() : null,
        wearableStatus:   d['wearable_sync_status'] as String,
        dataCompleteness: (d['data_completeness']   as num).toDouble(),
        topInsight:      _buildInsight(d),
      ));
    } catch (e) {
      emit(DashboardError(e.toString()));
    }
  }

  String? _buildInsight(Map<String, dynamic> d) {
    final typing = d['typing_stability_7d'];
    if (typing != null && (typing as num) < 0.7) {
      return 'Your typing consistency reduced this week. Ensure regular rest.';
    }
    final sleep = d['sleep_quality_last_night'];
    if (sleep != null && (sleep as num) < 0.7) {
      return 'Sleep quality was below average last night. Consider your sleep environment.';
    }
    return null;
  }
}
