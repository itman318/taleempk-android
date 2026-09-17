from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding='utf-8')


def once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f'v4.8 missing marker: {label}')
    return text.replace(old, new, 1)


def block_bounds(text: str, signature: str):
    start = text.find(signature)
    if start < 0:
        raise RuntimeError(f'v4.8 missing block: {signature}')
    brace = start + signature.rfind('{') if signature.rstrip().endswith('{') else text.find('{', start)
    if brace < 0:
        raise RuntimeError(f'v4.8 malformed block: {signature}')
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
        if ch in ('"', "'"):
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
    raise RuntimeError(f'v4.8 unterminated block: {signature}')


def replace_block(text: str, signature: str, replacement: str) -> str:
    start, end = block_bounds(text, signature)
    return text[:start] + replacement + text[end:]


# Startup/session failures must always leave the splash/loading state.
path = 'flutter/lib/core/app_state.dart'
text = read(path)
start = r'''  Future<void> start() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      darkMode = prefs.getBool('dark_mode') ?? false;
    } catch (_) {
      darkMode = false;
    }

    try {
      final hasToken = await api.restoreSession();
      if (!hasToken) {
        status = AppStatus.signedOut;
        notifyListeners();
        return;
      }
      await refreshSession();
    } catch (_) {
      error = 'TaleemPK could not finish starting. Check your connection and try again.';
      status = AppStatus.offline;
      notifyListeners();
    }
  }'''
text = replace_block(text, '  Future<void> start() async {', start)
refresh = r'''  Future<void> refreshSession() async {
    status = AppStatus.loading;
    error = null;
    notifyListeners();
    try {
      bootstrap = await _bootstrapAfterAuth();
      status = AppStatus.signedIn;
    } on ApiException catch (e) {
      error = e.message;
      status = e.status == 401 ? AppStatus.signedOut : AppStatus.offline;
    } catch (_) {
      error = 'Your account data could not be loaded. Check your connection and try again.';
      status = AppStatus.offline;
    }
    notifyListeners();
  }'''
text = replace_block(text, '  Future<void> refreshSession() async {', refresh)
write(path, text)


