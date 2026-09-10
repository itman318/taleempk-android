from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
FLUTTER = ROOT / 'flutter'


def read(path):
    return (ROOT / path).read_text()


def write(path, text):
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def replace_once(text, old, new, label):
    if old not in text:
        raise RuntimeError(f'{label}: anchor missing')
    return text.replace(old, new, 1)


def sub_once(text, pattern, replacement, label):
    updated, count = re.subn(pattern, lambda _: replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f'{label}: expected one match, got {count}')
    return updated


# ---------------------------------------------------------------------------
# Module routes: quizzes must use the website slug, never an integer id.
# ---------------------------------------------------------------------------
models_path = 'flutter/lib/core/models.dart'
models = read(models_path)
models = replace_once(
    models,
    "    required this.done,\n  });\n  final int id;\n  final String title, subtitle, meta, kind;\n  final bool done;",
    "    required this.done,\n    this.route = '',\n  });\n  final int id;\n  final String title, subtitle, meta, kind, route;\n  final bool done;",
    'ModuleItem route field',
)
models = replace_once(
    models,
    "    kind: '${j['kind'] ?? ''}',\n    done: _bool(j['done']),\n  );\n}\n\nclass ModuleData",
    "    kind: '${j['kind'] ?? ''}',\n    done: _bool(j['done']),\n    route: '${j['route'] ?? ''}',\n  );\n}\n\nclass ModuleData",
    'ModuleItem route json',
)
write(models_path, models)

module_path = 'flutter/lib/screens/module_screen.dart'
module = read(module_path)
old_open = """  Future<void> _open(ModuleItem item) async {
    if (item.kind == 'task') {
      try {
        await AppScope.of(context).api.moduleAction('toggle_task', id: item.id);
        _load();
      } catch (e) {
        showMessage(context, apiMessage(e));
      }
      return;
    }
    if (item.kind == 'setting') {
      try {
        if (item.id == 2) {
          await AppScope.of(context).api.moduleAction('cycle_privacy');
        } else if (item.id == 3) {
          await AppScope.of(context).api.moduleAction('toggle_online');
        } else {
          showMessage(context, 'Two-step verification is managed from the TaleemPK website.');
          return;
        }
        _load();
      } catch (e) {
        showMessage(context, apiMessage(e));
      }
      return;
    }
    if (item.kind == 'notification') {
      try {
        await AppScope.of(context).api.moduleAction('read_notification', id: item.id);
        _load();
      } catch (e) {
        showMessage(context, apiMessage(e));
      }
      return;
    }
    final route = switch (item.kind) {
      'resource' => 'resource.php?id=${item.id}',
      'quiz' => 'quiz-take.php?id=${item.id}',
      'group' => 'group.php?id=${item.id}',
      'board' => 'results.php?board=${item.id}',
      'ticket' => 'support.php?id=${item.id}',
      _ => '',
    };
    if (route.isNotEmpty) {
      final uri = Uri.parse('https://taleempk.online/$route');
      final opened = await launchUrl(uri, mode: LaunchMode.externalApplication);
      if (!opened && mounted) showMessage(context, 'Could not open this item.');
    }
  }
"""
new_open = """  Future<void> _open(ModuleItem item) async {
    if (item.kind == 'task') {
      try {
        await AppScope.of(context).api.moduleAction('toggle_task', id: item.id);
        _load();
      } catch (e) {
        showMessage(context, apiMessage(e));
      }
      return;
    }
    if (item.kind == 'setting') {
      try {
        if (item.id == 2) {
          await AppScope.of(context).api.moduleAction('cycle_privacy');
        } else if (item.id == 3) {
          await AppScope.of(context).api.moduleAction('toggle_online');
        } else {
          showMessage(context, 'Two-step verification is managed from the TaleemPK website.');
          return;
        }
        _load();
      } catch (e) {
        showMessage(context, apiMessage(e));
      }
      return;
    }
    if (item.kind == 'notification') {
      try {
        await AppScope.of(context).api.moduleAction('read_notification', id: item.id);
        _load();
      } catch (e) {
        showMessage(context, apiMessage(e));
      }
      return;
    }

    if (item.kind == 'quiz' && item.route.isEmpty) {
      showMessage(
        context,
        'This quiz needs the latest TaleemPK mobile API. Update api/mobile.php, then refresh.',
      );
      return;
    }

    final route = item.route.isNotEmpty
        ? item.route
        : switch (item.kind) {
            'resource' => 'resource.php?id=${item.id}',
            'group' => 'group.php?id=${item.id}',
            'board' => 'results.php?board=${item.id}',
            'ticket' => 'support.php?id=${item.id}',
            _ => '',
          };
    if (route.isNotEmpty) {
      final uri = Uri.parse('https://taleempk.online/$route');
      final opened = await launchUrl(uri, mode: LaunchMode.externalApplication);
      if (!opened && mounted) {
        showMessage(context, 'Could not open this item.');
      }
    }
  }
"""
module = replace_once(module, old_open, new_open, 'Module open route')
write(module_path, module)

