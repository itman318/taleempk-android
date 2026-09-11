import 'package:cached_network_image/cached_network_image.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/app_state.dart';
import '../core/models.dart';
import '../core/social_api.dart';
import '../core/social_models.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'home_shell.dart';
import 'profile_screen.dart';

class FeedScreen extends StatefulWidget {
  const FeedScreen({super.key});

  @override
  State<FeedScreen> createState() => _FeedScreenState();
}

class _FeedScreenState extends State<FeedScreen> with AutomaticKeepAliveClientMixin {
  final posts = <SocialPost>[];
  final scroll = ScrollController();
  String tab = 'latest', subject = '';
  List<String> subjects = const [];
  int before = 0;
  bool loading = true, loadingMore = false, hasMore = true, showDislikes = false;
  String? error;

  SocialApi get social => SocialApi(AppScope.of(context).api);

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    scroll.addListener(_onScroll);
    _refresh();
  }

  @override
  void dispose() {
    scroll
      ..removeListener(_onScroll)
      ..dispose();
    super.dispose();
  }

  void _onScroll() {
    if (scroll.hasClients && scroll.position.extentAfter < 650 && !loadingMore && hasMore) {
      _loadMore();
    }
  }

  Future<void> _refresh() async {
    if (mounted) setState(() { loading = true; error = null; before = 0; hasMore = true; });
    try {
      final page = await social.feed(tab: tab, subject: subject);
      if (!mounted) return;
      setState(() {
        posts
          ..clear()
          ..addAll(page.posts);
        before = page.nextBefore;
        hasMore = page.hasMore;
        showDislikes = page.showDislikes;
        if (page.subjects.isNotEmpty) subjects = page.subjects;
      });
    } catch (e) {
      if (mounted) setState(() => error = apiMessage(e));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> _loadMore() async {
    if (loadingMore || !hasMore) return;
    setState(() => loadingMore = true);
    try {
      final page = await social.feed(tab: tab, subject: subject, before: before);
      if (!mounted) return;
      final existing = posts.map((e) => e.id).toSet();
      setState(() {
        posts.addAll(page.posts.where((e) => existing.add(e.id)));
        before = page.nextBefore;
        hasMore = page.hasMore;
      });
    } catch (_) {
      // Infinite-scroll failure should not discard an already loaded feed.
    } finally {
      if (mounted) setState(() => loadingMore = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    return Scaffold(
      appBar: PremiumAppBar(
        title: 'Community feed',
        subtitle: subject.isEmpty ? 'Learn, ask and grow together' : 'Subject: $subject',
        actions: [
          IconButton(
            tooltip: 'Refresh',
            onPressed: _refresh,
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: loading
          ? const Center(child: CircularProgressIndicator())
          : error != null
              ? ErrorView(message: error!, retry: _refresh)
              : RefreshIndicator(
                  onRefresh: _refresh,
                  child: CustomScrollView(
                    controller: scroll,
                    physics: const AlwaysScrollableScrollPhysics(),
                    slivers: [
                      SliverToBoxAdapter(child: _composer()),
                      SliverToBoxAdapter(child: _filters()),
                      if (posts.isEmpty)
                        const SliverFillRemaining(
                          hasScrollBody: false,
                          child: EmptyView(
                            icon: Icons.dynamic_feed_outlined,
                            title: 'Nothing here yet',
                            message: 'Try another feed tab or be the first to share something useful.',
                          ),
                        )
                      else
                        SliverPadding(
                          padding: const EdgeInsets.fromLTRB(15, 3, 15, 0),
                          sliver: SliverList.builder(
                            itemCount: posts.length,
                            itemBuilder: (_, i) => Padding(
                              padding: const EdgeInsets.only(bottom: 12),
                              child: _post(posts[i]),
                            ),
                          ),
                        ),
                      SliverToBoxAdapter(
                        child: Padding(
                          padding: const EdgeInsets.fromLTRB(16, 6, 16, 28),
                          child: Center(
                            child: loadingMore
                                ? const CircularProgressIndicator()
                                : !hasMore && posts.isNotEmpty
                                    ? const Text('You’re all caught up', style: TextStyle(color: AppColors.muted))
                                    : null,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
    );
  }

  Widget _composer() {
    final u = AppScope.of(context).user!;
    return Padding(
      padding: const EdgeInsets.fromLTRB(15, 4, 15, 8),
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
                  child: Text('Share an update or ask a question…', style: TextStyle(color: AppColors.muted)),
                ),
                Container(
                  padding: const EdgeInsets.all(9),
                  decoration: const BoxDecoration(color: Color(0x123157E8), shape: BoxShape.circle),
                  child: const Icon(Icons.edit_rounded, color: AppColors.blue, size: 20),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _filters() => Padding(
        padding: const EdgeInsets.fromLTRB(12, 0, 12, 11),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  for (final item in const [('latest', 'Latest'), ('following', 'Following'), ('questions', 'Questions'), ('unsolved', 'Unsolved')])
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 3),
                      child: ChoiceChip(
                        label: Text(item.$2),
                        selected: tab == item.$1,
                        onSelected: (_) {
                          if (tab == item.$1) return;
                          setState(() => tab = item.$1);
                          _refresh();
                        },
                      ),
                    ),
                ],
              ),
            ),
            if (subjects.isNotEmpty) ...[
              const SizedBox(height: 7),
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(
                  children: [
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 3),
                      child: FilterChip(
                        label: const Text('All subjects'),
                        selected: subject.isEmpty,
                        onSelected: (_) {
                          if (subject.isEmpty) return;
                          setState(() => subject = '');
                          _refresh();
                        },
                      ),
                    ),
                    for (final s in subjects)
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 3),
                        child: FilterChip(
                          label: Text(s),
                          selected: subject == s,
                          onSelected: (_) {
                            setState(() => subject = subject == s ? '' : s);
                            _refresh();
                          },
                        ),
                      ),
                  ],
                ),
              ),
            ],
          ],
        ),
      );

  Widget _post(SocialPost p) => Card(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 10),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  GestureDetector(
                    onTap: p.username.isEmpty ? null : () => _openProfile(p),
                    child: UserAvatar(url: p.avatar, name: p.author, radius: 22),
                  ),
                  const SizedBox(width: 11),
                  Expanded(
                    child: GestureDetector(
                      onTap: p.username.isEmpty ? null : () => _openProfile(p),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Flexible(
                                child: Text(p.author, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w900)),
                              ),
                              if (p.verified) ...[
                                const SizedBox(width: 4),
                                const Icon(Icons.verified_rounded, size: 15, color: AppColors.blue),
                              ],
                            ],
                          ),
                          Text(
                            [if (p.username.isNotEmpty) '@${p.username}', p.createdAt].join(' · '),
                            style: const TextStyle(color: AppColors.muted, fontSize: 11.5),
                          ),
                        ],
                      ),
                    ),
                  ),
                  if (p.pinned) const Padding(padding: EdgeInsets.only(right: 5), child: Icon(Icons.push_pin_rounded, size: 16, color: AppColors.blue)),
                  PopupMenuButton<String>(
                    onSelected: (v) => _postMenu(p, v),
                    itemBuilder: (_) => p.mine
                        ? const [
                            PopupMenuItem(value: 'edit', child: ListTile(contentPadding: EdgeInsets.zero, leading: Icon(Icons.edit_outlined), title: Text('Edit post'))),
                            PopupMenuItem(value: 'delete', child: ListTile(contentPadding: EdgeInsets.zero, leading: Icon(Icons.delete_outline_rounded, color: AppColors.danger), title: Text('Delete post', style: TextStyle(color: AppColors.danger)))),
                          ]
                        : const [
                            PopupMenuItem(value: 'report', child: ListTile(contentPadding: EdgeInsets.zero, leading: Icon(Icons.flag_outlined), title: Text('Report post'))),
                          ],
                  ),
                ],
              ),
              if (p.type == 'question' || p.subject.isNotEmpty || p.solved || p.visibility == 'followers') ...[
                const SizedBox(height: 12),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    if (p.type == 'question') _tag('QUESTION', AppColors.violet),
                    if (p.subject.isNotEmpty) _tag(p.subject, AppColors.blue),
                    if (p.solved) _tag('SOLVED', AppColors.success),
                    if (p.visibility == 'followers') _tag('FOLLOWERS', AppColors.muted),
                  ],
                ),
              ],
              if (p.content.isNotEmpty) ...[
                const SizedBox(height: 13),
                SelectableText(p.content, style: const TextStyle(fontSize: 15, height: 1.52)),
              ],
              if (p.source != null) ...[
                const SizedBox(height: 12),
                _repostSource(p.source!),
              ],
              if (p.media.isNotEmpty) ...[
                const SizedBox(height: 12),
                _media(p.media),
              ],
              const SizedBox(height: 12),
              if (p.likes > 0 || p.dislikes > 0 || p.comments > 0 || p.reposts > 0)
                Padding(
                  padding: const EdgeInsets.only(bottom: 7),
                  child: Row(
                    children: [
                      if (p.likes > 0) Text('${p.likes} ${p.likes == 1 ? 'like' : 'likes'}', style: const TextStyle(color: AppColors.muted, fontSize: 11.5)),
                      if (p.dislikes > 0) Text(' · ${p.dislikes} dislikes', style: const TextStyle(color: AppColors.muted, fontSize: 11.5)),
                      const Spacer(),
                      if (p.comments > 0) Text('${p.comments} comments', style: const TextStyle(color: AppColors.muted, fontSize: 11.5)),
                      if (p.reposts > 0) Text(' · ${p.reposts} reposts', style: const TextStyle(color: AppColors.muted, fontSize: 11.5)),
                    ],
                  ),
                ),
              const Divider(height: 1),
              Row(
                children: [
                  _action(
                    p.myReaction == 'like' ? Icons.favorite_rounded : Icons.favorite_border_rounded,
                    'Like',
                    p.myReaction == 'like' ? AppColors.danger : AppColors.muted,
                    () => _react(p, 'like'),
                  ),
                  if (showDislikes)
                    _action(
                      p.myReaction == 'dislike' ? Icons.thumb_down_rounded : Icons.thumb_down_outlined,
                      '',
                      p.myReaction == 'dislike' ? AppColors.blue : AppColors.muted,
                      () => _react(p, 'dislike'),
                    ),
                  _action(Icons.mode_comment_outlined, '', AppColors.muted, () => _comments(p)),
                  if (!p.mine)
                    _action(
                      p.reposted ? Icons.repeat_rounded : Icons.repeat_outlined,
                      '',
                      p.reposted ? AppColors.success : AppColors.muted,
                      () => _repost(p),
                    ),
                  const Spacer(),
                  _action(
                    p.saved ? Icons.bookmark_rounded : Icons.bookmark_border_rounded,
                    '',
                    p.saved ? AppColors.blue : AppColors.muted,
                    () => _save(p),
                  ),
                  _action(Icons.ios_share_rounded, '', AppColors.muted, () => _share(p)),
                ],
              ),
            ],
          ),
        ),
      );

  Widget _tag(String text, Color color) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(color: color.withValues(alpha: .10), borderRadius: BorderRadius.circular(14)),
        child: Text(text, style: TextStyle(color: color, fontSize: 9.5, fontWeight: FontWeight.w900)),
      );

  Widget _repostSource(SocialSourcePost s) => Container(
        width: double.infinity,
        padding: const EdgeInsets.all(13),
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surfaceContainerLow,
          borderRadius: BorderRadius.circular(17),
          border: Border.all(color: Theme.of(context).dividerColor),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(s.author, style: const TextStyle(fontWeight: FontWeight.w900)),
            if (s.username.isNotEmpty) Text('@${s.username} · ${s.createdAt}', style: const TextStyle(color: AppColors.muted, fontSize: 11)),
            if (s.subject.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 6), child: _tag(s.subject, AppColors.blue)),
            if (s.content.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 8), child: Text(s.content, maxLines: 6, overflow: TextOverflow.ellipsis, style: const TextStyle(height: 1.4))),
          ],
        ),
      );

  Widget _media(List<SocialMedia> media) {
    final images = media.where((e) => e.isImage).toList();
    final files = media.where((e) => !e.isImage).toList();
    return Column(
      children: [
        if (images.isNotEmpty)
          ClipRRect(
            borderRadius: BorderRadius.circular(17),
            child: GridView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: images.length == 1 ? 1 : 2,
                mainAxisSpacing: 3,
                crossAxisSpacing: 3,
                childAspectRatio: images.length == 1 ? 1.65 : 1,
              ),
              itemCount: images.length.clamp(0, 4),
              itemBuilder: (_, i) => GestureDetector(
                onTap: () => _imageViewer(images, i),
                child: CachedNetworkImage(
                  imageUrl: images[i].url,
                  fit: BoxFit.cover,
                  memCacheWidth: 900,
                  placeholder: (_, _) => Container(color: Theme.of(context).colorScheme.surfaceContainerHighest),
                  errorWidget: (_, _, _) => const Center(child: Icon(Icons.broken_image_outlined)),
                ),
              ),
            ),
          ),
        for (final file in files)
          Padding(
            padding: EdgeInsets.only(top: images.isNotEmpty ? 7 : 0, bottom: 5),
            child: InkWell(
              onTap: () => launchUrl(Uri.parse(file.url), mode: LaunchMode.externalApplication),
              borderRadius: BorderRadius.circular(14),
              child: Container(
                padding: const EdgeInsets.all(11),
                decoration: BoxDecoration(
                  border: Border.all(color: Theme.of(context).dividerColor),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.attach_file_rounded, color: AppColors.blue),
                    const SizedBox(width: 8),
                    Expanded(child: Text(file.name.isEmpty ? 'Attachment' : file.name, maxLines: 1, overflow: TextOverflow.ellipsis)),
                    const Icon(Icons.open_in_new_rounded, size: 18, color: AppColors.muted),
                  ],
                ),
              ),
            ),
          ),
      ],
    );
  }

  void _imageViewer(List<SocialMedia> images, int initial) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => _ImageViewer(images: images, initial: initial),
      ),
    );
  }

  Widget _action(IconData icon, String label, Color color, VoidCallback tap) => InkWell(
        onTap: tap,
        borderRadius: BorderRadius.circular(14),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 11),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 20, color: color),
              if (label.isNotEmpty) ...[
                const SizedBox(width: 5),
                Text(label, style: TextStyle(color: color, fontWeight: FontWeight.w700, fontSize: 12)),
              ],
            ],
          ),
        ),
      );

  void _openProfile(SocialPost p) {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => PublicProfileScreen(username: p.username, userId: p.authorId)),
    );
  }

  Future<void> _react(SocialPost p, String kind) async {
    final old = p.myReaction;
    try {
      final data = await social.reactPost(p.id, kind);
      if (!mounted) return;
      setState(() {
        p.myReaction = data['reaction']?.toString();
        p.likes = smInt(data['likes'] ?? data['count']);
        p.dislikes = smInt(data['dislikes']);
      });
    } catch (e) {
      p.myReaction = old;
      if (mounted) showMessage(context, apiMessage(e));
    }
  }

  Future<void> _save(SocialPost p) async {
    try {
      final data = await social.toggleSave(p.id);
      if (mounted) setState(() => p.saved = smBool(data['saved']));
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    }
  }

  Future<void> _repost(SocialPost p) async {
    try {
      final data = await social.toggleRepost(p.id);
      if (!mounted) return;
      setState(() {
        p.reposted = smBool(data['reposted']);
        p.reposts = smInt(data['count']);
      });
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    }
  }

  Future<void> _share(SocialPost p) async {
    final link = 'https://taleempk.online/post.php?id=${p.id}';
    await Clipboard.setData(ClipboardData(text: link));
    if (mounted) showMessage(context, 'Post link copied.');
  }

  Future<void> _postMenu(SocialPost p, String value) async {
    if (value == 'edit') {
      await _editPost(p);
    } else if (value == 'delete') {
      await _deletePost(p);
    } else if (value == 'report') {
      await _reportPost(p);
    }
  }

  Future<void> _editPost(SocialPost p) async {
    final c = TextEditingController(text: p.content);
    final s = TextEditingController(text: p.subject);
    final save = await showDialog<bool>(
          context: context,
          builder: (d) => AlertDialog(
            title: const Text('Edit post'),
            content: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(controller: c, minLines: 4, maxLines: 8, maxLength: 8000, decoration: const InputDecoration(labelText: 'Post')),
                  const SizedBox(height: 10),
                  TextField(controller: s, maxLength: 100, decoration: const InputDecoration(labelText: 'Subject')),
                ],
              ),
            ),
            actions: [
              TextButton(onPressed: () => Navigator.pop(d, false), child: const Text('Cancel')),
              FilledButton(onPressed: () => Navigator.pop(d, true), child: const Text('Save')),
            ],
          ),
        ) ??
        false;
    if (save && mounted) {
      try {
        await social.editPost(p.id, c.text.trim(), subject: s.text.trim());
        await _refresh();
      } catch (e) {
        if (mounted) showMessage(context, apiMessage(e));
      }
    }
    c.dispose();
    s.dispose();
  }

  Future<void> _deletePost(SocialPost p) async {
    final yes = await showDialog<bool>(
          context: context,
          builder: (d) => AlertDialog(
            title: const Text('Delete post?'),
            content: const Text('This removes the post and its associated content.'),
            actions: [
              TextButton(onPressed: () => Navigator.pop(d, false), child: const Text('Cancel')),
              FilledButton(onPressed: () => Navigator.pop(d, true), child: const Text('Delete')),
            ],
          ),
        ) ??
        false;
    if (!yes || !mounted) return;
    try {
      await social.deletePost(p.id);
      setState(() => posts.removeWhere((e) => e.id == p.id));
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    }
  }

  Future<void> _reportPost(SocialPost p) async {
    final c = TextEditingController();
    final send = await showDialog<bool>(
          context: context,
          builder: (d) => AlertDialog(
            title: const Text('Report post'),
            content: TextField(controller: c, minLines: 3, maxLines: 6, decoration: const InputDecoration(labelText: 'Why are you reporting this?')),
            actions: [
              TextButton(onPressed: () => Navigator.pop(d, false), child: const Text('Cancel')),
              FilledButton(onPressed: () => Navigator.pop(d, true), child: const Text('Report')),
            ],
          ),
        ) ??
        false;
    if (send && mounted) {
      try {
        await AppScope.of(context).api.reportUser(p.authorId, reason: 'post', details: 'Post #${p.id}: ${c.text.trim()}');
        if (mounted) showMessage(context, 'Report sent to the moderation team.');
      } catch (e) {
        if (mounted) showMessage(context, apiMessage(e));
      }
    }
    c.dispose();
  }

  Future<void> _createPost() async {
    final c = TextEditingController();
    final s = TextEditingController(text: subject);
    var type = 'text', visibility = 'public';
    var anonymous = false, sending = false;
    var upload = 0.0;
    final files = <String>[];

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (sheet) => StatefulBuilder(
        builder: (sheet, setModal) => Padding(
          padding: EdgeInsets.fromLTRB(18, 8, 18, MediaQuery.viewInsetsOf(sheet).bottom + 18),
          child: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text('Create post', style: Theme.of(sheet).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w900)),
                const SizedBox(height: 14),
                SegmentedButton<String>(
                  segments: const [
                    ButtonSegment(value: 'text', icon: Icon(Icons.notes_rounded), label: Text('Post')),
                    ButtonSegment(value: 'question', icon: Icon(Icons.help_outline_rounded), label: Text('Question')),
                  ],
                  selected: {type},
                  onSelectionChanged: sending ? null : (v) => setModal(() { type = v.first; if (type != 'question') anonymous = false; }),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: c,
                  autofocus: true,
                  minLines: 5,
                  maxLines: 10,
                  maxLength: 8000,
                  decoration: InputDecoration(hintText: type == 'question' ? 'What do you want to ask?' : 'What would you like to share?'),
                ),
                const SizedBox(height: 8),
                TextField(controller: s, maxLength: 100, decoration: const InputDecoration(labelText: 'Subject (optional)')),
                const SizedBox(height: 8),
                DropdownButtonFormField<String>(
                  initialValue: visibility,
                  decoration: const InputDecoration(labelText: 'Who can see this?'),
                  items: const [
                    DropdownMenuItem(value: 'public', child: Text('Public')),
                    DropdownMenuItem(value: 'followers', child: Text('Followers')),
                  ],
                  onChanged: sending ? null : (v) => setModal(() => visibility = v ?? 'public'),
                ),
                if (type == 'question')
                  SwitchListTile.adaptive(
                    contentPadding: EdgeInsets.zero,
                    value: anonymous,
                    onChanged: sending ? null : (v) => setModal(() => anonymous = v),
                    title: const Text('Ask anonymously'),
                    subtitle: const Text('Your name will not appear on this question.'),
                  ),
                const SizedBox(height: 7),
                OutlinedButton.icon(
                  onPressed: sending || files.length >= 4
                      ? null
                      : () async {
                          final picked = await FilePicker.platform.pickFiles(
                            allowMultiple: true,
                            type: FileType.custom,
                            allowedExtensions: const ['jpg', 'jpeg', 'png', 'webp', 'pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'txt', 'zip'],
                          );
                          if (picked == null) return;
                          setModal(() {
                            for (final f in picked.files) {
                              if (f.path != null && files.length < 4) files.add(f.path!);
                            }
                          });
                        },
                  icon: const Icon(Icons.attach_file_rounded),
                  label: Text(files.isEmpty ? 'Add photos or files' : '${files.length}/4 attachments'),
                ),
                for (var i = 0; i < files.length; i++)
                  ListTile(
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                    leading: const Icon(Icons.insert_drive_file_outlined, size: 20),
                    title: Text(files[i].split('/').last, maxLines: 1, overflow: TextOverflow.ellipsis),
                    trailing: IconButton(onPressed: sending ? null : () => setModal(() => files.removeAt(i)), icon: const Icon(Icons.close_rounded, size: 19)),
                  ),
                if (sending) ...[
                  LinearProgressIndicator(value: upload > 0 ? upload : null),
                  const SizedBox(height: 7),
                  Text(upload > 0 ? 'Uploading ${(upload * 100).round()}%' : 'Publishing…', textAlign: TextAlign.center, style: const TextStyle(color: AppColors.muted)),
                ],
                const SizedBox(height: 10),
                FilledButton.icon(
                  onPressed: sending
                      ? null
                      : () async {
                          if (c.text.trim().isEmpty && files.isEmpty) {
                            showMessage(sheet, 'Write something or attach a file.');
                            return;
                          }
                          setModal(() { sending = true; upload = 0; });
                          try {
                            await social.createPost(
                              content: c.text.trim(),
                              type: type,
                              visibility: visibility,
                              subject: s.text.trim(),
                              anonymous: anonymous,
                              files: files,
                              onProgress: (v) {
                                if (sheet.mounted) setModal(() => upload = v);
                              },
                            );
                            if (sheet.mounted) Navigator.pop(sheet);
                            await _refresh();
                          } catch (e) {
                            if (sheet.mounted) {
                              setModal(() => sending = false);
                              showMessage(sheet, apiMessage(e));
                            }
                          }
                        },
                  icon: const Icon(Icons.send_rounded),
                  label: const Text('Publish'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
    c.dispose();
    s.dispose();
  }

  Future<void> _comments(SocialPost post) async {
    final c = TextEditingController();
    var refreshKey = 0;
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (sheet) => StatefulBuilder(
        builder: (sheet, setModal) => FractionallySizedBox(
          heightFactor: .88,
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(18, 4, 12, 11),
                child: Row(
                  children: [
                    const Icon(Icons.forum_outlined, color: AppColors.blue),
                    const SizedBox(width: 8),
                    const Expanded(child: Text('Comments', style: TextStyle(fontWeight: FontWeight.w900, fontSize: 19))),
                    IconButton(onPressed: () => Navigator.pop(sheet), icon: const Icon(Icons.close_rounded)),
                  ],
                ),
              ),
              const Divider(height: 1),
              Expanded(
                child: FutureBuilder<List<FeedComment>>(
                  key: ValueKey(refreshKey),
                  future: AppScope.of(context).api.comments(post.id),
                  builder: (context, snap) {
                    if (snap.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
                    if (snap.hasError) return ErrorView(message: apiMessage(snap.error!), retry: () => setModal(() => refreshKey++));
                    final rows = snap.data ?? const <FeedComment>[];
                    if (rows.isEmpty) return const EmptyView(icon: Icons.chat_bubble_outline_rounded, title: 'No comments yet', message: 'Be the first to add a helpful response.');
                    return ListView.separated(
                      padding: const EdgeInsets.all(13),
                      itemCount: rows.length,
                      separatorBuilder: (_, _) => const SizedBox(height: 8),
                      itemBuilder: (_, i) {
                        final r = rows[i];
                        return Container(
                          padding: const EdgeInsets.fromLTRB(12, 10, 6, 10),
                          decoration: BoxDecoration(
                            color: Theme.of(context).colorScheme.surfaceContainerLow,
                            borderRadius: BorderRadius.circular(16),
                          ),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              UserAvatar(name: r.author, radius: 18),
                              const SizedBox(width: 9),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(r.author, style: const TextStyle(fontWeight: FontWeight.w800)),
                                    const SizedBox(height: 3),
                                    Text(r.content, style: const TextStyle(height: 1.4)),
                                    const SizedBox(height: 4),
                                    Text(r.createdAt, style: const TextStyle(color: AppColors.muted, fontSize: 10.5)),
                                  ],
                                ),
                              ),
                              if (r.mine)
                                PopupMenuButton<String>(
                                  onSelected: (v) async {
                                    if (v == 'edit') {
                                      final e = TextEditingController(text: r.content);
                                      final save = await showDialog<bool>(
                                            context: context,
                                            builder: (d) => AlertDialog(
                                              title: const Text('Edit comment'),
                                              content: TextField(controller: e, minLines: 3, maxLines: 7),
                                              actions: [
                                                TextButton(onPressed: () => Navigator.pop(d, false), child: const Text('Cancel')),
                                                FilledButton(onPressed: () => Navigator.pop(d, true), child: const Text('Save')),
                                              ],
                                            ),
                                          ) ??
                                          false;
                                      if (save) {
                                        try {
                                          await AppScope.of(context).api.editComment(r.id, e.text.trim());
                                          if (sheet.mounted) setModal(() => refreshKey++);
                                        } catch (err) {
                                          if (sheet.mounted) showMessage(sheet, apiMessage(err));
                                        }
                                      }
                                      e.dispose();
                                    } else if (v == 'delete') {
                                      try {
                                        await AppScope.of(context).api.deleteComment(r.id);
                                        if (sheet.mounted) {
                                          setModal(() => refreshKey++);
                                          setState(() => post.comments = (post.comments - 1).clamp(0, 1 << 30));
                                        }
                                      } catch (err) {
                                        if (sheet.mounted) showMessage(sheet, apiMessage(err));
                                      }
                                    }
                                  },
                                  itemBuilder: (_) => const [
                                    PopupMenuItem(value: 'edit', child: Text('Edit')),
                                    PopupMenuItem(value: 'delete', child: Text('Delete')),
                                  ],
                                ),
                            ],
                          ),
                        );
                      },
                    );
                  },
                ),
              ),
              SafeArea(
                top: false,
                child: Container(
                  padding: EdgeInsets.fromLTRB(12, 9, 12, MediaQuery.viewInsetsOf(sheet).bottom + 9),
                  decoration: BoxDecoration(border: Border(top: BorderSide(color: Theme.of(context).dividerColor))),
                  child: Row(
                    children: [
                      Expanded(child: TextField(controller: c, minLines: 1, maxLines: 4, decoration: const InputDecoration(hintText: 'Add a comment…'))),
                      const SizedBox(width: 7),
                      IconButton.filled(
                        onPressed: () async {
                          final text = c.text.trim();
                          if (text.isEmpty) return;
                          try {
                            await AppScope.of(context).api.addComment(post.id, text);
                            c.clear();
                            if (sheet.mounted) {
                              setModal(() => refreshKey++);
                              setState(() => post.comments++);
                            }
                          } catch (e) {
                            if (sheet.mounted) showMessage(sheet, apiMessage(e));
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
}

class _ImageViewer extends StatefulWidget {
  const _ImageViewer({required this.images, required this.initial});
  final List<SocialMedia> images;
  final int initial;

  @override
  State<_ImageViewer> createState() => _ImageViewerState();
}

class _ImageViewerState extends State<_ImageViewer> {
  late final PageController page = PageController(initialPage: widget.initial);
  late int index = widget.initial;

  @override
  void dispose() {
    page.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        backgroundColor: Colors.black,
        appBar: AppBar(
          backgroundColor: Colors.black,
          foregroundColor: Colors.white,
          title: Text('${index + 1} / ${widget.images.length}'),
          actions: [
            IconButton(
              onPressed: () => launchUrl(Uri.parse(widget.images[index].url), mode: LaunchMode.externalApplication),
              icon: const Icon(Icons.open_in_new_rounded),
            ),
          ],
        ),
        body: PageView.builder(
          controller: page,
          itemCount: widget.images.length,
          onPageChanged: (v) => setState(() => index = v),
          itemBuilder: (_, i) => InteractiveViewer(
            minScale: .7,
            maxScale: 5,
            child: Center(
              child: CachedNetworkImage(
                imageUrl: widget.images[i].url,
                fit: BoxFit.contain,
                placeholder: (_, _) => const CircularProgressIndicator(),
                errorWidget: (_, _, _) => const Icon(Icons.broken_image_outlined, color: Colors.white, size: 48),
              ),
            ),
          ),
        ),
      );
}
