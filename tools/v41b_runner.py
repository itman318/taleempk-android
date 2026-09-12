from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
script_path = ROOT / 'tools' / 'v41_reply_media_viewonce.py'
source = script_path.read_text(encoding='utf-8')

# Put the view-once helpers after every import/directive. Later transforms add
# imports after call_screen.dart, so inserting declarations beside that import
# can produce `directive_after_declaration` in the generated Dart file.
old_helpers = '''import_marker = "import 'call_screen.dart';\\n"
helpers = r\'\'\'

bool _isViewOnceAttachmentName(String? value) =>
    value != null && value.startsWith('once__');

String _cleanAttachmentName(String? value) {
  final name = (value ?? '').trim();
  return name.startsWith('once__') ? name.substring(6) : name;
}
\'\'\'
if '_isViewOnceAttachmentName' not in text:
    text = once(text, import_marker, import_marker + helpers, 'view-once helpers')
'''
new_helpers = '''helpers = r\'\'\'

bool _isViewOnceAttachmentName(String? value) =>
    value != null && value.startsWith('once__');

String _cleanAttachmentName(String? value) {
  final name = (value ?? '').trim();
  return name.startsWith('once__') ? name.substring(6) : name;
}
\'\'\'
if '_isViewOnceAttachmentName' not in text:
    class_marker = 'class ChatScreen extends StatefulWidget {'
    text = once(text, class_marker, helpers + '\\n' + class_marker, 'view-once helpers')
'''
if old_helpers not in source:
    raise RuntimeError('v4.1b helper insertion source block missing')
source = source.replace(old_helpers, new_helpers, 1)

# No new reply navigation method is needed: TaleemPK already has a robust
# _jumpToMessage() used by pinned/search results. Reuse it from the quoted reply
# card instead of defining a duplicate method and extra message-key state.
source = source.replace(
    '''state_extra = """  final selectedIds = <int>{};
  final Map<int, GlobalKey> _messageKeys = <int, GlobalKey>{};
  Timer? _replyHighlightTimer;
  int? _replyHighlightId;
"""''',
    '''state_extra = """  final selectedIds = <int>{};
"""''',
    1,
)

start = source.find('# Dispose the reply highlight timer')
end = source.find('# Use a real GlobalKey', start)
if start < 0 or end < 0:
    raise RuntimeError('v4.1b reply-state cleanup boundary missing')
source = source[:start] + source[end:]

start = source.find('# Use a real GlobalKey')
end = source.find('# Replace the quoted/reply card.', start)
if start < 0 or end < 0:
    raise RuntimeError('v4.1b duplicate reply navigation boundary missing')
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

# Current VoiceBubble keeps its autoplay decision immediately after the
# handlingCompletion flag. Patch the v4.1 transform to preserve those lines
# while injecting view-once consumption state.
old_completion = """completion_marker = '  Future<void> _handleCompleted() async {\\n    if (handlingCompletion) return;\\n    handlingCompletion = true;\\n'\nif completion_marker not in voice_class:\n    raise RuntimeError('v4.1 voice completion marker missing')\nvoice_class = voice_class.replace(\n    completion_marker,\n    r'''  Future<void> _handleCompleted() async {\n    if (handlingCompletion) return;\n    handlingCompletion = true;\n    final consumeViewOnce = _isViewOnceAttachmentName(widget.message.attachmentName) &&\n        !widget.message.mine &&\n        !widget.message.playedByMe;\n''',\n    1,\n)\n"""
new_completion = """completion_marker = '  Future<void> _handleCompleted() async {\\n    if (handlingCompletion) return;\\n    handlingCompletion = true;\\n    final shouldContinue = activeVoice == this;\\n    if (shouldContinue) activeVoice = null;\\n'\nif completion_marker not in voice_class:\n    raise RuntimeError('v4.1 voice completion marker missing')\nvoice_class = voice_class.replace(\n    completion_marker,\n    r'''  Future<void> _handleCompleted() async {\n    if (handlingCompletion) return;\n    handlingCompletion = true;\n    final shouldContinue = activeVoice == this;\n    if (shouldContinue) activeVoice = null;\n    final consumeViewOnce = _isViewOnceAttachmentName(widget.message.attachmentName) &&\n        !widget.message.mine &&\n        !widget.message.playedByMe;\n''',\n    1,\n)\n"""
if old_completion not in source:
    raise RuntimeError('v4.1b completion source block missing')
source = source.replace(old_completion, new_completion, 1)

# The base app already owns one _jumpToMessage implementation. The v4.1 core
# assertions still expected the temporary GlobalKey implementation that this
# compatibility runner deliberately removes. Assert the behavior we keep.
old_asserts = """assert 'Future<void> _jumpToMessage(int messageId) async' in chat\nassert 'Scrollable.ensureVisible' in chat and 'key: _messageKey(m.id)' in chat\n"""
new_asserts = """assert chat.count('Future<void> _jumpToMessage(') == 1\nassert 'onTap: () => _jumpToMessage(r.id)' in chat\n"""
if old_asserts not in source:
    raise RuntimeError('v4.1b legacy reply assertions missing')
source = source.replace(old_asserts, new_asserts, 1)

code = compile(source, str(script_path), 'exec')
exec(code, {'__name__': '__main__', '__file__': str(script_path)})

# Final generated-source analyzer cleanup for code made obsolete by v4.1.
chat_path = ROOT / 'flutter/lib/screens/chat_screen.dart'
chat = chat_path.read_text(encoding='utf-8')
chat = chat.replace('url: original!.attachmentUrl!,', 'url: original.attachmentUrl!,')
legacy_icon = """  IconData _fileIcon(String? type) =>
      ['jpg', 'jpeg', 'png', 'gif', 'webp'].contains(type)
      ? Icons.image_rounded
      : type == 'pdf'
      ? Icons.picture_as_pdf_rounded
      : Icons.description_rounded;
"""
if legacy_icon in chat:
    chat = chat.replace(legacy_icon, '', 1)
chat_path.write_text(chat, encoding='utf-8')

assert chat.count('Future<void> _jumpToMessage(') == 1
assert 'onTap: () => _jumpToMessage(r.id)' in chat
assert '_messageKeys' not in chat
assert '_replyHighlightTimer' not in chat
assert '_fileIcon(String? type)' not in chat
print('TaleemPK v4.1 boundary/analyzer fixes applied successfully')
