from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
base = Path(__file__).with_name('v45b_runner.py')
exec(compile(base.read_text(encoding='utf-8'), str(base), 'exec'), {'__name__': '__main__', '__file__': str(base)})

# The premium profile header replacement must keep the role-aware verification
# helper originally introduced in v3.7 because lower profile cards still use it.
profile_path = ROOT / 'flutter/lib/screens/profile_screen.dart'
profile = profile_path.read_text(encoding='utf-8')
if 'Color _verificationColor(ProfileData p)' not in profile:
    marker = '  Widget _chip('
    if marker not in profile:
        raise RuntimeError('v4.5c profile chip marker missing')
    helper = r'''  Color _verificationColor(ProfileData p) {
    final kind = (p.verifiedKind.isNotEmpty ? p.verifiedKind : p.role).toLowerCase();
    if (kind.contains('admin')) return const Color(0xFFF59E0B);
    if (kind.contains('moderator')) return const Color(0xFF06B6D4);
    if (kind.contains('teacher')) return const Color(0xFF10B981);
    if (kind.contains('institute')) return const Color(0xFF8B5CF6);
    return const Color(0xFF3157E8);
  }

'''
    profile = profile.replace(marker, helper + marker, 1)
profile_path.write_text(profile, encoding='utf-8')

# Keep the existing Poll feature reachable from the redesigned attachment sheet.
# Its helper remains in ChatScreen, so removing the entry was both a regression
# and an analyzer warning.
chat_path = ROOT / 'flutter/lib/screens/chat_screen.dart'
chat = chat_path.read_text(encoding='utf-8')
if "title: 'Create poll'" not in chat:
    marker = r'''                    if (!viewOnce)
                      option(
                        icon: Icons.description_outlined,
                        color: AppColors.violet,
                        title: 'Document or file',
                        subtitle: 'Share a PDF, document or another supported file.',
                        onTap: () async {
                          Navigator.pop(sheet);
                          final file = await FilePicker.pickFile();
                          final filePath = file?.path;
                          if (filePath != null && mounted) await _upload(filePath);
                        },
                      ),
'''
    if marker not in chat:
        raise RuntimeError('v4.5c document attachment marker missing')
    poll = r'''                    if (!viewOnce)
                      option(
                        icon: Icons.poll_outlined,
                        color: AppColors.success,
                        title: 'Create poll',
                        subtitle: 'Ask a question and let members vote in chat.',
                        onTap: () {
                          Navigator.pop(sheet);
                          _createPoll();
                        },
                      ),
'''
    chat = chat.replace(marker, marker + poll, 1)
chat_path.write_text(chat, encoding='utf-8')

# Guard against repeating either regression in a later transform change.
profile = profile_path.read_text(encoding='utf-8')
chat = chat_path.read_text(encoding='utf-8')
assert 'Color _verificationColor(ProfileData p)' in profile
assert "title: 'Create poll'" in chat and '_createPoll();' in chat
print('TaleemPK v4.5 verification-color and poll regression fixes applied successfully')
