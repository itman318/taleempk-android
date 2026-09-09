class User {
  const User({
    required this.id,
    required this.name,
    required this.username,
    required this.role,
    this.avatar,
    required this.verified,
  });
  final int id;
  final String name, username, role;
  final String? avatar;
  final bool verified;
  factory User.fromJson(Map<String, dynamic> j) => User(
    id: _int(j['id']),
    name: '${j['name'] ?? ''}',
    username: '${j['username'] ?? ''}',
    role: '${j['role'] ?? 'student'}',
    avatar: _nullable(j['avatar']),
    verified: j['verified'] == true || j['verified'] == 1,
  );
}

class Stats {
  const Stats({
    this.members = 0,
    this.activeToday = 0,
    this.messagesToday = 0,
    this.quizAttempts = 0,
  });
  final int members, activeToday, messagesToday, quizAttempts;
  factory Stats.fromJson(Map<String, dynamic> j) => Stats(
    members: _int(j['members']),
    activeToday: _int(j['active_today']),
    messagesToday: _int(j['messages_today']),
    quizAttempts: _int(j['quiz_attempts']),
  );
}

class Shortcut {
  const Shortcut({
    required this.title,
    required this.subtitle,
    required this.route,
    required this.icon,
  });
  final String title, subtitle, route, icon;
  factory Shortcut.fromJson(Map<String, dynamic> j) => Shortcut(
    title: '${j['title'] ?? ''}',
    subtitle: '${j['subtitle'] ?? ''}',
    route: '${j['route'] ?? ''}',
    icon: '${j['icon'] ?? ''}',
  );
}

class BootstrapData {
  const BootstrapData({
    required this.user,
    required this.stats,
    required this.shortcuts,
  });
  final User user;
  final Stats stats;
  final List<Shortcut> shortcuts;
  factory BootstrapData.fromJson(Map<String, dynamic> j) => BootstrapData(
    user: User.fromJson(_map(j['user'])),
    stats: Stats.fromJson(_map(j['stats'])),
    shortcuts: _list(j['shortcuts'])
        .map((e) => Shortcut.fromJson(_map(e)))
        .toList(),
  );
}

class FeedPost {
  FeedPost({
    required this.id,
    required this.author,
    required this.username,
    this.avatar,
    required this.type,
    required this.content,
    required this.createdAt,
    required this.likes,
    required this.comments,
    required this.solved,
    required this.liked,
    required this.verified,
  });
  final int id;
  final String author, username, type, content, createdAt;
  final String? avatar;
  int likes, comments;
  final bool solved;
  bool liked;
  final bool verified;
  factory FeedPost.fromJson(Map<String, dynamic> j) => FeedPost(
    id: _int(j['id']),
    author: '${j['author'] ?? ''}',
    username: '${j['username'] ?? ''}',
    avatar: _nullable(j['avatar']),
    type: '${j['type'] ?? 'text'}',
    content: '${j['content'] ?? ''}',
    createdAt: '${j['created_at'] ?? ''}',
    likes: _int(j['likes']),
    comments: _int(j['comments']),
    solved: _bool(j['solved']),
    liked: _bool(j['liked']),
    verified: _bool(j['verified']),
  );
}

class FeedComment {
  const FeedComment({
    required this.id,
    required this.author,
    required this.content,
    required this.createdAt,
    required this.mine,
  });
  final int id;
  final String author, content, createdAt;
  final bool mine;
  factory FeedComment.fromJson(Map<String, dynamic> j) => FeedComment(
    id: _int(j['id']),
    author: '${j['author'] ?? ''}',
    content: '${j['content'] ?? ''}',
    createdAt: '${j['created_at'] ?? ''}',
    mine: _bool(j['mine']),
  );
}

class ModuleItem {
  const ModuleItem({
    required this.id,
    required this.title,
    required this.subtitle,
    required this.meta,
    required this.kind,
    required this.done,
  });
  final int id;
  final String title, subtitle, meta, kind;
  final bool done;
  factory ModuleItem.fromJson(Map<String, dynamic> j) => ModuleItem(
    id: _int(j['id']),
    title: '${j['title'] ?? ''}',
    subtitle: '${j['subtitle'] ?? ''}',
    meta: '${j['meta'] ?? ''}',
    kind: '${j['kind'] ?? ''}',
    done: _bool(j['done']),
  );
}

