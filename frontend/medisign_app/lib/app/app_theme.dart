import 'package:flutter/material.dart';

ThemeData buildMediSignTheme() {
  const surface = Color(0xFF051424);
  const surfaceLow = Color(0xFF0E1C2D);
  const surfaceHigh = Color(0xFF1D2B3C);
  const primary = Color(0xFF22D3EE);
  const tertiary = Color(0xFF68F5B8);
  const error = Color(0xFFEF4444);

  final colorScheme = ColorScheme.fromSeed(
    seedColor: primary,
    brightness: Brightness.dark,
    surface: surface,
    primary: primary,
    secondary: const Color(0xFFB9C8DF),
    tertiary: tertiary,
    error: error,
  ).copyWith(
    surface: surface,
    surfaceContainer: const Color(0xFF122031),
    surfaceContainerLow: surfaceLow,
    surfaceContainerHigh: surfaceHigh,
    surfaceContainerHighest: surfaceHigh,
    surfaceContainerLowest: const Color(0xFF010F1F),
  );

  return ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    colorScheme: colorScheme,
    scaffoldBackgroundColor: surface,
    appBarTheme: const AppBarTheme(
      backgroundColor: surface,
      foregroundColor: Color(0xFFD5E4FA),
      elevation: 0,
      scrolledUnderElevation: 0,
    ),
    cardTheme: CardThemeData(
      color: const Color(0xFF122031),
      elevation: 0,
      shadowColor: Colors.black54,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: const Color(0xFF122031),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: Color(0xFF3C494C)),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: Color(0xFF3C494C)),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: primary, width: 1.5),
      ),
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: primary,
        foregroundColor: const Color(0xFF00363E),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: const Color(0xFFD5E4FA),
        side: const BorderSide(color: Color(0xFF3C494C)),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      ),
    ),
    dividerTheme: const DividerThemeData(color: Color(0x223C494C), thickness: 1),
  );
}
