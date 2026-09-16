import 'package:flutter/material.dart';
import '../core/app_state.dart';
import '../core/models.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'home_shell.dart';
import 'module_screen.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});
  void _open(BuildContext context, String module) => Navigator.push(context,
    premiumRoute(builder: (_) => ModuleScreen(module: module)));
  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context), user = state.bootstrap!.user;
    final shortcuts = state.bootstrap!.shortcuts.where((s) => !['feed.php', 'chat.php'].contains(s.route)).toList();
    final colors = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: PremiumAppBar(title: 'Your learning space', subtitle: 'TALEEMPK', actions: [
        IconButton.filledTonal(tooltip: 'Notifications', onPressed: () => _open(context, 'notifications'),
          icon: const Icon(Icons.notifications_none_rounded)), const SizedBox(width: 12)]),
      body: RefreshIndicator(onRefresh: state.refreshSession,
        child: ListView(physics: const AlwaysScrollableScrollPhysics(), padding: const EdgeInsets.fromLTRB(18, 12, 18, 36),
          children: [Center(child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 880),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              Container(padding: const EdgeInsets.all(22), decoration: BoxDecoration(
                gradient: const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight,
                  colors: [Color(0xFF101E43), Color(0xFF2846A9), Color(0xFF6551C8)]),
                borderRadius: BorderRadius.circular(28),
                boxShadow: [BoxShadow(color: colors.primary.withValues(alpha: .16), blurRadius: 24, offset: const Offset(0, 10))]),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Row(children: [UserAvatar(url: user.avatar, name: user.name, radius: 23),
                    const SizedBox(width: 12), Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Row(children: [Flexible(child: Text(user.name, maxLines: 2, overflow: TextOverflow.ellipsis,
                        style: const TextStyle(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w800))),
                        if (user.verified) const Padding(padding: EdgeInsets.only(left: 5), child:
                          Icon(Icons.verified_rounded, size: 18, color: Color(0xFF80E5EC)))]),
                      Text('@${user.username}', maxLines: 1, overflow: TextOverflow.ellipsis,
                        style: const TextStyle(color: Color(0xFFD7E2FF), fontSize: 12))]))]),
                  const SizedBox(height: 25),
                  const Text('Make room for\nyour next big idea.', style: TextStyle(color: Colors.white,
                    fontSize: 27, height: 1.18, fontWeight: FontWeight.w800, letterSpacing: -.6)),
                  const SizedBox(height: 10),
                  const Text('A little practice. A clear plan. A step forward.',
                    style: TextStyle(color: Color(0xFFE0E7FF), fontSize: 13, height: 1.5)),
                  const SizedBox(height: 18),
                  FilledButton.icon(style: FilledButton.styleFrom(backgroundColor: const Color(0xFFC8F4DD),
                    foregroundColor: const Color(0xFF123A32)), onPressed: () => _open(context, 'study'),
                    icon: const Icon(Icons.arrow_forward_rounded, size: 19), label: const Text('Open study dashboard')),
                ])),
              const SizedBox(height: 24),
              Text('Start something good', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 12),
              LayoutBuilder(builder: (context, box) {
                final narrow = box.maxWidth < 340 || MediaQuery.textScalerOf(context).scale(1) > 1.3;
                final items = [
                  _quick(context, 'Practice a quiz', 'Build your confidence', Icons.quiz_outlined, 'quizzes', const Color(0xFF4664D9)),
                  _quick(context, 'Plan your study', 'Give your goals a place', Icons.event_note_outlined, 'planner', const Color(0xFF278273))];
                return narrow ? Column(children: [items[0], const SizedBox(height: 10), items[1]])
                  : Row(crossAxisAlignment: CrossAxisAlignment.start, children: [Expanded(child: items[0]),
                    const SizedBox(width: 12), Expanded(child: items[1])]);
              }),
              const SizedBox(height: 26),
              Text('Explore TaleemPK', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 4),
              Text('Everything you need to learn and connect.', style: TextStyle(color: colors.onSurfaceVariant, fontSize: 13)),
              const SizedBox(height: 14),
              for (final s in shortcuts) Padding(padding: const EdgeInsets.only(bottom: 10), child: _shortcut(context, s)),
              const SizedBox(height: 12),
              Row(mainAxisAlignment: MainAxisAlignment.center, children: [Icon(Icons.auto_awesome_outlined,
                size: 16, color: colors.primary), const SizedBox(width: 8), Flexible(child: Text('Learn at your pace. Grow together.',
                  style: TextStyle(fontSize: 12, color: colors.onSurfaceVariant), textAlign: TextAlign.center))]),
            ])))])));
  }
  Widget _quick(BuildContext context, String title, String subtitle, IconData icon, String module, Color accent) {
    final c = Theme.of(context).colorScheme;
    return Material(color: c.surface, borderRadius: BorderRadius.circular(22), child: InkWell(
      borderRadius: BorderRadius.circular(22), onTap: () => _open(context, module), child: Container(
        width: double.infinity, padding: const EdgeInsets.all(18), decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(22), border: Border.all(color: c.outlineVariant.withValues(alpha: .5))),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          CircleAvatar(backgroundColor: accent.withValues(alpha: .12), child: Icon(icon, color: accent)),
          const SizedBox(height: 14), Text(title, style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 15)),
          const SizedBox(height: 5), Text(subtitle, style: TextStyle(color: c.onSurfaceVariant, fontSize: 12, height: 1.4))]))));
  }
  Widget _shortcut(BuildContext context, Shortcut s) {
    final c = Theme.of(context).colorScheme;
    final key = switch(s.route) {'quiz.php' => 'quizzes', 'groups.php' => 'groups', 'results.php' => 'results',
      _ => s.route.replaceAll('.php', '')};
    final icon = switch(s.icon) {'study' => Icons.school_outlined, 'library' => Icons.local_library_outlined,
      'quiz' => Icons.quiz_outlined, 'groups' => Icons.groups_outlined, 'planner' => Icons.event_note_outlined,
      'results' => Icons.workspace_premium_outlined, _ => Icons.auto_stories_outlined};
    return Material(color: c.surface, borderRadius: BorderRadius.circular(20), child: InkWell(
      borderRadius: BorderRadius.circular(20), onTap: () => _open(context, key), child: Padding(
        padding: const EdgeInsets.all(16), child: Row(children: [Container(width: 44, height: 44,
          decoration: BoxDecoration(color: c.primary.withValues(alpha: .08), borderRadius: BorderRadius.circular(14)),
          child: Icon(icon, color: c.primary, size: 23)), const SizedBox(width: 14),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(s.title, style: const TextStyle(fontWeight: FontWeight.w700)), const SizedBox(height: 4),
            Text(s.subtitle, style: TextStyle(color: c.onSurfaceVariant, fontSize: 12, height: 1.4))])),
          const SizedBox(width: 8), Icon(Icons.chevron_right_rounded, size: 20, color: c.onSurfaceVariant)]))));
  }
}
