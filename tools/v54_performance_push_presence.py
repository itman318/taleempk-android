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
        raise RuntimeError(f'v5.4 missing anchor: {label}')
    return text.replace(old, new, 1)

def replace_between(text: str, start: str, end: str, replacement: str, label: str) -> str:
    a = text.find(start)
    if a < 0:
        raise RuntimeError(f'v5.4 missing start: {label}')
    b = text.find(end, a)
    if b < 0:
        raise RuntimeError(f'v5.4 missing end: {label}')
    return text[:a] + replacement + text[b:]

def function_bounds(text: str, signature: str):
    start = text.find(signature)
    if start < 0:
        raise RuntimeError(f'v5.4 missing function: {signature}')
    paren = text.find('(', start)
    if paren < 0:
        raise RuntimeError(f'v5.4 malformed function: {signature}')
    pdepth = 0
    quote = None
    escaped = False
    i = paren
    param_end = -1
    while i < len(text):
        ch = text[i]
        if quote is not None:
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == quote:
                quote = None
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
        elif ch == '(':
            pdepth += 1
        elif ch == ')':
            pdepth -= 1
            if pdepth == 0:
                param_end = i
                break
        i += 1
    if param_end < 0:
        raise RuntimeError(f'v5.4 unterminated parameters: {signature}')
    brace = text.find('{', param_end + 1)
    if brace < 0:
        raise RuntimeError(f'v5.4 missing body: {signature}')
    depth = 0
    quote = None
    escaped = False
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
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
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
    raise RuntimeError(f'v5.4 unterminated body: {signature}')

def replace_function(text: str, signature: str, replacement: str) -> str:
    a, b = function_bounds(text, signature)
    return text[:a] + replacement + text[b:]


# ---------------------------------------------------------------------------
# 1) Presence/last-seen correctness + cheaper conversations query.
# ---------------------------------------------------------------------------
conversation_block = r'''if ($action === 'conversations') {
    require_feature('feature_chat');
    $archived = !empty($_POST['archived']) ? 1 : 0;
    $rows = fetch_all(
        "SELECT c.id,c.type,c.title,c.avatar,c.last_message,c.last_activity,
                cm.unread_count,cm.is_muted,cm.is_archived,cm.role,
                peer.name other_name,peer.avatar other_avatar,peer.last_seen other_last_seen,
                peer.show_online other_show_online,peer.id other_id,peer.username other_username,
                EXISTS(SELECT 1 FROM blocks b WHERE b.user_id=? AND b.blocked_id=peer.id) self_blocked,
                EXISTS(SELECT 1 FROM blocks b WHERE b.user_id=peer.id AND b.blocked_id=?) blocked_by_other
           FROM conversation_members cm
           JOIN conversations c ON c.id=cm.conversation_id
           LEFT JOIN conversation_members pcm
             ON pcm.conversation_id=c.id AND pcm.user_id<>cm.user_id AND c.type<>'group'
           LEFT JOIN users peer ON peer.id=pcm.user_id
          WHERE cm.user_id=? AND cm.is_archived=?
          ORDER BY c.last_activity DESC LIMIT 100",
        [$uid,$uid,$uid,$archived]
    );
    $chatCallsEnabled = (int)setting('chat_calls',1)===1 && table_exists('calls');
    $videoCallsEnabledGlobal = $chatCallsEnabled && (int)setting('call_video',1)===1;
    $items = array_map(static function(array $c) use ($chatCallsEnabled,$videoCallsEnabledGlobal): array {
        $group = $c['type']==='group';
        $avatar = $group ? $c['avatar'] : $c['other_avatar'];
        $otherId = (int)($c['other_id'] ?? 0);
        $online = !$group && (int)($c['other_show_online'] ?? 0) === 1
            && !empty($c['other_last_seen']) && strtotime((string)$c['other_last_seen']) >= time() - 150;
        $status = $group ? 'Study group' : ($online ? 'Online now'
            : (!empty($c['other_last_seen']) && (int)($c['other_show_online'] ?? 0) === 1
                ? 'Last seen ' . time_ago($c['other_last_seen']) : 'Private conversation'));
        return [
            'id'=>(int)$c['id'], 'title'=>$group ? ($c['title'] ?: 'Study group') : ($c['other_name'] ?: 'Conversation'),
            'avatar'=>$avatar ? upload_url($avatar) : null, 'last_message'=>(string)($c['last_message'] ?? ''),
            'last_activity'=>time_ago($c['last_activity']), 'unread'=>(int)$c['unread_count'], 'is_group'=>$group,
            'online'=>$online, 'status_text'=>$status, 'muted'=>(int)$c['is_muted']===1,
            'archived'=>(int)$c['is_archived']===1, 'group_role'=>(string)($c['role'] ?? ''),
            'other_id'=>$otherId, 'other_username'=>(string)($c['other_username'] ?? ''),
            'self_blocked'=>!$group && (bool)($c['self_blocked'] ?? false),
            'blocked_by_other'=>!$group && (bool)($c['blocked_by_other'] ?? false),
            'calls_enabled'=>!$group && $otherId>0 && $chatCallsEnabled,
            'video_calls_enabled'=>!$group && $otherId>0 && $videoCallsEnabledGlobal,
        ];
    }, $rows);
    mobile_out(['conversations'=>$items]);
}

'''

