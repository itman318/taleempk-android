import 'package:flutter/material.dart';

import '../core/app_state.dart';
import '../core/models.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'home_shell.dart';

class FeedScreen extends StatefulWidget {
  const FeedScreen({super.key});
  @override
  State<FeedScreen> createState() => _FeedScreenState();
}

class _FeedScreenState extends State<FeedScreen> {
  final posts = <FeedPost>[];
  final scroll = ScrollController();
  int page = 1;
  bool loading = true, loadingMore = false, ended = false;
  String? error;
  @override
  void initState() {
    super.initState();
    _refresh();
    scroll.addListener(_nearEnd);
  }

  @override
  void dispose() {
    scroll.dispose();
    super.dispose();
  }

  void _nearEnd() {
    if (scroll.position.extentAfter < 450 && !loadingMore && !ended)
      _loadMore();
  }

  Future<void> _refresh() async {
    setState(() {
      loading = true;
      error = null;
      page = 1;
      ended = false;
    });
    try {
      final fresh = await AppScope.of(context).api.feed();
      posts
        ..clear()
        ..addAll(fresh);
      ended = fresh.length < 20;
    } catch (e) {
      error = apiMessage(e);
    }
    if (mounted) setState(() => loading = false);
  }

  Future<void> _loadMore() async {
    setState(() => loadingMore = true);
    try {
      final more = await AppScope.of(context).api.feed(page: page + 1);
      posts.addAll(more);
      page++;
      ended = more.length < 20;
    } catch (_) {}
    if (mounted) setState(() => loadingMore = false);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: const PremiumAppBar(
      title: 'Community feed',
      subtitle: 'Learn, ask and grow together',
    ),
    body: loading
        ? const Center(child: CircularProgressIndicator())
        : error != null
        ? ErrorView(message: error!, retry: _refresh)
        : RefreshIndicator(
            onRefresh: _refresh,
            child: ListView.builder(
              controller: scroll,
              padding: const EdgeInsets.fromLTRB(15, 6, 15, 28),
              itemCount: posts.length + 2,
              itemBuilder: (_, i) {
                if (i == 0) return _composer();
                if (i > posts.length)
                  return Padding(
                    padding: const EdgeInsets.all(20),
                    child: Center(
                      child: loadingMore
                          ? const CircularProgressIndicator()
                          : ended
                          ? const Text(
                              'You’re all caught up',
                              style: TextStyle(color: AppColors.muted),
                            )
                          : null,
                    ),
                  );
                return Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: _post(posts[i - 1]),
                );
              },
            ),
          ),
  );

  Widget _composer() {
    final u = AppScope.of(context).user!;
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Card(
        child: InkWell(
          onTap: _createPost,
          borderRadius: BorderRadius.circular(22),
          child: Padding(
            padding: const EdgeInsets.all(15),
            child: Row(
              children: [
                UserAvatar(url: u.avatar, name: u.name, radius: 21),
                const SizedBox(width: 12),
                const Expanded(
                  child: Text(
                    'Share an update or ask a question…',
                    style: TextStyle(color: AppColors.muted),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.all(9),
                  decoration: const BoxDecoration(
                    color: Color(0x123157E8),
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(
                    Icons.edit_rounded,
                    color: AppColors.blue,
                    size: 20,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _post(FeedPost p) => Card(
    child: Padding(
      padding: const EdgeInsets.fromLTRB(17, 17, 17, 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              UserAvatar(url: p.avatar, name: p.author, radius: 22),
              const SizedBox(width: 11),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Flexible(
                          child: Text(
                            p.author,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontWeight: FontWeight.w800),
                          ),
                        ),
                        if (p.verified) ...[
                          const SizedBox(width: 4),
                          const Icon(
                            Icons.verified_rounded,
                            size: 15,
                            color: AppColors.blue,
                          ),
                        ],
                      ],
                    ),
                    Text(
                      '@${p.username} · ${p.createdAt}',
                      style: const TextStyle(
                        color: AppColors.muted,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
              if (p.type == 'question')
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 9,
                    vertical: 5,
                  ),
                  decoration: BoxDecoration(
                    color: const Color(0x127657EF),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: const Text(
                    'QUESTION',
                    style: TextStyle(
                      fontSize: 9.5,
                      fontWeight: FontWeight.w900,
                      color: AppColors.violet,
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 15),
          Text(p.content, style: const TextStyle(fontSize: 15, height: 1.52)),
          if (p.solved)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Row(
                children: [
                  const Icon(
                    Icons.check_circle_rounded,
                    size: 17,
                    color: AppColors.success,
                  ),
                  const SizedBox(width: 6),
                  Text(
                    'Solved',
                    style: TextStyle(
                      color: AppColors.success,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
            ),
          const SizedBox(height: 12),
          const Divider(height: 1),
          Row(
            children: [
              _action(
                p.liked
                    ? Icons.favorite_rounded
                    : Icons.favorite_border_rounded,
                '${p.likes}',
                p.liked ? AppColors.danger : AppColors.muted,
                () async {
                  try {
                    await AppScope.of(context).api.togglePostLike(p.id);
                    setState(() {
                      p.liked = !p.liked;
                      p.likes += p.liked ? 1 : -1;
                    });
                  } catch (e) {
                    showMessage(context, apiMessage(e));
                  }
                },
              ),
              _action(
                Icons.mode_comment_outlined,
                '${p.comments}',
                AppColors.muted,
                () => _comments(p),
              ),
              const Spacer(),
              _action(
                Icons.bookmark_border_rounded,
                '',
                AppColors.muted,
                () => showMessage(
                  context,
                  'Saved posts are available from your website profile.',
                ),
              ),
            ],
          ),
        ],
      ),
    ),
  );

  Widget _action(IconData icon, String label, Color color, VoidCallback tap) =>
      InkWell(
        onTap: tap,
        borderRadius: BorderRadius.circular(14),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 11),
          child: Row(
            children: [
              Icon(icon, size: 20, color: color),
              if (label.isNotEmpty) ...[
                const SizedBox(width: 6),
                Text(
                  label,
                  style: TextStyle(color: color, fontWeight: FontWeight.w700),
                ),
              ],
            ],
          ),
        ),
      );

  Future<void> _createPost() async {
    final c = TextEditingController();
    bool question = false;
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (sheet) => StatefulBuilder(
        builder: (sheet, setModal) => Padding(
          padding: EdgeInsets.fromLTRB(
            20,
            22,
            20,
            MediaQuery.viewInsetsOf(sheet).bottom + 22,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Create post',
                style: Theme.of(sheet).textTheme.headlineSmall
                    ?.copyWith(fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 14),
              TextField(
                controller: c,
                autofocus: true,
                minLines: 5,
                maxLines: 10,
                maxLength: 8000,
                decoration: const InputDecoration(
                  hintText: 'What would you like to share?',
                ),
              ),
              SwitchListTile(
                value: question,
                onChanged: (v) => setModal(() => question = v),
                title: const Text('Ask as a question'),
                subtitle: const Text(
                  'Invite useful answers from the community',
                ),
                contentPadding: EdgeInsets.zero,
              ),
              const SizedBox(height: 10),
              FilledButton.icon(
                onPressed: () async {
                  if (c.text.trim().isEmpty) return;
                  try {
                    await AppScope.of(context).api
                        .createPost(c.text.trim(), question: question);
                    if (sheet.mounted) Navigator.pop(sheet);
                    await _refresh();
                  } catch (e) {
                    if (sheet.mounted) showMessage(sheet, apiMessage(e));
                  }
                },
                icon: const Icon(Icons.send_rounded),
                label: const Text('Publish post'),
              ),
            ],
          ),
        ),
      ),
    );
    c.dispose();
  }

  Future<void> _comments(FeedPost post) async {
    final c = TextEditingController();
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (sheet) => FractionallySizedBox(
        heightFactor: .86,
        child: FutureBuilder<List<FeedComment>>(
          future: AppScope.of(context).api.comments(post.id),
          builder: (context, snap) => Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 6, 14, 14),
                child: Row(
                  children: [
                    Container(
                      width: 38,
                      height: 38,
                      decoration: BoxDecoration(
                        color: AppColors.blue.withValues(alpha: .10),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: const Icon(
                        Icons.forum_outlined,
                        color: AppColors.blue,
                        size: 20,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Comments',
                            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                                  fontWeight: FontWeight.w900,
                                ),
                          ),
                          Text(
                            '${post.comments} ${post.comments == 1 ? 'reply' : 'replies'}',
                            style: const TextStyle(
                              color: AppColors.muted,
                              fontSize: 11.5,
                            ),
                          ),
                        ],
                      ),
                    ),
                    IconButton(
                      tooltip: 'Close',
                      onPressed: () => Navigator.pop(sheet),
                      icon: const Icon(Icons.close_rounded),
                    ),
                  ],
                ),
              ),
              const Divider(height: 1),
              Expanded(
                child: snap.connectionState != ConnectionState.done
                    ? const Center(child: CircularProgressIndicator())
                    : snap.hasError
                    ? ErrorView(
                        message: apiMessage(snap.error!),
                        retry: () => Navigator.pop(sheet),
                      )
                    : snap.data!.isEmpty
                    ? const EmptyView(
                        icon: Icons.chat_bubble_outline_rounded,
                        title: 'No comments yet',
                        message: 'Be the first to add a helpful response.',
                      )
                    : ListView.separated(
                        padding: const EdgeInsets.fromLTRB(14, 10, 14, 10),
                        itemCount: snap.data!.length,
                        separatorBuilder: (_, _) => const SizedBox(height: 8),
                        itemBuilder: (_, i) {
                          final r = snap.data![i];
                          return Container(
                            padding: const EdgeInsets.fromLTRB(12, 11, 7, 11),
                            decoration: BoxDecoration(
                              color: Theme.of(context).colorScheme.surfaceContainerLow,
                              borderRadius: BorderRadius.circular(18),
                              border: Border.all(
                                color: Theme.of(context).dividerColor.withValues(alpha: .55),
                              ),
                            ),
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                UserAvatar(name: r.author, radius: 19),
                                const SizedBox(width: 10),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Row(
                                        children: [
                                          Expanded(
                                            child: Text(
                                              r.author,
                                              overflow: TextOverflow.ellipsis,
                                              style: const TextStyle(
                                                fontWeight: FontWeight.w800,
                                              ),
                                            ),
                                          ),
                                          Text(
                                            r.createdAt,
                                            style: const TextStyle(
                                              fontSize: 10.5,
                                              color: AppColors.muted,
                                            ),
                                          ),
                                        ],
                                      ),
                                      const SizedBox(height: 5),
                                      Text(
                                        r.content,
                                        style: TextStyle(
                                          height: 1.42,
                                          color: Theme.of(context).colorScheme.onSurface,
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                                if (r.mine)
                                  PopupMenuButton<String>(
                                    tooltip: 'Comment options',
                                    onSelected: (value) {
                                      if (value == 'edit') {
                                        _editComment(post, r, sheet);
                                      } else if (value == 'delete') {
                                        _deleteComment(post, r, sheet);
                                      }
                                    },
                                    itemBuilder: (_) => const [
                                      PopupMenuItem(
                                        value: 'edit',
                                        child: ListTile(
                                          contentPadding: EdgeInsets.zero,
                                          leading: Icon(Icons.edit_outlined),
                                          title: Text('Edit comment'),
                                        ),
                                      ),
                                      PopupMenuItem(
                                        value: 'delete',
                                        child: ListTile(
                                          contentPadding: EdgeInsets.zero,
                                          leading: Icon(
                                            Icons.delete_outline_rounded,
                                            color: AppColors.danger,
                                          ),
                                          title: Text(
                                            'Delete comment',
                                            style: TextStyle(color: AppColors.danger),
                                          ),
                                        ),
                                      ),
                                    ],
                                  ),
                              ],
                            ),
                          );
                        },
                      ),
              ),
              SafeArea(
                top: false,
                child: Container(
                  decoration: BoxDecoration(
                    color: Theme.of(context).colorScheme.surface,
                    border: Border(
                      top: BorderSide(color: Theme.of(context).dividerColor),
                    ),
                  ),
                  padding: EdgeInsets.fromLTRB(
                    14,
                    10,
                    14,
                    MediaQuery.viewInsetsOf(context).bottom + 10,
                  ),
                  child: Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: c,
                          minLines: 1,
                          maxLines: 5,
                          textCapitalization: TextCapitalization.sentences,
                          decoration: const InputDecoration(
                            hintText: 'Write a comment…',
                            isDense: true,
                            prefixIcon: Icon(Icons.chat_bubble_outline_rounded),
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      IconButton.filled(
                        tooltip: 'Post comment',
                        onPressed: () async {
                          if (c.text.trim().isEmpty) return;
                          try {
                            await AppScope.of(context).api
                                .addComment(post.id, c.text.trim());
                            post.comments++;
                            if (sheet.mounted) Navigator.pop(sheet);
                            if (mounted) setState(() {});
                            _comments(post);
                          } catch (e) {
                            if (sheet.mounted) {
                              showMessage(sheet, apiMessage(e));
                            }
                          }
                        },
                        icon: const Icon(Icons.send_rounded),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
    c.dispose();
  }

  Future<void> _editComment(
    FeedPost post,
    FeedComment comment,
    BuildContext sheetContext,
  ) async {
    if (sheetContext.mounted) Navigator.pop(sheetContext);
    final controller = TextEditingController(text: comment.content);
    final updated = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (sheet) => Padding(
        padding: EdgeInsets.fromLTRB(
          20,
          6,
          20,
          MediaQuery.viewInsetsOf(sheet).bottom + 20,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Edit comment',
              style: Theme.of(sheet).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.w900,
                  ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: controller,
              autofocus: true,
              minLines: 4,
              maxLines: 9,
              maxLength: 5000,
              decoration: const InputDecoration(
                hintText: 'Update your comment',
              ),
            ),
            const SizedBox(height: 10),
            FilledButton.icon(
              onPressed: () {
                final value = controller.text.trim();
                if (value.isNotEmpty) Navigator.pop(sheet, value);
              },
              icon: const Icon(Icons.check_rounded),
              label: const Text('Save changes'),
            ),
          ],
        ),
      ),
    );
    controller.dispose();
    if (updated == null || updated == comment.content || !mounted) {
      if (mounted) _comments(post);
      return;
    }
    try {
      await AppScope.of(context).api.editComment(comment.id, updated);
      if (!mounted) return;
      showMessage(context, 'Comment updated.');
      _comments(post);
    } catch (e) {
      if (mounted) {
        showMessage(context, apiMessage(e));
        _comments(post);
      }
    }
  }

  Future<void> _deleteComment(
    FeedPost post,
    FeedComment comment,
    BuildContext sheetContext,
  ) async {
    if (sheetContext.mounted) Navigator.pop(sheetContext);
    final yes = await showDialog<bool>(
          context: context,
          builder: (dialog) => AlertDialog(
            icon: const Icon(
              Icons.delete_outline_rounded,
              color: AppColors.danger,
            ),
            title: const Text('Delete comment?'),
            content: const Text(
              'This removes your comment from the post. This action cannot be undone.',
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(dialog, false),
                child: const Text('Cancel'),
              ),
              FilledButton(
                style: FilledButton.styleFrom(backgroundColor: AppColors.danger),
                onPressed: () => Navigator.pop(dialog, true),
                child: const Text('Delete'),
              ),
            ],
          ),
        ) ??
        false;
    if (!yes || !mounted) {
      if (mounted) _comments(post);
      return;
    }
    try {
      await AppScope.of(context).api.deleteComment(comment.id);
      if (post.comments > 0) post.comments--;
      if (!mounted) return;
      setState(() {});
      showMessage(context, 'Comment deleted.');
      _comments(post);
    } catch (e) {
      if (mounted) {
        showMessage(context, apiMessage(e));
        _comments(post);
      }
    }
  }
}
