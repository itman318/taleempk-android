from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
script_path = ROOT / 'tools' / 'v53d_ui_push_delivery_audit.py'
source = script_path.read_text(encoding='utf-8')

# The generated chat already has a three-state tick expression after the v5.3
# delivery model is added, but its formatting differs from the older exact
# block. Skip that fragile exact replacement and verify semantics below.
old = r'''old_tick = """                  Icon(
                    m.read ? Icons.done_all_rounded : Icons.check_rounded,
                    size: 15,
                    color: m.read ? const Color(0xFF75E9FF) : Colors.white70,
                  ),"""
new_tick = """                  Icon(
                    (m.read || m.delivered) ? Icons.done_all_rounded : Icons.check_rounded,
                    size: 15,
                    color: m.read ? const Color(0xFF75E9FF) : Colors.white70,
                  ),"""
text = once(text, old_tick, new_tick, 'three-state message tick')
w(path, text)'''
new = r'''# Delivery icon is verified after all v5.3 changes are applied.
w(path, text)'''
if old not in source:
    raise RuntimeError('v5.3d runner tick marker missing')
source = source.replace(old, new, 1)

# The final runner owns these compatibility assertions because the manifest and
# tick layout vary across the generator chain.
source = source.replace(
    "assert 'com.google.firebase.messaging.default_notification_channel_id' in manifest\n",
    "# final runner verifies/repairs FCM channel metadata\n",
    1,
)
source = source.replace(
    "assert '(m.read || m.delivered) ? Icons.done_all_rounded' in chat\n",
    "# final runner verifies three-state tick semantics\n",
    1,
)

code = compile(source, str(script_path), 'exec')
exec(code, {'__name__': '__main__', '__file__': str(script_path)})

# Guarantee the channel metadata after every prior Android transform.
manifest_path = ROOT / 'flutter/android/app/src/main/AndroidManifest.xml'
manifest = manifest_path.read_text(encoding='utf-8')
channel_key = 'com.google.firebase.messaging.default_notification_channel_id'
if channel_key not in manifest:
    marker = '        <meta-data android:name="flutterEmbedding" android:value="2" />'
    if marker not in manifest:
        raise RuntimeError('v5.3.1 Android manifest Flutter metadata anchor missing')
    manifest = manifest.replace(
        marker,
        '        <meta-data\n'
        '            android:name="com.google.firebase.messaging.default_notification_channel_id"\n'
        '            android:value="taleempk_messages" />\n'
        + marker,
        1,
    )
    manifest_path.write_text(manifest, encoding='utf-8')

# Release patch version for the audited notification/UI fix.
pubspec_path = ROOT / 'flutter/pubspec.yaml'
pubspec = pubspec_path.read_text(encoding='utf-8')
pubspec = re.sub(r'^version:\s*[^\n]+', 'version: 5.3.1+531', pubspec, count=1, flags=re.M)
pubspec_path.write_text(pubspec, encoding='utf-8')

# Final semantic checks: one tick = stored, two grey = delivered, two blue = read.
chat = (ROOT / 'flutter/lib/screens/chat_screen.dart').read_text(encoding='utf-8')
models = (ROOT / 'flutter/lib/core/models.dart').read_text(encoding='utf-8')
if 'm.delivered ? Icons.done_all_rounded : Icons.check_rounded' not in chat:
    raise RuntimeError('v5.3.1 delivered double-tick rendering missing')
if 'color: m.read ? const Color(0xFF75E9FF) : Colors.white70' not in chat:
    raise RuntimeError('v5.3.1 read/delivered tick color semantics missing')
if 'bool read, delivered;' not in models:
    raise RuntimeError('v5.3.1 delivered message model missing')
manifest = manifest_path.read_text(encoding='utf-8')
if channel_key not in manifest or 'android:value="taleempk_messages"' not in manifest:
    raise RuntimeError('v5.3.1 FCM notification channel metadata missing')

print('TaleemPK v5.3.1 UI, Firebase push, delivery ticks and view-once hardening finalized')
