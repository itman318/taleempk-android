from pathlib import Path


def patch(path, old, new):
    p=Path(path); s=p.read_text()
    if old not in s: raise SystemExit(f'marker missing: {path}: {old[:80]}')
    p.write_text(s.replace(old,new,1))

# API: mark-all-read support.
patch('flutter/lib/core/api_client.dart',
"  Future<Map<String, dynamic>> moduleAction(String action, {int id = 0}) =>\n      _request({'action': 'module_action', 'do': action, 'id': '$id'});",
"  Future<Map<String, dynamic>> moduleAction(String action, {int id = 0}) =>\n      _request({'action': 'module_action', 'do': action, 'id': '$id'});\n\n  Future<void> markAllNotificationsRead() async {\n    await moduleAction('read_all_notifications');\n  }")

# Backend: include a useful route for each notification and allow one-tap read all.
patch('backend/api/mobile.php',
"$rows = fetch_all(\"SELECT id,message,type,is_read,created_at FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 80\", [$uid]);\n        foreach ($rows as $r) $items[] = ['id'=>(int)$r['id'],'title'=>$r['message'],'subtitle'=>ucfirst($r['type']),\n            'meta'=>time_ago($r['created_at']),'kind'=>'notification','done'=>(int)$r['is_read']===1];",
"$rows = fetch_all(\"SELECT id,message,type,is_read,created_at,target_type,target_id FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 80\", [$uid]);\n        foreach ($rows as $r) {\n            $targetType = strtolower((string)($r['target_type'] ?? '')); $targetId = (int)($r['target_id'] ?? 0);\n            $route = '';\n            if ($targetId > 0) {\n                if (in_array($targetType, ['post','comment'], true)) $route = 'feed.php?post=' . $targetId;\n                elseif (in_array($targetType, ['user','profile','follow'], true)) $route = 'profile.php?id=' . $targetId;\n                elseif (in_array($targetType, ['group'], true)) $route = 'group.php?id=' . $targetId;\n                elseif (in_array($targetType, ['ticket','support'], true)) $route = 'support.php?id=' . $targetId;\n                elseif (in_array($targetType, ['quiz'], true)) $route = 'quiz.php?id=' . $targetId;\n            }\n            $items[] = ['id'=>(int)$r['id'],'title'=>$r['message'],'subtitle'=>ucfirst($r['type']),\n                'meta'=>time_ago($r['created_at']),'kind'=>'notification','done'=>(int)$r['is_read']===1,'route'=>$route];\n        }")
patch('backend/api/mobile.php',
"    if ($do === 'read_notification') {\n        q('UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?', [$id,$uid]);\n        mobile_out(['read'=>true]);\n    }",
"    if ($do === 'read_notification') {\n        q('UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?', [$id,$uid]);\n        mobile_out(['read'=>true]);\n    }\n    if ($do === 'read_all_notifications') {\n        q('UPDATE notifications SET is_read=1 WHERE user_id=? AND is_read=0', [$uid]);\n        mobile_out(['read_all'=>true]);\n    }")

# Notification center: mark-all action and open the target after marking read.
patch('flutter/lib/screens/module_screen.dart',
"      actions: [\n        IconButton(onPressed: _load, icon: const Icon(Icons.refresh_rounded)),",
"      actions: [\n        if (widget.module == 'notifications')\n          TextButton.icon(\n            onPressed: _markAllRead,\n            icon: const Icon(Icons.done_all_rounded),\n            label: const Text('Read all'),\n          ),\n        IconButton(onPressed: _load, icon: const Icon(Icons.refresh_rounded)),")
patch('flutter/lib/screens/module_screen.dart',
"  Future<void> _newTicket() async {",
"  Future<void> _markAllRead() async {\n    try {\n      await AppScope.of(context).api.markAllNotificationsRead();\n      if (!mounted) return;\n      showMessage(context, 'All notifications marked as read.');\n      await _load();\n    } catch (e) {\n      if (mounted) showMessage(context, apiMessage(e));\n    }\n  }\n\n  Future<void> _newTicket() async {")
patch('flutter/lib/screens/module_screen.dart',
"    if (item.kind == 'notification') {\n      try {\n        await AppScope.of(context).api.moduleAction('read_notification', id: item.id);\n        _load();\n      } catch (e) {\n        showMessage(context, apiMessage(e));\n      }\n      return;\n    }",
"    if (item.kind == 'notification') {\n      try {\n        await AppScope.of(context).api.moduleAction('read_notification', id: item.id);\n        if (!mounted) return;\n        if (item.route.isNotEmpty) {\n          final uri = Uri.parse('https://taleempk.online/${item.route}');\n          final opened = await launchUrl(uri, mode: LaunchMode.externalApplication);\n          if (!opened && mounted) showMessage(context, 'Could not open this notification.');\n        }\n        if (mounted) _load();\n      } catch (e) {\n        if (mounted) showMessage(context, apiMessage(e));\n      }\n      return;\n    }")

