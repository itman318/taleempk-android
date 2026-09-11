from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace(path, old, new, count=1):
    p = ROOT / path
    text = p.read_text(encoding='utf-8')
    if old not in text:
        raise SystemExit(f'anchor missing in {path}: {old!r}')
    p.write_text(text.replace(old, new, count), encoding='utf-8')


# Correct two native quiz serialization/type issues found by source audit.
replace(
    'flutter/lib/core/api_client.dart',
    "for (final entry in answers.entries) '\\${entry.key}': entry.value,",
    "for (final entry in answers.entries) '${entry.key}': entry.value,",
)
replace(
    'flutter/lib/screens/quiz_screen.dart',
    "secondsLeft = (loaded.timeLimitSeconds - elapsed).clamp(0, loaded.timeLimitSeconds);",
    "secondsLeft = (loaded.timeLimitSeconds - elapsed)\n                .clamp(0, loaded.timeLimitSeconds)\n                .toInt();",
)

# Keep a concise production release note in the repository.
(ROOT / 'flutter/V3.md').write_text('''# TaleemPK Flutter v3.0\n\n## Delivered in v3.0\n\n- Native quiz runner with timer, answer submission, scoring and optional review.\n- Persistent text-message outbox with stable client tokens and automatic retry.\n- Native Privacy & Security center synced with the TaleemPK account.\n- Signed-in mobile device list with per-device revocation.\n- Native password change with optional sign-out of other mobile sessions.\n- Existing premium chat, calls, media, reactions, polls, groups and notification badges retained.\n\n## Reliability\n\n- Queued text messages survive process restarts through SharedPreferences.\n- Retried sends reuse the same client token to avoid duplicate messages on compatible servers.\n- New outbox tests cover persistence, attempts, isolation and removal.\n- CI runs Flutter analyze, Flutter tests, PHP syntax checks and a release APK build from committed source.\n\n## Known platform dependencies\n\n- Guaranteed notifications while the app is fully killed still require server-backed FCM/OneSignal credentials.\n- Existing web E2EE keys are not exported to the native client, so native UI does not claim full key-synced E2EE.\n- Chat realtime transport remains optimized short polling until a WebSocket/SSE service is deployed on hosting.\n''', encoding='utf-8')

# Replace build-time patching with a clean production CI workflow.
(ROOT / '.github/workflows/flutter-premium.yml').write_text('''name: Build TaleemPK Flutter APK\n\non:\n  workflow_dispatch:\n  pull_request:\n    paths:\n      - 'flutter/**'\n      - 'backend/**'\n      - '.github/workflows/flutter-premium.yml'\n  push:\n    branches: [main, flutter-premium-v2]\n    paths:\n      - 'flutter/**'\n      - 'backend/**'\n      - '.github/workflows/flutter-premium.yml'\n\npermissions:\n  contents: read\n\njobs:\n  build:\n    runs-on: ubuntu-latest\n    timeout-minutes: 30\n    defaults:\n      run:\n        working-directory: flutter\n    steps:\n      - uses: actions/checkout@v4\n      - uses: subosito/flutter-action@v2\n        with:\n          channel: stable\n          cache: true\n      - run: flutter pub get\n      - run: flutter analyze --no-fatal-infos\n      - run: flutter test\n      - name: PHP syntax check mobile API\n        working-directory: .\n        run: |\n          php -l flutter/backend/api/mobile.php\n          php -l backend/api/mobile.php\n      - run: flutter build apk --release\n      - uses: actions/upload-artifact@v4\n        with:\n          name: TaleemPK-v3.0.0-APK\n          path: flutter/build/app/outputs/flutter-apk/app-release.apk\n          if-no-files-found: error\n''', encoding='utf-8')

# Remove historical build-time patchers. The source itself is now canonical.
for rel in [
    'tools/patch_v29.py',
    'tools/patch_v29_prep.py',
    'tools/patch_v30.py',
    'tools/patch_v30_quiz.py',
]:
    path = ROOT / rel
    if path.exists():
        path.unlink()

# Self-delete after execution so production builds remain patch-free.
Path(__file__).unlink(missing_ok=True)
