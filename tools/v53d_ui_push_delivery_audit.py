from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def r(path):
    return (ROOT / path).read_text(encoding='utf-8')

def w(path, text):
    (ROOT / path).write_text(text, encoding='utf-8')

def once(text, old, new, label):
    if old not in text:
        raise RuntimeError(f'v5.3d missing anchor: {label}')
    return text.replace(old, new, 1)

# ---------------------------------------------------------------------------
# 1) Home: remove the oversized search card and use a compact search action
# beside the notification button.
# ---------------------------------------------------------------------------
path = 'flutter/lib/screens/home_screen.dart'
text = r(path)
start = text.find("children: [Padding(padding: const EdgeInsets.fromLTRB(18, 10, 18, 0), child: InkWell(")
end_marker = "Center(child: ConstrainedBox"
if start >= 0:
    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError('v5.3d home search card end missing')
    text = text[:start] + "children: [" + text[end:]

old_actions = """appBar: PremiumAppBar(title: 'Learn & grow', subtitle: 'TALEEMPK', actions: [
        IconButton.filledTonal(tooltip: 'Notifications', onPressed: () => _open(context, 'notifications'),
          icon: const Icon(Icons.notifications_none_rounded)), const SizedBox(width: 12)]),"""
new_actions = """appBar: PremiumAppBar(title: 'Learn & grow', subtitle: 'TALEEMPK', actions: [
        IconButton.filledTonal(
          tooltip: 'Search TaleemPK',
          onPressed: () => Navigator.push(context, premiumRoute(builder: (_) => const GlobalSearchScreen())),
          icon: const Icon(Icons.search_rounded),
        ),
        const SizedBox(width: 6),
        IconButton.filledTonal(
          tooltip: 'Notifications',
          onPressed: () => _open(context, 'notifications'),
          icon: const Icon(Icons.notifications_none_rounded),
        ),
        const SizedBox(width: 12),
      ]),"""
text = once(text, old_actions, new_actions, 'compact home actions')
w(path, text)

# ---------------------------------------------------------------------------
# 2) Push: initialize Firebase from bundled google-services.json instead of
# requiring the website to expose public Firebase config before token setup.
# This fixes registration on servers where only the secure relay is configured.
# ---------------------------------------------------------------------------
path = 'flutter/lib/core/push_service.dart'
text = r(path)
if 'taleemPkFirebaseBackgroundHandler' not in text:
    marker = "import 'realtime_service.dart';\n\n"
    handler = """@pragma('vm:entry-point')
Future<void> taleemPkFirebaseBackgroundHandler(RemoteMessage message) async {
  try {
    if (Firebase.apps.isEmpty) await Firebase.initializeApp();
  } catch (_) {
    // A background notification must never crash the process.
  }
}

"""
    text = once(text, marker, marker + handler, 'background push handler')

old_init = """      _api = api;
      final config = await api.pushConfig();
      if (config['enabled'] != true) return;

      if (!_firebaseReady) {
        final options = FirebaseOptions(
          apiKey: '${config['api_key'] ?? ''}',
          appId: '${config['app_id'] ?? ''}',
          messagingSenderId: '${config['sender_id'] ?? ''}',
          projectId: '${config['project_id'] ?? ''}',
        );
        if (options.apiKey.isEmpty ||
            options.appId.isEmpty ||
            options.messagingSenderId.isEmpty ||
            options.projectId.isEmpty) {
          return;
        }
        if (Firebase.apps.isEmpty) {
          await Firebase.initializeApp(options: options);
        }
        _firebaseReady = true;
      }

      final messaging = FirebaseMessaging.instance;"""
new_init = """      _api = api;
      if (!_firebaseReady) {
        if (Firebase.apps.isEmpty) {
          await Firebase.initializeApp();
        }
        _firebaseReady = Firebase.apps.isNotEmpty;
      }
      if (!_firebaseReady) return;

      final messaging = FirebaseMessaging.instance;
      await messaging.setAutoInitEnabled(true);"""
text = once(text, old_init, new_init, 'bundled Firebase initialization')
if 'static void installBackgroundHandler()' not in text:
    marker = '  static final PushService instance = PushService._();\n'
    method = """  static void installBackgroundHandler() {
    FirebaseMessaging.onBackgroundMessage(taleemPkFirebaseBackgroundHandler);
  }
"""
    text = once(text, marker, marker + method, 'background handler registration method')