for path in ('backend/api/mobile.php', 'flutter/backend/api/mobile.php'):
    text = r(path)
    old_last_seen = r'''    /* A chatty phone must not turn every API read into a database write. */
    q('UPDATE mobile_sessions SET last_seen=NOW()
        WHERE token_hash=? AND last_seen<DATE_SUB(NOW(), INTERVAL 5 MINUTE)', [hash('sha256', $token)]);
    return $row;'''
    new_last_seen = r'''    /* Keep both the device session and the public presence fresh, but throttle
       writes so chat polling does not hammer the users table. Conversation
       presence reads users.last_seen, not mobile_sessions.last_seen. */
    $tokenHash = hash('sha256', $token);
    q('UPDATE mobile_sessions SET last_seen=NOW()
        WHERE token_hash=? AND (last_seen IS NULL OR last_seen<DATE_SUB(NOW(), INTERVAL 2 MINUTE))', [$tokenHash]);
    q('UPDATE users SET last_seen=NOW()
        WHERE id=? AND (last_seen IS NULL OR last_seen<DATE_SUB(NOW(), INTERVAL 45 SECOND))', [(int)$row['id']]);
    return $row;'''
    text = once(text, old_last_seen, new_last_seen, f'{path} public last seen')
    text = replace_between(
        text,
        "if ($action === 'conversations') {",
        "if ($action === 'presence') {",
        conversation_block,
        f'{path} optimized conversations',
    )
    uid_marker = "$uid = (int) $u['id'];\n"
    if "if ($action === 'heartbeat')" not in text:
        text = once(
            text,
            uid_marker,
            uid_marker + "if ($action === 'heartbeat') { mobile_out(['online'=>true,'server_time'=>date('c')]); }\n",
            f'{path} heartbeat',
        )
    text = text.replace(
        "'SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0',",
        "\"SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0 AND type<>'message'\",",
        1,
    )
    w(path, text)

for path in ('backend/api/mobile_v53.php', 'flutter/backend/api/mobile_v53.php'):
    text = r(path)
    text = text.replace("p.status='published' AND p.content LIKE ?", "p.status='active' AND p.content LIKE ?")
    w(path, text)


# ---------------------------------------------------------------------------
# 2) Client performance: stop hidden-tab hammering and use realtime first.
# ---------------------------------------------------------------------------
path = 'flutter/lib/core/api_client.dart'
text = r(path)
if 'Future<void> heartbeat()' not in text:
    marker = '  String newClientToken() => _clientToken();\n'
    text = once(
        text,
        marker,
        "  Future<void> heartbeat() => _request({'action': 'heartbeat'});\n\n" + marker,
        'API heartbeat',
    )
text = text.replace('    unawaited(_notifyChat(conversationId));\n', '')
if '  Future<void> _notifyChat(int conversationId) async {' in text:
    a, b = function_bounds(text, '  Future<void> _notifyChat(int conversationId) async {')
    text = text[:a] + text[b:]
w(path, text)

