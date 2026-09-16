"""Deterministic final UI layer over the v49 source generation pipeline."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
auth = root / 'flutter/lib/screens/auth_screen.dart'
backdrop = auth.read_text().split('class _StudyBackdrop', 1)[1]
auth.write_text((root / 'tools/v50/auth_screen.dart').read_text() + '\nclass _StudyBackdrop' + backdrop)
target = root / 'flutter/lib/screens/verification_screen.dart'
target.write_text((root / 'tools/v50/verification_screen.dart').read_text())

# Keep shared typography, controls and error messages consistent across screens.
theme = root / 'flutter/lib/core/theme.dart'
text = theme.read_text()
text = text.replace('inputDecorationTheme: InputDecorationTheme(',
    'inputDecorationTheme: InputDecorationTheme(\n      errorMaxLines: 3,\n      helperMaxLines: 3,')
dark = text.index('ThemeData studyHubDarkTheme()')
marker = '    navigationBarTheme:'
position = text.index(marker, dark)
text = text[:position] + '''    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size(0, 54),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
      ),
    ),
''' + text[position:]
# Infinite minimum button width breaks buttons placed within dialog action rows.
text = text.replace('minimumSize: const Size.fromHeight(54),',
    'minimumSize: const Size(0, 54),\n        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),')
text = text.replace('    fontFamily:', '''    appBarTheme: AppBarTheme(
      backgroundColor: scheme.surface,
      foregroundColor: scheme.onSurface,
      surfaceTintColor: Colors.transparent,
      scrolledUnderElevation: 0,
      titleTextStyle: TextStyle(color: scheme.onSurface, fontSize: 20, fontWeight: FontWeight.w800),
    ),
    progressIndicatorTheme: ProgressIndicatorThemeData(color: scheme.primary),
    fontFamily:''')
theme.write_text(text)
spec = root / 'flutter/pubspec.yaml'
version = spec.read_text()
assert 'version: 4.9.0+490' in version
spec.write_text(version.replace('version: 4.9.0+490', 'version: 5.0.0+500'))
print('v5.0 premium forms applied')
