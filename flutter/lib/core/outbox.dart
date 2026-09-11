import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

class OutboxItem {
  const OutboxItem({
    required this.token,
    required this.conversationId,
    required this.text,
    required this.createdAt,
    this.replyTo,
    this.attempts = 0,
  });

  final String token;
  final int conversationId;
  final String text;
  final int? replyTo;
  final int createdAt;
  final int attempts;

  OutboxItem copyWith({int? attempts}) => OutboxItem(
        token: token,
        conversationId: conversationId,
        text: text,
        replyTo: replyTo,
        createdAt: createdAt,
        attempts: attempts ?? this.attempts,
      );

  Map<String, dynamic> toJson() => {
        'token': token,
        'conversation_id': conversationId,
        'text': text,
        'reply_to': replyTo,
        'created_at': createdAt,
        'attempts': attempts,
      };

  factory OutboxItem.fromJson(Map<String, dynamic> json) => OutboxItem(
        token: '${json['token'] ?? ''}',
        conversationId: _asInt(json['conversation_id']),
        text: '${json['text'] ?? ''}',
        replyTo: json['reply_to'] == null ? null : _asInt(json['reply_to']),
        createdAt: _asInt(json['created_at']),
        attempts: _asInt(json['attempts']),
      );

  static int _asInt(dynamic value) =>
      value is int ? value : int.tryParse('$value') ?? 0;
}

class MessageOutbox {
  static const _key = 'taleempk_chat_outbox_v3';

  Future<List<OutboxItem>> all() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_key);
    if (raw == null || raw.isEmpty) return <OutboxItem>[];
    try {
      final decoded = jsonDecode(raw);
      if (decoded is! List) return <OutboxItem>[];
      return decoded
          .whereType<Map>()
          .map((item) => OutboxItem.fromJson(item.cast<String, dynamic>()))
          .where((item) =>
              item.token.isNotEmpty &&
              item.conversationId > 0 &&
              item.text.trim().isNotEmpty)
          .toList()
        ..sort((a, b) => a.createdAt.compareTo(b.createdAt));
    } catch (_) {
      return <OutboxItem>[];
    }
  }

  Future<List<OutboxItem>> forConversation(int conversationId) async =>
      (await all())
          .where((item) => item.conversationId == conversationId)
          .toList();

  Future<int> countForConversation(int conversationId) async =>
      (await forConversation(conversationId)).length;

  Future<void> enqueue(OutboxItem item) async {
    final items = await all();
    final index = items.indexWhere((old) => old.token == item.token);
    if (index >= 0) {
      items[index] = item;
    } else {
      items.add(item);
    }
    await _save(items);
  }

  Future<void> remove(String token) async {
    final items = await all();
    items.removeWhere((item) => item.token == token);
    await _save(items);
  }

  Future<void> updateAttempts(String token, int attempts) async {
    final items = await all();
    final index = items.indexWhere((item) => item.token == token);
    if (index < 0) return;
    items[index] = items[index].copyWith(attempts: attempts);
    await _save(items);
  }

  Future<void> clearConversation(int conversationId) async {
    final items = await all();
    items.removeWhere((item) => item.conversationId == conversationId);
    await _save(items);
  }

  Future<void> _save(List<OutboxItem> items) async {
    final prefs = await SharedPreferences.getInstance();
    if (items.isEmpty) {
      await prefs.remove(_key);
      return;
    }
    await prefs.setString(
      _key,
      jsonEncode(items.map((item) => item.toJson()).toList()),
    );
  }
}
