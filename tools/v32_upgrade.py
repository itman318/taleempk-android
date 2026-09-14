from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


def write(path, text):
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')


def replace_once(text, old, new, label):
    if old not in text:
        raise RuntimeError(f'v3.2 patch target missing: {label}')
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# Chat models: ciphertext/decrypted state plus sent/delivered/read watermarks.
# ---------------------------------------------------------------------------
path = 'flutter/lib/core/models.dart'
text = read(path)
text = replace_once(text,
"""    this.playedByMe = false,
    this.playedByOther = false,
    this.poll,
    this.encrypted = false,
    this.linkPreview,
""",
"""    this.playedByMe = false,
    this.playedByOther = false,
    this.delivered = false,
    this.poll,
    this.encrypted = false,
    this.ciphertext = '',
    this.decrypted = false,
    this.linkPreview,
""", 'ChatMessage constructor')
text = replace_once(text,
"""  final int id, senderId, voiceSeconds;
  final String sender, content, time, dateLabel, voiceWave;
  final String? attachmentUrl, attachmentName, attachmentType;
  final bool mine, deleted, edited, forwarded, starred, pinned, canEdit;
  final bool encrypted;
  bool playedByMe, playedByOther;
  bool read;
""",
"""  final int id, senderId, voiceSeconds;
  final String sender, time, dateLabel, voiceWave, ciphertext;
  String content;
  String? attachmentUrl, attachmentName, attachmentType;
  final bool mine, deleted, edited, forwarded, starred, pinned, canEdit;
  final bool encrypted;
  bool playedByMe, playedByOther, delivered, decrypted;
  bool read;
""", 'ChatMessage fields')
text = replace_once(text,
"""    read: _bool(j['read']),
    dateLabel: '${j['date_label'] ?? ''}',
""",
"""    read: _bool(j['read']),
    delivered: _bool(j['delivered']),
    dateLabel: '${j['date_label'] ?? ''}',
""", 'ChatMessage delivered json')
text = replace_once(text,
"""    encrypted: _bool(j['encrypted']),
    linkPreview: j['link_preview'] is Map
""",
"""    encrypted: _bool(j['encrypted']),
    ciphertext: '${j['ciphertext'] ?? ''}',
    decrypted: false,
    linkPreview: j['link_preview'] is Map
""", 'ChatMessage ciphertext json')
text = replace_once(text,
"""    required this.readThrough,
    this.playedIds = const [],
  });
  final bool active;
  final String kind, name;
  final int readThrough;
""",
"""    required this.readThrough,
    this.deliveredThrough = 0,
    this.playedIds = const [],
  });
  final bool active;
  final String kind, name;
  final int readThrough, deliveredThrough;
""", 'ChatPresence delivered field')
text = replace_once(text,
"""    readThrough: _int(j['read_through']),
    playedIds: _list(j['played']).map(_int).where((id) => id > 0).toList(),
""",
"""    readThrough: _int(j['read_through']),
    deliveredThrough: _int(j['delivered_through']),
    playedIds: _list(j['played']).map(_int).where((id) => id > 0).toList(),
""", 'ChatPresence delivered json')
write(path, text)


# ---------------------------------------------------------------------------
# API: encrypted message/file flags, explicit native mentions, block list.
# ---------------------------------------------------------------------------
path = 'flutter/lib/core/api_client.dart'
text = read(path)
old = """  Future<void> sendText(
    int conversationId,
    String text, {
    int? replyTo,
    String? clientToken,
  }) =>
      _request({
        'action': 'send',
        'conversation_id': '$conversationId',
        'content': text,
        'client_token': clientToken ?? _clientToken(),
        if (replyTo != null) 'reply_to': '$replyTo',
      });

  Future<void> sendFile(
    int conversationId,
    String filePath, {
    String field = 'attachment',
    int voiceSeconds = 0,
    String voiceWave = '',
    int? replyTo,
    void Function(double progress)? onProgress,
  }) async {
    final fields = <String, String>{
      'action': 'send',
      'conversation_id': '$conversationId',
      'content': '',
      'client_token': _clientToken(),
      if (voiceSeconds > 0) 'voice_seconds': '$voiceSeconds',
      if (voiceWave.isNotEmpty) 'voice_wave': voiceWave,
      if (replyTo != null) 'reply_to': '$replyTo',
    };
    await _multipart(fields, field, filePath, onProgress: onProgress);
  }
"""
new = """  Future<void> sendText(
    int conversationId,
    String text, {
    int? replyTo,
    String? clientToken,
    bool encrypted = false,
    List<int> mentionIds = const <int>[],
  }) =>
      _request({
        'action': 'send',
        'conversation_id': '$conversationId',
        'content': text,
        'client_token': clientToken ?? _clientToken(),
        if (replyTo != null) 'reply_to': '$replyTo',
        if (encrypted) 'enc': '1',
        if (mentionIds.isNotEmpty) 'mention_ids': mentionIds.join(','),
      });

  Future<void> sendFile(
    int conversationId,
    String filePath, {
    String field = 'attachment',
    int voiceSeconds = 0,
    String voiceWave = '',
    int? replyTo,
    String content = '',
    String? clientToken,
    bool encrypted = false,
    List<int> mentionIds = const <int>[],
    void Function(double progress)? onProgress,
  }) async {
    final fields = <String, String>{
      'action': 'send',
      'conversation_id': '$conversationId',
      'content': content,
      'client_token': clientToken ?? _clientToken(),
      if (voiceSeconds > 0) 'voice_seconds': '$voiceSeconds',
      if (voiceWave.isNotEmpty) 'voice_wave': voiceWave,
      if (replyTo != null) 'reply_to': '$replyTo',
      if (encrypted) 'enc_att': '1',
      if (encrypted && content.isNotEmpty) 'enc': '1',
      if (mentionIds.isNotEmpty) 'mention_ids': mentionIds.join(','),
    };
    await _multipart(fields, field, filePath, onProgress: onProgress);
  }
"""
text = replace_once(text, old, new, 'encrypted send API')
marker = """  Future<Map<String, dynamic>> toggleBlock(int userId) => _request({
    'action': 'block_user',
    'id': '$userId',
  });
"""
addition = marker + """

  Future<List<Map<String, dynamic>>> blockedUsers() async {
    final data = await _request({'action': 'blocked_users'});
    return _list(data['users']).map(_map).toList();
  }
"""
text = replace_once(text, marker, addition, 'blocked users API')
write(path, text)


# ---------------------------------------------------------------------------
# Mobile API: reciprocal delivery/read watermarks, ciphertext for native
# decryption, and native block-list management.
# ---------------------------------------------------------------------------
path = 'backend/api/mobile.php'
text = read(path)
old = "$readThrough = (int)fetch_col('SELECT COALESCE(MAX(last_read_id),0) FROM conversation_members WHERE conversation_id=? AND user_id<>?', [$cid,$uid]);"
new = """$readThrough = 0;
    $deliveredThrough = 0;
    $receiptRows = fetch_all("SELECT cm.last_read_id,cm.last_fetched_id,COALESCE(u.show_receipts,1) show_receipts
                                FROM conversation_members cm JOIN users u ON u.id=cm.user_id
                               WHERE cm.conversation_id=? AND cm.user_id<>?", [$cid,$uid]);
    if ((int)($u['show_receipts'] ?? 1) === 1 && $receiptRows) {
        $readThrough = PHP_INT_MAX;
        $deliveredThrough = PHP_INT_MAX;
        foreach ($receiptRows as $receiptRow) {
            if ((int)$receiptRow['show_receipts'] !== 1) { $readThrough=0; $deliveredThrough=0; break; }
            $readThrough = min($readThrough, (int)$receiptRow['last_read_id']);
            $deliveredThrough = min($deliveredThrough, (int)($receiptRow['last_fetched_id'] ?? 0));
        }
        if ($readThrough === PHP_INT_MAX) $readThrough = 0;
        if ($deliveredThrough === PHP_INT_MAX) $deliveredThrough = 0;
        $deliveredThrough = max($readThrough, $deliveredThrough);
    }"""
