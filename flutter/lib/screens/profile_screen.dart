import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../core/app_state.dart';
import '../core/social_api.dart';
import '../core/social_models.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'home_shell.dart';
import 'module_screen.dart';
import 'security_screen.dart';
import 'verification_screen.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) => const _ProfileView();
}

class PublicProfileScreen extends StatelessWidget {
  const PublicProfileScreen({super.key, this.username = '', this.userId = 0});
  final String username;
  final int userId;

  @override
  Widget build(BuildContext context) => _ProfileView(username: username, userId: userId);
}

class _ProfileView extends StatefulWidget {
  const _ProfileView({this.username = '', this.userId = 0});
  final String username;
  final int userId;

  @override
  State<_ProfileView> createState() => _ProfileViewState();
}

class _ProfileViewState extends State<_ProfileView> with AutomaticKeepAliveClientMixin {
  ProfileData? profile;
  bool loading = true, actionBusy = false;
  String? error;
  String tab = 'posts';
  final activity = <ProfileActivityItem>[];
  bool activityLoading = false, activityMore = true;
  int activityBefore = 0;

  SocialApi get social => SocialApi(AppScope.of(context).api);

  @override
  bool get wantKeepAlive => widget.username.isEmpty && widget.userId == 0;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load({bool refresh = false}) async {
    if (mounted) setState(() { loading = true; error = null; });
    try {
      final ownId = widget.userId == 0 && widget.username.isEmpty ? AppScope.of(context).user?.id ?? 0 : widget.userId;
      final value = await social.profile(
        username: widget.username,
        userId: ownId,
        refresh: refresh,
      );
      if (mounted) {
        setState(() {
          profile = value;
          loading = false;
        });
      }
      await _loadActivity(reset: true);
    } catch (e) {
      if (mounted) setState(() { error = apiMessage(e); loading = false; });
    }
  }