# Offline messages contain private chat text. Secure storage is primary; the
# old preferences entry is migrated and retained only as a vendor fallback.
path = 'flutter/lib/core/outbox.dart'
text = read(path)
outbox = r'''class MessageOutbox {
  static const _legacyKey = 'taleempk_chat_outbox_v3';
  static const _secureKey = 'taleempk_chat_outbox_secure_v4';
  static final _storage = FlutterSecureStorage(aOptions: AndroidOptions());

  Future<List<OutboxItem>> all() async {
    final raw = await _readRaw();
    if (raw == null || raw.isEmpty) return <OutboxItem>[];
    try {
      final decoded = jsonDecode(raw);
      if (decoded is! List) return <OutboxItem>[];
      return decoded
          .whereType<Map>()
          .map((item) => OutboxItem.fromJson(item.cast<String, dynamic>()))
          .where((item) =>
              item.token.isNotEmpty &&
              item.conversationId > 0 &&
              item.text.trim().isNotEmpty)
          .toList()
        ..sort((a, b) => a.createdAt.compareTo(b.createdAt));
    } catch (_) {
      return <OutboxItem>[];
    }
  }

  Future<String?> _readRaw() async {
    try {
      final secure = await _storage
          .read(key: _secureKey)
          .timeout(const Duration(seconds: 3));
      if (secure != null && secure.isNotEmpty) return secure;
    } catch (_) {}

    try {
      final prefs = await SharedPreferences.getInstance();
      final legacy = prefs.getString(_legacyKey);
      if (legacy == null || legacy.isEmpty) return null;
      try {
        await _storage
            .write(key: _secureKey, value: legacy)
            .timeout(const Duration(seconds: 3));
        await prefs.remove(_legacyKey);
      } catch (_) {
        // Keep the legacy value only when secure storage is unavailable.
      }
      return legacy;
    } catch (_) {
      return null;
    }
  }

  Future<List<OutboxItem>> forConversation(int conversationId) async =>
      (await all())
          .where((item) => item.conversationId == conversationId)
          .toList();

  Future<int> countForConversation(int conversationId) async =>
      (await forConversation(conversationId)).length;

  Future<void> enqueue(OutboxItem item) async {
    final items = await all();
    final index = items.indexWhere((old) => old.token == item.token);
    if (index >= 0) {
      items[index] = item;
    } else {
      items.add(item);
    }
    await _save(items);
  }

  Future<void> remove(String token) async {
    final items = await all();
    items.removeWhere((item) => item.token == token);
    await _save(items);
  }

  Future<void> updateAttempts(String token, int attempts) async {
    final items = await all();
    final index = items.indexWhere((item) => item.token == token);
    if (index < 0) return;
    items[index] = items[index].copyWith(attempts: attempts);
    await _save(items);
  }

  Future<void> clearConversation(int conversationId) async {
    final items = await all();
    items.removeWhere((item) => item.conversationId == conversationId);
    await _save(items);
  }

  Future<void> _save(List<OutboxItem> items) async {
    final encoded = items.isEmpty
        ? null
        : jsonEncode(items.map((item) => item.toJson()).toList());
    try {
      if (encoded == null) {
        await _storage
            .delete(key: _secureKey)
            .timeout(const Duration(seconds: 3));
      } else {
        await _storage
            .write(key: _secureKey, value: encoded)
            .timeout(const Duration(seconds: 3));
      }
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_legacyKey);
      return;
    } catch (_) {
      // A few vendor keystores are unreliable; preserve offline delivery.
    }

    final prefs = await SharedPreferences.getInstance();
    if (encoded == null) {
      await prefs.remove(_legacyKey);
    } else {
      await prefs.setString(_legacyKey, encoded);
    }
  }
}'''
text = replace_block(text, 'class MessageOutbox {', outbox)
if "import 'package:flutter_secure_storage/flutter_secure_storage.dart';" not in text:
    text = once(
        text,
        "import 'package:shared_preferences/shared_preferences.dart';",
        "import 'package:flutter_secure_storage/flutter_secure_storage.dart';\nimport 'package:shared_preferences/shared_preferences.dart';",
        'outbox secure-storage import',
    )
write(path, text)


# Dark-mode contrast, accessible avatar rings, and non-stacking feedback.
path = 'flutter/lib/core/theme.dart'
text = read(path)
text = once(
    text,
    'color: light ? Colors.white : AppColors.navy,',
    'color: light\n                ? Colors.white\n                : Theme.of(context).colorScheme.onSurface,',
    'dark-aware brand name',
)
write(path, text)

path = 'flutter/lib/widgets/common.dart'
text = read(path)
text = once(
    text,
    'border: Border.all(color: Colors.white, width: 2.5),',
    'border: Border.all(\n                color: Theme.of(context).colorScheme.surface,\n                width: 2.5,\n              ),',
    'dark-aware online ring',
)
old_message = """void showMessage(BuildContext context, String text) =>
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));"""
new_message = """void showMessage(BuildContext context, String text) {
  final messenger = ScaffoldMessenger.of(context);
  messenger.hideCurrentSnackBar();
  messenger.showSnackBar(SnackBar(content: Text(text)));
}"""
text = once(text, old_message, new_message, 'single visible snackbar')
write(path, text)


# Remove the always-visible phantom notification dot. The generated dashboard
# already supplies its tooltip and theme-aware contrast.
path = 'flutter/lib/screens/home_screen.dart'
text = read(path)
text = once(
    text,
    "icon: const Badge(child: Icon(Icons.notifications_none_rounded, size: 21)),",
    "icon: const Icon(Icons.notifications_none_rounded, size: 21),",
    'notification icon',
)
write(path, text)


# Avoid unnecessary background traffic and overlapping WebRTC signal polls.
path = 'flutter/lib/screens/home_shell.dart'
text = read(path)
if "import 'package:flutter/scheduler.dart';" not in text:
    text = once(
        text,
        "import 'package:flutter/material.dart';",
        "import 'package:flutter/material.dart';\nimport 'package:flutter/scheduler.dart';",
        'scheduler import',
    )