# ---------------------------------------------------------------------------
# API client: comment management + lightweight notification peek.
# ---------------------------------------------------------------------------
api_path = 'flutter/lib/core/api_client.dart'
api = read(api_path)
api = replace_once(
    api,
    """  Future<void> addComment(int postId, String content) => _request({
    'action': 'create_comment',
    'post_id': '$postId',
    'content': content,
  });

  Future<ModuleData> module(String key) async =>
""",
    """  Future<void> addComment(int postId, String content) => _request({
    'action': 'create_comment',
    'post_id': '$postId',
    'content': content,
  });

  Future<void> editComment(int commentId, String content) => _request({
    'action': 'edit_comment',
    'kind': 'comment',
    'id': '$commentId',
    'content': content,
  });

  Future<void> deleteComment(int commentId) => _request({
    'action': 'delete_comment',
    'id': '$commentId',
  });

  Future<Map<String, dynamic>> notificationPeek() =>
      _request({'action': 'notification_peek'});

  Future<ModuleData> module(String key) async =>
""",
    'API comment and notification methods',
)
write(api_path, api)

# ---------------------------------------------------------------------------
# Feed comments: own comments get professional Edit/Delete controls.
# ---------------------------------------------------------------------------
feed_path = 'flutter/lib/screens/feed_screen.dart'
feed = read(feed_path)
new_comments = r'''  Future<void> _comments(FeedPost post) async {
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
'''
feed = sub_once(
    feed,
    r"  Future<void> _comments\(FeedPost post\) async \{.*?\n  \}\n\}\s*$",
    new_comments + "}\n",
    'Feed comment manager',
)
write(feed_path, feed)

# ---------------------------------------------------------------------------
# Native Android bridge: system notifications + reliable device photo editing.
# ---------------------------------------------------------------------------
bridge_path = 'flutter/lib/core/native_bridge.dart'
bridge = r'''import 'package:flutter/services.dart';

class NativeBridge {
  static const _notifications = MethodChannel('taleempk/native_notifications');
  static const _media = MethodChannel('taleempk/media_tools');

  static Future<void> requestNotificationPermission() async {
    try {
      await _notifications.invokeMethod<void>('requestPermission');
    } catch (_) {
      // Notifications are an enhancement; the app remains usable without them.
    }
  }

  static Future<void> showNotification({
    required int id,
    required String title,
    required String body,
    String payload = '',
  }) async {
    if (title.trim().isEmpty || body.trim().isEmpty) return;
    try {
      await _notifications.invokeMethod<void>('showNotification', {
        'id': id,
        'title': title.trim(),
        'body': body.trim(),
        'payload': payload,
      });
    } catch (_) {
      // Do not interrupt chat if Android notifications are unavailable.
    }
  }

  static Future<String?> editPhoto({
    required String path,
    required int turns,
    required bool flip,
    required String crop,
  }) async {
    return _media.invokeMethod<String>('editPhoto', {
      'path': path,
      'turns': turns,
      'flip': flip,
      'crop': crop,
    });
  }
}
'''
write(bridge_path, bridge)

manifest_path = 'flutter/android/app/src/main/AndroidManifest.xml'
manifest = read(manifest_path)
manifest = replace_once(
    manifest,
    '    <uses-permission android:name="android.permission.VIBRATE" />\n',
    '    <uses-permission android:name="android.permission.VIBRATE" />\n    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />\n',
    'Android notification permission',
)
write(manifest_path, manifest)