  Future<void> _loadActivity({bool reset = false}) async {
    final p = profile;
    if (p == null || activityLoading || (!reset && !activityMore)) return;
    setState(() {
      activityLoading = true;
      if (reset) {
        activity.clear();
        activityBefore = 0;
        activityMore = true;
      }
    });
    try {
      final page = await social.profileActivity(p.id, tab, before: activityBefore);
      if (!mounted) return;
      setState(() {
        activity.addAll(page.items);
        activityBefore = page.nextBefore;
        activityMore = page.hasMore;
      });
    } catch (_) {
      // Header remains usable if a secondary activity tab is temporarily unavailable.
    } finally {
      if (mounted) setState(() => activityLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    return Scaffold(
      appBar: PremiumAppBar(
        title: profile?.isMe == false ? profile!.name : 'Your profile',
        subtitle: profile == null ? 'Identity & learning profile' : '@${profile!.username}',
        actions: [
          if (profile?.isMe == true)
            IconButton(
              tooltip: 'Theme',
              onPressed: AppScope.of(context).toggleTheme,
              icon: Icon(AppScope.of(context).darkMode ? Icons.light_mode_outlined : Icons.dark_mode_outlined),
            ),
          if (profile?.isMe == false)
            PopupMenuButton<String>(
              onSelected: _profileMenu,
              itemBuilder: (_) => [
                PopupMenuItem(value: 'block', child: Text(profile?.iBlocked == true ? 'Unblock' : 'Block')),
                const PopupMenuItem(value: 'report', child: Text('Report profile')),
              ],
            ),
        ],
      ),
      body: loading
          ? const Center(child: CircularProgressIndicator())
          : error != null
              ? ErrorView(message: error!, retry: () => _load(refresh: true))
              : RefreshIndicator(
                  onRefresh: () => _load(refresh: true),
                  child: ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.only(bottom: 28),
                    children: [
                      _header(profile!),
                      if (profile!.blocked || profile!.private)
                        _restricted(profile!)
                      else ...[
                        _about(profile!),
                        _credentials(profile!),
                        _actions(profile!),
                        _tabs(),
                        _activityList(),
                      ],
                    ],
                  ),
                ),
    );
  }

  Widget _header(ProfileData p) => Column(
        children: [
          SizedBox(
            height: 182,
            child: Stack(
              clipBehavior: Clip.none,
              children: [
                Positioned.fill(
                  bottom: 48,
                  child: Container(
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(
                        colors: [AppColors.navy, Color(0xFF3157E8), Color(0xFF7657EF)],
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                      ),
                      image: p.cover != null
                          ? DecorationImage(
                              image: CachedNetworkImageProvider(p.cover!),
                              fit: BoxFit.cover,
                            )
                          : null,
                    ),
                  ),
                ),
                Positioned(
                  left: 18,
                  bottom: 12,
                  child: Container(
                    padding: const EdgeInsets.all(4),
                    decoration: BoxDecoration(
                      color: Theme.of(context).scaffoldBackgroundColor,
                      shape: BoxShape.circle,
                    ),
                    child: UserAvatar(url: p.avatar, name: p.name, radius: 47),
                  ),
                ),
                if (p.verified)
                  Positioned(
                    left: 95,
                    bottom: 20,
                    child: Container(
                      padding: const EdgeInsets.all(5),
                      decoration: const BoxDecoration(color: AppColors.blue, shape: BoxShape.circle),
                      child: const Icon(Icons.verified_rounded, color: Colors.white, size: 19),
                    ),
                  ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(18, 0, 18, 4),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Flexible(
                            child: Text(
                              p.name,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(fontSize: 23, fontWeight: FontWeight.w900, letterSpacing: -.4),
                            ),
                          ),
                          if (p.verified) ...[
                            const SizedBox(width: 5),
                            const Icon(Icons.verified_rounded, color: AppColors.blue, size: 20),
                          ],
                        ],
                      ),
                      Text('@${p.username}', style: const TextStyle(color: AppColors.muted)),
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 6,
                        runSpacing: 6,
                        children: [
                          _chip(p.role.toUpperCase(), AppColors.blue),
                          if (p.level.isNotEmpty) _chip(p.level, AppColors.violet),
                          if (p.classGrade.isNotEmpty) _chip(p.classGrade, AppColors.violet),
                          if (p.city.isNotEmpty) _chip(p.city, AppColors.success),
                          if (p.followsYou) _chip('Follows you', AppColors.success),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 10),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 18),
            child: Row(
              children: [
                _stat('${p.posts}', 'Posts'),
                _stat('${p.followers}', 'Followers'),
                _stat('${p.following}', 'Following'),
                if ((p.role == 'teacher' || p.role == 'institute') && p.ratings > 0)
                  _stat(p.rating.toStringAsFixed(1), '★ ${p.ratings}'),
              ],
            ),
          ),
        ],
      );