text = replace_once(text, old, new, 'presence receipt watermarks')
text = replace_once(text,
"""        'read_through'=>$readThrough,
        'played'=>$playedIds,
""",
"""        'read_through'=>$readThrough,
        'delivered_through'=>$deliveredThrough,
        'played'=>$playedIds,
""", 'presence delivered response')
text = replace_once(text,
"""    if ($newest) {
        q('UPDATE conversation_members SET last_read_id=GREATEST(last_read_id,?),unread_count=0 WHERE conversation_id=? AND user_id=?', [$newest,$cid,$uid]);
    }
    $otherReadThrough = (int) fetch_col(
        'SELECT COALESCE(MAX(last_read_id),0) FROM conversation_members WHERE conversation_id=? AND user_id<>?',
        [$cid,$uid]
    );
""",
"""    if ($newest) {
        q('UPDATE conversation_members SET last_fetched_id=GREATEST(last_fetched_id,?),last_read_id=GREATEST(last_read_id,?),unread_count=0 WHERE conversation_id=? AND user_id=?', [$newest,$newest,$cid,$uid]);
    }
    $otherReadThrough = 0;
    $otherFetchedThrough = 0;
    $receiptRows = fetch_all("SELECT cm.last_read_id,cm.last_fetched_id,COALESCE(u.show_receipts,1) show_receipts
                                FROM conversation_members cm JOIN users u ON u.id=cm.user_id
                               WHERE cm.conversation_id=? AND cm.user_id<>?", [$cid,$uid]);
    if ((int)($u['show_receipts'] ?? 1) === 1 && $receiptRows) {
        $otherReadThrough = PHP_INT_MAX;
        $otherFetchedThrough = PHP_INT_MAX;
        foreach ($receiptRows as $receiptRow) {
            if ((int)$receiptRow['show_receipts'] !== 1) { $otherReadThrough=0; $otherFetchedThrough=0; break; }
            $otherReadThrough=min($otherReadThrough,(int)$receiptRow['last_read_id']);
            $otherFetchedThrough=min($otherFetchedThrough,(int)($receiptRow['last_fetched_id']??0));
        }
        if ($otherReadThrough===PHP_INT_MAX) $otherReadThrough=0;
        if ($otherFetchedThrough===PHP_INT_MAX) $otherFetchedThrough=0;
        $otherFetchedThrough=max($otherReadThrough,$otherFetchedThrough);
    }
""", 'messages receipt watermarks')
text = replace_once(text,
"""    $items = array_reverse(array_map(static function(array $m) use ($uid, $otherReadThrough, $reactionMap, $pollMap): array {
        $mine = (int)$m['sender_id']===$uid;
        $read = $mine && $otherReadThrough >= (int) $m['id'];
""",
"""    $items = array_reverse(array_map(static function(array $m) use ($uid, $otherReadThrough, $otherFetchedThrough, $reactionMap, $pollMap): array {
        $mine = (int)$m['sender_id']===$uid;
        $read = $mine && $otherReadThrough >= (int) $m['id'];
        $delivered = $mine && $otherFetchedThrough >= (int) $m['id'];
""", 'message map receipt closure')
text = replace_once(text,
"""            'content'=>$deleted ? 'This message was deleted.'
                : ($encrypted ? 'Encrypted message' : (string)($m['content'] ?? '')),
            'encrypted'=>$encrypted, 'link_preview'=>$preview,
""",
"""            'content'=>$deleted ? 'This message was deleted.'
                : ($encrypted ? 'Encrypted message' : (string)($m['content'] ?? '')),
            'ciphertext'=>$encrypted && !$deleted ? (string)($m['content'] ?? '') : '',
            'encrypted'=>$encrypted, 'delivered'=>$delivered, 'link_preview'=>$preview,
""", 'ciphertext message payload')

insert_before = "if ($action === 'notification_peek') {"
blocked = """if ($action === 'blocked_users') {
    $rows = fetch_all("SELECT u.id,u.name,u.username,u.avatar,u.role,u.is_verified
                         FROM blocks b JOIN users u ON u.id=b.blocked_id
                        WHERE b.user_id=? ORDER BY u.name LIMIT 200", [$uid]);
    mobile_out(['users'=>array_map(static function(array $row): array {
        return ['id'=>(int)$row['id'],'name'=>(string)$row['name'],'username'=>(string)$row['username'],
                'avatar'=>!empty($row['avatar'])?upload_url((string)$row['avatar']):null,
                'role'=>(string)$row['role'],'verified'=>(int)$row['is_verified']===1];
    }, $rows)]);
}

"""
if insert_before not in text:
    raise RuntimeError('v3.2 patch target missing: blocked users insert')
text = text.replace(insert_before, blocked + insert_before, 1)
write(path, text)
shutil.copy2(ROOT / path, ROOT / 'flutter/backend/api/mobile.php')


# ---------------------------------------------------------------------------
# Chat screen: native E2EE, encrypted media, delivery ticks, mentions,
# improved emoji picker and photo editor.
# ---------------------------------------------------------------------------
path = 'flutter/lib/screens/chat_screen.dart'
text = read(path)
text = replace_once(text,
"""import '../core/api_client.dart';
import '../core/models.dart';
""",
"""import '../core/api_client.dart';
import '../core/e2ee_service.dart';
import '../core/models.dart';
""", 'E2EE import')
text = replace_once(text,
"""  String searchQuery = '', emojiCategory = 'Recent';
  final selectedIds = <int>{};
  final voiceLevels = <double>[];
  List<String> recentEmojis = <String>[];
  List<Map<String, dynamic>> pinnedMessages = const [];
""",
"""  String searchQuery = '', emojiCategory = 'Recent', emojiSearch = '', skinTone = '';
  final selectedIds = <int>{};
  final voiceLevels = <double>[];
  List<String> recentEmojis = <String>[];
  List<Map<String, dynamic>> pinnedMessages = const [];
  List<Map<String, dynamic>> mentionMembers = const [];
  E2eeService? _e2eeService;
  E2eeThreadState e2eeState = const E2eeThreadState(state: 'off');
  bool e2eeLoading = false;

  E2eeService get e2ee => _e2eeService ??= E2eeService(
        AppScope.of(context).api,
        AppScope.of(context).user?.id ?? 0,
      );
""", 'chat E2EE state')
text = replace_once(text,
"""    _loadRecentEmojis();
    _refreshOutboxCount();
    _load(jumpToBottom: true);
""",
"""    _loadRecentEmojis();
    _refreshOutboxCount();
    if (widget.conversation.isGroup) unawaited(_loadMentionMembers());
    _load(jumpToBottom: true);
    unawaited(_refreshEncryptionState());
""", 'chat init encryption')
text = replace_once(text,
"""      if (jumpToBottom) _toBottom();
""",
"""      unawaited(_decryptEncryptedTextMessages());
      if (jumpToBottom) _toBottom();
""", 'decrypt after load')
text = replace_once(text,
"""        if (message.mine && message.id <= p.readThrough && !message.read) {
          message.read = true;
          changed = true;
        }
""",
"""        if (message.mine && message.id <= p.deliveredThrough && !message.delivered) {
          message.delivered = true;
          changed = true;
        }
        if (message.mine && message.id <= p.readThrough && !message.read) {
          message.read = true;
          message.delivered = true;
          changed = true;
        }
""", 'delivery polling')
text = replace_once(text,
"""            if (old.mine && old.read) candidate.read = true;
            if (old.mine && old.playedByOther) {
""",
"""            if (old.mine && old.read) candidate.read = true;
            if (old.mine && old.delivered) candidate.delivered = true;
            if (old.decrypted) {
              candidate.decrypted = true;
              candidate.content = old.content;
              candidate.attachmentUrl = old.attachmentUrl;
              candidate.attachmentName = old.attachmentName;
              candidate.attachmentType = old.attachmentType;
            }
            if (old.mine && old.playedByOther) {
""", 'preserve decrypted/full sync')
text = text.replace("_threadHasEncryptedMessages\n                                      ? 'End-to-end encrypted on web'\n                                      : 'End-to-end encryption'",
                    "e2eeState.enabled\n                                      ? 'End-to-end encrypted'\n                                      : (e2eeState.locked ? 'Encryption locked' : 'End-to-end encryption')")