main_activity_path = 'flutter/android/app/src/main/kotlin/online/taleempk/studyhub/MainActivity.kt'
main_activity = r'''package online.taleempk.studyhub

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.os.Build
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.io.File
import java.io.FileOutputStream
import kotlin.math.roundToInt

class MainActivity : FlutterActivity() {
    private val notificationBridge = "taleempk/native_notifications"
    private val mediaBridge = "taleempk/media_tools"
    private val notificationChannelId = "taleempk_messages"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        createMessageChannel()

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, notificationBridge)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "requestPermission" -> {
                        requestNotificationPermissionIfNeeded()
                        result.success(null)
                    }
                    "showNotification" -> {
                        val id = call.argument<Int>("id") ?: 1
                        val title = call.argument<String>("title") ?: "TaleemPK"
                        val body = call.argument<String>("body") ?: "You have a new update."
                        val payload = call.argument<String>("payload") ?: ""
                        showSystemNotification(id, title, body, payload)
                        result.success(null)
                    }
                    else -> result.notImplemented()
                }
            }

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, mediaBridge)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "editPhoto" -> {
                        try {
                            val path = call.argument<String>("path")
                                ?: throw IllegalArgumentException("Missing photo path")
                            val turns = call.argument<Int>("turns") ?: 0
                            val flip = call.argument<Boolean>("flip") ?: false
                            val crop = call.argument<String>("crop") ?: "original"
                            result.success(editPhoto(path, turns, flip, crop))
                        } catch (error: Throwable) {
                            result.error("PHOTO_EDIT", error.message ?: "Photo edit failed", null)
                        }
                    }
                    else -> result.notImplemented()
                }
            }
    }

    private fun createMessageChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val channel = NotificationChannel(
            notificationChannelId,
            "Messages and activity",
            NotificationManager.IMPORTANCE_HIGH,
        ).apply {
            description = "TaleemPK messages, replies and account activity"
            enableVibration(true)
            lockscreenVisibility = Notification.VISIBILITY_PRIVATE
        }
        getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
    }

    private fun requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 2901)
        }
    }

    private fun showSystemNotification(id: Int, title: String, body: String, payload: String) {
        if (Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) return

        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
            putExtra("taleempk_payload", payload)
        }
        val pendingIntent = PendingIntent.getActivity(
            this,
            id,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val builder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Notification.Builder(this, notificationChannelId)
        } else {
            @Suppress("DEPRECATION")
            Notification.Builder(this)
        }
        builder
            .setSmallIcon(applicationInfo.icon)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(Notification.BigTextStyle().bigText(body))
            .setContentIntent(pendingIntent)
            .setAutoCancel(true)
            .setCategory(Notification.CATEGORY_MESSAGE)
            .setVisibility(Notification.VISIBILITY_PRIVATE)
            .setOnlyAlertOnce(true)

        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            @Suppress("DEPRECATION")
            builder.setPriority(Notification.PRIORITY_HIGH)
        }
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.notify(id.coerceAtLeast(1), builder.build())
    }

    private fun editPhoto(path: String, turns: Int, flip: Boolean, crop: String): String {
        var bitmap = BitmapFactory.decodeFile(path)
            ?: throw IllegalArgumentException("Android could not decode this image")

        val normalizedTurns = ((turns % 4) + 4) % 4
        if (normalizedTurns != 0 || flip) {
            val matrix = Matrix().apply {
                if (normalizedTurns != 0) postRotate(90f * normalizedTurns)
                if (flip) postScale(-1f, 1f)
            }
            val transformed = Bitmap.createBitmap(
                bitmap,
                0,
                0,
                bitmap.width,
                bitmap.height,
                matrix,
                true,
            )
            if (transformed !== bitmap) bitmap.recycle()
            bitmap = transformed
        }

        val targetRatio = when (crop) {
            "square" -> 1.0
            "portrait" -> 4.0 / 5.0
            "landscape" -> 16.0 / 9.0
            else -> null
        }
        if (targetRatio != null) {
            val currentRatio = bitmap.width.toDouble() / bitmap.height.toDouble()
            val cropped = if (currentRatio > targetRatio) {
                val width = (bitmap.height * targetRatio).roundToInt().coerceIn(1, bitmap.width)
                Bitmap.createBitmap(bitmap, (bitmap.width - width) / 2, 0, width, bitmap.height)
            } else if (currentRatio < targetRatio) {
                val height = (bitmap.width / targetRatio).roundToInt().coerceIn(1, bitmap.height)
                Bitmap.createBitmap(bitmap, 0, (bitmap.height - height) / 2, bitmap.width, height)
            } else {
                bitmap
            }
            if (cropped !== bitmap) bitmap.recycle()
            bitmap = cropped
        }

        val output = File(cacheDir, "taleempk_photo_${System.nanoTime()}.jpg")
        FileOutputStream(output).use { stream ->
            if (!bitmap.compress(Bitmap.CompressFormat.JPEG, 93, stream)) {
                throw IllegalStateException("Android could not save the edited image")
            }
            stream.flush()
        }
        bitmap.recycle()
        if (!output.exists() || output.length() < 256L) {
            throw IllegalStateException("Edited photo output is empty")
        }
        return output.absolutePath
    }
}
'''
write(main_activity_path, main_activity)