path = 'flutter/lib/screens/chat_screen.dart'
text = r(path)
text = text.replace('RealtimeService.instance.connected ? 1800 : 950', 'RealtimeService.instance.connected ? 10000 : 2500')
text = text.replace('final fullSync = pollTicks % 4 == 0;', 'final fullSync = pollTicks % 12 == 0;')
w(path, text)

path = 'flutter/lib/screens/conversations_screen.dart'
text = r(path)
text = once(
    text,
    '  const ConversationsScreen({super.key, this.initialConversationId=0});\n  final int initialConversationId;',
    '  const ConversationsScreen({super.key, this.initialConversationId=0, this.active=true});\n  final int initialConversationId;\n  final bool active;',
    'conversation active property',
)
old_init_timer = r'''    _load().then((_) { if (mounted && widget.initialConversationId > 0) _openConversationById(widget.initialConversationId); });
    refreshTimer = Timer.periodic(
      const Duration(seconds: 3),
      (_) => _refreshSilently(),
    );'''
new_init_timer = r'''    _load().then((_) { if (mounted && widget.initialConversationId > 0) _openConversationById(widget.initialConversationId); });
    _syncRefreshTimer();'''
text = once(text, old_init_timer, new_init_timer, 'conversation timer init')
dispose_marker = '  @override\n  void dispose() {\n'
if 'void didUpdateWidget(ConversationsScreen oldWidget)' not in text:
    helpers = r'''  @override
  void didUpdateWidget(ConversationsScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.active != widget.active) {
      _syncRefreshTimer();
      if (widget.active) unawaited(_refreshSilently());
    }
  }

  void _syncRefreshTimer() {
    refreshTimer?.cancel();
    refreshTimer = null;
    if (!widget.active) return;
    refreshTimer = Timer.periodic(
      const Duration(seconds: 10),
      (_) => _refreshSilently(),
    );
  }

'''
    text = once(text, dispose_marker, helpers + dispose_marker, 'conversation active timer helpers')
text = text.replace(
    '    if (!mounted || loading || silentRefreshing) return;',
    '    if (!mounted || !widget.active || loading || silentRefreshing) return;',
    1,
)
w(path, text)


# ---------------------------------------------------------------------------
# 3) Push registration reliability and foreground lifecycle/battery use.
# ---------------------------------------------------------------------------
path = 'flutter/lib/core/push_service.dart'
text = r(path)
if 'Timer? _retryTimer;' not in text:
    text = once(
        text,
        '  String? _registeredToken;\n',
        '  String? _registeredToken;\n  Timer? _retryTimer;\n  DateTime? _lastRegistration;\n',
        'push retry fields',
    )
old_register = r'''      final token = await messaging.getToken();
      if (token != null && token.isNotEmpty) {
        _registeredToken = token;
        await api.registerPushToken(token);
      }'''
new_register = r'''      final token = await messaging.getToken();
      if (token != null && token.isNotEmpty) {
        await _registerToken(api, token);
      }'''
text = once(text, old_register, new_register, 'initial push registration')
old_refresh = r'''      _tokenSub = messaging.onTokenRefresh.listen((token) async {
        _registeredToken = token;
        final bound = _api;
        if (bound == null || token.isEmpty) return;
        try {
          await bound.registerPushToken(token);
        } catch (_) {}
      });'''
new_refresh = r'''      _tokenSub = messaging.onTokenRefresh.listen((token) async {
        final bound = _api;
        if (bound == null || token.isEmpty) return;
        await _registerToken(bound, token);
      });'''
