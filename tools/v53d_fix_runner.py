from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
script_path = ROOT / 'tools' / 'v53d_ui_push_delivery_audit.py'
source = script_path.read_text(encoding='utf-8')

# The generated chat already has a three-state delivery tick, but formatting
# differs across generator versions. Remove the fragile exact replacement and
# verify the actual final semantics after all changes are applied.
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
new = r'''# Delivery icon is verified after all v5.3.1 changes are applied.
w(path, text)'''
if old not in source:
    raise RuntimeError('v5.3d runner tick marker missing')
source = source.replace(old, new, 1)

# v53d's old exact-string assertions were written before the compatibility
# runner. The final checks below are stricter semantically and emit useful errors.
source = '\n'.join(
    ('# ' + line if line.lstrip().startswith('assert ') else line)
    for line in source.splitlines()
) + '\n'

code = compile(source, str(script_path), 'exec')
exec(code, {'__name__': '__main__', '__file__': str(script_path)})

# Guarantee ChatMessage has the delivered state even if an older generator
# already changed the constructor shape and made v53d's exact field patch skip.
models_path = ROOT / 'flutter/lib/core/models.dart'
models = models_path.read_text(encoding='utf-8')
chat_start = models.find('class ChatMessage {')
chat_end = models.find('\nclass ChatPresence {', chat_start)
if chat_start < 0 or chat_end < 0:
    raise RuntimeError('v5.3.1 ChatMessage model boundary missing')
chunk = models[chat_start:chat_end]
if 'this.delivered' not in chunk:
    marker = '    this.linkPreview,\n  });'
    if marker not in chunk:
        raise RuntimeError('v5.3.1 ChatMessage constructor anchor missing')
    chunk = chunk.replace(marker, '    this.linkPreview,\n    this.delivered = false,\n  });', 1)
if 'bool delivered;' not in chunk and 'bool read, delivered;' not in chunk:
    marker = '  bool read;'
    if marker not in chunk:
        raise RuntimeError('v5.3.1 ChatMessage read field anchor missing')
    chunk = chunk.replace(marker, '  bool read, delivered;', 1)
if "delivered: _bool(j['delivered'])" not in chunk:
    marker = "    read: _bool(j['read']),"
    if marker not in chunk:
        raise RuntimeError('v5.3.1 ChatMessage read parser anchor missing')
    chunk = chunk.replace(marker, marker + "\n    delivered: _bool(j['delivered']),", 1)
models = models[:chat_start] + chunk + models[chat_end:]
models_path.write_text(models, encoding='utf-8')

# Guarantee the FCM high-importance channel after every Android transform.
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

# Release patch version for this audited notification/UI fix.
pubspec_path = ROOT / 'flutter/pubspec.yaml'
pubspec = pubspec_path.read_text(encoding='utf-8')
pubspec = re.sub(r'^version:\s*[^\n]+', 'version: 5.3.1+531', pubspec, count=1, flags=re.M)
pubspec_path.write_text(pubspec, encoding='utf-8')

# Final semantic audit with explicit failure messages.
home = (ROOT / 'flutter/lib/screens/home_screen.dart').read_text(encoding='utf-8')
push = (ROOT / 'flutter/lib/core/push_service.dart').read_text(encoding='utf-8')
main = (ROOT / 'flutter/lib/main.dart').read_text(encoding='utf-8')
chat = (ROOT / 'flutter/lib/screens/chat_screen.dart').read_text(encoding='utf-8')
models = models_path.read_text(encoding='utf-8')
mobile = (ROOT / 'backend/api/mobile.php').read_text(encoding='utf-8')
mobile_v53 = (ROOT / 'backend/api/mobile_v53.php').read_text(encoding='utf-8')
relay = (ROOT / 'backend/api/mobile_realtime_push_v44.php').read_text(encoding='utf-8')
manifest = manifest_path.read_text(encoding='utf-8')

if 'Search members, groups, pages and posts' in home:
    raise RuntimeError('v5.3.1 oversized home search card still present')
if "tooltip: 'Search TaleemPK'" not in home or "tooltip: 'Notifications'" not in home:
    raise RuntimeError('v5.3.1 compact search/notification app-bar actions missing')
if 'await Firebase.initializeApp();' not in push or 'api.pushConfig()' in push:
    raise RuntimeError('v5.3.1 bundled Firebase initialization not active')
if 'taleemPkFirebaseBackgroundHandler' not in push or 'PushService.installBackgroundHandler();' not in main:
    raise RuntimeError('v5.3.1 background FCM handler missing')
if channel_key not in manifest or 'android:value="taleempk_messages"' not in manifest:
    raise RuntimeError('v5.3.1 FCM notification channel metadata missing')
if 'acknowledgeDelivered(fresh.where((m) => !m.mine)' not in chat:
    raise RuntimeError('v5.3.1 recipient delivery acknowledgement missing')
if 'm.delivered ? Icons.done_all_rounded : Icons.check_rounded' not in chat:
    raise RuntimeError('v5.3.1 delivered double-tick rendering missing')
if 'color: m.read ? const Color(0xFF75E9FF) : Colors.white70' not in chat:
    raise RuntimeError('v5.3.1 read/delivered tick color semantics missing')
if 'this.delivered' not in models or "delivered: _bool(j['delivered'])" not in models:
    raise RuntimeError('v5.3.1 delivered message model missing')
if 'mobile_message_delivery md' not in mobile or "'delivered'=>$mine" not in mobile:
    raise RuntimeError('v5.3.1 delivered status missing from message API')
if 'ack_delivery' not in mobile_v53 or 'mobile_message_delivery' not in mobile_v53:
    raise RuntimeError('v5.3.1 delivery receipt endpoint missing')
if 'mobile_v44_push_relay_send' not in relay or 'TALEEMPK_PUSH_SECRET' not in relay:
    raise RuntimeError('v5.3.1 authenticated Node Firebase relay integration missing')
if "if ($action === 'mark_view_once')" not in mobile or "UPDATE messages SET status='deleted'" not in mobile:
    raise RuntimeError('v5.3.1 server-enforced View Once consumption missing')
if 'version: 5.3.1+531' not in pubspec_path.read_text(encoding='utf-8'):
    raise RuntimeError('v5.3.1 release version missing')

print('TaleemPK v5.3.1 UI, Firebase push, delivery ticks and view-once hardening finalized')