  Widget _stat(String value, String label) => Expanded(
        child: Column(
          children: [
            Text(value, style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 17)),
            Text(label, style: const TextStyle(color: AppColors.muted, fontSize: 11.5)),
          ],
        ),
      );

  Widget _chip(String text, Color color) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
        decoration: BoxDecoration(color: color.withValues(alpha: .10), borderRadius: BorderRadius.circular(20)),
        child: Text(text, style: TextStyle(color: color, fontSize: 10.5, fontWeight: FontWeight.w800)),
      );

  Widget _restricted(ProfileData p) => Padding(
        padding: const EdgeInsets.all(18),
        child: EmptyView(
          icon: p.blocked ? Icons.block_rounded : Icons.lock_outline_rounded,
          title: p.blocked ? 'Profile unavailable' : 'Private profile',
          message: p.blocked ? 'A block between these accounts prevents profile details from being shown.' : 'This member has limited who can view their profile.',
        ),
      );

  Widget _about(ProfileData p) {
    if (p.bio.isEmpty && p.headline.isEmpty && p.city.isEmpty && p.country.isEmpty) return const SizedBox(height: 8);
    return Padding(
      padding: const EdgeInsets.fromLTRB(18, 14, 18, 0),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (p.headline.isNotEmpty)
                Text(p.headline, style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 15)),
              if (p.headline.isNotEmpty && p.bio.isNotEmpty) const SizedBox(height: 8),
              if (p.bio.isNotEmpty) Text(p.bio, style: const TextStyle(height: 1.5)),
              if (p.city.isNotEmpty || p.country.isNotEmpty) ...[
                const SizedBox(height: 10),
                Row(
                  children: [
                    const Icon(Icons.location_on_outlined, size: 18, color: AppColors.muted),
                    const SizedBox(width: 5),
                    Expanded(child: Text([p.city, p.country].where((e) => e.isNotEmpty).join(', '), style: const TextStyle(color: AppColors.muted))),
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _credentials(ProfileData p) {
    final has = p.verified || p.subjects.isNotEmpty || p.qualification.isNotEmpty || p.institute.isNotEmpty || p.degree.isNotEmpty;
    if (!has) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.fromLTRB(18, 12, 18, 0),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (p.verified) ...[
                Row(
                  children: [
                    const Icon(Icons.verified_rounded, color: AppColors.blue),
                    const SizedBox(width: 8),
                    Expanded(child: Text('Verified ${p.verifiedKind.isNotEmpty ? p.verifiedKind : p.role}', style: const TextStyle(fontWeight: FontWeight.w900))),
                  ],
                ),
                if (p.verifiedAt.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 4), child: Text('Identity and role checked by TaleemPK.', style: const TextStyle(color: AppColors.muted, fontSize: 12))),
                const Divider(height: 22),
              ],
              if (p.qualification.isNotEmpty) _detail(Icons.workspace_premium_outlined, 'Qualification', p.qualification),
              if (p.subjects.isNotEmpty) _detail(Icons.menu_book_outlined, 'Subjects', p.subjects),
              if (p.experience > 0) _detail(Icons.history_edu_outlined, 'Experience', '${p.experience} years'),
              if (p.institute.isNotEmpty) _detail(Icons.account_balance_outlined, 'Institute', p.institute),
              if (p.degree.isNotEmpty) _detail(Icons.school_outlined, 'Education', [p.degree, p.department, p.semester].where((e) => e.isNotEmpty).join(' · ')),
              if (p.acceptingStudents)
                Padding(
                  padding: const EdgeInsets.only(top: 7),
                  child: _chip('Currently taking students', AppColors.success),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _detail(IconData icon, String label, String value) => Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, size: 20, color: AppColors.blue),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(label, style: const TextStyle(fontSize: 10.5, color: AppColors.muted, fontWeight: FontWeight.w800)),
                  Text(value, style: const TextStyle(fontWeight: FontWeight.w700)),
                ],
              ),
            ),
          ],
        ),
      );

  Widget _actions(ProfileData p) => Padding(
        padding: const EdgeInsets.fromLTRB(18, 14, 18, 0),
        child: p.isMe
            ? Column(
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: FilledButton.icon(
                          onPressed: () => _editProfile(p),
                          icon: const Icon(Icons.edit_outlined),
                          label: const Text('Edit profile'),
                        ),
                      ),
                      const SizedBox(width: 9),
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const VerificationScreen())).then((_) => _load(refresh: true)),
                          icon: const Icon(Icons.verified_user_outlined),
                          label: Text(p.verified ? 'Verification' : 'Get verified'),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 9),
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const SecurityScreen())),
                          icon: const Icon(Icons.shield_outlined),
                          label: const Text('Privacy & security'),
                        ),
                      ),
                      const SizedBox(width: 9),
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const ModuleScreen(module: 'support'))),
                          icon: const Icon(Icons.support_agent_rounded),
                          label: const Text('Support'),
                        ),
                      ),
                    ],
                  ),
                ],
              )
            : Row(
                children: [
                  Expanded(
                    child: FilledButton.icon(
                      onPressed: actionBusy ? null : _toggleFollow,
                      icon: Icon(p.isFollowing ? Icons.person_remove_alt_1_outlined : Icons.person_add_alt_1_rounded),
                      label: Text(p.isFollowing ? 'Following' : 'Follow'),
                    ),
                  ),
                  const SizedBox(width: 9),
                  OutlinedButton.icon(
                    onPressed: actionBusy ? null : () => _report(p.id),
                    icon: const Icon(Icons.flag_outlined),
                    label: const Text('Report'),
                  ),
                ],
              ),
      );

  Widget _tabs() => Padding(
        padding: const EdgeInsets.fromLTRB(12, 18, 12, 6),
        child: SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: [
              for (final item in const [('posts', 'Posts'), ('uploads', 'Uploads'), ('answers', 'Answers'), ('badges', 'Badges')])
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 3),
                  child: ChoiceChip(
                    label: Text(item.$2),
                    selected: tab == item.$1,
                    onSelected: (_) {
                      if (tab == item.$1) return;
                      setState(() => tab = item.$1);
                      _loadActivity(reset: true);
                    },
                  ),
                ),
            ],
          ),
        ),
      );

  Widget _activityList() {
    if (activityLoading && activity.isEmpty) {
      return const Padding(padding: EdgeInsets.all(28), child: Center(child: CircularProgressIndicator()));
    }
    if (activity.isEmpty) {
      return const Padding(
        padding: EdgeInsets.all(18),
        child: EmptyView(icon: Icons.auto_stories_outlined, title: 'Nothing here yet', message: 'This section will fill as this member contributes to TaleemPK.'),
      );
    }
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 18),
      child: Column(
        children: [
          for (final item in activity)
            Card(
              margin: const EdgeInsets.only(bottom: 9),
              child: ListTile(
                contentPadding: const EdgeInsets.symmetric(horizontal: 15, vertical: 7),
                leading: Icon(
                  item.kind == 'badge' ? Icons.workspace_premium_rounded : item.kind == 'answer' ? Icons.question_answer_outlined : Icons.article_outlined,
                  color: AppColors.blue,
                ),
                title: Text(item.title, maxLines: 3, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w800)),
                subtitle: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (item.subtitle.isNotEmpty) Text(item.subtitle, maxLines: 2, overflow: TextOverflow.ellipsis),
                    if (item.meta.isNotEmpty) Text(item.meta, style: const TextStyle(color: AppColors.muted, fontSize: 11)),
                  ],
                ),
              ),
            ),
          if (activityMore)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: OutlinedButton(
                onPressed: activityLoading ? null : _loadActivity,
                child: activityLoading ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)) : const Text('Load more'),
              ),
            ),
        ],
      ),
    );
  }

  Future<void> _toggleFollow() async {
    final p = profile!;
    setState(() => actionBusy = true);
    try {
      final following = await social.toggleFollow(p.id);
      if (mounted) {
        setState(() {
          if (following != p.isFollowing) p.followers += following ? 1 : -1;
          p.isFollowing = following;
        });
      }
    } catch (e) {
      if (mounted) showMessage(context, apiMessage(e));
    } finally {
      if (mounted) setState(() => actionBusy = false);
    }
  }

  Future<void> _profileMenu(String value) async {
    final p = profile;
    if (p == null) return;
    if (value == 'report') {
      await _report(p.id);
    } else if (value == 'block') {
      setState(() => actionBusy = true);
      try {
        await AppScope.of(context).api.toggleBlock(p.id);
        await _load(refresh: true);
      } catch (e) {
        if (mounted) showMessage(context, apiMessage(e));
      } finally {
        if (mounted) setState(() => actionBusy = false);
      }
    }
  }

  Future<void> _report(int userId) async {
    final details = TextEditingController();
    var reason = 'other';
    final submit = await showDialog<bool>(
          context: context,
          builder: (d) => StatefulBuilder(
            builder: (d, setDialog) => AlertDialog(
              title: const Text('Report profile'),
              content: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  DropdownButtonFormField<String>(
                    initialValue: reason,
                    items: const [
                      DropdownMenuItem(value: 'spam', child: Text('Spam')),
                      DropdownMenuItem(value: 'harassment', child: Text('Harassment')),
                      DropdownMenuItem(value: 'impersonation', child: Text('Impersonation')),
                      DropdownMenuItem(value: 'other', child: Text('Other')),
                    ],
                    onChanged: (v) => setDialog(() => reason = v ?? 'other'),
                  ),
                  const SizedBox(height: 10),
                  TextField(controller: details, minLines: 2, maxLines: 5, decoration: const InputDecoration(labelText: 'Details (optional)')),
                ],
              ),
              actions: [
                TextButton(onPressed: () => Navigator.pop(d, false), child: const Text('Cancel')),
                FilledButton(onPressed: () => Navigator.pop(d, true), child: const Text('Send report')),
              ],
            ),
          ),
        ) ??
        false;
    if (submit && mounted) {
      try {
        await AppScope.of(context).api.reportUser(userId, reason: reason, details: details.text.trim());
        if (mounted) showMessage(context, 'Report sent to the moderation team.');
      } catch (e) {
        if (mounted) showMessage(context, apiMessage(e));
      }
    }
    details.dispose();
  }

  Future<void> _editProfile(ProfileData p) async {
    final name = TextEditingController(text: p.name);
    final headline = TextEditingController(text: p.headline);
    final bio = TextEditingController(text: p.bio);
    final city = TextEditingController(text: p.city);
    final phone = TextEditingController(text: p.phone);
    final subjects = TextEditingController(text: p.subjects);
    final qualification = TextEditingController(text: p.qualification);
    final experience = TextEditingController(text: p.experience > 0 ? '${p.experience}' : '');
    final institute = TextEditingController(text: p.institute);
    final degree = TextEditingController(text: p.degree);
    final department = TextEditingController(text: p.department);
    final semester = TextEditingController(text: p.semester);
    final teaches = TextEditingController(text: p.teaches);
    final website = TextEditingController(text: p.website);
    var level = p.level;
    var accepting = p.acceptingStudents;
    String? avatarPath, coverPath;
    bool saving = false;

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (sheet) => StatefulBuilder(
        builder: (sheet, setModal) => Padding(
          padding: EdgeInsets.fromLTRB(18, 6, 18, MediaQuery.viewInsetsOf(sheet).bottom + 18),
          child: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text('Edit profile', style: Theme.of(sheet).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w900)),
                const SizedBox(height: 14),
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: saving ? null : () async {
                          final image = await ImagePicker().pickImage(source: ImageSource.gallery, imageQuality: 88, maxWidth: 1600);
                          if (image != null) setModal(() => avatarPath = image.path);
                        },
                        icon: const Icon(Icons.account_circle_outlined),
                        label: Text(avatarPath == null ? 'Change photo' : 'Photo selected'),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: saving ? null : () async {
                          final image = await ImagePicker().pickImage(source: ImageSource.gallery, imageQuality: 88, maxWidth: 2200);
                          if (image != null) setModal(() => coverPath = image.path);
                        },
                        icon: const Icon(Icons.panorama_outlined),
                        label: Text(coverPath == null ? 'Change cover' : 'Cover selected'),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                TextField(controller: name, decoration: const InputDecoration(labelText: 'Full name')),
                const SizedBox(height: 10),
                TextField(controller: headline, maxLength: 160, decoration: const InputDecoration(labelText: 'Headline')),
                const SizedBox(height: 10),
                TextField(controller: bio, minLines: 3, maxLines: 6, maxLength: 480, decoration: const InputDecoration(labelText: 'About you')),
                const SizedBox(height: 10),
                TextField(controller: city, decoration: const InputDecoration(labelText: 'City')),
                const SizedBox(height: 10),
                TextField(controller: phone, keyboardType: TextInputType.phone, decoration: const InputDecoration(labelText: 'Phone')),
                const SizedBox(height: 10),
                DropdownButtonFormField<String>(
                  initialValue: ['', 'school', 'college', 'university'].contains(level) ? level : '',
                  decoration: const InputDecoration(labelText: 'Education level'),
                  items: const [
                    DropdownMenuItem(value: '', child: Text('Not specified')),
                    DropdownMenuItem(value: 'school', child: Text('School')),
                    DropdownMenuItem(value: 'college', child: Text('College')),
                    DropdownMenuItem(value: 'university', child: Text('University')),
                  ],
                  onChanged: saving ? null : (v) => setModal(() => level = v ?? ''),
                ),
                const SizedBox(height: 10),
                TextField(controller: institute, decoration: const InputDecoration(labelText: 'Institute')),
                const SizedBox(height: 10),
                TextField(controller: degree, decoration: const InputDecoration(labelText: 'Degree / class')),
                const SizedBox(height: 10),
                TextField(controller: department, decoration: const InputDecoration(labelText: 'Department')),
                const SizedBox(height: 10),
                TextField(controller: semester, decoration: const InputDecoration(labelText: 'Semester')),
                const SizedBox(height: 10),
                TextField(controller: subjects, decoration: const InputDecoration(labelText: 'Subjects')),
                const SizedBox(height: 10),
                TextField(controller: qualification, decoration: const InputDecoration(labelText: 'Qualification')),
                const SizedBox(height: 10),
                TextField(controller: experience, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Experience (years)')),
                const SizedBox(height: 10),
                TextField(controller: teaches, decoration: const InputDecoration(labelText: 'Teaches / specialization')),
                const SizedBox(height: 10),
                TextField(controller: website, keyboardType: TextInputType.url, decoration: const InputDecoration(labelText: 'Website')),
                if (p.role == 'teacher' || p.role == 'institute')
                  SwitchListTile.adaptive(
                    contentPadding: EdgeInsets.zero,
                    value: accepting,
                    onChanged: saving ? null : (v) => setModal(() => accepting = v),
                    title: const Text('Currently taking students'),
                  ),
                const SizedBox(height: 8),
                FilledButton.icon(
                  onPressed: saving
                      ? null
                      : () async {
                          if (name.text.trim().length < 3) {
                            showMessage(sheet, 'Enter your full name.');
                            return;
                          }
                          setModal(() => saving = true);
                          try {
                            await social.updateProfile(
                              fields: {
                                'name': name.text.trim(),
                                'headline': headline.text.trim(),
                                'bio': bio.text.trim(),
                                'city': city.text.trim(),
                                'phone': phone.text.trim(),
                                'level': level,
                                'institute': institute.text.trim(),
                                'degree': degree.text.trim(),
                                'department': department.text.trim(),
                                'semester': semester.text.trim(),
                                'subjects': subjects.text.trim(),
                                'qualification': qualification.text.trim(),
                                'experience': experience.text.trim(),
                                'teaches': teaches.text.trim(),
                                'website': website.text.trim(),
                                'accepting_students': accepting ? '1' : '0',
                              },
                              avatarPath: avatarPath,
                              coverPath: coverPath,
                            );
                            await AppScope.of(context).refreshSession();
                            if (sheet.mounted) Navigator.pop(sheet);
                            await _load(refresh: true);
                          } catch (e) {
                            if (sheet.mounted) {
                              setModal(() => saving = false);
                              showMessage(sheet, apiMessage(e));
                            }
                          }
                        },
                  icon: const Icon(Icons.save_outlined),
                  label: Text(saving ? 'Saving…' : 'Save profile'),
                ),
              ],
            ),
          ),
        ),
      ),
    );

    for (final c in [name, headline, bio, city, phone, subjects, qualification, experience, institute, degree, department, semester, teaches, website]) {
      c.dispose();
    }
  }
}