text = replace_once(text,
"""            if (m.encrypted && !m.deleted)
              _encryptedBubble(m)
""",
"""            if (m.encrypted && !m.deleted && !m.decrypted)
              _encryptedBubble(m)
""", 'encrypted bubble gate')
text = replace_once(text,
"""                  Icon(
                    m.read ? Icons.done_all_rounded : Icons.check_rounded,
                    size: 15,
                    color: m.read ? const Color(0xFF75E9FF) : Colors.white70,
                  ),
""",
"""                  Icon(
                    m.read
                        ? Icons.done_all_rounded
                        : (m.delivered ? Icons.done_all_rounded : Icons.check_rounded),
                    size: 15,
                    color: m.read ? const Color(0xFF75E9FF) : Colors.white70,
                  ),
""", 'three-state delivery ticks')

# Local-file aware image/attachment rendering.
text = replace_once(text,
"""            if (image)
              ClipRRect(
                borderRadius: BorderRadius.circular(13),
                child: SecureChatImage(
                  api: AppScope.of(context).api,
                  url: m.attachmentUrl!,
                  mine: m.mine,
                ),
              )
""",
"""            if (image)
              ClipRRect(
                borderRadius: BorderRadius.circular(13),
                child: m.attachmentUrl!.startsWith('file://')
                    ? Image.file(
                        File(Uri.parse(m.attachmentUrl!).toFilePath()),
                        width: 240,
                        height: 190,
                        fit: BoxFit.cover,
                      )
                    : SecureChatImage(
                        api: AppScope.of(context).api,
                        url: m.attachmentUrl!,
                        mine: m.mine,
                      ),
              )
""", 'local decrypted image rendering')
text = replace_once(text,
"""      final bytes = await AppScope.of(context).api
          .attachmentBytes(m.attachmentUrl!);
""",
"""      final bytes = m.attachmentUrl!.startsWith('file://')
          ? await File(Uri.parse(m.attachmentUrl!).toFilePath()).readAsBytes()
          : await AppScope.of(context).api.attachmentBytes(m.attachmentUrl!);
""", 'local attachment open')

# Replace the locked web-only encrypted message bubble with native unlock.
text = re.sub(
    r"  Widget _encryptedBubble\(ChatMessage message\) => InkWell\(.*?\n  \);\n\n  Widget _linkPreview",
    """  Widget _encryptedBubble(ChatMessage message) => InkWell(
    borderRadius: BorderRadius.circular(12),
    onTap: () => _unlockEncryptedMessage(message),
    child: Container(
      padding: const EdgeInsets.all(11),
      decoration: BoxDecoration(
        color: (message.mine ? Colors.white : AppColors.success).withValues(alpha: .12),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: (message.mine ? Colors.white : AppColors.success).withValues(alpha: .18),
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            e2eeState.locked ? Icons.lock_clock_rounded : Icons.lock_rounded,
            size: 18,
            color: message.mine ? Colors.white : AppColors.success,
          ),
          const SizedBox(width: 8),
          Flexible(
            child: Text(
              e2eeState.locked
                  ? 'Encrypted message · tap to unlock this device'
                  : 'End-to-end encrypted · tap to open securely',
              style: TextStyle(
                fontSize: 12,
                height: 1.35,
                fontWeight: FontWeight.w700,
                color: message.mine ? Colors.white : Theme.of(context).colorScheme.onSurface,
              ),
            ),
          ),
        ],
      ),
    ),
  );

  Widget _linkPreview""",
    text,
    count=1,
    flags=re.S,
)

# Composer with native @mention suggestions.
text = re.sub(
    r"  Widget _composer\(\) => Container\(.*?\n  \);\n\n  Future<void> _loadRecentEmojis",
    """  Widget _composer() {
    final suggestions = _mentionSuggestions();
    return Container(
      color: Theme.of(context).colorScheme.surface,
      padding: const EdgeInsets.fromLTRB(8, 5, 8, 9),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (suggestions.isNotEmpty)
            SizedBox(
              height: 48,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                itemCount: suggestions.length,
                separatorBuilder: (_, _) => const SizedBox(width: 7),
                itemBuilder: (_, i) {
                  final member = suggestions[i];
                  return ActionChip(
                    avatar: const Icon(Icons.alternate_email_rounded, size: 16),
                    label: Text('${member['name'] ?? member['username'] ?? ''}'),
                    onPressed: () => _insertMention(member),
                  );
                },
              ),
            ),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              IconButton(
                onPressed: _pickAttachment,
                icon: const Icon(Icons.add_circle_outline_rounded, color: AppColors.blue),
              ),
              Expanded(
                child: TextField(
                  controller: textController,
                  minLines: 1,
                  maxLines: 5,
                  maxLength: 4000,
                  buildCounter: (_, {required currentLength, required isFocused, maxLength}) => null,
                  onTap: () => setState(() => showEmoji = false),
                  decoration: InputDecoration(
                    hintText: widget.conversation.isGroup ? 'Message · use @ to mention' : 'Message',
                    isDense: true,
                    fillColor: Theme.of(context).brightness == Brightness.dark
                        ? const Color(0xFF172033)
                        : const Color(0xFFF4F6FA),
                    suffixIcon: IconButton(
                      onPressed: () => setState(() => showEmoji = !showEmoji),
                      icon: const Icon(Icons.emoji_emotions_outlined),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 7),
              IconButton.filled(
                onPressed: sending
                    ? null
                    : (textController.text.trim().isEmpty ? _toggleRecording : _sendText),
                icon: Icon(
                  textController.text.trim().isEmpty
                      ? (recording ? Icons.stop_rounded : Icons.mic_rounded)
                      : Icons.send_rounded,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Future<void> _loadMentionMembers() async {
    if (!widget.conversation.isGroup) return;
    try {
      final data = await AppScope.of(context).api.groupMembers(widget.conversation.id);
      final raw = data['members'];
      if (raw is List && mounted) {
        setState(() {
          mentionMembers = raw.whereType<Map>().map((e) => e.cast<String, dynamic>()).toList();
        });
      }
    } catch (_) {}
  }

  List<Map<String, dynamic>> _mentionSuggestions() {
    if (!widget.conversation.isGroup || mentionMembers.isEmpty) return const [];
    final value = textController.text;
    final match = RegExp(r'(?:^|\\s)@([A-Za-z0-9_]*)$').firstMatch(value);
    if (match == null) return const [];
    final q = (match.group(1) ?? '').toLowerCase();
    return mentionMembers.where((m) {
      final username = '${m['username'] ?? ''}'.toLowerCase();
      final name = '${m['name'] ?? ''}'.toLowerCase();
      return username.isNotEmpty && (q.isEmpty || username.startsWith(q) || name.startsWith(q));
    }).take(6).toList();
  }

  void _insertMention(Map<String, dynamic> member) {
    final username = '${member['username'] ?? ''}'.trim();
    if (username.isEmpty) return;
    final value = textController.text;
    final match = RegExp(r'(?:^|\\s)@([A-Za-z0-9_]*)$').firstMatch(value);
    if (match == null) return;
    final start = value.lastIndexOf('@');
    final next = '${value.substring(0, start)}@$username ';
    textController.value = TextEditingValue(
      text: next,
      selection: TextSelection.collapsed(offset: next.length),
    );
  }

  List<int> _mentionIds(String plainText) {
    if (!widget.conversation.isGroup) return const [];
    final names = RegExp(r'@([A-Za-z0-9_]{2,40})')
        .allMatches(plainText)
        .map((m) => (m.group(1) ?? '').toLowerCase())
        .toSet();
    return mentionMembers
        .where((m) => names.contains('${m['username'] ?? ''}'.toLowerCase()))
        .map((m) => _asInt(m['id']))
        .where((id) => id > 0)
        .take(10)
        .toList();
  }

  Future<void> _loadRecentEmojis""",
    text,
    count=1,
    flags=re.S,
)