class ModuleData {
  const ModuleData({
    required this.key,
    required this.title,
    required this.subtitle,
    required this.items,
  });
  final String key, title, subtitle;
  final List<ModuleItem> items;
  factory ModuleData.fromJson(Map<String, dynamic> j) => ModuleData(
    key: '${j['key'] ?? ''}',
    title: '${j['title'] ?? ''}',
    subtitle: '${j['subtitle'] ?? ''}',
    items: _list(j['items']).map((e) => ModuleItem.fromJson(_map(e))).toList(),
  );
}

class Conversation {
  const Conversation({
    required this.id,
    required this.title,
    this.avatar,
    required this.lastMessage,
    required this.lastActivity,
    required this.unread,
    required this.isGroup,
    required this.online,
    required this.statusText,
    required this.muted,
  });
  final int id, unread;
  final String title, lastMessage, lastActivity, statusText;
  final String? avatar;
  final bool isGroup, online, muted;
  factory Conversation.fromJson(Map<String, dynamic> j) => Conversation(
    id: _int(j['id']),
    title: '${j['title'] ?? ''}',
    avatar: _nullable(j['avatar']),
    lastMessage: '${j['last_message'] ?? ''}',
    lastActivity: '${j['last_activity'] ?? ''}',
    unread: _int(j['unread']),
    isGroup: _bool(j['is_group']),
    online: _bool(j['online']),
    statusText: '${j['status_text'] ?? ''}',
    muted: _bool(j['muted']),
  );
}

class ChatReaction {
  const ChatReaction({
    required this.emoji,
    required this.count,
    required this.mine,
  });
  final String emoji;
  final int count;
  final bool mine;
  factory ChatReaction.fromJson(Map<String, dynamic> j) => ChatReaction(
    emoji: '${j['emoji'] ?? ''}',
    count: _int(j['count']),
    mine: _bool(j['mine']),
  );
}

class ReplyPreview {
  const ReplyPreview({
    required this.id,
    required this.sender,
    required this.text,
  });
  final int id;
  final String sender, text;
  factory ReplyPreview.fromJson(Map<String, dynamic> j) => ReplyPreview(
    id: _int(j['id']),
    sender: '${j['sender'] ?? ''}',
    text: '${j['text'] ?? ''}',
  );
}

class ChatMessage {
  const ChatMessage({
    required this.id,
    required this.senderId,
    required this.sender,
    required this.content,
    required this.time,
    required this.mine,
    required this.voiceSeconds,
    this.attachmentUrl,
    this.attachmentName,
    required this.read,
    this.attachmentType,
    required this.dateLabel,
    required this.deleted,
    required this.edited,
    required this.forwarded,
    required this.starred,
    required this.pinned,
    required this.canEdit,
    this.reply,
    required this.reactions,
  });
  final int id, senderId, voiceSeconds;
  final String sender, content, time, dateLabel;
  final String? attachmentUrl, attachmentName, attachmentType;
  final bool mine, deleted, edited, forwarded, starred, pinned, canEdit;
  bool read;
  final ReplyPreview? reply;
  final List<ChatReaction> reactions;
  factory ChatMessage.fromJson(Map<String, dynamic> j) => ChatMessage(
    id: _int(j['id']),
    senderId: _int(j['sender_id']),
    sender: '${j['sender'] ?? ''}',
    content: '${j['content'] ?? ''}',
    time: '${j['time'] ?? ''}',
    mine: _bool(j['mine']),
    voiceSeconds: _int(j['voice_seconds']),
    attachmentUrl: _nullable(j['attachment_url']),
    attachmentName: _nullable(j['attachment_name']),
    attachmentType: _nullable(j['attachment_type']),
    read: _bool(j['read']),
    dateLabel: '${j['date_label'] ?? ''}',
    deleted: _bool(j['deleted']),
    edited: _bool(j['edited']),
    forwarded: _bool(j['forwarded']),
    starred: _bool(j['starred']),
    pinned: _bool(j['pinned']),
    canEdit: _bool(j['can_edit']),
    reply: j['reply'] is Map ? ReplyPreview.fromJson(_map(j['reply'])) : null,
    reactions: _list(j['reactions'])
        .map((e) => ChatReaction.fromJson(_map(e)))
        .toList(),
  );
}

class ChatPresence {
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

Map<String, dynamic> _map(dynamic value) => value is Map<String, dynamic>
    ? value
    : value is Map
    ? value.cast<String, dynamic>()
    : <String, dynamic>{};
List<dynamic> _list(dynamic value) => value is List ? value : const [];
int _int(dynamic value) => value is int ? value : int.tryParse('$value') ?? 0;
bool _bool(dynamic value) => value == true || value == 1 || value == '1';
String? _nullable(dynamic value) =>
    value == null || '$value'.isEmpty ? null : '$value';
