from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

def r(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')

def w(path: str, text: str) -> None:
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')

def once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f'v5.5 missing anchor: {label}')
    return text.replace(old, new, 1)

# ---------------------------------------------------------------------------
# 1) Foreground + permission reliability.
# Background/terminated delivery remains Firebase-native; foreground delivery is
# mirrored through the existing Android notification bridge.
# ---------------------------------------------------------------------------
path = 'flutter/lib/core/push_service.dart'
text = r(path)
if "import 'native_bridge.dart';" not in text:
    text = once(
        text,
        "import 'api_client.dart';\n",
        "import 'api_client.dart';\nimport 'native_bridge.dart';\n",
        'push native bridge import',
    )

permission_marker = """      final messaging = FirebaseMessaging.instance;
      await messaging.setAutoInitEnabled(true);
      await messaging.requestPermission("""
if permission_marker in text and 'NativeBridge.requestNotificationPermission();' not in text:
    text = text.replace(
        permission_marker,
        """      final messaging = FirebaseMessaging.instance;
      await messaging.setAutoInitEnabled(true);
      await NativeBridge.requestNotificationPermission();
      await messaging.requestPermission(""",
        1,
    )

old_foreground = '      _foregroundSub = FirebaseMessaging.onMessage.listen(_handleMessage);'
if old_foreground in text:
    text = text.replace(
        old_foreground,
        '      _foregroundSub = FirebaseMessaging.onMessage.listen(_handleForegroundMessage);',
        1,
    )

if 'void _handleForegroundMessage(RemoteMessage message)' not in text:
    marker = '  void _handleMessage(RemoteMessage message) {\n'
    helper = r'''  void _handleForegroundMessage(RemoteMessage message) {
    _handleMessage(message);
    final notification = message.notification;
    final conversationId = _asInt(message.data['conversation_id']);
    final title = (notification?.title ?? 'TaleemPK').trim();
    final body = (notification?.body ?? 'You have a new update.').trim();
    if (title.isEmpty || body.isEmpty) return;
    unawaited(
      NativeBridge.showNotification(
        id: _asInt(message.data['message_id']) > 0
            ? _asInt(message.data['message_id'])
            : DateTime.now().millisecondsSinceEpoch.remainder(2147483647),
        title: title,
        body: body,
        payload: conversationId > 0 ? 'chat:$conversationId' : 'notification:push',
      ),
    );
  }

'''
    text = once(text, marker, helper + marker, 'foreground notification helper')

w(path, text)

# ---------------------------------------------------------------------------
# 2) Relay URL normalization + authenticated self-test route.
# This catches the common cPanel case where TALEEMPK_PUSH_URL points at /push
# rather than the actual /push/send endpoint.
# ---------------------------------------------------------------------------
for path in ('backend/api/mobile_realtime_push_v44.php', 'flutter/backend/api/mobile_realtime_push_v44.php'):
    text = r(path)
    old = r'''function mobile_v44_push_relay_config(): array
{
    $secret = mobile_v44_cfg('TALEEMPK_PUSH_SECRET', 'push_relay_secret');
    $relay = mobile_v44_cfg('TALEEMPK_PUSH_URL', 'push_relay_url');
    if ($relay === '' && $secret !== '' && function_exists('url')) $relay = url('push/send');
    return ['enabled' => $relay !== '' && $secret !== '', 'url' => $relay, 'secret' => $secret];
}'''
    new = r'''function mobile_v44_push_relay_config(): array
{
    $secret = mobile_v44_cfg('TALEEMPK_PUSH_SECRET', 'push_relay_secret');
    $relay = mobile_v44_cfg('TALEEMPK_PUSH_URL', 'push_relay_url');
    if ($relay === '' && $secret !== '' && function_exists('url')) $relay = url('push/send');
    $relay = rtrim($relay, '/');
    if ($relay !== '') {
        $path = (string)(parse_url($relay, PHP_URL_PATH) ?? '');
        if ($path === '' || $path === '/push') $relay .= '/send';
    }
    return ['enabled' => $relay !== '' && $secret !== '', 'url' => $relay, 'secret' => $secret];
}'''
    if old in text:
        text = text.replace(old, new, 1)

    marker = "if ($action === 'realtime_config') {"
    if "if ($action === 'push_self_test')" not in text:
        block = r'''if ($action === 'push_self_test') {
    mobile_v44_push_tables();
    $title = 'TaleemPK test';
    $body = 'Push notifications are connected on this device.';
    $sent = mobile_v54_fcm_send_users([$uid], $title, $body, [
        'event'=>'self_test',
        'conversation_id'=>'0',
        'message_id'=>'0',
    ]);
    $relay = mobile_v44_push_relay_config();
    $direct = mobile_v44_fcm_private_config();
    mobile_out([
        'sent'=>$sent,
        'relay'=>(bool)($relay['enabled'] ?? false),
        'direct_fcm'=>(bool)($direct['enabled'] ?? false),
    ]);
}

'''
        text = once(text, marker, block + marker, f'{path} push self test')
    w(path, text)

# Client diagnostic API (kept internal; useful for support and regression tests).
path = 'flutter/lib/core/api_client.dart'
text = r(path)
if 'Future<Map<String, dynamic>> pushSelfTest()' not in text:
    marker = '  Future<void> heartbeat() => _request({\'action\': \'heartbeat\'});\n'
    text = once(
        text,
        marker,
        marker + "\n  Future<Map<String, dynamic>> pushSelfTest() =>\n      _request({'action': 'push_self_test'});\n",
        'push self test client',
    )
w(path, text)

# ---------------------------------------------------------------------------
# 3) Release identity.
# ---------------------------------------------------------------------------
path = 'flutter/pubspec.yaml'
text = r(path)
text = re.sub(r'^version:\s*[^\n]+', 'version: 5.5.0+550', text, count=1, flags=re.M)
w(path, text)

# ---------------------------------------------------------------------------
# 4) Hard audit.
# ---------------------------------------------------------------------------
push = r('flutter/lib/core/push_service.dart')
relay = r('backend/api/mobile_realtime_push_v44.php')
api = r('flutter/lib/core/api_client.dart')
manifest = r('flutter/android/app/src/main/AndroidManifest.xml')
node = r('server/push/app.js')
pubspec = r('flutter/pubspec.yaml')

assert 'FirebaseMessaging.onMessage.listen(_handleForegroundMessage)' in push
assert 'NativeBridge.showNotification' in push
assert 'NativeBridge.requestNotificationPermission();' in push
assert 'taleemPkFirebaseBackgroundHandler' in push
assert "if ($action === 'push_self_test')" in relay
assert "if ($path === '' || $path === '/push') $relay .= '/send';" in relay
assert 'Future<Map<String, dynamic>> pushSelfTest()' in api
assert 'com.google.firebase.messaging.default_notification_channel_id' in manifest
assert "path === '/send' || path === '/push/send'" in node
assert 'sendEachForMulticast' in node
assert 'timingSafeEqual' in node
assert 'applicationDefault()' in node
assert 'version: 5.5.0+550' in pubspec

print('TaleemPK v5.5 foreground/background push reliability and secure relay audit passed')