# ---------------------------------------------------------------------------
# Notification watcher and badges in the shell.
# ---------------------------------------------------------------------------
home_path = 'flutter/lib/screens/home_shell.dart'
home = read(home_path)
home = replace_once(
    home,
    "import 'package:flutter/material.dart';\n",
    "import 'package:flutter/material.dart';\nimport 'package:shared_preferences/shared_preferences.dart';\n",
    'Home shared prefs import',
)
home = replace_once(
    home,
    "import '../core/models.dart';\n",
    "import '../core/models.dart';\nimport '../core/native_bridge.dart';\n",
    'Home native bridge import',
)
home = replace_once(
    home,
    """  Timer? callWatch;
  int activeIncomingId = 0;
""",
    """  Timer? callWatch, notificationWatch;
  int activeIncomingId = 0;
  int unreadChats = 0, unreadActivity = 0;
  int lastNotifiedMessage = 0, lastNotifiedActivity = 0;
  bool notificationBusy = false;
""",
    'Home notification state',
)
home = replace_once(
    home,
    """    WidgetsBinding.instance.addPostFrameCallback((_) => _watchIncomingCall());
  }

  @override
  void dispose() {
    callWatch?.cancel();
    super.dispose();
  }

  Future<void> _watchIncomingCall() async {
""",
    """    WidgetsBinding.instance.addPostFrameCallback((_) {
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
""",
    'Home notification watcher',
)
home = replace_once(
    home,
    """            const NavigationDestination(
              icon: Icon(Icons.home_outlined),
              selectedIcon: Icon(Icons.home_rounded),
              label: 'Home',
            ),
""",
    """            NavigationDestination(
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
""",
    'Home activity badge',
)
home = replace_once(
    home,
    """            NavigationDestination(
              icon: const Icon(Icons.chat_bubble_outline_rounded),
              selectedIcon: const Icon(Icons.chat_bubble_rounded),
              label: 'Chat',
            ),
""",
    """            NavigationDestination(
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
""",
    'Home chat badge',
)
write(home_path, home)

# ---------------------------------------------------------------------------
# Chat polish, visible encryption entry, richer emoji picker, native photo edit.
# ---------------------------------------------------------------------------
chat_path = 'flutter/lib/screens/chat_screen.dart'
chat = read(chat_path)
chat = replace_once(
    chat,
    "import '../core/models.dart';\n",
    "import '../core/models.dart';\nimport '../core/native_bridge.dart';\n",
    'Chat native bridge import',
)
chat = replace_once(
    chat,
    """  if (image == null) {
    throw StateError('This image format cannot be edited on this device.');
  }

  final normalizedTurns""",
    """  if (image == null) {
    throw StateError('This image format cannot be edited on this device.');
  }
  image = img.bakeOrientation(image);

  final normalizedTurns""",
    'Photo EXIF orientation',
)
chat = chat.replace("? const Color(0xFF07101B)\n        : const Color(0xFFF3F6FA)", "? const Color(0xFF06101A)\n        : const Color(0xFFF1F5F9)", 1)
chat = chat.replace("colors: [Color(0xFF245FD3), Color(0xFF5146D8)]", "colors: [Color(0xFF123B64), Color(0xFF285C8D)]", 1)
chat = chat.replace("const Color(0xFF0C5D58)", "const Color(0xFF0B665E)")
chat = chat.replace("const Color(0xFF183B63)", "const Color(0xFF173B63)")
chat = chat.replace("const Color(0xFFDCF6EF)", "const Color(0xFFE6F7F2)")
chat = chat.replace("const Color(0xFF132033)", "const Color(0xFF111E2E)")
chat = chat.replace("const Color(0xFFFFFFFF)", "const Color(0xFFFBFDFF)", 2)
chat = chat.replace("toolbarHeight: 68,", "toolbarHeight: 82,", 1)

