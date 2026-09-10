from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    p = ROOT / path
    return p, p.read_text(encoding='utf-8')


def save(p, text):
    p.write_text(text, encoding='utf-8')


def once(text, old, new, label):
    if old not in text:
        raise SystemExit(f'patch anchor missing: {label}')
    return text.replace(old, new, 1)


# ChatMessage.playedByOther must be mutable so normal presence polling can
# update an existing voice bubble without re-fetching the whole thread.
p, c = load('flutter/lib/core/models.dart')
c = once(
    c,
    "  final bool playedByMe, playedByOther, encrypted;",
    "  final bool playedByMe, encrypted;\n  bool playedByOther;",
    'mutable playedByOther',
)

old = """class ChatPresence {
  const ChatPresence({
    required this.active,
    required this.kind,
    required this.name,
    required this.readThrough,
  });
  final bool active;
  final String kind, name;
  final int readThrough;
  factory ChatPresence.fromJson(Map<String, dynamic> j) => ChatPresence(
    active: _bool(j['active']),
    kind: '${j['kind'] ?? ''}',
    name: '${j['name'] ?? ''}',
    readThrough: _int(j['read_through']),
  );
}
"""
new = """class ChatPresence {
  const ChatPresence({
    required this.active,
    required this.kind,
    required this.name,
    required this.readThrough,
    this.playedIds = const [],
  });
  final bool active;
  final String kind, name;
  final int readThrough;
  final List<int> playedIds;
  factory ChatPresence.fromJson(Map<String, dynamic> j) => ChatPresence(
    active: _bool(j['active']),
    kind: '${j['kind'] ?? ''}',
    name: '${j['name'] ?? ''}',
    readThrough: _int(j['read_through']),
    playedIds: _list(j['played']).map(_int).where((id) => id > 0).toList(),
  );
}
"""
c = once(c, old, new, 'ChatPresence played ids')
save(p, c)


# Update existing voice messages from the lightweight presence poll.
p, c = load('flutter/lib/screens/chat_screen.dart')
old = """      for (final message in messages) {
        if (message.mine && message.id <= p.readThrough) message.read = true;
      }
"""
new = """      final played = p.playedIds.toSet();
      for (final message in messages) {
        if (message.mine && message.id <= p.readThrough) message.read = true;
        if (message.mine &&
            message.voiceSeconds > 0 &&
            played.contains(message.id)) {
          message.playedByOther = true;
        }
      }
"""
c = once(c, old, new, 'live played receipt update')
save(p, c)


# Return recently played outgoing voice IDs together with typing/read state.
for path in ('flutter/backend/api/mobile.php', 'backend/api/mobile.php'):
    p, c = load(path)
    old = """    $readThrough = (int)fetch_col('SELECT COALESCE(MAX(last_read_id),0) FROM conversation_members WHERE conversation_id=? AND user_id<>?', [$cid,$uid]);
    mobile_out([
        'active'=>(bool)$other,
        'kind'=>$other ? (string)($other['typing_kind'] ?: 'text') : '',
        'name'=>$other ? (string)$other['name'] : '',
        'read_through'=>$readThrough,
    ]);
"""
    new = """    $readThrough = (int)fetch_col('SELECT COALESCE(MAX(last_read_id),0) FROM conversation_members WHERE conversation_id=? AND user_id<>?', [$cid,$uid]);
    $playedIds = [];
    if (table_exists('message_plays')) {
        $playedRows = fetch_all("SELECT DISTINCT m.id
                                   FROM messages m
                                   JOIN message_plays mp ON mp.message_id=m.id
                                  WHERE m.conversation_id=? AND m.sender_id=?
                                    AND mp.user_id<>? AND m.voice_seconds>0
                                  ORDER BY m.id DESC LIMIT 150", [$cid,$uid,$uid]);
        $playedIds = array_map(static fn(array $r): int => (int)$r['id'], $playedRows);
    }
    mobile_out([
        'active'=>(bool)$other,
        'kind'=>$other ? (string)($other['typing_kind'] ?: 'text') : '',
        'name'=>$other ? (string)$other['name'] : '',
        'read_through'=>$readThrough,
        'played'=>$playedIds,
    ]);
"""
    c = once(c, old, new, f'{path} presence played list')
    save(p, c)

print('Live voice played receipt patch applied.')