# Android notification tap bridge: retain cold/warm-start payload for Flutter.
patch('flutter/android/app/src/main/kotlin/online/taleempk/studyhub/MainActivity.kt',
"class MainActivity : FlutterActivity() {\n    private val notificationBridge",
"class MainActivity : FlutterActivity() {\n    private var pendingNotificationPayload: String? = null\n    private val notificationBridge")
patch('flutter/android/app/src/main/kotlin/online/taleempk/studyhub/MainActivity.kt',
"        super.configureFlutterEngine(flutterEngine)\n        createMessageChannel()",
"        super.configureFlutterEngine(flutterEngine)\n        pendingNotificationPayload = intent?.getStringExtra(\"taleempk_payload\")\n        createMessageChannel()")
patch('flutter/android/app/src/main/kotlin/online/taleempk/studyhub/MainActivity.kt',
"                    \"showNotification\" -> {",
"                    \"consumePayload\" -> {\n                        val payload = pendingNotificationPayload\n                        pendingNotificationPayload = null\n                        result.success(payload)\n                    }\n                    \"showNotification\" -> {")
patch('flutter/android/app/src/main/kotlin/online/taleempk/studyhub/MainActivity.kt',
"    private fun requireArg(value: String?, name: String): String =",
"    override fun onNewIntent(intent: Intent) {\n        super.onNewIntent(intent)\n        setIntent(intent)\n        pendingNotificationPayload = intent.getStringExtra(\"taleempk_payload\")\n    }\n\n    private fun requireArg(value: String?, name: String): String =")

# Flutter bridge consumer.
patch('flutter/lib/core/native_bridge.dart',
"  static Future<void> showNotification({",
"  static Future<String?> consumeNotificationPayload() async {\n    try {\n      return await _notifications.invokeMethod<String>('consumePayload');\n    } catch (_) {\n      return null;\n    }\n  }\n\n  static Future<void> showNotification({")

# Home notification UX: consume notification taps, make activity notification payload route-aware,
# don't suppress message alerts merely because Chat tab is selected, and add a professional center shortcut.
patch('flutter/lib/screens/home_shell.dart',
"import 'profile_screen.dart';",
"import 'profile_screen.dart';\nimport 'module_screen.dart';")
patch('flutter/lib/screens/home_shell.dart',
"    await _watchNotifications(seedOnly: true);",
"    await _watchNotifications(seedOnly: true);\n    await _consumeNotificationTap();")
patch('flutter/lib/screens/home_shell.dart',
"        if (!seedOnly && id > lastNotifiedMessage && index != 2) {",
"        if (!seedOnly && id > lastNotifiedMessage) {")
patch('flutter/lib/screens/home_shell.dart',
"            payload: 'notification:$id',",
"            payload: 'notification:$id:${activity['route'] ?? ''}',")
patch('flutter/lib/screens/home_shell.dart',
"    } catch (_) {\n      // A notification poll must never disturb the active app.\n    } finally {",
"      await _consumeNotificationTap();\n    } catch (_) {\n      // A notification poll must never disturb the active app.\n    } finally {")
patch('flutter/lib/screens/home_shell.dart',
"  Future<void> _watchIncomingCall() async {",
"  Future<void> _consumeNotificationTap() async {\n    if (!mounted) return;\n    final payload = await NativeBridge.consumeNotificationPayload();\n    if (!mounted || payload == null || payload.isEmpty) return;\n    if (payload.startsWith('chat:')) {\n      setState(() => index = 2);\n      return;\n    }\n    if (payload.startsWith('notification:')) {\n      setState(() => index = 0);\n      keys[0].currentState?.push(MaterialPageRoute<void>(builder: (_) => const ModuleScreen(module: 'notifications')));\n    }\n  }\n\n  Future<void> _watchIncomingCall() async {")

print('TaleemPK v5.2 notification upgrade applied')