presence_block = r'''                      Text(
                        presence?.active == true
                            ? (presence!.kind == 'voice'
                                  ? '${presence!.name} is recording voice…'
                                  : '${presence!.name} is typing…')
                            : widget.conversation.statusText,
                        style: TextStyle(
                          fontSize: 11.5,
                          color: presence?.active == true
                              ? AppColors.success
                              : AppColors.muted,
                        ),
                      ),'''
security_presence = presence_block + r'''
                      const SizedBox(height: 2),
                      InkWell(
                        borderRadius: BorderRadius.circular(10),
                        onTap: _encryptionInfo,
                        child: Padding(
                          padding: const EdgeInsets.only(right: 5, top: 1, bottom: 1),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(
                                Icons.lock_rounded,
                                size: 11.5,
                                color: _threadHasEncryptedMessages
                                    ? AppColors.success
                                    : AppColors.blue,
                              ),
                              const SizedBox(width: 4),
                              Flexible(
                                child: Text(
                                  _threadHasEncryptedMessages
                                      ? 'End-to-end encrypted on web'
                                      : 'End-to-end encryption',
                                  overflow: TextOverflow.ellipsis,
                                  style: TextStyle(
                                    fontSize: 9.8,
                                    fontWeight: FontWeight.w700,
                                    color: _threadHasEncryptedMessages
                                        ? AppColors.success
                                        : AppColors.blue,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),'''
chat = replace_once(chat, presence_block, security_presence, 'Chat encryption header')
chat = replace_once(
    chat,
    "  bool get _chatBlocked => selfBlocked || widget.conversation.blockedByOther;\n",
    "  bool get _chatBlocked => selfBlocked || widget.conversation.blockedByOther;\n  bool get _threadHasEncryptedMessages => messages.any((m) => m.encrypted);\n",
    'Encrypted thread getter',
)

# Add haptic feedback on emoji selection.
chat = replace_once(
    chat,
    """  Future<void> _insertEmoji(String emoji) async {
    final value = textController.value;
""",
    """  Future<void> _insertEmoji(String emoji) async {
    HapticFeedback.selectionClick();
    final value = textController.value;
""",
    'Emoji haptic feedback',
)
# Add a Symbols category after Study.
chat = replace_once(
    chat,
    """      'Nature': const [
""",
    """      'Symbols': const [
        '✅','☑️','✔️','❌','✖️','➕','➖','➗','✏️','✒️','🔒','🔓','🔐','🔑','🛡️','⚠️','🚫','⛔',
        '❓','❔','❗','❕','‼️','⁉️','💯','🔔','🔕','📣','📢','💬','💭','♻️','🔄','🔁','▶️','⏸️','⏹️','⏺️',
        '⬆️','⬇️','⬅️','➡️','↗️','↘️','↙️','↖️','↩️','↪️','🔵','🟢','🟡','🟠','🔴','🟣','⚫','⚪','🟤'
      ],
      'Nature': const [
""",
    'Emoji symbols category',
)
# Make chips look more like a compact professional picker.
chat = chat.replace("label: Text(name),\n                  onSelected", "avatar: Icon(\n                    switch (name) {\n                      'Recent' => Icons.history_rounded,\n                      'Smileys' => Icons.emoji_emotions_outlined,\n                      'People' => Icons.front_hand_outlined,\n                      'Hearts' => Icons.favorite_border_rounded,\n                      'Activities' => Icons.celebration_outlined,\n                      'Study' => Icons.school_outlined,\n                      'Symbols' => Icons.category_outlined,\n                      'Nature' => Icons.park_outlined,\n                      'Food' => Icons.restaurant_outlined,\n                      'Flags' => Icons.flag_outlined,\n                      _ => Icons.emoji_emotions_outlined,\n                    },\n                    size: 15,\n                  ),\n                  label: Text(name),\n                  onSelected", 1)