text = once(text, old_refresh, new_refresh, 'push token refresh')
if 'Future<bool> _registerToken(ApiClient api, String token)' not in text:
    marker = '  Future<void> unbind(ApiClient api) async {\n'
    helper = r'''  Future<bool> _registerToken(ApiClient api, String token) async {
    if (token.isEmpty || _api == null) return false;
    try {
      await api.registerPushToken(token);
      _registeredToken = token;
      _lastRegistration = DateTime.now();
      _retryTimer?.cancel();
      _retryTimer = null;
      return true;
    } catch (_) {
      _scheduleRetry();
      return false;
    }
  }

  void _scheduleRetry() {
    _retryTimer?.cancel();
    if (_api == null) return;
    _retryTimer = Timer(const Duration(seconds: 45), () {
      final api = _api;
      if (api != null) unawaited(ensureRegistered(api, force: true));
    });
  }

  Future<void> ensureRegistered(ApiClient api, {bool force = false}) async {
    if (!_firebaseReady || _api == null) return;
    final last = _lastRegistration;
    if (!force &&
        _registeredToken != null &&
        last != null &&
        DateTime.now().difference(last) < const Duration(minutes: 10)) {
      return;
    }
    try {
      final token = await FirebaseMessaging.instance.getToken();
      if (token != null && token.isNotEmpty) {
        await _registerToken(api, token);
      }
    } catch (_) {
      _scheduleRetry();
    }
  }

'''
    text = once(text, marker, helper + marker, 'push registration helpers')
text = text.replace(
    '    _api = null;\n    _tokenSub?.cancel();',
    '    _api = null;\n    _retryTimer?.cancel();\n    _retryTimer = null;\n    _lastRegistration = null;\n    _tokenSub?.cancel();',
    1,
)
w(path, text)

path = 'flutter/lib/screens/home_shell.dart'
text = r(path)
text = text.replace(
    'class _HomeShellState extends State<HomeShell> {',
    'class _HomeShellState extends State<HomeShell> with WidgetsBindingObserver {',
    1,
)
if 'Timer? presenceHeartbeat;' not in text:
    text = once(
        text,
        '  bool notificationBusy = false;\n',
        '  bool notificationBusy = false;\n  bool foreground = true;\n  Timer? presenceHeartbeat;\n',
        'home lifecycle fields',
    )
text = text.replace('      const Duration(seconds: 4),', '      const Duration(seconds: 6),', 1)
text = text.replace('      const Duration(seconds: 6),\n      (_) => _watchNotifications(),', '      const Duration(seconds: 20),\n      (_) => _watchNotifications(),', 1)
text = once(
    text,
    '    super.initState();\n',
    '    super.initState();\n    WidgetsBinding.instance.addObserver(this);\n',
    'home lifecycle observer',
)
post_frame = '    WidgetsBinding.instance.addPostFrameCallback((_) {\n'
if 'presenceHeartbeat = Timer.periodic' not in text:
    text = once(
        text,
        post_frame,
        "    presenceHeartbeat = Timer.periodic(const Duration(seconds: 45), (_) => _heartbeat());\n" + post_frame,
        'home heartbeat timer',
    )
text = text.replace(
    '    callWatch?.cancel();\n    notificationWatch?.cancel();',
    '    WidgetsBinding.instance.removeObserver(this);\n    presenceHeartbeat?.cancel();\n    callWatch?.cancel();\n    notificationWatch?.cancel();',
    1,
)
marker = '  Future<void> _setupNotificationWatch() async {\n'
if 'Future<void> _heartbeat() async {' not in text:
    heartbeat = r'''  Future<void> _heartbeat() async {
    if (!mounted || !foreground) return;
    final api = AppScope.of(context).api;
    try {
      await api.heartbeat();
    } catch (_) {}
    unawaited(PushService.instance.ensureRegistered(api));
  }

'''
    text = once(text, marker, heartbeat + marker, 'home heartbeat helper')
if 'void didChangeAppLifecycleState(AppLifecycleState state)' not in text:
    lifecycle = r'''  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    foreground = state == AppLifecycleState.resumed;
    if (foreground) {
      unawaited(_heartbeat());
      unawaited(_watchNotifications());
      unawaited(_watchIncomingCall());
    }
  }

'''
    text = once(text, marker, lifecycle + marker, 'home lifecycle callback')
text = text.replace('    if (!mounted || notificationBusy) return;', '    if (!mounted || !foreground || notificationBusy) return;', 1)
text = text.replace('    if (!mounted || activeIncomingId != 0) return;', '    if (!mounted || !foreground || activeIncomingId != 0) return;', 1)
text = text.replace('_tab(2, const ConversationsScreen()),', '_tab(2, ConversationsScreen(active: index == 2)),', 1)
w(path, text)

