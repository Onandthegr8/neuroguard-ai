import 'package:flutter/material.dart';

class AppTheme {
  static const _primaryBlue = Color(0xFF1E40AF);
  static const _accentTeal = Color(0xFF0D9488);
  static const _errorRed = Color(0xFFDC2626);
  static const _warningAmber = Color(0xFFD97706);
  static const _successGreen = Color(0xFF059669);

  static ThemeData get light => ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: _primaryBlue,
          brightness: Brightness.light,
          primary: _primaryBlue,
          secondary: _accentTeal,
          error: _errorRed,
        ),
        fontFamily: 'Inter',
        appBarTheme: const AppBarTheme(centerTitle: false, elevation: 0, scrolledUnderElevation: 1),
        cardTheme: CardTheme(
          elevation: 0,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        ),
        filledButtonTheme: FilledButtonThemeData(
          style: FilledButton.styleFrom(
            minimumSize: const Size(double.infinity, 52),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          ),
        ),
        inputDecorationTheme: InputDecorationTheme(
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
          filled: true,
        ),
      );

  static ThemeData get dark => light.copyWith(
        colorScheme: ColorScheme.fromSeed(
          seedColor: _primaryBlue,
          brightness: Brightness.dark,
          primary: const Color(0xFF3B82F6),
          secondary: _accentTeal,
        ),
      );

  static Color riskTierColor(String tier) {
    return switch (tier) {
      'very_low' => _successGreen,
      'low' => const Color(0xFF10B981),
      'moderate' => _warningAmber,
      'high' => const Color(0xFFEF4444),
      'very_high' => _errorRed,
      _ => Colors.grey,
    };
  }
}
