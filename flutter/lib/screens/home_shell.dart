import 'dart:async';

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../core/app_state.dart';
import '../core/models.dart';
import '../core/native_bridge.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'call_screen.dart';
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
  Timer? callWatch, notificationWatch;
  int activeIncomingId = 0;
  int unreadChats = 0, unreadActivity = 0;
  int lastNotifiedMessage = 0, lastNotifiedActivity = 0;
  bool notificationBusy = false;

  @override
  void initState() {
    super.initState();
    callWatch = Timer.periodic(
      const Duration(seconds: 4),
      (_) => _watchIncomingCall(),
    );
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _watchIncomingCall();
      _setupNotificationWatch();
    });
  }

  @override
  void dispose() {
    callWatch?.cancel();
    notificationWatch?.cancel();
    super.dispose();
  }

  Future<void> _setupNotificationWatch() async {
    await NativeBridge.requestNotificationPermission();
    try {
      final prefs = await SharedPreferences.getInstance();
      lastNotifiedMessage = prefs.getInt('notification_last_message') ?? 0;
      lastNotifiedActivity = prefs.getInt('notification_last_activity') ?? 0;
    } catch (_) {}
    await _watchNotifications(seedOnly: true);
    notificationWatch?.cancel();
    notificationWatch = Timer.periodic(
      const Duration(seconds: 6),
      (_) => _watchNotifications(),
    );
  }

  Future<void> _watchNotifications({bool seedOnly = false}) async {
    if (!mounted || notificationBusy) return;
    notificationBusy = true;
    try {
      final data = await AppScope.of(context).api.notificationPeek();
      final chatUnread = _int(data['chat_unread']);
      final activityUnread = _int(data['notification_unread']);
      if (mounted && (chatUnread != unreadChats || activityUnread != unreadActivity)) {
        setState(() {
          unreadChats = chatUnread;
          unreadActivity = activityUnread;
        });
      }

      final rawChat = data['latest_chat'];
      if (rawChat is Map) {
        final chat = rawChat.cast<String, dynamic>();
        final id = _int(chat['id']);
        if (!seedOnly && id > lastNotifiedMessage && index != 2) {
          await NativeBridge.showNotification(
            id: 200000 + id,
            title: '${chat['from'] ?? 'New message'}',
            body: '${chat['text'] ?? 'Sent you a message'}',
            payload: 'chat:${chat['conversation'] ?? 0}',
          );
        }
        if (id > lastNotifiedMessage) {
          lastNotifiedMessage = id;
          try {
            final prefs = await SharedPreferences.getInstance();
            await prefs.setInt('notification_last_message', id);
          } catch (_) {}
        }
      }

      final rawActivity = data['latest_notification'];
      if (rawActivity is Map) {
        final activity = rawActivity.cast<String, dynamic>();
        final id = _int(activity['id']);
        if (!seedOnly && id > lastNotifiedActivity) {
          await NativeBridge.showNotification(
            id: 400000 + id,
            title: 'TaleemPK',
            body: '${activity['message'] ?? 'You have a new notification'}',
            payload: 'notification:$id',
          );
        }
        if (id > lastNotifiedActivity) {
          lastNotifiedActivity = id;
          try {
            final prefs = await SharedPreferences.getInstance();
            await prefs.setInt('notification_last_activity', id);
          } catch (_) {}
        }
      }
    } catch (_) {
      // A notification poll must never disturb the active app.
    } finally {
      notificationBusy = false;
    }
  }

  Future<void> _watchIncomingCall() async {
    if (!mounted || activeIncomingId != 0) return;
    try {
      final data = await AppScope.of(context).api.watchCalls();
      final raw = data['ringing'];
      if (raw is! Map || !mounted) return;
      final ring = raw.cast<String, dynamic>();
      final callId = _int(ring['call_id']);
      if (callId <= 0 || activeIncomingId == callId) return;
      activeIncomingId = callId;
      final video = '${ring['kind'] ?? 'audio'}' == 'video';
      final name = '${ring['from'] ?? 'TaleemPK member'}';
      final conversationId = _int(ring['conversation']);
      final username = '${ring['username'] ?? ''}';
      final avatar = ring['avatar']?.toString();

      final answer = await showDialog<bool>(
        context: context,
        barrierDismissible: false,
        builder: (d) => AlertDialog(
          icon: Icon(
            video ? Icons.videocam_rounded : Icons.call_rounded,
            size: 46,
            color: AppColors.success,
          ),
          title: Text(video ? 'Incoming video call' : 'Incoming voice call'),
          content: Text('$name is calling you.'),
          actions: [
            TextButton.icon(
              onPressed: () => Navigator.pop(d, false),
              icon: const Icon(Icons.call_end_rounded, color: AppColors.danger),
              label: const Text('Decline'),
            ),
            FilledButton.icon(
              onPressed: () => Navigator.pop(d, true),
              icon: const Icon(Icons.call_rounded),
              label: const Text('Accept'),
            ),
          ],
        ),
      );

      if (!mounted) return;
      if (answer == true) {
        final conversation = Conversation(
          id: conversationId,
          title: name,
          avatar: avatar,
          lastMessage: '',
          lastActivity: '',
          unread: 0,
          isGroup: false,
          online: true,
          statusText: 'Incoming call',
          muted: false,
          otherUsername: username,
          callsEnabled: true,
          videoCallsEnabled: video,
        );
        await Navigator.of(context).push(
          MaterialPageRoute<void>(
            builder: (_) => CallScreen(
              conversation: conversation,
              video: video,
              incomingCallId: callId,
            ),
          ),
        );
      } else {
        await AppScope.of(context).api.declineCall(callId);
      }
    } catch (_) {
      // Calling is optional; a failed watch must never disturb the app.
    } finally {
      activeIncomingId = 0;
    }
  }

  int _int(dynamic value) =>
      value is int ? value : int.tryParse('$value') ?? 0;

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
            NavigationDestination(
              icon: Badge(
                isLabelVisible: unreadActivity > 0,
                label: Text(unreadActivity > 99 ? '99+' : '$unreadActivity'),
                child: const Icon(Icons.home_outlined),
              ),
              selectedIcon: Badge(
                isLabelVisible: unreadActivity > 0,
                label: Text(unreadActivity > 99 ? '99+' : '$unreadActivity'),
                child: const Icon(Icons.home_rounded),
              ),
              label: 'Home',
            ),
            const NavigationDestination(
              icon: Icon(Icons.dynamic_feed_outlined),
              selectedIcon: Icon(Icons.dynamic_feed_rounded),
              label: 'Feed',
            ),
            NavigationDestination(
              icon: Badge(
                isLabelVisible: unreadChats > 0,
                label: Text(unreadChats > 99 ? '99+' : '$unreadChats'),
                child: const Icon(Icons.chat_bubble_outline_rounded),
              ),
              selectedIcon: Badge(
                isLabelVisible: unreadChats > 0,
                label: Text(unreadChats > 99 ? '99+' : '$unreadChats'),
                child: const Icon(Icons.chat_bubble_rounded),
              ),
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