text = once(
    text,
    'const Duration(seconds: 6),',
    'const Duration(seconds: 15),',
    'notification fallback interval',
)
text = once(
    text,
    '    if (!mounted || notificationBusy) return;',
    """    if (!mounted ||
        notificationBusy ||
        SchedulerBinding.instance.lifecycleState != AppLifecycleState.resumed) {
      return;
    }""",
    'notification lifecycle guard',
)
text = once(
    text,
    '    if (!mounted || activeIncomingId != 0) return;',
    """    if (!mounted ||
        activeIncomingId != 0 ||
        SchedulerBinding.instance.lifecycleState != AppLifecycleState.resumed) {
      return;
    }""",
    'call lifecycle guard',
)
write(path, text)

path = 'flutter/lib/screens/call_screen.dart'
text = read(path)
text = once(
    text,
    '  bool muted = false, cameraOff = false, speakerOn = false, ending = false;',
    '  bool muted = false, cameraOff = false, speakerOn = false, ending = false, pollBusy = false;',
    'call polling state',
)
start_pos, start_end = block_bounds(text, '  Future<void> _start() async {')
chunk = text[start_pos:start_end]
chunk = once(
    chunk,
    """    } catch (e) {
      if (mounted) {
        setState(() => status = apiMessage(e));
      }
    }""",
    """    } catch (e) {
      await _finishLocal();
      if (mounted) {
        setState(() => status = apiMessage(e));
      }
    }""",
    'failed-call media cleanup',
)
text = text[:start_pos] + chunk + text[start_end:]
poll_pos, poll_end = block_bounds(text, '  Future<void> _poll() async {')
chunk = text[poll_pos:poll_end]
chunk = once(
    chunk,
    '    if (callId <= 0 || ending || !mounted) return;',
    """    if (callId <= 0 || ending || !mounted || pollBusy) return;
    pollBusy = true;""",
    'overlapping call poll guard',
)
chunk = once(
    chunk,
    """    } catch (_) {
      // A single missed signalling poll should not tear down a live call.
    }""",
    """    } catch (_) {
      // A single missed signalling poll should not tear down a live call.
    } finally {
      pollBusy = false;
    }""",
    'call poll release',
)
text = text[:poll_pos] + chunk + text[poll_end:]
write(path, text)


path = 'flutter/pubspec.yaml'
text = read(path)
text = re.sub(r'^version:\s*[^\n]+', 'version: 4.8.0+480', text, count=1, flags=re.M)
write(path, text)


# Release-grade regression guarantees.
state = read('flutter/lib/core/app_state.dart')
outbox = read('flutter/lib/core/outbox.dart')
theme = read('flutter/lib/core/theme.dart')
common = read('flutter/lib/widgets/common.dart')
home = read('flutter/lib/screens/home_screen.dart')
shell = read('flutter/lib/screens/home_shell.dart')
calls = read('flutter/lib/screens/call_screen.dart')
pubspec = read('flutter/pubspec.yaml')
assert "TaleemPK could not finish starting" in state
assert "catch (_) {\n      error = 'Your account data could not be loaded." in state
assert 'taleempk_chat_outbox_secure_v4' in outbox
assert "FlutterSecureStorage(aOptions: AndroidOptions())" in outbox
assert 'await prefs.remove(_legacyKey);' in outbox
assert 'Theme.of(context).colorScheme.onSurface' in theme
assert 'messenger.hideCurrentSnackBar();' in common
assert "icon: const Icon(Icons.notifications_none_rounded, size: 21)" in home
assert 'SchedulerBinding.instance.lifecycleState' in shell
assert 'const Duration(seconds: 15)' in shell
assert 'pollBusy = true;' in calls and 'pollBusy = false;' in calls
assert 'await _finishLocal();' in calls
assert 'version: 4.8.0+480' in pubspec
print('TaleemPK v4.8 professional reliability, privacy and UI audit applied successfully')
