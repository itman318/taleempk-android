from pathlib import Path
import re
import shutil

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
        raise RuntimeError(f'v4.4 missing function: {signature}')
    brace = text.find('{', start)
    if brace < 0:
        raise RuntimeError(f'v4.4 malformed function: {signature}')
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
    raise RuntimeError(f'v4.4 unterminated function: {signature}')


def replace_function(text: str, signature: str, replacement: str) -> str:
    start, end = function_bounds(text, signature)
    return text[:start] + replacement + text[end:]


# ---------------------------------------------------------------------------
# Dependencies + release version.
# ---------------------------------------------------------------------------
path = 'flutter/pubspec.yaml'
text = r(path)
if 'web_socket_channel:' not in text:
    marker = '  flutter_webrtc: ^1.2.0\n'
    if marker not in text:
        raise RuntimeError('v4.4 pubspec dependency marker missing')
    text = text.replace(
        marker,
        marker
        + '  web_socket_channel: ^3.0.3\n'
        + '  firebase_core: ^4.14.0\n'
        + '  firebase_messaging: ^16.6.0\n',
        1,
    )
text = re.sub(r'^version:\s*[^\n]+', 'version: 4.4.0+440', text, count=1, flags=re.M)
w(path, text)


# ---------------------------------------------------------------------------
# API client: configure realtime/push and publish invalidations after the
# existing, authoritative PHP send succeeds.
# ---------------------------------------------------------------------------
path = 'flutter/lib/core/api_client.dart'
text = r(path)
if "import 'realtime_service.dart';" not in text:
    marker = "import 'quiz_models.dart';\n"
    if marker not in text:
        raise RuntimeError('v4.4 API import marker missing')
    text = text.replace(marker, marker + "import 'realtime_service.dart';\n", 1)

presence = r'''  Future<ChatPresence> presence(
    int conversationId, {
    String? kind,
    bool clear = false,
  }) async {
    final result = ChatPresence.fromJson(
      await _request({
        'action': 'presence',
        'conversation_id': '$conversationId',
        if (kind != null && kind.isNotEmpty) 'kind': kind,
        if (clear) 'clear': '1',
      }),
    );
    if ((kind != null && kind.isNotEmpty) || clear) {
      RealtimeService.instance.publish(
        conversationId,
        type: clear ? 'presence_clear' : 'presence',
      );
    }
    return result;
  }'''
text = replace_function(text, '  Future<ChatPresence> presence(', presence)

send_text = r'''  Future<void> sendText(
    int conversationId,
    String text, {
    int? replyTo,
    String? clientToken,
    bool encrypted = false,
    List<int> mentionIds = const <int>[],
  }) async {
    await _request({
      'action': 'send',
      'conversation_id': '$conversationId',
      'content': text,
      'client_token': clientToken ?? _clientToken(),
      if (replyTo != null) 'reply_to': '$replyTo',
      if (encrypted) 'enc': '1',
      if (mentionIds.isNotEmpty) 'mention_ids': mentionIds.join(','),
    });
    RealtimeService.instance.publish(conversationId, type: 'message');
    unawaited(_notifyChat(conversationId));
  }'''
text = replace_function(text, '  Future<void> sendText(', send_text)

send_file = r'''  Future<void> sendFile(
    int conversationId,
    String filePath, {
    String field = 'attachment',
    int voiceSeconds = 0,
    String voiceWave = '',
    int? replyTo,
    String content = '',
    String? clientToken,
    bool encrypted = false,
    List<int> mentionIds = const <int>[],
    void Function(double progress)? onProgress,
  }) async {
    final fields = <String, String>{
      'action': 'send',
      'conversation_id': '$conversationId',
      'content': content,
      'client_token': clientToken ?? _clientToken(),
      if (voiceSeconds > 0) 'voice_seconds': '$voiceSeconds',
      if (voiceWave.isNotEmpty) 'voice_wave': voiceWave,
      if (replyTo != null) 'reply_to': '$replyTo',
      if (encrypted) 'enc_att': '1',
      if (encrypted && content.isNotEmpty) 'enc': '1',
      if (mentionIds.isNotEmpty) 'mention_ids': mentionIds.join(','),
    };
    await _multipart(fields, field, filePath, onProgress: onProgress);
    RealtimeService.instance.publish(conversationId, type: 'message');
    unawaited(_notifyChat(conversationId));
  }'''
text = replace_function(text, '  Future<void> sendFile(', send_file)

api_marker = '  String newClientToken() => _clientToken();\n'
if api_marker not in text:
    raise RuntimeError('v4.4 API insertion marker missing')
