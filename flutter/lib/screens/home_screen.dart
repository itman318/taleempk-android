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
            const SizedBox(height: 16),
            _learningPromise(),
            const SizedBox(height: 24),
            const Text(
              'Explore TaleemPK',
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

  Widget _learningPromise() => Container(
    padding: const EdgeInsets.all(18),
    decoration: BoxDecoration(
      color: Colors.white,
      borderRadius: BorderRadius.circular(22),
      border: Border.all(color: const Color(0x143157E8)),
    ),
    child: const Row(
      children: [
        CircleAvatar(
          radius: 23,
          backgroundColor: Color(0x123157E8),
          child: Icon(Icons.psychology_alt_rounded, color: AppColors.blue),
        ),
        SizedBox(width: 14),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Learn with purpose',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900),
              ),
              SizedBox(height: 4),
              Text(
                'Plan your studies, practise smarter and grow with trusted learning resources.',
                style: TextStyle(
                  fontSize: 12.5,
                  height: 1.4,
                  color: AppColors.muted,
                ),
              ),
            ],
          ),
        ),
      ],
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
  String _role(String role) =>
      role.isEmpty ? '' : '${role[0].toUpperCase()}${role.substring(1)}';
}