# Lazy-mount heavy tabs. IndexedStack keeps every child alive, so the old shell
# started Feed, Chat and Profile network work together on every app launch.
path = 'flutter/lib/screens/home_shell.dart'
text = r(path)
if 'final Set<int> mountedTabs = <int>{0};' not in text:
    text = once(
        text,
        '  final keys = List.generate(4, (_) => GlobalKey<NavigatorState>());\n',
        '  final keys = List.generate(4, (_) => GlobalKey<NavigatorState>());\n  final Set<int> mountedTabs = <int>{0};\n',
        'lazy tab state',
    )
text = text.replace('  int pushedConversation=0;\n', '')
old_push_listener = """    pushTapSub=PushService.instance.conversationTaps.listen((id){ if(!mounted)return; setState((){index=2;pushedConversation=id;}); keys[2].currentState?.pushReplacement(MaterialPageRoute(builder:(_)=>ConversationsScreen(initialConversationId:id))); });
"""
if old_push_listener in text:
    text = text.replace(
        old_push_listener,
        "    pushTapSub=PushService.instance.conversationTaps.listen(_openPushedConversation);\n",
        1,
    )
if 'void _openPushedConversation(int id)' not in text:
    marker = '  Future<void> _setupNotificationWatch() async {\n'
    helper = r'''  void _openPushedConversation(int id) {
    if (!mounted || id <= 0) return;
    setState(() {
      mountedTabs.add(2);
      index = 2;
    });
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final navigator = keys[2].currentState;
      if (navigator == null) return;
      navigator.pushReplacement(
        MaterialPageRoute<void>(
          builder: (_) => ConversationsScreen(
            initialConversationId: id,
            active: true,
          ),
        ),
      );
    });
  }

'''
    text = once(text, marker, helper + marker, 'push target helper')

# Native foreground notifications carry the same chat:<conversation> payload.
# Route them to the exact conversation instead of only switching to the Chat tab.
if '  Future<void> _consumeNotificationTap() async {' in text:
    replacement = r'''  Future<void> _consumeNotificationTap() async {
    if (!mounted) return;
    final payload = await NativeBridge.consumeNotificationPayload();
    if (!mounted || payload == null || payload.isEmpty) return;
    if (payload.startsWith('chat:')) {
      final id = int.tryParse(payload.substring(5)) ?? 0;
      if (id > 0) {
        _openPushedConversation(id);
      } else {
        setState(() {
          mountedTabs.add(2);
          index = 2;
        });
      }
      return;
    }
    if (payload.startsWith('notification:')) {
      setState(() {
        mountedTabs.add(0);
        index = 0;
      });
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        keys[0].currentState?.push(
          MaterialPageRoute<void>(
            builder: (_) => const ModuleScreen(module: 'notifications'),
          ),
        );
      });
    }
  }'''
    text = replace_function(text, '  Future<void> _consumeNotificationTap() async {', replacement)

text = text.replace(
    """            _tab(0, const HomeScreen()),
            _tab(1, const FeedScreen()),
            _tab(2, ConversationsScreen(active: index == 2)),
            _tab(3, const ProfileScreen()),""",
    """            _tab(0, const HomeScreen()),
            mountedTabs.contains(1)
                ? _tab(1, const FeedScreen())
                : const SizedBox.shrink(),
            mountedTabs.contains(2)
                ? _tab(2, ConversationsScreen(active: index == 2))
                : const SizedBox.shrink(),
            mountedTabs.contains(3)
                ? _tab(3, const ProfileScreen())
                : const SizedBox.shrink(),""",
    1,
)
text = text.replace(
    '          onDestinationSelected: (value) => setState(() => index = value),',
    """          onDestinationSelected: (value) => setState(() {
            mountedTabs.add(value);
            index = value;
          }),""",
    1,
)
w(path, text)


