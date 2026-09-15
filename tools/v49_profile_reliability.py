"""Final, fail-fast patch over the existing v4.8 generation pipeline."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch(path, replacements):
    target = ROOT / path
    text = target.read_text(encoding='utf-8')
    for old, new in replacements:
        if old not in text:
            raise RuntimeError(f'v4.9 marker missing in {path}: {old[:90]}')
        text = text.replace(old, new, 1)
    target.write_text(text, encoding='utf-8')


patch('flutter/lib/screens/profile_screen.dart', [
    ("import '../widgets/common.dart';", "import '../widgets/common.dart';\nimport '../widgets/profile_identity.dart';"),
    ('  int activityBefore = 0;', '  int activityBefore = 0;\n  int _activitySerial = 0;\n  String? activityError;'),
    ('''                Row(
                  children: [
                    Expanded(
                      child: Text(
                        p.name,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontSize: 24,
                          fontWeight: FontWeight.w900,
                          letterSpacing: -.55,
                        ),
                      ),
                    ),
                    if (p.verified) ...[
                      const SizedBox(width: 6),
                      Icon(Icons.verified_rounded, color: _verificationColor(p), size: 20),
                    ],
                  ],
                ),''', '''                ProfileIdentity(
                  name: p.name,
                  verified: p.verified,
                  badgeColor: _verificationColor(p),
                ),'''),
    ('if (p == null || activityLoading || (!reset && !activityMore)) return;',
     '''if (!mounted || p == null || (!reset && (activityLoading || !activityMore))) return;
    final serial = ++_activitySerial;
    final requestedTab = tab;'''),
    ('      activityLoading = true;', '      activityLoading = true;\n      activityError = null;'),
    ('''      final page = await social.profileActivity(p.id, tab, before: activityBefore);
      if (!mounted) return;''', '''      final page = await social.profileActivity(p.id, requestedTab, before: activityBefore);
      if (!mounted || serial != _activitySerial || tab != requestedTab) return;'''),
    ('''    } catch (_) {
      // Header remains usable if a secondary activity tab is temporarily unavailable.
    } finally {
      if (mounted) setState(() => activityLoading = false);
    }''', '''    } catch (e) {
      if (mounted && serial == _activitySerial) {
        setState(() => activityError = apiMessage(e));
      }
    } finally {
      if (mounted && serial == _activitySerial) {
        setState(() => activityLoading = false);
      }
    }'''),
    ('''  Widget _activityList() {
''', '''  Widget _activityList() {
    if (activityError != null) {
      return ErrorView(
        message: activityError!,
        retry: () => _loadActivity(reset: true),
      );
    }
'''),
])

# Cache only within one API client and one signed-in session. Profile data
# includes viewer-dependent privacy, follow/block state and isMe permissions.
patch('flutter/lib/core/social_api.dart', [
    ('  static final Map<String, _CachedProfile> _profiles = {};', '''  static final _profileCaches = Expando<_SessionProfileCache>();
  Map<String, _CachedProfile> get _profiles {
    var cache = _profileCaches[api];
    if (cache == null || cache.token != api.token) {
      cache = _SessionProfileCache(api.token);
      _profileCaches[api] = cache;
    }
    return cache.entries;
  }'''),
    ('''    final body = <String, String>{...fields, 'access_token': api.token!};''', '''    final requestToken = api.token!;
    final body = <String, String>{...fields, 'access_token': requestToken};'''),
    ('return _decode(response.statusCode, response.bodyBytes);', 'return _decode(response.statusCode, response.bodyBytes, requestToken);'),
    ('''    } on TimeoutException {
      throw const ApiException('The server took too long''', '''    } on ApiException {
      rethrow;
    } on TimeoutException {
      throw const ApiException('The server took too long'''),
    ('''    final request = http.MultipartRequest('POST', _endpoint)''', '''    final requestToken = api.token!;
    final request = http.MultipartRequest('POST', _endpoint)'''),
    ("..fields.addAll({...fields, 'access_token': api.token!});", "..fields.addAll({...fields, 'access_token': requestToken});"),
    ('final bytes = await streamed.stream.toBytes();', 'final bytes = await streamed.stream.toBytes().timeout(const Duration(seconds: 120));'),
    ('return _decode(streamed.statusCode, bytes);', 'return _decode(streamed.statusCode, bytes, requestToken);'),
    ('''  Map<String, dynamic> _decode(int status, List<int> bytes) {''', '''  Map<String, dynamic> _decode(int status, List<int> bytes, String requestToken) {
    if (api.token != requestToken) {
      throw const ApiException('Your account changed. Please open this screen again.', status: 409);
    }'''),
    ('class _CachedProfile {', '''class _SessionProfileCache {
  _SessionProfileCache(this.token);
  final String? token;
  final Map<String, _CachedProfile> entries = {};
}

class _CachedProfile {'''),
])

patch('flutter/lib/core/api_client.dart', [
    ('    final requestFields = <String, String>{...fields};', '''    final requestToken = _token;
    final requestFields = <String, String>{...fields};'''),
    ('        expireSessionOn401: authenticated,', '        expireSessionOn401: authenticated,\n        requestToken: requestToken,'),
    ('    final file = File(filePath);', '    final requestToken = _token;\n    final file = File(filePath);'),
    ("    request.fields['access_token'] = _token!;", """    if (_token != requestToken) {
      throw const ApiException('Your account changed. Please open this screen again.', status: 409);
    }
    request.fields['access_token'] = requestToken!;"""),
    ('final bytes = await streamed.stream.toBytes();', 'final bytes = await streamed.stream.toBytes().timeout(const Duration(seconds: 90));'),
    ('        expireSessionOn401: true,', '        expireSessionOn401: true,\n        requestToken: requestToken,'),
    ('''    required bool expireSessionOn401,
  }) async {''', '''    required bool expireSessionOn401,
    String? requestToken,
  }) async {
    if (expireSessionOn401 && requestToken != _token) {
      throw const ApiException('Your account changed. Please open this screen again.', status: 409);
    }'''),
    ('''        // Some shared-hosting stacks finish a successful PHP mutation but
        // strip its tiny response body. Treat only a 2xx empty body as an
        // acknowledgement; the UI immediately refreshes from the read API.
        return <String, dynamic>{};''', '''        // An empty body is not confirmation that a mutation succeeded.
        // Text messages retain their idempotency key when queued for retry.
        throw const ApiException('The server did not confirm this request. Please try again.');'''),
])

patch('flutter/lib/widgets/common.dart', [
    ('''        backgroundImage: url == null ? null : CachedNetworkImageProvider(url!),
        child: url == null
            ? Text(
                name.isEmpty ? '?' : name.substring(0, 1).toUpperCase(),''', '''        foregroundImage: url == null || url!.trim().isEmpty
            ? null : CachedNetworkImageProvider(url!),
        onForegroundImageError: url == null || url!.trim().isEmpty
            ? null : (exception, stackTrace) {},
        child: Text(
                name.trim().isEmpty ? '?' : name.trim().characters.first.toUpperCase(),'''),
    ('''              )
            : null,
      ),''', '''              ),
      ),'''),
])

# Keep pending messages and drafts separate when accounts share one phone.
# Unscoped legacy entries cannot safely be assigned to the current account:
# leave them untouched instead of sending them as an arbitrary new owner.
patch('flutter/lib/core/outbox.dart', [
    ('''class MessageOutbox {
  static const _legacyKey = 'taleempk_chat_outbox_v3';
  static const _secureKey = 'taleempk_chat_outbox_secure_v4';''', '''class MessageOutbox {
  MessageOutbox({this.ownerId = 0});
  final int ownerId;
  String get _legacyKey => 'taleempk_chat_outbox_v49_$ownerId';
  String get _secureKey => 'taleempk_chat_outbox_secure_v49_$ownerId';
  static Future<void> _writes = Future<void>.value();

  Future<void> _mutate(Future<void> Function() operation) {
    final next = _writes.then((_) => operation());
    _writes = next.then<void>((_) {}, onError: (Object _, StackTrace stack) {});
    return next;
  }'''),
    ('  Future<void> enqueue(OutboxItem item) async {', '  Future<void> enqueue(OutboxItem item) => _mutate(() async {'),
    ('''    await _save(items);
  }

  Future<void> remove(String token) async {''', '''    await _save(items);
  });

  Future<void> remove(String token) => _mutate(() async {'''),
    ('''    await _save(items);
  }

  Future<void> updateAttempts(String token, int attempts) async {''', '''    await _save(items);
  });

  Future<void> updateAttempts(String token, int attempts) => _mutate(() async {'''),
    ('''    await _save(items);
  }

  Future<void> clearConversation(int conversationId) async {''', '''    await _save(items);
  });

  Future<void> clearConversation(int conversationId) => _mutate(() async {'''),
    ('''    await _save(items);
  }

  Future<void> _save''', '''    await _save(items);
  });

  Future<void> _save'''),
])

patch('flutter/lib/screens/chat_screen.dart', [
    ('  final outbox = MessageOutbox();', '''  late final int _ownerId = _appState.user?.id ?? 0;
  late final outbox = MessageOutbox(ownerId: _ownerId);'''),
    ("String get _draftKey => 'chat_draft_${widget.conversation.id}';", "String get _draftKey => 'chat_draft_v49_${_ownerId}_${widget.conversation.id}';"),
    ('    if (_chatBlocked) return;\n    final plainText', '    if (!mounted || sending || _chatBlocked) return;\n    final plainText'),
    ('''      } else {
        restoringDraft = true;
        textController.value''', '''      } else {
        if (!mounted) return;
        restoringDraft = true;
        textController.value'''),
    ('''      for (final item in pending) {
        try {''', '''      for (final item in pending) {
        if (!mounted || _appState.user?.id != _ownerId || api.token == null) break;
        try {'''),
])

# Sign-out must finish locally even when the server is unavailable.
patch('flutter/lib/core/app_state.dart', [
    ('''    await api.logout();
    bootstrap = null;
    status = AppStatus.signedOut;
    notifyListeners();''', '''    try {
      await api.logout();
    } catch (_) {
      // ApiClient.logout clears its local token in finally.
    } finally {
      bootstrap = null;
      error = null;
      status = AppStatus.signedOut;
      notifyListeners();
    }'''),
    ('''    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('dark_mode', darkMode);
    notifyListeners();''', '''    notifyListeners();
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool('dark_mode', darkMode);
    } catch (_) {
      // The theme still changes if preference storage is unavailable.
    }'''),
])

patch('flutter/lib/screens/security_screen.dart', [
    ('''  Future<void> _load() async {
''', '''  Future<void> _load() async {
    if (!mounted) return;
'''),
    ('''        sessions = result[1] as List<Map<String, dynamic>>;
      }
    } catch (e) {''', '''        sessions = result[1] as List<Map<String, dynamic>>;
      }
      blocked = await api.blockedUsers();
    } catch (e) {'''),
    ('Upload the TaleemPK v3.8 server update to public_html/api/',
     "Upload the matching server API files to your domain's active document root".replace("'", "\\'")),
    ('''                      onPressed: saving ? null : () async {
                        final id = int.tryParse('${user['id'] ?? 0}') ?? 0;
                        if (id <= 0) return;
                        try { await AppScope.of(context).api.toggleBlock(id); await _load(); }
                        catch (e) { if (mounted) showMessage(context, apiMessage(e)); }
                      },''', '''                      onPressed: saving ? null : () => _unblockUser(
                        int.tryParse('${user['id'] ?? 0}') ?? 0,
                      ),'''),
    ('  Widget _sessionsCard() => Card(', '''  Future<void> _unblockUser(int id) async {
    if (!mounted || saving || id <= 0) return;
    final api = AppScope.of(context).api;
    setState(() => saving = true);
    try {
      await api.toggleBlock(id);
      if (mounted) await _load();
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    } finally {
      if (mounted) setState(() => saving = false);
    }
  }

  Widget _sessionsCard() => Card('''),
])

patch('flutter/lib/screens/feed_screen.dart', [
    ('  int before = 0;', '  int before = 0;\n  int _feedSerial = 0;'),
    ('''  Future<void> _refresh() async {
''', '''  Future<void> _refresh() async {
    if (!mounted) return;
    final serial = ++_feedSerial;
    loadingMore = false;
'''),
    ('''      final page = await social.feed(tab: tab, subject: subject);
      if (!mounted) return;''', '''      final page = await social.feed(tab: tab, subject: subject);
      if (!mounted || serial != _feedSerial) return;'''),
    ('if (mounted) setState(() => error = apiMessage(e));',
     'if (mounted && serial == _feedSerial) setState(() => error = apiMessage(e));'),
    ('if (mounted) setState(() => loading = false);',
     'if (mounted && serial == _feedSerial) setState(() => loading = false);'),
    ('    if (loadingMore || !hasMore) return;',
     '    if (!mounted || loading || loadingMore || !hasMore) return;\n    final serial = _feedSerial;'),
    ('''      final page = await social.feed(tab: tab, subject: subject, before: before);
      if (!mounted) return;''', '''      final page = await social.feed(tab: tab, subject: subject, before: before);
      if (!mounted || serial != _feedSerial) return;'''),
    ('if (mounted) setState(() => loadingMore = false);',
     'if (mounted && serial == _feedSerial) setState(() => loadingMore = false);'),
])

patch('flutter/lib/screens/conversations_screen.dart', [
    ("import 'package:flutter/material.dart';", "import 'package:flutter/material.dart';\nimport 'package:flutter/scheduler.dart';"),
    ('  Timer? refreshTimer;', '  Timer? refreshTimer;\n  int _inboxSerial = 0;'),
    ('''  Future<void> _load() async {
''', '''  Future<void> _load() async {
    if (!mounted) return;
    final serial = ++_inboxSerial;
'''),
    ('''      all = await _appState.api.conversations(
        archived: archivedMode,
      );
    } catch (e) {
      error = apiMessage(e);
    }
    if (mounted) setState(() => loading = false);''', '''      final fresh = await _appState.api.conversations(archived: archivedMode);
      if (!mounted || serial != _inboxSerial) return;
      all = fresh;
    } catch (e) {
      if (!mounted || serial != _inboxSerial) return;
      error = apiMessage(e);
    }
    if (mounted && serial == _inboxSerial) setState(() => loading = false);'''),
    ('''    if (!mounted || loading || silentRefreshing) return;
    silentRefreshing = true;''', '''    if (!mounted || loading || silentRefreshing ||
        SchedulerBinding.instance.lifecycleState != AppLifecycleState.resumed) return;
    final serial = _inboxSerial;
    final archived = archivedMode;
    silentRefreshing = true;'''),
    ('''      if (mounted && _conversationSignature(fresh) != _conversationSignature(all)) {''', '''      if (mounted && !loading && serial == _inboxSerial && archived == archivedMode &&
          _conversationSignature(fresh) != _conversationSignature(all)) {'''),
])

patch('flutter/pubspec.yaml', [('version: 4.8.0+480', 'version: 4.9.0+490')])
print('TaleemPK v4.9 profile, account isolation and request reliability fixes applied')