# Picker quality: reduce giant image memory while retaining excellent quality.
chat = chat.replace("imageQuality: 88,\n                  maxWidth: 2200,", "imageQuality: 92,\n                  maxWidth: 2600,\n                  maxHeight: 2600,", 2)
chat = chat.replace("imageQuality: 88,\n                            maxWidth: 2200,", "imageQuality: 92,\n                            maxWidth: 2600,\n                            maxHeight: 2600,", 1)

# Native Android editor first, Dart image package as a safe fallback.
old_apply = r'''    if (apply != true) return null;
    if (turns == 0 && !flip && crop == 'original') return sourcePath;
    try {
      final bytes = await File(sourcePath).readAsBytes();
      final edited = await compute(_processOutgoingPhoto, <String, dynamic>{
        'bytes': bytes,
        'turns': turns,
        'flip': flip,
        'crop': crop,
      });
      final dir = await getTemporaryDirectory();
      final output = '${dir.path}/taleempk_photo_${DateTime.now().microsecondsSinceEpoch}.jpg';
      final file = File(output);
      await file.writeAsBytes(edited, flush: true);
      if (!await file.exists() || await file.length() < 256) {
        throw StateError('Edited photo output is empty.');
      }
      return output;
    } catch (e) {
      if (mounted) {
        showMessage(context, 'Photo edit failed. The original photo is still selected.');
      }
      return null;
    }
'''
new_apply = r'''    if (apply != true) return null;
    if (turns == 0 && !flip && crop == 'original') return sourcePath;

    try {
      final nativeOutput = await NativeBridge.editPhoto(
        path: sourcePath,
        turns: turns,
        flip: flip,
        crop: crop,
      );
      if (nativeOutput != null) {
        final nativeFile = File(nativeOutput);
        if (await nativeFile.exists() && await nativeFile.length() >= 256) {
          if (mounted) showMessage(context, 'Photo changes applied.');
          return nativeOutput;
        }
      }
    } catch (_) {
      // Some Android codecs are device-specific. Fall back to Dart decoding.
    }

    try {
      final bytes = await File(sourcePath).readAsBytes();
      final edited = await compute(_processOutgoingPhoto, <String, dynamic>{
        'bytes': bytes,
        'turns': turns,
        'flip': flip,
        'crop': crop,
      });
      final dir = await getTemporaryDirectory();
      final output = '${dir.path}/taleempk_photo_${DateTime.now().microsecondsSinceEpoch}.jpg';
      final file = File(output);
      await file.writeAsBytes(edited, flush: true);
      if (!await file.exists() || await file.length() < 256) {
        throw StateError('Edited photo output is empty.');
      }
      if (mounted) showMessage(context, 'Photo changes applied.');
      return output;
    } catch (_) {
      if (mounted) {
        showMessage(
          context,
          'This photo format could not be edited. Try another image or take a new photo.',
        );
      }
      return null;
    }
'''
chat = replace_once(chat, old_apply, new_apply, 'Native photo edit fallback')