w(path, text)

path = 'flutter/lib/main.dart'
text = r(path)
if "import 'core/push_service.dart';" not in text:
    text = once(text, "import 'core/app_state.dart';\n", "import 'core/app_state.dart';\nimport 'core/push_service.dart';\n", 'main push import')
if 'PushService.installBackgroundHandler();' not in text:
    text = once(text, '  WidgetsFlutterBinding.ensureInitialized();\n', '  WidgetsFlutterBinding.ensureInitialized();\n  PushService.installBackgroundHandler();\n', 'main background handler')
w(path, text)

# Tell FCM which high-importance channel to use when the process is not alive.
path = 'flutter/android/app/src/main/AndroidManifest.xml'
text = r(path)
if 'com.google.firebase.messaging.default_notification_channel_id' not in text:
    marker = '        <meta-data android:name="flutterEmbedding" android:value="2" />'
    replacement = '''        <meta-data
            android:name="com.google.firebase.messaging.default_notification_channel_id"
            android:value="taleempk_messages" />
        <meta-data android:name="flutterEmbedding" android:value="2" />'''
    text = once(text, marker, replacement, 'FCM default channel')
w(path, text)

# ---------------------------------------------------------------------------
# 3) Delivery ticks: the recipient acknowledges messages when its app actually
# fetches them. Sender sees: one tick = stored, two grey = delivered, two blue = read.
# ---------------------------------------------------------------------------
path = 'flutter/lib/core/models.dart'
text = r(path)
if 'this.delivered = false,' not in text:
    text = once(text, '    this.linkPreview,\n  });', '    this.linkPreview,\n    this.delivered = false,\n  });', 'message delivered ctor')
    text = once(text, '  bool playedByMe, playedByOther;\n  bool read;', '  bool playedByMe, playedByOther;\n  bool read, delivered;', 'message delivered field')
    text = once(text, "    read: _bool(j['read']),", "    read: _bool(j['read']),\n    delivered: _bool(j['delivered']),", 'message delivered parse')
w(path, text)

for path in ('backend/api/mobile.php', 'flutter/backend/api/mobile.php'):
    text = r(path)
    action = "if ($action === 'messages') {\n    require_feature('feature_chat');"
    if "mobile_v53_tables();\n    $cid" not in text:
        text = once(text, action, action + "\n    if (function_exists('mobile_v53_tables')) mobile_v53_tables();", f'{path} delivery table')
    select_marker = """                EXISTS(SELECT 1 FROM message_plays mp2 WHERE mp2.message_id=m.id AND mp2.user_id<>m.sender_id) played_by_other
           FROM messages m"""
    if 'mobile_message_delivery md' not in text:
        select_replacement = """                EXISTS(SELECT 1 FROM message_plays mp2 WHERE mp2.message_id=m.id AND mp2.user_id<>m.sender_id) played_by_other,
                EXISTS(SELECT 1 FROM mobile_message_delivery md WHERE md.message_id=m.id AND md.user_id<>m.sender_id) delivered
           FROM messages m"""
        text = once(text, select_marker, select_replacement, f'{path} delivered select')
    if "'delivered'=>$mine" not in text:
        text = once(
            text,
            "            'attachment_type'=>$deleted ? null : ($m['attachment_type'] ?? null), 'read'=>$read,",
            "            'attachment_type'=>$deleted ? null : ($m['attachment_type'] ?? null), 'read'=>$read,\n            'delivered'=>$mine && (bool)($m['delivered'] ?? false),",
            f'{path} delivered output',
        )
    w(path, text)

path = 'flutter/lib/screens/chat_screen.dart'
text = r(path)
ack_line = "      unawaited(api.acknowledgeDelivered(fresh.where((m) => !m.mine).map((m) => m.id)));\n"
needle = '      final fresh = result[0] as List<ChatMessage>;\n'
if ack_line not in text:
    count = text.count(needle)
    if count < 2:
        raise RuntimeError('v5.3d expected load and poll fresh-message anchors')
    text = text.replace(needle, needle + ack_line)

