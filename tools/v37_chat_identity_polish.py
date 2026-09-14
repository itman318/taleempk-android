from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]

def r(path):
    return (ROOT / path).read_text(encoding='utf-8')

def w(path, text):
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')

# 1) Chat must cover the shell navigation completely. Any route that opens a
# ChatScreen from the conversations tab now uses the root navigator.
path = 'flutter/lib/screens/conversations_screen.dart'
text = r(path)
text, count = re.subn(
    r'Navigator\.push\(\s*context,\s*MaterialPageRoute\(builder:\s*\(_\)\s*=>\s*ChatScreen\(conversation:\s*([^\)]+)\)\),\s*\)',
    r'Navigator.of(context, rootNavigator: true).push(\n            MaterialPageRoute(builder: (_) => ChatScreen(conversation: \1)),\n          )',
    text,
    flags=re.S,
)
if count < 1:
    raise RuntimeError('v3.7 could not find ChatScreen navigation')
w(path, text)

# 2) Refine the composer and attachment progress so the thread feels like a
# dedicated messenger rather than a form field.
path = 'flutter/lib/screens/chat_screen.dart'
text = r(path)
composer_start = text.find('  Widget _composer() => Container(')
composer_end = text.find('  Future<void> _loadRecentEmojis()', composer_start)
if composer_start < 0 or composer_end < 0:
    raise RuntimeError('v3.7 composer boundary not found')
composer = r'''  Widget _composer() => Container(
    decoration: BoxDecoration(
      color: Theme.of(context).colorScheme.surface,
      border: Border(
        top: BorderSide(
          color: Theme.of(context).colorScheme.outlineVariant.withValues(alpha: .45),
        ),
      ),
      boxShadow: const [
        BoxShadow(
          color: Color(0x0C08142F),
          blurRadius: 14,
          offset: Offset(0, -3),
        ),
      ],
    ),
    padding: const EdgeInsets.fromLTRB(10, 8, 10, 10),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        SizedBox(
          width: 46,
          height: 46,
          child: IconButton.filledTonal(
            tooltip: 'Photo or file',
            onPressed: sending ? null : _pickAttachment,
            style: IconButton.styleFrom(
              backgroundColor: AppColors.blue.withValues(alpha: .10),
              foregroundColor: AppColors.blue,
            ),
            icon: const Icon(Icons.add_rounded, size: 26),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Container(
            decoration: BoxDecoration(
              color: Theme.of(context).brightness == Brightness.dark
                  ? const Color(0xFF121D2E)
                  : const Color(0xFFF7F9FC),
              borderRadius: BorderRadius.circular(24),
              border: Border.all(
                color: Theme.of(context).colorScheme.outlineVariant.withValues(alpha: .55),
              ),
            ),
            child: TextField(
              controller: textController,
              minLines: 1,
              maxLines: 6,
              maxLength: 4000,
              buildCounter: (
                _, {
                required currentLength,
                required isFocused,
                maxLength,
              }) => null,
              onTap: () => setState(() => showEmoji = false),
              style: TextStyle(
                fontSize: 15.5,
                height: 1.35,
                color: Theme.of(context).colorScheme.onSurface,
              ),
              decoration: InputDecoration(
                hintText: 'Write a message…',
                hintStyle: TextStyle(
                  color: Theme.of(context).colorScheme.onSurfaceVariant.withValues(alpha: .72),
                  fontSize: 15,
                ),
                isDense: true,
                filled: false,
                border: InputBorder.none,
                enabledBorder: InputBorder.none,
                focusedBorder: InputBorder.none,
                contentPadding: const EdgeInsets.fromLTRB(15, 12, 4, 12),
                suffixIconConstraints: const BoxConstraints(minWidth: 44, minHeight: 44),
                suffixIcon: IconButton(
                  tooltip: 'Emoji',
                  onPressed: () => setState(() => showEmoji = !showEmoji),
                  icon: Icon(
                    showEmoji ? Icons.keyboard_rounded : Icons.emoji_emotions_outlined,
                    color: showEmoji ? AppColors.blue : Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ),
            ),
          ),
        ),
        const SizedBox(width: 8),
        SizedBox(
          width: 48,
          height: 48,
          child: IconButton.filled(
            tooltip: textController.text.trim().isEmpty ? 'Voice message' : 'Send message',
            onPressed: sending
                ? null
                : (textController.text.trim().isEmpty
                      ? _toggleRecording
                      : _sendText),
            style: IconButton.styleFrom(
              backgroundColor: AppColors.blue,
              foregroundColor: Colors.white,
            ),
            icon: AnimatedSwitcher(
              duration: const Duration(milliseconds: 160),
              child: Icon(
                textController.text.trim().isEmpty
                    ? (recording ? Icons.stop_rounded : Icons.mic_rounded)
                    : Icons.send_rounded,
                key: ValueKey(textController.text.trim().isEmpty),
                size: 23,
              ),
            ),
          ),
        ),
      ],
    ),
  );

'''
text = text[:composer_start] + composer + text[composer_end:]

upload_start = text.find('  Widget _uploadBar() => Container(')
upload_end = text.find('  bool get _chatBlocked', upload_start)
if upload_start < 0 or upload_end < 0:
    raise RuntimeError('v3.7 upload indicator boundary not found')
