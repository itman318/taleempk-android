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

(ROOT / 'flutter/V3.md').write_text('''# TaleemPK Flutter v3.0\n\n## Delivered in v3.0\n\n- Native quiz runner with timer, answer submission, scoring and optional review.\n- Persistent text-message outbox with stable client tokens and automatic retry.\n- Native Privacy & Security center synced with the TaleemPK account.\n- Signed-in mobile device list with per-device revocation.\n- Native password change with optional sign-out of other mobile sessions.\n- Existing premium chat, calls, media, reactions, polls, groups and notification badges retained.\n\n## Reliability\n\n- Queued text messages survive process restarts through SharedPreferences.\n- Retried sends reuse the same client token to avoid duplicate messages on compatible servers.\n- New outbox tests cover persistence, attempts, isolation and removal.\n- Production CI builds directly from committed source after this migration is finalized.\n\n## Known platform dependencies\n\n- Guaranteed notifications while the app is fully killed still require server-backed FCM/OneSignal credentials.\n- Existing web E2EE keys are not exported to the native client, so native UI does not claim full key-synced E2EE.\n- Chat realtime transport remains optimized short polling until a WebSocket/SSE service is deployed on hosting.\n''', encoding='utf-8')

# Remove historical build-time patchers. The source itself becomes canonical.
for rel in [
    'tools/patch_v29.py',
    'tools/patch_v29_prep.py',
    'tools/patch_v30.py',
    'tools/patch_v30_quiz.py',
]:
    path = ROOT / rel
    if path.exists():
        path.unlink()