old_tick = """                  Icon(
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
w(path, text)

# ---------------------------------------------------------------------------
# 4) Server sender: prefer the already-deployed authenticated Node Firebase
# relay; fall back to direct FCM service-account settings when available.
# ---------------------------------------------------------------------------
path = 'backend/api/mobile_realtime_push_v44.php'
text = r(path)
if 'function mobile_v44_push_relay_config()' not in text:
    marker = 'function mobile_v44_fcm_send_token(string $token, string $title, string $body, array $data): bool\n{\n'
    relay = r'''function mobile_v44_push_relay_config(): array
{
    $secret = mobile_v44_cfg('TALEEMPK_PUSH_SECRET', 'push_relay_secret');
    $relay = mobile_v44_cfg('TALEEMPK_PUSH_URL', 'push_relay_url');
    if ($relay === '' && $secret !== '' && function_exists('url')) $relay = url('push/send');
    return ['enabled' => $relay !== '' && $secret !== '', 'url' => $relay, 'secret' => $secret];
}

function mobile_v44_push_relay_send(string $token, string $title, string $body, array $data): ?bool
{
    $cfg = mobile_v44_push_relay_config();
    if (!$cfg['enabled']) return null;
    [$status, $raw] = mobile_v44_http_post(
        $cfg['url'],
        ['Authorization: Bearer ' . $cfg['secret'], 'Content-Type: application/json'],
        json_encode(['tokens'=>[$token],'title'=>$title,'body'=>$body,'data'=>$data], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE),
        8
    );
    if ($status < 200 || $status >= 300) return false;
    $decoded = json_decode($raw, true);
    return is_array($decoded) && (int)($decoded['sent'] ?? 0) > 0;
}

'''
    text = once(text, marker, relay + marker, 'push relay functions')
    text = once(
        text,
        marker,
        marker + "    $relay = mobile_v44_push_relay_send($token, $title, $body, $data);\n    if ($relay !== null) return $relay;\n",
        'push relay priority',
    )

old_gate = """if ($action === 'push_chat') {
    $cfg = mobile_v44_fcm_private_config();
    if (!$cfg['enabled']) mobile_out(['enabled'=>false,'sent'=>0]);"""
new_gate = """if ($action === 'push_chat') {
    $cfg = mobile_v44_fcm_private_config();
    $relayCfg = mobile_v44_push_relay_config();
    if (!$cfg['enabled'] && !$relayCfg['enabled']) mobile_out(['enabled'=>false,'sent'=>0]);"""
if old_gate in text:
    text = text.replace(old_gate, new_gate, 1)
w(path, text)
w('flutter/backend/api/mobile_realtime_push_v44.php', text)

# ---------------------------------------------------------------------------
# 5) Regression guarantees for the user-reported v5.3 issues.
# ---------------------------------------------------------------------------
home = r('flutter/lib/screens/home_screen.dart')
push = r('flutter/lib/core/push_service.dart')
main = r('flutter/lib/main.dart')
manifest = r('flutter/android/app/src/main/AndroidManifest.xml')
chat = r('flutter/lib/screens/chat_screen.dart')
models = r('flutter/lib/core/models.dart')
mobile = r('backend/api/mobile.php')
relay = r('backend/api/mobile_realtime_push_v44.php')
assert 'Search members, groups, pages and posts' not in home
assert "tooltip: 'Search TaleemPK'" in home and "tooltip: 'Notifications'" in home
assert 'await Firebase.initializeApp();' in push and 'api.pushConfig()' not in push
assert 'taleemPkFirebaseBackgroundHandler' in push and 'PushService.installBackgroundHandler();' in main
assert 'com.google.firebase.messaging.default_notification_channel_id' in manifest
assert 'acknowledgeDelivered(fresh.where((m) => !m.mine)' in chat
assert '(m.read || m.delivered) ? Icons.done_all_rounded' in chat
assert 'bool read, delivered;' in models and "delivered: _bool(j['delivered'])" in models
assert 'mobile_message_delivery md' in mobile and "'delivered'=>$mine" in mobile
assert 'mobile_v44_push_relay_send' in relay and 'TALEEMPK_PUSH_SECRET' in relay
assert "if ($action === 'mark_view_once')" in mobile and "UPDATE messages SET status='deleted'" in mobile
print('TaleemPK v5.3 UI, push, delivery ticks and view-once audit fixes applied')
