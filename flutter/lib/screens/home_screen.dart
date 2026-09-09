import 'package:flutter/material.dart';

import '../core/app_state.dart';
import '../core/models.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'home_shell.dart';
import 'module_screen.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});
  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context),
        data = state.bootstrap!,
        user = data.user;
    return Scaffold(
      appBar: PremiumAppBar(
        title: 'Hello, ${user.name.split(' ').first}',
        subtitle: 'Ready to learn something new?',
        actions: [
          IconButton(
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => const ModuleScreen(module: 'notifications'),
              ),
            ),
            icon: const Badge(child: Icon(Icons.notifications_none_rounded)),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: state.refreshSession,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(18, 8, 18, 28),
          children: [
            _hero(context, user),
            const SizedBox(height: 22),
            const Text(
              'Community today',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w800,
                color: AppColors.ink,
              ),
            ),
            const SizedBox(height: 12),
            GridView.count(
              crossAxisCount: 2,
              childAspectRatio: 1.55,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              mainAxisSpacing: 12,
              crossAxisSpacing: 12,
              children: [
                _stat(
                  'Members',
                  data.stats.members,
                  Icons.groups_2_rounded,
                  AppColors.blue,
                ),
                _stat(
                  'Active today',
                  data.stats.activeToday,
                  Icons.bolt_rounded,
                  AppColors.success,
                ),
                _stat(
                  'Messages',
                  data.stats.messagesToday,
                  Icons.forum_rounded,
                  AppColors.violet,
                ),
                _stat(
                  'Quiz attempts',
                  data.stats.quizAttempts,
                  Icons.workspace_premium_rounded,
                  const Color(0xFFF19B38),
                ),
              ],
            ),
            const SizedBox(height: 24),
            const Text(
              'Your learning space',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w800,
                color: AppColors.ink,
              ),
            ),
            const SizedBox(height: 12),
            ...data.shortcuts
                .where((s) => !['feed.php', 'chat.php'].contains(s.route))
                .map(
                  (s) => Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: _shortcut(context, s),
                  ),
                ),
          ],
        ),
      ),
    );
  }

  Widget _hero(BuildContext context, User user) => Container(
    padding: const EdgeInsets.all(22),
    decoration: BoxDecoration(
      gradient: const LinearGradient(
        colors: [AppColors.navy, AppColors.navySoft, Color(0xFF4B35A4)],
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
      ),
      borderRadius: BorderRadius.circular(26),
      boxShadow: const [
        BoxShadow(
          color: Color(0x33264DD3),
          blurRadius: 24,
          offset: Offset(0, 12),
        ),
      ],
    ),
    child: Row(
      children: [
        UserAvatar(url: user.avatar, name: user.name, radius: 29),
        const SizedBox(width: 16),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Flexible(
                    child: Text(
                      user.name,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 20,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                  if (user.verified)
                    const Padding(
                      padding: EdgeInsets.only(left: 6),
                      child: Icon(
                        Icons.verified_rounded,
                        color: Color(0xFF5DD9FF),
                        size: 19,
                      ),
                    ),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                '@${user.username} · ${_role(user.role)}',
                style: const TextStyle(color: Color(0xBFFFFFFF)),
              ),
            ],
          ),
        ),
        const Icon(
          Icons.auto_awesome_rounded,
          color: Color(0xFFFFD667),
          size: 30,
        ),
      ],
    ),
  );

  Widget _stat(String label, int value, IconData icon, Color color) => Card(
    child: Padding(
      padding: const EdgeInsets.all(15),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: color.withValues(alpha: .11),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Icon(icon, color: color, size: 22),
          ),
          const SizedBox(width: 11),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  _compact(value),
                  style: const TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.w900,
                    color: AppColors.ink,
                  ),
                ),
                Text(
                  label,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 12, color: AppColors.muted),
                ),
              ],
            ),
          ),
        ],
      ),
    ),
  );

  Widget _shortcut(BuildContext context, Shortcut s) {
    final key = _moduleKey(s.route);
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(22),
        onTap: () => Navigator.push(
          context,
          MaterialPageRoute(builder: (_) => ModuleScreen(module: key)),
        ),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Container(
                width: 50,
                height: 50,
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [
                      AppColors.blue.withValues(alpha: .14),
                      AppColors.violet.withValues(alpha: .10),
                    ],
                  ),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Icon(_icon(s.icon), color: AppColors.blue),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      s.title,
                      style: const TextStyle(fontWeight: FontWeight.w800),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      s.subtitle,
                      style: const TextStyle(
                        fontSize: 12.5,
                        color: AppColors.muted,
                      ),
                    ),
                  ],
                ),
              ),
              const Icon(
                Icons.arrow_forward_ios_rounded,
                size: 15,
                color: AppColors.muted,
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _moduleKey(String route) => switch (route) {
    'quiz.php' => 'quizzes',
    'groups.php' => 'groups',
    'results.php' => 'results',
    _ => route.replaceAll('.php', ''),
  };
  IconData _icon(String key) => switch (key) {
    'study' => Icons.school_rounded,
    'library' => Icons.local_library_rounded,
    'quiz' => Icons.quiz_rounded,
    'groups' => Icons.groups_rounded,
    'planner' => Icons.event_note_rounded,
    'results' => Icons.workspace_premium_rounded,
    _ => Icons.auto_stories_rounded,
  };
  String _compact(int n) => n >= 1000000
      ? '${(n / 1000000).toStringAsFixed(1)}M'
      : n >= 1000
      ? '${(n / 1000).toStringAsFixed(1)}K'
      : '$n';
  String _role(String role) =>
      role.isEmpty ? '' : '${role[0].toUpperCase()}${role.substring(1)}';
}
