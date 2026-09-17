from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def r(path):
    return (ROOT / path).read_text(encoding='utf-8')


def w(path, text):
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')


def once(text, old, new, label):
    if old not in text:
        raise RuntimeError(f'v3.4 missing target: {label}')
    return text.replace(old, new, 1)


def replace_in_function(text, signature, old, new, label):
    start = text.find(signature)
    if start < 0:
        raise RuntimeError(f'v3.4 missing function: {label}')
    brace = text.find('{', start)
    if brace < 0:
        raise RuntimeError(f'v3.4 malformed function: {label}')
    depth = 0
    end = None
    for index in range(brace, len(text)):
        char = text[index]
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                end = index + 1
                break
    if end is None:
        raise RuntimeError(f'v3.4 unterminated function: {label}')
    chunk = text[start:end]
    if old not in chunk:
        raise RuntimeError(f'v3.4 missing function target: {label}')
    chunk = chunk.replace(old, new, 1)
    return text[:start] + chunk + text[end:]


# Chat v3.4: keep the conversation feeling live while reducing needless work
# after the user has been idle. The first seconds stay faster than v3.3, then
# polling gradually relaxes. Any typing, recording, send or incoming presence
# immediately returns the loop to the fast cadence.
path = 'flutter/lib/screens/chat_screen.dart'
text = r(path)
text = once(
    text,
    '  int recordSeconds = 0, pollTicks = 0, queuedMessages = 0;\n',
    '  int recordSeconds = 0, pollTicks = 0, queuedMessages = 0, idlePolls = 0;\n',
    'idle poll counter',
)
text = once(
    text,
    """  void _schedulePoll({bool immediate = false}) {
    poll?.cancel();
    if (!mounted || !foreground) return;
    poll = Timer(
      Duration(milliseconds: immediate ? 80 : 1150),
      _poll,
    );
  }
""",
    """  void _schedulePoll({bool immediate = false}) {
    poll?.cancel();
    if (!mounted || !foreground) return;
    final composing = textController.text.trim().isNotEmpty;
    final active = recording ||
        sending ||
        composing ||
        presence?.active == true ||
        idlePolls < 10;
    final delayMs = active ? 850 : (idlePolls < 45 ? 1350 : 2100);
    poll = Timer(
      Duration(milliseconds: immediate ? 60 : delayMs),
      _poll,
    );
  }
""",
    'adaptive poll scheduler',
)
text = once(
    text,
    """      final fresh = result[0] as List<ChatMessage>;
      final p = result[1] as ChatPresence;
      var changed = false;
""",
    """      final fresh = result[0] as List<ChatMessage>;
      final p = result[1] as ChatPresence;
      if (fresh.isNotEmpty || p.active) {
        idlePolls = 0;
      } else if (idlePolls < 120) {
        idlePolls++;
      }
      var changed = false;
""",
    'idle activity accounting',
)
text = replace_in_function(
    text,
    '  void _typing() {',
    '    if (mounted) setState(() {});\n',
    '    idlePolls = 0;\n    if (mounted) setState(() {});\n',
    'typing activity reset',
)

# Successful sends used to call _load(), which cleared and rebuilt the whole
# thread, re-fetched pins and could visibly jump the list. Reuse the incremental
# sync path instead. It fetches only what changed and preserves rendered state.
marker = '  Future<void> _sendText() async {\n'
helper = """  Future<void> _syncAfterSend() async {
    idlePolls = 0;
    poll?.cancel();
    if (polling) {
      _schedulePoll(immediate: true);
      return;
    }
    await _poll();
    _toBottom();
  }

"""
text = once(text, marker, helper + marker, 'post-send incremental sync helper')
for signature, label in [
    ('  Future<void> _sendText() async {', 'text send refresh'),
    ('  Future<void> _uploadManyImages(List<String> paths) async {', 'multi-photo send refresh'),
    ('  Future<void> _upload(String path) async {', 'attachment send refresh'),
    ('  Future<void> _sendVoicePreview() async {', 'voice-note send refresh'),
]:
    text = replace_in_function(
        text,
        signature,
        '      await _load(jumpToBottom: true);',
        '      await _syncAfterSend();',
        label,
    )
w(path, text)

# Release version.
path = 'flutter/pubspec.yaml'
pubspec = r(path)
pubspec = re.sub(r'^version:\s*[^\n]+', 'version: 3.4.0+340', pubspec, count=1, flags=re.M)
w(path, pubspec)

# Regression guarantees for the generated build source.
chat = r('flutter/lib/screens/chat_screen.dart')
assert 'final delayMs = active ? 850 : (idlePolls < 45 ? 1350 : 2100);' in chat
assert 'Duration(milliseconds: immediate ? 60 : delayMs)' in chat
assert chat.count('await _syncAfterSend();') >= 4
assert 'Future<void> _syncAfterSend() async' in chat
assert 'final fullSync = pollTicks % 8 == 0;' in chat
assert 'recordingPaused = true;' in chat and 'await recorder.resume();' in chat
print('TaleemPK v3.4 adaptive chat runtime patch applied successfully')