# Better emoji panel: search, skin tones and existing recents/categories.
emoji_start = text.find('  Widget _emojiPanel() {')
emoji_end = text.find('  Widget _recordingBar()', emoji_start)
if emoji_start < 0 or emoji_end < 0:
    raise RuntimeError('v3.2 patch target missing: emoji panel')
old_panel = text[emoji_start:emoji_end]
# Reuse the existing category data by extracting its groups literal from old panel.
groups_match = re.search(r"    final groups = <String, List<String>>\{.*?\n    \};", old_panel, re.S)
if not groups_match:
    raise RuntimeError('v3.2 patch target missing: emoji groups')
groups_code = groups_match.group(0)
new_panel = """  Widget _emojiPanel() {
""" + groups_code + """
    final activeCategory = emojiCategory == 'Recent' && recentEmojis.isEmpty
        ? 'Smileys'
        : emojiCategory;
    final aliases = <String, List<String>>{
      'smile': ['😀','😃','😊','🙂'], 'laugh': ['😂','🤣','😆'], 'love': ['🥰','😍','❤️','💕'],
      'heart': ['❤️','🩷','💙','💚','💜','🖤','🤍'], 'sad': ['😔','😢','😭'], 'cry': ['😭','😢'],
      'angry': ['😠','😡','🤬'], 'fire': ['🔥'], 'thumb': ['👍','👎'], 'clap': ['👏'], 'pray': ['🙏'],
      'study': ['📚','📖','🎓','📝','💡'], 'book': ['📚','📖','📘'], 'school': ['🏫','🎓'],
      'check': ['✅','✔️','☑️'], 'cross': ['❌','✖️'], 'star': ['⭐','🌟'], 'party': ['🎉','🥳','🎊'],
      'pakistan': ['🇵🇰'], 'phone': ['📱'], 'computer': ['💻'], 'camera': ['📷'], 'lock': ['🔒','🔐'],
    };
    var items = <String>[...(groups[activeCategory] ?? groups['Smileys']!)];
    final query = emojiSearch.trim().toLowerCase();
    if (query.isNotEmpty) {
      final found = <String>[];
      for (final entry in aliases.entries) {
        if (entry.key.contains(query)) found.addAll(entry.value);
      }
      if (query.runes.any((r) => r > 0x2000)) {
        found.addAll(groups.values.expand((e) => e).where((e) => e.contains(query)));
      }
      items = found.toSet().toList();
    }
    final dark = Theme.of(context).brightness == Brightness.dark;
    const tones = ['', '🏻', '🏼', '🏽', '🏾', '🏿'];
    const toneCapable = {'👍','👎','👌','🤌','🤏','✌️','🤞','🤟','🤘','🤙','👋','👏','🙌','🙏','💪'};

    String withTone(String emoji) {
      if (skinTone.isEmpty || !toneCapable.contains(emoji)) return emoji;
      return emoji.replaceAll('️', '') + skinTone;
    }

    return Container(
      height: 352,
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        border: Border(top: BorderSide(color: Theme.of(context).dividerColor.withValues(alpha: .65))),
      ),
      padding: const EdgeInsets.fromLTRB(10, 8, 10, 8),
      child: Column(
        children: [
          SizedBox(
            height: 38,
            child: TextField(
              onChanged: (value) => setState(() => emojiSearch = value),
              decoration: InputDecoration(
                isDense: true,
                hintText: 'Search emojis',
                prefixIcon: const Icon(Icons.search_rounded, size: 19),
                suffixIcon: emojiSearch.isEmpty
                    ? null
                    : IconButton(
                        onPressed: () => setState(() => emojiSearch = ''),
                        icon: const Icon(Icons.close_rounded, size: 18),
                      ),
              ),
            ),
          ),
          const SizedBox(height: 6),
          Row(
            children: [
              const Text('Skin tone', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: AppColors.muted)),
              const SizedBox(width: 7),
              for (final tone in tones)
                InkWell(
                  borderRadius: BorderRadius.circular(20),
                  onTap: () => setState(() => skinTone = tone),
                  child: Container(
                    margin: const EdgeInsets.only(right: 4),
                    padding: const EdgeInsets.all(5),
                    decoration: BoxDecoration(
                      color: skinTone == tone ? AppColors.blue.withValues(alpha: .14) : Colors.transparent,
                      shape: BoxShape.circle,
                    ),
                    child: Text(tone.isEmpty ? '👍' : '👍$tone', style: const TextStyle(fontSize: 17)),
                  ),
                ),
              const Spacer(),
              if (activeCategory == 'Recent' && recentEmojis.isNotEmpty)
                TextButton(
                  onPressed: () async {
                    setState(() => recentEmojis = <String>[]);
                    try {
                      final prefs = await SharedPreferences.getInstance();
                      await prefs.remove('chat_recent_emojis');
                    } catch (_) {}
                  },
                  child: const Text('Clear recent'),
                ),
            ],
          ),
          SizedBox(
            height: 38,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              itemCount: groups.keys.length,
              separatorBuilder: (_, _) => const SizedBox(width: 6),
              itemBuilder: (_, i) {
                final name = groups.keys.elementAt(i);
                return ChoiceChip(
                  selected: name == activeCategory,
                  showCheckmark: false,
                  visualDensity: VisualDensity.compact,
                  label: Text(name),
                  onSelected: (_) => setState(() { emojiCategory = name; emojiSearch = ''; }),
                );
              },
            ),
          ),
          const SizedBox(height: 7),
          Expanded(
            child: items.isEmpty
                ? const Center(child: Text('No matching emoji.', style: TextStyle(color: AppColors.muted)))
                : Container(
                    decoration: BoxDecoration(
                      color: dark ? const Color(0xFF101A2A) : const Color(0xFFF7F9FC),
                      borderRadius: BorderRadius.circular(18),
                    ),
                    padding: const EdgeInsets.all(7),
                    child: GridView.builder(
                      padding: EdgeInsets.zero,
                      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                        crossAxisCount: 8,
                        mainAxisSpacing: 2,
                        crossAxisSpacing: 2,
                      ),
                      itemCount: items.length,
                      itemBuilder: (_, i) {
                        final value = withTone(items[i]);
                        return InkWell(
                          borderRadius: BorderRadius.circular(14),
                          onTap: () => _insertEmoji(value),
                          child: Center(child: Text(value, style: const TextStyle(fontSize: 27))),
                        );
                      },
                    ),
                  ),
          ),
        ],
      ),
    );
  }

"""
text = text[:emoji_start] + new_panel + text[emoji_end:]