# ---------------------------------------------------------------------------
# 4) Server-side FCM: work for web-origin messages too, with secure service
# account fallback outside public_html and bulk relay support.
# ---------------------------------------------------------------------------
private_config = r'''function mobile_v44_fcm_private_config(): array
{
    $project = mobile_v44_cfg('FIREBASE_PROJECT_ID', 'firebase_project_id');
    $email = mobile_v44_cfg('FIREBASE_CLIENT_EMAIL', 'firebase_client_email');
    $key = mobile_v44_cfg('FIREBASE_PRIVATE_KEY', 'firebase_private_key');

    if ($project === '' || $email === '' || $key === '') {
        $candidates = [];
        $explicit = mobile_v44_cfg('FIREBASE_SERVICE_ACCOUNT_FILE', 'firebase_service_account_file');
        if ($explicit !== '') $candidates[] = $explicit;
        $google = getenv('GOOGLE_APPLICATION_CREDENTIALS');
        if ($google !== false && trim((string)$google) !== '') $candidates[] = trim((string)$google);
        /* TaleemPK's documented cPanel layout keeps this private file next to,
           never inside, public_html. This fallback removes the need to expose
           service-account fields as PHP environment variables. */
        $candidates[] = dirname(dirname(__DIR__)) . '/firebase-private/firebase-service-account.json';

        $publicRoot = realpath(dirname(__DIR__));
        foreach (array_values(array_unique($candidates)) as $candidate) {
            $real = realpath((string)$candidate);
            if (!$real || !is_file($real) || !is_readable($real)) continue;
            if ($publicRoot && str_starts_with($real, $publicRoot . DIRECTORY_SEPARATOR)) continue;
            $json = json_decode((string)@file_get_contents($real), true);
            if (!is_array($json)) continue;
            if ($project === '') $project = trim((string)($json['project_id'] ?? ''));
            if ($email === '') $email = trim((string)($json['client_email'] ?? ''));
            if ($key === '') $key = (string)($json['private_key'] ?? '');
            if ($project !== '' && $email !== '' && $key !== '') break;
        }
    }

    $key = str_replace('\\n', "\n", $key);
    return [
        'enabled' => $project !== '' && $email !== '' && $key !== '',
        'project_id' => $project,
        'client_email' => $email,
        'private_key' => $key,
    ];
}'''

direct_send = r'''function mobile_v44_fcm_send_token(string $token, string $title, string $body, array $data): bool
{
    /* Prefer the local Node relay: it batches efficiently and keeps Google
       credential work out of a user-facing PHP request. If it is unavailable,
       fall back to direct FCM using the private service-account file. */
    if (function_exists('mobile_v44_push_relay_send')) {
        $relay = mobile_v44_push_relay_send($token, $title, $body, $data);
        if ($relay === true) return true;
    }

    $cfg = mobile_v44_fcm_private_config();
    if (!$cfg['enabled']) return false;
    $access = mobile_v44_fcm_access_token();
    if ($access === '') return false;
    $payload = [
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
        'https://fcm.googleapis.com/v1/projects/' . rawurlencode($cfg['project_id']) . '/messages:send',
        ['Authorization: Bearer ' . $access, 'Content-Type: application/json'],
        json_encode($payload, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE),
        6
    );
    if ($status >= 200 && $status < 300) return true;
    if ($status === 400 || $status === 404) {
        $upper = strtoupper($raw);
        if (str_contains($upper, 'UNREGISTERED') || str_contains($upper, 'REGISTRATION-TOKEN-NOT-REGISTERED')) {
            mobile_v44_push_tables();
            q('DELETE FROM mobile_push_tokens WHERE token=?', [$token]);
        }
    }
    return false;
}'''