# Replace security sheet with accurate native/web E2E wording and a direct web action.
new_encryption = r'''  Future<void> _encryptionInfo() async {
    final hasEncrypted = _threadHasEncryptedMessages;
    await showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (sheet) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(22, 4, 22, 22),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Align(
                alignment: Alignment.centerLeft,
                child: Container(
                  width: 52,
                  height: 52,
                  decoration: BoxDecoration(
                    color: AppColors.success.withValues(alpha: .11),
                    borderRadius: BorderRadius.circular(17),
                  ),
                  child: const Icon(
                    Icons.lock_rounded,
                    color: AppColors.success,
                    size: 27,
                  ),
                ),
              ),
              const SizedBox(height: 14),
              Text(
                hasEncrypted ? 'End-to-end encrypted web chat' : 'Encryption & privacy',
                style: Theme.of(sheet).textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.w900,
                    ),
              ),
              const SizedBox(height: 8),
              Text(
                hasEncrypted
                    ? 'This conversation contains end-to-end encrypted website messages. Their keys stay on the devices that configured encryption, so this native app does not pretend it can decrypt them without native key sync.'
                    : 'TaleemPK protects this app with HTTPS and secure, revocable account sessions. Optional end-to-end encryption is configured in the TaleemPK web chat with your encryption passphrase.',
                style: TextStyle(
                  height: 1.48,
                  color: Theme.of(sheet).colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Theme.of(sheet).colorScheme.surfaceContainerLow,
                  borderRadius: BorderRadius.circular(15),
                ),
                child: const Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(Icons.verified_user_outlined, size: 19, color: AppColors.blue),
                    SizedBox(width: 9),
                    Expanded(
                      child: Text(
                        'Messages sent from the native app use secure transport. They are not labelled end-to-end encrypted unless native encryption keys are available.',
                        style: TextStyle(fontSize: 12, height: 1.4),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: () async {
                  Navigator.pop(sheet);
                  final uri = Uri.parse(
                    'https://taleempk.online/chat.php?c=${widget.conversation.id}',
                  );
                  final opened = await launchUrl(
                    uri,
                    mode: LaunchMode.externalApplication,
                  );
                  if (!opened && mounted) {
                    showMessage(context, 'Could not open TaleemPK web chat.');
                  }
                },
                icon: const Icon(Icons.open_in_new_rounded),
                label: const Text('Open encryption settings on web'),
              ),
            ],
          ),
        ),
      ),
    );
  }
'''
chat = sub_once(
    chat,
    r"  Future<void> _encryptionInfo\(\) async \{.*?\n  \}\n\n  Future<void> _reportUser",
    new_encryption + "\n  Future<void> _reportUser",
    'Encryption info sheet',
)
write(chat_path, chat)

# ---------------------------------------------------------------------------
# Mobile PHP companion: quiz slug, comment edit/delete, notification peek.
# ---------------------------------------------------------------------------
mobile_path = 'flutter/backend/api/mobile.php'
mobile = read(mobile_path)
mobile = replace_once(
    mobile,
    "    'create_comment' => 'comment_create.php',\n",
    "    'create_comment' => 'comment_create.php',\n    'edit_comment'   => 'post_edit.php',\n",
    'Shared edit comment handler',
)

