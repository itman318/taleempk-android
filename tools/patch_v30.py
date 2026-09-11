from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]

def replace(path, old, new, count=1):
    p = ROOT / path
    text = p.read_text(encoding='utf-8')
    if old not in text:
        raise SystemExit(f'anchor missing in {path}: {old[:80]!r}')
    text = text.replace(old, new, count)
    p.write_text(text, encoding='utf-8')

# Version.
replace('flutter/pubspec.yaml', 'version: 2.9.0+290', 'version: 3.0.0+300')

# API: stable client tokens, persistent outbox retries, native privacy/security.
replace(
    'flutter/lib/core/api_client.dart',
    "  Future<void> sendText(int conversationId, String text, {int? replyTo}) =>\n      _request({\n        'action': 'send',\n        'conversation_id': '$conversationId',\n        'content': text,\n        'client_token': _clientToken(),\n        if (replyTo != null) 'reply_to': '$replyTo',\n      });",
    "  String newClientToken() => _clientToken();\n\n  Future<void> sendText(\n    int conversationId,\n    String text, {\n    int? replyTo,\n    String? clientToken,\n  }) =>\n      _request({\n        'action': 'send',\n        'conversation_id': '$conversationId',\n        'content': text,\n        'client_token': clientToken ?? _clientToken(),\n        if (replyTo != null) 'reply_to': '$replyTo',\n      });"
)
replace(
    'flutter/lib/core/api_client.dart',
    "  Future<void> updateProfile(\n    String name,\n    String city,\n    String headline,\n    String bio,\n  ) => _request({\n    'action': 'update_profile',\n    'name': name,\n    'city': city,\n    'headline': headline,\n    'bio': bio,\n  });",
    "  Future<void> updateProfile(\n    String name,\n    String city,\n    String headline,\n    String bio,\n  ) => _request({\n    'action': 'update_profile',\n    'name': name,\n    'city': city,\n    'headline': headline,\n    'bio': bio,\n  });\n\n  Future<Map<String, dynamic>> privacySettings() =>\n      _request({'action': 'privacy_get'});\n\n  Future<Map<String, dynamic>> updatePrivacySetting(\n    String key,\n    String value,\n  ) =>\n      _request({\n        'action': 'privacy_update',\n        'key': key,\n        'value': value,\n      });\n\n  Future<List<Map<String, dynamic>>> mobileSessions() async {\n    final data = await _request({'action': 'sessions'});\n    return _list(data['sessions']).map(_map).toList();\n  }\n\n  Future<void> revokeMobileSession(int id) => _request({\n        'action': 'session_revoke',\n        'id': '$id',\n      });\n\n  Future<void> changePassword(\n    String currentPassword,\n    String newPassword, {\n    bool signOutOthers = true,\n  }) =>\n      _request({\n        'action': 'change_password',\n        'current_password': currentPassword,\n        'new_password': newPassword,\n        'sign_out_others': signOutOthers ? '1' : '0',\n      });"
)