bulk_helper = r'''
function mobile_v54_fcm_send_users(array $userIds, string $title, string $body, array $data): int
{
    mobile_v44_push_tables();
    $ids = array_values(array_unique(array_filter(array_map('intval', $userIds), static fn($id) => $id > 0)));
    if (!$ids) return 0;
    $ids = array_slice($ids, 0, 250);
    $ph = implode(',', array_fill(0, count($ids), '?'));
    $rows = fetch_all(
        "SELECT t.user_id,t.token FROM mobile_push_tokens t
          WHERE t.user_id IN ($ph)
            AND EXISTS(SELECT 1 FROM mobile_sessions s
                        WHERE s.token_hash=t.session_hash AND s.user_id=t.user_id AND s.expires_at>NOW())
          ORDER BY t.updated_at DESC LIMIT 500",
        $ids
    );
    $tokens = [];
    foreach ($rows as $row) {
        $token = trim((string)($row['token'] ?? ''));
        if ($token !== '') $tokens[$token] = true;
    }
    $tokens = array_keys($tokens);
    if (!$tokens) return 0;

    if (function_exists('mobile_v44_push_relay_config')) {
        $relay = mobile_v44_push_relay_config();
        if ($relay['enabled']) {
            [$status, $raw] = mobile_v44_http_post(
                $relay['url'],
                ['Authorization: Bearer ' . $relay['secret'], 'Content-Type: application/json'],
                json_encode(['tokens'=>$tokens,'title'=>$title,'body'=>$body,'data'=>$data], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE),
                6
            );
            if ($status >= 200 && $status < 300) {
                $decoded = json_decode($raw, true);
                $sent = is_array($decoded) ? max(0, (int)($decoded['sent'] ?? 0)) : 0;
                if ($sent > 0) return $sent;
            }
            /* A bad/missing relay must not make native notifications disappear.
               Continue with direct FCM below when private credentials exist. */
        }
    }

    $sent = 0;
    foreach ($tokens as $token) {
        if (mobile_v44_fcm_send_token($token, $title, $body, $data)) $sent++;
    }
    return $sent;
}

'''

for path in ('backend/api/mobile_realtime_push_v44.php', 'flutter/backend/api/mobile_realtime_push_v44.php'):
    text = r(path)
    text = replace_between(
        text,
        'function mobile_v44_fcm_private_config(): array',
        'function mobile_v44_http_post',
        private_config + '\n\n',
        f'{path} private Firebase config',
    )
    text = replace_between(
        text,
        'function mobile_v44_fcm_send_token(string $token, string $title, string $body, array $data): bool',
        'function mobile_v44_fcm_send_user',
        direct_send + '\n\n',
        f'{path} direct-first FCM sender',
    )
    marker = "if ($action === 'realtime_config') {"
    if 'function mobile_v54_fcm_send_users' not in text:
        text = once(text, marker, bulk_helper + marker, f'{path} bulk native push helper')
    if "if ($action === 'push_status')" not in text:
        status_action = r'''if ($action === 'push_status') {
    mobile_v44_push_tables();
    $relay = function_exists('mobile_v44_push_relay_config') ? mobile_v44_push_relay_config() : ['enabled'=>false];
    $direct = mobile_v44_fcm_private_config();
    $tokens = (int)fetch_col(
        "SELECT COUNT(*) FROM mobile_push_tokens t
          WHERE t.user_id=? AND EXISTS(SELECT 1 FROM mobile_sessions s
             WHERE s.token_hash=t.session_hash AND s.user_id=t.user_id AND s.expires_at>NOW())",
        [$uid]
    );
    mobile_out(['registered_tokens'=>$tokens,'direct_fcm'=>(bool)$direct['enabled'],'relay'=>(bool)($relay['enabled'] ?? false)]);
}

'''
        text = once(text, marker, status_action + marker, f'{path} push diagnostics')
    w(path, text)

