import 'package:flutter/services.dart';

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
