import 'package:get_it/get_it.dart';

import '../network/api_client.dart';
import '../storage/secure_storage.dart';
import '../../features/auth/bloc/auth_bloc.dart';
import '../../features/dashboard/bloc/dashboard_bloc.dart';
import '../../features/keystroke/bloc/keystroke_bloc.dart';
import '../../features/keystroke/services/keystroke_feature_extractor.dart';
import '../../features/alerts/bloc/alerts_bloc.dart';

final GetIt getIt = GetIt.instance;

void configureDependencies() {
  // Core
  getIt.registerLazySingleton<SecureStorageService>(() => SecureStorageService());
  getIt.registerLazySingleton<ApiClient>(() => ApiClient(getIt<SecureStorageService>()));

  // Feature services
  getIt.registerLazySingleton<KeystrokeFeatureExtractor>(() => KeystrokeFeatureExtractor());

  // BLoCs
  getIt.registerFactory<AuthBloc>(() => AuthBloc(apiClient: getIt<ApiClient>(), storage: getIt<SecureStorageService>()));
  getIt.registerFactory<DashboardBloc>(() => DashboardBloc(apiClient: getIt<ApiClient>()));
  getIt.registerFactory<KeystrokeBloc>(() => KeystrokeBloc(apiClient: getIt<ApiClient>(), extractor: getIt<KeystrokeFeatureExtractor>()));
  getIt.registerFactory<AlertsBloc>(() => AlertsBloc(apiClient: getIt<ApiClient>()));
}