if 'Future<Map<String, dynamic>> realtimeConfig()' not in text:
    methods = r'''  Future<Map<String, dynamic>> realtimeConfig() =>
      _request({'action': 'realtime_config'});

  Future<Map<String, dynamic>> pushConfig() =>
      _request({'action': 'push_config'});

  Future<void> registerPushToken(String token) => _request({
        'action': 'register_push',
        'token': token,
        'platform': 'android',
      });

  Future<void> unregisterPushToken(String token) => _request({
        'action': 'unregister_push',
        'token': token,
      });

  Future<void> _notifyChat(int conversationId) async {
    try {
      await _request({
        'action': 'push_chat',
        'conversation_id': '$conversationId',
      });
    } catch (_) {
      // The message is already stored; push delivery is best-effort only.
    }
  }

'''
    text = text.replace(api_marker, methods + api_marker, 1)
w(path, text)


# ---------------------------------------------------------------------------
# App lifecycle: activate optional transports after authentication. Failure of
# Firebase/WebSocket must never block account access.
# ---------------------------------------------------------------------------
path = 'flutter/lib/core/app_state.dart'
text = r(path)
if "import 'dart:async';" not in text:
    text = "import 'dart:async';\n\n" + text
if "import 'push_service.dart';" not in text:
    marker = "import 'models.dart';\n"
    if marker not in text:
        raise RuntimeError('v4.4 AppState import marker missing')
    text = text.replace(
        marker,
        marker + "import 'push_service.dart';\nimport 'realtime_service.dart';\n",
        1,
    )

start_marker = '  Future<void> start() async {\n'
start_pos = text.find(start_marker)
if start_pos < 0:
    raise RuntimeError('v4.4 AppState start marker missing')
if 'Future<void> _activateRealtimePush() async {' not in text:
    helper = r'''  Future<void> _activateRealtimePush() async {
    if (status != AppStatus.signedIn || api.token == null) return;
    try {
      final config = await api.realtimeConfig();
      if (config['enabled'] == true) {
        await RealtimeService.instance.configure(
          url: '${config['url'] ?? ''}',
          ticket: '${config['ticket'] ?? ''}',
        );
      } else {
        RealtimeService.instance.stop(clearRooms: false);
      }
    } catch (_) {
      RealtimeService.instance.stop(clearRooms: false);
    }
    try {
      await PushService.instance.bind(api);
    } catch (_) {}
  }

'''
    text = text[:start_pos] + helper + text[start_pos:]

# Add activation after any generated path that reaches signedIn. Avoid duplicate
# insertion if this transform is intentionally run twice during debugging.
pattern = re.compile(r'(?P<indent>\s*)status = AppStatus\.signedIn;\n(?P=indent)notifyListeners\(\);')
def activate(match):
    block = match.group(0)
    indent = match.group('indent')
    tail = f'\n{indent}unawaited(_activateRealtimePush());'
    after = text[match.end():match.end()+len(tail)+8]
    return block if '_activateRealtimePush' in after else block + tail
text = pattern.sub(activate, text)

ss, se = function_bounds(text, '  void _sessionExpired(String message) {')
chunk = text[ss:se]
if 'RealtimeService.instance.stop();' not in chunk:
    chunk = chunk.replace(
        '  void _sessionExpired(String message) {\n',
        '  void _sessionExpired(String message) {\n'
        '    RealtimeService.instance.stop();\n'
        '    PushService.instance.detach();\n',
        1,
    )
text = text[:ss] + chunk + text[se:]

logout = r'''  Future<void> logout() async {
    try {
      await PushService.instance.unbind(api);
    } catch (_) {
      PushService.instance.detach();
    }
    RealtimeService.instance.stop();
    await api.logout();
    bootstrap = null;
    status = AppStatus.signedOut;
    notifyListeners();
  }'''
text = replace_function(text, '  Future<void> logout() async {', logout)
w(path, text)


# ---------------------------------------------------------------------------
# Chat screen: subscribe to invalidations and let the existing API refresh stay
# authoritative for encryption, moderation, read receipts, edits and deletes.
# ---------------------------------------------------------------------------
path = 'flutter/lib/screens/chat_screen.dart'
text = r(path)
if "import '../core/realtime_service.dart';" not in text:
    marker = "import '../core/outbox.dart';\n"
    if marker not in text:
        raise RuntimeError('v4.4 chat import marker missing')
    text = text.replace(marker, marker + "import '../core/realtime_service.dart';\n", 1)

state_marker = '  final outbox = MessageOutbox();\n'
if state_marker not in text:
    raise RuntimeError('v4.4 chat outbox marker missing')
if 'StreamSubscription<RealtimeEvent>? realtimeSubscription;' not in text:
    text = text.replace(
        state_marker,
        state_marker + '  StreamSubscription<RealtimeEvent>? realtimeSubscription;\n',
        1,
    )

