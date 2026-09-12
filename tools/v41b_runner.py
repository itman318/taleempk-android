from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
script_path = ROOT / 'tools' / 'v41_reply_media_viewonce.py'
source = script_path.read_text(encoding='utf-8')

# Keep only the GlobalKey map; the original experimental visual highlight
# wrapper added a parent without a safe generated-source boundary.
source = source.replace(
    """state_extra = \"\"\"  final selectedIds = <int>{};
  final Map<int, GlobalKey> _messageKeys = <int, GlobalKey>{};
  Timer? _replyHighlightTimer;
  int? _replyHighlightId;
\"\"\"""",
    """state_extra = \"\"\"  final selectedIds = <int>{};
  final Map<int, GlobalKey> _messageKeys = <int, GlobalKey>{};
\"\"\"""",
    1,
)

# Remove the matching timer-dispose source patch.
start = source.find('# Dispose the reply highlight timer')
end = source.find('# Use a real GlobalKey', start)
if start < 0 or end < 0:
    raise RuntimeError('v4.1b dispose patch boundary missing')
source = source[:start] + source[end:]

# Reply navigation still scrolls precisely, but use haptic feedback rather than
# mutating the surrounding bubble layout.
source = source.replace(
    """    _replyHighlightTimer?.cancel();
    if (mounted) setState(() => _replyHighlightId = messageId);
    await Future<void>.delayed(const Duration(milliseconds: 30));
""",
    """    await Future<void>.delayed(const Duration(milliseconds: 30));
""",
    1,
)
source = source.replace(
    """    await reveal();
    _replyHighlightTimer = Timer(const Duration(milliseconds: 1500), () {
      if (mounted && _replyHighlightId == messageId) {
        setState(() => _replyHighlightId = null);
      }
    });
""",
    """    await reveal();
    unawaited(HapticFeedback.selectionClick());
""",
    1,
)

# Remove the experimental bubble wrapper source block entirely.
start = source.find('# Give the original bubble a brief visual cue')
end = source.find('# Replace the quoted/reply card.', start)
if start < 0 or end < 0:
    raise RuntimeError('v4.1b bubble wrapper boundary missing')
source = source[:start] + source[end:]

# Replace the fragile image-viewer branch search with a balanced-parentheses
# insertion immediately after the existing showDialog statement. This keeps all
# generated document/file opening behavior untouched.
start = source.find('# Mark a view-once photo consumed only after the full-screen viewer closes.')
end = source.find('# Add the view-once toggle to recorded voice preview.', start)
if start < 0 or end < 0:
    raise RuntimeError('v4.1b image viewer source boundary missing')
replacement = r'''# Mark a view-once photo consumed only after the existing image viewer closes.
os, oe = function_bounds(text, '  Future<void> _openAttachment(ChatMessage m) async {')
open_chunk = text[os:oe]
open_chunk = open_chunk.replace(
    '  Future<void> _openAttachment(ChatMessage m) async {\n    try {',
    """  Future<void> _openAttachment(ChatMessage m) async {
    final viewOnce = _isViewOnceAttachmentName(m.attachmentName);
    if (viewOnce && !m.mine && m.playedByMe) {
      if (mounted) showMessage(context, 'This view once photo has already been opened.');
      return;
    }
    try {""",
    1,
)
image_marker = '        await showDialog<void>('
dialog_start = open_chunk.find(image_marker)
if dialog_start < 0:
    raise RuntimeError('v4.1 image viewer marker missing')
paren = open_chunk.find('(', dialog_start)
if paren < 0:
    raise RuntimeError('v4.1 image viewer parenthesis missing')
depth = 0
quote = None
escape = False
dialog_end = None
for i in range(paren, len(open_chunk)):
    ch = open_chunk[i]
    if quote is not None:
        if escape:
            escape = False
        elif ch == '\\':
            escape = True
        elif ch == quote:
            quote = None
        continue
    if ch in ("'", '"'):
        quote = ch
        continue
    if ch == '(':
        depth += 1
    elif ch == ')':
        depth -= 1
        if depth == 0:
            semi = open_chunk.find(';', i)
            if semi >= 0:
                dialog_end = semi + 1
            break
if dialog_end is None:
    raise RuntimeError('v4.1 image viewer statement boundary missing')
consume_block = r"""
      if (viewOnce && !m.mine && !m.playedByMe) {
        try {
          await AppScope.of(context).api.markViewOnceConsumed(m.id);
          m.playedByMe = true;
          if (mounted) setState(() {});
        } catch (_) {}
      }
"""
open_chunk = open_chunk[:dialog_end] + consume_block + open_chunk[dialog_end:]
text = text[:os] + open_chunk + text[oe:]

'''
source = source[:start] + replacement + source[end:]

code = compile(source, str(script_path), 'exec')
exec(code, {'__name__': '__main__', '__file__': str(script_path)})

chat = (ROOT / 'flutter/lib/screens/chat_screen.dart').read_text(encoding='utf-8')
assert '_replyHighlightTimer' not in chat
assert '_replyHighlightId' not in chat
assert 'unawaited(HapticFeedback.selectionClick())' in chat
print('TaleemPK v4.1 boundary fixes applied successfully')