# Chat outbox.
replace(
    'flutter/lib/screens/chat_screen.dart',
    "import '../core/native_bridge.dart';\nimport '../core/theme.dart';",
    "import '../core/native_bridge.dart';\nimport '../core/outbox.dart';\nimport '../core/theme.dart';"
)
replace(
    'flutter/lib/screens/chat_screen.dart',
    "  final recorder = AudioRecorder();\n  final voicePreviewPlayer = AudioPlayer();",
    "  final recorder = AudioRecorder();\n  final voicePreviewPlayer = AudioPlayer();\n  final outbox = MessageOutbox();"
)
replace(
    'flutter/lib/screens/chat_screen.dart',
    "  int recordSeconds = 0, pollTicks = 0;",
    "  int recordSeconds = 0, pollTicks = 0, queuedMessages = 0;\n  bool flushingOutbox = false;"
)
replace(
    'flutter/lib/screens/chat_screen.dart',
    "    _loadRecentEmojis();\n    _load(jumpToBottom: true);",
    "    _loadRecentEmojis();\n    _refreshOutboxCount();\n    _load(jumpToBottom: true);"
)
replace(
    'flutter/lib/screens/chat_screen.dart',
    "    try {\n      pollTicks++;\n      final fullSync = pollTicks % 4 == 0;",
    "    try {\n      pollTicks++;\n      if (queuedMessages > 0 && pollTicks % 3 == 0) {\n        await _flushOutbox();\n      }\n      final fullSync = pollTicks % 4 == 0;"
)
replace(
    'flutter/lib/screens/chat_screen.dart',
    "          if (uploadProgress != null) _uploadBar(),",
    "          if (uploadProgress != null) _uploadBar(),\n          if (queuedMessages > 0 && selectedIds.isEmpty) _outboxBar(),"
)
old_send = """  Future<void> _sendText() async {
    if (_chatBlocked) return;
    final text = textController.text.trim();
    if (text.isEmpty) return;
    final currentReply = reply;
    setState(() => sending = true);
    textController.clear();
    setState(() => reply = null);
    try {
      await AppScope.of(context).api
          .sendText(widget.conversation.id, text, replyTo: currentReply?.id);
      await _load(jumpToBottom: true);
    } catch (e) {
      textController.text = text;
      if (mounted) showMessage(context, apiMessage(e));
    }
    if (mounted) setState(() => sending = false);
  }
"""
new_send = """  Future<void> _sendText() async {
    if (_chatBlocked) return;
    final text = textController.text.trim();
    if (text.isEmpty) return;
    final currentReply = reply;
    final api = AppScope.of(context).api;
    final token = api.newClientToken();
    setState(() => sending = true);
    textController.clear();
    setState(() => reply = null);
    try {
      await api.sendText(
        widget.conversation.id,
        text,
        replyTo: currentReply?.id,
        clientToken: token,
      );
      await _load(jumpToBottom: true);
    } catch (e) {
      if (e is ApiException && e.status == 0) {
        await outbox.enqueue(
          OutboxItem(
            token: token,
            conversationId: widget.conversation.id,
            text: text,
            replyTo: currentReply?.id,
            createdAt: DateTime.now().millisecondsSinceEpoch,
          ),
        );
        await _refreshOutboxCount();
        if (mounted) {
          showMessage(context, 'Message queued. It will send automatically when the connection returns.');
        }
      } else {
        textController.text = text;
        if (mounted) showMessage(context, apiMessage(e));
      }
    }
    if (mounted) setState(() => sending = false);
  }

  Future<void> _refreshOutboxCount() async {
    final count = await outbox.countForConversation(widget.conversation.id);
    if (mounted && count != queuedMessages) setState(() => queuedMessages = count);
  }

  Future<void> _flushOutbox() async {
    if (flushingOutbox || queuedMessages <= 0 || !mounted) return;
    flushingOutbox = true;
    try {
      final api = AppScope.of(context).api;
      final pending = await outbox.forConversation(widget.conversation.id);
      for (final item in pending) {
        try {
          await api.sendText(
            item.conversationId,
            item.text,
            replyTo: item.replyTo,
            clientToken: item.token,
          );
          await outbox.remove(item.token);
        } catch (e) {
          await outbox.updateAttempts(item.token, item.attempts + 1);
          if (e is ApiException && e.status != 0) {
            // A server-side rejection will not recover merely by retrying.
            break;
          }
          break;
        }
      }
    } finally {
      flushingOutbox = false;
      await _refreshOutboxCount();
    }
  }

  Widget _outboxBar() => Container(
        margin: const EdgeInsets.fromLTRB(10, 4, 10, 3),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
        decoration: BoxDecoration(
          color: AppColors.violet.withValues(alpha: .10),
          borderRadius: BorderRadius.circular(15),
          border: Border.all(color: AppColors.violet.withValues(alpha: .18)),
        ),
        child: Row(
          children: [
            const Icon(Icons.cloud_upload_outlined, size: 18, color: AppColors.violet),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                '$queuedMessages message${queuedMessages == 1 ? '' : 's'} waiting for connection',
                style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w800),
              ),
            ),
            TextButton(
              onPressed: flushingOutbox ? null : _flushOutbox,
              child: const Text('Retry'),
            ),
          ],
        ),
      );
"""
replace('flutter/lib/screens/chat_screen.dart', old_send, new_send)

# Profile routes to the native security center.
replace(
    'flutter/lib/screens/profile_screen.dart',
    "import 'module_screen.dart';",
    "import 'module_screen.dart';\nimport 'security_screen.dart';"
)
replace(
    'flutter/lib/screens/profile_screen.dart',
    "              'Privacy & security',\n              'Control profile and online visibility',\n              () => _privacy(context),",
    "              'Privacy & security',\n              'Privacy, password and signed-in devices',\n              () => Navigator.push(\n                context,\n                MaterialPageRoute(builder: (_) => const SecurityScreen()),\n              ),"
)

# Backend privacy/security actions.
backend = ROOT / 'flutter/backend/api/mobile.php'
text = backend.read_text(encoding='utf-8')
anchor = "$u = mobile_user();\n$uid = (int) $u['id'];\n\n/* Bridge the verified bearer identity"
if anchor not in text:
    raise SystemExit('backend auth bridge anchor missing')
