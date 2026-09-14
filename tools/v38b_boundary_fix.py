from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source_path = ROOT / 'tools/v38_messenger_security_verification.py'
source = source_path.read_text(encoding='utf-8')

old = "emoji_end = text.find('  Future<void> _pickAttachment()', emoji_start)"
new = "emoji_end = text.find('  Widget _recordingBar()', emoji_start)"
if old not in source:
    raise RuntimeError('v3.8b could not find the old emoji boundary')
source = source.replace(old, new, 1)

# Execute the corrected v3.8 transformation without changing the checked-in
# base Flutter source. The recording/voice/outbox/send helpers immediately
# follow the emoji panel and must be preserved.
exec(
    compile(source, str(source_path), 'exec'),
    {'__file__': str(source_path), '__name__': '__main__'},
)

chat = (ROOT / 'flutter/lib/screens/chat_screen.dart').read_text(encoding='utf-8')
for required in [
    'Widget _recordingBar()',
    'Future<void> _sendText()',
    'Future<void> _syncAfterSend()',
    'bool get _chatBlocked',
    'Future<void> _flushOutbox()',
    'Future<void> _refreshOutboxCount()',
]:
    if required not in chat:
        raise RuntimeError(f'v3.8b lost required chat helper: {required}')
print('TaleemPK v3.8 emoji boundary fix applied successfully')