# Text send encrypts before transport and keeps encrypted metadata in offline outbox.
text = re.sub(
    r"  Future<void> _sendText\(\) async \{.*?\n  \}\n\n  Future<void> _refreshOutboxCount",
    """  Future<void> _sendText() async {
    if (_chatBlocked) return;
    final plainText = textController.text.trim();
    if (plainText.isEmpty) return;
    final currentReply = reply;
    final api = AppScope.of(context).api;
    final token = api.newClientToken();
    final mentions = _mentionIds(plainText);
    setState(() => sending = true);
    textController.clear();
    setState(() => reply = null);
    var wireText = plainText;
    var encrypted = false;
    try {
      if (e2eeState.enabled) {
        wireText = await e2ee.encryptText(widget.conversation, plainText);
        encrypted = true;
      }
      await api.sendText(
        widget.conversation.id,
        wireText,
        replyTo: currentReply?.id,
        clientToken: token,
        encrypted: encrypted,
        mentionIds: mentions,
      );
      await _load(jumpToBottom: true);
    } catch (e) {
      if (e is ApiException && e.status == 0) {
        await outbox.enqueue(
          OutboxItem(
            token: token,
            conversationId: widget.conversation.id,
            text: wireText,
            replyTo: currentReply?.id,
            createdAt: DateTime.now().millisecondsSinceEpoch,
            encrypted: encrypted,
            mentionIds: mentions,
          ),
        );
        await _refreshOutboxCount();
        if (mounted) showMessage(context, 'Message queued securely. It will retry when the connection returns.');
      } else {
        textController.text = plainText;
        if (mounted) showMessage(context, apiMessage(e));
      }
    }
    if (mounted) setState(() => sending = false);
  }

  Future<void> _refreshOutboxCount""",
    text,
    count=1,
    flags=re.S,
)
text = replace_once(text,
"""          await api.sendText(
            item.conversationId,
            item.text,
            replyTo: item.replyTo,
            clientToken: item.token,
          );
""",
"""          await api.sendText(
            item.conversationId,
            item.text,
            replyTo: item.replyTo,
            clientToken: item.token,
            encrypted: item.encrypted,
            mentionIds: item.mentionIds,
          );
""", 'encrypted outbox retry')

# Professional photo editor with brightness/contrast + HD/standard output.
text = re.sub(
    r"  Future<String\?> _editPhoto\(String sourcePath\) async \{.*?\n  \}\n\n  Future<void> _uploadManyImages",
    """  Future<String?> _editPhoto(String sourcePath) async {
    if (!mounted) return null;
    final source = File(sourcePath);
    if (!await source.exists() || await source.length() < 256) {
      showMessage(context, 'That photo is no longer available.');
      return null;
    }
    var turns = 0;
    var flip = false;
    var crop = 'original';
    var brightness = 0.0;
    var contrast = 1.0;
    var hd = false;

    final apply = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      backgroundColor: const Color(0xFF08111D),
      builder: (sheet) => StatefulBuilder(
        builder: (context, setLocal) => SizedBox(
          height: MediaQuery.sizeOf(context).height * .92,
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(8, 8, 8, 4),
                child: Row(
                  children: [
                    IconButton(onPressed: () => Navigator.pop(sheet, false), icon: const Icon(Icons.close_rounded, color: Colors.white)),
                    const Expanded(
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text('Photo editor', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w900)),
                        Text('Crop · rotate · flip · light · contrast · HD', style: TextStyle(color: Colors.white60, fontSize: 11)),
                      ]),
                    ),
                    TextButton(
                      onPressed: () => setLocal(() { turns=0; flip=false; crop='original'; brightness=0; contrast=1; hd=false; }),
                      child: const Text('Reset'),
                    ),
                  ],
                ),
              ),
              const Divider(height: 1, color: Color(0x334B5870)),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Center(
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(20),
                      child: ColoredBox(
                        color: Colors.black,
                        child: Transform.flip(
                          flipX: flip,
                          child: RotatedBox(
                            quarterTurns: turns,
                            child: Image.file(source, fit: crop=='original' ? BoxFit.contain : BoxFit.cover, gaplessPlayback: true),
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ),
              Container(
                color: const Color(0xFF0D1828),
                padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
                child: Column(
                  children: [
                    SingleChildScrollView(
                      scrollDirection: Axis.horizontal,
                      child: Row(children: [
                        for (final entry in const {'original':'Original','square':'Square','portrait':'4:5','landscape':'16:9'}.entries) ...[
                          ChoiceChip(selected: crop==entry.key, showCheckmark: false, label: Text(entry.value), onSelected: (_) => setLocal(() => crop=entry.key)),
                          const SizedBox(width: 6),
                        ],
                      ]),
                    ),
                    Row(children: [
                      const SizedBox(width: 4),
                      const Icon(Icons.light_mode_outlined, color: Colors.white70, size: 18),
                      Expanded(child: Slider(value: brightness, min: -.35, max: .35, onChanged: (v) => setLocal(() => brightness=v))),
                      Text('${(brightness*100).round()}', style: const TextStyle(color: Colors.white70, fontSize: 11)),
                    ]),
                    Row(children: [
                      const SizedBox(width: 4),
                      const Icon(Icons.contrast_rounded, color: Colors.white70, size: 18),
                      Expanded(child: Slider(value: contrast, min: .7, max: 1.35, onChanged: (v) => setLocal(() => contrast=v))),
                      Text('${(contrast*100).round()}%', style: const TextStyle(color: Colors.white70, fontSize: 11)),
                    ]),
                    Row(children: [
                      IconButton.filledTonal(onPressed: () => setLocal(() => turns=(turns+3)%4), icon: const Icon(Icons.rotate_left_rounded)),
                      const SizedBox(width: 8),
                      IconButton.filledTonal(onPressed: () => setLocal(() => turns=(turns+1)%4), icon: const Icon(Icons.rotate_right_rounded)),
                      const SizedBox(width: 8),
                      IconButton.filledTonal(onPressed: () => setLocal(() => flip=!flip), icon: const Icon(Icons.flip_rounded)),
                      const SizedBox(width: 8),
                      FilterChip(selected: hd, label: const Text('HD'), avatar: const Icon(Icons.hd_rounded, size: 17), onSelected: (v) => setLocal(() => hd=v)),
                      const Spacer(),
                      FilledButton.icon(onPressed: () => Navigator.pop(sheet, true), icon: const Icon(Icons.check_rounded), label: const Text('Apply')),
                    ]),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
    if (apply != true) return null;
    try {
      final output = await NativeBridge.editPhoto(
        path: sourcePath,
        turns: turns,
        flip: flip,
        crop: crop,
        brightness: brightness,
        contrast: contrast,
        quality: hd ? 95 : 86,
        maxDimension: hd ? 3200 : 1920,
      );
      if (output != null) {
        final file = File(output);
        if (await file.exists() && await file.length() >= 256) {
          if (mounted) showMessage(context, hd ? 'HD photo ready.' : 'Photo changes applied.');
          return output;
        }
      }
    } catch (_) {}
    try {
      final bytes = await source.readAsBytes();
      final edited = await compute(_processOutgoingPhoto, <String, dynamic>{
        'bytes': bytes, 'turns': turns, 'flip': flip, 'crop': crop,
      });
      final dir = await getTemporaryDirectory();
      final output = '${dir.path}/taleempk_photo_${DateTime.now().microsecondsSinceEpoch}.jpg';
      final file = File(output);
      await file.writeAsBytes(edited, flush: true);
      if (await file.length() < 256) throw StateError('empty');
      return output;
    } catch (_) {
      if (mounted) showMessage(context, 'This photo could not be edited on this device.');
      return null;
    }
  }

  Future<void> _uploadManyImages""",
    text,
    count=1,
    flags=re.S,
)

