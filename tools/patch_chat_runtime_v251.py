from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Remove obsolete quick-reaction dialog; the action sheet already renders reactions.
path = ROOT / 'flutter/lib/screens/chat_screen.dart'
s = path.read_text(encoding='utf-8')
start = s.find('  Future<void> _quickReaction(ChatMessage m) async {')
end = s.find('  Future<void> _showEditHistory(ChatMessage m) async {', start)
if start >= 0 and end > start:
    s = s[:start] + s[end:]
path.write_text(s, encoding='utf-8')

# Avoid rebuilding the inbox every 3 seconds when nothing actually changed.
path = ROOT / 'flutter/lib/screens/conversations_screen.dart'
s = path.read_text(encoding='utf-8')
old = '''      if (mounted && fresh.toString() != all.toString()) {
        setState(() => all = fresh);
      }
'''
new = '''      if (mounted && _conversationSignature(fresh) != _conversationSignature(all)) {
        setState(() => all = fresh);
      }
'''
if old in s:
    s = s.replace(old, new, 1)
marker = '  @override\n  Widget build(BuildContext context) {'
helper = '''  String _conversationSignature(List<Conversation> items) => items
      .map(
        (c) => '${c.id}|${c.unread}|${c.lastMessage}|${c.lastActivity}|'
            '${c.online}|${c.statusText}|${c.muted}|${c.archived}|'
            '${c.selfBlocked}|${c.blockedByOther}',
      )
      .join('\\n');

'''
if helper not in s:
    idx = s.find(marker)
    if idx < 0:
        raise RuntimeError('conversation build marker missing')
    s = s[:idx] + helper + s[idx:]
path.write_text(s, encoding='utf-8')

print('v2.5.1 cleanup applied')
