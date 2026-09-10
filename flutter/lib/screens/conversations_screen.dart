import 'dart:async';

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
  bool loading = true, archivedMode = false, silentRefreshing = false;
  Timer? refreshTimer;
  @override
  void initState() {
    super.initState();
    _load();
    refreshTimer = Timer.periodic(
      const Duration(seconds: 3),
      (_) => _refreshSilently(),
    );
  }

  @override
  void dispose() {
    refreshTimer?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      all = await AppScope.of(context).api.conversations(
        archived: archivedMode,
      );
    } catch (e) {
      error = apiMessage(e);
    }
    if (mounted) setState(() => loading = false);
  }

  Future<void> _refreshSilently() async {
    if (!mounted || loading || silentRefreshing) return;
    silentRefreshing = true;
    try {
      final fresh = await AppScope.of(context).api.conversations(
        archived: archivedMode,
      );
      if (mounted && _conversationSignature(fresh) != _conversationSignature(all)) {
        setState(() => all = fresh);
      }
    } catch (_) {
      // Keep the inbox responsive when one background refresh misses.
    } finally {
      silentRefreshing = false;
    }
  }

  String _conversationSignature(List<Conversation> items) => items
      .map(
        (c) => '${c.id}|${c.unread}|${c.lastMessage}|${c.lastActivity}|'
            '${c.online}|${c.statusText}|${c.muted}|${c.archived}|'
            '${c.selfBlocked}|${c.blockedByOther}',
      )
      .join('\n');

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
        title: archivedMode ? 'Archived chats' : 'Messages',
        subtitle: archivedMode
            ? 'Conversations kept out of your main inbox'
            : 'Fast, private conversations',
        actions: [
          if (!archivedMode)
            IconButton(
              tooltip: 'Starred messages',
              onPressed: _showStarred,
              icon: const Icon(Icons.star_outline_rounded),
            ),
          if (!archivedMode)
            IconButton(
              tooltip: 'Search all messages',
              onPressed: _globalSearch,
              icon: const Icon(Icons.manage_search_rounded),
            ),
          PopupMenuButton<String>(
            tooltip: 'Chat options',
            onSelected: (value) {
              if (value == 'archive') {
                setState(() => archivedMode = !archivedMode);
                _load();
              } else if (value == 'group') {
                _createGroup();
              }
            },
            itemBuilder: (_) => [
              PopupMenuItem(
                value: 'archive',
                child: ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: Icon(
                    archivedMode
                        ? Icons.inbox_outlined
                        : Icons.archive_outlined,
                  ),
                  title: Text(
                    archivedMode ? 'Back to messages' : 'Archived chats',
                  ),
                ),
              ),
              if (!archivedMode)
                const PopupMenuItem(
                  value: 'group',
                  child: ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: Icon(Icons.group_add_outlined),
                    title: Text('New group'),
                  ),
                ),
            ],
          ),
          const SizedBox(width: 6),
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
                ? EmptyView(
                    icon: archivedMode
                        ? Icons.archive_outlined
                        : Icons.forum_outlined,
                    title: archivedMode ? 'Nothing archived' : 'No conversations',
                    message: archivedMode
                        ? 'Chats you archive will appear here.'
                        : 'Your private and group conversations will appear here.',
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
                color: c.unread > 0
                    ? Theme.of(context).colorScheme.onSurface
                    : Theme.of(context).colorScheme.onSurfaceVariant,
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
    trailing: PopupMenuButton<String>(
      onSelected: (value) => _conversationAction(c, value),
      itemBuilder: (_) => [
        PopupMenuItem(
          value: 'mute',
          child: Text(c.muted ? 'Unmute notifications' : 'Mute notifications'),
        ),
        PopupMenuItem(
          value: 'archive',
          child: Text(archivedMode ? 'Unarchive' : 'Archive'),
        ),
      ],
    ),
    onTap: () async {
      await Navigator.push(
        context,
        MaterialPageRoute(builder: (_) => ChatScreen(conversation: c)),
      );
      _load();
    },
  );

  Future<void> _conversationAction(Conversation chat, String action) async {
    try {
      if (action == 'mute') {
        await AppScope.of(context).api.toggleConversationMute(chat.id);
      } else if (action == 'archive') {
        await AppScope.of(context).api.toggleConversationArchive(chat.id);
      }
      await _load();
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    }
  }

  Future<void> _showStarred() async {
    try {
      final results = await AppScope.of(context).api.starredMessages();
      if (!mounted) return;
      await _resultsSheet(
        title: 'Starred messages',
        icon: Icons.star_rounded,
        results: results,
      );
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    }
  }

  Future<void> _globalSearch() async {
    final controller = TextEditingController();
    List<Map<String, dynamic>> results = const [];
    var busy = false;
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (sheet) => StatefulBuilder(
        builder: (context, setLocal) => SizedBox(
          height: MediaQuery.sizeOf(context).height * .78,
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(18, 4, 18, 10),
                child: TextField(
                  controller: controller,
                  autofocus: true,
                  textInputAction: TextInputAction.search,
                  onSubmitted: (_) async {
                    if (controller.text.trim().length < 2) return;
                    setLocal(() => busy = true);
                    try {
                      results = await AppScope.of(context).api
                          .searchMessages(controller.text.trim());
                    } finally {
                      if (sheet.mounted) setLocal(() => busy = false);
                    }
                  },
                  decoration: InputDecoration(
                    hintText: 'Search all messages',
                    prefixIcon: const Icon(Icons.search_rounded),
                    suffixIcon: IconButton(
                      onPressed: () async {
                        if (controller.text.trim().length < 2) return;
                        setLocal(() => busy = true);
                        try {
                          results = await AppScope.of(context).api
                              .searchMessages(controller.text.trim());
                        } finally {
                          if (sheet.mounted) setLocal(() => busy = false);
                        }
                      },
                      icon: const Icon(Icons.arrow_forward_rounded),
                    ),
                  ),
                ),
              ),
              if (busy) const LinearProgressIndicator(minHeight: 2),
              Expanded(
                child: results.isEmpty
                    ? const EmptyView(
                        icon: Icons.manage_search_rounded,
                        title: 'Search your chats',
                        message: 'Search message text and attachment names.',
                      )
                    : ListView.separated(
                        itemCount: results.length,
                        separatorBuilder: (_, _) => const Divider(height: 1),
                        itemBuilder: (_, i) {
                          final item = results[i];
                          return ListTile(
                            leading: const Icon(Icons.chat_bubble_outline_rounded),
                            title: Text('${item['title'] ?? item['where'] ?? 'Conversation'}'),
                            subtitle: Text(
                              '${item['sender'] ?? ''}: ${item['text'] ?? ''}',
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                            trailing: Text(
                              '${item['time'] ?? ''}',
                              style: const TextStyle(
                                fontSize: 10,
                                color: AppColors.muted,
                              ),
                            ),
                            onTap: () {
                              Navigator.pop(sheet);
                              _openConversationById(_asInt(item['conversation_id']));
                            },
                          );
                        },
                      ),
              ),
            ],
          ),
        ),
      ),
    );
    controller.dispose();
  }

  Future<void> _resultsSheet({
    required String title,
    required IconData icon,
    required List<Map<String, dynamic>> results,
  }) async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (sheet) => SizedBox(
        height: MediaQuery.sizeOf(sheet).height * .72,
        child: Column(
          children: [
            ListTile(
              leading: Icon(icon, color: AppColors.blue),
              title: Text(
                title,
                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900),
              ),
            ),
            Expanded(
              child: results.isEmpty
                  ? const EmptyView(
                      icon: Icons.star_border_rounded,
                      title: 'Nothing here yet',
                      message: 'Messages you star will appear here.',
                    )
                  : ListView.separated(
                      itemCount: results.length,
                      separatorBuilder: (_, _) => const Divider(height: 1),
                      itemBuilder: (_, i) {
                        final item = results[i];
                        return ListTile(
                          title: Text('${item['where'] ?? 'Conversation'}'),
                          subtitle: Text(
                            '${item['sender'] ?? ''}: ${item['text'] ?? ''}',
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                          ),
                          trailing: Text(
                            '${item['time'] ?? ''}',
                            style: const TextStyle(fontSize: 10, color: AppColors.muted),
                          ),
                          onTap: () {
                            Navigator.pop(sheet);
                            _openConversationById(_asInt(item['conversation_id']));
                          },
                        );
                      },
                    ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _openConversationById(int id) async {
    if (id <= 0 || !mounted) return;
    Conversation? chat;
    for (final item in all) {
      if (item.id == id) {
        chat = item;
        break;
      }
    }
    if (chat == null) {
      final active = await AppScope.of(context).api.conversations();
      final archived = await AppScope.of(context).api.conversations(archived: true);
      for (final item in [...active, ...archived]) {
        if (item.id == id) {
          chat = item;
          break;
        }
      }
    }
    if (chat == null || !mounted) {
      showMessage(context, 'That conversation is no longer available.');
      return;
    }
    await Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => ChatScreen(conversation: chat!)),
    );
    if (mounted) _load();
  }

  Future<void> _createGroup() async {
    final title = TextEditingController();
    final search = TextEditingController();
    List<Map<String, dynamic>> people = const [];
    final picked = <int>{};
    var busy = false;
    final create = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (sheet) => StatefulBuilder(
        builder: (context, setLocal) => SizedBox(
          height: MediaQuery.sizeOf(context).height * .82,
          child: Padding(
            padding: EdgeInsets.fromLTRB(
              18,
              0,
              18,
              MediaQuery.viewInsetsOf(context).bottom + 14,
            ),
            child: Column(
              children: [
                TextField(
                  controller: title,
                  maxLength: 120,
                  decoration: const InputDecoration(
                    labelText: 'Group name',
                    prefixIcon: Icon(Icons.groups_rounded),
                  ),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: search,
                  decoration: InputDecoration(
                    hintText: 'Search people by name or @username',
                    prefixIcon: const Icon(Icons.person_search_rounded),
                    suffixIcon: IconButton(
                      onPressed: () async {
                        if (search.text.trim().length < 2) return;
                        setLocal(() => busy = true);
                        try {
                          people = await AppScope.of(context).api
                              .searchPeople(search.text.trim());
                        } finally {
                          if (sheet.mounted) setLocal(() => busy = false);
                        }
                      },
                      icon: const Icon(Icons.search_rounded),
                    ),
                  ),
                  onSubmitted: (_) async {
                    if (search.text.trim().length < 2) return;
                    setLocal(() => busy = true);
                    try {
                      people = await AppScope.of(context).api
                          .searchPeople(search.text.trim());
                    } finally {
                      if (sheet.mounted) setLocal(() => busy = false);
                    }
                  },
                ),
                if (busy) const LinearProgressIndicator(minHeight: 2),
                const SizedBox(height: 6),
                Expanded(
                  child: people.isEmpty
                      ? const EmptyView(
                          icon: Icons.group_add_outlined,
                          title: 'Add members',
                          message: 'Search for people to add to your group.',
                        )
                      : ListView.builder(
                          itemCount: people.length,
                          itemBuilder: (_, i) {
                            final p = people[i];
                            final id = _asInt(p['id']);
                            return CheckboxListTile(
                              value: picked.contains(id),
                              onChanged: (v) => setLocal(() {
                                if (v == true) {
                                  picked.add(id);
                                } else {
                                  picked.remove(id);
                                }
                              }),
                              secondary: UserAvatar(
                                url: p['avatar']?.toString(),
                                name: '${p['name'] ?? ''}',
                                radius: 20,
                              ),
                              title: Text('${p['name'] ?? ''}'),
                              subtitle: Text('@${p['username'] ?? ''}'),
                            );
                          },
                        ),
                ),
                FilledButton.icon(
                  onPressed: () => Navigator.pop(sheet, true),
                  icon: const Icon(Icons.group_add_rounded),
                  label: Text('Create group (${picked.length + 1})'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
    if (create == true && mounted) {
      if (title.text.trim().length < 2 || picked.isEmpty) {
        showMessage(context, 'Add a group name and at least one member.');
      } else {
        try {
          await AppScope.of(context).api.groupAction(
            'create',
            title: title.text.trim(),
            members: picked.toList(),
          );
          await _load();
        } catch (e) {
          if (mounted) showMessage(context, apiMessage(e));
        }
      }
    }
    title.dispose();
    search.dispose();
  }

  int _asInt(dynamic value) =>
      value is int ? value : int.tryParse('$value') ?? 0;
}
