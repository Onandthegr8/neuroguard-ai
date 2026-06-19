import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../core/network/api_client.dart';
import '../../../core/storage/secure_storage.dart';

// ── Events ──────────────────────────────────────────────────────────────────
abstract class AuthEvent extends Equatable {
  const AuthEvent();
  @override List<Object?> get props => [];
}

class AuthCheckStatusEvent extends AuthEvent { const AuthCheckStatusEvent(); }
class AuthLoginEvent extends AuthEvent {
  final String email;
  final String password;
  const AuthLoginEvent({required this.email, required this.password});
  @override List<Object?> get props => [email];
}
class AuthLogoutEvent extends AuthEvent { const AuthLogoutEvent(); }

// ── States ───────────────────────────────────────────────────────────────────
abstract class AuthState extends Equatable {
  const AuthState();
  @override List<Object?> get props => [];
}
class AuthInitial extends AuthState {}
class AuthLoading extends AuthState {}
class AuthAuthenticated extends AuthState {
  final String userId;
  final String email;
  const AuthAuthenticated({required this.userId, required this.email});
  @override List<Object?> get props => [userId, email];
}
class AuthUnauthenticated extends AuthState {}
class AuthError extends AuthState {
  final String message;
  const AuthError(this.message);
  @override List<Object?> get props => [message];
}

// ── BLoC ─────────────────────────────────────────────────────────────────────
class AuthBloc extends Bloc<AuthEvent, AuthState> {
  final ApiClient apiClient;
  final SecureStorageService storage;

  AuthBloc({required this.apiClient, required this.storage}) : super(AuthInitial()) {
    on<AuthCheckStatusEvent>(_onCheckStatus);
    on<AuthLoginEvent>(_onLogin);
    on<AuthLogoutEvent>(_onLogout);
  }

  Future<void> _onCheckStatus(AuthCheckStatusEvent event, Emitter<AuthState> emit) async {
    final loggedIn = await storage.isLoggedIn;
    final userId = await storage.getUserId();
    if (loggedIn && userId != null) {
      emit(AuthAuthenticated(userId: userId, email: ''));
    } else {
      emit(AuthUnauthenticated());
    }
  }

  Future<void> _onLogin(AuthLoginEvent event, Emitter<AuthState> emit) async {
    emit(AuthLoading());
    try {
      final response = await apiClient.post<Map<String, dynamic>>(
        '/auth/login',
        data: {'email': event.email, 'password': event.password},
      );
      final data = response.data!;
      await storage.saveAccessToken(data['access_token'] as String);
      await storage.saveRefreshToken(data['refresh_token'] as String);
      final user = data['user'] as Map<String, dynamic>;
      await storage.saveUserId(user['id'] as String);
      emit(AuthAuthenticated(userId: user['id'] as String, email: user['email'] as String));
    } catch (e) {
      emit(AuthError('Login failed: ${e.toString()}'));
    }
  }

  Future<void> _onLogout(AuthLogoutEvent event, Emitter<AuthState> emit) async {
    await apiClient.post('/auth/logout');
    await storage.clearTokens();
    emit(AuthUnauthenticated());
  }
}
