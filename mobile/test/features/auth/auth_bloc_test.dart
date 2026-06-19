import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:neuroguard/features/auth/bloc/auth_bloc.dart';
import 'package:neuroguard/core/network/api_client.dart';
import 'package:neuroguard/core/storage/secure_storage.dart';

class MockApiClient extends Mock implements ApiClient {}
class MockSecureStorage extends Mock implements SecureStorageService {}

void main() {
  group('AuthBloc', () {
    late MockApiClient mockApi;
    late MockSecureStorage mockStorage;

    setUp(() {
      mockApi = MockApiClient();
      mockStorage = MockSecureStorage();
    });

    test('initial state is AuthInitial', () {
      final bloc = AuthBloc(api: mockApi, storage: mockStorage);
      expect(bloc.state, isA<AuthInitial>());
      bloc.close();
    });

    blocTest<AuthBloc, AuthState>(
      'emits [AuthLoading, AuthUnauthenticated] when no token stored',
      build: () {
        when(() => mockStorage.getAccessToken())
            .thenAnswer((_) async => null);
        return AuthBloc(api: mockApi, storage: mockStorage);
      },
      act: (bloc) => bloc.add(AuthCheckStatusEvent()),
      expect: () => [
        isA<AuthLoading>(),
        isA<AuthUnauthenticated>(),
      ],
    );

    blocTest<AuthBloc, AuthState>(
      'emits [AuthLoading, AuthAuthenticated] when valid token exists',
      build: () {
        when(() => mockStorage.getAccessToken())
            .thenAnswer((_) async => 'valid-jwt-token');
        when(() => mockStorage.getUserId())
            .thenAnswer((_) async => 'user-123');
        when(() => mockApi.get('/api/v1/health/summary'))
            .thenAnswer((_) async => {'wellness_score': 72});
        return AuthBloc(api: mockApi, storage: mockStorage);
      },
      act: (bloc) => bloc.add(AuthCheckStatusEvent()),
      expect: () => [
        isA<AuthLoading>(),
        isA<AuthAuthenticated>(),
      ],
    );

    blocTest<AuthBloc, AuthState>(
      'emits [AuthLoading, AuthError] on login failure',
      build: () {
        when(() => mockApi.post(
          '/api/v1/auth/login',
          body: any(named: 'body'),
        )).thenThrow(Exception('Invalid credentials'));
        return AuthBloc(api: mockApi, storage: mockStorage);
      },
      act: (bloc) => bloc.add(
        AuthLoginEvent(email: 'bad@email.com', password: 'wrong'),
      ),
      expect: () => [
        isA<AuthLoading>(),
        isA<AuthError>(),
      ],
    );
  });
}