# E2EE-aware photo/document/voice uploads.
text = replace_once(text,
"""        await AppScope.of(context).api.sendFile(
          widget.conversation.id,
          paths[i],
          replyTo: i == 0 ? currentReply : null,
          onProgress: (value) {
""",
"""        var sendPath = paths[i];
        var encrypted = false;
        if (e2eeState.enabled) {
          final sealed = await e2ee.encryptFile(
            widget.conversation,
            sendPath,
            originalName: sendPath.split(Platform.pathSeparator).last,
            mime: _mimeForPath(sendPath),
          );
          sendPath = sealed.path;
          encrypted = true;
        }
        await AppScope.of(context).api.sendFile(
          widget.conversation.id,
          sendPath,
          replyTo: i == 0 ? currentReply : null,
          encrypted: encrypted,
          onProgress: (value) {
""", 'encrypted multi-photo upload')
text = replace_once(text,
"""      await AppScope.of(context).api.sendFile(
        widget.conversation.id,
        path,
        replyTo: reply?.id,
        onProgress: (value) {
""",
"""      var sendPath = path;
      var encrypted = false;
      if (e2eeState.enabled) {
        final sealed = await e2ee.encryptFile(
          widget.conversation,
          path,
          originalName: path.split(Platform.pathSeparator).last,
          mime: _mimeForPath(path),
        );
        sendPath = sealed.path;
        encrypted = true;
      }
      await AppScope.of(context).api.sendFile(
        widget.conversation.id,
        sendPath,
        replyTo: reply?.id,
        encrypted: encrypted,
        onProgress: (value) {
""", 'encrypted document upload')
text = replace_once(text,
"""      await AppScope.of(context).api.sendFile(
        widget.conversation.id,
        path,
        field: 'voice',
        voiceSeconds: seconds,
        voiceWave: wave,
        replyTo: reply?.id,
        onProgress: (value) {
""",
"""      var sendPath = path;
      var encrypted = false;
      if (e2eeState.enabled) {
        final sealed = await e2ee.encryptFile(
          widget.conversation,
          path,
          originalName: 'voice-${DateTime.now().millisecondsSinceEpoch}.m4a',
          mime: 'audio/mp4',
        );
        sendPath = sealed.path;
        encrypted = true;
      }
      await AppScope.of(context).api.sendFile(
        widget.conversation.id,
        sendPath,
        field: encrypted ? 'attachment' : 'voice',
        voiceSeconds: seconds,
        voiceWave: wave,
        replyTo: reply?.id,
        encrypted: encrypted,
        onProgress: (value) {
""", 'encrypted voice upload')

