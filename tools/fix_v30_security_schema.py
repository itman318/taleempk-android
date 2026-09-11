from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]

def replace(path, old, new, count=1):
    p = ROOT / path
    text = p.read_text(encoding='utf-8')
    if old not in text:
        raise SystemExit(f'anchor missing in {path}: {old[:120]!r}')
    p.write_text(text.replace(old, new, count), encoding='utf-8')

# Client uses the mobile-session token hash as a non-secret stable row identifier.
replace(
    'flutter/lib/core/api_client.dart',
    "  Future<void> revokeMobileSession(int id) => _request({\n        'action': 'session_revoke',\n        'id': '$id',\n      });",
    "  Future<void> revokeMobileSession(String sessionId) => _request({\n        'action': 'session_revoke',\n        'session_id': sessionId,\n      });",
)

# Match privacy dropdown values to the actual TaleemPK ENUM schema.
replace(
    'flutter/lib/screens/security_screen.dart',
    """              values: const {
                'everyone': 'Everyone',
                'following': 'People you follow',
                'followers': 'Followers',
                'none': 'Nobody',
              },
              onChanged: (v) => _savePrivacy('allow_dm', v),""",
    """              values: const {
                'everyone': 'Everyone',
                'following': 'People you follow',
                'nobody': 'Nobody',
              },
              onChanged: (v) => _savePrivacy('allow_dm', v),""",
)
replace(
    'flutter/lib/screens/security_screen.dart',
    """              values: const {
                'everyone': 'Everyone',
                'following': 'People you follow',
                'followers': 'Followers',
                'none': 'Nobody',
              },
              onChanged: (v) => _savePrivacy('allow_calls', v),""",
    """              values: const {
                'everyone': 'Everyone',
                'following': 'People you follow',
                'nobody': 'Nobody',
              },
              onChanged: (v) => _savePrivacy('allow_calls', v),""",
)
replace(
    'flutter/lib/screens/security_screen.dart',
    """              values: const {
                'everyone': 'Everyone',
                'following': 'People you follow',
                'followers': 'Followers',
                'none': 'Nobody',
              },
              onChanged: (v) => _savePrivacy('allow_comments', v),""",
    """              values: const {
                'everyone': 'Everyone',
                'followers': 'Followers',
                'nobody': 'Nobody',
              },
              onChanged: (v) => _savePrivacy('allow_comments', v),""",
)
# Add native typing privacy beside receipts.
needle = """            SwitchListTile.adaptive(
              contentPadding: EdgeInsets.zero,
              value: _bool(s['show_receipts'], true),
              onChanged: saving ? null : (v) => _savePrivacy('show_receipts', v ? '1' : '0'),
              title: const Text('Read & played receipts'),
              subtitle: const Text('Share message read and voice played status.'),
            ),"""
replace(
    'flutter/lib/screens/security_screen.dart',
    needle,
    needle + """
            SwitchListTile.adaptive(
              contentPadding: EdgeInsets.zero,
              value: _bool(s['show_typing'], true),
              onChanged: saving ? null : (v) => _savePrivacy('show_typing', v ? '1' : '0'),
              title: const Text('Typing & recording indicators'),
              subtitle: const Text('Share live typing and voice-recording presence.'),
            ),""",
)
replace(
    'flutter/lib/screens/security_screen.dart',
    "onPressed: () => _revokeSession(_int(session['id'])),",
    "onPressed: () => _revokeSession('${session['session_id'] ?? ''}'),",
)
replace(
    'flutter/lib/screens/security_screen.dart',
    "  Future<void> _revokeSession(int id) async {\n    if (id <= 0) return;",
    "  Future<void> _revokeSession(String sessionId) async {\n    if (sessionId.length != 64) return;",
)
replace(
    'flutter/lib/screens/security_screen.dart',
    "await AppScope.of(context).api.revokeMobileSession(id);",
    "await AppScope.of(context).api.revokeMobileSession(sessionId);",
)

# Correct security endpoints to the production schema: mobile_sessions is keyed by token_hash.
p = ROOT / 'flutter/backend/api/mobile.php'
text = p.read_text(encoding='utf-8')
text = text.replace(
    "SELECT profile_privacy,show_online,searchable,allow_dm,allow_comments,allow_calls,show_receipts FROM users",
    "SELECT profile_privacy,show_online,searchable,allow_dm,allow_comments,allow_calls,show_receipts,show_typing FROM users",
)
text = text.replace(
    "'show_receipts' => (int) ($row['show_receipts'] ?? 1) === 1,",
    "'show_receipts' => (int) ($row['show_receipts'] ?? 1) === 1,\n        'show_typing' => (int) ($row['show_typing'] ?? 1) === 1,",
)
text = text.replace(
    "'allow_dm' => ['everyone','following','followers','none'],\n        'allow_comments' => ['everyone','following','followers','none'],\n        'allow_calls' => ['everyone','following','followers','none'],",
    "'allow_dm' => ['everyone','following','nobody'],\n        'allow_comments' => ['everyone','followers','nobody'],\n        'allow_calls' => ['everyone','following','nobody'],",
)
text = text.replace(
    "$booleans = ['show_online','searchable','show_receipts'];",
    "$booleans = ['show_online','searchable','show_receipts','show_typing'];",
)
text = text.replace(
    "SELECT id,token_hash,device_name,created_at,last_seen,expires_at FROM mobile_sessions",
    "SELECT token_hash,device_name,created_at,last_seen,expires_at FROM mobile_sessions",
)
text = text.replace(
    "'id' => (int) $row['id'],\n            'device'",
    "'session_id' => (string) $row['token_hash'],\n            'device'",
)
old = """if ($action === 'session_revoke') {
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
}"""
new = """if ($action === 'session_revoke') {
    $sessionId = strtolower(trim((string) ($_POST['session_id'] ?? '')));
    if (!preg_match('/^[a-f0-9]{64}$/', $sessionId)) { mobile_error('Choose a valid device session.'); }
    $row = fetch_one('SELECT token_hash FROM mobile_sessions WHERE token_hash=? AND user_id=? LIMIT 1', [$sessionId,$uid]);
    if (!$row) { mobile_error('That device session is no longer available.', 404); }
    if (hash_equals(hash('sha256', mobile_bearer()), (string) $row['token_hash'])) {
        mobile_error('Use Sign out to remove the current device.', 409);
    }
    delete_row('mobile_sessions', 'token_hash=? AND user_id=?', [$sessionId,$uid]);
    log_activity($uid, 'mobile_session_revoked', 'Revoked a mobile session from Android app');
    mobile_out(['revoked' => true]);
}"""
if old not in text:
    raise SystemExit('session revoke backend anchor missing')
text = text.replace(old, new, 1)
p.write_text(text, encoding='utf-8')
shutil.copyfile(p, ROOT / 'backend/api/mobile.php')