for path in ('backend/api/chat_send.php', 'flutter/backend/api/chat_send.php'):
    text = r(path)
    if 'mobile_v54_fcm_send_users' not in text.split('$cid', 1)[0]:
        load_marker = "require_login();\n"
        loader = r'''require_login();

/* Load native FCM helpers as a library for both website and Android sends.
   Guard the action variable so this include cannot execute a mobile endpoint. */
if (!function_exists('mobile_v54_fcm_send_users') && is_file(__DIR__ . '/mobile_realtime_push_v44.php')) {
    $__tpAction = $action ?? null;
    $action = '__push_library__';
    require_once __DIR__ . '/mobile_realtime_push_v44.php';
    if ($__tpAction === null) unset($action); else $action = $__tpAction;
}
'''
        text = once(text, load_marker, loader, f'{path} FCM library load')
    send_marker = "json_out(['ok' => true, 'id' => $mid]);"
    if 'TaleemPK native FCM after every shared chat send' not in text:
        push_block = r'''/* TaleemPK native FCM after every shared chat send.
   This runs for website-origin and Android-origin messages, so a closed Android
   app no longer depends on the sender being another Android client. */
if (function_exists('mobile_v54_fcm_send_users')) {
    $nativeRecipients = [];
    foreach ($others as $o) {
        $rid = (int)($o['user_id'] ?? 0);
        if ($rid < 1) continue;
        $isMentioned = in_array($rid, $mentioned, true);
        if (!$isMentioned && (int)($o['is_muted'] ?? 0) === 1) continue;
        $nativeRecipients[] = $rid;
    }
    $nativeRecipients = array_values(array_unique($nativeRecipients));
    if ($nativeRecipients) {
        $nativeTitle = (($conv['type'] ?? '') === 'group' && trim((string)($conv['title'] ?? '')) !== '')
            ? trim((string)$conv['title']) : (string)current_user()['name'];
        if ($isEnc) {
            $nativeBody = 'New encrypted message';
        } elseif ($voiceSeconds > 0) {
            $nativeBody = 'Voice message';
        } elseif (!empty($att['name'])) {
            $nativeBody = 'Photo or attachment';
        } else {
            $nativeBody = mb_substr(trim(strip_tags($content)), 0, 140);
            if ($nativeBody === '') $nativeBody = 'New message';
        }
        try {
            mobile_v54_fcm_send_users($nativeRecipients, $nativeTitle, $nativeBody, [
                'event'=>'message',
                'conversation_id'=>(string)$cid,
                'message_id'=>(string)$mid,
            ]);
        } catch (Throwable $e) {
            /* Message persistence wins over notification delivery. */
        }
    }
}

'''
        text = once(text, send_marker, push_block + send_marker, f'{path} shared FCM push')
    w(path, text)


# ---------------------------------------------------------------------------
# 5) Release version + hard regression audit.
# ---------------------------------------------------------------------------
path = 'flutter/pubspec.yaml'
text = r(path)
text = re.sub(r'^version:\s*[^\n]+', 'version: 5.4.0+540', text, count=1, flags=re.M)
w(path, text)

mobile = r('backend/api/mobile.php')
mobile53 = r('backend/api/mobile_v53.php')
api = r('flutter/lib/core/api_client.dart')
chat = r('flutter/lib/screens/chat_screen.dart')
inbox = r('flutter/lib/screens/conversations_screen.dart')
shell = r('flutter/lib/screens/home_shell.dart')
push = r('flutter/lib/core/push_service.dart')
relay = r('backend/api/mobile_realtime_push_v44.php')
chat_send = r('backend/api/chat_send.php')
pubspec = r('flutter/pubspec.yaml')

assert "UPDATE users SET last_seen=NOW()" in mobile
assert "if ($action === 'heartbeat')" in mobile
assert 'LEFT JOIN conversation_members pcm' in mobile
assert 'SELECT u2.name FROM conversation_members' not in mobile
assert "type<>'message'" in mobile
assert "p.status='active' AND p.content LIKE ?" in mobile53
assert "Future<void> heartbeat()" in api
assert "_notifyChat(conversationId)" not in api
assert 'RealtimeService.instance.connected ? 10000 : 2500' in chat
assert 'pollTicks % 12 == 0' in chat
assert 'this.active=true' in inbox and 'Duration(seconds: 10)' in inbox
assert 'ConversationsScreen(active: index == 2)' in shell
assert 'final Set<int> mountedTabs = <int>{0};' in shell
assert 'pushTapSub=PushService.instance.conversationTaps.listen(_openPushedConversation);' in shell
assert 'final id = int.tryParse(payload.substring(5)) ?? 0;' in shell
assert 'mountedTabs.contains(1)' in shell and 'mountedTabs.contains(3)' in shell
assert 'Duration(seconds: 20)' in shell and 'Duration(seconds: 45)' in shell
assert 'ensureRegistered' in push and 'Timer? _retryTimer;' in push
assert 'firebase-private/firebase-service-account.json' in relay
assert 'function mobile_v54_fcm_send_users' in relay
assert 'Prefer the local Node relay' in relay and 'Continue with direct FCM below' in relay
assert 'TaleemPK native FCM after every shared chat send' in chat_send
assert 'version: 5.4.0+540' in pubspec
print('TaleemPK v5.4 deep performance, push and presence audit fixes applied successfully')
