from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

def r(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')

def w(path: str, text: str) -> None:
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')

def function_bounds(text: str, signature: str):
    start = text.find(signature)
    if start < 0:
        raise RuntimeError(f'v5.6 missing function: {signature}')
    brace = text.find('{', start)
    if brace < 0:
        raise RuntimeError(f'v5.6 malformed function: {signature}')
    depth = 0
    quote = None
    escape = False
    line_comment = False
    block_comment = False
    i = brace
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ''
        if line_comment:
            if ch == '\n':
                line_comment = False
            i += 1
            continue
        if block_comment:
            if ch == '*' and nxt == '/':
                block_comment = False
                i += 2
                continue
            i += 1
            continue
        if quote is not None:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == quote:
                quote = None
            i += 1
            continue
        if ch == '/' and nxt == '/':
            line_comment = True
            i += 2
            continue
        if ch == '/' and nxt == '*':
            block_comment = True
            i += 2
            continue
        if ch in ("'", '"'):
            quote = ch
            i += 1
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return start, i + 1
        i += 1
    raise RuntimeError(f'v5.6 unterminated function: {signature}')

def replace_function(text: str, signature: str, replacement: str) -> str:
    a, b = function_bounds(text, signature)
    return text[:a] + replacement + text[b:]

# ---------------------------------------------------------------------------
# 1) Closed-app delivery receipt.
#
# A normal FCM notification+data packet is displayed by Android itself when
# the app is backgrounded. In that state application code is not guaranteed to
# run, so it cannot produce a WhatsApp-style "delivered to device" receipt.
#
# The server now sends a second data-only delivery_probe packet. This top-level
# background handler receives it even when the Flutter UI process is not alive
# (except Android force-stop), restores the signed-in device session and ACKs
# the exact message.
# ---------------------------------------------------------------------------
path = 'flutter/lib/core/push_service.dart'
text = r(path)
if "import 'dart:ui';" not in text:
    text = text.replace("import 'dart:async';\n", "import 'dart:async';\nimport 'dart:ui';\n", 1)

handler = r'''@pragma('vm:entry-point')
Future<void> taleemPkFirebaseBackgroundHandler(RemoteMessage message) async {
  try {
    DartPluginRegistrant.ensureInitialized();
    if (Firebase.apps.isEmpty) {
      await Firebase.initializeApp();
    }
    final event = '${message.data['event'] ?? ''}';
    final messageId = int.tryParse('${message.data['message_id'] ?? ''}') ?? 0;
    if (event != 'delivery_probe' || messageId <= 0) return;

    final api = ApiClient();
    final restored = await api.restoreSession();
    if (!restored) return;
    await api.acknowledgeDelivered(<int>[messageId]);
  } catch (_) {
    // Delivery acknowledgement is best effort. The visible notification was
    // already handled independently by FCM and must never be blocked by this.
  }
}'''
text = replace_function(
    text,
    "Future<void> taleemPkFirebaseBackgroundHandler(RemoteMessage message) async",
    handler,
)

# Foreground receives the probe through onMessage. ACK it, but never display a
# second local notification for the silent probe.
foreground = r'''  void _handleForegroundMessage(RemoteMessage message) {
    final event = '${message.data['event'] ?? ''}';
    if (event == 'delivery_probe') {
      unawaited(_ackDeliveryProbe(message));
      return;
    }
    _handleMessage(message);
    unawaited(_ackDeliveryProbe(message));
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
  }'''
text = replace_function(text, '  void _handleForegroundMessage(RemoteMessage message)', foreground)

if 'Future<void> _ackDeliveryProbe(RemoteMessage message)' not in text:
    marker = '  void _handleMessage(RemoteMessage message) {\n'
    helper = r'''  Future<void> _ackDeliveryProbe(RemoteMessage message) async {
    final messageId = _asInt(message.data['message_id']);
    if (messageId <= 0) return;
    final api = _api;
    if (api == null) return;
    try {
      await api.acknowledgeDelivered(<int>[messageId]);
    } catch (_) {}
  }

'''
    if marker not in text:
        raise RuntimeError('v5.6 push delivery helper marker missing')
    text = text.replace(marker, helper + marker, 1)

w(path, text)

# ---------------------------------------------------------------------------
# 2) Direct HTTP-v1 fallback also emits the same data-only delivery probe.
# The Node relay already sends the probe. This covers cPanel installations
# where PHP falls back to the service-account JSON directly.
# ---------------------------------------------------------------------------
for path in ('backend/api/mobile_realtime_push_v44.php', 'flutter/backend/api/mobile_realtime_push_v44.php'):
    text = r(path)
    direct = r'''function mobile_v44_fcm_send_token(string $token, string $title, string $body, array $data): bool
{
    /* Prefer the local Node relay. It sends both the visible notification and
       the data-only delivery probe. If the relay is unavailable, do both
       packets here with HTTP v1. */
    if (function_exists('mobile_v44_push_relay_send')) {
        $relay = mobile_v44_push_relay_send($token, $title, $body, $data);
        if ($relay === true) return true;
    }

    $cfg = mobile_v44_fcm_private_config();
    if (!$cfg['enabled']) return false;
    $access = mobile_v44_fcm_access_token();
    if ($access === '') return false;
    $url = 'https://fcm.googleapis.com/v1/projects/' . rawurlencode($cfg['project_id']) . '/messages:send';
    $headers = ['Authorization: Bearer ' . $access, 'Content-Type: application/json'];

    $visible = [
        'message' => [
            'token' => $token,
            'notification' => ['title' => $title, 'body' => $body],
            'data' => array_map(static fn($v): string => (string)$v, $data),
            'android' => [
                'priority' => 'high',
                'notification' => ['channel_id' => 'taleempk_messages', 'sound' => 'default'],
            ],
        ],
    ];
    [$status, $raw] = mobile_v44_http_post(
        $url,
        $headers,
        json_encode($visible, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE),
        6
    );
    if ($status < 200 || $status >= 300) {
        if ($status === 400 || $status === 404) {
            $upper = strtoupper($raw);
            if (str_contains($upper, 'UNREGISTERED') || str_contains($upper, 'REGISTRATION-TOKEN-NOT-REGISTERED')) {
                mobile_v44_push_tables();
                q('DELETE FROM mobile_push_tokens WHERE token=?', [$token]);
            }
        }
        return false;
    }

    $messageId = trim((string)($data['message_id'] ?? ''));
    if (($data['event'] ?? '') === 'message' && $messageId !== '') {
        $probeData = array_map(static fn($v): string => (string)$v, $data);
        $probeData['event'] = 'delivery_probe';
        $probe = [
            'message' => [
                'token' => $token,
                'data' => $probeData,
                'android' => ['priority' => 'high', 'ttl' => '1800s'],
            ],
        ];
        /* Probe failure must not turn a successfully delivered visible
           notification into a send failure. */
        mobile_v44_http_post(
            $url,
            $headers,
            json_encode($probe, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE),
            6
        );
    }
    return true;
}'''
    text = replace_function(
        text,
        'function mobile_v44_fcm_send_token(string $token, string $title, string $body, array $data): bool',
        direct,
    )
    w(path, text)

# ---------------------------------------------------------------------------
# 3) Release identity and hard guarantees.
# ---------------------------------------------------------------------------
path = 'flutter/pubspec.yaml'
text = r(path)
text = re.sub(r'^version:\s*[^\n]+', 'version: 5.6.0+560', text, count=1, flags=re.M)
w(path, text)

push = r('flutter/lib/core/push_service.dart')
relay = r('backend/api/mobile_realtime_push_v44.php')
node = r('server/push/app.js')
pubspec = r('flutter/pubspec.yaml')

assert 'DartPluginRegistrant.ensureInitialized();' in push
assert "event != 'delivery_probe'" in push
assert 'await api.acknowledgeDelivered(<int>[messageId]);' in push
assert "if (event == 'delivery_probe')" in push
assert 'delivery_probe' in relay and "'ttl' => '1800s'" in relay
assert "data: { ...data, event: 'delivery_probe' }" in node
assert 'delivery_probe_sent' in node
assert 'version: 5.6.0+560' in pubspec
print('TaleemPK v5.6 closed-app notifications and device delivery receipts applied successfully')
