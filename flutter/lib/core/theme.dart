import 'package:flutter/material.dart';

abstract final class AppColors {
  static const navy = Color(0xFF08142F);
  static const navySoft = Color(0xFF102451);
  static const blue = Color(0xFF3157E8);
  static const violet = Color(0xFF7657EF);
  static const cyan = Color(0xFF19B6D2);
  static const bg = Color(0xFFF5F7FC);
  static const card = Colors.white;
  static const ink = Color(0xFF17213B);
  static const muted = Color(0xFF667085);
  static const success = Color(0xFF17A673);
  static const danger = Color(0xFFE24B5B);
}

ThemeData studyHubTheme() {
  final scheme = ColorScheme.fromSeed(
    seedColor: AppColors.blue,
    brightness: Brightness.light,
    primary: AppColors.blue,
    secondary: AppColors.violet,
    surface: AppColors.card,
    error: AppColors.danger,
  );
  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    scaffoldBackgroundColor: AppColors.bg,
    fontFamily: 'sans',
    textTheme: const TextTheme(
      headlineLarge: TextStyle(
        fontWeight: FontWeight.w800,
        letterSpacing: -1.1,
        color: AppColors.ink,
      ),
      headlineMedium: TextStyle(
        fontWeight: FontWeight.w800,
        letterSpacing: -.7,
        color: AppColors.ink,
      ),
      titleLarge: TextStyle(fontWeight: FontWeight.w800, color: AppColors.ink),
      titleMedium: TextStyle(fontWeight: FontWeight.w700, color: AppColors.ink),
      bodyLarge: TextStyle(height: 1.45, color: AppColors.ink),
      bodyMedium: TextStyle(height: 1.42, color: AppColors.ink),
    ),
    cardTheme: CardThemeData(
      color: Colors.white,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(22),
        side: const BorderSide(color: Color(0x0D17213B)),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: Colors.white,
      contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(16),
        borderSide: const BorderSide(color: Color(0x1A667085)),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(16),
        borderSide: const BorderSide(color: Color(0x1A667085)),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(16),
        borderSide: const BorderSide(color: AppColors.blue, width: 1.6),
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: AppColors.blue,
        foregroundColor: Colors.white,
        minimumSize: const Size.fromHeight(54),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
      ),
    ),
    navigationBarTheme: const NavigationBarThemeData(
      backgroundColor: Colors.white,
      indicatorColor: Color(0x183157E8),
      height: 70,
      labelTextStyle: WidgetStatePropertyAll(
        TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
      ),
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: AppColors.navy,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
    ),
  );
}

class BrandMark extends StatelessWidget {
  const BrandMark({
    super.key,
    this.size = 56,
    this.showName = true,
    this.light = false,
  });
  final double size;
  final bool showName, light;
  @override
  Widget build(BuildContext context) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [AppColors.blue, AppColors.violet],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(size * .28),
          boxShadow: const [
            BoxShadow(
              color: Color(0x4D3157E8),
              blurRadius: 22,
              offset: Offset(0, 9),
            ),
          ],
        ),
        child: Icon(
          Icons.school_rounded,
          color: Colors.white,
          size: size * .55,
        ),
      ),
      if (showName) ...[
        const SizedBox(width: 13),
        Text(
          'TaleemPK',
          style: TextStyle(
            fontSize: size * .38,
            fontWeight: FontWeight.w900,
            letterSpacing: -.8,
            color: light ? Colors.white : AppColors.navy,
          ),
        ),
      ],
    ],
  );
}