server_blocks = r'''
if ($action === 'delete_comment') {
    require_feature('feature_comments');
    $id = (int) ($_POST['id'] ?? 0);
    $c = fetch_one(
        'SELECT c.*, p.user_id AS post_owner, p.type AS post_type, p.status AS post_status
           FROM comments c JOIN posts p ON p.id=c.post_id WHERE c.id=?',
        [$id]
    );
    if (!$c) { mobile_error('That comment no longer exists.', 404); }
    if ((int) $c['user_id'] !== $uid && !mod_can('comments')) {
        mobile_error('You can only delete your own comments.', 403);
    }
    db_transaction(static function () use ($id, $c): void {
        delete_row('reactions', "target_type='comment' AND target_id=?", [$id]);
        delete_row('notifications', "target_type='comment' AND target_id=?", [$id]);
        q('UPDATE comments SET parent_id=NULL WHERE parent_id=?', [$id]);
        delete_row('comments', 'id=?', [$id]);
        if (($c['status'] ?? 'active') === 'active') {
            q('UPDATE posts SET comments_count=GREATEST(comments_count-1,0) WHERE id=?', [$c['post_id']]);
        }
        if ((int) ($c['is_best_answer'] ?? 0) === 1) {
            q('UPDATE posts SET is_solved=0 WHERE id=?', [$c['post_id']]);
            remove_points_for_target((int) $c['user_id'], 'best_answer', 'comment', $id);
        }
        remove_points_for_target((int) $c['user_id'], 'comment', 'comment', $id);
    });
    mobile_out(['deleted' => true]);
}

if ($action === 'notification_peek') {
    $latestChat = null;
    $row = fetch_one(
        "SELECT m.id,m.conversation_id,m.content,m.enc,m.attachment_name,m.voice_seconds,
                sender.name AS from_name
           FROM messages m
           JOIN conversation_members cm
             ON cm.conversation_id=m.conversation_id AND cm.user_id=?
           JOIN users sender ON sender.id=m.sender_id
          WHERE m.sender_id<>? AND m.status='sent'
            AND m.id>COALESCE(cm.last_read_id,0)
          ORDER BY m.id DESC LIMIT 1",
        [$uid, $uid]
    );
    if ($row) {
        if ((int) ($row['enc'] ?? 0) === 1) {
            $text = 'Sent you an encrypted message';
        } elseif ((int) ($row['voice_seconds'] ?? 0) > 0) {
            $text = 'Sent a voice message';
        } elseif (trim((string) ($row['content'] ?? '')) !== '') {
            $text = excerpt((string) $row['content'], 90);
        } elseif (trim((string) ($row['attachment_name'] ?? '')) !== '') {
            $text = 'Sent a file';
        } else {
            $text = 'Sent you a message';
        }
        $latestChat = [
            'id' => (int) $row['id'],
            'from' => (string) $row['from_name'],
            'text' => $text,
            'conversation' => (int) $row['conversation_id'],
        ];
    }

    $latestNotification = fetch_one(
        "SELECT id,message,type,created_at FROM notifications
          WHERE user_id=? AND is_read=0 AND type<>'message'
          ORDER BY id DESC LIMIT 1",
        [$uid]
    );
    mobile_out([
        'chat_unread' => (int) fetch_col(
            'SELECT COALESCE(SUM(unread_count),0) FROM conversation_members WHERE user_id=?',
            [$uid]
        ),
        'notification_unread' => (int) fetch_col(
            'SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0',
            [$uid]
        ),
        'latest_chat' => $latestChat,
        'latest_notification' => $latestNotification ? [
            'id' => (int) $latestNotification['id'],
            'message' => (string) $latestNotification['message'],
            'type' => (string) $latestNotification['type'],
        ] : null,
    ]);
}
'''
mobile = replace_once(
    mobile,
    """if (isset($nativeSharedHandlers[$action])) {
    require __DIR__ . '/' . $nativeSharedHandlers[$action];
}

if ($action === 'bootstrap') {
""",
    """if (isset($nativeSharedHandlers[$action])) {
    require __DIR__ . '/' . $nativeSharedHandlers[$action];
}
""" + server_blocks + "\nif ($action === 'bootstrap') {\n",
    'Mobile comment delete and notifications',
)
mobile = replace_once(
    mobile,
    """        $rows = fetch_all("SELECT q.id,q.title,q.subject,q.class_grade,q.time_limit,q.attempts_count,
                           (SELECT COUNT(*) FROM quiz_questions qq WHERE qq.quiz_id=q.id) questions
""",
    """        $rows = fetch_all("SELECT q.id,q.slug,q.title,q.subject,q.class_grade,q.time_limit,q.attempts_count,
                           (SELECT COUNT(*) FROM quiz_questions qq WHERE qq.quiz_id=q.id) questions
""",
    'Quiz slug query',
)
mobile = replace_once(
    mobile,
    """            'meta'=>(int)$r['questions'].' questions'.((int)$r['time_limit']?' · '.(int)$r['time_limit'].' min':'').' · '.(int)$r['attempts_count'].' attempts',
            'kind'=>'quiz','done'=>false];
""",
    """            'meta'=>(int)$r['questions'].' questions'.((int)$r['time_limit']?' · '.(int)$r['time_limit'].' min':'').' · '.(int)$r['attempts_count'].' attempts',
            'kind'=>'quiz','done'=>false,
            'route'=>'quiz-take.php?s='.rawurlencode((string)$r['slug'])];
""",
    'Quiz slug route',
)
write(mobile_path, mobile)

# Version bump.
pub_path = 'flutter/pubspec.yaml'
pub = read(pub_path)
pub = replace_once(pub, 'version: 2.8.0+280', 'version: 2.9.0+290', 'Version bump')
write(pub_path, pub)

print('TaleemPK v2.9 quiz/comments/notifications/chat/media patch applied')