block = r'''$u = mobile_user();
$uid = (int) $u['id'];

function mobile_privacy_snapshot(int $uid): array
{
    $row = fetch_one('SELECT profile_privacy,show_online,searchable,allow_dm,allow_comments,allow_calls,show_receipts FROM users WHERE id=? LIMIT 1', [$uid]);
    if (!$row) { mobile_error('This account is not available.', 404); }
    return [
        'profile_privacy' => (string) ($row['profile_privacy'] ?? 'public'),
        'show_online' => (int) ($row['show_online'] ?? 1) === 1,
        'searchable' => (int) ($row['searchable'] ?? 1) === 1,
        'allow_dm' => (string) ($row['allow_dm'] ?? 'everyone'),
        'allow_comments' => (string) ($row['allow_comments'] ?? 'everyone'),
        'allow_calls' => (string) ($row['allow_calls'] ?? 'everyone'),
        'show_receipts' => (int) ($row['show_receipts'] ?? 1) === 1,
    ];
}

if ($action === 'privacy_get') {
    mobile_out(mobile_privacy_snapshot($uid));
}

if ($action === 'privacy_update') {
    $key = strtolower(trim((string) ($_POST['key'] ?? '')));
    $value = strtolower(trim((string) ($_POST['value'] ?? '')));
    $choices = [
        'profile_privacy' => ['public','members','private'],
        'allow_dm' => ['everyone','following','followers','none'],
        'allow_comments' => ['everyone','following','followers','none'],
        'allow_calls' => ['everyone','following','followers','none'],
    ];
    $booleans = ['show_online','searchable','show_receipts'];
    if (isset($choices[$key])) {
        if (!in_array($value, $choices[$key], true)) { mobile_error('That privacy option is not valid.'); }
        q("UPDATE users SET {$key}=? WHERE id=?", [$value,$uid]);
    } elseif (in_array($key, $booleans, true)) {
        if (!in_array($value, ['0','1'], true)) { mobile_error('That privacy option is not valid.'); }
        q("UPDATE users SET {$key}=? WHERE id=?", [(int)$value,$uid]);
    } else {
        mobile_error('That privacy setting is not supported.');
    }
    log_activity($uid, 'privacy_update', 'Updated ' . $key . ' from Android app');
    mobile_out(mobile_privacy_snapshot($uid));
}

if ($action === 'sessions') {
    $currentHash = hash('sha256', mobile_bearer());
    $rows = fetch_all('SELECT id,token_hash,device_name,created_at,last_seen,expires_at FROM mobile_sessions WHERE user_id=? AND expires_at>NOW() ORDER BY created_at DESC LIMIT 20', [$uid]);
    $sessions = array_map(static function(array $row) use ($currentHash): array {
        return [
            'id' => (int) $row['id'],
            'device' => (string) ($row['device_name'] ?: 'Mobile device'),
            'created_at' => (string) ($row['created_at'] ?? ''),
            'last_seen' => (string) ($row['last_seen'] ?? $row['created_at'] ?? ''),
            'expires_at' => (string) ($row['expires_at'] ?? ''),
            'current' => hash_equals($currentHash, (string) $row['token_hash']),
        ];
    }, $rows);
    mobile_out(['sessions' => $sessions]);
}

if ($action === 'session_revoke') {
    $id = max(0, (int) ($_POST['id'] ?? 0));
    if ($id <= 0) { mobile_error('Choose a valid device session.'); }
    $row = fetch_one('SELECT id,token_hash FROM mobile_sessions WHERE id=? AND user_id=? LIMIT 1', [$id,$uid]);
    if (!$row) { mobile_error('That device session is no longer available.', 404); }
    if (hash_equals(hash('sha256', mobile_bearer()), (string) $row['token_hash'])) {
        mobile_error('Use Sign out to remove the current device.', 409);
    }
    delete_row('mobile_sessions', 'id=? AND user_id=?', [$id,$uid]);
    log_activity($uid, 'mobile_session_revoked', 'Revoked a mobile session from Android app');
    mobile_out(['revoked' => true]);
}

if ($action === 'change_password') {
    $current = (string) ($_POST['current_password'] ?? '');
    $next = (string) ($_POST['new_password'] ?? '');
    if ($current === '' || $next === '') { mobile_error('Enter your current and new password.'); }
    if (!password_verify($current, (string) ($u['password_hash'] ?? ''))) {
        mobile_error('Your current password is not correct.', 401);
    }
    [$passwordOk, $passwordReason] = password_quality($next, [
        'name' => (string) ($u['name'] ?? ''),
        'username' => (string) ($u['username'] ?? ''),
        'email' => (string) ($u['email'] ?? ''),
    ]);
    if (!$passwordOk) { mobile_error($passwordReason); }
    if (password_verify($next, (string) ($u['password_hash'] ?? ''))) {
        mobile_error('Choose a new password that is different from your current password.');
    }
    q('UPDATE users SET password_hash=? WHERE id=?', [password_hash($next, PASSWORD_DEFAULT),$uid]);
    if ((int) ($_POST['sign_out_others'] ?? 1) === 1) {
        $currentHash = hash('sha256', mobile_bearer());
        q('DELETE FROM mobile_sessions WHERE user_id=? AND token_hash<>?', [$uid,$currentHash]);
    }
    log_activity($uid, 'password_changed_mobile', 'Password changed from Android app');
    mobile_out(['message' => 'Password updated securely.']);
}

/* Bridge the verified bearer identity'''
text = text.replace(anchor, block, 1)
backend.write_text(text, encoding='utf-8')

# Keep deploy copy in sync with the app companion API.
shutil.copyfile(ROOT / 'flutter/backend/api/mobile.php', ROOT / 'backend/api/mobile.php')
