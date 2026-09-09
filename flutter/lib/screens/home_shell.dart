import 'package:flutter/material.dart';

import '../core/app_state.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'conversations_screen.dart';
import 'feed_screen.dart';
import 'home_screen.dart';
import 'profile_screen.dart';

class HomeShell extends StatefulWidget {
  const HomeShell({super.key});
  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int index = 0;
  final keys = List.generate(4, (_) => GlobalKey<NavigatorState>());

  @override
  Widget build(BuildContext context) {
    final user = AppScope.of(context).user!;
    return PopScope(
      canPop: !(keys[index].currentState?.canPop() ?? false),
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) keys[index].currentState?.maybePop();
      },
      child: Scaffold(
        body: IndexedStack(
          index: index,
          children: [
            _tab(0, const HomeScreen()),
            _tab(1, const FeedScreen()),
            _tab(2, const ConversationsScreen()),
            _tab(3, const ProfileScreen()),
          ],
        ),
        bottomNavigationBar: NavigationBar(
          selectedIndex: index,
          onDestinationSelected: (value) => setState(() => index = value),
          destinations: [
            const NavigationDestination(
              icon: Icon(Icons.home_outlined),
              selectedIcon: Icon(Icons.home_rounded),
              label: 'Home',
            ),
            const NavigationDestination(
              icon: Icon(Icons.dynamic_feed_outlined),
              selectedIcon: Icon(Icons.dynamic_feed_rounded),
              label: 'Feed',
            ),
            NavigationDestination(
              icon: const Icon(Icons.chat_bubble_outline_rounded),
              selectedIcon: const Icon(Icons.chat_bubble_rounded),
              label: 'Chat',
            ),
            NavigationDestination(
              icon: UserAvatar(url: user.avatar, name: user.name, radius: 13),
              selectedIcon: UserAvatar(
                url: user.avatar,
                name: user.name,
                radius: 14,
              ),
              label: 'Profile',
            ),
          ],
        ),
      ),
    );
  }

  Widget _tab(int tab, Widget child) => Navigator(
    key: keys[tab],
    onGenerateRoute: (_) => MaterialPageRoute(builder: (_) => child),
  );
}

class PremiumAppBar extends StatelessWidget implements PreferredSizeWidget {
  const PremiumAppBar({
    super.key,
    required this.title,
    this.subtitle,
    this.actions = const [],
    this.leading,
  });
  final String title;
  final String? subtitle;
  final List<Widget> actions;
  final Widget? leading;
  @override
  Size get preferredSize => const Size.fromHeight(72);
  @override
  Widget build(BuildContext context) => AppBar(
    toolbarHeight: 72,
    backgroundColor: Theme.of(context).scaffoldBackgroundColor,
    surfaceTintColor: Colors.transparent,
    leading: leading,
    actions: actions,
    title: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          title,
          style: TextStyle(
            fontSize: 22,
            fontWeight: FontWeight.w800,
            letterSpacing: -.5,
            color: Theme.of(context).colorScheme.onSurface,
          ),
        ),
        if (subtitle != null)
          Text(
            subtitle!,
            style: TextStyle(
              fontSize: 12.5,
              fontWeight: FontWeight.w500,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
      ],
    ),
  );
}