is_, ie = function_bounds(text, '  void initState() {')
chunk = text[is_:ie]
if 'RealtimeService.instance.subscribe(widget.conversation.id);' not in chunk:
    marker = '    _refreshOutboxCount();\n'
    if marker not in chunk:
        raise RuntimeError('v4.4 chat init marker missing')
    chunk = chunk.replace(
        marker,
        marker
        + '    RealtimeService.instance.subscribe(widget.conversation.id);\n'
        + '    realtimeSubscription = RealtimeService.instance.events.listen((event) {\n'
        + '      if (!mounted || event.conversationId != widget.conversation.id) return;\n'
        + '      _schedulePoll(immediate: true);\n'
        + '    });\n',
        1,
    )
text = text[:is_] + chunk + text[ie:]

ss, se = function_bounds(text, '  void dispose() {')
chunk = text[ss:se]
if 'realtimeSubscription?.cancel();' not in chunk:
    marker = '    WidgetsBinding.instance.removeObserver(this);\n'
    if marker not in chunk:
        raise RuntimeError('v4.4 chat dispose marker missing')
    chunk = chunk.replace(
        marker,
        marker
        + '    realtimeSubscription?.cancel();\n'
        + '    RealtimeService.instance.unsubscribe(widget.conversation.id);\n',
        1,
    )
text = text[:ss] + chunk + text[se:]

schedule_poll = r'''  void _schedulePoll({bool immediate = false}) {
    poll?.cancel();
    if (!mounted || !foreground) return;
    poll = Timer(
      Duration(
        milliseconds: immediate
            ? 70
            : (RealtimeService.instance.connected ? 1800 : 950),
      ),
      _poll,
    );
  }'''
text = replace_function(text, '  void _schedulePoll(', schedule_poll)
w(path, text)


# ---------------------------------------------------------------------------
# Android 13+ notification permission.
# ---------------------------------------------------------------------------
path = 'flutter/android/app/src/main/AndroidManifest.xml'
text = r(path)
permission = '<uses-permission android:name="android.permission.POST_NOTIFICATIONS" />'
if permission not in text:
    marker = '<uses-permission android:name="android.permission.INTERNET" />'
    if marker in text:
        text = text.replace(marker, marker + '\n    ' + permission, 1)
    else:
        close = text.find('>')
        if close < 0:
            raise RuntimeError('v4.4 Android manifest malformed')
        text = text[:close + 1] + '\n    ' + permission + text[close + 1:]
w(path, text)


# ---------------------------------------------------------------------------
# PHP mobile API: install the v4.4 authenticated realtime/push action module.
# ---------------------------------------------------------------------------
for path in ('backend/api/mobile.php', 'flutter/backend/api/mobile.php'):
    text = r(path)
    marker = "$u = mobile_user();\n$uid = (int) $u['id'];\n"
    if marker not in text:
        raise RuntimeError(f'v4.4 server auth marker missing in {path}')
    require_line = "require_once __DIR__ . '/mobile_realtime_push_v44.php';\n"
    if require_line not in text:
        text = text.replace(marker, marker + require_line, 1)
    w(path, text)

shutil.copyfile(
    ROOT / 'backend/api/mobile_realtime_push_v44.php',
    ROOT / 'flutter/backend/api/mobile_realtime_push_v44.php',
)


# ---------------------------------------------------------------------------
# Regression guarantees.
# ---------------------------------------------------------------------------
pubspec = r('flutter/pubspec.yaml')
api = r('flutter/lib/core/api_client.dart')
state = r('flutter/lib/core/app_state.dart')
chat = r('flutter/lib/screens/chat_screen.dart')
mobile = r('backend/api/mobile.php')
module = r('backend/api/mobile_realtime_push_v44.php')
manifest = r('flutter/android/app/src/main/AndroidManifest.xml')
assert 'version: 4.4.0+440' in pubspec
assert 'web_socket_channel: ^3.0.3' in pubspec
assert 'firebase_core: ^4.14.0' in pubspec
assert 'firebase_messaging: ^16.6.0' in pubspec
assert 'RealtimeService.instance.publish' in api
assert "'action': 'realtime_config'" in api and "'action': 'register_push'" in api
assert '_activateRealtimePush' in state and 'PushService.instance.bind' in state
assert 'StreamSubscription<RealtimeEvent>? realtimeSubscription;' in chat
assert 'RealtimeService.instance.subscribe(widget.conversation.id)' in chat
assert 'RealtimeService.instance.connected ? 1800 : 950' in chat
assert 'POST_NOTIFICATIONS' in manifest
assert 'mobile_realtime_push_v44.php' in mobile
assert "if ($action === 'realtime_config')" in module
assert "if ($action === 'register_push')" in module
assert "if ($action === 'push_chat')" in module
assert 'https://fcm.googleapis.com/v1/projects/' in module
assert (ROOT / 'realtime/server.mjs').exists()
print('TaleemPK v4.4 realtime WebSocket + FCM infrastructure applied successfully')
