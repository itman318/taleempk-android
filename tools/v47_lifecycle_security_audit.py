from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding='utf-8')


def block_bounds(text: str, signature: str):
    start = text.find(signature)
    if start < 0:
        raise RuntimeError(f'v4.7 missing block: {signature}')
    brace = start + signature.rfind('{') if signature.rstrip().endswith('{') else text.find('{', start)
    if brace < 0:
        raise RuntimeError(f'v4.7 malformed block: {signature}')
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
    raise RuntimeError(f'v4.7 unterminated block: {signature}')


def patch_state(path: str, signature: str) -> None:
    text = read(path)
    start, end = block_bounds(text, signature)
    chunk = text[start:end]
    count = chunk.count('AppScope.of(context)')
    if count == 0:
        raise RuntimeError(f'v4.7 found no AppScope access in {signature}')
    chunk = chunk.replace('AppScope.of(context)', '_appState')
    opening = chunk.find('{') + 1
    cache = """
  AppState? _appStateCache;
  AppState get _appState => _appStateCache ??= AppScope.of(context);
"""
    chunk = chunk[:opening] + cache + chunk[opening:]
    text = text[:start] + chunk + text[end:]
    write(path, text)


states = {
    'flutter/lib/screens/auth_screen.dart':
        'class _AuthScreenState extends State<AuthScreen> {',
    'flutter/lib/screens/chat_screen.dart':
        'class _ChatScreenState extends State<ChatScreen> with WidgetsBindingObserver {',
    'flutter/lib/screens/conversations_screen.dart':
        'class _ConversationsScreenState extends State<ConversationsScreen>',
    'flutter/lib/screens/feed_screen.dart':
        'class _FeedScreenState extends State<FeedScreen>',
    'flutter/lib/screens/module_screen.dart':
        'class _ModuleScreenState extends State<ModuleScreen> {',
    'flutter/lib/screens/profile_screen.dart':
        'class _ProfileViewState extends State<_ProfileView>',
    'flutter/lib/screens/quiz_screen.dart':
        'class _QuizScreenState extends State<QuizScreen> {',
    'flutter/lib/screens/verification_screen.dart':
        'class _VerificationScreenState extends State<VerificationScreen> {',
}
for path, signature in states.items():
    patch_state(path, signature)


path = 'flutter/lib/screens/auth_screen.dart'
text = read(path)
text = text.replace(
"""        if (result.needsTwoFactor && result.challenge != null && mounted)
          await _showTwoFactor(result.challenge!);
""",
"""        if (result.needsTwoFactor && result.challenge != null && mounted) {
          await _showTwoFactor(result.challenge!);
        }
""",
)
text = text.replace(
"""      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(e.message)));
""",
"""      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(e.message)));
      }
""",
)
write(path, text)


for path in [
    'flutter/lib/screens/call_screen.dart',
    'flutter/lib/screens/chat_screen.dart',
    'flutter/lib/screens/conversations_screen.dart',
    'flutter/lib/screens/module_screen.dart',
    'flutter/lib/screens/profile_screen.dart',
]:
    text = read(path)
    text = re.sub(r'([,(]\s*)__+\b', r'\1_', text)
    write(path, text)

path = 'flutter/lib/screens/chat_screen.dart'
text = read(path)
text = text.replace(
"""                    onChanged: (value) {
                      if (value != null) setLocal(() => selected = value);
                    },
""",
"""                    onChanged: (value) {
                      if (value != null) {
                        setLocal(() => selected = value);
                      }
                    },
""",
)
text = text.replace(
"""  void _toBottom() => WidgetsBinding.instance.addPostFrameCallback((_) {
    if (scroll.hasClients)
      scroll.animateTo(
        scroll.position.maxScrollExtent,
        duration: const Duration(milliseconds: 240),
        curve: Curves.easeOut,
      );
  });
""",
"""  void _toBottom() => WidgetsBinding.instance.addPostFrameCallback((_) {
    if (scroll.hasClients) {
      scroll.animateTo(
        scroll.position.maxScrollExtent,
        duration: const Duration(milliseconds: 240),
        curve: Curves.easeOut,
      );
    }
  });
""",
)
text = text.replace(
"""                    return RadioListTile<int>(
                      value: id,
                      groupValue: selected,
                      onChanged: (v) => setLocal(() => selected = v ?? 0),
                      title: Text('${p['name'] ?? ''}'),
                      subtitle: Text('@${p['username'] ?? ''}'),
                    );
""",
"""                    return RadioGroup<int>(
                      groupValue: selected,
                      onChanged: (v) => setLocal(() => selected = v ?? 0),
                      child: RadioListTile<int>(
                        value: id,
                        title: Text('${p['name'] ?? ''}'),
                        subtitle: Text('@${p['username'] ?? ''}'),
                      ),
                    );
""",
)
write(path, text)


path = 'flutter/lib/screens/profile_screen.dart'
text = read(path)
text = re.sub(
    r'if \(image != null\) setModal\(\(\) => avatarPath = image\.path\);',
    """if (image != null && sheet.mounted) {
                             setModal(() => avatarPath = image.path);
                           }""",
    text,
    count=1,
)
text = re.sub(
    r'if \(image != null\) setModal\(\(\) => coverPath = image\.path\);',
    """if (image != null && sheet.mounted) {
                             setModal(() => coverPath = image.path);
                           }""",
    text,
    count=1,
)
write(path, text)

path = 'flutter/lib/screens/verification_screen.dart'
text = read(path)
text = text.replace(
"""                      onPick(result?.path);
""",
"""                      if (!context.mounted) return;
                      onPick(result?.files.single.path);
""",
)
write(path, text)


path = 'flutter/lib/core/api_client.dart'
text = read(path)
if "import 'dart:math';" not in text:
    text = text.replace("import 'dart:io';\n", "import 'dart:io';\nimport 'dart:math';\n", 1)
old = """  String _clientToken() =>
      '${DateTime.now().microsecondsSinceEpoch}_${_token?.substring(0, 8) ?? 'guest'}';
"""
new = """  String _clientToken() {
    final random = Random.secure();
    final bytes = List<int>.generate(
      24,
      (_) => random.nextInt(256),
      growable: false,
    );
    return base64UrlEncode(bytes).replaceAll('=', '');
  }
"""
if old not in text:
    raise RuntimeError('v4.7 client-token generator marker missing')
text = text.replace(old, new, 1)
write(path, text)


path = 'flutter/pubspec.yaml'
text = read(path)
text = re.sub(r'^version:\s*[^\n]+', 'version: 4.7.0+470', text, count=1, flags=re.M)
write(path, text)


api = read('flutter/lib/core/api_client.dart')
chat = read('flutter/lib/screens/chat_screen.dart')
profile = read('flutter/lib/screens/profile_screen.dart')
verification = read('flutter/lib/screens/verification_screen.dart')
assert '_token?.substring' + '(0, 8)' not in api
assert 'Random.secure()' in api and "base64UrlEncode(bytes)" in api
assert 'AppState get _appState' in chat
assert 'RadioGroup<int>' in chat
assert 'image != null && sheet.mounted' in profile
assert 'if (!context.mounted) return;' in verification
assert 'version: 4.7.0+470' in read('flutter/pubspec.yaml')
print('TaleemPK v4.7 lifecycle and security fixes applied successfully')
