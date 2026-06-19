import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../core/network/api_client.dart';

abstract class AlertsEvent extends Equatable {
  const AlertsEvent();
  @override List<Object?> get props => [];
}
class AlertsLoadEvent extends AlertsEvent { const AlertsLoadEvent(); }

abstract class AlertsState extends Equatable {
  const AlertsState();
  @override List<Object?> get props => [];
}
class AlertsInitial extends AlertsState {}
class AlertsLoading extends AlertsState {}
class AlertsLoaded extends AlertsState {
  final List<Map<String, dynamic>> alerts;
  const AlertsLoaded(this.alerts);
  @override List<Object?> get props => [alerts];
}
class AlertsError extends AlertsState {
  final String message;
  const AlertsError(this.message);
  @override List<Object?> get props => [message];
}

class AlertsBloc extends Bloc<AlertsEvent, AlertsState> {
  final ApiClient apiClient;
  AlertsBloc({required this.apiClient}) : super(AlertsInitial()) {
    on<AlertsLoadEvent>(_onLoad);
  }
  Future<void> _onLoad(AlertsLoadEvent event, Emitter<AlertsState> emit) async {
    emit(AlertsLoading());
    try {
      final resp = await apiClient.get<Map<String, dynamic>>('/alerts');
      final list = (resp.data!['alerts'] as List? ?? resp.data!.values.first as List);
      emit(AlertsLoaded(list.cast<Map<String, dynamic>>()));
    } catch (e) {
      emit(AlertsError(e.toString()));
    }
  }
}