# Replace encryption info sheet and add native setup/unlock/decrypt helpers.
text = re.sub(
    r"  Future<void> _encryptionInfo\(\) async \{.*?\n  \}\n\n  Future<void> _reportUser",
    """  Future<void> _refreshEncryptionState() async {
    if (e2eeLoading) return;
    e2eeLoading = true;
    try {
      final state = await e2ee.prepareThread(widget.conversation);
      if (mounted) setState(() => e2eeState = state);
      if (state.enabled) unawaited(_decryptEncryptedTextMessages());
    } catch (_) {
      // Encryption status must never stop the chat from loading.
    } finally {
      e2eeLoading = false;
    }
  }

  Future<void> _decryptEncryptedTextMessages() async {
    if (!e2eeState.enabled) return;
    var changed = false;
    for (final message in messages) {
      if (!message.encrypted || message.deleted || message.decrypted || message.ciphertext.isEmpty) continue;
      final hasEncryptedAttachment = message.attachmentUrl != null && message.attachmentType == 'enc';
      if (hasEncryptedAttachment) continue;
      try {
        message.content = await e2ee.decryptText(widget.conversation, message);
        message.decrypted = true;
        changed = true;
      } catch (_) {}
    }
    if (changed && mounted) setState(() {});
  }

  Future<void> _unlockEncryptedMessage(ChatMessage message) async {
    if (!message.encrypted || message.deleted) return;
    if (!e2eeState.enabled) {
      await _encryptionInfo();
      return;
    }
    try {
      if (message.attachmentUrl != null && message.attachmentType == 'enc') {
        final bytes = await AppScope.of(context).api.attachmentBytes(message.attachmentUrl!);
        final dir = await getTemporaryDirectory();
        final encPath = '${dir.path}/taleempk_enc_${message.id}.bin';
        await File(encPath).writeAsBytes(bytes, flush: true);
        final opened = await e2ee.decryptFile(widget.conversation, message, encPath);
        message.attachmentUrl = Uri.file(opened.path).toString();
        message.attachmentName = opened.name;
        message.attachmentType = _typeFromMime(opened.mime, opened.name);
        if (message.ciphertext.isNotEmpty && message.ciphertext != '1..') {
          try { message.content = await e2ee.decryptText(widget.conversation, message); } catch (_) {}
        }
        message.decrypted = true;
      } else {
        message.content = await e2ee.decryptText(widget.conversation, message);
        message.decrypted = true;
      }
      if (mounted) setState(() {});
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    }
  }

  Future<void> _encryptionInfo() async {
    await _refreshEncryptionState();
    if (!mounted) return;
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (sheet) => StatefulBuilder(
        builder: (context, setLocal) {
          Future<void> refresh() async {
            await _refreshEncryptionState();
            if (sheet.mounted) setLocal(() {});
          }
          Future<String?> askPassphrase(String title, {bool confirm = false}) async {
            final first = TextEditingController();
            final second = TextEditingController();
            final result = await showDialog<String>(
              context: sheet,
              builder: (dialog) => AlertDialog(
                title: Text(title),
                content: Column(mainAxisSize: MainAxisSize.min, children: [
                  TextField(controller: first, obscureText: true, autofocus: true, decoration: const InputDecoration(labelText: 'Encryption passphrase')),
                  if (confirm) ...[
                    const SizedBox(height: 10),
                    TextField(controller: second, obscureText: true, decoration: const InputDecoration(labelText: 'Confirm passphrase')),
                  ],
                ]),
                actions: [
                  TextButton(onPressed: () => Navigator.pop(dialog), child: const Text('Cancel')),
                  FilledButton(onPressed: () {
                    if (first.text.length < 8) { showMessage(dialog, 'Use at least 8 characters.'); return; }
                    if (confirm && first.text != second.text) { showMessage(dialog, 'Passphrases do not match.'); return; }
                    Navigator.pop(dialog, first.text);
                  }, child: Text(confirm ? 'Set up' : 'Unlock')),
                ],
              ),
            );
            first.dispose(); second.dispose();
            return result;
          }

          final state = e2eeState.state;
          final on = state == 'on';
          return SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 4, 20, 26),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(children: [
                    Container(
                      width: 52, height: 52,
                      decoration: BoxDecoration(color: (on ? AppColors.success : AppColors.blue).withValues(alpha: .11), borderRadius: BorderRadius.circular(17)),
                      child: Icon(on ? Icons.lock_rounded : Icons.enhanced_encryption_outlined, color: on ? AppColors.success : AppColors.blue, size: 27),
                    ),
                    const SizedBox(width: 13),
                    Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(on ? 'End-to-end encrypted' : state == 'locked' ? 'Encryption key locked' : 'End-to-end encryption', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900)),
                      Text(widget.conversation.isGroup ? 'P-256 ECDH · AES-256-GCM · group epoch ${e2eeState.epoch}' : 'P-256 ECDH · HKDF-SHA256 · AES-256-GCM', style: const TextStyle(fontSize: 11, color: AppColors.muted)),
                    ])),
                  ]),
                  const SizedBox(height: 14),
                  Text(
                    on
                        ? 'Text, photos, files and voice notes sent while this lock is on are encrypted on your device before upload. The server stores ciphertext, not message contents or real encrypted-file metadata.'
                        : state == 'locked'
                            ? 'This account already has an encryption key. Unlock it with the same passphrase you use on TaleemPK web.'
                            : widget.conversation.isGroup
                                ? 'Set up your account key first. A group can be enabled after at least two members have encryption keys.'
                                : 'Both people need an encryption key before this private chat switches on automatically.',
                    style: TextStyle(height: 1.45, color: Theme.of(sheet).colorScheme.onSurfaceVariant),
                  ),
                  const SizedBox(height: 14),
                  if (state == 'locked')
                    FilledButton.icon(
                      onPressed: () async {
                        final pass = await askPassphrase('Unlock encryption');
                        if (pass == null) return;
                        try { await e2ee.unlock(pass); await refresh(); if (sheet.mounted) showMessage(sheet, 'Encryption unlocked on this device.'); }
                        catch (e) { if (sheet.mounted) showMessage(sheet, apiMessage(e)); }
                      },
                      icon: const Icon(Icons.key_rounded), label: const Text('Unlock this device'),
                    )
                  else if (!e2ee.ready)
                    FilledButton.icon(
                      onPressed: () async {
                        final pass = await askPassphrase('Set up encryption', confirm: true);
                        if (pass == null) return;
                        try { await e2ee.setup(pass); await refresh(); if (sheet.mounted) showMessage(sheet, 'Encryption key created securely.'); }
                        catch (e) { if (sheet.mounted) showMessage(sheet, apiMessage(e)); }
                      },
                      icon: const Icon(Icons.add_moderator_rounded), label: const Text('Set up encryption'),
                    ),
                  if (widget.conversation.isGroup && e2ee.ready && e2eeState.epoch < 1) ...[
                    const SizedBox(height: 9),
                    OutlinedButton.icon(
                      onPressed: () async {
                        try { await e2ee.enableGroup(widget.conversation.id); await refresh(); }
                        catch (e) { if (sheet.mounted) showMessage(sheet, apiMessage(e)); }
                      },
                      icon: const Icon(Icons.group_work_outlined), label: const Text('Turn on for this group'),
                    ),
                  ],
                  if (on && !widget.conversation.isGroup) ...[
                    const SizedBox(height: 9),
                    OutlinedButton.icon(
                      onPressed: () async {
                        try {
                          final code = await e2ee.safetyNumber(widget.conversation);
                          if (!sheet.mounted) return;
                          await showDialog<void>(context: sheet, builder: (d) => AlertDialog(
                            title: const Text('Safety number'),
                            content: SelectableText(code, style: const TextStyle(fontSize: 17, height: 1.5, fontWeight: FontWeight.w800)),
                            actions: [TextButton(onPressed: () => Navigator.pop(d), child: const Text('Done'))],
                          ));
                        } catch (e) { if (sheet.mounted) showMessage(sheet, apiMessage(e)); }
                      },
                      icon: const Icon(Icons.verified_user_outlined), label: const Text('Compare safety number'),
                    ),
                  ],
                  if (e2ee.ready) ...[
                    const SizedBox(height: 9),
                    TextButton.icon(
                      onPressed: () async { await e2ee.forgetDevice(); await refresh(); },
                      icon: const Icon(Icons.phonelink_erase_rounded),
                      label: const Text('Forget encryption key on this device'),
                    ),
                  ],
                  const SizedBox(height: 10),
                  const Text(
                    'Security note: TaleemPK uses the same interoperable E2EE protocol as the web app. It does not implement a Signal-style forward-secret ratchet; group membership is still trusted from the server. Compare safety numbers for sensitive private chats.',
                    style: TextStyle(fontSize: 10.5, height: 1.4, color: AppColors.muted),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Future<void> _reportUser""",
    text,
    count=1,
    flags=re.S,
)

# MIME helpers for encrypted file metadata.
marker = """  String _duration(int seconds) =>
      '${(seconds ~/ 60).toString().padLeft(2, '0')}:${(seconds % 60).toString().padLeft(2, '0')}';
"""
helpers = marker + """

  String _mimeForPath(String path) {
    final ext = path.split('.').last.toLowerCase();
    return switch (ext) {
      'jpg' || 'jpeg' => 'image/jpeg',
      'png' => 'image/png',
      'webp' => 'image/webp',
      'gif' => 'image/gif',
      'm4a' || 'mp4' => 'audio/mp4',
      'mp3' => 'audio/mpeg',
      'pdf' => 'application/pdf',
      'txt' => 'text/plain',
      _ => 'application/octet-stream',
    };
  }

  String _typeFromMime(String mime, String name) {
    final value = mime.toLowerCase();
    if (value == 'image/jpeg') return 'jpg';
    if (value == 'image/png') return 'png';
    if (value == 'image/webp') return 'webp';
    if (value == 'image/gif') return 'gif';
    if (value.startsWith('audio/')) return name.split('.').last.toLowerCase();
    return name.contains('.') ? name.split('.').last.toLowerCase() : 'file';
  }
"""
text = replace_once(text, marker, helpers, 'encrypted MIME helpers')

# Voice player can consume decrypted local files.
text = replace_once(text,
"""  Future<void> _downloadFresh(File file) async {
    final bytes = await widget.api.attachmentBytes(widget.message.attachmentUrl!);
    await file.writeAsBytes(bytes, flush: true);
  }
""",
"""  Future<void> _downloadFresh(File file) async {
    final url = widget.message.attachmentUrl!;
    if (url.startsWith('file://')) {
      final source = File(Uri.parse(url).toFilePath());
      await source.copy(file.path);
      return;
    }
    final bytes = await widget.api.attachmentBytes(url);
    await file.writeAsBytes(bytes, flush: true);
  }
""", 'local encrypted voice playback')
write(path, text)