upload = r'''  Widget _uploadBar() => Container(
    margin: const EdgeInsets.fromLTRB(10, 5, 10, 4),
    padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
    decoration: BoxDecoration(
      color: Theme.of(context).colorScheme.surface,
      borderRadius: BorderRadius.circular(16),
      border: Border.all(
        color: AppColors.blue.withValues(alpha: .18),
      ),
    ),
    child: Column(
      children: [
        Row(
          children: [
            Container(
              width: 34,
              height: 34,
              decoration: BoxDecoration(
                color: AppColors.blue.withValues(alpha: .10),
                borderRadius: BorderRadius.circular(11),
              ),
              child: const Icon(Icons.cloud_upload_rounded, size: 19, color: AppColors.blue),
            ),
            const SizedBox(width: 10),
            const Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Uploading photo / file', style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w900)),
                  SizedBox(height: 2),
                  Text('Keep this chat open until the upload finishes.', style: TextStyle(fontSize: 10.5, color: AppColors.muted)),
                ],
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: AppColors.blue.withValues(alpha: .10),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(
                '${(uploadProgress! * 100).round()}%',
                style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w900, color: AppColors.blue),
              ),
            ),
          ],
        ),
        const SizedBox(height: 9),
        ClipRRect(
          borderRadius: BorderRadius.circular(99),
          child: LinearProgressIndicator(value: uploadProgress, minHeight: 5),
        ),
      ],
    ),
  );

'''
text = text[:upload_start] + upload + text[upload_end:]

# Slightly tighten bubbles and thread rhythm while preserving all existing
# voice/reaction/read-state behaviour.
text = text.replace("margin: const EdgeInsets.only(bottom: 7),", "margin: const EdgeInsets.only(bottom: 6),", 1)
text = text.replace("padding: const EdgeInsets.fromLTRB(13, 10, 11, 7),", "padding: const EdgeInsets.fromLTRB(13, 9, 11, 7),", 1)
w(path, text)

# 3) Role-aware verification colours. TaleemPK roles are visually distinct in
# the web product; mirror that distinction in the native profile badge instead
# of rendering every verified account in the same blue.
path = 'flutter/lib/screens/profile_screen.dart'
text = r(path)
marker = '  Widget _stat(String value, String label) => Expanded(\n'
if marker not in text:
    raise RuntimeError('v3.7 profile helper marker missing')
helper = r'''  Color _verificationColor(ProfileData p) {
    final kind = (p.verifiedKind.isNotEmpty ? p.verifiedKind : p.role).toLowerCase();
    if (kind.contains('admin')) return const Color(0xFFF59E0B);
    if (kind.contains('moderator')) return const Color(0xFF06B6D4);
    if (kind.contains('teacher')) return const Color(0xFF10B981);
    if (kind.contains('institute')) return const Color(0xFF8B5CF6);
    return const Color(0xFF3157E8);
  }

'''
text = text.replace(marker, helper + marker, 1)
text = text.replace("decoration: const BoxDecoration(color: AppColors.blue, shape: BoxShape.circle),\n                      child: const Icon(Icons.verified_rounded, color: Colors.white, size: 19),",
                    "decoration: BoxDecoration(color: _verificationColor(p), shape: BoxShape.circle),\n                      child: const Icon(Icons.verified_rounded, color: Colors.white, size: 19),")
text = text.replace("const Icon(Icons.verified_rounded, color: AppColors.blue, size: 20)",
                    "Icon(Icons.verified_rounded, color: _verificationColor(p), size: 20)")
text = text.replace("const Icon(Icons.verified_rounded, color: AppColors.blue),",
                    "Icon(Icons.verified_rounded, color: _verificationColor(p)),")
w(path, text)

# 4) Sign-in alerts: browser HTTP libraries do not identify themselves like a
# browser, which caused 'Unknown device · Unknown browser'. Preserve the real
# model/Android label sent by the app and expose a stable mobile user-agent to
# the existing website sign-in parser before it records/sends the alert.
for path in ['backend/api/mobile.php', 'flutter/backend/api/mobile.php']:
    text = r(path)
    old = "function mobile_finish_login(array $u, string $device): void\n{\n    $signin = record_signin((int) $u['id']);"
    new = "function mobile_finish_login(array $u, string $device): void\n{\n    $safeDevice = preg_replace('/[^A-Za-z0-9 ._·\\-]/u', '', trim($device));\n    if ($safeDevice === '') { $safeDevice = 'Android device'; }\n    $_SERVER['HTTP_USER_AGENT'] = 'Mozilla/5.0 (Linux; Android; ' . $safeDevice . ') AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Mobile Safari/537.36 TaleemPKApp/3.7';\n    $signin = record_signin((int) $u['id']);"
    if old not in text:
        raise RuntimeError(f'v3.7 mobile sign-in target missing in {path}')
    text = text.replace(old, new, 1)
    w(path, text)

# Release version.
path = 'flutter/pubspec.yaml'
text = r(path)
text = re.sub(r'^version:\s*[^\n]+', 'version: 3.7.0+370', text, count=1, flags=re.M)
w(path, text)

# Regression assertions.
conv = r('flutter/lib/screens/conversations_screen.dart')
chat = r('flutter/lib/screens/chat_screen.dart')
profile = r('flutter/lib/screens/profile_screen.dart')
api_php = r('backend/api/mobile.php')
pubspec = r('flutter/pubspec.yaml')
assert 'rootNavigator: true' in conv
assert "hintText: 'Write a message…'" in chat
assert 'Uploading photo / file' in chat
assert 'ClipRRect' in chat and 'LinearProgressIndicator(value: uploadProgress' in chat
assert '_verificationColor(ProfileData p)' in profile
assert 'TaleemPKApp/3.7' in api_php
assert 'version: 3.7.0+370' in pubspec
print('TaleemPK v3.7 chat/identity polish applied successfully')
