import 'package:flutter/material.dart';

import '../core/app_state.dart';
import '../core/models.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'chat_screen.dart';
import 'home_shell.dart';

class ConversationsScreen extends StatefulWidget {
  const ConversationsScreen({super.key});
  @override
  State<ConversationsScreen> createState() => _ConversationsScreenState();
}

class _ConversationsScreenState extends State<ConversationsScreen> {
  List<Conversation> all = const [];
  String query = '';
  String? error;
  bool loading = true;
  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      all = await AppScope.of(context).api.conversations();
    } catch (e) {
      error = apiMessage(e);
    }
    if (mounted) setState(() => loading = false);
  }

  @override
  Widget build(BuildContext context) {
    final items = all
        .where(
          (c) =>
              c.title.toLowerCase().contains(query.toLowerCase()) ||
              c.lastMessage.toLowerCase().contains(query.toLowerCase()),
        )
        .toList();
    return Scaffold(
      appBar: PremiumAppBar(
        title: 'Messages',
        subtitle: 'Fast, private conversations',
        actions: [
          IconButton(onPressed: _load, icon: const Icon(Icons.refresh_rounded)),
          const SizedBox(width: 8),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 3, 16, 12),
            child: TextField(
              onChanged: (v) => setState(() => query = v),
              decoration: const InputDecoration(
                hintText: 'Search conversations',
                prefixIcon: Icon(Icons.search_rounded),
                isDense: true,
              ),
            ),
          ),
          Expanded(
            child: loading
                ? const Center(child: CircularProgressIndicator())
                : error != null
                ? ErrorView(message: error!, retry: _load)
                : items.isEmpty
                ? const EmptyView(
                    icon: Icons.forum_outlined,
                    title: 'No conversations',
                    message: 'Your private and group conversations will appear here.',
                  )
                : RefreshIndicator(
                    onRefresh: _load,
                    child: ListView.separated(
                      padding: const EdgeInsets.fromLTRB(10, 2, 10, 22),
                      itemCount: items.length,
                      separatorBuilder: (_, __) =>
                          const Divider(indent: 78, height: 1),
                      itemBuilder: (_, i) => _row(items[i]),
                    ),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _row(Conversation c) => ListTile(
    contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 7),
    leading: UserAvatar(
      url: c.avatar,
      name: c.title,
      radius: 27,
      online: c.online,
    ),
    title: Row(
      children: [
        Expanded(
          child: Text(
            c.title,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              fontWeight: c.unread > 0 ? FontWeight.w900 : FontWeight.w700,
            ),
          ),
        ),
        Text(
          c.lastActivity,
          style: TextStyle(
            fontSize: 11.5,
            color: c.unread > 0 ? AppColors.blue : AppColors.muted,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    ),
    subtitle: Padding(
      padding: const EdgeInsets.only(top: 5),
      child: Row(
        children: [
          if (c.muted)
            const Padding(
              padding: EdgeInsets.only(right: 5),
              child: Icon(
                Icons.volume_off_rounded,
                size: 15,
                color: AppColors.muted,
              ),
            ),
          Expanded(
            child: Text(
              c.lastMessage.isEmpty ? c.statusText : c.lastMessage,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                color: c.unread > 0 ? AppColors.ink : AppColors.muted,
                fontWeight: c.unread > 0 ? FontWeight.w600 : FontWeight.w400,
              ),
            ),
          ),
          if (c.unread > 0)
            Container(
              margin: const EdgeInsets.only(left: 8),
              padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
              decoration: const BoxDecoration(
                color: AppColors.blue,
                shape: BoxShape.circle,
              ),
              child: Text(
                c.unread > 99 ? '99+' : '${c.unread}',
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 10,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
        ],
      ),
    ),
    onTap: () async {
      await Navigator.push(
        context,
        MaterialPageRoute(builder: (_) => ChatScreen(conversation: c)),
      );
      _load();
    },
  );
}