# ---------------------------------------------------------------------------
# Privacy screen: blocked people list with one-tap unblock.
# ---------------------------------------------------------------------------
path = 'flutter/lib/screens/security_screen.dart'
text = read(path)
text = replace_once(text,
"""  List<Map<String, dynamic>> sessions = const [];
  bool loading = true, saving = false;
""",
"""  List<Map<String, dynamic>> sessions = const [];
  List<Map<String, dynamic>> blocked = const [];
  bool loading = true, saving = false;
""", 'security blocked state')
text = replace_once(text,
"""      final result = await Future.wait<Object>([
        api.privacySettings(),
        api.mobileSessions(),
      ]);
      settings = (result[0] as Map<String, dynamic>);
      sessions = (result[1] as List<Map<String, dynamic>>);
""",
"""      final result = await Future.wait<Object>([
        api.privacySettings(),
        api.mobileSessions(),
        api.blockedUsers(),
      ]);
      settings = (result[0] as Map<String, dynamic>);
      sessions = (result[1] as List<Map<String, dynamic>>);
      blocked = (result[2] as List<Map<String, dynamic>>);
""", 'security load blocked')
text = replace_once(text,
"""                        _sessionsCard(),
                        const SizedBox(height: 16),
                        _passwordCard(),
""",
"""                        _blockedCard(),
                        const SizedBox(height: 16),
                        _sessionsCard(),
                        const SizedBox(height: 16),
                        _passwordCard(),
""", 'security blocked card location')
marker = "  Widget _sessionsCard() => Card("
blocked_widget = """  Widget _blockedCard() => Card(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 10),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const _SectionTitle(
                icon: Icons.block_rounded,
                title: 'Blocked people',
                subtitle: 'Blocked accounts cannot message or call you.',
              ),
              const SizedBox(height: 8),
              if (blocked.isEmpty)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 13),
                  child: Text('You have not blocked anyone.', style: TextStyle(color: AppColors.muted)),
                )
              else
                for (final user in blocked)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: UserAvatar(url: user['avatar']?.toString(), name: '${user['name'] ?? ''}', radius: 20),
                    title: Text('${user['name'] ?? ''}', style: const TextStyle(fontWeight: FontWeight.w800)),
                    subtitle: Text('@${user['username'] ?? ''}'),
                    trailing: TextButton(
                      onPressed: saving ? null : () async {
                        final id = int.tryParse('${user['id'] ?? 0}') ?? 0;
                        if (id <= 0) return;
                        try { await AppScope.of(context).api.toggleBlock(id); await _load(); }
                        catch (e) { if (mounted) showMessage(context, apiMessage(e)); }
                      },
                      child: const Text('Unblock'),
                    ),
                  ),
            ],
          ),
        ),
      );

""" + marker
text = replace_once(text, marker, blocked_widget, 'security blocked widget')
write(path, text)


# ---------------------------------------------------------------------------
# Calls: speaker routing, reconnect feedback and cleaner controls.
# ---------------------------------------------------------------------------
path = 'flutter/lib/screens/call_screen.dart'
text = read(path)
text = replace_once(text,
"""  bool muted = false, cameraOff = false, ending = false;
""",
"""  bool muted = false, cameraOff = false, speakerOn = false, ending = false;
""", 'call speaker state')
text = replace_once(text,
"""          } else if (state ==
              RTCPeerConnectionState.RTCPeerConnectionStateFailed) {
            status = 'Connection failed';
          }
""",
"""          } else if (state == RTCPeerConnectionState.RTCPeerConnectionStateDisconnected) {
            status = 'Reconnecting…';
          } else if (state == RTCPeerConnectionState.RTCPeerConnectionStateFailed) {
            status = 'Connection failed';
          }
""", 'call reconnect status')
marker = """  void _toggleCamera() {
"""
insert = """  Future<void> _toggleSpeaker() async {
    speakerOn = !speakerOn;
    try {
      await Helper.setSpeakerphoneOn(speakerOn);
    } catch (_) {}
    if (mounted) setState(() {});
  }

""" + marker
text = replace_once(text, marker, insert, 'speaker toggle method')
text = replace_once(text,
"""                        if (widget.video)
                          _round(
                            cameraOff
                                ? Icons.videocam_off_rounded
                                : Icons.videocam_rounded,
                            _toggleCamera,
                            cameraOff ? 'Camera on' : 'Camera off',
                          ),
""",
"""                        _round(
                          speakerOn ? Icons.volume_up_rounded : Icons.hearing_rounded,
                          _toggleSpeaker,
                          speakerOn ? 'Speaker' : 'Earpiece',
                        ),
                        if (widget.video)
                          _round(
                            cameraOff
                                ? Icons.videocam_off_rounded
                                : Icons.videocam_rounded,
                            _toggleCamera,
                            cameraOff ? 'Camera on' : 'Camera off',
                          ),
""", 'speaker control')
write(path, text)


# ---------------------------------------------------------------------------
# Notification text: surface mentions/replies distinctly when polling can run.
# ---------------------------------------------------------------------------
path = 'flutter/lib/screens/home_shell.dart'
text = read(path)
text = replace_once(text,
"""          await NativeBridge.showNotification(
            id: 400000 + id,
            title: 'TaleemPK',
            body: '${activity['message'] ?? 'You have a new notification'}',
            payload: 'notification:$id',
          );
""",
"""          final type = '${activity['type'] ?? ''}';
          await NativeBridge.showNotification(
            id: 400000 + id,
            title: type == 'mention'
                ? 'You were mentioned'
                : type == 'reply'
                    ? 'New message reply'
                    : 'TaleemPK',
            body: '${activity['message'] ?? 'You have a new notification'}',
            payload: 'notification:$id',
          );
""", 'mention/reply notification title')
write(path, text)


# ---------------------------------------------------------------------------
# Release version and notes.
# ---------------------------------------------------------------------------
path = 'flutter/pubspec.yaml'
text = read(path)
text = re.sub(r'^version:\s*[^\n]+', 'version: 3.2.0+320', text, count=1, flags=re.M)
write(path, text)
write('flutter/V3.2.md', '''# TaleemPK Flutter v3.2\n\n## Messaging & privacy\n- Native TaleemPK E2EE protocol parity: P-256 ECDH, HKDF-SHA256 and AES-256-GCM for private chats; epoch-based AES-GCM group keys sealed pairwise; encrypted photos/files/voice notes; passphrase unlock compatible with the web app; private-chat safety numbers.\n- Sent / delivered / read message states use the same fetched/read watermarks and reciprocal receipt privacy as the web chat.\n- Professional photo editor: crop ratios, rotate, flip, brightness, contrast, standard/HD output and verified file output.\n- Emoji picker adds search, skin tones, category browsing and persistent recent history.\n- Group @mention suggestions plus explicit encrypted-message mention metadata; reply metadata remains server-visible so reply notifications still work without reading ciphertext.\n- Calls add speaker/earpiece routing and reconnect state on top of WebRTC mute/camera/switch-camera controls.\n- Privacy adds a native blocked-people list alongside profile/DM/call/comment visibility, online/searchability, read receipts, typing indicators, device sessions and password controls.\n\n## Size\nThe release workflow publishes a universal APK plus split-per-ABI APKs. The arm64 APK is the recommended download for modern Android phones and is substantially smaller because it does not bundle native libraries for other CPU architectures.\n\n## Security scope\nThis is full native parity with TaleemPK's existing web E2EE protocol. It is not a Signal-style double-ratchet protocol: long-lived account ECDH keys do not provide forward secrecy, and group membership is trusted from the TaleemPK server.\n''')
